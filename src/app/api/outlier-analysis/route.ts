import { NextRequest, NextResponse } from "next/server";
import { connection } from "next/server";
import {
  enqueueOutlierAnalysisJob,
  getOutlierAnalysisRecord,
  OUTLIER_VIDEO_ID_RE,
  type OutlierAnalysisMode,
} from "@/lib/outlier-analysis";

export async function GET(req: NextRequest) {
  await connection();
  const videoId = (req.nextUrl.searchParams.get("videoId") || "").trim();
  if (!OUTLIER_VIDEO_ID_RE.test(videoId)) {
    return NextResponse.json(
      { error: "videoId phải đúng định dạng 11 ký tự YouTube ID." },
      { status: 400 }
    );
  }
  try {
    const record = await getOutlierAnalysisRecord(videoId);
    return NextResponse.json(record);
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? err.message
            : "Không thể đọc trạng thái giải phẫu nhịp dựng.",
      },
      { status: 400 }
    );
  }
}

export async function POST(req: NextRequest) {
  await connection();
  try {
    const body = (await req.json()) as {
      videoId?: string;
      mode?: OutlierAnalysisMode;
      force?: boolean;
    };
    const videoId = (body.videoId || "").trim();
    if (!OUTLIER_VIDEO_ID_RE.test(videoId)) {
      return NextResponse.json(
        { error: "videoId phải đúng định dạng 11 ký tự YouTube ID." },
        { status: 400 }
      );
    }

    const record = await enqueueOutlierAnalysisJob({
      videoId,
      mode: body.mode === "transcript_only" ? "transcript_only" : "download",
      force: Boolean(body.force),
    });
    return NextResponse.json(record);
  } catch (err) {
    return NextResponse.json(
      {
        error:
          err instanceof Error
            ? err.message
            : "Không thể khởi chạy giải phẫu nhịp dựng.",
      },
      { status: 400 }
    );
  }
}
