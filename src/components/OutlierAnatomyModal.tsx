"use client";

import {
  Activity,
  BookmarkPlus,
  CheckCircle2,
  Loader2,
  RefreshCw,
  Scissors,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import type {
  OutlierAnalysisMode,
  OutlierAnatomyBrief,
  OutlierStatusFile,
} from "@/lib/outlier-analysis";
import { formatNumber } from "@/lib/format";
import type { OutlierAnatomyRef, SavedIdea, VideoItem } from "@/lib/types";

interface OutlierAnatomyModalProps {
  video: VideoItem;
  onClose: () => void;
  onSaveIdeaWithAnatomy: (idea: Partial<SavedIdea>) => Promise<void>;
}

function sceneBarColor(cls: string): string {
  switch (cls) {
    case "REAL_VIDEO_ACTION":
      return "bg-emerald-500";
    case "REAL_VIDEO_ESTABLISHING":
      return "bg-teal-500";
    case "REAL_TIME_LAPSE":
      return "bg-cyan-400";
    case "ANIMATED_STILL":
      return "bg-amber-400";
    case "STILL_PHOTO":
      return "bg-sky-500";
    case "INFOGRAPHIC":
      return "bg-purple-500";
    default:
      return "bg-zinc-600";
  }
}

export function OutlierAnatomyModal({
  video,
  onClose,
  onSaveIdeaWithAnatomy,
}: OutlierAnatomyModalProps) {
  const [mode, setMode] = useState<OutlierAnalysisMode>("download");
  const [status, setStatus] = useState<OutlierStatusFile>({ status: "queued" });
  const [brief, setBrief] = useState<OutlierAnatomyBrief | null>(null);
  const [savedIdea, setSavedIdea] = useState(false);
  const [saving, setSaving] = useState(false);

  const triggerAnalysis = useCallback(
    async (selectedMode: OutlierAnalysisMode, force: boolean) => {
      const res = await fetch("/api/outlier-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          videoId: video.id,
          mode: selectedMode,
          force,
        }),
      });
      const json = (await res.json()) as {
        status?: OutlierStatusFile;
        brief?: OutlierAnatomyBrief | null;
        error?: string;
      };
      if (!res.ok) {
        setStatus({
          status: "failed",
          error: json.error || "Không thể chạy phân tích.",
        });
        return;
      }
      if (json.status) setStatus(json.status);
      if (json.brief) setBrief(json.brief);
    },
    [video.id]
  );

  useEffect(() => {
    let cancelled = false;
    let pollTimer: ReturnType<typeof setTimeout> | null = null;

    const startOrPoll = async () => {
      try {
        const res = await fetch(
          `/api/outlier-analysis?videoId=${encodeURIComponent(video.id)}`,
          { cache: "no-store" }
        );
        const data = (await res.json()) as {
          status?: OutlierStatusFile;
          brief?: OutlierAnatomyBrief | null;
        };
        if (cancelled) return;

        if (data.brief) {
          setBrief(data.brief);
          setStatus(data.status || { status: "completed" });
          return;
        }

        if (
          !data.status ||
          data.status.status === "idle"
        ) {
          await triggerAnalysis("download", false);
        } else {
          setStatus(data.status);
        }

        const poll = async () => {
          if (cancelled) return;
          const r = await fetch(
            `/api/outlier-analysis?videoId=${encodeURIComponent(video.id)}`,
            { cache: "no-store" }
          );
          if (!r.ok || cancelled) return;
          const d = (await r.json()) as {
            status?: OutlierStatusFile;
            brief?: OutlierAnatomyBrief | null;
          };
          if (cancelled) return;
          if (d.status) setStatus(d.status);
          if (d.brief) {
            setBrief(d.brief);
            return;
          }
          if (
            d.status?.status === "queued" ||
            d.status?.status === "running"
          ) {
            pollTimer = setTimeout(() => void poll(), 1500);
          }
        };

        pollTimer = setTimeout(() => void poll(), 1400);
      } catch {
        if (!cancelled) {
          setStatus({
            status: "failed",
            error: "Không thể kết nối API giải phẫu nhịp dựng.",
          });
        }
      }
    };

    void startOrPoll();
    return () => {
      cancelled = true;
      if (pollTimer) clearTimeout(pollTimer);
    };
  }, [video.id, triggerAnalysis]);

  const handleRerun = async () => {
    setBrief(null);
    setStatus({ status: "queued", detail: "Đang khởi chạy lại..." });
    await triggerAnalysis(mode, true);
    const pollLoop = async () => {
      const r = await fetch(
        `/api/outlier-analysis?videoId=${encodeURIComponent(video.id)}`,
        { cache: "no-store" }
      );
      if (!r.ok) return;
      const d = (await r.json()) as {
        status?: OutlierStatusFile;
        brief?: OutlierAnatomyBrief | null;
      };
      if (d.status) setStatus(d.status);
      if (d.brief) {
        setBrief(d.brief);
        return;
      }
      if (d.status?.status === "queued" || d.status?.status === "running") {
        setTimeout(() => void pollLoop(), 1500);
      }
    };
    setTimeout(() => void pollLoop(), 1400);
  };

  const handleSaveWithAnatomy = async () => {
    if (!brief) return;
    setSaving(true);
    try {
      const anatomyRef: OutlierAnatomyRef = {
        videoId: brief.target_id,
        analyzedAt: brief.analyzed_at,
        durationSec: brief.duration_s,
        cutCount: brief.cut_count,
        cutsPer10s: brief.cuts_per_10s_overall,
        medianShotDurationSec: brief.median_shot_duration_s,
        wordsPerSecond: brief.words_per_second_overall,
        openingHookType: brief.hook_and_loop.opening_hook_type,
        firstWordTimeSec: brief.hook_and_loop.first_word_time_s,
        realMovingPct: brief.visual_mix.real_moving_pct,
        loopSimilarityScore: brief.hook_and_loop.loop_similarity_score,
        whatWorks: brief.agent_annotations.what_works || [],
        differentiationSeeds:
          brief.agent_annotations.differentiation_seeds || [],
      };

      const coreKeyword =
        video.tags[0] || video.title.split(" ").slice(0, 5).join(" ");
      await onSaveIdeaWithAnatomy({
        title: `Ý tưởng từ Giải phẫu (${video.outlierScore.toFixed(1)}x): ${video.title}`,
        remakeTitle: `[Góc nhìn tư liệu thật PoW] ${video.title}`,
        targetKeyword: coreKeyword,
        sourceVideoId: video.id,
        sourceVideoTitle: video.title,
        sourceChannelTitle: video.channelTitle,
        sourceThumbnailUrl: video.thumbnailUrl,
        sourceOutlierScore: video.outlierScore,
        anatomyRef,
        format: video.isShort ? "short" : "long",
        status: "backlog",
        tags: video.tags.slice(0, 10),
        notes: [
          `• Gốc đạt ${formatNumber(video.views)} views (${video.outlierScore.toFixed(1)}x kênh ${video.channelTitle}).`,
          `• Nhịp dựng: ${brief.cut_count} cắt / ${brief.duration_s}s (trung vị ${brief.median_shot_duration_s ?? "—"}s/shot, ${brief.words_per_second_overall} từ/s, Hook=${brief.hook_and_loop.opening_hook_type}).`,
          ...(brief.agent_annotations.what_works || []).map(
            (w) => `• Điểm mạnh cấu trúc: ${w}`
          ),
          ...(brief.agent_annotations.differentiation_seeds || []).map(
            (s) => `• Hướng khác biệt PoW: ${s}`
          ),
        ].join("\n"),
      });
      setSavedIdea(true);
    } finally {
      setSaving(false);
    }
  };

  const isRunning =
    status.status === "queued" || status.status === "running";
  const cacheBust = encodeURIComponent(brief?.analyzed_at || "1");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-5xl max-h-[92vh] overflow-y-auto rounded-2xl border border-zinc-800 bg-zinc-950 text-zinc-100 shadow-2xl">
        {/* Sticky Header */}
        <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 bg-zinc-950/95 px-5 py-4 backdrop-blur">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Scissors className="h-4 w-4 text-amber-400 shrink-0" />
              <h3 className="text-sm font-bold text-white truncate">
                Giải Phẫu Nhịp Dựng Outlier — {video.title}
              </h3>
            </div>
            <div className="text-xs text-zinc-400 mt-0.5">
              {video.channelTitle} • {video.outlierScore.toFixed(1)}x Outlier •{" "}
              <span className="font-mono text-zinc-300">{video.id}</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <select
              value={mode}
              onChange={(e) => setMode(e.target.value as OutlierAnalysisMode)}
              className="rounded-xl border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-zinc-200"
            >
              <option value="download">480p tạm + tự xóa (Full nhịp + hình)</option>
              <option value="transcript_only">Chỉ phân tích Transcript</option>
            </select>

            <button
              type="button"
              disabled={isRunning}
              onClick={() => void handleRerun()}
              className="inline-flex items-center gap-1 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 px-3 py-1.5 text-xs font-medium text-zinc-200 cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${isRunning ? "animate-spin" : ""}`}
              />
              Phân tích lại
            </button>

            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="p-5 space-y-5">
          {isRunning && !brief && (
            <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-6 flex items-center gap-3 text-sm text-amber-200">
              <Loader2 className="h-5 w-5 animate-spin text-amber-400 shrink-0" />
              <div>
                <div className="font-semibold">
                  Đang giải phẫu nhịp dựng cục bộ ($0)...
                </div>
                <div className="text-xs text-amber-300/80 mt-0.5">
                  {status.detail ||
                    "Tải bản tạm <=480p -> PySceneDetect -> phân loại chuyển động -> tự động xóa video gốc."}
                </div>
              </div>
            </div>
          )}

          {status.status === "failed" && !brief && (
            <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 p-4 text-xs text-rose-200">
              Lỗi phân tích: {status.error || "Không xác định"}
            </div>
          )}

          {brief && (
            <>
              {/* Top Summary Cards + Clean-Room Auto-Delete Badge */}
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/10 px-3.5 py-2 text-xs text-emerald-200">
                <span className="inline-flex items-center gap-1.5 font-medium">
                  <ShieldCheck className="h-4 w-4 text-emerald-400" />
                  Chế độ nghiên cứu nội bộ: chỉ giữ chỉ số nhịp dựng + keyframe
                  nhỏ (media_deleted={String(brief.media_deleted)}). Không bao
                  giờ tái sử dụng cảnh hay câu chữ của đối thủ.
                </span>
                <span className="font-mono text-[11px] text-emerald-300">
                  {brief.scene_detector} • {brief.transcript_source}
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase text-zinc-400">
                    Tổng điểm cắt
                  </div>
                  <div className="text-base font-bold text-white mt-0.5">
                    {brief.cut_count} cắt{" "}
                    <span className="text-xs font-normal text-zinc-400">
                      ({brief.cuts_per_10s_overall ?? "—"}/10s)
                    </span>
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase text-zinc-400">
                    Shot trung vị
                  </div>
                  <div className="text-base font-bold text-amber-300 mt-0.5">
                    {brief.median_shot_duration_s ?? "—"}s
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase text-zinc-400">
                    Tốc độ lời dẫn
                  </div>
                  <div className="text-base font-bold text-cyan-300 mt-0.5">
                    {brief.words_per_second_overall} từ/s
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase text-zinc-400">
                    Loại Hook & Từ #1
                  </div>
                  <div className="text-xs font-bold text-indigo-300 mt-1">
                    {brief.hook_and_loop.opening_hook_type} •{" "}
                    {brief.hook_and_loop.first_word_time_s ?? "—"}s
                  </div>
                </div>
                <div className="rounded-xl border border-zinc-800 bg-zinc-900/70 p-3">
                  <div className="text-[10px] uppercase text-zinc-400">
                    Độ khép vòng lặp
                  </div>
                  <div className="text-base font-bold text-emerald-400 mt-0.5">
                    {brief.hook_and_loop.loop_similarity_score !== null
                      ? `${Math.round(
                          brief.hook_and_loop.loop_similarity_score * 100
                        )}%`
                      : "—"}
                  </div>
                </div>
              </div>

              {/* Cut Timeline Bar Colored by Motion Class */}
              {brief.scenes.length > 0 && (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="font-bold text-white flex items-center gap-1.5">
                      <Activity className="h-3.5 w-3.5 text-amber-400" />
                      Thanh Timeline Điểm Cắt Theo Lớp Chuyển Động ({brief.duration_s}s)
                    </span>
                    <div className="flex flex-wrap items-center gap-3 text-[11px] text-zinc-400">
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2.5 w-2.5 rounded-sm bg-emerald-500" />
                        Cảnh hành động thật
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2.5 w-2.5 rounded-sm bg-teal-500" />
                        Cảnh thiết lập
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2.5 w-2.5 rounded-sm bg-amber-400" />
                        Ảnh tĩnh/Pan
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="h-2.5 w-2.5 rounded-sm bg-purple-500" />
                        Đồ họa/Chữ dày
                      </span>
                    </div>
                  </div>

                  <div className="flex h-7 w-full overflow-hidden rounded-xl border border-zinc-800 bg-zinc-950">
                    {brief.scenes.map((sc) => {
                      const pct = Math.max(
                        0.8,
                        (sc.duration_s / Math.max(0.5, brief.duration_s)) * 100
                      );
                      return (
                        <div
                          key={sc.sid}
                          style={{ width: `${pct}%` }}
                          title={`${sc.sid}: ${sc.start_s}s–${sc.end_s}s (${sc.duration_s}s) • ${sc.motion_class}`}
                          className={`h-full border-r border-zinc-950/80 ${sceneBarColor(
                            sc.motion_class
                          )} opacity-90 hover:opacity-100 transition`}
                        />
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Phase Table + Comparison with Proof of Wonder Baseline */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
                <div className="lg:col-span-8 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 overflow-x-auto">
                  <div className="text-xs font-bold uppercase tracking-wider text-zinc-300 mb-2.5">
                    Chỉ Số Nhịp Dựng Theo 4 Pha
                  </div>
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-zinc-800 text-zinc-400">
                        <th className="pb-2">Pha</th>
                        <th className="pb-2 text-right">Cắt</th>
                        <th className="pb-2 text-right">Cắt/10s</th>
                        <th className="pb-2 text-right">Shot TV (s)</th>
                        <th className="pb-2 text-right">Từ/giây</th>
                        <th className="pb-2 text-right">Cảnh động %</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {brief.phases.map((p) => (
                        <tr key={p.phase_id} className="text-zinc-200">
                          <td className="py-2 font-medium">{p.label}</td>
                          <td className="py-2 text-right font-mono">
                            {p.cut_count}
                          </td>
                          <td className="py-2 text-right font-mono text-amber-300">
                            {p.cuts_per_10s}
                          </td>
                          <td className="py-2 text-right font-mono">
                            {p.median_shot_duration_s}s
                          </td>
                          <td className="py-2 text-right font-mono text-cyan-300">
                            {p.words_per_second}
                          </td>
                          <td className="py-2 text-right font-mono text-emerald-300">
                            {p.moving_footage_pct}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Comparison vs Our Channel Baseline */}
                <div className="lg:col-span-4 rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-2.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                    So Với Trung Vị Kênh Mình
                  </div>
                  {brief.our_channel_baseline &&
                  brief.our_channel_baseline.episodes_count > 0 ? (
                    <div className="space-y-2 text-xs">
                      <div className="flex items-center justify-between rounded-xl bg-zinc-950 p-2.5 border border-zinc-800">
                        <span className="text-zinc-400">Cắt trong Hook 0–3s</span>
                        <span className="font-mono font-bold text-white">
                          Outlier {brief.phases[0]?.cut_count ?? 0} vs PoW{" "}
                          {brief.our_channel_baseline.median_hook_0_3s_cuts}
                        </span>
                      </div>
                      <div className="flex items-center justify-between rounded-xl bg-zinc-950 p-2.5 border border-zinc-800">
                        <span className="text-zinc-400">Shot trung vị</span>
                        <span className="font-mono font-bold text-white">
                          {brief.median_shot_duration_s ?? "—"}s vs PoW{" "}
                          {brief.our_channel_baseline.median_shot_duration_s}s
                        </span>
                      </div>
                      <div className="flex items-center justify-between rounded-xl bg-zinc-950 p-2.5 border border-zinc-800">
                        <span className="text-zinc-400">Tốc độ cắt / 10s</span>
                        <span className="font-mono font-bold text-white">
                          {brief.cuts_per_10s_overall ?? "—"} vs PoW{" "}
                          {brief.our_channel_baseline.median_cuts_per_10s}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-xs text-zinc-500">
                      Chưa có dữ liệu baseline kênh.
                    </div>
                  )}
                </div>
              </div>

              {/* Keyframe Strip */}
              {brief.scenes.some((s) => s.mid_keyframe) && (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-4 space-y-2.5">
                  <div className="text-xs font-bold uppercase tracking-wider text-zinc-300">
                    Dải Keyframe Từng Cảnh ({brief.scenes.length} cảnh)
                  </div>
                  <div className="flex gap-2.5 overflow-x-auto pb-2">
                    {brief.scenes.map((sc) => (
                      <div
                        key={sc.sid}
                        className="w-28 shrink-0 rounded-xl border border-zinc-800 bg-zinc-950 overflow-hidden"
                      >
                        <div className="aspect-[9/16] bg-zinc-900 relative">
                          {sc.mid_keyframe && (
                            /* eslint-disable-next-line @next/next/no-img-element */
                            <img
                              src={`/api/outlier-analysis/media?videoId=${encodeURIComponent(
                                brief.target_id
                              )}&file=${encodeURIComponent(
                                sc.mid_keyframe
                              )}&v=${cacheBust}`}
                              alt={sc.sid}
                              loading="lazy"
                              className="h-full w-full object-cover"
                            />
                          )}
                          <span className="absolute left-1 top-1 rounded bg-black/75 px-1 py-0.5 text-[9px] font-mono text-white">
                            {sc.sid} • {sc.duration_s.toFixed(1)}s
                          </span>
                        </div>
                        <div className="p-1.5 text-[10px] text-zinc-400 line-clamp-2">
                          {sc.spoken_text || sc.motion_class}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Takeaways + Save Idea with Anatomy */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="space-y-1 text-xs">
                  <div className="font-bold text-amber-300 flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5" />
                    Cơ chế hiệu quả & Hướng khác biệt cho Proof of Wonder
                  </div>
                  {(brief.agent_annotations.what_works || []).map((w, i) => (
                    <div key={i} className="text-zinc-300">
                      • {w}
                    </div>
                  ))}
                  {(brief.agent_annotations.differentiation_seeds || []).map(
                    (s, i) => (
                      <div key={i} className="text-indigo-300">
                        → Khác biệt hóa: {s}
                      </div>
                    )
                  )}
                </div>

                <button
                  type="button"
                  disabled={saving || savedIdea}
                  onClick={() => void handleSaveWithAnatomy()}
                  className={`shrink-0 inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-bold transition cursor-pointer ${
                    savedIdea
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      : "bg-amber-500 hover:bg-amber-400 text-zinc-950"
                  }`}
                >
                  {savedIdea ? (
                    <>
                      <CheckCircle2 className="h-4 w-4" />
                      Đã lưu kèm giải phẫu
                    </>
                  ) : (
                    <>
                      <BookmarkPlus className="h-4 w-4" />
                      Lưu ý tưởng kèm giải phẫu
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
