"use client";

import {
  Activity,
  ArrowRight,
  Check,
  Copy,
  Crown,
  Download,
  ExternalLink,
  Eye,
  Film,
  Flame,
  Image as ImageIcon,
  Link2,
  Loader2,
  Lock,
  Play,
  Plus,
  RefreshCw,
  Rocket,
  Sparkles,
  Trash2,
  Upload,
  Zap,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

interface StagePreset {
  id: string;
  level: number;
  name: string;
  shortName: string;
  mediaUrl: string;
  silhouetteUrl?: string;
  isVideo?: boolean;
  auraHex: string;
  defaultTargetKi: number;
  hasLightning: boolean;
}

interface KiPointWeights {
  view: number;
  like: number;
  comment: number;
  sub: number;
}

interface KiLiveStats {
  views: number;
  likes: number;
  comments: number;
  channelSubs: number;
  gainedSubs: number;
}

interface KiChallengeTrackerItem {
  id: string;
  videoId: string;
  characterName: string;
  episodeNumber: number;
  currentStageId: string;
  currentStageLabel: string;
  nextStageId: string;
  nextStageLabel: string;
  targetKi: number;
  weights: KiPointWeights;
  baselineSubscribers: number;
  manualBonusSubs: number;
  titleTemplate: string;
  goalReachedTitleTemplate: string;
  autoSyncEnabled: boolean;
  syncIntervalMin: number;
  currentKi: number;
  lastSyncedMilestone?: 0 | 25 | 50 | 75 | 100;
  lastStats?: KiLiveStats;
  lastSyncedYoutubeTitle?: string;
  lastCheckedAt?: string;
  lastUpdatedYoutubeAt?: string;
  goalReachedAt?: string | null;
  lastError?: string | null;
  watchUrl: string;
  studioEditUrl: string;
  createdAt: string;
}

interface RenderedKiPackage {
  sessionId: string;
  videoFile: string;
  thumbFile: string;
  sizeMb: number;
  durationSec: number;
  elapsedSec: number;
}

interface KiChallengeStudioTabProps {
  hasYoutubeOAuth: boolean;
  connectedChannelLabel?: string;
  onGoToSettings: () => void;
  onNotify: (msg: string) => void;
}

const DEFAULT_GOKU_STAGES: StagePreset[] = [
  {
    id: "stage_01_kid_goku",
    level: 1,
    name: "Kid Goku (DB Base)",
    shortName: "ST.1 KID GOKU",
    mediaUrl: "/ki-challenge/goku/stage_01_kid_goku.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_01_kid_goku_sil.jpg",
    auraHex: "#38bdf8",
    defaultTargetKi: 5000,
    hasLightning: false,
  },
  {
    id: "stage_02_adult_base",
    level: 2,
    name: "Adult Goku (Base)",
    shortName: "ST.2 BASE FORM",
    mediaUrl: "/ki-challenge/goku/stage_02_adult_base.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_02_adult_base_sil.jpg",
    auraHex: "#38bdf8",
    defaultTargetKi: 10000,
    hasLightning: false,
  },
  {
    id: "stage_03_ssj1",
    level: 3,
    name: "Super Saiyan",
    shortName: "ST.3 SUPER SAIYAN",
    mediaUrl: "/ki-challenge/goku/stage_03_ssj1.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_03_ssj1_sil.jpg",
    auraHex: "#facc15",
    defaultTargetKi: 25000,
    hasLightning: false,
  },
  {
    id: "stage_04_ssj2",
    level: 4,
    name: "Super Saiyan 2",
    shortName: "ST.4 SSJ2",
    mediaUrl: "/ki-challenge/goku/stage_04_ssj2.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_04_ssj2_sil.jpg",
    auraHex: "#fde047",
    defaultTargetKi: 60000,
    hasLightning: true,
  },
  {
    id: "stage_05_ssj3",
    level: 5,
    name: "Super Saiyan 3",
    shortName: "ST.5 SSJ3",
    mediaUrl: "/ki-challenge/goku/stage_05_ssj3.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_05_ssj3_sil.jpg",
    auraHex: "#eab308",
    defaultTargetKi: 150000,
    hasLightning: true,
  },
  {
    id: "stage_06_ssg",
    level: 6,
    name: "Super Saiyan God",
    shortName: "ST.6 SS GOD",
    mediaUrl: "/ki-challenge/goku/stage_06_ssg.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_06_ssg_sil.jpg",
    auraHex: "#ef4444",
    defaultTargetKi: 350000,
    hasLightning: false,
  },
  {
    id: "stage_07_ssb",
    level: 7,
    name: "Super Saiyan Blue",
    shortName: "ST.7 SS BLUE",
    mediaUrl: "/ki-challenge/goku/stage_07_ssb.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_07_ssb_sil.jpg",
    auraHex: "#06b6d4",
    defaultTargetKi: 750000,
    hasLightning: false,
  },
  {
    id: "stage_07b_ssb_kaioken",
    level: 8,
    name: "SSB Kaioken (Bonus)",
    shortName: "SSB KAIOKEN",
    mediaUrl: "/ki-challenge/goku/stage_07b_ssb_kaioken.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_07b_ssb_kaioken_sil.jpg",
    auraHex: "#f43f5e",
    defaultTargetKi: 1200000,
    hasLightning: false,
  },
  {
    id: "stage_08_ui_sign",
    level: 9,
    name: "Ultra Instinct Sign",
    shortName: "ST.8 UI SIGN",
    mediaUrl: "/ki-challenge/goku/stage_08_ui_sign.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_08_ui_sign_sil.jpg",
    auraHex: "#94a3b8",
    defaultTargetKi: 2500000,
    hasLightning: false,
  },
  {
    id: "stage_09_mui",
    level: 10,
    name: "Mastered Ultra Instinct",
    shortName: "ST.9 MASTERED UI",
    mediaUrl: "/ki-challenge/goku/stage_09_mui.jpg",
    silhouetteUrl: "/ki-challenge/goku/stage_09_mui_sil.jpg",
    auraHex: "#e2e8f0",
    defaultTargetKi: 5000000,
    hasLightning: true,
  },
];

// Full-bleed 50/50 split character viewports on the 1920x1080 canvas (zero card clutter!)
const LEFT_VIEWPORT = { x: 0, y: 0, w: 960, h: 1080 };
const RIGHT_VIEWPORT = { x: 960, y: 0, w: 960, h: 1080 };

function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

function drawStrokedText(
  ctx: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  fill: string,
  strokeWidth: number,
  shadowOffsetY = 6
) {
  ctx.save();
  ctx.lineJoin = "round";
  ctx.miterLimit = 2;
  if (shadowOffsetY > 0) {
    ctx.fillStyle = "rgba(0, 0, 0, 0.72)";
    ctx.strokeStyle = "rgba(0, 0, 0, 0.72)";
    ctx.lineWidth = strokeWidth;
    ctx.strokeText(text, x, y + shadowOffsetY);
  }
  ctx.strokeStyle = "#09090b";
  ctx.lineWidth = strokeWidth;
  ctx.strokeText(text, x, y);
  ctx.fillStyle = fill;
  ctx.fillText(text, x, y);
  ctx.restore();
}

function drawChunkyVectorArrow(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale = 1
) {
  // Clean, bold MrBeast/Creator-style solid vector arrow (NO emojis!)
  const pathPoints: [number, number][] = [
    [cx - 128 * scale, cy - 30 * scale],
    [cx + 12 * scale, cy - 30 * scale],
    [cx + 12 * scale, cy - 72 * scale],
    [cx + 132 * scale, cy],
    [cx + 12 * scale, cy + 72 * scale],
    [cx + 12 * scale, cy + 30 * scale],
    [cx - 128 * scale, cy + 30 * scale],
  ];

  const trace = (ox: number, oy: number) => {
    ctx.beginPath();
    pathPoints.forEach(([px, py], i) => {
      if (i === 0) ctx.moveTo(px + ox, py + oy);
      else ctx.lineTo(px + ox, py + oy);
    });
    ctx.closePath();
  };

  ctx.save();
  ctx.lineJoin = "round";

  // Hard offset drop shadow
  trace(0, 10 * scale);
  ctx.fillStyle = "rgba(0, 0, 0, 0.78)";
  ctx.strokeStyle = "rgba(0, 0, 0, 0.78)";
  ctx.lineWidth = 16 * scale;
  ctx.stroke();
  ctx.fill();

  // Crisp black outline + clean gold fill
  trace(0, 0);
  ctx.strokeStyle = "#09090b";
  ctx.lineWidth = 16 * scale;
  ctx.stroke();

  const grad = ctx.createLinearGradient(
    cx - 128 * scale,
    cy - 60 * scale,
    cx + 132 * scale,
    cy + 60 * scale
  );
  grad.addColorStop(0, "#fde047");
  grad.addColorStop(1, "#facc15");
  ctx.fillStyle = grad;
  ctx.fill();
  ctx.restore();
}

function drawVectorPadlock(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  scale = 1
) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.scale(scale, scale);

  // Shackle
  ctx.beginPath();
  ctx.arc(0, -10, 11, Math.PI, 0, false);
  ctx.lineWidth = 5;
  ctx.strokeStyle = "#09090b";
  ctx.stroke();

  // Body
  drawRoundedRect(ctx, -15, -10, 30, 24, 5);
  ctx.fillStyle = "#09090b";
  ctx.fill();

  // Keyhole dot
  ctx.beginPath();
  ctx.arc(0, 2, 3.2, 0, Math.PI * 2);
  ctx.fillStyle = "#facc15";
  ctx.fill();
  ctx.restore();
}

function drawCoverImage(
  ctx: CanvasRenderingContext2D,
  source: HTMLImageElement | HTMLVideoElement,
  dx: number,
  dy: number,
  dw: number,
  dh: number,
  breathScale = 1,
  bobY = 0,
  shiftX = 0
) {
  const sw =
    source instanceof HTMLVideoElement
      ? source.videoWidth || 768
      : source.naturalWidth || 768;
  const sh =
    source instanceof HTMLVideoElement
      ? source.videoHeight || 1024
      : source.naturalHeight || 1024;

  const scale = Math.max(dw / sw, dh / sh) * breathScale;
  const rw = sw * scale;
  const rh = sh * scale;
  const rx = dx + (dw - rw) * 0.5 + shiftX;
  const ry = dy + (dh - rh) * 0.10 + bobY;

  ctx.save();
  ctx.beginPath();
  ctx.rect(dx, dy, dw, dh);
  ctx.clip();
  ctx.drawImage(source, rx, ry, rw, rh);
  ctx.restore();
}

