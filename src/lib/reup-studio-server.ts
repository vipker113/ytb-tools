import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export const REUP_TMP_ROOT = path.join(os.tmpdir(), "ytb-reup-studio");

const VIDEO_EXTS = new Set([".mp4", ".mov", ".webm", ".mkv", ".m4v"]);
const AUDIO_EXTS = new Set([".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"]);

export function expandHomePath(rawPath: string): string {
  const trimmed = rawPath.trim().replace(/^["']|["']$/g, "");
  if (trimmed === "~") return os.homedir();
  if (trimmed.startsWith("~/")) {
    return path.join(os.homedir(), trimmed.slice(2));
  }
  return path.resolve(trimmed);
}

export function resolvePythonBin(): string {
  const candidates = [
    path.resolve(process.cwd(), "../youtube-shorts-channel/.venv/bin/python"),
    path.resolve(process.cwd(), ".venv/bin/python"),
    "/opt/homebrew/bin/python3",
    "python3",
  ];
  for (const c of candidates) {
    if (c === "python3" || fs.existsSync(c)) {
      return c;
    }
  }
  return "python3";
}

export function resolveAnalyzerScript(): string {
  return path.resolve(process.cwd(), "scripts/beauty_frame_analyzer.py");
}

export function ensureSessionDir(sessionId: string): string {
  const cleanId = sessionId.replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 64) || `sess_${Date.now()}`;
  const dir = path.join(REUP_TMP_ROOT, cleanId);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

export function isAllowedVideoFile(filePath: string): boolean {
  return VIDEO_EXTS.has(path.extname(filePath).toLowerCase());
}

export function isAllowedAudioFile(filePath: string): boolean {
  return AUDIO_EXTS.has(path.extname(filePath).toLowerCase());
}

export function resolveBuiltinBgmPath(trackId: string): string {
  const safeFile = path.basename(trackId);
  return path.resolve(process.cwd(), "public/reup-bgm", safeFile);
}

export function runVideoRemaster(args: string[]): Promise<Record<string, unknown>> {
  const py = resolvePythonBin();
  const script = path.resolve(process.cwd(), "scripts/reup_video_remaster.py");

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
            reject(new Error(String(parsed.error || "Lỗi nâng cấp video")));
            return;
          }
          resolve(parsed);
          return;
        } catch {
          // Fall through
        }
      }
      reject(
        new Error(
          stderr.trim().slice(-400) ||
            stdout.trim().slice(-400) ||
            `Remaster exited with code ${code}`
        )
      );
    });
  });
}

export async function runBeautyAnalyzer(args: string[]): Promise<Record<string, unknown>> {
  const py = resolvePythonBin();
  const script = resolveAnalyzerScript();

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
            reject(new Error(String(parsed.error || "Lỗi phân tích khung hình video")));
            return;
          }
          resolve(parsed);
          return;
        } catch {
          // Fall through to error
        }
      }
      reject(
        new Error(
          stderr.trim().slice(-400) ||
            stdout.trim().slice(-400) ||
            `Analyzer exited with code ${code}`
        )
      );
    });
  });
}
