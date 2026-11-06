import { appendFile, mkdir, readdir, readFile, realpath, rename, stat, writeFile } from "node:fs/promises";
import path from "node:path";
import { DEFAULT_MAC_OUTPUT_ROOT } from "./mac-pipeline";

export const BACKLOT_SLUG_RE = /^[a-z0-9][a-z0-9_-]{1,80}$/;

const SAFE_MEDIA_FILE_RE =
  /^(?:board\/[A-Za-z0-9_-]{1,32}_(?:in|mid|out)\.jpg|thumbnail\.jpg|thumbnail_variant_[bc]\.jpg|thumbnail_concept_[A-Z0-9]\.jpg|pre_render_storyboard_contact_sheet\.jpg|cover_ab_comparison_sheet\.jpg)$/;

export const PROTECTED_COMPLETED_OUTPUT_DIRS = new Set<string>([
  "blood-falls-20261028",
  "blood-falls-20261028-v2-studio",
  "brine-pools-20261029",
  "blood-falls-v3-documentary",
  "brine-pools-v4-documentary",
  "forbidden-zones-earth-v4-documentary",
  "gemstone-mine-secrets-v4-documentary",
  "lava-cave-gold-v4-documentary",
  "unreal-places-earth-v4-documentary",
  "day-in-the-life-of-an-astronaut",
  "fermi-paradox-v4-documentary",
  "how-high-could-you-jump-on-other-planets",
  "mars-helicopter-1-percent-air",
  "venus-hotter-than-mercury",
]);

export const STUDIO_GATE_ORDER = [
  "feasibility",
  "voice_lock",
  "storyboard_approval",
  "render_master",
  "qa_six_pillar",
  "publish",
] as const;

export type StudioGateName = (typeof STUDIO_GATE_ORDER)[number];

export interface StudioGateEntry {
  status: string;
  detail?: string;
  updated_at?: string;
}

export interface StudioEventRow {
  ts: string;
  stage: string;
  event: string;
  status: string;
  detail?: string;
  artifacts?: string[];
  data?: Record<string, unknown>;
}

export interface StudioStateFile {
  state_version?: string;
  slug?: string;
  updated_at?: string;
  stages?: Record<
    string,
    {
      status?: string;
      started_at?: string | null;
      finished_at?: string | null;
      duration_s?: number;
      detail?: string;
      artifacts?: string[];
    }
  >;
  gates?: Partial<Record<StudioGateName | string, StudioGateEntry>>;
}

export interface StoryboardApprovalStatus {
  required: boolean;
  status:
    | "approved"
    | "changes_requested"
    | "stale_hash_mismatch"
    | "pending"
    | "not_required";
  approved: boolean;
  hash_matches: boolean;
  current_storyboard_sha256: string | null;
  approved_storyboard_sha256: string | null;
  decision: "approved" | "changes_requested" | null;
  approved_at: string | null;
  notes: string;
  shot_notes: Record<string, string>;
}

export interface BacklotOverlayItem {
  overlay_id: string;
  template: string;
  start_s: number;
  end_s: number;
  max_alpha_area_ratio?: number | null;
}

export interface BacklotQaIssue {
  pillar?: string;
  severity?: string;
  code?: string;
  sid?: string;
  message?: string;
}

export interface BacklotShotCard {
  index: number;
  sid: string;
  start_s: number;
  end_s: number;
  duration_s: number;
  kind: string;
  src_file: string;
  src_in: number;
  associated_seg_id?: string | null;
  story_beat?: string | null;
  visual_desc?: string | null;
  narration_text: string;
  transition_in: string;
  transition_duration_s: number;
  reframe: {
    mode: string;
    cx0: number;
    cy0: number;
    cx1: number;
    cy1: number;
    z0: number;
    z1: number;
  };
  media_class: string;
  source_media_class: string;
  counts_as_genuine_moving: boolean;
  license: string;
  creator_agency: string;
  source_page_url: string;
  clip_percentile: number | null;
  possible_mislabeled_asset: boolean;
  scene_editor_decision: string;
  overlays: BacklotOverlayItem[];
  qa_issues: BacklotQaIssue[];
  reviewer_note: string;
  frames: {
    in: string | null;
    mid: string | null;
    out: string | null;
  };
}

export interface BacklotThumbnailConcept {
  concept_id: string;
  file: string;
  headline_text: string;
  kicker_text: string;
  rationale: string;
}

