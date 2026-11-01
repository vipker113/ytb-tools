import { readFile } from "node:fs/promises";
import {
  buildDefaultDescription,
  buildDefaultTags,
  generateNextGrowthSprint,
} from "@/lib/auto-planner";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import {
  generateCompleteShortMp4,
  getGeneratedVideoPath,
} from "@/lib/video-generator";
import { fetchTrackedChannelLive } from "@/lib/youtube";
import {
  getValidYoutubeAccessToken,
  uploadShortVideoToStudio,
} from "@/lib/youtube-studio";

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const store = await readStore();

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

    const episodeIdParam = String(body.episodeId || "").trim();
    const targetIdx = store.activePlan
      ? episodeIdParam
        ? store.activePlan.items.findIndex((i) => i.id === episodeIdParam)
        : store.activePlan.items.findIndex((i) => i.status !== "completed")
      : -1;
    const targetEpisode =
      targetIdx >= 0 && store.activePlan
        ? store.activePlan.items[targetIdx]
        : undefined;

    // MODE A: Publish an ALREADY generated server-side MP4 directly to YouTube Studio!
    if (body.action === "publishGenerated") {
      const fileName = String(
        body.videoFileName || targetEpisode?.generatedVideoFileName || ""
      ).trim();
      if (!fileName) {
        return Response.json(
          { error: "Chưa có file video tự động nào được tạo cho bài này." },
          { status: 400 }
        );
      }

      const accessToken = await getValidYoutubeAccessToken(store);
      const filePath = getGeneratedVideoPath(fileName);
      const fileBuf = await readFile(filePath);
      const arrayBuf = fileBuf.buffer.slice(
        fileBuf.byteOffset,
        fileBuf.byteOffset + fileBuf.byteLength
      );

      const title = targetEpisode?.title || "Proof of Wonder Short";
      const description =
        targetEpisode?.description ||
        buildDefaultDescription(title, targetEpisode?.hook3s || "", handle);
      const tags =
        targetEpisode?.tags && targetEpisode.tags.length > 0
          ? targetEpisode.tags
          : buildDefaultTags(title);
      const pinnedComment = targetEpisode?.pinnedComment || "";

      const publishModeRaw = String(body.publishMode || "schedule_golden");
      const publishMode =
        publishModeRaw === "public_now" || publishModeRaw === "private_draft"
          ? publishModeRaw
          : "schedule_golden";

      const uploadResult = await uploadShortVideoToStudio({
        accessToken,
        ownerChannelId,
        videoBuffer: arrayBuf,
        mimeType: "video/mp4",
        title,
        description,
        tags,
        pinnedComment,
        publishMode,
      });

      let autoAdvanced = false;
      if (targetIdx >= 0 && store.activePlan) {
        store.activePlan.items[targetIdx].status = "completed";
        store.activePlan.basedOnVideoCount =
          (store.activePlan.basedOnVideoCount || activeCh?.videoCount || 0) + 1;

        const allDone =
          store.activePlan.items.length > 0 &&
          store.activePlan.items.every((i) => i.status === "completed");
        if (allDone && store.activePlan.autoContinueEnabled) {
          store.completedSprintsCount =
            (store.completedSprintsCount || 0) + 1;
          store.activePlan = await generateNextGrowthSprint(store, {
            fastMode: true,
          });
          autoAdvanced = true;
        }
      }

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
        ? `Hẹn giờ vàng ${new Date(uploadResult.scheduledAt).toLocaleString(
            "vi-VN",
            {
              hour: "2-digit",
              minute: "2-digit",
              day: "2-digit",
              month: "2-digit",
            }
          )}`
        : publishMode === "public_now"
        ? "Đăng Công khai ngay"
        : "Lưu Nháp riêng tư";

      const msg = `🚀 Đã đẩy video AI "${title}" thẳng lên YouTube Studio (${scheduleLabel})!${
        autoAdvanced
          ? ` 🎉 Xong 5/5 bài — Tự động lập mới Sprint #${store.activePlan?.sprintNumber}!`
          : ""
      }`;

      store.autopilotLogs = [
        {
          id: `log-${Date.now()}`,
          timestamp: new Date().toISOString(),
          type: "publish" as const,
          message: msg,
        },
        ...(store.autopilotLogs || []),
      ].slice(0, 25);

      await writeStore(store);
      return Response.json({
        ok: true,
        store,
        uploadResult,
        message: msg,
      });
    }

    // MODE B: Generate Complete 9:16 MP4 Video (+ optional Full-Auto Upload!)
    const topicOrTitle =
      String(body.topic || "").trim() ||
      targetEpisode?.title ||
      "Why the Sun Should Be Silent Yet NASA Recorded Its Roar";

    const generated = await generateCompleteShortMp4({
      store,
      episodeId: targetEpisode?.id,
      topicOrTitle,
      seedHook: targetEpisode?.hook3s,
      seedVoiceover: targetEpisode?.voiceoverScript,
      voiceName: body.voiceName ? String(body.voiceName) : "Puck",
    });

    if (targetIdx >= 0 && store.activePlan) {
      store.activePlan.items[targetIdx].title = generated.title;
      store.activePlan.items[targetIdx].description = generated.description;
      store.activePlan.items[targetIdx].tags = generated.tags;
      store.activePlan.items[targetIdx].pinnedComment = generated.pinnedComment;
      store.activePlan.items[targetIdx].generatedVideoUrl = generated.videoUrl;
      store.activePlan.items[targetIdx].generatedVideoFileName =
        generated.videoFileName;
    }

    let uploadResult = null;
    let finalMsg = `🎬 Đã tạo xong video MP4 (${generated.durationSeconds}s • 1080x1920 • Đạo diễn: ${generated.directorModelUsed} • Ảnh: ${generated.imageEngineUsed})!`;

    if (body.autoUploadToYoutube && store.youtubeOAuth?.refreshToken) {
      const accessToken = await getValidYoutubeAccessToken(store);
      const filePath = getGeneratedVideoPath(generated.videoFileName);
      const fileBuf = await readFile(filePath);
      const arrayBuf = fileBuf.buffer.slice(
        fileBuf.byteOffset,
        fileBuf.byteOffset + fileBuf.byteLength
      );

      uploadResult = await uploadShortVideoToStudio({
        accessToken,
        ownerChannelId,
        videoBuffer: arrayBuf,
        mimeType: "video/mp4",
        title: generated.title,
        description: generated.description,
        tags: generated.tags,
        pinnedComment: generated.pinnedComment,
        publishMode:
          body.publishMode === "public_now" ||
          body.publishMode === "private_draft"
            ? body.publishMode
            : "schedule_golden",
      });

      if (targetIdx >= 0 && store.activePlan) {
        store.activePlan.items[targetIdx].status = "completed";
        store.activePlan.basedOnVideoCount =
          (store.activePlan.basedOnVideoCount || activeCh?.videoCount || 0) + 1;

        const allDone =
          store.activePlan.items.length > 0 &&
          store.activePlan.items.every((i) => i.status === "completed");
        if (allDone && store.activePlan.autoContinueEnabled) {
          store.completedSprintsCount =
            (store.completedSprintsCount || 0) + 1;
          store.activePlan = await generateNextGrowthSprint(store, {
            fastMode: true,
          });
        }
      }

      finalMsg = `⚡ Đã tự động Tạo Video MP4 (${generated.durationSeconds}s) VÀ Upload hẹn giờ vàng 17:15 VN lên YouTube Studio!`;
    }

    store.autopilotLogs = [
      {
        id: `log-${Date.now()}`,
        timestamp: new Date().toISOString(),
        type: "publish" as const,
        message: finalMsg,
      },
      ...(store.autopilotLogs || []),
    ].slice(0, 25);

    await writeStore(store);

    return Response.json({
      ok: true,
      generated,
      uploadResult,
      store,
      message: finalMsg,
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Lỗi trong quá trình tự động dựng video.";
    return Response.json({ ok: false, error: message }, { status: 500 });
  }
}
