#!/usr/bin/env python3
"""
Studio v9 Outlier Video Reference Analyst (`pow_studio.outlier_analyst`).

Analyzes pacing, cut rhythm, visual motion classes, hook mechanics, and loop structure of
competitor outlier YouTube Shorts (or local Proof of Wonder episodes for comparison) at $0 cost.

Strict Policy (Decision D1-A & pow-guardrails):
  - Validates 11-char YouTube IDs (`^[A-Za-z0-9_-]{11}$`), invokes `yt-dlp` via argument array (never shell).
  - Downloads a temporary `<=480p` copy into an isolated temp directory and ALWAYS deletes all
    video/audio media in `finally:` unless `--keep-media` is explicitly set for local debugging.
  - Never copies or reuses competitor footage, titles, thumbnails, or sentences.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import statistics
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .media_classifier import detect_presentation_graphic_metrics, inspect_media_authenticity

CHANNEL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTLIERS_DIR = CHANNEL_ROOT / "research" / "outliers"
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
MEDIA_EXTS = {".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".wav", ".part", ".ytdl"}

COUNTER_INTUITIVE_RE = re.compile(
    r"\b(?:actually|wrong|never|impossible|shouldn't|cannot|can't|myth|lie|opposite|secretly|instead|nobody|without)\b",
    re.I,
)
CTA_RE = re.compile(r"\b(?:subscribe|follow\s+for|comment\s+below|let\s+me\s+know\s+in\s+the\s+comments|like\s+and\s+subscribe)\b", re.I)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def validate_video_id(video_id: str) -> str:
    vid = (video_id or "").strip()
    if not VIDEO_ID_RE.match(vid):
        raise ValueError(f"Invalid YouTube video_id '{video_id}'. Must match ^[A-Za-z0-9_-]{{11}}$.")
    return vid


def is_analysis_available() -> tuple[bool, str]:
    missing: list[str] = []
    if shutil.which("yt-dlp") is None:
        try:
            import yt_dlp  # noqa: F401
        except ImportError:
            missing.append("yt-dlp")
    try:
        import scenedetect  # noqa: F401
    except ImportError:
        missing.append("scenedetect")
    try:
        import youtube_transcript_api  # noqa: F401
    except ImportError:
        missing.append("youtube-transcript-api")
    if missing:
        return False, f"Missing packages: {', '.join(missing)}"
    return True, "yt-dlp + scenedetect + youtube-transcript-api ready"


def _write_status(out_dir: Path, status: str, stage: str, detail: str = "", error: Optional[str] = None) -> None:
    payload: dict[str, Any] = {
        "status": status,
        "stage": stage,
        "detail": detail,
        "updated_at": _now_iso(),
    }
    if error:
        payload["error"] = error
    _atomic_write_json(out_dir / "status.json", payload)


def _yt_dlp_cmd_prefix() -> list[str]:
    venv_bin = CHANNEL_ROOT / ".venv" / "bin" / "yt-dlp"
    if venv_bin.exists():
        return [str(venv_bin)]
    which_bin = shutil.which("yt-dlp")
    if which_bin:
        return [which_bin]
    return [str(CHANNEL_ROOT / ".venv" / "bin" / "python"), "-m", "yt_dlp"]


def _probe_video_duration_and_dims(video_path: Path) -> tuple[float, int, int, float]:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return 0.0, 0, 0, 30.0
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or [{}]
    st = streams[0] if streams else {}
    w = int(st.get("width") or 0)
    h = int(st.get("height") or 0)
    r_fps = str(st.get("r_frame_rate") or "30/1")
    try:
        if "/" in r_fps:
            num, den = r_fps.split("/", 1)
            fps = float(num) / max(1.0, float(den))
        else:
            fps = float(r_fps)
    except Exception:
        fps = 30.0
    dur = float((data.get("format") or {}).get("duration") or 0.0)
    return dur, w, h, round(fps, 3)


def fetch_youtube_metadata(video_id: str, timeout_s: int = 45) -> dict[str, Any]:
    vid = validate_video_id(video_id)
    url = f"https://www.youtube.com/watch?v={vid}"
    cmd = [
        *_yt_dlp_cmd_prefix(),
        "--no-playlist",
        "--skip-download",
        "--dump-single-json",
        "--no-warnings",
        "--",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp metadata fetch failed for {vid}: {(proc.stderr or proc.stdout).strip()[:280]}")
    info = json.loads(proc.stdout)
    return {
        "video_id": vid,
        "title": str(info.get("title") or ""),
        "channel": str(info.get("channel") or info.get("uploader") or ""),
        "channel_id": str(info.get("channel_id") or ""),
        "uploader_id": str(info.get("uploader_id") or ""),
        "duration_s": float(info.get("duration") or 0.0),
        "view_count": int(info.get("view_count") or 0),
        "like_count": int(info.get("like_count") or 0),
        "comment_count": int(info.get("comment_count") or 0),
        "upload_date": str(info.get("upload_date") or ""),
        "tags": list(info.get("tags") or [])[:20],
        "categories": list(info.get("categories") or []),
        "webpage_url": f"https://www.youtube.com/watch?v={vid}",
    }


def download_temp_480p_video(video_id: str, tmp_dir: Path, timeout_s: int = 120) -> Path:
    vid = validate_video_id(video_id)
    url = f"https://www.youtube.com/watch?v={vid}"
    out_tmpl = str(tmp_dir / "outlier_media.%(ext)s")
    cmd = [
        *_yt_dlp_cmd_prefix(),
        "--no-playlist",
        "--no-warnings",
        "-f",
        "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/bestvideo[height<=480]+bestaudio/best[height<=480]/worst",
        "--merge-output-format",
        "mp4",
        "-o",
        out_tmpl,
        "--",
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp <=480p download failed for {vid}: {(proc.stderr or proc.stdout).strip()[:280]}")
    candidates = sorted(
        p for p in tmp_dir.iterdir() if p.is_file() and p.suffix.lower() in {".mp4", ".webm", ".mkv"}
    )
    if not candidates:
        raise RuntimeError(f"yt-dlp completed for {vid} but no video file was produced in {tmp_dir}")
    return candidates[0]


def detect_scene_cuts(video_path: Path, duration_s: float) -> tuple[list[tuple[float, float]], str]:
    """
    Detect scene intervals `[(start_s, end_s), ...]`.
    Primary: PySceneDetect `AdaptiveDetector(adaptive_threshold=2.8, min_scene_len=12, min_content_val=20.0)`.
    Fallback: FFmpeg `select='gt(scene,0.32)',showinfo`.
    """
    if duration_s <= 0.0:
        duration_s, _, _, _ = _probe_video_duration_and_dims(video_path)
    duration_s = max(0.5, float(duration_s))

    try:
        from scenedetect import AdaptiveDetector, detect

        raw_scenes = detect(
            str(video_path),
            AdaptiveDetector(adaptive_threshold=2.8, min_scene_len=12, min_content_val=20.0),
            show_progress=False,
        )
        if raw_scenes:
            intervals: list[tuple[float, float]] = []
            for st_tc, end_tc in raw_scenes:
                a = round(float(getattr(st_tc, "seconds", None) if hasattr(st_tc, "seconds") else st_tc.get_seconds()), 3)
                b = round(float(getattr(end_tc, "seconds", None) if hasattr(end_tc, "seconds") else end_tc.get_seconds()), 3)
                if b - a >= 0.18:
                    intervals.append((a, b))
            if intervals:
                intervals[0] = (0.0, intervals[0][1])
                intervals[-1] = (intervals[-1][0], round(duration_s, 3))
                return intervals, "scenedetect_adaptive"
            return [(0.0, round(duration_s, 3))], "scenedetect_single_take"
    except Exception:
        pass

    # FFmpeg scene score fallback
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(video_path),
            "-vf",
            "select='gt(scene,0.32)',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    cut_times = [0.0]
    for m in re.finditer(r"pts_time:([0-9]+(?:\.[0-9]+)?)", proc.stderr or ""):
        t = float(m.group(1))
        if t - cut_times[-1] >= 0.25 and duration_s - t >= 0.25:
            cut_times.append(round(t, 3))
    cut_times.append(round(duration_s, 3))
    return [(cut_times[i], cut_times[i + 1]) for i in range(len(cut_times) - 1)], "ffmpeg_scene_fallback"


def _expand_snippets_to_words(snippets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    words: list[dict[str, Any]] = []
    for sn in snippets:
        txt = re.sub(r"\s+", " ", str(sn.get("text") or "")).strip()
        if not txt or txt.startswith("[") and txt.endswith("]"):
            continue
        toks = txt.split()
        if not toks:
            continue
        st = float(sn.get("start") or 0.0)
        dur = max(0.12, float(sn.get("duration") or 1.0))
        step = dur / len(toks)
        for idx, tok in enumerate(toks):
            words.append(
                {
                    "word": tok,
                    "start": round(st + idx * step, 3),
                    "end": round(st + (idx + 1) * step, 3),
                }
            )
    return words


def fetch_transcript_words(
    video_id: Optional[str],
    video_path: Optional[Path],
) -> tuple[list[dict[str, Any]], str, str]:
    """
    Return `(words, full_text, source_method)` using `youtube-transcript-api` first,
    then local `faster-whisper` (`base.en` in `assets/models/`) fallback.
    """
    if video_id and VIDEO_ID_RE.match(video_id):
        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            if hasattr(YouTubeTranscriptApi, "fetch"):
                api = YouTubeTranscriptApi()
                fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
                raw_list = fetched.to_raw_data() if hasattr(fetched, "to_raw_data") else [
                    {"text": s.text, "start": s.start, "duration": s.duration} for s in fetched
                ]
            else:
                raw_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])  # type: ignore[attr-defined]
            words = _expand_snippets_to_words(raw_list)
            if words:
                full_txt = " ".join(w["word"] for w in words)
                return words, full_txt, "youtube_transcript_api"
        except Exception:
            pass

    if video_path is not None and video_path.exists():
        try:
            from faster_whisper import WhisperModel

            with tempfile.TemporaryDirectory(prefix="pow_whisper_") as wtmp:
                wav_p = Path(wtmp) / "audio16k.wav"
                proc = subprocess.run(
                    [
                        "ffmpeg",
                        "-y",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-i",
                        str(video_path),
                        "-vn",
                        "-ac",
                        "1",
                        "-ar",
                        "16000",
                        str(wav_p),
                    ],
                    capture_output=True,
                )
                if proc.returncode == 0 and wav_p.exists():
                    dl_root = CHANNEL_ROOT / "assets" / "models"
                    kw = {"download_root": str(dl_root)} if dl_root.exists() else {}
                    model = WhisperModel("base.en", device="cpu", compute_type="int8", **kw)
                    segs, _ = model.transcribe(str(wav_p), language="en", word_timestamps=True, vad_filter=True)
                    words = []
                    for seg in segs:
                        for w in (seg.words or []):
                            tok = (w.word or "").strip()
                            if tok:
                                words.append(
                                    {"word": tok, "start": round(float(w.start), 3), "end": round(float(w.end), 3)}
                                )
                    full_txt = " ".join(w["word"] for w in words)
                    return words, full_txt, "faster_whisper_base_en"
        except Exception:
            pass

    return [], "", "unavailable"


def _extract_jpeg_frame(video_path: Path, seek_s: float, dst_jpg: Path, width: int = 270, height: int = 480) -> bool:
    dst_jpg.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, float(seek_s)):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            "5",
            str(dst_jpg),
        ],
        capture_output=True,
    )
    return proc.returncode == 0 and dst_jpg.exists() and dst_jpg.stat().st_size > 200


def compute_image_dhash64(img_path: Path) -> Optional[int]:
    """Compute 64-bit horizontal gradient perceptual hash (`9x8` grayscale) for loop similarity."""
    if not img_path.exists():
        return None
    try:
        with Image.open(img_path) as im:
            gray = np.asarray(im.convert("L").resize((9, 8), Image.Resampling.BILINEAR), dtype=np.float32)
        diff = gray[:, 1:] > gray[:, :-1]
        bits = 0
        for b in diff.flatten():
            bits = (bits << 1) | int(bool(b))
        return bits
    except Exception:
        return None


def _detect_frame0_text_overlay(frame0_jpg: Path) -> bool:
    """Heuristic check for burned-in Hook title / caption text in Frame 0."""
    if not frame0_jpg.exists():
        return False
    try:
        with Image.open(frame0_jpg) as im:
            rgb = im.convert("RGB")
            _, grid_score, is_slide = detect_presentation_graphic_metrics(rgb)
            if is_slide:
                return True
            gray = np.asarray(rgb.convert("L"), dtype=np.float32)
        h, w = gray.shape
        band = gray[int(0.08 * h) : int(0.88 * h), int(0.08 * w) : int(0.92 * w)]
        gx = np.abs(np.diff(band, axis=1))
        gy = np.abs(np.diff(band, axis=0))
        sharp_text_strokes = float(np.mean(gx > 42.0) + np.mean(gy > 42.0))
        return bool(sharp_text_strokes >= 0.085 and grid_score >= 2.1)
    except Exception:
        return False


def classify_opening_hook(words: list[dict[str, Any]], title: str = "") -> str:
    opening_words = [w["word"] for w in words if float(w["start"]) <= 4.0]
    sample = (" ".join(opening_words) if opening_words else title).strip()
    if not sample:
        return "visual_only"
    first_tok = re.sub(r"^[^A-Za-z0-9]+", "", sample.split()[0]).lower()
    if "?" in sample or first_tok in {"why", "how", "what", "where", "who", "when", "can", "could", "would", "did", "is", "are"}:
        return "question"
    if re.search(r"\b(?:\d+|million|billion|trillion|thousand|percent|miles|kilometers|degrees|octaves|seconds|years)\b", sample, re.I):
        return "numeric_shock"
    if COUNTER_INTUITIVE_RE.search(sample):
        return "counter_intuitive_claim"
    return "direct_statement"


def detect_cta_position(words: list[dict[str, Any]]) -> Optional[float]:
    if not words:
        return None
    for i in range(len(words)):
        window = re.sub(r"^[^A-Za-z0-9]+", "", " ".join(w["word"] for w in words[i : i + 5]))
        if CTA_RE.match(window):
            return round(float(words[i]["start"]), 2)
    return None


def _compute_phase_metrics(
    scenes: list[dict[str, Any]],
    words: list[dict[str, Any]],
    total_duration_s: float,
) -> list[dict[str, Any]]:
    phase_defs = [
        ("0_3s", "Hook (0–3s)", 0.0, min(3.0, total_duration_s)),
        ("3_15s", "Setup (3–15s)", 3.0, min(15.0, total_duration_s)),
        ("15_35s", "Escalation (15–35s)", 15.0, min(35.0, total_duration_s)),
        ("35s_end", "Payoff (35s–End)", 35.0, total_duration_s),
    ]
    rows: list[dict[str, Any]] = []
    for pid, label, p_start, p_end in phase_defs:
        span = round(max(0.0, p_end - p_start), 3)
        if span <= 0.05:
            rows.append(
                {
                    "phase_id": pid,
                    "label": label,
                    "start_s": round(p_start, 2),
                    "end_s": round(p_end, 2),
                    "span_s": 0.0,
                    "cut_count": 0,
                    "cuts_per_10s": 0.0,
                    "median_shot_duration_s": 0.0,
                    "word_count": 0,
                    "words_per_second": 0.0,
                    "moving_footage_pct": 0.0,
                    "text_heavy_pct": 0.0,
                }
            )
            continue

        # Cuts occurring inside (p_start, p_end] (excluding t=0 video start)
        cuts_in_phase = sum(1 for sc in scenes if sc["start_s"] > 0.05 and p_start <= sc["start_s"] < p_end)
        overlapping = []
        moving_dur = 0.0
        text_dur = 0.0
        for sc in scenes:
            ov = max(0.0, min(p_end, sc["end_s"]) - max(p_start, sc["start_s"]))
            if ov > 0.02:
                overlapping.append(float(sc["duration_s"]))
                if sc.get("is_real_moving"):
                    moving_dur += ov
                if sc.get("is_text_heavy_graphic"):
                    text_dur += ov

        phase_words = [
            w for w in words if p_start <= 0.5 * (float(w["start"]) + float(w["end"])) < p_end
        ]
        rows.append(
            {
                "phase_id": pid,
                "label": label,
                "start_s": round(p_start, 2),
                "end_s": round(p_end, 2),
                "span_s": span,
                "cut_count": cuts_in_phase,
                "cuts_per_10s": round(10.0 * cuts_in_phase / span, 2),
                "median_shot_duration_s": round(float(statistics.median(overlapping)), 2) if overlapping else round(span, 2),
                "word_count": len(phase_words),
                "words_per_second": round(len(phase_words) / span, 2),
                "moving_footage_pct": round(100.0 * moving_dur / span, 1),
                "text_heavy_pct": round(100.0 * text_dur / span, 1),
            }
        )
    return rows


def _render_outlier_contact_sheet(scenes: list[dict[str, Any]], out_dir: Path, title: str) -> Optional[str]:
    valid_cards = [sc for sc in scenes if sc.get("mid_keyframe") and (out_dir / sc["mid_keyframe"]).exists()][:16]
    if not valid_cards:
        return None
    cols = min(4, len(valid_cards))
    rows_n = int(math.ceil(len(valid_cards) / float(cols)))
    cell_w, cell_h = 240, 426
    pad = 16
    hdr_h = 64
    canvas_w = cols * (cell_w + pad) + pad
    canvas_h = hdr_h + rows_n * (cell_h + 44 + pad) + pad

    sheet = Image.new("RGB", (canvas_w, canvas_h), (14, 18, 26))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    draw.text((pad, 20), f"OUTLIER ANATOMY CONTACT SHEET — {title[:80]}", fill=(245, 247, 250), font=font)

    cls_colors = {
        "REAL_VIDEO_ACTION": (16, 185, 129),
        "REAL_VIDEO_ESTABLISHING": (20, 184, 166),
        "REAL_TIME_LAPSE": (56, 189, 248),
        "ANIMATED_STILL": (245, 158, 11),
        "STILL_PHOTO": (59, 130, 246),
        "INFOGRAPHIC": (168, 85, 247),
    }

    for idx, sc in enumerate(valid_cards):
        r = idx // cols
        c = idx % cols
        x = pad + c * (cell_w + pad)
        y = hdr_h + r * (cell_h + 44 + pad)
        with Image.open(out_dir / sc["mid_keyframe"]) as im:
            thumb = im.convert("RGB").resize((cell_w, cell_h), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y))
        col = cls_colors.get(sc["motion_class"], (120, 130, 145))
        draw.rectangle((x, y, x + cell_w, y + 5), fill=col)
        draw.text(
            (x + 4, y + cell_h + 6),
            f"#{sc['index']} {sc['start_s']:.1f}-{sc['end_s']:.1f}s ({sc['duration_s']:.1f}s)",
            fill=(235, 240, 245),
            font=font,
        )
        draw.text((x + 4, y + cell_h + 22), f"{sc['motion_class'][:24]}", fill=col, font=font)

    dst = out_dir / "contact_sheet.jpg"
    sheet.save(dst, format="JPEG", quality=85)
    return "contact_sheet.jpg"


def _build_initial_agent_annotations(
    meta: dict[str, Any],
    phases: list[dict[str, Any]],
    hook_info: dict[str, Any],
    visual_mix: dict[str, Any],
) -> dict[str, Any]:
    hook_p = phases[0] if phases else {}
    what_works: list[str] = []
    if hook_info.get("first_word_time_s") is not None and float(hook_info["first_word_time_s"]) <= 0.45:
        what_works.append(
            f"Zero-hesitation cold open: first spoken word lands at {hook_info['first_word_time_s']:.2f}s ({hook_info['opening_hook_type']})."
        )
    if int(hook_p.get("cut_count") or 0) >= 1:
        what_works.append(
            f"Fast visual reset inside 0–3s ({hook_p.get('cut_count')} cut(s), median shot {hook_p.get('median_shot_duration_s')}s)."
        )
    if float(visual_mix.get("real_moving_pct") or 0.0) >= 60.0:
        what_works.append(
            f"High kinetic density ({visual_mix['real_moving_pct']}% moving video vs {visual_mix['static_or_animated_still_pct']}% still)."
        )
    if not what_works:
        what_works.append(
            f"Sustained verbal density ({hook_p.get('words_per_second', 0.0)} words/s in Hook) driving curiosity."
        )

    return {
        "hook_5_aspects": {
            "subject": meta.get("title") or "Primary phenomenon in frame 0",
            "subject_motion": "Active visual change in opening shot" if (hook_p.get("moving_footage_pct") or 0) >= 50 else "Controlled framing / pan",
            "scene_and_overlays": "Burned-in text present on Frame 0" if hook_info.get("frame0_has_text_overlay") else "Clean visual cold open (caption-driven)",
            "spatial_framing": "9:16 vertical mobile-first framing",
            "camera": "Fast cut pacing" if (hook_p.get("cut_count") or 0) >= 2 else "Held opening shot before setup cut",
        },
        "what_works": what_works[:3],
        "differentiation_seeds": [
            "Replace any synthetic/CGI or stock filler with verified NASA/NOAA/Wikimedia expedition footage + .provenance.json.",
            "Add one parameterized ManimCE alpha mechanism overlay (<=35% area) anchored to the exact physical measurement.",
        ],
        "anti_copy_guardrail": "Structure/rhythm reference only — never reuse competitor sentences, titles, thumbnails, or footage.",
    }


def _write_brief_markdown(path: Path, brief: dict[str, Any]) -> None:
    meta = brief["metadata"]
    hk = brief["hook_and_loop"]
    vm = brief["visual_mix"]
    lines = [
        f"# Outlier Anatomy Brief — {meta.get('title') or brief['target_id']}",
        "",
        f"- **Target ID:** `{brief['target_id']}` (`mode={brief['mode']}`)",
        f"- **Channel:** {meta.get('channel') or 'Local Episode'} | **Duration:** `{brief['duration_s']:.2f}s` | **Total Scenes:** `{brief['scene_count']}` (`{brief['cut_count']}` cuts)",
        f"- **Scene Detector:** `{brief['scene_detector']}` | **Transcript Source:** `{brief['transcript_source']}`",
        f"- **Media Auto-Deleted:** `{brief['media_deleted']}`",
        "",
        "## 1. Hook & Loop Mechanics",
        f"- **Opening Hook Type:** `{hk['opening_hook_type']}`",
        f"- **First Word Time:** `{hk['first_word_time_s']}s`",
        f"- **Frame-0 Burned Text/Graphic:** `{hk['frame0_has_text_overlay']}`",
        f"- **CTA Position:** `{hk['cta_position_s']}`",
        f"- **First-vs-Last Frame Loop Similarity:** `{hk['loop_similarity_score']}` (dHash distance `{hk['first_last_dhash_distance']}` / 64)",
        "",
        "## 2. Visual Motion Mix",
        f"- **Genuine Moving Video:** `{vm['real_moving_pct']}%`",
        f"- **Animated Still / Static Photo:** `{vm['static_or_animated_still_pct']}%`",
        f"- **Graphic / Text-Heavy Slide:** `{vm['graphic_or_slide_pct']}%`",
        "",
        "## 3. Phase Pacing Table",
        "| Phase | Span (s) | Cuts | Cuts/10s | Median Shot (s) | Words/s | Moving % |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for p in brief["phases"]:
        lines.append(
            f"| {p['label']} | {p['span_s']:.1f} | {p['cut_count']} | {p['cuts_per_10s']:.2f} | "
            f"{p['median_shot_duration_s']:.2f} | {p['words_per_second']:.2f} | {p['moving_footage_pct']:.1f}% |"
        )
    lines.extend(["", "## 4. Structural Takeaways & Differentiation Seeds"])
    for item in brief["agent_annotations"].get("what_works", []):
        lines.append(f"- **What works:** {item}")
    for seed in brief["agent_annotations"].get("differentiation_seeds", []):
        lines.append(f"- **PoW Differentiation Seed:** {seed}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def analyze_outlier_video(
    video_id: Optional[str] = None,
    local_video_path: Optional[Path] = None,
    mode: Literal["download", "transcript_only"] = "download",
    keep_media: bool = False,
    out_root: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Run full Outlier Video Reference Analysis on either a YouTube `video_id` or a `local_video_path`.
    Guarantees deletion of temporary downloaded media in `finally:` when `keep_media=False`.
    """
    if not video_id and not local_video_path:
        raise ValueError("Provide either `video_id` or `local_video_path`.")

    root_dir = Path(out_root) if out_root else DEFAULT_OUTLIERS_DIR
    if local_video_path is not None:
        src_local = Path(local_video_path).resolve()
        if not src_local.is_file():
            raise FileNotFoundError(f"Local video not found: {src_local}")
        target_id = f"local_{re.sub(r'[^a-zA-Z0-9_-]+', '_', src_local.stem)[:48]}"
    else:
        target_id = validate_video_id(str(video_id))
        src_local = None

    out_dir = root_dir / target_id
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_status(out_dir, "running", "init", detail=f"Starting analysis ({mode})")

    tmp_dir_path = Path(tempfile.mkdtemp(prefix=f"pow_outlier_{target_id}_"))
    media_deleted = True

    try:
        if src_local is not None:
            dur_probe, w, h, fps = _probe_video_duration_and_dims(src_local)
            meta = {
                "video_id": target_id,
                "title": src_local.stem,
                "channel": "Proof of Wonder (Local)",
                "channel_id": "local",
                "uploader_id": "@proofofwonderscience",
                "duration_s": dur_probe,
                "view_count": 0,
                "like_count": 0,
                "comment_count": 0,
                "upload_date": "",
                "tags": [],
                "categories": ["Science & Technology"],
                "webpage_url": "",
            }
            working_video: Optional[Path] = src_local
        else:
            _write_status(out_dir, "running", "metadata", detail="Fetching YouTube metadata via yt-dlp")
            meta = fetch_youtube_metadata(target_id)
            if mode == "download":
                _write_status(out_dir, "running", "download_480p", detail="Downloading temporary <=480p video")
                working_video = download_temp_480p_video(target_id, tmp_dir_path)
                if keep_media:
                    kept_dst = out_dir / "_debug_media_480p.mp4"
                    shutil.copy2(working_video, kept_dst)
                    media_deleted = False
            else:
                working_video = None

        _write_status(out_dir, "running", "transcript", detail="Extracting word-timed transcript")
        words, full_transcript, transcript_src = fetch_transcript_words(
            video_id=target_id if src_local is None else None,
            video_path=working_video,
        )

        scenes: list[dict[str, Any]] = []
        scene_detector = "transcript_only"
        width, height, fps = 0, 0, 30.0
        duration_s = float(meta.get("duration_s") or (words[-1]["end"] if words else 30.0))

        if working_video is not None and working_video.exists():
            dur_v, width, height, fps = _probe_video_duration_and_dims(working_video)
            if dur_v > 0:
                duration_s = dur_v
            _write_status(out_dir, "running", "scene_cuts", detail="Detecting scene cuts & auditing motion classes")
            intervals, scene_detector = detect_scene_cuts(working_video, duration_s)

            kf_dir = out_dir / "keyframes"
            kf_dir.mkdir(parents=True, exist_ok=True)

            for idx, (st_s, en_s) in enumerate(intervals):
                sc_dur = round(max(0.1, en_s - st_s), 3)
                sid = f"S{idx + 1:02d}"
                start_rel = f"keyframes/{sid}_start.jpg"
                mid_rel = f"keyframes/{sid}_mid.jpg"
                ok_start = _extract_jpeg_frame(working_video, st_s + min(0.08, 0.25 * sc_dur), out_dir / start_rel)
                ok_mid = _extract_jpeg_frame(working_video, st_s + 0.5 * sc_dur, out_dir / mid_rel)

                auth = inspect_media_authenticity(
                    working_video,
                    start_s=st_s,
                    duration_s=min(3.2, sc_dur),
                    sample_fps=6.0,
                )
                is_slide = bool(auth.is_dense_presentation_graphic)
                if not is_slide and ok_mid:
                    with Image.open(out_dir / mid_rel) as mid_im:
                        _, _, is_slide = detect_presentation_graphic_metrics(mid_im.convert("RGB"))

                m_cls = auth.inferred_media_class if auth.valid else "REAL_VIDEO_ESTABLISHING"
                if is_slide:
                    m_cls = "INFOGRAPHIC"

                sc_words = [
                    w["word"]
                    for w in words
                    if st_s - 0.04 <= 0.5 * (float(w["start"]) + float(w["end"])) < en_s
                ]
                scenes.append(
                    {
                        "index": idx + 1,
                        "sid": sid,
                        "start_s": round(st_s, 3),
                        "end_s": round(en_s, 3),
                        "duration_s": sc_dur,
                        "motion_class": m_cls,
                        "is_real_moving": bool(auth.is_real_moving_footage and not is_slide),
                        "is_baked_animated_still": bool(auth.is_baked_animated_still),
                        "is_text_heavy_graphic": is_slide,
                        "spoken_text": " ".join(sc_words),
                        "start_keyframe": start_rel if ok_start else None,
                        "mid_keyframe": mid_rel if ok_mid else None,
                    }
                )

            # Frame 0 & Last frame for loop similarity + Frame 0 text check
            f0_jpg = out_dir / "keyframes" / "_frame_first.jpg"
            fl_jpg = out_dir / "keyframes" / "_frame_last.jpg"
            _extract_jpeg_frame(working_video, 0.06, f0_jpg)
            _extract_jpeg_frame(working_video, max(0.06, duration_s - 0.15), fl_jpg)
            h_first = compute_image_dhash64(f0_jpg)
            h_last = compute_image_dhash64(fl_jpg)
            if h_first is not None and h_last is not None:
                dhash_dist = int((h_first ^ h_last).bit_count())
                loop_sim = round(1.0 - (dhash_dist / 64.0), 3)
            else:
                dhash_dist = None
                loop_sim = None
            frame0_has_text = _detect_frame0_text_overlay(f0_jpg)
        else:
            dhash_dist = None
            loop_sim = None
            frame0_has_text = None

        phases = _compute_phase_metrics(scenes, words, duration_s)
        total_dur_safe = max(0.5, duration_s)
        moving_s = sum(sc["duration_s"] for sc in scenes if sc["is_real_moving"])
        graphic_s = sum(sc["duration_s"] for sc in scenes if sc["is_text_heavy_graphic"])
        still_s = max(0.0, sum(sc["duration_s"] for sc in scenes) - moving_s - graphic_s)

        visual_mix = {
            "real_moving_pct": round(100.0 * moving_s / total_dur_safe, 1) if scenes else None,
            "static_or_animated_still_pct": round(100.0 * still_s / total_dur_safe, 1) if scenes else None,
            "graphic_or_slide_pct": round(100.0 * graphic_s / total_dur_safe, 1) if scenes else None,
        }

        hook_and_loop = {
            "opening_hook_type": classify_opening_hook(words, title=str(meta.get("title") or "")),
            "first_word_time_s": round(float(words[0]["start"]), 3) if words else None,
            "frame0_has_text_overlay": frame0_has_text,
            "cta_position_s": detect_cta_position(words),
            "first_last_dhash_distance": dhash_dist,
            "loop_similarity_score": loop_sim,
        }

        contact_rel = _render_outlier_contact_sheet(scenes, out_dir, str(meta.get("title") or target_id)) if scenes else None

        # Merge channel comparison right away if outlier_patterns or unified_av_timeline exists
        our_bench = compute_our_channel_pacing_medians()

        shot_durs = [sc["duration_s"] for sc in scenes]
        brief: dict[str, Any] = {
            "brief_version": "9.0",
            "analyzed_at": _now_iso(),
            "target_id": target_id,
            "mode": "local" if src_local is not None else mode,
            "media_deleted": media_deleted,
            "duration_s": round(duration_s, 3),
            "width": width,
            "height": height,
            "fps": fps,
            "scene_detector": scene_detector,
            "transcript_source": transcript_src,
            "scene_count": len(scenes),
            "cut_count": max(0, len(scenes) - 1),
            "cuts_per_10s_overall": round(10.0 * max(0, len(scenes) - 1) / total_dur_safe, 2) if scenes else None,
            "median_shot_duration_s": round(float(statistics.median(shot_durs)), 2) if shot_durs else None,
            "word_count": len(words),
            "words_per_second_overall": round(len(words) / total_dur_safe, 2),
            "metadata": meta,
            "hook_and_loop": hook_and_loop,
            "visual_mix": visual_mix,
            "phases": phases,
            "scenes": scenes,
            "contact_sheet": contact_rel,
            "transcript_preview": full_transcript[:900],
            "our_channel_baseline": our_bench,
            "agent_annotations": _build_initial_agent_annotations(meta, phases, hook_and_loop, visual_mix),
        }

        _atomic_write_json(out_dir / "outlier_anatomy_brief.json", brief)
        _write_brief_markdown(out_dir / "outlier_anatomy_brief.md", brief)
        _write_status(out_dir, "completed", "done", detail=f"Analyzed {len(scenes)} scenes ({duration_s:.1f}s)")
        return brief

    except Exception as exc:
        _write_status(out_dir, "failed", "error", error=str(exc)[:400])
        raise
    finally:
        # Strict D1-A Enforcement: delete all temporary downloaded video/audio files immediately
        if tmp_dir_path.exists():
            shutil.rmtree(tmp_dir_path, ignore_errors=True)
        if not keep_media and out_dir.exists():
            for leftover in out_dir.rglob("*"):
                if leftover.is_file() and leftover.suffix.lower() in MEDIA_EXTS:
                    try:
                        leftover.unlink()
                    except OSError:
                        pass


