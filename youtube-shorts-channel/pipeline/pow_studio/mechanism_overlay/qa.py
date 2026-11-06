#!/usr/bin/env python3
"""
Per-frame alpha-mask, safe-zone, contrast, caption-duplication, and visual-honesty QA
for Studio v9 Mechanism Overlays (`pow_studio.mechanism_overlay.qa`).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from ..schema import EpisodeManifest, MechanismOverlaySpec, ShotSpecModel
from .anchoring import ResolvedOverlayTiming
from .spec import (
    SAFE_ZONE_Y_MAX_PX,
    SAFE_ZONE_Y_MIN_PX,
    extract_overlay_visible_texts,
    validate_overlay_specs,
)


def _norm_tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) >= 2]


def analyze_overlay_mov_alpha(
    mov_path: Path,
    sample_fps: float = 6.0,
    max_alpha_area_ratio: float = 0.35,
    reclassify_after_s: float = 1.0,
) -> dict[str, Any]:
    """
    Decode RGBA frames from `mov_path` at `270x480` (exact 1/4 scale of `1080x1920`) and measure:
      - per-frame & peak `alpha_area_ratio`,
      - contiguous duration above `max_alpha_area_ratio` (`reclassified_as_infographic`),
      - pixel bounding box `[x0, y0, x1, y1]` on the `1080x1920` canvas,
      - foreground luminance vs translucent backing contrast.
    """
    sw, sh = 270, 480
    frame_bytes = sw * sh * 4
    if not mov_path.exists():
        return {
            "valid": False,
            "sampled_frames": 0,
            "mean_alpha_area_ratio": 0.0,
            "max_alpha_area_ratio": 0.0,
            "max_contiguous_excess_s": 0.0,
            "reclassified_as_infographic": False,
            "bbox_1080x1920": None,
            "foreground_luma_mean": 0.0,
        }

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(mov_path),
            "-vf",
            f"fps={sample_fps:.2f},scale={sw}:{sh}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-",
        ],
        capture_output=True,
    )
    raw = proc.stdout or b""
    n_frames = len(raw) // frame_bytes
    if n_frames <= 0:
        return {
            "valid": False,
            "sampled_frames": 0,
            "mean_alpha_area_ratio": 0.0,
            "max_alpha_area_ratio": 0.0,
            "max_contiguous_excess_s": 0.0,
            "reclassified_as_infographic": False,
            "bbox_1080x1920": None,
            "foreground_luma_mean": 0.0,
        }

    arr = np.frombuffer(raw[: n_frames * frame_bytes], dtype=np.uint8).reshape((n_frames, sh, sw, 4))
    alpha = arr[:, :, :, 3]
    active_mask = alpha >= 20
    frame_ratios = active_mask.mean(axis=(1, 2))

    # Contiguous run above max_alpha_area_ratio
    dt = 1.0 / max(0.5, float(sample_fps))
    cur_run = 0.0
    max_run = 0.0
    for r in frame_ratios:
        if float(r) > float(max_alpha_area_ratio):
            cur_run += dt
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0.0

    # Bounding box across all visible pixels (alpha >= 28), scaled x4 back to 1080x1920
    vis_any = (alpha >= 28).any(axis=0)
    if vis_any.any():
        ys, xs = np.where(vis_any)
        bbox: Optional[list[int]] = [
            int(xs.min()) * 4,
            int(ys.min()) * 4,
            min(1080, (int(xs.max()) + 1) * 4),
            min(1920, (int(ys.max()) + 1) * 4),
        ]
    else:
        bbox = None

    # Foreground stroke/text brightness (high-alpha pixels >= 180)
    hi_mask = alpha >= 180
    if hi_mask.any():
        rgb_hi = arr[:, :, :, :3][hi_mask].astype(np.float32)
        fg_luma = float((0.2126 * rgb_hi[:, 0] + 0.7152 * rgb_hi[:, 1] + 0.0722 * rgb_hi[:, 2]).mean())
    else:
        fg_luma = 220.0

    return {
        "valid": True,
        "sampled_frames": int(n_frames),
        "mean_alpha_area_ratio": round(float(frame_ratios.mean()), 4),
        "max_alpha_area_ratio": round(float(frame_ratios.max()), 4),
        "max_contiguous_excess_s": round(float(max_run), 3),
        "reclassified_as_infographic": bool(max_run > float(reclassify_after_s)),
        "bbox_1080x1920": bbox,
        "foreground_luma_mean": round(fg_luma, 1),
    }


def _estimate_underlying_shot_luma(manifest: EpisodeManifest, shot: Optional[ShotSpecModel]) -> Optional[float]:
    if shot is None:
        return None
    target: Optional[Path] = None
    for d in manifest.all_asset_search_dirs():
        cand = d / shot.src_file
        if cand.exists():
            target = cand
            break
    if target is None:
        return None
    suf = target.suffix.lower()
    try:
        if suf in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            with Image.open(target) as im:
                g = np.asarray(im.convert("L").resize((120, 120)), dtype=np.float32)
                return float(g.mean())
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, float(shot.src_in) + 0.5):.2f}",
                "-i",
                str(target),
                "-frames:v",
                "1",
                "-vf",
                "scale=120:120",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and len(proc.stdout) >= 120 * 120:
            g = np.frombuffer(proc.stdout[: 120 * 120], dtype=np.uint8).astype(np.float32)
            return float(g.mean())
    except Exception:
        return None
    return None


def _check_caption_duplication(
    ov: MechanismOverlaySpec,
    timing: ResolvedOverlayTiming,
    cues: list[dict[str, Any]],
) -> Optional[str]:
    """Return offending text if an overlay repeats active spoken subtitle prose (`>= 4` shared words)."""
    active_caption_words: set[str] = set()
    for c in cues:
        if float(c.get("end", 0.0)) > timing.start_s and float(c.get("start", 0.0)) < timing.end_s:
            active_caption_words.update(_norm_tokens(str(c.get("text") or "")))
    if not active_caption_words:
        return None

    for txt in extract_overlay_visible_texts(ov):
        toks = _norm_tokens(txt)
        if len(toks) >= 4:
            overlap = sum(1 for t in toks if t in active_caption_words) / float(len(toks))
            if overlap >= 0.80:
                return txt
    return None


def run_mechanism_overlay_qa(
    manifest: EpisodeManifest,
    resolved_timings: list[ResolvedOverlayTiming],
    rendered_paths: dict[str, Path],
    timed_shots: list[ShotSpecModel],
    cues: Optional[list[dict[str, Any]]] = None,
    total_duration_s: Optional[float] = None,
    out_dir: Optional[Path] = None,
    write_report: bool = True,
) -> dict[str, Any]:
    """
    Execute full Mechanism Overlay QA and write `<output_dir>/mechanism_overlay_qa.json`.
    """
    style = manifest.resolve_style_profile()
    mo_cfg = style.mechanism_overlays
    overlays_by_id = {ov.overlay_id: ov for ov in (manifest.mechanism_overlays or [])}
    shots_by_sid = {s.sid: s for s in timed_shots}
    tot_dur = max(0.1, float(total_duration_s or (timed_shots[-1].end_s if timed_shots else 1.0)))

    issues: list[dict[str, Any]] = list(validate_overlay_specs(manifest))
    per_overlay_reports: list[dict[str, Any]] = []

    total_overlay_s = 0.0
    reclassified_intervals: list[dict[str, Any]] = []

    for rt in resolved_timings:
        oid = rt.overlay_id
        ov = overlays_by_id.get(oid)
        mov_p = rendered_paths.get(oid)
        total_overlay_s += float(rt.duration_s)

        if rt.in_hook_zone:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "overlay_in_opening_hook",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' starts at {rt.start_s:.2f}s inside forbidden Hook window (< {mo_cfg.forbid_in_hook_s}s).",
                }
            )

        if rt.crosses_hard_cut and not rt.span_cut_allowed:
            issues.append(
                {
                    "severity": "MAJOR",
                    "code": "overlay_crosses_hard_cut",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' [{rt.start_s:.2f}s–{rt.end_s:.2f}s] crosses a hard shot cut ({rt.overlapping_shot_sids}) without span_cut=True.",
                }
            )

        if ov is not None and cues:
            dup_txt = _check_caption_duplication(ov, rt, cues)
            if dup_txt:
                issues.append(
                    {
                        "severity": "MAJOR",
                        "code": "overlay_text_duplicates_caption",
                        "overlay_id": oid,
                        "message": f"Overlay '{oid}' prose '{dup_txt}' duplicates spoken subtitles; keep overlays to concise labels/units.",
                    }
                )

        alpha_stats = (
            analyze_overlay_mov_alpha(
                mov_p,
                max_alpha_area_ratio=mo_cfg.max_alpha_area_ratio,
                reclassify_after_s=mo_cfg.alpha_area_reclassify_after_s,
            )
            if mov_p is not None
            else {"valid": False, "bbox_1080x1920": None, "reclassified_as_infographic": False, "max_alpha_area_ratio": 0.0}
        )

        bbox = alpha_stats.get("bbox_1080x1920")
        if bbox is not None:
            _, y0, _, y1 = bbox
            if y0 < SAFE_ZONE_Y_MIN_PX - 4 or y1 > SAFE_ZONE_Y_MAX_PX + 4:
                issues.append(
                    {
                        "severity": "CRITICAL",
                        "code": "overlay_pixels_violate_safe_zone",
                        "overlay_id": oid,
                        "message": (
                            f"Rendered pixels of overlay '{oid}' span y=[{y0}, {y1}]px outside "
                            f"safe zone [{SAFE_ZONE_Y_MIN_PX}, {SAFE_ZONE_Y_MAX_PX}]px."
                        ),
                    }
                )

        if alpha_stats.get("reclassified_as_infographic"):
            reclassified_intervals.append(
                {
                    "overlay_id": oid,
                    "start_s": rt.start_s,
                    "end_s": rt.end_s,
                    "duration_s": rt.duration_s,
                    "max_alpha_area_ratio": alpha_stats.get("max_alpha_area_ratio", 0.0),
                }
            )
            issues.append(
                {
                    "severity": "MINOR",
                    "code": "overlay_reclassified_as_infographic",
                    "overlay_id": oid,
                    "message": (
                        f"Overlay '{oid}' exceeds {mo_cfg.max_alpha_area_ratio*100:.0f}% frame coverage "
                        f"for >{mo_cfg.alpha_area_reclassify_after_s:.1f}s; interval counted as INFOGRAPHIC."
                    ),
                }
            )

        # Contrast check against underlying shot brightness
        primary_shot = shots_by_sid.get(rt.overlapping_shot_sids[0]) if rt.overlapping_shot_sids else None
        bg_luma = _estimate_underlying_shot_luma(manifest, primary_shot)
        fg_luma = float(alpha_stats.get("foreground_luma_mean") or 220.0)
        if bg_luma is not None and bg_luma > 205.0 and fg_luma > 205.0:
            # Templates draw dark translucent backing pills, so only flag if alpha area is tiny (no scrim)
            if float(alpha_stats.get("mean_alpha_area_ratio") or 0.0) < 0.015:
                issues.append(
                    {
                        "severity": "MINOR",
                        "code": "low_overlay_contrast_over_bright_footage",
                        "overlay_id": oid,
                        "message": f"Overlay '{oid}' bright strokes (luma {fg_luma:.0f}) sit over bright footage (luma {bg_luma:.0f}) without sufficient scrim.",
                    }
                )

        per_overlay_reports.append(
            {
                **rt.to_dict(),
                "mov_path": str(mov_p) if mov_p else None,
                "claim_ref": ov.claim_ref if ov else None,
                "honesty_label": ov.honesty_label if ov else None,
                "alpha_metrics": alpha_stats,
            }
        )

    runtime_ratio = total_overlay_s / tot_dur
    if runtime_ratio > float(mo_cfg.max_runtime_ratio) + 1e-4:
        issues.append(
            {
                "severity": "MAJOR",
                "code": "overlay_runtime_exceeds_cap",
                "overlay_id": "*",
                "message": (
                    f"Total mechanism overlay runtime {runtime_ratio*100:.1f}% ({total_overlay_s:.1f}s/{tot_dur:.1f}s) "
                    f"exceeds {mo_cfg.max_runtime_ratio*100:.0f}% ceiling."
                ),
            }
        )

    has_critical = any(i["severity"] == "CRITICAL" for i in issues)
    has_major = any(i["severity"] == "MAJOR" for i in issues)
    report = {
        "slug": manifest.slug,
        "overlay_count": len(resolved_timings),
        "total_overlay_duration_s": round(total_overlay_s, 3),
        "total_timeline_duration_s": round(tot_dur, 3),
        "mechanism_overlay_ratio": round(runtime_ratio, 4),
        "mechanism_overlay_pct": round(100.0 * runtime_ratio, 2),
        "reclassified_infographic_intervals": reclassified_intervals,
        "qa_passed": not (has_critical or has_major),
        "issues": issues,
        "overlays": per_overlay_reports,
    }

    if write_report:
        target_dir = Path(out_dir) if out_dir else Path(manifest.output_dir)
        if target_dir.exists() or out_dir is not None:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "mechanism_overlay_qa.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
    return report