export interface BacklotBoardPayload {
  board_version: string;
  exported_at: string;
  slug: string;
  playlist: string;
  primary_title: string;
  alternative_title?: string | null;
  topic: string;
  manifest_version: string;
  style_profile: string;
  visual_corpus_mode: "off" | "shadow" | "on";
  require_storyboard_approval: boolean;
  storyboard_sha256: string;
  has_locked_voice: boolean;
  has_real_word_timings: boolean;
  has_rendered_mp4: boolean;
  total_duration_s: number;
  shot_count: number;
  coverage_metrics: {
    genuine_moving_footage_pct: number;
    meaningful_action_footage_pct: number;
    establishing_footage_pct: number;
    static_image_pct: number;
    animated_still_pct: number;
    scientific_visualization_pct: number;
    mechanism_overlay_pct: number;
  };
  qa_summary: {
    six_pillar_present: boolean;
    technical_approval?: boolean | null;
    creative_approval?: boolean | null;
    overall_release_approval?: boolean | null;
    issues_count: number;
    issues: BacklotQaIssue[];
  };
  approval: StoryboardApprovalStatus;
  thumbnail_concepts: BacklotThumbnailConcept[];
  shots: BacklotShotCard[];
}

export interface BacklotEpisodeSummary {
  slug: string;
  playlist: string;
  primaryTitle: string;
  manifestVersion: string;
  hasBoard: boolean;
  hasRenderedMp4: boolean;
  hasLockedVoice: boolean;
  shotCount: number;
  totalDurationSec: number | null;
  genuineMovingPct: number | null;
  mechanismOverlayPct: number | null;
  requireStoryboardApproval: boolean;
  storyboardSha256: string | null;
  approvalStatus: StoryboardApprovalStatus["status"];
  gates: Record<StudioGateName, StudioGateEntry>;
  isProtectedCompleted: boolean;
  updatedAtIso: string;
}

export interface BacklotEpisodeDetail {
  summary: BacklotEpisodeSummary;
  board: BacklotBoardPayload | null;
  studioState: StudioStateFile;
  recentEvents: StudioEventRow[];
  hasContactSheet: boolean;
}

interface RawApprovalJson {
  gate?: string;
  decision?: string;
  storyboard_sha256?: string;
  notes?: string;
  shotNotes?: Record<string, string>;
  shot_notes?: Record<string, string>;
  approved_at?: string;
}

async function readJsonSafe<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    const s = await stat(/*turbopackIgnore: true*/ filePath);
    return s.isFile();
  } catch {
    return false;
  }
}

async function atomicWriteJson(filePath: string, data: unknown): Promise<void> {
  const dir = path.dirname(filePath);
  await mkdir(dir, { recursive: true });
  const tmpPath = path.join(
    dir,
    `.${path.basename(filePath)}.${process.pid}.${Date.now()}.tmp`
  );
  await writeFile(tmpPath, JSON.stringify(data, null, 2), "utf-8");
  await rename(tmpPath, filePath);
}

async function readRecentEvents(
  episodeDir: string,
  limit = 50
): Promise<StudioEventRow[]> {
  try {
    const raw = await readFile(
      path.join(episodeDir, "studio_events.jsonl"),
      "utf-8"
    );
    const lines = raw.split(/\r?\n/).filter((ln) => ln.trim().length > 0);
    const tail = lines.slice(-limit);
    const parsed: StudioEventRow[] = [];
    for (const ln of tail) {
      try {
        parsed.push(JSON.parse(ln) as StudioEventRow);
      } catch {
        // skip malformed line
      }
    }
    return parsed;
  } catch {
    return [];
  }
}

function computeLiveApprovalStatus(
  board: BacklotBoardPayload | null,
  rawApproval: RawApprovalJson | null
): StoryboardApprovalStatus {
  const required = Boolean(board?.require_storyboard_approval);
  const currentSha = board?.storyboard_sha256 || null;

  if (!rawApproval) {
    return {
      required,
      status: required ? "pending" : "not_required",
      approved: false,
      hash_matches: false,
      current_storyboard_sha256: currentSha,
      approved_storyboard_sha256: null,
      decision: null,
      approved_at: null,
      notes: "",
      shot_notes: {},
    };
  }

  const savedSha = rawApproval.storyboard_sha256 || null;
  const decision =
    rawApproval.decision === "approved" ||
    rawApproval.decision === "changes_requested"
      ? rawApproval.decision
      : null;
  const hashMatches = Boolean(currentSha && savedSha && currentSha === savedSha);
  const isApproved = decision === "approved" && hashMatches;

  let status: StoryboardApprovalStatus["status"] = "pending";
  if (decision === "changes_requested") {
    status = "changes_requested";
  } else if (decision === "approved" && !hashMatches) {
    status = "stale_hash_mismatch";
  } else if (isApproved) {
    status = "approved";
  } else if (!required) {
    status = "not_required";
  }

  const rawNotesMap = rawApproval.shotNotes || rawApproval.shot_notes || {};
  const cleanShotNotes: Record<string, string> = {};
  for (const [k, v] of Object.entries(rawNotesMap)) {
    if (typeof v === "string" && v.trim()) {
      cleanShotNotes[k] = v.trim();
    }
  }

  return {
    required,
    status,
    approved: isApproved,
    hash_matches: hashMatches,
    current_storyboard_sha256: currentSha,
    approved_storyboard_sha256: savedSha,
    decision,
    approved_at: rawApproval.approved_at || null,
    notes: typeof rawApproval.notes === "string" ? rawApproval.notes : "",
    shot_notes: cleanShotNotes,
  };
}

