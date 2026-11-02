import type { StoreData, VideoAnalyticsMetrics } from "./types";
import { getValidYoutubeAccessToken } from "./youtube-studio";

export interface YoutubeAnalyticsReportResponse {
  ok: boolean;
  code:
    | "connected"
    | "not_connected"
    | "needs_reauth"
    | "needs_api_enable"
    | "error";
  messageVi: string;
  enableApiUrl?: string;
  oauthStartUrl?: string;
  fetchedAt: string;
  byVideoId: Record<string, VideoAnalyticsMetrics>;
  summary: {
    trackedVideosWithData: number;
    avgStayedToWatchPct: number | null;
    avgViewPercentage: number | null;
    avgViewDurationSec: number | null;
    totalNetSubscribers: number;
    totalEngagedViews: number;
    totalMinutesWatched: number;
  };
}

interface RawAnalyticsRow {
  columnHeaders?: Array<{ name: string; columnType: string; dataType: string }>;
  rows?: Array<Array<string | number>>;
  error?: {
    code?: number;
    status?: string;
    message?: string;
    details?: Array<{
      reason?: string;
      metadata?: { activationUrl?: string };
    }>;
  };
}

async function queryAnalyticsReport(
  accessToken: string,
  metricsList: string
): Promise<{ status: number; data: RawAnalyticsRow }> {
  const endDate = new Date().toISOString().slice(0, 10);
  const url = new URL("https://youtubeanalytics.googleapis.com/v2/reports");
  url.searchParams.set("ids", "channel==MINE");
  url.searchParams.set("startDate", "2024-01-01");
  url.searchParams.set("endDate", endDate);
  url.searchParams.set("dimensions", "video");
  url.searchParams.set("metrics", metricsList);
  url.searchParams.set("maxResults", "50");
  url.searchParams.set("sort", "-views");

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  const data = (await res.json().catch(() => ({}))) as RawAnalyticsRow;
  return { status: res.status, data };
}

let serverAnalyticsCache: {
  tokenKey: string;
  expiresAt: number;
  report: YoutubeAnalyticsReportResponse;
} | null = null;

