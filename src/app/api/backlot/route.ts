import { NextResponse } from "next/server";
import { connection } from "next/server";
import { listBacklotEpisodes } from "@/lib/backlot";

export async function GET() {
  await connection();
  try {
    const episodes = await listBacklotEpisodes();
    return NextResponse.json({ episodes });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? err.message
            : "Không thể tải danh sách Studio Backlot.",
      },
      { status: 500 }
    );
  }
}
