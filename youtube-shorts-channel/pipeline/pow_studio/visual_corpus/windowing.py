#!/usr/bin/env python3
"""
Scene-cut-aware clip windowing and frame sampling (`pow_studio.visual_corpus.windowing`).

Unlike whole-clip video indexers, Proof of Wonder clips frequently contain internal archival jump
cuts, mission slates, or multi-angle reels. We split each video at internal scene transitions
(`ffmpeg select='gt(scene,0.35)'`), drop sub-`1.5s` cut slivers so windows never straddle hard cuts,
subdivide segments longer than `8.0s` into uniform `<= 6.0s` windows, and sample `20% / 50% / 80%`
frames per window.
"""

from __future__ import annotations

import io
import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PIL import Image

from ..footage_sources.download import ffprobe_media
from ..media_classifier import STILL_EXTENSIONS, VIDEO_EXTENSIONS

_PTS_TIME_RE = re.compile(r"pts_time:([0-9]+(?:\.[0-9]+)?)")


@dataclass(frozen=True)
class MediaWindow:
    start_s: float
    end_s: float
    is_still: bool

    @property
    def duration_s(self) -> float:
        return round(max(0.0, self.end_s - self.start_s), 3)

    def sample_timestamps(self) -> tuple[float, ...]:
        if self.is_still or self.end_s <= self.start_s + 0.05:
            return (round(self.start_s, 3),)
        span = self.end_s - self.start_s
        return tuple(round(self.start_s + frac * span, 3) for frac in (0.20, 0.50, 0.80))


def detect_internal_scene_cuts(
    video_path: Path,
    duration_s: float,
    scene_threshold: float = 0.35,
    max_scan_duration_s: float = 240.0,
    min_cut_spacing_s: float = 0.8,
) -> list[float]:
    """Detect internal hard cuts in `video_path` using FFmpeg's `scene` filter."""
    if duration_s <= 1.8 or not video_path.exists():
        return []
    scan_dur = min(float(duration_s), float(max_scan_duration_s))
    vf = f"fps=8,scale=160:-2,select='gt(scene,{scene_threshold:.2f})',showinfo"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-t",
            f"{scan_dur:.2f}",
            "-i",
            str(video_path),
            "-vf",
            vf,
            "-an",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    text = (proc.stderr or "") + "\n" + (proc.stdout or "")
    raw_cuts: list[float] = []
    for m in _PTS_TIME_RE.finditer(text):
        t = float(m.group(1))
        if 0.45 <= t <= duration_s - 0.45:
            raw_cuts.append(round(t, 3))

    deduped: list[float] = []
    for t in sorted(raw_cuts):
        if not deduped or (t - deduped[-1]) >= min_cut_spacing_s:
            deduped.append(t)
    return deduped


def split_duration_into_windows(
    duration_s: float,
    cut_times: list[float],
    max_window_s: float = 8.0,
    target_chunk_s: float = 6.0,
    min_window_s: float = 1.5,
    max_windows_per_file: int = 40,
) -> list[MediaWindow]:
    """
    Partition `[0, duration_s]` along `cut_times` without crossing cuts:
      - Drop cut slivers `< min_window_s` (unless the entire clip has no segment `>= min_window_s`).
      - Subdivide segments `> max_window_s` into uniform sub-windows `<= target_chunk_s` (`>= min_window_s`).
    """
    dur = round(max(0.0, float(duration_s)), 3)
    if dur <= 0.05:
        return []
    if dur < min_window_s:
        return [MediaWindow(start_s=0.0, end_s=dur, is_still=False)]

    valid_cuts = sorted(t for t in cut_times if 0.05 < t < dur - 0.05)
    boundaries = [0.0, *valid_cuts, dur]
    raw_segments = [
        (round(boundaries[i], 3), round(boundaries[i + 1], 3))
        for i in range(len(boundaries) - 1)
        if (boundaries[i + 1] - boundaries[i]) > 0.05
    ]

    kept_segments = [(a, b) for (a, b) in raw_segments if (b - a) >= min_window_s]
    if not kept_segments and raw_segments:
        longest = max(raw_segments, key=lambda ab: ab[1] - ab[0])
        kept_segments = [longest]

    windows: list[MediaWindow] = []
    for a, b in kept_segments:
        seg_len = b - a
        if seg_len <= max_window_s:
            windows.append(MediaWindow(start_s=round(a, 2), end_s=round(b, 2), is_still=False))
        else:
            n_chunks = max(1, int(math.ceil(seg_len / float(target_chunk_s))))
            step = seg_len / float(n_chunks)
            for idx in range(n_chunks):
                ws = round(a + idx * step, 2)
                we = round(b if idx == n_chunks - 1 else (a + (idx + 1) * step), 2)
                if we - ws >= min(min_window_s, seg_len):
                    windows.append(MediaWindow(start_s=ws, end_s=we, is_still=False))
                if len(windows) >= max_windows_per_file:
                    return windows
        if len(windows) >= max_windows_per_file:
            return windows
    return windows


