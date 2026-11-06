import { execFile } from "node:child_process";
import { mkdir, readFile, realpath, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export const OUTLIER_VIDEO_ID_RE = /^[A-Za-z0-9_-]{11}$/;
const SAFE_OUTLIER_MEDIA_RE =
  /^(?:contact_sheet\.jpg|keyframes\/[A-Za-z0-9_-]{1,32}\.jpg)$/;

export const DEFAULT_CHANNEL_ROOT = path.resolve(
  process.cwd(),
  "..",
  "youtube-shorts-channel"
);

export const DEFAULT_OUTLIERS_ROOT =
  process.env.POW_OUTLIERS_DIR ||
  path.join(DEFAULT_CHANNEL_ROOT, "research", "outliers");

export const DEFAULT_POW_PYTHON =
  process.env.POW_STUDIO_PYTHON ||
  path.join(DEFAULT_CHANNEL_ROOT, ".venv", "bin", "python");

export type OutlierAnalysisMode = "download" | "transcript_only";

export interface OutlierSceneItem {
  index: number;
  sid: string;
  start_s: number;
  end_s: number;
  duration_s: number;
  motion_class: string;
  is_real_moving: boolean;
  is_baked_animated_still: boolean;
  is_text_heavy_graphic: boolean;
  spoken_text: string;
  start_keyframe: string | null;
  mid_keyframe: string | null;
}

export interface OutlierPhaseRow {
  phase_id: string;
  label: string;
  start_s: number;
  end_s: number;
  span_s: number;
  cut_count: number;
  cuts_per_10s: number;
  median_shot_duration_s: number;
  word_count: number;
  words_per_second: number;
  moving_footage_pct: number;
  text_heavy_pct: number;
}

export interface OutlierAnatomyBrief {
  brief_version: string;
  analyzed_at: string;
  target_id: string;
  mode: string;
  media_deleted: boolean;
  duration_s: number;
  width: number;
  height: number;
  fps: number;
  scene_detector: string;
  transcript_source: string;
  scene_count: number;
  cut_count: number;
  cuts_per_10s_overall: number | null;
  median_shot_duration_s: number | null;
  word_count: number;
  words_per_second_overall: number;
  metadata: {
    video_id: string;
    title: string;
    channel: string;
    duration_s: number;
    view_count: number;
  };
  hook_and_loop: {
    opening_hook_type: string;
    first_word_time_s: number | null;
    frame0_has_text_overlay: boolean | null;
    cta_position_s: number | null;
    first_last_dhash_distance: number | null;
    loop_similarity_score: number | null;
  };
  visual_mix: {
    real_moving_pct: number | null;
    static_or_animated_still_pct: number | null;
    graphic_or_slide_pct: number | null;
  };
  phases: OutlierPhaseRow[];
  scenes: OutlierSceneItem[];
  contact_sheet: string | null;
  transcript_preview: string;
  our_channel_baseline?: {
    episodes_count: number;
    median_duration_s?: number;
    median_cuts_per_10s?: number;
    median_hook_0_3s_cuts?: number;
    median_shot_duration_s?: number;
  };
  agent_annotations: {
    hook_5_aspects: Record<string, string>;
    what_works: string[];
    differentiation_seeds: string[];
  };
}

export interface OutlierStatusFile {
  status: "queued" | "running" | "completed" | "failed" | "idle";
  stage?: string;
  detail?: string;
  error?: string;
  updated_at?: string;
}

let queueTail: Promise<void> = Promise.resolve();
const activeOrQueuedIds = new Set<string>();

async function readJsonSafe<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await readFile(/*turbopackIgnore: true*/ filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function getOutlierAnalysisRecord(videoId: string): Promise<{
  videoId: string;
  status: OutlierStatusFile;
  brief: OutlierAnatomyBrief | null;
}> {
  if (!OUTLIER_VIDEO_ID_RE.test(videoId)) {
    throw new Error("videoId không hợp lệ (cần đúng 11 ký tự YouTube ID).");
  }
  const rootResolved = path.resolve(DEFAULT_OUTLIERS_ROOT);
  const videoDir = path.resolve(rootResolved, videoId);
  if (!videoDir.startsWith(rootResolved + path.sep)) {
    throw new Error("Đường dẫn không hợp lệ.");
  }

  const [statusRaw, brief] = await Promise.all([
    readJsonSafe<OutlierStatusFile>(path.join(videoDir, "status.json")),
    readJsonSafe<OutlierAnatomyBrief>(
      path.join(videoDir, "outlier_anatomy_brief.json")
    ),
  ]);

  if (brief && (!statusRaw || statusRaw.status !== "running")) {
    return {
      videoId,
      status: statusRaw || { status: "completed", stage: "done" },
      brief,
    };
  }

  if (activeOrQueuedIds.has(videoId) && !statusRaw) {
    return {
      videoId,
      status: {
        status: "queued",
        stage: "queue",
        detail: "Đang chờ hàng đợi phân tích cục bộ (1 job/lần)...",
      },
      brief: null,
    };
  }

  return {
    videoId,
    status: statusRaw || { status: "idle" },
    brief: brief || null,
  };
}

export async function enqueueOutlierAnalysisJob(params: {
  videoId: string;
  mode?: OutlierAnalysisMode;
  force?: boolean;
}): Promise<{
  videoId: string;
  status: OutlierStatusFile;
  brief: OutlierAnatomyBrief | null;
}> {
  const { videoId } = params;
  const mode: OutlierAnalysisMode =
    params.mode === "transcript_only" ? "transcript_only" : "download";

  if (!OUTLIER_VIDEO_ID_RE.test(videoId)) {
    throw new Error("videoId không hợp lệ (cần đúng 11 ký tự YouTube ID).");
  }

  const existing = await getOutlierAnalysisRecord(videoId);
  if (existing.brief && !params.force) {
    return existing;
  }
  if (activeOrQueuedIds.has(videoId)) {
    return existing;
  }

  const rootResolved = path.resolve(DEFAULT_OUTLIERS_ROOT);
  const videoDir = path.resolve(rootResolved, videoId);
  await mkdir(/*turbopackIgnore: true*/ videoDir, { recursive: true });
  const queuedStatus: OutlierStatusFile = {
    status: "queued",
    stage: "queue",
    detail: `Đã xếp hàng phân tích (${mode})`,
    updated_at: new Date().toISOString(),
  };
  await writeFile(
    /*turbopackIgnore: true*/ path.join(videoDir, "status.json"),
    JSON.stringify(queuedStatus, null, 2),
    "utf-8"
  );

  activeOrQueuedIds.add(videoId);
  queueTail = queueTail
    .catch(() => undefined)
    .then(async () => {
      try {
        await execFileAsync(
          DEFAULT_POW_PYTHON,
          [
            "-m",
            "pow_studio.cli",
            "analyze-outlier",
            "--video-id",
            videoId,
            "--mode",
            mode,
          ],
          {
            cwd: DEFAULT_CHANNEL_ROOT,
            env: {
              ...process.env,
              PYTHONPATH: "pipeline",
              PATH: `/opt/homebrew/bin:/usr/local/bin:${process.env.PATH || "/usr/bin:/bin"}`,
            },
            timeout: 180_000,
            maxBuffer: 8 * 1024 * 1024,
          }
        );
      } catch (err) {
        const failedStatus: OutlierStatusFile = {
          status: "failed",
          stage: "error",
          error:
            err instanceof Error
              ? err.message.slice(0, 400)
              : "Lỗi khi chạy pow_studio outlier_analyst.",
          updated_at: new Date().toISOString(),
        };
        await writeFile(
          /*turbopackIgnore: true*/ path.join(videoDir, "status.json"),
          JSON.stringify(failedStatus, null, 2),
          "utf-8"
        ).catch(() => undefined);
      } finally {
        activeOrQueuedIds.delete(videoId);
      }
    });

  return {
    videoId,
    status: queuedStatus,
    brief: null,
  };
}

export async function resolveSafeOutlierMediaPath(
  videoId: string,
  relFile: string
): Promise<string | null> {
  if (
    !OUTLIER_VIDEO_ID_RE.test(videoId) ||
    !SAFE_OUTLIER_MEDIA_RE.test(relFile)
  ) {
    return null;
  }
  const rootResolved = path.resolve(DEFAULT_OUTLIERS_ROOT);
  const videoDir = path.resolve(rootResolved, videoId);
  if (!videoDir.startsWith(rootResolved + path.sep)) {
    return null;
  }

  try {
    const dirReal = await realpath(/*turbopackIgnore: true*/ videoDir);
    const targetCandidate = path.resolve(dirReal, relFile);
    if (!targetCandidate.startsWith(dirReal + path.sep)) {
      return null;
    }
    const targetReal = await realpath(/*turbopackIgnore: true*/ targetCandidate);
    if (!targetReal.startsWith(dirReal + path.sep)) {
      return null;
    }
    const st = await stat(/*turbopackIgnore: true*/ targetReal);
    if (!st.isFile()) return null;
    return targetReal;
  } catch {
    return null;
  }
}
