import type {
  CrossSubPartner,
  DiscoveredNichePeer,
  NicheSafetyTier,
  RecentPublicSubscriberItem,
} from "./types";
import { extractVideoId, parseChannelQuery } from "./youtube";

const YT_API_BASE = "https://www.googleapis.com/youtube/v3";

const SCIENCE_DOC_KEYWORDS = [
  "science",
  "scientific",
  "space",
  "cosmos",
  "cosmic",
  "astronomy",
  "astrophysics",
  "nasa",
  "universe",
  "galaxy",
  "planet",
  "ocean",
  "abyss",
  "deep sea",
  "trench",
  "marine",
  "earth",
  "geology",
  "volcano",
  "antarctica",
  "glacier",
  "physics",
  "quantum",
  "chemistry",
  "biology",
  "microscope",
  "microbial",
  "nature",
  "wildlife",
  "history",
  "ancient",
  "mystery",
  "mysteries",
  "documentary",
  "facts",
  "curiosity",
  "curious",
  "wonder",
  "explained",
  "geography",
  "archaeology",
  "paleontology",
  "discovery",
  "engineering",
  "education",
  "educational",
];

const ADJACENT_KNOWLEDGE_KEYWORDS = [
  "tech",
  "technology",
  "ai",
  "psychology",
  "philosophy",
  "mind",
  "story",
  "stories",
  "archive",
  "atlas",
  "map",
  "maps",
  "khoa học",
  "vũ trụ",
  "khám phá",
  "kiến thức",
  "lịch sử",
  "địa lý",
  "bí ẩn",
  "thiên nhiên",
];

const OFF_NICHE_RISK_KEYWORDS = [
  "free fire",
  "roblox",
  "minecraft",
  "pubg",
  "valorant",
  "liên quân",
  "lien quan",
  "genshin",
  "gacha",
  "skibidi",
  "mukbang",
  "karaoke",
  "bolero",
  "nhạc chế",
  "nhạc trẻ",
  "remix",
  "xổ số",
  "soi cầu",
  "tài xỉu",
  "baby shark",
  "nursery rhymes",
  "kids song",
  "prank",
  "drama",
];

const VIETNAMESE_DIACRITIC_RE =
  /[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]/i;

async function ytPublicFetch<T>(
  endpoint: string,
  params: Record<string, string>,
  apiKey: string
): Promise<T> {
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
    throw new Error(
      json?.error?.message || `Lỗi kết nối YouTube API (HTTP ${res.status})`
    );
  }
  return json as T;
}

async function ytOAuthFetch<T>(
  endpoint: string,
  params: Record<string, string>,
  accessToken: string
): Promise<T> {
  const url = new URL(`${YT_API_BASE}/${endpoint}`);
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") {
      url.searchParams.set(k, v);
    }
  }

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  const json = await res.json();
  if (!res.ok) {
    throw new Error(
      json?.error?.message || `Lỗi xác thực YouTube OAuth (HTTP ${res.status})`
    );
  }
  return json as T;
}

