import { createReadStream } from "node:fs";
import { readFile, stat } from "node:fs/promises";
import {
  type MacAssetKind,
  resolveMacEpisodeAssetFile,
} from "@/lib/mac-pipeline";

function createSafeWebFileStream(
  filePath: string,
  opts?: { start?: number; end?: number }
): ReadableStream<Uint8Array> {
  const nodeStream = createReadStream(filePath, opts);
  let closed = false;

  return new ReadableStream<Uint8Array>({
    start(controller) {
      nodeStream.on("data", (chunk: Buffer | string) => {
        if (closed) return;
        try {
          const buf =
            typeof chunk === "string"
              ? new TextEncoder().encode(chunk)
              : new Uint8Array(
                  chunk.buffer,
                  chunk.byteOffset,
                  chunk.byteLength
                );
          controller.enqueue(buf);
        } catch {
          closed = true;
          nodeStream.destroy();
        }
      });
      nodeStream.on("end", () => {
        if (closed) return;
        closed = true;
        try {
          controller.close();
        } catch {
          // ignore already closed
        }
      });
      nodeStream.on("error", () => {
        if (closed) return;
        closed = true;
        try {
          controller.close();
        } catch {
          // ignore
        }
      });
    },
    cancel() {
      closed = true;
      nodeStream.destroy();
    },
  });
}

const VALID_ASSETS = new Set<MacAssetKind>([
  "video",
  "primary",
  "variant_b",
  "variant_c",
  "thumbnail_sheet",
  "first_3s_sheet",
  "contact_sheet",
  "ending_sheet",
]);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const slug = (url.searchParams.get("slug") || "").trim();
  const assetRaw = (url.searchParams.get("asset") || "primary").trim();
  const hasVersionParam = Boolean(url.searchParams.get("v"));

  if (!slug || !VALID_ASSETS.has(assetRaw as MacAssetKind)) {
    return new Response("Invalid slug or asset type", { status: 400 });
  }

  const asset = assetRaw as MacAssetKind;
  const resolved = await resolveMacEpisodeAssetFile(slug, asset);
  if (!resolved) {
    return new Response("Asset not found", { status: 404 });
  }

  const fileStat = await stat(resolved.filePath).catch(() => null);
  if (!fileStat || !fileStat.isFile()) {
    return new Response("File unavailable", { status: 404 });
  }

  const etag = `W/"${fileStat.size}-${Math.floor(fileStat.mtimeMs)}"`;
  const cacheHeader = hasVersionParam
    ? "private, max-age=3600, stale-while-revalidate=86400"
    : "private, max-age=15";

  // Image assets (thumbnails & QC sheets)
  if (asset !== "video") {
    if (request.headers.get("if-none-match") === etag) {
      return new Response(null, {
        status: 304,
        headers: {
          ETag: etag,
          "Cache-Control": cacheHeader,
        },
      });
    }

    const buf = await readFile(resolved.filePath);
    return new Response(new Uint8Array(buf), {
      status: 200,
      headers: {
        "Content-Type": resolved.mimeType,
        "Content-Length": String(buf.byteLength),
        ETag: etag,
        "Cache-Control": cacheHeader,
      },
    });
  }

  // Video streaming with HTTP 206 Range support for smooth scrubbing in Safari/Chrome
  const totalSize = fileStat.size;
  const rangeHeader = request.headers.get("range");

  if (rangeHeader) {
    const match = rangeHeader.match(/bytes=(\d*)-(\d*)/);
    if (match) {
      const start = match[1] ? parseInt(match[1], 10) : 0;
      const requestedEnd = match[2] ? parseInt(match[2], 10) : totalSize - 1;
      const end = Math.min(requestedEnd, totalSize - 1);

      if (start >= totalSize || start > end) {
        return new Response(null, {
          status: 416,
          headers: { "Content-Range": `bytes */${totalSize}` },
        });
      }

      const chunkSize = end - start + 1;
      const webStream = createSafeWebFileStream(resolved.filePath, {
        start,
        end,
      });

      return new Response(webStream, {
        status: 206,
        headers: {
          "Content-Range": `bytes ${start}-${end}/${totalSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": String(chunkSize),
          "Content-Type": "video/mp4",
          ETag: etag,
          "Cache-Control": cacheHeader,
        },
      });
    }
  }

  const webFullStream = createSafeWebFileStream(resolved.filePath);
  return new Response(webFullStream, {
    status: 200,
    headers: {
      "Accept-Ranges": "bytes",
      "Content-Length": String(totalSize),
      "Content-Type": "video/mp4",
      ETag: etag,
      "Cache-Control": cacheHeader,
    },
  });
}
