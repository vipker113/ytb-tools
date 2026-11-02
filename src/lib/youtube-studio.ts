import { buildDefaultTags } from "./auto-planner";
import {
  findMacEpisodeDirBySlug,
  listMacRenderedEpisodes,
  saveMacEpisodeOverride,
} from "./mac-pipeline";
import { getEffectiveYoutubeKey, writeStore } from "./store";
import type {
  PublishedMacEpisodeRecord,
  StoreData,
  StudioPublishMode,
  YoutubeOAuthState,
  YoutubePlaylistSummary,
} from "./types";

export const YOUTUBE_OAUTH_REDIRECT_URI =
  "http://localhost:3000/api/youtube/oauth/callback";

const YOUTUBE_SCOPES = [
  "https://www.googleapis.com/auth/youtube",
  "https://www.googleapis.com/auth/youtube.force-ssl",
  "https://www.googleapis.com/auth/youtube.upload",
  "https://www.googleapis.com/auth/yt-analytics.readonly",
].join(" ");

export function buildYoutubeOAuthUrl(clientId: string): string {
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.searchParams.set("client_id", clientId.trim());
  url.searchParams.set("redirect_uri", YOUTUBE_OAUTH_REDIRECT_URI);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", YOUTUBE_SCOPES);
  url.searchParams.set("access_type", "offline");
  url.searchParams.set("prompt", "consent select_account");
  return url.toString();
}

export async function exchangeYoutubeAuthCode(params: {
  code: string;
  clientId: string;
  clientSecret: string;
}): Promise<YoutubeOAuthState> {
  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code: params.code,
      client_id: params.clientId.trim(),
      client_secret: params.clientSecret.trim(),
      redirect_uri: YOUTUBE_OAUTH_REDIRECT_URI,
      grant_type: "authorization_code",
    }),
    cache: "no-store",
  });

  const tokenJson = await tokenRes.json();
  if (!tokenRes.ok || !tokenJson.access_token) {
    throw new Error(
      tokenJson.error_description ||
        tokenJson.error ||
        "Không thể đổi mã xác thực OAuth 2.0 với Google."
    );
  }

  const accessToken: string = tokenJson.access_token;
  const refreshToken: string = tokenJson.refresh_token || "";
  const expiresInSec = Number(tokenJson.expires_in || 3500);

  if (!refreshToken) {
    throw new Error(
      "Google không trả về Refresh Token. Hãy thử bấm Kết nối lại và tích chọn đầy đủ quyền."
    );
  }

  // Fetch the authenticated YouTube channel identity
  let connectedChannelId: string | undefined;
  let connectedChannelTitle: string | undefined;
  let connectedChannelHandle: string | undefined;

  const chRes = await fetch(
    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
    {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    }
  );
  if (chRes.ok) {
    const chJson = await chRes.json();
    const first = chJson?.items?.[0];
    if (first) {
      connectedChannelId = first.id;
      connectedChannelTitle = first.snippet?.title;
      connectedChannelHandle = first.snippet?.customUrl;
    }
  }

  return {
    refreshToken,
    accessToken,
    expiresAt: Date.now() + expiresInSec * 1000,
    connectedChannelId,
    connectedChannelTitle,
    connectedChannelHandle,
    hasAnalyticsScope: true,
    connectedAt: new Date().toISOString(),
  };
}

export async function getValidYoutubeAccessToken(
  store: StoreData
): Promise<string> {
  const oauth = store.youtubeOAuth;
  if (!oauth?.refreshToken) {
    throw new Error(
      "Chưa cấp quyền tài khoản YouTube Studio. Hãy bấm nút 'Cấp Quyền YouTube Studio (1-Click)' trước!"
    );
  }

  if (
    oauth.accessToken &&
    oauth.expiresAt &&
    oauth.expiresAt > Date.now() + 60_000
  ) {
    return oauth.accessToken;
  }

  const clientId = (store.settings.googleClientId || "").trim();
  const clientSecret = (store.settings.googleClientSecret || "").trim();
  if (!clientId || !clientSecret) {
    throw new Error("Thiếu Google OAuth Client ID hoặc Client Secret.");
  }

  const res = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      refresh_token: oauth.refreshToken,
      grant_type: "refresh_token",
    }),
    cache: "no-store",
  });

  const json = await res.json();
  if (!res.ok || !json.access_token) {
    throw new Error(
      json.error_description ||
        "Phiên đăng nhập YouTube Studio đã hết hạn. Hãy bấm Kết nối lại YouTube Studio."
    );
  }

  oauth.accessToken = json.access_token;
  oauth.expiresAt = Date.now() + Number(json.expires_in || 3500) * 1000;
  await writeStore(store);

  return json.access_token as string;
}

