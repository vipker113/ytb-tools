import { watch, type FSWatcher } from "node:fs";
import { stat } from "node:fs/promises";
import path from "node:path";
import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import { resolveBacklotEpisodeDir } from "@/lib/backlot";

export async function GET(
  req: NextRequest,
  ctx: { params: Promise<{ slug: string }> }
) {
  await connection();
  const { slug } = await ctx.params;
  const resolved = await resolveBacklotEpisodeDir(slug);
  if (!resolved) {
    return NextResponse.json(
      { error: `Không tìm thấy tập '${slug}'.` },
      { status: 404 }
    );
  }

  const encoder = new TextEncoder();
  const boardDir = path.join(resolved.episodeDir, "board");
  const hasBoardDir = await stat(boardDir)
    .then((s) => s.isDirectory())
    .catch(() => false);

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      let closed = false;
      let debounceTimer: ReturnType<typeof setTimeout> | null = null;
      const watchers: FSWatcher[] = [];

      const safeSend = (chunk: string) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(chunk));
        } catch {
          cleanup();
        }
      };

      const scheduleChanged = (filename: string | null) => {
        if (closed) return;
        if (filename && filename.startsWith(".") && filename.endsWith(".tmp")) {
          return;
        }
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          safeSend(
            `event: changed\ndata: ${JSON.stringify({
              slug,
              file: filename || null,
              ts: new Date().toISOString(),
            })}\n\n`
          );
        }, 300);
      };

      try {
        watchers.push(
          watch(resolved.episodeDir, (_eventType, filename) => {
            scheduleChanged(filename ? String(filename) : null);
          })
        );
      } catch {
        // ignore watcher error if directory vanished
      }

      if (hasBoardDir) {
        try {
          watchers.push(
            watch(boardDir, (_eventType, filename) => {
              scheduleChanged(filename ? `board/${String(filename)}` : "board");
            })
          );
        } catch {
          // ignore
        }
      }

      const heartbeat = setInterval(() => {
        safeSend(`: heartbeat ${Date.now()}\n\n`);
      }, 15000);

      const cleanup = () => {
        if (closed) return;
        closed = true;
        if (debounceTimer) clearTimeout(debounceTimer);
        clearInterval(heartbeat);
        for (const w of watchers) {
          try {
            w.close();
          } catch {
            // ignore
          }
        }
        try {
          controller.close();
        } catch {
          // ignore
        }
      };

      req.signal.addEventListener("abort", cleanup, { once: true });

      safeSend(
        `event: connected\ndata: ${JSON.stringify({
          slug,
          ts: new Date().toISOString(),
        })}\n\n`
      );
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
