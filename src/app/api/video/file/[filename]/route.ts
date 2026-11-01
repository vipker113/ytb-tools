import { readFile, stat } from "node:fs/promises";
import { connection } from "next/server";
import { getGeneratedVideoPath } from "@/lib/video-generator";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ filename: string }> }
) {
  await connection();
  const { filename } = await params;
  const filePath = getGeneratedVideoPath(decodeURIComponent(filename));

  try {
    const info = await stat(filePath);
    const total = info.size;
    const range = request.headers.get("range");
    const buf = await readFile(filePath);

    if (range) {
      const match = /bytes=(\d+)-(\d*)/.exec(range);
      if (match) {
        const start = Number(match[1]);
        const end = match[2] ? Math.min(total - 1, Number(match[2])) : total - 1;
        const slice = buf.subarray(start, end + 1);
        return new Response(slice, {
          status: 206,
          headers: {
            "Content-Range": `bytes ${start}-${end}/${total}`,
            "Accept-Ranges": "bytes",
            "Content-Length": String(slice.length),
            "Content-Type": "video/mp4",
          },
        });
      }
    }

    return new Response(buf, {
      status: 200,
      headers: {
        "Content-Length": String(total),
        "Accept-Ranges": "bytes",
        "Content-Type": "video/mp4",
        "Content-Disposition": `inline; filename="${encodeURIComponent(
          filename
        )}"`,
      },
    });
  } catch {
    return Response.json(
      { error: "Không tìm thấy file video." },
      { status: 404 }
    );
  }
}
