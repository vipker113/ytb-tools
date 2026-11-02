import {
  buildDefaultDescription,
  buildDefaultTags,
  generateNextGrowthSprint,
} from "@/lib/auto-planner";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import type { AutopilotLogEntry, StoreData } from "@/lib/types";
import {
  fetchCompetitorChannelLive,
  fetchTrackedChannelLive,
} from "@/lib/youtube";
import { reconcileStudioState } from "@/lib/youtube-studio";

function pushLog(
  store: StoreData,
  type: AutopilotLogEntry["type"],
  message: string
) {
  const entry: AutopilotLogEntry = {
    id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
    timestamp: new Date().toISOString(),
    type,
    message,
  };
  store.autopilotLogs = [entry, ...(store.autopilotLogs || [])].slice(0, 25);
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const mode = body.mode === "force" ? "force" : "autoIfStale";
    const store = await readStore();

    if (mode === "autoIfStale" && store.autoSyncOnOpen === false) {
      return Response.json({ skipped: true, store });
    }

    const nowMs = Date.now();
    const lastSyncMs = store.lastAutopilotSyncAt
      ? new Date(store.lastAutopilotSyncAt).getTime()
      : 0;
    const isFresh = nowMs - lastSyncMs < 4 * 3600 * 1000;

    const hasCompleteMetadata = Boolean(
      store.activePlan &&
        store.activePlan.items.length > 0 &&
        store.activePlan.items.every(
          (i) => Boolean(i.description) && Array.isArray(i.tags) && i.tags.length > 0
        )
    );

    const hasPublishedEpisodes =
      Object.keys(store.publishedMacEpisodes || {}).length > 0;

    if (mode === "autoIfStale" && isFresh && hasCompleteMetadata) {
      // Even when full channel/competitor sync is fresh, do a 1-quota-unit Studio check
      // if > 2 min elapsed and we have Studio-linked episodes, so Studio deletions/edits show up!
      if (hasPublishedEpisodes && nowMs - lastSyncMs > 120_000) {
        const quickRec = await reconcileStudioState(store);
        if (
          quickRec.deletedSlugs.length > 0 ||
          quickRec.updatedSlugs.length > 0 ||
          quickRec.deletedRecentCount > 0
        ) {
          store.lastAutopilotSyncAt = new Date().toISOString();
          if (quickRec.summaryMessage) {
            pushLog(store, "sync", quickRec.summaryMessage);
          }
          await writeStore(store);
          return Response.json({
            skipped: false,
            store,
            reconcile: quickRec,
            message:
              quickRec.summaryMessage ||
              "Đã đồng bộ trạng thái video mới nhất từ YouTube Studio!",
          });
        }
      }
      return Response.json({ skipped: true, store });
    }

    const apiKey = getEffectiveYoutubeKey(store);
    let syncedYoutube = false;
    let syncedCompetitors = false;

    if (apiKey) {
      const updatedMy = [];
      for (const ch of store.myChannels) {
        if (ch.isDemo) {
          updatedMy.push(ch);
          continue;
        }
        try {
          const refreshed = await fetchTrackedChannelLive({
            query: ch.id,
            apiKey,
            niche: ch.niche,
            existingSnapshots: ch.snapshots,
            existingMilestone: ch.targetMilestone,
          });
          updatedMy.push(refreshed);
          syncedYoutube = true;
        } catch {
          updatedMy.push(ch);
        }
      }
      store.myChannels = updatedMy;

      const updatedComp = [];
      for (const comp of store.competitors) {
        if (comp.isDemo) {
          updatedComp.push(comp);
          continue;
        }
        const compLastMs = comp.lastSyncedAt
          ? new Date(comp.lastSyncedAt).getTime()
          : 0;
        const compStale = nowMs - compLastMs > 12 * 3600 * 1000;
        if (mode === "force" || compStale) {
          try {
            const refreshed = await fetchCompetitorChannelLive({
              query: comp.id,
              apiKey,
              niche: comp.niche,
            });
            updatedComp.push(refreshed);
            syncedCompetitors = true;
          } catch {
            updatedComp.push(comp);
          }
        } else {
          updatedComp.push(comp);
        }
      }
      store.competitors = updatedComp;
    }

    // Reconcile Studio deletions & live metadata edits (0s CDN lag via OAuth videos.list!)
    // Running AFTER fetchTrackedChannelLive ensures any 2-minute YouTube CDN lag on deleted/edited
    // videos is immediately corrected by live Studio state!
    const reconcileResult = await reconcileStudioState(store);

    const activeCh =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];
    const handle = activeCh?.handle || "@proofofwonderscience";

    let statusMessage =
      reconcileResult.summaryMessage ||
      "Đã đồng bộ dữ liệu kênh & trạng thái YouTube Studio mới nhất!";

    // Backfill description & tags on any existing plan items
    if (store.activePlan) {
      for (const item of store.activePlan.items) {
        if (!item.description) {
          item.description = buildDefaultDescription(
            item.title,
            item.hook3s,
            handle
          );
        }
        if (!item.tags || item.tags.length === 0) {
          item.tags = buildDefaultTags(item.title);
        }
      }
    }

    if (!store.activePlan && activeCh) {
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
      statusMessage = `Autopilot đã tự động lập Kế hoạch Sprint #${store.activePlan.sprintNumber} (5 tập Shorts)!`;
      pushLog(store, "plan", statusMessage);
    } else if (store.activePlan && activeCh) {
      const newUploads = Math.max(
        0,
        activeCh.videoCount - store.activePlan.basedOnVideoCount
      );
      if (newUploads > 0 && store.activePlan.autoContinueEnabled) {
        let remaining = newUploads;
        const autoCompletedTitles: string[] = [];
        for (const item of store.activePlan.items) {
          if (item.status !== "completed" && remaining > 0) {
            item.status = "completed";
            autoCompletedTitles.push(item.title);
            remaining--;
          }
        }
        store.activePlan.basedOnVideoCount = activeCh.videoCount;
        if (autoCompletedTitles.length > 0) {
          pushLog(
            store,
            "publish",
            `Phát hiện ${newUploads} video mới trên kênh YouTube — Tự động gạch hoàn thành ${autoCompletedTitles.length} bước trong Sprint #${store.activePlan.sprintNumber}!`
          );
        }
      }

      const allCompleted =
        store.activePlan.items.length > 0 &&
        store.activePlan.items.every((i) => i.status === "completed");

      if (allCompleted && store.activePlan.autoContinueEnabled) {
        store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
        store.activePlan = await generateNextGrowthSprint(store, {
          fastMode: true,
        });
        statusMessage = `🎉 Hoàn thành đủ 5/5 tập cũ — Autopilot đã tự động lập Sprint #${store.activePlan.sprintNumber} tiếp theo!`;
        pushLog(store, "plan", statusMessage);
      }
    }

    store.lastAutopilotSyncAt = new Date().toISOString();

    if (reconcileResult.summaryMessage) {
      pushLog(store, "sync", reconcileResult.summaryMessage);
    }

    if (syncedYoutube && activeCh) {
      pushLog(
        store,
        "sync",
        `Đồng bộ YouTube (${activeCh.handle}: ${activeCh.subscribers} subs • ${activeCh.totalViews.toLocaleString(
          "vi-VN"
        )} views • ${activeCh.videoCount} videos)${
          syncedCompetitors ? ` + quét mới ${store.competitors.length} kênh đối thủ` : ""
        }.`
      );
    } else if (!syncedYoutube && !reconcileResult.summaryMessage) {
      pushLog(
        store,
        "system",
        "Đã chuẩn hóa dữ liệu Metadata 1-Click cho hàng đợi vận hành hằng ngày."
      );
    }

    await writeStore(store);
    return Response.json({
      skipped: false,
      store,
      reconcile: reconcileResult,
      message: statusMessage,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Lỗi khi chạy Autopilot.";
    return Response.json({ error: message }, { status: 500 });
  }
}
