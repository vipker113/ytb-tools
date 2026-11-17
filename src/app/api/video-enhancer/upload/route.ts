import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import type { NextRequest } from "next/server";
import { ensureSessionDir, isAllowedVideoFile } from "@/lib/reup-studio-server";
import { runEnhancerSyncJson } from "@/lib/video-enhancer-server";

export async function POST(request: NextRequest) {
  try {
    const url = request.nextUrl;
    const rawName = url.searchParams.get("name") || "video.mp4";
    const engine = url.searchParams.get("engine") === "ffmpeg_pro" ? "ffmpeg_pro" : "ai_realesrgan";
    const targetRes = ["1080p", "2k", "4k"].includes(url.searchParams.get("targetRes") || "")
      ? (url.searchParams.get("targetRes") as string)
      : "1080p";
    const aspectMode = ["shorts_fill", "shorts_blur", "keep_aspect"].includes(
      url.searchParams.get("aspectMode") || ""
    )
      ? (url.searchParams.get("aspectMode") as string)
      : "shorts_fill";
    const sessionId =
      url.searchParams.get("session") ||
      `enh_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const ext = path.extname(rawName).toLowerCase() || ".mp4";
    const safeStem =
      path
        .basename(rawName, ext)
        .replace(/[^a-zA-Z0-9_-]/g, "_")
        .slice(0, 72) || "video";
    const safeFileName = `${safeStem}${ext}`;

    if (!isAllowedVideoFile(safeFileName)) {
      return Response.json(
        {
          ok: false,
          error: "Định dạng không hỗ trợ. Vui lòng chọn file .mp4, .mov, .webm, .mkv hoặc .m4v.",
        },
        { status: 400 }
      );
    }

    if (!request.body) {
      return Response.json(
        { ok: false, error: "Không nhận được dữ liệu file video." },
        { status: 400 }
      );
    }

    const sessionDir = ensureSessionDir(sessionId);
    const savedVideoPath = path.join(sessionDir, safeFileName);

    const nodeStream = Readable.fromWeb(request.body as unknown as NodeReadableStream);
    const writeStream = fs.createWriteStream(savedVideoPath);
    await pipeline(nodeStream, writeStream);

    const probeRes = await runEnhancerSyncJson([
      "--mode",
      "probe",
      "--video",
      savedVideoPath,
      "--out-dir",
      sessionDir,
    ]);

    const videoInfo = (probeRes.video_info || {}) as Record<string, unknown>;
    const recTs = Number(videoInfo.recommended_ts ?? 1.0);

    const previewRes = await runEnhancerSyncJson([
      "--mode",
      "preview",
      "--video",
      savedVideoPath,
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
      "55",
      "--sharpen",
      "45",
      "--face-restore",
      "true",
      "--color-preset",
      "auto_vivid",
      "--crop-bars",
      "true",
    ]);

    return Response.json({
      ok: true,
      sessionId: path.basename(sessionDir),
      videoPath: savedVideoPath,
      originalName: rawName,
      videoInfo,
      preview: previewRes,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi đọc & phân tích video",
      },
      { status: 500 }
    );
  }
}
