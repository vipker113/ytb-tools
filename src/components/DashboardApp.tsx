"use client";

import {
  BarChart3,
  ChevronDown,
  Film,
  Lightbulb,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Settings,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { INITIAL_DEMO_STORE } from "@/lib/demo-data";
import { formatCompact } from "@/lib/format";
import type { AppSettings, SavedIdea, StoreData } from "@/lib/types";
import { AnalyticsStudioTab } from "./AnalyticsStudioTab";
import { IdeasAndCompetitorsTab } from "./IdeasAndCompetitorsTab";
import { MacStudioReviewTab } from "./MacStudioReviewTab";
import { SettingsTab } from "./SettingsTab";
import { YoutubeIcon } from "./YoutubeIcon";

type ActiveTab = "mac_review" | "analytics" | "ideas" | "settings";

export function DashboardApp() {
  const [store, setStore] = useState<StoreData>(INITIAL_DEMO_STORE);
  const [loaded, setLoaded] = useState(false);
  const [activeTab, setActiveTab] = useState<ActiveTab>("mac_review");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [autopilotRunning, setAutopilotRunning] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [selectedMacReviewSlug] = useState<string | null>(null);
  const [macCounts, setMacCounts] = useState<{
    unposted: number;
    total: number;
  }>({ unposted: 0, total: 0 });
  const [keywordSeedForIdeas, setKeywordSeedForIdeas] = useState<string | null>(
    null
  );
  const [studioSyncRevision, setStudioSyncRevision] = useState(0);

  const autoTriggeredRef = useRef(false);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => {
      setToast((prev) => (prev === msg ? null : prev));
    }, 4200);
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
            showToast(json.error || "Lỗi đồng bộ kênh YouTube");
          }
          return;
        }
        if (json.store) {
          setStore(json.store);
        }
        if (!json.skipped || mode === "force") {
          setStudioSyncRevision((prev) => prev + 1);
        }
        if (!json.skipped && json.message) {
          showToast(json.message);
        } else if (mode === "force") {
          showToast("Đã đồng bộ số liệu & trạng thái YouTube Studio mới nhất!");
        }
      } catch {
        if (mode === "force") {
          showToast("Không thể kết nối đồng bộ.");
        }
      } finally {
        setAutopilotRunning(false);
      }
    },
    [showToast]
  );

  const handleEpisodesCountChange = useCallback(
    (unposted: number, total: number) => {
      setMacCounts((prev) =>
        prev.unposted === unposted && prev.total === total
          ? prev
          : { unposted, total }
      );
    },
    []
  );

  const lastStateRefreshRef = useRef<number>(0);
  const refreshStoreQuietly = useCallback(async () => {
    const now = Date.now();
    if (now - lastStateRefreshRef.current < 3500) return;
    lastStateRefreshRef.current = now;
    try {
      const res = await fetch("/api/state", { cache: "no-store" });
      if (!res.ok) return;
      const data: StoreData = await res.json();
      if (data && Array.isArray(data.myChannels)) {
        setStore(data);
      }
    } catch {
      // Ignore transient focus fetch errors
    }
  }, []);

  useEffect(() => {
    lastStateRefreshRef.current = Date.now();
    fetch("/api/state", { cache: "no-store" })
      .then((r) => r.json())
      .then((data: StoreData) => {
        if (data && Array.isArray(data.myChannels)) {
          setStore(data);

          if (typeof window !== "undefined") {
            const params = new URLSearchParams(window.location.search);
            const oauthStatus = params.get("oauth");
            if (oauthStatus === "connected") {
              showToast(
                "🔐 Đã kết nối quyền quản trị YouTube Studio & Shorts Analytics thành công!"
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

  useEffect(() => {
    const onFocus = () => {
      void refreshStoreQuietly();
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        void refreshStoreQuietly();
      }
    };
    window.addEventListener("focus", onFocus);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("focus", onFocus);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refreshStoreQuietly]);

  useEffect(() => {
    if (loaded && activeTab === "ideas") {
      void refreshStoreQuietly();
    }
  }, [activeTab, loaded, refreshStoreQuietly]);

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

  const realBacklogCount =
    activeChannel && !activeChannel.isDemo
      ? store.ideas.filter(
          (i) =>
            !["idea-1", "idea-2", "idea-3", "idea-4", "idea-5"].includes(i.id)
        ).length
      : store.ideas.length;

  const navItems: Array<{
    id: ActiveTab;
    label: string;
    subtitle: string;
    badge?: string | number;
    icon: React.ComponentType<{ className?: string }>;
  }> = [
    {
      id: "mac_review",
      label: "Phòng Duyệt & Đăng",
      subtitle: "Review 9:16, AI SEO Diff & Đăng",
      badge:
        macCounts.unposted > 0
          ? `${macCounts.unposted} mới`
          : macCounts.total > 0
          ? macCounts.total
          : undefined,
      icon: Film,
    },
    {
      id: "analytics",
      label: "Phân Tích & Shorts",
      subtitle: "% Không vuốt bỏ, APV & Kéo Sub",
      badge: activeChannel
        ? `${formatCompact(activeChannel.subscribers)} sub`
        : undefined,
      icon: BarChart3,
    },
    {
      id: "ideas",
      label: "Ý Tưởng & Đối Thủ",
      subtitle: "AI Chủ đề, Outlier & Từ khóa Mỹ",
      badge:
        realBacklogCount > 0
          ? `${realBacklogCount} backlog`
          : totalOutliersCount > 0
          ? totalOutliersCount
          : undefined,
      icon: Lightbulb,
    },
    {
      id: "settings",
      label: "Cài Đặt & API",
      subtitle: "OAuth Studio, Analytics & Gemini",
      badge: store.youtubeOAuth?.refreshToken
        ? "OAuth"
        : store.settings.youtubeApiKey
        ? "Live"
        : "Setup",
      icon: Settings,
    },
  ];

  const cleanHandle = activeChannel?.handle?.startsWith("@")
    ? activeChannel.handle
    : activeChannel
    ? `@${activeChannel.handle}`
    : "";
  const smartClicks = cleanHandle ? store.smartLinkClicks[cleanHandle] || 0 : 0;

  const rawModel = store.settings.geminiModel || "gemini-3.6-flash";
  const displayModel = rawModel.startsWith("gemini-2.5")
    ? "gemini-3.6-flash"
    : rawModel;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      {/* Desktop Collapsible Sidebar (Optimized for Split-Screen Mac alongside Antigravity) */}
      <aside
        className={`hidden lg:flex shrink-0 flex-col justify-between border-r border-zinc-800/90 bg-zinc-950/95 sticky top-0 h-screen transition-all duration-200 ${
          sidebarCollapsed ? "w-[74px] p-3" : "w-64 p-4"
        }`}
      >
        <div className="space-y-5">
          {/* Brand Logo + Collapse Toggle */}
          <div className="flex items-center justify-between gap-2 px-1">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-red-600 to-rose-500 text-white shadow-lg shadow-red-600/25">
                <YoutubeIcon className="h-4 w-4" />
              </div>
              {!sidebarCollapsed && (
                <div className="min-w-0">
                  <div className="text-sm font-extrabold tracking-tight text-white truncate">
                    Proof Studio Pro
                  </div>
                  <div className="text-[10px] text-zinc-400 truncate">
                    Antigravity × YouTube 0₫
                  </div>
                </div>
              )}
            </div>

            <button
              type="button"
              onClick={() => setSidebarCollapsed((v) => !v)}
              title={
                sidebarCollapsed
                  ? "Mở rộng thanh điều hướng"
                  : "Thu gọn để chia đôi màn hình với Antigravity"
              }
              className="rounded-lg p-1.5 text-zinc-400 hover:bg-zinc-900 hover:text-white cursor-pointer shrink-0"
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="h-4 w-4" />
              ) : (
                <PanelLeftClose className="h-4 w-4" />
              )}
            </button>
          </div>

          {/* Channel Quick Switcher */}
          {!sidebarCollapsed && store.myChannels.length > 0 && (
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/80 p-2.5">
              <label className="block text-[10px] uppercase tracking-wider text-zinc-500 font-semibold mb-1">
                Kênh vận hành
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
                  className="w-full appearance-none rounded-lg border border-zinc-700/80 bg-zinc-950 pl-2.5 pr-7 py-1.5 text-xs font-semibold text-white focus:border-red-500 focus:outline-none cursor-pointer"
                >
                  {store.myChannels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      {ch.title} ({formatCompact(ch.subscribers)} subs)
                    </option>
                  ))}
                </select>
                <ChevronDown className="h-3.5 w-3.5 text-zinc-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          )}

          {/* 4-Tab Pro Studio Navigation */}
          <nav className="space-y-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  title={
                    sidebarCollapsed
                      ? `${item.label} — ${item.subtitle}`
                      : undefined
                  }
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center ${
                    sidebarCollapsed ? "justify-center px-2 py-3" : "justify-between px-3 py-2.5"
                  } rounded-xl text-left transition cursor-pointer ${
                    isActive
                      ? "bg-red-600 text-white shadow-md shadow-red-600/20"
                      : "text-zinc-400 hover:bg-zinc-900 hover:text-zinc-100"
                  }`}
                >
                  <span className="flex items-center gap-2.5 min-w-0">
                    <Icon className="h-4 w-4 shrink-0" />
                    {!sidebarCollapsed && (
                      <span className="min-w-0">
                        <span className="block text-xs font-extrabold truncate">
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
                    )}
                  </span>
                  {!sidebarCollapsed && item.badge !== undefined && (
                    <span
                      className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                        isActive
                          ? "bg-white/20 text-white"
                          : item.badge === "OAuth" || item.badge === "Live"
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
        {!sidebarCollapsed && (
          <div className="rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-3 text-[11px] text-zinc-400 leading-relaxed space-y-1">
            <div className="font-semibold text-zinc-200 flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              Đồng bộ trực tiếp ổ cứng Mac
            </div>
            <p className="text-[10px] text-zinc-400">
              Video tạo từ Antigravity tự hiện ngay ở Phòng Duyệt kèm chấm SEO & AI Diff.
            </p>
          </div>
        )}
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
                  <span className="font-bold text-white">Proof Studio Pro</span>
                </div>
                <button
                  type="button"
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
                      type="button"
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
        <header className="sticky top-0 z-30 border-b border-zinc-800/80 bg-zinc-950/85 backdrop-blur-md px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden rounded-lg border border-zinc-800 p-2 text-zinc-300"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div>
              <h1 className="text-sm sm:text-base font-extrabold text-white">
                {navItems.find((n) => n.id === activeTab)?.label}
              </h1>
              <p className="text-[11px] text-zinc-400 hidden sm:block">
                {autopilotRunning
                  ? "Đang đồng bộ số liệu kênh YouTube..."
                  : store.settings.youtubeApiKey
                  ? `${activeChannel?.title || "Proof of Wonder"} (${cleanHandle}) • AI: ${displayModel}`
                  : "Chưa cấu hình API Key — Hãy mở tab Cài Đặt & API"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="hidden md:inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-950/20 px-3 py-1.5 text-[11px] font-bold text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400" />
              0₫ API Chính Thống
            </span>

            <button
              type="button"
              onClick={() => {
                if (
                  !store.settings.youtubeApiKey &&
                  !store.youtubeOAuth?.refreshToken
                ) {
                  setActiveTab("settings");
                  showToast(
                    "Hãy nhập YouTube Data API v3 Key hoặc kết nối OAuth Studio!"
                  );
                  return;
                }
                void runAutopilot("force");
              }}
              disabled={autopilotRunning}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-200 transition cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${
                  autopilotRunning
                    ? "animate-spin text-amber-400"
                    : "text-emerald-400"
                }`}
              />
              <span>
                {autopilotRunning ? "Đang đồng bộ..." : "Đồng bộ Kênh"}
              </span>
            </button>
          </div>
        </header>

        {/* Toast Notification */}
        {toast && (
          <div className="fixed bottom-5 right-5 z-50 rounded-xl border border-emerald-500/40 bg-zinc-900/95 px-4 py-3 text-xs font-semibold text-emerald-300 shadow-2xl backdrop-blur-md max-w-md">
            ✨ {toast}
          </div>
        )}

        {/* Body Content */}
        <main className="flex-1 p-4 sm:p-6 max-w-[1440px] w-full mx-auto">
          {!loaded ? (
            <div className="py-20 text-center text-sm text-zinc-500">
              Đang tải Bàn Điều Khiển Creator Studio...
            </div>
          ) : (
            <>
              {/* TAB #1 (DEFAULT HOME): MAC VIDEO REVIEW, AI SEO DIFF & PUBLISH */}
              {activeTab === "mac_review" && (
                <MacStudioReviewTab
                  channel={activeChannel}
                  plan={store.activePlan}
                  youtubeOAuth={store.youtubeOAuth}
                  initialSelectedSlug={selectedMacReviewSlug}
                  syncRevision={studioSyncRevision}
                  onStoreSync={(nextStore) => setStore(nextStore)}
                  onEpisodesCountChange={handleEpisodesCountChange}
                  onUploadMacEpisode={async (params) => {
                    const fd = new FormData();
                    fd.append("localEpisodeSlug", params.localEpisodeSlug);
                    fd.append("thumbnailVariant", params.thumbnailVariant);
                    fd.append("advanceSprint", String(params.advanceSprint));
                    fd.append("publishMode", params.publishMode);
                    if (params.customPublishAtIso) {
                      fd.append("customPublishAtIso", params.customPublishAtIso);
                    }
                    if (params.playlistId) {
                      fd.append("playlistId", params.playlistId);
                    }
                    fd.append(
                      "hasPaidProductPlacement",
                      String(params.hasPaidProductPlacement)
                    );
                    fd.append(
                      "selfDeclaredMadeForKids",
                      String(params.selfDeclaredMadeForKids)
                    );
                    fd.append(
                      "containsSyntheticMedia",
                      String(params.containsSyntheticMedia)
                    );
                    fd.append(
                      "embedShortsCoverFrame",
                      String(params.embedShortsCoverFrame)
                    );
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
                    if (!res.ok) {
                      showToast(json.error || "Lỗi upload video lên YouTube");
                      throw new Error(json.error || "Upload failed");
                    }
                    setStore(json.store);
                    showToast(json.message);
                  }}
                  onPromoteOrUpdateMacDraft={async (params) => {
                    const res = await fetch("/api/youtube/studio", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "promoteOrUpdateMacVideo",
                        ...params,
                      }),
                    });
                    const json = await res.json();
                    if (!res.ok) {
                      showToast(
                        json.error || "Lỗi cập nhật video trên YouTube Studio"
                      );
                      setStudioSyncRevision((prev) => prev + 1);
                      throw new Error(json.error || "Studio update failed");
                    }
                    setStore(json.store);
                    showToast(json.message);
                  }}
                  onExploreKeyword={(kw) => {
                    setKeywordSeedForIdeas(kw);
                    setActiveTab("ideas");
                  }}
                  onNotify={showToast}
                />
              )}

              {/* TAB #2: CHANNEL & REAL SHORTS ANALYTICS + LIVE STUDIO AI SEO RESCUE */}
              {activeTab === "analytics" && (
                <AnalyticsStudioTab
                  channel={activeChannel}
                  youtubeOAuth={store.youtubeOAuth}
                  smartClicks={smartClicks}
                  onUpdateMilestone={async (channelId, targetMilestone) => {
                    await postStateAction({
                      action: "updateMilestone",
                      channelId,
                      targetMilestone,
                    });
                    showToast("Đã cập nhật cột mốc Subscribers mục tiêu!");
                  }}
                  onApplyLiveStudioMetadata={async (params) => {
                    const res = await fetch("/api/youtube/studio", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({
                        action: "applyEpisodeMetadata",
                        ...params,
                      }),
                    });
                    const json = await res.json();
                    if (!res.ok) {
                      showToast(
                        json.error || "Lỗi cập nhật video trên YouTube Studio"
                      );
                      throw new Error(json.error || "Studio update failed");
                    }
                    setStore(json.store);
                    showToast(json.message);
                  }}
                  onRescueAllOldVideos={async () => {
                    const res = await fetch("/api/youtube/studio", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      body: JSON.stringify({ action: "rescueAllOldVideos" }),
                    });
                    const json = await res.json();
                    if (!res.ok) {
                      showToast(
                        json.error || "Lỗi cập nhật hàng loạt trên Studio"
                      );
                      return;
                    }
                    setStore(json.store);
                    showToast(json.message);
                  }}
                  onGoToSettings={() => setActiveTab("settings")}
                  onNotify={showToast}
                />
              )}

              {/* TAB #3: AI TOPIC SUGGESTIONS + OUTLIER HUNTER + US KEYWORD EXPLORER */}
              {activeTab === "ideas" && (
                <IdeasAndCompetitorsTab
                  channel={activeChannel}
                  competitors={store.competitors}
                  ideas={store.ideas}
                  hasYoutubeKey={Boolean(store.settings.youtubeApiKey)}
                  initialKeywordQuery={keywordSeedForIdeas}
                  onConsumeInitialKeyword={() => setKeywordSeedForIdeas(null)}
                  onAddIdea={async (idea: Partial<SavedIdea>) => {
                    await postStateAction({ action: "addIdea", idea });
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
                    showToast("Đã xóa ý tưởng khỏi Backlog.");
                  }}
                  onAddCompetitor={(query, niche) =>
                    handleAddChannelOrCompetitor("competitor", query, niche)
                  }
                  onRemoveCompetitor={async (competitorId) => {
                    await postStateAction({
                      action: "removeCompetitor",
                      competitorId,
                    });
                    showToast("Đã gỡ kênh đối thủ.");
                  }}
                  onGoToSettings={() => setActiveTab("settings")}
                  defaultGeminiModel={displayModel}
                  onNotify={showToast}
                />
              )}

              {/* TAB #4: SETTINGS, OAUTH 2.0 & API CONNECTIONS */}
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