export function scoreNicheCtrSafety(params: {
  title: string;
  description: string;
  country?: string;
  sampleVideoTitle?: string;
}): {
  score: number;
  tier: NicheSafetyTier;
  reasonVi: string;
} {
  const combined =
    `${params.title} ${params.description} ${params.sampleVideoTitle || ""}`.toLowerCase();

  const matchedScience: string[] = [];
  for (const kw of SCIENCE_DOC_KEYWORDS) {
    if (combined.includes(kw)) {
      matchedScience.push(kw);
    }
  }

  const matchedAdjacent: string[] = [];
  for (const kw of ADJACENT_KNOWLEDGE_KEYWORDS) {
    if (combined.includes(kw)) {
      matchedAdjacent.push(kw);
    }
  }

  const matchedRisk: string[] = [];
  for (const kw of OFF_NICHE_RISK_KEYWORDS) {
    if (combined.includes(kw)) {
      matchedRisk.push(kw);
    }
  }

  const hasViDiacritics = VIETNAMESE_DIACRITIC_RE.test(combined);
  const countryUpper = (params.country || "").toUpperCase();
  const isEnglishTier1Country = ["US", "GB", "CA", "AU", "NZ", "IE"].includes(
    countryUpper
  );

  let score = 48;

  if (matchedScience.length >= 4) score += 36;
  else if (matchedScience.length >= 2) score += 28;
  else if (matchedScience.length === 1) score += 18;

  if (matchedAdjacent.length >= 2) score += 10;
  else if (matchedAdjacent.length === 1) score += 6;

  if (isEnglishTier1Country) {
    score += 10;
  } else if (!hasViDiacritics && matchedScience.length >= 1) {
    score += 6;
  }

  if (hasViDiacritics && countryUpper !== "US") {
    score -= 12;
  }

  if (matchedRisk.length > 0) {
    score -= Math.min(40, matchedRisk.length * 18);
  }

  score = Math.max(8, Math.min(98, Math.round(score)));

  if (score >= 70) {
    const topMatches = matchedScience.slice(0, 3).join(", ");
    return {
      score,
      tier: "safe_same_niche",
      reasonVi: topMatches
        ? `Cùng tệp Science/Doc (${topMatches}) — Ít gây lệch phân phối & bảo vệ CTR tốt nhất`
        : "Cùng tệp nội dung tiếng Anh — Tương thích tốt với khán giả kênh",
    };
  }

  if (score >= 45) {
    return {
      score,
      tier: "neutral_adjacent",
      reasonVi: hasViDiacritics
        ? "Khác ngôn ngữ/khu vực với tệp Mỹ — Nên dùng tài khoản phụ để trả Sub"
        : "Ngách kiến thức/phổ thông lân cận — Mức ảnh hưởng CTR trung bình",
    };
  }

  return {
    score,
    tier: "risky_off_niche",
    reasonVi:
      matchedRisk.length > 0
        ? `Lệch hẳn tệp (${matchedRisk.slice(0, 2).join(", ")}) — Dễ làm giảm CTR & tỷ lệ xem Shorts`
        : "Khác hoàn toàn tệp khán giả Science Mỹ — Cảnh báo kéo giảm CTR nếu trao đổi nhiều",
  };
}

