import fs from "node:fs";
import path from "node:path";
import { hasCloudKv, kvGetJson, kvSetJson } from "./cloud-kv";

export type YoutubeQuotaCategory =
  | "kiRead"
  | "kiTitleUpdate"
  | "videoUpload"
  | "studioWrite"
  | "search"
  | "channelRead";

export interface YoutubeQuotaBucket {
  calls: number;
  units: number;
}

export interface YoutubeQuotaLogEntry {
  at: string;
  endpoint: string;
  method: string;
  units: number;
  category: YoutubeQuotaCategory;
  label: string;
  ok: boolean;
}

export interface YoutubeQuotaDayRecord {
  ptDate: string;
  trackedUnits: number;
  manualAdjustment: number;
  dailyLimit: number;
  quotaExceededFlag: boolean;
  breakdown: Record<YoutubeQuotaCategory, YoutubeQuotaBucket>;
  recentLogs: YoutubeQuotaLogEntry[];
  updatedAt: string;
}

interface YoutubeQuotaStoreFile {
  current: YoutubeQuotaDayRecord;
  history: Array<{
    ptDate: string;
    totalUnits: number;
    dailyLimit: number;
  }>;
}

export interface YoutubeQuotaSummary extends YoutubeQuotaDayRecord {
  usedUnits: number;
  remainingUnits: number;
  usagePct: number;
  remainingTitleUpdates: number;
  remainingVideoUploads: number;
  nextResetAtIso: string;
  secondsUntilReset: number;
  history: Array<{
    ptDate: string;
    totalUnits: number;
    dailyLimit: number;
  }>;
}

const QUOTA_FILE_PATH = path.join(process.cwd(), "data", "ytb-quota.json");
const CLOUD_QUOTA_KEY = "ytb:quota:v1";
const DEFAULT_DAILY_LIMIT = 10_000;

let quotaMutationChain: Promise<void> = Promise.resolve();

function createEmptyBreakdown(): Record<YoutubeQuotaCategory, YoutubeQuotaBucket> {
  return {
    kiRead: { calls: 0, units: 0 },
    kiTitleUpdate: { calls: 0, units: 0 },
    videoUpload: { calls: 0, units: 0 },
    studioWrite: { calls: 0, units: 0 },
    search: { calls: 0, units: 0 },
    channelRead: { calls: 0, units: 0 },
  };
}

export function getPacificDateKey(date: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);

  const y = parts.find((p) => p.type === "year")?.value || "2026";
  const m = parts.find((p) => p.type === "month")?.value || "01";
  const d = parts.find((p) => p.type === "day")?.value || "01";
  return `${y}-${m}-${d}`;
}

export function getNextPacificMidnight(now: Date = new Date()): {
  nextResetAtIso: string;
  secondsUntilReset: number;
} {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles",
    hourCycle: "h23",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(now);

  const h = Number.parseInt(parts.find((p) => p.type === "hour")?.value || "0", 10) || 0;
  const m = Number.parseInt(parts.find((p) => p.type === "minute")?.value || "0", 10) || 0;
  const s = Number.parseInt(parts.find((p) => p.type === "second")?.value || "0", 10) || 0;

  const elapsedSec = h * 3600 + m * 60 + s;
  const secondsUntilReset = Math.max(1, 86_400 - elapsedSec);
  const nextResetAtIso = new Date(now.getTime() + secondsUntilReset * 1000).toISOString();

  return { nextResetAtIso, secondsUntilReset };
}

function createFreshDayRecord(
  ptDate: string,
  dailyLimit = DEFAULT_DAILY_LIMIT
): YoutubeQuotaDayRecord {
  return {
    ptDate,
    trackedUnits: 0,
    manualAdjustment: 0,
    dailyLimit,
    quotaExceededFlag: false,
    breakdown: createEmptyBreakdown(),
    recentLogs: [],
    updatedAt: new Date().toISOString(),
  };
}

