"use client";

import {
  AlertCircle,
  BookmarkPlus,
  Check,
  Copy,
  ExternalLink,
  MessageSquarePlus,
  Repeat,
  Rocket,
  Sparkles,
  Wand2,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RetentionWinnerBenchmark } from "@/app/api/growth/script/route";
import { formatNumber } from "@/lib/format";
import type { SavedIdea, TrackedChannel } from "@/lib/types";
import {
  diagnoseExistingVideosForSubRescue,
  type ViralShortBlueprint,
} from "@/lib/viral-script";

interface GrowthEngineTabProps {
  channel: TrackedChannel | undefined;
  defaultModel?: string;
  initialTopic?: { topic: string; sourceTitle?: string; autoRun?: boolean } | null;
  onSaveBlueprintAsIdea: (idea: Partial<SavedIdea>) => Promise<void>;
}

const SCIENCE_POWER_TOPICS = [
  "Why Scientists Sealed Movile Cave With 5-Million-Year-Old Toxic Air Forever",
  "What Actually Happens Inside the Deepest Hole Humans Ever Drilled (12,262m)?",
  "The Natural Nuclear Reactor in Gabon That Burned for 300,000 Years Underground",
  "The Cave in Mexico So Hot Humans Survive Only 10 Minutes Without Ice Suits",
];

