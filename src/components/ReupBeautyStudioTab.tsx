"use client";

import {
  Camera,
  Check,
  Copy,
  Crown,
  Download,
  FolderOpen,
  FolderSync,
  Image as ImageIcon,
  Languages,
  Loader2,
  RefreshCw,
  Sparkles,
  Tag,
  Type,
  Upload,
  Wand2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  generateLocalReupSeoPackage,
  type ReupLanguageMode,
  type ReupVibeCategory,
} from "@/lib/reup-seo-generator";

type EnhanceMode = "beauty_glow" | "crisp_hd" | "raw_hd";
type TextOverlayPreset = "clean_white" | "pink_glow" | "luxury_gold" | "magazine_minimal";
type TextOverlayPosition = "bottom" | "top" | "lower_mid";

interface FrameCandidate {
  id: string;
  rank: number;
  is_best: boolean;
  timestamp_s: number;
  total_score: number;
  face_score: number;
  sharpness_score: number;
  lighting_score: number;
  has_face: boolean;
  reason: string;
  jpg_file: string;
  png_file: string;
  width: number;
  height: number;
  jpg_size_kb: number;
  png_size_kb: number;
  jpeg_quality: number;
}

interface VideoInfo {
  width: number;
  height: number;
  duration_s: number;
  fps: number;
  is_vertical: boolean;
  aspect_label: string;
}

interface FolderVideoEntry {
  name: string;
  fullPath: string;
  sizeMb: number;
  mtimeMs: number;
}

interface ReupBeautyStudioTabProps {
  channelHandle?: string;
  hasGeminiKey?: boolean;
  onNotify: (msg: string) => void;
}

const LANGUAGE_OPTIONS: { id: ReupLanguageMode; label: string; sub: string }[] = [
  { id: "vi", label: "🇻🇳 Tiếng Việt", sub: "Trend VN" },
  { id: "en", label: "🇺🇸 English", sub: "Global View" },
  { id: "vi_en", label: "🌐 Việt + Anh", sub: "Đề xuất kép" },
  { id: "ko", label: "🇰🇷 한국어", sub: "Hàn Quốc" },
  { id: "zh", label: "🇨🇳 中文", sub: "Trung / Douyin" },
  { id: "ja", label: "🇯🇵 日本語", sub: "Nhật Bản" },
];

const VIBE_OPTIONS: { id: ReupVibeCategory; label: string }[] = [
  { id: "visual_smile", label: "✨ Cận Mặt & Nụ Cười" },
  { id: "dance_trend", label: "💃 Nhảy / Vũ Đạo" },
  { id: "street_fashion", label: "👗 Street Style / OOTD" },
  { id: "cosplay_trad", label: "🎀 Áo Dài / Cosplay" },
  { id: "beach_travel", label: "🏖️ Đi Biển / Du Lịch" },
  { id: "gym_sport", label: "🏋️‍♀️ Gym / Dáng Đẹp" },
];

const OVERLAY_PRESETS: {
  id: TextOverlayPreset;
  label: string;
  fill: string;
  accentFill: string;
  stroke: string;
  glow: string;
}[] = [
  {
    id: "clean_white",
    label: "Trắng Sang Trọng",
    fill: "#FFFFFF",
    accentFill: "#FFE066",
    stroke: "rgba(10, 12, 18, 0.92)",
    glow: "rgba(0, 0, 0, 0.85)",
  },
  {
    id: "pink_glow",
    label: "Hồng Hàn Quốc",
    fill: "#FFF5F8",
    accentFill: "#FF6B9D",
    stroke: "rgba(48, 8, 28, 0.9)",
    glow: "rgba(255, 64, 129, 0.55)",
  },
  {
    id: "luxury_gold",
    label: "Vàng Gold Nổi Bật",
    fill: "#FFFFFF",
    accentFill: "#FFD43B",
    stroke: "rgba(12, 10, 8, 0.95)",
    glow: "rgba(0, 0, 0, 0.9)",
  },
  {
    id: "magazine_minimal",
    label: "Tạp Chí Minimal",
    fill: "#F8FAFC",
    accentFill: "#E2E8F0",
    stroke: "rgba(15, 23, 42, 0.72)",
    glow: "rgba(0, 0, 0, 0.65)",
  },
];

