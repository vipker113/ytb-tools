"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Clock,
  ExternalLink,
  Layers,
  Radio,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  BacklotEpisodeDetail,
  BacklotEpisodeSummary,
  StudioGateName,
} from "@/lib/backlot";

interface StudioBacklotTabProps {
  onNotify: (msg: string) => void;
  onPendingCountChange?: (pendingCount: number, totalCount: number) => void;
}

const GATE_LABELS: Array<{ key: StudioGateName; label: string }> = [
  { key: "feasibility", label: "Feasibility" },
  { key: "voice_lock", label: "Khóa giọng" },
  { key: "storyboard_approval", label: "Storyboard" },
  { key: "render_master", label: "Render" },
  { key: "qa_six_pillar", label: "QA 6 trụ" },
  { key: "publish", label: "Publish" },
];

function mediaClassStyle(cls: string): { label: string; className: string } {
  switch (cls) {
    case "REAL_VIDEO_ACTION":
      return {
        label: "Cảnh thật • Hành động",
        className:
          "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
      };
    case "REAL_VIDEO_ESTABLISHING":
      return {
        label: "Cảnh thật • Thiết lập",
        className: "bg-teal-500/15 text-teal-300 border-teal-500/30",
      };
    case "STATIC_PHOTO_KEN_BURNS":
      return {
        label: "Ảnh tư liệu • Ken Burns",
        className: "bg-sky-500/15 text-sky-300 border-sky-500/30",
      };
    case "ANIMATED_STILL_OR_PAN":
      return {
        label: "Ảnh quét / Still động",
        className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
      };
    case "INFOGRAPHIC":
      return {
        label: "Đồ họa / Sci-Viz",
        className: "bg-purple-500/15 text-purple-300 border-purple-500/30",
      };
    default:
      return {
        label: cls || "Chưa phân loại",
        className: "bg-zinc-800 text-zinc-300 border-zinc-700",
      };
  }
}

function gatePillClass(status: string): string {
  if (status === "passed" || status === "approved") {
    return "bg-emerald-500/15 text-emerald-300 border-emerald-500/35";
  }
  if (status === "blocked" || status === "failed") {
    return "bg-rose-500/15 text-rose-300 border-rose-500/35";
  }
  if (status === "changes_requested" || status === "stale_hash_mismatch") {
    return "bg-amber-500/15 text-amber-300 border-amber-500/35";
  }
  if (status === "not_required" || status === "skipped") {
    return "bg-zinc-800/80 text-zinc-400 border-zinc-700/70";
  }
  return "bg-zinc-900 text-zinc-400 border-zinc-800";
}

function approvalBadge(
  status: BacklotEpisodeSummary["approvalStatus"],
  required: boolean
): { text: string; className: string } {
  if (status === "approved") {
    return {
      text: "Đã duyệt Storyboard",
      className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    };
  }
  if (status === "changes_requested") {
    return {
      text: "Cần sửa theo ghi chú",
      className: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    };
  }
  if (status === "stale_hash_mismatch") {
    return {
      text: "Lệch hash • Duyệt lại",
      className: "bg-rose-500/15 text-rose-300 border-rose-500/30",
    };
  }
  if (required) {
    return {
      text: "Chờ duyệt Master",
      className: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
    };
  }
  return {
    text: "Không bắt buộc khóa",
    className: "bg-zinc-800 text-zinc-400 border-zinc-700",
  };
}

