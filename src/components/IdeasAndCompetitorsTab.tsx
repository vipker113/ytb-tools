"use client";

import {
  BookmarkPlus,
  Check,
  ChevronDown,
  ChevronUp,
  Compass,
  Copy,
  ExternalLink,
  Flame,
  Lightbulb,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Trash2,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import type {
  AiSuggestedTopic,
  RetentionWinnerBenchmark,
} from "@/app/api/growth/script/route";
import { formatCompact, formatDuration, formatNumber } from "@/lib/format";
import type {
  CompetitorChannel,
  KeywordAnalysisResult,
  SavedIdea,
  TrackedChannel,
  VideoItem,
} from "@/lib/types";
import { GrowthEngineTab } from "./GrowthEngineTab";
import { OutlierHunterTab } from "./OutlierHunterTab";

interface IdeasAndCompetitorsTabProps {
  channel?: TrackedChannel;
  competitors: CompetitorChannel[];
  ideas: SavedIdea[];
  hasYoutubeKey: boolean;
  defaultGeminiModel?: string;
  initialSubView?: "ai_backlog" | "script_builder" | "outliers" | "keywords";
  initialKeywordQuery?: string | null;
  onConsumeInitialKeyword?: () => void;
  onAddIdea: (idea: Partial<SavedIdea>) => Promise<void>;
  onUpdateIdea: (ideaId: string, patch: Partial<SavedIdea>) => Promise<void>;
  onDeleteIdea: (ideaId: string) => Promise<void>;
  onAddCompetitor: (query: string, niche: string) => Promise<void>;
  onRemoveCompetitor: (competitorId: string) => Promise<void>;
  onGoToSettings: () => void;
  onNotify: (msg: string) => void;
}

const DEFAULT_CHECKLIST = {
  hook5s: true,
  peakValueCta: true,
  subConfirmationLink: true,
  pinnedCommentCta: true,
  endScreenSub: false,
};

const DEMO_IDEA_IDS = new Set([
  "idea-1",
  "idea-2",
  "idea-3",
  "idea-4",
  "idea-5",
]);

function buildAntigravityBriefPrompt(params: {
  title: string;
  keyword?: string;
  hook?: string;
}): string {
  const kwPart = params.keyword
    ? ` (Từ khóa SEO mục tiêu: "${params.keyword}")`
    : "";
  const trimmedHook = params.hook?.trim() || "";
  const hookPart = trimmedHook
    ? trimmedHook.includes("\n") || trimmedHook.length > 160
      ? `\n\nKịch bản / Ghi chú triển khai:\n${trimmedHook}\n\n`
      : ` Góc nghịch lý mở đầu 0–3s: ${trimmedHook} `
    : " ";
  return `Hãy tạo video documentary chuẩn kênh Proof of Wonder (pow_documentary_v3) cho chủ đề: "${params.title}"${kwPart}.${hookPart}Chạy đủ 11 cổng QC và xuất đầy đủ video + thumbnail + youtube_metadata.md để tôi duyệt trên Web.`;
}

export function IdeasAndCompetitorsTab({
  channel,
  competitors,
  ideas,
  hasYoutubeKey,
  defaultGeminiModel = "gemini-3.6-flash",
  initialSubView = "ai_backlog",
  initialKeywordQuery,
  onConsumeInitialKeyword,
  onAddIdea,
  onUpdateIdea,
  onDeleteIdea,
  onAddCompetitor,
  onRemoveCompetitor,
  onGoToSettings,
  onNotify,
}: IdeasAndCompetitorsTabProps) {
  const [subView, setSubView] = useState<
    "ai_backlog" | "script_builder" | "outliers" | "keywords"
  >(initialKeywordQuery ? "keywords" : initialSubView);

  // AI Topic Suggestions state
  const [focusHint, setFocusHint] = useState("");
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [aiTopics, setAiTopics] = useState<AiSuggestedTopic[]>([]);
  const [retentionWinners, setRetentionWinners] = useState<
    RetentionWinnerBenchmark[]
  >([]);
  const [aiModelUsed, setAiModelUsed] = useState<string>("");
  const [scriptSeed, setScriptSeed] = useState<{
    topic: string;
    sourceTitle?: string;
    autoRun?: boolean;
  } | null>(null);
  const [savedTitles, setSavedTitles] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [expandedIdeaIds, setExpandedIdeaIds] = useState<
    Record<string, boolean>
  >({});

  // Quick manual add idea form
  const [manualTitle, setManualTitle] = useState("");
  const [manualKeyword, setManualKeyword] = useState("");
  const [manualNotes, setManualNotes] = useState("");

  // Keyword Explorer state
  const [kwInput, setKwInput] = useState(initialKeywordQuery || "");
  const [kwRegion, setKwRegion] = useState<"US" | "GB" | "VN">("US");
  const [kwLoading, setKwLoading] = useState(false);
  const [kwError, setKwError] = useState<string | null>(null);
  const [kwResult, setKwResult] = useState<KeywordAnalysisResult | null>(null);

  const totalOutliers = competitors.reduce(
    (sum, c) => sum + c.videos.filter((v) => v.outlierScore >= 2).length,
    0
  );

  const copyText = (id: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(id);
    setTimeout(() => setCopiedId((p) => (p === id ? null : p)), 2200);
  };

  const runKeywordAnalysis = useCallback(
    async (queryToRun: string, region = kwRegion) => {
      const q = queryToRun.trim();
      if (!q) return;
      setKwLoading(true);
      setKwError(null);
      try {
        const res = await fetch("/api/seo/keyword", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keyword: q, regionCode: region }),
        });
        const json = await res.json();
        if (!res.ok) throw new Error(json.error || "Lỗi phân tích từ khóa");
        setKwResult(json as KeywordAnalysisResult);
      } catch (err) {
        setKwError(
          err instanceof Error ? err.message : "Không thể phân tích từ khóa"
        );
      } finally {
        setKwLoading(false);
      }
    },
    [kwRegion]
  );

  const consumedKeywordRef = useRef<string | null>(null);
  const consumeCallbackRef = useRef(onConsumeInitialKeyword);
  consumeCallbackRef.current = onConsumeInitialKeyword;

  useEffect(() => {
    const q = initialKeywordQuery?.trim() || "";
    if (q && consumedKeywordRef.current !== q) {
      consumedKeywordRef.current = q;
      setSubView("keywords");
      setKwInput(q);
      void runKeywordAnalysis(q, "US");
      consumeCallbackRef.current?.();
    }
  }, [initialKeywordQuery, runKeywordAnalysis]);

  const handleGenerateAiTopics = async () => {
    setSuggestLoading(true);
    try {
      const res = await fetch("/api/growth/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "suggestFromWinners",
          focusHint,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi gợi ý chủ đề AI");
      if (Array.isArray(json.suggestions)) {
        setAiTopics(json.suggestions);
        setAiModelUsed(json.modelUsed || defaultGeminiModel);
      }
      if (Array.isArray(json.retentionWinners)) {
        setRetentionWinners(json.retentionWinners);
      }
    } catch (err) {
      onNotify(
        err instanceof Error ? err.message : "Không thể gọi AI gợi ý chủ đề"
      );
    } finally {
      setSuggestLoading(false);
    }
  };

  const handleSaveAiTopicToBacklog = async (t: AiSuggestedTopic) => {
    await onAddIdea({
      title: t.title,
      remakeTitle: t.title,
      targetKeyword: t.targetKeyword,
      format: "short",
      status: "backlog",
      notes: `Hook 0–3s: ${t.coreParadoxHook}\nLý do chọn: ${t.whyItFitsChannelVi} (~${t.suggestedDurationSec}s)`,
      tags: [t.targetKeyword, "science shorts", "proof of wonder"],
      checklist: DEFAULT_CHECKLIST,
    });
    setSavedTitles((p) => ({ ...p, [t.title]: true }));
  };

  const handleManualAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualTitle.trim()) return;
    await onAddIdea({
      title: manualTitle.trim(),
      remakeTitle: manualTitle.trim(),
      targetKeyword: manualKeyword.trim(),
      format: "short",
      status: "backlog",
      notes: manualNotes.trim(),
      tags: manualKeyword.trim() ? [manualKeyword.trim()] : [],
      checklist: DEFAULT_CHECKLIST,
    });
    setManualTitle("");
    setManualKeyword("");
    setManualNotes("");
  };

  // Filter out only hardcoded Vietnamese demo seed ideas when connected to a live channel
  const displayedIdeas =
    channel && !channel.isDemo
      ? ideas.filter((i) => !DEMO_IDEA_IDS.has(i.id))
      : ideas;

  return (
    <div className="space-y-5">
      {/* SUB-NAVIGATION BAR */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex flex-wrap rounded-xl bg-zinc-900 p-1 border border-zinc-800 gap-1">
          <button
            type="button"
            onClick={() => setSubView("ai_backlog")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
              subView === "ai_backlog"
                ? "bg-red-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Lightbulb className="h-3.5 w-3.5" />
            Đề Xuất Chủ Đề Giữ Chân & Backlog ({displayedIdeas.length})
          </button>

          <button
            type="button"
            onClick={() => setSubView("script_builder")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
              subView === "script_builder"
                ? "bg-red-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Wand2 className="h-3.5 w-3.5" />
            AI Kịch Bản Giữ Chân (Viral Script)
          </button>

          <button
            type="button"
            onClick={() => setSubView("outliers")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
              subView === "outliers"
                ? "bg-red-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Flame className="h-3.5 w-3.5" />
            Săn Video Outlier Đối Thủ ({totalOutliers})
          </button>

          <button
            type="button"
            onClick={() => setSubView("keywords")}
            className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
              subView === "keywords"
                ? "bg-red-600 text-white shadow"
                : "text-zinc-400 hover:text-white"
            }`}
          >
            <Compass className="h-3.5 w-3.5" />
            Khám Phá Từ Khóa Mỏ Vàng (US)
          </button>
        </div>
      </div>

      {/* VIEW 1: AI TOPIC GENERATOR FROM CHANNEL WINNERS + CLEAN SHORTS BACKLOG */}
      {subView === "ai_backlog" && (
        <div className="space-y-6">
          {/* AI Winner-Based Topic Generator */}
          <div className="rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-zinc-950 p-5 space-y-4 shadow-lg">
            <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-emerald-400">
                  <Sparkles className="h-4 w-4" />
                  Trợ Lý Sáng Tạo Chủ Đề Documentary (Dựa Trên Video Thắng Của Kênh)
                </div>
                <h2 className="text-base font-extrabold text-white">
                  Phân tích các tập giữ chân tốt nhất của {channel?.title || "Proof of Wonder"} & đối thủ để đề xuất 5 chủ đề mới
                </h2>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="text"
                  value={focusHint}
                  onChange={(e) => setFocusHint(e.target.value)}
                  placeholder="Tuỳ chọn hướng đi (VD: đại dương sâu, vũ trụ, hầm ngầm...)"
                  className="w-64 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-emerald-500 focus:outline-none"
                />
                <button
                  type="button"
                  disabled={suggestLoading}
                  onClick={() => void handleGenerateAiTopics()}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 disabled:opacity-60 px-4 py-2 text-xs font-extrabold text-white shadow-lg cursor-pointer"
                >
                  {suggestLoading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      AI đang phân tích kênh...
                    </>
                  ) : (
                    <>
                      <Wand2 className="h-4 w-4" />
                      Gợi Ý 5 Chủ Đề Mới (0₫)
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Quick Seed Chips */}
            <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
              <span className="text-zinc-500">Chủ đề ngách gợi ý nhanh:</span>
              {[
                "Sealed caves & forbidden places",
                "Extreme planetary weather",
                "Deep ocean physics",
                "Counter-intuitive human survival",
                "Geological anomalies",
              ].map((chip) => (
                <button
                  key={chip}
                  type="button"
                  onClick={() => setFocusHint(chip)}
                  className="rounded-lg border border-zinc-800 bg-zinc-950 hover:border-zinc-600 px-2.5 py-1 text-zinc-300 cursor-pointer"
                >
                  {chip}
                </button>
              ))}
            </div>

            {aiTopics.length > 0 && (
              <div className="space-y-3 pt-2 border-t border-zinc-800">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                  <span className="font-bold text-emerald-300">
                    ✨ 5 Đề Xuất Chủ Đề Giữ Chân Cao (Model: {aiModelUsed})
                  </span>
                  {retentionWinners.length > 0 && (
                    <span className="text-[11px] text-zinc-400">
                      📊 Đã phân tích Retention thật:{" "}
                      <strong className="text-zinc-200">
                        {retentionWinners
                          .slice(0, 2)
                          .map(
                            (w) =>
                              `${w.title.slice(0, 26)}… (${
                                w.stayedToWatchPct !== null
                                  ? `${w.stayedToWatchPct}% ở lại`
                                  : `${w.averageViewPercentage ?? 100}% xem`
                              })`
                          )
                          .join(" • ")}
                      </strong>
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                  {aiTopics.map((t, idx) => {
                    const promptStr = buildAntigravityBriefPrompt({
                      title: t.title,
                      keyword: t.targetKeyword,
                      hook: t.coreParadoxHook,
                    });
                    const isSaved = Boolean(savedTitles[t.title]);
                    return (
                      <div
                        key={idx}
                        className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-4 flex flex-col justify-between gap-3"
                      >
                        <div className="space-y-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <span className="rounded-md bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                              Từ khóa: {t.targetKeyword}
                            </span>
                            <span className="text-[11px] text-zinc-400">
                              ~{t.suggestedDurationSec}s Shorts
                            </span>
                          </div>

                          <h3 className="text-sm font-extrabold text-white leading-snug">
                            {t.title}
                          </h3>

                          <p className="text-xs text-zinc-300 bg-zinc-900/80 rounded-lg p-2.5 border border-zinc-800/80">
                            <strong className="text-sky-300">
                              Hook 0–3s:
                            </strong>{" "}
                            {t.coreParadoxHook}
                          </p>

                          <p className="text-[11px] text-zinc-400">
                            🎯 {t.whyItFitsChannelVi}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2 pt-1">
                          <button
                            type="button"
                            onClick={() => {
                              setScriptSeed({
                                topic: t.title,
                                sourceTitle: t.coreParadoxHook,
                                autoRun: true,
                              });
                              setSubView("script_builder");
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 hover:bg-red-500 px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
                          >
                            <Wand2 className="h-3.5 w-3.5" />
                            Viết Kịch Bản Giữ Chân
                          </button>

                          <button
                            type="button"
                            onClick={() =>
                              copyText(`agy-ai-${idx}`, promptStr)
                            }
                            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500/15 hover:bg-sky-500/25 border border-sky-500/40 px-3 py-1.5 text-xs font-bold text-sky-200 cursor-pointer"
                          >
                            {copiedId === `agy-ai-${idx}` ? (
                              <Check className="h-3.5 w-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                            {copiedId === `agy-ai-${idx}`
                              ? "Đã chép lệnh cho Antigravity!"
                              : "Copy Lệnh Dựng Antigravity"}
                          </button>

                          <button
                            type="button"
                            disabled={isSaved}
                            onClick={() => void handleSaveAiTopicToBacklog(t)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 disabled:opacity-50 px-3 py-1.5 text-xs font-semibold text-zinc-200 cursor-pointer"
                          >
                            {isSaved ? (
                              <>
                                <Check className="h-3.5 w-3.5 text-emerald-400" />
                                Đã lưu Backlog
                              </>
                            ) : (
                              <>
                                <BookmarkPlus className="h-3.5 w-3.5" />
                                Lưu Backlog
                              </>
                            )}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setKwInput(t.targetKeyword);
                              setSubView("keywords");
                              void runKeywordAnalysis(t.targetKeyword, "US");
                            }}
                            className="text-[11px] text-zinc-400 hover:text-white ml-auto cursor-pointer"
                          >
                            Soi từ khóa →
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Clean Shorts Backlog */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-extrabold text-white">
                  Kho Backlog Chủ Đề Chờ Sản Xuất ({displayedIdeas.length})
                </h3>
                <p className="text-xs text-zinc-400">
                  Lưu gọn các ý tưởng tâm đắc, bấm 1 nút để chép lệnh sang Antigravity App dựng video.
                </p>
              </div>
            </div>

            {/* Quick Add Form */}
            <form
              onSubmit={handleManualAddSubmit}
              className="grid grid-cols-1 md:grid-cols-12 gap-2.5 rounded-xl border border-zinc-800 bg-zinc-950/70 p-3"
            >
              <input
                type="text"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                placeholder="Nhập chủ đề hoặc tiêu đề dự kiến..."
                className="md:col-span-5 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-red-500 focus:outline-none"
              />
              <input
                type="text"
                value={manualKeyword}
                onChange={(e) => setManualKeyword(e.target.value)}
                placeholder="Từ khóa chính (VD: deep sea brine)"
                className="md:col-span-3 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-red-500 focus:outline-none"
              />
              <input
                type="text"
                value={manualNotes}
                onChange={(e) => setManualNotes(e.target.value)}
                placeholder="Ghi chú nhanh góc khai thác..."
                className="md:col-span-2 rounded-lg border border-zinc-800 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-red-500 focus:outline-none"
              />
              <button
                type="submit"
                className="md:col-span-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-red-600 hover:bg-red-500 px-3 py-2 text-xs font-bold text-white cursor-pointer"
              >
                <Plus className="h-3.5 w-3.5" />
                Thêm Backlog
              </button>
            </form>

            {displayedIdeas.length === 0 ? (
              <div className="rounded-xl border border-zinc-800/70 bg-zinc-950/50 p-8 text-center text-xs text-zinc-400">
                Kho Backlog đang trống. Hãy bấm &ldquo;Gợi Ý 5 Chủ Đề Mới&rdquo; ở trên hoặc lưu từ tab Săn Outlier Đối Thủ!
              </div>
            ) : (
              <div className="space-y-2.5">
                {displayedIdeas.map((idea) => {
                  const brief = buildAntigravityBriefPrompt({
                    title: idea.remakeTitle || idea.title,
                    keyword: idea.targetKeyword,
                    hook: idea.notes,
                  });
                  const hasLongNotes =
                    Boolean(idea.notes) &&
                    (idea.notes.length > 160 || idea.notes.includes("\n"));
                  const isExpanded =
                    expandedIdeaIds[idea.id] ??
                    (idea.status === "scripting" && displayedIdeas.length <= 3);

                  return (
                    <div
                      key={idea.id}
                      className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4 space-y-3"
                    >
                      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                        <div className="space-y-1.5 min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              value={idea.status}
                              onChange={(e) =>
                                void onUpdateIdea(idea.id, {
                                  status: e.target.value as SavedIdea["status"],
                                })
                              }
                              className="rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] font-bold text-zinc-200 cursor-pointer"
                            >
                              <option value="backlog">📋 Chờ dựng</option>
                              <option value="scripting">✍️ Đã có kịch bản</option>
                              <option value="filming">🎬 Đang dựng</option>
                              <option value="published">✅ Đã đăng</option>
                            </select>

                            {idea.targetKeyword && (
                              <span className="rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                                KW: {idea.targetKeyword}
                              </span>
                            )}
                            {idea.sourceOutlierScore && (
                              <span className="rounded bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-300">
                                Outlier {idea.sourceOutlierScore.toFixed(1)}x
                              </span>
                            )}
                            {hasLongNotes && (
                              <button
                                type="button"
                                onClick={() =>
                                  setExpandedIdeaIds((prev) => ({
                                    ...prev,
                                    [idea.id]: !isExpanded,
                                  }))
                                }
                                className="inline-flex items-center gap-1 rounded bg-zinc-900 border border-zinc-700/80 hover:border-zinc-500 px-2 py-0.5 text-[10px] font-semibold text-sky-300 cursor-pointer"
                              >
                                {isExpanded ? (
                                  <>
                                    <ChevronUp className="h-3 w-3" />
                                    Thu gọn kịch bản
                                  </>
                                ) : (
                                  <>
                                    <ChevronDown className="h-3 w-3" />
                                    Xem đầy đủ kịch bản
                                  </>
                                )}
                              </button>
                            )}
                          </div>

                          <p className="text-sm font-bold text-white">
                            {idea.title}
                          </p>
                          {idea.notes && !isExpanded && (
                            <p className="text-xs text-zinc-400 line-clamp-2 whitespace-pre-line">
                              {idea.notes}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2 shrink-0">
                          <button
                            type="button"
                            onClick={() => {
                              setScriptSeed({
                                topic: idea.remakeTitle || idea.title,
                                sourceTitle: idea.sourceVideoTitle,
                                autoRun: true,
                              });
                              setSubView("script_builder");
                            }}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 hover:bg-red-500 px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
                          >
                            <Wand2 className="h-3.5 w-3.5" />
                            {idea.status === "scripting"
                              ? "Biến Thể Kịch Bản AI"
                              : "Viết Kịch Bản"}
                          </button>

                          <button
                            type="button"
                            onClick={() => copyText(`idea-${idea.id}`, brief)}
                            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 hover:bg-sky-500/25 px-3 py-1.5 text-xs font-bold text-sky-200 cursor-pointer"
                          >
                            {copiedId === `idea-${idea.id}` ? (
                              <Check className="h-3.5 w-3.5 text-emerald-400" />
                            ) : (
                              <Copy className="h-3.5 w-3.5" />
                            )}
                            {copiedId === `idea-${idea.id}`
                              ? "Đã chép!"
                              : "Copy Lệnh Dựng"}
                          </button>

                          <button
                            type="button"
                            onClick={() => void onDeleteIdea(idea.id)}
                            className="rounded-lg border border-zinc-800 bg-zinc-900 hover:text-rose-400 p-2 text-zinc-400 cursor-pointer"
                            title="Xóa ý tưởng"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {idea.notes && isExpanded && (
                        <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/70 p-3.5 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-300">
                              📜 Chi tiết kịch bản & ghi chú sản xuất
                            </span>
                            <button
                              type="button"
                              onClick={() =>
                                copyText(`notes-${idea.id}`, idea.notes)
                              }
                              className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-950 px-2 py-1 text-[10px] font-semibold text-zinc-300 hover:text-white cursor-pointer"
                            >
                              {copiedId === `notes-${idea.id}` ? (
                                <Check className="h-3 w-3 text-emerald-400" />
                              ) : (
                                <Copy className="h-3 w-3" />
                              )}
                              {copiedId === `notes-${idea.id}`
                                ? "Đã chép kịch bản"
                                : "Copy Kịch Bản"}
                            </button>
                          </div>
                          <pre className="text-xs text-zinc-200 whitespace-pre-wrap font-sans leading-relaxed">
                            {idea.notes}
                          </pre>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* VIEW 1.5: AI RETENTION VIRAL SCRIPT BUILDER */}
      {subView === "script_builder" && (
        <GrowthEngineTab
          channel={channel}
          defaultModel={defaultGeminiModel}
          initialTopic={scriptSeed}
          onSaveBlueprintAsIdea={async (idea) => {
            await onAddIdea(idea);
            onNotify("✨ Đã lưu trọn bộ kịch bản giữ chân vào Backlog!");
          }}
        />
      )}

      {/* VIEW 2: COMPETITOR OUTLIER HUNTER */}
      {subView === "outliers" && (
        <OutlierHunterTab
          competitors={competitors}
          hasYoutubeKey={hasYoutubeKey}
          onAddCompetitor={onAddCompetitor}
          onRemoveCompetitor={onRemoveCompetitor}
          onSaveIdeaFromVideo={async (idea) => {
            await onAddIdea(idea);
            onNotify("Đã lưu video Outlier vào Backlog!");
          }}
          onAuditCompetitorVideo={(vid: VideoItem) => {
            const kw =
              vid.tags[0] ||
              vid.title
                .replace(/#\S+/g, "")
                .split(/\s+/)
                .slice(0, 4)
                .join(" ");
            setKwInput(kw);
            setSubView("keywords");
            void runKeywordAnalysis(kw, "US");
          }}
          onBuildViralScriptFromVideo={(vid: VideoItem) => {
            const clean = vid.title.replace(/#\S+/g, "").trim();
            setScriptSeed({
              topic: clean,
              sourceTitle: `${clean} (${vid.channelTitle} • ${vid.outlierScore.toFixed(
                1
              )}x Outlier • ${formatNumber(vid.views)} views)`,
              autoRun: true,
            });
            setSubView("script_builder");
          }}
          onGoToSettings={onGoToSettings}
        />
      )}

      {/* VIEW 3: US/GLOBAL KEYWORD OPPORTUNITY EXPLORER */}
      {subView === "keywords" && (
        <div className="space-y-5">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4">
            <div className="space-y-1">
              <h2 className="text-base font-extrabold text-white">
                Khám Phá Từ Khóa Mỏ Vàng Trên YouTube Mỹ / Quốc Tế
              </h2>
              <p className="text-xs text-zinc-400">
                Đo trực tiếp lượng cầu (Demand) và số kênh nhỏ lọt Top 10 để chọn đúng từ khóa dễ nổ đề xuất nhất.
              </p>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                void runKeywordAnalysis(kwInput, kwRegion);
              }}
              className="flex flex-col sm:flex-row gap-2.5"
            >
              <div className="relative flex-1">
                <Search className="h-4 w-4 text-zinc-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={kwInput}
                  onChange={(e) => setKwInput(e.target.value)}
                  placeholder="Nhập từ khóa tiếng Anh (VD: fermi paradox, underwater brine lake, movile cave...)"
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 pl-10 pr-4 py-2.5 text-xs text-white focus:border-red-500 focus:outline-none"
                />
              </div>

              <select
                value={kwRegion}
                onChange={(e) =>
                  setKwRegion(e.target.value as "US" | "GB" | "VN")
                }
                className="rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-xs font-bold text-zinc-200 cursor-pointer"
              >
                <option value="US">🇺🇸 Thị trường Mỹ (US)</option>
                <option value="GB">🇬🇧 Anh Quốc (UK)</option>
                <option value="VN">🇻🇳 Việt Nam (VN)</option>
              </select>

              <button
                type="submit"
                disabled={kwLoading}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-5 py-2.5 text-xs font-extrabold text-white cursor-pointer"
              >
                {kwLoading ? "Đang quét Top YouTube..." : "Phân Tích Từ Khóa"}
              </button>
            </form>

            {kwError && (
              <p className="text-xs text-rose-400 font-semibold">{kwError}</p>
            )}
          </div>

          {kwResult && (
            <div className="space-y-5">
              {/* Score Overview */}
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3.5">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4">
                  <span className="text-xs text-zinc-400">Điểm Cơ Hội Tổng</span>
                  <div className="text-2xl font-extrabold text-emerald-300 mt-1">
                    {kwResult.overallScore}/100
                  </div>
                  <span className="text-[11px] font-bold text-zinc-300">
                    {kwResult.verdict === "golden"
                      ? "💎 Mỏ Vàng — Nên làm ngay!"
                      : kwResult.verdict === "good"
                      ? "✅ Cơ hội tốt"
                      : kwResult.verdict === "competitive"
                      ? "⚔️ Cạnh tranh cao — Cần ngách hẹp hơn"
                      : "📉 Nhu cầu tìm kiếm thấp"}
                  </span>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4">
                  <span className="text-xs text-zinc-400">Sức Hút Lượt Xem</span>
                  <div className="text-2xl font-extrabold text-white mt-1">
                    {kwResult.demandScore}/100
                  </div>
                  <span className="text-[11px] text-zinc-400">
                    Trung vị Top: {formatCompact(kwResult.medianViews)} views
                  </span>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4">
                  <span className="text-xs text-zinc-400">
                    Độ Mở Cho Kênh Nhỏ
                  </span>
                  <div className="text-2xl font-extrabold text-sky-300 mt-1">
                    {kwResult.smallChannelsInTop10}/10
                  </div>
                  <span className="text-[11px] text-zinc-400">
                    kênh nhỏ (&lt;50K sub) lọt Top 10
                  </span>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 flex flex-col justify-between">
                  <div>
                    <span className="text-xs text-zinc-400">Tỷ Lệ Shorts</span>
                    <div className="text-xl font-extrabold text-amber-300 mt-0.5">
                      {kwResult.shortsRatio}% • {kwResult.optimalDurationRange}
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={async () => {
                      await onAddIdea({
                        title: `Chủ đề từ khóa: ${kwResult.keyword}`,
                        remakeTitle:
                          kwResult.titlePatterns[0] || kwResult.keyword,
                        targetKeyword: kwResult.keyword,
                        format: "short",
                        status: "backlog",
                        notes: `Điểm cơ hội ${kwResult.overallScore}/100 (${kwResult.smallChannelsInTop10}/10 kênh nhỏ lọt Top).`,
                        tags: kwResult.recommendedTags.slice(0, 12),
                        checklist: DEFAULT_CHECKLIST,
                      });
                      onNotify("Đã lưu từ khóa vào Backlog!");
                    }}
                    className="mt-2 inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-[11px] font-bold text-white cursor-pointer"
                  >
                    <BookmarkPlus className="h-3.5 w-3.5" />
                    Lưu Vào Backlog
                  </button>
                </div>
              </div>

              {/* Recommended Tags + Top Videos */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-extrabold text-white">
                    Bộ Thẻ Tags Thực Tế Đang Lên Top ({kwResult.recommendedTags.length} thẻ)
                  </span>
                  <button
                    type="button"
                    onClick={() =>
                      copyText(
                        "kw-tags",
                        kwResult.recommendedTags.join(", ")
                      )
                    }
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-sky-400 hover:text-sky-300 cursor-pointer"
                  >
                    {copiedId === "kw-tags" ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    Copy trọn bộ Tags
                  </button>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {kwResult.recommendedTags.map((t) => (
                    <span
                      key={t}
                      className="rounded-md bg-zinc-950 border border-zinc-800 px-2.5 py-1 text-xs text-zinc-200"
                    >
                      {t}
                    </span>
                  ))}
                </div>

                {kwResult.topVideos.length > 0 && (
                  <div className="pt-3 border-t border-zinc-800 space-y-2">
                    <span className="text-xs font-bold text-zinc-300 block">
                      Top Video Đang Giữ Thứ Hạng Cao Cho &ldquo;{kwResult.keyword}&rdquo;:
                    </span>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                      {kwResult.topVideos.slice(0, 6).map((v) => (
                        <a
                          key={v.id}
                          href={`https://www.youtube.com/watch?v=${v.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="flex items-start gap-2.5 rounded-xl border border-zinc-800 bg-zinc-950/80 hover:border-zinc-700 p-2.5"
                        >
                          {v.thumbnailUrl && (
                            <img
                              src={v.thumbnailUrl}
                              alt={v.title}
                              className="h-12 w-20 rounded-lg object-cover shrink-0"
                            />
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-bold text-white line-clamp-2 leading-snug">
                              {v.title}
                            </p>
                            <div className="text-[10px] text-zinc-400 mt-1 flex items-center gap-1.5">
                              <span>{v.channelTitle}</span>
                              <span>•</span>
                              <span>{formatCompact(v.views)} views</span>
                              <span>•</span>
                              <span>{formatDuration(v.durationSeconds)}</span>
                              <ExternalLink className="h-2.5 w-2.5 ml-auto shrink-0" />
                            </div>
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
