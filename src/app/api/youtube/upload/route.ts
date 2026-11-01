import {
  buildDefaultDescription,
  buildDefaultTags,
  generateNextGrowthSprint,
} from "@/lib/auto-planner";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import { fetchTrackedChannelLive } from "@/lib/youtube";
import {
  getValidYoutubeAccessToken,
  uploadShortVideoToStudio,
} from "@/lib/youtube-studio";

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file");

    if (!file || !(file instanceof File)) {
      return Response.json(
        { error: "Vui lòng chọn file video (.mp4 / .mov) cần đăng lên YouTube." },
        { status: 400 }
      );
    }

    const store = await readStore();
    const accessToken = await getValidYoutubeAccessToken(store);

    const activeCh =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];
    const handle = activeCh?.handle || "@proofofwonderscience";
    const ownerChannelId =
      store.youtubeOAuth?.connectedChannelId || activeCh?.id;

    if (!store.activePlan && activeCh) {
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
    }

    const episodeIdParam = String(formData.get("episodeId") || "").trim();
    const targetEpisode = episodeIdParam
      ? store.activePlan?.items.find((i) => i.id === episodeIdParam)
      : store.activePlan?.items.find((i) => i.status !== "completed");

    const title =
      String(formData.get("title") || "").trim() ||
      targetEpisode?.title ||
      file.name.replace(/\.[^.]+$/, "");

    const description =
      String(formData.get("description") || "").trim() ||
      targetEpisode?.description ||
      buildDefaultDescription(title, targetEpisode?.hook3s || "", handle);

    const rawTagsStr = String(formData.get("tags") || "").trim();
    const tags = rawTagsStr
      ? rawTagsStr
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      : targetEpisode?.tags && targetEpisode.tags.length > 0
      ? targetEpisode.tags
      : buildDefaultTags(title);

    const pinnedComment =
      String(formData.get("pinnedComment") || "").trim() ||
      targetEpisode?.pinnedComment ||
      "";

    const publishModeRaw = String(
      formData.get("publishMode") || "schedule_golden"
    );
    const publishMode =
      publishModeRaw === "public_now" || publishModeRaw === "private_draft"
        ? publishModeRaw
        : "schedule_golden";

    const videoBuffer = await file.arrayBuffer();

    const uploadResult = await uploadShortVideoToStudio({
      accessToken,
      ownerChannelId,
      videoBuffer,
      mimeType: file.type || "video/mp4",
      title,
      description,
      tags,
      pinnedComment,
      publishMode,
    });

    // Advance Sprint step automatically!
    let autoAdvancedSprint = false;
    if (targetEpisode && store.activePlan) {
      const idx = store.activePlan.items.findIndex(
        (i) => i.id === targetEpisode.id
      );
      if (idx >= 0) {
        store.activePlan.items[idx].status = "completed";
      }
      store.activePlan.basedOnVideoCount =
        (store.activePlan.basedOnVideoCount || activeCh?.videoCount || 0) + 1;

      const allDone =
        store.activePlan.items.length > 0 &&
        store.activePlan.items.every((i) => i.status === "completed");
      if (allDone && store.activePlan.autoContinueEnabled) {
        store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
        store.activePlan = await generateNextGrowthSprint(store, {
          fastMode: true,
        });
        autoAdvancedSprint = true;
      }
    }

    // Refresh live channel data if possible
    const ytKey = getEffectiveYoutubeKey(store);
    if (ytKey && activeCh && !activeCh.isDemo) {
      try {
        const refreshed = await fetchTrackedChannelLive({
          query: activeCh.id,
          apiKey: ytKey,
          niche: activeCh.niche,
          existingSnapshots: activeCh.snapshots,
          existingMilestone: activeCh.targetMilestone,
        });
        const cIdx = store.myChannels.findIndex((c) => c.id === activeCh.id);
        if (cIdx >= 0) store.myChannels[cIdx] = refreshed;
      } catch {
        // ignore
      }
    }

    const scheduleLabel = uploadResult.scheduledAt
      ? `Hẹn giờ tự phát sóng lúc ${new Date(
          uploadResult.scheduledAt
        ).toLocaleString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          day: "2-digit",
          month: "2-digit",
        })}`
      : publishMode === "public_now"
      ? "Đã đăng Công khai ngay"
      : "Lưu bản nháp Riêng tư";

    const logMessage = `🎬 Upload thành công video "${title}" thẳng lên YouTube Studio (${scheduleLabel})!${
      autoAdvancedSprint
        ? ` 🎉 Đã xong 5/5 bài và tự lập Sprint #${store.activePlan?.sprintNumber}!`
        : ""
    }`;

    store.autopilotLogs = [
      {
        id: `log-${Date.now()}`,
        timestamp: new Date().toISOString(),
        type: "publish" as const,
        message: logMessage,
      },
      ...(store.autopilotLogs || []),
    ].slice(0, 25);

    await writeStore(store);

    return Response.json({
      ok: true,
      store,
      uploadResult,
      autoAdvancedSprint,
      message: logMessage,
    });
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Lỗi khi upload video trực tiếp lên YouTube Studio.";
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
}
