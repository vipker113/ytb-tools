import { readStore } from "@/lib/store";
import { fetchChannelShortsAnalytics } from "@/lib/youtube-analytics";

export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const forceRefresh = url.searchParams.get("force") === "1";
    const store = await readStore();
    const report = await fetchChannelShortsAnalytics(store, { forceRefresh });
    return Response.json(report);
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Không thể kết nối YouTube Analytics API.";
    return Response.json(
      {
        ok: false,
        code: "error",
        messageVi: message,
        fetchedAt: new Date().toISOString(),
        byVideoId: {},
        summary: {
          trackedVideosWithData: 0,
          avgStayedToWatchPct: null,
          avgViewPercentage: null,
          avgViewDurationSec: null,
          totalNetSubscribers: 0,
          totalEngagedViews: 0,
          totalMinutesWatched: 0,
        },
      },
      { status: 500 }
    );
  }
}
