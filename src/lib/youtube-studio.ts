import { buildDefaultTags } from "./auto-planner";
import { writeStore } from "./store";
import type { StoreData, YoutubeOAuthState } from "./types";

export const YOUTUBE_OAUTH_REDIRECT_URI =
  "http://localhost:3000/api/youtube/oauth/callback";

const YOUTUBE_SCOPES = [
  "https://www.googleapis.com/auth/youtube",
  "https://www.googleapis.com/auth/youtube.force-ssl",
  "https://www.googleapis.com/auth/youtube.upload",
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

export async function uploadShortVideoToStudio(params: {
  accessToken: string;
  ownerChannelId?: string;
  videoBuffer: ArrayBuffer;
  mimeType: string;
  title: string;
  description: string;
  tags: string[];
  pinnedComment?: string;
  publishMode: "schedule_golden" | "public_now" | "private_draft";
  customPublishAtIso?: string;
}): Promise<{
  videoId: string;
  studioEditUrl: string;
  watchUrl: string;
  scheduledAt?: string;
  commentPosted: boolean;
}> {
  // Compute next 17:15 Vietnam Time (+07:00) if schedule_golden
  let publishAtIso: string | undefined;
  let privacyStatus: "private" | "public" = "public";

  if (params.publishMode === "private_draft") {
    privacyStatus = "private";
  } else if (params.publishMode === "schedule_golden") {
    privacyStatus = "private";
    if (params.customPublishAtIso) {
      publishAtIso = new Date(params.customPublishAtIso).toISOString();
    } else {
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
      publishAtIso = candidate.toISOString();
    }
  }

  const metadataBody = {
    snippet: {
      title: params.title.replace(/#\S+/g, "").trim().slice(0, 100),
      description: params.description.slice(0, 4950),
      tags: sanitizeTagsForYoutube(params.tags),
      categoryId: "28", // Science & Technology
      defaultLanguage: "en",
      defaultAudioLanguage: "en",
    },
    status: {
      privacyStatus,
      ...(publishAtIso ? { publishAt: publishAtIso } : {}),
      selfDeclaredMadeForKids: false,
      publicStatsViewable: true,
    },
  };

  // Step 1: Initiate YouTube Resumable Upload session
  const initRes = await fetch(
    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${params.accessToken}`,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Length": String(params.videoBuffer.byteLength),
        "X-Upload-Content-Type": params.mimeType || "video/mp4",
      },
      body: JSON.stringify(metadataBody),
      cache: "no-store",
    }
  );

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
  let commentPosted = false;

  if (privacyStatus === "public" && params.pinnedComment) {
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
    scheduledAt: publishAtIso,
    commentPosted,
  };
}
