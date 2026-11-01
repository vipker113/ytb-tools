"use client";

import {
  ArrowUpRight,
  Award,
  Check,
  Copy,
  Eye,
  Link2,
  QrCode,
  Sparkles,
  Target,
  TrendingUp,
  Users,
  Video,
} from "lucide-react";
import { useMemo, useState } from "react";
import {
  formatCompact,
  formatDateShort,
  formatDuration,
  formatNumber,
  getOutlierBadgeStyle,
} from "@/lib/format";
import type { TrackedChannel, VideoItem } from "@/lib/types";

interface OverviewTabProps {
  channel: TrackedChannel | undefined;
  smartClicks: number;
  onUpdateMilestone: (channelId: string, milestone: number) => Promise<void>;
  onAuditVideoInSeo: (video: VideoItem) => void;
  onGoToAddChannel: () => void;
}

export function OverviewTab({
  channel,
  smartClicks,
  onUpdateMilestone,
  onAuditVideoInSeo,
  onGoToAddChannel,
}: OverviewTabProps) {
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [editingMilestone, setEditingMilestone] = useState(false);
  const [milestoneInput, setMilestoneInput] = useState("");
  const [hoveredSnapIdx, setHoveredSnapIdx] = useState<number | null>(null);
  const [hoveredVideoIdx, setHoveredVideoIdx] = useState<number | null>(null);
  const [chartMode, setChartMode] = useState<"auto" | "videos" | "subs">("auto");

  const growthMetrics = useMemo(() => {
    if (!channel || channel.snapshots.length < 2) {
      return { subsDelta: 0, dailyVelocity: 0, daysToGoal: null as number | null };
    }
    const first = channel.snapshots[0];
    const last = channel.snapshots[channel.snapshots.length - 1];
    const subsDelta = last.subscribers - first.subscribers;
    const msDiff =
      new Date(last.date).getTime() - new Date(first.date).getTime();
    const days = Math.max(1, msDiff / (1000 * 60 * 60 * 24));
    const dailyVelocity = subsDelta / days;
    const remaining = Math.max(0, channel.targetMilestone - channel.subscribers);
    const daysToGoal =
      dailyVelocity > 0.2 ? Math.ceil(remaining / dailyVelocity) : null;

    return {
      subsDelta,
      dailyVelocity: Math.round(dailyVelocity * 10) / 10,
      daysToGoal,
    };
  }, [channel]);

  if (!channel) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-12 text-center">
        <Users className="mx-auto h-12 w-12 text-red-400 mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">
          Chưa có kênh YouTube nào đang chọn
        </h2>
        <p className="text-sm text-zinc-400 max-w-md mx-auto mb-6">
          Hãy kết nối kênh YouTube của bạn bằng @handle hoặc URL để bắt đầu theo dõi tốc độ tăng trưởng Subscribers thật và phân tích video kéo Sub.
        </p>
        <button
          onClick={onGoToAddChannel}
          className="inline-flex items-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 px-5 py-3 text-sm font-semibold text-white transition cursor-pointer"
        >
          + Thêm kênh YouTube của tôi
        </button>
      </div>
    );
  }

  const cleanHandle = channel.handle.startsWith("@")
    ? channel.handle
    : `@${channel.handle}`;
  const directSubUrl = `https://www.youtube.com/${cleanHandle}?sub_confirmation=1`;
  const origin =
    typeof window !== "undefined" ? window.location.origin : "http://localhost:3000";
  const deepLinkUrl = `${origin}/go/${encodeURIComponent(cleanHandle)}`;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&margin=8&data=${encodeURIComponent(
    directSubUrl
  )}`;

  const progressPct = Math.min(
    100,
    Math.round((channel.subscribers / Math.max(channel.targetMilestone, 1)) * 1000) /
      10
  );

  const copyText = (key: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  // Build SVG coordinates for subscriber chart
  const snaps = channel.snapshots;
  const chartW = 640;
  const chartH = 190;
  const padX = 28;
  const padY = 24;

  const minSubs =
    snaps.length > 0 ? Math.min(...snaps.map((s) => s.subscribers)) : 0;
  const maxSubs =
    snaps.length > 0 ? Math.max(...snaps.map((s) => s.subscribers)) : 100;
  const range = Math.max(maxSubs - minSubs, 10);

  const points = snaps.map((s, idx) => {
    const x =
      snaps.length === 1
        ? chartW / 2
        : padX + (idx / (snaps.length - 1)) * (chartW - padX * 2);
    const y =
      snaps.length === 1
        ? chartH / 2
        : chartH - padY - ((s.subscribers - minSubs) / range) * (chartH - padY * 2);
    return { x, y, snap: s };
  });

  const activeChartView =
    chartMode === "auto"
      ? snaps.length >= 2
        ? "subs"
        : "videos"
      : chartMode;

  const chronoVideos = [...channel.recentVideos]
    .slice(0, 12)
    .reverse();
  const maxVideoViews = Math.max(
    ...chronoVideos.map((v) => v.views),
    channel.medianViewsRecent || 100,
    100
  );

  const linePath =
    points.length > 0
      ? points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ")
      : "";
  const areaPath =
    points.length > 1
      ? `${linePath} L ${points[points.length - 1].x} ${
          chartH - padY
        } L ${points[0].x} ${chartH - padY} Z`
      : "";

  const sortedVideos = [...channel.recentVideos].sort(
    (a, b) => b.estimatedSubConversionScore - a.estimatedSubConversionScore
  );

  return (
    <div className="space-y-6">
      {/* Top Channel Banner & Milestone Bar */}
      <div className="rounded-2xl border border-zinc-800/90 bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-red-950/20 p-6">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="flex items-start sm:items-center gap-4">
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
              className="h-16 w-16 rounded-2xl object-cover border border-zinc-700 bg-zinc-800 shrink-0"
            />
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-bold text-white">{channel.title}</h2>
                <span className="rounded-full bg-zinc-800 px-2.5 py-0.5 text-xs font-medium text-zinc-300">
                  {cleanHandle}
                </span>
                <span className="rounded-full bg-red-500/15 border border-red-500/30 px-2.5 py-0.5 text-xs font-medium text-red-300">
                  {channel.niche}
                </span>
                {channel.isDemo && (
                  <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2.5 py-0.5 text-xs font-medium text-amber-300">
                    Dữ liệu mẫu Demo
                  </span>
                )}
              </div>
              <p className="text-sm text-zinc-400 mt-1 line-clamp-1 max-w-2xl">
                {channel.description || "Chưa có mô tả kênh."}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <a
              href={`https://www.youtube.com/${cleanHandle}`}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800/80 hover:bg-zinc-800 px-3.5 py-2 text-xs font-medium text-zinc-200 transition"
            >
              Mở kênh YouTube
              <ArrowUpRight className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        {/* Subscriber Milestone Progress */}
        <div className="mt-6 rounded-xl border border-zinc-800/80 bg-zinc-950/60 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-red-400" />
              <span className="text-sm font-semibold text-zinc-200">
                Tiến độ cột mốc:{" "}
                <span className="text-white">
                  {formatNumber(channel.subscribers)}
                </span>{" "}
                / {formatNumber(channel.targetMilestone)} Subscribers ({progressPct}%)
              </span>
            </div>

            <div className="flex items-center gap-3 text-xs">
              {growthMetrics.daysToGoal !== null && (
                <span className="rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-emerald-300 font-medium">
                  Dự kiến cán đích sau ~{growthMetrics.daysToGoal} ngày (+
                  {growthMetrics.dailyVelocity} sub/ngày)
                </span>
              )}
              {!editingMilestone ? (
                <button
                  onClick={() => {
                    setMilestoneInput(String(channel.targetMilestone));
                    setEditingMilestone(true);
                  }}
                  className="text-zinc-400 hover:text-white underline cursor-pointer"
                >
                  Đổi mục tiêu
                </button>
              ) : (
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    const num = Number(milestoneInput);
                    if (num > 0) {
                      await onUpdateMilestone(channel.id, num);
                    }
                    setEditingMilestone(false);
                  }}
                  className="flex items-center gap-1.5"
                >
                  <input
                    type="number"
                    value={milestoneInput}
                    onChange={(e) => setMilestoneInput(e.target.value)}
                    className="w-28 rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-white"
                    placeholder="VD: 10000"
                  />
                  <button
                    type="submit"
                    className="rounded-lg bg-red-600 px-2.5 py-1 text-xs font-medium text-white cursor-pointer"
                  >
                    Lưu
                  </button>
                </form>
              )}
            </div>
          </div>

          <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-red-600 via-rose-500 to-amber-400 transition-all duration-500"
              style={{ width: `${Math.max(3, progressPct)}%` }}
            />
          </div>
        </div>
      </div>

      {/* 4 KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium mb-2">
            <span>SUBSCRIBERS THẬT</span>
            <Users className="h-4 w-4 text-red-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {formatNumber(channel.subscribers)}
          </div>
          <div className="mt-2 flex items-center gap-1.5 text-xs">
            <span className="text-emerald-400 font-semibold">
              {growthMetrics.subsDelta >= 0 ? "+" : ""}
              {formatNumber(growthMetrics.subsDelta)} subs
            </span>
            <span className="text-zinc-500">trong kỳ theo dõi</span>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium mb-2">
            <span>TỔNG LƯỢT XEM & TB VIDEO</span>
            <Eye className="h-4 w-4 text-sky-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {formatCompact(channel.totalViews)}
          </div>
          <div className="mt-2 text-xs text-zinc-400">
            Trung vị gần đây:{" "}
            <span className="text-zinc-200 font-medium">
              {formatNumber(channel.medianViewsRecent)} views/video
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium mb-2">
            <span>TỶ LỆ TƯƠNG TÁC TB</span>
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {channel.engagementRateAvg.toFixed(2)}%
          </div>
          <div className="mt-2 text-xs text-zinc-400">
            {channel.engagementRateAvg >= 4.5 ? (
              <span className="text-emerald-400">
                Rất tốt (&gt;4.5% dễ được đề xuất)
              </span>
            ) : (
              <span>Mục tiêu đề xuất mạnh: &ge; 4.5%</span>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
          <div className="flex items-center justify-between text-zinc-400 text-xs font-medium mb-2">
            <span>CLICK PHỄU SMART LINK</span>
            <Link2 className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-white">
            {formatNumber(smartClicks)}
          </div>
          <div className="mt-2 text-xs text-zinc-400">
            Tổng số video trên kênh:{" "}
            <span className="text-zinc-200 font-medium">
              {formatNumber(channel.videoCount)}
            </span>
          </div>
        </div>
      </div>

      {/* Growth Chart + Smart Subscribe Link Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Subscriber Trajectory / Video Views Bar Chart */}
        <div className="lg:col-span-2 rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 flex flex-col justify-between">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-red-400" />
                {activeChartView === "videos"
                  ? "Biểu đồ Lượt xem các Video gần nhất (So với Trung vị kênh)"
                  : "Biểu đồ tăng trưởng Subscribers theo thời gian"}
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                {activeChartView === "videos"
                  ? "Các cột màu Cam/Xanh lá vượt vạch đứt Trung vị chính là công thức chủ đề đang được thuật toán đề xuất mạnh!"
                  : "Mỗi ngày đồng bộ, hệ thống tự động ghi lại cột mốc mới để vẽ đường tăng trưởng Sub thật."}
              </p>
            </div>

            <div className="flex items-center gap-1.5 rounded-xl bg-zinc-950 border border-zinc-800 p-1 text-xs">
              <button
                onClick={() => setChartMode("videos")}
                className={`rounded-lg px-2.5 py-1 font-medium transition cursor-pointer ${
                  activeChartView === "videos"
                    ? "bg-red-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Lượt xem Video
              </button>
              <button
                onClick={() => setChartMode("subs")}
                className={`rounded-lg px-2.5 py-1 font-medium transition cursor-pointer ${
                  activeChartView === "subs"
                    ? "bg-red-600 text-white"
                    : "text-zinc-400 hover:text-zinc-200"
                }`}
              >
                Lịch sử Subs ({snaps.length} ngày)
              </button>
            </div>
          </div>

          {activeChartView === "videos" ? (
            chronoVideos.length > 0 ? (
              <div className="space-y-2">
                <div
                  className={`h-9 rounded-lg border px-3 text-xs flex items-center justify-between gap-2 transition-colors ${
                    hoveredVideoIdx !== null && chronoVideos[hoveredVideoIdx]
                      ? "border-amber-500/40 bg-zinc-950"
                      : "border-zinc-800/80 bg-zinc-950/60"
                  }`}
                >
                  {hoveredVideoIdx !== null && chronoVideos[hoveredVideoIdx] ? (
                    <>
                      <span className="text-zinc-100 font-medium truncate">
                        <span className="text-zinc-500 font-mono mr-1.5">
                          #{hoveredVideoIdx + 1}
                        </span>
                        {chronoVideos[hoveredVideoIdx].title}
                      </span>
                      <span className="shrink-0 font-bold text-amber-300">
                        {formatNumber(chronoVideos[hoveredVideoIdx].views)} views (
                        {chronoVideos[hoveredVideoIdx].outlierScore}x)
                      </span>
                    </>
                  ) : (
                    <>
                      <span className="text-zinc-400 truncate">
                        💡 Di chuột qua các cột bên dưới để xem tên video & lượt xem chi tiết
                      </span>
                      <span className="shrink-0 font-semibold text-zinc-400">
                        Trung vị: {formatNumber(channel.medianViewsRecent)} views
                      </span>
                    </>
                  )}
                </div>

                <div className="w-full overflow-x-auto">
                  <svg
                    viewBox={`0 0 ${chartW} ${chartH}`}
                    className="w-full h-52 select-none"
                    onMouseLeave={() => setHoveredVideoIdx(null)}
                  >
                    {/* Median baseline line */}
                    {channel.medianViewsRecent > 0 && (
                      <g className="pointer-events-none">
                        <line
                          x1={padX}
                          x2={chartW - padX}
                          y1={
                            chartH -
                            padY -
                            (channel.medianViewsRecent / maxVideoViews) *
                              (chartH - padY * 2)
                          }
                          y2={
                            chartH -
                            padY -
                            (channel.medianViewsRecent / maxVideoViews) *
                              (chartH - padY * 2)
                          }
                          stroke="#f59e0b"
                          strokeOpacity="0.6"
                          strokeDasharray="5 4"
                        />
                        <text
                          x={chartW - padX}
                          y={
                            chartH -
                            padY -
                            (channel.medianViewsRecent / maxVideoViews) *
                              (chartH - padY * 2) -
                            5
                          }
                          textAnchor="end"
                          fill="#fbbf24"
                          fontSize="10"
                        >
                          Trung vị: {formatNumber(channel.medianViewsRecent)} views
                        </text>
                      </g>
                    )}

                    {chronoVideos.map((v, idx) => {
                      const slotW =
                        (chartW - padX * 2) / Math.max(chronoVideos.length, 1);
                      const slotX = padX + idx * slotW;
                      const barW = Math.min(36, Math.max(14, slotW * 0.62));
                      const x = slotX + (slotW - barW) / 2;
                      const barH = Math.max(
                        6,
                        (v.views / maxVideoViews) * (chartH - padY * 2)
                      );
                      const y = chartH - padY - barH;
                      const isHovered = hoveredVideoIdx === idx;
                      const fill =
                        v.outlierScore >= 2.5
                          ? "#f59e0b"
                          : v.outlierScore >= 1.3
                          ? "#10b981"
                          : "#52525b";

                      return (
                        <g
                          key={v.id}
                          onMouseEnter={() => setHoveredVideoIdx(idx)}
                          className="cursor-pointer"
                        >
                          {/* Active column subtle highlight */}
                          {isHovered && (
                            <rect
                              x={slotX + 2}
                              y={6}
                              width={Math.max(4, slotW - 4)}
                              height={chartH - 10}
                              rx="6"
                              fill="#ffffff"
                              opacity={0.045}
                              className="pointer-events-none"
                            />
                          )}
                          <rect
                            x={x}
                            y={y}
                            width={barW}
                            height={barH}
                            rx="5"
                            fill={fill}
                            opacity={isHovered ? 1 : 0.85}
                            className="pointer-events-none"
                          />
                          <text
                            x={x + barW / 2}
                            y={Math.max(12, y - 5)}
                            textAnchor="middle"
                            fill={isHovered ? "#fde68a" : "#d4d4d8"}
                            fontSize="9.5"
                            fontWeight={isHovered ? "bold" : "normal"}
                            className="pointer-events-none"
                          >
                            {formatCompact(v.views)}
                          </text>
                          <text
                            x={x + barW / 2}
                            y={chartH - 6}
                            textAnchor="middle"
                            fill={isHovered ? "#f4f4f5" : "#71717a"}
                            fontSize="10"
                            fontWeight={isHovered ? "bold" : "normal"}
                            className="pointer-events-none"
                          >
                            #{idx + 1}
                          </text>
                          {/* Full-column invisible hit target to prevent hover dead-zones */}
                          <rect
                            x={slotX}
                            y={0}
                            width={slotW}
                            height={chartH}
                            fill="transparent"
                          />
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-sm text-zinc-500">
                Chưa có dữ liệu video trên kênh.
              </div>
            )
          ) : points.length > 0 ? (
            <div className="w-full overflow-x-auto">
              {points.length === 1 && (
                <div className="mb-2 rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2 text-xs text-zinc-300">
                  📌 Đã ghi nhận mốc ngày đầu tiên (<strong>{formatNumber(points[0].snap.subscribers)} Subscribers</strong>). Hãy bấm <strong>Đồng bộ YouTube</strong> vào các ngày tiếp theo để nối đường xu hướng!
                </div>
              )}
              <svg
                viewBox={`0 0 ${chartW} ${chartH}`}
                className="w-full h-48 select-none"
              >
                <defs>
                  <linearGradient id="subAreaGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#ef4444" stopOpacity="0.38" />
                    <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
                  </linearGradient>
                </defs>

                {[0.2, 0.5, 0.8].map((ratio, idx) => (
                  <line
                    key={idx}
                    x1={padX}
                    x2={chartW - padX}
                    y1={padY + ratio * (chartH - padY * 2)}
                    y2={padY + ratio * (chartH - padY * 2)}
                    stroke="#27272a"
                    strokeDasharray="4 4"
                  />
                ))}

                {areaPath && <path d={areaPath} fill="url(#subAreaGrad)" />}
                {linePath && points.length > 1 && (
                  <path
                    d={linePath}
                    fill="none"
                    stroke="#ef4444"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                )}

                {points.map((p, idx) => (
                  <g
                    key={p.snap.date}
                    onMouseEnter={() => setHoveredSnapIdx(idx)}
                    onMouseLeave={() => setHoveredSnapIdx(null)}
                    className="cursor-pointer"
                  >
                    <circle
                      cx={p.x}
                      cy={p.y}
                      r={hoveredSnapIdx === idx ? 7 : 5}
                      fill="#ef4444"
                      stroke="#09090b"
                      strokeWidth="2"
                    />
                    <text
                      x={p.x}
                      y={p.y - 10}
                      textAnchor="middle"
                      fill="#f4f4f5"
                      fontSize="11"
                      fontWeight="bold"
                    >
                      {formatNumber(p.snap.subscribers)} subs
                    </text>
                    <text
                      x={p.x}
                      y={chartH - 5}
                      textAnchor="middle"
                      fill="#71717a"
                      fontSize="11"
                    >
                      {formatDateShort(p.snap.date)}
                    </text>
                  </g>
                ))}
              </svg>
            </div>
          ) : (
            <div className="py-12 text-center text-sm text-zinc-500">
              Chưa có mốc lịch sử nào.
            </div>
          )}
        </div>

        {/* Smart Subscribe Link & Deep Link Box */}
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <QrCode className="h-4 w-4 text-amber-400" />
              <h3 className="text-base font-bold text-white">
                Link Kéo Sub 1-Click & Deep Link
              </h3>
            </div>
            <p className="text-xs text-zinc-400 leading-relaxed mb-4">
              Dán vào Bio TikTok/FB, bình luận ghim và mô tả video để bật thẳng hộp thoại xác nhận Đăng ký trên App YouTube.
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium text-zinc-400 mb-1">
                  1. Link Xác Nhận Đăng Ký Chuẩn (Gắn Mô tả / Bình luận ghim)
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    readOnly
                    value={directSubUrl}
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 font-mono"
                  />
                  <button
                    onClick={() => copyText("direct", directSubUrl)}
                    className="shrink-0 rounded-xl bg-zinc-800 hover:bg-zinc-700 p-2 text-zinc-200 transition cursor-pointer"
                    title="Sao chép"
                  >
                    {copiedKey === "direct" ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-medium text-zinc-400 mb-1">
                  2. Smart Deep Link Mở App YouTube (Gắn Bio TikTok / FB / Zalo)
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    readOnly
                    value={deepLinkUrl}
                    className="w-full rounded-xl border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-amber-300 font-mono"
                  />
                  <button
                    onClick={() => copyText("deep", deepLinkUrl)}
                    className="shrink-0 rounded-xl bg-zinc-800 hover:bg-zinc-700 p-2 text-zinc-200 transition cursor-pointer"
                    title="Sao chép"
                  >
                    {copiedKey === "deep" ? (
                      <Check className="h-4 w-4 text-emerald-400" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-zinc-800/80 flex items-center gap-3">
            <img
              src={qrImageUrl}
              alt="QR Subscribe"
              className="h-16 w-16 rounded-xl bg-white p-1 shrink-0"
            />
            <div className="text-xs text-zinc-400 leading-relaxed">
              <strong className="text-zinc-200 block mb-0.5">
                Mã QR Đăng ký nhanh
              </strong>
              Chèn góc video dài (khi kêu gọi Sub) để người xem TV & máy tính quét bằng điện thoại!
            </div>
          </div>
        </div>
      </div>

      {/* Sub Magnet Video Analyzer Table */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-5">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-400" />
              Phân tích Video Kéo Sub Tốt Nhất Trên Kênh (Sub-Magnet Score)
            </h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              Xếp hạng các video đang có sức hút chuyển đổi người xem thành người đăng ký cao nhất để bạn nhân bản chủ đề hoặc tối ưu lại SEO cho video yếu.
            </p>
          </div>
        </div>

        {sortedVideos.length === 0 ? (
          <div className="py-10 text-center text-sm text-zinc-500">
            Kênh chưa có dữ liệu video công khai.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-zinc-800 text-[11px] uppercase tracking-wider text-zinc-400">
                  <th className="pb-3 pr-4">Video</th>
                  <th className="pb-3 px-3">Định dạng</th>
                  <th className="pb-3 px-3">Lượt xem</th>
                  <th className="pb-3 px-3">So với chuẩn kênh</th>
                  <th className="pb-3 px-3">Tương tác</th>
                  <th className="pb-3 px-3">Điểm Kéo Sub</th>
                  <th className="pb-3 pl-3 text-right">Tối ưu</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/70 text-sm">
                {sortedVideos.map((vid) => {
                  const badge = getOutlierBadgeStyle(vid.outlierScore);
                  return (
                    <tr
                      key={vid.id}
                      className="hover:bg-zinc-800/30 transition group"
                    >
                      <td className="py-3.5 pr-4 max-w-md">
                        <div className="flex items-center gap-3">
                          {vid.thumbnailUrl ? (
                            <img
                              src={vid.thumbnailUrl}
                              alt={vid.title}
                              className="h-12 w-20 rounded-lg object-cover bg-zinc-800 shrink-0 border border-zinc-800"
                            />
                          ) : (
                            <div className="h-12 w-20 rounded-lg bg-zinc-800 flex items-center justify-center shrink-0">
                              <Video className="h-5 w-5 text-zinc-500" />
                            </div>
                          )}
                          <div className="min-w-0">
                            <p className="font-medium text-zinc-100 line-clamp-2 text-xs sm:text-sm leading-snug">
                              {vid.title}
                            </p>
                            <span className="text-[11px] text-zinc-500">
                              Đăng ngày {formatDateShort(vid.publishedAt)} •{" "}
                              {formatNumber(vid.viewsPerDay)} views/ngày
                            </span>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-3 whitespace-nowrap">
                        {vid.isShort ? (
                          <span className="inline-flex items-center gap-1 rounded-md bg-rose-500/15 border border-rose-500/30 px-2 py-0.5 text-xs font-medium text-rose-300">
                            Shorts ({formatDuration(vid.durationSeconds)})
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-md bg-zinc-800 px-2 py-0.5 text-xs text-zinc-300">
                            Dài ({formatDuration(vid.durationSeconds)})
                          </span>
                        )}
                      </td>

                      <td className="py-3.5 px-3 whitespace-nowrap font-semibold text-zinc-200">
                        {formatNumber(vid.views)}
                      </td>

                      <td className="py-3.5 px-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${badge.className}`}
                        >
                          {badge.label}
                        </span>
                      </td>

                      <td className="py-3.5 px-3 whitespace-nowrap text-xs text-zinc-300">
                        <span className="font-semibold text-emerald-400">
                          {vid.engagementRate.toFixed(2)}%
                        </span>
                        <div className="text-[11px] text-zinc-500">
                          {formatCompact(vid.likes)} thích •{" "}
                          {formatCompact(vid.comments)} cmt
                        </div>
                      </td>

                      <td className="py-3.5 px-3 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <div className="h-2 w-16 rounded-full bg-zinc-800 overflow-hidden">
                            <div
                              className={`h-full rounded-full ${
                                vid.estimatedSubConversionScore >= 80
                                  ? "bg-emerald-500"
                                  : vid.estimatedSubConversionScore >= 55
                                  ? "bg-amber-400"
                                  : "bg-red-500"
                              }`}
                              style={{
                                width: `${vid.estimatedSubConversionScore}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs font-bold text-white">
                            {vid.estimatedSubConversionScore}/100
                          </span>
                        </div>
                      </td>

                      <td className="py-3.5 pl-3 text-right whitespace-nowrap">
                        <button
                          onClick={() => onAuditVideoInSeo(vid)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800/90 hover:bg-red-600 hover:border-red-500 px-3 py-1.5 text-xs font-medium text-zinc-200 hover:text-white transition cursor-pointer"
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                          Chấm SEO
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