export async function fetchChannelShortsAnalytics(
  store: StoreData,
  options?: { forceRefresh?: boolean }
): Promise<YoutubeAnalyticsReportResponse> {
  const emptySummary = {
    trackedVideosWithData: 0,
    avgStayedToWatchPct: null,
    avgViewPercentage: null,
    avgViewDurationSec: null,
    totalNetSubscribers: 0,
    totalEngagedViews: 0,
    totalMinutesWatched: 0,
  };

  if (!store.youtubeOAuth?.refreshToken) {
    return {
      ok: false,
      code: "not_connected",
      messageVi:
        "Chưa kết nối OAuth 2.0 với YouTube Studio. Hãy bấm Cấp Quyền 1-Click để đọc % Không vuốt bỏ & % Xem trung bình!",
      oauthStartUrl: "/api/youtube/oauth/start",
      fetchedAt: new Date().toISOString(),
      byVideoId: {},
      summary: emptySummary,
    };
  }

  const tokenKey = store.youtubeOAuth.refreshToken.slice(-16);
  if (
    !options?.forceRefresh &&
    serverAnalyticsCache &&
    serverAnalyticsCache.tokenKey === tokenKey &&
    serverAnalyticsCache.expiresAt > Date.now()
  ) {
    return serverAnalyticsCache.report;
  }

  let accessToken: string;
  try {
    accessToken = await getValidYoutubeAccessToken(store);
  } catch (err) {
    return {
      ok: false,
      code: "needs_reauth",
      messageVi:
        err instanceof Error
          ? err.message
          : "Phiên OAuth đã hết hạn, vui lòng cấp quyền lại.",
      oauthStartUrl: "/api/youtube/oauth/start",
      fetchedAt: new Date().toISOString(),
      byVideoId: {},
      summary: emptySummary,
    };
  }

  const fullMetrics =
    "views,engagedViews,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost,estimatedMinutesWatched";
  const fallbackMetrics =
    "views,averageViewDuration,averageViewPercentage,likes,comments,shares,subscribersGained,subscribersLost,estimatedMinutesWatched";

  let attempt = await queryAnalyticsReport(accessToken, fullMetrics);

  // If engagedViews metric is unsupported for a specific account/query, retry cleanly without it
  if (
    attempt.status === 400 &&
    JSON.stringify(attempt.data?.error || "").includes("engagedViews")
  ) {
    attempt = await queryAnalyticsReport(accessToken, fallbackMetrics);
  }

  if (attempt.status !== 200) {
    const errMsg = attempt.data?.error?.message || "";
    const errStatus = attempt.data?.error?.status || "";
    const rawJson = JSON.stringify(attempt.data?.error || {});

    // Case 1: YouTube Analytics API is not enabled on user's Google Cloud project yet
    if (
      errMsg.includes("YouTube Analytics API has not been used") ||
      errMsg.includes("youtubeanalytics.googleapis.com") ||
      rawJson.includes("SERVICE_DISABLED") ||
      rawJson.includes("accessNotConfigured")
    ) {
      const urlMatch = errMsg.match(
        /https:\/\/console\.(?:developers|cloud)\.google\.com\/[^\s"]+/
      );
      const activationFromDetails = attempt.data?.error?.details?.find(
        (d) => d.metadata?.activationUrl
      )?.metadata?.activationUrl;

      return {
        ok: false,
        code: "needs_api_enable",
        enableApiUrl:
          activationFromDetails ||
          urlMatch?.[0] ||
          "https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com",
        oauthStartUrl: "/api/youtube/oauth/start",
        messageVi:
          "Dự án Google Cloud của bạn chưa bật công tắc 'YouTube Analytics API' (Miễn phí 0₫). Chỉ cần bấm nút 'Mở Google Cloud Bật API (10 giây)' bên dưới rồi bấm Kiểm tra lại!",
        fetchedAt: new Date().toISOString(),
        byVideoId: {},
        summary: emptySummary,
      };
    }

    // Case 2: Existing refreshToken was granted before yt-analytics.readonly scope was added
    if (
      attempt.status === 401 ||
      attempt.status === 403 ||
      errStatus === "PERMISSION_DENIED" ||
      errMsg.toLowerCase().includes("scope") ||
      errMsg.toLowerCase().includes("insufficient")
    ) {
      return {
        ok: false,
        code: "needs_reauth",
        oauthStartUrl: "/api/youtube/oauth/start",
        enableApiUrl:
          "https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com",
        messageVi:
          "Phiên kết nối cũ chưa bao gồm quyền đọc Shorts Analytics (yt-analytics.readonly). Bấm 'Cấp Bổ Sung Quyền Analytics (1-Click)' để mở khóa toàn bộ chỉ số giữ chân!",
        fetchedAt: new Date().toISOString(),
        byVideoId: {},
        summary: emptySummary,
      };
    }

    return {
      ok: false,
      code: "error",
      messageVi:
        errMsg || `Không thể tải YouTube Analytics (HTTP ${attempt.status}).`,
      fetchedAt: new Date().toISOString(),
      byVideoId: {},
      summary: emptySummary,
    };
  }

  const headers = (attempt.data.columnHeaders || []).map((h) => h.name);
  const rows = attempt.data.rows || [];
  const idxOf = (col: string) => headers.indexOf(col);

  const byVideoId: Record<string, VideoAnalyticsMetrics> = {};
  let sumStayed = 0;
  let countStayed = 0;
  let sumApv = 0;
  let countApv = 0;
  let sumAvd = 0;
  let totalNetSubs = 0;
  let totalEngaged = 0;
  let totalMinutes = 0;

  for (const row of rows) {
    const vIdx = idxOf("video");
    const videoId = vIdx >= 0 ? String(row[vIdx] || "") : "";
    if (!videoId) continue;

    const num = (col: string): number => {
      const i = idxOf(col);
      return i >= 0 ? Number(row[i] || 0) : 0;
    };

    const views = num("views");
    const hasEngaged = idxOf("engagedViews") >= 0;
    const engagedViews = hasEngaged ? num("engagedViews") : undefined;
    const stayedToWatchPct =
      hasEngaged && views > 0 && engagedViews !== undefined && engagedViews > 0
        ? Math.min(100, Math.round((engagedViews / views) * 1000) / 10)
        : null;

    const averageViewDurationSec =
      Math.round(num("averageViewDuration") * 10) / 10;
    const averageViewPercentage =
      Math.round(num("averageViewPercentage") * 10) / 10;
    const likes = num("likes");
    const comments = num("comments");
    const shares = num("shares");
    const subscribersGained = num("subscribersGained");
    const subscribersLost = num("subscribersLost");
    const netSubscribers = subscribersGained - subscribersLost;
    const estimatedMinutesWatched =
      Math.round(num("estimatedMinutesWatched") * 10) / 10;

    byVideoId[videoId] = {
      videoId,
      views,
      engagedViews,
      stayedToWatchPct,
      averageViewDurationSec,
      averageViewPercentage,
      likes,
      comments,
      shares,
      subscribersGained,
      subscribersLost,
      netSubscribers,
      estimatedMinutesWatched,
    };

    if (stayedToWatchPct !== null) {
      sumStayed += stayedToWatchPct;
      countStayed++;
    }
    if (averageViewPercentage > 0) {
      sumApv += averageViewPercentage;
      sumAvd += averageViewDurationSec;
      countApv++;
    }
    totalNetSubs += netSubscribers;
    totalEngaged += engagedViews || 0;
    totalMinutes += estimatedMinutesWatched;
  }

  const finalReport: YoutubeAnalyticsReportResponse = {
    ok: true,
    code: "connected",
    messageVi: `Đã tải trực tiếp dữ liệu YouTube Analytics cho ${
      Object.keys(byVideoId).length
    } video trên kênh!`,
    fetchedAt: new Date().toISOString(),
    byVideoId,
    summary: {
      trackedVideosWithData: Object.keys(byVideoId).length,
      avgStayedToWatchPct:
        countStayed > 0 ? Math.round((sumStayed / countStayed) * 10) / 10 : null,
      avgViewPercentage:
        countApv > 0 ? Math.round((sumApv / countApv) * 10) / 10 : null,
      avgViewDurationSec:
        countApv > 0 ? Math.round((sumAvd / countApv) * 10) / 10 : null,
      totalNetSubscribers: totalNetSubs,
      totalEngagedViews: totalEngaged,
      totalMinutesWatched: Math.round(totalMinutes * 10) / 10,
    },
  };

  serverAnalyticsCache = {
    tokenKey,
    expiresAt: Date.now() + 60_000,
    report: finalReport,
  };
  return finalReport;
}
