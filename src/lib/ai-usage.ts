import crypto from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type { AiUsageLogEntry, AiUsageSummary } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");
const USAGE_PATH = path.join(DATA_DIR, "ai-usage.json");
const VERTEX_SA_PATH = path.join(DATA_DIR, "vertex-service-account.json");

export interface RawGeminiUsageMetadata {
  promptTokenCount?: number;
  candidatesTokenCount?: number;
  thoughtsTokenCount?: number;
  totalTokenCount?: number;
}

interface StoredUsageLedger {
  creditLimitUsd: number;
  trackedVertexCostUsd: number;
  manualOffsetUsd: number;
  totalPromptTokens: number;
  totalOutputTokens: number;
  totalThoughtTokens: number;
  totalTokens: number;
  totalImagesGenerated: number;
  totalTtsCalls: number;
  totalCalls: number;
  recentCalls: AiUsageLogEntry[];
  lastUpdatedAt: string;
}

const INITIAL_SEEDED_LEDGER: StoredUsageLedger = {
  creditLimitUsd: 300,
  trackedVertexCostUsd: 0.3272,
  manualOffsetUsd: 0,
  totalPromptTokens: 2410,
  totalOutputTokens: 10920,
  totalThoughtTokens: 520,
  totalTokens: 13850,
  totalImagesGenerated: 8,
  totalTtsCalls: 2,
  totalCalls: 15,
  recentCalls: [
    {
      id: "seed-vertex-init",
      timestamp: "2026-10-30T20:15:11.000Z",
      provider: "vertex",
      model: "vertex/gemini-3.8-flash + 2.5-flash-image + tts",
      feature: " Phiên kích hoạt & test Vertex AI ban đầu (8 ảnh 3D + 2 TTS + 5 lệnh text)",
      promptTokens: 2410,
      outputTokens: 10920,
      thoughtTokens: 520,
      totalTokens: 13850,
      imageCount: 8,
      costUsd: 0.3272,
    },
  ],
  lastUpdatedAt: new Date().toISOString(),
};

let cachedLedger: StoredUsageLedger | null = null;
let writeQueue: Promise<void> = Promise.resolve();

function toSummary(ledger: StoredUsageLedger): AiUsageSummary {
  const totalUsedUsd = Math.max(
    0,
    Number((ledger.trackedVertexCostUsd + ledger.manualOffsetUsd).toFixed(4))
  );
  const remainingUsd = Math.max(
    0,
    Number((ledger.creditLimitUsd - totalUsedUsd).toFixed(4))
  );
  return {
    creditLimitUsd: ledger.creditLimitUsd,
    trackedVertexCostUsd: Number(ledger.trackedVertexCostUsd.toFixed(4)),
    manualOffsetUsd: Number(ledger.manualOffsetUsd.toFixed(4)),
    totalUsedUsd,
    remainingUsd,
    totalPromptTokens: ledger.totalPromptTokens,
    totalOutputTokens: ledger.totalOutputTokens,
    totalThoughtTokens: ledger.totalThoughtTokens,
    totalTokens: ledger.totalTokens,
    totalImagesGenerated: ledger.totalImagesGenerated,
    totalTtsCalls: ledger.totalTtsCalls,
    totalCalls: ledger.totalCalls,
    recentCalls: ledger.recentCalls,
    lastUpdatedAt: ledger.lastUpdatedAt,
  };
}

async function loadLedger(): Promise<StoredUsageLedger> {
  if (cachedLedger) return cachedLedger;
  try {
    const raw = await readFile(USAGE_PATH, "utf-8");
    const parsed = JSON.parse(raw) as Partial<StoredUsageLedger>;
    cachedLedger = {
      ...INITIAL_SEEDED_LEDGER,
      ...parsed,
      recentCalls: Array.isArray(parsed.recentCalls)
        ? parsed.recentCalls
        : INITIAL_SEEDED_LEDGER.recentCalls,
    };
    return cachedLedger;
  } catch {
    cachedLedger = structuredClone(INITIAL_SEEDED_LEDGER);
    await persistLedger(cachedLedger);
    return cachedLedger;
  }
}

async function persistLedger(ledger: StoredUsageLedger): Promise<void> {
  writeQueue = writeQueue
    .then(async () => {
      await mkdir(DATA_DIR, { recursive: true });
      await writeFile(USAGE_PATH, JSON.stringify(ledger, null, 2), "utf-8");
    })
    .catch(() => {});
  await writeQueue;
}

