"use client";

import {
  AlertTriangle,
  Check,
  CheckCircle2,
  Clock,
  Compass,
  Copy,
  ExternalLink,
  Play,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Trash2,
  UserCheck,
  UserMinus,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { formatCompact } from "@/lib/format";
import type {
  CrossSubPartner,
  CrossSubSourcePlatform,
  CrossSubStatus,
  DiscoveredNichePeer,
  RecentPublicSubscriberItem,
  StoreData,
  TrackedChannel,
  YoutubeOAuthState,
} from "@/lib/types";

interface CrossSubTabProps {
  channel: TrackedChannel | undefined;
  partners: CrossSubPartner[];
  lastCrossSubAuditAt?: string;
  youtubeOAuth?: YoutubeOAuthState | null;
  hasYoutubeKey: boolean;
  smartClicks: number;
  onStoreUpdate: (nextStore: StoreData) => void;
  onGoToSettings: () => void;
  onNotify: (msg: string) => void;
}

const NICHE_PRESETS = [
  {
    label: "🌊 Deep Ocean & Abyss",
    query: "deep ocean trench mystery science #shorts",
  },
  {
    label: "🪐 Space & Universe",
    query: "space astronomy universe facts #shorts",
  },
  {
    label: "🌋 Hidden Earth & Geology",
    query: "earth geology volcano phenomenon #shorts",
  },
  {
    label: "🧊 Antarctica Discovery",
    query: "antarctica glacier science discovery #shorts",
  },
  {
    label: "🔬 Strange Physics",
    query: "strange physics science explained #shorts",
  },
  {
    label: "🧬 Microscopic World",
    query: "microscope biology hidden life #shorts",
  },
];

const SUB_RANGE_OPTIONS = [
  { label: "20 – 1.500 subs (Kênh mới dễ trả lễ nhất)", min: 20, max: 1500 },
  { label: "50 – 5.000 subs (Khuyên dùng)", min: 50, max: 5000 },
  { label: "500 – 15.000 subs (Cùng tệp đang lên)", min: 500, max: 15000 },
  { label: "Mọi kênh nhỏ (< 50.000 subs)", min: 10, max: 50000 },
];

type FilterMode =
  | "all"
  | "waiting_their_sub"
  | "need_my_sub"
  | "overdue_24h"
  | "completed"
  | "unsubscribed"
  | "safe_niche"
  | "risky_niche";

function getHoursElapsed(iso?: string): number {
  if (!iso) return 0;
  const diffMs = Date.now() - new Date(iso).getTime();
  return Math.max(0, diffMs / (1000 * 60 * 60));
}

function formatRelativeVi(iso?: string): string {
  if (!iso) return "—";
  const hours = getHoursElapsed(iso);
  if (hours < 1) {
    const mins = Math.max(1, Math.round(hours * 60));
    return `${mins} phút trước`;
  }
  if (hours < 24) {
    return `${Math.round(hours)} giờ trước`;
  }
  const days = Math.floor(hours / 24);
  return `${days} ngày trước`;
}

export function CrossSubTab({
  channel,
  partners,
  lastCrossSubAuditAt,
  youtubeOAuth,
  hasYoutubeKey,
  smartClicks,
  onStoreUpdate,
  onGoToSettings,
  onNotify,
}: CrossSubTabProps) {
  const [subView, setSubView] = useState<"crm" | "niche_finder">("crm");

  // Quick Add CRM state
  const [rawInput, setRawInput] = useState("");
  const [initialStatus, setInitialStatus] =
    useState<CrossSubStatus>("waiting_their_sub");
  const [sourcePlatform, setSourcePlatform] =
    useState<CrossSubSourcePlatform>("facebook_zalo");
  const [subAccountUsed, setSubAccountUsed] = useState("Acc phụ / Clone");
  const [notesInput, setNotesInput] = useState("");
  const [addingPartner, setAddingPartner] = useState(false);

  // Filter & Search CRM
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // OAuth Verification state
  const [auditingOAuth, setAuditingOAuth] = useState(false);
  const [recentPublicSubs, setRecentPublicSubs] = useState<
    RecentPublicSubscriberItem[]
  >([]);
  const [auditBannerText, setAuditBannerText] = useState<string | null>(null);

  // Niche Peer Finder state
  const [nicheKeyword, setNicheKeyword] = useState(NICHE_PRESETS[0].query);
  const [subRangeIdx, setSubRangeIdx] = useState(1);
  const [searchingPeers, setSearchingPeers] = useState(false);
  const [discoveredPeers, setDiscoveredPeers] = useState<DiscoveredNichePeer[]>(
    []
  );
  const [savingPeerId, setSavingPeerId] = useState<string | null>(null);

  // 60-Second Anti-Spam Watch Timer state
  const [watchSession, setWatchSession] = useState<{
    partnerId?: string;
    channelTitle: string;
    targetUrl: string;
    secondsLeft: number;
  } | null>(null);

  useEffect(() => {
    if (!watchSession || watchSession.secondsLeft <= 0) return;
    const timer = setInterval(() => {
      setWatchSession((prev) => {
        if (!prev) return null;
        if (prev.secondsLeft <= 1) {
          return { ...prev, secondsLeft: 0 };
        }
        return { ...prev, secondsLeft: prev.secondsLeft - 1 };
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [watchSession]);

  const cleanHandle = useMemo(() => {
    const raw =
      youtubeOAuth?.connectedChannelHandle ||
      channel?.handle ||
      "@proofofwonderscience";
    return raw.startsWith("@") ? raw : `@${raw}`;
  }, [channel?.handle, youtubeOAuth?.connectedChannelHandle]);

  const directSubUrl = `https://www.youtube.com/${cleanHandle}?sub_confirmation=1`;
  const latestMyShort = useMemo(() => {
    const firstVid = channel?.recentVideos?.[0];
    if (!firstVid?.id || channel?.isDemo) return null;
    return {
      title: firstVid.title,
      url: firstVid.isShort
        ? `https://www.youtube.com/shorts/${firstVid.id}`
        : `https://www.youtube.com/watch?v=${firstVid.id}`,
    };
  }, [channel]);

  const copyText = (key: string, text: string, toastMsg: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedKey(key);
      onNotify(toastMsg);
      setTimeout(() => {
        setCopiedKey((prev) => (prev === key ? null : prev));
      }, 2200);
    });
  };

  // KPI computations
  const stats = useMemo(() => {
    const total = partners.length;
    const completed = partners.filter((p) => p.status === "completed").length;
    const waitingTheir = partners.filter(
      (p) => p.status === "waiting_their_sub"
    ).length;
    const overdue24h = partners.filter(
      (p) =>
        p.status === "waiting_their_sub" &&
        getHoursElapsed(p.iSubscribedAt || p.createdAt) >= 24
    ).length;
    const needMy = partners.filter((p) => p.status === "need_my_sub").length;
    const unsubscribed = partners.filter(
      (p) =>
        p.status === "unsubscribed" ||
        p.publicSubState === "unsubscribed_detected"
    ).length;
    const safeNicheCount = partners.filter(
      (p) => p.nicheSafetyTier === "safe_same_niche"
    ).length;
    const safePct = total > 0 ? Math.round((safeNicheCount / total) * 100) : 100;

    return {
      total,
      completed,
      waitingTheir,
      overdue24h,
      needMy,
      unsubscribed,
      safeNicheCount,
      safePct,
    };
  }, [partners]);

  const filteredPartners = useMemo(() => {
    const q = searchTerm.trim().toLowerCase();
    return partners.filter((p) => {
      if (q) {
        const hay = `${p.title} ${p.handle} ${p.notes}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      switch (filterMode) {
        case "waiting_their_sub":
          return p.status === "waiting_their_sub";
        case "need_my_sub":
          return p.status === "need_my_sub";
        case "overdue_24h":
          return (
            p.status === "waiting_their_sub" &&
            getHoursElapsed(p.iSubscribedAt || p.createdAt) >= 24
          );
        case "completed":
          return p.status === "completed";
        case "unsubscribed":
          return (
            p.status === "unsubscribed" ||
            p.publicSubState === "unsubscribed_detected"
          );
        case "safe_niche":
          return p.nicheSafetyTier === "safe_same_niche";
        case "risky_niche":
          return p.nicheSafetyTier === "risky_off_niche";
        default:
          return true;
      }
    });
  }, [partners, filterMode, searchTerm]);

  const handleAddPartner = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawInput.trim()) return;
    if (!hasYoutubeKey) {
      onGoToSettings();
      onNotify("Hãy nhập YouTube Data API v3 Key trong mục Cài Đặt trước!");
      return;
    }

    setAddingPartner(true);
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "addPartner",
          rawInput: rawInput.trim(),
          initialStatus,
          sourcePlatform,
          subAccountUsed,
          notes: notesInput.trim(),
        }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json.error || "Không thể thêm kênh đối tác.");
      }
      onStoreUpdate(json.store);
      setRawInput("");
      setNotesInput("");
      onNotify(json.message);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi thêm kênh đối tác");
    } finally {
      setAddingPartner(false);
    }
  };

  const handleUpdatePartner = async (
    partnerId: string,
    patch: Partial<CrossSubPartner>
  ) => {
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "updatePartner",
          partnerId,
          patch,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi cập nhật");
      onStoreUpdate(json.store);
      if (json.message) onNotify(json.message);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi cập nhật trạng thái");
    }
  };

  const handleDeletePartner = async (partnerId: string) => {
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "deletePartner",
          partnerId,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi xóa kênh");
      onStoreUpdate(json.store);
      onNotify("Đã xóa kênh đối tác khỏi danh sách.");
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi xóa kênh");
    }
  };

  const handleVerifyOAuth = async () => {
    if (!youtubeOAuth?.refreshToken) {
      onGoToSettings();
      onNotify(
        "Cần kết nối OAuth YouTube Studio ở mục Cài Đặt để đối soát người đăng ký!"
      );
      return;
    }
    setAuditingOAuth(true);
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "verifyOAuthSubs" }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi đối soát OAuth");
      onStoreUpdate(json.store);
      setRecentPublicSubs(json.summary?.recentPublicSubscribers || []);
      setAuditBannerText(json.message);
      onNotify(json.message);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi đối soát OAuth");
    } finally {
      setAuditingOAuth(false);
    }
  };

  const handleDiscoverPeers = async (customQuery?: string) => {
    if (!hasYoutubeKey) {
      onGoToSettings();
      onNotify("Cần YouTube Data API v3 Key để quét kênh cùng ngách!");
      return;
    }
    const q = (customQuery ?? nicheKeyword).trim();
    const range = SUB_RANGE_OPTIONS[subRangeIdx] || SUB_RANGE_OPTIONS[1];
    setSearchingPeers(true);
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "discoverNichePeers",
          keyword: q,
          minSubs: range.min,
          maxSubs: range.max,
          regionCode: "US",
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi tìm kiếm kênh cùng ngách");
      setDiscoveredPeers(json.peers || []);
      onNotify(json.message);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi quét kênh cùng ngách");
    } finally {
      setSearchingPeers(false);
    }
  };

  const handleSaveDiscoveredPeer = async (
    peer: DiscoveredNichePeer,
    statusChoice: CrossSubStatus
  ) => {
    setSavingPeerId(peer.channelId);
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "addDiscoveredPartner",
          peer,
          subAccountUsed,
          initialStatus: statusChoice,
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi lưu kênh");
      onStoreUpdate(json.store);
      setDiscoveredPeers((prev) =>
        prev.map((item) =>
          item.channelId === peer.channelId
            ? { ...item, alreadySaved: true }
            : item
        )
      );
      onNotify(json.message);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi lưu kênh");
    } finally {
      setSavingPeerId(null);
    }
  };

  const handleSaveRecentPublicSub = async (sub: RecentPublicSubscriberItem) => {
    setSavingPeerId(sub.channelId);
    try {
      const res = await fetch("/api/cross-sub", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "addPartner",
          rawInput: sub.channelId,
          initialStatus: "need_my_sub",
          sourcePlatform: "youtube_comment",
          subAccountUsed,
          confirmedPublicSub: true,
          notes: "Đã tự động xác nhận họ Sub công khai qua OAuth",
        }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json.error || "Lỗi lưu người đăng ký");
      onStoreUpdate(json.store);
      setRecentPublicSubs((prev) =>
        prev.map((item) =>
          item.channelId === sub.channelId
            ? { ...item, alreadyInCrm: true }
            : item
        )
      );
      onNotify(`Đã lưu "${sub.title}" vào danh sách chờ bạn trả lễ!`);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi lưu kênh");
    } finally {
      setSavingPeerId(null);
    }
  };

  const start60sWatchBeforeSub = (params: {
    partnerId?: string;
    channelTitle: string;
    videoId?: string;
    handleOrId: string;
  }) => {
    const normHandle = params.handleOrId.startsWith("@")
      ? params.handleOrId
      : params.handleOrId.startsWith("UC")
      ? `channel/${params.handleOrId}`
      : `@${params.handleOrId}`;

    const targetUrl = params.videoId
      ? `https://www.youtube.com/shorts/${params.videoId}`
      : `https://www.youtube.com/${normHandle}?sub_confirmation=1`;

    window.open(targetUrl, "_blank", "noopener,noreferrer");
    setWatchSession({
      partnerId: params.partnerId,
      channelTitle: params.channelTitle,
      targetUrl,
      secondsLeft: 60,
    });
  };

  const vnOutreachTemplate = latestMyShort
    ? `Chào bạn, mình giao lưu Sub chéo bền vững không hủy nhé! Bạn mở xem hết Short này khoảng 60s rồi bấm Like + Đăng ký giúp mình để YouTube không quét spam tụt sub nhé: ${latestMyShort.url} — Xong gửi link video + ảnh chụp mình dùng tài khoản phụ xem đủ 60s trả lễ uy tín ngay lập tức!`
    : `Chào bạn, mình giao lưu Sub chéo uy tín lâu dài nhé! Bạn mở kênh mình xem 1 video Short đủ 60s rồi bấm Đăng ký giúp mình để không bị quét spam nhé: ${directSubUrl} — Gửi link video của bạn mình xem đủ giờ và trả sub ngay!`;

  const usPeerCollabTemplate = `Awesome science Short! Always great discovering fellow small science/documentary creators here. Just watched through and subscribed from a fellow curiosity creator (${cleanHandle}) — excited to see your next upload!`;

  return (
    <div className="space-y-6">
      {/* 60-Second Anti-Spam Watch Countdown Banner */}
      {watchSession && (
        <div
          className={`sticky top-16 z-20 rounded-2xl border p-4 shadow-xl backdrop-blur-md transition ${
            watchSession.secondsLeft === 0
              ? "border-emerald-500/60 bg-emerald-950/90 text-emerald-100"
              : "border-amber-500/50 bg-zinc-900/95 text-zinc-100"
          }`}
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div
                className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl font-extrabold text-sm ${
                  watchSession.secondsLeft === 0
                    ? "bg-emerald-500 text-zinc-950"
                    : "bg-amber-500/20 border border-amber-400/40 text-amber-300"
                }`}
              >
                {watchSession.secondsLeft === 0
                  ? "OK!"
                  : `${watchSession.secondsLeft}s`}
              </div>
              <div>
                <div className="text-xs sm:text-sm font-bold">
                  {watchSession.secondsLeft === 0
                    ? `✅ Đã đủ 60 giây xem kênh "${watchSession.channelTitle}" — Bấm Sub lúc này cực khó bị YouTube quét tụt!`
                    : `⏳ Đang đếm 60 giây xem video của "${watchSession.channelTitle}" trước khi bấm Đăng Ký...`}
                </div>
                <p className="text-[11px] text-zinc-300 mt-0.5">
                  YouTube thường quét & gỡ các lượt Sub bấm ngay lập tức dưới 15 giây. Hãy đợi bộ đếm về 0s rồi bấm Subscribe trên tab YouTube vừa mở.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 shrink-0">
              {watchSession.partnerId && (
                <button
                  type="button"
                  onClick={() => {
                    const target = partners.find(
                      (p) => p.id === watchSession.partnerId
                    );
                    const nextSt: CrossSubStatus =
                      target?.status === "need_my_sub" ||
                      target?.publicSubState === "confirmed_public_sub"
                        ? "completed"
                        : "waiting_their_sub";
                    void handleUpdatePartner(watchSession.partnerId!, {
                      status: nextSt,
                      iSubscribedAt: new Date().toISOString(),
                    });
                    setWatchSession(null);
                  }}
                  className="rounded-xl bg-emerald-500 hover:bg-emerald-400 px-3.5 py-2 text-xs font-extrabold text-zinc-950 transition cursor-pointer"
                >
                  ✓ Đánh dấu Mình Đã Sub
                </button>
              )}
              <button
                type="button"
                onClick={() => setWatchSession(null)}
                className="rounded-xl border border-zinc-700 bg-zinc-800/80 hover:bg-zinc-700 px-3 py-2 text-xs font-semibold text-zinc-300 cursor-pointer"
              >
                Đóng
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Strategic CTR-Protection Guardrail Header */}
      <div className="rounded-2xl border border-amber-500/25 bg-gradient-to-r from-amber-950/25 via-zinc-900/90 to-zinc-900/90 p-4 sm:p-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1.5">
            <div className="inline-flex items-center gap-2 rounded-full bg-amber-500/15 border border-amber-500/30 px-2.5 py-0.5 text-[11px] font-bold text-amber-300">
              <ShieldCheck className="h-3.5 w-3.5" />
              Chế Độ Sub Chéo Giảm Thiểu Hại CTR & Giữ Chân Shorts
            </div>
            <h2 className="text-base sm:text-lg font-extrabold text-white">
              Quản Lý Giao Lưu Sub Chéo & Lọc Kênh Cùng Ngách Science US
            </h2>
            <p className="text-xs text-zinc-400 leading-relaxed max-w-3xl">
              Sub chéo bừa bãi với kênh lệch tệp (Game, Nhạc, Vlog VN) sẽ khiến họ vuốt bỏ video mới của bạn trong 1 giây đầu, kéo tụt{" "}
              <span className="text-zinc-200 font-semibold">Viewed vs. Swiped Away %</span>.
              Để giảm tối đa tác hại CTR: <span className="text-emerald-300 font-semibold">(1) Ưu tiên giao lưu kênh nhỏ cùng ngách Science/Space/Ocean tiếng Anh</span>,{" "}
              <span className="text-emerald-300 font-semibold">(2) Dùng Gmail/Kênh phụ đi trả lễ</span>, và{" "}
              <span className="text-emerald-300 font-semibold">(3) Luôn xem đủ 60s video Short trước khi bấm Sub</span>.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => void handleVerifyOAuth()}
              disabled={auditingOAuth}
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/20 transition cursor-pointer"
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${auditingOAuth ? "animate-spin" : ""}`}
              />
              <span>
                {auditingOAuth
                  ? "Đang quét OAuth..."
                  : "Đối Soát Ai Đã Sub / Hủy Sub (OAuth)"}
              </span>
            </button>
          </div>
        </div>

        {lastCrossSubAuditAt && (
          <div className="mt-3 pt-3 border-t border-zinc-800/80 flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400">
            <span>
              Lần đối soát YouTube OAuth gần nhất:{" "}
              <strong className="text-zinc-200">
                {formatRelativeVi(lastCrossSubAuditAt)}
              </strong>
              {auditBannerText ? ` — ${auditBannerText}` : ""}
            </span>
            <span className="text-zinc-500">
              Lưu ý: YouTube API xác nhận chính xác 100% các kênh bật công khai danh sách Đăng ký; kênh khóa ẩn danh sách sẽ hiển thị trạng thái Ẩn.
            </span>
          </div>
        )}
      </div>

      {/* 5 KPI Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-3.5">
          <div className="flex items-center justify-between text-xs text-zinc-400">
            <span>Tổng kênh giao lưu</span>
            <Users className="h-4 w-4 text-zinc-500" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-white">
            {stats.total}
          </div>
          <div className="mt-1 text-[11px] text-zinc-500">
            {stats.needMy > 0
              ? `${stats.needMy} kênh chờ bạn trả lễ`
              : "Sổ theo dõi tập trung"}
          </div>
        </div>

        <div className="rounded-2xl border border-emerald-500/25 bg-zinc-900/70 p-3.5">
          <div className="flex items-center justify-between text-xs text-emerald-300">
            <span>Hoàn tất 2 chiều</span>
            <UserCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-emerald-300">
            {stats.completed}
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            Đã trao đổi đủ 2 bên
          </div>
        </div>

        <div className="rounded-2xl border border-amber-500/25 bg-zinc-900/70 p-3.5">
          <div className="flex items-center justify-between text-xs text-amber-300">
            <span>Chờ họ trả Sub</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-amber-300">
            {stats.waitingTheir}
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            {stats.overdue24h > 0 ? (
              <span className="text-red-400 font-semibold">
                {stats.overdue24h} kênh quá 24h chưa trả!
              </span>
            ) : (
              "Trong hạn 24h theo dõi"
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-red-500/25 bg-zinc-900/70 p-3.5">
          <div className="flex items-center justify-between text-xs text-red-300">
            <span>Hủy / Tụt Sub</span>
            <UserMinus className="h-4 w-4 text-red-400" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-red-400">
            {stats.unsubscribed}
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            Phát hiện hủy sau khi nhận lễ
          </div>
        </div>

        <div className="rounded-2xl border border-sky-500/25 bg-zinc-900/70 p-3.5 col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-xs text-sky-300">
            <span>Tỷ lệ Cùng Ngách</span>
            <ShieldCheck className="h-4 w-4 text-sky-400" />
          </div>
          <div className="mt-2 text-2xl font-extrabold text-sky-300">
            {stats.safePct}%
          </div>
          <div className="mt-1 text-[11px] text-zinc-400">
            {stats.safeNicheCount}/{stats.total} kênh an toàn CTR
          </div>
        </div>
      </div>

      {/* 1-Click Outreach & Smart Link Copy Bar */}
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="text-xs font-bold text-zinc-200 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-red-400" />
            <span>Bộ Link & Mẫu Tin Nhắn Đi Giao Lưu Nhanh ({cleanHandle})</span>
          </div>
          <span className="text-[11px] text-zinc-400">
            Lượt mở Smart Link của bạn:{" "}
            <strong className="text-emerald-300">{smartClicks}</strong> lượt
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          <button
            type="button"
            onClick={() =>
              copyText(
                "sub_url",
                directSubUrl,
                "Đã chép link 1-Click Subscribe (?sub_confirmation=1)!"
              )
            }
            className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950 hover:border-red-500/50 px-3.5 py-2.5 text-left transition cursor-pointer"
          >
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate">
                Link 1-Click Subscribe
              </div>
              <div className="text-[10px] text-zinc-400 truncate">
                {directSubUrl}
              </div>
            </div>
            {copiedKey === "sub_url" ? (
              <Check className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400 shrink-0" />
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              copyText(
                "latest_short",
                latestMyShort ? latestMyShort.url : directSubUrl,
                latestMyShort
                  ? "Đã chép link Short mới nhất để đối tác xem 60s trước khi Sub!"
                  : "Đã chép link kênh của bạn!"
              )
            }
            className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950 hover:border-emerald-500/50 px-3.5 py-2.5 text-left transition cursor-pointer"
          >
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate">
                Link Short Mới Nhất (Xem 60s)
              </div>
              <div className="text-[10px] text-zinc-400 truncate">
                {latestMyShort
                  ? latestMyShort.title
                  : "Gửi video để chống tụt sub 24h"}
              </div>
            </div>
            {copiedKey === "latest_short" ? (
              <Check className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400 shrink-0" />
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              copyText(
                "vn_msg",
                vnOutreachTemplate,
                "Đã chép mẫu tin nhắn Sub Chéo Group FB/Zalo (nhắc xem đủ 60s)!"
              )
            }
            className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950 hover:border-amber-500/50 px-3.5 py-2.5 text-left transition cursor-pointer"
          >
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate">
                Mẫu Rủ Sub Chéo (FB / Zalo)
              </div>
              <div className="text-[10px] text-zinc-400 truncate">
                Kèm link xem 60s + hẹn trả bằng acc phụ
              </div>
            </div>
            {copiedKey === "vn_msg" ? (
              <Check className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400 shrink-0" />
            )}
          </button>

          <button
            type="button"
            onClick={() =>
              copyText(
                "us_msg",
                usPeerCollabTemplate,
                "Đã chép mẫu giao lưu Tiếng Anh tự nhiên cho kênh Science Mỹ!"
              )
            }
            className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950 hover:border-sky-500/50 px-3.5 py-2.5 text-left transition cursor-pointer"
          >
            <div className="min-w-0">
              <div className="text-xs font-bold text-white truncate">
                Mẫu Giao Lưu Creator Mỹ (EN)
              </div>
              <div className="text-[10px] text-zinc-400 truncate">
                Tự nhiên, không dính từ khóa spam YouTube
              </div>
            </div>
            {copiedKey === "us_msg" ? (
              <Check className="h-4 w-4 text-emerald-400 shrink-0" />
            ) : (
              <Copy className="h-4 w-4 text-zinc-400 shrink-0" />
            )}
          </button>
        </div>
      </div>

      {/* Newly Detected Public Subscribers Drawer (from OAuth scan) */}
      {recentPublicSubs.filter((s) => !s.alreadyInCrm).length > 0 && (
        <div className="rounded-2xl border border-emerald-500/30 bg-emerald-950/15 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-extrabold text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4" />
              <span>
                Phát hiện người đăng ký công khai mới trên kênh của bạn — Bấm 1 chạm nếu cần lưu & trả lễ:
              </span>
            </div>
            <button
              type="button"
              onClick={() => setRecentPublicSubs([])}
              className="text-[11px] text-zinc-400 hover:text-white cursor-pointer"
            >
              Ẩn
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
            {recentPublicSubs
              .filter((s) => !s.alreadyInCrm)
              .slice(0, 6)
              .map((sub) => (
                <div
                  key={sub.channelId}
                  className="flex items-center justify-between gap-2.5 rounded-xl border border-zinc-800 bg-zinc-950/90 p-2.5"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {sub.thumbnailUrl ? (
                      <img
                        src={sub.thumbnailUrl}
                        alt={sub.title}
                        className="h-8 w-8 rounded-full object-cover shrink-0"
                      />
                    ) : (
                      <div className="h-8 w-8 rounded-full bg-zinc-800 shrink-0" />
                    )}
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-white truncate">
                        {sub.title}
                      </div>
                      <div className="text-[10px] text-emerald-400">
                        Đã Sub {formatRelativeVi(sub.subscribedAt)}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    disabled={savingPeerId === sub.channelId}
                    onClick={() => void handleSaveRecentPublicSub(sub)}
                    className="shrink-0 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1.5 text-[11px] font-bold text-white cursor-pointer"
                  >
                    {savingPeerId === sub.channelId ? "..." : "+ Lưu & Trả Lễ"}
                  </button>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Mode Switcher: CRM vs Same-Niche US Peer Finder */}
      <div className="flex flex-wrap items-center gap-2 border-b border-zinc-800 pb-3">
        <button
          type="button"
          onClick={() => setSubView("crm")}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-extrabold transition cursor-pointer ${
            subView === "crm"
              ? "bg-red-600 text-white shadow-md shadow-red-600/20"
              : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
          }`}
        >
          <Users className="h-4 w-4" />
          <span>Sổ Quản Lý & Đối Soát Sub Chéo ({partners.length})</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setSubView("niche_finder");
            if (discoveredPeers.length === 0 && hasYoutubeKey) {
              void handleDiscoverPeers(nicheKeyword);
            }
          }}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-extrabold transition cursor-pointer ${
            subView === "niche_finder"
              ? "bg-sky-600 text-white shadow-md shadow-sky-600/20"
              : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
          }`}
        >
          <Compass className="h-4 w-4" />
          <span>Bộ Lọc Tìm Kênh Nhỏ Cùng Ngách Science US (Bảo Vệ CTR)</span>
        </button>
      </div>

      {/* VIEW 1: CRM & OAUTH VERIFICATION */}
      {subView === "crm" && (
        <div className="space-y-5">
          {/* Quick Add Partner Form */}
          <form
            onSubmit={handleAddPartner}
            className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 space-y-3"
          >
            <div className="text-xs font-extrabold text-white flex items-center gap-2">
              <Plus className="h-4 w-4 text-red-400" />
              <span>
                Thêm Nhanh Kênh Đối Tác (Dán @handle, Link Kênh hoặc Link Video Shorts họ gửi)
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
              <div className="md:col-span-5">
                <input
                  type="text"
                  value={rawInput}
                  onChange={(e) => setRawInput(e.target.value)}
                  placeholder="VD: @tenkenh, https://youtube.com/@... hoặc link Shorts..."
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950 px-3.5 py-2.5 text-xs text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
                />
              </div>

              <div className="md:col-span-3">
                <select
                  value={initialStatus}
                  onChange={(e) =>
                    setInitialStatus(e.target.value as CrossSubStatus)
                  }
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950 px-3 py-2.5 text-xs font-semibold text-zinc-200 focus:border-red-500 focus:outline-none"
                >
                  <option value="waiting_their_sub">
                    ⏳ Mình đã Sub — Chờ họ trả
                  </option>
                  <option value="need_my_sub">
                    📥 Họ đã Sub — Cần mình trả lễ
                  </option>
                  <option value="completed">✅ Đã hoàn tất 2 chiều</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <select
                  value={sourcePlatform}
                  onChange={(e) =>
                    setSourcePlatform(e.target.value as CrossSubSourcePlatform)
                  }
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950 px-3 py-2.5 text-xs text-zinc-200 focus:border-red-500 focus:outline-none"
                >
                  <option value="facebook_zalo">Group FB / Zalo</option>
                  <option value="niche_finder_us">Cùng ngách US</option>
                  <option value="reddit_discord">Reddit / Discord</option>
                  <option value="youtube_comment">Giao lưu Comment</option>
                  <option value="other">Nguồn khác</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <button
                  type="submit"
                  disabled={addingPartner || !rawInput.trim()}
                  className="w-full rounded-xl bg-red-600 hover:bg-red-500 disabled:opacity-50 px-4 py-2.5 text-xs font-extrabold text-white transition cursor-pointer"
                >
                  {addingPartner ? "Đang quét..." : "+ Lưu & Chấm CTR"}
                </button>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-zinc-400 shrink-0">
                  Tài khoản đi Sub:
                </span>
                <input
                  type="text"
                  value={subAccountUsed}
                  onChange={(e) => setSubAccountUsed(e.target.value)}
                  placeholder="VD: Acc phụ Gmail 2 (Khuyên dùng)"
                  className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-[11px] text-zinc-200 focus:border-red-500 focus:outline-none"
                />
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-zinc-400 shrink-0">
                  Ghi chú:
                </span>
                <input
                  type="text"
                  value={notesInput}
                  onChange={(e) => setNotesInput(e.target.value)}
                  placeholder="VD: Nhóm Sub Chéo Uy Tín VN, hẹn trả tối nay..."
                  className="flex-1 rounded-lg border border-zinc-800 bg-zinc-950 px-2.5 py-1.5 text-[11px] text-zinc-200 focus:border-red-500 focus:outline-none"
                />
              </div>
            </div>
          </form>

          {/* Filter Pills & Search */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5">
              {[
                { id: "all", label: `Tất cả (${partners.length})` },
                {
                  id: "waiting_their_sub",
                  label: `Chờ họ trả (${stats.waitingTheir})`,
                },
                {
                  id: "need_my_sub",
                  label: `Cần mình trả (${stats.needMy})`,
                },
                {
                  id: "overdue_24h",
                  label: `Quá hạn >24h (${stats.overdue24h})`,
                },
                {
                  id: "completed",
                  label: `Hoàn tất (${stats.completed})`,
                },
                {
                  id: "unsubscribed",
                  label: `Hủy Sub (${stats.unsubscribed})`,
                },
                {
                  id: "safe_niche",
                  label: `Cùng ngách CTR tốt (${stats.safeNicheCount})`,
                },
              ].map((pill) => (
                <button
                  key={pill.id}
                  type="button"
                  onClick={() => setFilterMode(pill.id as FilterMode)}
                  className={`rounded-lg px-2.5 py-1.5 text-[11px] font-bold transition cursor-pointer ${
                    filterMode === pill.id
                      ? "bg-zinc-100 text-zinc-950"
                      : "bg-zinc-900 text-zinc-400 hover:text-white border border-zinc-800"
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>

            <div className="relative w-full sm:w-60">
              <Search className="h-3.5 w-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Tìm tên kênh, @handle..."
                className="w-full rounded-xl border border-zinc-800 bg-zinc-900 pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-zinc-500 focus:border-red-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Partner List */}
          {filteredPartners.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-900/30 p-10 text-center space-y-3">
              <Users className="h-8 w-8 text-zinc-600 mx-auto" />
              <div className="text-sm font-bold text-zinc-300">
                {partners.length === 0
                  ? "Chưa có kênh đối tác nào trong Sổ Sub Chéo"
                  : "Không có kênh nào khớp với bộ lọc hiện tại"}
              </div>
              <p className="text-xs text-zinc-500 max-w-md mx-auto">
                Dán link kênh hoặc link Shorts của đối tác ở khung bên trên, hoặc chuyển sang tab{" "}
                <button
                  type="button"
                  onClick={() => setSubView("niche_finder")}
                  className="text-sky-400 underline font-semibold cursor-pointer"
                >
                  Bộ Lọc Tìm Kênh Nhỏ Cùng Ngách Science US
                </button>{" "}
                để tìm các kênh cùng tệp người xem ít gây hại CTR nhất.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredPartners.map((p) => {
                const isOverdue =
                  p.status === "waiting_their_sub" &&
                  getHoursElapsed(p.iSubscribedAt || p.createdAt) >= 24;

                const tierStyle =
                  p.nicheSafetyTier === "safe_same_niche"
                    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                    : p.nicheSafetyTier === "neutral_adjacent"
                    ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                    : "border-red-500/30 bg-red-500/10 text-red-300";

                const tierLabel =
                  p.nicheSafetyTier === "safe_same_niche"
                    ? `An toàn CTR (${p.nicheMatchScore}/100)`
                    : p.nicheSafetyTier === "neutral_adjacent"
                    ? `Trung lập (${p.nicheMatchScore}/100)`
                    : `Lệch ngách - Hại CTR (${p.nicheMatchScore}/100)`;

                return (
                  <div
                    key={p.id}
                    className={`rounded-2xl border p-4 transition ${
                      p.status === "unsubscribed" ||
                      p.publicSubState === "unsubscribed_detected"
                        ? "border-red-500/40 bg-red-950/10"
                        : isOverdue
                        ? "border-amber-500/40 bg-amber-950/10"
                        : "border-zinc-800 bg-zinc-900/70"
                    }`}
                  >
                    <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                      {/* Left: Channel Identity & CTR Score */}
                      <div className="flex items-start gap-3.5 min-w-0">
                        {p.thumbnailUrl ? (
                          <img
                            src={p.thumbnailUrl}
                            alt={p.title}
                            className="h-12 w-12 rounded-full object-cover border border-zinc-700 shrink-0"
                          />
                        ) : (
                          <div className="h-12 w-12 rounded-full bg-zinc-800 shrink-0" />
                        )}

                        <div className="min-w-0 space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <a
                              href={`https://www.youtube.com/channel/${p.channelId}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-sm font-extrabold text-white hover:text-red-400 inline-flex items-center gap-1 truncate"
                            >
                              <span>{p.title}</span>
                              <ExternalLink className="h-3 w-3 shrink-0" />
                            </a>
                            <span className="text-[11px] text-zinc-400">
                              {p.handle}
                            </span>
                            <span className="rounded-md bg-zinc-800 px-2 py-0.5 text-[10px] font-bold text-zinc-300">
                              {formatCompact(p.subscribers)} subs •{" "}
                              {p.videoCount} videos
                              {p.country ? ` • ${p.country}` : ""}
                            </span>
                          </div>

                          {/* CTR Safety & OAuth Verification Badges */}
                          <div className="flex flex-wrap items-center gap-2">
                            <span
                              title={p.nicheReasonVi}
                              className={`inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-[10px] font-bold ${tierStyle}`}
                            >
                              {p.nicheSafetyTier === "safe_same_niche" ? (
                                <ShieldCheck className="h-3 w-3" />
                              ) : p.nicheSafetyTier === "risky_off_niche" ? (
                                <ShieldAlert className="h-3 w-3" />
                              ) : (
                                <AlertTriangle className="h-3 w-3" />
                              )}
                              <span>{tierLabel}</span>
                            </span>

                            {p.publicSubState === "confirmed_public_sub" && (
                              <span className="inline-flex items-center gap-1 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-2 py-0.5 text-[10px] font-bold text-emerald-300">
                                <CheckCircle2 className="h-3 w-3" />
                                Xác nhận OAuth: Đã Sub công khai
                              </span>
                            )}

                            {p.publicSubState === "unsubscribed_detected" && (
                              <span className="inline-flex items-center gap-1 rounded-lg border border-red-500/50 bg-red-500/20 px-2 py-0.5 text-[10px] font-bold text-red-300">
                                <UserMinus className="h-3 w-3" />
                                OAuth báo động: Đã Hủy Sub / Khóa ẩn!
                              </span>
                            )}

                            {p.publicSubState === "not_in_public_list" && (
                              <span className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800/80 px-2 py-0.5 text-[10px] text-zinc-400">
                                Ẩn danh sách Sub (Kiểm tra ảnh chụp)
                              </span>
                            )}

                            <span className="text-[10px] text-zinc-500">
                              Acc đi sub:{" "}
                              <strong className="text-zinc-300">
                                {p.subAccountUsed}
                              </strong>
                            </span>

                            {isOverdue && (
                              <span className="rounded-lg bg-red-500/20 border border-red-500/40 px-2 py-0.5 text-[10px] font-bold text-red-300">
                                ⏰ Quá 24h chưa trả ({formatRelativeVi(p.iSubscribedAt || p.createdAt)})
                              </span>
                            )}
                          </div>

                          <p className="text-[11px] text-zinc-400">
                            {p.nicheReasonVi}
                            {p.notes ? ` • Ghi chú: ${p.notes}` : ""}
                          </p>
                        </div>
                      </div>

                      {/* Right: Actions & Status Selector */}
                      <div className="flex flex-wrap items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() =>
                            start60sWatchBeforeSub({
                              partnerId: p.id,
                              channelTitle: p.title,
                              videoId: p.latestVideoId,
                              handleOrId: p.handle || p.channelId,
                            })
                          }
                          className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/15 hover:bg-amber-500/25 px-3 py-2 text-xs font-bold text-amber-200 transition cursor-pointer"
                        >
                          <Play className="h-3.5 w-3.5 fill-current" />
                          <span>Xem 60s & Sub</span>
                        </button>

                        <select
                          value={p.status}
                          onChange={(e) =>
                            void handleUpdatePartner(p.id, {
                              status: e.target.value as CrossSubStatus,
                            })
                          }
                          className={`rounded-xl border px-3 py-2 text-xs font-bold focus:outline-none cursor-pointer ${
                            p.status === "completed"
                              ? "border-emerald-500/40 bg-emerald-950/40 text-emerald-300"
                              : p.status === "waiting_their_sub"
                              ? "border-amber-500/40 bg-amber-950/40 text-amber-300"
                              : p.status === "need_my_sub"
                              ? "border-sky-500/40 bg-sky-950/40 text-sky-300"
                              : "border-red-500/40 bg-red-950/40 text-red-300"
                          }`}
                        >
                          <option value="need_my_sub">
                            📥 Cần mình trả lễ
                          </option>
                          <option value="waiting_their_sub">
                            ⏳ Chờ họ trả Sub
                          </option>
                          <option value="completed">
                            ✅ Đã hoàn tất 2 chiều
                          </option>
                          <option value="unsubscribed">
                            🚨 Họ đã Hủy / Tụt Sub
                          </option>
                        </select>

                        <button
                          type="button"
                          onClick={() => void handleDeletePartner(p.id)}
                          title="Xóa khỏi sổ"
                          className="rounded-xl border border-zinc-800 bg-zinc-950 hover:border-red-500/50 hover:text-red-400 p-2 text-zinc-500 transition cursor-pointer"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* VIEW 2: SAME-NICHE US PEER FINDER */}
      {subView === "niche_finder" && (
        <div className="space-y-5">
          <div className="rounded-2xl border border-sky-500/25 bg-zinc-900/75 p-4 space-y-4">
            <div className="space-y-1">
              <div className="text-xs font-extrabold text-sky-300 flex items-center gap-2">
                <Compass className="h-4 w-4" />
                <span>
                  Tìm Các Kênh Nhỏ Cùng Ngách Science / Documentary Mỹ Để Giao Lưu Tự Nhiên
                </span>
              </div>
              <p className="text-xs text-zinc-400">
                Các kênh dưới 5.000 subscribers làm cùng chủ đề Science, Ocean, Space bằng tiếng Anh có tệp khán giả trùng khớp với{" "}
                <strong className="text-zinc-200">Proof of Wonder</strong>. Giao lưu với nhóm này vừa dễ nhận phản hồi thiện chí, vừa hạn chế tối đa làm hỏng thuật toán đề xuất Shorts.
              </p>
            </div>

            {/* Topic Preset Chips */}
            <div className="flex flex-wrap gap-2">
              {NICHE_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => {
                    setNicheKeyword(preset.query);
                    void handleDiscoverPeers(preset.query);
                  }}
                  className={`rounded-xl border px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                    nicheKeyword === preset.query
                      ? "border-sky-400 bg-sky-500/20 text-sky-200"
                      : "border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                  }`}
                >
                  {preset.label}
                </button>
              ))}
            </div>

            {/* Search Input + Subscriber Size Filter */}
            <div className="grid grid-cols-1 md:grid-cols-12 gap-2.5">
              <div className="md:col-span-6">
                <input
                  type="text"
                  value={nicheKeyword}
                  onChange={(e) => setNicheKeyword(e.target.value)}
                  placeholder="Nhập từ khóa ngách tiếng Anh (VD: bermuda triangle ocean science #shorts)"
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950 px-3.5 py-2.5 text-xs text-white focus:border-sky-500 focus:outline-none"
                />
              </div>

              <div className="md:col-span-4">
                <select
                  value={subRangeIdx}
                  onChange={(e) => setSubRangeIdx(Number(e.target.value))}
                  className="w-full rounded-xl border border-zinc-700/80 bg-zinc-950 px-3 py-2.5 text-xs font-semibold text-zinc-200 focus:border-sky-500 focus:outline-none"
                >
                  {SUB_RANGE_OPTIONS.map((opt, idx) => (
                    <option key={opt.label} value={idx}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="md:col-span-2">
                <button
                  type="button"
                  disabled={searchingPeers}
                  onClick={() => void handleDiscoverPeers(nicheKeyword)}
                  className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 disabled:opacity-50 px-4 py-2.5 text-xs font-extrabold text-white transition cursor-pointer"
                >
                  <Search className="h-3.5 w-3.5" />
                  <span>{searchingPeers ? "Đang tìm..." : "Quét Kênh"}</span>
                </button>
              </div>
            </div>
          </div>

          {searchingPeers ? (
            <div className="py-14 text-center text-xs text-zinc-400">
              Đang quét các kênh nhỏ cùng ngách Science/Shorts tại thị trường Mỹ...
            </div>
          ) : discoveredPeers.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-zinc-800 p-10 text-center text-xs text-zinc-500">
              Bấm chọn một chủ đề phía trên hoặc nhấn &ldquo;Quét Kênh&rdquo; để lọc các kênh nhỏ cùng tệp khán giả.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {discoveredPeers.map((peer) => (
                <div
                  key={peer.channelId}
                  className="rounded-2xl border border-zinc-800 bg-zinc-900/75 p-4 flex flex-col justify-between gap-3.5"
                >
                  <div className="space-y-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3 min-w-0">
                        {peer.thumbnailUrl ? (
                          <img
                            src={peer.thumbnailUrl}
                            alt={peer.title}
                            className="h-11 w-11 rounded-full object-cover border border-zinc-700 shrink-0"
                          />
                        ) : (
                          <div className="h-11 w-11 rounded-full bg-zinc-800 shrink-0" />
                        )}
                        <div className="min-w-0">
                          <a
                            href={`https://www.youtube.com/channel/${peer.channelId}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-extrabold text-white hover:text-sky-400 truncate block"
                          >
                            {peer.title}
                          </a>
                          <div className="text-[11px] text-zinc-400 truncate">
                            {peer.handle} •{" "}
                            <strong className="text-zinc-200">
                              {formatCompact(peer.subscribers)} subs
                            </strong>{" "}
                            • {peer.videoCount} videos
                            {peer.country ? ` • ${peer.country}` : ""}
                          </div>
                        </div>
                      </div>

                      <span
                        className={`shrink-0 rounded-lg border px-2 py-1 text-[10px] font-extrabold ${
                          peer.nicheSafetyTier === "safe_same_niche"
                            ? "border-emerald-500/35 bg-emerald-500/15 text-emerald-300"
                            : "border-amber-500/35 bg-amber-500/15 text-amber-300"
                        }`}
                      >
                        CTR {peer.nicheMatchScore}/100
                      </span>
                    </div>

                    <div className="rounded-xl border border-zinc-800/90 bg-zinc-950/70 p-2.5 text-xs text-zinc-300">
                      <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold block mb-0.5">
                        Short mẫu để vào xem 60s & để lại bình luận kết nối:
                      </span>
                      <a
                        href={`https://www.youtube.com/shorts/${peer.sampleVideoId}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-semibold text-sky-300 hover:underline line-clamp-1"
                      >
                        {peer.sampleVideoTitle}
                      </a>
                    </div>

                    <p className="text-[11px] text-zinc-400">
                      {peer.nicheReasonVi}
                    </p>
                  </div>

                  <div className="flex items-center justify-between gap-2 pt-2 border-t border-zinc-800/80">
                    <button
                      type="button"
                      onClick={() =>
                        start60sWatchBeforeSub({
                          channelTitle: peer.title,
                          videoId: peer.sampleVideoId,
                          handleOrId: peer.handle || peer.channelId,
                        })
                      }
                      className="inline-flex items-center gap-1.5 rounded-xl border border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20 px-3 py-2 text-xs font-bold text-amber-200 transition cursor-pointer"
                    >
                      <Play className="h-3.5 w-3.5 fill-current" />
                      <span>Mở xem 60s</span>
                    </button>

                    {peer.alreadySaved ? (
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-emerald-400 px-3 py-2">
                        <Check className="h-4 w-4" />
                        Đã có trong Sổ
                      </span>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          disabled={savingPeerId === peer.channelId}
                          onClick={() =>
                            void handleSaveDiscoveredPeer(
                              peer,
                              "waiting_their_sub"
                            )
                          }
                          className="rounded-xl bg-sky-600 hover:bg-sky-500 px-3 py-2 text-xs font-extrabold text-white transition cursor-pointer"
                        >
                          {savingPeerId === peer.channelId
                            ? "Đang lưu..."
                            : "+ Lưu (Mình đã Sub)"}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
