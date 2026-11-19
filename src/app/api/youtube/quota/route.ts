import { NextResponse } from "next/server";
import {
  calibrateYoutubeQuota,
  getYoutubeQuotaSummary,
} from "@/lib/youtube-quota";

export async function GET() {
  try {
    const summary = await getYoutubeQuotaSummary();
    return NextResponse.json({ ok: true, quota: summary });
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        error:
          err instanceof Error
            ? err.message
            : "Không thể đọc thông tin YouTube Quota.",
      },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as {
      setExactUsedUnits?: number;
      dailyLimit?: number;
      clearQuotaExceeded?: boolean;
    };
    const summary = await calibrateYoutubeQuota({
      setExactUsedUnits:
        typeof body.setExactUsedUnits === "number"
          ? body.setExactUsedUnits
          : undefined,
      dailyLimit:
        typeof body.dailyLimit === "number" ? body.dailyLimit : undefined,
      clearQuotaExceeded: Boolean(body.clearQuotaExceeded),
    });
    return NextResponse.json({ ok: true, quota: summary });
  } catch (err) {
    return NextResponse.json(
      {
        ok: false,
        error:
          err instanceof Error
            ? err.message
            : "Không thể cập nhật YouTube Quota.",
      },
      { status: 500 }
    );
  }
}
