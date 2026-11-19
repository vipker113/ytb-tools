import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { hasCloudKv, kvGetJson, kvSetJson } from "./cloud-kv";
import {
  ensureSessionDir,
  resolveBuiltinBgmPath,
  resolvePythonBin,
} from "./reup-studio-server";
import { readStore } from "./store";
import {
  getValidYoutubeAccessToken,
  uploadShortVideoToStudio,
} from "./youtube-studio";

export interface KiPointWeights {
  view: number;
  like: number;
  comment: number;
  sub: number;
}

export interface KiLiveStats {
  views: number;
  likes: number;
  comments: number;
  channelSubs: number;
  gainedSubs: number;
}

export type KiTitleMilestone = 0 | 25 | 50 | 75 | 100;

export const KI_MILESTONE_CHECKPOINTS: KiTitleMilestone[] = [25, 50, 75, 100];

export function computeReachedKiMilestone(
  ki: number,
  targetKi: number
): KiTitleMilestone {
  const pct = (Math.max(0, ki) / Math.max(1, targetKi)) * 100;
  if (pct >= 100) return 100;
  if (pct >= 75) return 75;
  if (pct >= 50) return 50;
  if (pct >= 25) return 25;
  return 0;
}

export interface KiChallengeTrackerItem {
  id: string;
  videoId: string;
  characterName: string;
  episodeNumber: number;
  currentStageId: string;
  currentStageLabel: string;
  currentStageMediaUrl?: string;
  currentAuraHex?: string;
  nextStageId: string;
  nextStageLabel: string;
  nextStageMediaUrl?: string;
  nextAuraHex?: string;
  mysteryNext?: boolean;
  targetKi: number;
  weights: KiPointWeights;
  baselineSubscribers: number;
  manualBonusSubs: number;
  titleTemplate: string;
  goalReachedTitleTemplate: string;
  autoSyncEnabled: boolean;
  syncIntervalMin: number;
  currentKi: number;
  lastSyncedMilestone: KiTitleMilestone;
  lastStats?: KiLiveStats;
  lastSyncedYoutubeTitle?: string;
  lastCheckedAt?: string;
  lastUpdatedYoutubeAt?: string;
  goalReachedAt?: string | null;
  lastError?: string | null;
  watchUrl: string;
  studioEditUrl: string;
  createdAt: string;
}

interface KiChallengeStoreFile {
  items: KiChallengeTrackerItem[];
}

const DATA_DIR = path.resolve(process.cwd(), "data");
const KI_STORE_PATH = path.join(DATA_DIR, "ki-challenges.json");
const CLOUD_KI_KEY = "ytb:ki-challenges:v1";
const CUSTOM_ART_DIR = path.resolve(process.cwd(), "public/ki-challenge/custom");
const CUSTOM_AUDIO_DIR = path.resolve(process.cwd(), "public/ki-challenge/custom-audio");

const globalForKiDaemon = globalThis as unknown as {
  __kiChallengeDaemonTimer?: ReturnType<typeof setInterval>;
  __kiChallengeDaemonBusy?: boolean;
};

