import { generateNextGrowthSprint } from "@/lib/auto-planner";
import {
  type MacThumbVariant,
  optimizeThumbnailForYoutube,
  resolveMacEpisodeAssetFile,
  saveMacEpisodeOverride,
} from "@/lib/mac-pipeline";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import type {
  AutopilotLogEntry,
  StoreData,
  StudioPublishMode,
} from "@/lib/types";
import { diagnoseExistingVideosForSubRescue } from "@/lib/viral-script";
import { fetchTrackedChannelLive } from "@/lib/youtube";
import {
  applyEpisodeMetadataToVideo,
  getValidYoutubeAccessToken,
  reconcileStudioState,
  rescueSingleVideoOnStudio,
  updateOrPromoteStudioVideo,
} from "@/lib/youtube-studio";

function pushLog(
  store: StoreData,
  type: AutopilotLogEntry["type"],
  message: string
) {
  store.autopilotLogs = [
    {
      id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      timestamp: new Date().toISOString(),
      type,
      message,
    },
    ...(store.autopilotLogs || []),
  ].slice(0, 25);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();
    const accessToken = await getValidYoutubeAccessToken(store);

    const activeIdx = store.myChannels.findIndex(
      (c) => c.id === store.activeChannelId
    );
    const activeCh =
      activeIdx >= 0 ? store.myChannels[activeIdx] : store.myChannels[0];

    if (!activeCh) {
      return Response.json(
        { error: "Chưa có kênh YouTube nào để cập nhật." },
        { status: 400 }
      );
    }

    const handle = activeCh.handle.startsWith("@")
      ? activeCh.handle
      : `@${activeCh.handle}`;
    const ownerChannelId =
      store.youtubeOAuth?.connectedChannelId || activeCh.id;

    // ACTION 1: Rescue a single existing video on YouTube Studio
    if (body.action === "rescueSingle") {
      const videoId = String(body.videoId || "").trim();
      const allDiags = diagnoseExistingVideosForSubRescue(
        activeCh.recentVideos || [],
        handle
      );
      const diag = allDiags.find((d) => d.videoId === videoId);
      if (!diag) {
        return Response.json(
          { error: "Không tìm thấy thông tin video cần tối ưu." },
          { status: 404 }
        );
      }

      const res = await rescueSingleVideoOnStudio({
        accessToken,
        videoId,
        channelHandle: handle,
        ownerChannelId,
        cleanedTitle: diag.cleanedTitle,
        appendDescriptionBlock: diag.appendDescriptionBlock,
        suggestedComment: diag.suggestedPinnedComment,
        postComment: body.postComment !== false,
      });

      const resolved = new Set(store.resolvedVideoIds || []);
      resolved.add(videoId);
      store.resolvedVideoIds = Array.from(resolved);

      const ytKey = getEffectiveYoutubeKey(store);
      if (ytKey && !activeCh.isDemo) {
        try {
          const refreshed = await fetchTrackedChannelLive({
            query: activeCh.id,
            apiKey: ytKey,
            niche: activeCh.niche,
            existingSnapshots: activeCh.snapshots,
            existingMilestone: activeCh.targetMilestone,
          });
          const idx = store.myChannels.findIndex((c) => c.id === activeCh.id);
          if (idx >= 0) store.myChannels[idx] = refreshed;
        } catch {
          // ignore refresh glitch
        }
      }

      const msg = `⚡ Đã cập nhật trực tiếp lên YouTube Studio: "${res.updatedTitle}"${
        res.commentPosted ? " + tự đăng Bình luận câu hỏi!" : "!"
      }`;
      pushLog(store, "publish", msg);
      await writeStore(store);

      return Response.json({ ok: true, store, message: msg });
    }

    // ACTION 2: Batch-rescue ALL unresolved old videos in 1 click!
    if (body.action === "rescueAllOldVideos") {
      const resolved = new Set(store.resolvedVideoIds || []);
      const diags = diagnoseExistingVideosForSubRescue(
        activeCh.recentVideos || [],
        handle
      ).filter((d) => d.issues.length > 0 && !resolved.has(d.videoId));

      if (diags.length === 0) {
        return Response.json({
          ok: true,
          store,
          updatedCount: 0,
          message: "Tất cả video trên kênh đều đã được tối ưu sạch sẽ!",
        });
      }

      let updatedCount = 0;
      let commentsCount = 0;
      const errors: string[] = [];

      for (const diag of diags) {
        try {
          const r = await rescueSingleVideoOnStudio({
            accessToken,
            videoId: diag.videoId,
            channelHandle: handle,
            ownerChannelId,
            cleanedTitle: diag.cleanedTitle,
            appendDescriptionBlock: diag.appendDescriptionBlock,
            suggestedComment: diag.suggestedPinnedComment,
            postComment: body.postComment !== false,
          });
          resolved.add(diag.videoId);
          updatedCount++;
          if (r.commentPosted) commentsCount++;
        } catch (e) {
          errors.push(
            `${diag.videoId}: ${e instanceof Error ? e.message : "Lỗi"}`
          );
        }
      }

      store.resolvedVideoIds = Array.from(resolved);

      const ytKey = getEffectiveYoutubeKey(store);
      if (ytKey && !activeCh.isDemo && updatedCount > 0) {
        try {
          const refreshed = await fetchTrackedChannelLive({
            query: activeCh.id,
            apiKey: ytKey,
            niche: activeCh.niche,
            existingSnapshots: activeCh.snapshots,
            existingMilestone: activeCh.targetMilestone,
          });
          const idx = store.myChannels.findIndex((c) => c.id === activeCh.id);
          if (idx >= 0) store.myChannels[idx] = refreshed;
        } catch {
          // ignore
        }
      }

      if (updatedCount === 0 && errors.length > 0) {
        throw new Error(
          `Không thể cập nhật video (Hãy kiểm tra bạn đã chọn đúng kênh ${handle} khi cấp quyền chưa): ${errors[0]}`
        );
      }

      const msg = `🚀 Đã tự động sửa trực tiếp ${updatedCount}/${diags.length} video cũ trên YouTube Studio (dọn tiêu đề, nối link ?sub_confirmation=1, bật hiển thị Like & đăng ${commentsCount} bình luận)!`;
      pushLog(store, "publish", msg);
      await writeStore(store);

      return Response.json({
        ok: true,
        store,
        updatedCount,
        errors,
        message: msg,
      });
    }

    // ACTION 3: Apply today's Sprint Episode metadata directly to an existing/draft video ID
    if (body.action === "applyEpisodeMetadata") {
      const videoId = String(body.videoId || "").trim();
      if (!videoId) {
        return Response.json(
          { error: "Vui lòng chọn hoặc nhập Video ID cần áp dụng Metadata." },
          { status: 400 }
        );
      }

      const res = await applyEpisodeMetadataToVideo({
        accessToken,
        videoId,
        ownerChannelId,
        title: String(body.title || ""),
        description: String(body.description || ""),
        tags: Array.isArray(body.tags) ? body.tags : [],
        pinnedComment: body.pinnedComment ? String(body.pinnedComment) : undefined,
        appendToExistingDescription: Boolean(body.appendToExistingDescription),
      });

      if (body.markEpisodeCompleted && body.episodeId && store.activePlan) {
        const idx = store.activePlan.items.findIndex(
          (i) => i.id === body.episodeId
        );
        if (idx >= 0) {
          store.activePlan.items[idx].status = "completed";
        }
        const allDone =
          store.activePlan.items.length > 0 &&
          store.activePlan.items.every((i) => i.status === "completed");
        if (allDone && store.activePlan.autoContinueEnabled) {
          store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
          store.activePlan = await generateNextGrowthSprint(store, {
            fastMode: true,
          });
        }
      }

      const msg = `✅ Đã đẩy trọn bộ Tiêu đề, Mô tả, Tags${
        res.commentPosted ? " & Bình luận" : ""
      } thẳng lên video (${videoId}) trong YouTube Studio!`;
      pushLog(store, "publish", msg);
      await writeStore(store);

      return Response.json({ ok: true, store, message: msg });
    }

    // ACTION 4: Update or Promote an already-uploaded Mac Draft/Scheduled/Public video in <1s without re-uploading MP4
    if (body.action === "promoteOrUpdateMacVideo") {
      const videoId = String(body.videoId || "").trim();
      const slug = String(body.slug || "").trim();
      if (!videoId) {
        return Response.json(
          { error: "Thiếu Video ID của video cần cập nhật." },
          { status: 400 }
        );
      }

      const publishModeRaw = String(body.publishMode || "private_draft");
      const publishMode: StudioPublishMode =
        publishModeRaw === "public_now" ||
        publishModeRaw === "schedule_golden" ||
        publishModeRaw === "unlisted" ||
        publishModeRaw === "private_draft"
          ? publishModeRaw
          : "private_draft";

      const playlistIdRaw = String(body.playlistId || "").trim();
      const playlistId =
        playlistIdRaw && playlistIdRaw !== "none" ? playlistIdRaw : undefined;

      const hasPaidProductPlacement = Boolean(
        body.hasPaidProductPlacement ?? false
      );
      const selfDeclaredMadeForKids = Boolean(
        body.selfDeclaredMadeForKids ?? false
      );
      const containsSyntheticMedia = Boolean(
        body.containsSyntheticMedia ?? false
      );

      const thumbVariantRaw = String(body.thumbnailVariant || "primary");
      const chosenThumbVariant: MacThumbVariant =
        thumbVariantRaw === "variant_b" || thumbVariantRaw === "variant_c"
          ? thumbVariantRaw
          : "primary";

      let thumbnailBuffer: ArrayBuffer | null = null;
      let thumbnailMimeType = "image/jpeg";
      if (slug && body.updateThumbnail !== false) {
        const resolvedThumb =
          (await resolveMacEpisodeAssetFile(slug, chosenThumbVariant)) ||
          (await resolveMacEpisodeAssetFile(slug, "primary"));
        if (resolvedThumb) {
          const opt = await optimizeThumbnailForYoutube(
            resolvedThumb.filePath,
            resolvedThumb.mimeType
          );
          thumbnailBuffer = opt.buffer;
          thumbnailMimeType = opt.mimeType;
        }
      }

      const title = String(body.title || "").trim();
      const description = String(body.description || "");
      const tags: string[] = Array.isArray(body.tags)
        ? body.tags.map((t: unknown) => String(t).trim()).filter(Boolean)
        : [];
      const pinnedComment = body.pinnedComment
        ? String(body.pinnedComment)
        : undefined;

      const existingScheduledIsos = Object.values(
        store.publishedMacEpisodes || {}
      )
        .filter(
          (r) =>
            r.status === "scheduled" &&
            r.scheduledAt &&
            r.slug !== slug &&
            r.videoId !== videoId
        )
        .map((r) => r.scheduledAt!);

      let updateRes: Awaited<ReturnType<typeof updateOrPromoteStudioVideo>>;
      try {
        updateRes = await updateOrPromoteStudioVideo({
          accessToken,
          videoId,
          ownerChannelId,
          title,
          description,
          tags,
          pinnedComment,
          publishMode,
          customPublishAtIso: body.customPublishAtIso
            ? String(body.customPublishAtIso)
            : undefined,
          existingScheduledIsos,
          thumbnailBuffer,
          thumbnailMimeType,
          playlistId,
          hasPaidProductPlacement,
          selfDeclaredMadeForKids,
          containsSyntheticMedia,
        });
      } catch (err) {
        // If video was deleted on YouTube Studio, reconcile immediately so UI resets to unposted!
        await reconcileStudioState(store).catch(() => {});
        await writeStore(store).catch(() => {});
        throw err;
      }

      if (slug) {
        store.publishedMacEpisodes = store.publishedMacEpisodes || {};
        store.publishedMacEpisodes[slug] = {
          slug,
          videoId,
          status:
            publishMode === "private_draft"
              ? "private_draft"
              : publishMode === "unlisted"
              ? "unlisted"
              : publishMode === "schedule_golden"
              ? "scheduled"
              : "public",
          scheduledAt: updateRes.scheduledAt,
          watchUrl: updateRes.watchUrl,
          studioEditUrl: updateRes.studioEditUrl,
          title,
          description,
          tags,
          thumbnailVariant: chosenThumbVariant,
          playlistId,
          hasPaidProductPlacement,
          selfDeclaredMadeForKids,
          containsSyntheticMedia,
          updatedAt: new Date().toISOString(),
        };

        await saveMacEpisodeOverride(slug, {
          title,
          description,
          tags,
          pinnedComment,
          selectedThumbVariant: chosenThumbVariant,
          publishMode,
          customPublishAtIso:
            updateRes.scheduledAt ||
            (body.customPublishAtIso ? String(body.customPublishAtIso) : undefined),
          playlistId: playlistId || "",
          hasPaidProductPlacement,
          selfDeclaredMadeForKids,
          containsSyntheticMedia,
        }).catch(() => {});
      }

      if (
        body.advanceSprint &&
        publishMode !== "private_draft" &&
        store.activePlan
      ) {
        const targetEp = body.episodeId
          ? store.activePlan.items.find((i) => i.id === body.episodeId)
          : store.activePlan.items.find((i) => i.status !== "completed");
        if (targetEp) {
          targetEp.status = "completed";
        }
        const allDone =
          store.activePlan.items.length > 0 &&
          store.activePlan.items.every((i) => i.status === "completed");
        if (allDone && store.activePlan.autoContinueEnabled) {
          store.completedSprintsCount = (store.completedSprintsCount || 0) + 1;
          store.activePlan = await generateNextGrowthSprint(store, {
            fastMode: true,
          });
        }
      }

      await reconcileStudioState(store).catch(() => {});

      const modeLabel =
        publishMode === "private_draft"
          ? "Riêng tư / Bản nháp"
          : publishMode === "unlisted"
          ? "Không công khai (Unlisted)"
          : publishMode === "schedule_golden"
          ? `Hẹn giờ tự phát lúc ${new Date(
              updateRes.scheduledAt || ""
            ).toLocaleString("vi-VN", {
              hour: "2-digit",
              minute: "2-digit",
              day: "2-digit",
              month: "2-digit",
            })}`
          : "Đăng Công khai";

      const plLabel = updateRes.playlistAdded ? " + đã thêm vào Playlist" : "";
      const msg = `⚡ Đã cập nhật video "${title}" trên YouTube Studio (${modeLabel}${plLabel})!`;
      pushLog(store, "publish", msg);
      await writeStore(store);

      return Response.json({
        ok: true,
        store,
        uploadResult: updateRes,
        message: msg,
      });
    }

    return Response.json(
      { error: "Hành động YouTube Studio không hợp lệ." },
      { status: 400 }
    );
  } catch (err) {
    const message =
      err instanceof Error
        ? err.message
        : "Lỗi khi gọi trực tiếp YouTube Studio API.";
    return Response.json({ error: message }, { status: 500 });
  }
}
