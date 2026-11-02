import { connection } from "next/server";
import {
  listMacRenderedEpisodes,
  type MacThumbVariant,
  resetMacEpisodeOverride,
  saveMacEpisodeOverride,
} from "@/lib/mac-pipeline";
import { runSeoAndConversionAudit } from "@/lib/seo-analyzer";
import { readStore, writeStore } from "@/lib/store";
import type { StoreData, StudioPublishMode } from "@/lib/types";
import { reconcileStudioState } from "@/lib/youtube-studio";

async function buildEnrichedEpisodes(existingStore?: StoreData) {
  const store = existingStore || (await readStore());
  const activeCh =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];
  const handle = activeCh?.handle || "@proofofwonderscience";

  const rawEpisodes = await listMacRenderedEpisodes(handle, {
    publishedRecords: store.publishedMacEpisodes,
    recentVideos: activeCh?.recentVideos || [],
  });

  const episodes = rawEpisodes.map((ep) => {
    const audit = runSeoAndConversionAudit({
      title: ep.primaryTitle,
      description: ep.description,
      tags: ep.tags,
      targetKeyword: ep.targetKeyword,
      channelHandle: handle,
      isShort: (ep.durationSec ?? 60) <= 180,
      views: ep.youtubeState.liveViews || 0,
      likes: ep.youtubeState.liveLikes || 0,
      comments: 0,
    });
    return {
      ...ep,
      seoScore: audit.totalScore,
      seoGrade: audit.grade,
    };
  });

  return episodes;
}

export async function GET(request: Request) {
  await connection();
  const url = new URL(request.url);
  const syncStudio = url.searchParams.get("syncStudio") === "1";

  const store = await readStore();
  let reconcile: Awaited<ReturnType<typeof reconcileStudioState>> | undefined;

  if (syncStudio) {
    reconcile = await reconcileStudioState(store);
    if (
      reconcile.deletedSlugs.length > 0 ||
      reconcile.updatedSlugs.length > 0 ||
      reconcile.deletedRecentCount > 0
    ) {
      store.lastAutopilotSyncAt = new Date().toISOString();
      await writeStore(store);
    }
  }

  const episodes = await buildEnrichedEpisodes(store);
  return Response.json({
    ok: true,
    count: episodes.length,
    unpostedCount: episodes.filter(
      (e) =>
        e.youtubeState.status === "unposted" ||
        e.youtubeState.status === "private_draft"
    ).length,
    episodes,
    ...(syncStudio ? { store, reconcile } : {}),
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = String(body.action || "saveOverride");
    const slug = String(body.slug || "").trim();

    if (!slug) {
      return Response.json(
        { ok: false, error: "Thiếu mã tập video (slug)." },
        { status: 400 }
      );
    }

    if (action === "resetOverride") {
      await resetMacEpisodeOverride(slug);
      const episodes = await buildEnrichedEpisodes();
      return Response.json({
        ok: true,
        episodes,
        message: "Đã khôi phục nội dung gốc từ Antigravity!",
      });
    }

    if (action === "saveOverride") {
      const thumbVariantRaw = String(body.selectedThumbVariant || "primary");
      const selectedThumbVariant: MacThumbVariant =
        thumbVariantRaw === "variant_b" || thumbVariantRaw === "variant_c"
          ? thumbVariantRaw
          : "primary";

      const tagsArray: string[] = Array.isArray(body.tags)
        ? body.tags.map((t: unknown) => String(t).trim()).filter(Boolean)
        : typeof body.tags === "string"
        ? body.tags
            .split(",")
            .map((t: string) => t.trim())
            .filter(Boolean)
        : [];

      const publishModeRaw = String(body.publishMode || "");
      const publishMode: StudioPublishMode | undefined =
        publishModeRaw === "private_draft" ||
        publishModeRaw === "unlisted" ||
        publishModeRaw === "schedule_golden" ||
        publishModeRaw === "public_now"
          ? publishModeRaw
          : undefined;

      await saveMacEpisodeOverride(slug, {
        title: typeof body.title === "string" ? body.title.trim() : undefined,
        targetKeyword:
          typeof body.targetKeyword === "string"
            ? body.targetKeyword.trim()
            : undefined,
        description:
          typeof body.description === "string" ? body.description : undefined,
        tags: tagsArray,
        pinnedComment:
          typeof body.pinnedComment === "string"
            ? body.pinnedComment.trim()
            : undefined,
        selectedThumbVariant,
        ...(publishMode ? { publishMode } : {}),
        ...(typeof body.customPublishAtIso === "string"
          ? { customPublishAtIso: body.customPublishAtIso.trim() || undefined }
          : {}),
        ...(typeof body.playlistId === "string"
          ? { playlistId: body.playlistId.trim() }
          : {}),
        ...(typeof body.hasPaidProductPlacement === "boolean"
          ? { hasPaidProductPlacement: body.hasPaidProductPlacement }
          : {}),
        ...(typeof body.selfDeclaredMadeForKids === "boolean"
          ? { selfDeclaredMadeForKids: body.selfDeclaredMadeForKids }
          : {}),
        ...(typeof body.containsSyntheticMedia === "boolean"
          ? { containsSyntheticMedia: body.containsSyntheticMedia }
          : {}),
        ...(typeof body.embedShortsCoverFrame === "boolean"
          ? { embedShortsCoverFrame: body.embedShortsCoverFrame }
          : {}),
      });

      const episodes = await buildEnrichedEpisodes();
      return Response.json({
        ok: true,
        episodes,
        message: "Đã lưu nội dung & cấu hình xuất bản trên Mac!",
      });
    }

    return Response.json(
      { ok: false, error: "Hành động không hợp lệ." },
      { status: 400 }
    );
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error:
          err instanceof Error ? err.message : "Lỗi lưu chỉnh sửa nội dung.",
      },
      { status: 500 }
    );
  }
}
