import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import type { NextRequest } from "next/server";
import {
  ensureSessionDir,
  expandHomePath,
  isAllowedVideoFile,
} from "@/lib/reup-studio-server";

export async function GET(request: NextRequest) {
  try {
    const sp = request.nextUrl.searchParams;
    const videoPathParam = sp.get("videoPath");

    // 1. Stream local video file with HTTP Range support for smooth scrubbing
    if (videoPathParam) {
      const absVideo = expandHomePath(videoPathParam);
      if (!fs.existsSync(absVideo) || !isAllowedVideoFile(absVideo)) {
        return new Response("Not found", { status: 404 });
      }
      const stat = fs.statSync(absVideo);
      const fileSize = stat.size;
      const ext = path.extname(absVideo).toLowerCase();
      const mime =
        ext === ".webm"
          ? "video/webm"
          : ext === ".mov"
          ? "video/quicktime"
          : "video/mp4";

      const range = request.headers.get("range");
      if (range) {
        const parts = range.replace(/bytes=/, "").split("-");
        const start = Number.parseInt(parts[0], 10);
        const end = parts[1] ? Number.parseInt(parts[1], 10) : fileSize - 1;
        const chunkSize = end - start + 1;
        const stream = fs.createReadStream(absVideo, { start, end });
        return new Response(Readable.toWeb(stream) as ReadableStream, {
          status: 206,
          headers: {
            "Content-Range": `bytes ${start}-${end}/${fileSize}`,
            "Accept-Ranges": "bytes",
            "Content-Length": String(chunkSize),
            "Content-Type": mime,
          },
        });
      }

      const stream = fs.createReadStream(absVideo);
      return new Response(Readable.toWeb(stream) as ReadableStream, {
        status: 200,
        headers: {
          "Content-Length": String(fileSize),
          "Accept-Ranges": "bytes",
          "Content-Type": mime,
        },
      });
    }

    // 2. Serve extracted HD thumbnail JPG / PNG
    const sessionId = sp.get("session") || "";
    const file = sp.get("file") || "";
    if (!sessionId || !file) {
      return new Response("Missing session or file", { status: 400 });
    }
    const sessionDir = ensureSessionDir(sessionId);
    const safeName = path.basename(file);
    const imgPath = path.join(sessionDir, safeName);
    if (!fs.existsSync(imgPath)) {
      return new Response("Thumbnail not found", { status: 404 });
    }

    const buf = fs.readFileSync(imgPath);
    const isPng = safeName.toLowerCase().endsWith(".png");
    const downloadName = sp.get("download");

    const headers: Record<string, string> = {
      "Content-Type": isPng ? "image/png" : "image/jpeg",
      "Cache-Control": "no-store",
    };
    if (downloadName) {
      const cleanDl = path.basename(downloadName).replace(/["\r\n]/g, "");
      headers["Content-Disposition"] = `attachment; filename="${cleanDl}"`;
    }

    return new Response(buf, { status: 200, headers });
  } catch {
    return new Response("Internal error", { status: 500 });
  }
}
