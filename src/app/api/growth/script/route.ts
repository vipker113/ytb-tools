import { listMacRenderedEpisodes } from "@/lib/mac-pipeline";
import { getEffectiveGeminiKey, readStore } from "@/lib/store";
import type { StoreData } from "@/lib/types";
import {
  buildGeminiModelChain,
  diagnoseExistingVideosForSubRescue,
  generateViralShortBlueprint,
} from "@/lib/viral-script";
import { fetchChannelShortsAnalytics } from "@/lib/youtube-analytics";

export interface RetentionWinnerBenchmark {
  videoId: string;
  title: string;
  views: number;
  stayedToWatchPct: number | null;
  averageViewPercentage: number | null;
}

async function buildLiveRetentionTelemetry(store: StoreData): Promise<{
  contextPrompt: string;
  winners: RetentionWinnerBenchmark[];
}> {
  const activeChannel =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];
  const videos = activeChannel?.recentVideos || [];
  const analytics = await fetchChannelShortsAnalytics(store).catch(() => null);
  const byId = analytics?.byVideoId || {};

  const enriched = videos.map((v) => {
    const m = byId[v.id];
    const stayed = m?.stayedToWatchPct ?? null;
    const apv = m?.averageViewPercentage ?? null;
    const retentionScore =
      (stayed !== null ? stayed * 1.4 : 45) +
      (apv !== null ? Math.min(apv, 160) * 0.6 : 50) +
      Math.log10(Math.max(10, v.views)) * 10;
    return {
      videoId: v.id,
      title: v.title,
      views: v.views,
      stayedToWatchPct: stayed,
      averageViewPercentage: apv,
      avgDurSec: m?.averageViewDurationSec ?? null,
      subs: m?.netSubscribers ?? 0,
      retentionScore,
    };
  });

  const sortedByRetention = [...enriched].sort(
    (a, b) => b.retentionScore - a.retentionScore
  );

  const topWinners = sortedByRetention.slice(0, 4);
  const weakHooks = enriched.filter(
    (v) => v.stayedToWatchPct !== null && v.stayedToWatchPct < 28
  );

  const outlierExamples = (store.competitors || [])
    .flatMap((c) => c.videos)
    .filter((v) => v.outlierScore >= 2)
    .sort((a, b) => b.outlierScore - a.outlierScore)
    .slice(0, 8)
    .map(
      (v) =>
        `- "${v.title}" by ${v.channelTitle} (${v.outlierScore.toFixed(
          1
        )}x channel average, ${v.views.toLocaleString("en-US")} views)`
    );

  const lines: string[] = [];
  if (topWinners.length > 0) {
    lines.push(
      "CHANNEL HIGH-RETENTION WINNERS (EMULATE THEIR HOOK & PACING STRUCTURE):"
    );
    for (const w of topWinners) {
      const stayedStr =
        w.stayedToWatchPct !== null
          ? `Stayed-to-Watch: ${w.stayedToWatchPct}%`
          : "";
      const apvStr =
        w.averageViewPercentage !== null
          ? `Avg View %: ${w.averageViewPercentage}%`
          : "";
      const durStr = w.avgDurSec !== null ? `Avg Watch: ${w.avgDurSec}s` : "";
      const metrics = [stayedStr, apvStr, durStr, `${w.views} views`]
        .filter(Boolean)
        .join(" | ");
      lines.push(`- "${w.title}" (${metrics})`);
    }
  }

  if (weakHooks.length > 0) {
    lines.push(
      "\nLOW-HOOK ANTI-PATTERNS ON CHANNEL (STRICTLY AVOID THIS OPENING STYLE):"
    );
    for (const low of weakHooks) {
      lines.push(
        `- "${low.title}" (Only ${low.stayedToWatchPct}% stayed to watch — 90% swiped away in first 3s; avoid slow/technical openings without immediate visual shock!)`
      );
    }
  }

  if (outlierExamples.length > 0) {
    lines.push("\nCOMPETITOR VIRAL OUTLIERS (PROVEN HIGH-DEMAND ANGLES):");
    lines.push(...outlierExamples);
  }

  return {
    contextPrompt: lines.join("\n"),
    winners: topWinners.map((w) => ({
      videoId: w.videoId,
      title: w.title,
      views: w.views,
      stayedToWatchPct: w.stayedToWatchPct,
      averageViewPercentage: w.averageViewPercentage,
    })),
  };
}