function formatSeconds(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`;
}

export function ReupBeautyStudioTab({
  channelHandle,
  hasGeminiKey,
  onNotify,
}: ReupBeautyStudioTabProps) {
  // Video & Frame Scanner state
  const [sessionId, setSessionId] = useState<string>("");
  const [serverVideoPath, setServerVideoPath] = useState<string>("");
  const [videoDisplayName, setVideoDisplayName] = useState<string>("");
  const [videoPreviewUrl, setVideoPreviewUrl] = useState<string>("");
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [enhanceMode, setEnhanceMode] = useState<EnhanceMode>("beauty_glow");
  const [scanning, setScanning] = useState(false);
  const [extractingCustom, setExtractingCustom] = useState(false);
  const [candidates, setCandidates] = useState<FrameCandidate[]>([]);
  const [selectedCandidateId, setSelectedCandidateId] = useState<string>("");
  const [isDragging, setIsDragging] = useState(false);
  const [currentPlayheadSec, setCurrentPlayheadSec] = useState(0);

  // Batch local folder scanner state
  const [showFolderPanel, setShowFolderPanel] = useState(false);
  const [folderInput, setFolderInput] = useState("~/Downloads");
  const [folderFiles, setFolderFiles] = useState<FolderVideoEntry[]>([]);
  const [loadingFolder, setLoadingFolder] = useState(false);

  // Optional Text Overlay state (default OFF = 100% clean HD photo!)
  const [enableTextOverlay, setEnableTextOverlay] = useState(false);
  const [overlayLine1, setOverlayLine1] = useState("VISUAL CỰC PHẨM");
  const [overlayLine2, setOverlayLine2] = useState("XEM LÀ DÍNH ✨");
  const [overlayBadge, setOverlayBadge] = useState("");
  const [overlayPreset, setOverlayPreset] = useState<TextOverlayPreset>("clean_white");
  const [overlayPosition, setOverlayPosition] = useState<TextOverlayPosition>("bottom");
  const [overlayFontScale, setOverlayFontScale] = useState<number>(100);

  // SEO Title & Tags generator state
  const [language, setLanguage] = useState<ReupLanguageMode>("vi");
  const [vibe, setVibe] = useState<ReupVibeCategory>("visual_smile");
  const [customNote, setCustomNote] = useState("");
  const [isShortFormat, setIsShortFormat] = useState(true);
  const [seoSeed, setSeoSeed] = useState(0);
  const [aiPolishing, setAiPolishing] = useState(false);
  const [aiOverrideSeo, setAiOverrideSeo] = useState<ReturnType<
    typeof generateLocalReupSeoPackage
  > | null>(null);
  const [selectedTitleIdx, setSelectedTitleIdx] = useState(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [savingBundle, setSavingBundle] = useState(false);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const loadedBaseImgRef = useRef<HTMLImageElement | null>(null);
  const [canvasReadyTick, setCanvasReadyTick] = useState(0);

  const selectedCandidate = useMemo(
    () =>
      candidates.find((c) => c.id === selectedCandidateId) ||
      candidates[0] ||
      null,
    [candidates, selectedCandidateId]
  );

  // Auto-sync Shorts vs Horizontal format when video loads
  useEffect(() => {
    if (videoInfo) {
      setIsShortFormat(videoInfo.is_vertical);
    }
  }, [videoInfo]);

  // Instant deterministic SEO package (or AI-polished override until inputs change)
  const localSeo = useMemo(
    () =>
      generateLocalReupSeoPackage({
        language,
        vibe,
        customNote,
        isShort: isShortFormat,
        channelHandle,
        seed: seoSeed,
      }),
    [language, vibe, customNote, isShortFormat, channelHandle, seoSeed]
  );

  useEffect(() => {
    setAiOverrideSeo(null);
  }, [language, vibe, customNote, isShortFormat, seoSeed]);

  const activeSeo = aiOverrideSeo || localSeo;

  const markCopied = useCallback(
    (key: string, text: string, label: string) => {
      navigator.clipboard.writeText(text);
      setCopiedKey(key);
      onNotify(`📋 Đã copy ${label}!`);
      setTimeout(() => {
        setCopiedKey((prev) => (prev === key ? null : prev));
      }, 1800);
    },
    [onNotify]
  );

  const selectedImageUrl = useMemo(() => {
    if (!sessionId || !selectedCandidate) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      sessionId
    )}&file=${encodeURIComponent(selectedCandidate.jpg_file)}`;
  }, [sessionId, selectedCandidate]);

  // Load base HD image into memory whenever selectedCandidate changes so Canvas renders overlays in 0ms
  useEffect(() => {
    if (!selectedImageUrl) {
      loadedBaseImgRef.current = null;
      return;
    }
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      loadedBaseImgRef.current = img;
      setCanvasReadyTick((t) => t + 1);
    };
    img.src = selectedImageUrl;
  }, [selectedImageUrl]);

  // Draw HD Thumbnail (+ optional text overlay) onto full-resolution Canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const img = loadedBaseImgRef.current;
    if (!canvas || !img) return;

    const w = img.naturalWidth || 1080;
    const h = img.naturalHeight || 1920;
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, w, h);
    ctx.drawImage(img, 0, 0, w, h);

    if (!enableTextOverlay) return;

    const l1 = overlayLine1.trim();
    const l2 = overlayLine2.trim();
    const badge = overlayBadge.trim();
    if (!l1 && !l2 && !badge) return;

    const preset =
      OVERLAY_PRESETS.find((p) => p.id === overlayPreset) || OVERLAY_PRESETS[0];

    // Soft readability gradient scrim at chosen position
    const grad =
      overlayPosition === "top"
        ? ctx.createLinearGradient(0, 0, 0, h * 0.42)
        : ctx.createLinearGradient(0, h * 0.52, 0, h);
    if (overlayPosition === "top") {
      grad.addColorStop(0, "rgba(0, 0, 0, 0.62)");
      grad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h * 0.42);
    } else {
      grad.addColorStop(0, "rgba(0, 0, 0, 0)");
      grad.addColorStop(1, "rgba(0, 0, 0, 0.68)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, h * 0.52, w, h * 0.48);
    }

    const shortSide = Math.min(w, h);
    const scaleFactor = (overlayFontScale / 100) * (shortSide / 1080);
    const mainFontPx = Math.round((w < h ? 82 : 76) * scaleFactor);
    const lineStep = Math.round(mainFontPx * 1.18);

    const lines = [
      l1 ? { text: l1, color: preset.fill } : null,
      l2 ? { text: l2, color: preset.accentFill } : null,
    ].filter(Boolean) as { text: string; color: string }[];

    let baseY =
      overlayPosition === "top"
        ? Math.round(h * 0.12)
        : overlayPosition === "lower_mid"
        ? Math.round(h * 0.68)
        : Math.round(h * 0.84 - (lines.length - 1) * lineStep);

    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    if (badge) {
      const badgeFontPx = Math.max(22, Math.round(30 * scaleFactor));
      ctx.font = `800 ${badgeFontPx}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      const bw = ctx.measureText(badge.toUpperCase()).width + badgeFontPx * 1.5;
      const bh = badgeFontPx * 1.65;
      const bx = (w - bw) / 2;
      const by = baseY - lineStep * 0.78 - bh / 2;

      ctx.save();
      ctx.fillStyle = "rgba(225, 29, 72, 0.92)";
      ctx.beginPath();
      ctx.roundRect(bx, by, bw, bh, bh / 2);
      ctx.fill();
      ctx.fillStyle = "#FFFFFF";
      ctx.fillText(badge.toUpperCase(), w / 2, by + bh / 2 + 1);
      ctx.restore();
    }

    for (let i = 0; i < lines.length; i++) {
      const { text, color } = lines[i];
      let fontPx = mainFontPx;
      ctx.font = `900 ${fontPx}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      while (fontPx > 32 && ctx.measureText(text).width > w * 0.88) {
        fontPx -= 3;
        ctx.font = `900 ${fontPx}px system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      }
      const y = baseY + i * lineStep;

      ctx.save();
      ctx.shadowColor = preset.glow;
      ctx.shadowBlur = Math.round(22 * scaleFactor);
      ctx.shadowOffsetY = Math.round(6 * scaleFactor);
      ctx.lineJoin = "round";
      ctx.lineWidth = Math.max(4, Math.round(11 * scaleFactor));
      ctx.strokeStyle = preset.stroke;
      ctx.strokeText(text, w / 2, y);

      ctx.shadowBlur = 0;
      ctx.fillStyle = color;
      ctx.fillText(text, w / 2, y);
      ctx.restore();
    }
  }, [
    canvasReadyTick,
    enableTextOverlay,
    overlayLine1,
    overlayLine2,
    overlayBadge,
    overlayPreset,
    overlayPosition,
    overlayFontScale,
  ]);

  const handleUploadFile = useCallback(
    async (file: File, modeOverride?: EnhanceMode) => {
      const mode = modeOverride || enhanceMode;
      const localObjUrl = URL.createObjectURL(file);
      setVideoPreviewUrl((prev) => {
        if (prev.startsWith("blob:")) URL.revokeObjectURL(prev);
        return localObjUrl;
      });
      setVideoDisplayName(file.name);
      setScanning(true);

      try {
        const res = await fetch(
          `/api/reup-tool/upload?name=${encodeURIComponent(
            file.name
          )}&enhance=${encodeURIComponent(mode)}`,
          {
            method: "POST",
            body: file,
          }
        );
        const json = await res.json();
        if (!res.ok || !json.ok) {
          throw new Error(json.error || "Không thể quét khung hình video");
        }
        setSessionId(json.sessionId);
        setServerVideoPath(json.videoPath);
        setVideoInfo(json.video_info || null);
        const cands: FrameCandidate[] = json.candidates || [];
        setCandidates(cands);
        if (cands[0]) {
          setSelectedCandidateId(cands[0].id);
          if (videoRef.current) {
            videoRef.current.currentTime = cands[0].timestamp_s;
          }
        }
        onNotify(
          `✨ Đã lọc xong ${cands.length} khung hình HD đẹp nhất từ "${file.name}"!`
        );
      } catch (err) {
        onNotify(err instanceof Error ? err.message : "Lỗi phân tích video");
      } finally {
        setScanning(false);
      }
    },
    [enhanceMode, onNotify]
  );

  const handleScanLocalPath = useCallback(
    async (fullPath: string, modeOverride?: EnhanceMode) => {
      const mode = modeOverride || enhanceMode;
      setScanning(true);
      setVideoDisplayName(fullPath.split("/").pop() || "video.mp4");
      setVideoPreviewUrl(
        `/api/reup-tool/media?videoPath=${encodeURIComponent(fullPath)}`
      );

      try {
        const res = await fetch("/api/reup-tool/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "scanLocalPath",
            videoPath: fullPath,
            enhanceMode: mode,
          }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
          throw new Error(json.error || "Không thể quét video");
        }
        setSessionId(json.sessionId);
        setServerVideoPath(json.videoPath);
        setVideoInfo(json.video_info || null);
        const cands: FrameCandidate[] = json.candidates || [];
        setCandidates(cands);
        if (cands[0]) {
          setSelectedCandidateId(cands[0].id);
          if (videoRef.current) {
            videoRef.current.currentTime = cands[0].timestamp_s;
          }
        }
        onNotify(
          `✨ Đã chọn ra khung hình HD đẹp nhất (#1: ${cands[0]?.total_score || 0} điểm)!`
        );
      } catch (err) {
        onNotify(err instanceof Error ? err.message : "Lỗi quét đường dẫn video");
      } finally {
        setScanning(false);
      }
    },
    [enhanceMode, onNotify]
  );

  const handleLoadFolderList = useCallback(async () => {
    setLoadingFolder(true);
    try {
      const res = await fetch("/api/reup-tool/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "listFolder",
          folderPath: folderInput,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        throw new Error(json.error || "Không đọc được thư mục");
      }
      setFolderFiles(json.files || []);
      if ((json.files || []).length === 0) {
        onNotify("Không tìm thấy file video (.mp4/.mov/.webm) nào trong thư mục này.");
      }
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi đọc thư mục");
    } finally {
      setLoadingFolder(false);
    }
  }, [folderInput, onNotify]);

  const handleSwitchEnhanceMode = useCallback(
    async (newMode: EnhanceMode) => {
      setEnhanceMode(newMode);
      if (!serverVideoPath) return;
      await handleScanLocalPath(serverVideoPath, newMode);
    },
    [serverVideoPath, handleScanLocalPath]
  );

  const handleSnapCurrentVideoFrame = useCallback(async () => {
    if (!serverVideoPath || !videoRef.current) return;
    const tSec = videoRef.current.currentTime || 0;
    setExtractingCustom(true);
    try {
      const res = await fetch("/api/reup-tool/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "extractCustomTime",
          videoPath: serverVideoPath,
          sessionId,
          timeSec: tSec,
          enhanceMode,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        throw new Error(json.error || "Lỗi cắt khung hình");
      }
      const newCand: FrameCandidate = json.candidate;
      setCandidates((prev) => [newCand, ...prev]);
      setSelectedCandidateId(newCand.id);
      onNotify(`📸 Đã cắt & nâng nét HD khung hình tại ${formatSeconds(tSec)}!`);
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi cắt khung hình");
    } finally {
      setExtractingCustom(false);
    }
  }, [serverVideoPath, sessionId, enhanceMode, onNotify]);

  const handleDownloadThumbnail = useCallback(
    (format: "jpg" | "png") => {
      if (!selectedCandidate || !sessionId) return;
      const baseStem =
        (videoDisplayName || "reup_video").replace(/\.[^.]+$/, "") || "reup_video";

      // If text overlay is OFF, download exact server-side 4:4:4 RGB JPG (< 2MB) or lossless PNG!
      if (!enableTextOverlay) {
        const file =
          format === "png" ? selectedCandidate.png_file : selectedCandidate.jpg_file;
        const dlName = `${baseStem}_thumbnail_hd.${format}`;
        const a = document.createElement("a");
        a.href = `/api/reup-tool/media?session=${encodeURIComponent(
          sessionId
        )}&file=${encodeURIComponent(file)}&download=${encodeURIComponent(dlName)}`;
        a.download = dlName;
        document.body.appendChild(a);
        a.click();
        a.remove();
        onNotify(`⬇️ Đang tải ${dlName}!`);
        return;
      }

      // With text overlay ON, export directly from full-HD canvas
      const canvas = canvasRef.current;
      if (!canvas) return;
      const mime = format === "png" ? "image/png" : "image/jpeg";
      const dataUrl = canvas.toDataURL(mime, 0.94);
      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = `${baseStem}_thumbnail_hd.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      onNotify(`⬇️ Đã tải Thumbnail HD kèm chữ (.${format.toUpperCase()})!`);
    },
    [selectedCandidate, sessionId, videoDisplayName, enableTextOverlay, onNotify]
  );

  const buildFullSeoText = useCallback(() => {
    const chosenTitle = activeSeo.titles[selectedTitleIdx] || activeSeo.titles[0] || "";
    return [
      `=== TIÊU ĐỀ ĐÃ CHỌN ===`,
      chosenTitle,
      ``,
      `=== 6 PHƯƠNG ÁN TIÊU ĐỀ GỢI Ý ===`,
      ...activeSeo.titles.map((t, i) => `${i + 1}. ${t}`),
      ``,
      `=== MÔ TẢ VIDEO (DESCRIPTION) ===`,
      activeSeo.description,
      ``,
      `=== HASHTAGS ===`,
      activeSeo.hashtags.join(" "),
      ``,
      `=== THẺ TAGS YOUTUBE STUDIO (Copy dán thẳng vào ô Thẻ - ${activeSeo.studioTagsCharCount}/500 ký tự) ===`,
      activeSeo.studioTagsCsv,
      ``,
    ].join("\n");
  }, [activeSeo, selectedTitleIdx]);

  const handleSaveBundleToMac = useCallback(async () => {
    setSavingBundle(true);
    try {
      let dataUrl: string | undefined;
      if (enableTextOverlay && canvasRef.current) {
        dataUrl = canvasRef.current.toDataURL("image/jpeg", 0.94);
      }
      const res = await fetch("/api/reup-tool/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "exportBundleToDisk",
          baseName: videoDisplayName || "reup_video",
          sessionId,
          imageFile: selectedCandidate?.jpg_file,
          dataUrl,
          seoTextContent: buildFullSeoText(),
          revealInFinder: true,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        throw new Error(json.error || "Không thể lưu gói xuất bản");
      }
      onNotify(
        `💾 Đã lưu Thumbnail HD + File Tiêu đề/Tags vào ${json.targetDir} (đã mở Finder)!`
      );
    } catch (err) {
      onNotify(err instanceof Error ? err.message : "Lỗi lưu file");
    } finally {
      setSavingBundle(false);
    }
  }, [
    enableTextOverlay,
    videoDisplayName,
    sessionId,
    selectedCandidate,
    buildFullSeoText,
    onNotify,
  ]);

  const handleAiPolishSeo = useCallback(async () => {
    setAiPolishing(true);
    try {
      const res = await fetch("/api/reup-tool/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "aiPolishSeo",
          language,
          vibe,
          customNote,
          isShort: isShortFormat,
          channelHandle,
          seed: seoSeed + 1,
        }),
      });
      const json = await res.json();
      if (res.ok && json.ok && json.seo) {
        setAiOverrideSeo(json.seo);
        setSelectedTitleIdx(0);
        onNotify(
          json.usedAi
            ? "✨ AI đã viết bộ Tiêu đề & Tags mới!"
            : "🔄 Đã làm mới bộ Tiêu đề & Tags (chế độ Local 0₫)!"
        );
      }
    } catch {
      setSeoSeed((s) => s + 1);
    } finally {
      setAiPolishing(false);
    }
  }, [language, vibe, customNote, isShortFormat, channelHandle, seoSeed, onNotify]);

  const stepVideoFrame = (deltaSec: number) => {
    if (!videoRef.current) return;
    videoRef.current.pause();
    const dur = videoRef.current.duration || 60;
    videoRef.current.currentTime = Math.max(
      0,
      Math.min(dur - 0.02, videoRef.current.currentTime + deltaSec)
    );
  };

  return (
    <div className="space-y-6">
      {/* Top Banner & Dropzone / Folder Picker */}
      <div className="rounded-2xl border border-pink-500/25 bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-rose-950/25 p-5 shadow-xl">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 mb-4">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-pink-500/30 bg-pink-500/10 px-3 py-1 text-[11px] font-bold text-pink-300 mb-2">
              <Sparkles className="h-3.5 w-3.5" />
              Tool Độc Lập Cho Video Có Sẵn • Nhận Diện Khuôn Mặt & Nét Mắt YuNet HD
            </div>
            <h2 className="text-lg sm:text-xl font-extrabold text-white">
              Cắt Thumbnail HD Đẹp Nhất & Render Tiêu Đề / Tags Reup
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5">
              Tự động chấm điểm khuôn mặt, ánh mắt, góc nghiêng & ánh sáng trên toàn bộ video để lọc ra khung hình sắc nét nhất (nâng chuẩn Full HD ≥ 1080p) kèm bộ Tiêu đề & Tags đa ngôn ngữ.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {/* Enhance mode selector */}
            <div className="flex items-center rounded-xl border border-zinc-800 bg-zinc-950 p-1 text-xs">
              {(
                [
                  { id: "beauty_glow", label: "✨ Trong trẻo HD" },
                  { id: "crisp_hd", label: "🔍 Sắc nét HD" },
                  { id: "raw_hd", label: "🎞️ Màu gốc HD" },
                ] as { id: EnhanceMode; label: string }[]
              ).map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleSwitchEnhanceMode(m.id)}
                  disabled={scanning}
                  className={`rounded-lg px-2.5 py-1.5 font-bold transition cursor-pointer ${
                    enhanceMode === m.id
                      ? "bg-pink-600 text-white shadow"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={() => {
                setShowFolderPanel((v) => {
                  const next = !v;
                  if (next && folderFiles.length === 0) {
                    setTimeout(() => handleLoadFolderList(), 50);
                  }
                  return next;
                });
              }}
              className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                showFolderPanel
                  ? "border-pink-500 bg-pink-500/15 text-pink-200"
                  : "border-zinc-700 bg-zinc-900 text-zinc-200 hover:bg-zinc-800"
              }`}
            >
              <FolderOpen className="h-4 w-4" />
              Quét Thư Mục Máy Mac
            </button>
          </div>
        </div>

        {/* Drag & Drop Video Zone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            const f = e.dataTransfer.files?.[0];
            if (f) handleUploadFile(f);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`rounded-2xl border-2 border-dashed p-5 text-center transition cursor-pointer ${
            isDragging
              ? "border-pink-400 bg-pink-500/15"
              : "border-zinc-700/80 bg-zinc-950/60 hover:border-pink-500/60 hover:bg-zinc-900/70"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) handleUploadFile(f);
              e.target.value = "";
            }}
          />
          {scanning ? (
            <div className="flex flex-col items-center justify-center py-2 space-y-2">
              <Loader2 className="h-7 w-7 animate-spin text-pink-400" />
              <div className="text-sm font-bold text-white">
                Đang quét 54 khung hình & chấm điểm khuôn mặt / độ nét HD cho &ldquo;{videoDisplayName}&rdquo;...
              </div>
              <div className="text-xs text-zinc-400">
                Tự động loại bỏ khung hình nhắm mắt, rung mờ và thiếu sáng
              </div>
            </div>
          ) : (
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 py-1">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-pink-500/15 text-pink-400 border border-pink-500/30">
                <Upload className="h-5 w-5" />
              </div>
              <div className="text-left">
                <div className="text-sm font-bold text-white">
                  {videoDisplayName
                    ? `Đang mở: ${videoDisplayName} — Bấm hoặc kéo thả video khác vào đây`
                    : "Kéo thả video có sẵn (.mp4, .mov, .webm) vào đây hoặc bấm để chọn file"}
                </div>
                <div className="text-xs text-zinc-400">
                  Hỗ trợ cả video dọc Shorts (9:16) lẫn video ngang (16:9) • Tự động nâng nét chuẩn Full HD ≥ 1080p
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Optional Local Folder Batch Browser */}
        {showFolderPanel && (
          <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/90 p-3.5 space-y-3">
            <div className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={folderInput}
                onChange={(e) => setFolderInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleLoadFolderList();
                }}
                placeholder="Nhập đường dẫn thư mục chứa video trên Mac (VD: ~/Downloads)"
                className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-pink-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={handleLoadFolderList}
                disabled={loadingFolder}
                className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 px-4 py-2 text-xs font-bold text-white cursor-pointer"
              >
                {loadingFolder ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <FolderSync className="h-3.5 w-3.5" />
                )}
                Liệt kê Video
              </button>
            </div>

            {folderFiles.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 max-h-44 overflow-y-auto pr-1">
                {folderFiles.map((f) => {
                  const active = serverVideoPath === f.fullPath;
                  return (
                    <button
                      key={f.fullPath}
                      type="button"
                      onClick={() => handleScanLocalPath(f.fullPath)}
                      className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-left text-xs transition cursor-pointer ${
                        active
                          ? "border-pink-500 bg-pink-500/15 text-white"
                          : "border-zinc-800 bg-zinc-900/70 text-zinc-300 hover:border-zinc-700 hover:text-white"
                      }`}
                    >
                      <span className="truncate font-medium">{f.name}</span>
                      <span className="shrink-0 text-[10px] text-zinc-400">
                        {f.sizeMb} MB
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main 2-Column Workspace: Left = HD Thumbnail Picker & Editor | Right = Multi-Language Titles & Tags */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        {/* LEFT COLUMN (7 cols): HD Thumbnail Candidates, Live Canvas & Scrubbing */}
        <div className="xl:col-span-7 space-y-5">
          {selectedCandidate && sessionId ? (
            <>
              {/* Selected HD Thumbnail Preview + Export Controls */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 sm:p-5 space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/20 border border-amber-500/40 px-2.5 py-0.5 text-[11px] font-extrabold text-amber-300">
                        <Crown className="h-3 w-3" />
                        {selectedCandidate.is_best
                          ? "Khung Đẹp Nhất #1"
                          : selectedCandidate.rank > 0
                          ? `Top #${selectedCandidate.rank}`
                          : "Khung Tự Chọn"}
                      </span>
                      <span className="text-xs font-bold text-emerald-400">
                        Điểm thẩm mỹ: {selectedCandidate.total_score}/100
                      </span>
                      <span className="text-xs text-zinc-400">
                        • {selectedCandidate.width}×{selectedCandidate.height} HD (
                        {selectedCandidate.jpg_size_kb} KB)
                      </span>
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-1">
                      ⏱ Thời điểm {formatSeconds(selectedCandidate.timestamp_s)} —{" "}
                      {selectedCandidate.reason} (Độ nét:{" "}
                      {selectedCandidate.sharpness_score}% • Ánh sáng:{" "}
                      {selectedCandidate.lighting_score}%)
                    </p>
                  </div>

                  {/* Clean vs Text Overlay Mode Switch */}
                  <div className="flex items-center rounded-xl border border-zinc-800 bg-zinc-950 p-1 text-xs">
                    <button
                      type="button"
                      onClick={() => setEnableTextOverlay(false)}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-bold transition cursor-pointer ${
                        !enableTextOverlay
                          ? "bg-emerald-600 text-white"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <ImageIcon className="h-3.5 w-3.5" />
                      Ảnh Sạch 100%
                    </button>
                    <button
                      type="button"
                      onClick={() => setEnableTextOverlay(true)}
                      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-bold transition cursor-pointer ${
                        enableTextOverlay
                          ? "bg-pink-600 text-white"
                          : "text-zinc-400 hover:text-white"
                      }`}
                    >
                      <Type className="h-3.5 w-3.5" />
                      Chèn Chữ Đẹp
                    </button>
                  </div>
                </div>

                {/* Canvas Display + Optional Overlay Controls */}
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-start">
                  <div
                    className={`${
                      enableTextOverlay ? "md:col-span-7" : "md:col-span-12"
                    } flex justify-center rounded-xl border border-zinc-800/90 bg-zinc-950 p-3`}
                  >
                    <canvas
                      ref={canvasRef}
                      className={`${
                        selectedCandidate.height > selectedCandidate.width
                          ? "max-h-[520px] w-auto"
                          : "w-full max-h-[420px] object-contain"
                      } rounded-lg shadow-2xl`}
                    />
                  </div>

                  {enableTextOverlay && (
                    <div className="md:col-span-5 space-y-3 rounded-xl border border-zinc-800 bg-zinc-950/80 p-3.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-white">
                          Tùy chỉnh chữ trên Thumbnail
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const raw = (
                              activeSeo.titles[selectedTitleIdx] ||
                              activeSeo.titles[0] ||
                              ""
                            )
                              .replace(/#shorts/gi, "")
                              .split("|")[0]
                              .trim();
                            const words = raw.split(/\s+/);
                            const mid = Math.ceil(words.length / 2);
                            setOverlayLine1(words.slice(0, mid).join(" ").slice(0, 26));
                            setOverlayLine2(words.slice(mid).join(" ").slice(0, 26));
                          }}
                          className="text-[11px] font-semibold text-pink-400 hover:text-pink-300 cursor-pointer"
                        >
                          Lấy từ tiêu đề
                        </button>
                      </div>

                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-1">
                          Dòng chính (Dòng 1)
                        </label>
                        <input
                          type="text"
                          value={overlayLine1}
                          onChange={(e) => setOverlayLine1(e.target.value)}
                          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-white focus:border-pink-500 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-1">
                          Dòng nhấn màu (Dòng 2)
                        </label>
                        <input
                          type="text"
                          value={overlayLine2}
                          onChange={(e) => setOverlayLine2(e.target.value)}
                          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-white focus:border-pink-500 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-1">
                          Nhãn nhỏ phía trên (Tùy chọn, VD: FULL HD / HOT)
                        </label>
                        <input
                          type="text"
                          value={overlayBadge}
                          onChange={(e) => setOverlayBadge(e.target.value)}
                          placeholder="Để trống nếu không cần"
                          className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-xs text-white focus:border-pink-500 focus:outline-none"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] text-zinc-400 mb-1">
                          Phong cách màu chữ
                        </label>
                        <div className="grid grid-cols-2 gap-1.5">
                          {OVERLAY_PRESETS.map((p) => (
                            <button
                              key={p.id}
                              type="button"
                              onClick={() => setOverlayPreset(p.id)}
                              className={`rounded-lg border px-2 py-1.5 text-[11px] font-bold transition cursor-pointer ${
                                overlayPreset === p.id
                                  ? "border-pink-500 bg-pink-500/15 text-white"
                                  : "border-zinc-800 bg-zinc-900 text-zinc-400 hover:text-white"
                              }`}
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <label className="block text-[10px] text-zinc-400 mb-1">
                            Vị trí chữ
                          </label>
                          <select
                            value={overlayPosition}
                            onChange={(e) =>
                              setOverlayPosition(
                                e.target.value as TextOverlayPosition
                              )
                            }
                            className="w-full rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-white"
                          >
                            <option value="bottom">Dưới cùng</option>
                            <option value="lower_mid">Giữa dưới</option>
                            <option value="top">Trên cùng</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[10px] text-zinc-400 mb-1">
                            Cỡ chữ ({overlayFontScale}%)
                          </label>
                          <input
                            type="range"
                            min={65}
                            max={135}
                            value={overlayFontScale}
                            onChange={(e) =>
                              setOverlayFontScale(Number(e.target.value))
                            }
                            className="w-full accent-pink-500 mt-1.5"
                          />
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Download HD Thumbnail Buttons */}
                <div className="flex flex-wrap items-center gap-2.5 pt-1">
                  <button
                    type="button"
                    onClick={() => handleDownloadThumbnail("jpg")}
                    className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-pink-600 to-rose-600 hover:from-pink-500 hover:to-rose-500 px-4 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-pink-600/20 cursor-pointer"
                  >
                    <Download className="h-4 w-4" />
                    Tải Thumbnail HD (.JPG chuẩn YouTube)
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDownloadThumbnail("png")}
                    className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3.5 py-2.5 text-xs font-bold text-zinc-100 cursor-pointer"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Tải Bản Nét Căng (.PNG)
                  </button>
                </div>
              </div>

              {/* Top 6 Candidate Strip */}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-extrabold uppercase tracking-wider text-zinc-300">
                    Top {candidates.length} Khung Hình Đẹp Nhất Đã Lọc Tự Động
                  </h3>
                  <span className="text-[11px] text-zinc-400">
                    Bấm để đổi nhanh khung hình
                  </span>
                </div>
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5">
                  {candidates.map((cand) => {
                    const isSelected = cand.id === selectedCandidate.id;
                    const thumbUrl = `/api/reup-tool/media?session=${encodeURIComponent(
                      sessionId
                    )}&file=${encodeURIComponent(cand.jpg_file)}`;
                    return (
                      <button
                        key={cand.id}
                        type="button"
                        onClick={() => {
                          setSelectedCandidateId(cand.id);
                          if (videoRef.current) {
                            videoRef.current.currentTime = cand.timestamp_s;
                          }
                        }}
                        className={`group relative rounded-xl overflow-hidden border-2 transition cursor-pointer text-left ${
                          isSelected
                            ? "border-pink-500 ring-2 ring-pink-500/30"
                            : "border-zinc-800 hover:border-zinc-600"
                        }`}
                      >
                        <img
                          src={thumbUrl}
                          alt={`Frame ${cand.timestamp_s}s`}
                          className={`w-full ${
                            cand.height > cand.width ? "aspect-[9/16]" : "aspect-video"
                          } object-cover`}
                        />
                        {cand.is_best && (
                          <span className="absolute top-1.5 left-1.5 rounded-md bg-amber-500 px-1.5 py-0.5 text-[9px] font-black text-zinc-950 shadow">
                            #1 ĐẸP NHẤT
                          </span>
                        )}
                        <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-1.5">
                          <div className="text-[10px] font-extrabold text-white">
                            {cand.total_score}đ
                          </div>
                          <div className="text-[9px] text-zinc-300">
                            {formatSeconds(cand.timestamp_s)}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          ) : (
            <div className="rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-8 text-center space-y-2">
              <Camera className="h-8 w-8 text-pink-400/70 mx-auto" />
              <div className="text-sm font-bold text-zinc-200">
                Chưa có video nào được chọn
              </div>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                Hãy kéo thả 1 video có sẵn vào khung phía trên (hoặc bấm &ldquo;Quét Thư Mục Máy Mac&rdquo;). Hệ thống sẽ tự động chấm điểm từng khung mặt để cắt ra bức Thumbnail HD đẹp nhất cho bạn.
              </p>
            </div>
          )}

          {/* Precision Manual Video Scrubber (if user wants to hand-pick an extra moment) */}
          {videoPreviewUrl && (
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="text-xs font-extrabold text-white">
                    Tua Chọn Thêm Khoảnh Khắc Thủ Công ({formatSeconds(currentPlayheadSec)})
                  </h3>
                  <p className="text-[11px] text-zinc-400">
                    Dừng video ở bất kỳ khoảnh khắc nào bạn thích rồi bấm &ldquo;Cắt Khung Này Chuẩn HD&rdquo;
                  </p>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => stepVideoFrame(-0.1)}
                    className="rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 text-[11px] font-bold text-zinc-200 cursor-pointer"
                  >
                    -0.1s
                  </button>
                  <button
                    type="button"
                    onClick={() => stepVideoFrame(0.1)}
                    className="rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 text-[11px] font-bold text-zinc-200 cursor-pointer"
                  >
                    +0.1s
                  </button>
                  <button
                    type="button"
                    onClick={handleSnapCurrentVideoFrame}
                    disabled={extractingCustom || !serverVideoPath}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-pink-600 hover:bg-pink-500 disabled:opacity-50 px-3 py-1.5 text-xs font-extrabold text-white cursor-pointer"
                  >
                    {extractingCustom ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Camera className="h-3.5 w-3.5" />
                    )}
                    Cắt Khung Này Chuẩn HD
                  </button>
                </div>
              </div>

              <video
                ref={videoRef}
                src={videoPreviewUrl}
                controls
                playsInline
                onTimeUpdate={(e) =>
                  setCurrentPlayheadSec(e.currentTarget.currentTime)
                }
                className="w-full max-h-72 rounded-xl bg-black object-contain"
              />
            </div>
          )}
        </div>

        {/* RIGHT COLUMN (5 cols): Multi-Language Title, Description & Tags Generator */}
        <div className="xl:col-span-5 rounded-2xl border border-zinc-800 bg-zinc-900/75 p-4 sm:p-5 space-y-5">
          <div className="flex items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-extrabold text-white flex items-center gap-2">
                <Languages className="h-4 w-4 text-pink-400" />
                Render Tiêu Đề, Mô Tả & Bộ Tags Chuẩn SEO
              </h3>
              <p className="text-[11px] text-zinc-400">
                Tạo tức thì 6 tiêu đề hút click + Hashtags + Thẻ Tags YouTube (&lt; 500 ký tự)
              </p>
            </div>

            {/* Shorts vs Long Video Toggle */}
            <div className="flex rounded-xl border border-zinc-800 bg-zinc-950 p-0.5 text-[11px]">
              <button
                type="button"
                onClick={() => setIsShortFormat(true)}
                className={`rounded-lg px-2.5 py-1 font-bold cursor-pointer ${
                  isShortFormat
                    ? "bg-red-600 text-white"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Shorts
              </button>
              <button
                type="button"
                onClick={() => setIsShortFormat(false)}
                className={`rounded-lg px-2.5 py-1 font-bold cursor-pointer ${
                  !isShortFormat
                    ? "bg-red-600 text-white"
                    : "text-zinc-400 hover:text-white"
                }`}
              >
                Video Ngang
              </button>
            </div>
          </div>

          {/* 1. Language Selector */}
          <div className="space-y-1.5">
            <label className="block text-[11px] font-bold text-zinc-300">
              1. Ngôn ngữ kênh đăng
            </label>
            <div className="grid grid-cols-3 gap-1.5">
              {LANGUAGE_OPTIONS.map((lang) => (
                <button
                  key={lang.id}
                  type="button"
                  onClick={() => setLanguage(lang.id)}
                  className={`rounded-xl border px-2.5 py-2 text-left transition cursor-pointer ${
                    language === lang.id
                      ? "border-pink-500 bg-pink-500/15 text-white"
                      : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <div className="text-xs font-bold truncate">{lang.label}</div>
                  <div className="text-[10px] text-zinc-500 truncate">
                    {lang.sub}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* 2. Vibe / Category Selector */}
          <div className="space-y-1.5">
            <label className="block text-[11px] font-bold text-zinc-300">
              2. Phong cách / Chủ đề video
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              {VIBE_OPTIONS.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  onClick={() => setVibe(v.id)}
                  className={`rounded-xl border px-3 py-2 text-left text-xs font-bold transition cursor-pointer ${
                    vibe === v.id
                      ? "border-pink-500 bg-pink-500/15 text-white"
                      : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>

          {/* 3. Optional Custom Keyword / Detail */}
          <div className="space-y-1.5">
            <label className="block text-[11px] font-bold text-zinc-300">
              3. Chi tiết điểm nhấn (Tùy chọn — gõ để lồng vào tiêu đề & tags)
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={customNote}
                onChange={(e) => setCustomNote(e.target.value)}
                placeholder="VD: áo dài trắng, tóc ngắn, nhảy nhạc remix, phố đi bộ..."
                className="flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2 text-xs text-white focus:border-pink-500 focus:outline-none"
              />
              <button
                type="button"
                onClick={() => setSeoSeed((s) => s + 1)}
                title="Đổi sang nhóm mẫu câu tiêu đề khác"
                className="inline-flex items-center gap-1 rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3 py-2 text-xs font-bold text-zinc-200 cursor-pointer shrink-0"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                Đổi mẫu
              </button>
              {hasGeminiKey && (
                <button
                  type="button"
                  onClick={handleAiPolishSeo}
                  disabled={aiPolishing}
                  title="Dùng Gemini AI sáng tạo thêm bộ tiêu đề mới"
                  className="inline-flex items-center gap-1 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-50 px-3 py-2 text-xs font-bold text-white cursor-pointer shrink-0"
                >
                  {aiPolishing ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Wand2 className="h-3.5 w-3.5" />
                  )}
                  AI
                </button>
              )}
            </div>
          </div>

          {/* Generated 6 Titles */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold text-white">
                6 Phương Án Tiêu Đề Hút Click (Bấm Copy nhanh)
              </span>
              <span className="text-[10px] text-zinc-400">
                Chuẩn &lt; 100 ký tự YouTube
              </span>
            </div>
            <div className="space-y-1.5">
              {activeSeo.titles.map((title, idx) => {
                const key = `title_${idx}`;
                const isPicked = selectedTitleIdx === idx;
                return (
                  <div
                    key={key}
                    onClick={() => setSelectedTitleIdx(idx)}
                    className={`flex items-center justify-between gap-2 rounded-xl border p-2.5 transition cursor-pointer ${
                      isPicked
                        ? "border-pink-500/80 bg-pink-500/10"
                        : "border-zinc-800 bg-zinc-950/70 hover:border-zinc-700"
                    }`}
                  >
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-semibold text-zinc-100 leading-snug">
                        {title}
                      </div>
                      <div className="text-[10px] text-zinc-500 mt-0.5">
                        {title.length} ký tự
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedTitleIdx(idx);
                        markCopied(key, title, `Tiêu đề #${idx + 1}`);
                      }}
                      className="shrink-0 inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1.5 text-[11px] font-bold text-white cursor-pointer"
                    >
                      {copiedKey === key ? (
                        <Check className="h-3.5 w-3.5 text-emerald-400" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                      Copy
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* YouTube Studio Tags Box (< 500 chars comma-separated) */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/85 p-3.5 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-extrabold text-white flex items-center gap-1.5">
                <Tag className="h-3.5 w-3.5 text-emerald-400" />
                Thẻ Tags YouTube Studio ({activeSeo.studioTagsCharCount}/500 ký tự)
              </span>
              <button
                type="button"
                onClick={() =>
                  markCopied(
                    "studio_tags",
                    activeSeo.studioTagsCsv,
                    "bộ Thẻ Tags YouTube Studio"
                  )
                }
                className="inline-flex items-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2.5 py-1 text-[11px] font-bold text-white cursor-pointer"
              >
                {copiedKey === "studio_tags" ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )}
                Copy Tất Cả Tags
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {activeSeo.studioTags.map((t) => (
                <span
                  key={t}
                  className="rounded-md border border-zinc-800 bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-300"
                >
                  {t}
                </span>
              ))}
            </div>
          </div>

          {/* Hashtags + Description */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-950/85 p-3.5 space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-extrabold text-white">
                Mô Tả Video & Hashtags
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  onClick={() =>
                    markCopied(
                      "hashtags",
                      activeSeo.hashtags.join(" "),
                      "cụm Hashtags"
                    )
                  }
                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-[11px] font-bold text-zinc-200 cursor-pointer"
                >
                  {copiedKey === "hashtags" ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  Copy #Hashtags
                </button>
                <button
                  type="button"
                  onClick={() =>
                    markCopied(
                      "desc",
                      activeSeo.description,
                      "Mô tả (Description)"
                    )
                  }
                  className="inline-flex items-center gap-1 rounded-lg border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-2.5 py-1 text-[11px] font-bold text-white cursor-pointer"
                >
                  {copiedKey === "desc" ? (
                    <Check className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <Copy className="h-3 w-3" />
                  )}
                  Copy Mô Tả
                </button>
              </div>
            </div>
            <pre className="whitespace-pre-wrap rounded-lg bg-zinc-900/90 p-2.5 text-[11px] text-zinc-300 font-sans leading-relaxed border border-zinc-800/80 max-h-40 overflow-y-auto">
              {activeSeo.description}
            </pre>
          </div>

          {/* Save Complete Bundle Button */}
          <button
            type="button"
            onClick={handleSaveBundleToMac}
            disabled={savingBundle}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl border border-pink-500/40 bg-pink-500/15 hover:bg-pink-500/25 py-3 text-xs font-extrabold text-pink-200 transition cursor-pointer"
          >
            {savingBundle ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <FolderOpen className="h-4 w-4" />
            )}
            Lưu Trọn Bộ (Thumbnail HD + File Tiêu Đề & Tags .txt) Ra Máy Mac
          </button>
        </div>
      </div>
    </div>
  );
}
