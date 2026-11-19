import type { NextRequest } from "next/server";
import {
  computeReachedKiMilestone,
  ensureKiChallengeAutoDaemon,
  readKiChallengesAsync,
} from "@/lib/ki-challenge-server";

export async function GET(request: NextRequest) {
  ensureKiChallengeAutoDaemon();
  const videoIdFilter = (request.nextUrl.searchParams.get("v") || "").trim();
  const all = await readKiChallengesAsync();

  const filtered = videoIdFilter
    ? all.filter((it) => it.videoId === videoIdFilter || it.id === videoIdFilter)
    : all;

  const publicItems = filtered.map((it) => {
    const pctExact = Math.min(
      100,
      Math.round((it.currentKi / Math.max(1, it.targetKi)) * 1000) / 10
    );
    const reachedMilestone = computeReachedKiMilestone(it.currentKi, it.targetKi);
    const nextCheckpoint =
      reachedMilestone < 25
        ? 25
        : reachedMilestone < 50
        ? 50
        : reachedMilestone < 75
        ? 75
        : 100;

    return {
      id: it.id,
      videoId: it.videoId,
      characterName: it.characterName,
      episodeNumber: it.episodeNumber,
      currentStageLabel: it.currentStageLabel,
      currentStageMediaUrl:
        it.currentStageMediaUrl || "/ki-challenge/goku/stage_1_base.jpg",
      currentAuraHex: it.currentAuraHex || "#38bdf8",
      nextStageLabel: it.nextStageLabel,
      nextStageMediaUrl:
        it.nextStageMediaUrl || "/ki-challenge/goku/stage_2_kaioken.jpg",
      nextAuraHex: it.nextAuraHex || "#facc15",
      currentKi: it.currentKi,
      targetKi: it.targetKi,
      pctExact,
      reachedMilestone,
      lastSyncedMilestone: it.lastSyncedMilestone ?? 0,
      nextCheckpoint,
      weights: it.weights,
      stats: {
        views: it.lastStats?.views || 0,
        likes: it.lastStats?.likes || 0,
        comments: it.lastStats?.comments || 0,
        gainedSubs: it.lastStats?.gainedSubs || 0,
      },
      syncIntervalMin: it.syncIntervalMin || 5,
      lastCheckedAt: it.lastCheckedAt || null,
      watchUrl: it.watchUrl,
    };
  });

  return Response.json(
    {
      ok: true,
      serverTime: new Date().toISOString(),
      items: publicItems,
    },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    }
  );
}