/**
 * Official Google Cloud Vertex AI Pay-As-You-Go / Free-Trial-$300 Pricing Calculator:
 * - Flagship (`gemini-4-argon`, `gemini-3.1-pro`, `gemini-2.5-pro`): $2.00 / 1M input, $12.00 / 1M output+thinking
 * - Flash (`gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-2.5-flash`): $0.30 / 1M input, $2.50 / 1M output+thinking
 * - TTS (`gemini-3.8-flash-tts`, `gemini-2.5-flash-preview-tts`): $0.50 / 1M text input, $10.00 / 1M audio output tokens
 * - Image (`gemini-2.5-flash-image`, `imagen-*`): $0.039 per generated image + $0.30 / 1M prompt tokens
 */
export function calculateVertexCostUsd(params: {
  provider: "vertex" | "gemini_free" | "mac_pipeline";
  model: string;
  promptTokens: number;
  outputTokens: number;
  thoughtTokens: number;
  imageCount?: number;
  isTts?: boolean;
  explicitCostUsd?: number;
}): number {
  if (typeof params.explicitCostUsd === "number" && params.explicitCostUsd >= 0) {
    return params.explicitCostUsd;
  }
  if (params.provider === "gemini_free") {
    return 0;
  }

  const m = params.model.toLowerCase();
  const inTok = Math.max(0, params.promptTokens);
  const outTok = Math.max(0, params.outputTokens + params.thoughtTokens);
  const imgs = Math.max(0, params.imageCount || 0);

  if (imgs > 0 || m.includes("image") || m.includes("imagen")) {
    const imgCount = Math.max(1, imgs);
    return inTok * 0.0000003 + imgCount * 0.039;
  }

  if (params.isTts || m.includes("tts")) {
    const effectiveAudioTok = outTok > 0 ? outTok : Math.max(400, inTok * 6);
    return inTok * 0.0000005 + effectiveAudioTok * 0.00001;
  }

  if (m.includes("argon") || m.includes("pro")) {
    return inTok * 0.000002 + outTok * 0.000012;
  }

  // Flash family default
  return inTok * 0.0000003 + outTok * 0.0000025;
}

export async function readAiUsageSummary(): Promise<AiUsageSummary> {
  const ledger = await loadLedger();
  return toSummary(ledger);
}

