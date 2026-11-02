"use client";

import {
  AlertTriangle,
  BookmarkPlus,
  Check,
  CheckCircle2,
  Compass,
  Copy,
  FileSearch,
  Link2,
  Sparkles,
  Wand2,
} from "lucide-react";
import { useState } from "react";
import { formatCompact, formatDuration, formatNumber } from "@/lib/format";
import { runSeoAndConversionAudit } from "@/lib/seo-analyzer";
import type {
  AiOptimizationResult,
  KeywordAnalysisResult,
  SavedIdea,
  SeoAuditResult,
  TrackedChannel,
  VideoItem,
} from "@/lib/types";

interface SeoStudioTabProps {
  activeChannel: TrackedChannel | undefined;
  initialVideoToAudit: VideoItem | null;
  onSaveIdea: (idea: Partial<SavedIdea>) => Promise<void>;
}

const DEFAULT_TITLE =
  "5 Công cụ AI Miễn Phí giúp tiết kiệm 15 giờ làm việc mỗi tuần (2026)";
const DEFAULT_KEYWORD = "công cụ ai miễn phí";
const DEFAULT_DESCRIPTION =
  "Tổng hợp 5 công cụ AI miễn phí thực chiến nhất cho dân văn phòng & người sáng tạo nội dung.\n\n👉 Đăng ký kênh nhận tài liệu mới mỗi tuần: https://www.youtube.com/@MinhTechAI?sub_confirmation=1\n\n00:00 Lý do bạn tốn hàng giờ mỗi ngày\n01:45 Công cụ #1: Tự động hóa ghi chú\n04:30 Công cụ #2: Thiết kế slide 30 giây\n\n💬 Bạn thích công cụ số mấy nhất? Bình luận bên dưới nhé!";
const DEFAULT_TAGS =
  "công cụ ai miễn phí, ai cho dân văn phòng, tự động hóa công việc, hướng dẫn ai 2026, tăng năng suất làm việc, chatgpt thực chiến";

