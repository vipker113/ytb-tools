import { readFile } from "node:fs/promises";
import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import { resolveSafeBacklotMediaPath } from "@/lib/backlot";

export async function GET(req: NextRequest) {
  await connection();
  const slug = req.nextUrl.searchParams.get("slug") || "";
  const relFile = req.nextUrl.searchParams.get("file") || "";
  const absPath = await resolveSafeBacklotMediaPath(slug, relFile);
  if (!absPath) {
    return NextResponse.json(
      { error: "Tệp hình ảnh Backlot không tồn tại hoặc không hợp lệ." },
      { status: 404 }
    );
  }

  try {
    const bytes = await readFile(absPath);
    return new NextResponse(new Uint8Array(bytes), {
      status: 200,
      headers: {
        "Content-Type": "image/jpeg",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Không thể đọc tệp hình ảnh Backlot." },
      { status: 500 }
    );
  }
}
