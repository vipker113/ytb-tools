import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import {
  getBacklotEpisodeDetail,
  writeBacklotApprovalDecision,
} from "@/lib/backlot";

export async function POST(
  req: NextRequest,
  ctx: { params: Promise<{ slug: string }> }
) {
  await connection();
  const { slug } = await ctx.params;

  try {
    const body = (await req.json()) as {
      gate?: string;
      decision?: "approved" | "changes_requested";
      notes?: string;
      shotNotes?: Record<string, string>;
    };

    if (
      body.decision !== "approved" &&
      body.decision !== "changes_requested"
    ) {
      return NextResponse.json(
        { error: "Trường decision phải là 'approved' hoặc 'changes_requested'." },
        { status: 400 }
      );
    }

    await writeBacklotApprovalDecision({
      slug,
      gate: body.gate || "storyboard_approval",
      decision: body.decision,
      notes: body.notes || "",
      shotNotes: body.shotNotes || {},
    });

    const detail = await getBacklotEpisodeDetail(slug);
    return NextResponse.json({
      ok: true,
      message:
        body.decision === "approved"
          ? `Đã duyệt Storyboard cho '${slug}'. Giờ có thể chạy stage5-edit --mode master!`
          : `Đã ghi nhận yêu cầu chỉnh sửa Storyboard cho '${slug}'.`,
      detail,
    });
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? err.message
            : "Không thể lưu quyết định duyệt Storyboard.",
      },
      { status: 400 }
    );
  }
}