export function SeoStudioTab({
  activeChannel,
  initialVideoToAudit,
  onSaveIdea,
}: SeoStudioTabProps) {
  const [subTab, setSubTab] = useState<"audit" | "keyword">("audit");

  const initTitle = initialVideoToAudit?.title ?? DEFAULT_TITLE;
  const initKeyword = initialVideoToAudit
    ? initialVideoToAudit.tags[0] || ""
    : DEFAULT_KEYWORD;
  const initDescription =
    initialVideoToAudit?.description ?? DEFAULT_DESCRIPTION;
  const initTagsText = initialVideoToAudit
    ? initialVideoToAudit.tags.join(", ")
    : DEFAULT_TAGS;
  const initIsShort = initialVideoToAudit?.isShort ?? false;
  const initStats = initialVideoToAudit
    ? {
        views: initialVideoToAudit.views,
        likes: initialVideoToAudit.likes,
        comments: initialVideoToAudit.comments,
      }
    : { views: 0, likes: 0, comments: 0 };

  // Audit state
  const [videoUrlInput, setVideoUrlInput] = useState("");
  const [fetchingUrl, setFetchingUrl] = useState(false);
  const [title, setTitle] = useState(initTitle);
  const [targetKeyword, setTargetKeyword] = useState(initKeyword);
  const [description, setDescription] = useState(initDescription);
  const [tagsText, setTagsText] = useState(initTagsText);
  const [isShort, setIsShort] = useState(initIsShort);
  const [liveStats, setLiveStats] = useState<{
    views: number;
    likes: number;
    comments: number;
  }>(initStats);

  const [auditResult, setAuditResult] = useState<SeoAuditResult | null>(() =>
    runSeoAndConversionAudit({
      title: initTitle,
      description: initDescription,
      tags: initTagsText
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
      targetKeyword: initKeyword,
      channelHandle: activeChannel?.handle || "@KenhCuaBan",
      isShort: initIsShort,
      views: initStats.views,
      likes: initStats.likes,
      comments: initStats.comments,
    })
  );
  const [auditing, setAuditing] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);

  // AI Optimizer state
  const [aiLoading, setAiLoading] = useState(false);
  const [aiResult, setAiResult] = useState<{
    data: AiOptimizationResult;
    usedAi: boolean;
  } | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Keyword Explorer state
  const [kwQuery, setKwQuery] = useState("");
  const [kwLoading, setKwLoading] = useState(false);
  const [kwError, setKwError] = useState<string | null>(null);
  const [kwResult, setKwResult] = useState<KeywordAnalysisResult | null>(null);

  const runManualAudit = async (customPayload?: {
    title: string;
    description: string;
    tags: string[];
    targetKeyword: string;
    isShort: boolean;
    views: number;
    likes: number;
    comments: number;
  }) => {
    setAuditing(true);
    setAuditError(null);
    try {
      const payload = customPayload || {
        title,
        description,
        tags: tagsText
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        targetKeyword,
        isShort,
        views: liveStats.views,
        likes: liveStats.likes,
        comments: liveStats.comments,
      };
      const res = await fetch("/api/seo/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          channelHandle: activeChannel?.handle || "@KenhCuaBan",
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi chấm điểm SEO");
      setAuditResult(json.audit);
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Lỗi chấm điểm SEO");
    } finally {
      setAuditing(false);
    }
  };

  const handleFetchByUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!videoUrlInput.trim()) return;
    setFetchingUrl(true);
    setAuditError(null);
    try {
      const res = await fetch("/api/seo/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          videoUrl: videoUrlInput.trim(),
          targetKeyword,
          channelHandle: activeChannel?.handle || "@KenhCuaBan",
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Không thể quét URL này");

      if (json.fetchedVideo) {
        const v = json.fetchedVideo as VideoItem;
        setTitle(v.title);
        setDescription(v.description);
        setTagsText(v.tags.join(", "));
        setIsShort(v.isShort);
        if (!targetKeyword && v.tags[0]) setTargetKeyword(v.tags[0]);
        setLiveStats({ views: v.views, likes: v.likes, comments: v.comments });
      }
      setAuditResult(json.audit);
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Lỗi khi tải video");
    } finally {
      setFetchingUrl(false);
    }
  };

  const handleAiOptimize = async () => {
    setAiLoading(true);
    try {
      const res = await fetch("/api/seo/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "aiOptimize",
          topicOrTitle: title,
          targetKeyword: targetKeyword || title,
          channelHandle: activeChannel?.handle || "@KenhCuaBan",
          niche: activeChannel?.niche || "Sáng tạo nội dung",
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi tối ưu AI");
      setAiResult(json);
    } catch (err) {
      setAuditError(err instanceof Error ? err.message : "Lỗi tối ưu AI");
    } finally {
      setAiLoading(false);
    }
  };

  const handleAnalyzeKeyword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!kwQuery.trim()) return;
    setKwLoading(true);
    setKwError(null);
    try {
      const res = await fetch("/api/seo/keyword", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ keyword: kwQuery.trim() }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi phân tích từ khóa");
      setKwResult(json);
    } catch (err) {
      setKwError(err instanceof Error ? err.message : "Lỗi phân tích từ khóa");
    } finally {
      setKwLoading(false);
    }
  };

  const copyText = (id: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  return (
    <div className="space-y-6">
      {/* Sub-navigation Pills */}
      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-2 w-fit">
        <button
          onClick={() => setSubTab("audit")}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs sm:text-sm font-semibold transition cursor-pointer ${
            subTab === "audit"
              ? "bg-red-600 text-white shadow"
              : "text-zinc-400 hover:text-white"
          }`}
        >
          <FileSearch className="h-4 w-4" />
          Chấm điểm SEO & Tối ưu Chuyển Đổi Sub (100đ)
        </button>
        <button
          onClick={() => setSubTab("keyword")}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-xs sm:text-sm font-semibold transition cursor-pointer ${
            subTab === "keyword"
              ? "bg-red-600 text-white shadow"
              : "text-zinc-400 hover:text-white"
          }`}
        >
          <Compass className="h-4 w-4" />
          Khám phá Từ khóa Mỏ Vàng (Cho kênh nhỏ)
        </button>
      </div>

      {subTab === "audit" ? (
        <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
          {/* Left Editor Column */}
          <div className="xl:col-span-6 space-y-5">
            {/* Import Live URL */}
            <form
              onSubmit={handleFetchByUrl}
              className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4"
            >
              <label className="block text-xs font-semibold text-zinc-300 mb-2 flex items-center gap-1.5">
                <Link2 className="h-3.5 w-3.5 text-red-400" />
                Quét trực tiếp từ Link Video YouTube (Của bạn hoặc Đối thủ)
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={videoUrlInput}
                  onChange={(e) => setVideoUrlInput(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=... hoặc shorts/..."
                  className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2 text-xs sm:text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={fetchingUrl || !videoUrlInput.trim()}
                  className="shrink-0 rounded-xl bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 px-4 py-2 text-xs font-semibold text-white transition cursor-pointer"
                >
                  {fetchingUrl ? "Đang tải..." : "Tải dữ liệu"}
                </button>
              </div>
            </form>

            {/* Metadata Form */}
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-white">
                  Soạn thảo / Kiểm tra Metadata trước khi Đăng
                </h3>
                <label className="inline-flex items-center gap-2 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isShort}
                    onChange={(e) => setIsShort(e.target.checked)}
                    className="rounded accent-red-600"
                  />
                  Là YouTube Shorts (&le; 3 phút)
                </label>
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-zinc-300">
                    Từ khóa mục tiêu chính
                  </span>
                  <span className="text-zinc-500">
                    Cụm từ khán giả gõ tìm kiếm
                  </span>
                </div>
                <input
                  type="text"
                  value={targetKeyword}
                  onChange={(e) => setTargetKeyword(e.target.value)}
                  placeholder="VD: tự học tiếng anh giao tiếp"
                  className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-3.5 py-2 text-sm text-white focus:border-red-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-zinc-300">Tiêu đề Video</span>
                  <span
                    className={
                      title.length >= 42 && title.length <= 72
                        ? "text-emerald-400 font-medium"
                        : "text-amber-400"
                    }
                  >
                    {title.length}/70 ký tự tối ưu
                  </span>
                </div>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-3.5 py-2.5 text-sm font-medium text-white focus:border-red-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-zinc-300">
                    Phần Mô tả (Description & Phễu Kéo Sub)
                  </span>
                  <span className="text-zinc-500">{description.length} ký tự</span>
                </div>
                <textarea
                  rows={7}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-3.5 py-2.5 text-xs sm:text-sm text-zinc-200 leading-relaxed focus:border-red-500 focus:outline-none"
                />
              </div>

              <div>
                <div className="flex justify-between text-xs mb-1">
                  <span className="font-medium text-zinc-300">
                    Thẻ Tags (Ngăn cách bằng dấu phẩy)
                  </span>
                  <span
                    className={
                      tagsText.length <= 500
                        ? "text-zinc-400"
                        : "text-red-400 font-semibold"
                    }
                  >
                    {tagsText.length}/500 ký tự
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={tagsText}
                  onChange={(e) => setTagsText(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700/90 bg-zinc-950 px-3.5 py-2 text-xs text-zinc-300 focus:border-red-500 focus:outline-none"
                />
              </div>

              {auditError && (
                <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-3.5 py-2.5 text-xs text-red-300">
                  {auditError}
                </div>
              )}

              <div className="flex flex-wrap gap-2.5 pt-1">
                <button
                  onClick={() => runManualAudit()}
                  disabled={auditing}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 px-4 py-2.5 text-sm font-semibold text-white transition cursor-pointer"
                >
                  <Sparkles className="h-4 w-4" />
                  {auditing ? "Đang chấm điểm..." : "Chấm điểm SEO & Kéo Sub"}
                </button>

                <button
                  onClick={handleAiOptimize}
                  disabled={aiLoading}
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/15 hover:bg-amber-500/25 px-4 py-2.5 text-sm font-semibold text-amber-300 transition cursor-pointer"
                >
                  <Wand2 className="h-4 w-4" />
                  {aiLoading ? "AI đang viết..." : "Tối ưu tự động (AI)"}
                </button>
              </div>
            </div>

            {/* AI / Smart Optimization Suggestions Box */}
            {aiResult && (
              <div className="rounded-2xl border border-amber-500/35 bg-gradient-to-br from-amber-950/25 via-zinc-900 to-zinc-900 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-bold text-amber-300 flex items-center gap-2">
                    <Wand2 className="h-4 w-4" />
                    Đề xuất tối ưu CTR & Kịch bản Kéo Sub{" "}
                    {aiResult.usedAi ? "(Gemini AI)" : "(Công thức Chuẩn)"}
                  </h4>
                </div>

                <div>
                  <div className="text-xs font-semibold text-zinc-300 mb-2">
                    5 Phương án Tiêu đề CTR cao (Bấm để áp dụng ngay):
                  </div>
                  <div className="space-y-1.5">
                    {aiResult.data.titles.map((t, i) => (
                      <button
                        key={i}
                        onClick={() => setTitle(t)}
                        className="w-full text-left rounded-xl border border-zinc-800 bg-zinc-950/80 hover:border-amber-500/50 px-3 py-2 text-xs text-zinc-200 transition flex items-center justify-between gap-2 cursor-pointer"
                      >
                        <span>{t}</span>
                        <span className="shrink-0 text-[11px] text-amber-400 font-medium">
                          Áp dụng
                        </span>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5">
                  <div className="text-xs font-semibold text-emerald-400 mb-1">
                    🎙️ Lời mở đầu 5–10 giây giữ chân người xem (Tăng Watch Time):
                  </div>
                  <p className="text-xs text-zinc-300 italic leading-relaxed">
                    {aiResult.data.hookScript5s}
                  </p>
                </div>

                <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5">
                  <div className="text-xs font-semibold text-rose-400 mb-1">
                    💡 Mẹo chuyển đổi người xem thành Subscriber thật:
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {aiResult.data.subTriggerTip}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      setDescription(aiResult.data.seoDescription);
                      setTagsText(aiResult.data.tags.join(", "));
                    }}
                    className="rounded-xl bg-amber-500 hover:bg-amber-400 px-3.5 py-2 text-xs font-bold text-zinc-950 transition cursor-pointer"
                  >
                    Áp dụng luôn Mô tả chuẩn SEO + Bộ 12 Tags vào biểu mẫu
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Right Audit Scoreboard Column */}
          <div className="xl:col-span-6 space-y-5">
            {auditResult && (
              <>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-5 pb-5 border-b border-zinc-800">
                    <div className="flex items-center gap-4">
                      <div
                        className={`h-20 w-20 rounded-2xl flex flex-col items-center justify-center border-2 shrink-0 ${
                          auditResult.totalScore >= 80
                            ? "border-emerald-500 bg-emerald-500/10 text-emerald-300"
                            : auditResult.totalScore >= 60
                            ? "border-amber-500 bg-amber-500/10 text-amber-300"
                            : "border-red-500 bg-red-500/10 text-red-300"
                        }`}
                      >
                        <span className="text-2xl font-extrabold">
                          {auditResult.totalScore}
                        </span>
                        <span className="text-[10px] uppercase tracking-wider">
                          Hạng {auditResult.grade}
                        </span>
                      </div>
                      <div>
                        <h3 className="text-lg font-bold text-white">
                          Điểm Chuẩn SEO & Chuyển Đổi Sub
                        </h3>
                        <p className="text-xs text-zinc-400 mt-1">
                          Đạt{" "}
                          <strong className="text-white">
                            {
                              auditResult.checks.filter((c) => c.passed).length
                            }
                            /{auditResult.checks.length}
                          </strong>{" "}
                          tiêu chí quan trọng giúp video dễ cắn đề xuất & thu hút người đăng ký mới.
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* 4 Category Sub-bars */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-5">
                    {[
                      {
                        label: "Tiêu đề & CTR",
                        val: auditResult.categoryScores.title,
                        max: 30,
                      },
                      {
                        label: "Mô tả & Phễu",
                        val: auditResult.categoryScores.description,
                        max: 30,
                      },
                      {
                        label: "Thẻ Từ Khóa",
                        val: auditResult.categoryScores.tags,
                        max: 20,
                      },
                      {
                        label: "Kéo Sub Thật",
                        val: auditResult.categoryScores.conversion,
                        max: 20,
                      },
                    ].map((cat) => (
                      <div
                        key={cat.label}
                        className="rounded-xl border border-zinc-800/90 bg-zinc-950/60 p-3"
                      >
                        <div className="text-[11px] text-zinc-400 mb-1">
                          {cat.label}
                        </div>
                        <div className="text-sm font-bold text-white">
                          {cat.val}/{cat.max}
                        </div>
                        <div className="mt-1.5 h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                          <div
                            className="h-full rounded-full bg-red-500"
                            style={{ width: `${(cat.val / cat.max) * 100}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Ready-to-copy Subscribe CTA Block */}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-bold text-zinc-200">
                      📋 Khối Mô tả Kéo Sub 1-Click mẫu (Dán thêm vào cuối Mô tả)
                    </span>
                    <button
                      onClick={() => {
                        copyText("cta-block", auditResult.suggestedCtaBlock);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                    >
                      {copiedId === "cta-block" ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                          Đã chép
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          Sao chép
                        </>
                      )}
                    </button>
                  </div>
                  <pre className="whitespace-pre-wrap rounded-xl bg-zinc-950 border border-zinc-800 p-3 text-xs text-zinc-300 font-sans leading-relaxed">
                    {auditResult.suggestedCtaBlock}
                  </pre>
                </div>

                {/* Detailed 14 Checks */}
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 space-y-2.5 max-h-[540px] overflow-y-auto">
                  <h4 className="text-sm font-bold text-white mb-2">
                    Chi tiết 14 hạng mục kiểm tra
                  </h4>
                  {auditResult.checks.map((item) => (
                    <div
                      key={item.id}
                      className={`rounded-xl border p-3.5 ${
                        item.passed
                          ? "border-zinc-800/80 bg-zinc-950/40"
                          : "border-amber-500/30 bg-amber-950/10"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex items-start gap-2.5">
                          {item.passed ? (
                            <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                          ) : (
                            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                          )}
                          <div>
                            <div className="text-xs font-semibold text-zinc-100">
                              {item.label}
                            </div>
                            <p className="text-xs text-zinc-400 mt-0.5">
                              {item.feedback}
                            </p>
                            {item.actionTip && (
                              <p className="text-xs text-amber-300 mt-1 font-medium">
                                → Gợi ý sửa: {item.actionTip}
                              </p>
                            )}
                          </div>
                        </div>
                        <span className="shrink-0 text-xs font-bold text-zinc-300">
                          {item.score}/{item.maxScore}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        /* Keyword Opportunity Explorer Sub-tab */
        <div className="space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
            <h2 className="text-lg font-bold text-white mb-1">
              Khám phá Từ Khóa Ngách Dễ Nổ View Cho Kênh Nhỏ
            </h2>
            <p className="text-xs sm:text-sm text-zinc-400 mb-4">
              Hệ thống quét Top 15 video xếp hạng đầu trên YouTube để đếm xem có bao nhiêu{" "}
              <strong className="text-emerald-300">
                kênh nhỏ (&lt; 15.000 Subs) đang lọt Top với lượng view cao
              </strong>
              . Nếu kênh nhỏ làm được, kênh của bạn cũng hoàn toàn lọt Top và hút Sub thật từ tìm kiếm!
            </p>

            <form onSubmit={handleAnalyzeKeyword} className="flex gap-2.5">
              <input
                type="text"
                value={kwQuery}
                onChange={(e) => setKwQuery(e.target.value)}
                placeholder="Nhập chủ đề hoặc từ khóa ngách (VD: tự động hóa excel, học tiếng trung tại nhà, đầu tư chứng khoán...)"
                className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={kwLoading || !kwQuery.trim()}
                className="shrink-0 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-6 py-3 text-sm font-semibold text-white transition cursor-pointer"
              >
                {kwLoading ? "Đang phân tích..." : "Phân tích Từ khóa"}
              </button>
            </form>

            {kwError && (
              <div className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
                {kwError}
              </div>
            )}
          </div>

          {kwResult && (
            <div className="space-y-6">
              {!kwResult.isLiveData && (
                <div className="rounded-xl border border-amber-500/35 bg-amber-500/10 px-4 py-3 text-xs text-amber-200">
                  ℹ️ Đang hiển thị bản mô phỏng cấu trúc từ khóa cho{" "}
                  <strong>&ldquo;{kwResult.keyword}&rdquo;</strong>. Hãy dán khóa YouTube Data API v3 miễn phí ở mục <strong>Quản lý Kênh & API</strong> để lấy số liệu Top 15 video thời gian thực trên YouTube!
                </div>
              )}

              {/* Score Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
                  <div className="text-xs text-zinc-400 mb-1">
                    ĐIỂM CƠ HỘI TỔNG HỢP
                  </div>
                  <div className="text-3xl font-extrabold text-emerald-400">
                    {kwResult.overallScore}/100
                  </div>
                  <div className="mt-2 text-xs font-semibold text-white">
                    {kwResult.verdict === "golden"
                      ? "🏆 Mỏ vàng kéo Sub cho kênh nhỏ!"
                      : kwResult.verdict === "good"
                      ? "✅ Cơ hội tốt để làm video"
                      : kwResult.verdict === "competitive"
                      ? "⚠️ Cạnh tranh cao (Nên thu hẹp ngách)"
                      : "📉 Lượng tìm kiếm thấp"}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
                  <div className="text-xs text-zinc-400 mb-1">
                    SỨC CẦU LƯỢT XEM (DEMAND)
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {kwResult.demandScore}/100
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">
                    View trung bình Top đầu:{" "}
                    <strong className="text-zinc-200">
                      {formatNumber(kwResult.avgViews)}
                    </strong>
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
                  <div className="text-xs text-zinc-400 mb-1">
                    ĐỘ DỄ LỌT TOP (KÊNH NHỎ)
                  </div>
                  <div className="text-2xl font-bold text-amber-300">
                    {kwResult.opportunityScore}/100
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">
                    Có{" "}
                    <strong className="text-emerald-400">
                      {kwResult.smallChannelsInTop10}/10
                    </strong>{" "}
                    kênh &lt;15k subs đang đứng Top!
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5">
                  <div className="text-xs text-zinc-400 mb-1">
                    THỜI LƯỢNG KHUYẾN NGHỊ
                  </div>
                  <div className="text-base font-bold text-white mt-1">
                    {kwResult.optimalDurationRange}
                  </div>
                  <div className="mt-2 text-xs text-zinc-400">
                    Tỷ lệ Shorts trong Top: {kwResult.shortsRatio}%
                  </div>
                </div>
              </div>

              {/* Tags + Title Formulas */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-white">
                      Bộ Thẻ Tags Chiến Thắng (Trích xuất từ Top Video)
                    </h3>
                    <button
                      onClick={() =>
                        copyText(
                          "kw-tags",
                          kwResult.recommendedTags.join(", ")
                        )
                      }
                      className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                    >
                      {copiedId === "kw-tags" ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                          Đã chép tất cả
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          Chép toàn bộ Tags
                        </>
                      )}
                    </button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {kwResult.recommendedTags.map((t) => (
                      <span
                        key={t}
                        className="rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1 text-xs text-zinc-300"
                      >
                        #{t}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
                  <h3 className="text-sm font-bold text-white mb-3">
                    Gợi ý Công thức Đặt Tiêu đề Kéo Sub cho Từ khóa này
                  </h3>
                  <div className="space-y-2">
                    {kwResult.titlePatterns.map((pat, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/70 px-3.5 py-2.5 text-xs text-zinc-200"
                      >
                        <span>{pat}</span>
                        <button
                          onClick={() =>
                            onSaveIdea({
                              title: pat,
                              remakeTitle: pat,
                              targetKeyword: kwResult.keyword,
                              tags: kwResult.recommendedTags,
                              format: "long",
                              notes: `Từ khóa mục tiêu "${kwResult.keyword}" đạt điểm cơ hội ${kwResult.overallScore}/100.`,
                            })
                          }
                          className="shrink-0 inline-flex items-center gap-1 rounded-lg bg-red-600/20 hover:bg-red-600 text-red-300 hover:text-white px-2.5 py-1 font-semibold transition cursor-pointer"
                        >
                          <BookmarkPlus className="h-3.5 w-3.5" />
                          Lưu ý tưởng
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Top Ranking Videos */}
              {kwResult.topVideos.length > 0 && (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
                  <h3 className="text-sm font-bold text-white mb-4">
                    Top Video đang thống trị từ khóa &ldquo;{kwResult.keyword}&rdquo;
                  </h3>
                  <div className="divide-y divide-zinc-800/70">
                    {kwResult.topVideos.slice(0, 8).map((v) => (
                      <div
                        key={v.id}
                        className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          {v.thumbnailUrl && (
                            <img
                              src={v.thumbnailUrl}
                              alt={v.title}
                              className="h-12 w-20 rounded-lg object-cover shrink-0"
                            />
                          )}
                          <div className="min-w-0">
                            <p className="text-xs sm:text-sm font-semibold text-white line-clamp-1">
                              {v.title}
                            </p>
                            <p className="text-xs text-zinc-400">
                              {v.channelTitle} •{" "}
                              <span
                                className={
                                  v.channelSubscribers < 15000
                                    ? "text-emerald-400 font-semibold"
                                    : ""
                                }
                              >
                                {formatCompact(v.channelSubscribers)} subs
                              </span>{" "}
                              • Thời lượng {formatDuration(v.durationSeconds)}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3 shrink-0 text-xs">
                          <span className="font-bold text-white">
                            {formatCompact(v.views)} views
                          </span>
                          <span className="rounded-full bg-emerald-500/15 text-emerald-300 px-2.5 py-0.5 font-semibold">
                            {v.viewsToSubsRatio.toFixed(1)}x Subs
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
