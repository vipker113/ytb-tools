import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { INITIAL_DEMO_STORE } from "./demo-data";
import type { StoreData } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "ytb-growth-db.json");

export async function readStore(): Promise<StoreData> {
  try {
    const raw = await readFile(DB_PATH, "utf-8");
    const parsed = JSON.parse(raw) as StoreData;
    return {
      ...INITIAL_DEMO_STORE,
      ...parsed,
      settings: {
        ...INITIAL_DEMO_STORE.settings,
        ...(parsed.settings ?? {}),
        youtubeApiKey:
          parsed.settings?.youtubeApiKey || process.env.YOUTUBE_API_KEY || "",
        geminiApiKey:
          parsed.settings?.geminiApiKey || process.env.GEMINI_API_KEY || "",
      },
    };
  } catch {
    const seeded: StoreData = {
      ...structuredClone(INITIAL_DEMO_STORE),
      settings: {
        ...INITIAL_DEMO_STORE.settings,
        youtubeApiKey: process.env.YOUTUBE_API_KEY || "",
        geminiApiKey: process.env.GEMINI_API_KEY || "",
      },
    };
    await writeStore(seeded);
    return seeded;
  }
}

export async function writeStore(data: StoreData): Promise<void> {
  await mkdir(DATA_DIR, { recursive: true });
  await writeFile(DB_PATH, JSON.stringify(data, null, 2), "utf-8");
}

export function getEffectiveYoutubeKey(store: StoreData): string {
  return (store.settings.youtubeApiKey || process.env.YOUTUBE_API_KEY || "").trim();
}

export function getEffectiveGeminiKey(store: StoreData): string {
  return (store.settings.geminiApiKey || process.env.GEMINI_API_KEY || "").trim();
}