def build_media_windows(
    media_path: Path,
    probe: Optional[dict] = None,
    scene_threshold: float = 0.35,
    max_window_s: float = 8.0,
    target_chunk_s: float = 6.0,
    min_window_s: float = 1.5,
    max_video_duration_s: float = 240.0,
    max_windows_per_file: int = 40,
) -> tuple[list[MediaWindow], dict]:
    """Build scene-aware windows for a still image or video file and return `(windows, probe_info)`."""
    ext = media_path.suffix.lower()
    if ext in STILL_EXTENSIONS:
        try:
            with Image.open(media_path) as im:
                w, h = im.size
        except Exception:
            return [], {}
        info = {"width": int(w), "height": int(h), "duration_s": 0.0, "video_codec": "still"}
        return [MediaWindow(start_s=0.0, end_s=0.0, is_still=True)], info

    if ext not in VIDEO_EXTENSIONS:
        return [], {}

    p = dict(probe) if probe else ffprobe_media(media_path)
    dur = float(p.get("duration_s") or 0.0)
    if dur <= 0.05 or int(p.get("width") or 0) <= 0:
        return [], p

    capped_dur = min(dur, float(max_video_duration_s))
    cuts = detect_internal_scene_cuts(
        media_path,
        duration_s=capped_dur,
        scene_threshold=scene_threshold,
        max_scan_duration_s=max_video_duration_s,
    )
    p["internal_scene_cuts_s"] = cuts
    wins = split_duration_into_windows(
        duration_s=capped_dur,
        cut_times=cuts,
        max_window_s=max_window_s,
        target_chunk_s=target_chunk_s,
        min_window_s=min_window_s,
        max_windows_per_file=max_windows_per_file,
    )
    return wins, p


def decode_video_frame(video_path: Path, timestamp_s: float, max_width: int = 384) -> Optional[Image.Image]:
    """Fast keyframe-assisted single-frame decode at `timestamp_s` scaled to `max_width`."""
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, float(timestamp_s)):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            f"scale='min({int(max_width)},iw)':-2",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return Image.open(io.BytesIO(proc.stdout)).convert("RGB")
    except Exception:
        return None


def sample_window_frames(media_path: Path, window: MediaWindow, max_width: int = 384) -> list[Image.Image]:
    """Return `[frame]` for stills or `[20%, 50%, 80%]` RGB frames for video windows."""
    if window.is_still:
        try:
            with Image.open(media_path) as raw:
                im = raw.convert("RGB")
                if im.width > max_width:
                    new_h = max(2, int(round(im.height * (max_width / float(im.width)))))
                    im = im.resize((max_width, new_h), Image.Resampling.BILINEAR)
                return [im]
        except Exception:
            return []

    frames: list[Image.Image] = []
    for ts in window.sample_timestamps():
        fr = decode_video_frame(media_path, ts, max_width=max_width)
        if fr is not None:
            frames.append(fr)
    if not frames:
        fallback = decode_video_frame(media_path, window.start_s, max_width=max_width)
        if fallback is not None:
            frames.append(fallback)
    return frames