export function readKiChallenges(): KiChallengeTrackerItem[] {
  try {
    if (!fs.existsSync(KI_STORE_PATH)) {
      return [];
    }
    const raw = fs.readFileSync(KI_STORE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as Partial<KiChallengeStoreFile>;
    return Array.isArray(parsed.items) ? parsed.items : [];
  } catch {
    return [];
  }
}

export function writeKiChallenges(items: KiChallengeTrackerItem[]): void {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    const tmp = `${KI_STORE_PATH}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify({ items }, null, 2), "utf-8");
    fs.renameSync(tmp, KI_STORE_PATH);
  } catch {
    // Vercel serverless filesystem is read-only; cloud KV handles persistence
  }
}

export async function readKiChallengesAsync(): Promise<KiChallengeTrackerItem[]> {
  if (hasCloudKv()) {
    const cloud = await kvGetJson<KiChallengeStoreFile>(CLOUD_KI_KEY);
    if (cloud && Array.isArray(cloud.items)) {
      return cloud.items;
    }
  }
  const local = readKiChallenges();
  if (local.length > 0 && hasCloudKv()) {
    await kvSetJson<KiChallengeStoreFile>(CLOUD_KI_KEY, { items: local });
  }
  return local;
}

export async function writeKiChallengesAsync(
  items: KiChallengeTrackerItem[]
): Promise<void> {
  if (hasCloudKv()) {
    await kvSetJson<KiChallengeStoreFile>(CLOUD_KI_KEY, { items });
  }
  writeKiChallenges(items);
}

export function parseYoutubeVideoId(input: string): string | null {
  const raw = (input || "").trim();
  if (!raw) return null;
  if (/^[a-zA-Z0-9_-]{11}$/.test(raw)) {
    return raw;
  }
  try {
    const u = new URL(raw);
    const vParam = u.searchParams.get("v");
    if (vParam && /^[a-zA-Z0-9_-]{11}$/.test(vParam)) {
      return vParam;
    }
    const parts = u.pathname.split("/").filter(Boolean);
    // youtu.be/<id>, /shorts/<id>, /video/<id>/edit, /embed/<id>
    for (const seg of parts) {
      if (/^[a-zA-Z0-9_-]{11}$/.test(seg)) {
        return seg;
      }
    }
  } catch {
    const match = raw.match(/(?:v=|youtu\.be\/|shorts\/|video\/)([a-zA-Z0-9_-]{11})/);
    if (match?.[1]) return match[1];
  }
  return null;
}

export function computeKiTotal(stats: KiLiveStats, weights: KiPointWeights): number {
  const v = Math.max(0, Math.floor(stats.views || 0)) * (weights.view ?? 1);
  const l = Math.max(0, Math.floor(stats.likes || 0)) * (weights.like ?? 20);
  const c = Math.max(0, Math.floor(stats.comments || 0)) * (weights.comment ?? 50);
  const s = Math.max(0, Math.floor(stats.gainedSubs || 0)) * (weights.sub ?? 200);
  return Math.max(0, Math.round(v + l + c + s));
}

export function formatKiDynamicTitle(
  template: string,
  vars: {
    ki: number;
    target: number;
    milestone: KiTitleMilestone;
    char: string;
    currentForm: string;
    nextForm: string;
  }
): string {
  const kiNum = Math.max(0, Math.round(vars.ki));
  const targetNum = Math.max(1, Math.round(vars.target));
  const kiFmt = kiNum.toLocaleString("en-US");
  const targetFmt = targetNum.toLocaleString("en-US");
  const pct = Math.min(999, Math.floor((kiNum / targetNum) * 100));

  let rendered = template
    .replace(/\{milestone\}/gi, `${vars.milestone}`)
    .replace(/\{ki\}/gi, kiFmt)
    .replace(/\{target\}/gi, targetFmt)
    .replace(/\{kiRaw\}/gi, `${kiNum}`)
    .replace(/\{targetRaw\}/gi, `${targetNum}`)
    .replace(/\{pct\}/gi, `${pct}`)
    .replace(/\{char\}/gi, vars.char)
    .replace(/\{currentForm\}/gi, vars.currentForm)
    .replace(/\{nextForm\}/gi, vars.nextForm)
    .replace(/[\r\n<>]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  if (rendered.length > 100) {
    rendered = rendered.slice(0, 99).trim() + "⚡";
  }
  return rendered || `⚡ [${kiFmt}/${targetFmt} KI] Help ${vars.char} Unlock ${vars.nextForm}!`;
}

export async function fetchAuthenticatedChannelSubscriberCount(
  accessToken: string
): Promise<number> {
  try {
    const res = await fetch(
      "https://www.googleapis.com/youtube/v3/channels?part=statistics&mine=true",
      {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      }
    );
    if (!res.ok) return 0;
    const json = await res.json();
    const subStr = json?.items?.[0]?.statistics?.subscriberCount;
    return subStr ? Math.max(0, Number.parseInt(String(subStr), 10) || 0) : 0;
  } catch {
    return 0;
  }
}

export async function syncSingleKiChallenge(
  challengeId: string,
  options?: { forceUpdateTitle?: boolean }
): Promise<KiChallengeTrackerItem> {
  const items = await readKiChallengesAsync();
  const idx = items.findIndex((it) => it.id === challengeId);
  if (idx === -1) {
    throw new Error("Không tìm thấy phiên theo dõi KI Challenge này.");
  }

  const item = { ...items[idx] };
  const nowIso = new Date().toISOString();

  try {
    const store = await readStore();
    const accessToken = await getValidYoutubeAccessToken(store);

    // 1. Fetch video snippet + live statistics (1 quota unit)
    const vUrl = new URL("https://www.googleapis.com/youtube/v3/videos");
    vUrl.searchParams.set("part", "snippet,statistics");
    vUrl.searchParams.set("id", item.videoId);

    const vRes = await fetch(vUrl.toString(), {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: "no-store",
    });
    const vJson = await vRes.json();
    if (!vRes.ok) {
      throw new Error(
        vJson?.error?.message || `YouTube API trả lỗi HTTP ${vRes.status}`
      );
    }

    const videoObj = vJson?.items?.[0];
    if (!videoObj) {
      throw new Error(
        `Không tìm thấy video ID "${item.videoId}" trên kênh YouTube hiện tại.`
      );
    }

    // 2. Fetch live channel subscriber count (1 quota unit)
    const channelSubs = await fetchAuthenticatedChannelSubscriberCount(accessToken);
    if (item.baselineSubscribers <= 0 && channelSubs > 0) {
      item.baselineSubscribers = channelSubs;
    }

    const rawStats = videoObj.statistics || {};
    const views = Math.max(0, Number.parseInt(String(rawStats.viewCount || "0"), 10) || 0);
    const likes = Math.max(0, Number.parseInt(String(rawStats.likeCount || "0"), 10) || 0);
    const comments = Math.max(
      0,
      Number.parseInt(String(rawStats.commentCount || "0"), 10) || 0
    );
    const deltaSubs =
      channelSubs > 0 && item.baselineSubscribers > 0
        ? Math.max(0, channelSubs - item.baselineSubscribers)
        : 0;
    const gainedSubs = Math.max(0, deltaSubs + (item.manualBonusSubs || 0));

    const liveStats: KiLiveStats = {
      views,
      likes,
      comments,
      channelSubs,
      gainedSubs,
    };

    const totalKi = computeKiTotal(liveStats, item.weights);
    const reachedMilestone = computeReachedKiMilestone(totalKi, item.targetKi);
    const prevMilestone: KiTitleMilestone = item.lastSyncedMilestone ?? 0;

    item.lastStats = liveStats;
    item.currentKi = totalKi;
    item.lastCheckedAt = nowIso;
    item.lastError = null;

    if (totalKi >= item.targetKi && !item.goalReachedAt) {
      item.goalReachedAt = nowIso;
    }

    const activeTemplate =
      reachedMilestone >= 100 && item.goalReachedTitleTemplate.trim()
        ? item.goalReachedTitleTemplate
        : item.titleTemplate;

    const hideNextFormName = item.mysteryNext !== false && reachedMilestone < 100;
    const publicNextForm = hideNextFormName ? "Next Form (???)" : item.nextStageLabel;

    const desiredTitle = formatKiDynamicTitle(activeTemplate, {
      ki: totalKi,
      target: item.targetKi,
      milestone: reachedMilestone,
      char: item.characterName,
      currentForm: item.currentStageLabel,
      nextForm: publicNextForm,
    });

    const existingSnippet = videoObj.snippet || {};
    const currentYtTitle = String(existingSnippet.title || "").trim();

    // QUOTA-SAFE MILESTONE GATING:
    // Auto-daemon ONLY calls `videos.update` (50 quota units) when crossing 25%, 50%, 75%, or 100%
    // (max 4 writes = 200 units across the entire video lifecycle!), unless admin clicks Force Push.
    const crossedNewCheckpoint = reachedMilestone > prevMilestone;
    const shouldPushTitle =
      Boolean(options?.forceUpdateTitle) ||
      (crossedNewCheckpoint && currentYtTitle !== desiredTitle);

    if (shouldPushTitle) {
      const updatedSnippet: Record<string, unknown> = {
        title: desiredTitle,
        description: String(existingSnippet.description || ""),
        categoryId: String(existingSnippet.categoryId || "24"),
      };
      if (Array.isArray(existingSnippet.tags) && existingSnippet.tags.length > 0) {
        updatedSnippet.tags = existingSnippet.tags;
      }
      if (existingSnippet.defaultLanguage) {
        updatedSnippet.defaultLanguage = existingSnippet.defaultLanguage;
      }
      if (existingSnippet.defaultAudioLanguage) {
        updatedSnippet.defaultAudioLanguage = existingSnippet.defaultAudioLanguage;
      }

      const putRes = await fetch(
        "https://www.googleapis.com/youtube/v3/videos?part=snippet",
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json; charset=UTF-8",
          },
          body: JSON.stringify({
            id: item.videoId,
            snippet: updatedSnippet,
          }),
          cache: "no-store",
        }
      );

      const putJson = await putRes.json().catch(() => ({}));
      if (!putRes.ok) {
        throw new Error(
          putJson?.error?.message ||
            `Không thể cập nhật tiêu đề YouTube (HTTP ${putRes.status}).`
        );
      }

      item.lastSyncedMilestone = Math.max(
        prevMilestone,
        reachedMilestone
      ) as KiTitleMilestone;
      item.lastSyncedYoutubeTitle = desiredTitle;
      item.lastUpdatedYoutubeAt = nowIso;
    } else {
      if (!item.lastSyncedYoutubeTitle) {
        item.lastSyncedYoutubeTitle = currentYtTitle;
      }
    }
  } catch (err) {
    item.lastCheckedAt = nowIso;
    item.lastError = err instanceof Error ? err.message : "Lỗi đồng bộ KI YouTube";
    const latest = await readKiChallengesAsync();
    const latestIdx = latest.findIndex((x) => x.id === challengeId);
    if (latestIdx !== -1) {
      latest[latestIdx] = item;
      await writeKiChallengesAsync(latest);
    }
    throw err;
  }

  const latest = await readKiChallengesAsync();
  const latestIdx = latest.findIndex((x) => x.id === challengeId);
  if (latestIdx !== -1) {
    latest[latestIdx] = item;
    await writeKiChallengesAsync(latest);
  }
  return item;
}

export async function runAllDueKiChallengesSync(options?: {
  forceAll?: boolean;
}): Promise<{
  checked: number;
  synced: number;
  errors: string[];
}> {
  const items = await readKiChallengesAsync();
  const now = Date.now();
  let synced = 0;
  const errors: string[] = [];

  for (const it of items) {
    if (!it.autoSyncEnabled || !it.videoId) continue;
    const intervalMs = Math.max(2, it.syncIntervalMin || 5) * 60_000;
    const lastMs = it.lastCheckedAt ? Date.parse(it.lastCheckedAt) : 0;
    if (options?.forceAll || !lastMs || now - lastMs >= intervalMs - 15_000) {
      try {
        await syncSingleKiChallenge(it.id, { forceUpdateTitle: false });
        synced += 1;
      } catch (err) {
        errors.push(
          `${it.videoId}: ${err instanceof Error ? err.message : "Sync failed"}`
        );
      }
    }
  }

  return { checked: items.length, synced, errors };
}

export function ensureKiChallengeAutoDaemon(): void {
  // On Vercel serverless, Vercel Schedules triggers `/api/schedules/ki-sync` every 5 min instead of in-memory setInterval
  if (process.env.VERCEL || globalForKiDaemon.__kiChallengeDaemonTimer) {
    return;
  }
  globalForKiDaemon.__kiChallengeDaemonTimer = setInterval(async () => {
    if (globalForKiDaemon.__kiChallengeDaemonBusy) return;
    globalForKiDaemon.__kiChallengeDaemonBusy = true;
    try {
      await runAllDueKiChallengesSync();
    } finally {
      globalForKiDaemon.__kiChallengeDaemonBusy = false;
    }
  }, 45_000);
}

function resolvePublicMediaPath(publicRelUrl: string): string {
  const cleanRel = (publicRelUrl || "").split("?")[0].replace(/^\/+/, "");
  const abs = path.resolve(process.cwd(), "public", cleanRel);
  const pubRoot = path.resolve(process.cwd(), "public");
  if (!abs.startsWith(pubRoot)) {
    throw new Error("Đường dẫn media nhân vật không hợp lệ.");
  }
  if (!fs.existsSync(abs)) {
    throw new Error(`Không tìm thấy file nhân vật: ${cleanRel}`);
  }
  return abs;
}

export async function renderIdleKiVideoAndThumbnail(params: {
  sessionId?: string;
  uiOverlayPngDataUrl: string;
  thumbJpgDataUrl: string;
  currentMediaUrl: string;
  nextMediaUrl: string;
  leftBox: string;
  rightBox: string;
  currentAuraHex: string;
  nextAuraHex: string;
  mysteryNext: boolean;
  lightning: boolean;
  durationSec: number;
  audioMode: "epic_hum" | "builtin_bgm" | "custom_audio" | "silent";
  bgmTrack?: string;
  customAudioUrl?: string;
  audioStartSec?: number;
  audioEndSec?: number;
}): Promise<{
  sessionId: string;
  videoFile: string;
  videoPath: string;
  thumbFile: string;
  thumbPath: string;
  sizeMb: number;
  durationSec: number;
  elapsedSec: number;
}> {
  const sid =
    params.sessionId ||
    `ki_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
  const sessionDir = ensureSessionDir(sid);
  const stamp = Date.now().toString(36);

  const stripDataPrefix = (dataUrl: string) => {
    const commaIdx = dataUrl.indexOf(",");
    if (commaIdx === -1) throw new Error("Dữ liệu khung hình Canvas không hợp lệ.");
    return Buffer.from(dataUrl.slice(commaIdx + 1), "base64");
  };

  const overlayPngBuf = stripDataPrefix(params.uiOverlayPngDataUrl);
  const jpgBuf = stripDataPrefix(params.thumbJpgDataUrl);

  const overlayPngPath = path.join(sessionDir, `ki_ui_overlay_${stamp}.png`);
  const thumbFile = `ki_thumbnail_${stamp}.jpg`;
  const thumbPath = path.join(sessionDir, thumbFile);
  const videoFile = `ki_idle_1080p_${stamp}.mp4`;
  const videoPath = path.join(sessionDir, videoFile);

  fs.writeFileSync(overlayPngPath, overlayPngBuf);
  fs.writeFileSync(thumbPath, jpgBuf);

  const currentAbs = resolvePublicMediaPath(params.currentMediaUrl);
  const nextAbs = resolvePublicMediaPath(params.nextMediaUrl);
  const dur = Math.max(5, Math.min(60, Math.round(params.durationSec || 15)));
  let bgmAbs = "";
  if (params.audioMode === "custom_audio" && params.customAudioUrl) {
    bgmAbs = resolvePublicMediaPath(params.customAudioUrl);
  } else if (params.audioMode === "builtin_bgm" && params.bgmTrack) {
    bgmAbs = resolveBuiltinBgmPath(params.bgmTrack);
  }
  const audioStart = Math.max(0, Number(params.audioStartSec || 0));
  const audioEnd = Math.max(0, Number(params.audioEndSec || 0));

  const py = resolvePythonBin();
  const scriptPath = path.resolve(process.cwd(), "scripts/render_ki_idle_video.py");

  const cliArgs = [
    scriptPath,
    "--ui-overlay",
    overlayPngPath,
    "--current-media",
    currentAbs,
    "--next-media",
    nextAbs,
    "--out",
    videoPath,
    "--left-box",
    params.leftBox,
    "--right-box",
    params.rightBox,
    "--current-aura",
    params.currentAuraHex || "#38bdf8",
    "--next-aura",
    params.nextAuraHex || "#facc15",
    "--mystery-next",
    String(Boolean(params.mysteryNext)),
    "--lightning",
    String(Boolean(params.lightning)),
    "--duration",
    String(dur),
    "--audio-mode",
    params.audioMode,
    "--bgm-path",
    bgmAbs,
    "--audio-start",
    String(audioStart),
    "--audio-end",
    String(audioEnd),
  ];

  const parsed = await new Promise<Record<string, unknown>>((resolve, reject) => {
    const child = spawn(py, cliArgs, {
      env: { ...process.env, OPENCV_LOG_LEVEL: "OFF" },
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (err) => reject(err));
    child.on("close", (code) => {
      const lines = stdout
        .trim()
        .split("\n")
        .map((l) => l.trim())
        .filter((l) => l.startsWith("{") && l.endsWith("}"));
      const last = lines[lines.length - 1];
      if (last) {
        try {
          const obj = JSON.parse(last);
          if (obj.ok === false) {
            reject(new Error(String(obj.error || "Lỗi dựng video Idle")));
            return;
          }
          resolve(obj);
          return;
        } catch {
          // fall through
        }
      }
      reject(
        new Error(
          stderr.trim().slice(-400) ||
            stdout.trim().slice(-400) ||
            `Idle renderer exited with code ${code}`
        )
      );
    });
  });

  return {
    sessionId: path.basename(sessionDir),
    videoFile,
    videoPath,
    thumbFile,
    thumbPath,
    sizeMb: Number(parsed.size_mb || 0),
    durationSec: dur,
    elapsedSec: Number(parsed.elapsed_s || 0),
  };
}

export function saveCustomStageArtwork(params: {
  fileName: string;
  dataUrl: string;
}): { url: string; silhouetteUrl?: string; isVideo: boolean } {
  fs.mkdirSync(CUSTOM_ART_DIR, { recursive: true });
  const ext = path.extname(params.fileName || ".png").toLowerCase();
  const allowed = [".png", ".jpg", ".jpeg", ".webp", ".mp4", ".webm", ".mov"];
  const safeExt = allowed.includes(ext) ? ext : ".png";
  const isVideo = [".mp4", ".webm", ".mov"].includes(safeExt);
  const stem =
    path
      .basename(params.fileName || "char", ext)
      .replace(/[^a-zA-Z0-9_-]/g, "_")
      .slice(0, 36) || "char";
  const uniqueBase = `${stem}_${Date.now().toString(36)}`;
  const outName = `${uniqueBase}${safeExt}`;
  const commaIdx = params.dataUrl.indexOf(",");
  if (commaIdx === -1) {
    throw new Error("File tải lên không hợp lệ.");
  }
  const buf = Buffer.from(params.dataUrl.slice(commaIdx + 1), "base64");
  const savedAbs = path.join(CUSTOM_ART_DIR, outName);
  fs.writeFileSync(savedAbs, buf);

  let silhouetteUrl: string | undefined;
  if (!isVideo) {
    const silName = `${uniqueBase}_sil.jpg`;
    const silAbs = path.join(CUSTOM_ART_DIR, silName);
    try {
      const py = resolvePythonBin();
      const scriptPath = path.resolve(process.cwd(), "scripts/render_ki_idle_video.py");
      spawnSync(
        py,
        [
          scriptPath,
          "--silhouette-only",
          savedAbs,
          "--out",
          silAbs,
          "--next-aura",
          "#facc15",
        ],
        { timeout: 15_000, env: { ...process.env, OPENCV_LOG_LEVEL: "OFF" } }
      );
      if (fs.existsSync(silAbs)) {
        silhouetteUrl = `/ki-challenge/custom/${silName}`;
      }
    } catch {
      // Fallback gracefully if silhouette pregen fails
    }
  }

  return { url: `/ki-challenge/custom/${outName}`, silhouetteUrl, isVideo };
}

export function saveCustomAudioFile(params: {
  fileName: string;
  dataUrl: string;
}): { name: string; url: string } {
  fs.mkdirSync(CUSTOM_AUDIO_DIR, { recursive: true });
  const ext = path.extname(params.fileName || ".mp3").toLowerCase();
  const allowed = [".mp3", ".m4a", ".wav", ".aac", ".ogg", ".flac"];
  const safeExt = allowed.includes(ext) ? ext : ".mp3";
  const stem =
    path
      .basename(params.fileName || "audio", ext)
      .replace(/[^a-zA-Z0-9_-]/g, "_")
      .slice(0, 42) || "audio";
  const outName = `${stem}_${Date.now().toString(36)}${safeExt}`;
  const commaIdx = params.dataUrl.indexOf(",");
  if (commaIdx === -1) {
    throw new Error("File âm thanh tải lên không hợp lệ.");
  }
  const buf = Buffer.from(params.dataUrl.slice(commaIdx + 1), "base64");
  fs.writeFileSync(path.join(CUSTOM_AUDIO_DIR, outName), buf);
  return { name: outName, url: `/ki-challenge/custom-audio/${outName}` };
}

export async function publishKiVideoAndStartTracking(params: {
  sessionId: string;
  videoFile: string;
  thumbFile: string;
  privacyStatus: "public" | "unlisted" | "private";
  characterName: string;
  episodeNumber: number;
  currentStageId: string;
  currentStageLabel: string;
  currentStageMediaUrl?: string;
  currentAuraHex?: string;
  nextStageId: string;
  nextStageLabel: string;
  nextStageMediaUrl?: string;
  nextAuraHex?: string;
  mysteryNext?: boolean;
  targetKi: number;
  weights: KiPointWeights;
  titleTemplate: string;
  goalReachedTitleTemplate: string;
  description: string;
  tags: string[];
  pinnedComment: string;
  syncIntervalMin: number;
}): Promise<KiChallengeTrackerItem> {
  const sessionDir = ensureSessionDir(params.sessionId);
  const vPath = path.join(sessionDir, path.basename(params.videoFile));
  const tPath = path.join(sessionDir, path.basename(params.thumbFile));
  if (!fs.existsSync(vPath) || !fs.existsSync(tPath)) {
    throw new Error("Không tìm thấy file Video hoặc Thumbnail đã dựng. Hãy bấm Dựng Video trước.");
  }

  const store = await readStore();
  const accessToken = await getValidYoutubeAccessToken(store);
  const baselineSubs = await fetchAuthenticatedChannelSubscriberCount(accessToken);

  const hideNextFormName = params.mysteryNext !== false;
  const initialTitle = formatKiDynamicTitle(params.titleTemplate, {
    ki: 0,
    target: params.targetKi,
    milestone: 0,
    char: params.characterName,
    currentForm: params.currentStageLabel,
    nextForm: hideNextFormName ? "Next Form (???)" : params.nextStageLabel,
  });

  const vBuf = fs.readFileSync(vPath);
  const tBuf = fs.readFileSync(tPath);

  const uploaded = await uploadShortVideoToStudio({
    accessToken,
    ownerChannelId: store.youtubeOAuth?.connectedChannelId,
    videoBuffer: vBuf.buffer.slice(vBuf.byteOffset, vBuf.byteOffset + vBuf.byteLength),
    mimeType: "video/mp4",
    thumbnailBuffer: tBuf.buffer.slice(tBuf.byteOffset, tBuf.byteOffset + tBuf.byteLength),
    thumbnailMimeType: "image/jpeg",
    title: initialTitle,
    description: params.description,
    tags: params.tags,
    pinnedComment: params.pinnedComment,
    publishMode:
      params.privacyStatus === "public"
        ? "public_now"
        : params.privacyStatus === "unlisted"
        ? "unlisted"
        : "private_draft",
    containsSyntheticMedia: true,
    selfDeclaredMadeForKids: false,
  });

  const nowIso = new Date().toISOString();
  const newItem: KiChallengeTrackerItem = {
    id: `kich_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    videoId: uploaded.videoId,
    characterName: params.characterName,
    episodeNumber: params.episodeNumber,
    currentStageId: params.currentStageId,
    currentStageLabel: params.currentStageLabel,
    currentStageMediaUrl: params.currentStageMediaUrl,
    currentAuraHex: params.currentAuraHex,
    nextStageId: params.nextStageId,
    nextStageLabel: params.nextStageLabel,
    nextStageMediaUrl: params.nextStageMediaUrl,
    nextAuraHex: params.nextAuraHex,
    mysteryNext: params.mysteryNext !== false,
    targetKi: params.targetKi,
    weights: params.weights,
    baselineSubscribers: baselineSubs,
    manualBonusSubs: 0,
    titleTemplate: params.titleTemplate,
    goalReachedTitleTemplate: params.goalReachedTitleTemplate,
    autoSyncEnabled: true,
    syncIntervalMin: Math.max(2, params.syncIntervalMin || 5),
    currentKi: 0,
    lastSyncedMilestone: 0,
    lastStats: {
      views: 0,
      likes: 0,
      comments: 0,
      channelSubs: baselineSubs,
      gainedSubs: 0,
    },
    lastSyncedYoutubeTitle: initialTitle,
    lastCheckedAt: nowIso,
    lastUpdatedYoutubeAt: nowIso,
    goalReachedAt: null,
    lastError: null,
    watchUrl: `https://www.youtube.com/watch?v=${uploaded.videoId}`,
    studioEditUrl: uploaded.studioEditUrl,
    createdAt: nowIso,
  };

  const items = await readKiChallengesAsync();
  items.unshift(newItem);
  await writeKiChallengesAsync(items);
  ensureKiChallengeAutoDaemon();

  return newItem;
}
