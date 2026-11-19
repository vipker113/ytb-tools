import fs from "node:fs";
import path from "node:path";
import type { NextRequest } from "next/server";
import {
  ensureKiChallengeAutoDaemon,
  fetchAuthenticatedChannelSubscriberCount,
  type KiChallengeTrackerItem,
  type KiPointWeights,
  parseYoutubeVideoId,
  publishKiVideoAndStartTracking,
  readKiChallengesAsync,
  renderIdleKiVideoAndThumbnail,
  saveCustomAudioFile,
  saveCustomStageArtwork,
  syncSingleKiChallenge,
  writeKiChallengesAsync,
} from "@/lib/ki-challenge-server";
import { readStore } from "@/lib/store";
import { getValidYoutubeAccessToken } from "@/lib/youtube-studio";

export async function GET() {
  try {
    ensureKiChallengeAutoDaemon();
    const items = await readKiChallengesAsync();

    const customDir = path.resolve(process.cwd(), "public/ki-challenge/custom");
    let customAssets: {
      name: string;
      url: string;
      silhouetteUrl?: string;
      isVideo: boolean;
    }[] = [];
    if (fs.existsSync(customDir)) {
      const allFiles = fs.readdirSync(customDir);
      const fileSet = new Set(allFiles);
      customAssets = allFiles
        .filter(
          (f) =>
            /\.(png|jpg|jpeg|webp|mp4|webm|mov)$/i.test(f) &&
            !f.endsWith("_sil.jpg")
        )
        .map((f) => {
          const baseNoExt = f.replace(/\.[^/.]+$/, "");
          const silCandidate = `${baseNoExt}_sil.jpg`;
          return {
            name: f,
            url: `/ki-challenge/custom/${f}`,
            silhouetteUrl: fileSet.has(silCandidate)
              ? `/ki-challenge/custom/${silCandidate}`
              : undefined,
            isVideo: /\.(mp4|webm|mov)$/i.test(f),
          };
        });
    }

    const customAudioDir = path.resolve(
      process.cwd(),
      "public/ki-challenge/custom-audio"
    );
    let customAudios: { name: string; url: string }[] = [];
    if (fs.existsSync(customAudioDir)) {
      customAudios = fs
        .readdirSync(customAudioDir)
        .filter((f) => /\.(mp3|m4a|wav|aac|ogg|flac)$/i.test(f))
        .map((f) => ({
          name: f,
          url: `/ki-challenge/custom-audio/${f}`,
        }));
    }

    return Response.json({
      ok: true,
      items,
      customAssets,
      customAudios,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi tải danh sách KI Challenge",
      },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    ensureKiChallengeAutoDaemon();
    const body = await request.json();
    const action = String(body.action || "");

    // 1. Render 1920x1080 Character Idle Video (.mp4) + 16:9 Thumbnail (.jpg)
    if (action === "renderIdleVideo") {
      const res = await renderIdleKiVideoAndThumbnail({
        sessionId: body.sessionId ? String(body.sessionId) : undefined,
        uiOverlayPngDataUrl: String(body.uiOverlayPngDataUrl || ""),
        thumbJpgDataUrl: String(body.thumbJpgDataUrl || ""),
        currentMediaUrl: String(body.currentMediaUrl || ""),
        nextMediaUrl: String(body.nextMediaUrl || ""),
        leftBox: String(body.leftBox || "0,0,960,1080"),
        rightBox: String(body.rightBox || "960,0,960,1080"),
        currentAuraHex: String(body.currentAuraHex || "#38bdf8"),
        nextAuraHex: String(body.nextAuraHex || "#facc15"),
        mysteryNext: Boolean(body.mysteryNext),
        lightning: Boolean(body.lightning),
        durationSec: Number(body.durationSec || 15),
        audioMode:
          body.audioMode === "custom_audio"
            ? "custom_audio"
            : body.audioMode === "builtin_bgm"
            ? "builtin_bgm"
            : body.audioMode === "silent"
            ? "silent"
            : "epic_hum",
        bgmTrack: body.bgmTrack ? String(body.bgmTrack) : undefined,
        customAudioUrl: body.customAudioUrl
          ? String(body.customAudioUrl)
          : undefined,
        audioStartSec: Number(body.audioStartSec || 0),
        audioEndSec: Number(body.audioEndSec || 0),
      });

      return Response.json({
        ok: true,
        ...res,
      });
    }

    // 1B. Upload custom MP3/audio source for trimming & mixing into Idle Video
    if (action === "uploadCustomAudio") {
      const saved = saveCustomAudioFile({
        fileName: String(body.fileName || "track.mp3"),
        dataUrl: String(body.dataUrl || ""),
      });
      return Response.json({
        ok: true,
        ...saved,
      });
    }

    // 2. Upload custom AI character image or idle video loop
    if (action === "uploadCustomMedia") {
      const saved = saveCustomStageArtwork({
        fileName: String(body.fileName || "character.png"),
        dataUrl: String(body.dataUrl || ""),
      });
      return Response.json({
        ok: true,
        ...saved,
      });
    }

    // 3. One-click Publish to YouTube Studio + Start Real-Time KI Title Tracking
    if (action === "publishAndTrack") {
      const weights: KiPointWeights = {
        view: Number(body.weights?.view ?? 1),
        like: Number(body.weights?.like ?? 20),
        comment: Number(body.weights?.comment ?? 50),
        sub: Number(body.weights?.sub ?? 200),
      };

      const created = await publishKiVideoAndStartTracking({
        sessionId: String(body.sessionId || ""),
        videoFile: String(body.videoFile || ""),
        thumbFile: String(body.thumbFile || ""),
        privacyStatus:
          body.privacyStatus === "unlisted"
            ? "unlisted"
            : body.privacyStatus === "private"
            ? "private"
            : "public",
        characterName: String(body.characterName || "Goku"),
        episodeNumber: Number(body.episodeNumber || 1),
        currentStageId: String(body.currentStageId || "stage_1"),
        currentStageLabel: String(body.currentStageLabel || "Base Form"),
        currentStageMediaUrl: body.currentStageMediaUrl
          ? String(body.currentStageMediaUrl)
          : undefined,
        currentAuraHex: body.currentAuraHex ? String(body.currentAuraHex) : "#38bdf8",
        nextStageId: String(body.nextStageId || "stage_2"),
        nextStageLabel: String(body.nextStageLabel || "03. Super Saiyan"),
        nextStageMediaUrl: body.nextStageMediaUrl
          ? String(body.nextStageMediaUrl)
          : undefined,
        nextAuraHex: body.nextAuraHex ? String(body.nextAuraHex) : "#facc15",
        mysteryNext: body.mysteryNext !== false,
        targetKi: Math.max(10, Number(body.targetKi || 10000)),
        weights,
        titleTemplate: String(
          body.titleTemplate ||
            "⚡ [{ki}/{target} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
        ),
        goalReachedTitleTemplate: String(
          body.goalReachedTitleTemplate ||
            "🎉 [{ki}/{target} KI — COMPLETE!] {char} Unlocked {nextForm} — New Video Up! ⚡"
        ),
        description: String(body.description || ""),
        tags: Array.isArray(body.tags) ? body.tags.map(String) : [],
        pinnedComment: String(body.pinnedComment || ""),
        syncIntervalMin: Math.max(2, Number(body.syncIntervalMin || 5)),
      });

      return Response.json({
        ok: true,
        item: created,
        items: await readKiChallengesAsync(),
      });
    }

    // 4. Attach an already-uploaded YouTube Video URL / ID to Real-Time KI Title Tracker
    if (action === "attachExistingVideo") {
      const vid = parseYoutubeVideoId(String(body.videoUrlOrId || ""));
      if (!vid) {
        return Response.json(
          {
            ok: false,
            error: "Link hoặc Video ID YouTube không hợp lệ. Hãy dán link youtube.com/watch?v=... hoặc mã 11 ký tự.",
          },
          { status: 400 }
        );
      }

      let baselineSubs = Number(body.baselineSubscribers || 0);
      if (baselineSubs <= 0) {
        try {
          const store = await readStore();
          const token = await getValidYoutubeAccessToken(store);
          baselineSubs = await fetchAuthenticatedChannelSubscriberCount(token);
        } catch {
          baselineSubs = 0;
        }
      }

      const weights: KiPointWeights = {
        view: Number(body.weights?.view ?? 1),
        like: Number(body.weights?.like ?? 20),
        comment: Number(body.weights?.comment ?? 50),
        sub: Number(body.weights?.sub ?? 200),
      };

      const nowIso = new Date().toISOString();
      const newItem: KiChallengeTrackerItem = {
        id: `kich_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        videoId: vid,
        characterName: String(body.characterName || "Goku"),
        episodeNumber: Number(body.episodeNumber || 1),
        currentStageId: String(body.currentStageId || "stage_02_adult_base"),
        currentStageLabel: String(body.currentStageLabel || "02. Adult Goku (Base)"),
        currentStageMediaUrl: body.currentStageMediaUrl
          ? String(body.currentStageMediaUrl)
          : "/ki-challenge/goku/stage_02_adult_base.jpg",
        currentAuraHex: body.currentAuraHex ? String(body.currentAuraHex) : "#38bdf8",
        nextStageId: String(body.nextStageId || "stage_03_ssj1"),
        nextStageLabel: String(body.nextStageLabel || "03. Super Saiyan"),
        nextStageMediaUrl: body.nextStageMediaUrl
          ? String(body.nextStageMediaUrl)
          : "/ki-challenge/goku/stage_03_ssj1.jpg",
        nextAuraHex: body.nextAuraHex ? String(body.nextAuraHex) : "#facc15",
        mysteryNext: body.mysteryNext !== false,
        targetKi: Math.max(10, Number(body.targetKi || 10000)),
        weights,
        baselineSubscribers: baselineSubs,
        manualBonusSubs: 0,
        titleTemplate: String(
          body.titleTemplate ||
            "⚡ [{ki}/{target} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
        ),
        goalReachedTitleTemplate: String(
          body.goalReachedTitleTemplate ||
            "🎉 [{ki}/{target} KI — COMPLETE!] {char} Unlocked {nextForm} — New Video Up! ⚡"
        ),
        autoSyncEnabled: true,
        syncIntervalMin: Math.max(2, Number(body.syncIntervalMin || 5)),
        currentKi: 0,
        lastSyncedMilestone: 0,
        watchUrl: `https://www.youtube.com/watch?v=${vid}`,
        studioEditUrl: `https://studio.youtube.com/video/${vid}/edit`,
        createdAt: nowIso,
      };

      const items = await readKiChallengesAsync();
      items.unshift(newItem);
      await writeKiChallengesAsync(items);

      // Perform immediate first sync & push title to YouTube!
      let synced = newItem;
      try {
        synced = await syncSingleKiChallenge(newItem.id, { forceUpdateTitle: true });
      } catch {
        // Keep item registered even if OAuth needs re-login; error is saved on item.lastError
        synced =
          (await readKiChallengesAsync()).find((x) => x.id === newItem.id) ||
          newItem;
      }

      return Response.json({
        ok: true,
        item: synced,
        items: await readKiChallengesAsync(),
      });
    }

    // 5. Sync a tracked video right now
    if (action === "syncNow") {
      const id = String(body.id || "");
      const updated = await syncSingleKiChallenge(id, {
        forceUpdateTitle: Boolean(body.forceUpdateTitle),
      });
      return Response.json({
        ok: true,
        item: updated,
        items: await readKiChallengesAsync(),
      });
    }

    // 6. Update tracker configuration (toggle autoSync, adjust bonusSubs, interval, templates, etc.)
    if (action === "updateTrackerSettings") {
      const id = String(body.id || "");
      const patch = (body.patch || {}) as Record<string, unknown>;
      const items = await readKiChallengesAsync();
      const idx = items.findIndex((x) => x.id === id);
      if (idx === -1) {
        return Response.json({ ok: false, error: "Không tìm thấy video đang theo dõi." }, { status: 404 });
      }

      const cur = { ...items[idx] };
      if (typeof patch.autoSyncEnabled === "boolean") {
        cur.autoSyncEnabled = patch.autoSyncEnabled;
      }
      if (typeof patch.syncIntervalMin === "number") {
        cur.syncIntervalMin = Math.max(2, Math.min(60, Math.round(patch.syncIntervalMin)));
      }
      if (typeof patch.targetKi === "number") {
        cur.targetKi = Math.max(10, Math.round(patch.targetKi));
      }
      if (typeof patch.manualBonusSubs === "number") {
        cur.manualBonusSubs = Math.round(patch.manualBonusSubs);
      }
      if (typeof patch.baselineSubscribers === "number") {
        cur.baselineSubscribers = Math.max(0, Math.round(patch.baselineSubscribers));
      }
      if (typeof patch.titleTemplate === "string" && patch.titleTemplate.trim()) {
        cur.titleTemplate = patch.titleTemplate.trim();
      }
      if (typeof patch.goalReachedTitleTemplate === "string") {
        cur.goalReachedTitleTemplate = patch.goalReachedTitleTemplate.trim();
      }
      if (patch.weights && typeof patch.weights === "object") {
        const w = patch.weights as Record<string, unknown>;
        cur.weights = {
          view: Number(w.view ?? cur.weights.view),
          like: Number(w.like ?? cur.weights.like),
          comment: Number(w.comment ?? cur.weights.comment),
          sub: Number(w.sub ?? cur.weights.sub),
        };
      }

      items[idx] = cur;
      await writeKiChallengesAsync(items);
      return Response.json({ ok: true, item: cur, items });
    }

    // 7. Remove tracker
    if (action === "deleteTracker") {
      const id = String(body.id || "");
      const items = (await readKiChallengesAsync()).filter((x) => x.id !== id);
      await writeKiChallengesAsync(items);
      return Response.json({ ok: true, items });
    }

    return Response.json({ ok: false, error: `Unknown action: ${action}` }, { status: 400 });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error: err instanceof Error ? err.message : "Lỗi xử lý KI Challenge",
      },
      { status: 500 }
    );
  }
}