function drawCenterWhiteScoreBoard(
  ctx: CanvasRenderingContext2D,
  cx: number,
  y0: number,
  boardW: number,
  boardH: number,
  rows: {
    kind: "view" | "like" | "comment" | "sub";
    iconColor: string;
    label: string;
    val: string;
    isSub?: boolean;
  }[]
) {
  const x0 = Math.round(cx - boardW / 2);
  const r = 18;

  ctx.save();
  // Clean offset shadow
  drawRoundedRect(ctx, x0, y0 + 8, boardW, boardH, r);
  ctx.fillStyle = "rgba(0, 0, 0, 0.55)";
  ctx.fill();

  // Pure white board (#ffffff) with crisp dark ink border (#09090b)
  drawRoundedRect(ctx, x0, y0, boardW, boardH, r);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.lineWidth = 6;
  ctx.strokeStyle = "#09090b";
  ctx.stroke();

  const rowH = boardH / rows.length;
  const padX = Math.round(boardW * 0.068);
  const labelPx = Math.round(rowH * 0.33);
  const valPx = Math.round(rowH * 0.43);

  rows.forEach((row, idx) => {
    const ry = y0 + idx * rowH;
    const midY = ry + rowH / 2 + 1;

    if (idx > 0) {
      ctx.beginPath();
      ctx.moveTo(x0 + 20, ry);
      ctx.lineTo(x0 + boardW - 20, ry);
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#e4e4e7";
      ctx.stroke();
    }

    // Left: Crisp Colored Icon Badge + Action Label (1 VIEW, 1 LIKE, 1 COMMENT, 1 SUBSCRIBE)
    const iconCx = x0 + padX + 20;
    drawActionVectorIcon(ctx, row.kind, iconCx, midY - 1, row.iconColor);

    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.font = `900 ${labelPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
    ctx.fillStyle = "#18181b";
    ctx.fillText(row.label, x0 + padX + 52, midY);

    // Right: Point Value (+1 KI, +20 KI, +50 KI, +200 KI)
    ctx.textAlign = "right";
    ctx.font = `900 ${valPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
    ctx.fillStyle = row.isSub ? "#dc2626" : "#09090b";
    ctx.fillText(row.val, x0 + boardW - padX, midY);
  });

  ctx.restore();
}

function drawActionVectorIcon(
  ctx: CanvasRenderingContext2D,
  kind: "view" | "like" | "comment" | "sub",
  cx: number,
  cy: number,
  color: string
) {
  ctx.save();
  ctx.translate(cx, cy);
  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3.2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  if (kind === "view") {
    // Crisp vector eye icon
    ctx.beginPath();
    ctx.moveTo(-16, 0);
    ctx.quadraticCurveTo(0, -13, 16, 0);
    ctx.quadraticCurveTo(0, 13, -16, 0);
    ctx.closePath();
    ctx.stroke();
    ctx.beginPath();
    ctx.arc(0, 0, 5.2, 0, Math.PI * 2);
    ctx.fill();
  } else if (kind === "like") {
    // Crisp vector thumbs-up icon
    drawRoundedRect(ctx, -14, -2, 7, 14, 2);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-5, -1);
    ctx.lineTo(-1, -12);
    ctx.quadraticCurveTo(3, -13, 3, -7);
    ctx.lineTo(3, -3);
    ctx.lineTo(12, -3);
    ctx.quadraticCurveTo(15, -3, 14, 1);
    ctx.lineTo(11, 10);
    ctx.quadraticCurveTo(10, 12, 7, 12);
    ctx.lineTo(-5, 12);
    ctx.closePath();
    ctx.fill();
  } else if (kind === "comment") {
    // Crisp vector speech bubble with 2 dots inside
    drawRoundedRect(ctx, -15, -11, 30, 19, 6);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-6, 7);
    ctx.lineTo(-11, 14);
    ctx.lineTo(1, 7);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.beginPath();
    ctx.arc(-5, -1.5, 2.2, 0, Math.PI * 2);
    ctx.arc(5, -1.5, 2.2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    // Crisp YouTube red play badge icon (works on white board!)
    drawRoundedRect(ctx, -16, -11, 32, 22, 6);
    ctx.fillStyle = "#dc2626";
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(-4, -6);
    ctx.lineTo(7, 0);
    ctx.lineTo(-4, 6);
    ctx.closePath();
    ctx.fillStyle = "#ffffff";
    ctx.fill();
  }

  ctx.restore();
}

function formatPreviewTitle(
  template: string,
  vars: {
    ki: number;
    target: number;
    milestone: 0 | 25 | 50 | 75 | 100;
    char: string;
    currentForm: string;
    nextForm: string;
  }
): string {
  const kiNum = Math.max(0, Math.round(vars.ki));
  const targetNum = Math.max(1, Math.round(vars.target));
  const kiFmt = kiNum.toLocaleString("en-US");
  const targetFmt = targetNum.toLocaleString("en-US");
  const pct = Math.min(999, Math.floor((kiNum / targetNum) * 100));
  return template
    .replace(/\{milestone\}/gi, `${vars.milestone}`)
    .replace(/\{ki\}/gi, kiFmt)
    .replace(/\{target\}/gi, targetFmt)
    .replace(/\{kiRaw\}/gi, `${kiNum}`)
    .replace(/\{targetRaw\}/gi, `${targetNum}`)
    .replace(/\{pct\}/gi, `${pct}`)
    .replace(/\{char\}/gi, vars.char)
    .replace(/\{currentForm\}/gi, vars.currentForm)
    .replace(/\{nextForm\}/gi, vars.nextForm)
    .slice(0, 100);
}

