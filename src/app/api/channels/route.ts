import { generateNextGrowthSprint } from "@/lib/auto-planner";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import {
  fetchCompetitorChannelLive,
  fetchTrackedChannelLive,
} from "@/lib/youtube";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();
    const apiKey = getEffectiveYoutubeKey(store);

    if (!apiKey) {
      return Response.json(
        {
          error:
            "Chưa cấu hình YouTube Data API v3 Key. Hãy vào mục 'Quản lý Kênh & API' để dán khóa miễn phí từ Google Cloud.",
        },
        { status: 400 }
      );
    }

    if (body.syncAll) {
      const updatedMy = [];
      for (const ch of store.myChannels) {
        if (ch.isDemo) {
          updatedMy.push(ch);
          continue;
        }
        const refreshed = await fetchTrackedChannelLive({
          query: ch.id,
          apiKey,
          niche: ch.niche,
          existingSnapshots: ch.snapshots,
          existingMilestone: ch.targetMilestone,
        });
        updatedMy.push(refreshed);
      }

      const updatedComp = [];
      for (const comp of store.competitors) {
        if (comp.isDemo) {
          updatedComp.push(comp);
          continue;
        }
        const refreshed = await fetchCompetitorChannelLive({
          query: comp.id,
          apiKey,
          niche: comp.niche,
        });
        updatedComp.push(refreshed);
      }

      store.myChannels = updatedMy;
      store.competitors = updatedComp;

      // Closed-loop Autopilot: auto-advance or initialize plan after sync
      const activeCh =
        store.myChannels.find((c) => c.id === store.activeChannelId) ||
        store.myChannels[0];
      let planMessage = "Đã đồng bộ dữ liệu mới nhất từ YouTube!";

      if (!store.activePlan && activeCh) {
        store.activePlan = await generateNextGrowthSprint(store);
        planMessage = `Đã đồng bộ YouTube & tự động khởi tạo Kế hoạch Sprint #${store.activePlan.sprintNumber}!`;
      } else if (
        store.activePlan &&
        activeCh &&
        store.activePlan.autoContinueEnabled
      ) {
        const newUploads = Math.max(
          0,
          activeCh.videoCount - store.activePlan.basedOnVideoCount
        );
        if (newUploads > 0) {
          let remainingToMark = newUploads;
          for (const item of store.activePlan.items) {
            if (item.status !== "completed" && remainingToMark > 0) {
              item.status = "completed";
              remainingToMark--;
            }
          }
          store.activePlan.basedOnVideoCount = activeCh.videoCount;
        }

        const allCompleted =
          store.activePlan.items.length > 0 &&
          store.activePlan.items.every((i) => i.status === "completed");

        if (allCompleted) {
          store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
          store.activePlan = await generateNextGrowthSprint(store);
          planMessage = `🎉 Phát hiện hoàn thành lộ trình cũ — Đã TỰ ĐỘNG lập Kế hoạch Sprint #${store.activePlan.sprintNumber} tiếp theo!`;
        }
      }

      await writeStore(store);
      return Response.json({ store, message: planMessage });
    }

    const query = String(body.query || "").trim();
    const niche = String(body.niche || "").trim();
    const mode = body.mode === "competitor" ? "competitor" : "myChannel";

    if (!query) {
      return Response.json(
        { error: "Vui lòng nhập @handle, URL kênh hoặc Channel ID." },
        { status: 400 }
      );
    }

    if (mode === "myChannel") {
      const existing = store.myChannels.find(
        (c) =>
          c.id === query ||
          c.handle.toLowerCase() === query.toLowerCase()
      );
      const liveChannel = await fetchTrackedChannelLive({
        query,
        apiKey,
        niche: niche || existing?.niche || "Sáng tạo nội dung",
        existingSnapshots: existing?.snapshots,
        existingMilestone: existing?.targetMilestone,
      });

      const idx = store.myChannels.findIndex((c) => c.id === liveChannel.id);
      if (idx >= 0) {
        liveChannel.snapshots = [
          ...store.myChannels[idx].snapshots.filter(
            (s) => !liveChannel.snapshots.some((ns) => ns.date === s.date)
          ),
          ...liveChannel.snapshots,
        ].sort((a, b) => a.date.localeCompare(b.date));
        store.myChannels[idx] = liveChannel;
      } else {
        store.myChannels = [liveChannel, ...store.myChannels];
      }
      store.activeChannelId = liveChannel.id;
    } else {
      const liveComp = await fetchCompetitorChannelLive({
        query,
        apiKey,
        niche: niche || "Đối thủ cùng ngách",
      });
      const idx = store.competitors.findIndex((c) => c.id === liveComp.id);
      if (idx >= 0) {
        store.competitors[idx] = liveComp;
      } else {
        store.competitors = [liveComp, ...store.competitors];
      }
    }

    await writeStore(store);
    return Response.json({ store });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Đã xảy ra lỗi khi tải dữ liệu từ YouTube.";
    return Response.json({ error: message }, { status: 500 });
  }
}
