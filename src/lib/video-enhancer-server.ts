import { type ChildProcess, spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { ensureSessionDir, resolvePythonBin } from "./reup-studio-server";

interface ActiveEnhancerJob {
  jobId: string;
  sessionId: string;
  outPath: string;
  progressFile: string;
  child: ChildProcess;
  startedAt: number;
}

const globalForEnhancer = globalThis as unknown as {
  __videoEnhancerJobs?: Map<string, ActiveEnhancerJob>;
};

function getJobsMap(): Map<string, ActiveEnhancerJob> {
  if (!globalForEnhancer.__videoEnhancerJobs) {
    globalForEnhancer.__videoEnhancerJobs = new Map<string, ActiveEnhancerJob>();
  }
  return globalForEnhancer.__videoEnhancerJobs;
}

export function resolveEnhancerScript(): string {
  return path.resolve(process.cwd(), "scripts/ai_video_enhancer.py");
}

export function runEnhancerSyncJson(args: string[]): Promise<Record<string, unknown>> {
  const py = resolvePythonBin();
  const script = resolveEnhancerScript();

  return new Promise((resolve, reject) => {
    const child = spawn(py, [script, ...args], {
      env: {
        ...process.env,
        OPENCV_LOG_LEVEL: "OFF",
      },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      const lines = stdout
        .trim()
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.startsWith("{") && l.endsWith("}"));
      const lastJsonLine = lines[lines.length - 1];
      if (lastJsonLine) {
        try {
          const parsed = JSON.parse(lastJsonLine);
          if (parsed.ok === false) {
            reject(new Error(String(parsed.error || "Lỗi xử lý nâng cấp video")));
            return;
          }
          resolve(parsed);
          return;
        } catch {
          // fall through
        }
      }
      reject(
        new Error(
          stderr.trim().slice(-450) ||
            stdout.trim().slice(-450) ||
            `Enhancer exited with code ${code}`
        )
      );
    });
  });
}

export interface StartEnhancerRenderOptions {
  sessionId: string;
  videoPath: string;
  fileName: string;
  engine: "ai_realesrgan" | "ffmpeg_pro";
  targetRes: "1080p" | "2k" | "4k";
  aspectMode: "shorts_fill" | "shorts_blur" | "keep_aspect";
  denoise: number;
  sharpen: number;
  faceRestore: boolean;
  colorPreset: "natural" | "auto_vivid" | "beauty_glow" | "cinema_hdr";
  cropBars: boolean;
  fpsMode: "keep" | "smooth_60fps";
}

export function startEnhancerRenderJob(opts: StartEnhancerRenderOptions): {
  jobId: string;
  outFile: string;
  outPath: string;
} {
  const sessionDir = ensureSessionDir(opts.sessionId);
  const jobId = `job_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
  const stem =
    path
      .basename(opts.fileName, path.extname(opts.fileName))
      .replace(/[^a-zA-Z0-9_-]/g, "_")
      .slice(0, 48) || "video";

  const fmtTag = opts.aspectMode !== "keep_aspect" ? "SHORTS_" : "";
  const tag =
    opts.engine === "ai_realesrgan"
      ? `${fmtTag}AI_${opts.targetRes.toUpperCase()}`
      : `${fmtTag}PRO_${opts.targetRes.toUpperCase()}`;
  const outFile = `${stem}_${tag}_${jobId.slice(-5)}.mp4`;
  const outPath = path.join(sessionDir, outFile);
  const progressFile = path.join(sessionDir, `${jobId}.json`);

  const initialPayload = {
    status: "running",
    stage:
      opts.engine === "ai_realesrgan"
        ? "Đang khởi động mạng nơ-ron Real-ESRGAN trên GPU Apple Silicon..."
        : "Đang khởi tạo đường ống FFmpeg Pro VideoToolbox...",
    percent: 1,
    processed_frames: 0,
    total_frames: 0,
    fps: 0,
    eta_s: null,
    out_file: outFile,
  };
  fs.writeFileSync(progressFile, JSON.stringify(initialPayload), "utf-8");

  const py = resolvePythonBin();
  const script = resolveEnhancerScript();
  const cliArgs = [
    script,
    "--mode",
    "render",
    "--video",
    opts.videoPath,
    "--out",
    outPath,
    "--progress-file",
    progressFile,
    "--engine",
    opts.engine,
    "--target-res",
    opts.targetRes,
    "--aspect-mode",
    opts.aspectMode,
    "--denoise",
    String(Math.round(opts.denoise)),
    "--sharpen",
    String(Math.round(opts.sharpen)),
    "--face-restore",
    String(Boolean(opts.faceRestore)),
    "--color-preset",
    opts.colorPreset,
    "--crop-bars",
    String(Boolean(opts.cropBars)),
    "--fps-mode",
    opts.fpsMode,
  ];

  const child = spawn(py, cliArgs, {
    env: {
      ...process.env,
      OPENCV_LOG_LEVEL: "OFF",
    },
  });

  let stderrBuf = "";
  child.stderr.on("data", (chunk) => {
    stderrBuf += chunk.toString();
  });

  const jobs = getJobsMap();
  jobs.set(jobId, {
    jobId,
    sessionId: path.basename(sessionDir),
    outPath,
    progressFile,
    child,
    startedAt: Date.now(),
  });

  child.on("close", (code) => {
    jobs.delete(jobId);
    try {
      if (fs.existsSync(progressFile)) {
        const current = JSON.parse(fs.readFileSync(progressFile, "utf-8"));
        if (current.status === "cancelled") {
          return;
        }
        if (current.status !== "completed" && code !== 0) {
          fs.writeFileSync(
            progressFile,
            JSON.stringify({
              ok: false,
              status: "error",
              error:
                current.error ||
                stderrBuf.trim().slice(-400) ||
                `Quá trình nâng cấp kết thúc với mã lỗi ${code}`,
            }),
            "utf-8"
          );
        }
      }
    } catch {
      // ignore
    }
  });

  return { jobId, outFile, outPath };
}

export function readEnhancerJobStatus(
  sessionId: string,
  jobId: string
): Record<string, unknown> | null {
  const sessionDir = ensureSessionDir(sessionId);
  const safeJob = path.basename(jobId).replace(/[^a-zA-Z0-9_-]/g, "");
  const progressFile = path.join(sessionDir, `${safeJob}.json`);
  if (!fs.existsSync(progressFile)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(progressFile, "utf-8"));
  } catch {
    return { status: "running", stage: "Đang xử lý khung hình...", percent: 5 };
  }
}

export function cancelEnhancerRenderJob(sessionId: string, jobId: string): boolean {
  const jobs = getJobsMap();
  const active = jobs.get(jobId);
  const sessionDir = ensureSessionDir(sessionId);
  const safeJob = path.basename(jobId).replace(/[^a-zA-Z0-9_-]/g, "");
  const progressFile = path.join(sessionDir, `${safeJob}.json`);

  if (active) {
    try {
      active.child.kill("SIGTERM");
    } catch {
      // ignore
    }
    jobs.delete(jobId);
  }

  try {
    fs.writeFileSync(
      progressFile,
      JSON.stringify({
        ok: false,
        status: "cancelled",
        error: "Đã dừng quá trình render theo yêu cầu.",
      }),
      "utf-8"
    );
  } catch {
    // ignore
  }
  return Boolean(active);
}
