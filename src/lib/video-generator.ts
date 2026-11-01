import { spawn } from "node:child_process";
import crypto from "node:crypto";
import { mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import ffmpegPath from "ffmpeg-static";
import { buildDefaultDescription, buildDefaultTags } from "./auto-planner";
import { recordAiUsageCall } from "./ai-usage";
import { getEffectiveGeminiKey } from "./store";
import type { StoreData } from "./types";

export interface VideoBeatSpec {
  beatIndex: number;
  narration: string;
  imagePrompt: string;
  archiveQuery?: string;
  badgeText?: string;
}

export interface GeneratedVideoPackage {
  videoFileName: string;
  videoUrl: string;
  durationSeconds: number;
  directorModelUsed: string;
  imageEngineUsed:
    | "vertex-gemini-image"
    | "hybrid-3d-nasa-science"
    | "flux-3d-ai";
  ttsModelUsed: string;
  title: string;
  fullNarration: string;
  description: string;
  tags: string[];
  pinnedComment: string;
  scientificSources: string[];
}

const DATA_DIR = path.join(process.cwd(), "data");
const VIDEOS_DIR = path.join(DATA_DIR, "videos");
const VERTEX_SA_PATH = path.join(DATA_DIR, "vertex-service-account.json");

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

async function getVertexAuthIfAvailable(): Promise<{
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

const BRAND_VISUAL_DNA =
  "Ultra-clean cinematic 3D scientific visualization, deep obsidian space and dark laboratory aesthetic, volumetric cyan and warm solar-amber rim lighting, crisp photorealistic macro detail, dramatic scale contrast, vertical 9:16 portrait composition, strictly NO text, NO letters, NO watermark";

async function directStoryboardWithMasterRules(params: {
  topicOrTitle: string;
  seedHook?: string;
  seedVoiceover?: string;
  channelHandle: string;
  geminiKey: string;
}): Promise<{
  title: string;
  beats: VideoBeatSpec[];
  scientificSources: string[];
  pinnedComment: string;
  tags: string[];
  directorModelUsed: string;
}> {
  const prompt = `You are the Master Showrunner for the US Science YouTube Shorts channel "Proof of Wonder" (${params.channelHandle}).
Apply ALL 7 Data-Driven Master Rules distilled from 150 top viral US Science Outliers (Cleo Abram, AstroKobi, Zack D. Films, MinuteEarth):
1. TARGET DURATION: ~44-48 seconds (~112-125 spoken US English words total across EXACTLY 6 visual beats).
2. RULE 1 (0-3s Hook): Beat 1 narration MUST start mid-consequence with an everyday physical paradox (NEVER "Did you know" or greetings).
3. RULE 2 (Visual Pacing): 6 distinct, vivid 3D visual beats (~7.5s each). Every imagePrompt MUST describe a crystal-clear physical scene with NO text/words inside the image.
4. RULE 5 (35s Peak-Dopamine Sub CTA): Beat 5 narration naturally weaves in "Follow Proof of Wonder for daily strange science" right after the scientific climax reveal.
5. RULE 6 (Infinite Loop): Beat 6 final words end on an unfinished causal bridge that grammatically flows straight back into Beat 1's opening words!
6. RULE 7 (Real Scientific Sources): Provide 2 real, verifiable scientific references (NASA, ESA, NOAA, MIT, Nature, etc.).
7. TITLE: Clean US English, 36-52 characters, strong curiosity gap, ZERO hashtags!

Topic / Seed Title: "${params.topicOrTitle}"
${params.seedHook ? `Seed Hook reference: "${params.seedHook}"` : ""}
${params.seedVoiceover ? `Seed Script reference: "${params.seedVoiceover}"` : ""}

Return pure JSON matching this exact schema:
{
  "title": "Clean US English title (no hashtags)",
  "beats": [
    {
      "beatIndex": 1,
      "narration": "18-22 spoken words...",
      "imagePrompt": "Detailed visual scene description (no text in image)",
      "archiveQuery": "3-4 concrete scientific visual keywords for NASA/Wikimedia photo search (e.g. 'solar flare corona plasma', 'earth magnetosphere aurora', 'electron microscope mosquito')"
    }
  ],
  "scientificSources": [
    "NASA / University Source 1",
    "Peer-reviewed / Agency Source 2"
  ],
  "pinnedComment": "Engaging US English debate question for comments",
  "tags": ["10 relevant US English science tags"]
}`;

  // 1. Try Vertex AI Flagship first (gemini-4-argon -> gemini-3.8-flash -> gemini-3.1-pro-preview)
  const vertex = await getVertexAuthIfAvailable();
  if (vertex) {
    for (const vModel of [
      "gemini-4-argon",
      "gemini-3.8-flash",
      "gemini-3.1-pro-preview",
    ]) {
      try {
        const vUrl = `https://aiplatform.googleapis.com/v1beta1/projects/${vertex.projectId}/locations/global/publishers/google/models/${vModel}:generateContent`;
        const vGenConfig: Record<string, unknown> = {
          temperature: 0.7,
          responseMimeType: "application/json",
        };
        if (vModel.includes("3.8")) {
          vGenConfig.thinkingConfig = { thinkingBudget: 512 };
        }
        const res = await fetch(vUrl, {
          method: "POST",
          signal: AbortSignal.timeout(32_000),
          headers: {
            Authorization: `Bearer ${vertex.token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            contents: [{ role: "user", parts: [{ text: prompt }] }],
            generationConfig: vGenConfig,
          }),
          cache: "no-store",
        });
        if (res.ok) {
          const json = await res.json();
          await recordAiUsageCall({
            provider: "vertex",
            model: vModel,
            feature: "Đạo diễn kịch bản 6 cảnh",
            usageMetadata: json?.usageMetadata,
            fallbackPromptChars: prompt.length,
          });
          const parts: Array<{ text?: string; thought?: boolean }> =
            json?.candidates?.[0]?.content?.parts || [];
          const text = (
            parts.find((p) => !p.thought && p.text) || parts[parts.length - 1]
          )?.text;
          if (text) {
            const parsed = JSON.parse(
              text.replace(/^```json\s*/i, "").replace(/```\s*$/, "")
            );
            if (Array.isArray(parsed.beats) && parsed.beats.length >= 4) {
              return {
                title: String(parsed.title || params.topicOrTitle)
                  .replace(/#\S+/g, "")
                  .trim(),
                beats: parsed.beats.slice(0, 6),
                scientificSources: Array.isArray(parsed.scientificSources)
                  ? parsed.scientificSources
                  : ["NASA Science Mission Directorate"],
                pinnedComment:
                  parsed.pinnedComment ||
                  "What part of this phenomenon surprised you the most? 👇🔬",
                tags: Array.isArray(parsed.tags)
                  ? parsed.tags
                  : buildDefaultTags(params.topicOrTitle),
                directorModelUsed: `vertex/${vModel}`,
              };
            }
          }
        }
      } catch {
        // fallback cleanly
      }
    }
  }

  // 2. Active Gemini API Key (gemini-3.6-flash fast & reliable, then gemini-3.8-flash with thinkingBudget)
  if (params.geminiKey) {
    for (const model of [
      "gemini-3.6-flash",
      "gemini-3.8-flash",
      "gemini-3.5-flash",
    ]) {
      try {
        const genConfig: Record<string, unknown> = {
          temperature: 0.72,
          responseMimeType: "application/json",
        };
        if (model.includes("3.8")) {
          genConfig.thinkingConfig = { thinkingBudget: 256 };
        }
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
            params.geminiKey
          )}`,
          {
            method: "POST",
            signal: AbortSignal.timeout(26_000),
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: genConfig,
            }),
            cache: "no-store",
          }
        );
        if (!res.ok) continue;
        const json = await res.json();
        await recordAiUsageCall({
          provider: "gemini_free",
          model,
          feature: "Đạo diễn kịch bản 6 cảnh",
          usageMetadata: json?.usageMetadata,
          fallbackPromptChars: prompt.length,
        });
        const parts: Array<{ text?: string; thought?: boolean }> =
          json?.candidates?.[0]?.content?.parts || [];
        const text = (
          parts.find((p) => !p.thought && p.text) || parts[parts.length - 1]
        )?.text;
        if (!text) continue;
        const parsed = JSON.parse(
          text.replace(/^```json\s*/i, "").replace(/```\s*$/, "")
        );
        if (Array.isArray(parsed.beats) && parsed.beats.length >= 4) {
          return {
            title: String(parsed.title || params.topicOrTitle)
              .replace(/#\S+/g, "")
              .trim(),
            beats: parsed.beats.slice(0, 6),
            scientificSources: Array.isArray(parsed.scientificSources)
              ? parsed.scientificSources
              : ["NASA Science Mission Directorate"],
            pinnedComment:
              parsed.pinnedComment ||
              "What part of this phenomenon surprised you the most? 👇🔬",
            tags: Array.isArray(parsed.tags)
              ? parsed.tags
              : buildDefaultTags(params.topicOrTitle),
            directorModelUsed: model,
          };
        }
      } catch {
        // try next model
      }
    }
  }

  // 3. Deterministic fallback from existing seed script
  const fullSeed = `${(params.seedHook || "").replace(/^\.\.\.\s*/, "")} ${
    params.seedVoiceover || params.topicOrTitle
  }`.trim();
  const sentences = fullSeed
    .split(/(?<=[.!?])\s+/)
    .filter(Boolean);
  const fallbackBeats: VideoBeatSpec[] = Array.from({ length: 6 }, (_, i) => ({
    beatIndex: i + 1,
    narration:
      sentences[i] ||
      `Discover the extraordinary physics hidden inside ${params.topicOrTitle}.`,
    imagePrompt: `Dramatic scientific 3D cutaway visualization of ${params.topicOrTitle}, scene ${
      i + 1
    }, glowing energy waves in deep space`,
  }));

  return {
    title: params.topicOrTitle.replace(/#\S+/g, "").trim(),
    beats: fallbackBeats,
    scientificSources: ["NASA Astrophysics & Planetary Science Division"],
    pinnedComment: `What surprised you most about ${params.topicOrTitle}? 👇🔬`,
    tags: buildDefaultTags(params.topicOrTitle),
    directorModelUsed: "template-fallback",
  };
}

function getWavDurationSeconds(wavBuffer: Buffer): number {
  try {
    // Parse RIFF WAV chunks for exact byteRate & data chunk size
    if (
      wavBuffer.length > 44 &&
      wavBuffer.toString("ascii", 0, 4) === "RIFF" &&
      wavBuffer.toString("ascii", 8, 12) === "WAVE"
    ) {
      let offset = 12;
      let byteRate = 48000; // default 24kHz * 1ch * 2B
      let dataBytes = wavBuffer.length - 44;

      while (offset + 8 <= wavBuffer.length) {
        const chunkId = wavBuffer.toString("ascii", offset, offset + 4);
        const chunkSize = wavBuffer.readUInt32LE(offset + 4);
        if (chunkId === "fmt " && offset + 20 <= wavBuffer.length) {
          byteRate = wavBuffer.readUInt32LE(offset + 16);
        } else if (chunkId === "data") {
          dataBytes = Math.min(chunkSize, wavBuffer.length - (offset + 8));
          break;
        }
        offset += 8 + chunkSize + (chunkSize % 2);
      }
      if (byteRate > 0 && dataBytes > 0) {
        return Math.max(5, dataBytes / byteRate);
      }
    }
  } catch {
    // fallback calculation
  }
  return Math.max(10, (wavBuffer.length - 44) / 48000);
}

function wrapRawPcmToWav(pcmBuffer: Buffer, sampleRate = 24000): Buffer {
  if (
    pcmBuffer.length > 12 &&
    pcmBuffer.toString("ascii", 0, 4) === "RIFF"
  ) {
    return pcmBuffer;
  }
  const header = Buffer.alloc(44);
  const dataLen = pcmBuffer.length;
  header.write("RIFF", 0);
  header.writeUInt32LE(36 + dataLen, 4);
  header.write("WAVE", 8);
  header.write("fmt ", 12);
  header.writeUInt32LE(16, 16); // PCM
  header.writeUInt16LE(1, 20); // AudioFormat = 1 (PCM)
  header.writeUInt16LE(1, 22); // Channels = 1
  header.writeUInt32LE(sampleRate, 24);
  header.writeUInt32LE(sampleRate * 2, 28); // ByteRate
  header.writeUInt16LE(2, 32); // BlockAlign
  header.writeUInt16LE(16, 34); // BitsPerSample
  header.write("data", 36);
  header.writeUInt32LE(dataLen, 40);
  return Buffer.concat([header, pcmBuffer]);
}

async function synthesizeStudioVoiceoverWav(params: {
  narrationText: string;
  geminiKey: string;
  voiceName?: string;
  vertex?: { token: string; projectId: string } | null;
}): Promise<{ wavBuffer: Buffer; ttsModelUsed: string }> {
  const voice = params.voiceName || "Puck";
  const spokenPrompt = `Read this science narration briskly, clearly, and captivatingly like a top US YouTube science host, with zero trailing silence at the end:\n\n${params.narrationText}`;

  // 1. Primary: Google Cloud Vertex AI ($300 Credit — high quota, zero rate-limit!)
  if (params.vertex) {
    try {
      const vTtsUrl = `https://aiplatform.googleapis.com/v1beta1/projects/${params.vertex.projectId}/locations/global/publishers/google/models/gemini-3.8-flash-tts:generateContent`;
      const res = await fetch(vTtsUrl, {
        method: "POST",
        signal: AbortSignal.timeout(35_000),
        headers: {
          Authorization: `Bearer ${params.vertex.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          contents: [{ role: "user", parts: [{ text: spokenPrompt }] }],
          generationConfig: {
            responseModalities: ["AUDIO"],
            speechConfig: {
              voiceConfig: {
                prebuiltVoiceConfig: { voiceName: voice },
              },
            },
          },
        }),
        cache: "no-store",
      });
      if (res.ok) {
        const json = await res.json();
        await recordAiUsageCall({
          provider: "vertex",
          model: "gemini-3.8-flash-tts",
          feature: "Thu âm giọng đọc Mỹ (TTS)",
          usageMetadata: json?.usageMetadata,
          fallbackPromptChars: spokenPrompt.length,
          isTts: true,
        });
        const inline = json?.candidates?.[0]?.content?.parts?.find(
          (p: { inlineData?: { data?: string; mimeType?: string } }) =>
            p.inlineData?.data
        )?.inlineData;
        if (inline?.data) {
          const rawBuf = Buffer.from(inline.data, "base64");
          const wavBuffer = wrapRawPcmToWav(rawBuf, 24000);
          return { wavBuffer, ttsModelUsed: "vertex/gemini-3.8-flash-tts" };
        }
      }
    } catch {
      // fall through to API Key TTS
    }
  }

  // 2. Fallback: Gemini API Key TTS
  for (const ttsModel of [
    "gemini-3.8-flash-tts",
    "gemini-2.5-flash-preview-tts",
  ]) {
    try {
      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${ttsModel}:generateContent?key=${encodeURIComponent(
          params.geminiKey
        )}`,
        {
          method: "POST",
          signal: AbortSignal.timeout(35_000),
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ parts: [{ text: spokenPrompt }] }],
            generationConfig: {
              responseModalities: ["AUDIO"],
              speechConfig: {
                voiceConfig: {
                  prebuiltVoiceConfig: { voiceName: voice },
                },
              },
            },
          }),
          cache: "no-store",
        }
      );
      if (!res.ok) continue;
      const json = await res.json();
      await recordAiUsageCall({
        provider: "gemini_free",
        model: ttsModel,
        feature: "Thu âm giọng đọc Mỹ (TTS)",
        usageMetadata: json?.usageMetadata,
        fallbackPromptChars: spokenPrompt.length,
        isTts: true,
      });
      const inline = json?.candidates?.[0]?.content?.parts?.find(
        (p: { inlineData?: { data?: string; mimeType?: string } }) =>
          p.inlineData?.data
      )?.inlineData;
      if (inline?.data) {
        const rawBuf = Buffer.from(inline.data, "base64");
        const wavBuffer = wrapRawPcmToWav(rawBuf, 24000);
        return { wavBuffer, ttsModelUsed: ttsModel };
      }
    } catch {
      // try next TTS model
    }
  }

  throw new Error(
    "Không thể tạo giọng đọc AI (Gemini TTS). Hãy kiểm tra kết nối mạng hoặc khóa Gemini API."
  );
}

async function downloadImageBuffer(url: string, timeoutMs = 5500): Promise<Buffer | null> {
  try {
    const res = await fetch(url, {
      signal: AbortSignal.timeout(timeoutMs),
      headers: { "User-Agent": "SubPulseAutopilot/1.0 (https://youtube.com/@proofofwonderscience)" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const arr = await res.arrayBuffer();
    return arr.byteLength > 5000 ? Buffer.from(arr) : null;
  } catch {
    return null;
  }
}

async function searchNasaArchiveImage(
  query: string,
  usedUrls: Set<string>
): Promise<Buffer | null> {
  try {
    const res = await fetch(
      `https://images-api.nasa.gov/search?q=${encodeURIComponent(
        query
      )}&media_type=image`,
      {
        signal: AbortSignal.timeout(4500),
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const json = await res.json();
    const items: Array<{
      data?: Array<{ nasa_id?: string }>;
      links?: Array<{ href?: string; render?: string }>;
    }> = json?.collection?.items || [];
    for (const item of items.slice(0, 12)) {
      const nasaId = item.data?.[0]?.nasa_id || "";
      if (nasaId && usedUrls.has(`nasa:${nasaId}`)) continue;
      const href = item.links?.find(
        (l) =>
          l.href &&
          /\.(jpg|jpeg|png)$/i.test(l.href.split("?")[0]) &&
          !usedUrls.has(l.href)
      )?.href;
      if (href) {
        const buf = await downloadImageBuffer(href, 5000);
        if (buf) {
          usedUrls.add(href);
          if (nasaId) usedUrls.add(`nasa:${nasaId}`);
          return buf;
        }
      }
    }
  } catch {
    // ignore
  }
  return null;
}

async function searchWikimediaScienceImage(
  query: string,
  usedUrls: Set<string>
): Promise<Buffer | null> {
  try {
    const apiUrl = `https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrnamespace=6&gsrsearch=${encodeURIComponent(
      `filetype:bitmap ${query}`
    )}&gsrlimit=6&prop=imageinfo&iiprop=url|mime&iiurlwidth=1280&format=json`;
    const res = await fetch(apiUrl, {
      signal: AbortSignal.timeout(4500),
      headers: { "User-Agent": "SubPulseAutopilot/1.0" },
      cache: "no-store",
    });
    if (!res.ok) return null;
    const json = await res.json();
    const pages = Object.values(json?.query?.pages || {}) as Array<{
      imageinfo?: Array<{ thumburl?: string; url?: string; mime?: string }>;
    }>;
    for (const page of pages) {
      const info = page.imageinfo?.[0];
      const mime = info?.mime || "";
      if (!mime.includes("jpeg") && !mime.includes("png")) continue;
      // Prefer 1280px thumburl so we never pull a 40MB raw observatory PNG
      const candidate = info?.thumburl || info?.url;
      if (candidate && !usedUrls.has(candidate)) {
        const buf = await downloadImageBuffer(candidate, 5000);
        if (buf) {
          usedUrls.add(candidate);
          return buf;
        }
      }
    }
  } catch {
    // ignore
  }
  return null;
}

async function resolveAllSceneVisuals(params: {
  beats: VideoBeatSpec[];
  topicOrTitle: string;
  vertex: { token: string; projectId: string } | null;
}): Promise<{
  buffers: Array<Buffer | null>;
  engineSummary: "vertex-gemini-image" | "hybrid-3d-nasa-science" | "flux-3d-ai";
}> {
  const usedUrls = new Set<string>();
  const buffers: Array<Buffer | null> = new Array(params.beats.length).fill(null);
  let usedVertexCount = 0;
  let usedArchiveCount = 0;

  // TIER 1: Google Cloud Vertex AI ($300 Credit) — Generate ALL 6 native 9:16 3D scenes IN PARALLEL via gemini-2.5-flash-image!
  if (params.vertex) {
    const vertexResults = await Promise.all(
      params.beats.map(async (beat) => {
        const fullPrompt = `Generate an ultra-clean vertical 9:16 3D scientific visual: ${beat.imagePrompt}. ${BRAND_VISUAL_DNA}`;
        try {
          const vUrl = `https://aiplatform.googleapis.com/v1beta1/projects/${params.vertex!.projectId}/locations/global/publishers/google/models/gemini-2.5-flash-image:generateContent`;
          const res = await fetch(vUrl, {
            method: "POST",
            signal: AbortSignal.timeout(28_000),
            headers: {
              Authorization: `Bearer ${params.vertex!.token}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              contents: [{ role: "user", parts: [{ text: fullPrompt }] }],
              generationConfig: {
                responseModalities: ["TEXT", "IMAGE"],
                imageConfig: { aspectRatio: "9:16" },
              },
            }),
            cache: "no-store",
          });
          if (!res.ok) return null;
          const json = await res.json();
          const imgPart = json?.candidates?.[0]?.content?.parts?.find(
            (p: { inlineData?: { data?: string } }) => p.inlineData?.data
          );
          if (imgPart?.inlineData?.data) {
            await recordAiUsageCall({
              provider: "vertex",
              model: "gemini-2.5-flash-image",
              feature: "Vẽ cảnh 3D 9:16 (Vertex Image)",
              usageMetadata: json?.usageMetadata,
              imageCount: 1,
            });
            return Buffer.from(imgPart.inlineData.data, "base64");
          }
        } catch {
          // fallback per-beat below
        }
        return null;
      })
    );

    vertexResults.forEach((buf, idx) => {
      if (buf) {
        buffers[idx] = buf;
        usedVertexCount++;
      }
    });
  }

  let fluxAvailable = usedVertexCount === 0;

  for (let i = 0; i < params.beats.length; i++) {
    if (buffers[i]) continue;
    const beat = params.beats[i];
    const fullPrompt = `${beat.imagePrompt}. ${BRAND_VISUAL_DNA}`;
    let sceneBuf: Buffer | null = null;

    // TIER 2: Flux 3D AI Generator (Hero Hook Beat 1 + any open burst slot, fast-fail on 402/429)
    if (!sceneBuf && fluxAvailable) {
      try {
        const seed = 1000 + i * 137 + (Date.now() % 997);
        const fluxUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(
          fullPrompt.slice(0, 360)
        )}?width=720&height=1280&nologo=true&model=flux&seed=${seed}`;
        const res = await fetch(fluxUrl, {
          signal: AbortSignal.timeout(9000),
          cache: "no-store",
        });
        if (res.status === 402 || res.status === 429) {
          fluxAvailable = false;
        } else if (res.ok) {
          const arr = await res.arrayBuffer();
          if (arr.byteLength > 5000) {
            sceneBuf = Buffer.from(arr);
          }
        }
      } catch {
        fluxAvailable = false;
      }
    }

    // TIER 3 & 4: Real High-Res NASA / ESA / Wikimedia Scientific Photography (Deduplicated per beat!)
    if (!sceneBuf) {
      const cleanQuery = (
        beat.archiveQuery ||
        beat.imagePrompt
          .replace(/[^a-zA-Z0-9\s]/g, " ")
          .split(/\s+/)
          .filter((w) => w.length > 3)
          .slice(0, 4)
          .join(" ") ||
        params.topicOrTitle
      ).trim();

      const isSpaceOrEarth =
        /\b(sun|solar|space|nasa|star|planet|earth|moon|orbit|galaxy|nebula|black hole|astronaut|mars|jupiter|cosmos|aurora|magnetic|atmosphere|jet stream)\b/i.test(
          `${cleanQuery} ${params.topicOrTitle}`
        );

      const broadQuery = cleanQuery.split(/\s+/).slice(0, 2).join(" ");
      const coreTopicNoun =
        params.topicOrTitle
          .replace(/[^a-zA-Z0-9\s]/g, " ")
          .split(/\s+/)
          .find(
            (w) =>
              w.length > 2 &&
              !/^(why|how|the|what|when|your|secretly|terrifying|strange|makes|would|never|most|from|into|this|that)$/i.test(
                w
              )
          ) || "galaxy";

      if (isSpaceOrEarth) {
        sceneBuf =
          (await searchNasaArchiveImage(cleanQuery, usedUrls)) ||
          (await searchWikimediaScienceImage(cleanQuery, usedUrls)) ||
          (await searchNasaArchiveImage(broadQuery, usedUrls)) ||
          (await searchNasaArchiveImage(coreTopicNoun, usedUrls)) ||
          (await searchNasaArchiveImage("nebula galaxy", usedUrls));
      } else {
        sceneBuf =
          (await searchWikimediaScienceImage(cleanQuery, usedUrls)) ||
          (await searchWikimediaScienceImage(broadQuery, usedUrls)) ||
          (await searchNasaArchiveImage(broadQuery, usedUrls)) ||
          (await searchWikimediaScienceImage(`${coreTopicNoun} science`, usedUrls)) ||
          (await searchNasaArchiveImage("earth science", usedUrls));
      }
      if (sceneBuf) {
        usedArchiveCount++;
      } else {
        sceneBuf = buffers.find((b): b is Buffer => Boolean(b)) || null;
      }
    }

    buffers[i] = sceneBuf;
  }

  const engineSummary =
    usedVertexCount >= 3
      ? "vertex-gemini-image"
      : usedArchiveCount > 0
      ? "hybrid-3d-nasa-science"
      : "flux-3d-ai";

  return { buffers, engineSummary };
}

function formatAssTime(seconds: number): string {
  const clamped = Math.max(0, seconds);
  const h = Math.floor(clamped / 3600);
  const m = Math.floor((clamped % 3600) / 60);
  const s = Math.floor(clamped % 60);
  const cs = Math.floor((clamped - Math.floor(clamped)) * 100);
  return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(
    2,
    "0"
  )}.${String(cs).padStart(2, "0")}`;
}

function buildSafeZoneAssSubtitles(
  fullNarration: string,
  totalDurationSec: number
): string {
  const words = fullNarration
    .replace(/\s+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean);

  // Group into crisp 3-word kinetic chunks
  const chunks: string[] = [];
  for (let i = 0; i < words.length; i += 3) {
    chunks.push(words.slice(i, i + 3).join(" "));
  }

  const totalChars = Math.max(
    1,
    chunks.reduce((sum, c) => sum + c.length, 0)
  );
  const usableDuration = Math.max(1, totalDurationSec - 0.15);

  const header = `[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: SafeKinetic,Arial,74,&H00FFFFFF,&H0000FFFF,&H00080808,&H80000000,-1,0,0,0,100,100,1,0,1,5,3,2,90,90,620,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`;

  let cursor = 0.05;
  const lines: string[] = [];

  chunks.forEach((chunk, idx) => {
    const share = (chunk.length / totalChars) * usableDuration;
    const start = cursor;
    const end =
      idx === chunks.length - 1
        ? totalDurationSec
        : Math.min(totalDurationSec, cursor + share);
    cursor = end;

    // Highlight numbers or dramatic words in warm amber (&H0024BFFB in BGR = #FBBF24)
    const styledWords = chunk
      .split(" ")
      .map((w) => {
        const clean = w.replace(/[{}]/g, "");
        if (
          /\d/.test(clean) ||
          /^(never|million|billion|silent|deadly|impossible|proof|wonder|subscribe|follow)$/i.test(
            clean.replace(/[^a-z0-9]/gi, "")
          )
        ) {
          return `{\\c&H0024BFFB&}${clean.toUpperCase()}{\\c&H00FFFFFF&}`;
        }
        return clean.toUpperCase();
      })
      .join(" ");

    lines.push(
      `Dialogue: 0,${formatAssTime(start)},${formatAssTime(
        end
      )},SafeKinetic,,0,0,0,,{\\fad(45,30)}${styledWords}`
    );
  });

  return header + lines.join("\n") + "\n";
}

function runFfmpeg(args: string[], cwd: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!ffmpegPath) {
      reject(new Error("Không tìm thấy bộ dựng video ffmpeg-static."));
      return;
    }
    const proc = spawn(ffmpegPath, args, { cwd, windowsHide: true });
    let stderr = "";
    proc.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    proc.on("error", (err) => reject(err));
    proc.on("close", (code) => {
      if (code === 0) resolve();
      else
        reject(
          new Error(
            `FFmpeg thoát với mã ${code}: ${stderr.slice(-350)}`
          )
        );
    });
  });
}

export async function generateCompleteShortMp4(params: {
  store: StoreData;
  episodeId?: string;
  topicOrTitle: string;
  seedHook?: string;
  seedVoiceover?: string;
  voiceName?: string;
}): Promise<GeneratedVideoPackage> {
  await mkdir(VIDEOS_DIR, { recursive: true });

  const activeCh =
    params.store.myChannels.find(
      (c) => c.id === params.store.activeChannelId
    ) || params.store.myChannels[0];
  const handle = activeCh?.handle
    ? activeCh.handle.startsWith("@")
      ? activeCh.handle
      : `@${activeCh.handle}`
    : "@proofofwonderscience";

  const geminiKey = getEffectiveGeminiKey(params.store);
  const vertex = await getVertexAuthIfAvailable();
  if (!geminiKey && !vertex) {
    throw new Error("Chưa cấu hình khóa Google Gemini API hoặc Vertex AI.");
  }

  // 1. Direct 6-Beat Master-Rule Storyboard
  const storyboard = await directStoryboardWithMasterRules({
    topicOrTitle: params.topicOrTitle,
    seedHook: params.seedHook,
    seedVoiceover: params.seedVoiceover,
    channelHandle: handle,
    geminiKey,
  });

  const fullNarration = storyboard.beats
    .map((b) => b.narration.replace(/^\.\.\.\s*/, "").trim())
    .join(" ")
    .replace(/\s{2,}/g, " ")
    .trim();

  // 2. Generate Voiceover WAV + 6 Scene Images IN PARALLEL for maximum speed!
  const [ttsResult, visualPack] = await Promise.all([
    synthesizeStudioVoiceoverWav({
      narrationText: fullNarration,
      geminiKey,
      voiceName: params.voiceName || "Puck",
      vertex,
    }),
    resolveAllSceneVisuals({
      beats: storyboard.beats,
      topicOrTitle: storyboard.title || params.topicOrTitle,
      vertex,
    }),
  ]);

  const durationSec = getWavDurationSeconds(ttsResult.wavBuffer);
  const jobId = `job-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const workDir = path.join(VIDEOS_DIR, jobId);
  await mkdir(workDir, { recursive: true });

  const imageEngineUsed = visualPack.engineSummary;

  try {
    await writeFile(path.join(workDir, "voiceover.wav"), ttsResult.wavBuffer);

    const assContent = buildSafeZoneAssSubtitles(fullNarration, durationSec);
    await writeFile(path.join(workDir, "captions.ass"), assContent, "utf-8");

    const numScenes = storyboard.beats.length;
    const perSceneSec = durationSec / numScenes;
    const fps = 25;
    const framesPerScene = Math.max(25, Math.ceil(perSceneSec * fps));

    // Save or synthesize fallback dark-space frame for each scene, then render individual MP4 clips with smooth Ken Burns zoom
    const clipNames: string[] = [];
    for (let i = 0; i < numScenes; i++) {
      const sceneBuf = visualPack.buffers[i];
      const imgFile = `scene_${i}.jpg`;
      const clipFile = `clip_${i}.mp4`;
      clipNames.push(clipFile);

      if (sceneBuf) {
        await writeFile(path.join(workDir, imgFile), sceneBuf);
        const zoomExpr =
          i % 2 === 0
            ? `min(zoom+0.0012,1.16)`
            : `if(eq(on,1),1.16,max(1.0,zoom-0.0012))`;

        await runFfmpeg(
          [
            "-y",
            "-loop",
            "1",
            "-i",
            imgFile,
            "-vf",
            `scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,eq=contrast=1.10:saturation=1.16:brightness=-0.05,zoompan=z='${zoomExpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${framesPerScene}:s=1080x1920:fps=${fps},setsar=1`,
            "-t",
            perSceneSec.toFixed(3),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            clipFile,
          ],
          workDir
        );
      } else {
        // Guaranteed local procedural cosmic fallback if an image request timed out
        await runFfmpeg(
          [
            "-y",
            "-f",
            "lavfi",
            "-i",
            `color=c=#070B19:s=1080x1920:r=${fps}:d=${perSceneSec.toFixed(3)}`,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            clipFile,
          ],
          workDir
        );
      }
    }

    // Concatenate the 6 smooth Ken Burns clips + Burn Safe-Zone ASS Kinetic Captions + Mix subtle -24dB Cosmic Wonder Drone under crisp Voiceover
    const concatList = clipNames.map((n) => `file '${n}'`).join("\n");
    await writeFile(path.join(workDir, "concat.txt"), concatList, "utf-8");

    const safeSlug = (params.episodeId || "short")
      .replace(/[^a-zA-Z0-9_-]/g, "")
      .slice(0, 24);
    const outFileName = `${safeSlug}-${Date.now()}.mp4`;
    const finalOutPath = path.join(VIDEOS_DIR, outFileName);

    await runFfmpeg(
      [
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "concat.txt",
        "-i",
        "voiceover.wav",
        "-f",
        "lavfi",
        "-i",
        `aevalsrc=0.025*sin(2*PI*110*t)+0.018*sin(2*PI*164.81*t)+0.012*sin(2*PI*220*t):s=24000:d=${durationSec.toFixed(
          3
        )}`,
        "-filter_complex",
        `[0:v]subtitles=captions.ass[vout];[1:a]volume=1.15[vo];[2:a]afade=t=in:st=0:d=0.6,afade=t=out:st=${Math.max(
          0,
          durationSec - 0.8
        ).toFixed(2)}:d=0.8[bgm];[vo][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]`,
        "-map",
        "[vout]",
        "-map",
        "[aout]",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        "-shortest",
        finalOutPath,
      ],
      workDir
    );

    const fileStats = await stat(finalOutPath);
    if (fileStats.size < 10_000) {
      throw new Error("File MP4 xuất ra không hợp lệ.");
    }

    const baseDesc = buildDefaultDescription(
      storyboard.title,
      storyboard.beats[0]?.narration || "",
      handle
    );
    const sourcesBlock =
      storyboard.scientificSources.length > 0
        ? `\n\n📚 SCIENTIFIC SOURCES:\n${storyboard.scientificSources
            .map((s) => `• ${s}`)
            .join("\n")}`
        : "";

    return {
      videoFileName: outFileName,
      videoUrl: `/api/video/file/${encodeURIComponent(outFileName)}`,
      durationSeconds: Math.round(durationSec),
      directorModelUsed: storyboard.directorModelUsed,
      imageEngineUsed,
      ttsModelUsed: ttsResult.ttsModelUsed,
      title: storyboard.title,
      fullNarration,
      description: `${baseDesc}${sourcesBlock}`,
      tags: storyboard.tags,
      pinnedComment: storyboard.pinnedComment,
      scientificSources: storyboard.scientificSources,
    };
  } finally {
    // Clean up temporary intermediate frames/wavs, keeping only final MP4 in data/videos/
    await rm(workDir, { recursive: true, force: true }).catch(() => {});
  }
}

export function getGeneratedVideoPath(fileName: string): string {
  const cleanName = path.basename(fileName);
  return path.join(VIDEOS_DIR, cleanName);
}
