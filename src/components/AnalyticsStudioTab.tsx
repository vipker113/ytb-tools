"use client";

import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  Eye,
  KeyRound,
  Link2,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Wand2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  formatCompact,
  formatDateShort,
  formatNumber,
  getOutlierBadgeStyle,
} from "@/lib/format";
import {
  runSeoAndConversionAudit,
  splitDescriptionEditorialAndCredits,
} from "@/lib/seo-analyzer";
import type {
  AiSeoRewriteProposal,
  TrackedChannel,
  VideoAnalyticsMetrics,
  VideoItem,
  YoutubeOAuthState,
} from "@/lib/types";
import type { YoutubeAnalyticsReportResponse } from "@/lib/youtube-analytics";

interface AnalyticsStudioTabProps {
  channel: TrackedChannel | undefined;
  youtubeOAuth?: YoutubeOAuthState | null;
  smartClicks: number;
  onUpdateMilestone: (channelId: string, milestone: number) => Promise<void>;
  onApplyLiveStudioMetadata: (params: {
    videoId: string;
    title: string;
    description: string;
    tags: string[];
    pinnedComment?: string;
  }) => Promise<void>;
  onRescueAllOldVideos: () => Promise<void>;
  onGoToSettings: () => void;
  onNotify: (msg: string) => void;
}

function getShortsBottleneckDiagnosis(
  video: VideoItem,
  metrics: VideoAnalyticsMetrics | undefined,
  seoScore: number
): { badge: string; color: "emerald" | "amber" | "rose" | "sky"; detail: string } {
  const stayed = metrics?.stayedToWatchPct ?? null;
  const apv = metrics?.averageViewPercentage ?? 0;

  if (stayed !== null && stayed < 68) {
    return {
      badge: "Cần siết Hook 0–3s",
      color: "rose",
      detail: `Chỉ ${stayed}% ở lại xem (mốc bùng nổ Shorts Mỹ là ≥75%). Khán giả vuốt qua ở 2 giây đầu — cần mở cảnh bằng xung đột thị giác ngay 0.3s đầu.`,
    };
  }
  if (apv > 0 && apv < 85) {
    return {
      badge: "Rơi nhịp giữa/cuối",
      color: "amber",
      detail: `Xem trung bình đạt ${apv}% (${metrics?.averageViewDurationSec}s/${video.durationSeconds}s). Để vượt trần 1.3K views lên 50K+, cần rút gọn đoạn giải thích giữa và nối câu cuối mượt về câu đầu (Loop).`,
    };
  }
  if (stayed !== null && stayed >= 75 && apv >= 92) {
    return {
      badge: "Giữ chân chuẩn Viral",
      color: "emerald",
      detail: `${stayed}% không vuốt bỏ & ${apv}% APV — thuật toán đánh giá rất tốt! Tối ưu thêm Bình luận ghim tranh luận để kích vòng phân phối thứ 2.`,
    };
  }
  if (seoScore < 82) {
    return {
      badge: `SEO ${seoScore}đ (Thiếu phễu Sub)`,
      color: "amber",
      detail:
        "Metadata chưa tối ưu từ khóa tìm kiếm hoặc thiếu link ?sub_confirmation=1 kéo Sub tự nhiên. Bấm 'AI Tối Ưu SEO' bên phải để nâng cấp ngay!",
    };
  }
  if (video.views >= 1000 && video.views <= 1500) {
    return {
      badge: "Chạm trần Seed 1.2K",
      color: "sky",
      detail:
        "Video vượt qua vòng kiểm tra ban đầu (~1.1K–1.3K views). Kết nối/xem cột % Không vuốt bỏ để biết chính xác điểm nghẽn lên 50K views.",
    };
  }
  return {
    badge: "Đang phân phối ổn định",
    color: "emerald",
    detail: `Tương tác ${video.engagementRate.toFixed(1)}% • SEO ${seoScore}đ.`,
  };
}

let clientAnalyticsCache: {
  data: YoutubeAnalyticsReportResponse;
  expiresAt: number;
} | null = null;

