"use client";

import {
  BarChart3,
  Check,
  CheckCircle2,
  ClipboardList,
  Clock,
  Copy,
  ExternalLink,
  FastForward,
  History,
  KeyRound,
  ListChecks,
  RefreshCw,
  Rocket,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  Upload,
  Wand2,
  Wrench,
  Zap,
} from "lucide-react";
import { useState } from "react";
import {
  analyzeChannelTimingVn,
  buildDefaultDescription,
  buildDefaultTags,
} from "@/lib/auto-planner";
import { formatNumber } from "@/lib/format";
import type {
  AutopilotLogEntry,
  GrowthSprintPlan,
  TrackedChannel,
  VideoItem,
  YoutubeOAuthState,
} from "@/lib/types";
import { diagnoseExistingVideosForSubRescue } from "@/lib/viral-script";
import { OverviewTab } from "./OverviewTab";

interface DailyCockpitTabProps {
  channel?: TrackedChannel;
  plan?: GrowthSprintPlan | null;
  autoSyncOnOpen: boolean;
  lastAutopilotSyncAt?: string;
  autopilotRunning: boolean;
  resolvedVideoIds: string[];
  autopilotLogs: AutopilotLogEntry[];
  smartClicks: number;
  hasOAuthClient: boolean;
  youtubeOAuth?: YoutubeOAuthState | null;
  onRunAutopilotForce: () => Promise<void>;
  onToggleAutoSync: (enabled: boolean) => Promise<void>;
  onGeneratePlan: (incrementSprint?: boolean) => Promise<void>;
  onUpdateStepStatus: (
    itemId: string,
    status: "pending" | "in_progress" | "completed"
  ) => Promise<void>;
  onSkipPlanItem: (itemId: string) => Promise<void>;
  onToggleAutoContinue: (enabled: boolean) => Promise<void>;
  onToggleResolvedVideo: (videoId: string) => Promise<void>;
  onRescueSingleStudio: (videoId: string) => Promise<void>;
  onRescueAllStudio: () => Promise<void>;
  onUploadShortDirect: (params: {
    file: File;
    publishMode: "schedule_golden" | "public_now" | "private_draft";
    episodeId: string;
    title: string;
    description: string;
    tags: string[];
    pinnedComment: string;
  }) => Promise<void>;
  onSendToScriptBuilder: (topic: string, sourceTitle?: string) => void;
  onUpdateMilestone: (channelId: string, milestone: number) => Promise<void>;
  onAuditVideoInSeo: (video: VideoItem) => void;
  onGoToSettings: () => void;
}

