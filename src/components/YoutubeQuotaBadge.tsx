"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Clock,
  ExternalLink,
  Gauge,
  RefreshCw,
  SlidersHorizontal,
} from "lucide-react";

interface QuotaBucket {
  calls: number;
  units: number;
}

interface QuotaLogEntry {
  at: string;
  endpoint: string;
  method: string;
  units: number;
  category: string;
  label: string;
  ok: boolean;
}

export interface YoutubeQuotaClientSummary {
  ptDate: string;
  trackedUnits: number;
  manualAdjustment: number;
  dailyLimit: number;
  usedUnits: number;
  remainingUnits: number;
  usagePct: number;
  remainingTitleUpdates: number;
  remainingVideoUploads: number;
  quotaExceededFlag: boolean;
  nextResetAtIso: string;
  secondsUntilReset: number;
  breakdown: {
    kiRead: QuotaBucket;
    kiTitleUpdate: QuotaBucket;
    videoUpload: QuotaBucket;
    studioWrite: QuotaBucket;
    search: QuotaBucket;
    channelRead: QuotaBucket;
  };
  recentLogs: QuotaLogEntry[];
}

export function triggerYoutubeQuotaRefresh() {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("ytb-quota-refresh"));
  }
}

function formatCountdown(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${h}h ${m.toString().padStart(2, "0")}p`;
}

function formatVnTime(iso: string): string {
  try {
    return new Intl.DateTimeFormat("vi-VN", {
      timeZone: "Asia/Ho_Chi_Minh",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return "14:00";
  }
}

export function YoutubeQuotaBadge({
  variant = "header",
}: {
  variant?: "header" | "card";
}) {
  const [quota, setQuota] = useState<YoutubeQuotaClientSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [showCalibrate, setShowCalibrate] = useState(false);
  const [manualInput, setManualInput] = useState("");
  const [savingCalibrate, setSavingCalibrate] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);

  const fetchQuota = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/youtube/quota", { cache: "no-store" });
      const json = await res.json();
      if (json?.ok && json.quota) {
        setQuota(json.quota);
      }
    } catch {
      // ignore transient network errors
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchQuota();
    const id = setInterval(() => {
      void fetchQuota();
    }, 25_000);
    const onRefresh = () => void fetchQuota();
    window.addEventListener("ytb-quota-refresh", onRefresh);
    return () => {
      clearInterval(id);
      window.removeEventListener("ytb-quota-refresh", onRefresh);
    };
  }, [fetchQuota]);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const handleSaveCalibrate = async () => {
    const num = Number.parseInt(manualInput.replace(/[^\d]/g, ""), 10);
    if (!Number.isFinite(num) || num < 0) return;
    setSavingCalibrate(true);
    try {
      const res = await fetch("/api/youtube/quota", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ setExactUsedUnits: num }),
      });
      const json = await res.json();
      if (json?.ok && json.quota) {
        setQuota(json.quota);
        setShowCalibrate(false);
        setManualInput("");
        triggerYoutubeQuotaRefresh();
      }
    } finally {
      setSavingCalibrate(false);
    }
  };

  const pct = quota?.usagePct ?? 0;
  const isDanger = Boolean(quota?.quotaExceededFlag) || pct >= 85;
  const isWarn = !isDanger && pct >= 60;

  const toneBorder = isDanger
    ? "border-rose-500/45 bg-rose-950/30 text-rose-200"
    : isWarn
    ? "border-amber-500/45 bg-amber-950/25 text-amber-200"
    : "border-emerald-500/35 bg-emerald-950/20 text-emerald-200";

  const barFill = isDanger
    ? "bg-gradient-to-r from-rose-500 to-red-400"
    : isWarn
    ? "bg-gradient-to-r from-amber-500 to-yellow-400"
    : "bg-gradient-to-r from-emerald-500 to-sky-400";

  if (variant === "card") {
    return (
      <div className="rounded-xl border border-zinc-800 bg-zinc-950/85 p-3.5 space-y-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Gauge
              className={`h-4 w-4 ${
                isDanger
                  ? "text-rose-400"
                  : isWarn
                  ? "text-amber-400"
                  : "text-emerald-400"
              }`}
            />
            <span className="text-xs font-extrabold text-white">
              YouTube Daily Quota ({quota?.ptDate || "Hôm nay"})
            </span>
            {quota?.quotaExceededFlag && (
              <span className="inline-flex items-center gap-1 rounded-md bg-rose-500/20 border border-rose-500/40 px-2 py-0.5 text-[10px] font-bold text-rose-300">
                <AlertTriangle className="h-3 w-3" />
                Chạm trần Quota API
              </span>
            )}
          </div>

          <div className="flex items-center gap-2 text-[11px]">
            <span className="inline-flex items-center gap-1 text-zinc-400">
              <Clock className="h-3 w-3 text-sky-400" />
              Reset sau{" "}
              <strong className="text-sky-300">
                {quota ? formatCountdown(quota.secondsUntilReset) : "--"}
              </strong>{" "}
              ({quota ? formatVnTime(quota.nextResetAtIso) : "14:00"} VN)
            </span>
            <button
              type="button"
              onClick={() => {
                setManualInput(String(quota?.usedUnits ?? 0));
                setShowCalibrate((v) => !v);
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2 py-1 text-[10px] font-semibold text-zinc-300 cursor-pointer"
              title="Khớp số unit thực tế trên Google Cloud Console (nếu có dùng key ở app khác)"
            >
              <SlidersHorizontal className="h-3 w-3" />
              Khớp GCP
            </button>
            <a
              href="https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2 py-1 text-[10px] font-semibold text-zinc-300"
            >
              GCP Quotas
              <ExternalLink className="h-2.5 w-2.5" />
            </a>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-xs">
            <span className="font-bold text-zinc-200">
              Đã dùng:{" "}
              <span className="text-white font-extrabold">
                {(quota?.usedUnits ?? 0).toLocaleString()}
              </span>{" "}
              / {(quota?.dailyLimit ?? 10000).toLocaleString()} units ({pct}%)
            </span>
            <span className="text-[11px] text-zinc-400">
              Còn lại:{" "}
              <strong className="text-emerald-300">
                {(quota?.remainingUnits ?? 10000).toLocaleString()}u
              </strong>{" "}
              (~{quota?.remainingTitleUpdates ?? 200} lần đổi Title • ~
              {quota?.remainingVideoUploads ?? 6} lần Upload)
            </span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-900 border border-zinc-800">
            <div
              style={{ width: `${Math.max(1, Math.min(100, pct))}%` }}
              className={`h-full transition-all duration-500 ${barFill}`}
            />
          </div>
        </div>

        {/* Category Pills */}
        {quota && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2.5 py-1.5 flex items-center justify-between">
              <span className="text-zinc-400">⚡ KI Đọc stats</span>
              <span className="font-bold text-sky-300">
                {quota.breakdown.kiRead.units}u ({quota.breakdown.kiRead.calls})
              </span>
            </div>
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2.5 py-1.5 flex items-center justify-between">
              <span className="text-zinc-400">🔥 KI Đổi Title</span>
              <span className="font-bold text-amber-300">
                {quota.breakdown.kiTitleUpdate.units}u (
                {quota.breakdown.kiTitleUpdate.calls})
              </span>
            </div>
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2.5 py-1.5 flex items-center justify-between">
              <span className="text-zinc-400">🎬 Upload/Thumb</span>
              <span className="font-bold text-violet-300">
                {quota.breakdown.videoUpload.units}u (
                {quota.breakdown.videoUpload.calls})
              </span>
            </div>
            <div className="rounded-lg border border-zinc-800/80 bg-zinc-900/60 px-2.5 py-1.5 flex items-center justify-between">
              <span className="text-zinc-400">📊 Kênh & Studio</span>
              <span className="font-bold text-emerald-300">
                {quota.breakdown.channelRead.units +
                  quota.breakdown.studioWrite.units +
                  quota.breakdown.search.units}
                u
              </span>
            </div>
          </div>
        )}

        {showCalibrate && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-zinc-800/80 text-xs">
            <span className="text-zinc-400">
              Nhập tổng unit hiện tại trên Google Cloud Console:
            </span>
            <input
              type="number"
              min={0}
              max={1000000}
              value={manualInput}
              onChange={(e) => setManualInput(e.target.value)}
              placeholder="VD: 1850"
              className="w-28 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-white"
            />
            <button
              type="button"
              disabled={savingCalibrate}
              onClick={() => void handleSaveCalibrate()}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1 text-xs font-bold text-white cursor-pointer disabled:opacity-50"
            >
              {savingCalibrate ? "Đang lưu..." : "Lưu khớp số"}
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={() => {
          setOpen((v) => !v);
          void fetchQuota();
        }}
        className={`inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-[11px] font-bold transition cursor-pointer ${toneBorder}`}
        title="Xem chi tiết hạn mức YouTube Data API v3 hôm nay (10,000 units/ngày)"
      >
        <Gauge className="h-3.5 w-3.5 shrink-0" />
        <span className="hidden sm:inline">YT Quota:</span>
        <span>
          {quota
            ? `${quota.usedUnits.toLocaleString()}/${(
                quota.dailyLimit / 1000
              ).toFixed(0)}k`
            : "--/10k"}
        </span>
        <span className="hidden md:inline-block w-12 h-1.5 rounded-full bg-zinc-900/90 overflow-hidden">
          <span
            style={{ width: `${Math.max(3, Math.min(100, pct))}%` }}
            className={`block h-full ${barFill}`}
          />
        </span>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl border border-zinc-700/90 bg-zinc-950/95 backdrop-blur-xl p-4 shadow-2xl z-50 space-y-3 text-xs">
          <div className="flex items-center justify-between gap-2">
            <div className="font-extrabold text-white flex items-center gap-1.5">
              <Activity className="h-4 w-4 text-emerald-400" />
              YouTube API Daily Quota
            </div>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => void fetchQuota()}
                className="rounded-lg border border-zinc-800 p-1 text-zinc-400 hover:text-white cursor-pointer"
                title="Làm mới"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`}
                />
              </button>
              <a
                href="https://console.cloud.google.com/apis/api/youtube.googleapis.com/quotas"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-900 px-2 py-1 text-[10px] font-bold text-sky-300 hover:bg-zinc-800"
              >
                GCP Console
                <ExternalLink className="h-2.5 w-2.5" />
              </a>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-extrabold text-white">
                {(quota?.usedUnits ?? 0).toLocaleString()}{" "}
                <span className="text-xs font-normal text-zinc-400">
                  / {(quota?.dailyLimit ?? 10000).toLocaleString()} units ({pct}
                  %)
                </span>
              </span>
              <span className="text-[11px] text-emerald-300 font-bold">
                Còn {(quota?.remainingUnits ?? 10000).toLocaleString()}u
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-900 border border-zinc-800">
              <div
                style={{ width: `${Math.max(1, Math.min(100, pct))}%` }}
                className={`h-full transition-all duration-500 ${barFill}`}
              />
            </div>
            <div className="flex items-center justify-between text-[11px] text-zinc-400">
              <span>
                Đổi Title còn ~
                <strong className="text-zinc-200">
                  {quota?.remainingTitleUpdates ?? 200}
                </strong>{" "}
                lần • Upload ~
                <strong className="text-zinc-200">
                  {quota?.remainingVideoUploads ?? 6}
                </strong>{" "}
                video
              </span>
              <span>
                Reset:{" "}
                <strong className="text-sky-300">
                  {quota ? formatCountdown(quota.secondsUntilReset) : "--"}
                </strong>
              </span>
            </div>
          </div>

          {quota && (
            <div className="space-y-1 border-t border-zinc-800/80 pt-2.5 text-[11px]">
              <div className="flex justify-between text-zinc-300">
                <span>⚡ KI Sync đọc chỉ số (1u/call):</span>
                <span className="font-bold">
                  {quota.breakdown.kiRead.units}u ({quota.breakdown.kiRead.calls}{" "}
                  calls)
                </span>
              </div>
              <div className="flex justify-between text-zinc-300">
                <span>🔥 KI tự đổi Title (50u/lần):</span>
                <span className="font-bold text-amber-300">
                  {quota.breakdown.kiTitleUpdate.units}u (
                  {quota.breakdown.kiTitleUpdate.calls} lần)
                </span>
              </div>
              <div className="flex justify-between text-zinc-300">
                <span>🎬 Upload Video / Thumb (1600u / 50u):</span>
                <span className="font-bold text-violet-300">
                  {quota.breakdown.videoUpload.units}u (
                  {quota.breakdown.videoUpload.calls} lần)
                </span>
              </div>
              <div className="flex justify-between text-zinc-300">
                <span>📊 Đồng bộ Kênh / Studio / Search:</span>
                <span className="font-bold text-emerald-300">
                  {quota.breakdown.channelRead.units +
                    quota.breakdown.studioWrite.units +
                    quota.breakdown.search.units}
                  u
                </span>
              </div>
            </div>
          )}

          {quota && quota.recentLogs.length > 0 && (
            <div className="border-t border-zinc-800/80 pt-2 space-y-1 max-h-32 overflow-y-auto">
              <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                Lịch sử gọi API gần nhất
              </div>
              {quota.recentLogs.slice(0, 6).map((log, i) => (
                <div
                  key={`${log.at}-${i}`}
                  className="flex items-center justify-between gap-2 text-[11px] text-zinc-400"
                >
                  <span className="truncate">{log.label}</span>
                  <span className="shrink-0 font-mono text-zinc-200">
                    +{log.units}u
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-zinc-800/80 pt-2">
            {!showCalibrate ? (
              <button
                type="button"
                onClick={() => {
                  setManualInput(String(quota?.usedUnits ?? 0));
                  setShowCalibrate(true);
                }}
                className="w-full rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 py-1.5 text-[11px] font-semibold text-zinc-300 cursor-pointer"
              >
                Chỉnh khớp số thực tế trên Google Cloud Console
              </button>
            ) : (
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min={0}
                  value={manualInput}
                  onChange={(e) => setManualInput(e.target.value)}
                  placeholder="Số unit trên GCP..."
                  className="flex-1 rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1 text-xs text-white"
                />
                <button
                  type="button"
                  disabled={savingCalibrate}
                  onClick={() => void handleSaveCalibrate()}
                  className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 text-xs font-bold text-white cursor-pointer"
                >
                  Lưu
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