def compute_our_channel_pacing_medians() -> dict[str, Any]:
    """Compute Proof of Wonder pacing medians from `output/*/*/unified_av_timeline.json`."""
    output_root = CHANNEL_ROOT / "output"
    timelines = sorted(output_root.glob("*/*/unified_av_timeline.json"))
    ep_rows: list[dict[str, Any]] = []
    for tl_p in timelines:
        if "regression-" in str(tl_p):
            continue
        try:
            tl = json.loads(tl_p.read_text(encoding="utf-8"))
        except Exception:
            continue
        dur = float(tl.get("total_duration_s") or 0.0)
        sc_list = tl.get("scenes") or []
        if dur < 20.0 or not sc_list:
            continue
        durs = [float(s.get("duration_s") or 0.0) for s in sc_list if float(s.get("duration_s") or 0.0) > 0]
        hook_cuts = sum(1 for s in sc_list if 0.05 < float(s.get("start_s") or 0.0) < 3.0)
        ep_rows.append(
            {
                "slug": tl.get("slug") or tl_p.parent.name,
                "duration_s": dur,
                "cut_count": max(0, len(sc_list) - 1),
                "cuts_per_10s": round(10.0 * max(0, len(sc_list) - 1) / dur, 2),
                "hook_0_3s_cuts": hook_cuts,
                "median_shot_duration_s": round(float(statistics.median(durs)), 2) if durs else 0.0,
            }
        )

    if not ep_rows:
        return {"episodes_count": 0}

    return {
        "episodes_count": len(ep_rows),
        "median_duration_s": round(float(statistics.median(r["duration_s"] for r in ep_rows)), 2),
        "median_cuts_per_10s": round(float(statistics.median(r["cuts_per_10s"] for r in ep_rows)), 2),
        "median_hook_0_3s_cuts": round(float(statistics.median(r["hook_0_3s_cuts"] for r in ep_rows)), 2),
        "median_shot_duration_s": round(float(statistics.median(r["median_shot_duration_s"] for r in ep_rows)), 2),
        "episodes": ep_rows,
    }