function sanitizeTagsForYoutube(tags: string[]): string[] {
  const unique: string[] = [];
  const seen = new Set<string>();
  let totalChars = 0;

  for (const raw of tags) {
    const clean = raw
      .replace(/[#<>"]/g, "")
      .trim();
    if (!clean || clean.length > 60) continue;
    const key = clean.toLowerCase();
    if (seen.has(key)) continue;
    if (totalChars + clean.length + 2 > 440) break;
    seen.add(key);
    unique.push(clean);
    totalChars += clean.length + 2;
    if (unique.length >= 20) break;
  }
  return unique;
}

export async function postOwnerCommentIfMissing(params: {
  accessToken: string;
  videoId: string;
  ownerChannelId?: string;
  commentText: string;
}): Promise<{ posted: boolean; reason?: string }> {
  const text = params.commentText.trim();
  if (!text) return { posted: false, reason: "empty" };

  try {
    // Check existing top comments to prevent duplicates
    const checkUrl = new URL(
      "https://www.googleapis.com/youtube/v3/commentThreads"
    );
    checkUrl.searchParams.set("part", "snippet");
    checkUrl.searchParams.set("videoId", params.videoId);
    checkUrl.searchParams.set("maxResults", "15");

    const checkRes = await fetch(checkUrl.toString(), {
      headers: { Authorization: `Bearer ${params.accessToken}` },
      cache: "no-store",
    });

    if (checkRes.ok && params.ownerChannelId) {
      const checkJson = await checkRes.json();
      const items: Array<{
        snippet?: {
          topLevelComment?: {
            snippet?: {
              authorChannelId?: { value?: string };
              textOriginal?: string;
            };
          };
        };
      }> = checkJson?.items || [];

      const alreadyHasOwnerComment = items.some(
        (it) =>
          it.snippet?.topLevelComment?.snippet?.authorChannelId?.value ===
          params.ownerChannelId
      );
      if (alreadyHasOwnerComment) {
        return { posted: false, reason: "already_exists" };
      }
    }

    const postRes = await fetch(
      "https://www.googleapis.com/youtube/v3/commentThreads?part=snippet",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${params.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          snippet: {
            videoId: params.videoId,
            topLevelComment: {
              snippet: {
                textOriginal: text,
              },
            },
          },
        }),
        cache: "no-store",
      }
    );

    if (!postRes.ok) {
      return { posted: false, reason: "api_rejected" };
    }
    return { posted: true };
  } catch {
    return { posted: false, reason: "network_error" };
  }
}

export async function rescueSingleVideoOnStudio(params: {
  accessToken: string;
  videoId: string;
  channelHandle: string;
  ownerChannelId?: string;
  cleanedTitle: string;
  appendDescriptionBlock: string;
  suggestedComment?: string;
  postComment?: boolean;
}): Promise<{
  videoId: string;
  updatedTitle: string;
  commentPosted: boolean;
}> {
  // 1. Fetch exact live snippet & status from YouTube Studio
  const getUrl = new URL("https://www.googleapis.com/youtube/v3/videos");
  getUrl.searchParams.set("part", "snippet,status");
  getUrl.searchParams.set("id", params.videoId);

  const getRes = await fetch(getUrl.toString(), {
    headers: { Authorization: `Bearer ${params.accessToken}` },
    cache: "no-store",
  });
  const getJson = await getRes.json();
  const liveVideo = getJson?.items?.[0];

  if (!getRes.ok || !liveVideo) {
    throw new Error(
      getJson?.error?.message ||
        `Không tìm thấy video ${params.videoId} trong tài khoản YouTube Studio đang kết nối.`
    );
  }

  const existingSnippet = liveVideo.snippet || {};
  const existingStatus = liveVideo.status || {};

  const finalTitle = (params.cleanedTitle || existingSnippet.title || "")
    .replace(/#\S+/g, "")
    .replace(/\s+\?/g, "?")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, 100);

  const oldDesc: string = existingSnippet.description || "";
  const finalDescription = oldDesc.toLowerCase().includes("sub_confirmation=1")
    ? oldDesc
    : `${oldDesc.trimEnd()}\n${params.appendDescriptionBlock}`.slice(0, 4950);

  const mergedTags = sanitizeTagsForYoutube([
    ...(Array.isArray(existingSnippet.tags) ? existingSnippet.tags : []),
    ...buildDefaultTags(finalTitle),
  ]);

  const updatedSnippet: Record<string, unknown> = {
    title: finalTitle,
    description: finalDescription,
    tags: mergedTags,
    categoryId: existingSnippet.categoryId || "28",
  };
  if (existingSnippet.defaultLanguage) {
    updatedSnippet.defaultLanguage = existingSnippet.defaultLanguage;
  }
  if (existingSnippet.defaultAudioLanguage) {
    updatedSnippet.defaultAudioLanguage = existingSnippet.defaultAudioLanguage;
  }

  const updatedStatus: Record<string, unknown> = {
    privacyStatus: existingStatus.privacyStatus || "public",
    publicStatsViewable: true, // Turn ON visible Like count for Social Proof!
  };
  if (typeof existingStatus.selfDeclaredMadeForKids === "boolean") {
    updatedStatus.selfDeclaredMadeForKids =
      existingStatus.selfDeclaredMadeForKids;
  }
  if (typeof existingStatus.embeddable === "boolean") {
    updatedStatus.embeddable = existingStatus.embeddable;
  }
  if (existingStatus.license) {
    updatedStatus.license = existingStatus.license;
  }
  if (existingStatus.publishAt && existingStatus.privacyStatus === "private") {
    updatedStatus.publishAt = existingStatus.publishAt;
  }

  const putRes = await fetch(
    "https://www.googleapis.com/youtube/v3/videos?part=snippet,status",
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: params.videoId,
        snippet: updatedSnippet,
        status: updatedStatus,
      }),
      cache: "no-store",
    }
  );

  const putJson = await putRes.json();
  if (!putRes.ok) {
    throw new Error(
      putJson?.error?.message ||
        `Không thể cập nhật video ${params.videoId} trên YouTube Studio.`
    );
  }

  let commentPosted = false;
  if (
    params.postComment !== false &&
    params.suggestedComment &&
    updatedStatus.privacyStatus === "public"
  ) {
    const cRes = await postOwnerCommentIfMissing({
      accessToken: params.accessToken,
      videoId: params.videoId,
      ownerChannelId: params.ownerChannelId,
      commentText: params.suggestedComment,
    });
    commentPosted = cRes.posted;
  }

  return {
    videoId: params.videoId,
    updatedTitle: finalTitle,
    commentPosted,
  };
}

