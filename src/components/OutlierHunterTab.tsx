"use client";

import {
  BookmarkPlus,
  Check,
  ExternalLink,
  Flame,
  Plus,
  Rocket,
  Search,
  Sparkles,
  Trash2,
  TrendingUp,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  formatCompact,
  formatDateShort,
  formatDuration,
  formatNumber,
  getOutlierBadgeStyle,
} from "@/lib/format";
import type { CompetitorChannel, SavedIdea, VideoItem } from "@/lib/types";

interface OutlierHunterTabProps {
  competitors: CompetitorChannel[];
  hasYoutubeKey: boolean;
  onAddCompetitor: (query: string, niche: string) => Promise<void>;
  onRemoveCompetitor: (competitorId: string) => Promise<void>;
  onSaveIdeaFromVideo: (idea: Partial<SavedIdea>) => Promise<void>;
  onAuditCompetitorVideo: (video: VideoItem) => void;
  onBuildViralScriptFromVideo: (video: VideoItem) => void;
  onGoToSettings: () => void;
}

export function OutlierHunterTab({
  competitors,
  hasYoutubeKey,
  onAddCompetitor,
  onRemoveCompetitor,
  onSaveIdeaFromVideo,
  onAuditCompetitorVideo,
  onBuildViralScriptFromVideo,
  onGoToSettings,
}: OutlierHunterTabProps) {
  const [compInput, setCompInput] = useState("");
  const [nicheInput, setNicheInput] = useState("");
  const [adding, setAdding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [selectedChannelId, setSelectedChannelId] = useState<string>("all");
  const [minOutlier, setMinOutlier] = useState<number>(2);
  const [formatFilter, setFormatFilter] = useState<"all" | "long" | "short">("all");
  const [sortBy, setSortBy] = useState<"outlier" | "velocity" | "subsRatio">("outlier");
  const [searchText, setSearchText] = useState("");
  const [savedVideoIds, setSavedVideoIds] = useState<Record<string, boolean>>({});

  const filteredOutliers = useMemo(() => {
    const allVideos: VideoItem[] = [];
    for (const comp of competitors) {
      if (selectedChannelId !== "all" && comp.id !== selectedChannelId) continue;
      allVideos.push(...comp.videos);
    }

    return allVideos
      .filter((v) => v.outlierScore >= minOutlier)
      .filter((v) => {
        if (formatFilter === "short") return v.isShort;
        if (formatFilter === "long") return !v.isShort;
        return true;
      })
      .filter((v) => {
        if (!searchText.trim()) return true;
        const q = searchText.toLowerCase();
        return (
          v.title.toLowerCase().includes(q) ||
          v.channelTitle.toLowerCase().includes(q) ||
          v.tags.some((t) => t.toLowerCase().includes(q))
        );
      })
      .sort((a, b) => {
        if (sortBy === "velocity") return b.viewsPerDay - a.viewsPerDay;
        if (sortBy === "subsRatio") return b.viewsToSubsRatio - a.viewsToSubsRatio;
        return b.outlierScore - a.outlierScore;
      });
  }, [competitors, selectedChannelId, minOutlier, formatFilter, searchText, sortBy]);

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!compInput.trim()) return;
    setErrorMsg(null);
    setAdding(true);
    try {
      await onAddCompetitor(compInput.trim(), nicheInput.trim() || "Đối thủ cùng ngách");
      setCompInput("");
      setNicheInput("");
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Lỗi khi thêm kênh đối thủ.");
    } finally {
      setAdding(false);
    }
  };

  const handleCloneIdea = async (v: VideoItem) => {
    const coreKeyword = v.tags[0] || v.title.split(" ").slice(0, 5).join(" ");
    await onSaveIdeaFromVideo({
      title: `Nhân bản Outlier (${v.outlierScore.toFixed(1)}x): ${v.title}`,
      remakeTitle: `[Phiên bản nâng cấp] ${v.title}`,
      targetKeyword: coreKeyword,
      sourceVideoId: v.id,
      sourceVideoTitle: v.title,
      sourceChannelTitle: v.channelTitle,
      sourceThumbnailUrl: v.thumbnailUrl,
      sourceOutlierScore: v.outlierScore,
      format: v.isShort ? "short" : "long",
      status: "backlog",
      tags: v.tags.slice(0, 10),
      notes: `Video gốc đạt ${formatNumber(v.views)} views trên kênh chỉ có ${formatNumber(
        v.channelSubscribers
      )} subs (${v.viewsToSubsRatio}x lượng sub). Hãy giữ cấu trúc nỗi đau/tò mò của tiêu đề nhưng làm ví dụ thực tế sâu hơn!`,
    });
    setSavedVideoIds((prev) => ({ ...prev, [v.id]: true }));
  };

  return (
    <div className="space-y-6">
      {/* Header Explanation + Add Competitor Form */}
      <div className="rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900 to-amber-950/15 p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-5">
          <div>
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Flame className="h-5 w-5 text-amber-400" />
              Săn Video Viral Đột Biến Của Đối Thủ (Outlier Hunter)
            </h2>
            <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
              Bí quyết tăng Subscribers thật nhanh nhất cho kênh nhỏ: Tìm những video trên kênh đối thủ có{" "}
              <strong className="text-amber-300">
                lượt xem cao gấp 5–15 lần mức trung bình của chính kênh đó
              </strong>
              . Đó là bằng chứng thuật toán YouTube đang cực kỳ khát nguồn cung cho chủ đề này!
            </p>
          </div>
          {!hasYoutubeKey && (
            <button
              onClick={onGoToSettings}
              className="shrink-0 rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 px-4 py-2.5 text-xs font-semibold text-amber-300 transition cursor-pointer"
            >
              ⚡ Kết nối YouTube API để quét đối thủ thật
            </button>
          )}
        </div>

        <form
          onSubmit={handleAddSubmit}
          className="grid grid-cols-1 md:grid-cols-12 gap-3"
        >
          <div className="md:col-span-6">
            <input
              type="text"
              value={compInput}
              onChange={(e) => setCompInput(e.target.value)}
              placeholder="Nhập @handle đối thủ, URL kênh YouTube hoặc UC... ID"
              className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-4 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
            />
          </div>
          <div className="md:col-span-3">
            <input
              type="text"
              value={nicheInput}
              onChange={(e) => setNicheInput(e.target.value)}
              placeholder="Nhãn ngách (VD: AI, Tài chính...)"
              className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-4 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
            />
          </div>
          <div className="md:col-span-3">
            <button
              type="submit"
              disabled={adding || !compInput.trim()}
              className="w-full h-full inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-4 py-2.5 text-sm font-semibold text-white transition cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              {adding ? "Đang quét kênh..." : "Thêm & Quét Đối Thủ"}
            </button>
          </div>
        </form>

        {errorMsg && (
          <div className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
            {errorMsg}
          </div>
        )}

        {/* Quick 1-Click Niche Competitor Presets */}
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-zinc-400">Gợi ý quét nhanh ngách Science & Curiosity:</span>
          {[
            { handle: "@CleoAbram", niche: "Science Shorts" },
            { handle: "@MinuteEarth", niche: "Science & Earth" },
            { handle: "@BeSmart", niche: "Deep Science" },
            { handle: "@zackdfilms", niche: "3D Curiosity Shorts" },
            { handle: "@scishow", niche: "Strange Questions" },
          ].map((preset) => (
            <button
              key={preset.handle}
              type="button"
              disabled={adding}
              onClick={async () => {
                setErrorMsg(null);
                setAdding(true);
                try {
                  await onAddCompetitor(preset.handle, preset.niche);
                } catch (err) {
                  setErrorMsg(
                    err instanceof Error ? err.message : "Lỗi quét kênh đối thủ."
                  );
                } finally {
                  setAdding(false);
                }
              }}
              className="rounded-lg border border-zinc-700/80 bg-zinc-950/80 hover:border-amber-500/50 hover:text-amber-300 px-2.5 py-1 text-zinc-300 transition cursor-pointer"
            >
              + {preset.handle}
            </button>
          ))}
        </div>

        {/* Tracked Competitor Pills */}
        {competitors.length > 0 && (
          <div className="mt-5 pt-4 border-t border-zinc-800/80 flex flex-wrap items-center gap-2">
            <button
              onClick={() => setSelectedChannelId("all")}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition cursor-pointer ${
                selectedChannelId === "all"
                  ? "bg-white text-zinc-950"
                  : "bg-zinc-800/90 text-zinc-300 hover:bg-zinc-800"
              }`}
            >
              Tất cả đối thủ ({competitors.length})
            </button>

            {competitors.map((comp) => (
              <div
                key={comp.id}
                className={`inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-xs transition ${
                  selectedChannelId === comp.id
                    ? "border-red-500 bg-red-500/15 text-white"
                    : "border-zinc-800 bg-zinc-950/70 text-zinc-300"
                }`}
              >
                <button
                  onClick={() => setSelectedChannelId(comp.id)}
                  className="flex items-center gap-2 cursor-pointer"
                >
                  <img
                    src={
                      comp.thumbnailUrl ||
                      `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                        comp.title
                      )}`
                    }
                    alt={comp.title}
                    referrerPolicy="no-referrer"
                    onError={(e) => {
                      e.currentTarget.src = `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                        comp.title
                      )}`;
                    }}
                    className="h-4 w-4 rounded-full object-cover"
                  />
                  <span className="font-medium">{comp.title}</span>
                  <span className="text-zinc-500">
                    ({formatCompact(comp.subscribers)} subs)
                  </span>
                </button>
                <button
                  onClick={() => onRemoveCompetitor(comp.id)}
                  title="Bỏ theo dõi đối thủ này"
                  className="text-zinc-500 hover:text-red-400 transition cursor-pointer"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Filter & Sort Controls */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-zinc-400 mr-1">
            Ngưỡng đột biến:
          </span>
          {[
            { val: 0, label: "Tất cả" },
            { val: 2, label: "≥ 2.0x" },
            { val: 4, label: "≥ 4.0x 🔥" },
            { val: 10, label: "≥ 10.0x 🚀" },
          ].map((opt) => (
            <button
              key={opt.val}
              onClick={() => setMinOutlier(opt.val)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition cursor-pointer ${
                minOutlier === opt.val
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                  : "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {opt.label}
            </button>
          ))}

          <div className="h-4 w-px bg-zinc-800 mx-1 hidden sm:block" />

          {[
            { val: "all" as const, label: "Mọi định dạng" },
            { val: "long" as const, label: "Video dài" },
            { val: "short" as const, label: "Shorts" },
          ].map((f) => (
            <button
              key={f.val}
              onClick={() => setFormatFilter(f.val)}
              className={`rounded-lg px-2.5 py-1.5 text-xs font-medium transition cursor-pointer ${
                formatFilter === f.val
                  ? "bg-red-500/20 text-red-300 border border-red-500/40"
                  : "bg-zinc-800/80 text-zinc-400 hover:text-zinc-200"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-52">
            <Search className="h-3.5 w-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder="Lọc theo từ khóa..."
              className="w-full rounded-lg border border-zinc-800 bg-zinc-950 pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-zinc-500 focus:border-zinc-600 focus:outline-none"
            />
          </div>

          <select
            value={sortBy}
            onChange={(e) =>
              setSortBy(e.target.value as "outlier" | "velocity" | "subsRatio")
            }
            className="rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs text-zinc-200 focus:outline-none"
          >
            <option value="outlier">Sắp xếp: Điểm Outlier cao nhất</option>
            <option value="velocity">Sắp xếp: Tốc độ Views/Ngày</option>
            <option value="subsRatio">Sắp xếp: Views gấp nhiều lần Subs</option>
          </select>
        </div>
      </div>

      {/* Outlier Cards Grid */}
      {filteredOutliers.length === 0 ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-12 text-center">
          <p className="text-sm text-zinc-400">
            Không có video nào khớp với bộ lọc hiện tại. Hãy hạ ngưỡng Outlier xuống{" "}
            <button
              onClick={() => setMinOutlier(0)}
              className="text-amber-400 underline cursor-pointer"
            >
              Tất cả
            </button>{" "}
            hoặc thêm kênh đối thủ mới!
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredOutliers.map((v) => {
            const badge = getOutlierBadgeStyle(v.outlierScore);
            const isSaved = Boolean(savedVideoIds[v.id]);
            return (
              <div
                key={`${v.channelId}-${v.id}`}
                className="rounded-2xl border border-zinc-800/90 bg-zinc-900/80 overflow-hidden flex flex-col justify-between hover:border-zinc-700 transition group"
              >
                <div>
                  {/* Thumbnail with Outlier & Duration overlays */}
                  <div className="relative aspect-video bg-zinc-950 overflow-hidden">
                    {v.thumbnailUrl && (
                      <img
                        src={v.thumbnailUrl}
                        alt={v.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition duration-500"
                      />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-zinc-950/90 via-transparent to-zinc-950/30" />

                    <div className="absolute top-3 left-3 flex flex-wrap gap-1.5">
                      <span
                        className={`rounded-full border backdrop-blur-md px-2.5 py-1 text-xs font-bold shadow-lg ${badge.className}`}
                      >
                        {badge.label}
                      </span>
                    </div>

                    <div className="absolute bottom-2.5 left-3 right-3 flex items-center justify-between text-xs">
                      <span className="rounded-md bg-emerald-500/20 border border-emerald-500/40 backdrop-blur-md px-2 py-0.5 font-semibold text-emerald-300">
                        {v.viewsToSubsRatio.toFixed(1)}x lượng Sub kênh
                      </span>
                      <span className="rounded-md bg-zinc-950/85 px-2 py-0.5 font-mono text-[11px] text-zinc-200">
                        {v.isShort ? "Shorts • " : ""}
                        {formatDuration(v.durationSeconds)}
                      </span>
                    </div>
                  </div>

                  {/* Body */}
                  <div className="p-5">
                    <div className="flex items-center justify-between text-xs text-zinc-400 mb-2">
                      <span className="font-medium text-zinc-300 truncate">
                        {v.channelTitle}{" "}
                        <span className="text-zinc-500">
                          ({formatCompact(v.channelSubscribers)} subs)
                        </span>
                      </span>
                      <span className="shrink-0">
                        {formatDateShort(v.publishedAt)}
                      </span>
                    </div>

                    <h3 className="text-sm font-bold text-white leading-snug line-clamp-2 mb-3">
                      {v.title}
                    </h3>

                    {/* Metrics Box */}
                    <div className="grid grid-cols-3 gap-2 rounded-xl bg-zinc-950/80 border border-zinc-800/80 p-2.5 text-center mb-3">
                      <div>
                        <div className="text-[10px] text-zinc-500 uppercase">
                          Lượt xem
                        </div>
                        <div className="text-xs font-bold text-white">
                          {formatCompact(v.views)}
                        </div>
                      </div>
                      <div className="border-x border-zinc-800">
                        <div className="text-[10px] text-zinc-500 uppercase flex items-center justify-center gap-0.5">
                          <TrendingUp className="h-2.5 w-2.5 text-emerald-400" />
                          Tốc độ
                        </div>
                        <div className="text-xs font-bold text-emerald-400">
                          {formatCompact(v.viewsPerDay)}/ngày
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] text-zinc-500 uppercase flex items-center justify-center gap-0.5">
                          <Users className="h-2.5 w-2.5 text-amber-400" />
                          Tương tác
                        </div>
                        <div className="text-xs font-bold text-amber-300">
                          {v.engagementRate.toFixed(1)}%
                        </div>
                      </div>
                    </div>

                    {/* Extracted Tags */}
                    {v.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mb-2">
                        {v.tags.slice(0, 4).map((t) => (
                          <span
                            key={t}
                            className="rounded-md bg-zinc-800/80 px-2 py-0.5 text-[11px] text-zinc-400"
                          >
                            #{t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions Footer */}
                <div className="px-5 pb-5 pt-2 flex items-center gap-2">
                  <button
                    onClick={() => handleCloneIdea(v)}
                    disabled={isSaved}
                    className={`flex-1 inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition cursor-pointer ${
                      isSaved
                        ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                        : "bg-red-600 hover:bg-red-500 text-white"
                    }`}
                  >
                    {isSaved ? (
                      <>
                        <Check className="h-3.5 w-3.5" />
                        Đã lưu vào Kho Ý Tưởng
                      </>
                    ) : (
                      <>
                        <BookmarkPlus className="h-3.5 w-3.5" />
                        Nhân bản chủ đề
                      </>
                    )}
                  </button>

                  <button
                    onClick={() => onBuildViralScriptFromVideo(v)}
                    title="Tạo kịch bản Shorts 45s nối vòng lặp bằng AI từ chủ đề này"
                    className="rounded-xl border border-red-500/40 bg-red-500/15 hover:bg-red-600 p-2 text-red-300 hover:text-white transition cursor-pointer"
                  >
                    <Rocket className="h-4 w-4" />
                  </button>

                  <button
                    onClick={() => onAuditCompetitorVideo(v)}
                    title="Mổ xẻ cấu trúc SEO của video này"
                    className="rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 p-2 text-zinc-200 transition cursor-pointer"
                  >
                    <Sparkles className="h-4 w-4 text-amber-400" />
                  </button>

                  {!v.id.startsWith("out-") && !v.id.startsWith("demo-") && (
                    <a
                      href={`https://www.youtube.com/watch?v=${v.id}`}
                      target="_blank"
                      rel="noreferrer"
                      title="Xem trên YouTube"
                      className="rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 p-2 text-zinc-200 transition"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