function buildNormalizedGates(
  studioState: StudioStateFile,
  board: BacklotBoardPayload | null,
  approval: StoryboardApprovalStatus,
  hasRenderedMp4: boolean,
  hasLockedVoice: boolean,
  hasPublishedRecord: boolean
): Record<StudioGateName, StudioGateEntry> {
  const rawGates = studioState.gates || {};
  const gates: Record<StudioGateName, StudioGateEntry> = {
    feasibility: rawGates.feasibility || { status: "pending" },
    voice_lock:
      rawGates.voice_lock ||
      (hasLockedVoice
        ? { status: "passed", detail: "voice_approval_lock.json" }
        : { status: "pending" }),
    storyboard_approval:
      approval.status === "approved"
        ? {
            status: "passed",
            detail: `sha256=${(approval.current_storyboard_sha256 || "").slice(0, 12)}`,
            updated_at: approval.approved_at || undefined,
          }
        : approval.status === "changes_requested"
        ? {
            status: "changes_requested",
            detail: approval.notes || "Yêu cầu chỉnh sửa shot",
            updated_at: approval.approved_at || undefined,
          }
        : approval.status === "stale_hash_mismatch"
        ? {
            status: "blocked",
            detail: "Storyboard đã thay đổi sau lần duyệt trước",
          }
        : rawGates.storyboard_approval || {
            status: approval.required ? "pending" : "not_required",
          },
    render_master:
      rawGates.render_master ||
      (hasRenderedMp4
        ? { status: "passed", detail: "MP4 master present" }
        : { status: "pending" }),
    qa_six_pillar:
      rawGates.qa_six_pillar ||
      (board?.qa_summary?.six_pillar_present
        ? {
            status: board.qa_summary.overall_release_approval
              ? "passed"
              : "blocked",
          }
        : { status: "pending" }),
    publish:
      rawGates.publish ||
      (hasPublishedRecord ? { status: "passed" } : { status: "pending" }),
  };
  return gates;
}

export async function resolveBacklotEpisodeDir(slug: string): Promise<{
  slug: string;
  playlist: string;
  episodeDir: string;
} | null> {
  if (!BACKLOT_SLUG_RE.test(slug)) {
    return null;
  }
  const rootResolved = path.resolve(DEFAULT_MAC_OUTPUT_ROOT);
  let playlistEntries;
  try {
    playlistEntries = await readdir(rootResolved, { withFileTypes: true });
  } catch {
    return null;
  }

  for (const pl of playlistEntries) {
    if (!pl.isDirectory() || pl.name.startsWith(".")) continue;
    const candidate = path.resolve(rootResolved, pl.name, slug);
    if (!candidate.startsWith(rootResolved + path.sep)) continue;
    try {
      const st = await stat(candidate);
      if (!st.isDirectory()) continue;
      const hasBoard = await fileExists(
        path.join(candidate, "board", "storyboard_board.json")
      );
      const hasState = await fileExists(
        path.join(candidate, "studio_state.json")
      );
      if (hasBoard || hasState) {
        return { slug, playlist: pl.name, episodeDir: candidate };
      }
    } catch {
      continue;
    }
  }
  return null;
}