export function GrowthEngineTab({
  channel,
  defaultModel = "gemini-3.6-flash",
  initialTopic,
  onSaveBlueprintAsIdea,
}: GrowthEngineTabProps) {
  const [topicInput, setTopicInput] = useState(
    initialTopic?.topic || SCIENCE_POWER_TOPICS[0]
  );
  const [sourceOutlierTitle, setSourceOutlierTitle] = useState(
    initialTopic?.sourceTitle || ""
  );
  const [selectedModel, setSelectedModel] = useState<string>(
    defaultModel || "gemini-3.6-flash"
  );
  const [generating, setGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [result, setResult] = useState<{
    blueprint: ViralShortBlueprint;
    usedAi: boolean;
    modelUsed?: string;
    retentionWinners?: RetentionWinnerBenchmark[];
  } | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [savedIdea, setSavedIdea] = useState(false);

  const rescues = useMemo(() => {
    if (!channel) return [];
    return diagnoseExistingVideosForSubRescue(
      channel.recentVideos,
      channel.handle
    );
  }, [channel]);

  const copyText = (key: string, val: string) => {
    navigator.clipboard.writeText(val);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  const lastSeedRef = useRef<string>("");

  const handleGenerate = async (customTopic?: string, customSource?: string) => {
    const target = (customTopic ?? topicInput).trim();
    if (!target) return;
    if (customTopic !== undefined) {
      setTopicInput(customTopic);
      setSourceOutlierTitle(customSource ?? "");
    }
    setGenerating(true);
    setErrorMsg(null);
    setSavedIdea(false);
    try {
      const res = await fetch("/api/growth/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: target,
          sourceOutlierTitle:
            customTopic !== undefined ? customSource : sourceOutlierTitle,
          model: selectedModel,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi tạo kịch bản AI");
      setResult(json);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Lỗi tạo kịch bản AI");
    } finally {
      setGenerating(false);
    }
  };

  useEffect(() => {
    if (!initialTopic?.topic) return;
    const sig = `${initialTopic.topic}|${initialTopic.sourceTitle || ""}`;
    if (lastSeedRef.current === sig) return;
    lastSeedRef.current = sig;
    setTopicInput(initialTopic.topic);
    setSourceOutlierTitle(initialTopic.sourceTitle || "");
    if (initialTopic.autoRun) {
      void handleGenerate(initialTopic.topic, initialTopic.sourceTitle);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialTopic]);

  const antigravityProductionPrompt = useMemo(() => {
    if (!result) return "";
    const bp = result.blueprint;
    const bestTitle = bp.winningTitles[0] || bp.topic;
    const sceneLines = bp.scenes
      .map(
        (s) =>
          `- [${s.timestamp}] Visual: ${s.visualDirection}\n  Voiceover: "${s.voiceover}"`
      )
      .join("\n");
    return `Hãy sản xuất video Documentary Shorts chuẩn kênh Proof of Wonder (pow_documentary_v3) theo kịch bản giữ chân người xem dưới đây:
- Tiêu đề chính: "${bestTitle}"
- Từ khóa SEO mục tiêu: "${bp.tags[0] || bp.topic}"
- Mở đầu 0–3s (Hook chống vuốt bỏ):
  + Hình ảnh: ${bp.first3sHook.visualPrompt}
  + Lời thoại mở đầu: "${bp.first3sHook.voiceover}"
- Kịch bản phân cảnh giữ chân & Loop:
${sceneLines}
- Bình luận ghim: "${bp.pinnedDebateComment}"
Hãy tải tư liệu thực tế chuẩn NASA/NOAA/CC-BY, chạy đủ 11 cổng QC và xuất sang đúng thư mục Playlist để tôi duyệt trên Web.`;
  }, [result]);

  const fullVoiceoverText = useMemo(() => {
    if (!result) return "";
    return [
      result.blueprint.first3sHook.voiceover,
      ...result.blueprint.scenes.map((s) => s.voiceover),
    ].join(" ");
  }, [result]);

  return (
    <div className="space-y-8">
      {/* SECTION 1: AI 45-Second Infinite-Loop Shorts Generator */}
      <div className="rounded-2xl border border-red-500/30 bg-gradient-to-br from-red-950/25 via-zinc-900 to-zinc-900 p-6">
        <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
          <div>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-red-500/15 border border-red-500/30 px-3 py-1 text-xs font-bold text-red-300 mb-2">
              <Rocket className="h-3.5 w-3.5" />
              Vũ khí Tăng Tốc Subscribers cho {channel?.title || "Kênh của bạn"}
            </div>
            <h2 className="text-xl font-extrabold text-white">
              AI Thiết Kế Kịch Bản Shorts 45s Nối Vòng Lặp (Infinite-Loop &gt;105% APV)
            </h2>
            <p className="text-sm text-zinc-400 mt-1 max-w-3xl">
              Trên YouTube Shorts, thuật toán chỉ bơm video vượt mốc 1.200 views lên{" "}
              <strong className="text-white">50.000 – 500.000+ views</strong> khi đạt{" "}
              <strong className="text-emerald-300">
                &gt;75% không vuốt bỏ ở 3 giây đầu
              </strong>{" "}
              và{" "}
              <strong className="text-amber-300">
                &gt;100% thời lượng xem trung bình nhờ câu cuối nối thẳng về câu đầu
              </strong>
              .
            </p>
          </div>
        </div>

        {/* Quick Topic Pills tailored to Proof of Wonder */}
        <div className="mb-4">
          <span className="block text-xs font-semibold text-zinc-400 mb-2">
            🔥 Gợi ý chủ đề đúng công thức thắng lớn nhất trên kênh của bạn (Bấm để tạo ngay):
          </span>
          <div className="flex flex-wrap gap-2">
            {SCIENCE_POWER_TOPICS.map((t) => (
              <button
                key={t}
                type="button"
                disabled={generating}
                onClick={() => handleGenerate(t)}
                className="rounded-xl border border-zinc-700/80 bg-zinc-950/80 hover:border-red-500/60 hover:text-white px-3 py-1.5 text-xs text-zinc-300 transition cursor-pointer text-left"
              >
                ⚡ {t}
              </button>
            ))}
          </div>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleGenerate();
          }}
          className="flex flex-col sm:flex-row gap-3"
        >
          <input
            type="text"
            value={topicInput}
            onChange={(e) => setTopicInput(e.target.value)}
            placeholder="Nhập câu hỏi khoa học kỳ lạ hoặc chủ đề Outlier đối thủ..."
            className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
          />
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            className="rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-3 text-xs sm:text-sm font-medium text-zinc-200 focus:border-red-500 focus:outline-none"
          >
            <option value="gemini-3.6-flash">
              Gemini 3.6 Flash (0₫ • Khuyên dùng • Mới nhất)
            </option>
            <option value="gemini-3.5-flash">
              Gemini 3.5 Flash (0₫ • Siêu nhanh ~1s)
            </option>
            <option value="gemini-3-flash-preview">
              Gemini 3 Flash Preview (0₫ • Ổn định)
            </option>
            <option value="gemini-3.1-pro-preview">
              Gemini 3.1 Pro (Cần Billing • Tự fallback 3.6 Flash)
            </option>
            <option value="gemini-4-argon">
              Gemini 4 Argon (Cần Billing • Tự fallback 3.6 Flash)
            </option>
          </select>

          <button
            type="submit"
            disabled={generating || !topicInput.trim()}
            className="shrink-0 inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-red-600/20 transition cursor-pointer"
          >
            <Wand2 className="h-4 w-4" />
            {generating
              ? "Gemini AI đang biên kịch giữ chân..."
              : "Tạo Kịch Bản Giữ Chân"}
          </button>
        </form>

        {errorMsg && (
          <div className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
            {errorMsg}
          </div>
        )}

        {/* Generated Blueprint Display */}
        {result && (
          <div className="mt-6 pt-6 border-t border-zinc-800 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-amber-400" />
                <span className="text-sm font-bold text-white">
                  Bản thiết kế hoàn chỉnh{" "}
                  {result.usedAi
                    ? `(Được tạo bởi ${result.modelUsed || selectedModel} Live)`
                    : ""}
                </span>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  onClick={() =>
                    copyText("agy-full-script", antigravityProductionPrompt)
                  }
                  className="inline-flex items-center gap-1.5 rounded-xl bg-sky-500/20 hover:bg-sky-500/30 border border-sky-500/40 px-4 py-2 text-xs font-bold text-sky-200 transition cursor-pointer"
                >
                  {copiedKey === "agy-full-script" ? (
                    <>
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                      Đã chép trọn bộ lệnh dựng cho Antigravity!
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      Copy Kịch Bản Này Để Antigravity Dựng Video
                    </>
                  )}
                </button>

                <button
                  onClick={async () => {
                    await onSaveBlueprintAsIdea({
                      title:
                        result.blueprint.winningTitles[0] ||
                        result.blueprint.topic,
                      remakeTitle:
                        result.blueprint.winningTitles[0] ||
                        result.blueprint.topic,
                      targetKeyword:
                        result.blueprint.tags[0] || result.blueprint.topic,
                      format: "short",
                      status: "scripting",
                      tags: result.blueprint.tags,
                      notes: `🎙️ VOICEOVER:\n${fullVoiceoverText}\n\n💬 PINNED COMMENT:\n${result.blueprint.pinnedDebateComment}`,
                    });
                    setSavedIdea(true);
                  }}
                  disabled={savedIdea}
                  className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-2 text-xs font-bold transition cursor-pointer ${
                    savedIdea
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                      : "bg-amber-500 hover:bg-amber-400 text-zinc-950"
                  }`}
                >
                  {savedIdea ? (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      Đã lưu kịch bản vào Kho Ý Tưởng
                    </>
                  ) : (
                    <>
                      <BookmarkPlus className="h-3.5 w-3.5" />
                      Lưu trọn bộ sang Kho Ý Tưởng
                    </>
                  )}
                </button>
              </div>
            </div>

            {result.retentionWinners && result.retentionWinners.length > 0 && (
              <div className="rounded-xl border border-emerald-500/25 bg-emerald-950/20 px-4 py-2.5 text-[11px] text-zinc-300 flex flex-wrap items-center gap-2">
                <span className="font-bold text-emerald-300">
                  📊 Đã học theo cấu trúc giữ chân tốt nhất của kênh:
                </span>
                {result.retentionWinners.slice(0, 3).map((w) => (
                  <span
                    key={w.videoId}
                    className="rounded-md bg-zinc-900/90 border border-zinc-800 px-2 py-0.5 text-zinc-200"
                  >
                    {w.title.slice(0, 34)}…{" "}
                    {w.stayedToWatchPct !== null
                      ? `(${w.stayedToWatchPct}% ở lại`
                      : "("}
                    {w.averageViewPercentage !== null
                      ? ` • ${w.averageViewPercentage}% xem)`
                      : ")"}
                  </span>
                ))}
              </div>
            )}

            {/* Winning Titles + Strategy */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4 space-y-2.5">
                <div className="text-xs font-bold text-amber-300 uppercase tracking-wider">
                  1. Chọn 1 trong 4 Tiêu đề US English (Không dính #hashtag rác)
                </div>
                {result.blueprint.winningTitles.map((t, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800/90 bg-zinc-900/80 px-3 py-2 text-xs text-white font-medium"
                  >
                    <span>{t}</span>
                    <button
                      onClick={() => copyText(`title-${i}`, t)}
                      className="shrink-0 text-zinc-400 hover:text-white cursor-pointer"
                      title="Sao chép tiêu đề"
                    >
                      {copiedKey === `title-${i}` ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </button>
                  </div>
                ))}
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4 space-y-3">
                <div>
                  <div className="text-xs font-bold text-emerald-400 flex items-center gap-1.5 mb-1">
                    <Repeat className="h-3.5 w-3.5" />
                    Cơ chế Infinite Loop (&gt;105% Retention)
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {result.blueprint.infiniteLoopBridge}
                  </p>
                </div>
                <div className="pt-2 border-t border-zinc-800/80">
                  <div className="text-xs font-bold text-rose-400 mb-1">
                    🎯 Lý do kịch bản này chuyển đổi Subscribers cao
                  </div>
                  <p className="text-xs text-zinc-300 leading-relaxed">
                    {result.blueprint.whyItConvertsSubs}
                  </p>
                </div>
              </div>
            </div>

            {/* Scene-by-Scene Voiceover & Visual Table */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-5">
              <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                <div className="text-xs font-bold text-white uppercase tracking-wider">
                  2. Kịch bản Phân cảnh & Lời đọc Voiceover chuẩn 42–46 giây
                </div>
                <button
                  onClick={() => copyText("full-vo", fullVoiceoverText)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 hover:bg-red-500 px-3 py-1.5 text-xs font-semibold text-white cursor-pointer"
                >
                  {copiedKey === "full-vo" ? (
                    <>
                      <Check className="h-3.5 w-3.5" />
                      Đã chép toàn bộ Voiceover
                    </>
                  ) : (
                    <>
                      <Copy className="h-3.5 w-3.5" />
                      Chép toàn bộ lời đọc (Đưa vào TTS / Thu âm)
                    </>
                  )}
                </button>
              </div>

              <div className="space-y-3">
                {/* 0-3s Hook */}
                <div className="rounded-xl border border-red-500/40 bg-red-950/20 p-3.5">
                  <div className="text-[11px] font-bold text-red-300 mb-1">
                    ⚡ 00:00 - 00:03 (ANTI-SWIPE HOOK — Quyết định 80% lượt xem!)
                  </div>
                  <p className="text-xs text-zinc-400 mb-1.5">
                    <strong>Hình ảnh:</strong> {result.blueprint.first3sHook.visualPrompt}
                  </p>
                  <p className="text-sm font-semibold text-white">
                    &ldquo;{result.blueprint.first3sHook.voiceover}&rdquo;
                  </p>
                </div>

                {result.blueprint.scenes.map((sc, idx) => (
                  <div
                    key={idx}
                    className="rounded-xl border border-zinc-800 bg-zinc-900/60 p-3.5"
                  >
                    <div className="text-[11px] font-bold text-amber-300 mb-1">
                      🎬 {sc.timestamp}
                    </div>
                    <p className="text-xs text-zinc-400 mb-1.5">
                      <strong>Hình ảnh:</strong> {sc.visualDirection}
                    </p>
                    <p className="text-sm text-zinc-100">
                      &ldquo;{sc.voiceover}&rdquo;
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Pinned Debate Comment + Description */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-emerald-400 flex items-center gap-1.5">
                    <MessageSquarePlus className="h-3.5 w-3.5" />
                    3. Bình luận Ghim (Tăng tranh luận khi video đang Loop!)
                  </span>
                  <button
                    onClick={() =>
                      copyText("pin-cmt", result.blueprint.pinnedDebateComment)
                    }
                    className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                  >
                    {copiedKey === "pin-cmt" ? "Đã chép!" : "Sao chép"}
                  </button>
                </div>
                <p className="text-xs text-zinc-200 bg-zinc-900 rounded-lg p-3 border border-zinc-800 leading-relaxed">
                  {result.blueprint.pinnedDebateComment}
                </p>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-bold text-sky-400">
                    4. Mô tả Chuẩn SEO + Link ?sub_confirmation=1
                  </span>
                  <button
                    onClick={() =>
                      copyText("ready-desc", result.blueprint.readyDescription)
                    }
                    className="inline-flex items-center gap-1 rounded-lg bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-xs text-zinc-200 cursor-pointer"
                  >
                    {copiedKey === "ready-desc" ? "Đã chép!" : "Sao chép"}
                  </button>
                </div>
                <pre className="whitespace-pre-wrap font-sans text-xs text-zinc-300 bg-zinc-900 rounded-lg p-3 border border-zinc-800 leading-relaxed">
                  {result.blueprint.readyDescription}
                </pre>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* SECTION 2: Rescue Station for Existing Videos on the Channel */}
      {channel && rescues.length > 0 && (
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6">
          <div className="mb-5">
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Wrench className="h-5 w-5 text-amber-400" />
              Trạm Tối Ưu Nóng {rescues.length} Video Hiện Tại Trên Kênh {channel.title}
            </h3>
            <p className="text-xs sm:text-sm text-zinc-400 mt-1">
              Sửa ngay các lỗi rò rỉ Subscribers trên những video đã đăng của bạn. Bấm{" "}
              <strong className="text-zinc-200">Chép Tiêu đề sạch</strong> +{" "}
              <strong className="text-zinc-200">Chép Bình luận ghim</strong> rồi mở thẳng trình sửa YouTube Studio chỉ mất 20 giây/video!
            </p>
          </div>

          <div className="space-y-4">
            {rescues.map((r) => (
              <div
                key={r.videoId}
                className="rounded-xl border border-zinc-800/90 bg-zinc-950/60 p-4 space-y-3"
              >
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-sm font-bold text-white">
                        {r.originalTitle}
                      </span>
                      <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[11px] text-zinc-300">
                        {formatNumber(r.views)} views • {r.durationSeconds}s
                      </span>
                    </div>

                    <div className="space-y-1 mt-2">
                      {r.issues.map((iss, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-1.5 text-xs text-amber-300"
                        >
                          <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                          <span>{iss}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {!r.videoId.startsWith("demo-") && (
                    <a
                      href={`https://studio.youtube.com/video/${r.videoId}/edit`}
                      target="_blank"
                      rel="noreferrer"
                      className="shrink-0 inline-flex items-center gap-1.5 rounded-xl bg-red-600/20 border border-red-500/40 hover:bg-red-600 text-red-300 hover:text-white px-3.5 py-2 text-xs font-semibold transition"
                    >
                      Mở YouTube Studio sửa ngay
                      <ExternalLink className="h-3.5 w-3.5" />
                    </a>
                  )}
                </div>

                {/* Quick Copy Action Buttons */}
                <div className="flex flex-wrap gap-2 pt-2 border-t border-zinc-800/70">
                  {r.cleanedTitle !== r.originalTitle && (
                    <button
                      onClick={() =>
                        copyText(`clean-${r.videoId}`, r.cleanedTitle)
                      }
                      className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-300 cursor-pointer"
                    >
                      {copiedKey === `clean-${r.videoId}` ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                      Chép Tiêu đề sạch: &ldquo;{r.cleanedTitle}&rdquo;
                    </button>
                  )}

                  <button
                    onClick={() =>
                      copyText(`pin-${r.videoId}`, r.suggestedPinnedComment)
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 cursor-pointer"
                  >
                    {copiedKey === `pin-${r.videoId}` ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    Chép Bình luận Ghim kéo tương tác
                  </button>

                  <button
                    onClick={() =>
                      copyText(`subblock-${r.videoId}`, r.appendDescriptionBlock)
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-medium text-zinc-200 cursor-pointer"
                  >
                    {copiedKey === `subblock-${r.videoId}` ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                    Chép Khối Mô tả ?sub_confirmation=1
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