export async function applyEpisodeMetadataToVideo(params: {
  accessToken: string;
  videoId: string;
  ownerChannelId?: string;
  title: string;
  description: string;
  tags: string[];
  pinnedComment?: string;
  appendToExistingDescription?: boolean;
}): Promise<{ videoId: string; commentPosted: boolean }> {
  const getUrl = new URL("https://www.googleapis.com/youtube/v3/videos");
  getUrl.searchParams.set("part", "snippet,status");
  getUrl.searchParams.set("id", params.videoId);

  const getRes = await fetch(getUrl.toString(), {
    headers: { Authorization: `Bearer ${params.accessToken}` },
    cache: "no-store",
  });
  const getJson = await getRes.json();
  const liveVideo = getJson?.items?.[0];

  if (!getRes.ok || !liveVideo) {
    throw new Error(
      getJson?.error?.message ||
        "Không tìm thấy video này trong tài khoản YouTube Studio của bạn."
    );
  }

  const existingSnippet = liveVideo.snippet || {};
  const existingStatus = liveVideo.status || {};

  const cleanTitle = params.title
    .replace(/#\S+/g, "")
    .trim()
    .slice(0, 100);
  const oldDesc: string = existingSnippet.description || "";
  const finalDesc =
    params.appendToExistingDescription && oldDesc.trim()
      ? `${params.description.trim()}\n\n${oldDesc.trim()}`.slice(0, 4950)
      : params.description.slice(0, 4950);

  const updatedSnippet: Record<string, unknown> = {
    title: cleanTitle,
    description: finalDesc,
    tags: sanitizeTagsForYoutube(params.tags),
    categoryId: existingSnippet.categoryId || "28",
    defaultLanguage: existingSnippet.defaultLanguage || "en",
    defaultAudioLanguage: existingSnippet.defaultAudioLanguage || "en",
  };

  const updatedStatus: Record<string, unknown> = {
    privacyStatus: existingStatus.privacyStatus || "public",
    publicStatsViewable: true,
    selfDeclaredMadeForKids: false,
  };
  if (existingStatus.publishAt && existingStatus.privacyStatus === "private") {
    updatedStatus.publishAt = existingStatus.publishAt;
  }

  const putRes = await fetch(
    "https://www.googleapis.com/youtube/v3/videos?part=snippet,status",
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: params.videoId,
        snippet: updatedSnippet,
        status: updatedStatus,
      }),
      cache: "no-store",
    }
  );
  const putJson = await putRes.json();
  if (!putRes.ok) {
    throw new Error(
      putJson?.error?.message || "Lỗi khi cập nhật Metadata lên YouTube Studio."
    );
  }

  let commentPosted = false;
  if (params.pinnedComment && updatedStatus.privacyStatus === "public") {
    const cRes = await postOwnerCommentIfMissing({
      accessToken: params.accessToken,
      videoId: params.videoId,
      ownerChannelId: params.ownerChannelId,
      commentText: params.pinnedComment,
    });
    commentPosted = cRes.posted;
  }

  return { videoId: params.videoId, commentPosted };
}

export function computeNextAvailableGoldenSlotIso(
  existingScheduledIsos: string[] = []
): string {
  const occupiedDays = new Set(
    existingScheduledIsos
      .map((iso) => {
        const d = new Date(iso);
        return Number.isNaN(d.getTime())
          ? ""
          : d.toISOString().slice(0, 10);
      })
      .filter(Boolean)
  );

  const now = new Date();
  // Target 17:15 ICT (10:15 UTC)
  const candidate = new Date(
    Date.UTC(
      now.getUTCFullYear(),
      now.getUTCMonth(),
      now.getUTCDate(),
      10,
      15,
      0
    )
  );
  if (candidate.getTime() <= now.getTime() + 10 * 60_000) {
    candidate.setUTCDate(candidate.getUTCDate() + 1);
  }

  // Avoid scheduling two Shorts on the exact same golden-hour day
  let guard = 0;
  while (
    occupiedDays.has(candidate.toISOString().slice(0, 10)) &&
    guard < 30
  ) {
    candidate.setUTCDate(candidate.getUTCDate() + 1);
    guard++;
  }

  return candidate.toISOString();
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function listChannelPlaylists(
  accessToken: string
): Promise<YoutubePlaylistSummary[]> {
  const url = new URL("https://www.googleapis.com/youtube/v3/playlists");
  url.searchParams.set("part", "snippet,contentDetails,status");
  url.searchParams.set("mine", "true");
  url.searchParams.set("maxResults", "50");

  const res = await fetch(url.toString(), {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  const json = await res.json();
  if (!res.ok) {
    throw new Error(
      json?.error?.message || "Không thể tải danh sách Playlist từ YouTube Studio."
    );
  }

  return ((json?.items || []) as Array<{
    id?: string;
    snippet?: {
      title?: string;
      description?: string;
      thumbnails?: {
        medium?: { url?: string };
        default?: { url?: string };
      };
    };
    contentDetails?: { itemCount?: number };
    status?: { privacyStatus?: string };
  }>)
    .filter((it) => Boolean(it.id))
    .map((it) => ({
      id: String(it.id),
      title: String(it.snippet?.title || "Untitled Playlist"),
      description: String(it.snippet?.description || ""),
      itemCount: Number(it.contentDetails?.itemCount || 0),
      privacyStatus: String(it.status?.privacyStatus || "public"),
      thumbnailUrl:
        it.snippet?.thumbnails?.medium?.url ||
        it.snippet?.thumbnails?.default?.url,
    }));
}

export async function createChannelPlaylist(params: {
  accessToken: string;
  title: string;
  description?: string;
  privacyStatus?: "public" | "unlisted" | "private";
}): Promise<YoutubePlaylistSummary> {
  const cleanTitle = params.title.trim().slice(0, 140);
  if (!cleanTitle) {
    throw new Error("Vui lòng nhập tên Playlist mới.");
  }

  const res = await fetch(
    "https://www.googleapis.com/youtube/v3/playlists?part=snippet,status",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        snippet: {
          title: cleanTitle,
          description: (params.description || "").slice(0, 4900),
          defaultLanguage: "en",
        },
        status: {
          privacyStatus: params.privacyStatus || "public",
        },
      }),
      cache: "no-store",
    }
  );
  const json = await res.json();
  if (!res.ok || !json?.id) {
    throw new Error(
      json?.error?.message || "Không thể tạo Playlist mới trên YouTube Studio."
    );
  }

  return {
    id: String(json.id),
    title: String(json.snippet?.title || cleanTitle),
    description: String(json.snippet?.description || ""),
    itemCount: 0,
    privacyStatus: String(json.status?.privacyStatus || "public"),
  };
}