export interface AiSuggestedTopic {
  title: string;
  targetKeyword: string;
  coreParadoxHook: string;
  whyItFitsChannelVi: string;
  suggestedDurationSec: number;
}

const FALLBACK_TOPICS: AiSuggestedTopic[] = [
  {
    title: "Why Scientists Sealed This Cave With 5-Million-Year-Old Air Forever",
    targetKeyword: "movile cave",
    coreParadoxHook:
      "33 species evolved in complete darkness breathing toxic hydrogen sulfide instead of oxygen.",
    whyItFitsChannelVi:
      "Nối tiếp trực tiếp chuỗi video 'Deadly Ocean Lakes' & 'Forbidden Zones' đang giữ chân tốt nhất trên kênh.",
    suggestedDurationSec: 78,
  },
  {
    title: "What Actually Happens Inside the Deepest Hole Humans Ever Drilled?",
    targetKeyword: "kola superdeep borehole",
    coreParadoxHook:
      "At 12,262 meters down, solid granite stopped acting like rock and started behaving like boiling plastic.",
    whyItFitsChannelVi:
      "Khán giả Mỹ cực thích mô-típ đi sâu vào lòng đất (cùng tệp với Lava Cave Gold & Gemstone Mines).",
    suggestedDurationSec: 74,
  },
  {
    title: "Why Rain on Titan Falls Slow Enough to Outrun on Foot",
    targetKeyword: "titan methane rain",
    coreParadoxHook:
      "Liquid methane raindrops the size of strawberries fall 6x slower than Earth rain—until you feel the -179°C air.",
    whyItFitsChannelVi:
      "Phiên bản nâng cấp vật lý cảm giác thật của bài 'Jump on Other Worlds' (Top 2 views của kênh).",
    suggestedDurationSec: 70,
  },
  {
    title: "The Underground Reactor That Burned for 300,000 Years Before Humans Existed",
    targetKeyword: "oklo natural nuclear reactor",
    coreParadoxHook:
      "Physicists thought uranium ore had been stolen—until they realized groundwater built a self-regulating reactor 2 billion years ago.",
    whyItFitsChannelVi:
      "Nghịch lý địa chất có thật 100% kèm số liệu DOI cực mạnh, kích thích bình luận tranh luận.",
    suggestedDurationSec: 82,
  },
  {
    title: "Why Sound Travels Backwards Inside the Ocean's SOFAR Channel",
    targetKeyword: "sofar channel ocean",
    coreParadoxHook:
      "1,000 meters underwater, pressure and temperature trap sound waves so a whale song crosses an entire ocean.",
    whyItFitsChannelVi:
      "Kết hợp đại dương sâu (Top 1 views của kênh) với cơ chế vật lý ít người biết.",
    suggestedDurationSec: 68,
  },
];

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();
    const activeChannel =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];

    if (body.action === "diagnoseChannel") {
      if (!activeChannel) {
        return Response.json({ diagnoses: [] });
      }
      const diagnoses = diagnoseExistingVideosForSubRescue(
        activeChannel.recentVideos,
        activeChannel.handle
      );
      return Response.json({ diagnoses });
    }

    if (body.action === "suggestFromWinners") {
      const geminiKey = getEffectiveGeminiKey(store);
      const handle = activeChannel?.handle || "@proofofwonderscience";
      const macEps = await listMacRenderedEpisodes(handle, {
        publishedRecords: store.publishedMacEpisodes,
        recentVideos: activeChannel?.recentVideos || [],
      }).catch(() => []);

      const existingTitles = [
        ...(activeChannel?.recentVideos || []).map(
          (v) => `${v.title} (${v.views} views)`
        ),
        ...macEps.map((m) => `${m.primaryTitle} [local Mac output]`),
        ...(store.ideas || []).map((i) => i.title),
      ];

      const { contextPrompt, winners } = await buildLiveRetentionTelemetry(store);
      const customFocus = String(body.focusHint || "").trim();

      if (!geminiKey) {
        return Response.json({
          ok: true,
          usedAi: false,
          modelUsed: "fallback",
          retentionWinners: winners,
          suggestions: FALLBACK_TOPICS,
        });
      }

      const prompt = `You are the Executive Producer of "${
        activeChannel?.title || "Proof of Wonder"
      }" (${handle}), a US English Science & Earth/Space Documentary Shorts channel (65–95s 9:16 documentaries, style: Veritasium + Fern + Cleo Abram, real NASA/NOAA/peer-reviewed DOI facts, zero sci-fi speculation).

EXISTING CHANNEL VIDEOS & BACKLOG (DO NOT REPEAT THESE EXACT TOPICS):
${existingTitles.slice(0, 20).join("\n") || "None yet"}

${contextPrompt || "COMPETITOR SIGNALS: Extreme geology, sealed places, planetary physics, counter-intuitive survival."}

${customFocus ? `CREATOR FOCUS REQUEST: "${customFocus}"` : ""}

Propose 5 NEW, high-retention Documentary Short topics engineered specifically from the high-retention winners & viral outliers above to push Stayed-to-Watch > 60% and Average Percentage Viewed > 100%.
Each idea MUST:
- Have a natural US English "title" (46–68 chars, zero #hashtags, strong curiosity gap + specific mechanism).
- Have a 2–4 word lowercase search "targetKeyword".
- Have a 1-sentence "coreParadoxHook" in English (the shocking 0–3s visual + spoken contradiction).
- Have "whyItFitsChannelVi" in VIETNAMESE (1 concise sentence citing which retention winner / viral pattern this emulates and why viewers won't swipe away).
- Have "suggestedDurationSec" between 65 and 95.

Return STRICT RAW JSON ONLY:
{
  "suggestions": [
    {
      "title": "...",
      "targetKeyword": "...",
      "coreParadoxHook": "...",
      "whyItFitsChannelVi": "...",
      "suggestedDurationSec": 75
    }
  ]
}`;

      const models = buildGeminiModelChain(
        typeof body.model === "string" && body.model.trim()
          ? body.model.trim()
          : store.settings.geminiModel
      );

      for (const model of models) {
        try {
          const res = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
              geminiKey
            )}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                contents: [{ parts: [{ text: prompt }] }],
                generationConfig: {
                  temperature: 0.75,
                  responseMimeType: "application/json",
                },
              }),
              cache: "no-store",
            }
          );
          if (!res.ok) continue;
          const json = await res.json();
          const parts: Array<{ text?: string; thought?: boolean }> =
            json?.candidates?.[0]?.content?.parts || [];
          const answerPart =
            parts.find((p) => !p.thought && p.text) || parts[parts.length - 1];
          const rawText = answerPart?.text;
          if (!rawText) continue;
          const parsed = JSON.parse(
            rawText
              .replace(/^```json\s*/i, "")
              .replace(/```\s*$/, "")
              .trim()
          ) as { suggestions?: AiSuggestedTopic[] };

          if (
            Array.isArray(parsed.suggestions) &&
            parsed.suggestions.length > 0
          ) {
            return Response.json({
              ok: true,
              usedAi: true,
              modelUsed: model,
              retentionWinners: winners,
              suggestions: parsed.suggestions.slice(0, 5),
            });
          }
        } catch {
          // try next model
        }
      }

      return Response.json({
        ok: true,
        usedAi: false,
        modelUsed: "fallback",
        retentionWinners: winners,
        suggestions: FALLBACK_TOPICS,
      });
    }

    const topic = String(body.topic || "").trim();
    if (!topic) {
      return Response.json(
        { error: "Vui lòng nhập chủ đề khoa học / ý tưởng video." },
        { status: 400 }
      );
    }

    const geminiKey = getEffectiveGeminiKey(store);
    const preferredModel =
      typeof body.model === "string" && body.model.trim()
        ? body.model.trim()
        : store.settings.geminiModel;
    const { contextPrompt, winners } = await buildLiveRetentionTelemetry(store);

    const result = await generateViralShortBlueprint({
      topic,
      sourceOutlierTitle: body.sourceOutlierTitle
        ? String(body.sourceOutlierTitle)
        : undefined,
      retentionTelemetryContext: contextPrompt,
      channelTitle: activeChannel?.title || "Proof of Wonder",
      channelHandle: activeChannel?.handle || "@proofofwonderscience",
      geminiApiKey: geminiKey,
      preferredModel,
    });

    return Response.json({
      ...result,
      retentionWinners: winners,
    });
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Không thể tạo kịch bản AI lúc này.";
    return Response.json({ error: message }, { status: 400 });
  }
}