function normalizeStore(raw: Partial<YoutubeQuotaStoreFile> | null): YoutubeQuotaStoreFile {
  const todayPt = getPacificDateKey();
  const history = Array.isArray(raw?.history) ? [...raw!.history] : [];
  const cur = raw?.current;

  if (!cur || typeof cur.ptDate !== "string") {
    return {
      current: createFreshDayRecord(todayPt, DEFAULT_DAILY_LIMIT),
      history: history.slice(0, 7),
    };
  }

  const limit = Math.max(1000, Number(cur.dailyLimit) || DEFAULT_DAILY_LIMIT);

  if (cur.ptDate !== todayPt) {
    const prevTotal = Math.max(0, (cur.trackedUnits || 0) + (cur.manualAdjustment || 0));
    const nextHistory = [
      { ptDate: cur.ptDate, totalUnits: prevTotal, dailyLimit: limit },
      ...history.filter((h) => h.ptDate !== cur.ptDate),
    ].slice(0, 7);
    return {
      current: createFreshDayRecord(todayPt, limit),
      history: nextHistory,
    };
  }

  const baseBreakdown = createEmptyBreakdown();
  if (cur.breakdown && typeof cur.breakdown === "object") {
    for (const k of Object.keys(baseBreakdown) as YoutubeQuotaCategory[]) {
      const b = cur.breakdown[k];
      if (b && typeof b === "object") {
        baseBreakdown[k] = {
          calls: Math.max(0, Number(b.calls) || 0),
          units: Math.max(0, Number(b.units) || 0),
        };
      }
    }
  }

  return {
    current: {
      ptDate: cur.ptDate,
      trackedUnits: Math.max(0, Number(cur.trackedUnits) || 0),
      manualAdjustment: Number(cur.manualAdjustment) || 0,
      dailyLimit: limit,
      quotaExceededFlag: Boolean(cur.quotaExceededFlag),
      breakdown: baseBreakdown,
      recentLogs: Array.isArray(cur.recentLogs) ? cur.recentLogs.slice(0, 20) : [],
      updatedAt: cur.updatedAt || new Date().toISOString(),
    },
    history: history.slice(0, 7),
  };
}

function readLocalQuotaStore(): YoutubeQuotaStoreFile | null {
  try {
    if (!fs.existsSync(QUOTA_FILE_PATH)) return null;
    const raw = fs.readFileSync(QUOTA_FILE_PATH, "utf-8");
    return JSON.parse(raw) as YoutubeQuotaStoreFile;
  } catch {
    return null;
  }
}