export async function addVideoToPlaylistIfMissing(params: {
  accessToken: string;
  playlistId?: string;
  videoId: string;
}): Promise<{
  added: boolean;
  alreadyInPlaylist?: boolean;
  error?: string;
}> {
  const playlistId = (params.playlistId || "").trim();
  if (!playlistId || playlistId === "none") {
    return { added: false };
  }

  try {
    const checkUrl = new URL(
      "https://www.googleapis.com/youtube/v3/playlistItems"
    );
    checkUrl.searchParams.set("part", "id");
    checkUrl.searchParams.set("playlistId", playlistId);
    checkUrl.searchParams.set("videoId", params.videoId);
    checkUrl.searchParams.set("maxResults", "5");

    const checkRes = await fetch(checkUrl.toString(), {
      headers: { Authorization: `Bearer ${params.accessToken}` },
      cache: "no-store",
    });
    if (checkRes.ok) {
      const checkJson = await checkRes.json();
      if (Array.isArray(checkJson?.items) && checkJson.items.length > 0) {
        return { added: true, alreadyInPlaylist: true };
      }
    }

    const insRes = await fetch(
      "https://www.googleapis.com/youtube/v3/playlistItems?part=snippet",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${params.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          snippet: {
            playlistId,
            resourceId: {
              kind: "youtube#video",
              videoId: params.videoId,
            },
          },
        }),
        cache: "no-store",
      }
    );
    const insJson = await insRes.json().catch(() => ({}));
    if (!insRes.ok) {
      return {
        added: false,
        error:
          insJson?.error?.message ||
          `Không thể thêm video vào Playlist (HTTP ${insRes.status}).`,
      };
    }
    return { added: true };
  } catch (err) {
    return {
      added: false,
      error: err instanceof Error ? err.message : "Lỗi kết nối Playlist API.",
    };
  }
}

