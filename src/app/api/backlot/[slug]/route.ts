import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import { getBacklotEpisodeDetail } from "@/lib/backlot";

export async function GET(
  _req: NextRequest,
  ctx: { params: Promise<{ slug: string }> }
) {
  await connection();
  const { slug } = await ctx.params;
  const detail = await getBacklotEpisodeDetail(slug);
  if (!detail) {
    return NextResponse.json(
      { error: `Không tìm thấy tập '${slug}' trong Studio Backlot.` },
      { status: 404 }
    );
  }
  return NextResponse.json(detail);
}
