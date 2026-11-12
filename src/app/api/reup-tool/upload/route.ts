import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import { pipeline } from "node:stream/promises";
import type { ReadableStream as NodeReadableStream } from "node:stream/web";
import type { NextRequest } from "next/server";
import {
  ensureSessionDir,
  isAllowedVideoFile,
  runBeautyAnalyzer,
} from "@/lib/reup-studio-server";

export async function POST(request: NextRequest) {
  try {
    const url = request.nextUrl;
    const rawName = url.searchParams.get("name") || "video.mp4";
    const enhanceMode = url.searchParams.get("enhance") || "beauty_glow";
    const sessionId =
      url.searchParams.get("session") ||
      `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    const ext = path.extname(rawName).toLowerCase() || ".mp4";
    const safeStem =
      path
        .basename(rawName, ext)
        .replace(/[^a-zA-Z0-9_-]/g, "_")
        .slice(0, 80) || "video";
    const safeFileName = `${safeStem}${ext}`;

    if (!isAllowedVideoFile(safeFileName)) {
      return Response.json(
        {
          ok: false,
          error: "Định dạng không hỗ trợ. Vui lòng chọn video .mp4, .mov, .webm hoặc .mkv.",
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

    const result = await runBeautyAnalyzer([
      "scan",
      "--video",
      savedVideoPath,
      "--out-dir",
      sessionDir,
      "--top-k",
      "6",
      "--enhance",
      ["beauty_glow", "crisp_hd", "raw_hd"].includes(enhanceMode)
        ? enhanceMode
        : "beauty_glow",
    ]);

    return Response.json({
      ...result,
      ok: true,
      sessionId: path.basename(sessionDir),
      videoPath: savedVideoPath,
      originalName: rawName,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi xử lý video",
      },
      { status: 500 }
    );
  }
}
