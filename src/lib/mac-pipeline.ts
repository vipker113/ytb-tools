import { execFile } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readdir, readFile, stat, unlink, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import type {
  PublishedMacEpisodeRecord,
  StudioPublishMode,
  VideoItem,
} from "./types";

const execFileAsync = promisify(execFile);

export const DEFAULT_MAC_OUTPUT_ROOT =
  process.env.MAC_PIPELINE_OUTPUT_DIR ||
  path.resolve(process.cwd(), "..", "youtube-shorts-channel", "output");

export type MacThumbVariant = "primary" | "variant_b" | "variant_c";

export type MacAssetKind =
  | "video"
  | "primary"
  | "variant_b"
  | "variant_c"
  | "thumbnail_sheet"
  | "first_3s_sheet"
  | "contact_sheet"
  | "ending_sheet";

export interface MacQcGateRow {
  gate: string;
  status: string;
  measured: string;
}

export interface MacMetadataOverride {
  title?: string;
  targetKeyword?: string;
  description?: string;
  tags?: string[];
  pinnedComment?: string;
  selectedThumbVariant?: MacThumbVariant;
  publishMode?: StudioPublishMode;
  customPublishAtIso?: string;
  playlistId?: string;
  hasPaidProductPlacement?: boolean;
  selfDeclaredMadeForKids?: boolean;
  containsSyntheticMedia?: boolean;
  embedShortsCoverFrame?: boolean;
  updatedAt?: string;
}

export interface MacYoutubeLinkState {
  status: "unposted" | "private_draft" | "unlisted" | "scheduled" | "public";
  videoId?: string;
  watchUrl?: string;
  studioEditUrl?: string;
  scheduledAt?: string;
  playlistId?: string;
  hasPaidProductPlacement?: boolean;
  selfDeclaredMadeForKids?: boolean;
  containsSyntheticMedia?: boolean;
  liveViews?: number;
  liveLikes?: number;
  publishedTitle?: string;
}

export interface MacRenderedEpisode {
  slug: string;
  playlist: string;
  outputDir: string;
  mp4Path: string;
  thumbnailPath: string | null;
  hasPrimaryThumb: boolean;
  hasVariantB: boolean;
  hasVariantC: boolean;
  selectedThumbVariant: MacThumbVariant;
  availableSheets: Array<
    "thumbnail_sheet" | "first_3s_sheet" | "contact_sheet" | "ending_sheet"
  >;
  originalPrimaryTitle: string;
  primaryTitle: string;
  alternativeTitle: string;
  targetKeyword: string;
  description: string;
  tags: string[];
  pinnedComment: string;
  savedPublishMode?: StudioPublishMode;
  savedCustomPublishAtIso?: string;
  savedPlaylistId?: string;
  savedHasPaidProductPlacement?: boolean;
  savedSelfDeclaredMadeForKids?: boolean;
  savedContainsSyntheticMedia?: boolean;
  savedEmbedShortsCoverFrame?: boolean;
  narrationText: string;
  wordCount: number;
  subtitleCueCount: number;
  subtitlesPreview: string;
  durationSec: number | null;
  fileSizeMb: number;
  qcPassed: boolean;
  qcPassedGatesCount: number;
  qcTotalGatesCount: number;
  qcGates: MacQcGateRow[];
  hasSavedOverride: boolean;
  youtubeState: MacYoutubeLinkState;
  updatedAtIso: string;
}

const OVERRIDE_FILENAME = "web_metadata_override.json";

type CachedEpisodeBase = Omit<MacRenderedEpisode, "youtubeState">;
const episodeParseCache = new Map<
  string,
  { sig: string; base: CachedEpisodeBase }
>();

function injectConversionLinksSafely(
  description: string,
  channelHandle: string
): string {
  const cleanHandle = channelHandle.startsWith("@")
    ? channelHandle
    : `@${channelHandle}`;

  let result = description.trim();
  const hasSub = result.toLowerCase().includes("sub_confirmation=1");
  const withoutSub = result
    .toLowerCase()
    .replace(/[^\s]*sub_confirmation=1[^\s]*/g, "");
  const hasBridge =
    /(youtu\.be\/|youtube\.com\/watch|youtube\.com\/playlist|youtube\.com\/shorts|youtube\.com\/@[^/\s]+\/shorts)/i.test(
      withoutSub
    );

  const additions: string[] = [];
  if (!hasSub) {
    additions.push(
      `🔔 Subscribe for daily strange science: https://www.youtube.com/${cleanHandle}?sub_confirmation=1`
    );
  }
  if (!hasBridge) {
    additions.push(
      `▶️ Watch more Proof of Wonder Shorts: https://www.youtube.com/${cleanHandle}/shorts`
    );
  }

  if (additions.length > 0) {
    const ctaBlock = `\n\n${additions.join("\n")}`;
    if (result.length + ctaBlock.length <= 4950) {
      const marker = "\n\nScientific Sources:";
      const idx = result.indexOf(marker);
      if (idx > 0) {
        result = result.slice(0, idx) + ctaBlock + result.slice(idx);
      } else {
        result = `${result.trimEnd()}${ctaBlock}`;
      }
    }
  }
  return result.slice(0, 4950);
}

