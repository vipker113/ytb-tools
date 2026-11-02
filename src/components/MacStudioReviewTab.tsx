"use client";

import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Copy,
  ExternalLink,
  Eye,
  FileCheck2,
  FileText,
  Film,
  FolderPlus,
  Globe,
  Image as ImageIcon,
  Keyboard,
  Link2,
  ListVideo,
  Lock,
  Plus,
  RefreshCw,
  Rocket,
  RotateCcw,
  Save,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Wand2,
  X,
} from "lucide-react";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { formatNumber } from "@/lib/format";
import type { MacRenderedEpisode, MacThumbVariant } from "@/lib/mac-pipeline";
import {
  auditShortsScriptAndCompliance,
  runSeoAndConversionAudit,
  splitDescriptionEditorialAndCredits,
} from "@/lib/seo-analyzer";
import type {
  AiSeoRewriteProposal,
  GrowthSprintPlan,
  StoreData,
  StudioPublishMode,
  TrackedChannel,
  YoutubeOAuthState,
  YoutubePlaylistSummary,
} from "@/lib/types";

export interface EnrichedMacEpisode extends MacRenderedEpisode {
  seoScore: number;
  seoGrade: "S" | "A" | "B" | "C" | "D";
}

interface MacStudioReviewTabProps {
  channel?: TrackedChannel;
  plan?: GrowthSprintPlan | null;
  youtubeOAuth?: YoutubeOAuthState | null;
  initialSelectedSlug?: string | null;
  syncRevision?: number;
  onStoreSync?: (nextStore: StoreData) => void;
  onEpisodesCountChange?: (unpostedCount: number, totalCount: number) => void;
  onUploadMacEpisode: (params: {
    localEpisodeSlug: string;
    thumbnailVariant: MacThumbVariant;
    advanceSprint: boolean;
    publishMode: StudioPublishMode;
    customPublishAtIso?: string;
    playlistId?: string;
    hasPaidProductPlacement: boolean;
    selfDeclaredMadeForKids: boolean;
    containsSyntheticMedia: boolean;
    embedShortsCoverFrame: boolean;
    episodeId: string;
    title: string;
    description: string;
    tags: string[];
    pinnedComment: string;
  }) => Promise<void>;
  onPromoteOrUpdateMacDraft: (params: {
    slug: string;
    videoId: string;
    thumbnailVariant: MacThumbVariant;
    advanceSprint: boolean;
    episodeId: string;
    publishMode: StudioPublishMode;
    customPublishAtIso?: string;
    playlistId?: string;
    hasPaidProductPlacement: boolean;
    selfDeclaredMadeForKids: boolean;
    containsSyntheticMedia: boolean;
    title: string;
    description: string;
    tags: string[];
    pinnedComment: string;
  }) => Promise<void>;
  onExploreKeyword?: (keyword: string) => void;
  onNotify: (msg: string) => void;
}

interface DiffFieldSelection {
  title: boolean;
  targetKeyword: boolean;
  description: boolean;
  tags: boolean;
  pinnedComment: boolean;
}

const SHEET_LABELS: Record<
  "thumbnail_sheet" | "first_3s_sheet" | "contact_sheet" | "ending_sheet",
  string
> = {
  thumbnail_sheet: "Preview Bìa Trên Kệ Mobile",
  first_3s_sheet: "Audit 3 Giây Mở Đầu (Hook)",
  contact_sheet: "Contact Sheet Toàn Bộ Cảnh",
  ending_sheet: "Audit Điểm Nối Loop Cuối",
};

let macEpisodesClientCache: {
  episodes: EnrichedMacEpisode[];
  unpostedCount: number;
  signature: string;
  fetchedAt: number;
} | null = null;

let playlistsClientCache: YoutubePlaylistSummary[] | null = null;