export function StudioBacklotTab({
  onNotify,
  onPendingCountChange,
}: StudioBacklotTabProps) {
  const [episodes, setEpisodes] = useState<BacklotEpisodeSummary[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [detail, setDetail] = useState<BacklotEpisodeDetail | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sseConnected, setSseConnected] = useState(false);

  const [overallNotes, setOverallNotes] = useState("");
  const [shotNotes, setShotNotes] = useState<Record<string, string>>({});
  const hydratedSlugRef = useRef<string | null>(null);

  const loadEpisodesAsync = useCallback(async () => {
    try {
      const res = await fetch("/api/backlot", { cache: "no-store" });
      if (!res.ok) return;
      const json = (await res.json()) as {
        episodes?: BacklotEpisodeSummary[];
      };
      const list = json.episodes || [];
      setEpisodes(list);
      const pendingCount = list.filter(
        (e) =>
          e.requireStoryboardApproval && e.approvalStatus !== "approved"
      ).length;
      onPendingCountChange?.(pendingCount, list.length);

      setSelectedSlug((prev) => {
        if (prev && list.some((e) => e.slug === prev)) return prev;
        return list[0]?.slug || null;
      });
    } finally {
      setLoadingList(false);
    }
  }, [onPendingCountChange]);

  const loadEpisodeDetailAsync = useCallback(
    async (slug: string, forceNotesReset = false) => {
      try {
        const res = await fetch(`/api/backlot/${encodeURIComponent(slug)}`, {
          cache: "no-store",
        });
        if (!res.ok) return;
        const data = (await res.json()) as BacklotEpisodeDetail;
        setDetail(data);

        if (hydratedSlugRef.current !== slug || forceNotesReset) {
          hydratedSlugRef.current = slug;
          setOverallNotes(data.board?.approval?.notes || "");
          const initialShotNotes: Record<string, string> = {};
          for (const sh of data.board?.shots || []) {
            if (sh.reviewer_note) {
              initialShotNotes[sh.sid] = sh.reviewer_note;
            }
          }
          setShotNotes(initialShotNotes);
        }
      } finally {
        setLoadingDetail(false);
      }
    },
    []
  );

  useEffect(() => {
    void loadEpisodesAsync();
  }, [loadEpisodesAsync]);

  useEffect(() => {
    if (!selectedSlug) return;
    void loadEpisodeDetailAsync(selectedSlug, false);
  }, [selectedSlug, loadEpisodeDetailAsync]);

  // Live SSE subscription (`fs.watch` debounced 300ms -> < 2s auto-refresh without F5)
  useEffect(() => {
    if (!selectedSlug) return;
    const es = new EventSource(
      `/api/backlot/${encodeURIComponent(selectedSlug)}/events`
    );

    const onConnected = () => setSseConnected(true);
    const onChanged = () => {
      void loadEpisodeDetailAsync(selectedSlug, false);
      void loadEpisodesAsync();
    };

    es.addEventListener("connected", onConnected);
    es.addEventListener("changed", onChanged);
    es.onerror = () => setSseConnected(false);

    return () => {
      es.removeEventListener("connected", onConnected);
      es.removeEventListener("changed", onChanged);
      es.close();
      setSseConnected(false);
    };
  }, [selectedSlug, loadEpisodeDetailAsync, loadEpisodesAsync]);

  const handleSubmitDecision = async (
    decision: "approved" | "changes_requested"
  ) => {
    if (!selectedSlug || !detail?.board) return;
    setSubmitting(true);
    try {
      const res = await fetch(
        `/api/backlot/${encodeURIComponent(selectedSlug)}/approve`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            gate: "storyboard_approval",
            decision,
            notes: overallNotes,
            shotNotes,
          }),
        }
      );
      const json = (await res.json()) as {
        ok?: boolean;
        message?: string;
        error?: string;
        detail?: BacklotEpisodeDetail;
      };
      if (!res.ok) {
        onNotify(json.error || "Không thể lưu quyết định Storyboard.");
        return;
      }
      if (json.detail) {
        setDetail(json.detail);
      }
      void loadEpisodesAsync();
      onNotify(
        json.message ||
          (decision === "approved"
            ? "Đã duyệt Storyboard!"
            : "Đã gửi yêu cầu chỉnh sửa Storyboard!")
      );
    } catch {
      onNotify("Lỗi kết nối khi lưu quyết định Storyboard.");
    } finally {
      setSubmitting(false);
    }
  };

  const board = detail?.board || null;
  const cacheBust = encodeURIComponent(
    board?.exported_at || detail?.summary.updatedAtIso || "0"
  );

  const activeShotNotesCount = useMemo(
    () =>
      Object.values(shotNotes).filter((v) => typeof v === "string" && v.trim())
        .length,
    [shotNotes]
  );

  const reversedEvents = useMemo(
    () => [...(detail?.recentEvents || [])].reverse(),
    [detail?.recentEvents]
  );

  return (
    <div className="space-y-4">
      {/* Top Studio Backlot Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-zinc-800/90 bg-zinc-900/60 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400 border border-indigo-500/30">
            <Clapperboard className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-white">
                Studio Backlot — Bàn Dựng & Cổng Duyệt Storyboard (v9)
              </h1>
              <span
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${
                  sseConnected
                    ? "border-emerald-500/35 bg-emerald-500/10 text-emerald-300"
                    : "border-zinc-700 bg-zinc-800 text-zinc-400"
                }`}
              >
                <Radio className="h-2.5 w-2.5" />
                {sseConnected ? "Live SSE (<2s)" : "Offline"}
              </span>
            </div>
            <p className="text-xs text-zinc-400">
              Duyệt filmstrip 3 khung hình/shot, kiểm tra bản quyền + lớp Manim
              alpha + điểm CLIP và mở khóa render Master (chế độ chỉ xem &
              duyệt an toàn).
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => {
            setLoadingList(true);
            void loadEpisodesAsync();
            if (selectedSlug) {
              setLoadingDetail(true);
              void loadEpisodeDetailAsync(selectedSlug, true);
            }
          }}
          className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:bg-zinc-800 cursor-pointer"
        >
          <RefreshCw
            className={`h-3.5 w-3.5 ${
              loadingList || loadingDetail ? "animate-spin" : ""
            }`}
          />
          Làm mới
        </button>
      </div>

      {episodes.length === 0 && !loadingList ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-8 text-center space-y-2">
          <div className="text-sm font-semibold text-zinc-200">
            Chưa có tập nào xuất Storyboard sang Studio Backlot
          </div>
          <p className="text-xs text-zinc-400 max-w-xl mx-auto">
            Chạy lệnh{" "}
            <code className="rounded bg-zinc-800 px-1.5 py-0.5 text-indigo-300">
              PYTHONPATH=pipeline .venv/bin/python -m pow_studio.cli
              export-storyboard -m episodes/&lt;tap&gt;.yaml
            </code>{" "}
            trong terminal để đẩy toàn bộ filmstrip IN/MID/OUT lên bàn dựng.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-4 items-start">
          {/* LEFT COLUMN: Episode List + 6-Gate Progress Rail */}
          <div className="xl:col-span-3 space-y-4">
            <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3 space-y-2.5">
              <div className="flex items-center justify-between px-1">
                <span className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Danh sách tập ({episodes.length})
                </span>
                <span className="text-[11px] text-zinc-500">
                  Kể cả chưa có MP4
                </span>
              </div>

              <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                {episodes.map((ep) => {
                  const active = ep.slug === selectedSlug;
                  const badge = approvalBadge(
                    ep.approvalStatus,
                    ep.requireStoryboardApproval
                  );
                  return (
                    <button
                      key={ep.slug}
                      type="button"
                      onClick={() => {
                        if (ep.slug !== selectedSlug) {
                          setLoadingDetail(true);
                          setSelectedSlug(ep.slug);
                        }
                      }}
                      className={`w-full text-left rounded-xl border p-2.5 transition cursor-pointer space-y-1.5 ${
                        active
                          ? "border-indigo-500/60 bg-indigo-500/10"
                          : "border-zinc-800 bg-zinc-950/60 hover:border-zinc-700"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-xs font-semibold text-white line-clamp-2">
                          {ep.primaryTitle}
                        </div>
                        <span className="shrink-0 rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-mono text-zinc-300">
                          v{ep.manifestVersion}
                        </span>
                      </div>

                      <div className="text-[11px] font-mono text-zinc-400 truncate">
                        {ep.slug}
                      </div>

                      <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                        <span
                          className={`rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${badge.className}`}
                        >
                          {badge.text}
                        </span>
                        <span
                          className={`rounded-md border px-1.5 py-0.5 text-[10px] ${
                            ep.hasRenderedMp4
                              ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                              : "border-amber-500/25 bg-amber-500/10 text-amber-300"
                          }`}
                        >
                          {ep.hasRenderedMp4 ? "Đã có MP4" : "Tiền kỳ (0 MP4)"}
                        </span>
                        {ep.shotCount > 0 && (
                          <span className="text-[10px] text-zinc-400">
                            {ep.shotCount} shots
                          </span>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 6-Gate Progress Bar */}
            {detail && (
              <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3.5 space-y-2.5">
                <div className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Tiến Trình 6 Cổng Sản Xuất
                </div>
                <div className="space-y-1.5">
                  {GATE_LABELS.map((g, idx) => {
                    const entry = detail.summary.gates[g.key] || {
                      status: "pending",
                    };
                    return (
                      <div
                        key={g.key}
                        className={`rounded-xl border px-2.5 py-2 ${gatePillClass(
                          entry.status
                        )}`}
                      >
                        <div className="flex items-center justify-between gap-2 text-xs font-semibold">
                          <span>
                            {idx + 1}. {g.label}
                          </span>
                          <span className="text-[10px] uppercase font-mono">
                            {entry.status}
                          </span>
                        </div>
                        {entry.detail && (
                          <div className="mt-0.5 text-[10px] opacity-80 truncate">
                            {entry.detail}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* CENTER COLUMN: Storyboard Filmstrip */}
          <div className="xl:col-span-6 space-y-3">
            {!board ? (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 text-center space-y-2">
                <div className="text-sm font-semibold text-zinc-200">
                  Tập <span className="font-mono">{selectedSlug}</span> mới có{" "}
                  <code>studio_state.json</code> nhưng chưa xuất{" "}
                  <code>storyboard_board.json</code>.
                </div>
                <p className="text-xs text-zinc-400">
                  Chạy <code>export-storyboard -m episodes/...</code> để dựng
                  filmstrip 3 khung hình/shot.
                </p>
              </div>
            ) : (
              <>
                {/* Board Metadata Bar */}
                <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/60 p-3.5 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <div className="text-sm font-bold text-white">
                        {board.primary_title}
                      </div>
                      <div className="text-[11px] text-zinc-400">
                        {board.playlist} • {board.shot_count} shots •{" "}
                        {board.total_duration_s.toFixed(2)}s • Profile:{" "}
                        <span className="font-mono text-zinc-300">
                          {board.style_profile}
                        </span>{" "}
                        • Corpus:{" "}
                        <span className="font-mono text-indigo-300">
                          {board.visual_corpus_mode}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-[11px] font-mono text-cyan-300">
                      sha256: {board.storyboard_sha256.slice(0, 14)}…
                    </div>
                  </div>

                  {board.approval.status === "stale_hash_mismatch" && (
                    <div className="flex items-center gap-2 rounded-xl border border-rose-500/40 bg-rose-500/10 px-3 py-2 text-xs text-rose-200">
                      <ShieldAlert className="h-4 w-4 shrink-0 text-rose-400" />
                      <span>
                        Storyboard đã thay đổi sau lần duyệt trước (
                        <code className="font-mono">
                          {(board.approval.approved_storyboard_sha256 || "").slice(
                            0,
                            10
                          )}
                        </code>{" "}
                        →{" "}
                        <code className="font-mono">
                          {board.storyboard_sha256.slice(0, 10)}
                        </code>
                        ). Render Master đang tự động khóa cho tới khi bạn duyệt
                        lại.
                      </span>
                    </div>
                  )}
                </div>

                {/* Shot Cards Filmstrip */}
                <div className="space-y-3">
                  {board.shots.map((sh) => {
                    const clsBadge = mediaClassStyle(sh.media_class);
                    const noteVal = shotNotes[sh.sid] ?? "";
                    return (
                      <div
                        key={sh.sid}
                        className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3.5 space-y-3"
                      >
                        {/* Card Top Header */}
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="rounded-lg bg-zinc-800 px-2 py-0.5 text-xs font-bold font-mono text-white">
                              #{sh.index} {sh.sid}
                            </span>
                            <span className="inline-flex items-center gap-1 text-xs font-mono text-zinc-300">
                              <Clock className="h-3 w-3 text-zinc-400" />
                              {sh.start_s.toFixed(2)}s → {sh.end_s.toFixed(2)}s
                              ({sh.duration_s.toFixed(2)}s)
                            </span>
                            {sh.story_beat && (
                              <span className="rounded-md bg-indigo-500/15 border border-indigo-500/30 px-2 py-0.5 text-[11px] font-medium text-indigo-300">
                                {sh.story_beat}
                              </span>
                            )}
                            <span className="rounded-md bg-zinc-800/80 px-1.5 py-0.5 text-[10px] font-mono text-zinc-400">
                              {sh.transition_in}
                              {sh.transition_duration_s > 0
                                ? ` (${sh.transition_duration_s}s)`
                                : ""}
                            </span>
                          </div>

                          <span
                            className={`rounded-md border px-2 py-0.5 text-[11px] font-semibold ${clsBadge.className}`}
                          >
                            {clsBadge.label}
                          </span>
                        </div>

                        {/* 3-Frame Filmstrip (IN / MID / OUT) */}
                        <div className="grid grid-cols-3 gap-2">
                          {(["in", "mid", "out"] as const).map((pos) => {
                            const rel = sh.frames[pos];
                            return (
                              <div
                                key={pos}
                                className="relative overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950 aspect-[9/16]"
                              >
                                {rel ? (
                                  /* eslint-disable-next-line @next/next/no-img-element */
                                  <img
                                    src={`/api/backlot/media?slug=${encodeURIComponent(
                                      board.slug
                                    )}&file=${encodeURIComponent(
                                      rel
                                    )}&v=${cacheBust}`}
                                    alt={`${sh.sid} ${pos}`}
                                    loading="lazy"
                                    className="h-full w-full object-cover"
                                  />
                                ) : (
                                  <div className="flex h-full items-center justify-center text-[11px] text-zinc-600">
                                    Không có frame
                                  </div>
                                )}
                                <span className="absolute left-1.5 top-1.5 rounded bg-black/75 px-1.5 py-0.5 text-[9px] font-mono uppercase text-zinc-200">
                                  {pos}
                                </span>
                              </div>
                            );
                          })}
                        </div>

                        {/* Spoken Narration */}
                        <div className="rounded-xl bg-zinc-950/70 border border-zinc-800/80 px-3 py-2 text-xs text-zinc-200 leading-relaxed">
                          <span className="text-zinc-500 font-semibold mr-1.5">
                            Lời dẫn:
                          </span>
                          “{sh.narration_text || sh.visual_desc || "—"}”
                        </div>

                        {/* Provenance + CLIP + Overlay + QA Badges */}
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span className="rounded-md border border-zinc-700/80 bg-zinc-950 px-2 py-0.5 font-mono text-zinc-300">
                            {sh.src_file} (in={sh.src_in}s)
                          </span>
                          <span className="rounded-md border border-zinc-700/80 bg-zinc-950 px-2 py-0.5 text-zinc-300">
                            {sh.license}
                            {sh.creator_agency ? ` • ${sh.creator_agency}` : ""}
                          </span>
                          {sh.source_page_url && (
                            <a
                              href={sh.source_page_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-sky-300 hover:bg-zinc-800"
                            >
                              Nguồn <ExternalLink className="h-2.5 w-2.5" />
                            </a>
                          )}
                          {sh.clip_percentile !== null && (
                            <span className="rounded-md border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 font-mono text-cyan-300">
                              CLIP p{Math.round(sh.clip_percentile * 100)}
                            </span>
                          )}
                          {sh.overlays.map((ov) => (
                            <span
                              key={ov.overlay_id}
                              className="inline-flex items-center gap-1 rounded-md border border-amber-500/35 bg-amber-500/15 px-2 py-0.5 font-medium text-amber-200"
                            >
                              <Layers className="h-3 w-3" />
                              OV: {ov.template}
                              {typeof ov.max_alpha_area_ratio === "number"
                                ? ` (${(ov.max_alpha_area_ratio * 100).toFixed(
                                    1
                                  )}% α)`
                                : ""}
                            </span>
                          ))}
                          {sh.possible_mislabeled_asset && (
                            <span className="inline-flex items-center gap-1 rounded-md border border-rose-500/40 bg-rose-500/15 px-2 py-0.5 font-semibold text-rose-300">
                              <AlertTriangle className="h-3 w-3" />
                              Nghi lệch nhãn CLIP
                            </span>
                          )}
                        </div>

                        {sh.qa_issues.length > 0 && (
                          <div className="space-y-1 rounded-xl border border-amber-500/30 bg-amber-500/10 p-2 text-[11px] text-amber-200">
                            {sh.qa_issues.map((iss, idx) => (
                              <div key={idx}>
                                [{iss.severity}] {iss.code}: {iss.message}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Per-Shot Reviewer Note Input */}
                        <div>
                          <input
                            type="text"
                            value={noteVal}
                            onChange={(e) =>
                              setShotNotes((prev) => ({
                                ...prev,
                                [sh.sid]: e.target.value,
                              }))
                            }
                            placeholder={`Ghi chú đạo diễn cho ${sh.sid} (vd: đổi sang cảnh cận hơn, lùi src_in +2s, chỉnh vị trí overlay...)`}
                            className="w-full rounded-xl border border-zinc-800 bg-zinc-950/90 px-3 py-1.5 text-xs text-zinc-100 placeholder:text-zinc-500 focus:border-indigo-500 focus:outline-none"
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            )}
          </div>

          {/* RIGHT COLUMN: Mobile Thumbnails (160x284) + QA Summary + Approve Gate + Live Event Feed */}
          <div className="xl:col-span-3 space-y-4">
            {/* Approval Decision Card */}
            {board && (
              <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/60 p-3.5 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                    Cổng Duyệt Storyboard
                  </span>
                  {activeShotNotesCount > 0 && (
                    <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                      {activeShotNotesCount} shot có ghi chú
                    </span>
                  )}
                </div>

                <textarea
                  rows={3}
                  value={overallNotes}
                  onChange={(e) => setOverallNotes(e.target.value)}
                  placeholder="Ghi chú tổng thể cho tập (tùy chọn)..."
                  className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-100 placeholder:text-zinc-500 focus:border-indigo-500 focus:outline-none"
                />

                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    disabled={submitting || detail?.summary.isProtectedCompleted}
                    onClick={() => void handleSubmitDecision("approved")}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-3 py-2 text-xs font-bold text-white cursor-pointer"
                  >
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    Duyệt Master
                  </button>
                  <button
                    type="button"
                    disabled={submitting || detail?.summary.isProtectedCompleted}
                    onClick={() =>
                      void handleSubmitDecision("changes_requested")
                    }
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/15 hover:bg-amber-500/25 disabled:opacity-50 px-3 py-2 text-xs font-bold text-amber-200 cursor-pointer"
                  >
                    <XCircle className="h-3.5 w-3.5" />
                    Yêu cầu sửa
                  </button>
                </div>

                {board.approval.approved_at && (
                  <div className="text-[11px] text-zinc-400">
                    Lần lưu gần nhất:{" "}
                    <span className="font-mono text-zinc-300">
                      {new Date(board.approval.approved_at).toLocaleString(
                        "vi-VN"
                      )}
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Coverage & 6-Pillar QA Summary */}
            {board && (
              <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3.5 space-y-2.5">
                <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-zinc-400">
                  <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
                  Độ Thật Cảnh Quay & QA
                </div>

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl bg-zinc-950/80 border border-zinc-800 p-2">
                    <div className="text-[10px] text-zinc-400">
                      Cảnh quay thật
                    </div>
                    <div className="text-sm font-bold text-emerald-400">
                      {board.coverage_metrics.genuine_moving_footage_pct}%
                    </div>
                  </div>
                  <div className="rounded-xl bg-zinc-950/80 border border-zinc-800 p-2">
                    <div className="text-[10px] text-zinc-400">
                      Lớp Manim α
                    </div>
                    <div className="text-sm font-bold text-amber-300">
                      {board.coverage_metrics.mechanism_overlay_pct}%
                    </div>
                  </div>
                  <div className="rounded-xl bg-zinc-950/80 border border-zinc-800 p-2">
                    <div className="text-[10px] text-zinc-400">
                      Ảnh tĩnh Ken Burns
                    </div>
                    <div className="text-sm font-bold text-sky-300">
                      {board.coverage_metrics.static_image_pct}%
                    </div>
                  </div>
                  <div className="rounded-xl bg-zinc-950/80 border border-zinc-800 p-2">
                    <div className="text-[10px] text-zinc-400">
                      Sci-Viz / Đồ họa
                    </div>
                    <div className="text-sm font-bold text-purple-300">
                      {board.coverage_metrics.scientific_visualization_pct}%
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/60 p-2.5 text-xs space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-400">QA 6 Trụ:</span>
                    <span
                      className={`font-bold ${
                        !board.qa_summary.six_pillar_present
                          ? "text-zinc-400"
                          : board.qa_summary.overall_release_approval
                          ? "text-emerald-400"
                          : "text-amber-300"
                      }`}
                    >
                      {!board.qa_summary.six_pillar_present
                        ? "Chưa chạy Stage 6"
                        : board.qa_summary.overall_release_approval
                        ? "PASS TOÀN DIỆN"
                        : `${board.qa_summary.issues_count} lưu ý`}
                    </span>
                  </div>
                  {board.qa_summary.issues.slice(0, 4).map((iss, i) => (
                    <div key={i} className="text-[11px] text-zinc-400 truncate">
                      • [{iss.severity}] {iss.message}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 3 Thumbnail Concepts in 160x284 Mobile Frames */}
            {board && board.thumbnail_concepts.length > 0 && (
              <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3.5 space-y-2.5">
                <div className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                  Thumbnail Kệ Điện Thoại (160×284)
                </div>
                <div className="flex flex-wrap gap-3 justify-center">
                  {board.thumbnail_concepts.slice(0, 3).map((tc) => (
                    <div key={tc.concept_id} className="space-y-1">
                      <div
                        style={{ width: 160, height: 284 }}
                        className="relative overflow-hidden rounded-2xl border-2 border-zinc-700 bg-zinc-950 shadow-lg"
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={`/api/backlot/media?slug=${encodeURIComponent(
                            board.slug
                          )}&file=${encodeURIComponent(
                            tc.file
                          )}&v=${cacheBust}`}
                          alt={`Concept ${tc.concept_id}`}
                          className="h-full w-full object-cover"
                        />
                        <span className="absolute left-2 top-2 rounded bg-black/75 px-1.5 py-0.5 text-[10px] font-bold text-amber-300">
                          Concept {tc.concept_id}
                        </span>
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/55 to-transparent p-2">
                          <div className="text-[10px] font-semibold text-white line-clamp-2 leading-snug">
                            {board.primary_title}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Live Event Feed from studio_events.jsonl */}
            <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/50 p-3.5 space-y-2.5">
              <div className="text-xs font-bold uppercase tracking-wider text-zinc-400">
                Nhật Ký Pipeline ({reversedEvents.length})
              </div>
              <div className="max-h-72 overflow-y-auto space-y-1.5 pr-1">
                {reversedEvents.length === 0 ? (
                  <div className="text-xs text-zinc-500">
                    Chưa có sự kiện nào trong <code>studio_events.jsonl</code>.
                  </div>
                ) : (
                  reversedEvents.map((ev, idx) => (
                    <div
                      key={`${ev.ts}-${idx}`}
                      className="rounded-xl border border-zinc-800/80 bg-zinc-950/70 px-2.5 py-1.5 text-[11px]"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono font-semibold text-zinc-200 truncate">
                          {ev.stage}
                        </span>
                        <span className="text-[10px] font-mono uppercase text-zinc-400">
                          {ev.status}
                        </span>
                      </div>
                      {ev.detail && (
                        <div className="text-zinc-400 line-clamp-2 mt-0.5">
                          {ev.detail}
                        </div>
                      )}
                      <div className="text-[9px] font-mono text-zinc-500 mt-0.5">
                        {new Date(ev.ts).toLocaleTimeString("vi-VN")}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
