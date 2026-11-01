"use client";

import {
  Check,
  Coins,
  Cpu,
  ExternalLink,
  RefreshCw,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { useState } from "react";
import { formatCompact, formatNumber } from "@/lib/format";
import type { AiUsageSummary } from "@/lib/types";

interface CreditMeterWidgetProps {
  usage?: AiUsageSummary;
  onCalibrated: (updatedUsage: AiUsageSummary, message?: string) => void;
}

export function CreditMeterWidget({
  usage,
  onCalibrated,
}: CreditMeterWidgetProps) {
  const [open, setOpen] = useState(false);
  const [syncInput, setSyncInput] = useState("");
  const [savingSync, setSavingSync] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  const creditLimit = usage?.creditLimitUsd ?? 300;
  const usedUsd = usage?.totalUsedUsd ?? 0;
  const remainingUsd = usage?.remainingUsd ?? creditLimit;
  const totalTokens = usage?.totalTokens ?? 0;
  const usedPct = Math.min(
    100,
    Math.max(0.2, (usedUsd / Math.max(1, creditLimit)) * 100)
  );
  const approxVnd = Math.round(usedUsd * 25_500);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await fetch("/api/usage");
      const json = await res.json();
      if (res.ok && json.aiUsage) {
        onCalibrated(json.aiUsage);
      }
    } finally {
      setRefreshing(false);
    }
  };

  const handleSaveCalibration = async () => {
    const val = Number(syncInput.replace(",", "."));
    if (Number.isNaN(val) || val < 0) return;
    setSavingSync(true);
    try {
      const res = await fetch("/api/usage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "calibrate",
          actualTotalUsedUsd: val,
        }),
      });
      const json = await res.json();
      if (res.ok && json.aiUsage) {
        onCalibrated(json.aiUsage, json.message);
        setSyncInput("");
      }
    } finally {
      setSavingSync(false);
    }
  };

  return (
    <div className="relative">
      {/* Compact Header Pill */}
      <button
        onClick={() => {
          setOpen((prev) => !prev);
          if (!open) void handleRefresh();
        }}
        className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/35 bg-emerald-950/25 hover:bg-emerald-950/45 px-3 py-2 text-xs font-semibold text-emerald-200 transition cursor-pointer"
        title="Xem chi tiết số Token & số tiền đã dùng trong gói $300 Google Cloud"
      >
        <Coins className="h-3.5 w-3.5 text-amber-400 shrink-0" />
        <span className="hidden md:inline text-zinc-300">Gói ${creditLimit}:</span>
        <span className="font-extrabold text-white">
          Đã dùng ${usedUsd.toFixed(2)}
        </span>
        <span className="hidden sm:inline text-emerald-300 font-bold">
          (Còn ${remainingUsd.toFixed(2)})
        </span>
        <span className="hidden xl:inline-flex items-center gap-1 rounded-md bg-zinc-900/90 border border-zinc-700/80 px-1.5 py-0.5 text-[10px] font-bold text-cyan-300">
          <Cpu className="h-3 w-3" />
          {formatCompact(totalTokens)} tok
        </span>
      </button>

      {/* Detailed Dropdown / Modal */}
      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px]"
            onClick={() => setOpen(false)}
          />
          <div className="fixed right-3 left-3 sm:left-auto sm:right-6 top-16 z-50 sm:w-[460px] rounded-2xl border border-zinc-700/90 bg-zinc-950 p-5 shadow-2xl space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-300">
                  <Coins className="h-4 w-4" />
                </div>
                <div>
                  <h3 className="text-sm font-extrabold text-white">
                    Đồng Hồ Gói $300 Vertex AI & Token
                  </h3>
                  <p className="text-[11px] text-zinc-400">
                    Project: starlit-cocoa-513211-p9 • Tự động đếm realtime
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1.5">
                <button
                  onClick={handleRefresh}
                  className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white cursor-pointer"
                  title="Làm mới số liệu"
                >
                  <RefreshCw
                    className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
                  />
                </button>
                <button
                  onClick={() => setOpen(false)}
                  className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 hover:text-white cursor-pointer"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

            {/* Credit Balance Card */}
            <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/30 via-zinc-900 to-zinc-900 p-4 space-y-3">
              <div className="flex items-end justify-between gap-2">
                <div>
                  <span className="block text-[10px] uppercase tracking-wider font-bold text-zinc-400">
                    Số tiền đã dùng (trừ vào gói tặng)
                  </span>
                  <div className="text-2xl font-extrabold text-white">
                    ${usedUsd.toFixed(3)}{" "}
                    <span className="text-xs font-semibold text-zinc-400">
                      (~{formatNumber(approxVnd)}đ)
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <span className="block text-[10px] uppercase tracking-wider font-bold text-emerald-400">
                    Còn lại trong $300
                  </span>
                  <div className="text-lg font-extrabold text-emerald-300">
                    ${remainingUsd.toFixed(2)}
                  </div>
                </div>
              </div>

              <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-amber-400 transition-all"
                  style={{ width: `${usedPct}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[11px] text-zinc-400">
                <span>
                  Đã tiêu:{" "}
                  <strong className="text-zinc-200">
                    {((usedUsd / Math.max(1, creditLimit)) * 100).toFixed(2)}%
                  </strong>{" "}
                  gói Free Trial
                </span>
                <a
                  href="https://console.cloud.google.com/billing/credits?project=starlit-cocoa-513211-p9"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-amber-300 hover:text-amber-200 font-semibold"
                >
                  Xem trên Google Billing
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>

            {/* Token Breakdown Grid */}
            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-2.5">
                <span className="block text-[10px] text-zinc-400">
                  Tổng Token AI
                </span>
                <span className="text-sm font-extrabold text-cyan-300">
                  {formatNumber(totalTokens)}
                </span>
                <span className="block text-[10px] text-zinc-500">
                  In: {formatCompact(usage?.totalPromptTokens ?? 0)} • Out:{" "}
                  {formatCompact(
                    (usage?.totalOutputTokens ?? 0) +
                      (usage?.totalThoughtTokens ?? 0)
                  )}
                </span>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-2.5">
                <span className="block text-[10px] text-zinc-400">
                  Ảnh AI / TTS
                </span>
                <span className="text-sm font-extrabold text-white">
                  {usage?.totalImagesGenerated ?? 0} ảnh •{" "}
                  {usage?.totalTtsCalls ?? 0} TTS
                </span>
                <span className="block text-[10px] text-zinc-500">
                  Tổng {usage?.totalCalls ?? 0} lệnh gọi
                </span>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-2.5">
                <span className="block text-[10px] text-zinc-400">
                  Thẻ Visa thật
                </span>
                <span className="text-sm font-extrabold text-emerald-400">
                  $0.00 bị trừ
                </span>
                <span className="block text-[10px] text-zinc-500">
                  100% trừ gói tặng
                </span>
              </div>
            </div>

            {/* Manual Sync Box (for standalone Mac runs) */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3 space-y-2">
              <div className="flex items-center gap-1.5 text-[11px] font-bold text-zinc-200">
                <SlidersHorizontal className="h-3.5 w-3.5 text-amber-400" />
                Khớp nhanh số dư với Google Cloud (nếu có chạy thêm ngoài Web)
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={syncInput}
                  onChange={(e) => setSyncInput(e.target.value)}
                  placeholder={`Nhập tổng $ đã dùng (VD: ${usedUsd.toFixed(2)})`}
                  className="flex-1 rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1.5 text-xs text-white placeholder:text-zinc-500 focus:border-emerald-500 focus:outline-none"
                />
                <button
                  onClick={handleSaveCalibration}
                  disabled={!syncInput.trim() || savingSync}
                  className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-45 px-3 py-1.5 text-xs font-bold text-white cursor-pointer"
                >
                  <Check className="h-3.5 w-3.5" />
                  Đồng bộ
                </button>
              </div>
            </div>

            {/* Recent AI Calls Feed */}
            <div className="space-y-1.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-zinc-400">
                Nhật ký tiêu thụ Token gần nhất
              </div>
              <div className="max-h-44 overflow-y-auto space-y-1.5 pr-1">
                {(usage?.recentCalls || []).slice(0, 12).map((item) => (
                  <div
                    key={item.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/80 bg-zinc-900/50 px-2.5 py-1.5 text-[11px]"
                  >
                    <div className="min-w-0">
                      <div className="font-semibold text-zinc-200 truncate">
                        {item.feature}
                      </div>
                      <div className="text-[10px] text-zinc-500 truncate">
                        {item.model} • {formatNumber(item.totalTokens)} tokens
                      </div>
                    </div>
                    <span
                      className={`shrink-0 font-bold ${
                        item.costUsd > 0 ? "text-amber-300" : "text-emerald-400"
                      }`}
                    >
                      {item.costUsd > 0
                        ? `-$${item.costUsd.toFixed(4)}`
                        : "Free $0"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
