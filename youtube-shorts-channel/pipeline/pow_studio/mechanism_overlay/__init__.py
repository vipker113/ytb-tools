#!/usr/bin/env python3
"""
Studio v9 Alpha Mechanism Overlays (`pow_studio.mechanism_overlay`).

Renders parameterized, transparent (`1080x1920 @ 30fps` RGBA) scientific mechanism graphics
with ManimCE (no LaTeX required — bundled Pango fonts + Unicode) and composites them above
authentic camera footage and below subtitles at the final mux stage without invalidating
per-shot caches.
"""

from __future__ import annotations

from .anchoring import ResolvedOverlayTiming, resolve_overlay_timings
from .qa import analyze_overlay_mov_alpha, run_mechanism_overlay_qa
from .renderer import (
    build_ffmpeg_overlay_mux_plan,
    compute_overlay_cache_hash,
    extract_overlay_rgba_frame,
    render_episode_overlays,
    render_single_overlay_cached,
)
from .spec import KNOWN_OVERLAY_TEMPLATES, is_graphics_available, validate_overlay_specs

__all__ = [
    "KNOWN_OVERLAY_TEMPLATES",
    "ResolvedOverlayTiming",
    "analyze_overlay_mov_alpha",
    "build_ffmpeg_overlay_mux_plan",
    "compute_overlay_cache_hash",
    "extract_overlay_rgba_frame",
    "is_graphics_available",
    "render_episode_overlays",
    "render_single_overlay_cached",
    "resolve_overlay_timings",
    "run_mechanism_overlay_qa",
    "validate_overlay_specs",
]