export function KiChallengeStudioTab({
  hasYoutubeOAuth,
  connectedChannelLabel,
  onGoToSettings,
  onNotify,
}: KiChallengeStudioTabProps) {
  const [stages, setStages] = useState<StagePreset[]>(DEFAULT_GOKU_STAGES);
  const [characterName, setCharacterName] = useState<string>("Goku");
  const [episodeNumber, setEpisodeNumber] = useState<number>(1);
  const [currentStageId, setCurrentStageId] = useState<string>("stage_02_adult_base");
  const [nextStageId, setNextStageId] = useState<string>("stage_03_ssj1");
  const [targetKi, setTargetKi] = useState<number>(10000);
  const [weights, setWeights] = useState<KiPointWeights>({
    view: 1,
    like: 20,
    comment: 50,
    sub: 200,
  });

  // Visual & Video Idle Options
  const [aspectMode, setAspectMode] = useState<"16:9" | "9:16">("16:9");
  const [languageStyle, setLanguageStyle] = useState<"en" | "vi">("en");
  const [mysteryNext, setMysteryNext] = useState<boolean>(true);
  const [enableLightning, setEnableLightning] = useState<boolean>(false);
  const [durationSec, setDurationSec] = useState<number>(15);
  const [audioMode, setAudioMode] = useState<
    "epic_hum" | "builtin_bgm" | "custom_audio" | "silent"
  >("epic_hum");
  const [bgmTrack, setBgmTrack] = useState<string>("dance_trend_club.m4a");
  const [customAudios, setCustomAudios] = useState<
    { name: string; url: string }[]
  >([]);
  const [selectedCustomAudioUrl, setSelectedCustomAudioUrl] =
    useState<string>("");
  const [uploadingAudio, setUploadingAudio] = useState<boolean>(false);
  const [audioTrimStartSec, setAudioTrimStartSec] = useState<number>(0);
  const [audioTrimEndSec, setAudioTrimEndSec] = useState<number>(15);
  const [audioTotalDurSec, setAudioTotalDurSec] = useState<number>(60);
  const [isPreviewingAudio, setIsPreviewingAudio] = useState<boolean>(false);

  // Dynamic Title Templates (Showing actual KI numbers e.g. 5,000/10,000 KI instead of %!)
  const [titleTemplate, setTitleTemplate] = useState<string>(
    "⚡ [{ki}/{target} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
  );
  const [goalReachedTitleTemplate, setGoalReachedTitleTemplate] = useState<string>(
    "🎉 [{ki}/{target} KI — UNLOCKED!] {char} Transformed Into {nextForm}! ⚡"
  );
  const [customDescription, setCustomDescription] = useState<string>("");
  const [isDescManuallyEdited, setIsDescManuallyEdited] =
    useState<boolean>(false);
  const [customTagsInput, setCustomTagsInput] = useState<string>(
    "goku, super saiyan, dragon ball, ki challenge, power level, anime evolution, interactive video"
  );
  const [customPinnedComment, setCustomPinnedComment] = useState<string>("");
  const [isPinManuallyEdited, setIsPinManuallyEdited] =
    useState<boolean>(false);
  const [privacyStatus, setPrivacyStatus] = useState<"public" | "unlisted" | "private">(
    "public"
  );
  const [syncIntervalMin, setSyncIntervalMin] = useState<number>(5);

  // Render & Publish State
  const [renderingVideo, setRenderingVideo] = useState<boolean>(false);
  const [renderedPkg, setRenderedPkg] = useState<RenderedKiPackage | null>(null);
  const [previewTab, setPreviewTab] = useState<"live_canvas" | "rendered_mp4">(
    "live_canvas"
  );
  const [publishing, setPublishing] = useState<boolean>(false);
  const [uploadingCustomFor, setUploadingCustomFor] = useState<
    "current" | "next" | null
  >(null);

  // Tracker State
  const [trackers, setTrackers] = useState<KiChallengeTrackerItem[]>([]);
  const [attachInput, setAttachInput] = useState<string>("");
  const [attaching, setAttaching] = useState<boolean>(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const liveCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const customFileInputRef = useRef<HTMLInputElement | null>(null);
  const customAudioInputRef = useRef<HTMLInputElement | null>(null);
  const audioPreviewRef = useRef<HTMLAudioElement | null>(null);
  const customUploadTargetRef = useRef<"current" | "next">("current");
  const loadedMediaCacheRef = useRef<
    Map<string, HTMLImageElement | HTMLVideoElement>
  >(new Map());
  const [mediaTick, setMediaTick] = useState<number>(0);

  const currentStage = useMemo(
    () => stages.find((s) => s.id === currentStageId) || stages[0],
    [stages, currentStageId]
  );
  const nextStage = useMemo(
    () => stages.find((s) => s.id === nextStageId) || stages[1] || stages[0],
    [stages, nextStageId]
  );

  // Auto-sync lightning toggle & default target KI when stages change
  useEffect(() => {
    setEnableLightning(Boolean(currentStage.hasLightning));
  }, [currentStage]);

  // Switch preset texts when language toggles
  const handleSwitchLanguage = useCallback((lang: "en" | "vi") => {
    setLanguageStyle(lang);
    setIsDescManuallyEdited(false);
    setIsPinManuallyEdited(false);
    if (lang === "vi") {
      setTitleTemplate(
        "⚡ [{ki}/{target} KI] Tiếp KI Giúp {char} Lên {nextForm}! (Like & Sub = +KI) 🔥"
      );
      setGoalReachedTitleTemplate(
        "🎉 [{ki}/{target} KI — MỞ KHÓA!] {char} Đã Lên {nextForm} — Xem Tập Mới! ⚡"
      );
    } else {
      setTitleTemplate(
        "⚡ [{ki}/{target} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
      );
      setGoalReachedTitleTemplate(
        "🎉 [{ki}/{target} KI — UNLOCKED!] {char} Transformed Into {nextForm}! ⚡"
      );
    }
  }, []);

  // Load trackers + custom uploaded assets on mount & poll trackers every 25s
  const fetchTrackers = useCallback(async () => {
    try {
      const res = await fetch("/api/ki-challenge", { cache: "no-store" });
      const json = await res.json();
      if (res.ok && json.ok) {
        setTrackers(json.items || []);
        if (Array.isArray(json.customAudios) && json.customAudios.length > 0) {
          setCustomAudios(json.customAudios);
          setSelectedCustomAudioUrl(
            (prev) => prev || json.customAudios[0]?.url || ""
          );
        }
        if (Array.isArray(json.customAssets) && json.customAssets.length > 0) {
          setStages((prev) => {
            const existingUrls = new Set(prev.map((p) => p.mediaUrl));
            const extras: StagePreset[] = [];
            json.customAssets.forEach(
              (
                asset: {
                  name: string;
                  url: string;
                  silhouetteUrl?: string;
                  isVideo: boolean;
                },
                idx: number
              ) => {
                if (!existingUrls.has(asset.url)) {
                  extras.push({
                    id: `custom_${asset.name}`,
                    level: prev.length + idx + 1,
                    name: asset.name.replace(/\.[^/.]+$/, "").slice(0, 22),
                    shortName: `CUSTOM`,
                    mediaUrl: asset.url,
                    silhouetteUrl: asset.silhouetteUrl,
                    isVideo: asset.isVideo,
                    auraHex: "#f59e0b",
                    defaultTargetKi: 25000,
                    hasLightning: false,
                  });
                }
              }
            );
            return extras.length > 0 ? [...prev, ...extras] : prev;
          });
        }
      }
    } catch {
      // ignore transient error
    }
  }, []);

  useEffect(() => {
    void fetchTrackers();
    const timer = setInterval(() => {
      void fetchTrackers();
    }, 20_000);
    return () => clearInterval(timer);
  }, [fetchTrackers]);

  // Preload active character images/videos + silhouette images into cache for 60fps Canvas drawing
  useEffect(() => {
    const preloadImage = (url?: string) => {
      if (!url || loadedMediaCacheRef.current.has(url)) return;
      const img = new window.Image();
      img.crossOrigin = "anonymous";
      img.onload = () => {
        loadedMediaCacheRef.current.set(url, img);
        setMediaTick((t) => t + 1);
      };
      img.src = url;
    };

    for (const st of [currentStage, nextStage]) {
      if (!st?.mediaUrl) continue;
      if (st.silhouetteUrl) {
        preloadImage(st.silhouetteUrl);
      }
      if (loadedMediaCacheRef.current.has(st.mediaUrl)) continue;
      if (st.isVideo) {
        const vid = document.createElement("video");
        vid.src = st.mediaUrl;
        vid.muted = true;
        vid.loop = true;
        vid.playsInline = true;
        vid.onloadeddata = () => {
          void vid.play().catch(() => {});
          loadedMediaCacheRef.current.set(st.mediaUrl, vid);
          setMediaTick((t) => t + 1);
        };
      } else {
        preloadImage(st.mediaUrl);
      }
    }
  }, [currentStage, nextStage]);

  // Clean High-Impact 50/50 Split Painter (`mode = "full_animated"` for live preview & JPG thumbnail, `"ui_cutout"` for Python 2.5D video compositor)
  const paintKiComposition = useCallback(
    (
      ctx: CanvasRenderingContext2D,
      phaseSec: number,
      mode: "full_animated" | "ui_cutout"
    ) => {
      const isShorts = aspectMode === "9:16";
      const W = isShorts ? 1080 : 1920;
      const H = isShorts ? 1920 : 1080;
      ctx.clearRect(0, 0, W, H);

      const leftBox = isShorts
        ? { x: 0, y: 150, w: 540, h: 1080 }
        : LEFT_VIEWPORT;
      const rightBox = isShorts
        ? { x: 540, y: 150, w: 540, h: 1080 }
        : RIGHT_VIEWPORT;

      // 1. Character Viewports
      if (mode === "ui_cutout") {
        ctx.clearRect(0, 0, W, H);
        if (isShorts) {
          // Fill solid dark studio bands above (0..150) and below (1230..1920) the 540x1080 character slots
          ctx.fillStyle = "#090c14";
          ctx.fillRect(0, 0, W, 150);
          ctx.fillRect(0, 1230, W, H - 1230);
        }
      } else {
        const curMedia = loadedMediaCacheRef.current.get(currentStage.mediaUrl);
        const nxtSilMedia =
          mysteryNext && nextStage.silhouetteUrl
            ? loadedMediaCacheRef.current.get(nextStage.silhouetteUrl)
            : undefined;
        const nxtMedia =
          nxtSilMedia || loadedMediaCacheRef.current.get(nextStage.mediaUrl);
        const breath = Math.sin((phaseSec * 2 * Math.PI) / 3.0);

        ctx.fillStyle = "#090c14";
        ctx.fillRect(0, 0, W, H);

        const shiftPx = isShorts ? 0 : 72;

        if (curMedia) {
          drawCoverImage(
            ctx,
            curMedia,
            leftBox.x,
            leftBox.y,
            leftBox.w,
            leftBox.h,
            1.015 + 0.01 * breath,
            -2.5 * breath,
            -shiftPx
          );
        }

        if (nxtMedia) {
          ctx.save();
          if (mysteryNext && !nxtSilMedia) {
            ctx.filter = "brightness(0.08) contrast(1.85)";
          }
          drawCoverImage(
            ctx,
            nxtMedia,
            rightBox.x,
            rightBox.y,
            rightBox.w,
            rightBox.h,
            1.01 + 0.006 * Math.cos((phaseSec * 2 * Math.PI) / 3.0),
            0,
            shiftPx
          );
          ctx.restore();
        }
      }

      const boardRows: {
        kind: "view" | "like" | "comment" | "sub";
        iconColor: string;
        label: string;
        val: string;
        isSub?: boolean;
      }[] = [
        {
          kind: "view",
          iconColor: "#0284c7",
          label: "1 VIEW",
          val: `+${weights.view.toLocaleString("en-US")} KI`,
          isSub: false,
        },
        {
          kind: "like",
          iconColor: "#16a34a",
          label: "1 LIKE",
          val: `+${weights.like.toLocaleString("en-US")} KI`,
          isSub: false,
        },
        {
          kind: "comment",
          iconColor: "#7c3aed",
          label: languageStyle === "vi" ? "1 BÌNH LUẬN" : "1 COMMENT",
          val: `+${weights.comment.toLocaleString("en-US")} KI`,
          isSub: false,
        },
        {
          kind: "sub",
          iconColor: "#dc2626",
          label: languageStyle === "vi" ? "1 ĐĂNG KÝ" : "1 SUBSCRIBE",
          val: `+${weights.sub.toLocaleString("en-US")} KI`,
          isSub: true,
        },
      ];

      ctx.textBaseline = "middle";

      // =======================================================================
      // MODE B: 9:16 YOUTUBE SHORTS VERTICAL (1080 x 1920)
      // =======================================================================
      if (isShorts) {
        // Top & Bottom studio gradients
        const topGrad = ctx.createLinearGradient(0, 0, 0, 260);
        topGrad.addColorStop(0, "rgba(9, 12, 20, 0.96)");
        topGrad.addColorStop(0.65, "rgba(9, 12, 20, 0.65)");
        topGrad.addColorStop(1, "rgba(9, 12, 20, 0)");
        ctx.fillStyle = topGrad;
        ctx.fillRect(0, 0, W, 260);

        const botGrad = ctx.createLinearGradient(0, 1020, 0, H);
        botGrad.addColorStop(0, "rgba(9, 12, 20, 0)");
        botGrad.addColorStop(0.22, "rgba(9, 12, 20, 0.94)");
        botGrad.addColorStop(1, "rgba(9, 12, 20, 0.99)");
        ctx.fillStyle = botGrad;
        ctx.fillRect(0, 1020, W, H - 1020);

        // Center split line (x = 540, y = 70..1130)
        ctx.fillStyle = "#09090b";
        ctx.fillRect(W / 2 - 5, 70, 10, 1060);
        ctx.fillStyle = "rgba(255, 255, 255, 0.88)";
        ctx.fillRect(W / 2 - 2, 70, 4, 1060);

        // Top-Left Corner: Current Form Name
        const leftOverline =
          languageStyle === "vi"
            ? `HIỆN TẠI • LV.${currentStage.level}`
            : `CURRENT • LV.${currentStage.level}`;
        ctx.textAlign = "left";
        ctx.font = "800 18px 'Helvetica Neue', Arial, system-ui, sans-serif";
        drawStrokedText(ctx, leftOverline, 36, 98, "#38bdf8", 6, 2);

        const leftFormTitle = currentStage.name.toUpperCase();
        let lPx = 33;
        ctx.font = `900 ${lPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
        while (ctx.measureText(leftFormTitle).width > 475 && lPx > 21) {
          lPx -= 2;
          ctx.font = `900 ${lPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
        }
        drawStrokedText(ctx, leftFormTitle, 36, 142, "#ffffff", 10, 4);

        // Top-Right Corner: NEVER leak nextStage.name when mysteryNext is true!
        const rightOverline =
          languageStyle === "vi"
            ? `NÂNG CẤP • LV.${nextStage.level}`
            : `FORM UPDATE • LV.${nextStage.level}`;
        ctx.textAlign = "right";
        ctx.font = "800 18px 'Helvetica Neue', Arial, system-ui, sans-serif";
        drawStrokedText(ctx, rightOverline, W - 36, 98, "#facc15", 6, 2);

        const rightFormTitle = mysteryNext
          ? languageStyle === "vi"
            ? "CẤP TIẾP THEO ???"
            : "NEXT FORM ???"
          : nextStage.name.toUpperCase();
        let rPx = 33;
        ctx.font = `900 ${rPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
        while (ctx.measureText(rightFormTitle).width > 475 && rPx > 21) {
          rPx -= 2;
          ctx.font = `900 ${rPx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
        }
        drawStrokedText(ctx, rightFormTitle, W - 36, 142, "#fde047", 10, 4);

        // Center Gold Arrow (x = 540, y = 635)
        drawChunkyVectorArrow(ctx, W / 2, 635, 0.74);

        // Right Silhouette Focal Point (rxMid = 810): ONLY '?' + '10,000 KI' directly on the Black Silhouette!
        const rxMid = 810;
        const targetKiText = `${targetKi.toLocaleString("en-US")} KI`;
        let kiPx = 68;
        ctx.font = `900 ${kiPx}px 'Arial Black', Impact, system-ui, sans-serif`;
        while (ctx.measureText(targetKiText).width > 470 && kiPx > 44) {
          kiPx -= 4;
          ctx.font = `900 ${kiPx}px 'Arial Black', Impact, system-ui, sans-serif`;
        }

        if (mysteryNext) {
          ctx.textAlign = "center";
          ctx.font = "900 164px 'Arial Black', Impact, system-ui, sans-serif";
          drawStrokedText(ctx, "?", rxMid, 520, "#facc15", 18, 8);

          ctx.font = `900 ${kiPx}px 'Arial Black', Impact, system-ui, sans-serif`;
          drawStrokedText(ctx, targetKiText, rxMid, 675, "#ffffff", 15, 7);
        } else {
          ctx.textAlign = "center";
          ctx.font = `900 ${kiPx}px 'Arial Black', Impact, system-ui, sans-serif`;
          drawStrokedText(ctx, targetKiText, rxMid, 725, "#ffffff", 15, 7);
        }

        // Single Clean White Board with 4 Rows centered at (540, 1140..1510)
        drawCenterWhiteScoreBoard(ctx, W / 2, 1140, 680, 360, boardRows);
        return;
      }

      // =======================================================================
      // MODE A: 16:9 HORIZONTAL FULL HD (1920 x 1080)
      // =======================================================================
      const topGrad = ctx.createLinearGradient(0, 0, 0, 175);
      topGrad.addColorStop(0, "rgba(0, 0, 0, 0.78)");
      topGrad.addColorStop(0.65, "rgba(0, 0, 0, 0.30)");
      topGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = topGrad;
      ctx.fillRect(0, 0, W, 175);

      // Crisp Center Split Line (x = 960)
      ctx.fillStyle = "#09090b";
      ctx.fillRect(W / 2 - 6, 0, 12, H);
      ctx.fillStyle = "rgba(255, 255, 255, 0.90)";
      ctx.fillRect(W / 2 - 2, 0, 4, H);

      // Top-Left: Current Form Overline + Large Clear Form Name
      const leftOverline =
        languageStyle === "vi"
          ? `CẤP HIỆN TẠI • LV.${currentStage.level}`
          : `CURRENT FORM • LV.${currentStage.level}`;
      ctx.textAlign = "left";
      ctx.font = "800 20px 'Helvetica Neue', Arial, system-ui, sans-serif";
      drawStrokedText(ctx, leftOverline, 52, 42, "#38bdf8", 7, 3);

      const leftFormTitle = currentStage.name.toUpperCase();
      let leftNamePx = 44;
      ctx.font = `900 ${leftNamePx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
      while (ctx.measureText(leftFormTitle).width > 820 && leftNamePx > 28) {
        leftNamePx -= 2;
        ctx.font = `900 ${leftNamePx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
      }
      drawStrokedText(ctx, leftFormTitle, 50, 92, "#ffffff", 12, 5);

      // Top-Right: Form Update Overline + "NEXT FORM ???" (NEVER leaks nextStage.name when mysteryNext is true!)
      const rightOverline =
        languageStyle === "vi"
          ? `NÂNG CẤP HÌNH DẠNG • LV.${nextStage.level}`
          : `FORM UPDATE • LV.${nextStage.level}`;
      ctx.textAlign = "right";
      ctx.font = "800 20px 'Helvetica Neue', Arial, system-ui, sans-serif";
      drawStrokedText(ctx, rightOverline, W - 52, 42, "#facc15", 7, 3);

      const rightFormTitle = mysteryNext
        ? languageStyle === "vi"
          ? "CẤP TIẾP THEO ???"
          : "NEXT FORM ???"
        : nextStage.name.toUpperCase();
      let rightNamePx = 44;
      ctx.font = `900 ${rightNamePx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
      while (ctx.measureText(rightFormTitle).width > 820 && rightNamePx > 28) {
        rightNamePx -= 2;
        ctx.font = `900 ${rightNamePx}px 'Arial Black', 'Helvetica Neue', system-ui, sans-serif`;
      }
      drawStrokedText(ctx, rightFormTitle, W - 50, 92, "#fde047", 12, 5);

      // Center Chunky Gold Arrow (x = 960, y = 435)
      drawChunkyVectorArrow(ctx, W / 2, 435, 0.94);

      // RIGHT SILHOUETTE FOCAL POINT (rxMid = 1440 + 72 = 1512): ONLY Giant '?' + Target Power ('10,000 KI') directly on the Black Silhouette!
      const rxMid = 1512;
      const targetKiText = `${targetKi.toLocaleString("en-US")} KI`;

      let kiFontPx = 94;
      ctx.font = `900 ${kiFontPx}px 'Arial Black', Impact, system-ui, sans-serif`;
      while (ctx.measureText(targetKiText).width > 740 && kiFontPx > 60) {
        kiFontPx -= 4;
        ctx.font = `900 ${kiFontPx}px 'Arial Black', Impact, system-ui, sans-serif`;
      }

      if (mysteryNext) {
        ctx.textAlign = "center";
        ctx.font = "900 198px 'Arial Black', Impact, system-ui, sans-serif";
        drawStrokedText(ctx, "?", rxMid, 365, "#facc15", 20, 10);

        ctx.font = `900 ${kiFontPx}px 'Arial Black', Impact, system-ui, sans-serif`;
        drawStrokedText(ctx, targetKiText, rxMid, 540, "#ffffff", 18, 8);
      } else {
        ctx.textAlign = "center";
        ctx.font = `900 ${kiFontPx}px 'Arial Black', Impact, system-ui, sans-serif`;
        drawStrokedText(ctx, targetKiText, rxMid, 620, "#ffffff", 18, 9);
      }

      // SINGLE CLEAN WHITE BOARD IN THE CENTER WITH 4 ROWS (x = 692..1228, y = 605..945)
      drawCenterWhiteScoreBoard(ctx, W / 2, 605, 536, 340, boardRows);
    },
    [
      aspectMode,
      currentStage,
      nextStage,
      languageStyle,
      mysteryNext,
      targetKi,
      weights,
    ]
  );

  // Live 60fps Idle Animation loop on preview Canvas!
  useEffect(() => {
    if (previewTab !== "live_canvas") return;
    let rafId = 0;
    const startMs = performance.now();
    const targetW = aspectMode === "9:16" ? 1080 : 1920;
    const targetH = aspectMode === "9:16" ? 1920 : 1080;

    const renderTick = (nowMs: number) => {
      const canvas = liveCanvasRef.current;
      if (canvas) {
        if (canvas.width !== targetW) canvas.width = targetW;
        if (canvas.height !== targetH) canvas.height = targetH;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          paintKiComposition(ctx, (nowMs - startMs) / 1000, "full_animated");
        }
      }
      rafId = requestAnimationFrame(renderTick);
    };

    rafId = requestAnimationFrame(renderTick);
    return () => cancelAnimationFrame(rafId);
  }, [paintKiComposition, previewTab, mediaTick, aspectMode]);

  // Render full 2.5D Idle Video (.mp4) + Thumbnail (.jpg) in either 16:9 (1920x1080) or 9:16 Shorts (1080x1920)
  const handleRenderIdleVideo = useCallback(async () => {
    setRenderingVideo(true);
    try {
      const isShorts = aspectMode === "9:16";
      const targetW = isShorts ? 1080 : 1920;
      const targetH = isShorts ? 1920 : 1080;
      const leftBoxStr = isShorts
        ? "0,150,540,1080"
        : `${LEFT_VIEWPORT.x},${LEFT_VIEWPORT.y},${LEFT_VIEWPORT.w},${LEFT_VIEWPORT.h}`;
      const rightBoxStr = isShorts
        ? "540,150,540,1080"
        : `${RIGHT_VIEWPORT.x},${RIGHT_VIEWPORT.y},${RIGHT_VIEWPORT.w},${RIGHT_VIEWPORT.h}`;

      const offThumb = document.createElement("canvas");
      offThumb.width = targetW;
      offThumb.height = targetH;
      const tCtx = offThumb.getContext("2d");
      if (!tCtx) throw new Error("Không khởi tạo được Canvas");
      paintKiComposition(tCtx, 0.75, "full_animated");
      const thumbJpgDataUrl = offThumb.toDataURL("image/jpeg", 0.94);

      const offUi = document.createElement("canvas");
      offUi.width = targetW;
      offUi.height = targetH;
      const uCtx = offUi.getContext("2d");
      if (!uCtx) throw new Error("Không khởi tạo được UI Overlay Canvas");
      paintKiComposition(uCtx, 0.0, "ui_cutout");
      const uiOverlayPngDataUrl = offUi.toDataURL("image/png");

      const res = await fetch("/api/ki-challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "renderIdleVideo",
          sessionId: renderedPkg?.sessionId,
          uiOverlayPngDataUrl,
          thumbJpgDataUrl,
          currentMediaUrl: currentStage.mediaUrl,
          nextMediaUrl: nextStage.mediaUrl,
          leftBox: leftBoxStr,
          rightBox: rightBoxStr,
          currentAuraHex: currentStage.auraHex,
          nextAuraHex: nextStage.auraHex,
          mysteryNext,
          lightning: enableLightning,
          durationSec,
          audioMode,
          bgmTrack,
          customAudioUrl: selectedCustomAudioUrl,
          audioStartSec: audioTrimStartSec,
          audioEndSec: audioTrimEndSec,
        }),
      });

      const json = await res.json();
      if (!res.ok || !json.ok) {
        onNotify(json.error || "Lỗi dựng video Character Idle");
        return;
      }

      setRenderedPkg({
        sessionId: json.sessionId,
        videoFile: json.videoFile,
        thumbFile: json.thumbFile,
        sizeMb: json.sizeMb,
        durationSec: json.durationSec,
        elapsedSec: json.elapsedSec,
      });
      setPreviewTab("rendered_mp4");
      onNotify(
        `🎬 Đã dựng xong Video Idle 1080p (${json.durationSec}s • ${json.sizeMb} MB) + Thumbnail HD trong ${json.elapsedSec}s!`
      );
    } catch (err) {
      onNotify(
        err instanceof Error ? err.message : "Lỗi dựng video Character Idle."
      );
    } finally {
      setRenderingVideo(false);
    }
  }, [
    aspectMode,
    paintKiComposition,
    renderedPkg?.sessionId,
    currentStage,
    nextStage,
    mysteryNext,
    enableLightning,
    durationSec,
    audioMode,
    bgmTrack,
    selectedCustomAudioUrl,
    audioTrimStartSec,
    audioTrimEndSec,
    onNotify,
  ]);

  // Upload custom MP3 / audio source for trimming
  const handleCustomAudioSelected = useCallback(
    async (file: File) => {
      setUploadingAudio(true);
      try {
        const dataUrl = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ""));
          reader.onerror = () => reject(new Error("Không đọc được file âm thanh"));
          reader.readAsDataURL(file);
        });

        const res = await fetch("/api/ki-challenge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "uploadCustomAudio",
            fileName: file.name,
            dataUrl,
          }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
          onNotify(json.error || "Lỗi tải file MP3");
          return;
        }

        const newTrack = { name: String(json.name), url: String(json.url) };
        setCustomAudios((prev) => [newTrack, ...prev]);
        setSelectedCustomAudioUrl(newTrack.url);
        setAudioMode("custom_audio");
        setAudioTrimStartSec(0);
        setAudioTrimEndSec(durationSec);
        onNotify(`🎵 Đã tải lên nhạc "${file.name}" — hãy chọn đoạn cắt bên dưới!`);
      } catch {
        onNotify("Lỗi tải file MP3 tùy chỉnh.");
      } finally {
        setUploadingAudio(false);
      }
    },
    [durationSec, onNotify]
  );

  // Preview exact trimmed audio segment in browser
  const handlePreviewTrimmedAudio = useCallback(() => {
    const audioEl = audioPreviewRef.current;
    if (!audioEl) return;
    if (isPreviewingAudio) {
      audioEl.pause();
      setIsPreviewingAudio(false);
      return;
    }
    audioEl.currentTime = Math.max(0, audioTrimStartSec);
    void audioEl.play().catch(() => {});
    setIsPreviewingAudio(true);
  }, [audioTrimStartSec, isPreviewingAudio]);

  // Upload custom character image / idle video
  const handleCustomFileSelected = useCallback(
    async (file: File) => {
      const targetSlot = customUploadTargetRef.current;
      setUploadingCustomFor(targetSlot);
      try {
        const dataUrl = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result || ""));
          reader.onerror = () => reject(new Error("Không đọc được file"));
          reader.readAsDataURL(file);
        });

        const res = await fetch("/api/ki-challenge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "uploadCustomMedia",
            fileName: file.name,
            dataUrl,
          }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
          onNotify(json.error || "Lỗi tải file nhân vật");
          return;
        }

        const newStage: StagePreset = {
          id: `custom_${Date.now()}`,
          level: stages.length + 1,
          name: file.name.replace(/\.[^/.]+$/, "").slice(0, 20),
          shortName: "CUSTOM",
          mediaUrl: json.url,
          silhouetteUrl: json.silhouetteUrl,
          isVideo: Boolean(json.isVideo),
          auraHex: targetSlot === "current" ? "#38bdf8" : "#facc15",
          defaultTargetKi: targetKi,
          hasLightning: false,
        };
        setStages((prev) => [...prev, newStage]);
        if (targetSlot === "current") {
          setCurrentStageId(newStage.id);
        } else {
          setNextStageId(newStage.id);
        }
        onNotify(`✨ Đã thêm hình/clip nhân vật "${newStage.name}"!`);
      } catch {
        onNotify("Lỗi tải ảnh/clip nhân vật tùy chỉnh.");
      } finally {
        setUploadingCustomFor(null);
      }
    },
    [stages.length, targetKi, onNotify]
  );

  const publicNextFormLabel = useMemo(
    () =>
      mysteryNext
        ? languageStyle === "vi"
          ? "Cấp Tiếp Theo (???)"
          : "Next Form (???)"
        : nextStage.name,
    [mysteryNext, languageStyle, nextStage.name]
  );

  const generatedDescription = useMemo(() => {
    if (languageStyle === "vi") {
      return [
        `⚡ THỬ THÁCH NÂNG CẤP SỨC MẠNH CHO ${characterName.toUpperCase()} (Tập #${episodeNumber}) ⚡`,
        `Trạng thái hiện tại: ${currentStage.name}`,
        `Mục tiêu tiếp theo: ${targetKi.toLocaleString("en-US")} KI ➡️ Mở khóa ${publicNextFormLabel}!`,
        ``,
        `📊 CÁCH TÍNH ĐIỂM KI (Cập nhật tự động trên Tiêu đề video!):`,
        `👁️ 1 View = +${weights.view} KI`,
        `👍 1 Like = +${weights.like} KI`,
        `💬 1 Comment = +${weights.comment} KI`,
        `🔔 1 Đăng ký (Subscribe) = +${weights.sub} KI`,
        ``,
        `Ngay khi tổng điểm chạm mốc ${targetKi.toLocaleString("en-US")} KI, mình sẽ đăng ngay video ${characterName} biến hình sang ${publicNextFormLabel} cùng cột mốc sức mạnh mới!`,
        `#Goku #Saiyan #DragonBall #PowerLevel #AnimeChallenge`,
      ].join("\n");
    }
    return [
      `⚡ ${characterName.toUpperCase()} KI POWER-UP CHALLENGE (Episode #${episodeNumber}) ⚡`,
      `Current Form: ${currentStage.name}`,
      `Next Evolution Goal: ${targetKi.toLocaleString("en-US")} KI ➡️ Unlock ${publicNextFormLabel}!`,
      ``,
      `📊 HOW KI POINTS ARE CALCULATED (Updated automatically in the Video Title!):`,
      `👁️ 1 View = +${weights.view} KI`,
      `👍 1 Like = +${weights.like} KI`,
      `💬 1 Comment = +${weights.comment} KI`,
      `🔔 1 Subscribe = +${weights.sub} KI`,
      ``,
      `As soon as this video hits ${targetKi.toLocaleString("en-US")} KI, the next video featuring ${publicNextFormLabel} will drop with a brand new milestone!`,
      `#Goku #SuperSaiyan #DragonBall #Anime #InteractiveVideo`,
    ].join("\n");
  }, [
    languageStyle,
    characterName,
    episodeNumber,
    currentStage.name,
    publicNextFormLabel,
    targetKi,
    weights,
  ]);

  const generatedPinnedComment = useMemo(() => {
    if (languageStyle === "vi") {
      return `⚡ Tiếp thêm KI cho ${characterName} lên ${publicNextFormLabel} nào anh em! (👍 Like = +${weights.like} KI | 💬 Comment = +${weights.comment} KI | 🔔 Sub = +${weights.sub} KI). Bạn muốn thấy nhân vật nào nữa ở chuỗi sau? Comment bên dưới nhé! 👇🔥`;
    }
    return `⚡ Lend your KI energy to help ${characterName} transform into ${publicNextFormLabel}! (👍 Like = +${weights.like} KI | 💬 Comment = +${weights.comment} KI | 🔔 Subscribe = +${weights.sub} KI). Which character should we do next? Comment below! 👇🔥`;
  }, [languageStyle, characterName, publicNextFormLabel, weights]);

  // Keep editable Description & Pinned Comment synced unless user manually customized them
  useEffect(() => {
    if (!isDescManuallyEdited) {
      setCustomDescription(generatedDescription);
    }
  }, [generatedDescription, isDescManuallyEdited]);

  useEffect(() => {
    if (!isPinManuallyEdited) {
      setCustomPinnedComment(generatedPinnedComment);
    }
  }, [generatedPinnedComment, isPinManuallyEdited]);

  // Keep audioTrimEndSec synced when durationSec changes if user hasn't set a custom window
  useEffect(() => {
    setAudioTrimEndSec((prevStartEnd) => {
      const nextEnd = audioTrimStartSec + durationSec;
      return Math.min(
        Math.max(nextEnd, prevStartEnd > audioTrimStartSec ? nextEnd : durationSec),
        Math.max(durationSec, audioTotalDurSec)
      );
    });
  }, [durationSec, audioTrimStartSec, audioTotalDurSec]);

  const parsedTagsList = useMemo(
    () =>
      customTagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean),
    [customTagsInput]
  );

  // One-click Upload to YouTube + Start Auto KI Title Tracker
  const handlePublishAndTrack = useCallback(async () => {
    if (!renderedPkg) {
      onNotify("Hãy bấm 'Dựng Video Idle 1080p + Thumbnail' trước khi đăng!");
      return;
    }
    if (!hasYoutubeOAuth) {
      onGoToSettings();
      onNotify("Hãy cấp quyền YouTube Studio OAuth ở tab Cài Đặt & API trước!");
      return;
    }

    setPublishing(true);
    try {
      const res = await fetch("/api/ki-challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "publishAndTrack",
          sessionId: renderedPkg.sessionId,
          videoFile: renderedPkg.videoFile,
          thumbFile: renderedPkg.thumbFile,
          privacyStatus,
          characterName,
          episodeNumber,
          currentStageId: currentStage.id,
          currentStageLabel: currentStage.name,
          currentStageMediaUrl: currentStage.mediaUrl,
          currentAuraHex: currentStage.auraHex,
          nextStageId: nextStage.id,
          nextStageLabel: nextStage.name,
          nextStageMediaUrl: nextStage.mediaUrl,
          nextAuraHex: nextStage.auraHex,
          mysteryNext,
          targetKi,
          weights,
          titleTemplate,
          goalReachedTitleTemplate,
          description: customDescription.trim() || generatedDescription,
          tags:
            parsedTagsList.length > 0
              ? parsedTagsList
              : [
                  characterName.toLowerCase(),
                  "goku",
                  "super saiyan",
                  "ki challenge",
                  "power level",
                  "dragon ball",
                ],
          pinnedComment: customPinnedComment.trim() || generatedPinnedComment,
          syncIntervalMin,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        onNotify(json.error || "Lỗi đăng video lên YouTube Studio");
        return;
      }
      setTrackers(json.items || []);
      onNotify(
        "🚀 Đã đăng video + Thumbnail lên YouTube và bật Tự Động Cập Nhật KI Ở Tiêu Đề!"
      );
    } catch {
      onNotify("Lỗi kết nối khi đăng video lên YouTube.");
    } finally {
      setPublishing(false);
    }
  }, [
    renderedPkg,
    hasYoutubeOAuth,
    onGoToSettings,
    onNotify,
    privacyStatus,
    characterName,
    episodeNumber,
    currentStage,
    nextStage,
    targetKi,
    weights,
    titleTemplate,
    goalReachedTitleTemplate,
    customDescription,
    generatedDescription,
    parsedTagsList,
    customPinnedComment,
    generatedPinnedComment,
    syncIntervalMin,
  ]);

  // Attach an manually uploaded YouTube video URL/ID
  const handleAttachExisting = useCallback(async () => {
    if (!attachInput.trim()) return;
    setAttaching(true);
    try {
      const res = await fetch("/api/ki-challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "attachExistingVideo",
          videoUrlOrId: attachInput.trim(),
          characterName,
          episodeNumber,
          currentStageId: currentStage.id,
          currentStageLabel: currentStage.name,
          currentStageMediaUrl: currentStage.mediaUrl,
          currentAuraHex: currentStage.auraHex,
          nextStageId: nextStage.id,
          nextStageLabel: nextStage.name,
          nextStageMediaUrl: nextStage.mediaUrl,
          nextAuraHex: nextStage.auraHex,
          mysteryNext,
          targetKi,
          weights,
          titleTemplate,
          goalReachedTitleTemplate,
          syncIntervalMin,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        onNotify(json.error || "Không gắn được video YouTube");
        return;
      }
      setAttachInput("");
      setTrackers(json.items || []);
      onNotify("⚡ Đã gắn video & cập nhật số KI thực tế lên Tiêu đề YouTube!");
    } catch {
      onNotify("Lỗi kết nối khi gắn video.");
    } finally {
      setAttaching(false);
    }
  }, [
    attachInput,
    characterName,
    episodeNumber,
    currentStage,
    nextStage,
    targetKi,
    weights,
    titleTemplate,
    goalReachedTitleTemplate,
    syncIntervalMin,
    onNotify,
  ]);

  const handleSyncSingle = useCallback(
    async (id: string, forceUpdateTitle = true) => {
      setSyncingId(id);
      try {
        const res = await fetch("/api/ki-challenge", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "syncNow",
            id,
            forceUpdateTitle,
          }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
          onNotify(json.error || "Lỗi đồng bộ KI từ YouTube");
          void fetchTrackers();
          return;
        }
        setTrackers(json.items || []);
        onNotify(
          `⚡ Đã cập nhật KI = ${Number(json.item?.currentKi || 0).toLocaleString(
            "en-US"
          )} lên Tiêu đề YouTube!`
        );
      } catch {
        onNotify("Lỗi kết nối tới YouTube Data API.");
      } finally {
        setSyncingId(null);
      }
    },
    [fetchTrackers, onNotify]
  );

  const handleToggleAutoSync = useCallback(
    async (item: KiChallengeTrackerItem) => {
      const res = await fetch("/api/ki-challenge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "updateTrackerSettings",
          id: item.id,
          patch: { autoSyncEnabled: !item.autoSyncEnabled },
        }),
      });
      const json = await res.json();
      if (res.ok && json.ok) {
        setTrackers(json.items || []);
      }
    },
    []
  );

  const handleDeleteTracker = useCallback(async (id: string) => {
    const res = await fetch("/api/ki-challenge", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "deleteTracker", id }),
    });
    const json = await res.json();
    if (res.ok && json.ok) {
      setTrackers(json.items || []);
    }
  }, []);

  // Advance to Next Evolution Episode in 1 Click when Goal is Reached!
  const handlePrepareNextEvolutionEpisode = useCallback(
    (item: KiChallengeTrackerItem) => {
      const nxtIdx = stages.findIndex((s) => s.id === item.nextStageId);
      if (nxtIdx !== -1) {
        const newCur = stages[nxtIdx];
        const newNxt = stages[Math.min(stages.length - 1, nxtIdx + 1)];
        setCurrentStageId(newCur.id);
        setNextStageId(newNxt.id);
        setEpisodeNumber(item.episodeNumber + 1);
        setTargetKi(Math.max(item.targetKi * 3, newNxt.defaultTargetKi));
        setRenderedPkg(null);
        setPreviewTab("live_canvas");
        window.scrollTo({ top: 0, behavior: "smooth" });
        onNotify(
          `🔥 Đã chuyển sang Tập #${item.episodeNumber + 1}: ${newCur.name} ➡️ ${
            newNxt.name
          }!`
        );
      }
    },
    [stages, onNotify]
  );

  const renderedVideoUrl = useMemo(() => {
    if (!renderedPkg) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      renderedPkg.sessionId
    )}&file=${encodeURIComponent(renderedPkg.videoFile)}`;
  }, [renderedPkg]);

  const downloadVideoUrl = useMemo(() => {
    if (!renderedPkg) return "";
    const dl = `${characterName}_Ep${episodeNumber}_${currentStage.name.replace(
      /\s+/g,
      "_"
    )}_Idle_1080p.mp4`;
    return `${renderedVideoUrl}&download=${encodeURIComponent(dl)}`;
  }, [renderedPkg, renderedVideoUrl, characterName, episodeNumber, currentStage.name]);

  const downloadThumbUrl = useMemo(() => {
    if (!renderedPkg) return "";
    const dl = `${characterName}_Ep${episodeNumber}_Thumbnail_${targetKi}KI.jpg`;
    return `/api/reup-tool/media?session=${encodeURIComponent(
      renderedPkg.sessionId
    )}&file=${encodeURIComponent(renderedPkg.thumbFile)}&download=${encodeURIComponent(
      dl
    )}`;
  }, [renderedPkg, characterName, episodeNumber, targetKi]);

  const sampleTitlePreview = useMemo(
    () =>
      formatPreviewTitle(titleTemplate, {
        ki: Math.round(targetKi * 0.5),
        target: targetKi,
        milestone: 50,
        char: characterName,
        currentForm: currentStage.name,
        nextForm: publicNextFormLabel,
      }),
    [
      titleTemplate,
      targetKi,
      characterName,
      currentStage.name,
      publicNextFormLabel,
    ]
  );

  const copyText = (key: string, val: string, label: string) => {
    navigator.clipboard.writeText(val);
    setCopiedKey(key);
    onNotify(`📋 Đã copy ${label}!`);
    setTimeout(() => setCopiedKey(null), 1800);
  };

  return (
    <div className="space-y-6">
      <input
        ref={customFileInputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp,video/mp4,video/webm,.png,.jpg,.jpeg,.webp,.mp4,.webm,.mov"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleCustomFileSelected(f);
          e.target.value = "";
        }}
      />
      <input
        ref={customAudioInputRef}
        type="file"
        accept="audio/*,.mp3,.m4a,.wav,.aac,.ogg,.flac"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleCustomAudioSelected(f);
          e.target.value = "";
        }}
      />

      {/* TOP BANNER */}
      <div className="rounded-2xl border border-amber-500/35 bg-gradient-to-r from-amber-950/35 via-zinc-900/90 to-violet-950/35 p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="inline-flex items-center gap-2 text-amber-300 text-xs font-extrabold uppercase tracking-wider">
            <Flame className="h-4 w-4 text-amber-400" />
            Interactive KI Power Evolution Studio (16:9 Idle Video + Auto-Title KI)
          </div>
          <h2 className="text-base sm:text-lg font-extrabold text-white">
            Dựng Video Nhân Vật Idle (Thở & Gồng Hào Quang Ki) + Tự Động Nhảy Điểm KI Ở Tiêu Đề YouTube
          </h2>
          <p className="text-xs text-zinc-400">
            Nhân vật không đứng đơ như ảnh chụp • Tự quy đổi{" "}
            <strong className="text-zinc-200">
              View + Like + Comment + Subscribe (+{weights.sub} KI)
            </strong>{" "}
            cập nhật thẳng lên Tiêu đề YouTube theo thời gian thật!
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleSwitchLanguage("en")}
            className={`rounded-xl px-3 py-1.5 text-xs font-extrabold border cursor-pointer ${
              languageStyle === "en"
                ? "border-amber-400 bg-amber-500/20 text-amber-200"
                : "border-zinc-800 bg-zinc-950 text-zinc-400"
            }`}
          >
            🇺🇸 English Global
          </button>
          <button
            type="button"
            onClick={() => handleSwitchLanguage("vi")}
            className={`rounded-xl px-3 py-1.5 text-xs font-extrabold border cursor-pointer ${
              languageStyle === "vi"
                ? "border-amber-400 bg-amber-500/20 text-amber-200"
                : "border-zinc-800 bg-zinc-950 text-zinc-400"
            }`}
          >
            🇻🇳 Tiếng Việt
          </button>
        </div>
      </div>

      {/* PART 1: 2-COLUMN VIDEO & THUMBNAIL BUILDER */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* LEFT (7 COLS): LIVE 60FPS IDLE PREVIEW CANVAS & RENDERED MP4 PLAYER */}
        <div className="lg:col-span-7 space-y-4">
          <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/75 p-4 space-y-3.5 shadow-xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-1.5 rounded-xl bg-zinc-950 p-1 border border-zinc-800">
                <button
                  type="button"
                  onClick={() => setPreviewTab("live_canvas")}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                    previewTab === "live_canvas"
                      ? "bg-amber-500 text-zinc-950"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Eye className="h-3.5 w-3.5" />
                  Xem Trước Bố Cục & Chuyển Động Idle
                </button>
                <button
                  type="button"
                  disabled={!renderedPkg}
                  onClick={() => setPreviewTab("rendered_mp4")}
                  className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer disabled:opacity-40 ${
                    previewTab === "rendered_mp4"
                      ? "bg-emerald-600 text-white"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Play className="h-3.5 w-3.5" />
                  Video Idle 1080p Đã Xuất (.MP4)
                </button>
              </div>

              <div className="flex items-center gap-1.5 rounded-xl bg-zinc-950 p-1 border border-zinc-800">
                <button
                  type="button"
                  onClick={() => {
                    setAspectMode("16:9");
                    setPreviewTab("live_canvas");
                  }}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-extrabold transition cursor-pointer ${
                    aspectMode === "16:9"
                      ? "bg-sky-500 text-zinc-950"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  📺 Ngang 16:9 (1920×1080)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setAspectMode("9:16");
                    setPreviewTab("live_canvas");
                  }}
                  className={`rounded-lg px-2.5 py-1 text-[11px] font-extrabold transition cursor-pointer ${
                    aspectMode === "9:16"
                      ? "bg-rose-500 text-white"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  📱 Shorts Dọc 9:16 (1080×1920)
                </button>
              </div>
            </div>

            {previewTab === "live_canvas" ? (
              <div
                className={`overflow-hidden rounded-xl border border-zinc-800 bg-black mx-auto ${
                  aspectMode === "9:16" ? "max-w-[340px]" : "w-full"
                }`}
              >
                <canvas
                  ref={liveCanvasRef}
                  width={aspectMode === "9:16" ? 1080 : 1920}
                  height={aspectMode === "9:16" ? 1920 : 1080}
                  className={`w-full block ${
                    aspectMode === "9:16" ? "aspect-[9/16]" : "aspect-video"
                  }`}
                />
              </div>
            ) : (
              <div
                className={`overflow-hidden rounded-xl border border-emerald-500/40 bg-black mx-auto ${
                  aspectMode === "9:16" ? "max-w-[340px]" : "w-full"
                }`}
              >
                <video
                  key={renderedVideoUrl}
                  src={renderedVideoUrl}
                  controls
                  autoPlay
                  loop
                  playsInline
                  className={`w-full block ${
                    aspectMode === "9:16" ? "aspect-[9/16]" : "aspect-video"
                  }`}
                />
              </div>
            )}

            {/* Live Simulated YouTube Title Preview right underneath video! */}
            <div className="rounded-xl border border-zinc-800 bg-zinc-950/90 p-3 space-y-1.5">
              <div className="flex items-center justify-between text-[11px] text-zinc-400">
                <span className="font-bold text-emerald-400 flex items-center gap-1">
                  <Activity className="h-3.5 w-3.5" />
                  Mô phỏng Tiêu đề YouTube tự nhảy số KI khi có người xem/like/sub:
                </span>
                <span>{sampleTitlePreview.length}/100 ký tự</span>
              </div>
              <div className="text-sm sm:text-base font-extrabold text-white truncate">
                {sampleTitlePreview}
              </div>
            </div>

            {/* Action Buttons: Render Idle MP4 + Download + Direct Publish */}
            <div className="flex flex-wrap items-center gap-2.5 pt-1">
              <button
                type="button"
                disabled={renderingVideo}
                onClick={() => void handleRenderIdleVideo()}
                className="flex-1 min-w-[230px] inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-400 hover:to-orange-400 px-4 py-3 text-xs sm:text-sm font-extrabold text-zinc-950 shadow-lg shadow-amber-500/20 transition cursor-pointer disabled:opacity-60"
              >
                {renderingVideo ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Đang thổi hồn 2.5D Idle (Thở + Ki Aura + Hạt sáng)...
                  </>
                ) : (
                  <>
                    <Film className="h-4 w-4" />
                    1. Dựng Video Idle 1080p (.MP4) + Thumbnail (.JPG)
                  </>
                )}
              </button>

              {renderedPkg && (
                <>
                  <a
                    href={downloadVideoUrl}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/50 bg-emerald-950/40 hover:bg-emerald-900/50 px-3.5 py-3 text-xs font-extrabold text-emerald-200 transition"
                  >
                    <Download className="h-4 w-4" />
                    Tải Video (.MP4)
                  </a>
                  <a
                    href={downloadThumbUrl}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3.5 py-3 text-xs font-extrabold text-zinc-200 transition"
                  >
                    <ImageIcon className="h-4 w-4 text-amber-400" />
                    Tải Thumbnail (.JPG)
                  </a>
                </>
              )}
            </div>

            {/* Direct 1-Click Publish & Auto-Track Card */}
            {renderedPkg && (
              <div className="rounded-xl border border-violet-500/40 bg-violet-950/20 p-3.5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-xs font-extrabold text-violet-200 flex items-center gap-1.5">
                    <Rocket className="h-4 w-4 text-violet-400" />
                    2. Đăng Thẳng Lên Kênh{" "}
                    {connectedChannelLabel ? `(${connectedChannelLabel})` : "YouTube"} & Bật Auto-Update Tiêu Đề KI
                  </div>
                  <select
                    value={privacyStatus}
                    onChange={(e) =>
                      setPrivacyStatus(
                        e.target.value as "public" | "unlisted" | "private"
                      )
                    }
                    className="rounded-lg border border-zinc-700 bg-zinc-950 px-2.5 py-1 text-xs font-bold text-white"
                  >
                    <option value="public">🌍 Công khai ngay (Public)</option>
                    <option value="unlisted">🔗 Không công khai (Unlisted test)</option>
                    <option value="private">🔒 Riêng tư (Private)</option>
                  </select>
                </div>

                <button
                  type="button"
                  disabled={publishing}
                  onClick={() => void handlePublishAndTrack()}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 py-3 text-xs sm:text-sm font-extrabold text-white shadow-lg cursor-pointer disabled:opacity-50"
                >
                  {publishing ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Đang upload Video + Thumbnail & kích hoạt bộ đếm KI...
                    </>
                  ) : (
                    <>
                      <Rocket className="h-4 w-4" />
                      Đăng Lên YouTube & Tự Động Cập Nhật KI Ở Tiêu Đề Ngay!
                    </>
                  )}
                </button>
              </div>
            )}

            {/* Quick Copy Description & Pinned Comment (for manual uploaders) */}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button
                type="button"
                onClick={() =>
                  copyText("sample_title", sampleTitlePreview, "Tiêu đề mẫu")
                }
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-2.5 py-1.5 text-[11px] font-bold text-zinc-300 cursor-pointer"
              >
                {copiedKey === "sample_title" ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                Copy Tiêu Đề Mẫu
              </button>
              <button
                type="button"
                onClick={() =>
                  copyText(
                    "desc",
                    customDescription || generatedDescription,
                    "Mô tả quy đổi KI"
                  )
                }
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-2.5 py-1.5 text-[11px] font-bold text-zinc-300 cursor-pointer"
              >
                {copiedKey === "desc" ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                Copy Mô Tả Video
              </button>
              <button
                type="button"
                onClick={() =>
                  copyText("tags", customTagsInput, "Thẻ Tags YouTube")
                }
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-2.5 py-1.5 text-[11px] font-bold text-zinc-300 cursor-pointer"
              >
                {copiedKey === "tags" ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                Copy Tags
              </button>
              <button
                type="button"
                onClick={() =>
                  copyText(
                    "pin",
                    customPinnedComment || generatedPinnedComment,
                    "Bình luận ghim"
                  )
                }
                className="inline-flex items-center gap-1 rounded-lg border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 px-2.5 py-1.5 text-[11px] font-bold text-zinc-300 cursor-pointer"
              >
                {copiedKey === "pin" ? (
                  <Check className="h-3 w-3 text-emerald-400" />
                ) : (
                  <Copy className="h-3 w-3" />
                )}
                Copy Bình Luận Ghim
              </button>
            </div>
          </div>
        </div>

        {/* RIGHT (5 COLS): CHARACTER STAGES, MILESTONE & IDLE MOTION CONTROLS */}
        <div className="lg:col-span-5 space-y-4">
          {/* 1. CHARACTER & EVOLUTION PAIR */}
          <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/75 p-4 space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold uppercase tracking-wider text-amber-300 flex items-center gap-1.5">
                <Crown className="h-3.5 w-3.5" />
                1. Nhân Vật & Cặp Cấp Độ Tiến Hóa
              </span>
              <span className="text-[10px] text-zinc-400">
                Có sẵn 9 cấp Goku chính truyện (+ SSB Kaioken) chuẩn 2D Toriyama
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2">
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Tên nhân vật
                </label>
                <input
                  type="text"
                  value={characterName}
                  onChange={(e) => setCharacterName(e.target.value)}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs font-bold text-white"
                />
              </div>
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Tập số (#)
                </label>
                <input
                  type="number"
                  min={1}
                  value={episodeNumber}
                  onChange={(e) =>
                    setEpisodeNumber(Math.max(1, Number(e.target.value) || 1))
                  }
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs font-bold text-white"
                />
              </div>
            </div>

            {/* Current Form & Next Form Selectors */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="rounded-xl border border-sky-500/40 bg-zinc-950/80 p-2.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold text-sky-300">
                    BÊN TRÁI (Hiện Tại)
                  </span>
                  <button
                    type="button"
                    disabled={uploadingCustomFor !== null}
                    onClick={() => {
                      customUploadTargetRef.current = "current";
                      customFileInputRef.current?.click();
                    }}
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-sky-300 hover:underline cursor-pointer"
                  >
                    <Upload className="h-3 w-3" />
                    Tải ảnh/clip AI
                  </button>
                </div>
                <select
                  value={currentStageId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setCurrentStageId(id);
                    const idx = stages.findIndex((s) => s.id === id);
                    if (idx !== -1 && idx + 1 < stages.length) {
                      setNextStageId(stages[idx + 1].id);
                      setTargetKi(stages[idx + 1].defaultTargetKi);
                    }
                  }}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-bold text-white"
                >
                  {stages.map((s, idx) => (
                    <option key={s.id} value={s.id}>
                      #{idx + 1} • {s.name} {s.isVideo ? "(Video)" : ""}
                    </option>
                  ))}
                </select>
              </div>

              <div className="rounded-xl border border-amber-500/40 bg-zinc-950/80 p-2.5 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-extrabold text-amber-300">
                    BÊN PHẢI (Mốc Tiếp Theo)
                  </span>
                  <button
                    type="button"
                    disabled={uploadingCustomFor !== null}
                    onClick={() => {
                      customUploadTargetRef.current = "next";
                      customFileInputRef.current?.click();
                    }}
                    className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-300 hover:underline cursor-pointer"
                  >
                    <Upload className="h-3 w-3" />
                    Tải ảnh AI
                  </button>
                </div>
                <select
                  value={nextStageId}
                  onChange={(e) => {
                    const id = e.target.value;
                    setNextStageId(id);
                    const found = stages.find((s) => s.id === id);
                    if (found) setTargetKi(found.defaultTargetKi);
                  }}
                  className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-bold text-white"
                >
                  {stages.map((s, idx) => (
                    <option key={s.id} value={s.id}>
                      #{idx + 1} • {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <label className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/80 px-3 py-2 cursor-pointer">
                <span className="text-[11px] font-bold text-zinc-200 flex items-center gap-1">
                  <Lock className="h-3.5 w-3.5 text-amber-400" />
                  Ẩn bóng đen cấp sau (?)
                </span>
                <input
                  type="checkbox"
                  checked={mysteryNext}
                  onChange={(e) => setMysteryNext(e.target.checked)}
                  className="h-4 w-4 accent-amber-500"
                />
              </label>

              <label className="flex items-center justify-between gap-2 rounded-xl border border-zinc-800 bg-zinc-950/80 px-3 py-2 cursor-pointer">
                <span className="text-[11px] font-bold text-zinc-200 flex items-center gap-1">
                  <Zap className="h-3.5 w-3.5 text-cyan-400" />
                  Tia sét Ki quanh người
                </span>
                <input
                  type="checkbox"
                  checked={enableLightning}
                  onChange={(e) => setEnableLightning(e.target.checked)}
                  className="h-4 w-4 accent-cyan-500"
                />
              </label>
            </div>
          </div>

          {/* 2. TARGET KI MILESTONE & POINT CONVERSION WEIGHTS */}
          <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/75 p-4 space-y-3.5">
            <span className="text-xs font-extrabold uppercase tracking-wider text-emerald-300 flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5" />
              2. Cột Mốc KI & Công Thức Quy Đổi Tương Tác
            </span>

            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-bold text-zinc-200">
                  Cột mốc KI mục tiêu để lên hình dạng mới
                </label>
                <div className="flex gap-1">
                  {[5000, 10000, 50000, 200000].map((preset) => (
                    <button
                      key={preset}
                      type="button"
                      onClick={() => setTargetKi(preset)}
                      className="rounded-md border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[10px] font-bold text-zinc-300 hover:border-amber-400 cursor-pointer"
                    >
                      {preset >= 1000 ? `${preset / 1000}K` : preset}
                    </button>
                  ))}
                </div>
              </div>
              <input
                type="number"
                min={100}
                step={500}
                value={targetKi}
                onChange={(e) =>
                  setTargetKi(Math.max(10, Number(e.target.value) || 1000))
                }
                className="w-full rounded-xl border border-amber-500/50 bg-zinc-950 px-3.5 py-2 text-sm font-extrabold text-amber-300"
              />
            </div>

            <div className="grid grid-cols-4 gap-2">
              {(
                [
                  { key: "view", label: "👁️ 1 View", color: "text-sky-300" },
                  { key: "like", label: "👍 1 Like", color: "text-emerald-300" },
                  { key: "comment", label: "💬 1 Cmt", color: "text-purple-300" },
                  { key: "sub", label: "🔔 1 Sub", color: "text-amber-300" },
                ] as const
              ).map((item) => (
                <div
                  key={item.key}
                  className="rounded-xl border border-zinc-800 bg-zinc-950 p-2 text-center"
                >
                  <div className={`text-[10px] font-extrabold ${item.color}`}>
                    {item.label}
                  </div>
                  <input
                    type="number"
                    min={0}
                    value={weights[item.key]}
                    onChange={(e) =>
                      setWeights((prev) => ({
                        ...prev,
                        [item.key]: Math.max(0, Number(e.target.value) || 0),
                      }))
                    }
                    className="mt-1 w-full rounded-lg border border-zinc-800 bg-zinc-900 px-1.5 py-1 text-center text-xs font-extrabold text-white"
                  />
                </div>
              ))}
            </div>

            {/* Idle Video Duration & Audio + Custom MP3 Trimmer */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div>
                <label className="block text-[11px] text-zinc-400 mb-1">
                  Độ dài video Idle
                </label>
                <select
                  value={durationSec}
                  onChange={(e) => setDurationSec(Number(e.target.value))}
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-2.5 py-2 text-xs font-bold text-white"
                >
                  <option value={12}>12 giây (Ngắn gọn)</option>
                  <option value={15}>15 giây (Chuẩn khuyên dùng)</option>
                  <option value={25}>25 giây</option>
                  <option value={45}>45 giây</option>
                </select>
              </div>
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-[11px] text-zinc-400">
                    Nguồn âm thanh nền
                  </label>
                  <button
                    type="button"
                    disabled={uploadingAudio}
                    onClick={() => customAudioInputRef.current?.click()}
                    className="inline-flex items-center gap-1 text-[10px] font-extrabold text-amber-300 hover:underline cursor-pointer"
                  >
                    <Upload className="h-3 w-3" />
                    {uploadingAudio ? "Đang tải..." : "+ Tải file MP3"}
                  </button>
                </div>
                <select
                  value={audioMode}
                  onChange={(e) =>
                    setAudioMode(
                      e.target.value as
                        | "epic_hum"
                        | "builtin_bgm"
                        | "custom_audio"
                        | "silent"
                    )
                  }
                  className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-2.5 py-2 text-xs font-bold text-white"
                >
                  <option value="epic_hum">⚡ Tiếng Gồng Hào Quang Ki</option>
                  <option value="builtin_bgm">🎵 Nhạc Beat Có Sẵn</option>
                  <option value="custom_audio">
                    🎧 File MP3 Tải Lên & Cắt Đoạn
                  </option>
                  <option value="silent">🔇 Im lặng</option>
                </select>
              </div>
            </div>

            {/* MP3 / Audio Source Selector & Segment Trimmer */}
            {(audioMode === "custom_audio" || audioMode === "builtin_bgm") && (
              <div className="rounded-xl border border-amber-500/35 bg-zinc-950/90 p-3 space-y-2.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-[11px] font-extrabold text-amber-300">
                    🎧 Chọn File Nhạc & Cắt Đoạn Khớp Video ({durationSec}s)
                  </span>
                  <button
                    type="button"
                    disabled={uploadingAudio}
                    onClick={() => customAudioInputRef.current?.click()}
                    className="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-500/15 hover:bg-amber-500/25 px-2 py-1 text-[10px] font-extrabold text-amber-200 cursor-pointer"
                  >
                    <Upload className="h-3 w-3" />
                    Tải MP3/WAV mới từ máy
                  </button>
                </div>

                {audioMode === "custom_audio" ? (
                  customAudios.length > 0 ? (
                    <select
                      value={selectedCustomAudioUrl}
                      onChange={(e) => {
                        setSelectedCustomAudioUrl(e.target.value);
                        setAudioTrimStartSec(0);
                        setAudioTrimEndSec(durationSec);
                      }}
                      className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-bold text-white"
                    >
                      {customAudios.map((a) => (
                        <option key={a.url} value={a.url}>
                          🎵 {a.name}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <div className="rounded-lg border border-dashed border-zinc-700 p-2.5 text-center text-[11px] text-zinc-400">
                      Chưa có file MP3 nào. Hãy bấm{" "}
                      <button
                        type="button"
                        onClick={() => customAudioInputRef.current?.click()}
                        className="font-extrabold text-amber-300 underline cursor-pointer"
                      >
                        Tải MP3/WAV mới từ máy
                      </button>{" "}
                      để chọn nhạc và cắt đoạn!
                    </div>
                  )
                ) : (
                  <select
                    value={bgmTrack}
                    onChange={(e) => setBgmTrack(e.target.value)}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs font-bold text-white"
                  >
                    <option value="dance_trend_club.m4a">
                      🎵 Dance Trend Club Beat
                    </option>
                    <option value="lofi_chill_spark.m4a">
                      🎵 Lofi Chill Spark
                    </option>
                    <option value="upbeat_fashion_pop.m4a">
                      🎵 Upbeat Energy Pop
                    </option>
                  </select>
                )}

                {/* Hidden/compact audio element to inspect duration and preview exact trimmed window */}
                <audio
                  ref={audioPreviewRef}
                  src={
                    audioMode === "custom_audio"
                      ? selectedCustomAudioUrl || undefined
                      : `/reup-bgm/${bgmTrack}`
                  }
                  onLoadedMetadata={(e) => {
                    const dur = Math.round(e.currentTarget.duration || 60);
                    if (dur > 0 && Number.isFinite(dur)) {
                      setAudioTotalDurSec(dur);
                      setAudioTrimEndSec(Math.min(dur, audioTrimStartSec + durationSec));
                    }
                  }}
                  onTimeUpdate={(e) => {
                    if (
                      isPreviewingAudio &&
                      audioTrimEndSec > audioTrimStartSec &&
                      e.currentTarget.currentTime >= audioTrimEndSec
                    ) {
                      e.currentTarget.pause();
                      setIsPreviewingAudio(false);
                    }
                  }}
                  onEnded={() => setIsPreviewingAudio(false)}
                  className="hidden"
                />

                {/* Start / End Segment Trimmer Inputs */}
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/80 p-2">
                    <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-1">
                      <span>Bắt đầu cắt (giây)</span>
                      <span className="font-mono text-amber-300">
                        {audioTrimStartSec.toFixed(1)}s
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={Math.max(1, audioTotalDurSec - 2)}
                      step={0.5}
                      value={audioTrimStartSec}
                      onChange={(e) => {
                        const st = Number(e.target.value);
                        setAudioTrimStartSec(st);
                        setAudioTrimEndSec(
                          Math.min(audioTotalDurSec, st + durationSec)
                        );
                      }}
                      className="w-full accent-amber-400"
                    />
                    <input
                      type="number"
                      min={0}
                      max={Math.max(1, audioTotalDurSec)}
                      step={0.5}
                      value={audioTrimStartSec}
                      onChange={(e) => {
                        const st = Math.max(0, Number(e.target.value) || 0);
                        setAudioTrimStartSec(st);
                        if (audioTrimEndSec <= st) {
                          setAudioTrimEndSec(st + durationSec);
                        }
                      }}
                      className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-0.5 text-xs font-mono text-white"
                    />
                  </div>

                  <div className="rounded-lg border border-zinc-800 bg-zinc-900/80 p-2">
                    <div className="flex items-center justify-between text-[10px] text-zinc-400 mb-1">
                      <span>Kết thúc cắt (giây)</span>
                      <span className="font-mono text-emerald-300">
                        {audioTrimEndSec.toFixed(1)}s (Tổng file: {audioTotalDurSec}s)
                      </span>
                    </div>
                    <input
                      type="range"
                      min={Math.min(audioTotalDurSec, audioTrimStartSec + 1)}
                      max={Math.max(durationSec, audioTotalDurSec)}
                      step={0.5}
                      value={audioTrimEndSec}
                      onChange={(e) =>
                        setAudioTrimEndSec(
                          Math.max(audioTrimStartSec + 1, Number(e.target.value))
                        )
                      }
                      className="w-full accent-emerald-400"
                    />
                    <input
                      type="number"
                      min={audioTrimStartSec + 1}
                      max={Math.max(durationSec, audioTotalDurSec)}
                      step={0.5}
                      value={audioTrimEndSec}
                      onChange={(e) =>
                        setAudioTrimEndSec(
                          Math.max(
                            audioTrimStartSec + 1,
                            Number(e.target.value) || audioTrimStartSec + durationSec
                          )
                        )
                      }
                      className="mt-1 w-full rounded border border-zinc-700 bg-zinc-950 px-2 py-0.5 text-xs font-mono text-white"
                    />
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
                  <button
                    type="button"
                    onClick={handlePreviewTrimmedAudio}
                    disabled={
                      audioMode === "custom_audio" && !selectedCustomAudioUrl
                    }
                    className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 px-3 py-1.5 text-[11px] font-extrabold text-zinc-950 cursor-pointer disabled:opacity-40"
                  >
                    <Play className="h-3 w-3" />
                    {isPreviewingAudio
                      ? "⏹ Dừng nghe thử"
                      : `Nghe thử đoạn cắt (${audioTrimStartSec}s ➔ ${audioTrimEndSec}s)`}
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setAudioTrimEndSec(
                        Math.min(
                          Math.max(durationSec, audioTotalDurSec),
                          audioTrimStartSec + durationSec
                        )
                      )
                    }
                    className="rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1.5 text-[10px] font-bold text-zinc-300 cursor-pointer"
                  >
                    ⚡ Khớp đúng {durationSec}s video
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 3. INTEGRATED YOUTUBE PUBLISHING METADATA (TITLE • DESCRIPTION • TAGS • PINNED COMMENT) */}
          <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/75 p-4 space-y-3.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold uppercase tracking-wider text-violet-300 flex items-center gap-1.5">
                <Rocket className="h-3.5 w-3.5" />
                3. Thông Tin Đăng YouTube (Title • Description • Tags)
              </span>
              <button
                type="button"
                onClick={() => {
                  setIsDescManuallyEdited(false);
                  setIsPinManuallyEdited(false);
                  setCustomDescription(generatedDescription);
                  setCustomPinnedComment(generatedPinnedComment);
                  onNotify("🔄 Đã đồng bộ lại Mô tả & Bình luận theo mốc KI mới!");
                }}
                className="text-[10px] font-bold text-amber-300 hover:underline cursor-pointer"
              >
                🔄 Tự điền theo thông số KI
              </button>
            </div>

            {/* Dynamic Title Template showing actual KI numbers (e.g. 5,000/10,000 KI) */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-bold text-zinc-200">
                  Tiêu đề YouTube (Hiển thị số KI thật: `{"{ki}"}/{"{target}"} KI` hoặc `{"{kiRaw}"}/{"{targetRaw}"}`)
                </label>
                <div className="flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() =>
                      setTitleTemplate(
                        languageStyle === "vi"
                          ? "⚡ [{ki}/{target} KI] Tiếp KI Giúp {char} Lên {nextForm}! (Like & Sub = +KI) 🔥"
                          : "⚡ [{ki}/{target} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
                      )
                    }
                    className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[10px] font-bold text-emerald-300 hover:border-emerald-400 cursor-pointer"
                  >
                    5,000/10,000
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setTitleTemplate(
                        languageStyle === "vi"
                          ? "⚡ [{kiRaw}/{targetRaw} KI] Tiếp KI Giúp {char} Lên {nextForm}! (Like & Sub = +KI) 🔥"
                          : "⚡ [{kiRaw}/{targetRaw} KI] Help {char} Unlock {nextForm}! (Like & Sub = +KI) 🔥"
                      )
                    }
                    className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 text-[10px] font-bold text-sky-300 hover:border-sky-400 cursor-pointer"
                  >
                    5000/10000
                  </button>
                </div>
              </div>
              <input
                type="text"
                value={titleTemplate}
                onChange={(e) => setTitleTemplate(e.target.value)}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs font-mono text-emerald-300"
              />
              <div className="text-[11px] text-zinc-400 truncate">
                Xem trước:{" "}
                <strong className="text-white">{sampleTitlePreview}</strong>
              </div>
            </div>

            {/* 100% Goal Reached Title Template */}
            <div className="space-y-1">
              <label className="block text-[11px] font-bold text-zinc-300">
                Tiêu đề khi chạm đích 100% (`{targetKi.toLocaleString("en-US")}/{targetKi.toLocaleString("en-US")} KI`)
              </label>
              <input
                type="text"
                value={goalReachedTitleTemplate}
                onChange={(e) => setGoalReachedTitleTemplate(e.target.value)}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-1.5 text-xs font-mono text-amber-300"
              />
            </div>

            {/* Editable Description */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-bold text-zinc-200">
                  Mô tả video (Description)
                </label>
                <button
                  type="button"
                  onClick={() =>
                    copyText(
                      "desc_box",
                      customDescription || generatedDescription,
                      "Mô tả video"
                    )
                  }
                  className="inline-flex items-center gap-1 text-[10px] font-bold text-zinc-300 hover:text-white cursor-pointer"
                >
                  {copiedKey === "desc_box" ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  Copy Description
                </button>
              </div>
              <textarea
                rows={5}
                value={customDescription}
                onChange={(e) => {
                  setCustomDescription(e.target.value);
                  setIsDescManuallyEdited(true);
                }}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-200 leading-relaxed"
              />
            </div>

            {/* Editable Tags */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-bold text-zinc-200">
                  Thẻ Tags YouTube (phân cách bằng dấu phẩy • {parsedTagsList.length} tags)
                </label>
                <button
                  type="button"
                  onClick={() =>
                    copyText("tags_box", customTagsInput, "Thẻ Tags")
                  }
                  className="inline-flex items-center gap-1 text-[10px] font-bold text-zinc-300 hover:text-white cursor-pointer"
                >
                  {copiedKey === "tags_box" ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  Copy Tags
                </button>
              </div>
              <input
                type="text"
                value={customTagsInput}
                onChange={(e) => setCustomTagsInput(e.target.value)}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-sky-200"
              />
            </div>

            {/* Editable Pinned Comment */}
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-bold text-zinc-200">
                  Bình luận ghim (Pinned Comment kêu gọi tương tác)
                </label>
                <button
                  type="button"
                  onClick={() =>
                    copyText(
                      "pin_box",
                      customPinnedComment || generatedPinnedComment,
                      "Bình luận ghim"
                    )
                  }
                  className="inline-flex items-center gap-1 text-[10px] font-bold text-zinc-300 hover:text-white cursor-pointer"
                >
                  {copiedKey === "pin_box" ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  Copy Pinned Comment
                </button>
              </div>
              <textarea
                rows={2}
                value={customPinnedComment}
                onChange={(e) => {
                  setCustomPinnedComment(e.target.value);
                  setIsPinManuallyEdited(true);
                }}
                className="w-full rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-zinc-200"
              />
            </div>
          </div>
        </div>
      </div>

      {/* PART 2: REAL-TIME YOUTUBE TITLE KI AUTO-UPDATER DASHBOARD */}
      <div className="rounded-2xl border border-emerald-500/35 bg-zinc-900/80 p-5 space-y-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-sm sm:text-base font-extrabold text-white flex items-center gap-2">
                <Activity className="h-4 w-4 text-emerald-400" />
                Đồng Bộ 5 Phút/Lần • Đổi Tiêu Đề YouTube Ở Mốc 25% • 50% • 75% • 100%
              </h3>
              <a
                href="/ki-live"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-amber-400/50 bg-amber-500/15 hover:bg-amber-500/25 px-2.5 py-1 text-[11px] font-extrabold text-amber-200 transition"
              >
                🌐 Mở Trang Live KI Bar Riêng (/ki-live)
                <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">
              Tiết kiệm 100% Quota (~576 read units/ngày + tối đa 4 lần ghi = 200 units/video). Thanh KI realtime từng điểm hiển thị tại trang riêng <code className="text-amber-300">/ki-live</code>.
            </p>
          </div>

          {/* Attach Any Existing YouTube Video URL/ID */}
          <div className="flex items-center gap-2 w-full sm:w-auto">
            <input
              type="text"
              value={attachInput}
              onChange={(e) => setAttachInput(e.target.value)}
              placeholder="Hoặc dán Link / ID video YouTube đã đăng..."
              className="flex-1 sm:w-72 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-emerald-500 focus:outline-none"
            />
            <button
              type="button"
              disabled={attaching || !attachInput.trim()}
              onClick={() => void handleAttachExisting()}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-3.5 py-2 text-xs font-extrabold text-white cursor-pointer disabled:opacity-50"
            >
              {attaching ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Link2 className="h-3.5 w-3.5" />
              )}
              Gắn Auto-KI
            </button>
          </div>
        </div>

        {trackers.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-800 bg-zinc-950/60 py-8 text-center text-xs text-zinc-400">
            Chưa có video nào đang chạy bộ đếm KI. Hãy bấm{" "}
            <strong className="text-zinc-200">
              Đăng Lên YouTube & Tự Động Cập Nhật KI
            </strong>{" "}
            ở trên (hoặc tự upload video lên kênh rồi dán Link YouTube vào ô bên phải).
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3.5">
            {trackers.map((it) => {
              const pct = Math.min(
                100,
                Math.round((it.currentKi / Math.max(1, it.targetKi)) * 100)
              );
              const reached = it.currentKi >= it.targetKi;
              const stats = it.lastStats || {
                views: 0,
                likes: 0,
                comments: 0,
                channelSubs: it.baselineSubscribers,
                gainedSubs: 0,
              };

              return (
                <div
                  key={it.id}
                  className={`rounded-2xl border p-4 space-y-3 ${
                    reached
                      ? "border-amber-400/70 bg-amber-950/20"
                      : "border-zinc-800 bg-zinc-950/85"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-lg bg-amber-500/20 border border-amber-400/40 px-2.5 py-0.5 text-xs font-extrabold text-amber-300">
                        {it.characterName} Tập #{it.episodeNumber}:{" "}
                        {it.currentStageLabel} ➔ {it.nextStageLabel}
                      </span>
                      <a
                        href={it.watchUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-sky-400 hover:underline"
                      >
                        {it.videoId}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => void handleToggleAutoSync(it)}
                        className={`rounded-lg border px-2.5 py-1 text-[11px] font-bold cursor-pointer ${
                          it.autoSyncEnabled
                            ? "border-emerald-500/50 bg-emerald-950/50 text-emerald-300"
                            : "border-zinc-700 bg-zinc-900 text-zinc-400"
                        }`}
                      >
                        {it.autoSyncEnabled
                          ? `🟢 Đang tự quét mỗi ${it.syncIntervalMin} phút`
                          : "⏸️ Đang tạm dừng"}
                      </button>

                      <a
                        href={`/ki-live?v=${encodeURIComponent(it.videoId)}`}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-lg border border-amber-500/40 bg-amber-950/30 hover:bg-amber-900/40 px-2.5 py-1 text-[11px] font-bold text-amber-200"
                      >
                        Live KI Bar
                        <ExternalLink className="h-3 w-3" />
                      </a>

                      <button
                        type="button"
                        disabled={syncingId === it.id}
                        onClick={() => void handleSyncSingle(it.id, false)}
                        className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1 text-[11px] font-extrabold text-white cursor-pointer disabled:opacity-50"
                        title="Đọc số liệu mới nhất (2 units) & tự đổi Title nếu vừa cán mốc 25/50/75/100%"
                      >
                        <RefreshCw
                          className={`h-3 w-3 ${
                            syncingId === it.id ? "animate-spin" : ""
                          }`}
                        />
                        Quét Số Liệu
                      </button>

                      <button
                        type="button"
                        disabled={syncingId === it.id}
                        onClick={() => void handleSyncSingle(it.id, true)}
                        className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-2.5 py-1 text-[11px] font-bold text-zinc-300 cursor-pointer disabled:opacity-50"
                        title="Ép ghi tiêu đề lên YouTube ngay lúc này (tốn 50 quota units)"
                      >
                        Ép Ghi Title
                      </button>

                      <button
                        type="button"
                        onClick={() => void handleDeleteTracker(it.id)}
                        className="rounded-lg border border-zinc-800 hover:border-red-500/50 p-1.5 text-zinc-500 hover:text-red-400 cursor-pointer"
                        title="Ngừng theo dõi video này"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* KI Progress Bar */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-extrabold text-white">
                        ⚡ Tổng Sức Mạnh Hiện Tại:{" "}
                        <span className="text-amber-300 text-sm">
                          {it.currentKi.toLocaleString("en-US")}
                        </span>{" "}
                        / {it.targetKi.toLocaleString("en-US")} KI ({pct}%)
                      </span>
                      {reached && (
                        <span className="font-extrabold text-amber-300">
                          🎉 ĐÃ ĐỦ KI LÊN CẤP MỚI!
                        </span>
                      )}
                    </div>
                    <div className="h-3 w-full overflow-hidden rounded-full bg-zinc-900 border border-zinc-800">
                      <div
                        style={{ width: `${Math.max(2, pct)}%` }}
                        className={`h-full transition-all duration-500 ${
                          reached
                            ? "bg-gradient-to-r from-amber-400 via-yellow-300 to-emerald-400"
                            : "bg-gradient-to-r from-sky-500 via-violet-500 to-amber-400"
                        }`}
                      />
                    </div>
                    <div className="flex items-center justify-between text-[10px] font-bold pt-0.5">
                      {([0, 25, 50, 75, 100] as const).map((cp) => {
                        const synced = (it.lastSyncedMilestone ?? 0) >= cp;
                        return (
                          <span
                            key={cp}
                            className={
                              synced ? "text-emerald-400" : "text-zinc-500"
                            }
                          >
                            {synced ? "✓" : "○"} Mốc Title {cp}%
                          </span>
                        );
                      })}
                    </div>
                  </div>

                  {/* Live Breakdown Grid */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/70 px-3 py-2">
                      <div className="text-[10px] text-zinc-400">👁️ Views (×{it.weights.view})</div>
                      <div className="font-extrabold text-white">
                        {stats.views.toLocaleString()} ={" "}
                        <span className="text-sky-300">
                          +{(stats.views * it.weights.view).toLocaleString()} KI
                        </span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/70 px-3 py-2">
                      <div className="text-[10px] text-zinc-400">👍 Likes (×{it.weights.like})</div>
                      <div className="font-extrabold text-white">
                        {stats.likes.toLocaleString()} ={" "}
                        <span className="text-emerald-300">
                          +{(stats.likes * it.weights.like).toLocaleString()} KI
                        </span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/70 px-3 py-2">
                      <div className="text-[10px] text-zinc-400">
                        💬 Comments (×{it.weights.comment})
                      </div>
                      <div className="font-extrabold text-white">
                        {stats.comments.toLocaleString()} ={" "}
                        <span className="text-purple-300">
                          +{(stats.comments * it.weights.comment).toLocaleString()} KI
                        </span>
                      </div>
                    </div>
                    <div className="rounded-xl border border-zinc-800/90 bg-zinc-900/70 px-3 py-2">
                      <div className="text-[10px] text-zinc-400">
                        🔔 Sub Mới (×{it.weights.sub})
                      </div>
                      <div className="font-extrabold text-white">
                        +{stats.gainedSubs.toLocaleString()} ={" "}
                        <span className="text-amber-300">
                          +{(stats.gainedSubs * it.weights.sub).toLocaleString()} KI
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Current Synced YouTube Title */}
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400 pt-0.5">
                    <span className="truncate max-w-2xl">
                      📌 Tiêu đề trên YouTube:{" "}
                      <strong className="text-zinc-200">
                        {it.lastSyncedYoutubeTitle || "Chưa đồng bộ"}
                      </strong>
                    </span>
                    {it.lastCheckedAt && (
                      <span>
                        Quét lúc:{" "}
                        {new Date(it.lastCheckedAt).toLocaleTimeString("vi-VN")}
                      </span>
                    )}
                  </div>

                  {it.lastError && (
                    <div className="rounded-lg border border-red-500/40 bg-red-950/30 px-3 py-1.5 text-[11px] text-red-200">
                      ⚠️ {it.lastError}
                    </div>
                  )}

                  {/* 1-Click Next Evolution Episode Button when Goal Reached! */}
                  {reached && (
                    <button
                      type="button"
                      onClick={() => handlePrepareNextEvolutionEpisode(it)}
                      className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-400 to-orange-500 py-2.5 text-xs font-extrabold text-zinc-950 shadow-lg cursor-pointer"
                    >
                      <Sparkles className="h-4 w-4" />
                      Chuyển Lên Dựng Tập #{it.episodeNumber + 1} ({it.nextStageLabel} ➔ Cấp Mới) Ngay!
                      <ArrowRight className="h-4 w-4" />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