function computeDefaultLocalScheduleInput(iso?: string): string {
  const target = iso ? new Date(iso) : new Date();
  if (!iso || Number.isNaN(target.getTime())) {
    const now = new Date();
    const candidate = new Date(now);
    candidate.setHours(17, 15, 0, 0);
    if (candidate.getTime() <= now.getTime() + 10 * 60_000) {
      candidate.setDate(candidate.getDate() + 1);
    }
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${candidate.getFullYear()}-${pad(candidate.getMonth() + 1)}-${pad(
      candidate.getDate()
    )}T${pad(candidate.getHours())}:${pad(candidate.getMinutes())}`;
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${target.getFullYear()}-${pad(target.getMonth() + 1)}-${pad(
    target.getDate()
  )}T${pad(target.getHours())}:${pad(target.getMinutes())}`;
}

function normalizeFolderKey(val: string): string {
  return val
    .toLowerCase()
    .replace(/\band\b/g, "")
    .replace(/[^a-z0-9]+/g, "");
}

function computeEpisodesSignature(list: EnrichedMacEpisode[]): string {
  return list
    .map(
      (e) =>
        `${e.slug}:${e.updatedAtIso}:${e.primaryTitle}:${e.description.length}:${e.tags.length}:${e.seoScore}:${e.selectedThumbVariant}:${e.hasSavedOverride}:${e.youtubeState.status}:${e.youtubeState.videoId || ""}:${e.youtubeState.scheduledAt || ""}:${e.youtubeState.playlistId || ""}:${e.youtubeState.liveViews || 0}`
    )
    .join("|");
}

export function MacStudioReviewTab({
  channel,
  plan,
  youtubeOAuth,
  initialSelectedSlug,
  syncRevision = 0,
  onStoreSync,
  onEpisodesCountChange,
  onUploadMacEpisode,
  onPromoteOrUpdateMacDraft,
  onExploreKeyword,
  onNotify,
}: MacStudioReviewTabProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [episodes, setEpisodes] = useState<EnrichedMacEpisode[]>(
    () => macEpisodesClientCache?.episodes || []
  );
  const [loading, setLoading] = useState(() => !macEpisodesClientCache);
  const [filterMode, setFilterMode] = useState<"pending" | "all" | "public">(
    "pending"
  );
  const [selectedSlug, setSelectedSlug] = useState<string>("");

  // Left inspector sub-tab
  const [inspectTab, setInspectTab] = useState<"script" | "qc">("script");
  const [zoomedImageUrl, setZoomedImageUrl] = useState<{
    url: string;
    label: string;
  } | null>(null);

  // Editable form states for selected episode
  const [title, setTitle] = useState("");
  const [targetKeyword, setTargetKeyword] = useState("");
  const [description, setDescription] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [pinnedComment, setPinnedComment] = useState("");
  const [thumbVariant, setThumbVariant] = useState<MacThumbVariant>("primary");
  const [advanceSprint, setAdvanceSprint] = useState(false);

  // Full YouTube Studio Publish Options (defaults strictly per user requirements)
  const [selectedPublishMode, setSelectedPublishMode] =
    useState<StudioPublishMode>("private_draft");
  const [customScheduleLocal, setCustomScheduleLocal] = useState<string>(() =>
    computeDefaultLocalScheduleInput()
  );
  const [selectedPlaylistId, setSelectedPlaylistId] = useState<string>("");
  const [hasPaidProductPlacement, setHasPaidProductPlacement] =
    useState<boolean>(false);
  const [selfDeclaredMadeForKids, setSelfDeclaredMadeForKids] =
    useState<boolean>(false);
  const [containsSyntheticMedia, setContainsSyntheticMedia] =
    useState<boolean>(false);
  const [embedShortsCoverFrame, setEmbedShortsCoverFrame] =
    useState<boolean>(true);

  // Playlist list & inline creator states
  const [playlists, setPlaylists] = useState<YoutubePlaylistSummary[]>(
    () => playlistsClientCache || []
  );
  const [playlistsLoading, setPlaylistsLoading] = useState(false);
  const [showCreatePlaylist, setShowCreatePlaylist] = useState(false);
  const [newPlaylistTitle, setNewPlaylistTitle] = useState("");
  const [creatingPlaylist, setCreatingPlaylist] = useState(false);

  // SEO & AI Diff Review states
  const [showAllSeoChecks, setShowAllSeoChecks] = useState(false);
  const [aiRewriteLoading, setAiRewriteLoading] = useState(false);
  const [aiDiffProposal, setAiDiffProposal] =
    useState<AiSeoRewriteProposal | null>(null);
  const [chosenDiffTitle, setChosenDiffTitle] = useState("");
  const [diffFields, setDiffFields] = useState<DiffFieldSelection>({
    title: true,
    targetKeyword: true,
    description: true,
    tags: true,
    pinnedComment: true,
  });

  // Action states
  const [savingLocal, setSavingLocal] = useState(false);
  const [publishingMode, setPublishingMode] =
    useState<StudioPublishMode | null>(null);
  const [forceReuploadMp4, setForceReuploadMp4] = useState(false);
  const [confirmPublicNow, setConfirmPublicNow] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handle = channel?.handle
    ? channel.handle.startsWith("@")
      ? channel.handle
      : `@${channel.handle}`
    : "@proofofwonderscience";

  const todaySprintItem = plan?.items.find((i) => i.status !== "completed");
  const isStudioConnected = Boolean(youtubeOAuth?.refreshToken);

  const todaySprintRef = useRef(todaySprintItem);
  todaySprintRef.current = todaySprintItem;

  const onCountChangeRef = useRef(onEpisodesCountChange);
  onCountChangeRef.current = onEpisodesCountChange;

  const onStoreSyncRef = useRef(onStoreSync);
  onStoreSyncRef.current = onStoreSync;

  const onNotifyRef = useRef(onNotify);
  onNotifyRef.current = onNotify;

  const playlistsRef = useRef(playlists);
  playlistsRef.current = playlists;

  const selectedSlugRef = useRef(selectedSlug);
  selectedSlugRef.current = selectedSlug;

  const initialSlugRef = useRef(initialSelectedSlug);
  initialSlugRef.current = initialSelectedSlug;

  const lastSignatureRef = useRef<string>(
    macEpisodesClientCache?.signature || ""
  );
  const lastFetchAtRef = useRef<number>(macEpisodesClientCache?.fetchedAt || 0);
  const inFlightRef = useRef<boolean>(false);
  const hydratedInitialRef = useRef<boolean>(false);
  const prevSyncRevRef = useRef<number>(syncRevision);

  const hydrateEditorFromEpisode = useCallback((ep: EnrichedMacEpisode) => {
    setTitle(ep.primaryTitle);
    setTargetKeyword(ep.targetKeyword || ep.tags[0] || "");
    setDescription(ep.description);
    setTagsText(ep.tags.join(", "));
    setPinnedComment(ep.pinnedComment);
    setThumbVariant(ep.selectedThumbVariant || "primary");
    setAiDiffProposal(null);
    setChosenDiffTitle("");
    setForceReuploadMp4(false);
    setConfirmPublicNow(false);

    // Hydrate publish mode from live Studio status first, then saved preference, default private_draft
    const st = ep.youtubeState;
    if (st.status === "public") {
      setSelectedPublishMode("public_now");
    } else if (st.status === "unlisted") {
      setSelectedPublishMode("unlisted");
    } else if (st.status === "scheduled") {
      setSelectedPublishMode("schedule_golden");
    } else if (ep.savedPublishMode) {
      setSelectedPublishMode(ep.savedPublishMode);
    } else {
      setSelectedPublishMode("private_draft");
    }

    setCustomScheduleLocal(
      computeDefaultLocalScheduleInput(
        st.scheduledAt || ep.savedCustomPublishAtIso
      )
    );

    // Hydrate compliance toggles (strictly default false / false / false)
    setHasPaidProductPlacement(
      Boolean(
        st.hasPaidProductPlacement ?? ep.savedHasPaidProductPlacement ?? false
      )
    );
    setSelfDeclaredMadeForKids(
      Boolean(
        st.selfDeclaredMadeForKids ?? ep.savedSelfDeclaredMadeForKids ?? false
      )
    );
    setContainsSyntheticMedia(
      Boolean(
        st.containsSyntheticMedia ?? ep.savedContainsSyntheticMedia ?? false
      )
    );
    setEmbedShortsCoverFrame(
      ep.savedEmbedShortsCoverFrame !== undefined
        ? ep.savedEmbedShortsCoverFrame
        : true
    );

    // Hydrate Playlist selection (saved -> live -> folder auto-match -> empty)
    const explicitPlaylist = st.playlistId ?? ep.savedPlaylistId;
    if (explicitPlaylist !== undefined) {
      setSelectedPlaylistId(explicitPlaylist === "none" ? "" : explicitPlaylist);
    } else {
      const folderNorm = normalizeFolderKey(ep.playlist || "");
      const fallbackNorm =
        folderNorm === "cosmicmysteries" || folderNorm === "proofofwonder"
          ? "spaceuniverse"
          : "";
      const autoMatched =
        playlistsRef.current.find(
          (pl) => normalizeFolderKey(pl.title) === folderNorm
        ) ||
        (fallbackNorm
          ? playlistsRef.current.find(
              (pl) => normalizeFolderKey(pl.title) === fallbackNorm
            )
          : undefined);
      setSelectedPlaylistId(autoMatched ? autoMatched.id : "");
    }

    const sprint = todaySprintRef.current;
    if (sprint) {
      const sprintWords = new Set(
        sprint.title
          .toLowerCase()
          .split(/[^a-z0-9]+/)
          .filter((w) => w.length >= 4)
      );
      const epWords = `${ep.primaryTitle} ${ep.slug}`
        .toLowerCase()
        .split(/[^a-z0-9]+/)
        .filter((w) => w.length >= 4);
      const overlap = epWords.filter((w) => sprintWords.has(w)).length;
      setAdvanceSprint(overlap >= 2);
    } else {
      setAdvanceSprint(false);
    }
  }, []);

  const loadPlaylists = useCallback(async (force = false) => {
    setPlaylistsLoading(true);
    try {
      const res = await fetch(
        `/api/youtube/playlists${force ? "?force=1" : ""}`,
        { cache: "no-store" }
      );
      const json = await res.json();
      if (res.ok && Array.isArray(json.playlists)) {
        const list = json.playlists as YoutubePlaylistSummary[];
        playlistsClientCache = list;
        setPlaylists(list);
      }
    } catch {
      // ignore
    } finally {
      setPlaylistsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isStudioConnected && !playlistsClientCache) {
      void loadPlaylists(false);
    }
  }, [isStudioConnected, loadPlaylists]);

  // Once live playlists finish loading on first mount, auto-match folder -> playlist if none chosen yet
  useEffect(() => {
    if (playlists.length === 0 || !selectedSlug) return;
    const ep = episodes.find((e) => e.slug === selectedSlug);
    if (!ep) return;
    const explicitPlaylist = ep.youtubeState.playlistId ?? ep.savedPlaylistId;
    if (explicitPlaylist !== undefined) return;
    setSelectedPlaylistId((prev) => {
      if (prev) return prev;
      const folderNorm = normalizeFolderKey(ep.playlist || "");
      const fallbackNorm =
        folderNorm === "cosmicmysteries" || folderNorm === "proofofwonder"
          ? "spaceuniverse"
          : "";
      const matched =
        playlists.find((pl) => normalizeFolderKey(pl.title) === folderNorm) ||
        (fallbackNorm
          ? playlists.find(
              (pl) => normalizeFolderKey(pl.title) === fallbackNorm
            )
          : undefined);
      return matched ? matched.id : "";
    });
  }, [playlists, selectedSlug, episodes]);

  const handleCreateNewPlaylist = async () => {
    const clean = newPlaylistTitle.trim();
    if (!clean) return;
    setCreatingPlaylist(true);
    try {
      const res = await fetch("/api/youtube/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: clean, privacyStatus: "public" }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.error || "Không thể tạo Playlist mới");
      }
      if (Array.isArray(json.playlists)) {
        playlistsClientCache = json.playlists;
        setPlaylists(json.playlists);
      }
      if (json.created?.id) {
        setSelectedPlaylistId(json.created.id);
      }
      setNewPlaylistTitle("");
      setShowCreatePlaylist(false);
      onNotify(json.message || `📂 Đã tạo Playlist "${clean}"!`);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi tạo Playlist");
    } finally {
      setCreatingPlaylist(false);
    }
  };

  const applyInitialSelection = useCallback(
    (list: EnrichedMacEpisode[]) => {
      if (list.length === 0) return;
      const curSlug = selectedSlugRef.current;
      if (curSlug && list.some((e) => e.slug === curSlug)) {
        if (!hydratedInitialRef.current) {
          hydratedInitialRef.current = true;
          const curEp = list.find((e) => e.slug === curSlug)!;
          hydrateEditorFromEpisode(curEp);
        }
        return;
      }

      const initSlug = initialSlugRef.current;
      if (initSlug && list.some((e) => e.slug === initSlug)) {
        const target = list.find((e) => e.slug === initSlug)!;
        hydratedInitialRef.current = true;
        setSelectedSlug(target.slug);
        hydrateEditorFromEpisode(target);
        if (target.youtubeState.status === "public") {
          setFilterMode("all");
        }
        return;
      }

      const firstPending = list.find(
        (e) =>
          e.youtubeState.status === "unposted" ||
          e.youtubeState.status === "private_draft"
      );
      const chosen = firstPending || list[0];
      if (chosen) {
        hydratedInitialRef.current = true;
        setSelectedSlug(chosen.slug);
        hydrateEditorFromEpisode(chosen);
        if (!firstPending) {
          setFilterMode("all");
        }
      }
    },
    [hydrateEditorFromEpisode]
  );

  const fetchMacEpisodes = useCallback(
    async (
      silent = false,
      force = false,
      opts?: { syncStudio?: boolean; rehydrateCurrent?: boolean }
    ) => {
      if (inFlightRef.current && !force) return;
      if (
        silent &&
        !force &&
        Date.now() - lastFetchAtRef.current < 15_000
      ) {
        return;
      }

      inFlightRef.current = true;
      if (!silent) setLoading(true);
      try {
        const endpoint = opts?.syncStudio
          ? "/api/mac-outputs?syncStudio=1"
          : "/api/mac-outputs";
        const res = await fetch(endpoint, { cache: "no-store" });
        const json = await res.json();
        if (json?.store) {
          onStoreSyncRef.current?.(json.store);
        }
        if (opts?.syncStudio && json?.reconcile?.summaryMessage) {
          onNotifyRef.current?.(json.reconcile.summaryMessage);
        }
        if (json?.ok && Array.isArray(json.episodes)) {
          const list = json.episodes as EnrichedMacEpisode[];
          const unposted = Number(json.unpostedCount ?? 0);
          const nextSig = computeEpisodesSignature(list);

          lastFetchAtRef.current = Date.now();
          macEpisodesClientCache = {
            episodes: list,
            unpostedCount: unposted,
            signature: nextSig,
            fetchedAt: lastFetchAtRef.current,
          };

          onCountChangeRef.current?.(unposted, list.length);

          if (nextSig !== lastSignatureRef.current || force) {
            lastSignatureRef.current = nextSig;
            setEpisodes(list);
          }

          if (opts?.rehydrateCurrent && selectedSlugRef.current) {
            const freshCurrent = list.find(
              (e) => e.slug === selectedSlugRef.current
            );
            if (freshCurrent) {
              hydrateEditorFromEpisode(freshCurrent);
            } else {
              applyInitialSelection(list);
            }
          } else {
            applyInitialSelection(list);
          }
        }
      } catch {
        // ignore offline glitch
      } finally {
        inFlightRef.current = false;
        if (!silent) setLoading(false);
      }
    },
    [applyInitialSelection, hydrateEditorFromEpisode]
  );

  // React immediately when top-header "Đồng bộ Kênh" completes Two-Way Studio Sync!
  useEffect(() => {
    if (syncRevision > prevSyncRevRef.current) {
      prevSyncRevRef.current = syncRevision;
      void fetchMacEpisodes(false, true, {
        syncStudio: false,
        rehydrateCurrent: true,
      });
      if (isStudioConnected) {
        void loadPlaylists(true);
      }
    }
  }, [syncRevision, fetchMacEpisodes, isStudioConnected, loadPlaylists]);

  // Mount once + lightweight throttled focus check (ZERO continuous setInterval polling!)
  useEffect(() => {
    if (macEpisodesClientCache) {
      applyInitialSelection(macEpisodesClientCache.episodes);
      onCountChangeRef.current?.(
        macEpisodesClientCache.unpostedCount,
        macEpisodesClientCache.episodes.length
      );
      void fetchMacEpisodes(true, false);
    } else {
      void fetchMacEpisodes(false, true);
    }

    const onWindowFocus = () => {
      if (document.visibilityState === "visible") {
        void fetchMacEpisodes(true, false);
      }
    };
    window.addEventListener("focus", onWindowFocus);
    return () => {
      window.removeEventListener("focus", onWindowFocus);
    };
  }, [applyInitialSelection, fetchMacEpisodes]);

  useEffect(() => {
    if (
      initialSelectedSlug &&
      initialSelectedSlug !== selectedSlugRef.current &&
      episodes.some((e) => e.slug === initialSelectedSlug)
    ) {
      const found = episodes.find((e) => e.slug === initialSelectedSlug)!;
      hydratedInitialRef.current = true;
      setSelectedSlug(found.slug);
      hydrateEditorFromEpisode(found);
      if (found.youtubeState.status === "public") {
        setFilterMode("all");
      }
    }
  }, [initialSelectedSlug, episodes, hydrateEditorFromEpisode]);

  const pendingEpisodes = useMemo(
    () =>
      episodes.filter(
        (e) =>
          e.youtubeState.status === "unposted" ||
          e.youtubeState.status === "private_draft" ||
          e.youtubeState.status === "unlisted" ||
          e.youtubeState.status === "scheduled"
      ),
    [episodes]
  );
  const publicEpisodes = useMemo(
    () => episodes.filter((e) => e.youtubeState.status === "public"),
    [episodes]
  );

  const filteredEpisodes = useMemo(() => {
    if (filterMode === "pending") {
      return pendingEpisodes.length > 0 ? pendingEpisodes : episodes;
    }
    if (filterMode === "public") return publicEpisodes;
    return episodes;
  }, [episodes, filterMode, pendingEpisodes, publicEpisodes]);

  const selectedEp = useMemo(
    () =>
      episodes.find((e) => e.slug === selectedSlug) ||
      filteredEpisodes[0] ||
      null,
    [episodes, filteredEpisodes, selectedSlug]
  );

  const parsedTags = useMemo(
    () =>
      tagsText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    [tagsText]
  );

  // Defer heavy regex/scoring computations so typing in inputs stays 120fps instant
  const deferredTitle = useDeferredValue(title);
  const deferredDesc = useDeferredValue(description);
  const deferredKw = useDeferredValue(targetKeyword);
  const deferredTags = useDeferredValue(parsedTags);

  const liveSeoAudit = useMemo(() => {
    return runSeoAndConversionAudit({
      title: deferredTitle,
      description: deferredDesc,
      tags: deferredTags,
      targetKeyword: deferredKw,
      channelHandle: handle,
      isShort: (selectedEp?.durationSec ?? 60) <= 180,
      views: selectedEp?.youtubeState.liveViews || 0,
      likes: selectedEp?.youtubeState.liveLikes || 0,
      comments: 0,
    });
  }, [
    deferredTitle,
    deferredDesc,
    deferredTags,
    deferredKw,
    handle,
    selectedEp,
  ]);

  const scriptComplianceAudit = useMemo(() => {
    return auditShortsScriptAndCompliance({
      narrationText: selectedEp?.narrationText || "",
      durationSec: selectedEp?.durationSec,
      description: deferredDesc,
    });
  }, [selectedEp?.narrationText, selectedEp?.durationSec, deferredDesc]);

  // Live preview of SEO score if the user accepts the currently selected diff checkboxes + chosen title
  const previewProposedAudit = useMemo(() => {
    if (!aiDiffProposal) return null;
    const nextTitle = diffFields.title
      ? chosenDiffTitle || aiDiffProposal.proposed.title
      : deferredTitle;
    const nextKw = diffFields.targetKeyword
      ? aiDiffProposal.proposed.targetKeyword
      : deferredKw;
    const nextDesc = diffFields.description
      ? aiDiffProposal.proposed.fullDescription
      : deferredDesc;
    const nextTags = diffFields.tags
      ? aiDiffProposal.proposed.tags
      : deferredTags;
    return runSeoAndConversionAudit({
      title: nextTitle,
      description: nextDesc,
      tags: nextTags,
      targetKeyword: nextKw,
      channelHandle: handle,
      isShort: (selectedEp?.durationSec ?? 60) <= 180,
    });
  }, [
    aiDiffProposal,
    diffFields,
    chosenDiffTitle,
    deferredTitle,
    deferredKw,
    deferredDesc,
    deferredTags,
    handle,
    selectedEp?.durationSec,
  ]);

  const saveOverridePayload = useCallback(
    async (payload: {
      slug: string;
      title: string;
      targetKeyword: string;
      description: string;
      tags: string[];
      pinnedComment: string;
      selectedThumbVariant: MacThumbVariant;
      publishMode?: StudioPublishMode;
      customPublishAtIso?: string;
      playlistId?: string;
      hasPaidProductPlacement?: boolean;
      selfDeclaredMadeForKids?: boolean;
      containsSyntheticMedia?: boolean;
      embedShortsCoverFrame?: boolean;
    }) => {
      setSavingLocal(true);
      try {
        const res = await fetch("/api/mac-outputs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "saveOverride",
            ...payload,
          }),
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || "Không thể lưu nội dung");
        if (Array.isArray(json.episodes)) {
          const list = json.episodes as EnrichedMacEpisode[];
          const sig = computeEpisodesSignature(list);
          lastSignatureRef.current = sig;
          macEpisodesClientCache = {
            episodes: list,
            unpostedCount: list.filter(
              (e) =>
                e.youtubeState.status === "unposted" ||
                e.youtubeState.status === "private_draft"
            ).length,
            signature: sig,
            fetchedAt: Date.now(),
          };
          setEpisodes(list);
          onCountChangeRef.current?.(
            macEpisodesClientCache.unpostedCount,
            list.length
          );
        }
        return json;
      } finally {
        setSavingLocal(false);
      }
    },
    []
  );

  const handleSaveLocalEdits = useCallback(async () => {
    if (!selectedEp) return;
    try {
      const customIso =
        selectedPublishMode === "schedule_golden" && customScheduleLocal
          ? new Date(customScheduleLocal).toISOString()
          : undefined;
      const json = await saveOverridePayload({
        slug: selectedEp.slug,
        title,
        targetKeyword,
        description,
        tags: parsedTags,
        pinnedComment,
        selectedThumbVariant: thumbVariant,
        publishMode: selectedPublishMode,
        customPublishAtIso: customIso,
        playlistId: selectedPlaylistId || "none",
        hasPaidProductPlacement,
        selfDeclaredMadeForKids,
        containsSyntheticMedia,
        embedShortsCoverFrame,
      });
      onNotify(
        json.message || "💾 Đã lưu nội dung & cấu hình xuất bản trên Mac!"
      );
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi lưu nội dung");
    }
  }, [
    selectedEp,
    saveOverridePayload,
    title,
    targetKeyword,
    description,
    parsedTags,
    pinnedComment,
    thumbVariant,
    selectedPublishMode,
    customScheduleLocal,
    selectedPlaylistId,
    hasPaidProductPlacement,
    selfDeclaredMadeForKids,
    containsSyntheticMedia,
    embedShortsCoverFrame,
    onNotify,
  ]);

  const handleSelectEpisode = useCallback(
    (ep: EnrichedMacEpisode) => {
      setSelectedSlug(ep.slug);
      hydrateEditorFromEpisode(ep);
    },
    [hydrateEditorFromEpisode]
  );

  // Stable ref so keydown listener is bound ONCE on mount (never re-bound on keystrokes!)
  const keyActionsRef = useRef({
    filteredEpisodes,
    selectedEp,
    handleSaveLocalEdits,
    handleSelectEpisode,
  });
  keyActionsRef.current = {
    filteredEpisodes,
    selectedEp,
    handleSaveLocalEdits,
    handleSelectEpisode,
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const {
        filteredEpisodes: list,
        selectedEp: cur,
        handleSaveLocalEdits: saveFn,
        handleSelectEpisode: selectFn,
      } = keyActionsRef.current;

      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void saveFn();
        return;
      }

      const activeEl = document.activeElement as HTMLElement | null;
      const tag = activeEl?.tagName?.toUpperCase() || "";
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        tag === "SELECT" ||
        activeEl?.isContentEditable
      ) {
        return;
      }

      if (e.code === "Space") {
        const vid = videoRef.current;
        if (vid) {
          e.preventDefault();
          if (vid.paused) {
            void vid.play().catch(() => {});
          } else {
            vid.pause();
          }
        }
        return;
      }

      if (e.key === "[" && list.length > 1 && cur) {
        e.preventDefault();
        const idx = list.findIndex((x) => x.slug === cur.slug);
        const prevIdx = idx <= 0 ? list.length - 1 : Math.max(0, idx - 1);
        selectFn(list[prevIdx]);
        return;
      }

      if (e.key === "]" && list.length > 1 && cur) {
        e.preventDefault();
        const idx = list.findIndex((x) => x.slug === cur.slug);
        const nextIdx = (idx + 1) % list.length;
        selectFn(list[nextIdx]);
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  const copyText = (id: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(id);
    setTimeout(() => setCopiedId((p) => (p === id ? null : p)), 2200);
  };

  // REAL AI SEO REWRITE WITH BEFORE -> AFTER DIFF & CITATION LOCK
  const handleRunAiSeoRewriteDiff = async () => {
    if (!selectedEp) return;
    setAiRewriteLoading(true);
    try {
      const res = await fetch("/api/seo/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "aiRewriteSeoDiff",
          title,
          targetKeyword,
          description,
          tags: parsedTags,
          pinnedComment,
          narrationScript: selectedEp.narrationText || "",
          channelHandle: handle,
          niche: channel?.niche || "Science & Space Documentary Shorts",
          isShort: (selectedEp.durationSec ?? 60) <= 180,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json?.proposal) {
        throw new Error(json?.error || "Không thể gọi AI viết lại gói SEO.");
      }
      const prop = json.proposal as AiSeoRewriteProposal;
      setAiDiffProposal(prop);
      setChosenDiffTitle(prop.proposed.title);
      setDiffFields({
        title: prop.proposed.title.trim() !== title.trim(),
        targetKeyword:
          prop.proposed.targetKeyword.trim().toLowerCase() !==
          targetKeyword.trim().toLowerCase(),
        description:
          prop.proposed.fullDescription.trim() !== description.trim(),
        tags:
          prop.proposed.tags.join(", ").toLowerCase() !==
          parsedTags.join(", ").toLowerCase(),
        pinnedComment:
          Boolean(prop.proposed.pinnedComment) &&
          prop.proposed.pinnedComment.trim() !== pinnedComment.trim(),
      });
    } catch (err) {
      onNotify(
        err instanceof Error ? err.message : "Lỗi khi gọi AI tối ưu SEO"
      );
    } finally {
      setAiRewriteLoading(false);
    }
  };

  const handleAcceptAiDiff = async (acceptAll = false) => {
    if (!aiDiffProposal || !selectedEp) return;
    const sel = acceptAll
      ? {
          title: true,
          targetKeyword: true,
          description: true,
          tags: true,
          pinnedComment: true,
        }
      : diffFields;

    const nextTitle = sel.title
      ? chosenDiffTitle || aiDiffProposal.proposed.title
      : title;
    const nextKw = sel.targetKeyword
      ? aiDiffProposal.proposed.targetKeyword
      : targetKeyword;
    const nextDesc = sel.description
      ? aiDiffProposal.proposed.fullDescription
      : description;
    const nextTags = sel.tags ? aiDiffProposal.proposed.tags : parsedTags;
    const nextPinned = sel.pinnedComment
      ? aiDiffProposal.proposed.pinnedComment || pinnedComment
      : pinnedComment;

    setTitle(nextTitle);
    setTargetKeyword(nextKw);
    setDescription(nextDesc);
    setTagsText(nextTags.join(", "));
    setPinnedComment(nextPinned);
    setAiDiffProposal(null);

    try {
      await saveOverridePayload({
        slug: selectedEp.slug,
        title: nextTitle,
        targetKeyword: nextKw,
        description: nextDesc,
        tags: nextTags,
        pinnedComment: nextPinned,
        selectedThumbVariant: thumbVariant,
      });
      onNotify(
        "✅ Đã áp dụng bản tối ưu SEO của AI & lưu an toàn trên ổ cứng Mac!"
      );
    } catch {
      onNotify("✅ Đã áp dụng bản tối ưu SEO lên khung soạn thảo!");
    }
  };

  const handleResetLocalEdits = async () => {
    if (!selectedEp) return;
    setSavingLocal(true);
    try {
      const res = await fetch("/api/mac-outputs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "resetOverride",
          slug: selectedEp.slug,
        }),
      });
      const json = await res.json();
      if (res.ok && Array.isArray(json.episodes)) {
        const list = json.episodes as EnrichedMacEpisode[];
        const sig = computeEpisodesSignature(list);
        lastSignatureRef.current = sig;
        macEpisodesClientCache = {
          episodes: list,
          unpostedCount: list.filter(
            (e) =>
              e.youtubeState.status === "unposted" ||
              e.youtubeState.status === "private_draft"
          ).length,
          signature: sig,
          fetchedAt: Date.now(),
        };
        setEpisodes(list);
        onCountChangeRef.current?.(
          macEpisodesClientCache.unpostedCount,
          list.length
        );
        const refreshed = list.find((e) => e.slug === selectedEp.slug);
        if (refreshed) hydrateEditorFromEpisode(refreshed);
        onNotify("↺ Đã khôi phục nội dung gốc từ Antigravity!");
      }
    } finally {
      setSavingLocal(false);
    }
  };

  const executePublishAction = async (mode: StudioPublishMode) => {
    if (!selectedEp) return;
    const isTransitioningToPublic =
      mode === "public_now" && selectedEp.youtubeState.status !== "public";
    if (isTransitioningToPublic && !confirmPublicNow) {
      setConfirmPublicNow(true);
      return;
    }
    setConfirmPublicNow(false);
    setPublishingMode(mode);

    let customPublishAtIso: string | undefined;
    if (mode === "schedule_golden" && customScheduleLocal) {
      const parsedDate = new Date(customScheduleLocal);
      if (!Number.isNaN(parsedDate.getTime())) {
        if (parsedDate.getTime() <= Date.now() + 60_000) {
          setPublishingMode(null);
          onNotify(
            "⚠️ Thời gian hẹn giờ phải nằm trong tương lai (cách hiện tại ít nhất 2 phút)!"
          );
          return;
        }
        customPublishAtIso = parsedDate.toISOString();
      }
    }

    try {
      await saveOverridePayload({
        slug: selectedEp.slug,
        title,
        targetKeyword,
        description,
        tags: parsedTags,
        pinnedComment,
        selectedThumbVariant: thumbVariant,
        publishMode: mode,
        customPublishAtIso,
        playlistId: selectedPlaylistId || "none",
        hasPaidProductPlacement,
        selfDeclaredMadeForKids,
        containsSyntheticMedia,
        embedShortsCoverFrame,
      }).catch(() => {});

      const existingVideoId = selectedEp.youtubeState.videoId;
      const canFastUpdateExisting =
        Boolean(existingVideoId) &&
        !forceReuploadMp4 &&
        selectedEp.youtubeState.status !== "unposted";

      if (canFastUpdateExisting && existingVideoId) {
        await onPromoteOrUpdateMacDraft({
          slug: selectedEp.slug,
          videoId: existingVideoId,
          thumbnailVariant: thumbVariant,
          advanceSprint: mode === "private_draft" ? false : advanceSprint,
          episodeId: todaySprintItem?.id || "",
          publishMode: mode,
          customPublishAtIso,
          playlistId: selectedPlaylistId || undefined,
          hasPaidProductPlacement,
          selfDeclaredMadeForKids,
          containsSyntheticMedia,
          title,
          description,
          tags: parsedTags,
          pinnedComment,
        });
      } else {
        await onUploadMacEpisode({
          localEpisodeSlug: selectedEp.slug,
          thumbnailVariant: thumbVariant,
          advanceSprint: mode === "private_draft" ? false : advanceSprint,
          publishMode: mode,
          customPublishAtIso,
          playlistId: selectedPlaylistId || undefined,
          hasPaidProductPlacement,
          selfDeclaredMadeForKids,
          containsSyntheticMedia,
          embedShortsCoverFrame,
          episodeId: todaySprintItem?.id || "",
          title,
          description,
          tags: parsedTags,
          pinnedComment,
        });
      }
      await fetchMacEpisodes(true, true, { rehydrateCurrent: true });
      if (selectedPlaylistId) {
        void loadPlaylists(true);
      }
    } finally {
      setPublishingMode(null);
    }
  };

  const renderStatusBadge = (ep: EnrichedMacEpisode) => {
    const st = ep.youtubeState;
    if (st.status === "public") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
          <Globe className="h-2.5 w-2.5" />
          Đã đăng
          {st.liveViews !== undefined
            ? ` • ${formatNumber(st.liveViews)} views`
            : ""}
        </span>
      );
    }
    if (st.status === "unlisted") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-cyan-500/20 border border-cyan-500/40 px-2 py-0.5 text-[10px] font-bold text-cyan-300">
          <Link2 className="h-2.5 w-2.5" />
          Không công khai
        </span>
      );
    }
    if (st.status === "scheduled") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 text-[10px] font-bold text-amber-300">
          <Clock className="h-2.5 w-2.5" />
          Đã hẹn giờ
        </span>
      );
    }
    if (st.status === "private_draft") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-violet-500/20 border border-violet-500/40 px-2 py-0.5 text-[10px] font-bold text-violet-300">
          <Lock className="h-2.5 w-2.5" />
          Riêng tư / Nháp
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-sky-500/20 border border-sky-500/40 px-2 py-0.5 text-[10px] font-bold text-sky-300">
        ✨ Mới • Chờ duyệt
      </span>
    );
  };

  const currentEditorialSplit = useMemo(
    () => splitDescriptionEditorialAndCredits(description),
    [description]
  );

  const selectedDiffCount = Object.values(diffFields).filter(Boolean).length;

  const currentTagSet = useMemo(
    () => new Set(parsedTags.map((t) => t.toLowerCase())),
    [parsedTags]
  );
  const proposedTagSet = useMemo(
    () =>
      new Set(
        (aiDiffProposal?.proposed.tags || []).map((t) => t.toLowerCase())
      ),
    [aiDiffProposal]
  );

  const currentEpIndex = selectedEp
    ? filteredEpisodes.findIndex((e) => e.slug === selectedEp.slug)
    : -1;

  return (
    <div className="space-y-5">
      {/* 1. COMPACT PRO STUDIO TOP BAR + EPISODE STRIP */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/90 p-4 shadow-lg space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-xl bg-zinc-950 p-1 border border-zinc-800">
            <button
              type="button"
              onClick={() => setFilterMode("pending")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                filterMode === "pending"
                  ? "bg-red-600 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Chờ duyệt & Draft ({pendingEpisodes.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterMode("all")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                filterMode === "all"
                  ? "bg-red-600 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Tất cả ({episodes.length})
            </button>
            <button
              type="button"
              onClick={() => setFilterMode("public")}
              className={`rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                filterMode === "public"
                  ? "bg-red-600 text-white"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              Đã đăng ({publicEpisodes.length})
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Split-screen keyboard shortcuts hint */}
            <div className="hidden md:inline-flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/90 px-3 py-1.5 text-[11px] text-zinc-400">
              <Keyboard className="h-3.5 w-3.5 text-zinc-500" />
              <span>
                <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-200">
                  Space
                </kbd>{" "}
                Phát/Dừng
              </span>
              <span>•</span>
              <span>
                <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-200">
                  [
                </kbd>{" "}
                <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-200">
                  ]
                </kbd>{" "}
                Đổi tập
              </span>
              <span>•</span>
              <span>
                <kbd className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-200">
                  ⌘S
                </kbd>{" "}
                Lưu
              </span>
            </div>

            {filteredEpisodes.length > 1 && selectedEp && (
              <div className="inline-flex items-center rounded-xl border border-zinc-800 bg-zinc-950">
                <button
                  type="button"
                  title="Tập trước ([)"
                  onClick={() => {
                    const prevIdx =
                      currentEpIndex <= 0
                        ? filteredEpisodes.length - 1
                        : currentEpIndex - 1;
                    handleSelectEpisode(filteredEpisodes[prevIdx]);
                  }}
                  className="p-2 text-zinc-300 hover:text-white cursor-pointer"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </button>
                <span className="px-1.5 text-[11px] font-bold text-zinc-400">
                  {currentEpIndex + 1}/{filteredEpisodes.length}
                </span>
                <button
                  type="button"
                  title="Tập tiếp theo (])"
                  onClick={() => {
                    const nextIdx =
                      (currentEpIndex + 1) % filteredEpisodes.length;
                    handleSelectEpisode(filteredEpisodes[nextIdx]);
                  }}
                  className="p-2 text-zinc-300 hover:text-white cursor-pointer"
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            )}

            <button
              type="button"
              onClick={() =>
                void fetchMacEpisodes(false, true, {
                  syncStudio: true,
                  rehydrateCurrent: true,
                })
              }
              disabled={loading}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 transition cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  loading ? "animate-spin text-sky-400" : "text-emerald-400"
                }`}
              />
              Đồng bộ Studio & Ổ cứng
            </button>
          </div>
        </div>

        {/* Episode Selector Cards */}
        {filteredEpisodes.length === 0 ? (
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-5 text-center text-xs text-zinc-400">
            Chưa có video nào trong bộ lọc này. Hãy chọn tab &ldquo;Tất cả&rdquo; hoặc tạo video mới trên Antigravity App!
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-56 overflow-y-auto pr-1">
            {filteredEpisodes.map((ep) => {
              const active = selectedEp?.slug === ep.slug;
              const cardThumbUrl = `/api/mac-outputs/media?slug=${encodeURIComponent(
                ep.slug
              )}&asset=${ep.selectedThumbVariant}&v=${encodeURIComponent(
                ep.updatedAtIso
              )}`;
              return (
                <button
                  key={ep.slug}
                  type="button"
                  onClick={() => handleSelectEpisode(ep)}
                  className={`flex items-start gap-2.5 rounded-xl border p-2.5 text-left transition cursor-pointer ${
                    active
                      ? "border-red-500 bg-red-950/20 shadow-md shadow-red-950/30"
                      : "border-zinc-800 bg-zinc-950/80 hover:border-zinc-700"
                  }`}
                >
                  <div className="h-16 w-10 shrink-0 rounded-lg overflow-hidden bg-zinc-900 border border-zinc-800">
                    {ep.hasPrimaryThumb ? (
                      <img
                        src={cardThumbUrl}
                        alt={ep.primaryTitle}
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="h-full w-full flex items-center justify-center text-zinc-600">
                        <Film className="h-4 w-4" />
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-1.5">
                      {renderStatusBadge(ep)}
                      <span
                        className={`rounded-full px-1.5 py-0.5 text-[10px] font-extrabold ${
                          ep.seoScore >= 88
                            ? "bg-emerald-500/15 text-emerald-300"
                            : ep.seoScore >= 70
                            ? "bg-amber-500/15 text-amber-300"
                            : "bg-rose-500/15 text-rose-300"
                        }`}
                      >
                        SEO {ep.seoScore}đ ({ep.seoGrade})
                      </span>
                    </div>

                    <p className="text-xs font-bold text-white line-clamp-2 leading-snug">
                      {ep.primaryTitle}
                    </p>

                    <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
                      <span>
                        {ep.durationSec
                          ? `${ep.durationSec.toFixed(1)}s`
                          : "Shorts"}
                      </span>
                      <span>•</span>
                      <span>{ep.fileSizeMb} MB</span>
                      {ep.qcTotalGatesCount > 0 && (
                        <>
                          <span>•</span>
                          <span
                            className={
                              ep.qcPassed
                                ? "text-emerald-400 font-semibold"
                                : "text-amber-400"
                            }
                          >
                            QC {ep.qcPassedGatesCount}/{ep.qcTotalGatesCount}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* 2. MAIN WORKSPACE: LEFT VIDEO & CONTENT INSPECTOR | RIGHT AI SEO DIFF, EDITOR & PUBLISH */}
      {selectedEp && (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
          {/* LEFT COLUMN: 9:16 VIDEO PLAYER + THUMBNAIL VARIANT PICKER + SCRIPT/QC */}
          <div className="xl:col-span-5 space-y-5">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 sm:p-5 space-y-4">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <span className="text-[11px] font-extrabold uppercase tracking-wider text-emerald-400">
                    1. Duyệt Video 9:16 & Ảnh Bìa
                  </span>
                  <p className="text-[11px] text-zinc-400 truncate font-mono">
                    {selectedEp.playlist}/{selectedEp.slug}.mp4
                  </p>
                </div>
                {selectedEp.qcPassed && (
                  <span className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-emerald-500/15 border border-emerald-500/35 px-2.5 py-1 text-[11px] font-bold text-emerald-300">
                    <ShieldCheck className="h-3.5 w-3.5" />
                    {selectedEp.qcPassedGatesCount}/{selectedEp.qcTotalGatesCount} QC PASS
                  </span>
                )}
              </div>

              {/* 9:16 Vertical HTML5 Video Player */}
              <div className="relative mx-auto w-full max-w-[290px] aspect-[9/16] rounded-2xl overflow-hidden border border-zinc-700 bg-black shadow-2xl">
                <video
                  ref={videoRef}
                  key={`${selectedEp.slug}-${selectedEp.updatedAtIso}`}
                  controls
                  playsInline
                  preload="metadata"
                  poster={
                    selectedEp.hasPrimaryThumb
                      ? `/api/mac-outputs/media?slug=${encodeURIComponent(
                          selectedEp.slug
                        )}&asset=${thumbVariant}&v=${encodeURIComponent(
                          selectedEp.updatedAtIso
                        )}`
                      : undefined
                  }
                  src={`/api/mac-outputs/media?slug=${encodeURIComponent(
                    selectedEp.slug
                  )}&asset=video&v=${encodeURIComponent(
                    selectedEp.updatedAtIso
                  )}`}
                  className="h-full w-full object-contain bg-black"
                />
              </div>

              {/* Thumbnail Cover Variant Selector */}
              {selectedEp.hasPrimaryThumb && (
                <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5 space-y-2.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-bold text-zinc-200 flex items-center gap-1.5">
                      <ImageIcon className="h-3.5 w-3.5 text-amber-400" />
                      Chọn Ảnh Bìa Thumbnail Đẩy Lên YouTube
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setZoomedImageUrl({
                          url: `/api/mac-outputs/media?slug=${encodeURIComponent(
                            selectedEp.slug
                          )}&asset=${thumbVariant}&v=${encodeURIComponent(
                            selectedEp.updatedAtIso
                          )}`,
                          label: `Ảnh bìa (${thumbVariant}) — ${selectedEp.primaryTitle}`,
                        })
                      }
                      className="text-[11px] text-sky-400 hover:text-sky-300 font-semibold inline-flex items-center gap-1 cursor-pointer"
                    >
                      <Eye className="h-3 w-3" />
                      Phóng to bìa
                    </button>
                  </div>

                  <div className="grid grid-cols-3 gap-2.5">
                    {(
                      [
                        {
                          id: "primary" as const,
                          label: "Bìa Chính",
                          available: selectedEp.hasPrimaryThumb,
                        },
                        {
                          id: "variant_b" as const,
                          label: "Biến thể B",
                          available: selectedEp.hasVariantB,
                        },
                        {
                          id: "variant_c" as const,
                          label: "Biến thể C",
                          available: selectedEp.hasVariantC,
                        },
                      ] as const
                    )
                      .filter((v) => v.available)
                      .map((variant) => {
                        const isPicked = thumbVariant === variant.id;
                        const imgUrl = `/api/mac-outputs/media?slug=${encodeURIComponent(
                          selectedEp.slug
                        )}&asset=${variant.id}&v=${encodeURIComponent(
                          selectedEp.updatedAtIso
                        )}`;
                        return (
                          <button
                            key={variant.id}
                            type="button"
                            onClick={() => setThumbVariant(variant.id)}
                            className={`group relative rounded-xl overflow-hidden border-2 transition cursor-pointer ${
                              isPicked
                                ? "border-emerald-500 ring-2 ring-emerald-500/30"
                                : "border-zinc-800 hover:border-zinc-600"
                            }`}
                          >
                            <div className="aspect-[9/16] bg-zinc-900">
                              <img
                                src={imgUrl}
                                alt={variant.label}
                                className="h-full w-full object-cover"
                              />
                            </div>
                            <div
                              className={`py-1 text-center text-[10px] font-bold ${
                                isPicked
                                  ? "bg-emerald-600 text-white"
                                  : "bg-zinc-900/95 text-zinc-300"
                              }`}
                            >
                              {isPicked ? `✓ ${variant.label}` : variant.label}
                            </div>
                          </button>
                        );
                      })}
                  </div>

                  {/* Dual-Layer YouTube Shorts Cover Guarantee */}
                  <label className="flex items-start gap-2.5 rounded-xl border border-amber-500/30 bg-amber-950/15 p-2.5 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={embedShortsCoverFrame}
                      onChange={(e) =>
                        setEmbedShortsCoverFrame(e.target.checked)
                      }
                      className="mt-0.5 h-4 w-4 rounded accent-emerald-500 shrink-0"
                    />
                    <div className="space-y-0.5 text-[11px] leading-relaxed">
                      <div className="font-bold text-amber-200">
                        Nhúng ảnh bìa vào 0.2s đầu video MP4 khi tải lên (Chuẩn YouTube Shorts)
                      </div>
                      <p className="text-zinc-400">
                        Với video dọc 9:16 (&le; 3 phút), Google Studio khóa tải ảnh bìa rời trên Web và chỉ lấy khung hình nằm trong luồng video. Bật mục này giúp tự ghép ảnh bìa bạn chọn vào{" "}
                        <strong className="text-zinc-200">0:00 (0.2s đầu)</strong>{" "}
                        khi upload (không chạm file gốc trên Mac) đồng thời gửi kèm Thumbnail API cho Google Search!
                      </p>
                    </div>
                  </label>
                </div>
              )}
            </div>

            {/* Spoken Script, Subtitles & Technical QC Inspector */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 sm:p-5 space-y-4">
              <div className="flex items-center justify-between gap-2 border-b border-zinc-800 pb-3">
                <div className="inline-flex rounded-xl bg-zinc-950 p-1 border border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setInspectTab("script")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                      inspectTab === "script"
                        ? "bg-zinc-800 text-white"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <FileText className="h-3.5 w-3.5 text-sky-400" />
                    Lời Thoại & Nhịp Đọc ({selectedEp.wordCount} từ)
                  </button>
                  <button
                    type="button"
                    onClick={() => setInspectTab("qc")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                      inspectTab === "qc"
                        ? "bg-zinc-800 text-white"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <FileCheck2 className="h-3.5 w-3.5 text-emerald-400" />
                    Báo Cáo QC & Contact Sheet
                  </button>
                </div>
              </div>

              {/* 5-Point Content & Compliance Check Strip */}
              <div className="grid grid-cols-1 gap-1.5">
                {scriptComplianceAudit.checks.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/80 bg-zinc-950/70 px-2.5 py-1.5 text-[11px]"
                  >
                    <span className="flex items-center gap-1.5 font-semibold text-zinc-200 min-w-0">
                      {c.passed ? (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                      ) : (
                        <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0" />
                      )}
                      <span className="truncate">{c.label}</span>
                    </span>
                    <span className="text-zinc-400 shrink-0 text-[10px]">
                      {c.detail}
                    </span>
                  </div>
                ))}
              </div>

              {inspectTab === "script" ? (
                <div className="space-y-3">
                  {selectedEp.narrationText ? (
                    <>
                      <div className="flex items-center justify-between text-[11px] text-zinc-400">
                        <span>
                          Lời thoại gốc •{" "}
                          <strong className="text-white">
                            {selectedEp.subtitleCueCount} dòng phụ đề
                          </strong>
                        </span>
                        <button
                          type="button"
                          onClick={() =>
                            copyText("script-copy", selectedEp.narrationText)
                          }
                          className="text-sky-400 hover:text-sky-300 font-semibold inline-flex items-center gap-1 cursor-pointer"
                        >
                          {copiedId === "script-copy" ? (
                            <Check className="h-3 w-3 text-emerald-400" />
                          ) : (
                            <Copy className="h-3 w-3" />
                          )}
                          Chép kịch bản
                        </button>
                      </div>
                      <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-3.5 text-xs text-zinc-200 leading-relaxed whitespace-pre-line max-h-56 overflow-y-auto">
                        {selectedEp.narrationText}
                      </div>
                      {selectedEp.subtitlesPreview && (
                        <details className="rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-3 text-xs">
                          <summary className="font-semibold text-zinc-300 cursor-pointer">
                            Xem mốc thời gian phụ đề SRT (
                            {selectedEp.subtitleCueCount} cues)
                          </summary>
                          <pre className="mt-2.5 max-h-44 overflow-y-auto whitespace-pre-wrap font-mono text-[11px] text-zinc-400 leading-relaxed">
                            {selectedEp.subtitlesPreview}
                          </pre>
                        </details>
                      )}
                    </>
                  ) : (
                    <p className="text-xs text-zinc-500">
                      Tập video này không có file script.md / subtitles.srt đính kèm.
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-3">
                  {selectedEp.availableSheets.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="text-[11px] font-bold text-zinc-300">
                        Bảng Ảnh Kiểm Định Trực Quan (Bấm để phóng to):
                      </span>
                      <div className="grid grid-cols-2 gap-2">
                        {selectedEp.availableSheets.map((sheetKey) => (
                          <button
                            key={sheetKey}
                            type="button"
                            onClick={() =>
                              setZoomedImageUrl({
                                url: `/api/mac-outputs/media?slug=${encodeURIComponent(
                                  selectedEp.slug
                                )}&asset=${sheetKey}&v=${encodeURIComponent(
                                  selectedEp.updatedAtIso
                                )}`,
                                label: `${SHEET_LABELS[sheetKey]} — ${selectedEp.slug}`,
                              })
                            }
                            className="rounded-xl border border-zinc-800 bg-zinc-950 hover:border-sky-500/50 px-3 py-2 text-left text-[11px] font-semibold text-zinc-200 flex items-center justify-between gap-2 cursor-pointer"
                          >
                            <span className="truncate">
                              {SHEET_LABELS[sheetKey]}
                            </span>
                            <Eye className="h-3.5 w-3.5 text-sky-400 shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {selectedEp.qcGates.length > 0 ? (
                    <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                      {selectedEp.qcGates.map((g, i) => (
                        <div
                          key={i}
                          className="rounded-xl border border-zinc-800/80 bg-zinc-950/70 px-3 py-2 text-xs flex items-start justify-between gap-2"
                        >
                          <div className="min-w-0">
                            <div className="font-bold text-zinc-200">
                              {g.gate}
                            </div>
                            <div className="text-[11px] text-zinc-400">
                              {g.measured}
                            </div>
                          </div>
                          <span
                            className={`shrink-0 rounded-md px-2 py-0.5 text-[10px] font-extrabold ${
                              g.status.toUpperCase() === "PASS"
                                ? "bg-emerald-500/15 text-emerald-300"
                                : "bg-amber-500/15 text-amber-300"
                            }`}
                          >
                            {g.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-zinc-500">
                      Không tìm thấy bảng qc_report.md cho video này.
                    </p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: LIVE SEO + AI BEFORE->AFTER DIFF + METADATA EDITOR + PUBLISH */}
          <div className="xl:col-span-7 space-y-5">
            {/* A. LIVE 100-POINT SEO SCOREBOARD & AI REWRITE BUTTON */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 sm:p-5 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-800">
                <div className="flex items-center gap-3.5">
                  <div
                    className={`h-16 w-16 rounded-2xl flex flex-col items-center justify-center border-2 shrink-0 ${
                      liveSeoAudit.totalScore >= 88
                        ? "border-emerald-500 bg-emerald-500/10 text-emerald-300"
                        : liveSeoAudit.totalScore >= 65
                        ? "border-amber-500 bg-amber-500/10 text-amber-300"
                        : "border-rose-500 bg-rose-500/10 text-rose-300"
                    }`}
                  >
                    <span className="text-xl font-extrabold">
                      {liveSeoAudit.totalScore}
                    </span>
                    <span className="text-[10px] font-bold uppercase">
                      Hạng {liveSeoAudit.grade}
                    </span>
                  </div>

                  <div>
                    <h3 className="text-sm sm:text-base font-extrabold text-white">
                      2. Chấm Điểm SEO & Tối Ưu Bằng AI (0₫)
                    </h3>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Đạt{" "}
                      <strong className="text-white">
                        {liveSeoAudit.checks.filter((c) => c.passed).length}/
                        {liveSeoAudit.checks.length}
                      </strong>{" "}
                      tiêu chí chuẩn YouTube Mỹ. Bấm nút AI để đọc lời thoại video, viết lại gói SEO và xem bảng đối chiếu trước khi Accept!
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => void handleRunAiSeoRewriteDiff()}
                  disabled={aiRewriteLoading}
                  className="shrink-0 inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 disabled:opacity-60 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/25 transition cursor-pointer"
                >
                  {aiRewriteLoading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      AI đang đọc kịch bản & viết lại...
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-4 w-4" />
                      Tối Ưu SEO Bằng AI (Xem Diff & Accept)
                    </>
                  )}
                </button>
              </div>

              {/* INTERACTIVE AI BEFORE -> AFTER DIFF REVIEW PANEL */}
              {aiDiffProposal && (
                <div className="rounded-2xl border-2 border-emerald-500/50 bg-gradient-to-br from-emerald-950/30 via-zinc-950 to-zinc-950 p-4 sm:p-5 space-y-4 shadow-2xl">
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-emerald-500/25 pb-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 px-2.5 py-1 text-xs font-extrabold text-emerald-300">
                          <Sparkles className="h-3.5 w-3.5" />
                          Đề Xuất Tối Ưu Từ AI ({aiDiffProposal.modelUsed})
                        </span>

                        {previewProposedAudit && (
                          <span className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 border border-zinc-700 px-2.5 py-1 text-xs font-extrabold">
                            <span className="text-zinc-400">
                              {aiDiffProposal.beforeScore}đ ({aiDiffProposal.beforeGrade})
                            </span>
                            <ArrowRight className="h-3.5 w-3.5 text-emerald-400" />
                            <span className="text-emerald-300">
                              {previewProposedAudit.totalScore}đ (
                              {previewProposedAudit.grade})
                            </span>
                            {previewProposedAudit.totalScore -
                              aiDiffProposal.beforeScore !==
                              0 && (
                              <span
                                className={`rounded px-1.5 py-0.5 text-[10px] ${
                                  previewProposedAudit.totalScore >=
                                  aiDiffProposal.beforeScore
                                    ? "bg-emerald-500/25 text-emerald-200"
                                    : "bg-amber-500/25 text-amber-200"
                                }`}
                              >
                                {previewProposedAudit.totalScore >=
                                aiDiffProposal.beforeScore
                                  ? `+${
                                      previewProposedAudit.totalScore -
                                      aiDiffProposal.beforeScore
                                    }đ`
                                  : `${
                                      previewProposedAudit.totalScore -
                                      aiDiffProposal.beforeScore
                                    }đ`}
                              </span>
                            )}
                          </span>
                        )}

                        {aiDiffProposal.protectedCreditsKept && (
                          <span className="inline-flex items-center gap-1 rounded-lg bg-sky-500/15 border border-sky-500/35 px-2.5 py-1 text-[11px] font-bold text-sky-300">
                            <ShieldCheck className="h-3.5 w-3.5" />
                            Đã khóa giữ nguyên 100% DOI & CC-BY
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-zinc-200 leading-relaxed pt-1">
                        💡 <strong className="text-emerald-300">Lý do tối ưu:</strong>{" "}
                        {aiDiffProposal.reasoningVi}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() => setAiDiffProposal(null)}
                      className="rounded-lg bg-zinc-900 hover:bg-zinc-800 p-1.5 text-zinc-400 hover:text-white cursor-pointer"
                      title="Đóng bảng so sánh"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  {/* DIFF ITEM 1: TITLE + CLICKABLE ALTERNATIVES */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3.5 space-y-2.5">
                    <label className="flex items-center justify-between gap-2 cursor-pointer">
                      <span className="inline-flex items-center gap-2 text-xs font-extrabold text-white">
                        <input
                          type="checkbox"
                          checked={diffFields.title}
                          onChange={(e) =>
                            setDiffFields((p) => ({
                              ...p,
                              title: e.target.checked,
                            }))
                          }
                          className="rounded accent-emerald-500 h-4 w-4"
                        />
                        1. Tiêu đề Video ({chosenDiffTitle.length} ký tự)
                      </span>
                      <span className="text-[11px] text-zinc-400">
                        Chọn 1 trong các phương án CTR cao bên dưới:
                      </span>
                    </label>

                    <div className="grid grid-cols-1 gap-2 text-xs">
                      <div className="rounded-lg border border-rose-500/25 bg-rose-950/15 px-3 py-2 text-zinc-300">
                        <span className="text-[10px] font-extrabold uppercase text-rose-300 mr-2">
                          Trước ({title.length} chars):
                        </span>
                        <span className="line-through decoration-rose-400/60 text-zinc-400">
                          {title}
                        </span>
                      </div>

                      <div className="rounded-lg border border-emerald-500/40 bg-emerald-950/20 px-3 py-2 text-white font-bold">
                        <span className="text-[10px] font-extrabold uppercase text-emerald-300 mr-2">
                          Sau ({chosenDiffTitle.length} chars):
                        </span>
                        {chosenDiffTitle}
                      </div>
                    </div>

                    {aiDiffProposal.alternativeTitles.length > 1 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[11px] font-semibold text-zinc-400">
                          Đổi nhanh phương án tiêu đề khác của AI:
                        </span>
                        <div className="grid grid-cols-1 gap-1.5">
                          {aiDiffProposal.alternativeTitles.map((alt, idx) => {
                            const activeAlt = chosenDiffTitle === alt;
                            return (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  setChosenDiffTitle(alt);
                                  setDiffFields((p) => ({ ...p, title: true }));
                                }}
                                className={`text-left rounded-lg border px-3 py-1.5 text-xs flex items-center justify-between gap-2 transition cursor-pointer ${
                                  activeAlt
                                    ? "border-emerald-500 bg-emerald-500/15 text-white font-bold"
                                    : "border-zinc-800 bg-zinc-950 text-zinc-300 hover:border-zinc-600"
                                }`}
                              >
                                <span>
                                  PA #{idx + 1}: {alt}
                                </span>
                                <span className="text-[10px] text-zinc-400 shrink-0">
                                  {alt.length} chars
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* DIFF ITEM 2: TARGET KEYWORD */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3.5 space-y-2">
                    <label className="inline-flex items-center gap-2 text-xs font-extrabold text-white cursor-pointer">
                      <input
                        type="checkbox"
                        checked={diffFields.targetKeyword}
                        onChange={(e) =>
                          setDiffFields((p) => ({
                            ...p,
                            targetKeyword: e.target.checked,
                          }))
                        }
                        className="rounded accent-emerald-500 h-4 w-4"
                      />
                      2. Từ khóa SEO mục tiêu chính
                    </label>
                    <div className="flex flex-wrap items-center gap-2 text-xs">
                      <span className="rounded-lg border border-rose-500/25 bg-rose-950/15 px-2.5 py-1 text-zinc-400 line-through">
                        {targetKeyword || "(trống)"}
                      </span>
                      <ArrowRight className="h-3.5 w-3.5 text-emerald-400" />
                      <span className="rounded-lg border border-emerald-500/40 bg-emerald-950/25 px-2.5 py-1 font-bold text-emerald-200">
                        {aiDiffProposal.proposed.targetKeyword}
                      </span>
                    </div>
                  </div>

                  {/* DIFF ITEM 3: EDITORIAL DESCRIPTION (WITH LOCKED CITATIONS GUARANTEE) */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3.5 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <label className="inline-flex items-center gap-2 text-xs font-extrabold text-white cursor-pointer">
                        <input
                          type="checkbox"
                          checked={diffFields.description}
                          onChange={(e) =>
                            setDiffFields((p) => ({
                              ...p,
                              description: e.target.checked,
                            }))
                          }
                          className="rounded accent-emerald-500 h-4 w-4"
                        />
                        3. Phần Mở Đầu Mô Tả & Phễu Kéo Sub
                      </label>
                      {aiDiffProposal.protectedCreditsKept && (
                        <span className="text-[10px] font-semibold text-sky-300">
                          🔒 Giữ nguyên toàn bộ Scientific Sources & Media Credits bên dưới
                        </span>
                      )}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs">
                      <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-2.5 space-y-1">
                        <div className="text-[10px] font-extrabold uppercase text-rose-300">
                          Trước (Đoạn giới thiệu cũ):
                        </div>
                        <p className="text-[11px] text-zinc-400 whitespace-pre-line max-h-40 overflow-y-auto leading-relaxed">
                          {currentEditorialSplit.editorialPart}
                        </p>
                      </div>
                      <div className="rounded-lg border border-emerald-500/35 bg-emerald-950/15 p-2.5 space-y-1">
                        <div className="text-[10px] font-extrabold uppercase text-emerald-300">
                          Sau (Chuẩn từ khóa 2 dòng đầu + CTA):
                        </div>
                        <p className="text-[11px] text-zinc-100 whitespace-pre-line max-h-40 overflow-y-auto leading-relaxed">
                          {aiDiffProposal.proposed.editorialDescription}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* DIFF ITEM 4: TAGS (+ ADDED / - REMOVED) */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3.5 space-y-2">
                    <label className="inline-flex items-center gap-2 text-xs font-extrabold text-white cursor-pointer">
                      <input
                        type="checkbox"
                        checked={diffFields.tags}
                        onChange={(e) =>
                          setDiffFields((p) => ({
                            ...p,
                            tags: e.target.checked,
                          }))
                        }
                        className="rounded accent-emerald-500 h-4 w-4"
                      />
                      4. Bộ Thẻ Tags ({aiDiffProposal.proposed.tags.length} thẻ •{" "}
                      {aiDiffProposal.proposed.tags.join(", ").length}/500 ký tự)
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {aiDiffProposal.proposed.tags.map((t) => {
                        const isAdded = !currentTagSet.has(t.toLowerCase());
                        return (
                          <span
                            key={t}
                            className={`rounded-md px-2 py-0.5 text-[11px] font-semibold ${
                              isAdded
                                ? "bg-emerald-500/20 border border-emerald-500/40 text-emerald-200"
                                : "bg-zinc-800 text-zinc-200"
                            }`}
                          >
                            {isAdded ? `+ ${t}` : t}
                          </span>
                        );
                      })}
                      {parsedTags
                        .filter((t) => !proposedTagSet.has(t.toLowerCase()))
                        .map((removed) => (
                          <span
                            key={`rem-${removed}`}
                            className="rounded-md bg-rose-950/30 border border-rose-500/25 px-2 py-0.5 text-[11px] text-rose-300/80 line-through"
                          >
                            - {removed}
                          </span>
                        ))}
                    </div>
                  </div>

                  {/* DIFF ITEM 5: PINNED COMMENT */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3.5 space-y-2">
                    <label className="inline-flex items-center gap-2 text-xs font-extrabold text-white cursor-pointer">
                      <input
                        type="checkbox"
                        checked={diffFields.pinnedComment}
                        onChange={(e) =>
                          setDiffFields((p) => ({
                            ...p,
                            pinnedComment: e.target.checked,
                          }))
                        }
                        className="rounded accent-emerald-500 h-4 w-4"
                      />
                      5. Bình Luận Ghim Kích Thích Tranh Luận
                    </label>
                    <div className="grid grid-cols-1 gap-1.5 text-xs">
                      {pinnedComment && (
                        <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 px-2.5 py-1.5 text-zinc-400">
                          <span className="text-[10px] font-bold text-rose-300 mr-1.5">
                            Trước:
                          </span>
                          {pinnedComment}
                        </div>
                      )}
                      <div className="rounded-lg border border-emerald-500/35 bg-emerald-950/15 px-2.5 py-1.5 text-emerald-100 font-medium">
                        <span className="text-[10px] font-bold text-emerald-300 mr-1.5">
                          Sau:
                        </span>
                        {aiDiffProposal.proposed.pinnedComment}
                      </div>
                    </div>
                  </div>

                  {/* ACCEPT / CANCEL ACTION BAR */}
                  <div className="flex flex-wrap items-center justify-between gap-2.5 pt-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        disabled={selectedDiffCount === 0}
                        onClick={() => void handleAcceptAiDiff(false)}
                        className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/25 transition cursor-pointer"
                      >
                        <Check className="h-4 w-4" />
                        Accept Các Mục Đã Chọn ({selectedDiffCount}) & Lưu
                      </button>

                      {selectedDiffCount < 5 && (
                        <button
                          type="button"
                          onClick={() => void handleAcceptAiDiff(true)}
                          className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/15 hover:bg-emerald-500/25 px-3.5 py-2.5 text-xs font-bold text-emerald-200 transition cursor-pointer"
                        >
                          Accept Tất Cả (5/5)
                        </button>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={() => setAiDiffProposal(null)}
                      className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3.5 py-2.5 text-xs font-semibold text-zinc-300 cursor-pointer"
                    >
                      Hủy / Giữ Nguyên Bản Cũ
                    </button>
                  </div>
                </div>
              )}

              {/* 4 Category Mini-bars */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                {[
                  {
                    label: "Tiêu đề & CTR",
                    val: liveSeoAudit.categoryScores.title,
                    max: 30,
                  },
                  {
                    label: "Mô tả & Phễu",
                    val: liveSeoAudit.categoryScores.description,
                    max: 30,
                  },
                  {
                    label: "Thẻ Từ Khóa",
                    val: liveSeoAudit.categoryScores.tags,
                    max: 20,
                  },
                  {
                    label: "Kéo Sub Thật",
                    val: liveSeoAudit.categoryScores.conversion,
                    max: 20,
                  },
                ].map((cat) => (
                  <div
                    key={cat.label}
                    className="rounded-xl border border-zinc-800/90 bg-zinc-950/70 p-2.5"
                  >
                    <div className="flex items-center justify-between text-[11px]">
                      <span className="text-zinc-400">{cat.label}</span>
                      <strong className="text-white">
                        {cat.val}/{cat.max}
                      </strong>
                    </div>
                    <div className="mt-1.5 h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full ${
                          cat.val / cat.max >= 0.8
                            ? "bg-emerald-500"
                            : "bg-amber-500"
                        }`}
                        style={{ width: `${(cat.val / cat.max) * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              {/* Toggleable 14 Detailed Checks + Keyword Explorer Jump */}
              <div className="space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <button
                    type="button"
                    onClick={() => setShowAllSeoChecks((v) => !v)}
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-sky-400 hover:text-sky-300 cursor-pointer"
                  >
                    <SearchCheck className="h-3.5 w-3.5" />
                    {showAllSeoChecks
                      ? "Thu gọn bảng 14 tiêu chí SEO"
                      : `Xem chi tiết 14 tiêu chí SEO (${
                          liveSeoAudit.checks.filter((c) => !c.passed).length
                        } mục có thể cải thiện)`}
                  </button>

                  {onExploreKeyword && (
                    <button
                      type="button"
                      onClick={() =>
                        onExploreKeyword(targetKeyword || parsedTags[0] || title)
                      }
                      className="text-[11px] font-semibold text-zinc-400 hover:text-white inline-flex items-center gap-1 cursor-pointer"
                    >
                      Phân tích độ cạnh tranh từ khóa trên thị trường Mỹ
                      <ExternalLink className="h-3 w-3" />
                    </button>
                  )}
                </div>

                {showAllSeoChecks && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-60 overflow-y-auto pr-1">
                    {[...liveSeoAudit.checks]
                      .sort((a, b) => Number(a.passed) - Number(b.passed))
                      .map((chk) => (
                        <div
                          key={chk.id}
                          className={`rounded-xl border p-2.5 text-xs ${
                            chk.passed
                              ? "border-zinc-800/80 bg-zinc-950/50"
                              : "border-amber-500/35 bg-amber-950/15"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-start gap-2 min-w-0">
                              {chk.passed ? (
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0 mt-0.5" />
                              ) : (
                                <AlertTriangle className="h-3.5 w-3.5 text-amber-400 shrink-0 mt-0.5" />
                              )}
                              <div className="min-w-0">
                                <div className="font-semibold text-zinc-100 leading-snug">
                                  {chk.label}
                                </div>
                                {!chk.passed && chk.actionTip && (
                                  <p className="text-[11px] text-amber-300 mt-0.5">
                                    → {chk.actionTip}
                                  </p>
                                )}
                              </div>
                            </div>
                            <span className="shrink-0 text-[11px] font-bold text-zinc-400">
                              {chk.score}/{chk.maxScore}
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            </div>

            {/* B. EDITABLE CONTENT & METADATA FORM */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 sm:p-5 space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-extrabold text-white">
                  3. Nội Dung Đăng Kèm Video (Tự chấm điểm tức thì khi sửa)
                </h3>

                <div className="flex items-center gap-2">
                  {selectedEp.hasSavedOverride && (
                    <button
                      type="button"
                      onClick={handleResetLocalEdits}
                      disabled={savingLocal}
                      className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-2.5 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                    >
                      <RotateCcw className="h-3 w-3" />
                      Khôi phục gốc
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleSaveLocalEdits()}
                    disabled={savingLocal}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
                  >
                    <Save className="h-3.5 w-3.5 text-sky-400" />
                    {savingLocal ? "Đang lưu..." : "Lưu Chỉnh Sửa (⌘S)"}
                  </button>
                </div>
              </div>

              {/* Title + A/B Title Switch */}
              <div className="space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-semibold text-zinc-300">
                    Tiêu đề Video (Không gắn #hashtag)
                  </span>
                  <div className="flex items-center gap-2">
                    {selectedEp.alternativeTitle &&
                      selectedEp.alternativeTitle !== title && (
                        <button
                          type="button"
                          onClick={() => setTitle(selectedEp.alternativeTitle)}
                          className="text-[11px] font-semibold text-amber-300 hover:text-amber-200 cursor-pointer"
                        >
                          🔄 Đổi sang Tiêu đề B có sẵn
                        </button>
                      )}
                    {selectedEp.originalPrimaryTitle &&
                      selectedEp.originalPrimaryTitle !== title && (
                        <button
                          type="button"
                          onClick={() =>
                            setTitle(selectedEp.originalPrimaryTitle)
                          }
                          className="text-[11px] font-semibold text-sky-300 hover:text-sky-200 cursor-pointer"
                        >
                          ↺ Tiêu đề Gốc
                        </button>
                      )}
                    <span
                      className={
                        title.length >= 42 && title.length <= 72
                          ? "text-emerald-400 font-semibold"
                          : "text-amber-400"
                      }
                    >
                      {title.length}/70 ký tự
                    </span>
                  </div>
                </div>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm font-bold text-white focus:border-red-500 focus:outline-none"
                />
              </div>

              {/* Target SEO Keyword + Pinned Comment */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-zinc-300 mb-1">
                    Từ khóa SEO mục tiêu chính
                  </label>
                  <input
                    type="text"
                    value={targetKeyword}
                    onChange={(e) => setTargetKeyword(e.target.value)}
                    placeholder="VD: fermi paradox"
                    className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-red-500 focus:outline-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="font-semibold text-zinc-300">
                      Bình luận Ghim (Pinned Comment)
                    </span>
                    <button
                      type="button"
                      onClick={() => copyText("pin-copy", pinnedComment)}
                      className="text-[11px] text-amber-300 hover:text-amber-200 cursor-pointer"
                    >
                      {copiedId === "pin-copy" ? "Đã chép" : "Copy"}
                    </button>
                  </div>
                  <input
                    type="text"
                    value={pinnedComment}
                    onChange={(e) => setPinnedComment(e.target.value)}
                    className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Description */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-zinc-300">
                    Mô tả Video (Kèm Link Đăng Ký 1-Click, Nguồn Khoa Học DOI & Bản Quyền)
                  </span>
                  <span
                    className={
                      description.length <= 4950
                        ? "text-zinc-400"
                        : "text-rose-400 font-bold"
                    }
                  >
                    {description.length}/4950 ký tự
                  </span>
                </div>
                <textarea
                  rows={6}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-xs text-zinc-200 leading-relaxed focus:border-red-500 focus:outline-none"
                />
              </div>

              {/* Tags */}
              <div>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-semibold text-zinc-300">
                    Bộ Thẻ Tags ({parsedTags.length} từ khóa)
                  </span>
                  <span
                    className={
                      tagsText.length <= 480
                        ? "text-zinc-400"
                        : "text-amber-400 font-bold"
                    }
                  >
                    {tagsText.length}/500 ký tự
                  </span>
                </div>
                <textarea
                  rows={2}
                  value={tagsText}
                  onChange={(e) => setTagsText(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-300 focus:border-red-500 focus:outline-none"
                />
              </div>
            </div>

            {/* C. FULL YOUTUBE STUDIO PUBLISH OPTIONS & FINAL DECISION */}
            <div className="rounded-2xl border border-emerald-500/40 bg-gradient-to-br from-emerald-950/25 via-zinc-900 to-zinc-950 p-4 sm:p-5 space-y-4 shadow-lg">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 pb-3.5">
                <div>
                  <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-400">
                    4. Tùy Chọn Đăng & Xuất Bản Lên YouTube Studio ({handle})
                  </span>
                  <p className="text-xs text-zinc-300 mt-0.5">
                    Chọn chế độ hiển thị, danh sách phát (Playlist) và các khai báo tuân thủ chuẩn YouTube Studio trước khi đăng.
                  </p>
                </div>

                {selectedEp.youtubeState.studioEditUrl && (
                  <a
                    href={selectedEp.youtubeState.studioEditUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3 py-2 text-xs font-bold text-sky-300 transition"
                  >
                    Mở Trong YouTube Studio
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>

              {selectedEp.youtubeState.status !== "unposted" &&
                selectedEp.youtubeState.videoId && (
                  <div className="rounded-xl border border-violet-500/35 bg-violet-950/20 p-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="text-violet-200">
                      {selectedEp.youtubeState.status === "public"
                        ? `🌍 Video đang Công khai trên kênh (ID: ${selectedEp.youtubeState.videoId}). Sửa chế độ đăng / SEO / Playlist bên dưới rồi bấm Cập nhật (1 giây)!`
                        : selectedEp.youtubeState.status === "unlisted"
                        ? `🔗 Video đang ở chế độ Không công khai (ID: ${selectedEp.youtubeState.videoId}).`
                        : selectedEp.youtubeState.status === "private_draft"
                        ? `🔒 Video đang ở chế độ Riêng tư / Bản nháp (ID: ${selectedEp.youtubeState.videoId}).`
                        : `⏰ Video đang hẹn giờ tự phát sóng (${
                            selectedEp.youtubeState.scheduledAt
                              ? new Date(
                                  selectedEp.youtubeState.scheduledAt
                                ).toLocaleString("vi-VN")
                              : "17:15 VN"
                          }).`}
                    </span>
                    <label className="inline-flex items-center gap-1.5 text-[11px] text-zinc-300 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={forceReuploadMp4}
                        onChange={(e) => setForceReuploadMp4(e.target.checked)}
                        className="rounded accent-red-500"
                      />
                      Tải mới lại file .mp4 (kèm nhúng lại bìa 0.2s)
                    </label>
                  </div>
                )}

              {/* 4.1 CHẾ ĐỘ ĐĂNG (VISIBILITY MODE) */}
              <div className="space-y-2">
                <label className="block text-xs font-extrabold text-zinc-200">
                  4.1 Chế độ đăng (Hiển thị trên YouTube):
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
                  {(
                    [
                      {
                        id: "private_draft" as const,
                        title: "Riêng tư (Private)",
                        desc: "Lưu bản nháp kín trong Studio",
                        icon: Lock,
                        activeCls:
                          "border-violet-500 bg-violet-500/15 text-violet-200",
                      },
                      {
                        id: "unlisted" as const,
                        title: "Không công khai",
                        desc: "Chỉ người có link mới xem được",
                        icon: Link2,
                        activeCls:
                          "border-cyan-500 bg-cyan-500/15 text-cyan-200",
                      },
                      {
                        id: "schedule_golden" as const,
                        title: "Hẹn giờ đăng",
                        desc: "Tự phát sóng đúng giờ hẹn",
                        icon: Clock,
                        activeCls:
                          "border-amber-500 bg-amber-500/15 text-amber-200",
                      },
                      {
                        id: "public_now" as const,
                        title: "Công khai (Public)",
                        desc: "Đăng ngay lên kênh cho mọi người",
                        icon: Globe,
                        activeCls:
                          "border-emerald-500 bg-emerald-500/15 text-emerald-200",
                      },
                    ] as const
                  ).map((m) => {
                    const Icon = m.icon;
                    const active = selectedPublishMode === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        onClick={() => {
                          setSelectedPublishMode(m.id);
                          setConfirmPublicNow(false);
                        }}
                        className={`rounded-xl border p-3 text-left transition cursor-pointer ${
                          active
                            ? `${m.activeCls} shadow-md`
                            : "border-zinc-800 bg-zinc-950/80 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="inline-flex items-center gap-1.5 text-xs font-extrabold text-white">
                            <Icon className="h-3.5 w-3.5 shrink-0" />
                            {m.title}
                          </span>
                          {active && (
                            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
                          )}
                        </div>
                        <p className="text-[10px] opacity-85 mt-1 leading-snug">
                          {m.desc}
                        </p>
                      </button>
                    );
                  })}
                </div>

                {selectedPublishMode === "schedule_golden" && (
                  <div className="rounded-xl border border-amber-500/35 bg-amber-950/15 p-3 flex flex-wrap items-center justify-between gap-3">
                    <div className="space-y-0.5">
                      <span className="text-xs font-bold text-amber-200">
                        Chọn ngày & giờ tự động Công khai (Giờ máy Mac của bạn):
                      </span>
                      <p className="text-[11px] text-zinc-400">
                        Khung giờ vàng đề xuất cho tệp khán giả Mỹ:{" "}
                        <strong className="text-amber-300">17:15 – 19:00 VN</strong>
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <input
                        type="datetime-local"
                        value={customScheduleLocal}
                        onChange={(e) => setCustomScheduleLocal(e.target.value)}
                        className="rounded-xl border border-amber-500/40 bg-zinc-950 px-3 py-1.5 text-xs font-bold text-white focus:border-amber-400 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() =>
                          setCustomScheduleLocal(
                            computeDefaultLocalScheduleInput()
                          )
                        }
                        className="rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-[11px] font-semibold text-amber-300 cursor-pointer"
                      >
                        Đặt 17:15 tiếp theo
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* 4.2 CHỌN DANH SÁCH PHÁT (PLAYLIST) */}
              <div className="space-y-2">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <label className="inline-flex items-center gap-1.5 text-xs font-extrabold text-zinc-200">
                    <ListVideo className="h-3.5 w-3.5 text-sky-400" />
                    4.2 Thêm vào Danh sách phát (Playlist):
                  </label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowCreatePlaylist((v) => !v)}
                      className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-400 hover:text-emerald-300 cursor-pointer"
                    >
                      <FolderPlus className="h-3.5 w-3.5" />
                      {showCreatePlaylist ? "Đóng tạo mới" : "+ Tạo Playlist mới"}
                    </button>
                    {isStudioConnected && (
                      <button
                        type="button"
                        onClick={() => void loadPlaylists(true)}
                        disabled={playlistsLoading}
                        className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white cursor-pointer"
                        title="Tải lại danh sách Playlist từ kênh"
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${
                            playlistsLoading ? "animate-spin text-sky-400" : ""
                          }`}
                        />
                        Làm mới
                      </button>
                    )}
                  </div>
                </div>

                <select
                  value={selectedPlaylistId}
                  onChange={(e) => setSelectedPlaylistId(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-xs font-semibold text-white focus:border-emerald-500 focus:outline-none cursor-pointer"
                >
                  <option value="">
                    — Không thêm vào danh sách phát (Playlist) —
                  </option>
                  {playlists.map((pl) => (
                    <option key={pl.id} value={pl.id}>
                      📂 {pl.title} ({pl.itemCount} video • {pl.privacyStatus})
                    </option>
                  ))}
                </select>

                {showCreatePlaylist && (
                  <div className="rounded-xl border border-emerald-500/35 bg-zinc-950/90 p-3 flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
                    <input
                      type="text"
                      value={newPlaylistTitle}
                      onChange={(e) => setNewPlaylistTitle(e.target.value)}
                      placeholder="Nhập tên Playlist mới (VD: Cosmic Mysteries)..."
                      className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-emerald-500 focus:outline-none"
                    />
                    <button
                      type="button"
                      disabled={creatingPlaylist || !newPlaylistTitle.trim()}
                      onClick={() => void handleCreateNewPlaylist()}
                      className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-3.5 py-2 text-xs font-extrabold text-white cursor-pointer"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      {creatingPlaylist ? "Đang tạo..." : "Tạo trên Studio"}
                    </button>
                  </div>
                )}
              </div>

              {/* 4.3 KHAI BÁO TUÂN THỦ CHUẨN YOUTUBE STUDIO (MẶC ĐỊNH: KHÔNG QUẢNG CÁO, KHÔNG TRẺ EM, KHÔNG AI) */}
              <div className="space-y-2">
                <span className="block text-xs font-extrabold text-zinc-200">
                  4.3 Tùy chọn khai báo YouTube Studio (Đã đặt mặc định chuẩn):
                </span>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
                  {/* Paid Promotion: Default NO */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 space-y-2">
                    <div>
                      <div className="text-xs font-bold text-white">
                        Quảng cáo / Tài trợ trả phí
                      </div>
                      <p className="text-[10px] text-zinc-400">
                        Paid promotion &amp; sponsorship
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        onClick={() => setHasPaidProductPlacement(false)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-extrabold transition cursor-pointer ${
                          !hasPaidProductPlacement
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        ✓ Không (Mặc định)
                      </button>
                      <button
                        type="button"
                        onClick={() => setHasPaidProductPlacement(true)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-bold transition cursor-pointer ${
                          hasPaidProductPlacement
                            ? "bg-amber-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        Có quảng cáo
                      </button>
                    </div>
                  </div>

                  {/* Made for Kids: Default NO */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 space-y-2">
                    <div>
                      <div className="text-xs font-bold text-white">
                        Đối tượng trẻ em (COPPA)
                      </div>
                      <p className="text-[10px] text-zinc-400">
                        Giữ bật Bình luận &amp; Đề xuất
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        onClick={() => setSelfDeclaredMadeForKids(false)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-extrabold transition cursor-pointer ${
                          !selfDeclaredMadeForKids
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        ✓ Không cho trẻ em
                      </button>
                      <button
                        type="button"
                        onClick={() => setSelfDeclaredMadeForKids(true)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-bold transition cursor-pointer ${
                          selfDeclaredMadeForKids
                            ? "bg-amber-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        Dành cho trẻ em
                      </button>
                    </div>
                  </div>

                  {/* Altered / Synthetic AI Content: Default NO */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 space-y-2">
                    <div>
                      <div className="text-xs font-bold text-white">
                        Nội dung tạo bằng AI
                      </div>
                      <p className="text-[10px] text-zinc-400">
                        Altered or synthetic media
                      </p>
                    </div>
                    <div className="grid grid-cols-2 gap-1.5">
                      <button
                        type="button"
                        onClick={() => setContainsSyntheticMedia(false)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-extrabold transition cursor-pointer ${
                          !containsSyntheticMedia
                            ? "bg-emerald-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        ✓ Không dùng AI
                      </button>
                      <button
                        type="button"
                        onClick={() => setContainsSyntheticMedia(true)}
                        className={`rounded-lg py-1.5 px-2 text-[11px] font-bold transition cursor-pointer ${
                          containsSyntheticMedia
                            ? "bg-amber-600 text-white"
                            : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                        }`}
                      >
                        Có dùng AI
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* 4.4 PRIMARY PUBLISH / UPDATE ACTION BUTTON */}
              {!isStudioConnected ? (
                <div className="rounded-xl border border-amber-500/40 bg-amber-950/20 p-4 flex items-center justify-between gap-3 text-xs">
                  <span className="text-amber-200 font-semibold">
                    Chưa kết nối quyền ghi YouTube Studio. Hãy cấp quyền 1-Click để Lưu Draft &amp; Đăng video trực tiếp!
                  </span>
                  <a
                    href="/api/youtube/oauth/start"
                    className="shrink-0 rounded-xl bg-amber-500 hover:bg-amber-400 px-4 py-2 font-extrabold text-zinc-950"
                  >
                    Cấp Quyền Ngay
                  </a>
                </div>
              ) : (
                <div className="pt-1 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                  <button
                    type="button"
                    disabled={publishingMode !== null}
                    onClick={() =>
                      void executePublishAction(selectedPublishMode)
                    }
                    onBlur={() => setConfirmPublicNow(false)}
                    className={`flex-1 inline-flex items-center justify-center gap-2 rounded-xl px-5 py-3.5 text-sm font-extrabold transition cursor-pointer disabled:opacity-50 shadow-lg ${
                      confirmPublicNow
                        ? "bg-red-600 hover:bg-red-500 text-white ring-2 ring-red-400 shadow-red-600/30"
                        : selectedPublishMode === "public_now"
                        ? "bg-gradient-to-r from-red-600 to-rose-500 hover:from-red-500 hover:to-rose-400 text-white shadow-red-600/25"
                        : selectedPublishMode === "schedule_golden"
                        ? "bg-gradient-to-r from-amber-600 to-orange-500 hover:from-amber-500 hover:to-orange-400 text-white shadow-amber-600/25"
                        : selectedPublishMode === "unlisted"
                        ? "bg-cyan-600 hover:bg-cyan-500 text-white shadow-cyan-600/25"
                        : "bg-violet-600 hover:bg-violet-500 text-white shadow-violet-600/25"
                    }`}
                  >
                    {publishingMode !== null ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" />
                        {selectedEp.youtubeState.status !== "unposted" &&
                        !forceReuploadMp4
                          ? "Đang cập nhật lên YouTube Studio..."
                          : "Đang xử lý ảnh bìa & tải video lên YouTube Studio..."}
                      </>
                    ) : confirmPublicNow ? (
                      <>
                        <Rocket className="h-4 w-4" />
                        Bấm Lần Nữa Để Xác Nhận Đăng CÔNG KHAI Ngay!
                      </>
                    ) : (
                      <>
                        {selectedPublishMode === "public_now" ? (
                          <Globe className="h-4 w-4" />
                        ) : selectedPublishMode === "schedule_golden" ? (
                          <Clock className="h-4 w-4" />
                        ) : selectedPublishMode === "unlisted" ? (
                          <Link2 className="h-4 w-4" />
                        ) : (
                          <Lock className="h-4 w-4" />
                        )}
                        {selectedEp.youtubeState.status !== "unposted" &&
                        !forceReuploadMp4
                          ? selectedPublishMode === "public_now"
                            ? "Cập Nhật & Chuyển Sang Công Khai Trên Studio"
                            : selectedPublishMode === "schedule_golden"
                            ? "Cập Nhật & Lưu Lịch Hẹn Giờ Trên Studio"
                            : selectedPublishMode === "unlisted"
                            ? "Cập Nhật Chế Độ Không Công Khai Trên Studio"
                            : "Cập Nhật Chế Độ Riêng Tư / Bản Nháp Trên Studio"
                          : selectedPublishMode === "public_now"
                          ? "Đăng Video Công Khai Ngay Lên YouTube"
                          : selectedPublishMode === "schedule_golden"
                          ? "Tải Lên Studio & Đặt Lịch Hẹn Giờ Phát"
                          : selectedPublishMode === "unlisted"
                          ? "Tải Lên Studio (Chế Độ Không Công Khai)"
                          : "Tải Lên Studio (Chế Độ Riêng Tư / Bản Nháp)"}
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* FULLSCREEN IMAGE ZOOM MODAL FOR THUMBNAILS & QC SHEETS */}
      {zoomedImageUrl && (
        <div
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => setZoomedImageUrl(null)}
        >
          <div
            className="relative max-w-4xl max-h-[92vh] rounded-2xl border border-zinc-700 bg-zinc-950 p-3 flex flex-col gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-4 px-2">
              <span className="text-xs font-bold text-white truncate">
                {zoomedImageUrl.label}
              </span>
              <button
                type="button"
                onClick={() => setZoomedImageUrl(null)}
                className="rounded-lg bg-zinc-800 hover:bg-zinc-700 p-1.5 text-zinc-200 cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <img
              src={zoomedImageUrl.url}
              alt={zoomedImageUrl.label}
              className="max-h-[82vh] w-auto object-contain rounded-xl mx-auto"
            />
          </div>
        </div>
      )}
    </div>
  );
}