async function uploadThumbnailWithRetry(params: {
  accessToken: string;
  videoId: string;
  thumbnailBuffer: ArrayBuffer;
  thumbnailMimeType?: string;
  initialDelayMs?: number;
}): Promise<{ uploaded: boolean; error?: string }> {
  if (params.initialDelayMs && params.initialDelayMs > 0) {
    await sleep(params.initialDelayMs);
  }

  let lastError = "";
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const thumbRes = await fetch(
        `https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${encodeURIComponent(
          params.videoId
        )}&uploadType=media`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${params.accessToken}`,
            "Content-Type": params.thumbnailMimeType || "image/jpeg",
            "Content-Length": String(params.thumbnailBuffer.byteLength),
          },
          body: params.thumbnailBuffer,
          cache: "no-store",
        }
      );

      if (thumbRes.ok) {
        return { uploaded: true };
      }

      const errJson = await thumbRes.json().catch(() => ({}));
      lastError =
        errJson?.error?.message || `HTTP ${thumbRes.status} khi tải Thumbnail`;

      // Permanent permission error (e.g., unverified phone number for custom thumbnails)
      if (thumbRes.status === 403) {
        return { uploaded: false, error: lastError };
      }

      if (attempt < 3) {
        await sleep(1400 * attempt);
      }
    } catch (err) {
      lastError =
        err instanceof Error ? err.message : "Lỗi mạng khi tải Thumbnail";
      if (attempt < 3) {
        await sleep(1200 * attempt);
      }
    }
  }

  return { uploaded: false, error: lastError || "Không thể đặt Thumbnail" };
}

function resolvePrivacyAndSchedule(params: {
  publishMode: StudioPublishMode;
  customPublishAtIso?: string;
  existingScheduledIsos?: string[];
}): {
  privacyStatus: "private" | "unlisted" | "public";
  publishAtIso?: string;
} {
  if (params.publishMode === "private_draft") {
    return { privacyStatus: "private" };
  }
  if (params.publishMode === "unlisted") {
    return { privacyStatus: "unlisted" };
  }
  if (params.publishMode === "schedule_golden") {
    let publishAtIso: string | undefined;
    if (params.customPublishAtIso) {
      const parsed = new Date(params.customPublishAtIso);
      if (!Number.isNaN(parsed.getTime()) && parsed.getTime() > Date.now() + 60_000) {
        publishAtIso = parsed.toISOString();
      }
    }
    if (!publishAtIso) {
      publishAtIso = computeNextAvailableGoldenSlotIso(
        params.existingScheduledIsos
      );
    }
    return { privacyStatus: "private", publishAtIso };
  }
  return { privacyStatus: "public" };
}

export async function uploadShortVideoToStudio(params: {
  accessToken: string;
  ownerChannelId?: string;
  videoBuffer: ArrayBuffer;
  mimeType: string;
  thumbnailBuffer?: ArrayBuffer | null;
  thumbnailMimeType?: string;
  title: string;
  description: string;
  tags: string[];
  pinnedComment?: string;
  publishMode: StudioPublishMode;
  customPublishAtIso?: string;
  existingScheduledIsos?: string[];
  playlistId?: string;
  hasPaidProductPlacement?: boolean;
  selfDeclaredMadeForKids?: boolean;
  containsSyntheticMedia?: boolean;
}): Promise<{
  videoId: string;
  studioEditUrl: string;
  watchUrl: string;
  privacyStatus: "private" | "unlisted" | "public";
  scheduledAt?: string;
  commentPosted: boolean;
  thumbnailUploaded: boolean;
  thumbnailError?: string;
  playlistAdded: boolean;
  playlistError?: string;
}> {
  const { privacyStatus, publishAtIso } = resolvePrivacyAndSchedule({
    publishMode: params.publishMode,
    customPublishAtIso: params.customPublishAtIso,
    existingScheduledIsos: params.existingScheduledIsos,
  });

  const madeForKids = Boolean(params.selfDeclaredMadeForKids ?? false);
  const containsSyntheticMedia = Boolean(
    params.containsSyntheticMedia ?? false
  );
  const hasPaidProductPlacement = Boolean(
    params.hasPaidProductPlacement ?? false
  );

  const snippetPayload = {
    title: params.title.replace(/#\S+/g, "").trim().slice(0, 100),
    description: params.description.slice(0, 4950),
    tags: sanitizeTagsForYoutube(params.tags),
    categoryId: "28", // Science & Technology
    defaultLanguage: "en",
    defaultAudioLanguage: "en",
  };

  const statusPayload: Record<string, unknown> = {
    privacyStatus,
    ...(publishAtIso ? { publishAt: publishAtIso } : {}),
    selfDeclaredMadeForKids: madeForKids,
    containsSyntheticMedia,
    publicStatsViewable: true,
    embeddable: true,
  };

  // Step 1: Initiate YouTube Resumable Upload session (with paidProductPlacementDetails + graceful fallback)
  let initRes = await fetch(
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status,paidProductPlacementDetails",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": String(params.videoBuffer.byteLength),
        "X-Upload-Content-Type": params.mimeType || "video/mp4",
      },
      body: JSON.stringify({
        snippet: snippetPayload,
        status: statusPayload,
        paidProductPlacementDetails: {
          hasPaidProductPlacement,
        },
      }),
      cache: "no-store",
    }
  );

  if (!initRes.ok && initRes.status === 400) {
    // Fallback without paidProductPlacementDetails part if rejected
    initRes = await fetch(
      "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${params.accessToken}`,
          "Content-Type": "application/json; charset=UTF-8",
          "X-Upload-Content-Length": String(params.videoBuffer.byteLength),
          "X-Upload-Content-Type": params.mimeType || "video/mp4",
        },
        body: JSON.stringify({
          snippet: snippetPayload,
          status: statusPayload,
        }),
        cache: "no-store",
      }
    );
  }

  if (!initRes.ok) {
    const errJson = await initRes.json().catch(() => ({}));
    throw new Error(
      errJson?.error?.message ||
        `Không thể khởi tạo phiên Upload lên YouTube (HTTP ${initRes.status}).`
    );
  }

  const uploadUrl = initRes.headers.get("location");
  if (!uploadUrl) {
    throw new Error("YouTube API không trả về đường dẫn Resumable Upload.");
  }

  // Step 2: Upload binary video bytes
  const putRes = await fetch(uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": params.mimeType || "video/mp4",
      "Content-Length": String(params.videoBuffer.byteLength),
    },
    body: params.videoBuffer,
    cache: "no-store",
  });

  const videoJson = await putRes.json();
  if (!putRes.ok || !videoJson?.id) {
    throw new Error(
      videoJson?.error?.message ||
        "Lỗi trong quá trình truyền file video lên YouTube."
    );
  }

  const videoId: string = videoJson.id;
  let thumbnailUploaded = false;
  let thumbnailError: string | undefined;

  if (params.thumbnailBuffer && params.thumbnailBuffer.byteLength > 0) {
    const tRes = await uploadThumbnailWithRetry({
      accessToken: params.accessToken,
      videoId,
      thumbnailBuffer: params.thumbnailBuffer,
      thumbnailMimeType: params.thumbnailMimeType,
      initialDelayMs: 1200,
    });
    thumbnailUploaded = tRes.uploaded;
    thumbnailError = tRes.error;
  }

  let playlistAdded = false;
  let playlistError: string | undefined;
  if (params.playlistId && params.playlistId !== "none") {
    const plRes = await addVideoToPlaylistIfMissing({
      accessToken: params.accessToken,
      playlistId: params.playlistId,
      videoId,
    });
    playlistAdded = plRes.added;
    playlistError = plRes.error;
  }

  let commentPosted = false;
  if (
    (privacyStatus === "public" || privacyStatus === "unlisted") &&
    params.pinnedComment
  ) {
    const cRes = await postOwnerCommentIfMissing({
      accessToken: params.accessToken,
      videoId,
      ownerChannelId: params.ownerChannelId,
      commentText: params.pinnedComment,
    });
    commentPosted = cRes.posted;
  }

  return {
    videoId,
    studioEditUrl: `https://studio.youtube.com/video/${videoId}/edit`,
    watchUrl: `https://www.youtube.com/shorts/${videoId}`,
    privacyStatus,
    scheduledAt: publishAtIso,
    commentPosted,
    thumbnailUploaded,
    thumbnailError,
    playlistAdded,
    playlistError,
  };
}

