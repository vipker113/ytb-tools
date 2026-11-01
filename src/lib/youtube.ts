import type {
  ChannelSnapshot,
  CompetitorChannel,
  KeywordAnalysisResult,
  TrackedChannel,
  VideoItem,
} from "./types";

const YT_API_BASE = "https://www.googleapis.com/youtube/v3";

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

export function parseIsoDuration(iso: string | undefined): number {
  if (!iso) return 0;
  const match = iso.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return 0;
  const hours = Number(match[1] || 0);
  const minutes = Number(match[2] || 0);
  const seconds = Number(match[3] || 0);
  return hours * 3600 + minutes * 60 + seconds;
}

export function computeMedian(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) {
    return Math.round((sorted[mid - 1] + sorted[mid]) / 2);
  }
  return sorted[mid];
}

export function extractVideoId(input: string): string | null {
  const trimmed = input.trim();
  if (/^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return trimmed;
  }
  try {
    const url = new URL(trimmed);
    if (url.hostname.includes("youtu.be")) {
      const id = url.pathname.split("/").filter(Boolean)[0];
      return id && id.length === 11 ? id : null;
    }
    if (url.searchParams.get("v")) {
      return url.searchParams.get("v");
    }
    const shortsMatch = url.pathname.match(/\/shorts\/([a-zA-Z0-9_-]{11})/);
    if (shortsMatch) return shortsMatch[1];
  } catch {
    // Not a URL
  }
  return null;
}

