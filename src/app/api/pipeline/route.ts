import { connection } from "next/server";
import {
  buildDefaultDescription,
  buildDefaultTags,
  generateNextGrowthSprint,
} from "@/lib/auto-planner";
import { readStore, writeStore } from "@/lib/store";
import type { AutopilotLogEntry, GrowthPlanItem, StoreData } from "@/lib/types";

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

function formatEpisodePayload(item: GrowthPlanItem | undefined, handle: string) {
  if (!item) return null;
  const cleanHook = item.hook3s.replace(/^\.\.\.\s*/, "").trim();
  const fullNarration = `${cleanHook} ${item.voiceoverScript}`.trim();
  return {
    episodeId: item.id,
    dayLabel: item.dayLabel,
    scheduledDate: item.scheduledDate,
    vnPublishWindow: item.vnPublishWindow,
    strategyType: item.strategyType,
    title: item.title,
    hook3s: item.hook3s,
    voiceoverScript: item.voiceoverScript,
    fullNarration,
    description:
      item.description ||
      buildDefaultDescription(item.title, item.hook3s, handle),
    tags:
      item.tags && item.tags.length > 0
        ? item.tags
        : buildDefaultTags(item.title),
    pinnedComment: item.pinnedComment,
    status: item.status,
  };
}

export async function GET() {
  await connection();
  const store = await readStore();
  const activeCh =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];
  const handle = activeCh?.handle || "@proofofwonderscience";

  if (!store.activePlan && activeCh) {
    store.activePlan = await generateNextGrowthSprint(store, { fastMode: true });
    await writeStore(store);
  }

  const plan = store.activePlan;
  const nextItem = plan?.items.find((i) => i.status !== "completed");
  const completedSteps =
    plan?.items.filter((i) => i.status === "completed").length || 0;

  return Response.json({
    ok: true,
    channel: activeCh
      ? {
          id: activeCh.id,
          handle: activeCh.handle,
          title: activeCh.title,
          subscribers: activeCh.subscribers,
          totalViews: activeCh.totalViews,
          videoCount: activeCh.videoCount,
          targetMilestone: activeCh.targetMilestone,
        }
      : null,
    sprint: plan
      ? {
          sprintNumber: plan.sprintNumber,
          completedSteps,
          totalSteps: plan.items.length,
          bestPublishWindowVn: plan.bestPublishWindowVn,
          autoContinueEnabled: plan.autoContinueEnabled,
        }
      : null,
    nextEpisode: formatEpisodePayload(nextItem, handle),
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const store = await readStore();
    const activeCh =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];
    const handle = activeCh?.handle || "@proofofwonderscience";

    if (!store.activePlan) {
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
    }

    const action = body.action || "complete";

    if (action === "generateNextSprint") {
      store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
      pushLog(
        store,
        "plan",
        `Pipeline yêu cầu tạo mới Sprint #${store.activePlan.sprintNumber}.`
      );
      await writeStore(store);
      const nextItem = store.activePlan.items.find(
        (i) => i.status !== "completed"
      );
      return Response.json({
        ok: true,
        autoAdvanced: true,
        nextEpisode: formatEpisodePayload(nextItem, handle),
      });
    }

    const targetId = body.episodeId
      ? String(body.episodeId)
      : store.activePlan.items.find((i) => i.status !== "completed")?.id;

    const idx = store.activePlan.items.findIndex((i) => i.id === targetId);
    if (idx < 0) {
      return Response.json(
        { ok: false, error: "Không tìm thấy tập video cần cập nhật." },
        { status: 404 }
      );
    }

    if (action === "in_progress") {
      store.activePlan.items[idx].status = "in_progress";
      pushLog(
        store,
        "system",
        `Tool tạo video bắt đầu render tập: "${store.activePlan.items[idx].title}".`
      );
    } else {
      store.activePlan.items[idx].status = "completed";
      pushLog(
        store,
        "publish",
        `Pipeline xác nhận hoàn tất tập: "${store.activePlan.items[idx].title}".`
      );
    }

    let autoAdvanced = false;
    const allDone =
      store.activePlan.items.length > 0 &&
      store.activePlan.items.every((i) => i.status === "completed");

    if (allDone && store.activePlan.autoContinueEnabled) {
      store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
      autoAdvanced = true;
      pushLog(
        store,
        "plan",
        `🎉 Pipeline hoàn tất đủ 5/5 tập — Tự động sinh Sprint #${store.activePlan.sprintNumber} mới!`
      );
    }

    await writeStore(store);
    const nextItem = store.activePlan.items.find(
      (i) => i.status !== "completed"
    );

    return Response.json({
      ok: true,
      autoAdvanced,
      sprintNumber: store.activePlan.sprintNumber,
      nextEpisode: formatEpisodePayload(nextItem, handle),
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Lỗi xử lý API Pipeline.";
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
}