async function buildSummaryForDir(
  slug: string,
  playlistDirName: string,
  episodeDir: string
): Promise<{
  summary: BacklotEpisodeSummary;
  board: BacklotBoardPayload | null;
  studioState: StudioStateFile;
} | null> {
  const boardPath = path.join(episodeDir, "board", "storyboard_board.json");
  const statePath = path.join(episodeDir, "studio_state.json");
  const approvalPath = path.join(episodeDir, "storyboard_approval.json");

  const [board, studioStateRaw, rawApproval] = await Promise.all([
    readJsonSafe<BacklotBoardPayload>(boardPath),
    readJsonSafe<StudioStateFile>(statePath),
    readJsonSafe<RawApprovalJson>(approvalPath),
  ]);

  if (!board && !studioStateRaw) {
    return null;
  }

  const studioState: StudioStateFile = studioStateRaw || {
    state_version: "9.0",
    slug,
    stages: {},
    gates: {},
  };

  const hasRenderedMp4 =
    Boolean(board?.has_rendered_mp4) ||
    (await fileExists(path.join(episodeDir, `${slug}.mp4`)));
  const hasLockedVoice =
    Boolean(board?.has_locked_voice) ||
    (await fileExists(path.join(episodeDir, "voice_approval_lock.json")));

  const approval = computeLiveApprovalStatus(board, rawApproval);
  if (board) {
    board.approval = approval;
    board.has_rendered_mp4 = hasRenderedMp4;
    board.has_locked_voice = hasLockedVoice;
    for (const sh of board.shots || []) {
      sh.reviewer_note = approval.shot_notes[sh.sid] || sh.reviewer_note || "";
    }
  }

  const gates = buildNormalizedGates(
    studioState,
    board,
    approval,
    hasRenderedMp4,
    hasLockedVoice,
    false
  );

  // Determine latest update timestamp
  let latestMs = 0;
  for (const p of [boardPath, statePath, approvalPath]) {
    try {
      const s = await stat(/*turbopackIgnore: true*/ p);
      if (s.mtimeMs > latestMs) latestMs = s.mtimeMs;
    } catch {
      // ignore missing
    }
  }
  const updatedAtIso =
    latestMs > 0
      ? new Date(latestMs).toISOString()
      : studioState.updated_at ||
        board?.exported_at ||
        new Date().toISOString();

  const summary: BacklotEpisodeSummary = {
    slug,
    playlist: board?.playlist || playlistDirName,
    primaryTitle: board?.primary_title || slug,
    manifestVersion: board?.manifest_version || "8.0",
    hasBoard: Boolean(board),
    hasRenderedMp4,
    hasLockedVoice,
    shotCount: board?.shot_count ?? 0,
    totalDurationSec: board?.total_duration_s ?? null,
    genuineMovingPct:
      board?.coverage_metrics?.genuine_moving_footage_pct ?? null,
    mechanismOverlayPct:
      board?.coverage_metrics?.mechanism_overlay_pct ?? null,
    requireStoryboardApproval: Boolean(board?.require_storyboard_approval),
    storyboardSha256: board?.storyboard_sha256 || null,
    approvalStatus: approval.status,
    gates,
    isProtectedCompleted: PROTECTED_COMPLETED_OUTPUT_DIRS.has(slug),
    updatedAtIso,
  };

  return { summary, board, studioState };
}