def aggregate_outlier_patterns(out_root: Optional[Path] = None) -> dict[str, Any]:
    """
    Aggregate all analyzed competitor outlier briefs in `research/outliers/` and compare against
    Proof of Wonder's own `unified_av_timeline.json` episodes → `outlier_patterns.{json,md}`.
    """
    root_dir = Path(out_root) if out_root else DEFAULT_OUTLIERS_DIR
    root_dir.mkdir(parents=True, exist_ok=True)

    competitor_briefs: list[dict[str, Any]] = []
    for p in sorted(root_dir.glob("*/outlier_anatomy_brief.json")):
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(b.get("target_id", "")).startswith("local_"):
            continue
        competitor_briefs.append(b)

    our = compute_our_channel_pacing_medians()

    def _med(vals: list[float]) -> Optional[float]:
        clean = [float(x) for x in vals if x is not None]
        return round(float(statistics.median(clean)), 2) if clean else None

    comp_cuts_10s = _med([b["cuts_per_10s_overall"] for b in competitor_briefs if b.get("cuts_per_10s_overall") is not None])
    comp_shot_dur = _med([b["median_shot_duration_s"] for b in competitor_briefs if b.get("median_shot_duration_s") is not None])
    comp_wps = _med([b["words_per_second_overall"] for b in competitor_briefs if b.get("words_per_second_overall") is not None])
    comp_first_word = _med(
        [b["hook_and_loop"]["first_word_time_s"] for b in competitor_briefs if (b.get("hook_and_loop") or {}).get("first_word_time_s") is not None]
    )
    comp_loop_sim = _med(
        [b["hook_and_loop"]["loop_similarity_score"] for b in competitor_briefs if (b.get("hook_and_loop") or {}).get("loop_similarity_score") is not None]
    )
    comp_hook_cuts = _med(
        [b["phases"][0]["cut_count"] for b in competitor_briefs if b.get("phases") and b.get("scene_count", 0) > 0]
    )
    comp_moving_pct = _med(
        [b["visual_mix"]["real_moving_pct"] for b in competitor_briefs if (b.get("visual_mix") or {}).get("real_moving_pct") is not None]
    )

    hook_type_counts: dict[str, int] = {}
    channels_seen: set[str] = set()
    for b in competitor_briefs:
        ht = (b.get("hook_and_loop") or {}).get("opening_hook_type") or "unknown"
        hook_type_counts[ht] = hook_type_counts.get(ht, 0) + 1
        ch = (b.get("metadata") or {}).get("channel") or ""
        if ch:
            channels_seen.add(ch)

    pacing_gap_notes: list[str] = []
    if comp_hook_cuts is not None and our.get("median_hook_0_3s_cuts") is not None:
        pacing_gap_notes.append(
            f"Hook (0–3s) cuts median: Competitor Outliers = {comp_hook_cuts} cuts/3s vs Proof of Wonder = {our['median_hook_0_3s_cuts']} cuts/3s."
        )
    if comp_shot_dur is not None and our.get("median_shot_duration_s") is not None:
        pacing_gap_notes.append(
            f"Median shot length: Competitor Outliers = {comp_shot_dur}s vs Proof of Wonder = {our['median_shot_duration_s']}s."
        )
    if comp_cuts_10s is not None and our.get("median_cuts_per_10s") is not None:
        pacing_gap_notes.append(
            f"Overall cut velocity: Competitor Outliers = {comp_cuts_10s} cuts/10s vs Proof of Wonder = {our['median_cuts_per_10s']} cuts/10s."
        )

    summary = {
        "generated_at": _now_iso(),
        "competitor_outliers_count": len(competitor_briefs),
        "competitor_channels_count": len(channels_seen),
        "competitor_channels": sorted(channels_seen),
        "competitor_medians": {
            "cuts_per_10s": comp_cuts_10s,
            "hook_0_3s_cuts": comp_hook_cuts,
            "median_shot_duration_s": comp_shot_dur,
            "words_per_second": comp_wps,
            "first_word_time_s": comp_first_word,
            "real_moving_footage_pct": comp_moving_pct,
            "loop_similarity_score": comp_loop_sim,
        },
        "hook_type_distribution": hook_type_counts,
        "our_channel_medians": our,
        "pacing_gap_report": pacing_gap_notes,
        "outliers": [
            {
                "video_id": b["target_id"],
                "title": (b.get("metadata") or {}).get("title", ""),
                "channel": (b.get("metadata") or {}).get("channel", ""),
                "duration_s": b.get("duration_s"),
                "cut_count": b.get("cut_count"),
                "cuts_per_10s": b.get("cuts_per_10s_overall"),
                "median_shot_duration_s": b.get("median_shot_duration_s"),
                "words_per_second": b.get("words_per_second_overall"),
                "hook_type": (b.get("hook_and_loop") or {}).get("opening_hook_type"),
                "real_moving_pct": (b.get("visual_mix") or {}).get("real_moving_pct"),
            }
            for b in competitor_briefs
        ],
    }

    _atomic_write_json(root_dir / "outlier_patterns.json", summary)
    md_lines = [
        "# Studio v9 Outlier Pacing & Hook Patterns Report",
        "",
        f"- **Analyzed Competitor Outliers:** `{len(competitor_briefs)}` across `{len(channels_seen)}` channels ({', '.join(sorted(channels_seen))})",
        f"- **Proof of Wonder Baseline Episodes:** `{our.get('episodes_count', 0)}`",
        "",
        "## Pacing Gap Summary (Competitors vs Proof of Wonder)",
    ]
    for note in pacing_gap_notes:
        md_lines.append(f"- {note}")
    md_lines.extend(
        [
            "",
            "## Analyzed Outliers",
            "| Video ID | Channel | Duration (s) | Cuts | Cuts/10s | Median Shot (s) | Words/s | Moving % | Hook Type |",
            "|---|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary["outliers"]:
        md_lines.append(
            f"| `{row['video_id']}` | {row['channel']} | {row['duration_s']} | {row['cut_count']} | "
            f"{row['cuts_per_10s']} | {row['median_shot_duration_s']} | {row['words_per_second']} | "
            f"{row['real_moving_pct']}% | `{row['hook_type']}` |"
        )
    (root_dir / "outlier_patterns.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return summary
