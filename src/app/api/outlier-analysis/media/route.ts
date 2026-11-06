import { readFile } from "node:fs/promises";
import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import { resolveSafeOutlierMediaPath } from "@/lib/outlier-analysis";

export async function GET(req: NextRequest) {
  await connection();
  const videoId = (req.nextUrl.searchParams.get("videoId") || "").trim();
  const relFile = (req.nextUrl.searchParams.get("file") || "").trim();
  const absPath = await resolveSafeOutlierMediaPath(videoId, relFile);
  if (!absPath) {
    return NextResponse.json(
      { error: "Không tìm thấy keyframe giải phẫu hoặc đường dẫn không hợp lệ." },
      { status: 404 }
    );
  }

  try {
    const bytes = await readFile(/*turbopackIgnore: true*/ absPath);
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": "image/jpeg",
        "Cache-Control": "private, max-age=300",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Không thể đọc tệp keyframe giải phẫu." },
      { status: 500 }
    );
  }
}
