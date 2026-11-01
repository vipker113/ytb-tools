import { generateNextGrowthSprint } from "@/lib/auto-planner";
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

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();

    if (body.action === "toggleAutoContinue") {
      if (store.activePlan) {
        store.activePlan.autoContinueEnabled = Boolean(body.enabled);
        await writeStore(store);
      }
      return Response.json({ store });
    }

    if (body.action === "updateStepStatus" && store.activePlan) {
      const idx = store.activePlan.items.findIndex(
        (i) => i.id === body.itemId
      );
      let completedTitle = "";
      if (idx >= 0) {
        store.activePlan.items[idx].status = body.status as GrowthPlanItem["status"];
        completedTitle = store.activePlan.items[idx].title;
      }

      if (body.status === "completed" && completedTitle) {
        pushLog(
          store,
          "publish",
          `Đã đánh dấu hoàn thành bài đăng: "${completedTitle}".`
        );
      }

      const allDone =
        store.activePlan.items.length > 0 &&
        store.activePlan.items.every((i) => i.status === "completed");

      if (allDone && store.activePlan.autoContinueEnabled) {
        store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
        store.activePlan = await generateNextGrowthSprint(store, {
          fastMode: Boolean(body.fastMode),
        });
        pushLog(
          store,
          "plan",
          `🎉 Hoàn thành 5/5 bài Sprint cũ — Tự động lập mới Sprint #${store.activePlan.sprintNumber} (Mục tiêu ${store.activePlan.targetSubscribersGoal} Subs).`
        );
        await writeStore(store);
        return Response.json({
          store,
          autoAdvanced: true,
          message: `🎉 Hoàn tất Sprint cũ! Hệ thống đã TỰ ĐỘNG lập Kế hoạch Sprint #${store.activePlan.sprintNumber} tiếp theo!`,
        });
      }

      await writeStore(store);
      return Response.json({ store, autoAdvanced: false });
    }

    if (body.incrementSprint) {
      store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
    }
    store.activePlan = await generateNextGrowthSprint(store, {
      fastMode: Boolean(body.fastMode),
    });
    pushLog(
      store,
      "plan",
      `Đã tạo mới Kế hoạch Sprint #${store.activePlan.sprintNumber} gồm ${store.activePlan.items.length} tập Shorts.`
    );
    await writeStore(store);

    return Response.json({
      store,
      autoAdvanced: true,
      message: `Đã lập Kế hoạch Tăng trưởng Tự động (Sprint #${store.activePlan.sprintNumber})!`,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Không thể tạo kế hoạch tự động.";
    return Response.json({ error: message }, { status: 500 });
  }
}