export function DailyCockpitTab({
  channel,
  plan,
  autoSyncOnOpen,
  lastAutopilotSyncAt,
  autopilotRunning,
  resolvedVideoIds,
  autopilotLogs,
  smartClicks,
  hasOAuthClient,
  youtubeOAuth,
  onRunAutopilotForce,
  onToggleAutoSync,
  onGeneratePlan,
  onUpdateStepStatus,
  onSkipPlanItem,
  onToggleAutoContinue,
  onToggleResolvedVideo,
  onRescueSingleStudio,
  onRescueAllStudio,
  onUploadShortDirect,
  onSendToScriptBuilder,
  onUpdateMilestone,
  onAuditVideoInSeo,
  onGoToSettings,
}: DailyCockpitTabProps) {
  const [viewMode, setViewMode] = useState<"cockpit" | "analytics">("cockpit");
  const [controlPanelTab, setControlPanelTab] = useState<
    "queue" | "rescue" | "logs"
  >("queue");
  const [showResolvedVideos, setShowResolvedVideos] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [regeneratingSprint, setRegeneratingSprint] = useState(false);
  const [completingToday, setCompletingToday] = useState(false);

  // Direct Studio states
  const [selectedVideoFile, setSelectedVideoFile] = useState<File | null>(null);
  const [publishMode, setPublishMode] = useState<
    "schedule_golden" | "public_now" | "private_draft"
  >("schedule_golden");
  const [uploadingVideo, setUploadingVideo] = useState(false);
  const [updatingVideoId, setUpdatingVideoId] = useState<string | null>(null);
  const [updatingAllVideos, setUpdatingAllVideos] = useState(false);

  const isStudioConnected = Boolean(youtubeOAuth?.refreshToken);

  const copyText = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => {
      setCopiedId((prev) => (prev === id ? null : prev));
    }, 2200);
  };

  if (!channel) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-10 text-center space-y-4">
        <p className="text-base font-bold text-white">
          Chưa có kênh YouTube nào được kết nối
        </p>
        <p className="text-xs text-zinc-400">
          Hãy vào mục Kênh & API để gắn kênh YouTube của bạn, sau đó toàn bộ quy trình hằng ngày sẽ tự động vận hành.
        </p>
        <button
          onClick={onGoToSettings}
          className="rounded-xl bg-red-600 hover:bg-red-500 px-5 py-2.5 text-xs font-bold text-white cursor-pointer"
        >
          Mở Cài Đặt Kênh & API
        </button>
      </div>
    );
  }

  const handle = channel.handle.startsWith("@")
    ? channel.handle
    : `@${channel.handle}`;

  const timing = analyzeChannelTimingVn(channel.recentVideos || []);
  const allDiagnostics = diagnoseExistingVideosForSubRescue(
    channel.recentVideos || [],
    handle
  ).filter((d) => d.issues.length > 0);

  const resolvedSet = new Set(resolvedVideoIds || []);
  const unresolvedDiagnostics = allDiagnostics.filter(
    (d) => !resolvedSet.has(d.videoId)
  );
  const visibleDiagnostics = showResolvedVideos
    ? allDiagnostics
    : unresolvedDiagnostics;

  const completedCount =
    plan?.items.filter((i) => i.status === "completed").length || 0;
  const totalCount = plan?.items.length || 0;
  const todayItem = plan?.items.find((i) => i.status !== "completed");

  const milestone = channel.targetMilestone || 100;
  const subProgressPct = Math.min(
    100,
    Math.round((channel.subscribers / Math.max(1, milestone)) * 100)
  );

  const formattedLastSync = lastAutopilotSyncAt
    ? new Date(lastAutopilotSyncAt).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Chưa quét";

  const handleRegenerateSprint = async () => {
    setRegeneratingSprint(true);
    try {
      await onGeneratePlan(false);
    } finally {
      setRegeneratingSprint(false);
    }
  };

  const handleCompleteToday = async () => {
    if (!todayItem) return;
    setCompletingToday(true);
    try {
      await onUpdateStepStatus(todayItem.id, "completed");
    } finally {
      setCompletingToday(false);
    }
  };

  const cleanHookForTts = todayItem
    ? todayItem.hook3s.replace(/^\.\.\.\s*/, "").trim()
    : "";
  const fullVoiceoverForTts = todayItem
    ? `${cleanHookForTts} ${todayItem.voiceoverScript}`.trim()
    : "";
  const wordCount = fullVoiceoverForTts
    ? fullVoiceoverForTts.split(/\s+/).filter(Boolean).length
    : 0;
  const estimatedSeconds = Math.max(35, Math.round(wordCount / 2.65));

  const readyDescription = todayItem
    ? todayItem.description ||
      buildDefaultDescription(todayItem.title, todayItem.hook3s, handle)
    : "";
  const readyTags = todayItem
    ? todayItem.tags && todayItem.tags.length > 0
      ? todayItem.tags
      : buildDefaultTags(todayItem.title)
    : [];

  const handleDirectUploadSubmit = async () => {
    if (!selectedVideoFile || !todayItem) return;
    setUploadingVideo(true);
    try {
      await onUploadShortDirect({
        file: selectedVideoFile,
        publishMode,
        episodeId: todayItem.id,
        title: todayItem.title,
        description: readyDescription,
        tags: readyTags,
        pinnedComment: todayItem.pinnedComment,
      });
      setSelectedVideoFile(null);
    } finally {
      setUploadingVideo(false);
    }
  };

  const handleSingleStudioFix = async (videoId: string) => {
    setUpdatingVideoId(videoId);
    try {
      await onRescueSingleStudio(videoId);
    } finally {
      setUpdatingVideoId(null);
    }
  };

  const handleBatchStudioFix = async () => {
    setUpdatingAllVideos(true);
    try {
      await onRescueAllStudio();
    } finally {
      setUpdatingAllVideos(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* OAUTH ONE-CLICK AUTHORIZE BANNER (IF CLIENT ID READY BUT NOT YET LOGGED IN) */}
      {hasOAuthClient && !isStudioConnected && (
        <div className="rounded-2xl border border-amber-500/50 bg-gradient-to-r from-amber-950/40 via-zinc-900 to-red-950/30 p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-amber-300">
              <KeyRound className="h-4 w-4" />
              Bước Kích Hoạt Duy Nhất (Chỉ 10 Giây)
            </div>
            <p className="text-sm font-bold text-white">
              Đã nạp sẵn Client ID & Client Secret của bạn! Hãy bấm nút bên phải để cấp quyền ghi trực tiếp vào kênh {handle}.
            </p>
            <p className="text-xs text-zinc-300">
              Lưu ý khi Google hỏi chọn tài khoản: Hãy chọn Gmail rồi bấm vào đúng <strong>kênh thương hiệu Proof of Wonder ({handle})</strong> và tích chọn các ô cấp quyền.
            </p>
          </div>
          <a
            href="/api/youtube/oauth/start"
            className="shrink-0 inline-flex items-center justify-center gap-2 rounded-xl bg-amber-500 hover:bg-amber-400 px-5 py-3 text-xs font-extrabold text-zinc-950 shadow-lg shadow-amber-500/20 transition"
          >
            <Rocket className="h-4 w-4" />
            Cấp Quyền YouTube Studio (1-Click)
          </a>
        </div>
      )}

      {/* 1. TOP CHANNEL & AUTOPILOT COMMAND BAR */}
      <div className="rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-zinc-950 p-5 shadow-lg">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Channel Identity & Live Goal */}
          <div className="flex items-center gap-3.5 min-w-0">
            <img
              src={
                channel.thumbnailUrl ||
                `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                  channel.title
                )}`
              }
              alt={channel.title}
              referrerPolicy="no-referrer"
              onError={(e) => {
                e.currentTarget.src = `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                  channel.title
                )}`;
              }}
              className="h-12 w-12 rounded-2xl object-cover border border-zinc-700 bg-zinc-800 shrink-0"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base sm:text-lg font-extrabold text-white truncate">
                  {channel.title}
                </h2>
                <span className="text-xs text-zinc-400 font-mono">{handle}</span>
                {isStudioConnected ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/35 px-2.5 py-0.5 text-[11px] font-bold text-emerald-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    Đã nối thẳng YouTube Studio (
                    {youtubeOAuth?.connectedChannelHandle ||
                      youtubeOAuth?.connectedChannelTitle ||
                      "API Ghi BẬT"}
                    )
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 rounded-full bg-zinc-800 border border-zinc-700 px-2.5 py-0.5 text-[11px] font-semibold text-zinc-300">
                    Chế độ Đọc API
                  </span>
                )}
              </div>

              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-zinc-300">
                <span>
                  Subscribers:{" "}
                  <strong className="text-white text-sm">
                    {formatNumber(channel.subscribers)}
                  </strong>{" "}
                  <span className="text-zinc-500">
                    / mục tiêu {formatNumber(milestone)} ({subProgressPct}%)
                  </span>
                </span>
                <span className="text-zinc-600">•</span>
                <span>
                  Tổng xem:{" "}
                  <strong className="text-zinc-100">
                    {formatNumber(channel.totalViews)}
                  </strong>{" "}
                  ({channel.videoCount} videos)
                </span>
                <span className="text-zinc-600">•</span>
                <span className="text-amber-300 font-semibold">
                  ⏰ Khung đăng vàng: 17:00 – 18:15 Giờ VN
                </span>
              </div>
            </div>
          </div>

          {/* Autopilot Controls */}
          <div className="flex flex-wrap items-center gap-2.5 shrink-0">
            <button
              onClick={() => onToggleAutoSync(!autoSyncOnOpen)}
              title="Tự động đồng bộ YouTube & lập kế hoạch mới mỗi khi mở Dashboard"
              className="inline-flex items-center gap-2 rounded-xl border border-zinc-800 bg-zinc-950/90 px-3 py-2 text-xs font-medium text-zinc-300 hover:border-zinc-700 cursor-pointer"
            >
              {autoSyncOnOpen ? (
                <ToggleRight className="h-4 w-4 text-emerald-400" />
              ) : (
                <ToggleLeft className="h-4 w-4 text-zinc-500" />
              )}
              <span>Tự động khi mở:</span>
              <strong
                className={
                  autoSyncOnOpen ? "text-emerald-400" : "text-zinc-500"
                }
              >
                {autoSyncOnOpen ? "BẬT" : "TẮT"}
              </strong>
            </button>

            <button
              onClick={onRunAutopilotForce}
              disabled={autopilotRunning}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-emerald-600/20 transition cursor-pointer"
            >
              <Zap
                className={`h-3.5 w-3.5 ${
                  autopilotRunning ? "animate-bounce" : ""
                }`}
              />
              {autopilotRunning
                ? "Đang đồng bộ & lập lịch..."
                : `Chạy Autopilot Ngay (Quét ${formattedLastSync})`}
            </button>
          </div>
        </div>

        {/* Sub-view Switcher: Daily 1-2-3 vs Full Analytics */}
        <div className="mt-4 pt-4 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-xl bg-zinc-950 p-1 border border-zinc-800">
            <button
              onClick={() => setViewMode("cockpit")}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition cursor-pointer ${
                viewMode === "cockpit"
                  ? "bg-red-600 text-white shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <ClipboardList className="h-3.5 w-3.5" />
              Bàn Làm Việc Hôm Nay (Quy trình 2 Bước)
            </button>
            <button
              onClick={() => setViewMode("analytics")}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition cursor-pointer ${
                viewMode === "analytics"
                  ? "bg-red-600 text-white shadow"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <BarChart3 className="h-3.5 w-3.5" />
              Biểu Đồ Kênh & Link Tăng Sub ({smartClicks} clicks)
            </button>
          </div>

          <p className="text-[11px] text-zinc-400">💡 {timing.insight}</p>
        </div>
      </div>

      {/* MODE B: DETAILED CHANNEL ANALYTICS & SMART LINK */}
      {viewMode === "analytics" ? (
        <OverviewTab
          channel={channel}
          smartClicks={smartClicks}
          onUpdateMilestone={onUpdateMilestone}
          onAuditVideoInSeo={onAuditVideoInSeo}
          onGoToAddChannel={onGoToSettings}
        />
      ) : (
        /* MODE A: ULTRA-SIMPLE DAILY COCKPIT */
        <>
          {!plan || !todayItem ? (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/15 p-8 text-center space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-500/20 text-emerald-300">
                <Sparkles className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-extrabold text-white">
                {plan
                  ? `🎉 Bạn đã hoàn thành trọn bộ ${totalCount}/${totalCount} bài trong Sprint #${plan.sprintNumber}!`
                  : "Sẵn sàng khởi tạo Lộ trình 5 Ngày đầu tiên"}
              </h3>
              <p className="text-xs text-zinc-300 max-w-xl mx-auto">
                Bấm nút bên dưới để AI tự động phân tích các video thắng lớn nhất trên kênh & đối thủ, lập ngay 5 kịch bản Shorts tiếp theo.
              </p>
              <button
                onClick={() => onGeneratePlan(Boolean(plan))}
                disabled={regeneratingSprint}
                className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-5 py-2.5 text-sm font-bold text-white cursor-pointer"
              >
                <RefreshCw
                  className={`h-4 w-4 ${
                    regeneratingSprint ? "animate-spin" : ""
                  }`}
                />
                {regeneratingSprint
                  ? "AI đang lập Sprint mới..."
                  : "Tự Động Lập Kế Hoạch 5 Ngày Tiếp Theo"}
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
              {/* STEP 1: SCRIPT FOR VIDEO CREATION */}
              <div className="xl:col-span-6 rounded-2xl border border-red-500/35 bg-zinc-900/80 p-6 flex flex-col justify-between space-y-5">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-extrabold text-white">
                        BƯỚC 1: TẠO VIDEO
                      </span>
                      <span className="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-[11px] font-semibold text-zinc-300">
                        Sprint #{plan.sprintNumber} • Tiến độ {completedCount}/
                        {totalCount}
                      </span>
                    </div>

                    <button
                      onClick={() => onSkipPlanItem(todayItem.id)}
                      title="Đẩy bài này xuống cuối hàng đợi và lấy bài kế tiếp lên làm hôm nay"
                      className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-2.5 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                    >
                      <FastForward className="h-3 w-3 text-amber-400" />
                      Đổi bài khác lên trước
                    </button>
                  </div>

                  <div>
                    <div className="text-[11px] font-semibold text-amber-300 mb-1">
                      🎯 Chủ đề hôm nay ({todayItem.dayLabel}) —{" "}
                      {todayItem.expectedGoal}
                    </div>
                    <h3 className="text-lg font-extrabold text-white leading-snug">
                      {todayItem.title}
                    </h3>
                    <p className="text-xs text-zinc-400 mt-1">
                      {todayItem.whySelected}
                    </p>
                  </div>

                  {/* Voiceover Script Box */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-4 space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                        🎙️ Lời Đọc Voiceover Chuẩn Vòng Lặp ({wordCount} từ • ~
                        {estimatedSeconds}s)
                      </span>
                      <span className="text-[11px] text-zinc-500">
                        Giọng US English
                      </span>
                    </div>

                    <div className="rounded-lg border border-amber-500/20 bg-amber-950/15 p-2.5">
                      <span className="block text-[10px] font-bold uppercase text-amber-300 mb-0.5">
                        00:00 – 00:03 (Câu Hook giữ chân đầu video):
                      </span>
                      <p className="text-xs font-semibold text-zinc-100 leading-relaxed">
                        &ldquo;{todayItem.hook3s}&rdquo;
                      </p>
                    </div>

                    <div>
                      <span className="block text-[10px] font-bold uppercase text-zinc-400 mb-1">
                        00:03 – 00:45 (Nội dung chính + Câu kết nối Loop):
                      </span>
                      <p className="text-xs text-zinc-200 leading-relaxed">
                        {todayItem.voiceoverScript}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Step 1 Mac Pipeline Bridge & Zero-Cost Actions */}
                <div className="space-y-3 pt-3 border-t border-zinc-800/80">
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5 space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs font-bold text-emerald-300">
                        🍎 Dựng Video trên Mac (0₫ • Giữ 100% chất lượng gốc)
                      </span>
                      <span className="font-mono text-[10px] text-zinc-500">
                        GET /api/pipeline
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 leading-relaxed">
                      Đã tắt hoàn toàn tạo video bằng Vertex trả phí. Kịch bản tạo video trên máy Mac của bạn có thể lấy tự động đề tài hôm nay qua <code className="text-zinc-200">GET /api/pipeline</code> rồi đẩy file <code className="text-zinc-200">.mp4</code> sang Bước 2 để hẹn lịch 17:15 VN (miễn phí 0₫).
                    </p>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <button
                      onClick={() => copyText("step1-vo", fullVoiceoverForTts)}
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-3 py-2 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                    >
                      {copiedId === "step1-vo" ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                      {copiedId === "step1-vo"
                        ? "Đã chép Lời đọc!"
                        : "Chép Lời Đọc Voiceover"}
                    </button>

                    <button
                      onClick={() =>
                        onSendToScriptBuilder(todayItem.title, todayItem.title)
                      }
                      className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-3 py-2 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                    >
                      <Wand2 className="h-3.5 w-3.5 text-amber-400" />
                      Mở Chia Cảnh Chi Tiết (0₫)
                    </button>
                  </div>
                </div>
              </div>

              {/* STEP 2: DIRECT API UPLOAD / UPDATE TO YOUTUBE STUDIO */}
              <div className="xl:col-span-6 rounded-2xl border border-emerald-500/35 bg-zinc-900/80 p-6 flex flex-col justify-between space-y-5">
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-extrabold text-white">
                      BƯỚC 2: ĐẨY THẲNG LÊN YOUTUBE STUDIO
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 text-[11px] font-bold text-amber-300">
                      <Clock className="h-3.5 w-3.5" />
                      Giờ vàng: {todayItem.vnPublishWindow}
                    </span>
                  </div>

                  {/* DIRECT API UPLOAD WIDGET (NO NEED TO OPEN YOUTUBE STUDIO!) */}
                  {isStudioConnected ? (
                    <div className="rounded-xl border border-emerald-500/35 bg-emerald-950/20 p-4 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-extrabold text-emerald-300 flex items-center gap-1.5">
                          <Upload className="h-4 w-4" />
                          Upload & Tự Điền Toàn Bộ Metadata (1-Click API)
                        </span>
                        <span className="text-[10px] text-emerald-400/80 font-semibold">
                          Không cần mở Studio
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5">
                        <label className="sm:col-span-7 flex items-center justify-between rounded-xl border border-dashed border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 hover:border-emerald-500 cursor-pointer truncate">
                          <span className="truncate">
                            {selectedVideoFile
                              ? `🎬 ${selectedVideoFile.name}`
                              : "Chọn file video (.mp4 / .mov)..."}
                          </span>
                          <input
                            type="file"
                            accept="video/mp4,video/quicktime,video/*"
                            onChange={(e) =>
                              setSelectedVideoFile(e.target.files?.[0] || null)
                            }
                            className="hidden"
                          />
                        </label>

                        <select
                          value={publishMode}
                          onChange={(e) =>
                            setPublishMode(
                              e.target.value as
                                | "schedule_golden"
                                | "public_now"
                                | "private_draft"
                            )
                          }
                          className="sm:col-span-5 rounded-xl border border-zinc-700 bg-zinc-950 px-2.5 py-2 text-xs font-semibold text-zinc-200 focus:outline-none"
                        >
                          <option value="schedule_golden">
                            ⏰ Hẹn 17:15 VN tiếp theo
                          </option>
                          <option value="public_now">
                            🌐 Đăng Công khai ngay
                          </option>
                          <option value="private_draft">
                            🔒 Lưu Nháp riêng tư
                          </option>
                        </select>
                      </div>

                      <button
                        onClick={handleDirectUploadSubmit}
                        disabled={!selectedVideoFile || uploadingVideo}
                        className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-45 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/20 transition cursor-pointer"
                      >
                        <Rocket
                          className={`h-4 w-4 ${
                            uploadingVideo ? "animate-bounce" : ""
                          }`}
                        />
                        {uploadingVideo
                          ? "Đang truyền file & cài đặt SEO lên YouTube..."
                          : "Upload Thẳng Lên YouTube + Tự Chuyển Bài Ngày Mai"}
                      </button>
                    </div>
                  ) : (
                    <div className="rounded-xl border border-amber-500/30 bg-amber-950/15 p-3.5 flex items-center justify-between gap-3 text-xs">
                      <span className="text-amber-200">
                        Cấp quyền YouTube Studio để Upload & tự điền Tiêu đề/Mô tả/Tags không cần copy-paste!
                      </span>
                      <a
                        href="/api/youtube/oauth/start"
                        className="shrink-0 rounded-lg bg-amber-500 hover:bg-amber-400 px-3 py-1.5 font-extrabold text-zinc-950"
                      >
                        Cấp quyền ngay
                      </a>
                    </div>
                  )}

                  {/* 4 Metadata Preview & Manual Backup Copy Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-2.5 flex flex-col justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold uppercase text-zinc-400">
                          1. Tiêu đề chuẩn (Không #hashtag)
                        </span>
                        <p className="text-xs font-bold text-white mt-0.5 line-clamp-2">
                          {todayItem.title}
                        </p>
                      </div>
                      <button
                        onClick={() => copyText("meta-title", todayItem.title)}
                        className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                      >
                        {copiedId === "meta-title" ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                        {copiedId === "meta-title"
                          ? "Đã chép"
                          : "Chép Tiêu đề"}
                      </button>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-2.5 flex flex-col justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold uppercase text-emerald-400">
                          2. Mô tả (Kèm ?sub_confirmation=1)
                        </span>
                        <p className="text-[11px] text-zinc-300 mt-0.5 line-clamp-2 whitespace-pre-line">
                          {readyDescription}
                        </p>
                      </div>
                      <button
                        onClick={() => copyText("meta-desc", readyDescription)}
                        className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                      >
                        {copiedId === "meta-desc" ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                        {copiedId === "meta-desc" ? "Đã chép" : "Chép Mô tả"}
                      </button>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-2.5 flex flex-col justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold uppercase text-sky-400">
                          3. Bộ Tags ({readyTags.length} từ khóa)
                        </span>
                        <p className="text-[11px] text-zinc-400 mt-0.5 line-clamp-1">
                          {readyTags.join(", ")}
                        </p>
                      </div>
                      <button
                        onClick={() =>
                          copyText("meta-tags", readyTags.join(", "))
                        }
                        className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                      >
                        {copiedId === "meta-tags" ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                        {copiedId === "meta-tags" ? "Đã chép" : "Chép Tags"}
                      </button>
                    </div>

                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-2.5 flex flex-col justify-between gap-2">
                      <div>
                        <span className="text-[10px] font-bold uppercase text-amber-300">
                          4. Bình luận Ghim
                        </span>
                        <p className="text-[11px] text-zinc-300 mt-0.5 line-clamp-1">
                          {todayItem.pinnedComment}
                        </p>
                      </div>
                      <button
                        onClick={() =>
                          copyText("meta-pin", todayItem.pinnedComment)
                        }
                        className="w-full inline-flex items-center justify-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 py-1 text-[11px] font-semibold text-zinc-300 cursor-pointer"
                      >
                        {copiedId === "meta-pin" ? (
                          <Check className="h-3 w-3 text-emerald-400" />
                        ) : (
                          <Copy className="h-3 w-3" />
                        )}
                        {copiedId === "meta-pin"
                          ? "Đã chép"
                          : "Chép Bình luận"}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Step 2 Manual Finish Controls */}
                <div className="flex flex-col sm:flex-row gap-2.5 pt-2 border-t border-zinc-800/80">
                  <a
                    href="https://studio.youtube.com"
                    target="_blank"
                    rel="noreferrer"
                    className="sm:w-44 inline-flex items-center justify-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3.5 py-2 text-xs font-bold text-zinc-300 transition"
                  >
                    Mở YouTube Studio
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>

                  <button
                    onClick={handleCompleteToday}
                    disabled={completingToday}
                    className="flex-1 inline-flex items-center justify-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-950/30 hover:bg-emerald-900/40 disabled:opacity-60 px-4 py-2 text-xs font-bold text-emerald-300 transition cursor-pointer"
                  >
                    <CheckCircle2 className="h-4 w-4" />
                    {completingToday
                      ? "Đang chuyển bài..."
                      : "Đã tự đăng thủ công → Chuyển Bài Tiếp Theo"}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* 3. OPERATOR CONTROL CENTER (QUEUE • OLD VIDEO DIRECT STUDIO FIX • LOGS) */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5 space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800 pb-3.5">
              <div className="flex flex-wrap items-center gap-2">
                <button
                  onClick={() => setControlPanelTab("queue")}
                  className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                    controlPanelTab === "queue"
                      ? "bg-zinc-800 text-white border border-zinc-700"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <ListChecks className="h-4 w-4 text-emerald-400" />
                  Hàng Đợi 5 Ngày ({completedCount}/{totalCount})
                </button>

                <button
                  onClick={() => setControlPanelTab("rescue")}
                  className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                    controlPanelTab === "rescue"
                      ? "bg-zinc-800 text-white border border-zinc-700"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <Wrench className="h-4 w-4 text-amber-400" />
                  Tối Ưu Video Cũ ({unresolvedDiagnostics.length} cần sửa)
                </button>

                <button
                  onClick={() => setControlPanelTab("logs")}
                  className={`inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                    controlPanelTab === "logs"
                      ? "bg-zinc-800 text-white border border-zinc-700"
                      : "text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <History className="h-4 w-4 text-sky-400" />
                  Nhật Ký Tự Động ({autopilotLogs.length})
                </button>
              </div>

              {controlPanelTab === "queue" && plan && (
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() =>
                      onToggleAutoContinue(!plan.autoContinueEnabled)
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-[11px] font-medium text-zinc-300 cursor-pointer"
                  >
                    {plan.autoContinueEnabled ? (
                      <ToggleRight className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <ToggleLeft className="h-4 w-4 text-zinc-500" />
                    )}
                    Xong 5/5 tự lập Sprint mới:{" "}
                    <strong className="text-emerald-400">
                      {plan.autoContinueEnabled ? "BẬT" : "TẮT"}
                    </strong>
                  </button>

                  <button
                    onClick={handleRegenerateSprint}
                    disabled={regeneratingSprint}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3 py-1.5 text-[11px] font-semibold text-zinc-200 cursor-pointer"
                  >
                    <RefreshCw
                      className={`h-3.5 w-3.5 ${
                        regeneratingSprint ? "animate-spin" : ""
                      }`}
                    />
                    {regeneratingSprint
                      ? "Đang tạo lại..."
                      : "AI Đổi Lộ Trình 5 Bài Khác"}
                  </button>
                </div>
              )}

              {controlPanelTab === "rescue" &&
                unresolvedDiagnostics.length > 0 &&
                isStudioConnected && (
                  <button
                    onClick={handleBatchStudioFix}
                    disabled={updatingAllVideos}
                    className="inline-flex items-center gap-2 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-60 px-4 py-2 text-xs font-extrabold text-zinc-950 shadow-lg shadow-amber-500/20 cursor-pointer"
                  >
                    <Rocket
                      className={`h-4 w-4 ${
                        updatingAllVideos ? "animate-bounce" : ""
                      }`}
                    />
                    {updatingAllVideos
                      ? "Đang tự động sửa trên YouTube Studio..."
                      : `Tự Động Sửa Tất Cả ${unresolvedDiagnostics.length} Video Cũ Trên Studio (1-Click)`}
                  </button>
                )}
            </div>

            {/* TAB 3A: 5-DAY SPRINT QUEUE */}
            {controlPanelTab === "queue" && plan && (
              <div className="space-y-2.5">
                {plan.items.map((item, index) => {
                  const isDone = item.status === "completed";
                  const isToday = todayItem?.id === item.id;
                  return (
                    <div
                      key={item.id}
                      className={`rounded-xl border p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition ${
                        isDone
                          ? "border-emerald-500/20 bg-emerald-950/10 opacity-70"
                          : isToday
                          ? "border-red-500/50 bg-red-950/15"
                          : "border-zinc-800 bg-zinc-950/60"
                      }`}
                    >
                      <div className="flex items-start gap-3 min-w-0">
                        <button
                          onClick={() =>
                            onUpdateStepStatus(
                              item.id,
                              isDone ? "pending" : "completed"
                            )
                          }
                          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-xs font-bold cursor-pointer ${
                            isDone
                              ? "border-emerald-500 bg-emerald-500 text-zinc-950"
                              : isToday
                              ? "border-red-500 text-red-400"
                              : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
                          }`}
                        >
                          {isDone ? <Check className="h-3.5 w-3.5" /> : index + 1}
                        </button>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-[11px] font-bold text-zinc-400">
                              {item.dayLabel}
                            </span>
                            {isToday && (
                              <span className="rounded bg-red-600 px-2 py-0.5 text-[10px] font-extrabold text-white">
                                ĐANG LÀM HÔM NAY
                              </span>
                            )}
                            {isDone && (
                              <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                                Đã xong ✓
                              </span>
                            )}
                            <span className="text-[11px] text-zinc-500">
                              • {item.vnPublishWindow}
                            </span>
                          </div>
                          <p
                            className={`text-sm font-bold mt-0.5 ${
                              isDone
                                ? "line-through text-zinc-400"
                                : "text-white"
                            }`}
                          >
                            {item.title}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() =>
                            onUpdateStepStatus(
                              item.id,
                              isDone ? "pending" : "completed"
                            )
                          }
                          className="rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 cursor-pointer"
                        >
                          {isDone ? "Hoàn tác" : "Đánh dấu Xong"}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* TAB 3B: ONE-TIME OLD VIDEO CLEANUP (DIRECT API OR MANUAL) */}
            {controlPanelTab === "rescue" && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/25 bg-amber-950/15 px-4 py-3 text-xs text-amber-200">
                  <span>
                    💡 <strong>Cơ chế API an toàn 100%:</strong> Khi bấm{" "}
                    <strong>&ldquo;Tự sửa thẳng lên Studio&rdquo;</strong>, hệ thống tải nguyên văn mô tả gốc từ YouTube về, <strong>giữ nguyên 100% nguồn NASA / CC BY 4.0</strong>, chỉ xóa <code>#venus</code> khỏi tiêu đề, nối thêm link <code>?sub_confirmation=1</code> xuống cuối, bật lại hiển thị nút Like và đăng Bình luận câu hỏi!
                  </span>
                  <button
                    onClick={() => setShowResolvedVideos((v) => !v)}
                    className="rounded-lg border border-amber-500/40 bg-zinc-950 px-2.5 py-1 text-[11px] font-semibold text-amber-300 cursor-pointer"
                  >
                    {showResolvedVideos
                      ? "Ẩn các video đã sửa"
                      : `Hiện cả video đã sửa (${resolvedSet.size})`}
                  </button>
                </div>

                {visibleDiagnostics.length === 0 ? (
                  <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/15 p-6 text-center text-xs text-emerald-300 font-semibold">
                    🎉 Tuyệt vời! Toàn bộ video cũ trên kênh đều đã được tối ưu sạch sẽ để đón Subscribers mới!
                  </div>
                ) : (
                  <div className="space-y-3">
                    {visibleDiagnostics.map((diag) => {
                      const isResolved = resolvedSet.has(diag.videoId);
                      const isUpdatingThis = updatingVideoId === diag.videoId;
                      return (
                        <div
                          key={diag.videoId}
                          className={`rounded-xl border p-4 space-y-3 ${
                            isResolved
                              ? "border-emerald-500/25 bg-emerald-950/10 opacity-65"
                              : "border-zinc-800 bg-zinc-950/70"
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-emerald-400">
                                  {formatNumber(diag.views)} views
                                </span>
                                <span className="text-xs text-zinc-500">•</span>
                                <span className="text-sm font-bold text-white">
                                  {diag.originalTitle}
                                </span>
                              </div>
                              <ul className="mt-1 space-y-0.5 text-xs text-amber-300/90">
                                {diag.issues.map((iss, idx) => (
                                  <li key={idx}>• {iss}</li>
                                ))}
                              </ul>
                            </div>

                            <div className="flex flex-wrap items-center gap-2 shrink-0">
                              {isStudioConnected && !isResolved && (
                                <button
                                  onClick={() =>
                                    handleSingleStudioFix(diag.videoId)
                                  }
                                  disabled={
                                    isUpdatingThis || updatingAllVideos
                                  }
                                  className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 disabled:opacity-60 px-3.5 py-2 text-xs font-extrabold text-zinc-950 cursor-pointer"
                                >
                                  <Zap className="h-3.5 w-3.5" />
                                  {isUpdatingThis
                                    ? "Đang ghi lên Studio..."
                                    : "Tự sửa thẳng lên Studio"}
                                </button>
                              )}

                              <button
                                onClick={() =>
                                  onToggleResolvedVideo(diag.videoId)
                                }
                                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-bold cursor-pointer ${
                                  isResolved
                                    ? "border border-zinc-700 bg-zinc-900 text-zinc-300"
                                    : "border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 text-zinc-200"
                                }`}
                              >
                                <Check className="h-3.5 w-3.5" />
                                {isResolved
                                  ? "Đã sửa (Mở lại)"
                                  : "Đánh dấu Đã sửa"}
                              </button>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2 pt-1">
                            {diag.originalTitle !== diag.cleanedTitle && (
                              <button
                                onClick={() =>
                                  copyText(
                                    `clean-${diag.videoId}`,
                                    diag.cleanedTitle
                                  )
                                }
                                className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-300 cursor-pointer"
                              >
                                {copiedId === `clean-${diag.videoId}` ? (
                                  <Check className="h-3.5 w-3.5 text-emerald-400" />
                                ) : (
                                  <Copy className="h-3.5 w-3.5" />
                                )}
                                Chép Tiêu đề sạch
                              </button>
                            )}

                            <button
                              onClick={() =>
                                copyText(
                                  `desc-${diag.videoId}`,
                                  diag.appendDescriptionBlock
                                )
                              }
                              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-emerald-300 cursor-pointer"
                            >
                              {copiedId === `desc-${diag.videoId}` ? (
                                <Check className="h-3.5 w-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="h-3.5 w-3.5" />
                              )}
                              Chép Khối Thêm Vào Cuối Mô Tả
                            </button>

                            <button
                              onClick={() =>
                                copyText(
                                  `pin-${diag.videoId}`,
                                  diag.suggestedPinnedComment
                                )
                              }
                              className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-amber-300 cursor-pointer"
                            >
                              {copiedId === `pin-${diag.videoId}` ? (
                                <Check className="h-3.5 w-3.5 text-emerald-400" />
                              ) : (
                                <Copy className="h-3.5 w-3.5" />
                              )}
                              Chép Comment Ghim
                            </button>

                            <a
                              href={`https://studio.youtube.com/video/${diag.videoId}/edit`}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-400"
                            >
                              Xem trong Studio
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* TAB 3C: AUTOPILOT LOGS */}
            {controlPanelTab === "logs" && (
              <div className="space-y-2">
                {autopilotLogs.length === 0 ? (
                  <p className="text-xs text-zinc-500 py-4 text-center">
                    Chưa có nhật ký hoạt động. Hãy bấm &ldquo;Chạy Autopilot Ngay&rdquo; để ghi nhận lần đồng bộ đầu tiên.
                  </p>
                ) : (
                  autopilotLogs.map((log) => (
                    <div
                      key={log.id}
                      className="flex items-start justify-between gap-3 rounded-xl border border-zinc-800/80 bg-zinc-950/60 px-3.5 py-2.5 text-xs"
                    >
                      <div className="flex items-center gap-2.5">
                        <span
                          className={`h-2 w-2 rounded-full shrink-0 ${
                            log.type === "publish"
                              ? "bg-emerald-400"
                              : log.type === "plan"
                              ? "bg-amber-400"
                              : "bg-sky-400"
                          }`}
                        />
                        <span className="text-zinc-200">{log.message}</span>
                      </div>
                      <span className="text-[11px] font-mono text-zinc-500 shrink-0">
                        {new Date(log.timestamp).toLocaleString("vi-VN", {
                          hour: "2-digit",
                          minute: "2-digit",
                          day: "2-digit",
                          month: "2-digit",
                        })}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
