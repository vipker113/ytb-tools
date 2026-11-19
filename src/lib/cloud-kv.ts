/**
 * Lightweight zero-dependency Upstash Redis / Vercel KV REST client.
 * Uses native `fetch()` so it works identically on local Mac dev AND Vercel Serverless Functions.
 */

function getKvConfig(): { url: string; token: string } | null {
  const url = (
    process.env.UPSTASH_REDIS_REST_URL ||
    process.env.KV_REST_API_URL ||
    ""
  )
    .trim()
    .replace(/\/+$/, "");
  const token = (
    process.env.UPSTASH_REDIS_REST_TOKEN ||
    process.env.KV_REST_API_TOKEN ||
    ""
  ).trim();

  if (!url || !token) return null;
  return { url, token };
}

export function hasCloudKv(): boolean {
  return getKvConfig() !== null;
}

export async function kvGetJson<T>(key: string): Promise<T | null> {
  const cfg = getKvConfig();
  if (!cfg) return null;

  try {
    const res = await fetch(`${cfg.url}/get/${encodeURIComponent(key)}`, {
      headers: { Authorization: `Bearer ${cfg.token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = (await res.json()) as { result?: string | null };
    if (!json.result) return null;
    return JSON.parse(json.result) as T;
  } catch {
    return null;
  }
}

export async function kvSetJson<T>(key: string, value: T): Promise<boolean> {
  const cfg = getKvConfig();
  if (!cfg) return false;

  try {
    const res = await fetch(`${cfg.url}/set/${encodeURIComponent(key)}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${cfg.token}`,
        "Content-Type": "text/plain; charset=utf-8",
      },
      body: JSON.stringify(value),
      cache: "no-store",
    });
    return res.ok;
  } catch {
    return false;
  }
}
