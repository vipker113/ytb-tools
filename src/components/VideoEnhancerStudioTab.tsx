"use client";

import {
  Check,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Download,
  Eye,
  Film,
  FolderOpen,
  Gauge,
  Loader2,
  MoveHorizontal,
  Play,
  RefreshCw,
  Scissors,
  Sliders,
  Smartphone,
  Sparkles,
  Square,
  Upload,
  UserCheck,
  Wand2,
  Zap,
  ZoomIn,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type EnhancerEngine = "ai_realesrgan" | "ffmpeg_pro";
type TargetRes = "1080p" | "2k" | "4k";
type AspectMode = "shorts_fill" | "shorts_blur" | "keep_aspect";
type ColorPreset = "auto_vivid" | "beauty_glow" | "cinema_hdr" | "natural";
type FpsMode = "keep" | "smooth_60fps";
type StageMode = "split_frame" | "video_player";

interface ResOption {
  width: number;
  height: number;
}

interface ProbedVideoInfo {
  width: number;
  height: number;
  active_width: number;
  active_height: number;
  is_native_9_16?: boolean;
  duration_s: number;
  fps: number;
  total_frames: number;
  codec: string;
  bitrate_kbps: number;
  size_mb: number;
  has_audio: boolean;
  has_pillarbox: boolean;
  crop_box: number[] | null;
  recommended_ts: number;
  shorts_res_options?: {
    "1080p": ResOption;
    "2k": ResOption;
    "4k": ResOption;
  };
  res_options?: {
    "1080p": ResOption;
    "2k": ResOption;
    "4k": ResOption;
  };
}

interface PreviewFrameResult {
  before_file: string;
  after_file: string;
  orig_width: number;
  orig_height: number;
  preview_width: number;
  preview_height: number;
  timestamp_s: number;
  focus_x: number;
  focus_y: number;
  did_crop_bars: boolean;
  engine_label: string;
  elapsed_ms: number;
}

interface RenderJobStatus {
  status: "running" | "completed" | "error" | "cancelled";
  stage?: string;
  percent?: number;
  processed_frames?: number;
  total_frames?: number;
  fps?: number;
  eta_s?: number | null;
  out_file?: string;
  out_path?: string;
  orig_width?: number;
  orig_height?: number;
  active_width?: number;
  active_height?: number;
  out_width?: number;
  out_height?: number;
  orig_fps?: number;
  out_fps?: number;
  did_crop_bars?: boolean;
  duration_s?: number;
  size_mb?: number;
  bitrate_mbps?: number;
  elapsed_s?: number;
  engine_label?: string;
  error?: string;
}

interface FolderVideoEntry {
  name: string;
  fullPath: string;
  sizeMb: number;
  mtimeMs: number;
}

interface VideoEnhancerStudioTabProps {
  onNotify: (msg: string) => void;
}

const COLOR_PRESET_OPTIONS: {
  id: ColorPreset;
  label: string;
  sub: string;
}[] = [
  {
    id: "auto_vivid",
    label: "✨ Trong Trẻo & Tươi",
    sub: "Khử xỉn màu, tăng chiều sâu",
  },
  {
    id: "beauty_glow",
    label: "🌸 Sáng Mịn Chân Dung",
    sub: "Da sáng hồng tự nhiên",
  },
  {
    id: "cinema_hdr",
    label: "🎬 Điện Ảnh HDR",
    sub: "Tương phản sâu, nổi khối",
  },
  {
    id: "natural",
    label: "🎯 Giữ Màu Gốc",
    sub: "Không đổi tông màu",
  },
];

function formatTimeSec(sec: number): string {
  const s = Math.max(0, sec);
  const mins = Math.floor(s / 60);
  const rem = s - mins * 60;
  return `${String(mins).padStart(2, "0")}:${rem.toFixed(1).padStart(4, "0")}`;
}

export function VideoEnhancerStudioTab({ onNotify }: VideoEnhancerStudioTabProps) {
  // Video session state
  const [sessionId, setSessionId] = useState<string>("");
  const [videoPath, setVideoPath] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [videoInfo, setVideoInfo] = useState<ProbedVideoInfo | null>(null);

  // Loading & drag state
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [showFolderPicker, setShowFolderPicker] = useState(false);
  const [folderInput, setFolderInput] = useState("~/Downloads");
  const [folderVideos, setFolderVideos] = useState<FolderVideoEntry[]>([]);
  const [scanningFolder, setScanningFolder] = useState(false);
  const [localPathInput, setLocalPathInput] = useState("");

  // Enhancement controls
  const [engine, setEngine] = useState<EnhancerEngine>("ai_realesrgan");
  const [targetRes, setTargetRes] = useState<TargetRes>("1080p");
  const [aspectMode, setAspectMode] = useState<AspectMode>("shorts_fill");
  const [denoise, setDenoise] = useState<number>(55);
  const [sharpen, setSharpen] = useState<number>(45);
  const [faceRestore, setFaceRestore] = useState<boolean>(true);
  const [colorPreset, setColorPreset] = useState<ColorPreset>("auto_vivid");
  const [cropBars, setCropBars] = useState<boolean>(true);
  const [fpsMode, setFpsMode] = useState<FpsMode>("keep");

  // Before / After 1-Frame Preview state
  const [previewTimestamp, setPreviewTimestamp] = useState<number>(1.0);
  const [previewResult, setPreviewResult] = useState<PreviewFrameResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [splitPct, setSplitPct] = useState<number>(50);
  const [zoomLevel, setZoomLevel] = useState<1 | 2 | 3>(1);
  const [customZoomOrigin, setCustomZoomOrigin] = useState<{ x: number; y: number } | null>(
    null
  );
  const [isDraggingSplit, setIsDraggingSplit] = useState<boolean>(false);

  // Stage mode & Full Render state
  const [stageMode, setStageMode] = useState<StageMode>("split_frame");
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [renderJob, setRenderJob] = useState<RenderJobStatus | null>(null);
  const [comparingOrigVideo, setComparingOrigVideo] = useState<boolean>(false);
  const [savingToDownloads, setSavingToDownloads] = useState<boolean>(false);
  const [savedLocalPath, setSavedLocalPath] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const splitContainerRef = useRef<HTMLDivElement | null>(null);
  const enhancedVideoRef = useRef<HTMLVideoElement | null>(null);
  const previewSeqRef = useRef<number>(0);
  const skipNextAutoPreviewRef = useRef<boolean>(false);

  const isRendering = activeJobId !== null && renderJob?.status === "running";
  const completedJob = renderJob?.status === "completed" ? renderJob : null;

  // Compute media URLs
  const beforeImgUrl = useMemo(() => {
    if (!sessionId || !previewResult?.before_file) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      sessionId
    )}&file=${encodeURIComponent(previewResult.before_file)}`;
  }, [sessionId, previewResult]);

  const afterImgUrl = useMemo(() => {
    if (!sessionId || !previewResult?.after_file) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      sessionId
    )}&file=${encodeURIComponent(previewResult.after_file)}`;
  }, [sessionId, previewResult]);

  const enhancedVideoStreamUrl = useMemo(() => {
    if (!sessionId || !completedJob?.out_file) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      sessionId
    )}&file=${encodeURIComponent(completedJob.out_file)}`;
  }, [sessionId, completedJob]);

  const origVideoStreamUrl = useMemo(() => {
    if (!videoPath) return "";
    return `/api/reup-tool/media?videoPath=${encodeURIComponent(videoPath)}`;
  }, [videoPath]);

  const downloadFileName = useMemo(() => {
    const stem = fileName
      ? fileName.replace(/\.[^/.]+$/, "")
      : "enhanced_video";
    const fmtTag = aspectMode !== "keep_aspect" ? "SHORTS_" : "";
    const tag =
      engine === "ai_realesrgan"
        ? `${fmtTag}AI_${targetRes.toUpperCase()}`
        : `${fmtTag}PRO_${targetRes.toUpperCase()}`;
    return `${stem}_${tag}.mp4`;
  }, [fileName, engine, targetRes, aspectMode]);

  const enhancedDownloadUrl = useMemo(() => {
    if (!sessionId || !completedJob?.out_file) return "";
    return `/api/reup-tool/media?session=${encodeURIComponent(
      sessionId
    )}&file=${encodeURIComponent(completedJob.out_file)}&download=${encodeURIComponent(
      downloadFileName
    )}`;
  }, [sessionId, completedJob, downloadFileName]);

  // Effective zoom focal point (defaults to AI-detected eyes/face center)
  const zoomOrigin = useMemo(() => {
    if (customZoomOrigin) return customZoomOrigin;
    if (previewResult) {
      return {
        x: Math.round(previewResult.focus_x * 100),
        y: Math.round(previewResult.focus_y * 100),
      };
    }
    return { x: 50, y: 40 };
  }, [customZoomOrigin, previewResult]);

  // Request 1-Frame Before / After Preview
  const requestFramePreview = useCallback(
    async (overrideTs?: number) => {
      if (!sessionId || !videoPath) return;
      const seq = ++previewSeqRef.current;
      const ts = overrideTs !== undefined ? overrideTs : previewTimestamp;
      setPreviewLoading(true);
      try {
        const res = await fetch("/api/video-enhancer/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "preview",
            sessionId,
            videoPath,
            timestamp: ts,
            engine,
            targetRes,
            aspectMode,
            denoise,
            sharpen,
            faceRestore,
            colorPreset,
            cropBars,
          }),
        });
        const json = await res.json();
        if (seq !== previewSeqRef.current) return;
        if (!res.ok || !json.ok) {
          onNotify(json.error || "Không thể tạo khung xem thử");
          return;
        }
        setPreviewResult(json.preview as PreviewFrameResult);
      } catch {
        if (seq === previewSeqRef.current) {
          onNotify("Lỗi kết nối khi tạo khung xem thử Trước/Sau.");
        }
      } finally {
        if (seq === previewSeqRef.current) {
          setPreviewLoading(false);
        }
      }
    },
    [
      sessionId,
      videoPath,
      previewTimestamp,
      engine,
      targetRes,
      aspectMode,
      denoise,
      sharpen,
      faceRestore,
      colorPreset,
      cropBars,
      onNotify,
    ]
  );

  // Debounced auto-update of 1-frame Before/After preview whenever quality parameters change
  useEffect(() => {
    if (!sessionId || !videoPath) return;
    if (skipNextAutoPreviewRef.current) {
      skipNextAutoPreviewRef.current = false;
      return;
    }
    const timer = setTimeout(() => {
      void requestFramePreview();
    }, 420);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    engine,
    targetRes,
    aspectMode,
    denoise,
    sharpen,
    faceRestore,
    colorPreset,
    cropBars,
  ]);

  // Upload file handler
  const handleUploadVideoFile = useCallback(
    async (file: File) => {
      setUploading(true);
      setRenderJob(null);
      setActiveJobId(null);
      setSavedLocalPath(null);
      setStageMode("split_frame");
      setCustomZoomOrigin(null);
      try {
        const qs = new URLSearchParams({
          name: file.name,
          engine,
          targetRes,
          aspectMode,
        });
        const res = await fetch(`/api/video-enhancer/upload?${qs.toString()}`, {
          method: "POST",
          body: file,
        });
        const rawText = await res.text();
        let json: Record<string, unknown> = {};
        try {
          json = rawText ? JSON.parse(rawText) : {};
        } catch {
          throw new Error(`Server trả về HTTP ${res.status} (không phải JSON).`);
        }
        if (!res.ok || !json.ok) {
          onNotify(String(json.error || `Không thể đọc file video (HTTP ${res.status})`));
          return;
        }
        skipNextAutoPreviewRef.current = true;
        setSessionId(String(json.sessionId || ""));
        setVideoPath(String(json.videoPath || ""));
        setFileName(String(json.originalName || file.name));
        const info = json.videoInfo as ProbedVideoInfo;
        setVideoInfo(info);
        setPreviewTimestamp(info.recommended_ts ?? 1.0);
        setPreviewResult(json.preview as PreviewFrameResult);
        setSplitPct(50);
        onNotify("✨ Đã phân tích video & ép chuẩn xem thử màn hình Shorts 9:16!");
      } catch (err) {
        onNotify(
          err instanceof Error && err.message
            ? `Lỗi tải video: ${err.message}`
            : "Lỗi tải video lên bộ xử lý."
        );
      } finally {
        setUploading(false);
      }
    },
    [engine, targetRes, aspectMode, onNotify]
  );

  // Load local Mac path directly
  const handleLoadLocalVideoPath = useCallback(
    async (rawPath: string) => {
      const clean = rawPath.trim();
      if (!clean) return;
      setUploading(true);
      setRenderJob(null);
      setActiveJobId(null);
      setSavedLocalPath(null);
      setStageMode("split_frame");
      setCustomZoomOrigin(null);
      try {
        const res = await fetch("/api/video-enhancer/action", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "loadLocalPath",
            localPath: clean,
            engine,
            targetRes,
            aspectMode,
            denoise,
            sharpen,
            faceRestore,
            colorPreset,
            cropBars,
          }),
        });
        const json = await res.json();
        if (!res.ok || !json.ok) {
          onNotify(json.error || "Không mở được đường dẫn video");
          return;
        }
        skipNextAutoPreviewRef.current = true;
        setSessionId(json.sessionId);
        setVideoPath(json.videoPath);
        setFileName(json.originalName);
        const info = json.videoInfo as ProbedVideoInfo;
        setVideoInfo(info);
        setPreviewTimestamp(info.recommended_ts ?? 1.0);
        setPreviewResult(json.preview as PreviewFrameResult);
        setSplitPct(50);
        setShowFolderPicker(false);
        onNotify(`✨ Đã mở "${json.originalName}" & ép chuẩn khung Shorts 9:16!`);
      } catch {
        onNotify("Lỗi đọc đường dẫn video trên máy Mac.");
      } finally {
        setUploading(false);
      }
    },
    [
      engine,
      targetRes,
      aspectMode,
      denoise,
      sharpen,
      faceRestore,
      colorPreset,
      cropBars,
      onNotify,
    ]
  );

  const handleScanFolder = useCallback(async () => {
    setScanningFolder(true);
    try {
      const res = await fetch("/api/video-enhancer/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "scanFolder",
          folderPath: folderInput,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        onNotify(json.error || "Không quét được thư mục");
        return;
      }
      setFolderVideos(json.videos || []);
    } catch {
      onNotify("Lỗi quét thư mục video.");
    } finally {
      setScanningFolder(false);
    }
  }, [folderInput, onNotify]);

  // Start Full Video Render
  const handleStartFullRender = useCallback(async () => {
    if (!sessionId || !videoPath || isRendering) return;
    setSavedLocalPath(null);
    setComparingOrigVideo(false);
    setRenderJob({
      status: "running",
      stage:
        engine === "ai_realesrgan"
          ? "Đang khởi tạo mạng nơ-ron Real-ESRGAN v3 trên GPU Apple Silicon..."
          : "Đang khởi chạy FFmpeg Pro VideoToolbox...",
      percent: 1,
      processed_frames: 0,
      total_frames: videoInfo?.total_frames || 0,
    });

    try {
      const res = await fetch("/api/video-enhancer/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "startRender",
          sessionId,
          videoPath,
          fileName,
          engine,
          targetRes,
          aspectMode,
          denoise,
          sharpen,
          faceRestore,
          colorPreset,
          cropBars,
          fpsMode,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        setRenderJob({
          status: "error",
          error: json.error || "Không thể bắt đầu nâng cấp video.",
        });
        onNotify(json.error || "Lỗi bắt đầu render video");
        return;
      }
      setActiveJobId(json.jobId);
    } catch {
      setRenderJob({
        status: "error",
        error: "Mất kết nối tới bộ xử lý nâng cấp video.",
      });
    }
  }, [
    sessionId,
    videoPath,
    fileName,
    isRendering,
    engine,
    targetRes,
    aspectMode,
    denoise,
    sharpen,
    faceRestore,
    colorPreset,
    cropBars,
    fpsMode,
    videoInfo,
    onNotify,
  ]);

  // Poll Render Job Progress
  useEffect(() => {
    if (!activeJobId || !sessionId) return;
    let cancelled = false;

    const poll = async () => {
      try {
        const res = await fetch(
          `/api/video-enhancer/action?session=${encodeURIComponent(
            sessionId
          )}&jobId=${encodeURIComponent(activeJobId)}`,
          { cache: "no-store" }
        );
        const json = await res.json();
        if (cancelled || !res.ok || !json.ok) return;
        const job = json.job as RenderJobStatus;
        setRenderJob(job);

        if (job.status === "completed") {
          setActiveJobId(null);
          setStageMode("video_player");
          onNotify(
            `🎉 Hoàn tất nâng cấp video lên ${job.out_width}×${job.out_height} (${job.elapsed_s}s)!`
          );
        } else if (job.status === "error" || job.status === "cancelled") {
          setActiveJobId(null);
          if (job.status === "error") {
            onNotify(job.error || "Lỗi trong quá trình nâng cấp video.");
          }
        }
      } catch {
        // ignore transient poll error
      }
    };

    const interval = setInterval(() => {
      void poll();
    }, 750);
    void poll();

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [activeJobId, sessionId, onNotify]);

  const handleCancelRender = useCallback(async () => {
    if (!sessionId || !activeJobId) return;
    try {
      await fetch("/api/video-enhancer/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "cancelRender",
          sessionId,
          jobId: activeJobId,
        }),
      });
      setActiveJobId(null);
      setRenderJob({
        status: "cancelled",
        error: "Đã dừng quá trình render.",
      });
      onNotify("⏹️ Đã dừng tiến trình nâng cấp video.");
    } catch {
      onNotify("Không thể hủy tiến trình.");
    }
  }, [sessionId, activeJobId, onNotify]);

  const handleSaveToDownloads = useCallback(async () => {
    if (!sessionId || !completedJob?.out_file) return;
    setSavingToDownloads(true);
    try {
      const res = await fetch("/api/video-enhancer/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "saveToMacFolder",
          sessionId,
          outFile: completedJob.out_file,
          targetFolder: "~/Downloads",
          saveFileName: downloadFileName,
        }),
      });
      const json = await res.json();
      if (!res.ok || !json.ok) {
        onNotify(json.error || "Lỗi lưu file vào ~/Downloads");
        return;
      }
      setSavedLocalPath(json.savedPath);
      onNotify(`✅ Đã lưu vào ${json.savedPath}`);
    } catch {
      onNotify("Không thể lưu vào ~/Downloads.");
    } finally {
      setSavingToDownloads(false);
    }
  }, [sessionId, completedJob, downloadFileName, onNotify]);

  // Split slider pointer interaction
  const updateSplitFromClientX = useCallback((clientX: number) => {
    const el = splitContainerRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0) return;
    const pct = ((clientX - rect.left) / rect.width) * 100;
    setSplitPct(Math.max(2, Math.min(98, Math.round(pct * 10) / 10)));
  }, []);

  const activeResOptions = useMemo(() => {
    if (aspectMode !== "keep_aspect") {
      return (
        videoInfo?.shorts_res_options || {
          "1080p": { width: 1080, height: 1920 },
          "2k": { width: 1440, height: 2560 },
          "4k": { width: 2160, height: 3840 },
        }
      );
    }
    return videoInfo?.res_options;
  }, [aspectMode, videoInfo]);

  const targetDimsLabel = useMemo(() => {
    const opt = activeResOptions?.[targetRes];
    if (opt) return `${opt.width}×${opt.height}`;
    if (targetRes === "4k") return "2160×3840";
    if (targetRes === "2k") return "1440×2560";
    return "1080×1920";
  }, [activeResOptions, targetRes]);

  const isVerticalPreview = useMemo(() => {
    if (previewResult) {
      return previewResult.preview_height >= previewResult.preview_width;
    }
    if (videoInfo) {
      return videoInfo.active_height >= videoInfo.active_width;
    }
    return true;
  }, [previewResult, videoInfo]);

  return (
    <div className="space-y-5">
      {/* Hidden File Input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv,.m4v"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void handleUploadVideoFile(f);
          e.target.value = "";
        }}
      />

      {/* STEP 1: DROPZONE (IF NO VIDEO LOADED) OR COMPACT SOURCE HEADER */}
      {!videoInfo ? (
        <div className="rounded-2xl border border-zinc-800/90 bg-gradient-to-b from-zinc-900/90 to-zinc-950 p-6 sm:p-8 shadow-2xl">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragActive(false);
              const f = e.dataTransfer.files?.[0];
              if (f) void handleUploadVideoFile(f);
            }}
            onClick={() => {
              if (!uploading) fileInputRef.current?.click();
            }}
            className={`rounded-2xl border-2 border-dashed p-8 sm:p-12 text-center transition cursor-pointer ${
              dragActive
                ? "border-violet-400 bg-violet-950/25"
                : "border-zinc-700/80 hover:border-violet-500/70 bg-zinc-950/60 hover:bg-zinc-900/60"
            }`}
          >
            {uploading ? (
              <div className="flex flex-col items-center gap-3 py-4">
                <Loader2 className="h-10 w-10 animate-spin text-violet-400" />
                <div className="text-base font-extrabold text-white">
                  Đang đọc thông số video & tạo khung so sánh AI Trước / Sau...
                </div>
                <p className="text-xs text-zinc-400">
                  Mạng nơ-ron Real-ESRGAN v3 + YuNet đang quét khung hình đẹp nhất (~1–2 giây)
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3.5 max-w-xl mx-auto">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-600 to-fuchsia-600 text-white shadow-lg shadow-violet-600/30">
                  <Sparkles className="h-7 w-7" />
                </div>
                <div className="space-y-1">
                  <h2 className="text-lg sm:text-xl font-extrabold text-white">
                    Nâng Cấp Chất Lượng Video AI (Real-ESRGAN GPU & 4K Studio)
                  </h2>
                  <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
                    Kéo thả video bị mờ, vỡ hạt nén TikTok/Douyin/Shorts vào đây để xem thử{" "}
                    <span className="text-violet-300 font-semibold">
                      Thanh kéo Trước / Sau
                    </span>{" "}
                    trước khi xuất Full HD 1080p, 2K hoặc 4K.
                  </p>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-2.5 pt-2">
                  <span className="inline-flex items-center gap-2 rounded-xl bg-violet-600 hover:bg-violet-500 px-5 py-2.5 text-xs sm:text-sm font-extrabold text-white shadow-lg shadow-violet-600/25 transition">
                    <Upload className="h-4 w-4" />
                    Chọn Video Từ Máy Mac (.MP4, .MOV, .WEBM)
                  </span>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowFolderPicker((v) => !v);
                      if (!showFolderPicker && folderVideos.length === 0) {
                        void handleScanFolder();
                      }
                    }}
                    className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-4 py-2.5 text-xs font-bold text-zinc-200 transition cursor-pointer"
                  >
                    <FolderOpen className="h-4 w-4 text-amber-400" />
                    Mở Nhanh Từ Thư Mục Mac
                  </button>
                </div>

                <div className="flex flex-wrap items-center justify-center gap-3 pt-2 text-[11px] text-zinc-400">
                  <span className="inline-flex items-center gap-1">
                    <Cpu className="h-3.5 w-3.5 text-emerald-400" />
                    Apple M2 Pro MPS GPU (FP16)
                  </span>
                  <span>•</span>
                  <span className="inline-flex items-center gap-1">
                    <UserCheck className="h-3.5 w-3.5 text-pink-400" />
                    AI Phục Hồi Nét Mặt & Mắt
                  </span>
                  <span>•</span>
                  <span className="inline-flex items-center gap-1">
                    <Zap className="h-3.5 w-3.5 text-amber-400" />
                    FFmpeg Pro 2–5s/video
                  </span>
                </div>
              </div>
            )}
          </div>

          {/* Optional Quick Local Folder / Path Drawer */}
          {showFolderPicker && (
            <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/90 p-4 space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={folderInput}
                    onChange={(e) => setFolderInput(e.target.value)}
                    placeholder="~/Downloads"
                    className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-violet-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => void handleScanFolder()}
                    disabled={scanningFolder}
                    className="rounded-xl border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 px-3.5 py-2 text-xs font-bold text-white cursor-pointer"
                  >
                    {scanningFolder ? "Đang quét..." : "Quét Thư Mục"}
                  </button>
                </div>

                <div className="flex gap-2">
                  <input
                    type="text"
                    value={localPathInput}
                    onChange={(e) => setLocalPathInput(e.target.value)}
                    placeholder="Hoặc dán đường dẫn file: ~/Downloads/clip.mp4"
                    className="flex-1 rounded-xl border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs text-white focus:border-violet-500 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => void handleLoadLocalVideoPath(localPathInput)}
                    className="rounded-xl bg-violet-600 hover:bg-violet-500 px-3.5 py-2 text-xs font-bold text-white cursor-pointer"
                  >
                    Mở Ngay
                  </button>
                </div>
              </div>

              {folderVideos.length > 0 && (
                <div className="max-h-48 overflow-y-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pt-1">
                  {folderVideos.map((v) => (
                    <button
                      key={v.fullPath}
                      type="button"
                      onClick={() => void handleLoadLocalVideoPath(v.fullPath)}
                      className="flex items-center justify-between gap-2 rounded-lg border border-zinc-800 bg-zinc-900/80 hover:border-violet-500/60 hover:bg-zinc-900 px-3 py-2 text-left transition cursor-pointer"
                    >
                      <span className="text-xs font-semibold text-zinc-200 truncate">
                        {v.name}
                      </span>
                      <span className="shrink-0 text-[10px] text-zinc-400">
                        {v.sizeMb} MB
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* COMPACT TOP SOURCE BAR WHEN VIDEO IS LOADED */
        <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/75 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2.5 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-600/20 border border-violet-500/40 text-violet-300">
              <Film className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="text-xs sm:text-sm font-extrabold text-white truncate max-w-md">
                {fileName}
              </div>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-400">
                <span>
                  Gốc:{" "}
                  <strong className="text-zinc-200">
                    {videoInfo.width}×{videoInfo.height}
                  </strong>
                </span>
                <span>•</span>
                <span>{videoInfo.fps} FPS</span>
                <span>•</span>
                <span>{videoInfo.duration_s}s</span>
                {videoInfo.bitrate_kbps > 0 && (
                  <>
                    <span>•</span>
                    <span>
                      {videoInfo.bitrate_kbps >= 1000
                        ? `${(videoInfo.bitrate_kbps / 1000).toFixed(1)} Mbps`
                        : `${videoInfo.bitrate_kbps} kbps`}
                    </span>
                  </>
                )}
                <span>→</span>
                <span className="text-emerald-300 font-bold">
                  Đích: {targetDimsLabel} (
                  {aspectMode !== "keep_aspect"
                    ? `Shorts 9:16 • ${targetRes.toUpperCase()}`
                    : targetRes.toUpperCase()}
                  )
                </span>
              </div>
            </div>

            {videoInfo.has_pillarbox && (
              <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-950/40 px-2.5 py-1 text-[10px] font-bold text-amber-300">
                <Scissors className="h-3 w-3" />
                Phát hiện viền đen thừa ({videoInfo.active_width}×{videoInfo.active_height})
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={uploading || isRendering}
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-950 hover:bg-zinc-800 px-3.5 py-2 text-xs font-bold text-zinc-200 transition cursor-pointer disabled:opacity-50"
            >
              <Upload className="h-3.5 w-3.5 text-violet-400" />
              Đổi Video Khác
            </button>
          </div>
        </div>
      )}

      {/* MAIN 2-COLUMN WORKSPACE */}
      {videoInfo && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          {/* LEFT COLUMN (7 COLS): INTERACTIVE BEFORE / AFTER SPLIT SLIDER + VIDEO PLAYER */}
          <div className="lg:col-span-7 space-y-4">
            <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/70 p-4 space-y-3.5 shadow-xl">
              {/* Stage Header & Mode Switcher */}
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 rounded-xl bg-zinc-950 p-1 border border-zinc-800">
                  <button
                    type="button"
                    onClick={() => setStageMode("split_frame")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer ${
                      stageMode === "split_frame"
                        ? "bg-violet-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <MoveHorizontal className="h-3.5 w-3.5" />
                    So Sánh Trước / Sau (1 Frame)
                  </button>
                  <button
                    type="button"
                    disabled={!completedJob}
                    onClick={() => setStageMode("video_player")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-bold transition cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed ${
                      stageMode === "video_player"
                        ? "bg-emerald-600 text-white shadow"
                        : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    <Play className="h-3.5 w-3.5" />
                    Xem Video Đã Nâng Cấp
                  </button>
                </div>

                {/* Zoom Controls (when in Split Frame mode) */}
                {stageMode === "split_frame" && (
                  <div className="flex items-center gap-1.5">
                    <span className="text-[11px] text-zinc-400 hidden sm:inline mr-1">
                      Phóng đại soi nét:
                    </span>
                    {([1, 2, 3] as const).map((z) => (
                      <button
                        key={z}
                        type="button"
                        onClick={() => {
                          setZoomLevel(z);
                          if (z === 1) setCustomZoomOrigin(null);
                        }}
                        className={`inline-flex items-center gap-1 rounded-lg border px-2.5 py-1 text-xs font-extrabold transition cursor-pointer ${
                          zoomLevel === z
                            ? "border-violet-500 bg-violet-600/25 text-violet-200"
                            : "border-zinc-800 bg-zinc-950 text-zinc-400 hover:text-white"
                        }`}
                      >
                        <ZoomIn className="h-3 w-3" />
                        {z}x
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* MODE A: INTERACTIVE BEFORE / AFTER SPLIT COMPARISON STAGE */}
              {stageMode === "split_frame" ? (
                <div className="space-y-3">
                  <div
                    ref={splitContainerRef}
                    onPointerDown={(e) => {
                      setIsDraggingSplit(true);
                      (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
                      updateSplitFromClientX(e.clientX);
                    }}
                    onPointerMove={(e) => {
                      if (isDraggingSplit) {
                        updateSplitFromClientX(e.clientX);
                      }
                    }}
                    onPointerUp={(e) => {
                      if (isDraggingSplit) {
                        setIsDraggingSplit(false);
                        try {
                          (e.currentTarget as HTMLDivElement).releasePointerCapture(
                            e.pointerId
                          );
                        } catch {
                          // ignore
                        }
                      }
                    }}
                    onDoubleClick={(e) => {
                      // Double-click sets zoom focal point & toggles 2x zoom!
                      const rect = e.currentTarget.getBoundingClientRect();
                      const xPct = Math.round(((e.clientX - rect.left) / rect.width) * 100);
                      const yPct = Math.round(((e.clientY - rect.top) / rect.height) * 100);
                      setCustomZoomOrigin({
                        x: Math.max(10, Math.min(90, xPct)),
                        y: Math.max(10, Math.min(90, yPct)),
                      });
                      setZoomLevel((prev) => (prev === 1 ? 2 : 1));
                    }}
                    className={`relative mx-auto overflow-hidden rounded-xl border border-zinc-800 bg-black select-none touch-none cursor-ew-resize ${
                      isVerticalPreview
                        ? "max-w-[360px] sm:max-w-[395px] aspect-[9/16]"
                        : "w-full aspect-video"
                    }`}
                  >
                    {afterImgUrl && beforeImgUrl ? (
                      <>
                        {/* Base Layer: AFTER (Enhanced AI / Pro) */}
                        <img
                          src={afterImgUrl}
                          alt="Sau nâng cấp"
                          draggable={false}
                          style={{
                            transform: `scale(${zoomLevel})`,
                            transformOrigin: `${zoomOrigin.x}% ${zoomOrigin.y}%`,
                          }}
                          className="absolute inset-0 h-full w-full object-contain transition-transform duration-200 pointer-events-none"
                        />

                        {/* Top Clipped Layer: BEFORE (Original) — 0.00px drift clipPath */}
                        <div
                          style={{
                            clipPath: `inset(0 ${100 - splitPct}% 0 0)`,
                          }}
                          className="absolute inset-0 pointer-events-none"
                        >
                          <img
                            src={beforeImgUrl}
                            alt="Trước nâng cấp (Gốc)"
                            draggable={false}
                            style={{
                              transform: `scale(${zoomLevel})`,
                              transformOrigin: `${zoomOrigin.x}% ${zoomOrigin.y}%`,
                            }}
                            className="absolute inset-0 h-full w-full object-contain transition-transform duration-200"
                          />
                        </div>

                        {/* Top Corner Labels */}
                        <div className="absolute top-3 left-3 z-10 rounded-lg bg-black/75 border border-zinc-700/80 px-2.5 py-1 text-[10px] font-extrabold text-zinc-200 backdrop-blur-md pointer-events-none">
                          GỐC ({previewResult?.orig_width}×{previewResult?.orig_height})
                        </div>
                        <div className="absolute top-3 right-3 z-10 rounded-lg bg-violet-950/85 border border-violet-400/50 px-2.5 py-1 text-[10px] font-extrabold text-violet-200 backdrop-blur-md pointer-events-none">
                          SAU NÂNG CẤP ({previewResult?.preview_width}×
                          {previewResult?.preview_height})
                        </div>

                        {/* Vertical Divider Line + Handle */}
                        <div
                          style={{ left: `${splitPct}%` }}
                          className="absolute inset-y-0 z-20 w-0.5 -translate-x-1/2 bg-white shadow-[0_0_12px_rgba(255,255,255,0.9)] pointer-events-none"
                        >
                          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex h-9 w-9 items-center justify-center rounded-full border-2 border-white bg-violet-600 text-white shadow-xl">
                            <MoveHorizontal className="h-4 w-4" />
                          </div>
                        </div>

                        {/* Loading Pill Overlay when regenerating preview */}
                        {previewLoading && (
                          <div className="absolute bottom-3 left-1/2 -translate-x-1/2 z-30 inline-flex items-center gap-2 rounded-full border border-violet-400/50 bg-zinc-950/90 px-3.5 py-1.5 text-[11px] font-bold text-violet-200 shadow-xl backdrop-blur-md">
                            <Loader2 className="h-3.5 w-3.5 animate-spin text-violet-400" />
                            Đang tính toán khung xem thử AI...
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-xs text-zinc-500">
                        {previewLoading ? (
                          <span className="inline-flex items-center gap-2 text-violet-300">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Đang dựng khung xem thử...
                          </span>
                        ) : (
                          "Chưa có khung xem thử"
                        )}
                      </div>
                    )}
                  </div>

                  {/* Helper Caption + Preview Info */}
                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400 px-1">
                    <span>
                      💡 Kéo thanh trắng sang trái/phải để đối chiếu • Bấm{" "}
                      <strong className="text-zinc-200">2x / 3x</strong> (hoặc nhấp đúp) để soi cận mắt & chi tiết
                    </span>
                    {previewResult && (
                      <span className="text-violet-300 font-semibold">
                        {previewResult.engine_label} • {(previewResult.elapsed_ms / 1000).toFixed(1)}s
                      </span>
                    )}
                  </div>

                  {/* Frame Timestamp Scrubber */}
                  <div className="rounded-xl border border-zinc-800 bg-zinc-950/80 p-3 space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-bold text-zinc-200">
                        Chọn khoảnh khắc bất kỳ để thử nét ({formatTimeSec(previewTimestamp)} /{" "}
                        {formatTimeSec(videoInfo.duration_s)})
                      </span>
                      <div className="flex items-center gap-1.5">
                        <button
                          type="button"
                          disabled={previewLoading}
                          onClick={() => {
                            const nextTs = Math.max(
                              0,
                              Math.round((previewTimestamp - 0.5) * 100) / 100
                            );
                            setPreviewTimestamp(nextTs);
                            void requestFramePreview(nextTs);
                          }}
                          className="inline-flex items-center gap-0.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-2 py-1 text-[11px] font-bold text-zinc-300 cursor-pointer disabled:opacity-50"
                        >
                          <ChevronLeft className="h-3 w-3" />
                          0.5s
                        </button>
                        <button
                          type="button"
                          disabled={previewLoading}
                          onClick={() => {
                            const nextTs = Math.min(
                              Math.max(0, videoInfo.duration_s - 0.1),
                              Math.round((previewTimestamp + 0.5) * 100) / 100
                            );
                            setPreviewTimestamp(nextTs);
                            void requestFramePreview(nextTs);
                          }}
                          className="inline-flex items-center gap-0.5 rounded-lg border border-zinc-800 bg-zinc-900 hover:bg-zinc-800 px-2 py-1 text-[11px] font-bold text-zinc-300 cursor-pointer disabled:opacity-50"
                        >
                          0.5s
                          <ChevronRight className="h-3 w-3" />
                        </button>
                        <button
                          type="button"
                          disabled={previewLoading}
                          onClick={() => void requestFramePreview(previewTimestamp)}
                          className="inline-flex items-center gap-1 rounded-lg bg-violet-600 hover:bg-violet-500 px-2.5 py-1 text-[11px] font-bold text-white cursor-pointer disabled:opacity-50"
                        >
                          <RefreshCw
                            className={`h-3 w-3 ${previewLoading ? "animate-spin" : ""}`}
                          />
                          Xem Thử Khung Này
                        </button>
                      </div>
                    </div>

                    <input
                      type="range"
                      min={0}
                      max={Math.max(0.2, videoInfo.duration_s - 0.05)}
                      step={0.1}
                      value={previewTimestamp}
                      onChange={(e) => setPreviewTimestamp(Number(e.target.value))}
                      onMouseUp={(e) =>
                        void requestFramePreview(Number((e.target as HTMLInputElement).value))
                      }
                      onTouchEnd={(e) =>
                        void requestFramePreview(Number((e.target as HTMLInputElement).value))
                      }
                      className="w-full accent-violet-500 cursor-pointer"
                    />
                  </div>
                </div>
              ) : (
                /* MODE B: ENHANCED FULL VIDEO PLAYER (WITH INSTANT A/B ORIGINAL MOTION TOGGLE) */
                <div className="space-y-3">
                  <div className="relative mx-auto overflow-hidden rounded-xl border border-zinc-800 bg-black">
                    <video
                      ref={enhancedVideoRef}
                      key={comparingOrigVideo ? origVideoStreamUrl : enhancedVideoStreamUrl}
                      src={comparingOrigVideo ? origVideoStreamUrl : enhancedVideoStreamUrl}
                      controls
                      playsInline
                      loop
                      autoPlay
                      className={`mx-auto w-full ${
                        isVerticalPreview ? "max-h-[600px]" : "aspect-video"
                      } object-contain`}
                    />

                    <div className="absolute top-3 left-3 pointer-events-none">
                      <span
                        className={`rounded-lg px-2.5 py-1 text-[11px] font-extrabold border backdrop-blur-md ${
                          comparingOrigVideo
                            ? "bg-black/80 border-zinc-600 text-zinc-200"
                            : "bg-emerald-950/85 border-emerald-400/50 text-emerald-200"
                        }`}
                      >
                        {comparingOrigVideo
                          ? `VIDEO GỐC (${videoInfo.width}×${videoInfo.height})`
                          : `ĐÃ NÂNG CẤP (${completedJob?.out_width}×${completedJob?.out_height} • ${completedJob?.out_fps} FPS)`}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <button
                      type="button"
                      onClick={() => setComparingOrigVideo((v) => !v)}
                      className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-bold transition cursor-pointer ${
                        comparingOrigVideo
                          ? "border-amber-500/60 bg-amber-950/40 text-amber-200"
                          : "border-zinc-700 bg-zinc-950 hover:bg-zinc-800 text-zinc-200"
                      }`}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      {comparingOrigVideo
                        ? "Đang phát Video Gốc — Bấm để quay lại Video Đã Nâng Cấp"
                        : "Đổi nhanh sang Video Gốc để đối chiếu chuyển động"}
                    </button>

                    {enhancedDownloadUrl && (
                      <a
                        href={enhancedDownloadUrl}
                        download={downloadFileName}
                        className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/25 transition"
                      >
                        <Download className="h-3.5 w-3.5" />
                        Tải Video (.MP4)
                      </a>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN (5 COLS): ENGINE, RESOLUTION, SLIDERS & LIVE RENDER */}
          <div className="lg:col-span-5 space-y-4">
            {/* 1. ENGINE SELECTOR */}
            <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/70 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-extrabold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                  <Wand2 className="h-3.5 w-3.5 text-violet-400" />
                  1. Chế Độ Nâng Cấp
                </span>
                <span className="text-[10px] font-bold text-emerald-400">
                  Tự cập nhật khung Xem thử
                </span>
              </div>

              <div className="grid grid-cols-1 gap-2.5">
                <button
                  type="button"
                  disabled={isRendering}
                  onClick={() => setEngine("ai_realesrgan")}
                  className={`rounded-xl border p-3.5 text-left transition cursor-pointer ${
                    engine === "ai_realesrgan"
                      ? "border-violet-500 bg-violet-950/35 shadow-md shadow-violet-600/10"
                      : "border-zinc-800 bg-zinc-950/70 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs sm:text-sm font-extrabold text-white flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4 text-violet-400" />
                      AI Phục Hồi Nét (Real-ESRGAN GPU)
                    </span>
                    <span className="rounded-full bg-violet-500/20 border border-violet-400/40 px-2 py-0.5 text-[10px] font-bold text-violet-200">
                      Nét sâu nhất
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed">
                    Tái tạo chi tiết thật bằng mạng nơ-ron Real-ESRGAN v3 trên GPU M2 Pro + phục hồi mắt, mi & da mặt bị bệt nén.
                  </p>
                </button>

                <button
                  type="button"
                  disabled={isRendering}
                  onClick={() => setEngine("ffmpeg_pro")}
                  className={`rounded-xl border p-3.5 text-left transition cursor-pointer ${
                    engine === "ffmpeg_pro"
                      ? "border-amber-500 bg-amber-950/25 shadow-md shadow-amber-600/10"
                      : "border-zinc-800 bg-zinc-950/70 hover:border-zinc-700"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs sm:text-sm font-extrabold text-white flex items-center gap-1.5">
                      <Zap className="h-4 w-4 text-amber-400" />
                      Siêu Nhanh (FFmpeg Pro Studio)
                    </span>
                    <span className="rounded-full bg-amber-500/20 border border-amber-400/40 px-2 py-0.5 text-[10px] font-bold text-amber-200">
                      2–5 giây/clip
                    </span>
                  </div>
                  <p className="mt-1 text-[11px] text-zinc-400 leading-relaxed">
                    Khử ô vuông nén Deblock + Khử nhiễu 3D + Tăng nét tương phản CAS bằng phần cứng Apple VideoToolbox.
                  </p>
                </button>
              </div>
            </div>

            {/* 2. YOUTUBE SHORTS 9:16 FRAMING & TARGET RESOLUTION */}
            <div className="rounded-2xl border border-emerald-500/35 bg-zinc-900/80 p-4 space-y-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-extrabold uppercase tracking-wider text-zinc-200 flex items-center gap-1.5">
                  <Smartphone className="h-3.5 w-3.5 text-emerald-400" />
                  2. Ép Chuẩn Màn Hình Shorts (9:16) & Độ Nét
                </span>
                {aspectMode !== "keep_aspect" && (
                  <span className="rounded-full bg-emerald-500/20 border border-emerald-400/40 px-2 py-0.5 text-[10px] font-extrabold text-emerald-300">
                    Chuẩn Shorts 9:16
                  </span>
                )}
              </div>

              {/* Shorts Framing Mode Selector */}
              <div className="grid grid-cols-1 gap-2">
                <button
                  type="button"
                  disabled={isRendering}
                  onClick={() => setAspectMode("shorts_fill")}
                  className={`rounded-xl border px-3 py-2.5 text-left transition cursor-pointer ${
                    aspectMode === "shorts_fill"
                      ? "border-emerald-500 bg-emerald-950/35 text-white shadow-sm"
                      : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-extrabold">
                      📱 Shorts 9:16 Tràn Màn Hình (AI Tự Căn Mặt)
                    </span>
                    <span className="text-[10px] font-bold text-emerald-300">
                      Khuyên dùng
                    </span>
                  </div>
                  <div className="text-[10px] text-zinc-400 mt-0.5">
                    Ép mọi video (16:9, 3:4, 1:1, viền đen) phủ kín 100% màn hình dọc điện thoại, tự bám tâm mặt không bị cắt đầu.
                  </div>
                </button>

                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    disabled={isRendering}
                    onClick={() => setAspectMode("shorts_blur")}
                    className={`rounded-xl border px-3 py-2 text-left transition cursor-pointer ${
                      aspectMode === "shorts_blur"
                        ? "border-emerald-500 bg-emerald-950/35 text-white"
                        : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <div className="text-xs font-bold">🖼️ Shorts 9:16 Nền Mờ</div>
                    <div className="text-[10px] text-zinc-500 mt-0.5">
                      Giữ trọn góc quay gốc + nền kính mờ
                    </div>
                  </button>

                  <button
                    type="button"
                    disabled={isRendering}
                    onClick={() => setAspectMode("keep_aspect")}
                    className={`rounded-xl border px-3 py-2 text-left transition cursor-pointer ${
                      aspectMode === "keep_aspect"
                        ? "border-zinc-500 bg-zinc-800/80 text-white"
                        : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                    }`}
                  >
                    <div className="text-xs font-bold">📐 Giữ Tỷ Lệ Gốc</div>
                    <div className="text-[10px] text-zinc-500 mt-0.5">
                      Không ép dọc (cho video dài ngang)
                    </div>
                  </button>
                </div>
              </div>

              {/* Resolution Cards */}
              <div className="space-y-1.5 pt-0.5">
                <div className="flex items-center justify-between text-[11px] text-zinc-400">
                  <span className="flex items-center gap-1 font-semibold text-zinc-300">
                    <Gauge className="h-3 w-3 text-emerald-400" />
                    Độ phân giải đầu ra:
                  </span>
                  <span>SAR 1:1 • Chuẩn YouTube Studio</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {(
                    [
                      { id: "1080p", title: "Full HD", sub: "1080p • 18 Mbps" },
                      { id: "2k", title: "2K QHD", sub: "1440p • 28 Mbps" },
                      { id: "4k", title: "4K UHD", sub: "2160p • 42 Mbps" },
                    ] as const
                  ).map((item) => {
                    const dims = activeResOptions?.[item.id];
                    const active = targetRes === item.id;
                    return (
                      <button
                        key={item.id}
                        type="button"
                        disabled={isRendering}
                        onClick={() => setTargetRes(item.id)}
                        className={`rounded-xl border p-2.5 text-center transition cursor-pointer ${
                          active
                            ? "border-emerald-500 bg-emerald-950/35 text-white"
                            : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        <div className="text-xs font-extrabold">{item.title}</div>
                        <div className="text-[10px] text-emerald-300 font-semibold mt-0.5">
                          {dims ? `${dims.width}×${dims.height}` : item.sub}
                        </div>
                        <div className="text-[9px] text-zinc-500 mt-0.5">{item.sub}</div>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* 3. DETAIL, FACE & COLOR TUNING */}
            <div className="rounded-2xl border border-zinc-800/90 bg-zinc-900/70 p-4 space-y-4">
              <span className="text-xs font-extrabold uppercase tracking-wider text-zinc-300 flex items-center gap-1.5">
                <Sliders className="h-3.5 w-3.5 text-pink-400" />
                3. Tinh Chỉnh Độ Nét, Khuôn Mặt & Màu Sắc
              </span>

              {/* Denoise / De-artifact Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-zinc-200">
                    Khử vỡ hạt & Bệt khối nén (Denoise)
                  </span>
                  <span className="font-extrabold text-violet-300">{denoise}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  disabled={isRendering}
                  value={denoise}
                  onChange={(e) => setDenoise(Number(e.target.value))}
                  className="w-full accent-violet-500 cursor-pointer"
                />
                <div className="flex justify-between text-[10px] text-zinc-500">
                  <span>0% (Giữ hạt gốc)</span>
                  <span>55% (Cân bằng)</span>
                  <span>100% (Khử bệt tối đa)</span>
                </div>
              </div>

              {/* Micro-Sharpen Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-zinc-200">
                    Tăng chi tiết vi mô (Micro-Sharpen)
                  </span>
                  <span className="font-extrabold text-violet-300">{sharpen}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  disabled={isRendering}
                  value={sharpen}
                  onChange={(e) => setSharpen(Number(e.target.value))}
                  className="w-full accent-violet-500 cursor-pointer"
                />
              </div>

              {/* Color Mastering Preset */}
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-zinc-200">
                  Tông màu & Cứu sáng
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {COLOR_PRESET_OPTIONS.map((c) => {
                    const active = colorPreset === c.id;
                    return (
                      <button
                        key={c.id}
                        type="button"
                        disabled={isRendering}
                        onClick={() => setColorPreset(c.id)}
                        className={`rounded-xl border px-3 py-2 text-left transition cursor-pointer ${
                          active
                            ? "border-pink-500/80 bg-pink-950/25 text-white"
                            : "border-zinc-800 bg-zinc-950/70 text-zinc-400 hover:text-zinc-200"
                        }`}
                      >
                        <div className="text-xs font-bold">{c.label}</div>
                        <div className="text-[10px] text-zinc-500 truncate">{c.sub}</div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Smart Checkboxes */}
              <div className="space-y-2 pt-1">
                {engine === "ai_realesrgan" && (
                  <label className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/75 px-3 py-2.5 cursor-pointer">
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-zinc-100">
                        👤 AI Phục hồi nét mặt & Đôi mắt (YuNet)
                      </div>
                      <div className="text-[10px] text-zinc-400">
                        Làm rõ tròng mắt, hàng mi & mịn da không gây méo mặt
                      </div>
                    </div>
                    <input
                      type="checkbox"
                      checked={faceRestore}
                      disabled={isRendering}
                      onChange={(e) => setFaceRestore(e.target.checked)}
                      className="h-4 w-4 accent-violet-500 cursor-pointer"
                    />
                  </label>
                )}

                <label className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/75 px-3 py-2.5 cursor-pointer">
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-zinc-100">
                      ✂️ Tự động cắt bỏ 2 viền đen thừa
                    </div>
                    <div className="text-[10px] text-zinc-400">
                      Chuẩn hóa khung hình tràn viền trước khi phóng nét
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={cropBars}
                    disabled={isRendering}
                    onChange={(e) => setCropBars(e.target.checked)}
                    className="h-4 w-4 accent-violet-500 cursor-pointer"
                  />
                </label>

                <label className="flex items-center justify-between gap-3 rounded-xl border border-zinc-800 bg-zinc-950/75 px-3 py-2.5 cursor-pointer">
                  <div className="min-w-0">
                    <div className="text-xs font-bold text-zinc-100">
                      🎞️ Làm mượt chuyển động lên 60 FPS
                    </div>
                    <div className="text-[10px] text-zinc-400">
                      Nội suy khung hình chống giật cho video 24/30 FPS
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={fpsMode === "smooth_60fps"}
                    disabled={isRendering}
                    onChange={(e) =>
                      setFpsMode(e.target.checked ? "smooth_60fps" : "keep")
                    }
                    className="h-4 w-4 accent-violet-500 cursor-pointer"
                  />
                </label>
              </div>
            </div>

            {/* 4. FULL VIDEO RENDER CTA + REAL-TIME PROGRESS + DOWNLOAD */}
            <div className="rounded-2xl border border-violet-500/40 bg-gradient-to-b from-violet-950/30 to-zinc-900/90 p-4 space-y-3.5 shadow-xl">
              {!isRendering ? (
                <button
                  type="button"
                  onClick={() => void handleStartFullRender()}
                  className="w-full flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-500 hover:to-fuchsia-500 px-5 py-3.5 text-sm font-extrabold text-white shadow-lg shadow-violet-600/30 transition cursor-pointer"
                >
                  <Sparkles className="h-4 w-4" />
                  <span>
                    Bắt Đầu Nâng Cấp Toàn Bộ Video ({targetRes.toUpperCase()})
                  </span>
                </button>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-extrabold text-violet-200 flex items-center gap-2">
                      <Loader2 className="h-4 w-4 animate-spin text-violet-400" />
                      Đang nâng cấp toàn bộ video...
                    </span>
                    <span className="text-sm font-extrabold text-white">
                      {Math.round(renderJob?.percent || 1)}%
                    </span>
                  </div>

                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-zinc-950 border border-zinc-800">
                    <div
                      style={{
                        width: `${Math.max(2, Math.min(100, renderJob?.percent || 2))}%`,
                      }}
                      className="h-full bg-gradient-to-r from-violet-500 via-fuchsia-500 to-emerald-400 transition-all duration-300"
                    />
                  </div>

                  <div className="text-[11px] text-zinc-300 leading-relaxed">
                    {renderJob?.stage || "Đang xử lý khung hình..."}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-zinc-400">
                    <span>
                      {renderJob?.total_frames
                        ? `Frame ${renderJob.processed_frames || 0} / ${renderJob.total_frames}`
                        : "Đang chuẩn bị luồng..."}
                      {renderJob?.fps ? ` • ${renderJob.fps} FPS` : ""}
                      {renderJob?.eta_s !== null && renderJob?.eta_s !== undefined
                        ? ` • Còn ~${renderJob.eta_s}s`
                        : ""}
                    </span>

                    <button
                      type="button"
                      onClick={() => void handleCancelRender()}
                      className="inline-flex items-center gap-1 rounded-lg border border-red-500/40 bg-red-950/40 hover:bg-red-900/50 px-2.5 py-1 text-[11px] font-bold text-red-200 cursor-pointer"
                    >
                      <Square className="h-3 w-3" />
                      Dừng
                    </button>
                  </div>
                </div>
              )}

              {/* Error Notice */}
              {renderJob?.status === "error" && (
                <div className="rounded-xl border border-red-500/40 bg-red-950/30 p-3 text-xs text-red-200">
                  ⚠️ {renderJob.error}
                </div>
              )}

              {/* Completed Result & Download Card */}
              {completedJob && (
                <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/25 p-3.5 space-y-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-extrabold text-emerald-300 flex items-center gap-1.5">
                      <Check className="h-4 w-4" />
                      Đã xuất bản nét căng thành công!
                    </span>
                    <span className="text-[11px] font-bold text-zinc-300">
                      {completedJob.elapsed_s}s • {completedJob.size_mb} MB
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[11px]">
                    <div className="rounded-lg bg-zinc-950/80 border border-zinc-800 px-2.5 py-1.5">
                      <div className="text-zinc-500">Độ phân giải</div>
                      <div className="font-bold text-white">
                        {completedJob.orig_width}×{completedJob.orig_height} →{" "}
                        <span className="text-emerald-300">
                          {completedJob.out_width}×{completedJob.out_height}
                        </span>
                      </div>
                    </div>
                    <div className="rounded-lg bg-zinc-950/80 border border-zinc-800 px-2.5 py-1.5">
                      <div className="text-zinc-500">Tốc độ khung & Bitrate</div>
                      <div className="font-bold text-white">
                        {completedJob.out_fps} FPS • {completedJob.bitrate_mbps} Mbps
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <a
                      href={enhancedDownloadUrl}
                      download={downloadFileName}
                      className="flex items-center justify-center gap-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 px-3.5 py-2.5 text-xs font-extrabold text-white shadow-lg shadow-emerald-600/20 transition"
                    >
                      <Download className="h-4 w-4" />
                      Tải Video Về Máy (.MP4)
                    </a>

                    <button
                      type="button"
                      disabled={savingToDownloads}
                      onClick={() => void handleSaveToDownloads()}
                      className="flex items-center justify-center gap-1.5 rounded-xl border border-zinc-700 bg-zinc-900 hover:bg-zinc-800 px-3.5 py-2.5 text-xs font-bold text-zinc-200 transition cursor-pointer disabled:opacity-50"
                    >
                      <FolderOpen className="h-4 w-4 text-amber-400" />
                      {savingToDownloads ? "Đang lưu..." : "Lưu Vào ~/Downloads"}
                    </button>
                  </div>

                  {savedLocalPath && (
                    <div className="text-[11px] text-emerald-300 truncate">
                      📁 Đã lưu: {savedLocalPath}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