export async function listBacklotEpisodes(): Promise<BacklotEpisodeSummary[]> {
  const rootResolved = path.resolve(DEFAULT_MAC_OUTPUT_ROOT);
  let playlistEntries;
  try {
    playlistEntries = await readdir(rootResolved, { withFileTypes: true });
  } catch {
    return [];
  }

  const summaries: BacklotEpisodeSummary[] = [];
  for (const pl of playlistEntries) {
    if (!pl.isDirectory() || pl.name.startsWith(".")) continue;
    const plPath = path.join(rootResolved, pl.name);
    let epEntries;
    try {
      epEntries = await readdir(plPath, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ep of epEntries) {
      if (!ep.isDirectory() || !BACKLOT_SLUG_RE.test(ep.name)) continue;
      const epPath = path.join(plPath, ep.name);
      const item = await buildSummaryForDir(ep.name, pl.name, epPath);
      if (item) {
        summaries.push(item.summary);
      }
    }
  }

  summaries.sort((a, b) => b.updatedAtIso.localeCompare(a.updatedAtIso));
  return summaries;
}

export async function getBacklotEpisodeDetail(
  slug: string
): Promise<BacklotEpisodeDetail | null> {
  const resolved = await resolveBacklotEpisodeDir(slug);
  if (!resolved) return null;

  const built = await buildSummaryForDir(
    resolved.slug,
    resolved.playlist,
    resolved.episodeDir
  );
  if (!built) return null;

  const [recentEvents, hasContactSheet] = await Promise.all([
    readRecentEvents(resolved.episodeDir, 50),
    fileExists(
      path.join(
        resolved.episodeDir,
        "pre_render_storyboard_contact_sheet.jpg"
      )
    ),
  ]);

  return {
    summary: built.summary,
    board: built.board,
    studioState: built.studioState,
    recentEvents,
    hasContactSheet,
  };
}

export async function resolveSafeBacklotMediaPath(
  slug: string,
  relFile: string
): Promise<string | null> {
  if (!SAFE_MEDIA_FILE_RE.test(relFile)) {
    return null;
  }
  const resolved = await resolveBacklotEpisodeDir(slug);
  if (!resolved) return null;

  try {
    const epReal = await realpath(resolved.episodeDir);
    const targetCandidate = path.resolve(epReal, relFile);
    if (!targetCandidate.startsWith(epReal + path.sep)) {
      return null;
    }
    const targetReal = await realpath(targetCandidate);
    if (!targetReal.startsWith(epReal + path.sep)) {
      return null;
    }
    const st = await stat(targetReal);
    if (!st.isFile()) return null;
    return targetReal;
  } catch {
    return null;
  }
}

export async function writeBacklotApprovalDecision(params: {
  slug: string;
  gate?: string;
  decision: "approved" | "changes_requested";
  notes?: string;
  shotNotes?: Record<string, string>;
}): Promise<{
  approval: StoryboardApprovalStatus;
  savedPayload: Record<string, unknown>;
}> {
  const { slug, decision } = params;
  if (decision !== "approved" && decision !== "changes_requested") {
    throw new Error("Quyết định không hợp lệ (chỉ chấp nhận approved hoặc changes_requested).");
  }
  if (PROTECTED_COMPLETED_OUTPUT_DIRS.has(slug)) {
    throw new Error(`Thư mục tập '${slug}' nằm trong danh sách bảo vệ chống ghi đè.`);
  }

  const resolved = await resolveBacklotEpisodeDir(slug);
  if (!resolved) {
    throw new Error(`Không tìm thấy tập '${slug}' trong Backlot.`);
  }

  const boardPath = path.join(
    resolved.episodeDir,
    "board",
    "storyboard_board.json"
  );
  const board = await readJsonSafe<BacklotBoardPayload>(boardPath);
  if (!board || !board.storyboard_sha256) {
    throw new Error(
      `Tập '${slug}' chưa có storyboard_board.json. Hãy chạy lệnh export-storyboard trước khi duyệt.`
    );
  }

  const cleanNotes = (params.notes || "").trim().slice(0, 2000);
  const cleanShotNotes: Record<string, string> = {};
  for (const [k, v] of Object.entries(params.shotNotes || {})) {
    const sid = String(k).trim();
    const note = typeof v === "string" ? v.trim().slice(0, 800) : "";
    if (/^[A-Za-z0-9_-]{1,32}$/.test(sid) && note) {
      cleanShotNotes[sid] = note;
    }
  }

  const nowIso = new Date().toISOString();
  const gateName = params.gate || "storyboard_approval";
  const savedPayload = {
    gate: gateName,
    decision,
    storyboard_sha256: board.storyboard_sha256,
    notes: cleanNotes,
    shotNotes: cleanShotNotes,
    approved_at: nowIso,
  };

  await atomicWriteJson(
    path.join(resolved.episodeDir, "storyboard_approval.json"),
    savedPayload
  );

  // Sync studio_state.json + studio_events.jsonl with exact Python pow_studio.events schema
  const statePath = path.join(resolved.episodeDir, "studio_state.json");
  const currentState: StudioStateFile = (await readJsonSafe<StudioStateFile>(
    statePath
  )) || {
    state_version: "9.0",
    slug,
    stages: {},
    gates: {},
  };

  const gateStatus =
    decision === "approved" ? "passed" : "changes_requested";
  const detailText =
    `${decision} (sha256=${board.storyboard_sha256.slice(0, 12)})` +
    (cleanNotes ? ` — ${cleanNotes.slice(0, 120)}` : "");

  currentState.state_version = "9.0";
  currentState.slug = slug;
  currentState.updated_at = nowIso;
  currentState.gates = currentState.gates || {};
  currentState.gates.storyboard_approval = {
    status: gateStatus,
    detail: detailText,
    updated_at: nowIso,
  };
  await atomicWriteJson(statePath, currentState);

  const eventRow: StudioEventRow = {
    ts: nowIso,
    stage: "gate:storyboard_approval",
    event: "gate",
    status: gateStatus,
    detail: detailText,
    artifacts: ["storyboard_approval.json"],
  };
  await appendFile(
    path.join(resolved.episodeDir, "studio_events.jsonl"),
    JSON.stringify(eventRow) + "\n",
    "utf-8"
  );

  const approval = computeLiveApprovalStatus(board, savedPayload);
  return { approval, savedPayload };
}
