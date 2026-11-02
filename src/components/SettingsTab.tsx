"use client";

import {
  Check,
  CheckCircle2,
  Copy,
  ExternalLink,
  KeyRound,
  Plus,
  RefreshCw,
  ShieldCheck,
  Terminal,
  Trash2,
} from "lucide-react";
import { YoutubeIcon } from "./YoutubeIcon";
import { useState } from "react";
import { formatNumber } from "@/lib/format";
import type {
  AppSettings,
  TrackedChannel,
  YoutubeOAuthState,
} from "@/lib/types";

interface SettingsTabProps {
  myChannels: TrackedChannel[];
  activeChannelId: string;
  settings: AppSettings;
  youtubeOAuth?: YoutubeOAuthState | null;
  onSelectChannel: (channelId: string) => Promise<void>;
  onAddMyChannel: (query: string, niche: string) => Promise<void>;
  onRemoveMyChannel: (channelId: string) => Promise<void>;
  onSaveSettings: (newSettings: Partial<AppSettings>) => Promise<void>;
  onDisconnectOAuth: () => Promise<void>;
  onClearDemoData: () => Promise<void>;
  onResetDemoData: () => Promise<void>;
}

export function SettingsTab({
  myChannels,
  activeChannelId,
  settings,
  youtubeOAuth,
  onSelectChannel,
  onAddMyChannel,
  onRemoveMyChannel,
  onSaveSettings,
  onDisconnectOAuth,
  onClearDemoData,
  onResetDemoData,
}: SettingsTabProps) {
  const [ytKey, setYtKey] = useState(settings.youtubeApiKey || "");
  const [geminiKey, setGeminiKey] = useState(settings.geminiApiKey || "");
  const [geminiModel, setGeminiModel] = useState(() => {
    const m = settings.geminiModel || "";
    if (!m || m.startsWith("gemini-2.5")) return "gemini-3.6-flash";
    return m;
  });
  const [clientId, setClientId] = useState(settings.googleClientId || "");
  const [clientSecret, setClientSecret] = useState(
    settings.googleClientSecret || ""
  );
  const [countryCode, setCountryCode] = useState(
    settings.defaultCountryCode || "VN"
  );

  const [testingKey, setTestingKey] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [statusFeedback, setStatusFeedback] = useState<{
    ok: boolean;
    message: string;
  } | null>(null);

  const [channelQuery, setChannelQuery] = useState("");
  const [channelNiche, setChannelNiche] = useState("");
  const [addingChannel, setAddingChannel] = useState(false);
  const [channelError, setChannelError] = useState<string | null>(null);
  const [copiedCmd, setCopiedCmd] = useState<string | null>(null);

  const copyCommand = (id: string, cmd: string) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(id);
    setTimeout(() => {
      setCopiedCmd((prev) => (prev === id ? null : prev));
    }, 2000);
  };

  const handleTestKey = async () => {
    setTestingKey(true);
    setStatusFeedback(null);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "testYoutubeKey",
          youtubeApiKey: ytKey,
        }),
      });
      const json = await res.json();
      setStatusFeedback({ ok: Boolean(json.ok), message: json.message });
    } catch {
      setStatusFeedback({
        ok: false,
        message: "Lỗi mạng khi kiểm tra khóa API.",
      });
    } finally {
      setTestingKey(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    setStatusFeedback(null);
    try {
      await onSaveSettings({
        youtubeApiKey: ytKey,
        geminiApiKey: geminiKey,
        geminiModel,
        googleClientId: clientId,
        googleClientSecret: clientSecret,
        defaultCountryCode: countryCode,
      });
      setStatusFeedback({
        ok: true,
        message: "Đã lưu khóa API vào cơ sở dữ liệu cục bộ trên máy của bạn!",
      });
    } catch (err) {
      setStatusFeedback({
        ok: false,
        message: err instanceof Error ? err.message : "Không thể lưu cài đặt.",
      });
    } finally {
      setSavingSettings(false);
    }
  };

  const handleAddChannelSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!channelQuery.trim()) return;
    setAddingChannel(true);
    setChannelError(null);
    try {
      await onAddMyChannel(
        channelQuery.trim(),
        channelNiche.trim() || "Sáng tạo nội dung"
      );
      setChannelQuery("");
      setChannelNiche("");
    } catch (err) {
      setChannelError(
        err instanceof Error ? err.message : "Lỗi khi thêm kênh YouTube."
      );
    } finally {
      setAddingChannel(false);
    }
  };

  const hasDemoItems = myChannels.some((c) => c.isDemo);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        {/* Left: API Key Setup & Guide */}
        <div className="xl:col-span-6 space-y-6">
          <form
            onSubmit={handleSave}
            className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 space-y-4"
          >
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-red-500/15 text-red-400">
                <KeyRound className="h-5 w-5" />
              </div>
              <div>
                <h2 className="text-base font-bold text-white">
                  Cấu hình Kết nối API Chính Thống
                </h2>
                <p className="text-xs text-zinc-400">
                  Khóa API chỉ lưu cục bộ trong thư mục `data/` trên máy tính của bạn.
                </p>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                YouTube Data API v3 Key (Miễn phí 10.000 đơn vị/ngày)
              </label>
              <div className="flex gap-2">
                <input
                  type="password"
                  value={ytKey}
                  onChange={(e) => setYtKey(e.target.value)}
                  placeholder="AIzaSy..."
                  className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-white font-mono placeholder:text-zinc-600 focus:border-red-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleTestKey}
                  disabled={testingKey || !ytKey.trim()}
                  className="shrink-0 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 px-3.5 py-2 text-xs font-semibold text-zinc-200 transition cursor-pointer"
                >
                  {testingKey ? "Đang thử..." : "Kiểm tra Key"}
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                Google Gemini API Key (Tùy chọn — Dùng để AI viết Tiêu đề & Mô tả)
              </label>
              <input
                type="password"
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
                placeholder="AIzaSy... (Bỏ trống vẫn dùng được bộ công thức có sẵn)"
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-white font-mono placeholder:text-zinc-600 focus:border-red-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                Mô hình Gemini mặc định (Áp dụng cho AI Kịch bản, SEO & Kế hoạch)
              </label>
              <select
                value={geminiModel}
                onChange={(e) => setGeminiModel(e.target.value)}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-zinc-200 focus:outline-none"
              >
                <option value="gemini-3.6-flash">
                  Gemini 3.6 Flash (Khuyên dùng • Miễn phí 0₫ • Thế hệ mới nhất ~1.5s)
                </option>
                <option value="gemini-3.5-flash">
                  Gemini 3.5 Flash (Miễn phí 0₫ • Siêu tốc ~1.0s)
                </option>
                <option value="gemini-3-flash-preview">
                  Gemini 3 Flash Preview (Miễn phí 0₫ • Ổn định)
                </option>
                <option value="gemini-3.1-pro-preview">
                  Gemini 3.1 Pro (Suy luận sâu • Cần bật Billing trên Google AI Studio)
                </option>
                <option value="gemini-4-argon">
                  Gemini 4 Argon (Flagship • Cần bật Billing trên Google AI Studio)
                </option>
              </select>
              <p className="mt-1.5 text-[11px] text-zinc-400 leading-relaxed">
                💡 Gói <strong className="text-emerald-400">Free Tier (0₫)</strong> của Google AI Studio mở tối đa đến{" "}
                <strong className="text-white">Gemini 3.6 Flash</strong> (các dòng Pro / Argon bị Google giới hạn quota = 0 nếu chưa gắn thẻ Billing; nếu chọn Pro khi dùng key Free, hệ thống sẽ tự động dự phòng mượt sang Gemini 3.6 Flash).
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-zinc-300 mb-1.5">
                Thị trường khán giả mục tiêu (Khi quét từ khóa tìm kiếm)
              </label>
              <select
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value)}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-zinc-200 focus:outline-none"
              >
                <option value="VN">Việt Nam (VN)</option>
                <option value="US">Hoa Kỳ / Quốc tế (US)</option>
                <option value="JP">Nhật Bản (JP)</option>
                <option value="KR">Hàn Quốc (KR)</option>
              </select>
            </div>

            {/* Direct YouTube Studio OAuth 2.0 Credentials */}
            <div className="pt-3 border-t border-zinc-800 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <label className="text-xs font-bold text-amber-300">
                  🔐 Quyền YouTube Studio & Shorts Analytics (OAuth 2.0 • 0₫)
                </label>
                {youtubeOAuth?.refreshToken ? (
                  <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-bold text-emerald-300">
                    Đã kết nối:{" "}
                    {youtubeOAuth.connectedChannelHandle ||
                      youtubeOAuth.connectedChannelTitle ||
                      "OK"}
                  </span>
                ) : (
                  <span className="rounded-full bg-amber-500/20 px-2.5 py-0.5 text-[10px] font-bold text-amber-300">
                    Chờ bấm Cấp quyền
                  </span>
                )}
              </div>

              <input
                type="text"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="Google OAuth Client ID (...apps.googleusercontent.com)"
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2 text-xs text-white font-mono placeholder:text-zinc-600 focus:border-amber-500 focus:outline-none"
              />
              <input
                type="password"
                value={clientSecret}
                onChange={(e) => setClientSecret(e.target.value)}
                placeholder="Google OAuth Client Secret (GOCSPX-...)"
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2 text-xs text-white font-mono placeholder:text-zinc-600 focus:border-amber-500 focus:outline-none"
              />

              <div className="flex flex-wrap items-center gap-2">
                {clientId.trim() && clientSecret.trim() && (
                  <a
                    href="/api/youtube/oauth/start"
                    className="inline-flex items-center gap-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 px-3.5 py-2 text-xs font-extrabold text-zinc-950 transition"
                  >
                    {youtubeOAuth?.refreshToken
                      ? "Đổi tài khoản / Cấp quyền lại"
                      : "Cấp Quyền YouTube Studio Ngay (1-Click)"}
                  </a>
                )}

                {youtubeOAuth?.refreshToken && (
                  <button
                    type="button"
                    onClick={onDisconnectOAuth}
                    className="rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-2 text-xs font-semibold text-zinc-300 cursor-pointer"
                  >
                    Ngắt kết nối
                  </button>
                )}
              </div>
            </div>

            {statusFeedback && (
              <div
                className={`rounded-xl border px-4 py-3 text-xs ${
                  statusFeedback.ok
                    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    : "border-red-500/40 bg-red-500/10 text-red-300"
                }`}
              >
                {statusFeedback.message}
              </div>
            )}

            <button
              type="submit"
              disabled={savingSettings}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 px-4 py-2.5 text-sm font-semibold text-white transition cursor-pointer"
            >
              <ShieldCheck className="h-4 w-4" />
              {savingSettings ? "Đang lưu..." : "Lưu cấu hình API"}
            </button>
          </form>

          {/* 2-Minute Step-by-Step Guide */}
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/50 p-6 space-y-3">
            <h3 className="text-sm font-bold text-white">
              📖 Cách lấy khóa YouTube Data API v3 miễn phí trong 2 phút
            </h3>
            <ol className="list-decimal list-inside space-y-2 text-xs text-zinc-300 leading-relaxed">
              <li>
                Truy cập{" "}
                <a
                  href="https://console.cloud.google.com/apis/library/youtube.googleapis.com"
                  target="_blank"
                  rel="noreferrer"
                  className="text-red-400 hover:underline inline-flex items-center gap-1 font-medium"
                >
                  Google Cloud — YouTube Data API v3
                  <ExternalLink className="h-3 w-3" />
                </a>{" "}
                và bấm nút <strong>Enable (Bật)</strong>.
              </li>
              <li>
                Vào mục <strong>Credentials (Thông tin xác thực)</strong> → bấm{" "}
                <strong>Create Credentials → API Key</strong>.
              </li>
              <li>
                Sao chép chuỗi khóa bắt đầu bằng <code>AIza...</code> dán vào ô phía trên và bấm <strong>Lưu cấu hình API</strong>.
              </li>
              <li>
                Để đọc chỉ số giữ chân Shorts (<code>% Không vuốt bỏ</code> & <code>% APV</code>), mở{" "}
                <a
                  href="https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com"
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-400 hover:underline inline-flex items-center gap-1 font-medium"
                >
                  Google Cloud — YouTube Analytics API (0₫)
                  <ExternalLink className="h-3 w-3" />
                </a>{" "}
                bấm <strong>Enable (Bật)</strong>, sau đó bấm nút <strong>Đổi tài khoản / Cấp quyền lại</strong> ở trên.
              </li>
              <li>
                (Tùy chọn) Lấy khóa Gemini miễn phí tại{" "}
                <a
                  href="https://aistudio.google.com/apikey"
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-400 hover:underline inline-flex items-center gap-1 font-medium"
                >
                  Google AI Studio
                  <ExternalLink className="h-3 w-3" />
                </a>{" "}
                để mở khóa tính năng viết Tiêu đề & Kịch bản bằng AI.
              </li>
            </ol>
            <p className="text-[11px] text-zinc-500 pt-1">
              💡 Tối ưu hóa hạn ngạch: Tool sử dụng <code>playlistItems</code> thay vì <code>search</code> khi quét kênh, chỉ tốn <strong>3 đơn vị / kênh</strong> (bạn có thể quét hơn 3.000 lần mỗi ngày hoàn toàn miễn phí!).
            </p>
          </div>
        </div>

        {/* Right: Manage Personal Channels */}
        <div className="xl:col-span-6 space-y-6">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-6 space-y-5">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-red-500/15 text-red-400">
                  <YoutubeIcon className="h-5 w-5" />
                </div>
                <div>
                  <h2 className="text-base font-bold text-white">
                    Các Kênh YouTube Cá Nhân Của Tôi ({myChannels.length})
                  </h2>
                  <p className="text-xs text-zinc-400">
                    Thêm và chuyển đổi nhanh giữa các kênh bạn đang xây dựng.
                  </p>
                </div>
              </div>

              {hasDemoItems ? (
                <button
                  onClick={onClearDemoData}
                  className="rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition cursor-pointer"
                >
                  Ẩn dữ liệu mẫu Demo
                </button>
              ) : (
                <button
                  onClick={onResetDemoData}
                  className="inline-flex items-center gap-1 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs text-zinc-300 transition cursor-pointer"
                >
                  <RefreshCw className="h-3 w-3" />
                  Nạp lại kênh mẫu
                </button>
              )}
            </div>

            <form
              onSubmit={handleAddChannelSubmit}
              className="grid grid-cols-1 sm:grid-cols-12 gap-2.5"
            >
              <input
                type="text"
                value={channelQuery}
                onChange={(e) => setChannelQuery(e.target.value)}
                placeholder="@handle kênh của bạn hoặc URL..."
                className="sm:col-span-6 rounded-xl border border-zinc-700 bg-zinc-950 px-3.5 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
              />
              <input
                type="text"
                value={channelNiche}
                onChange={(e) => setChannelNiche(e.target.value)}
                placeholder="Ngách (VD: Vlog, AI...)"
                className="sm:col-span-3 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
              />
              <button
                type="submit"
                disabled={addingChannel || !channelQuery.trim()}
                className="sm:col-span-3 inline-flex items-center justify-center gap-1.5 rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-3 py-2.5 text-xs font-semibold text-white transition cursor-pointer"
              >
                <Plus className="h-4 w-4" />
                {addingChannel ? "Đang tải..." : "Thêm kênh"}
              </button>
            </form>

            {channelError && (
              <div className="rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-2.5 text-xs text-red-300">
                {channelError}
              </div>
            )}

            <div className="space-y-3">
              {myChannels.map((ch) => {
                const isSelected = ch.id === activeChannelId;
                return (
                  <div
                    key={ch.id}
                    className={`rounded-xl border p-4 flex items-center justify-between gap-3 transition ${
                      isSelected
                        ? "border-red-500/60 bg-red-950/15"
                        : "border-zinc-800 bg-zinc-950/60"
                    }`}
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <img
                        src={
                          ch.thumbnailUrl ||
                          `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                            ch.title
                          )}`
                        }
                        alt={ch.title}
                        referrerPolicy="no-referrer"
                        onError={(e) => {
                          e.currentTarget.src = `https://api.dicebear.com/9.x/shapes/svg?seed=${encodeURIComponent(
                            ch.title
                          )}`;
                        }}
                        className="h-11 w-11 rounded-xl object-cover shrink-0 bg-zinc-800"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-bold text-white truncate">
                            {ch.title}
                          </p>
                          {ch.isDemo && (
                            <span className="rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">
                              Demo
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-zinc-400">
                          {ch.handle} •{" "}
                          <strong className="text-zinc-200">
                            {formatNumber(ch.subscribers)} subs
                          </strong>{" "}
                          • {ch.videoCount} videos
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {isSelected ? (
                        <span className="inline-flex items-center gap-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 px-2.5 py-1 text-xs font-semibold text-emerald-300">
                          <CheckCircle2 className="h-3.5 w-3.5" />
                          Đang chọn
                        </span>
                      ) : (
                        <button
                          onClick={() => onSelectChannel(ch.id)}
                          className="rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3 py-1.5 text-xs font-medium text-zinc-200 cursor-pointer"
                        >
                          Chọn kênh
                        </button>
                      )}

                      <button
                        onClick={() => onRemoveMyChannel(ch.id)}
                        title="Xóa kênh khỏi danh sách"
                        className="rounded-lg p-1.5 text-zinc-500 hover:text-red-400 transition cursor-pointer"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Ready-to-Connect Mac Video Pipeline API Bridge */}
          <div className="rounded-2xl border border-sky-500/30 bg-sky-950/15 p-6 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400">
                <Terminal className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-sm font-bold text-white">
                  🔌 Cầu Nối Tự Động Hóa Với Tool Tạo Video (Máy Mac / Script)
                </h3>
                <p className="text-xs text-zinc-400">
                  Khi đồng bộ tool tạo video từ Mac sang, chỉ cần gọi 2 API nội bộ này để khép kín 100%:
                </p>
              </div>
            </div>

            <div className="space-y-2.5 text-xs">
              <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-sky-300 mb-0.5">
                    1. Lấy kịch bản & Metadata bài cần làm hôm nay:
                  </div>
                  <code className="text-[11px] text-zinc-300 font-mono break-all">
                    curl -s http://localhost:3000/api/pipeline
                  </code>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    copyCommand(
                      "get-pipe",
                      "curl -s http://localhost:3000/api/pipeline"
                    )
                  }
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-[11px] font-semibold text-zinc-200 cursor-pointer"
                >
                  {copiedCmd === "get-pipe" ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  Chép
                </button>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-emerald-300 mb-0.5">
                    2. Báo đã tạo/đăng xong (Tự chuyển bài & tự lập Sprint mới):
                  </div>
                  <code className="text-[11px] text-zinc-300 font-mono break-all">
                    {`curl -X POST http://localhost:3000/api/pipeline -H "Content-Type: application/json" -d '{"action":"complete"}'`}
                  </code>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    copyCommand(
                      "post-pipe",
                      `curl -X POST http://localhost:3000/api/pipeline -H "Content-Type: application/json" -d '{"action":"complete"}'`
                    )
                  }
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-[11px] font-semibold text-zinc-200 cursor-pointer"
                >
                  {copiedCmd === "post-pipe" ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  Chép
                </button>
              </div>

              <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-3 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-amber-300 mb-0.5">
                    3. (Tự động 100%) Upload file .MP4 thẳng lên YouTube + Hẹn 17:15 VN + Tự chuyển bài:
                  </div>
                  <code className="text-[11px] text-zinc-200 font-mono break-all">
                    {`curl -X POST http://localhost:3000/api/youtube/upload -F "file=@output.mp4" -F "publishMode=schedule_golden"`}
                  </code>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    copyCommand(
                      "upload-pipe",
                      `curl -X POST http://localhost:3000/api/youtube/upload -F "file=@output.mp4" -F "publishMode=schedule_golden"`
                    )
                  }
                  className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-[11px] font-semibold text-zinc-200 cursor-pointer"
                >
                  {copiedCmd === "upload-pipe" ? (
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                  Chép
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