export function parseChannelQuery(rawInput: string): {
  type: "id" | "handle" | "search";
  value: string;
} {
  let cleaned = rawInput.trim();
  try {
    if (cleaned.startsWith("http://") || cleaned.startsWith("https://")) {
      const u = new URL(cleaned);
      const decodedPath = decodeURIComponent(u.pathname);
      const channelMatch = decodedPath.match(/\/channel\/(UC[a-zA-Z0-9_-]{20,})/);
      if (channelMatch) {
        return { type: "id", value: channelMatch[1] };
      }
      const handleMatch = decodedPath.match(/\/@([^/?#]+)/);
      if (handleMatch) {
        return { type: "handle", value: `@${handleMatch[1]}` };
      }
      const segments = decodedPath.split("/").filter(Boolean);
      if (segments.length > 0) {
        cleaned = segments[segments.length - 1];
      }
    }
  } catch {
    // Fallback to string parsing
  }

  if (/^UC[a-zA-Z0-9_-]{20,}$/.test(cleaned)) {
    return { type: "id", value: cleaned };
  }
  if (cleaned.startsWith("@")) {
    return { type: "handle", value: cleaned };
  }
  if (!cleaned.includes(" ") && /^[a-zA-Z0-9._-]+$/.test(cleaned)) {
    return { type: "handle", value: `@${cleaned}` };
  }
  return { type: "search", value: cleaned };
}

async function ytFetch<T>(endpoint: string, params: Record<string, string>, apiKey: string): Promise<T> {
  const url = new URL(`${YT_API_BASE}/${endpoint}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      url.searchParams.set(k, v);
    }
  }
  url.searchParams.set("key", apiKey);

  const res = await fetch(url.toString(), { cache: "no-store" });
  const json = await res.json();
  if (!res.ok) {
    const errMsg =
      json?.error?.message || `Lỗi kết nối YouTube API (HTTP ${res.status})`;
    throw new Error(errMsg);
  }
  return json as T;
}

export async function testYoutubeApiKey(apiKey: string): Promise<{
  ok: boolean;
  message: string;
}> {
  if (!apiKey.trim()) {
    return { ok: false, message: "Vui lòng nhập YouTube Data API v3 Key." };
  }
  try {
    await ytFetch("channels", {
      part: "id,snippet",
      id: "UC_x5XG1OV2P6uZZ5FSM9Ttw",
    }, apiKey.trim());
    return {
      ok: true,
      message: "Kết nối YouTube Data API v3 thành công! Đã sẵn sàng đồng bộ dữ liệu thật.",
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : "Không thể xác thực API Key";
    return {
      ok: false,
      message: `Lỗi API: ${msg}`,
    };
  }
}

interface YtChannelResource {
  id: string;
  snippet?: {
    title?: string;
    description?: string;
    customUrl?: string;
    thumbnails?: {
      high?: { url?: string };
      medium?: { url?: string };
      default?: { url?: string };
    };
  };
  statistics?: {
    subscriberCount?: string;
    viewCount?: string;
    videoCount?: string;
  };
  contentDetails?: {
    relatedPlaylists?: {
      uploads?: string;
    };
  };
}

interface YtVideoResource {
  id: string;
  snippet?: {
    channelId?: string;
    channelTitle?: string;
    title?: string;
    description?: string;
    tags?: string[];
    publishedAt?: string;
    thumbnails?: {
      maxres?: { url?: string };
      high?: { url?: string };
      medium?: { url?: string };
      default?: { url?: string };
    };
  };
  contentDetails?: {
    duration?: string;
  };
  statistics?: {
    viewCount?: string;
    likeCount?: string;
    commentCount?: string;
  };
}

function estimateSubConversionScore(params: {
  outlierScore: number;
  engagementRate: number;
  viewsToSubsRatio: number;
  description: string;
  title: string;
  isShort: boolean;
}): number {
  let score = 35;
  if (params.outlierScore >= 5) score += 25;
  else if (params.outlierScore >= 2) score += 16;
  else if (params.outlierScore >= 1.2) score += 8;

  if (params.engagementRate >= 6) score += 20;
  else if (params.engagementRate >= 4) score += 14;
  else if (params.engagementRate >= 2.5) score += 7;

  if (params.viewsToSubsRatio >= 3) score += 10;
  else if (params.viewsToSubsRatio >= 1) score += 5;

  const descLower = params.description.toLowerCase();
  if (
    descLower.includes("sub_confirmation=1") ||
    descLower.includes("đăng ký") ||
    descLower.includes("subscribe")
  ) {
    score += 6;
  }
  if (/\d{1,2}:\d{2}/.test(params.description) || params.isShort) {
    score += 4;
  }
  return Math.min(99, Math.max(15, Math.round(score)));
}

async function resolveYoutubeChannel(
  rawQuery: string,
  apiKey: string
): Promise<YtChannelResource> {
  const parsed = parseChannelQuery(rawQuery);

  if (parsed.type === "id") {
    const data = await ytFetch<{ items?: YtChannelResource[] }>(
      "channels",
      { part: "snippet,statistics,contentDetails", id: parsed.value },
      apiKey
    );
    if (data.items && data.items.length > 0) return data.items[0];
  }

  if (parsed.type === "handle") {
    const data = await ytFetch<{ items?: YtChannelResource[] }>(
      "channels",
      { part: "snippet,statistics,contentDetails", forHandle: parsed.value },
      apiKey
    );
    if (data.items && data.items.length > 0) return data.items[0];
  }

  // Fallback to search.list for channel name or custom URL
  const searchRes = await ytFetch<{
    items?: Array<{ id?: { channelId?: string }; snippet?: { channelId?: string } }>;
  }>(
    "search",
    {
      part: "snippet",
      type: "channel",
      maxResults: "1",
      q: rawQuery.replace(/^@/, ""),
    },
    apiKey
  );

  const channelId =
    searchRes.items?.[0]?.id?.channelId || searchRes.items?.[0]?.snippet?.channelId;
  if (!channelId) {
    throw new Error(`Không tìm thấy kênh YouTube nào khớp với "${rawQuery}".`);
  }

  const byId = await ytFetch<{ items?: YtChannelResource[] }>(
    "channels",
    { part: "snippet,statistics,contentDetails", id: channelId },
    apiKey
  );
  if (!byId.items || byId.items.length === 0) {
    throw new Error(`Không thể tải thông tin kênh "${rawQuery}".`);
  }
  return byId.items[0];
}

async function fetchChannelVideosFromUploads(
  channel: YtChannelResource,
  apiKey: string,
  maxResults = 25
): Promise<{
  videos: VideoItem[];
  avgViews: number;
  medianViews: number;
  avgEngagement: number;
}> {
  const uploadsId = channel.contentDetails?.relatedPlaylists?.uploads;
  const subscribers = Number(channel.statistics?.subscriberCount || 0);
  const channelTitle = channel.snippet?.title || "YouTube Channel";
  const channelHandle = channel.snippet?.customUrl || `@${channel.id.slice(0, 8)}`;

  if (!uploadsId) {
    return { videos: [], avgViews: 0, medianViews: 0, avgEngagement: 0 };
  }

  const plRes = await ytFetch<{
    items?: Array<{ contentDetails?: { videoId?: string } }>;
  }>(
    "playlistItems",
    {
      part: "contentDetails",
      playlistId: uploadsId,
      maxResults: String(maxResults),
    },
    apiKey
  );

  const videoIds = (plRes.items || [])
    .map((item) => item.contentDetails?.videoId)
    .filter((id): id is string => Boolean(id));

  if (videoIds.length === 0) {
    return { videos: [], avgViews: 0, medianViews: 0, avgEngagement: 0 };
  }

  const vidRes = await ytFetch<{ items?: YtVideoResource[] }>(
    "videos",
    {
      part: "snippet,contentDetails,statistics",
      id: videoIds.join(","),
    },
    apiKey
  );

  const rawVideos = vidRes.items || [];
  const viewCounts = rawVideos.map((v) => Number(v.statistics?.viewCount || 0));
  const avgViews =
    viewCounts.length > 0
      ? Math.round(viewCounts.reduce((a, b) => a + b, 0) / viewCounts.length)
      : 0;
  const medianViews = computeMedian(viewCounts);
  const baseline = Math.max(medianViews || avgViews, 25);
  const nowMs = Date.now();

  const videos: VideoItem[] = rawVideos.map((v) => {
    const views = Number(v.statistics?.viewCount || 0);
    const likes = Number(v.statistics?.likeCount || 0);
    const comments = Number(v.statistics?.commentCount || 0);
    const durationSeconds = parseIsoDuration(v.contentDetails?.duration);
    const title = v.snippet?.title || "Untitled";
    const description = v.snippet?.description || "";
    const isShort =
      (durationSeconds > 0 && durationSeconds <= 90 && !/00:00/.test(description)) ||
      /#(shorts|scienceshorts|short)\b/i.test(title) ||
      /#(shorts|scienceshorts|short)\b/i.test(description);

    const publishedAt = v.snippet?.publishedAt || new Date(nowMs).toISOString();
    const daysSince = Math.max(
      1,
      (nowMs - new Date(publishedAt).getTime()) / (1000 * 60 * 60 * 24)
    );
    const viewsPerDay = Math.round(views / daysSince);
    const engagementRate = round2(((likes + comments) / Math.max(views, 1)) * 100);
    const outlierScore = round2(views / baseline);
    const viewsToSubsRatio = round2(views / Math.max(subscribers, 10));

    const thumbnailUrl =
      v.snippet?.thumbnails?.maxres?.url ||
      v.snippet?.thumbnails?.high?.url ||
      v.snippet?.thumbnails?.medium?.url ||
      v.snippet?.thumbnails?.default?.url ||
      "";

    return {
      id: v.id,
      channelId: channel.id,
      channelTitle,
      channelHandle,
      channelSubscribers: subscribers,
      title,
      description,
      tags: v.snippet?.tags || [],
      thumbnailUrl,
      publishedAt,
      durationSeconds,
      isShort,
      views,
      likes,
      comments,
      engagementRate,
      viewsPerDay,
      outlierScore,
      viewsToSubsRatio,
      estimatedSubConversionScore: estimateSubConversionScore({
        outlierScore,
        engagementRate,
        viewsToSubsRatio,
        description,
        title,
        isShort,
      }),
    };
  });

  const avgEngagement =
    videos.length > 0
      ? round2(videos.reduce((sum, item) => sum + item.engagementRate, 0) / videos.length)
      : 0;

  return { videos, avgViews, medianViews, avgEngagement };
}

function nextSubscriberMilestone(subs: number): number {
  const milestones = [100, 500, 1000, 5000, 10000, 50000, 100000, 500000, 1000000];
  for (const m of milestones) {
    if (subs < m) return m;
  }
  return Math.ceil((subs + 1) / 1000000) * 1000000;
}

export async function fetchTrackedChannelLive(params: {
  query: string;
  apiKey: string;
  niche?: string;
  existingSnapshots?: ChannelSnapshot[];
  existingMilestone?: number;
}): Promise<TrackedChannel> {
  const ch = await resolveYoutubeChannel(params.query, params.apiKey);
  const { videos, avgViews, medianViews, avgEngagement } =
    await fetchChannelVideosFromUploads(ch, params.apiKey, 25);

  const subscribers = Number(ch.statistics?.subscriberCount || 0);
  const totalViews = Number(ch.statistics?.viewCount || 0);
  const videoCount = Number(ch.statistics?.videoCount || 0);
  const today = new Date().toISOString().slice(0, 10);

  const history = [...(params.existingSnapshots || [])];
  const todayIdx = history.findIndex((s) => s.date === today);
  const snap: ChannelSnapshot = {
    date: today,
    subscribers,
    totalViews,
    videoCount,
  };
  if (todayIdx >= 0) {
    history[todayIdx] = snap;
  } else {
    history.push(snap);
  }
  history.sort((a, b) => a.date.localeCompare(b.date));

  return {
    id: ch.id,
    handle: ch.snippet?.customUrl || `@${ch.id.slice(0, 10)}`,
    title: ch.snippet?.title || params.query,
    description: ch.snippet?.description || "",
    thumbnailUrl:
      ch.snippet?.thumbnails?.high?.url ||
      ch.snippet?.thumbnails?.medium?.url ||
      ch.snippet?.thumbnails?.default?.url ||
      "",
    subscribers,
    totalViews,
    videoCount,
    avgViewsRecent: avgViews,
    medianViewsRecent: medianViews,
    engagementRateAvg: avgEngagement,
    uploadsPlaylistId: ch.contentDetails?.relatedPlaylists?.uploads,
    targetMilestone:
      params.existingMilestone && params.existingMilestone > subscribers
        ? params.existingMilestone
        : nextSubscriberMilestone(subscribers),
    niche: params.niche || "Sáng tạo nội dung",
    isDemo: false,
    lastSyncedAt: new Date().toISOString(),
    snapshots: history,
    recentVideos: videos,
  };
}

export async function fetchCompetitorChannelLive(params: {
  query: string;
  apiKey: string;
  niche?: string;
}): Promise<CompetitorChannel> {
  const ch = await resolveYoutubeChannel(params.query, params.apiKey);
  const { videos, avgViews, medianViews } = await fetchChannelVideosFromUploads(
    ch,
    params.apiKey,
    30
  );

  return {
    id: ch.id,
    handle: ch.snippet?.customUrl || `@${ch.id.slice(0, 10)}`,
    title: ch.snippet?.title || params.query,
    thumbnailUrl:
      ch.snippet?.thumbnails?.high?.url ||
      ch.snippet?.thumbnails?.medium?.url ||
      ch.snippet?.thumbnails?.default?.url ||
      "",
    subscribers: Number(ch.statistics?.subscriberCount || 0),
    totalViews: Number(ch.statistics?.viewCount || 0),
    videoCount: Number(ch.statistics?.videoCount || 0),
    avgViewsRecent: avgViews,
    medianViewsRecent: medianViews,
    uploadsPlaylistId: ch.contentDetails?.relatedPlaylists?.uploads,
    niche: params.niche || "Đối thủ cùng ngách",
    isDemo: false,
    lastSyncedAt: new Date().toISOString(),
    videos,
  };
}

export async function fetchSingleVideoLive(
  videoInput: string,
  apiKey: string
): Promise<VideoItem> {
  const videoId = extractVideoId(videoInput);
  if (!videoId) {
    throw new Error("URL hoặc ID video YouTube không hợp lệ.");
  }

  const vidRes = await ytFetch<{ items?: YtVideoResource[] }>(
    "videos",
    { part: "snippet,contentDetails,statistics", id: videoId },
    apiKey
  );
  const v = vidRes.items?.[0];
  if (!v) {
    throw new Error("Không tìm thấy video YouTube này hoặc video đang ở chế độ riêng tư.");
  }

  let subscribers = 1000;
  let channelHandle = "";
  if (v.snippet?.channelId) {
    const chRes = await ytFetch<{ items?: YtChannelResource[] }>(
      "channels",
      { part: "snippet,statistics", id: v.snippet.channelId },
      apiKey
    );
    const ch = chRes.items?.[0];
    if (ch) {
      subscribers = Number(ch.statistics?.subscriberCount || 1000);
      channelHandle = ch.snippet?.customUrl || "";
    }
  }

  const views = Number(v.statistics?.viewCount || 0);
  const likes = Number(v.statistics?.likeCount || 0);
  const comments = Number(v.statistics?.commentCount || 0);
  const durationSeconds = parseIsoDuration(v.contentDetails?.duration);
  const title = v.snippet?.title || "";
  const description = v.snippet?.description || "";
  const isShort = durationSeconds > 0 && durationSeconds <= 65;
  const engagementRate = round2(((likes + comments) / Math.max(views, 1)) * 100);
  const publishedAt = v.snippet?.publishedAt || new Date().toISOString();
  const daysSince = Math.max(
    1,
    (Date.now() - new Date(publishedAt).getTime()) / (1000 * 60 * 60 * 24)
  );
  const viewsToSubsRatio = round2(views / Math.max(subscribers, 10));

  return {
    id: v.id,
    channelId: v.snippet?.channelId || "",
    channelTitle: v.snippet?.channelTitle || "",
    channelHandle,
    channelSubscribers: subscribers,
    title,
    description,
    tags: v.snippet?.tags || [],
    thumbnailUrl:
      v.snippet?.thumbnails?.maxres?.url ||
      v.snippet?.thumbnails?.high?.url ||
      v.snippet?.thumbnails?.medium?.url ||
      "",
    publishedAt,
    durationSeconds,
    isShort,
    views,
    likes,
    comments,
    engagementRate,
    viewsPerDay: Math.round(views / daysSince),
    outlierScore: viewsToSubsRatio,
    viewsToSubsRatio,
    estimatedSubConversionScore: estimateSubConversionScore({
      outlierScore: viewsToSubsRatio,
      engagementRate,
      viewsToSubsRatio,
      description,
      title,
      isShort,
    }),
  };
}

export async function analyzeKeywordLiveOrDemo(params: {
  keyword: string;
  apiKey: string;
  regionCode?: string;
}): Promise<KeywordAnalysisResult> {
  const kw = params.keyword.trim();
  if (!kw) {
    throw new Error("Vui lòng nhập từ khóa cần phân tích.");
  }

  if (!params.apiKey) {
    // Intelligent preview mode when user hasn't entered YouTube API key yet
    const baseTags = [
      kw.toLowerCase(),
      `hướng dẫn ${kw.toLowerCase()}`,
      `${kw.toLowerCase()} cho người mới`,
      `${kw.toLowerCase()} 2026`,
      `cách làm ${kw.toLowerCase()}`,
      `mẹo ${kw.toLowerCase()} hiệu quả`,
      `sai lầm khi ${kw.toLowerCase()}`,
      `kinh nghiệm ${kw.toLowerCase()}`,
    ];
    return {
      keyword: kw,
      isLiveData: false,
      demandScore: 78,
      opportunityScore: 74,
      overallScore: 76,
      verdict: "golden",
      avgViews: 28400,
      medianViews: 16500,
      smallChannelsInTop10: 4,
      shortsRatio: 30,
      optimalDurationRange: "8 - 14 phút (Video dài) hoặc 45 - 58 giây (Shorts)",
      recommendedTags: baseTags,
      titlePatterns: [
        `Cách ${kw} từ con số 0 cho người mới bắt đầu (2026)`,
        `5 Sai lầm khiến bạn thất bại khi ${kw} (Và cách khắc phục)`,
        `Tôi đã thử ${kw} trong 30 ngày và đây là kết quả thật sự`,
      ],
      topVideos: [],
    };
  }

  const isEnglishMarket =
    (params.regionCode && params.regionCode !== "VN") ||
    !/[\u00C0-\u1EF9]/.test(kw);

  const searchRes = await ytFetch<{
    items?: Array<{ id?: { videoId?: string } }>;
  }>(
    "search",
    {
      part: "id",
      type: "video",
      q: kw,
      maxResults: "15",
      regionCode: params.regionCode || "VN",
      relevanceLanguage: isEnglishMarket ? "en" : "vi",
    },
    params.apiKey
  );

  const videoIds = (searchRes.items || [])
    .map((i) => i.id?.videoId)
    .filter((id): id is string => Boolean(id));

  if (videoIds.length === 0) {
    return {
      keyword: kw,
      isLiveData: true,
      demandScore: 15,
      opportunityScore: 60,
      overallScore: 35,
      verdict: "low_demand",
      avgViews: 0,
      medianViews: 0,
      smallChannelsInTop10: 0,
      shortsRatio: 0,
      optimalDurationRange: "8 - 12 phút",
      recommendedTags: [kw],
      titlePatterns: [`Hướng dẫn ${kw} chi tiết từ A-Z`],
      topVideos: [],
    };
  }

  const vidRes = await ytFetch<{ items?: YtVideoResource[] }>(
    "videos",
    {
      part: "snippet,contentDetails,statistics",
      id: videoIds.join(","),
    },
    params.apiKey
  );
  const rawVideos = vidRes.items || [];

  const uniqueChannelIds = Array.from(
    new Set(
      rawVideos
        .map((v) => v.snippet?.channelId)
        .filter((id): id is string => Boolean(id))
    )
  );

  const channelMap = new Map<string, { subs: number; handle: string }>();
  if (uniqueChannelIds.length > 0) {
    const chRes = await ytFetch<{ items?: YtChannelResource[] }>(
      "channels",
      {
        part: "snippet,statistics",
        id: uniqueChannelIds.join(","),
      },
      params.apiKey
    );
    for (const c of chRes.items || []) {
      channelMap.set(c.id, {
        subs: Number(c.statistics?.subscriberCount || 0),
        handle: c.snippet?.customUrl || "",
      });
    }
  }

  const viewsList = rawVideos.map((v) => Number(v.statistics?.viewCount || 0));
  const avgViews =
    viewsList.length > 0
      ? Math.round(viewsList.reduce((a, b) => a + b, 0) / viewsList.length)
      : 0;
  const medianViews = computeMedian(viewsList);
  const nowMs = Date.now();

  const tagFreq = new Map<string, number>();

  const topVideos: VideoItem[] = rawVideos.map((v) => {
    const chInfo = channelMap.get(v.snippet?.channelId || "") || {
      subs: 5000,
      handle: "",
    };
    const views = Number(v.statistics?.viewCount || 0);
    const likes = Number(v.statistics?.likeCount || 0);
    const comments = Number(v.statistics?.commentCount || 0);
    const durationSeconds = parseIsoDuration(v.contentDetails?.duration);
    const title = v.snippet?.title || "";
    const description = v.snippet?.description || "";
    const isShort = durationSeconds > 0 && durationSeconds <= 65;
    const engagementRate = round2(((likes + comments) / Math.max(views, 1)) * 100);
    const publishedAt = v.snippet?.publishedAt || new Date(nowMs).toISOString();
    const daysSince = Math.max(
      1,
      (nowMs - new Date(publishedAt).getTime()) / (1000 * 60 * 60 * 24)
    );
    const outlierScore = round2(views / Math.max(medianViews, 100));
    const viewsToSubsRatio = round2(views / Math.max(chInfo.subs, 10));

    for (const t of v.snippet?.tags || []) {
      const norm = t.trim().toLowerCase();
      if (norm.length >= 3 && norm.length <= 45) {
        tagFreq.set(norm, (tagFreq.get(norm) || 0) + 1);
      }
    }

    return {
      id: v.id,
      channelId: v.snippet?.channelId || "",
      channelTitle: v.snippet?.channelTitle || "",
      channelHandle: chInfo.handle,
      channelSubscribers: chInfo.subs,
      title,
      description,
      tags: v.snippet?.tags || [],
      thumbnailUrl:
        v.snippet?.thumbnails?.high?.url ||
        v.snippet?.thumbnails?.medium?.url ||
        "",
      publishedAt,
      durationSeconds,
      isShort,
      views,
      likes,
      comments,
      engagementRate,
      viewsPerDay: Math.round(views / daysSince),
      outlierScore,
      viewsToSubsRatio,
      estimatedSubConversionScore: estimateSubConversionScore({
        outlierScore,
        engagementRate,
        viewsToSubsRatio,
        description,
        title,
        isShort,
      }),
    };
  });

  const top10 = topVideos.slice(0, 10);
  const smallChannelsInTop10 = top10.filter(
    (v) => v.channelSubscribers > 0 && v.channelSubscribers < 15000
  ).length;
  const highRatioCount = top10.filter((v) => v.viewsToSubsRatio >= 1.5).length;

  // Demand score from median & average views
  const demandScore = Math.min(
    98,
    Math.max(
      18,
      Math.round(Math.log10(Math.max(medianViews, 100)) * 20)
    )
  );

  // Opportunity score: higher when small channels rank in top 10 & get views > subs
  const opportunityScore = Math.min(
    96,
    Math.max(
      15,
      25 + smallChannelsInTop10 * 10 + highRatioCount * 6
    )
  );

  const overallScore = Math.round(demandScore * 0.45 + opportunityScore * 0.55);
  let verdict: KeywordAnalysisResult["verdict"] = "good";
  if (overallScore >= 72 && opportunityScore >= 60) verdict = "golden";
  else if (demandScore < 35) verdict = "low_demand";
  else if (opportunityScore < 42) verdict = "competitive";

  const shortsCount = topVideos.filter((v) => v.isShort).length;
  const shortsRatio = Math.round((shortsCount / Math.max(topVideos.length, 1)) * 100);

  const longVideos = topVideos.filter((v) => !v.isShort && v.durationSeconds > 65);
  let optimalDurationRange = "8 - 12 phút";
  if (longVideos.length > 0) {
    const avgMin = Math.round(
      longVideos.reduce((s, v) => s + v.durationSeconds, 0) / longVideos.length / 60
    );
    const low = Math.max(4, avgMin - 2);
    const high = Math.max(low + 3, avgMin + 3);
    optimalDurationRange = `${low} - ${high} phút`;
  } else if (shortsRatio >= 70) {
    optimalDurationRange = "40 - 58 giây (Ưu tiên YouTube Shorts)";
  }

  const recommendedTags = Array.from(tagFreq.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 14)
    .map(([tag]) => tag);

  if (recommendedTags.length < 5) {
    recommendedTags.push(
      kw.toLowerCase(),
      `hướng dẫn ${kw.toLowerCase()}`,
      `${kw.toLowerCase()} 2026`
    );
  }

  const titlePatterns = isEnglishMarket
    ? [
        `Why ${kw} Shouldn't Exist (According to Physics)`,
        `What Actually Happens Inside ${kw}?`,
        `Scientists Still Can't Explain This About ${kw}`,
      ]
    : [
        `Cách ${kw} hiệu quả nhất cho người mới (Hướng dẫn thực tế 2026)`,
        `Đừng bắt đầu ${kw} trước khi biết 3 bí mật này!`,
        `Lộ trình ${kw} từ con số 0 trong 15 phút`,
      ];

  return {
    keyword: kw,
    isLiveData: true,
    demandScore,
    opportunityScore,
    overallScore,
    verdict,
    avgViews,
    medianViews,
    smallChannelsInTop10,
    shortsRatio,
    optimalDurationRange,
    recommendedTags: Array.from(new Set(recommendedTags)),
    titlePatterns,
    topVideos,
  };
}
