import { readFile } from "node:fs/promises";
import {
  buildDefaultDescription,
  buildDefaultTags,
  generateNextGrowthSprint,
} from "@/lib/auto-planner";
import {
  buildShortsMp4WithEmbeddedCoverFrame,
  listMacRenderedEpisodes,
  type MacThumbVariant,
  optimizeThumbnailForYoutube,
  resolveMacEpisodeAssetFile,
  saveMacEpisodeOverride,
} from "@/lib/mac-pipeline";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import type { StudioPublishMode } from "@/lib/types";
import { fetchTrackedChannelLive } from "@/lib/youtube";
import {
  getValidYoutubeAccessToken,
  reconcileStudioState,
  uploadShortVideoToStudio,
} from "@/lib/youtube-studio";

function parseFormBool(
  val: FormDataEntryValue | null,
  defaultVal: boolean
): boolean {
  if (val === null || val === undefined || val === "") return defaultVal;
  const s = String(val).trim().toLowerCase();
  if (s === "true" || s === "1" || s === "yes") return true;
  if (s === "false" || s === "0" || s === "no") return false;
  return defaultVal;
}

export async function POST(request: Request) {
  try {
    const formData = await request.formData();
    const file = formData.get("file");
    const thumbnailFile = formData.get("thumbnail");
    const localEpisodeSlug = String(
      formData.get("localEpisodeSlug") || ""
    ).trim();
    const thumbVariantRaw = String(
      formData.get("thumbnailVariant") || ""
    ).trim();

    const publishModeRaw = String(
      formData.get("publishMode") || "private_draft"
    );
    const publishMode: StudioPublishMode =
      publishModeRaw === "public_now" ||
      publishModeRaw === "private_draft" ||
      publishModeRaw === "unlisted" ||
      publishModeRaw === "schedule_golden"
        ? publishModeRaw
        : "private_draft";

    const playlistIdRaw = String(formData.get("playlistId") || "").trim();
    const playlistId =
      playlistIdRaw && playlistIdRaw !== "none" ? playlistIdRaw : undefined;

    // Compliance options (defaults strictly per user requirements: Ads=No, Kids=No, AI=No)
    const hasPaidProductPlacement = parseFormBool(
      formData.get("hasPaidProductPlacement"),
      false
    );
    const selfDeclaredMadeForKids = parseFormBool(
      formData.get("selfDeclaredMadeForKids"),
      false
    );
    const containsSyntheticMedia = parseFormBool(
      formData.get("containsSyntheticMedia"),
      false
    );
    const embedShortsCoverFrame = parseFormBool(
      formData.get("embedShortsCoverFrame"),
      true
    );

    const advanceSprintRaw = String(
      formData.get("advanceSprint") ??
        (publishMode === "private_draft" ? "false" : "true")
    ).trim();
    const shouldAdvanceSprint =
      publishMode === "private_draft"
        ? advanceSprintRaw === "force_true"
        : advanceSprintRaw !== "false";

    const store = await readStore();
    const accessToken = await getValidYoutubeAccessToken(store);

    const activeCh =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];
    const handle = activeCh?.handle || "@proofofwonderscience";
    const ownerChannelId =
      store.youtubeOAuth?.connectedChannelId || activeCh?.id;

    let videoBuffer: ArrayBuffer;
    let videoMimeType = "video/mp4";
    let fallbackFileTitle = "Proof of Wonder Short";
    let thumbnailBuffer: ArrayBuffer | null = null;
    let thumbnailMimeType = "image/jpeg";
    let chosenThumbVariant: MacThumbVariant = "primary";
    let coverEmbeddedIntoShort = false;
    let matchedLocalMeta: Awaited<
      ReturnType<typeof listMacRenderedEpisodes>
    >[number] | undefined;

    if (localEpisodeSlug) {
      const macEpisodes = await listMacRenderedEpisodes(handle, {
        publishedRecords: store.publishedMacEpisodes,
        recentVideos: activeCh?.recentVideos || [],
      });
      matchedLocalMeta = macEpisodes.find((e) => e.slug === localEpisodeSlug);
      if (!matchedLocalMeta) {
        return Response.json(
          {
            error: `Không tìm thấy tập "${localEpisodeSlug}" trong thư mục output trên Mac.`,
          },
          { status: 404 }
        );
      }

      fallbackFileTitle = matchedLocalMeta.primaryTitle;

      chosenThumbVariant =
        thumbVariantRaw === "variant_b" || thumbVariantRaw === "variant_c"
          ? thumbVariantRaw
          : matchedLocalMeta.selectedThumbVariant || "primary";

      const resolvedThumb =
        (await resolveMacEpisodeAssetFile(
          localEpisodeSlug,
          chosenThumbVariant
        )) || (await resolveMacEpisodeAssetFile(localEpisodeSlug, "primary"));

      if (resolvedThumb) {
        const opt = await optimizeThumbnailForYoutube(
          resolvedThumb.filePath,
          resolvedThumb.mimeType
        );
        thumbnailBuffer = opt.buffer;
        thumbnailMimeType = opt.mimeType;
      }

      const isShortEpisode = (matchedLocalMeta.durationSec ?? 60) <= 180;
      if (embedShortsCoverFrame && isShortEpisode && resolvedThumb) {
        const muxed = await buildShortsMp4WithEmbeddedCoverFrame(
          matchedLocalMeta.mp4Path,
          resolvedThumb.filePath
        );
        videoBuffer = muxed.buffer;
        coverEmbeddedIntoShort = muxed.embedded;
      } else {
        const nodeBuf = await readFile(matchedLocalMeta.mp4Path);
        videoBuffer = nodeBuf.buffer.slice(
          nodeBuf.byteOffset,
          nodeBuf.byteOffset + nodeBuf.byteLength
        ) as ArrayBuffer;
      }
    } else if (file && file instanceof File) {
      videoBuffer = await file.arrayBuffer();
      videoMimeType = file.type || "video/mp4";
      fallbackFileTitle = file.name.replace(/\.[^.]+$/, "");
      if (thumbnailFile && thumbnailFile instanceof File) {
        const rawThumb = await thumbnailFile.arrayBuffer();
        const opt = await optimizeThumbnailForYoutube(
          rawThumb,
          thumbnailFile.type || "image/jpeg"
        );
        thumbnailBuffer = opt.buffer;
        thumbnailMimeType = opt.mimeType;
      }
    } else {
      return Response.json(
        {
          error:
            "Vui lòng chọn file video (.mp4 / .mov) hoặc chọn 1 tập thành phẩm từ Mac.",
        },
        { status: 400 }
      );
    }

    if (!store.activePlan && activeCh) {
      store.activePlan = await generateNextGrowthSprint(store, {
        fastMode: true,
      });
    }

    const episodeIdParam = String(formData.get("episodeId") || "").trim();
    const targetEpisode = shouldAdvanceSprint
      ? episodeIdParam
        ? store.activePlan?.items.find((i) => i.id === episodeIdParam)
        : store.activePlan?.items.find((i) => i.status !== "completed")
      : undefined;

    const title =
      String(formData.get("title") || "").trim() ||
      (matchedLocalMeta && !shouldAdvanceSprint
        ? matchedLocalMeta.primaryTitle
        : "") ||
      targetEpisode?.title ||
      matchedLocalMeta?.primaryTitle ||
      fallbackFileTitle;

    const description =
      String(formData.get("description") || "").trim() ||
      matchedLocalMeta?.description ||
      targetEpisode?.description ||
      buildDefaultDescription(title, targetEpisode?.hook3s || "", handle);

    const rawTagsStr = String(formData.get("tags") || "").trim();
    const tags = rawTagsStr
      ? rawTagsStr
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean)
      : matchedLocalMeta && matchedLocalMeta.tags.length > 0
      ? matchedLocalMeta.tags
      : targetEpisode?.tags && targetEpisode.tags.length > 0
      ? targetEpisode.tags
      : buildDefaultTags(title);

    const pinnedComment =
      String(formData.get("pinnedComment") || "").trim() ||
      matchedLocalMeta?.pinnedComment ||
      targetEpisode?.pinnedComment ||
      "";

    const customPublishAtIso =
      String(formData.get("customPublishAtIso") || "").trim() || undefined;

    const existingScheduledIsos = Object.values(
      store.publishedMacEpisodes || {}
    )
      .filter(
        (r) =>
          r.status === "scheduled" &&
          r.scheduledAt &&
          r.slug !== localEpisodeSlug
      )
      .map((r) => r.scheduledAt!);

    const uploadResult = await uploadShortVideoToStudio({
      accessToken,
      ownerChannelId,
      videoBuffer,
      mimeType: videoMimeType,
      thumbnailBuffer,
      thumbnailMimeType,
      title,
      description,
      tags,
      pinnedComment,
      publishMode,
      customPublishAtIso,
      existingScheduledIsos,
      playlistId,
      hasPaidProductPlacement,
      selfDeclaredMadeForKids,
      containsSyntheticMedia,
    });

    // Save local Mac episode -> YouTube Studio tracking record + override preferences
    if (localEpisodeSlug) {
      store.publishedMacEpisodes = store.publishedMacEpisodes || {};
      store.publishedMacEpisodes[localEpisodeSlug] = {
        slug: localEpisodeSlug,
        videoId: uploadResult.videoId,
        status:
          publishMode === "private_draft"
            ? "private_draft"
            : publishMode === "unlisted"
            ? "unlisted"
            : publishMode === "schedule_golden"
            ? "scheduled"
            : "public",
        scheduledAt: uploadResult.scheduledAt,
        watchUrl: uploadResult.watchUrl,
        studioEditUrl: uploadResult.studioEditUrl,
        title,
        description,
        tags,
        thumbnailVariant: chosenThumbVariant,
        playlistId,
        hasPaidProductPlacement,
        selfDeclaredMadeForKids,
        containsSyntheticMedia,
        embedShortsCoverFrame,
        updatedAt: new Date().toISOString(),
      };

      await saveMacEpisodeOverride(localEpisodeSlug, {
        title,
        description,
        tags,
        pinnedComment,
        selectedThumbVariant: chosenThumbVariant,
        publishMode,
        customPublishAtIso: uploadResult.scheduledAt || customPublishAtIso,
        playlistId: playlistId || "",
        hasPaidProductPlacement,
        selfDeclaredMadeForKids,
        containsSyntheticMedia,
        embedShortsCoverFrame,
      }).catch(() => {});
    }

    // Advance Sprint step automatically when linked to Sprint
    let autoAdvancedSprint = false;
    if (shouldAdvanceSprint && targetEpisode && store.activePlan) {
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

    // Refresh live channel data if possible, then reconcile Studio state
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
    await reconcileStudioState(store).catch(() => {});

    const scheduleLabel = uploadResult.scheduledAt
      ? `Hẹn giờ tự phát lúc ${new Date(
          uploadResult.scheduledAt
        ).toLocaleString("vi-VN", {
          hour: "2-digit",
          minute: "2-digit",
          day: "2-digit",
          month: "2-digit",
        })}`
      : publishMode === "public_now"
      ? "Công khai ngay"
      : publishMode === "unlisted"
      ? "Không công khai (Unlisted)"
      : "Riêng tư / Bản nháp";

    const thumbParts: string[] = [];
    if (coverEmbeddedIntoShort) {
      thumbParts.push("nhúng bìa 0.2s đầu Shorts");
    }
    if (uploadResult.thumbnailUploaded) {
      thumbParts.push("đặt Thumbnail API");
    }
    const thumbNote =
      thumbParts.length > 0
        ? ` (${thumbParts.join(" + ")})`
        : uploadResult.thumbnailError
        ? ` (Lưu ý bìa API: ${uploadResult.thumbnailError})`
        : "";

    const playlistNote = uploadResult.playlistAdded
      ? " + đã thêm vào Playlist"
      : uploadResult.playlistError
      ? ` (Lỗi Playlist: ${uploadResult.playlistError})`
      : "";

    const logMessage = `🎬 Đăng thành công "${title}"${thumbNote}${playlistNote} → [${scheduleLabel}]!${
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
      uploadResult: {
        ...uploadResult,
        coverEmbeddedIntoShort,
      },
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