export function AnalyticsStudioTab({
  channel,
  youtubeOAuth,
  smartClicks,
  onUpdateMilestone,
  onApplyLiveStudioMetadata,
  onRescueAllOldVideos,
  onGoToSettings,
  onNotify,
}: AnalyticsStudioTabProps) {
  const [analytics, setAnalytics] =
    useState<YoutubeAnalyticsReportResponse | null>(
      () => clientAnalyticsCache?.data || null
    );
  const [loadingAnalytics, setLoadingAnalytics] = useState(
    () => !clientAnalyticsCache
  );
  const [rescuingAll, setRescuingAll] = useState(false);

  const [editingMilestone, setEditingMilestone] = useState(false);
  const [milestoneInput, setMilestoneInput] = useState("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Live Video AI SEO Rewrite Modal State
  const [targetVideo, setTargetVideo] = useState<VideoItem | null>(null);
  const [aiLoadingId, setAiLoadingId] = useState<string | null>(null);
  const [liveProposal, setLiveProposal] =
    useState<AiSeoRewriteProposal | null>(null);
  const [selectedAltTitle, setSelectedAltTitle] = useState("");
  const [applyingStudio, setApplyingStudio] = useState(false);

  const fetchAnalytics = useCallback(async (force = false) => {
    if (
      !force &&
      clientAnalyticsCache &&
      clientAnalyticsCache.expiresAt > Date.now()
    ) {
      setAnalytics(clientAnalyticsCache.data);
      setLoadingAnalytics(false);
      return;
    }
    setLoadingAnalytics(true);
    try {
      const url = force
        ? "/api/youtube/analytics?force=1"
        : "/api/youtube/analytics";
      const res = await fetch(url, { cache: "no-store" });
      const json = (await res.json()) as YoutubeAnalyticsReportResponse;
      clientAnalyticsCache = {
        data: json,
        expiresAt: Date.now() + (json.ok ? 60_000 : 25_000),
      };
      setAnalytics(json);
    } catch {
      // ignore
    } finally {
      setLoadingAnalytics(false);
    }
  }, []);

  useEffect(() => {
    void fetchAnalytics(false);
  }, [fetchAnalytics]);

  const cleanHandle = channel?.handle
    ? channel.handle.startsWith("@")
      ? channel.handle
      : `@${channel.handle}`
    : "@proofofwonderscience";

  const copyText = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const enrichedVideos = useMemo(() => {
    if (!channel) return [];
    return channel.recentVideos.map((v) => {
      const audit = runSeoAndConversionAudit({
        title: v.title,
        description: v.description,
        tags: v.tags,
        channelHandle: cleanHandle,
        isShort: v.isShort,
        views: v.views,
        likes: v.likes,
        comments: v.comments,
      });
      const metrics = analytics?.byVideoId?.[v.id];
      const diagnosis = getShortsBottleneckDiagnosis(
        v,
        metrics,
        audit.totalScore
      );
      return { video: v, audit, metrics, diagnosis };
    });
  }, [channel, cleanHandle, analytics]);

  const videosNeedingSeoFixCount = useMemo(
    () => enrichedVideos.filter((x) => x.audit.totalScore < 82).length,
    [enrichedVideos]
  );

  const handleOpenAiFixForLiveVideo = async (v: VideoItem) => {
    setAiLoadingId(v.id);
    setTargetVideo(v);
    setLiveProposal(null);
    try {
      const res = await fetch("/api/seo/audit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "aiRewriteSeoDiff",
          title: v.title,
          targetKeyword: v.tags[0] || "",
          description: v.description,
          tags: v.tags,
          pinnedComment: "",
          channelHandle: cleanHandle,
          niche: channel?.niche || "Science & Space Documentary Shorts",
          isShort: v.isShort,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json?.proposal) {
        throw new Error(json?.error || "Lỗi gọi AI tối ưu SEO.");
      }
      const prop = json.proposal as AiSeoRewriteProposal;
      setLiveProposal(prop);
      setSelectedAltTitle(prop.proposed.title);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Không thể chạy AI tối ưu");
      setTargetVideo(null);
    } finally {
      setAiLoadingId(null);
    }
  };

  const handleConfirmApplyToYoutubeStudio = async () => {
    if (!targetVideo || !liveProposal) return;
    setApplyingStudio(true);
    try {
      await onApplyLiveStudioMetadata({
        videoId: targetVideo.id,
        title: selectedAltTitle || liveProposal.proposed.title,
        description: liveProposal.proposed.fullDescription,
        tags: liveProposal.proposed.tags,
        pinnedComment: liveProposal.proposed.pinnedComment,
      });
      setTargetVideo(null);
      setLiveProposal(null);
    } finally {
      setApplyingStudio(false);
    }
  };

  if (!channel) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-12 text-center space-y-4">
        <BarChart3 className="mx-auto h-12 w-12 text-red-400" />
        <h2 className="text-lg font-extrabold text-white">
          Chưa kết nối kênh YouTube
        </h2>
        <p className="text-xs text-zinc-400 max-w-md mx-auto">
          Hãy kết nối kênh của bạn trong mục Cài đặt & API để xem trọn bộ phân tích Shorts Retention & tăng trưởng Subscribers.
        </p>
        <button
          type="button"
          onClick={onGoToSettings}
          className="rounded-xl bg-red-600 hover:bg-red-500 px-5 py-2.5 text-xs font-bold text-white cursor-pointer"
        >
          Mở Cài đặt & Kết nối Kênh
        </button>
      </div>
    );
  }

  const directSubUrl = `https://www.youtube.com/${cleanHandle}?sub_confirmation=1`;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=140x140&margin=6&data=${encodeURIComponent(
    directSubUrl
  )}`;
  const progressPct = Math.min(
    100,
    Math.round(
      (channel.subscribers / Math.max(channel.targetMilestone, 1)) * 1000
    ) / 10
  );

  const chronoVideos = [...channel.recentVideos].slice(0, 12).reverse();
  const maxViews = Math.max(
    ...chronoVideos.map((v) => v.views),
    channel.medianViewsRecent || 100,
    100
  );

  return (
    <div className="space-y-6">
      {/* 1. YOUTUBE ANALYTICS API (0₫) CONNECTION / UPGRADE BANNER WHEN NEEDED */}
      {analytics && !analytics.ok && (
        <div className="rounded-2xl border border-amber-500/40 bg-gradient-to-r from-amber-950/30 via-zinc-900 to-zinc-950 p-5 flex flex-col lg:flex-row lg:items-center justify-between gap-4 shadow-lg">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-300">
              <KeyRound className="h-4 w-4" />
              Mở Khóa Chỉ Số Sống Còn Shorts (% Không Vuốt Bỏ & % Xem Trung Bình — 0₫)
            </div>
            <p className="text-xs text-zinc-200 leading-relaxed max-w-3xl">
              {analytics.messageVi}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            {analytics.code === "needs_api_enable" && analytics.enableApiUrl && (
              <a
                href={analytics.enableApiUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 px-4 py-2.5 text-xs font-extrabold text-zinc-950 shadow transition"
              >
                1. Bật YouTube Analytics API (Google Cloud)
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            )}

            <a
              href={analytics.oauthStartUrl || "/api/youtube/oauth/start"}
              className="inline-flex items-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-500 px-4 py-2.5 text-xs font-extrabold text-white shadow transition"
            >
              {analytics.code === "needs_api_enable"
                ? "2. Cấp Quyền Đọc Analytics (1-Click)"
                : "🔐 Cấp Quyền Đọc Shorts Analytics (1-Click)"}
            </a>

            <button
              type="button"
              onClick={() => void fetchAnalytics(true)}
              disabled={loadingAnalytics}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3.5 py-2.5 text-xs font-bold text-zinc-200 cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  loadingAnalytics ? "animate-spin text-amber-400" : ""
                }`}
              />
              Kiểm tra lại
            </button>
          </div>
        </div>
      )}

      {/* 2. TOP 5 CORE CHANNEL & SHORTS RETENTION KPI CARDS */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3.5">
        {/* Subscribers + Goal */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-2">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span className="font-semibold flex items-center gap-1.5">
              <Users className="h-3.5 w-3.5 text-red-400" />
              Subscribers thật
            </span>
            <button
              type="button"
              onClick={() => {
                setMilestoneInput(String(channel.targetMilestone));
                setEditingMilestone((v) => !v);
              }}
              className="text-[10px] text-sky-400 hover:text-sky-300 font-semibold cursor-pointer"
            >
              Đích: {formatCompact(channel.targetMilestone)}
            </button>
          </div>
          <div className="text-2xl font-extrabold text-white">
            {formatNumber(channel.subscribers)}
          </div>
          {editingMilestone ? (
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const val = Number(milestoneInput);
                if (val > 0) {
                  await onUpdateMilestone(channel.id, val);
                  setEditingMilestone(false);
                }
              }}
              className="flex gap-1.5"
            >
              <input
                type="number"
                value={milestoneInput}
                onChange={(e) => setMilestoneInput(e.target.value)}
                className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-white"
              />
              <button
                type="submit"
                className="rounded-lg bg-emerald-600 px-2.5 py-1 text-[11px] font-bold text-white cursor-pointer"
              >
                Lưu
              </button>
            </form>
          ) : (
            <div className="space-y-1">
              <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-red-500 to-amber-400"
                  style={{ width: `${Math.max(progressPct, 2)}%` }}
                />
              </div>
              <div className="text-[10px] text-zinc-400">
                Đạt {progressPct}% cột mốc mục tiêu
              </div>
            </div>
          )}
        </div>

        {/* Total Views & Median */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-1.5">
          <span className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
            <Eye className="h-3.5 w-3.5 text-sky-400" />
            Tổng Views ({channel.videoCount} video)
          </span>
          <div className="text-2xl font-extrabold text-white">
            {formatNumber(channel.totalViews)}
          </div>
          <div className="text-[11px] text-zinc-400">
            Trung vị gần đây:{" "}
            <strong className="text-zinc-200">
              {formatNumber(channel.medianViewsRecent)}
            </strong>{" "}
            views/bài
          </div>
        </div>

        {/* Stayed-to-Watch % */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-1.5">
          <span className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
            <Activity className="h-3.5 w-3.5 text-emerald-400" />
            % Không vuốt bỏ TB
          </span>
          <div className="text-2xl font-extrabold text-white">
            {analytics?.ok && analytics.summary.avgStayedToWatchPct !== null
              ? `${analytics.summary.avgStayedToWatchPct}%`
              : "—"}
          </div>
          <div className="text-[11px] text-zinc-400">
            Chuẩn phá trần 50K+ views:{" "}
            <strong className="text-emerald-400">≥ 75%</strong>
          </div>
        </div>

        {/* Average Percentage Viewed (APV) */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-1.5">
          <span className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
            <TrendingUp className="h-3.5 w-3.5 text-amber-400" />
            % Xem trung bình (APV)
          </span>
          <div className="text-2xl font-extrabold text-white">
            {analytics?.ok && analytics.summary.avgViewPercentage !== null
              ? `${analytics.summary.avgViewPercentage}%`
              : "—"}
          </div>
          <div className="text-[11px] text-zinc-400">
            {analytics?.ok && analytics.summary.avgViewDurationSec !== null
              ? `Thời lượng xem TB: ${analytics.summary.avgViewDurationSec}s`
              : "Chuẩn giữ chân tốt: ≥ 95%"}
          </div>
        </div>

        {/* Net Subscribers from Videos */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-4 space-y-1.5">
          <span className="text-xs font-semibold text-zinc-400 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-violet-400" />
            Sub ròng từ Video & Giờ xem
          </span>
          <div className="text-2xl font-extrabold text-emerald-300">
            {analytics?.ok
              ? `+${formatNumber(analytics.summary.totalNetSubscribers)}`
              : `${channel.engagementRateAvg}% tương tác`}
          </div>
          <div className="text-[11px] text-zinc-400">
            {analytics?.ok
              ? `${formatNumber(
                  Math.round(analytics.summary.totalMinutesWatched / 60)
                )} giờ xem tích lũy`
              : "Cấp quyền Analytics để xem +Sub/video"}
          </div>
        </div>
      </div>

      {/* 3. PER-VIDEO SHORTS DIAGNOSTIC & 1-CLICK AI SEO RESCUE TABLE */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-4">
          <div>
            <h2 className="text-sm sm:text-base font-extrabold text-white">
              Bảng Phân Tích Chuyên Sâu Từng Video & Chẩn Đoán Điểm Nghẽn Thuật Toán
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Soi trực tiếp lý do video dừng ở mốc ~1.200 views hay bứt phá, đồng thời bấm{" "}
              <strong className="text-emerald-300">AI Tối Ưu SEO</strong> để nâng cấp các bài đã đăng ngay trên YouTube Studio.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {videosNeedingSeoFixCount > 0 && youtubeOAuth?.refreshToken && (
              <button
                type="button"
                disabled={rescuingAll}
                onClick={async () => {
                  setRescuingAll(true);
                  try {
                    await onRescueAllOldVideos();
                  } finally {
                    setRescuingAll(false);
                  }
                }}
                className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 px-3.5 py-2 text-xs font-extrabold text-amber-200 transition cursor-pointer"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {rescuingAll
                  ? "Đang vá hàng loạt..."
                  : `Gắn Nhanh Link Sub Cho ${videosNeedingSeoFixCount} Video Cũ`}
              </button>
            )}

            <button
              type="button"
              onClick={() => void fetchAnalytics(true)}
              disabled={loadingAnalytics}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3 py-2 text-xs font-semibold text-zinc-200 cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  loadingAnalytics ? "animate-spin text-emerald-400" : ""
                }`}
              />
              Làm mới Analytics
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[860px]">
            <thead>
              <tr className="border-b border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-400">
                <th className="py-2.5 pr-3">Video trên kênh</th>
                <th className="py-2.5 px-2.5">Lượt xem</th>
                <th className="py-2.5 px-2.5">% Không vuốt bỏ</th>
                <th className="py-2.5 px-2.5">% Xem TB (APV)</th>
                <th className="py-2.5 px-2.5">+Sub / Tương tác</th>
                <th className="py-2.5 px-2.5">Chẩn đoán Thuật toán</th>
                <th className="py-2.5 pl-2.5 text-right">Tối ưu Studio</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800/70 text-xs">
              {enrichedVideos.map(({ video, audit, metrics, diagnosis }) => {
                const stayed = metrics?.stayedToWatchPct ?? null;
                const apv = metrics?.averageViewPercentage ?? null;
                return (
                  <tr
                    key={video.id}
                    className="hover:bg-zinc-950/50 transition align-top"
                  >
                    {/* Video Info */}
                    <td className="py-3.5 pr-3 max-w-[290px]">
                      <div className="flex items-start gap-2.5">
                        <a
                          href={`https://www.youtube.com/shorts/${video.id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="h-14 w-10 shrink-0 rounded-lg overflow-hidden bg-zinc-950 border border-zinc-800 block"
                        >
                          {video.thumbnailUrl && (
                            <img
                              src={video.thumbnailUrl}
                              alt={video.title}
                              className="h-full w-full object-cover"
                            />
                          )}
                        </a>
                        <div className="min-w-0 space-y-1">
                          <a
                            href={`https://www.youtube.com/shorts/${video.id}`}
                            target="_blank"
                            rel="noreferrer"
                            className="font-bold text-white hover:text-sky-300 line-clamp-2 leading-snug"
                          >
                            {video.title}
                          </a>
                          <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-zinc-400">
                            <span>{formatDateShort(video.publishedAt)}</span>
                            <span>•</span>
                            <span>{video.durationSeconds}s</span>
                            <span>•</span>
                            <span
                              className={`rounded px-1.5 py-0.5 font-bold ${
                                audit.totalScore >= 85
                                  ? "bg-emerald-500/15 text-emerald-300"
                                  : audit.totalScore >= 68
                                  ? "bg-amber-500/15 text-amber-300"
                                  : "bg-rose-500/15 text-rose-300"
                              }`}
                            >
                              SEO {audit.totalScore}đ ({audit.grade})
                            </span>
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Views & Outlier */}
                    <td className="py-3.5 px-2.5 whitespace-nowrap">
                      <div className="font-extrabold text-white text-sm">
                        {formatNumber(video.views)}
                      </div>
                      <span
                        className={`inline-block mt-1 rounded-full px-2 py-0.5 text-[10px] font-bold ${getOutlierBadgeStyle(
                          video.outlierScore
                        )}`}
                      >
                        {video.outlierScore.toFixed(1)}x median
                      </span>
                    </td>

                    {/* Stayed to watch % */}
                    <td className="py-3.5 px-2.5 whitespace-nowrap">
                      {stayed !== null ? (
                        <div>
                          <span
                            className={`text-sm font-extrabold ${
                              stayed >= 75
                                ? "text-emerald-400"
                                : stayed >= 65
                                ? "text-amber-300"
                                : "text-rose-400"
                            }`}
                          >
                            {stayed}%
                          </span>
                          {metrics?.engagedViews !== undefined && (
                            <div className="text-[10px] text-zinc-400">
                              {formatNumber(metrics.engagedViews)} engaged
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="text-[11px] text-zinc-500">
                          Chờ Analytics
                        </span>
                      )}
                    </td>

                    {/* APV & AVD */}
                    <td className="py-3.5 px-2.5 whitespace-nowrap">
                      {apv !== null && apv > 0 ? (
                        <div>
                          <span
                            className={`text-sm font-extrabold ${
                              apv >= 95
                                ? "text-emerald-400"
                                : apv >= 78
                                ? "text-amber-300"
                                : "text-rose-400"
                            }`}
                          >
                            {apv}%
                          </span>
                          <div className="text-[10px] text-zinc-400">
                            TB {metrics?.averageViewDurationSec}s /{" "}
                            {video.durationSeconds}s
                          </div>
                        </div>
                      ) : (
                        <span className="text-[11px] text-zinc-500">—</span>
                      )}
                    </td>

                    {/* Net Subs & Engagement */}
                    <td className="py-3.5 px-2.5 whitespace-nowrap">
                      {metrics ? (
                        <div className="font-extrabold text-emerald-300">
                          {metrics.netSubscribers >= 0
                            ? `+${metrics.netSubscribers} sub`
                            : `${metrics.netSubscribers} sub`}
                        </div>
                      ) : null}
                      <div className="text-[11px] text-zinc-300">
                        👍 {formatNumber(video.likes)} • 💬 {video.comments} (
                        {video.engagementRate.toFixed(1)}%)
                      </div>
                    </td>

                    {/* Bottleneck Verdict */}
                    <td className="py-3.5 px-2.5 max-w-[260px]">
                      <span
                        className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-extrabold mb-1 ${
                          diagnosis.color === "emerald"
                            ? "bg-emerald-500/15 text-emerald-300"
                            : diagnosis.color === "rose"
                            ? "bg-rose-500/15 text-rose-300"
                            : diagnosis.color === "amber"
                            ? "bg-amber-500/15 text-amber-300"
                            : "bg-sky-500/15 text-sky-300"
                        }`}
                      >
                        {diagnosis.badge}
                      </span>
                      <p className="text-[11px] text-zinc-400 leading-snug">
                        {diagnosis.detail}
                      </p>
                    </td>

                    {/* 1-Click AI SEO Optimize */}
                    <td className="py-3.5 pl-2.5 text-right whitespace-nowrap">
                      <button
                        type="button"
                        disabled={aiLoadingId === video.id}
                        onClick={() => void handleOpenAiFixForLiveVideo(video)}
                        className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/40 bg-emerald-500/15 hover:bg-emerald-500/25 px-3 py-1.5 text-[11px] font-bold text-emerald-200 transition cursor-pointer"
                      >
                        {aiLoadingId === video.id ? (
                          <>
                            <RefreshCw className="h-3 w-3 animate-spin" />
                            AI...
                          </>
                        ) : (
                          <>
                            <Wand2 className="h-3 w-3" />
                            AI Tối Ưu SEO
                          </>
                        )}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. RECENT VIDEO VIEWS BAR CHART + SMART SUBSCRIBE LINK & QR */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Visual Bar Chart comparing videos against the 1.3K seed shelf */}
        <div className="lg:col-span-7 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 space-y-4">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-extrabold text-white">
                Biểu Đồ So Sánh Đà Lượt Xem Giữa Các Tập
              </h3>
              <p className="text-xs text-zinc-400">
                Đường chuẩn trung vị kênh:{" "}
                <strong className="text-amber-300">
                  {formatNumber(channel.medianViewsRecent)} views
                </strong>
              </p>
            </div>
          </div>

          <div className="grid grid-cols-12 gap-2 items-end h-44 pt-4 px-1">
            {chronoVideos.map((v) => {
              const hPct = Math.max(8, Math.round((v.views / maxViews) * 100));
              const aboveMedian = v.views >= channel.medianViewsRecent;
              return (
                <div
                  key={v.id}
                  className="col-span-2 sm:col-span-1 flex flex-col items-center gap-1.5 group"
                  title={`${v.title} — ${formatNumber(v.views)} views`}
                >
                  <span className="text-[9px] font-bold text-zinc-400 group-hover:text-white">
                    {formatCompact(v.views)}
                  </span>
                  <div className="w-full h-28 flex items-end justify-center bg-zinc-950/60 rounded-lg p-1 border border-zinc-800/60">
                    <div
                      className={`w-full rounded-md transition-all ${
                        aboveMedian
                          ? "bg-gradient-to-t from-emerald-600 to-teal-400"
                          : "bg-zinc-700"
                      }`}
                      style={{ height: `${hPct}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-zinc-500 truncate w-full text-center">
                    {formatDateShort(v.publishedAt)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Smart 1-Click Subscribe Link + QR */}
        <div className="lg:col-span-5 rounded-2xl border border-zinc-800 bg-zinc-900/80 p-5 flex flex-col justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold uppercase tracking-wider text-red-400 flex items-center gap-1.5">
                <Link2 className="h-3.5 w-3.5" />
                Link Đăng Ký 1-Click Chuẩn Chuyển Đổi
              </span>
              {smartClicks > 0 && (
                <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                  {smartClicks} clicks
                </span>
              )}
            </div>
            <p className="text-xs text-zinc-400">
              Tự động gắn vào mọi mô tả video để bật hộp thoại xác nhận Subscribe ngay lập tức:
            </p>
            <div className="flex items-center gap-2">
              <input
                readOnly
                value={directSubUrl}
                className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 font-mono"
              />
              <button
                type="button"
                onClick={() => copyText("sub-link", directSubUrl)}
                className="shrink-0 inline-flex items-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-500 px-3.5 py-2 text-xs font-bold text-white cursor-pointer"
              >
                {copiedKey === "sub-link" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                Copy
              </button>
            </div>
          </div>

          <div className="flex items-center gap-3.5 rounded-xl border border-zinc-800 bg-zinc-950/70 p-3">
            <img
              src={qrImageUrl}
              alt="QR Subscribe"
              className="h-16 w-16 rounded-lg bg-white p-1 shrink-0"
            />
            <div className="text-xs text-zinc-400 leading-relaxed">
              <strong className="text-zinc-200 block">
                Mã QR Kéo Sub Trực Tiếp
              </strong>
              Quét thử trên điện thoại hoặc chèn vào bài đăng cộng đồng để dẫn thẳng về trang Subscribe kênh {cleanHandle}.
            </div>
          </div>
        </div>
      </div>

      {/* MODAL: BEFORE -> AFTER AI SEO DIFF FOR PUBLISHED YOUTUBE VIDEO */}
      {targetVideo && liveProposal && (
        <div
          className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={() => {
            if (!applyingStudio) {
              setTargetVideo(null);
              setLiveProposal(null);
            }
          }}
        >
          <div
            className="w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border-2 border-emerald-500/50 bg-zinc-950 p-5 space-y-4 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3 border-b border-zinc-800 pb-3">
              <div className="space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/20 border border-emerald-500/40 px-2.5 py-1 text-xs font-extrabold text-emerald-300">
                    <Sparkles className="h-3.5 w-3.5" />
                    Nâng Cấp SEO Video Đã Đăng ({liveProposal.modelUsed})
                  </span>
                  <span className="inline-flex items-center gap-1.5 rounded-lg bg-zinc-900 border border-zinc-700 px-2.5 py-1 text-xs font-extrabold">
                    <span className="text-zinc-400">
                      {liveProposal.beforeScore}đ ({liveProposal.beforeGrade})
                    </span>
                    <ArrowRight className="h-3.5 w-3.5 text-emerald-400" />
                    <span className="text-emerald-300">
                      {liveProposal.afterScore}đ ({liveProposal.afterGrade})
                    </span>
                  </span>
                  {liveProposal.protectedCreditsKept && (
                    <span className="inline-flex items-center gap-1 rounded-lg bg-sky-500/15 border border-sky-500/35 px-2.5 py-1 text-[11px] font-bold text-sky-300">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      Giữ nguyên 100% DOI & CC-BY
                    </span>
                  )}
                </div>
                <p className="text-xs text-zinc-300 pt-1">
                  💡 {liveProposal.reasoningVi}
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setTargetVideo(null);
                  setLiveProposal(null);
                }}
                className="rounded-lg bg-zinc-900 p-1.5 text-zinc-400 hover:text-white cursor-pointer"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            {/* Title comparison */}
            <div className="space-y-2 text-xs">
              <div className="font-bold text-white">1. Tiêu đề Trước → Sau:</div>
              <div className="rounded-xl border border-rose-500/25 bg-rose-950/15 px-3 py-2 text-zinc-400 line-through">
                {targetVideo.title}
              </div>
              <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/20 px-3 py-2 text-white font-bold">
                {selectedAltTitle}
              </div>
              {liveProposal.alternativeTitles.length > 1 && (
                <div className="grid grid-cols-1 gap-1.5 pt-1">
                  {liveProposal.alternativeTitles.map((alt, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => setSelectedAltTitle(alt)}
                      className={`text-left rounded-lg border px-3 py-1.5 text-xs cursor-pointer ${
                        selectedAltTitle === alt
                          ? "border-emerald-500 bg-emerald-500/15 text-white font-bold"
                          : "border-zinc-800 bg-zinc-900 text-zinc-300"
                      }`}
                    >
                      PA #{i + 1}: {alt}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Description editorial diff */}
            <div className="space-y-2 text-xs">
              <div className="font-bold text-white">
                2. Mở đầu Mô tả & Link Kéo Sub:
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                <div className="rounded-xl border border-rose-500/20 bg-rose-950/10 p-3 text-[11px] text-zinc-400 whitespace-pre-line max-h-40 overflow-y-auto">
                  {
                    splitDescriptionEditorialAndCredits(targetVideo.description)
                      .editorialPart
                  }
                </div>
                <div className="rounded-xl border border-emerald-500/35 bg-emerald-950/15 p-3 text-[11px] text-zinc-100 whitespace-pre-line max-h-40 overflow-y-auto">
                  {liveProposal.proposed.editorialDescription}
                </div>
              </div>
            </div>

            {/* Tags & Pinned comment */}
            <div className="space-y-2 text-xs">
              <div className="font-bold text-white">
                3. Bộ Thẻ Tags Mới ({liveProposal.proposed.tags.length} thẻ):
              </div>
              <div className="flex flex-wrap gap-1.5">
                {liveProposal.proposed.tags.map((t) => (
                  <span
                    key={t}
                    className="rounded-md bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 text-[11px] text-emerald-200"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2 border-t border-zinc-800">
              {!youtubeOAuth?.refreshToken ? (
                <a
                  href="/api/youtube/oauth/start"
                  className="rounded-xl bg-amber-500 px-4 py-2.5 text-xs font-extrabold text-zinc-950"
                >
                  Cấp Quyền YouTube Studio Để Áp Dụng Trực Tiếp
                </a>
              ) : (
                <button
                  type="button"
                  disabled={applyingStudio}
                  onClick={() => void handleConfirmApplyToYoutubeStudio()}
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-5 py-2.5 text-xs font-extrabold text-white shadow-lg cursor-pointer"
                >
                  {applyingStudio ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      Đang cập nhật lên YouTube Studio...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="h-4 w-4" />
                      Accept & Đẩy Thẳng Lên YouTube Studio
                    </>
                  )}
                </button>
              )}

              <button
                type="button"
                disabled={applyingStudio}
                onClick={() => {
                  setTargetVideo(null);
                  setLiveProposal(null);
                }}
                className="rounded-xl border border-zinc-700 bg-zinc-900 px-4 py-2.5 text-xs font-semibold text-zinc-300 cursor-pointer"
              >
                Hủy
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