function parseYoutubeMetadataMarkdown(
  md: string,
  fallbackSlug: string,
  channelHandle: string
): {
  primaryTitle: string;
  alternativeTitle: string;
  description: string;
  tags: string[];
  pinnedComment: string;
} {
  const primaryMatch = md.match(
    /\*\*Primary Title[^*]*\*\*[:\s\r\n]+`([^`]+)`/
  );
  const altMatch = md.match(
    /\*\*Alternative Title[^*]*\*\*[:\s\r\n]+`([^`]+)`/
  );

  let description = "";
  const descHeaderIdx = md.indexOf("## YouTube Description");
  if (descHeaderIdx >= 0) {
    const afterHeader = md.slice(descHeaderIdx).replace(/^[^\n]*\n+/, "");
    const endSepIdx = afterHeader.indexOf("\n---\n");
    description = (
      endSepIdx >= 0 ? afterHeader.slice(0, endSepIdx) : afterHeader
    ).trim();
  }

  let tags: string[] = [];
  const tagsSectionIdx = md.indexOf("## YouTube Studio Tags");
  if (tagsSectionIdx >= 0) {
    const tagsSlice = md.slice(tagsSectionIdx, tagsSectionIdx + 900);
    const backtickMatch = tagsSlice.match(/`([^`]+)`/);
    if (backtickMatch) {
      tags = backtickMatch[1]
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);
    }
  }

  let pinnedComment = "";
  const pinSectionIdx = md.indexOf("## Suggested Pinned Comments");
  if (pinSectionIdx >= 0) {
    const pinSlice = md.slice(pinSectionIdx);
    const pinMatch = pinSlice.match(/`([^`]+)`/);
    if (pinMatch) {
      pinnedComment = pinMatch[1].trim();
    }
  }

  const primaryTitle = (primaryMatch?.[1] || fallbackSlug).trim();
  const alternativeTitle = (altMatch?.[1] || "").trim();

  if (tags.length === 0) {
    const hashMatches = description.match(/#([A-Za-z0-9_]+)/g) || [];
    tags = [
      ...hashMatches.map((h) => h.replace(/^#/, "").toLowerCase()),
      "proof of wonder",
      "science shorts",
    ];
  }

  return {
    primaryTitle,
    alternativeTitle,
    description: description
      ? injectConversionLinksSafely(description, channelHandle)
      : "",
    tags,
    pinnedComment,
  };
}

function parseScriptAndSrt(scriptMd: string, srtRaw: string): {
  narrationText: string;
  wordCount: number;
  subtitleCueCount: number;
  subtitlesPreview: string;
} {
  let narrationText = "";
  const marker = "## Verbatim Final Spoken Narration";
  const idx = scriptMd.indexOf(marker);
  if (idx >= 0) {
    const after = scriptMd.slice(idx + marker.length).trimStart();
    const sepIdx = after.indexOf("\n---");
    narrationText = (sepIdx >= 0 ? after.slice(0, sepIdx) : after).trim();
  }

  const blocks = srtRaw
    .trim()
    .split(/\r?\n\r?\n/)
    .map((b) => b.trim())
    .filter(Boolean);

  const previewLines: string[] = [];
  const plainSrtLines: string[] = [];

  for (const blk of blocks) {
    const lines = blk.split(/\r?\n/);
    if (lines.length >= 3 && lines[1].includes("-->")) {
      const timeRange = lines[1].replace(/,\d+/g, "").trim();
      const text = lines.slice(2).join(" ").trim();
      if (text) {
        previewLines.push(`[${timeRange}] ${text}`);
        plainSrtLines.push(text);
      }
    }
  }

  if (!narrationText && plainSrtLines.length > 0) {
    narrationText = plainSrtLines.join(" ");
  }

  const wordCount = narrationText
    ? narrationText.split(/\s+/).filter(Boolean).length
    : 0;

  return {
    narrationText,
    wordCount,
    subtitleCueCount: previewLines.length,
    subtitlesPreview: previewLines.join("\n"),
  };
}

function parseQcReport(qcRaw: string): {
  durationSec: number | null;
  qcPassed: boolean;
  qcPassedGatesCount: number;
  qcTotalGatesCount: number;
  qcGates: MacQcGateRow[];
} {
  const durMatch = qcRaw.match(/\*\*Duration:\*\*\s*`([0-9.]+)\s*seconds`/i);
  const durationSec = durMatch ? Number(durMatch[1]) : null;
  const qcGates: MacQcGateRow[] = [];

  for (const line of qcRaw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed.startsWith("| **")) continue;
    const cols = trimmed
      .split("|")
      .map((c) => c.trim())
      .filter(Boolean);
    if (cols.length >= 4) {
      qcGates.push({
        gate: cols[0].replace(/\*\*/g, ""),
        status: cols[2].replace(/\*\*/g, ""),
        measured: cols[3].replace(/`/g, ""),
      });
    }
  }

  const passedCount = qcGates.filter(
    (g) => g.status.toUpperCase() === "PASS"
  ).length;
  const qcHasFail =
    qcRaw.includes("| **FAIL** |") || qcRaw.includes("| **WARN** |");
  const qcPassed = Boolean(qcRaw) && !qcHasFail;

  return {
    durationSec,
    qcPassed,
    qcPassedGatesCount: passedCount,
    qcTotalGatesCount: qcGates.length,
    qcGates,
  };
}

function stemToken(word: string): string {
  if (word.length > 4 && word.endsWith("ies")) return `${word.slice(0, -3)}y`;
  if (word.length > 4 && word.endsWith("s") && !word.endsWith("ss")) {
    return word.slice(0, -1);
  }
  return word;
}

const MATCH_STOP_WORDS = new Set([
  "the",
  "and",
  "for",
  "are",
  "but",
  "not",
  "you",
  "all",
  "can",
  "why",
  "how",
  "who",
  "what",
  "when",
  "where",
  "which",
  "from",
  "into",
  "that",
  "this",
  "these",
  "those",
  "with",
  "actually",
  "inside",
  "look",
  "like",
  "other",
  "world",
  "documentary",
  "studio",
  "science",
  "short",
]);

function extractKeyStems(text: string): Set<string> {
  const raw = text
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((w) => w.length >= 3 && !MATCH_STOP_WORDS.has(w))
    .map(stemToken);
  return new Set(raw);
}

function computeYoutubeLinkState(params: {
  slug: string;
  title: string;
  originalTitle: string;
  publishedRecords?: Record<string, PublishedMacEpisodeRecord>;
  recentVideos?: VideoItem[];
}): {
  state: MacYoutubeLinkState;
  liveMetadata?: { title?: string; description?: string; tags?: string[] };
} {
  const saved = params.publishedRecords?.[params.slug];

  // If we have a Studio-tracked record (verified via OAuth videos.list on sync),
  // trust its exact visibility/schedule status first and enrich views if also in recentVideos.
  if (saved) {
    const exactLive = (params.recentVideos || []).find(
      (v) => v.id === saved.videoId
    );
    const resolvedTitle = exactLive?.title || saved.title;
    const resolvedDesc =
      saved.description !== undefined
        ? saved.description
        : exactLive?.description;
    const resolvedTags =
      saved.tags && saved.tags.length > 0
        ? saved.tags
        : exactLive?.tags && exactLive.tags.length > 0
        ? exactLive.tags
        : undefined;

    return {
      state: {
        status: saved.status,
        videoId: saved.videoId,
        watchUrl: saved.watchUrl,
        studioEditUrl: saved.studioEditUrl,
        scheduledAt: saved.scheduledAt,
        playlistId: saved.playlistId,
        hasPaidProductPlacement: saved.hasPaidProductPlacement,
        selfDeclaredMadeForKids: saved.selfDeclaredMadeForKids,
        containsSyntheticMedia: saved.containsSyntheticMedia,
        liveViews:
          saved.liveViews !== undefined
            ? Math.max(saved.liveViews, exactLive?.views ?? 0)
            : exactLive?.views,
        liveLikes:
          saved.liveLikes !== undefined
            ? Math.max(saved.liveLikes, exactLive?.likes ?? 0)
            : exactLive?.likes,
        publishedTitle: resolvedTitle,
      },
      liveMetadata: {
        title: resolvedTitle,
        description: resolvedDesc,
        tags: resolvedTags,
      },
    };
  }

  // Fallback for legacy episodes uploaded before publishedMacEpisodes existed
  const cleanedSlug = params.slug
    .replace(/^\d+-/, "")
    .replace(/-(v\d+|202\d+)(-[a-z0-9]+)*$/i, "");
  const slugStems = extractKeyStems(cleanedSlug);
  const epStems = extractKeyStems(
    `${params.originalTitle} ${params.title} ${cleanedSlug}`
  );

  let matchedLive: VideoItem | undefined;
  let bestScore = 0;

  for (const vid of params.recentVideos || []) {
    const vidStems = extractKeyStems(vid.title);
    if (vidStems.size === 0) continue;
    let overlap = 0;
    let slugOverlap = 0;
    for (const st of vidStems) {
      if (epStems.has(st)) overlap++;
      if (slugStems.has(st)) slugOverlap++;
    }
    const vidRatio = overlap / vidStems.size;
    const slugRatio =
      slugStems.size > 0 ? slugOverlap / slugStems.size : overlap / Math.max(1, epStems.size);

    const isStrongMatch =
      overlap >= 3 ||
      (overlap >= 2 &&
        (vidRatio >= 0.99 || (slugRatio >= 0.65 && vidRatio >= 0.65)));

    const score = overlap + vidRatio * 0.5 + slugRatio * 0.5;
    if (isStrongMatch && score > bestScore) {
      bestScore = score;
      matchedLive = vid;
    }
  }

  if (matchedLive) {
    return {
      state: {
        status: "public",
        videoId: matchedLive.id,
        watchUrl: `https://www.youtube.com/shorts/${matchedLive.id}`,
        studioEditUrl: `https://studio.youtube.com/video/${matchedLive.id}/edit`,
        liveViews: matchedLive.views,
        liveLikes: matchedLive.likes,
        publishedTitle: matchedLive.title,
      },
      liveMetadata: {
        title: matchedLive.title,
        description: matchedLive.description,
        tags:
          matchedLive.tags && matchedLive.tags.length > 0
            ? matchedLive.tags
            : undefined,
      },
    };
  }

  return { state: { status: "unposted" } };
}

async function fileExists(p: string): Promise<boolean> {
  return stat(p)
    .then((s) => s.isFile())
    .catch(() => false);
}

export async function findMacEpisodeDirBySlug(
  slug: string
): Promise<{ epDir: string; playlist: string } | null> {
  if (!slug || slug.includes("/") || slug.includes("..")) return null;
  let playlistDirs: string[] = [];
  try {
    playlistDirs = await readdir(DEFAULT_MAC_OUTPUT_ROOT);
  } catch {
    return null;
  }

  for (const playlist of playlistDirs) {
    if (playlist.startsWith(".")) continue;
    const candidateDir = path.join(DEFAULT_MAC_OUTPUT_ROOT, playlist, slug);
    const mp4Path = path.join(candidateDir, `${slug}.mp4`);
    if (await fileExists(mp4Path)) {
      return { epDir: candidateDir, playlist };
    }
  }
  return null;
}

export async function resolveMacEpisodeAssetFile(
  slug: string,
  asset: MacAssetKind
): Promise<{ filePath: string; mimeType: string } | null> {
  const found = await findMacEpisodeDirBySlug(slug);
  if (!found) return null;
  const { epDir } = found;

  if (asset === "video") {
    const mp4 = path.join(epDir, `${slug}.mp4`);
    if (await fileExists(mp4)) {
      return { filePath: mp4, mimeType: "video/mp4" };
    }
    return null;
  }

  const candidateMap: Record<Exclude<MacAssetKind, "video">, string[]> = {
    primary: [path.join(epDir, "thumbnail.jpg"), path.join(epDir, `${slug}.jpg`)],
    variant_b: [
      path.join(epDir, "thumbnail_variant_B.jpg"),
      path.join(epDir, "thumbnail_variant_b.jpg"),
    ],
    variant_c: [
      path.join(epDir, "thumbnail_variant_C.jpg"),
      path.join(epDir, "thumbnail_variant_c.jpg"),
    ],
    thumbnail_sheet: [path.join(epDir, "thumbnail_small_preview_sheet.jpg")],
    first_3s_sheet: [path.join(epDir, "first_3_seconds_audit_sheet.jpg")],
    contact_sheet: [path.join(epDir, "contact_sheet.jpg")],
    ending_sheet: [path.join(epDir, "ending_audit_sheet.jpg")],
  };

  for (const candidate of candidateMap[asset] || []) {
    if (await fileExists(candidate)) {
      return { filePath: candidate, mimeType: "image/jpeg" };
    }
  }
  return null;
}

export async function saveMacEpisodeOverride(
  slug: string,
  patch: MacMetadataOverride
): Promise<void> {
  const found = await findMacEpisodeDirBySlug(slug);
  if (!found) {
    throw new Error(`Không tìm thấy thư mục tập "${slug}" trên Mac.`);
  }
  const overridePath = path.join(found.epDir, OVERRIDE_FILENAME);
  let existing: MacMetadataOverride = {};
  try {
    existing = JSON.parse(await readFile(overridePath, "utf-8"));
  } catch {
    existing = {};
  }
  const merged: MacMetadataOverride = {
    ...existing,
    ...patch,
    updatedAt: new Date().toISOString(),
  };
  await writeFile(overridePath, JSON.stringify(merged, null, 2), "utf-8");
  episodeParseCache.delete(found.epDir);
}

export async function resetMacEpisodeOverride(slug: string): Promise<void> {
  const found = await findMacEpisodeDirBySlug(slug);
  if (!found) return;
  const overridePath = path.join(found.epDir, OVERRIDE_FILENAME);
  await unlink(overridePath).catch(() => {});
  episodeParseCache.delete(found.epDir);
}

export async function listMacRenderedEpisodes(
  channelHandle = "@proofofwonderscience",
  options?: {
    publishedRecords?: Record<string, PublishedMacEpisodeRecord>;
    recentVideos?: VideoItem[];
  }
): Promise<MacRenderedEpisode[]> {
  let playlistDirs: string[] = [];
  try {
    playlistDirs = await readdir(DEFAULT_MAC_OUTPUT_ROOT);
  } catch {
    return [];
  }

  const candidateJobs: Array<{
    playlist: string;
    slug: string;
    epDir: string;
  }> = [];

  await Promise.all(
    playlistDirs
      .filter((p) => !p.startsWith("."))
      .map(async (playlist) => {
        const playlistPath = path.join(DEFAULT_MAC_OUTPUT_ROOT, playlist);
        const pStat = await stat(playlistPath).catch(() => null);
        if (!pStat?.isDirectory()) return;
        const epDirs = await readdir(playlistPath).catch(() => []);
        for (const slug of epDirs) {
          if (slug.startsWith(".")) continue;
          candidateJobs.push({
            playlist,
            slug,
            epDir: path.join(playlistPath, slug),
          });
        }
      })
  );

  const loaded = await Promise.all(
    candidateJobs.map(
      async ({ playlist, slug, epDir }): Promise<MacRenderedEpisode | null> => {
        const mp4Candidate = path.join(epDir, `${slug}.mp4`);
        const overrideFile = path.join(epDir, OVERRIDE_FILENAME);
        const metaFile = path.join(epDir, "youtube_metadata.md");

        const [mp4Stat, overrideStat, metaStat] = await Promise.all([
          stat(mp4Candidate).catch(() => null),
          stat(overrideFile).catch(() => null),
          stat(metaFile).catch(() => null),
        ]);
        if (!mp4Stat?.isFile()) return null;

        const cacheSig = `${channelHandle}|${mp4Stat.size}|${Math.floor(
          mp4Stat.mtimeMs
        )}|${overrideStat ? Math.floor(overrideStat.mtimeMs) : 0}|${
          metaStat ? Math.floor(metaStat.mtimeMs) : 0
        }`;

        let base = episodeParseCache.get(epDir);
        if (!base || base.sig !== cacheSig) {
          const thumbPrimary1 = path.join(epDir, "thumbnail.jpg");
          const thumbPrimary2 = path.join(epDir, `${slug}.jpg`);
          const thumbB = path.join(epDir, "thumbnail_variant_B.jpg");
          const thumbC = path.join(epDir, "thumbnail_variant_C.jpg");

          const sheetDefs: Array<{
            key:
              | "thumbnail_sheet"
              | "first_3s_sheet"
              | "contact_sheet"
              | "ending_sheet";
            file: string;
          }> = [
            {
              key: "thumbnail_sheet",
              file: "thumbnail_small_preview_sheet.jpg",
            },
            { key: "first_3s_sheet", file: "first_3_seconds_audit_sheet.jpg" },
            { key: "contact_sheet", file: "contact_sheet.jpg" },
            { key: "ending_sheet", file: "ending_audit_sheet.jpg" },
          ];

          const [
            hasP1,
            hasP2,
            hasVariantB,
            hasVariantC,
            sheetChecks,
            mdRaw,
            qcRaw,
            scriptRaw,
            srtRaw,
            overrideRaw,
          ] = await Promise.all([
            fileExists(thumbPrimary1),
            fileExists(thumbPrimary2),
            fileExists(thumbB),
            fileExists(thumbC),
            Promise.all(
              sheetDefs.map(async (sd) => ({
                key: sd.key,
                ok: await fileExists(path.join(epDir, sd.file)),
              }))
            ),
            readFile(metaFile, "utf-8").catch(() => ""),
            readFile(path.join(epDir, "qc_report.md"), "utf-8").catch(() => ""),
            readFile(path.join(epDir, "script.md"), "utf-8").catch(() => ""),
            readFile(path.join(epDir, "subtitles.srt"), "utf-8").catch(
              () => ""
            ),
            overrideStat
              ? readFile(overrideFile, "utf-8").catch(() => "")
              : Promise.resolve(""),
          ]);

          const hasPrimaryThumb = hasP1 || hasP2;
          const primaryThumbPath = hasP1
            ? thumbPrimary1
            : hasP2
            ? thumbPrimary2
            : null;
          const availableSheets = sheetChecks
            .filter((s) => s.ok)
            .map((s) => s.key);

          let override: MacMetadataOverride | null = null;
          if (overrideRaw) {
            try {
              override = JSON.parse(overrideRaw) as MacMetadataOverride;
            } catch {
              override = null;
            }
          }

          const meta = parseYoutubeMetadataMarkdown(mdRaw, slug, channelHandle);
          const qcInfo = parseQcReport(qcRaw);
          const scriptInfo = parseScriptAndSrt(scriptRaw, srtRaw);

          const selectedThumbVariant: MacThumbVariant =
            override?.selectedThumbVariant === "variant_b" && hasVariantB
              ? "variant_b"
              : override?.selectedThumbVariant === "variant_c" && hasVariantC
              ? "variant_c"
              : "primary";

          const resolvedThumbPath =
            selectedThumbVariant === "variant_b" && hasVariantB
              ? thumbB
              : selectedThumbVariant === "variant_c" && hasVariantC
              ? thumbC
              : primaryThumbPath;

          const finalTitle = (override?.title || meta.primaryTitle).trim();
          const finalTags =
            override?.tags && override.tags.length > 0
              ? override.tags
              : meta.tags;
          const finalTargetKeyword = (
            override?.targetKeyword ||
            finalTags[0] ||
            ""
          ).trim();
          const finalDescription = (
            override?.description ?? meta.description
          ).slice(0, 4950);
          const finalPinnedComment =
            override?.pinnedComment ?? meta.pinnedComment;

          const parsedBase: CachedEpisodeBase = {
            slug,
            playlist,
            outputDir: epDir,
            mp4Path: mp4Candidate,
            thumbnailPath: resolvedThumbPath,
            hasPrimaryThumb,
            hasVariantB,
            hasVariantC,
            selectedThumbVariant,
            availableSheets,
            originalPrimaryTitle: meta.primaryTitle,
            primaryTitle: finalTitle,
            alternativeTitle: meta.alternativeTitle,
            targetKeyword: finalTargetKeyword,
            description: finalDescription,
            tags: finalTags,
            pinnedComment: finalPinnedComment,
            savedPublishMode: override?.publishMode,
            savedCustomPublishAtIso: override?.customPublishAtIso,
            savedPlaylistId: override?.playlistId,
            savedHasPaidProductPlacement: override?.hasPaidProductPlacement,
            savedSelfDeclaredMadeForKids: override?.selfDeclaredMadeForKids,
            savedContainsSyntheticMedia: override?.containsSyntheticMedia,
            savedEmbedShortsCoverFrame: override?.embedShortsCoverFrame,
            narrationText: scriptInfo.narrationText,
            wordCount: scriptInfo.wordCount,
            subtitleCueCount: scriptInfo.subtitleCueCount,
            subtitlesPreview: scriptInfo.subtitlesPreview,
            durationSec: qcInfo.durationSec,
            fileSizeMb: Number((mp4Stat.size / (1024 * 1024)).toFixed(1)),
            qcPassed: qcInfo.qcPassed,
            qcPassedGatesCount: qcInfo.qcPassedGatesCount,
            qcTotalGatesCount: qcInfo.qcTotalGatesCount,
            qcGates: qcInfo.qcGates,
            hasSavedOverride: Boolean(override),
            updatedAtIso: mp4Stat.mtime.toISOString(),
          };
          base = { sig: cacheSig, base: parsedBase };
          episodeParseCache.set(epDir, base);
        }

        const { state: youtubeState, liveMetadata } = computeYoutubeLinkState({
          slug,
          title: base.base.primaryTitle,
          originalTitle: base.base.originalPrimaryTitle,
          publishedRecords: options?.publishedRecords,
          recentVideos: options?.recentVideos,
        });

        const shouldOverlayLive = Boolean(
          liveMetadata && !base.base.hasSavedOverride
        );

        return {
          ...base.base,
          ...(shouldOverlayLive
            ? {
                primaryTitle: liveMetadata?.title || base.base.primaryTitle,
                description: liveMetadata?.description || base.base.description,
                tags:
                  liveMetadata?.tags && liveMetadata.tags.length > 0
                    ? liveMetadata.tags
                    : base.base.tags,
              }
            : {}),
          youtubeState,
        };
      }
    )
  );

  const results = loaded.filter(
    (item): item is MacRenderedEpisode => item !== null
  );
  results.sort((a, b) => b.updatedAtIso.localeCompare(a.updatedAtIso));
  return results;
}

/**
 * Ensures thumbnail JPEG is safely under YouTube Data API v3's strict 2 MB limit
 * (compressing cleanly via local ffmpeg only if > 1.80 MB).
 */
export async function optimizeThumbnailForYoutube(
  inputPathOrBuffer: string | ArrayBuffer,
  fallbackMime = "image/jpeg"
): Promise<{ buffer: ArrayBuffer; mimeType: string }> {
  let rawBuf: Buffer;
  let srcPath: string | null = null;
  let tempInput: string | null = null;
  const tempOutput = path.join(
    os.tmpdir(),
    `ytb-thumb-opt-${randomUUID()}.jpg`
  );

  try {
    if (typeof inputPathOrBuffer === "string") {
      srcPath = inputPathOrBuffer;
      rawBuf = await readFile(srcPath);
    } else {
      rawBuf = Buffer.from(inputPathOrBuffer);
    }

    // Under 1.80 MB JPEG -> send directly without touching pixels
    if (
      rawBuf.byteLength <= 1_800_000 &&
      (fallbackMime === "image/jpeg" || fallbackMime === "image/jpg")
    ) {
      return {
        buffer: rawBuf.buffer.slice(
          rawBuf.byteOffset,
          rawBuf.byteOffset + rawBuf.byteLength
        ) as ArrayBuffer,
        mimeType: "image/jpeg",
      };
    }

    if (!srcPath) {
      tempInput = path.join(os.tmpdir(), `ytb-thumb-in-${randomUUID()}.img`);
      await writeFile(tempInput, rawBuf);
      srcPath = tempInput;
    }

    await execFileAsync("ffmpeg", [
      "-y",
      "-hide_banner",
      "-loglevel",
      "error",
      "-i",
      srcPath,
      "-vf",
      "scale='min(1280,iw)':'min(1920,ih)':force_original_aspect_ratio=decrease",
      "-q:v",
      "4",
      tempOutput,
    ]);

    const optBuf = await readFile(tempOutput);
    if (optBuf.byteLength > 0 && optBuf.byteLength <= 1_980_000) {
      return {
        buffer: optBuf.buffer.slice(
          optBuf.byteOffset,
          optBuf.byteOffset + optBuf.byteLength
        ) as ArrayBuffer,
        mimeType: "image/jpeg",
      };
    }

    return {
      buffer: rawBuf.buffer.slice(
        rawBuf.byteOffset,
        rawBuf.byteOffset + rawBuf.byteLength
      ) as ArrayBuffer,
      mimeType: fallbackMime,
    };
  } catch {
    const fallbackBuf =
      typeof inputPathOrBuffer === "string"
        ? await readFile(inputPathOrBuffer)
        : Buffer.from(inputPathOrBuffer);
    return {
      buffer: fallbackBuf.buffer.slice(
        fallbackBuf.byteOffset,
        fallbackBuf.byteOffset + fallbackBuf.byteLength
      ) as ArrayBuffer,
      mimeType: fallbackMime,
    };
  } finally {
    if (tempInput) await unlink(tempInput).catch(() => {});
    await unlink(tempOutput).catch(() => {});
  }
}

/**
 * Prepends the chosen 9:16 Thumbnail Cover as a crisp 0.20s (6 frames @ 30fps)
 * opening cover frame via lossless mpegts stream-copy concat (~1.6s on Mac, 0₫).
 *
 * Why needed: On YouTube Shorts (vertical <= 180s), YouTube Studio Web disables
 * external custom thumbnail uploads on Shorts Shelf and extracts the cover frame
 * directly from inside the video stream (0:00). Embedding 0.20s at 0:00 guarantees
 * the cover exists inside the Short stream without altering the original file on disk.
 */
export async function buildShortsMp4WithEmbeddedCoverFrame(
  mp4Path: string,
  coverImagePath: string
): Promise<{ buffer: ArrayBuffer; embedded: boolean }> {
  const uid = randomUUID();
  const introTs = path.join(os.tmpdir(), `ytb-intro-${uid}.ts`);
  const mainTs = path.join(os.tmpdir(), `ytb-main-${uid}.ts`);
  const outMp4 = path.join(os.tmpdir(), `ytb-muxed-${uid}.mp4`);

  try {
    const { stdout } = await execFileAsync("ffprobe", [
      "-v",
      "error",
      "-show_entries",
      "stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
      "-of",
      "json",
      mp4Path,
    ]);
    const parsed = JSON.parse(stdout) as {
      streams?: Array<{
        codec_type?: string;
        codec_name?: string;
        width?: number;
        height?: number;
        r_frame_rate?: string;
        sample_rate?: string;
        channels?: number;
      }>;
    };

    const vStream = (parsed.streams || []).find(
      (s) => s.codec_type === "video"
    );
    const aStream = (parsed.streams || []).find(
      (s) => s.codec_type === "audio"
    );

    if (!vStream || vStream.codec_name !== "h264") {
      const raw = await readFile(mp4Path);
      return {
        buffer: raw.buffer.slice(
          raw.byteOffset,
          raw.byteOffset + raw.byteLength
        ) as ArrayBuffer,
        embedded: false,
      };
    }

    const width = Number(vStream.width || 1080);
    const height = Number(vStream.height || 1920);
    const fps = vStream.r_frame_rate || "30/1";
    const sampleRate = String(aStream?.sample_rate || "48000");
    const channels = Number(aStream?.channels || 2);
    const chLayout = channels === 1 ? "mono" : "stereo";

    const introArgs = aStream
      ? [
          "-y",
          "-hide_banner",
          "-loglevel",
          "error",
          "-loop",
          "1",
          "-t",
          "0.2",
          "-framerate",
          fps,
          "-i",
          coverImagePath,
          "-f",
          "lavfi",
          "-t",
          "0.2",
          "-i",
          `anullsrc=channel_layout=${chLayout}:sample_rate=${sampleRate}`,
          "-vf",
          `scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},format=yuv420p`,
          "-c:v",
          "libx264",
          "-profile:v",
          "high",
          "-level:v",
          "4.0",
          "-pix_fmt",
          "yuv420p",
          "-x264-params",
          "stitchable=1",
          "-r",
          fps,
          "-bf",
          "2",
          "-crf",
          "16",
          "-c:a",
          "aac",
          "-ar",
          sampleRate,
          "-ac",
          String(channels),
          "-b:a",
          "192k",
          "-shortest",
          "-f",
          "mpegts",
          introTs,
        ]
      : [
          "-y",
          "-hide_banner",
          "-loglevel",
          "error",
          "-loop",
          "1",
          "-t",
          "0.2",
          "-framerate",
          fps,
          "-i",
          coverImagePath,
          "-vf",
          `scale=${width}:${height}:force_original_aspect_ratio=increase,crop=${width}:${height},format=yuv420p`,
          "-c:v",
          "libx264",
          "-profile:v",
          "high",
          "-level:v",
          "4.0",
          "-pix_fmt",
          "yuv420p",
          "-x264-params",
          "stitchable=1",
          "-r",
          fps,
          "-bf",
          "2",
          "-crf",
          "16",
          "-f",
          "mpegts",
          introTs,
        ];

    await execFileAsync("ffmpeg", introArgs);

    await execFileAsync("ffmpeg", [
      "-y",
      "-hide_banner",
      "-loglevel",
      "error",
      "-i",
      mp4Path,
      "-c",
      "copy",
      "-bsf:v",
      "h264_mp4toannexb",
      "-f",
      "mpegts",
      mainTs,
    ]);

    const concatArgs = aStream
      ? [
          "-y",
          "-hide_banner",
          "-loglevel",
          "error",
          "-i",
          `concat:${introTs}|${mainTs}`,
          "-c",
          "copy",
          "-bsf:a",
          "aac_adtstoasc",
          "-movflags",
          "+faststart",
          outMp4,
        ]
      : [
          "-y",
          "-hide_banner",
          "-loglevel",
          "error",
          "-i",
          `concat:${introTs}|${mainTs}`,
          "-c",
          "copy",
          "-movflags",
          "+faststart",
          outMp4,
        ];

    await execFileAsync("ffmpeg", concatArgs);

    const outBuf = await readFile(outMp4);
    return {
      buffer: outBuf.buffer.slice(
        outBuf.byteOffset,
        outBuf.byteOffset + outBuf.byteLength
      ) as ArrayBuffer,
      embedded: true,
    };
  } catch {
    const raw = await readFile(mp4Path);
    return {
      buffer: raw.buffer.slice(
        raw.byteOffset,
        raw.byteOffset + raw.byteLength
      ) as ArrayBuffer,
      embedded: false,
    };
  } finally {
    await Promise.all([
      unlink(introTs).catch(() => {}),
      unlink(mainTs).catch(() => {}),
      unlink(outMp4).catch(() => {}),
    ]);
  }
}
