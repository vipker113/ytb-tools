import fs from "node:fs";
import path from "node:path";
import type { NextRequest } from "next/server";
import {
  ensureSessionDir,
  expandHomePath,
  isAllowedVideoFile,
} from "@/lib/reup-studio-server";
import {
  cancelEnhancerRenderJob,
  readEnhancerJobStatus,
  runEnhancerSyncJson,
  startEnhancerRenderJob,
} from "@/lib/video-enhancer-server";

export async function GET(request: NextRequest) {
  try {
    const sp = request.nextUrl.searchParams;
    const sessionId = sp.get("session") || "";
    const jobId = sp.get("jobId") || "";
    if (!sessionId || !jobId) {
      return Response.json(
        { ok: false, error: "Thiếu session hoặc jobId" },
        { status: 400 }
      );
    }

    const status = readEnhancerJobStatus(sessionId, jobId);
    if (!status) {
      return Response.json(
        { ok: false, error: "Không tìm thấy tiến trình render" },
        { status: 404 }
      );
    }
    return Response.json({ ok: true, job: status });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi kiểm tra tiến trình",
      },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const action = String(body.action || "");

    // 1. Scan a local Mac directory for video files
    if (action === "scanFolder") {
      const folderRaw = String(body.folderPath || "~/Downloads");
      const absFolder = expandHomePath(folderRaw);
      if (!fs.existsSync(absFolder) || !fs.statSync(absFolder).isDirectory()) {
        return Response.json(
          { ok: false, error: `Không tìm thấy thư mục: ${absFolder}` },
          { status: 404 }
        );
      }
      const entries = fs
        .readdirSync(absFolder, { withFileTypes: true })
        .filter((d) => d.isFile() && isAllowedVideoFile(d.name))
        .map((d) => {
          const full = path.join(absFolder, d.name);
          const st = fs.statSync(full);
          return {
            name: d.name,
            fullPath: full,
            sizeMb: Math.round((st.size / (1024 * 1024)) * 10) / 10,
            mtimeMs: st.mtimeMs,
          };
        })
        .sort((a, b) => b.mtimeMs - a.mtimeMs)
        .slice(0, 60);

      return Response.json({
        ok: true,
        folderPath: absFolder,
        videos: entries,
      });
    }

    // 2. Load a video directly from a local Mac path (zero file duplication)
    if (action === "loadLocalPath") {
      const rawPath = String(body.localPath || "");
      const absVideo = expandHomePath(rawPath);
      if (!fs.existsSync(absVideo) || !fs.statSync(absVideo).isFile()) {
        return Response.json(
          { ok: false, error: `Không tìm thấy file video: ${absVideo}` },
          { status: 404 }
        );
      }
      if (!isAllowedVideoFile(absVideo)) {
        return Response.json(
          { ok: false, error: "File không phải định dạng video hợp lệ (.mp4, .mov, .webm, .mkv)." },
          { status: 400 }
        );
      }

      const sessionId =
        String(body.sessionId || "") ||
        `enh_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const sessionDir = ensureSessionDir(sessionId);

      const engine = body.engine === "ffmpeg_pro" ? "ffmpeg_pro" : "ai_realesrgan";
      const targetRes = ["1080p", "2k", "4k"].includes(String(body.targetRes))
        ? String(body.targetRes)
        : "1080p";
      const aspectMode = ["shorts_fill", "shorts_blur", "keep_aspect"].includes(
        String(body.aspectMode)
      )
        ? String(body.aspectMode)
        : "shorts_fill";
      const denoise = Number(body.denoise ?? 55);
      const sharpen = Number(body.sharpen ?? 45);
      const faceRestore = body.faceRestore !== false;
      const colorPreset = ["natural", "auto_vivid", "beauty_glow", "cinema_hdr"].includes(
        String(body.colorPreset)
      )
        ? String(body.colorPreset)
        : "auto_vivid";
      const cropBars = body.cropBars !== false;

      const probeRes = await runEnhancerSyncJson([
        "--mode",
        "probe",
        "--video",
        absVideo,
        "--out-dir",
        sessionDir,
      ]);
      const videoInfo = (probeRes.video_info || {}) as Record<string, unknown>;
      const recTs = Number(videoInfo.recommended_ts ?? 1.0);

      const previewRes = await runEnhancerSyncJson([
        "--mode",
        "preview",
        "--video",
        absVideo,
        "--out-dir",
        sessionDir,
        "--timestamp",
        String(recTs),
        "--engine",
        engine,
        "--target-res",
        targetRes,
        "--aspect-mode",
        aspectMode,
        "--denoise",
        String(Math.round(denoise)),
        "--sharpen",
        String(Math.round(sharpen)),
        "--face-restore",
        String(faceRestore),
        "--color-preset",
        colorPreset,
        "--crop-bars",
        String(cropBars),
      ]);

      return Response.json({
        ok: true,
        sessionId: path.basename(sessionDir),
        videoPath: absVideo,
        originalName: path.basename(absVideo),
        videoInfo,
        preview: previewRes,
      });
    }

    // 3. Generate Before / After 1-Frame Comparison Preview (<1s-2s)
    if (action === "preview") {
      const sessionId = String(body.sessionId || "");
      const videoPath = expandHomePath(String(body.videoPath || ""));
      if (!sessionId || !fs.existsSync(videoPath)) {
        return Response.json(
          { ok: false, error: "Phiên video không tồn tại. Vui lòng chọn lại video." },
          { status: 400 }
        );
      }

      const sessionDir = ensureSessionDir(sessionId);
      const timestamp = Math.max(0, Number(body.timestamp ?? 1.0));
      const engine = body.engine === "ffmpeg_pro" ? "ffmpeg_pro" : "ai_realesrgan";
      const targetRes = ["1080p", "2k", "4k"].includes(String(body.targetRes))
        ? String(body.targetRes)
        : "1080p";
      const aspectMode = ["shorts_fill", "shorts_blur", "keep_aspect"].includes(
        String(body.aspectMode)
      )
        ? String(body.aspectMode)
        : "shorts_fill";
      const denoise = Math.max(0, Math.min(100, Number(body.denoise ?? 55)));
      const sharpen = Math.max(0, Math.min(100, Number(body.sharpen ?? 45)));
      const faceRestore = body.faceRestore !== false;
      const colorPreset = ["natural", "auto_vivid", "beauty_glow", "cinema_hdr"].includes(
        String(body.colorPreset)
      )
        ? String(body.colorPreset)
        : "auto_vivid";
      const cropBars = body.cropBars !== false;

      const previewRes = await runEnhancerSyncJson([
        "--mode",
        "preview",
        "--video",
        videoPath,
        "--out-dir",
        sessionDir,
        "--timestamp",
        String(timestamp),
        "--engine",
        engine,
        "--target-res",
        targetRes,
        "--aspect-mode",
        aspectMode,
        "--denoise",
        String(Math.round(denoise)),
        "--sharpen",
        String(Math.round(sharpen)),
        "--face-restore",
        String(faceRestore),
        "--color-preset",
        colorPreset,
        "--crop-bars",
        String(cropBars),
      ]);

      return Response.json({
        ok: true,
        preview: previewRes,
      });
    }

    // 4. Start asynchronous full-video enhancement render job
    if (action === "startRender") {
      const sessionId = String(body.sessionId || "");
      const videoPath = expandHomePath(String(body.videoPath || ""));
      const fileName = String(body.fileName || path.basename(videoPath) || "video.mp4");
      if (!sessionId || !fs.existsSync(videoPath)) {
        return Response.json(
          { ok: false, error: "Không tìm thấy video nguồn để nâng cấp." },
          { status: 400 }
        );
      }

      const engine = body.engine === "ffmpeg_pro" ? "ffmpeg_pro" : "ai_realesrgan";
      const targetRes = (
        ["1080p", "2k", "4k"].includes(String(body.targetRes))
          ? String(body.targetRes)
          : "1080p"
      ) as "1080p" | "2k" | "4k";
      const aspectMode = (
        ["shorts_fill", "shorts_blur", "keep_aspect"].includes(String(body.aspectMode))
          ? String(body.aspectMode)
          : "shorts_fill"
      ) as "shorts_fill" | "shorts_blur" | "keep_aspect";
      const denoise = Math.max(0, Math.min(100, Number(body.denoise ?? 55)));
      const sharpen = Math.max(0, Math.min(100, Number(body.sharpen ?? 45)));
      const faceRestore = body.faceRestore !== false;
      const colorPreset = (
        ["natural", "auto_vivid", "beauty_glow", "cinema_hdr"].includes(String(body.colorPreset))
          ? String(body.colorPreset)
          : "auto_vivid"
      ) as "natural" | "auto_vivid" | "beauty_glow" | "cinema_hdr";
      const cropBars = body.cropBars !== false;
      const fpsMode = body.fpsMode === "smooth_60fps" ? "smooth_60fps" : "keep";

      const started = startEnhancerRenderJob({
        sessionId,
        videoPath,
        fileName,
        engine,
        targetRes,
        aspectMode,
        denoise,
        sharpen,
        faceRestore,
        colorPreset,
        cropBars,
        fpsMode,
      });

      return Response.json({
        ok: true,
        jobId: started.jobId,
        outFile: started.outFile,
      });
    }

    // 5. Cancel an in-progress render job
    if (action === "cancelRender") {
      const sessionId = String(body.sessionId || "");
      const jobId = String(body.jobId || "");
      if (!sessionId || !jobId) {
        return Response.json({ ok: false, error: "Thiếu jobId" }, { status: 400 });
      }
      cancelEnhancerRenderJob(sessionId, jobId);
      return Response.json({ ok: true });
    }

    // 6. Save enhanced video directly to a local Mac folder (e.g. ~/Downloads)
    if (action === "saveToMacFolder") {
      const sessionId = String(body.sessionId || "");
      const outFile = path.basename(String(body.outFile || ""));
      const targetFolder = expandHomePath(String(body.targetFolder || "~/Downloads"));
      const sessionDir = ensureSessionDir(sessionId);
      const srcPath = path.join(sessionDir, outFile);

      if (!outFile || !fs.existsSync(srcPath)) {
        return Response.json(
          { ok: false, error: "Không tìm thấy file video đã nâng cấp." },
          { status: 404 }
        );
      }

      fs.mkdirSync(targetFolder, { recursive: true });
      const cleanDestName = path.basename(String(body.saveFileName || outFile));
      const destPath = path.join(targetFolder, cleanDestName);
      fs.copyFileSync(srcPath, destPath);

      return Response.json({
        ok: true,
        savedPath: destPath,
      });
    }

    return Response.json({ ok: false, error: `Unknown action: ${action}` }, { status: 400 });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi xử lý yêu cầu nâng cấp video",
      },
      { status: 500 }
    );
  }
}