export async function recordAiUsageCall(params: {
  provider: "vertex" | "gemini_free" | "mac_pipeline";
  model: string;
  feature: string;
  usageMetadata?: RawGeminiUsageMetadata;
  fallbackPromptChars?: number;
  fallbackOutputChars?: number;
  imageCount?: number;
  isTts?: boolean;
  explicitCostUsd?: number;
}): Promise<AiUsageSummary> {
  const ledger = await loadLedger();

  const meta = params.usageMetadata;
  const promptTokens =
    meta?.promptTokenCount ??
    Math.max(1, Math.round((params.fallbackPromptChars || 120) / 4));
  const thoughtTokens = meta?.thoughtsTokenCount ?? 0;
  const outputTokens =
    meta?.candidatesTokenCount ??
    (params.imageCount
      ? params.imageCount * 1290
      : Math.max(1, Math.round((params.fallbackOutputChars || 120) / 4)));
  const totalTokens =
    meta?.totalTokenCount ?? promptTokens + outputTokens + thoughtTokens;

  const costUsd = calculateVertexCostUsd({
    provider: params.provider,
    model: params.model,
    promptTokens,
    outputTokens,
    thoughtTokens,
    imageCount: params.imageCount,
    isTts: params.isTts,
    explicitCostUsd: params.explicitCostUsd,
  });

  if (params.provider !== "gemini_free") {
    ledger.trackedVertexCostUsd += costUsd;
  }

  ledger.totalPromptTokens += promptTokens;
  ledger.totalOutputTokens += outputTokens;
  ledger.totalThoughtTokens += thoughtTokens;
  ledger.totalTokens += totalTokens;
  ledger.totalImagesGenerated += params.imageCount || 0;
  if (params.isTts || params.model.toLowerCase().includes("tts")) {
    ledger.totalTtsCalls += 1;
  }
  ledger.totalCalls += 1;
  ledger.lastUpdatedAt = new Date().toISOString();

  const entry: AiUsageLogEntry = {
    id: `usage-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    timestamp: ledger.lastUpdatedAt,
    provider: params.provider,
    model: params.model,
    feature: params.feature,
    promptTokens,
    outputTokens,
    thoughtTokens,
    totalTokens,
    imageCount: params.imageCount,
    costUsd: Number(costUsd.toFixed(5)),
  };

  ledger.recentCalls = [entry, ...ledger.recentCalls].slice(0, 40);
  await persistLedger(ledger);
  return toSummary(ledger);
}

export async function calibrateAiUsageUsd(params: {
  actualTotalUsedUsd: number;
  creditLimitUsd?: number;
}): Promise<AiUsageSummary> {
  const ledger = await loadLedger();
  if (typeof params.creditLimitUsd === "number" && params.creditLimitUsd > 0) {
    ledger.creditLimitUsd = params.creditLimitUsd;
  }
  const target = Math.max(0, params.actualTotalUsedUsd);
  const delta = target - ledger.trackedVertexCostUsd;
  ledger.manualOffsetUsd = delta;
  ledger.lastUpdatedAt = new Date().toISOString();

  const syncEntry: AiUsageLogEntry = {
    id: `sync-${Date.now()}`,
    timestamp: ledger.lastUpdatedAt,
    provider: "manual_sync",
    model: "google-cloud-billing",
    feature: `Đồng bộ số dư chuẩn theo Google Cloud Billing ($${target.toFixed(2)})`,
    promptTokens: 0,
    outputTokens: 0,
    thoughtTokens: 0,
    totalTokens: 0,
    costUsd: 0,
  };
  ledger.recentCalls = [syncEntry, ...ledger.recentCalls].slice(0, 40);
  await persistLedger(ledger);
  return toSummary(ledger);
}

// Shared Vertex AI JWT Auth Helper
let cachedVertexToken: {
  token: string;
  projectId: string;
  expiresAt: number;
} | null = null;

function base64UrlEncode(input: string | Buffer): string {
  return Buffer.from(input)
    .toString("base64")
    .replace(/=/g, "")
    .replace(/\+/g, "-")
    .replace(/\//g, "_");
}

export async function getVertexAuthServer(): Promise<{
  token: string;
  projectId: string;
} | null> {
  if (cachedVertexToken && cachedVertexToken.expiresAt > Date.now() + 60_000) {
    return {
      token: cachedVertexToken.token,
      projectId: cachedVertexToken.projectId,
    };
  }
  try {
    const raw = await readFile(VERTEX_SA_PATH, "utf-8");
    const sa = JSON.parse(raw) as {
      project_id: string;
      client_email: string;
      private_key: string;
      token_uri?: string;
    };
    if (!sa.client_email || !sa.private_key || !sa.project_id) return null;

    const nowSec = Math.floor(Date.now() / 1000);
    const header = base64UrlEncode(JSON.stringify({ alg: "RS256", typ: "JWT" }));
    const payload = base64UrlEncode(
      JSON.stringify({
        iss: sa.client_email,
        scope: "https://www.googleapis.com/auth/cloud-platform",
        aud: sa.token_uri || "https://oauth2.googleapis.com/token",
        iat: nowSec,
        exp: nowSec + 3600,
      })
    );
    const unsigned = `${header}.${payload}`;
    const signer = crypto.createSign("RSA-SHA256");
    signer.update(unsigned);
    const sig = signer
      .sign(sa.private_key, "base64")
      .replace(/=/g, "")
      .replace(/\+/g, "-")
      .replace(/\//g, "_");

    const res = await fetch(
      sa.token_uri || "https://oauth2.googleapis.com/token",
      {
        method: "POST",
        signal: AbortSignal.timeout(8000),
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
          assertion: `${unsigned}.${sig}`,
        }),
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const json = await res.json();
    if (!json.access_token) return null;

    cachedVertexToken = {
      token: json.access_token,
      projectId: sa.project_id,
      expiresAt: Date.now() + Number(json.expires_in || 3500) * 1000,
    };
    return {
      token: cachedVertexToken.token,
      projectId: cachedVertexToken.projectId,
    };
  } catch {
    return null;
  }
}