function writeLocalQuotaStore(data: YoutubeQuotaStoreFile): void {
  try {
    fs.mkdirSync(path.dirname(QUOTA_FILE_PATH), { recursive: true });
    const tmp = `${QUOTA_FILE_PATH}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(data, null, 2), "utf-8");
    fs.renameSync(tmp, QUOTA_FILE_PATH);
  } catch {
    // Ignore read-only FS on serverless
  }
}

async function loadQuotaStore(): Promise<YoutubeQuotaStoreFile> {
  if (hasCloudKv()) {
    const cloud = await kvGetJson<YoutubeQuotaStoreFile>(CLOUD_QUOTA_KEY);
    if (cloud) {
      return normalizeStore(cloud);
    }
  }
  return normalizeStore(readLocalQuotaStore());
}

async function saveQuotaStore(store: YoutubeQuotaStoreFile): Promise<void> {
  if (hasCloudKv()) {
    await kvSetJson<YoutubeQuotaStoreFile>(CLOUD_QUOTA_KEY, store);
  }
  writeLocalQuotaStore(store);
}

export function toQuotaSummary(store: YoutubeQuotaStoreFile): YoutubeQuotaSummary {
  const cur = store.current;
  const rawUsed = Math.max(0, cur.trackedUnits + cur.manualAdjustment);
  const usedUnits = cur.quotaExceededFlag
    ? Math.max(rawUsed, cur.dailyLimit)
    : rawUsed;
  const remainingUnits = Math.max(0, cur.dailyLimit - usedUnits);
  const usagePct = Math.min(100, Math.round((usedUnits / Math.max(1, cur.dailyLimit)) * 1000) / 10);
  const { nextResetAtIso, secondsUntilReset } = getNextPacificMidnight();

  return {
    ...cur,
    usedUnits,
    remainingUnits,
    usagePct,
    remainingTitleUpdates: Math.floor(remainingUnits / 50),
    remainingVideoUploads: Math.floor(remainingUnits / 1600),
    nextResetAtIso,
    secondsUntilReset,
    history: store.history,
  };
}

export async function getYoutubeQuotaSummary(): Promise<YoutubeQuotaSummary> {
  const store = await loadQuotaStore();
  return toQuotaSummary(store);
}

export async function calibrateYoutubeQuota(params: {
  setExactUsedUnits?: number;
  dailyLimit?: number;
  clearQuotaExceeded?: boolean;
}): Promise<YoutubeQuotaSummary> {
  let result!: YoutubeQuotaSummary;
  quotaMutationChain = quotaMutationChain
    .catch(() => undefined)
    .then(async () => {
      const store = await loadQuotaStore();
      if (typeof params.dailyLimit === "number" && Number.isFinite(params.dailyLimit)) {
        store.current.dailyLimit = Math.max(1000, Math.round(params.dailyLimit));
      }
      if (
        typeof params.setExactUsedUnits === "number" &&
        Number.isFinite(params.setExactUsedUnits)
      ) {
        const target = Math.max(0, Math.round(params.setExactUsedUnits));
        store.current.manualAdjustment = target - store.current.trackedUnits;
        if (target < store.current.dailyLimit) {
          store.current.quotaExceededFlag = false;
        }
      }
      if (params.clearQuotaExceeded) {
        store.current.quotaExceededFlag = false;
      }
      store.current.updatedAt = new Date().toISOString();
      await saveQuotaStore(store);
      result = toQuotaSummary(store);
    });
  await quotaMutationChain;
  return result;
}

function estimateYoutubeCallCost(
  urlStr: string,
  method: string,
  status: number,
  hint?: { category?: YoutubeQuotaCategory; label?: string }
): {
  units: number;
  endpoint: string;
  category: YoutubeQuotaCategory;
  label: string;
} {
  let pathname = urlStr;
  try {
    pathname = new URL(urlStr).pathname;
  } catch {
    // keep raw
  }

  const m = (method || "GET").toUpperCase();

  // Resumable upload initiation: /upload/youtube/v3/videos
  if (pathname.includes("/upload/youtube/v3/videos")) {
    // If validation failed with 400 before session creation, don't charge 1600
    const units = status === 400 ? 1 : 1600;
    return {
      units,
      endpoint: "videos.insert",
      category: hint?.category || "videoUpload",
      label: hint?.label || "Upload Video YouTube",
    };
  }

  if (pathname.includes("/thumbnails/set")) {
    const units = status === 400 ? 1 : 50;
    return {
      units,
      endpoint: "thumbnails.set",
      category: hint?.category || "videoUpload",
      label: hint?.label || "Cập nhật Thumbnail",
    };
  }

  const seg = pathname.split("/youtube/v3/")[1]?.split("/")[0] || "unknown";

  if (seg === "search") {
    return {
      units: 100,
      endpoint: "search.list",
      category: hint?.category || "search",
      label: hint?.label || "Tìm kiếm YouTube (search.list)",
    };
  }

  if (m === "POST" || m === "PUT" || m === "DELETE") {
    const units = status === 400 ? 1 : 50;
    return {
      units,
      endpoint: `${seg}.${m === "POST" ? "insert" : m === "PUT" ? "update" : "delete"}`,
      category: hint?.category || "studioWrite",
      label: hint?.label || `Ghi dữ liệu Studio (${seg})`,
    };
  }

  return {
    units: 1,
    endpoint: `${seg}.list`,
    category: hint?.category || "channelRead",
    label: hint?.label || `Đọc dữ liệu (${seg}.list)`,
  };
}

export async function ytApiFetch(
  input: string | URL,
  init?: RequestInit,
  quotaMeta?: { category?: YoutubeQuotaCategory; label?: string }
): Promise<Response> {
  const urlStr = typeof input === "string" ? input : input.toString();
  const method = init?.method || "GET";
  const res = await fetch(urlStr, init);

  let hitQuotaExceeded = false;
  if (res.status === 403) {
    try {
      const clonedText = await res.clone().text();
      if (clonedText.includes("quotaExceeded") || clonedText.includes("dailyLimitExceeded")) {
        hitQuotaExceeded = true;
      }
    } catch {
      // ignore clone errors
    }
  }

  const est = estimateYoutubeCallCost(urlStr, method, res.status, quotaMeta);
  const nowIso = new Date().toISOString();

  quotaMutationChain = quotaMutationChain
    .catch(() => undefined)
    .then(async () => {
      const store = await loadQuotaStore();
      if (est.units > 0) {
        store.current.trackedUnits += est.units;
        const bucket = store.current.breakdown[est.category];
        bucket.calls += 1;
        bucket.units += est.units;
        store.current.recentLogs = [
          {
            at: nowIso,
            endpoint: est.endpoint,
            method: method.toUpperCase(),
            units: est.units,
            category: est.category,
            label: est.label,
            ok: res.ok,
          },
          ...store.current.recentLogs,
        ].slice(0, 20);
      }
      if (hitQuotaExceeded) {
        store.current.quotaExceededFlag = true;
      }
      store.current.updatedAt = nowIso;
      await saveQuotaStore(store);
    });

  // Await so serverless cron / route handlers persist quota to Cloud KV before freezing
  await quotaMutationChain;

  return res;
}
