"use client";

import {
  ChevronDown,
  Flame,
  Lightbulb,
  Menu,
  RefreshCw,
  Rocket,
  Settings,
  Sparkles,
  Target,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { INITIAL_DEMO_STORE } from "@/lib/demo-data";
import { formatCompact } from "@/lib/format";
import type {
  AppSettings,
  SavedIdea,
  StoreData,
  VideoItem,
} from "@/lib/types";
import { DailyCockpitTab } from "./DailyCockpitTab";
import { GrowthEngineTab } from "./GrowthEngineTab";
import { IdeaBankTab } from "./IdeaBankTab";
import { OutlierHunterTab } from "./OutlierHunterTab";
import { SeoStudioTab } from "./SeoStudioTab";
import { SettingsTab } from "./SettingsTab";
import { YoutubeIcon } from "./YoutubeIcon";

type ActiveTab = "cockpit" | "discover" | "studio" | "settings";

export function DashboardApp() {
  const [store, setStore] = useState<StoreData>(INITIAL_DEMO_STORE);
  const [loaded, setLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("cockpit");
  const [discoverSubTab, setDiscoverSubTab] = useState<"outliers" | "ideas">(
    "outliers"
  );
  const [studioSubTab, setStudioSubTab] = useState<"growth" | "seo">("growth");

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [autopilotRunning, setAutopilotRunning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [videoToAudit, setVideoToAudit] = useState<VideoItem | null>(null);
  const [scriptTopicSeed, setScriptTopicSeed] = useState<{
    topic: string;
    sourceTitle?: string;
  } | null>(null);

  const autoTriggeredRef = useRef(false);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => {
      setToast((prev) => (prev === msg ? null : prev));
    }, 3600);
  }, []);

  const runAutopilot = useCallback(
    async (mode: "autoIfStale" | "force") => {
      setAutopilotRunning(true);
      try {
        const res = await fetch("/api/autopilot", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ mode }),
        });
        const json = await res.json();
        if (!res.ok) {
          if (mode === "force") {
            showToast(json.error || "Lỗi đồng bộ Autopilot");
          }
          return;
        }
        if (json.store) {
          setStore(json.store);
        }
        if (!json.skipped && json.message) {
          showToast(json.message);
        } else if (mode === "force") {
          showToast("Đã đồng bộ dữ liệu mới nhất & kiểm tra lộ trình!");
        }
      } catch {
        if (mode === "force") {
          showToast("Không thể kết nối Autopilot.");
        }
      } finally {
        setAutopilotRunning(false);
      }
    },
    [showToast]
  );

  useEffect(() => {
    fetch("/api/state")
      .then((r) => r.json())
      .then((data: StoreData) => {
        if (data && Array.isArray(data.myChannels)) {
          setStore(data);

          if (typeof window !== "undefined") {
            const params = new URLSearchParams(window.location.search);
            const oauthStatus = params.get("oauth");
            if (oauthStatus === "connected") {
              showToast(
                "🔐 Đã kết nối trực tiếp quyền quản trị YouTube Studio thành công!"
              );
              window.history.replaceState({}, "", "/");
            } else if (oauthStatus === "error") {
              showToast(
                params.get("reason") || "Lỗi xác thực quyền YouTube Studio."
              );
              window.history.replaceState({}, "", "/");
            }
          }

          if (!autoTriggeredRef.current && data.autoSyncOnOpen !== false) {
            autoTriggeredRef.current = true;
            void runAutopilot("autoIfStale");
          }
        }
      })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [runAutopilot, showToast]);

  const postStateAction = async (payload: Record<string, unknown>) => {
    const res = await fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Lỗi cập nhật dữ liệu");
    setStore(json);
    return json as StoreData;
  };

  const handleAddChannelOrCompetitor = async (
    mode: "myChannel" | "competitor",
    query: string,
    niche: string
  ) => {
    const res = await fetch("/api/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode, query, niche }),
    });
    const json = await res.json();
    if (!res.ok) {
      throw new Error(json.error || "Không thể tải kênh YouTube.");
    }
    setStore(json.store);
    showToast(
      mode === "myChannel"
        ? "Đã kết nối kênh YouTube của bạn thành công!"
        : "Đã quét kênh đối thủ & tính điểm Outlier!"
    );
  };

  const handleSaveSettings = async (newSettings: Partial<AppSettings>) => {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(newSettings),
    });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || "Lỗi lưu cài đặt");
    setStore(json.store);
    showToast("Đã lưu cài đặt API thành công!");
  };

  const activeChannel =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];

  const totalOutliersCount = store.competitors.reduce(
    (sum, c) => sum + c.videos.filter((v) => v.outlierScore >= 2).length,
    0
  );

  const planDone =
    store.activePlan?.items.filter((i) => i.status === "completed").length || 0;
  const planTotal = store.activePlan?.items.length || 0;

  const navItems: Array<{
    id: ActiveTab;
    label: string;
    subtitle: string;
    badge?: string | number;
    icon: React.ComponentType<{ className?: string }>;
  }> = [
    {
      id: "cockpit",
      label: "Vận Hành Hằng Ngày",
      subtitle: "Quy trình 2 bước & Tự động hóa",
      badge: store.activePlan ? `${planDone}/${planTotal}` : "Auto",
      icon: Target,
    },
    {
      id: "discover",
      label: "Săn Viral & Ý Tưởng",
      subtitle: "Quét Outlier đối thủ & Kho lưu",
      badge: totalOutliersCount > 0 ? totalOutliersCount : undefined,
      icon: Flame,
    },
    {
      id: "studio",
      label: "Xưởng AI & Chấm SEO",
      subtitle: "Chia cảnh 45s & Từ khóa Mỹ",
      icon: Sparkles,
    },
    {
      id: "settings",
      label: "Kênh, API & Kết Nối Mac",
      subtitle: "Cấu hình khóa & Cầu nối Video",
      badge: store.settings.youtubeApiKey ? "Live" : "Setup",
      icon: Settings,
    },
  ];

  const cleanHandle = activeChannel?.handle?.startsWith("@")
    ? activeChannel.handle
    : activeChannel
    ? `@${activeChannel.handle}`
    : "";
  const smartClicks = cleanHandle ? store.smartLinkClicks[cleanHandle] || 0 : 0;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-72 shrink-0 flex-col justify-between border-r border-zinc-800/90 bg-zinc-950/95 p-5 sticky top-0 h-screen">
        <div className="space-y-6">
          {/* Brand Logo */}
          <div className="flex items-center gap-3 px-1">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-red-600 to-rose-500 text-white shadow-lg shadow-red-600/25">
              <YoutubeIcon className="h-5 w-5" />
            </div>
            <div>
              <div className="text-base font-extrabold tracking-tight text-white">
                SubPulse Autopilot
              </div>
              <div className="text-[11px] text-zinc-400">
                Hệ thống Tăng Subscribers Thật
              </div>
            </div>
          </div>

          {/* Channel Quick Switcher */}
          {store.myChannels.length > 0 && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-3">
              <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-semibold mb-1.5">
                Kênh đang vận hành
              </label>
              <div className="relative">
                <select
                  value={activeChannel?.id || ""}
                  onChange={(e) =>
                    postStateAction({
                      action: "setActiveChannel",
                      channelId: e.target.value,
                    })
                  }
                  className="w-full appearance-none rounded-lg border border-zinc-700/80 bg-zinc-950 pl-3 pr-8 py-2 text-xs font-semibold text-white focus:border-red-500 focus:outline-none cursor-pointer"
                >
                  {store.myChannels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      {ch.title} ({formatCompact(ch.subscribers)} subs)
                    </option>
                  ))}
                </select>
                <ChevronDown className="h-3.5 w-3.5 text-zinc-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          )}

          {/* Streamlined 4-Module Nav */}
          <nav className="space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between rounded-xl px-3.5 py-3 text-left transition cursor-pointer ${
                    isActive
                      ? "bg-red-600 text-white shadow-md shadow-red-600/20"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                  }`}
                >
                  <span className="flex items-center gap-3 min-w-0">
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0">
                      <span className="block text-sm font-bold truncate">
                        {item.label}
                      </span>
                      <span
                        className={`block text-[10px] truncate ${
                          isActive ? "text-red-100" : "text-zinc-500"
                        }`}
                      >
                        {item.subtitle}
                      </span>
                    </span>
                  </span>
                  {item.badge !== undefined && (
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        isActive
                          ? "bg-white/20 text-white"
                          : item.badge === "Live"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : item.badge === "Setup"
                          ? "bg-amber-500/20 text-amber-300"
                          : "bg-zinc-800 text-zinc-300"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Bottom Status Box */}
        <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3.5 text-xs text-zinc-400 leading-relaxed space-y-1">
          <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Vận hành khép kín & An toàn
          </div>
          <p className="text-[11px] text-zinc-400">
            Mở app tự quét kênh, tự gạch bài đã đăng & tự sinh lộ trình 5 ngày mới. Sẵn sàng nối API với tool tạo video trên Mac.
          </p>
        </div>
      </aside>

      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="fixed inset-0 bg-black/70"
            onClick={() => setMobileMenuOpen(false)}
          />
          <div className="relative z-10 w-72 bg-zinc-950 border-r border-zinc-800 p-5 flex flex-col justify-between">
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <YoutubeIcon className="h-6 w-6 text-red-500" />
                  <span className="font-bold text-white">
                    SubPulse Autopilot
                  </span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="text-zinc-400 hover:text-white"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <nav className="space-y-1.5">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = activeTab === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => {
                        setActiveTab(item.id);
                        setMobileMenuOpen(false);
                      }}
                      className={`w-full flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-medium ${
                        isActive
                          ? "bg-red-600 text-white"
                          : "text-zinc-400 hover:bg-zinc-900"
                      }`}
                    >
                      <span className="flex items-center gap-3">
                        <Icon className="h-4 w-4" />
                        <span>{item.label}</span>
                      </span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top Sticky Header */}
        <header className="sticky top-0 z-30 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-md px-4 sm:px-8 py-3.5 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden rounded-lg border border-zinc-800 p-2 text-zinc-300"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-sm sm:text-base font-bold text-white">
                {navItems.find((n) => n.id === activeTab)?.label}
              </h1>
              <p className="text-[11px] text-zinc-400 hidden sm:block">
                {autopilotRunning
                  ? "Autopilot đang đồng bộ số liệu YouTube & cập nhật lộ trình..."
                  : store.settings.youtubeApiKey
                  ? `Kết nối trực tiếp YouTube API v3 • AI mặc định: ${
                      store.settings.geminiModel || "gemini-3.8-flash"
                    }`
                  : "Chưa nhập khóa API — Hãy cấu hình trong mục Kênh & API"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <span className="hidden md:inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-3 py-2 text-xs font-semibold text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Chế độ 0₫ (Chỉ dùng API miễn phí)
            </span>

            <button
              onClick={() => {
                if (!store.settings.youtubeApiKey) {
                  setActiveTab("settings");
                  showToast(
                    "Hãy nhập YouTube Data API v3 Key để đồng bộ dữ liệu thật!"
                  );
                  return;
                }
                void runAutopilot("force");
              }}
              disabled={autopilotRunning}
              className="inline-flex items-center gap-2 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3.5 py-2 text-xs font-semibold text-zinc-200 transition cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  autopilotRunning
                    ? "animate-spin text-amber-400"
                    : "text-emerald-400"
                }`}
              />
              <span>
                {autopilotRunning ? "Đang đồng bộ..." : "Đồng bộ & Cập nhật"}
              </span>
            </button>
          </div>
        </header>

        {/* Toast Notification */}
        {toast && (
          <div className="fixed bottom-5 right-5 z-50 rounded-xl border border-emerald-500/40 bg-zinc-900/95 px-4 py-3 text-xs font-semibold text-emerald-300 shadow-2xl backdrop-blur-md">
            ✨ {toast}
          </div>
        )}

        {/* Body Content */}
        <main className="flex-1 p-4 sm:p-8 max-w-7xl w-full mx-auto">
          {!loaded ? (
            <div className="py-20 text-center text-sm text-zinc-500">
              Đang mở Bàn Vận Hành Tự Động...
            </div>
          ) : (
            <>
              {/* TAB 1: DAILY COCKPIT */}
              {activeTab === "cockpit" && (
                <DailyCockpitTab
                  channel={activeChannel}
                  plan={store.activePlan}
                  autoSyncOnOpen={store.autoSyncOnOpen !== false}
                  lastAutopilotSyncAt={store.lastAutopilotSyncAt}
                  autopilotRunning={autopilotRunning}
                  resolvedVideoIds={store.resolvedVideoIds || []}
                  autopilotLogs={store.autopilotLogs || []}
                  smartClicks={smartClicks}
                  hasOAuthClient={Boolean(
                    store.settings.googleClientId &&
                      store.settings.googleClientSecret
                  )}
                  youtubeOAuth={store.youtubeOAuth}
                  onRunAutopilotForce={() => runAutopilot("force")}
                  onToggleAutoSync={async (enabled) => {
                    await postStateAction({
                      action: "toggleAutoSync",
                      enabled,
                    });
                    showToast(
                      enabled
                        ? "Đã BẬT tự động đồng bộ mỗi khi mở app!"
                        : "Đã tắt tự động đồng bộ khi mở app."
                    );
                  }}
                  onGeneratePlan={async (incrementSprint) => {
                    const res = await fetch("/api/growth/plan", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "generateNext",
                        incrementSprint,
                        fastMode: true,
                      }),
                    });
                    const json = await res.json();
                    if (!res.ok)
                      throw new Error(json.error || "Lỗi lập kế hoạch");
                    setStore(json.store);
                    showToast(json.message || "Đã lập Kế hoạch Sprint mới!");
                  }}
                  onUpdateStepStatus={async (itemId, status) => {
                    const res = await fetch("/api/growth/plan", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "updateStepStatus",
                        itemId,
                        status,
                        fastMode: true,
                      }),
                    });
                    const json = await res.json();
                    if (!res.ok) throw new Error(json.error || "Lỗi cập nhật");
                    setStore(json.store);
                    if (json.autoAdvanced && json.message) {
                      showToast(json.message);
                    } else if (status === "completed") {
                      showToast(
                        "Đã chốt xong bài hôm nay! Bài tiếp theo đã sẵn sàng ở Bước 1."
                      );
                    }
                  }}
                  onSkipPlanItem={async (itemId) => {
                    await postStateAction({
                      action: "skipPlanItem",
                      itemId,
                    });
                    showToast("Đã đẩy bài này xuống cuối & đưa bài kế tiếp lên!");
                  }}
                  onToggleAutoContinue={async (enabled) => {
                    const res = await fetch("/api/growth/plan", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "toggleAutoContinue",
                        enabled,
                      }),
                    });
                    const json = await res.json();
                    if (res.ok) {
                      setStore(json.store);
                      showToast(
                        enabled
                          ? "Đã BẬT tự động lập Sprint tiếp theo khi xong 5/5 bài!"
                          : "Đã tắt tự động chuyển Sprint."
                      );
                    }
                  }}
                  onToggleResolvedVideo={async (videoId) => {
                    await postStateAction({
                      action: "toggleResolvedVideo",
                      videoId,
                    });
                    showToast("Đã cập nhật trạng thái tối ưu video cũ!");
                  }}
                  onRescueSingleStudio={async (videoId) => {
                    try {
                      const res = await fetch("/api/youtube/studio", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({
                          action: "rescueSingle",
                          videoId,
                        }),
                      });
                      const json = await res.json();
                      if (!res.ok)
                        throw new Error(
                          json.error || "Lỗi cập nhật YouTube Studio"
                        );
                      setStore(json.store);
                      showToast(json.message);
                    } catch (err) {
                      showToast(
                        err instanceof Error
                          ? err.message
                          : "Lỗi cập nhật Studio"
                      );
                    }
                  }}
                  onRescueAllStudio={async () => {
                    try {
                      const res = await fetch("/api/youtube/studio", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ action: "rescueAllOldVideos" }),
                      });
                      const json = await res.json();
                      if (!res.ok)
                        throw new Error(
                          json.error || "Lỗi cập nhật hàng loạt trên Studio"
                        );
                      setStore(json.store);
                      showToast(json.message);
                    } catch (err) {
                      showToast(
                        err instanceof Error
                          ? err.message
                          : "Lỗi cập nhật hàng loạt"
                      );
                    }
                  }}
                  onUploadShortDirect={async (params) => {
                    try {
                      const fd = new FormData();
                      fd.append("file", params.file);
                      fd.append("publishMode", params.publishMode);
                      fd.append("episodeId", params.episodeId);
                      fd.append("title", params.title);
                      fd.append("description", params.description);
                      fd.append("tags", params.tags.join(", "));
                      fd.append("pinnedComment", params.pinnedComment);

                      const res = await fetch("/api/youtube/upload", {
                        method: "POST",
                        body: fd,
                      });
                      const json = await res.json();
                      if (!res.ok)
                        throw new Error(
                          json.error || "Lỗi Upload video lên YouTube"
                        );
                      setStore(json.store);
                      showToast(json.message);
                    } catch (err) {
                      showToast(
                        err instanceof Error
                          ? err.message
                          : "Không thể upload video"
                      );
                    }
                  }}
                  onSendToScriptBuilder={(topic, sourceTitle) => {
                    setScriptTopicSeed({ topic, sourceTitle });
                    setStudioSubTab("growth");
                    setActiveTab("studio");
                  }}
                  onUpdateMilestone={async (channelId, targetMilestone) => {
                    await postStateAction({
                      action: "updateMilestone",
                      channelId,
                      targetMilestone,
                    });
                    showToast("Đã cập nhật cột mốc Subscribers mục tiêu!");
                  }}
                  onAuditVideoInSeo={(vid) => {
                    setVideoToAudit(vid);
                    setStudioSubTab("seo");
                    setActiveTab("studio");
                  }}
                  onGoToSettings={() => setActiveTab("settings")}
                />
              )}

              {/* TAB 2: DISCOVER OUTLIERS & IDEA BANK */}
              {activeTab === "discover" && (
                <div className="space-y-6">
                  <div className="inline-flex rounded-xl bg-zinc-900 p-1 border border-zinc-800">
                    <button
                      onClick={() => setDiscoverSubTab("outliers")}
                      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
                        discoverSubTab === "outliers"
                          ? "bg-red-600 text-white shadow"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Flame className="h-3.5 w-3.5" />
                      Quét Video Outlier Đối Thủ ({totalOutliersCount})
                    </button>
                    <button
                      onClick={() => setDiscoverSubTab("ideas")}
                      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
                        discoverSubTab === "ideas"
                          ? "bg-red-600 text-white shadow"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Lightbulb className="h-3.5 w-3.5" />
                      Kho Ý Tưởng & Kịch Bản Lưu ({store.ideas.length})
                    </button>
                  </div>

                  {discoverSubTab === "outliers" ? (
                    <OutlierHunterTab
                      competitors={store.competitors}
                      hasYoutubeKey={Boolean(store.settings.youtubeApiKey)}
                      onAddCompetitor={(query, niche) =>
                        handleAddChannelOrCompetitor("competitor", query, niche)
                      }
                      onRemoveCompetitor={async (competitorId) => {
                        await postStateAction({
                          action: "removeCompetitor",
                          competitorId,
                        });
                        showToast(
                          "Đã gỡ kênh đối thủ khỏi danh sách theo dõi."
                        );
                      }}
                      onSaveIdeaFromVideo={async (idea: Partial<SavedIdea>) => {
                        await postStateAction({ action: "addIdea", idea });
                        showToast("Đã lưu vào Kho Ý Tưởng & Kịch Bản!");
                      }}
                      onAuditCompetitorVideo={(vid) => {
                        setVideoToAudit(vid);
                        setStudioSubTab("seo");
                        setActiveTab("studio");
                      }}
                      onBuildViralScriptFromVideo={(vid) => {
                        setScriptTopicSeed({
                          topic: vid.title.replace(/#\S+/g, "").trim(),
                          sourceTitle: vid.title,
                        });
                        setStudioSubTab("growth");
                        setActiveTab("studio");
                      }}
                      onGoToSettings={() => setActiveTab("settings")}
                    />
                  ) : (
                    <IdeaBankTab
                      ideas={store.ideas}
                      onAddIdea={async (idea) => {
                        await postStateAction({ action: "addIdea", idea });
                        showToast("Đã thêm ý tưởng mới!");
                      }}
                      onUpdateIdea={async (ideaId, patch) => {
                        await postStateAction({
                          action: "updateIdea",
                          ideaId,
                          patch,
                        });
                      }}
                      onDeleteIdea={async (ideaId) => {
                        await postStateAction({ action: "deleteIdea", ideaId });
                        showToast("Đã xóa ý tưởng.");
                      }}
                    />
                  )}
                </div>
              )}

              {/* TAB 3: AI SCENE BUILDER & SEO AUDITOR */}
              {activeTab === "studio" && (
                <div className="space-y-6">
                  <div className="inline-flex rounded-xl bg-zinc-900 p-1 border border-zinc-800">
                    <button
                      onClick={() => setStudioSubTab("growth")}
                      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
                        studioSubTab === "growth"
                          ? "bg-red-600 text-white shadow"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Rocket className="h-3.5 w-3.5" />
                      Xưởng Chia Cảnh 45s (Visual + Loop)
                    </button>
                    <button
                      onClick={() => setStudioSubTab("seo")}
                      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition cursor-pointer ${
                        studioSubTab === "seo"
                          ? "bg-red-600 text-white shadow"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      Chấm Điểm SEO & Từ Khóa Mỏ Vàng
                    </button>
                  </div>

                  {studioSubTab === "growth" ? (
                    <GrowthEngineTab
                      key={scriptTopicSeed?.topic || "default-growth"}
                      channel={activeChannel}
                      initialTopic={scriptTopicSeed}
                      onSaveBlueprintAsIdea={async (idea) => {
                        await postStateAction({ action: "addIdea", idea });
                        showToast("Đã lưu kịch bản AI sang Kho Ý Tưởng!");
                      }}
                    />
                  ) : (
                    <SeoStudioTab
                      key={videoToAudit?.id || "default-seo"}
                      activeChannel={activeChannel}
                      initialVideoToAudit={videoToAudit}
                      onSaveIdea={async (idea) => {
                        await postStateAction({ action: "addIdea", idea });
                        showToast("Đã lưu ý tưởng từ khóa vào Kho Ý Tưởng!");
                      }}
                    />
                  )}
                </div>
              )}

              {/* TAB 4: CHANNELS, API & MAC PIPELINE BRIDGE */}
              {activeTab === "settings" && (
                <SettingsTab
                  myChannels={store.myChannels}
                  activeChannelId={activeChannel?.id || ""}
                  settings={store.settings}
                  youtubeOAuth={store.youtubeOAuth}
                  onSelectChannel={async (channelId) => {
                    await postStateAction({
                      action: "setActiveChannel",
                      channelId,
                    });
                    showToast("Đã chuyển kênh làm việc!");
                  }}
                  onAddMyChannel={(query, niche) =>
                    handleAddChannelOrCompetitor("myChannel", query, niche)
                  }
                  onRemoveMyChannel={async (channelId) => {
                    await postStateAction({
                      action: "removeChannel",
                      channelId,
                    });
                    showToast("Đã gỡ kênh khỏi danh sách.");
                  }}
                  onSaveSettings={handleSaveSettings}
                  onDisconnectOAuth={async () => {
                    const res = await fetch("/api/settings", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "disconnectYoutubeOAuth",
                      }),
                    });
                    const json = await res.json();
                    if (res.ok && json.store) {
                      setStore(json.store);
                      showToast("Đã ngắt kết nối tài khoản YouTube Studio.");
                    }
                  }}
                  onClearDemoData={async () => {
                    await postStateAction({ action: "clearDemoData" });
                    showToast("Đã ẩn toàn bộ dữ liệu mẫu Demo!");
                  }}
                  onResetDemoData={async () => {
                    await postStateAction({ action: "resetDemoData" });
                    showToast("Đã nạp lại dữ liệu mẫu Demo!");
                  }}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
