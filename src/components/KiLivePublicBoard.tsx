"use client";

import {
  Activity,
  ArrowRight,
  ExternalLink,
  Flame,
  RefreshCw,
  Sparkles,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface PublicKiChallenge {
  id: string;
  videoId: string;
  characterName: string;
  episodeNumber: number;
  currentStageLabel: string;
  currentStageMediaUrl: string;
  currentAuraHex: string;
  nextStageLabel: string;
  nextStageMediaUrl: string;
  nextAuraHex: string;
  currentKi: number;
  targetKi: number;
  pctExact: number;
  reachedMilestone: 0 | 25 | 50 | 75 | 100;
  lastSyncedMilestone: 0 | 25 | 50 | 75 | 100;
  nextCheckpoint: 25 | 50 | 75 | 100;
  weights: {
    view: number;
    like: number;
    comment: number;
    sub: number;
  };
  stats: {
    views: number;
    likes: number;
    comments: number;
    gainedSubs: number;
  };
  syncIntervalMin: number;
  lastCheckedAt: string | null;
  watchUrl: string;
}

const CHECKPOINTS = [0, 25, 50, 75, 100] as const;

export function KiLivePublicBoard() {
  const [items, setItems] = useState<PublicKiChallenge[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(true);
  const [countdownSec, setCountdownSec] = useState<number>(15);

  const fetchLive = useCallback(async () => {
    try {
      const sp =
        typeof window !== "undefined"
          ? new URLSearchParams(window.location.search)
          : new URLSearchParams();
      const vFilter = sp.get("v") || "";
      const qs = vFilter ? `?v=${encodeURIComponent(vFilter)}` : "";
      const res = await fetch(`/api/ki-challenge/public${qs}`, {
        cache: "no-store",
      });
      const json = await res.json();
      if (res.ok && json.ok) {
        const list: PublicKiChallenge[] = json.items || [];
        setItems(list);
        setSelectedId((prev) =>
          prev && list.some((x) => x.id === prev) ? prev : list[0]?.id || ""
        );
      }
    } catch {
      // ignore transient error
    } finally {
      setLoading(false);
      setCountdownSec(15);
    }
  }, []);

  useEffect(() => {
    void fetchLive();
    const poll = setInterval(() => {
      void fetchLive();
    }, 15_000);
    const tick = setInterval(() => {
      setCountdownSec((s) => (s > 1 ? s - 1 : 15));
    }, 1_000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [fetchLive]);

  const active = items.find((x) => x.id === selectedId) || items[0] || null;

  return (
    <div className="min-h-screen bg-[#050816] text-zinc-100 px-4 py-8 sm:py-12">
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-zinc-800/80 pb-5">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/40 bg-emerald-950/30 px-3 py-1 text-[11px] font-extrabold text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
              REALTIME KI POWER TRACKER • ĐỒNG BỘ YOUTUBE MỖI 5 PHÚT
            </div>
            <h1 className="text-xl sm:text-2xl font-black tracking-tight text-white">
              ⚡ Bảng Đo Năng Lượng KI Thời Gian Thật
            </h1>
          </div>

          <div className="flex items-center gap-2">
            {items.length > 1 && (
              <select
                value={active?.id || ""}
                onChange={(e) => setSelectedId(e.target.value)}
                className="rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs font-bold text-white"
              >
                {items.map((it) => (
                  <option key={it.id} value={it.id}>
                    {it.characterName} Tập #{it.episodeNumber} ({it.pctExact}%)
                  </option>
                ))}
              </select>
            )}
            <button
              type="button"
              onClick={() => void fetchLive()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3.5 py-2 text-xs font-bold text-zinc-200 cursor-pointer"
            >
              <RefreshCw className="h-3.5 w-3.5 text-emerald-400" />
              Làm mới ({countdownSec}s)
            </button>
          </div>
        </div>

        {loading ? (
          <div className="py-24 text-center text-sm text-zinc-400">
            Đang kết nối cảm biến năng lượng KI...
          </div>
        ) : !active ? (
          <div className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-12 text-center space-y-3">
            <Flame className="h-10 w-10 text-amber-400 mx-auto" />
            <div className="text-base font-extrabold text-white">
              Hiện chưa có thử thách KI nào đang mở
            </div>
            <p className="text-xs text-zinc-400">
              Hãy mở Studio quản trị tại{" "}
              <a href="/?tab=ki" className="text-amber-300 underline">
                /?tab=ki
              </a>{" "}
              để khởi tạo hoặc gắn video YouTube cần theo dõi!
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* HERO REALTIME KI PROGRESS BAR CARD */}
            <div className="rounded-3xl border border-amber-500/40 bg-gradient-to-b from-zinc-900/95 to-zinc-950 p-6 sm:p-8 shadow-2xl space-y-6">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <div className="text-xs font-extrabold uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                    <Activity className="h-4 w-4" />
                    {active.characterName} • Episode #{active.episodeNumber}
                  </div>
                  <div className="mt-1 text-3xl sm:text-5xl font-black text-white tracking-tight">
                    {active.currentKi.toLocaleString("en-US")}{" "}
                    <span className="text-lg sm:text-2xl text-zinc-400 font-bold">
                      / {active.targetKi.toLocaleString("en-US")} KI
                    </span>
                  </div>
                </div>

                <div className="text-right">
                  <div className="text-3xl sm:text-4xl font-black text-amber-300">
                    {active.pctExact.toFixed(1)}%
                  </div>
                  <div className="text-xs text-zinc-400">
                    Mốc cập nhật Tiêu đề YouTube tiếp theo:{" "}
                    <strong className="text-emerald-300">
                      {active.pctExact >= 100
                        ? "100% (Đã hoàn thành!)"
                        : `${active.nextCheckpoint}%`}
                    </strong>
                  </div>
                </div>
              </div>

              {/* Giant Glowing Energy Bar + 25% / 50% / 75% / 100% Checkpoints */}
              <div className="space-y-3">
                <div className="relative h-7 w-full rounded-full bg-zinc-950 border-2 border-zinc-800 overflow-hidden p-0.5">
                  <div
                    style={{ width: `${Math.max(1.5, Math.min(100, active.pctExact))}%` }}
                    className="h-full rounded-full bg-gradient-to-r from-sky-500 via-amber-400 to-rose-500 shadow-[0_0_24px_rgba(250,204,21,0.65)] transition-all duration-700"
                  />
                  {[25, 50, 75].map((cp) => (
                    <div
                      key={cp}
                      style={{ left: `${cp}%` }}
                      className="absolute inset-y-0 w-0.5 bg-white/30"
                    />
                  ))}
                </div>

                <div className="flex items-center justify-between text-xs font-extrabold">
                  {CHECKPOINTS.map((cp) => {
                    const passed = active.pctExact >= cp;
                    const synced = active.lastSyncedMilestone >= cp && cp > 0;
                    return (
                      <div
                        key={cp}
                        className={`flex flex-col items-center ${
                          passed ? "text-amber-300" : "text-zinc-600"
                        }`}
                      >
                        <span>
                          {passed ? "⚡" : "🔒"} {cp}%
                        </span>
                        {cp > 0 && (
                          <span className="text-[10px] font-semibold text-zinc-400">
                            {synced ? "Đã đổi Title YT" : "Mốc đổi Title"}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* CHARACTER EVOLUTION STAGE COMPARISON */}
              <div className="grid grid-cols-1 md:grid-cols-7 gap-4 items-center pt-2">
                {/* Current Form */}
                <div className="md:col-span-3 rounded-2xl border-2 border-sky-500/60 bg-zinc-950 overflow-hidden shadow-lg">
                  <div className="aspect-[3/4] max-h-80 w-full overflow-hidden bg-black">
                    <img
                      src={active.currentStageMediaUrl}
                      alt={active.currentStageLabel}
                      className="h-full w-full object-cover object-top animate-pulse"
                      style={{ animationDuration: "3.5s" }}
                    />
                  </div>
                  <div className="p-3 text-center bg-zinc-950">
                    <div className="text-[10px] font-extrabold uppercase text-sky-400">
                      Trạng Thái Hiện Tại
                    </div>
                    <div className="text-base font-black text-white">
                      {active.currentStageLabel}
                    </div>
                  </div>
                </div>

                {/* Arrow */}
                <div className="md:col-span-1 flex flex-col items-center justify-center gap-1 py-2">
                  <div className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/20 border border-amber-400/60 text-amber-300">
                    <ArrowRight className="h-6 w-6" />
                  </div>
                  <span className="text-[11px] font-extrabold text-amber-300 text-center">
                    {active.targetKi.toLocaleString()} KI
                  </span>
                </div>

                {/* Next Form */}
                <div className="md:col-span-3 rounded-2xl border-2 border-amber-400/70 bg-zinc-950 overflow-hidden shadow-lg">
                  <div className="aspect-[3/4] max-h-80 w-full overflow-hidden bg-black">
                    <img
                      src={active.nextStageMediaUrl}
                      alt={active.nextStageLabel}
                      className={`h-full w-full object-cover object-top transition ${
                        active.pctExact >= 100 ? "" : "brightness-90"
                      }`}
                    />
                  </div>
                  <div className="p-3 text-center bg-zinc-950">
                    <div className="text-[10px] font-extrabold uppercase text-amber-300">
                      {active.pctExact >= 100
                        ? "🎉 ĐÃ MỞ KHÓA!"
                        : `Mở khóa khi đạt 100%`}
                    </div>
                    <div className="text-base font-black text-amber-200">
                      {active.nextStageLabel}
                    </div>
                  </div>
                </div>
              </div>

              {/* LIVE INTERACTION BREAKDOWN */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-3.5">
                  <div className="text-xs text-zinc-400">
                    👁️ Lượt xem (+{active.weights.view} KI)
                  </div>
                  <div className="mt-1 text-lg font-black text-white">
                    {active.stats.views.toLocaleString()}
                  </div>
                  <div className="text-xs font-bold text-sky-300">
                    +{(active.stats.views * active.weights.view).toLocaleString()} KI
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-3.5">
                  <div className="text-xs text-zinc-400">
                    👍 Lượt thích (+{active.weights.like} KI)
                  </div>
                  <div className="mt-1 text-lg font-black text-white">
                    {active.stats.likes.toLocaleString()}
                  </div>
                  <div className="text-xs font-bold text-emerald-300">
                    +{(active.stats.likes * active.weights.like).toLocaleString()} KI
                  </div>
                </div>

                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/80 p-3.5">
                  <div className="text-xs text-zinc-400">
                    💬 Bình luận (+{active.weights.comment} KI)
                  </div>
                  <div className="mt-1 text-lg font-black text-white">
                    {active.stats.comments.toLocaleString()}
                  </div>
                  <div className="text-xs font-bold text-purple-300">
                    +{(active.stats.comments * active.weights.comment).toLocaleString()} KI
                  </div>
                </div>

                <div className="rounded-2xl border border-amber-500/35 bg-amber-950/20 p-3.5">
                  <div className="text-xs text-amber-200">
                    🔔 Đăng ký mới (+{active.weights.sub} KI)
                  </div>
                  <div className="mt-1 text-lg font-black text-white">
                    +{active.stats.gainedSubs.toLocaleString()}
                  </div>
                  <div className="text-xs font-bold text-amber-300">
                    +{(active.stats.gainedSubs * active.weights.sub).toLocaleString()} KI
                  </div>
                </div>
              </div>

              {/* CTA TO YOUTUBE VIDEO */}
              <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
                <span className="text-xs text-zinc-400">
                  {active.lastCheckedAt
                    ? `Cập nhật từ YouTube lúc: ${new Date(
                        active.lastCheckedAt
                      ).toLocaleTimeString("vi-VN")}`
                    : "Đang chờ lần quét đầu tiên..."}
                </span>

                <a
                  href={active.watchUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 rounded-2xl bg-gradient-to-r from-red-600 to-amber-500 hover:from-red-500 hover:to-amber-400 px-6 py-3 text-sm font-black text-white shadow-xl transition"
                >
                  <Zap className="h-4 w-4" />
                  Mở Video YouTube Để Truyền Thêm KI Ngay!
                  <ExternalLink className="h-4 w-4" />
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