export async function updateOrPromoteStudioVideo(params: {
  accessToken: string;
  videoId: string;
  ownerChannelId?: string;
  title: string;
  description: string;
  tags: string[];
  pinnedComment?: string;
  publishMode: StudioPublishMode;
  customPublishAtIso?: string;
  existingScheduledIsos?: string[];
  thumbnailBuffer?: ArrayBuffer | null;
  thumbnailMimeType?: string;
  playlistId?: string;
  hasPaidProductPlacement?: boolean;
  selfDeclaredMadeForKids?: boolean;
  containsSyntheticMedia?: boolean;
}): Promise<{
  videoId: string;
  studioEditUrl: string;
  watchUrl: string;
  privacyStatus: "private" | "unlisted" | "public";
  scheduledAt?: string;
  commentPosted: boolean;
  thumbnailUploaded: boolean;
  thumbnailError?: string;
  playlistAdded: boolean;
  playlistError?: string;
}> {
  const getUrl = new URL("https://www.googleapis.com/youtube/v3/videos");
  getUrl.searchParams.set("part", "snippet,status");
  getUrl.searchParams.set("id", params.videoId);

  const getRes = await fetch(getUrl.toString(), {
    headers: { Authorization: `Bearer ${params.accessToken}` },
    cache: "no-store",
  });
  const getJson = await getRes.json();
  const liveVideo = getJson?.items?.[0];

  if (!getRes.ok || !liveVideo) {
    throw new Error(
      getJson?.error?.message ||
        `Video (${params.videoId}) không còn tồn tại trên YouTube Studio (có thể đã bị xóa). Hãy bấm Đồng bộ Kênh!`
    );
  }

  const existingSnippet = liveVideo.snippet || {};

  const { privacyStatus, publishAtIso } = resolvePrivacyAndSchedule({
    publishMode: params.publishMode,
    customPublishAtIso: params.customPublishAtIso,
    existingScheduledIsos: params.existingScheduledIsos,
  });

  const madeForKids = Boolean(params.selfDeclaredMadeForKids ?? false);
  const containsSyntheticMedia = Boolean(
    params.containsSyntheticMedia ?? false
  );
  const hasPaidProductPlacement = Boolean(
    params.hasPaidProductPlacement ?? false
  );

  const cleanTitle = params.title.replace(/#\S+/g, "").trim().slice(0, 100);
  const updatedSnippet: Record<string, unknown> = {
    title: cleanTitle,
    description: params.description.slice(0, 4950),
    tags: sanitizeTagsForYoutube(params.tags),
    categoryId: existingSnippet.categoryId || "28",
    defaultLanguage: existingSnippet.defaultLanguage || "en",
    defaultAudioLanguage: existingSnippet.defaultAudioLanguage || "en",
  };

  const updatedStatus: Record<string, unknown> = {
    privacyStatus,
    ...(publishAtIso ? { publishAt: publishAtIso } : {}),
    selfDeclaredMadeForKids: madeForKids,
    containsSyntheticMedia,
    publicStatsViewable: true,
    embeddable: true,
  };

  let putRes = await fetch(
    "https://www.googleapis.com/youtube/v3/videos?part=snippet,status,paidProductPlacementDetails",
    {
      method: "PUT",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        id: params.videoId,
        snippet: updatedSnippet,
        status: updatedStatus,
        paidProductPlacementDetails: {
          hasPaidProductPlacement,
        },
      }),
      cache: "no-store",
    }
  );

  if (!putRes.ok && putRes.status === 400) {
    putRes = await fetch(
      "https://www.googleapis.com/youtube/v3/videos?part=snippet,status",
      {
        method: "PUT",
        headers: {
          Authorization: `Bearer ${params.accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          id: params.videoId,
          snippet: updatedSnippet,
          status: updatedStatus,
        }),
        cache: "no-store",
      }
    );
  }

  const putJson = await putRes.json();
  if (!putRes.ok) {
    throw new Error(
      putJson?.error?.message ||
        "Không thể cập nhật trạng thái phát sóng trên YouTube Studio."
    );
  }

  let thumbnailUploaded = false;
  let thumbnailError: string | undefined;
  if (params.thumbnailBuffer && params.thumbnailBuffer.byteLength > 0) {
    const tRes = await uploadThumbnailWithRetry({
      accessToken: params.accessToken,
      videoId: params.videoId,
      thumbnailBuffer: params.thumbnailBuffer,
      thumbnailMimeType: params.thumbnailMimeType,
    });
    thumbnailUploaded = tRes.uploaded;
    thumbnailError = tRes.error;
  }

  let playlistAdded = false;
  let playlistError: string | undefined;
  if (params.playlistId && params.playlistId !== "none") {
    const plRes = await addVideoToPlaylistIfMissing({
      accessToken: params.accessToken,
      playlistId: params.playlistId,
      videoId: params.videoId,
    });
    playlistAdded = plRes.added;
    playlistError = plRes.error;
  }

  let commentPosted = false;
  if (
    (privacyStatus === "public" || privacyStatus === "unlisted") &&
    params.pinnedComment
  ) {
    const cRes = await postOwnerCommentIfMissing({
      accessToken: params.accessToken,
      videoId: params.videoId,
      ownerChannelId: params.ownerChannelId,
      commentText: params.pinnedComment,
    });
    commentPosted = cRes.posted;
  }

  return {
    videoId: params.videoId,
    studioEditUrl: `https://studio.youtube.com/video/${params.videoId}/edit`,
    watchUrl: `https://www.youtube.com/shorts/${params.videoId}`,
    privacyStatus,
    scheduledAt: publishAtIso,
    commentPosted,
    thumbnailUploaded,
    thumbnailError,
    playlistAdded,
    playlistError,
  };
}

interface RawLiveYoutubeVideoItem {
  id: string;
  snippet?: {
    title?: string;
    description?: string;
    tags?: string[];
  };
  status?: {
    uploadStatus?: string;
    privacyStatus?: string;
    publishAt?: string;
    madeForKids?: boolean;
    selfDeclaredMadeForKids?: boolean;
    containsSyntheticMedia?: boolean;
  };
  statistics?: {
    viewCount?: string;
    likeCount?: string;
    commentCount?: string;
  };
  paidProductPlacementDetails?: {
    hasPaidProductPlacement?: boolean;
  };
}

/**
 * True Two-Way YouTube Studio Reconciliation (0s CDN lag via OAuth videos.list, 1 quota unit):
 * 1. Detects videos deleted on YouTube Studio -> removes stale `publishedMacEpisodes[slug]`
 *    (resetting episode back to "Mới • Chờ duyệt") AND purges deleted IDs from `recentVideos`.
 * 2. Detects videos edited on YouTube Studio (title, description, tags, privacyStatus,
 *    schedule time, kids/AI/ad flags) -> updates `publishedMacEpisodes[slug]`, `recentVideos`,
 *    AND syncs updated title/description/tags into `web_metadata_override.json` on Mac!
 */
export async function reconcileStudioState(store: StoreData): Promise<{
  checkedCount: number;
  deletedSlugs: string[];
  deletedTitles: string[];
  updatedSlugs: string[];
  deletedRecentCount: number;
  summaryMessage: string | null;
}> {
  const result = {
    checkedCount: 0,
    deletedSlugs: [] as string[],
    deletedTitles: [] as string[],
    updatedSlugs: [] as string[],
    deletedRecentCount: 0,
    summaryMessage: null as string | null,
  };

  let accessToken: string | null = null;
  if (store.youtubeOAuth?.refreshToken) {
    try {
      accessToken = await getValidYoutubeAccessToken(store);
    } catch {
      accessToken = null;
    }
  }

  const apiKey = getEffectiveYoutubeKey(store);
  if (!accessToken && !apiKey) {
    return result;
  }

  const activeCh =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];

  const publishedEntries = Object.entries(store.publishedMacEpisodes || {});
  const idSet = new Set<string>();
  for (const [, rec] of publishedEntries) {
    if (rec?.videoId) idSet.add(rec.videoId);
  }
  if (activeCh && !activeCh.isDemo) {
    for (const v of activeCh.recentVideos || []) {
      if (v?.id) idSet.add(v.id);
    }
  }

  const allIds = Array.from(idSet);
  if (allIds.length === 0) {
    return result;
  }

  const liveMap = new Map<string, RawLiveYoutubeVideoItem>();

  for (let i = 0; i < allIds.length; i += 45) {
    const chunk = allIds.slice(i, i + 45);
    const url = new URL("https://www.googleapis.com/youtube/v3/videos");
    url.searchParams.set(
      "part",
      accessToken
        ? "snippet,status,statistics,paidProductPlacementDetails"
        : "snippet,status,statistics"
    );
    url.searchParams.set("id", chunk.join(","));
    if (!accessToken && apiKey) {
      url.searchParams.set("key", apiKey);
    }

    const res = await fetch(url.toString(), {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
      cache: "no-store",
    });

    // Never mutate state if the network/API request itself errored
    if (!res.ok) {
      return result;
    }

    const json = await res.json();
    for (const item of (json?.items || []) as RawLiveYoutubeVideoItem[]) {
      if (item?.id) {
        liveMap.set(item.id, item);
      }
    }
  }

  result.checkedCount = allIds.length;

  // 1. Reconcile store.publishedMacEpisodes
  if (store.publishedMacEpisodes) {
    for (const [slug, rec] of publishedEntries) {
      if (!rec?.videoId) continue;
      // If local episode folder was deleted or renamed on disk, prune stale slug key
      const dirExists = await findMacEpisodeDirBySlug(slug);
      if (!dirExists) {
        delete store.publishedMacEpisodes[slug];
        continue;
      }
      const live = liveMap.get(rec.videoId);
      const uploadStatus = live?.status?.uploadStatus || "";

      const isConfirmedMissingOrDeleted =
        (!live &&
          (Boolean(accessToken) ||
            rec.status === "public" ||
            rec.status === "unlisted")) ||
        uploadStatus === "deleted" ||
        uploadStatus === "rejected" ||
        uploadStatus === "failed";

      if (isConfirmedMissingOrDeleted) {
        delete store.publishedMacEpisodes[slug];
        result.deletedSlugs.push(slug);
        result.deletedTitles.push(rec.title || slug);
        continue;
      }

      if (live) {
        const privacy = live.status?.privacyStatus || "private";
        const publishAt = live.status?.publishAt;
        let nextStatus: PublishedMacEpisodeRecord["status"] = "private_draft";
        let mappedPublishMode: StudioPublishMode = "private_draft";

        if (privacy === "public") {
          nextStatus = "public";
          mappedPublishMode = "public_now";
        } else if (privacy === "unlisted") {
          nextStatus = "unlisted";
          mappedPublishMode = "unlisted";
        } else if (
          privacy === "private" &&
          publishAt &&
          new Date(publishAt).getTime() > Date.now()
        ) {
          nextStatus = "scheduled";
          mappedPublishMode = "schedule_golden";
        }

        const liveTitle = (live.snippet?.title || rec.title || "").trim();
        const liveDesc = live.snippet?.description;
        const liveTags = Array.isArray(live.snippet?.tags)
          ? live.snippet!.tags!
          : undefined;
        const liveViews = Number(live.statistics?.viewCount ?? rec.liveViews ?? 0);
        const liveLikes = Number(live.statistics?.likeCount ?? rec.liveLikes ?? 0);
        const liveKids = Boolean(
          live.status?.selfDeclaredMadeForKids ??
            live.status?.madeForKids ??
            rec.selfDeclaredMadeForKids ??
            false
        );
        const liveSynthetic = Boolean(
          live.status?.containsSyntheticMedia ??
            rec.containsSyntheticMedia ??
            false
        );
        const livePaid = Boolean(
          live.paidProductPlacementDetails?.hasPaidProductPlacement ??
            rec.hasPaidProductPlacement ??
            false
        );

        const descChanged =
          typeof liveDesc === "string" &&
          rec.description !== undefined &&
          liveDesc !== rec.description;
        const tagsChanged =
          Boolean(liveTags) &&
          Array.isArray(rec.tags) &&
          JSON.stringify(liveTags) !== JSON.stringify(rec.tags);

        const metadataChanged =
          liveTitle !== rec.title ||
          descChanged ||
          tagsChanged ||
          nextStatus !== rec.status ||
          (publishAt || undefined) !== (rec.scheduledAt || undefined) ||
          liveKids !== Boolean(rec.selfDeclaredMadeForKids) ||
          liveSynthetic !== Boolean(rec.containsSyntheticMedia) ||
          livePaid !== Boolean(rec.hasPaidProductPlacement);

        store.publishedMacEpisodes[slug] = {
          ...rec,
          status: nextStatus,
          scheduledAt: nextStatus === "scheduled" ? publishAt : undefined,
          title: liveTitle || rec.title,
          description:
            typeof liveDesc === "string" ? liveDesc : rec.description,
          tags: liveTags ?? rec.tags,
          hasPaidProductPlacement: livePaid,
          selfDeclaredMadeForKids: liveKids,
          containsSyntheticMedia: liveSynthetic,
          liveViews,
          liveLikes,
          updatedAt: new Date().toISOString(),
        };

        // Only overwrite local override when Studio state genuinely changed since last snapshot
        if (metadataChanged) {
          await saveMacEpisodeOverride(slug, {
            ...(liveTitle ? { title: liveTitle } : {}),
            ...(typeof liveDesc === "string" ? { description: liveDesc } : {}),
            ...(liveTags ? { tags: liveTags } : {}),
            publishMode: mappedPublishMode,
            customPublishAtIso:
              nextStatus === "scheduled" ? publishAt : undefined,
            hasPaidProductPlacement: livePaid,
            selfDeclaredMadeForKids: liveKids,
            containsSyntheticMedia: liveSynthetic,
          }).catch(() => {});
          result.updatedSlugs.push(slug);
        }
      }
    }
  }

  // 2. Reconcile activeCh.recentVideos immediately (eliminates 2-minute YouTube public CDN lag!)
  if (activeCh && !activeCh.isDemo && Array.isArray(activeCh.recentVideos)) {
    const beforeLen = activeCh.recentVideos.length;
    const survivingVideos = [];

    for (const vid of activeCh.recentVideos) {
      const live = liveMap.get(vid.id);
      if (!live) {
        // Confirmed deleted on YouTube Studio
        continue;
      }
      const privacy = live.status?.privacyStatus || "public";
      const uploadStatus = live.status?.uploadStatus || "";
      if (
        privacy === "private" ||
        uploadStatus === "deleted" ||
        uploadStatus === "rejected"
      ) {
        continue;
      }

      const views = Number(live.statistics?.viewCount ?? vid.views);
      const likes = Number(live.statistics?.likeCount ?? vid.likes);
      const comments = Number(live.statistics?.commentCount ?? vid.comments);
      const engagementRate =
        views > 0 ? Number((((likes + comments) / views) * 100).toFixed(2)) : 0;

      survivingVideos.push({
        ...vid,
        title: live.snippet?.title ? live.snippet.title : vid.title,
        description:
          typeof live.snippet?.description === "string"
            ? live.snippet.description
            : vid.description,
        tags: Array.isArray(live.snippet?.tags) ? live.snippet.tags : vid.tags,
        views,
        likes,
        comments,
        engagementRate,
      });
    }

    const removedCount = beforeLen - survivingVideos.length;
    if (removedCount > 0) {
      result.deletedRecentCount = removedCount;
      activeCh.videoCount = Math.max(
        survivingVideos.length,
        activeCh.videoCount - removedCount
      );
    }
    activeCh.recentVideos = survivingVideos;

    // 3. Anchor any pre-existing published local Mac episode by videoId once so future
    // Studio title rewrites, privacy changes, or deletions are tracked 100% by ID!
    try {
      store.publishedMacEpisodes = store.publishedMacEpisodes || {};
      const claimedVideoIds = new Set(
        Object.values(store.publishedMacEpisodes).map((r) => r.videoId)
      );
      const macEpisodes = await listMacRenderedEpisodes(
        activeCh.handle || "@proofofwonderscience",
        {
          publishedRecords: store.publishedMacEpisodes,
          recentVideos: survivingVideos,
        }
      );
      for (const ep of macEpisodes) {
        const vidId = ep.youtubeState.videoId;
        if (
          !vidId ||
          store.publishedMacEpisodes[ep.slug] ||
          claimedVideoIds.has(vidId)
        ) {
          continue;
        }
        const live = liveMap.get(vidId);
        if (!live) continue;
        claimedVideoIds.add(vidId);
        store.publishedMacEpisodes[ep.slug] = {
          slug: ep.slug,
          videoId: vidId,
          status: "public",
          watchUrl: `https://www.youtube.com/shorts/${vidId}`,
          studioEditUrl: `https://studio.youtube.com/video/${vidId}/edit`,
          title: live.snippet?.title || ep.primaryTitle,
          description: live.snippet?.description,
          tags: Array.isArray(live.snippet?.tags)
            ? live.snippet.tags
            : undefined,
          hasPaidProductPlacement: Boolean(
            live.paidProductPlacementDetails?.hasPaidProductPlacement ?? false
          ),
          selfDeclaredMadeForKids: Boolean(
            live.status?.selfDeclaredMadeForKids ??
              live.status?.madeForKids ??
              false
          ),
          containsSyntheticMedia: Boolean(
            live.status?.containsSyntheticMedia ?? false
          ),
          liveViews: Number(live.statistics?.viewCount ?? 0),
          liveLikes: Number(live.statistics?.likeCount ?? 0),
          updatedAt: new Date().toISOString(),
        };
      }
    } catch {
      // ignore local disk scan error
    }
  }

  const parts: string[] = [];
  if (result.deletedSlugs.length > 0) {
    parts.push(
      `phát hiện ${result.deletedSlugs.length} video đã xóa trên Studio (${result.deletedTitles
        .map((t) => `"${t.slice(0, 38)}"`)
        .join(", ")}) → đã chuyển về Chờ duyệt`
    );
  }
  if (result.updatedSlugs.length > 0) {
    parts.push(
      `cập nhật trạng thái/nội dung mới nhất từ Studio cho ${result.updatedSlugs.length} video`
    );
  }

  if (parts.length > 0) {
    result.summaryMessage = `🔄 Đồng bộ 2 chiều Studio: Đã ${parts.join(" & ")}!`;
  }

  return result;
}
