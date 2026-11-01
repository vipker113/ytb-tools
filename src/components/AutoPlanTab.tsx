"use client";

import {
  CalendarCheck2,
  Check,
  CheckCircle2,
  Clock,
  Copy,
  Flame,
  PlayCircle,
  RefreshCw,
  Repeat,
  Sparkles,
  Zap,
} from "lucide-react";
import { useMemo, useState } from "react";
import { analyzeChannelTimingVn } from "@/lib/auto-planner";
import { formatNumber } from "@/lib/format";
import type { GrowthPlanItem, GrowthSprintPlan, TrackedChannel } from "@/lib/types";

interface AutoPlanTabProps {
  channel: TrackedChannel | undefined;
  plan: GrowthSprintPlan | null | undefined;
  onGeneratePlan: (incrementSprint?: boolean) => Promise<void>;
  onUpdateStepStatus: (
    itemId: string,
    status: GrowthPlanItem["status"]
  ) => Promise<void>;
  onToggleAutoContinue: (enabled: boolean) => Promise<void>;
  onSendToScriptBuilder: (topic: string, sourceTitle?: string) => void;
}

export function AutoPlanTab({
  channel,
  plan,
  onGeneratePlan,
  onUpdateStepStatus,
  onToggleAutoContinue,
  onSendToScriptBuilder,
}: AutoPlanTabProps) {
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [updatingItemId, setUpdatingItemId] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const timingStats = useMemo(() => {
    return analyzeChannelTimingVn(channel?.recentVideos || []);
  }, [channel]);

  const copyText = (id: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1800);
  };

  const handleGenerateClick = async (incrementSprint = false) => {
    setLoadingPlan(true);
    try {
      await onGeneratePlan(incrementSprint);
    } finally {
      setLoadingPlan(false);
    }
  };

  const handleStepToggle = async (item: GrowthPlanItem) => {
    const nextStatus: GrowthPlanItem["status"] =
      item.status === "completed" ? "pending" : "completed";
    setUpdatingItemId(item.id);
    try {
      await onUpdateStepStatus(item.id, nextStatus);
    } finally {
      setUpdatingItemId(null);
    }
  };

  const completedCount =
    plan?.items.filter((i) => i.status === "completed").length || 0;
  const totalCount = plan?.items.length || 0;
  const pct =
    totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

  const maxBucketAvg = Math.max(
    ...timingStats.buckets.map((b) => b.avgViews),
    100
  );

  return (
    <div className="space-y-6">
      {/* Top Autopilot Banner */}
      <div className="rounded-2xl border border-emerald-500/35 bg-gradient-to-br from-emerald-950/30 via-zinc-900 to-zinc-900 p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-5">
          <div>
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/15 border border-emerald-500/40 px-3 py-1 text-xs font-bold text-emerald-300">
                <Zap className="h-3.5 w-3.5" />
                Chế độ Tự Động Nối Tiếp (Closed-Loop Autopilot)
              </span>
              {plan && (
                <span className="rounded-full bg-zinc-800 px-3 py-1 text-xs font-semibold text-zinc-200">
                  Đang chạy: Sprint #{plan.sprintNumber}
                </span>
              )}
            </div>
            <h2 className="text-xl font-extrabold text-white">
              Kế Hoạch Hành Động Tự Động — Chạy Xong Tự Lên Lộ Trình Mới
            </h2>
            <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
              Ngay khi bạn hoàn thành các bước trong Sprint hiện tại (hoặc bấm{" "}
              <strong className="text-white">Đồng bộ YouTube</strong> sau khi đăng video mới lên kênh), AI sẽ tự động tổng kết hiệu suất, quét Outlier đối thủ mới và lập sẵn{" "}
              <strong className="text-emerald-300">Sprint kế tiếp</strong> mà không bao giờ đứt quãng ý tưởng!
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3 shrink-0">
            {plan && (
              <label className="inline-flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-950/80 px-3.5 py-2.5 text-xs font-semibold text-zinc-200 cursor-pointer">
                <input
                  type="checkbox"
                  checked={plan.autoContinueEnabled}
                  onChange={(e) => onToggleAutoContinue(e.target.checked)}
                  className="rounded accent-emerald-500 h-4 w-4"
                />
                Tự động lập Sprint mới khi xong
              </label>
            )}

            <button
              onClick={() => handleGenerateClick(Boolean(plan))}
              disabled={loadingPlan}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 px-4 py-2.5 text-xs sm:text-sm font-bold text-white shadow-lg shadow-emerald-600/20 transition cursor-pointer"
            >
              <RefreshCw
                className={`h-4 w-4 ${loadingPlan ? "animate-spin" : ""}`}
              />
              {loadingPlan
                ? "AI đang lập Sprint mới..."
                : plan
                ? "Chuyển sang Sprint Tiếp Theo"
                : "Khởi tạo Kế Hoạch Tự Động"}
            </button>
          </div>
        </div>

        {plan && (
          <div className="mt-5 rounded-xl border border-zinc-800 bg-zinc-950/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 text-xs mb-2">
              <span className="font-semibold text-zinc-200">
                Tiến độ Sprint #{plan.sprintNumber}: {completedCount}/
                {totalCount} video hoàn tất ({pct}%)
              </span>
              <span className="text-emerald-400 font-semibold">
                Mục tiêu Sprint: Cán mốc{" "}
                {formatNumber(plan.targetSubscribersGoal)} Subscribers
              </span>
            </div>
            <div className="h-2.5 w-full rounded-full bg-zinc-800 overflow-hidden mb-3">
              <div
                className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-amber-400 transition-all duration-500"
                style={{ width: `${Math.max(4, pct)}%` }}
              />
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed">
              <strong className="text-emerald-300">Chiến lược AI:</strong>{" "}
              {plan.strategicSummary}
            </p>
          </div>
        )}
      </div>

      {/* Real Publish-Hour Intelligence Card */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <div className="flex items-center gap-2 mb-1">
          <Clock className="h-4 w-4 text-amber-400" />
          <h3 className="text-base font-bold text-white">
            Khung Giờ Đăng Vàng Thực Tế Của Kênh (Quy đổi Giờ Việt Nam → Thị trường Mỹ)
          </h3>
        </div>
        <p className="text-xs text-amber-300 font-medium mb-4">
          💡 {timingStats.insight}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          {timingStats.buckets.map((b) => {
            const isBest =
              b.avgViews > 0 && b.label === timingStats.bestWindow;
            return (
              <div
                key={b.id}
                className={`rounded-xl border p-3.5 ${
                  isBest
                    ? "border-amber-500/50 bg-amber-500/10"
                    : "border-zinc-800 bg-zinc-950/60"
                }`}
              >
                <div className="flex items-center justify-between gap-1 mb-1">
                  <span className="text-xs font-bold text-zinc-100">
                    {b.label.split("(")[0].trim()}
                  </span>
                  {isBest && (
                    <span className="rounded bg-amber-500 px-1.5 py-0.5 text-[10px] font-extrabold text-zinc-950">
                      GIỜ VÀNG
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-zinc-400 mb-2">
                  ({b.label.split("(")[1] || ""}
                </div>
                <div className="flex items-baseline justify-between text-xs mb-1.5">
                  <span className="text-zinc-400">Đã đăng: {b.count} video</span>
                  <span className="font-bold text-white">
                    TB: {formatNumber(b.avgViews)} views
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      isBest ? "bg-amber-400" : "bg-zinc-500"
                    }`}
                    style={{
                      width: `${Math.max(
                        4,
                        (b.avgViews / maxBucketAvg) * 100
                      )}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Sprint Steps List */}
      {!plan ? (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-12 text-center">
          <CalendarCheck2 className="mx-auto h-12 w-12 text-emerald-400 mb-3" />
          <h3 className="text-lg font-bold text-white mb-2">
            Sẵn sàng lập Kế hoạch Sprint #1 tự động
          </h3>
          <p className="text-sm text-zinc-400 max-w-lg mx-auto mb-5">
            AI sẽ kết hợp các video thắng lớn trên kênh của bạn cùng dữ liệu Outlier từ 5 kênh Science lớn nhất để lên lịch đăng từng ngày kèm kịch bản 45s.
          </p>
          <button
            onClick={() => handleGenerateClick(false)}
            disabled={loadingPlan}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-6 py-3 text-sm font-bold text-white cursor-pointer"
          >
            <Sparkles className="h-4 w-4" />
            {loadingPlan
              ? "Đang phân tích & lập kế hoạch..."
              : "Tạo Kế hoạch 5 Ngày Đầu Tiên"}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {plan.items.map((item, idx) => {
            const isDone = item.status === "completed";
            const isUpdating = updatingItemId === item.id;
            return (
              <div
                key={item.id}
                className={`rounded-2xl border p-5 transition ${
                  isDone
                    ? "border-emerald-500/30 bg-emerald-950/10 opacity-75"
                    : idx === completedCount
                    ? "border-red-500/50 bg-zinc-900/90 shadow-lg shadow-red-950/20"
                    : "border-zinc-800 bg-zinc-900/70"
                }`}
              >
                <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                  <div className="space-y-2.5 flex-1">
                    {/* Badges Row */}
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-lg bg-zinc-800 px-2.5 py-1 text-xs font-bold text-white">
                        {item.dayLabel} ({item.scheduledDate})
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-lg bg-amber-500/15 border border-amber-500/30 px-2.5 py-1 text-xs font-semibold text-amber-300">
                        <Clock className="h-3 w-3" />
                        {item.vnPublishWindow}
                      </span>
                      {item.strategyType === "sequel_winner" ? (
                        <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs font-semibold text-emerald-300">
                          <Repeat className="h-3 w-3" />
                          Phần 2 ăn theo Video Thắng Lớn
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-lg bg-rose-500/15 border border-rose-500/30 px-2.5 py-1 text-xs font-semibold text-rose-300">
                          <Flame className="h-3 w-3" />
                          Nhân bản Outlier Đối Thủ
                        </span>
                      )}
                      {idx === completedCount && !isDone && (
                        <span className="rounded-full bg-red-600 px-2.5 py-0.5 text-[11px] font-extrabold text-white">
                          VIỆC CẦN LÀM TIẾP THEO
                        </span>
                      )}
                    </div>

                    {/* Title */}
                    <div className="flex items-center gap-2">
                      <h4
                        className={`text-base sm:text-lg font-bold ${
                          isDone ? "line-through text-zinc-400" : "text-white"
                        }`}
                      >
                        {item.title}
                      </h4>
                      <button
                        onClick={() => copyText(`t-${item.id}`, item.title)}
                        className="text-zinc-400 hover:text-white cursor-pointer"
                        title="Chép tiêu đề"
                      >
                        {copiedId === `t-${item.id}` ? (
                          <Check className="h-4 w-4 text-emerald-400" />
                        ) : (
                          <Copy className="h-4 w-4" />
                        )}
                      </button>
                    </div>

                    <p className="text-xs text-zinc-400">
                      <strong className="text-zinc-200">Lý do chọn:</strong>{" "}
                      {item.whySelected} •{" "}
                      <strong className="text-emerald-400">
                         Kỳ vọng: {item.expectedGoal}
                      </strong>
                    </p>

                    {/* Script Box */}
                    <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5 space-y-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="text-[11px] font-bold text-red-300 uppercase">
                          ⚡ Hook 3s + Voiceover Kịch bản 45s (US English)
                        </span>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() =>
                              copyText(
                                `vo-${item.id}`,
                                `${item.hook3s} ${item.voiceoverScript}`
                              )
                            }
                            className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                          >
                            {copiedId === `vo-${item.id}` ? (
                              "Đã chép lời đọc!"
                            ) : (
                              <>
                                <Copy className="h-3 w-3" />
                                Chép Voiceover
                              </>
                            )}
                          </button>

                          <button
                            onClick={() =>
                              copyText(`pin-${item.id}`, item.pinnedComment)
                            }
                            className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                          >
                            {copiedId === `pin-${item.id}` ? (
                              "Đã chép Comment!"
                            ) : (
                              <>
                                <Copy className="h-3 w-3" />
                                Chép Pinned Comment
                              </>
                            )}
                          </button>
                        </div>
                      </div>

                      <p className="text-xs font-semibold text-amber-200">
                        [00:00 Hook]: &ldquo;{item.hook3s}&rdquo;
                      </p>
                      <p className="text-xs text-zinc-300 leading-relaxed">
                        {item.voiceoverScript}
                      </p>
                      <p className="text-[11px] text-emerald-300/90 pt-1 border-t border-zinc-800/80">
                        💬 <strong>Pinned Comment:</strong> {item.pinnedComment}
                      </p>
                    </div>
                  </div>

                  {/* Right Action Column */}
                  <div className="flex lg:flex-col items-center lg:items-end gap-2 shrink-0">
                    <button
                      onClick={() => handleStepToggle(item)}
                      disabled={isUpdating}
                      className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-xs font-bold transition cursor-pointer ${
                        isDone
                          ? "bg-emerald-500/20 border border-emerald-500/40 text-emerald-300"
                          : "bg-red-600 hover:bg-red-500 text-white shadow-md shadow-red-600/20"
                      }`}
                    >
                      <CheckCircle2 className="h-4 w-4" />
                      {isUpdating
                        ? "Đang xử lý & kiểm tra Sprint..."
                        : isDone
                        ? "Đã hoàn thành ✓"
                        : completedCount === totalCount - 1 &&
                          plan.autoContinueEnabled
                        ? "Hoàn tất & Tự lập Sprint mới!"
                        : "Đánh dấu Đã Đăng"}
                    </button>

                    <button
                      onClick={() =>
                        onSendToScriptBuilder(item.title, item.whySelected)
                      }
                      className="inline-flex items-center gap-1 rounded-xl border border-zinc-700 bg-zinc-800/80 hover:bg-zinc-800 px-3 py-2 text-xs text-zinc-300 transition cursor-pointer"
                    >
                      <PlayCircle className="h-3.5 w-3.5 text-amber-400" />
                      Chi tiết hóa phân cảnh
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