interface RawYtChannel {
  id: string;
  snippet?: {
    title?: string;
    description?: string;
    customUrl?: string;
    country?: string;
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

export async function resolvePartnerFromInput(params: {
  rawInput: string;
  apiKey: string;
}): Promise<{
  channelId: string;
  handle: string;
  title: string;
  description: string;
  thumbnailUrl: string;
  country?: string;
  subscribers: number;
  videoCount: number;
  totalViews: number;
  latestVideoId?: string;
  latestVideoTitle?: string;
  nicheMatchScore: number;
  nicheSafetyTier: NicheSafetyTier;
  nicheReasonVi: string;
}> {
  const cleaned = params.rawInput.trim();
  if (!cleaned) {
    throw new Error("Vui lòng nhập link kênh, @handle hoặc link video Shorts.");
  }

  let resolvedChannelId: string | null = null;
  let latestVideoId: string | undefined;
  let latestVideoTitle: string | undefined;

  // 1. Check if user pasted a direct YouTube video / Shorts URL
  const maybeVideoId = extractVideoId(cleaned);
  if (maybeVideoId) {
    const vidData = await ytPublicFetch<{
      items?: Array<{
        id: string;
        snippet?: { channelId?: string; title?: string };
      }>;
    }>("videos", { part: "snippet", id: maybeVideoId }, params.apiKey);

    const firstVid = vidData.items?.[0];
    if (firstVid?.snippet?.channelId) {
      resolvedChannelId = firstVid.snippet.channelId;
      latestVideoId = firstVid.id;
      latestVideoTitle = firstVid.snippet.title || undefined;
    }
  }

  // 2. Resolve channel metadata
  let ch: RawYtChannel | undefined;
  if (resolvedChannelId) {
    const chData = await ytPublicFetch<{ items?: RawYtChannel[] }>(
      "channels",
      {
        part: "snippet,statistics,contentDetails",
        id: resolvedChannelId,
      },
      params.apiKey
    );
    ch = chData.items?.[0];
  } else {
    const parsed = parseChannelQuery(cleaned);
    if (parsed.type === "id") {
      const chData = await ytPublicFetch<{ items?: RawYtChannel[] }>(
        "channels",
        { part: "snippet,statistics,contentDetails", id: parsed.value },
        params.apiKey
      );
      ch = chData.items?.[0];
    } else if (parsed.type === "handle") {
      const chData = await ytPublicFetch<{ items?: RawYtChannel[] }>(
        "channels",
        { part: "snippet,statistics,contentDetails", forHandle: parsed.value },
        params.apiKey
      );
      ch = chData.items?.[0];
    }

    if (!ch) {
      const searchRes = await ytPublicFetch<{
        items?: Array<{
          id?: { channelId?: string };
          snippet?: { channelId?: string };
        }>;
      }>(
        "search",
        {
          part: "snippet",
          type: "channel",
          q: parsed.value,
          maxResults: "1",
        },
        params.apiKey
      );
      const foundId =
        searchRes.items?.[0]?.id?.channelId ||
        searchRes.items?.[0]?.snippet?.channelId;
      if (foundId) {
        const chData = await ytPublicFetch<{ items?: RawYtChannel[] }>(
          "channels",
          { part: "snippet,statistics,contentDetails", id: foundId },
          params.apiKey
        );
        ch = chData.items?.[0];
      }
    }
  }

  if (!ch) {
    throw new Error(
      `Không tìm thấy kênh YouTube khớp với "${cleaned}". Hãy dán URL kênh, @handle hoặc link Shorts.`
    );
  }

  // 3. Fetch 1 latest uploaded video if not already provided so user can watch 60s before subscribing
  const uploadsPlaylistId = ch.contentDetails?.relatedPlaylists?.uploads;
  if (!latestVideoId && uploadsPlaylistId) {
    try {
      const plRes = await ytPublicFetch<{
        items?: Array<{
          snippet?: {
            title?: string;
            resourceId?: { videoId?: string };
          };
        }>;
      }>(
        "playlistItems",
        {
          part: "snippet",
          playlistId: uploadsPlaylistId,
          maxResults: "1",
        },
        params.apiKey
      );
      const firstPl = plRes.items?.[0];
      if (firstPl?.snippet?.resourceId?.videoId) {
        latestVideoId = firstPl.snippet.resourceId.videoId;
        latestVideoTitle = firstPl.snippet.title || undefined;
      }
    } catch {
      // Ignore if channel has 0 public uploads
    }
  }

  const rawHandle = ch.snippet?.customUrl || ch.id;
  const handle = rawHandle.startsWith("@") ? rawHandle : `@${rawHandle}`;
  const title = ch.snippet?.title || handle;
  const description = ch.snippet?.description || "";
  const country = ch.snippet?.country || undefined;
  const thumbnailUrl =
    ch.snippet?.thumbnails?.high?.url ||
    ch.snippet?.thumbnails?.medium?.url ||
    ch.snippet?.thumbnails?.default?.url ||
    "";

  const safety = scoreNicheCtrSafety({
    title,
    description,
    country,
    sampleVideoTitle: latestVideoTitle,
  });

  return {
    channelId: ch.id,
    handle,
    title,
    description,
    thumbnailUrl,
    country,
    subscribers: Number(ch.statistics?.subscriberCount || 0),
    videoCount: Number(ch.statistics?.videoCount || 0),
    totalViews: Number(ch.statistics?.viewCount || 0),
    latestVideoId,
    latestVideoTitle,
    nicheMatchScore: safety.score,
    nicheSafetyTier: safety.tier,
    nicheReasonVi: safety.reasonVi,
  };
}

export async function discoverSameNichePeers(params: {
  keyword: string;
  minSubs: number;
  maxSubs: number;
  regionCode?: string;
  apiKey: string;
  existingChannelIds: Set<string>;
  myChannelId?: string;
}): Promise<DiscoveredNichePeer[]> {
  const q = params.keyword.trim() || "deep ocean science mystery #shorts";
  const regionCode = (params.regionCode || "US").toUpperCase();

  const searchRes = await ytPublicFetch<{
    items?: Array<{
      id?: { videoId?: string };
      snippet?: {
        channelId?: string;
        title?: string;
        thumbnails?: {
          high?: { url?: string };
          medium?: { url?: string };
          default?: { url?: string };
        };
      };
    }>;
  }>(
    "search",
    {
      part: "snippet",
      type: "video",
      videoDuration: "short",
      q,
      regionCode,
      relevanceLanguage: "en",
      maxResults: "30",
      safeSearch: "none",
    },
    params.apiKey
  );

  const byChannel = new Map<
    string,
    { videoId: string; videoTitle: string; videoThumb: string }
  >();

  for (const item of searchRes.items || []) {
    const chId = item.snippet?.channelId;
    const vidId = item.id?.videoId;
    if (!chId || !vidId) continue;
    if (params.myChannelId && chId === params.myChannelId) continue;
    if (!byChannel.has(chId)) {
      byChannel.set(chId, {
        videoId: vidId,
        videoTitle: item.snippet?.title || "YouTube Short",
        videoThumb:
          item.snippet?.thumbnails?.medium?.url ||
          item.snippet?.thumbnails?.high?.url ||
          item.snippet?.thumbnails?.default?.url ||
          "",
      });
    }
  }

  const channelIds = Array.from(byChannel.keys()).slice(0, 45);
  if (channelIds.length === 0) return [];

  const chRes = await ytPublicFetch<{ items?: RawYtChannel[] }>(
    "channels",
    {
      part: "snippet,statistics",
      id: channelIds.join(","),
    },
    params.apiKey
  );

  const peers: DiscoveredNichePeer[] = [];
  for (const ch of chRes.items || []) {
    const subs = Number(ch.statistics?.subscriberCount || 0);
    if (subs < params.minSubs || subs > params.maxSubs) continue;

    const sample = byChannel.get(ch.id);
    if (!sample) continue;

    const rawHandle = ch.snippet?.customUrl || ch.id;
    const handle = rawHandle.startsWith("@") ? rawHandle : `@${rawHandle}`;
    const title = ch.snippet?.title || handle;
    const description = ch.snippet?.description || "";
    const country = ch.snippet?.country || undefined;

    const safety = scoreNicheCtrSafety({
      title,
      description,
      country,
      sampleVideoTitle: sample.videoTitle,
    });

    peers.push({
      channelId: ch.id,
      handle,
      title,
      description,
      thumbnailUrl:
        ch.snippet?.thumbnails?.medium?.url ||
        ch.snippet?.thumbnails?.high?.url ||
        ch.snippet?.thumbnails?.default?.url ||
        "",
      country,
      subscribers: subs,
      videoCount: Number(ch.statistics?.videoCount || 0),
      totalViews: Number(ch.statistics?.viewCount || 0),
      sampleVideoId: sample.videoId,
      sampleVideoTitle: sample.videoTitle,
      sampleVideoThumb: sample.videoThumb,
      nicheMatchScore: safety.score,
      nicheSafetyTier: safety.tier,
      nicheReasonVi: safety.reasonVi,
      alreadySaved: params.existingChannelIds.has(ch.id),
    });
  }

  peers.sort((a, b) => {
    if (b.nicheMatchScore !== a.nicheMatchScore) {
      return b.nicheMatchScore - a.nicheMatchScore;
    }
    return a.subscribers - b.subscribers;
  });

  return peers;
}

interface YtSubscriptionListResponse {
  nextPageToken?: string;
  pageInfo?: { totalResults?: number };
  items?: Array<{
    snippet?: {
      publishedAt?: string;
      resourceId?: { channelId?: string };
    };
    subscriberSnippet?: {
      channelId?: string;
      title?: string;
      description?: string;
      thumbnails?: {
        medium?: { url?: string };
        default?: { url?: string };
      };
    };
  }>;
}

export async function verifyPartnersViaYoutubeOAuth(params: {
  accessToken: string;
  partners: CrossSubPartner[];
}): Promise<{
  updatedPartners: CrossSubPartner[];
  confirmedCount: number;
  unsubscribedCount: number;
  privateOrPendingCount: number;
  publicSubscribersScanned: number;
  recentPublicSubscribers: RecentPublicSubscriberItem[];
}> {
  const publicSubMap = new Map<string, string>(); // channelId -> publishedAt
  const recentPublicList: RecentPublicSubscriberItem[] = [];
  let scanComplete = true;

  // 1. Fetch recent public subscribers first (ordered newest first)
  try {
    const recentRes = await ytOAuthFetch<YtSubscriptionListResponse>(
      "subscriptions",
      {
        part: "snippet,subscriberSnippet",
        myRecentSubscribers: "true",
        maxResults: "50",
      },
      params.accessToken
    );

    const existingIds = new Set(params.partners.map((p) => p.channelId));
    for (const item of recentRes.items || []) {
      const subChId = item.subscriberSnippet?.channelId;
      const pubAt = item.snippet?.publishedAt || new Date().toISOString();
      if (subChId) {
        publicSubMap.set(subChId, pubAt);
        recentPublicList.push({
          channelId: subChId,
          title: item.subscriberSnippet?.title || subChId,
          description: item.subscriberSnippet?.description || "",
          thumbnailUrl:
            item.subscriberSnippet?.thumbnails?.medium?.url ||
            item.subscriberSnippet?.thumbnails?.default?.url ||
            "",
          subscribedAt: pubAt,
          alreadyInCrm: existingIds.has(subChId),
        });
      }
    }
  } catch {
    // Continue with mySubscribers fallback
  }

  // 2. Paginate mySubscribers=true up to 4 pages (200 public subscribers)
  let pageToken = "";
  let pagesFetched = 0;
  try {
    while (pagesFetched < 4) {
      const subRes = await ytOAuthFetch<YtSubscriptionListResponse>(
        "subscriptions",
        {
          part: "snippet,subscriberSnippet",
          mySubscribers: "true",
          maxResults: "50",
          ...(pageToken ? { pageToken } : {}),
        },
        params.accessToken
      );
      pagesFetched += 1;
      for (const item of subRes.items || []) {
        const subChId = item.subscriberSnippet?.channelId;
        const pubAt = item.snippet?.publishedAt || new Date().toISOString();
        if (subChId && !publicSubMap.has(subChId)) {
          publicSubMap.set(subChId, pubAt);
        }
      }
      if (subRes.nextPageToken) {
        pageToken = subRes.nextPageToken;
      } else {
        pageToken = "";
        break;
      }
    }
    if (pageToken) {
      // More than 200 public subscribers exist; avoid false unsubscribed_detected flags for older subs
      scanComplete = false;
    }
  } catch {
    scanComplete = false;
  }

  // 3. Check outbound subscriptions on the connected main channel (in batches of 50)
  const myOutboundSubscribedSet = new Set<string>();
  const allPartnerChannelIds = Array.from(
    new Set(params.partners.map((p) => p.channelId).filter(Boolean))
  );

  for (let i = 0; i < allPartnerChannelIds.length; i += 50) {
    const chunk = allPartnerChannelIds.slice(i, i + 50);
    if (chunk.length === 0) continue;
    try {
      const outRes = await ytOAuthFetch<YtSubscriptionListResponse>(
        "subscriptions",
        {
          part: "snippet",
          mine: "true",
          forChannelId: chunk.join(","),
          maxResults: "50",
        },
        params.accessToken
      );
      for (const item of outRes.items || []) {
        const targetId = item.snippet?.resourceId?.channelId;
        if (targetId) {
          myOutboundSubscribedSet.add(targetId);
        }
      }
    } catch {
      // Ignore outbound check failure if scope restricted
    }
  }

  const nowIso = new Date().toISOString();
  let confirmedCount = 0;
  let unsubscribedCount = 0;
  let privateOrPendingCount = 0;

  const updatedPartners = params.partners.map((partner) => {
    const next: CrossSubPartner = {
      ...partner,
      myMainChannelSubscribed: myOutboundSubscribedSet.has(partner.channelId),
      lastVerifiedAt: nowIso,
      updatedAt: nowIso,
    };

    const pubSubscribedAt = publicSubMap.get(partner.channelId);
    if (pubSubscribedAt) {
      next.publicSubState = "confirmed_public_sub";
      if (!next.theySubscribedAt) {
        next.theySubscribedAt = pubSubscribedAt;
      }
      if (next.status === "waiting_their_sub") {
        next.status = "completed";
      }
      confirmedCount += 1;
    } else if (
      scanComplete &&
      partner.publicSubState === "confirmed_public_sub"
    ) {
      next.publicSubState = "unsubscribed_detected";
      next.status = "unsubscribed";
      unsubscribedCount += 1;
    } else {
      next.publicSubState = "not_in_public_list";
      privateOrPendingCount += 1;
    }

    return next;
  });

  return {
    updatedPartners,
    confirmedCount,
    unsubscribedCount,
    privateOrPendingCount,
    publicSubscribersScanned: publicSubMap.size,
    recentPublicSubscribers: recentPublicList.slice(0, 15),
  };
}
