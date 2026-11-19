import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { hasCloudKv, kvGetJson, kvSetJson } from "./cloud-kv";
import { INITIAL_DEMO_STORE } from "./demo-data";
import type { StoreData } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "ytb-growth-db.json");
const CLOUD_STORE_KEY = "ytb:store:v1";

function hydrateStoreEnvDefaults(parsed: Partial<StoreData>): StoreData {
  let envOAuth = parsed.youtubeOAuth;
  if (!envOAuth?.refreshToken && process.env.YOUTUBE_OAUTH_JSON) {
    try {
      envOAuth = JSON.parse(process.env.YOUTUBE_OAUTH_JSON);
    } catch {
      // ignore invalid env json
    }
  }
  return {
    ...INITIAL_DEMO_STORE,
    ...parsed,
    youtubeOAuth: envOAuth,
    settings: {
      ...INITIAL_DEMO_STORE.settings,
      ...(parsed.settings ?? {}),
      youtubeApiKey:
        parsed.settings?.youtubeApiKey || process.env.YOUTUBE_API_KEY || "",
      geminiApiKey:
        parsed.settings?.geminiApiKey || process.env.GEMINI_API_KEY || "",
    },
  };
}

export async function readStore(): Promise<StoreData> {
  if (hasCloudKv()) {
    const cloud = await kvGetJson<Partial<StoreData>>(CLOUD_STORE_KEY);
    if (cloud) {
      return hydrateStoreEnvDefaults(cloud);
    }
  }

  try {
    const raw = await readFile(DB_PATH, "utf-8");
    const parsed = JSON.parse(raw) as StoreData;
    const hydrated = hydrateStoreEnvDefaults(parsed);
    if (hasCloudKv()) {
      await kvSetJson(CLOUD_STORE_KEY, hydrated);
    }
    return hydrated;
  } catch {
    const seeded = hydrateStoreEnvDefaults({});
    await writeStore(seeded);
    return seeded;
  }
}

export async function writeStore(data: StoreData): Promise<void> {
  if (hasCloudKv()) {
    await kvSetJson(CLOUD_STORE_KEY, data);
  }
  try {
    await mkdir(DATA_DIR, { recursive: true });
    await writeFile(DB_PATH, JSON.stringify(data, null, 2), "utf-8");
  } catch {
    // Vercel serverless filesystem is read-only; cloud KV already persisted the state
  }
}

export function getEffectiveYoutubeKey(store: StoreData): string {
  return (store.settings.youtubeApiKey || process.env.YOUTUBE_API_KEY || "").trim();
}

export function getEffectiveGeminiKey(store: StoreData): string {
  return (store.settings.geminiApiKey || process.env.GEMINI_API_KEY || "").trim();
}
