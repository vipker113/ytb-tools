import fs from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import type { NextRequest } from "next/server";
import {
  ensureSessionDir,
  expandHomePath,
  isAllowedAudioFile,
  isAllowedVideoFile,
} from "@/lib/reup-studio-server";

function getMimeType(filePath: string): string {
  const ext = path.extname(filePath).toLowerCase();
  if (ext === ".png") return "image/png";
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".webm") return "video/webm";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".mp4" || ext === ".m4v") return "video/mp4";
  if (ext === ".mp3") return "audio/mpeg";
  if (ext === ".m4a" || ext === ".aac") return "audio/mp4";
  if (ext === ".wav") return "audio/wav";
  if (ext === ".ogg") return "audio/ogg";
  return "application/octet-stream";
}

function streamFileWithRange(
  absPath: string,
  request: NextRequest,
  downloadName: string | null
): Response {
  const stat = fs.statSync(absPath);
  const fileSize = stat.size;
  const mime = getMimeType(absPath);

  const extraHeaders: Record<string, string> = {};
  if (downloadName) {
    const cleanDl = path.basename(downloadName).replace(/["\r\n]/g, "");
    extraHeaders["Content-Disposition"] = `attachment; filename="${cleanDl}"`;
  }

  const range = request.headers.get("range");
  if (range && !downloadName) {
    const parts = range.replace(/bytes=/, "").split("-");
    const start = Number.parseInt(parts[0], 10);
    const end = parts[1] ? Number.parseInt(parts[1], 10) : fileSize - 1;
    const chunkSize = end - start + 1;
    const stream = fs.createReadStream(absPath, { start, end });
    return new Response(Readable.toWeb(stream) as ReadableStream, {
      status: 206,
      headers: {
        "Content-Range": `bytes ${start}-${end}/${fileSize}`,
        "Accept-Ranges": "bytes",
        "Content-Length": String(chunkSize),
        "Content-Type": mime,
        ...extraHeaders,
      },
    });
  }

  const stream = fs.createReadStream(absPath);
  return new Response(Readable.toWeb(stream) as ReadableStream, {
    status: 200,
    headers: {
      "Content-Length": String(fileSize),
      "Accept-Ranges": "bytes",
      "Content-Type": mime,
      "Cache-Control": "no-store",
      ...extraHeaders,
    },
  });
}

export async function GET(request: NextRequest) {
  try {
    const sp = request.nextUrl.searchParams;
    const videoPathParam = sp.get("videoPath");
    const downloadName = sp.get("download");

    // 1. Stream local video/audio file with HTTP Range support
    if (videoPathParam) {
      const absMedia = expandHomePath(videoPathParam);
      if (
        !fs.existsSync(absMedia) ||
        (!isAllowedVideoFile(absMedia) && !isAllowedAudioFile(absMedia))
      ) {
        return new Response("Not found", { status: 404 });
      }
      return streamFileWithRange(absMedia, request, downloadName);
    }

    // 2. Serve session file (HD thumbnail JPG/PNG, remastered MP4, or custom BGM audio)
    const sessionId = sp.get("session") || "";
    const file = sp.get("file") || "";
    if (!sessionId || !file) {
      return new Response("Missing session or file", { status: 400 });
    }
    const sessionDir = ensureSessionDir(sessionId);
    const safeName = path.basename(file);
    const targetPath = path.join(sessionDir, safeName);
    if (!fs.existsSync(targetPath)) {
      return new Response("Session file not found", { status: 404 });
    }

    if (isAllowedVideoFile(safeName) || isAllowedAudioFile(safeName)) {
      return streamFileWithRange(targetPath, request, downloadName);
    }

    const buf = fs.readFileSync(targetPath);
    const headers: Record<string, string> = {
      "Content-Type": getMimeType(safeName),
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
