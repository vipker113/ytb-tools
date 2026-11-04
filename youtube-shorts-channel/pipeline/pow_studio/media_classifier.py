#!/usr/bin/env python3
"""
Source-Level 10-Class Media Classifier, Motion Authenticity Inspector &
5-Part Documentary Visual Coverage Metrics (`pow_studio.media_classifier` v8.0).

Implements Part 2 (Sections 4 & 5) and Part 4 (Sections 9 & 10):
1. Explicit 10-category source-level media taxonomy (`SourceMediaClass`):
   - `REAL_VIDEO_ACTION`       (Genuine moving footage = Yes | Meaningful action = Yes)
   - `REAL_VIDEO_ESTABLISHING` (Genuine moving footage = Yes | Establishing = Yes)
   - `REAL_TIME_LAPSE`         (Genuine moving footage = Yes, separately identified)
   - `STILL_PHOTO`             (Genuine moving footage = No  | Static image = Yes)
   - `ANIMATED_STILL`          (Genuine moving footage = No  | Static image = Yes)
   - `SCIENTIFIC_IMAGE`        (Genuine moving footage = No  | Static image = Yes)
   - `INFOGRAPHIC`             (Genuine moving footage = No  | Scientific visualization = Yes)
   - `REAL_ANIMATION`          (Genuine moving footage = No  | Scientific visualization = Yes, reported separately)
   - `AI_GENERATED`            (Genuine moving footage = No  | Never misrepresent as real footage)
   - `REENACTMENT`             (Genuine moving footage = No  | Identify appropriately)

2. Immutable Source-Lineage Preservation:
   - A JPEG/PNG converted into MP4 or rendered with pan, zoom, or 2.5D parallax
     NEVER becomes `REAL_VIDEO_*`; it remains `STILL_PHOTO` (if held static) or
     `ANIMATED_STILL` (if digital camera motion is applied).
   - Multi-panel shots (`triptych_hook`) weight each panel's true underlying source
     classification honestly rather than inflating moving-footage ratios.

3. Affine-Compensated Optical Motion Authenticity Analysis:
   - Replaces naive raw frame-difference checks (`median_diff >= 0.45`) with 2D patch
     displacement fitting (`u(x,y) = ax*x + bx`, `v(x,y) = ay*y + by`) + bilinear warp
     compensation so Ken Burns pan/zoom over a static image is accurately flagged as
     `ANIMATED_STILL` while genuine localized action vs establishing drift are separated.

4. 5-Part Timeline Visual Coverage Metrics:
   - A. `genuine_moving_footage_ratio`
   - B. `meaningful_action_footage_ratio`
   - C. `establishing_footage_ratio`
   - D. `static_image_ratio`
   - E. `scientific_visualization_ratio`
"""

from __future__ import annotations

import io
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

import numpy as np
from PIL import Image


class SourceMediaClass(str, Enum):
    REAL_VIDEO_ACTION = "REAL_VIDEO_ACTION"
    REAL_VIDEO_ESTABLISHING = "REAL_VIDEO_ESTABLISHING"
    REAL_TIME_LAPSE = "REAL_TIME_LAPSE"
    STILL_PHOTO = "STILL_PHOTO"
    ANIMATED_STILL = "ANIMATED_STILL"
    SCIENTIFIC_IMAGE = "SCIENTIFIC_IMAGE"
    INFOGRAPHIC = "INFOGRAPHIC"
    REAL_ANIMATION = "REAL_ANIMATION"
    AI_GENERATED = "AI_GENERATED"
    REENACTMENT = "REENACTMENT"


SourceMediaClassLiteral = Literal[
    "REAL_VIDEO_ACTION",
    "REAL_VIDEO_ESTABLISHING",
    "REAL_TIME_LAPSE",
    "STILL_PHOTO",
    "ANIMATED_STILL",
    "SCIENTIFIC_IMAGE",
    "INFOGRAPHIC",
    "REAL_ANIMATION",
    "AI_GENERATED",
    "REENACTMENT",
]

GENUINE_MOVING_CLASSES = {
    SourceMediaClass.REAL_VIDEO_ACTION.value,
    SourceMediaClass.REAL_VIDEO_ESTABLISHING.value,
    SourceMediaClass.REAL_TIME_LAPSE.value,
}

MEANINGFUL_ACTION_CLASSES = {
    SourceMediaClass.REAL_VIDEO_ACTION.value,
}

ESTABLISHING_CLASSES = {
    SourceMediaClass.REAL_VIDEO_ESTABLISHING.value,
}

STATIC_IMAGE_CLASSES = {
    SourceMediaClass.STILL_PHOTO.value,
    SourceMediaClass.ANIMATED_STILL.value,
    SourceMediaClass.SCIENTIFIC_IMAGE.value,
}

SCIENTIFIC_VISUALIZATION_CLASSES = {
    SourceMediaClass.INFOGRAPHIC.value,
    SourceMediaClass.REAL_ANIMATION.value,
}

STILL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v", ".ogv", ".avi"}

ACTION_CUE_PATTERN = re.compile(
    r"\b(?:sampling|sample|drilling|drill|lowering|collecting|collect|walking|climbing|"
    r"traversing|diving|swimming|slithering|striking|hunting|moving|crawling|bubbling|"
    r"boiling|erupting|flowing|pouring|venting|smoking|steaming|operating|deploying|"
    r"measuring|swabbing|coring|excavating|handling|testing|pipetting|spinning|flying|"
    r"hovering|landing|launching|manipulator|rov|submersible|expedition|fieldwork)\b",
    re.I,
)

ESTABLISHING_ONLY_PATTERN = re.compile(
    r"\b(?:aerial|drone|flyover|panorama|panoramic|landscape|horizon|overview|"
    r"satellite\s+view|wide\s+establishing|scenic\s+view|empty\s+desert|mountain\s+range)\b",
    re.I,
)

TIME_LAPSE_PATTERN = re.compile(r"\b(?:time[- ]?lapse|timelapse|hyperlapse)\b", re.I)

SCIENTIFIC_STILL_PATTERN = re.compile(
    r"\b(?:microscopy|micrograph|sem\b|tem\b|epifluorescence|histology|x-ray|spectrometer|"
    r"landsat|aster\b|modis\b|sentinel-2|hirise|radargram|sonar\s+bathymetry\s+still)\b",
    re.I,
)

INFOGRAPHIC_PATTERN = re.compile(
    r"\b(?:infographic|diagram|chart|bar\s+chart|graph|dashboard|cross[- ]section|"
    r"schematic|map\s+panel|scale\s+comparison|slide|table|statistics\s+card)\b",
    re.I,
)

ANIMATION_PATTERN = re.compile(
    r"\b(?:animation|animated\s+simulation|3d\s+simulation|numerical\s+model|"
    r"computer\s+simulation|artist'?s\s+animation|cgi\s+simulation|svs\s+simulation)\b",
    re.I,
)

AI_GENERATED_PATTERN = re.compile(
    r"\b(?:ai[- ]generated|midjourney|runway|sora|veo|stable\s+diffusion|dall[- ]?e|"
    r"synthetic\s+ai\s+video|generative\s+ai)\b",
    re.I,
)

REENACTMENT_PATTERN = re.compile(
    r"\b(?:reenactment|re-enactment|dramatization|staged\s+reconstruction|actor\s+portrayal)\b",
    re.I,
)


@dataclass
class MediaAuthenticityAudit:
    valid: bool
    container_kind: str  # "still_file", "video_file", "missing"
    sampled_frames: int
    width: int
    height: int
    raw_mean_diff: float
    raw_median_diff: float
    affine_compensated_diff: float
    residual_to_raw_ratio: float
    p90_local_flow_residual_px: float
    independent_motion_patch_ratio: float
    flat_graphic_pixel_ratio: float
    grid_box_edge_score: float
    is_frozen_static: bool
    is_baked_animated_still: bool
    is_dense_presentation_graphic: bool
    has_localized_action_motion: bool
    is_real_moving_footage: bool
    inferred_media_class: str
    diagnostic_note: str


def _bilinear_warp_gray(img: np.ndarray, ax: float, bx: float, ay: float, by: float) -> tuple[np.ndarray, np.ndarray]:
    """
    Predict Frame t+1 from Frame t given forward displacement `u(x) = ax*x + bx`, `v(y) = ay*y + by`,
    i.e., pixel `(x', y')` in Frame t+1 originates from `x = (x' - bx)/(1 + ax)`, `y = (y' - by)/(1 + ay)`.
    Returns `(warped_t, valid_interior_mask)`.
    """
    h, w = img.shape
    denom_x = max(0.25, 1.0 + ax)
    denom_y = max(0.25, 1.0 + ay)

    xs = (np.arange(w, dtype=np.float32) - bx) / denom_x
    ys = (np.arange(h, dtype=np.float32) - by) / denom_y
    gx, gy = np.meshgrid(xs, ys)

    valid = (gx >= 2.0) & (gx <= w - 3.0) & (gy >= 2.0) & (gy <= h - 3.0)
    x0 = np.clip(np.floor(gx).astype(np.int32), 0, w - 2)
    y0 = np.clip(np.floor(gy).astype(np.int32), 0, h - 2)
    wx = np.clip(gx - x0, 0.0, 1.0)
    wy = np.clip(gy - y0, 0.0, 1.0)

    i00 = img[y0, x0]
    i10 = img[y0, x0 + 1]
    i01 = img[y0 + 1, x0]
    i11 = img[y0 + 1, x0 + 1]
    warped = (
        (1.0 - wx) * (1.0 - wy) * i00
        + wx * (1.0 - wy) * i10
        + (1.0 - wx) * wy * i01
        + wx * wy * i11
    )
    return warped.astype(np.float32), valid


def _estimate_pair_motion_decomposition(
    f0: np.ndarray,
    f1: np.ndarray,
    search_r: int = 18,
    patch_size: int = 20,
) -> dict[str, float]:
    """
    Decompose frame-to-frame motion between `f0` and `f1` into:
      1. Global 2D pan/zoom similarity transform `(ax, bx, ay, by)`
      2. Local non-rigid / multi-object residual flow (`p90_flow_res_px`, `indep_ratio`)
      3. Affine-compensated appearance residual (`comp_diff`) vs raw frame difference (`raw_diff`).
    """
    h, w = f0.shape
    raw_diff = float(np.mean(np.abs(f1 - f0)))
    if raw_diff < 0.35:
        return {
            "raw_diff": raw_diff,
            "comp_diff": raw_diff,
            "p90_flow_res_px": 0.0,
            "indep_ratio": 0.0,
            "textured_patches": 0,
        }

    margin = search_r + patch_size // 2 + 2
    if h < 2 * margin + 16 or w < 2 * margin + 16:
        return {
            "raw_diff": raw_diff,
            "comp_diff": raw_diff,
            "p90_flow_res_px": 0.0,
            "indep_ratio": 0.0,
            "textured_patches": 0,
        }

    ys = np.linspace(margin, h - margin - 1, 6).astype(int)
    xs = np.linspace(margin, w - margin - 1, 6).astype(int)
    half = patch_size // 2

    pts_x: list[float] = []
    pts_y: list[float] = []
    vecs_u: list[float] = []
    vecs_v: list[float] = []
    patch_min_sad: list[float] = []

    for cy in ys:
        for cx in xs:
            tpl = f0[cy - half : cy + half, cx - half : cx + half]
            if float(np.std(tpl)) < 3.2:
                continue
            best_sad = 1e9
            best_du = 0
            best_dv = 0
            sad_grid = np.full((2 * search_r + 1, 2 * search_r + 1), 1e9, dtype=np.float32)

            # Coarse step-2 search then 3x3 refine around best candidate for speed
            for dv in range(-search_r, search_r + 1, 2):
                y_lo = cy - half + dv
                for du in range(-search_r, search_r + 1, 2):
                    x_lo = cx - half + du
                    cand = f1[y_lo : y_lo + patch_size, x_lo : x_lo + patch_size]
                    sad = float(np.mean(np.abs(cand - tpl)))
                    sad_grid[dv + search_r, du + search_r] = sad
                    if sad < best_sad:
                        best_sad = sad
                        best_du = du
                        best_dv = dv

            c_du, c_dv = best_du, best_dv
            for dv in range(max(-search_r, c_dv - 1), min(search_r, c_dv + 1) + 1):
                y_lo = cy - half + dv
                for du in range(max(-search_r, c_du - 1), min(search_r, c_du + 1) + 1):
                    if sad_grid[dv + search_r, du + search_r] < 1e8:
                        continue
                    x_lo = cx - half + du
                    cand = f1[y_lo : y_lo + patch_size, x_lo : x_lo + patch_size]
                    sad = float(np.mean(np.abs(cand - tpl)))
                    sad_grid[dv + search_r, du + search_r] = sad
                    if sad < best_sad:
                        best_sad = sad
                        best_du = du
                        best_dv = dv

            # 1D parabolic subpixel refinement
            sub_u = float(best_du)
            sub_v = float(best_dv)
            iu = best_du + search_r
            iv = best_dv + search_r
            if 0 < iu < 2 * search_r:
                s_l, s_c, s_r = sad_grid[iv, iu - 1], sad_grid[iv, iu], sad_grid[iv, iu + 1]
                if s_l < 1e8 and s_r < 1e8:
                    denom = 2.0 * (s_l - 2.0 * s_c + s_r)
                    if abs(denom) > 1e-4:
                        sub_u += float(np.clip((s_l - s_r) / denom, -0.5, 0.5))
            if 0 < iv < 2 * search_r:
                s_u, s_c, s_d = sad_grid[iv - 1, iu], sad_grid[iv, iu], sad_grid[iv + 1, iu]
                if s_u < 1e8 and s_d < 1e8:
                    denom = 2.0 * (s_u - 2.0 * s_c + s_d)
                    if abs(denom) > 1e-4:
                        sub_v += float(np.clip((s_u - s_d) / denom, -0.5, 0.5))

            pts_x.append(float(cx))
            pts_y.append(float(cy))
            vecs_u.append(sub_u)
            vecs_v.append(sub_v)
            patch_min_sad.append(best_sad)

    n_tex = len(pts_x)
    if n_tex < 4:
        return {
            "raw_diff": raw_diff,
            "comp_diff": raw_diff * 0.85,
            "p90_flow_res_px": 0.0,
            "indep_ratio": 0.0,
            "textured_patches": n_tex,
        }

    px = np.array(pts_x, dtype=np.float64)
    py = np.array(pts_y, dtype=np.float64)
    vu = np.array(vecs_u, dtype=np.float64)
    vv = np.array(vecs_v, dtype=np.float64)

    # Robust 2-pass linear fit `u = ax*x + bx`, `v = ay*y + by`
    ax_mat = np.column_stack([px, np.ones_like(px)])
    ay_mat = np.column_stack([py, np.ones_like(py)])
    coef_x, _, _, _ = np.linalg.lstsq(ax_mat, vu, rcond=None)
    coef_y, _, _, _ = np.linalg.lstsq(ay_mat, vv, rcond=None)

    res_init = np.hypot(vu - (coef_x[0] * px + coef_x[1]), vv - (coef_y[0] * py + coef_y[1]))
    inliers = res_init <= max(1.0, float(np.percentile(res_init, 70.0)))
    if int(np.sum(inliers)) >= 4:
        coef_x, _, _, _ = np.linalg.lstsq(ax_mat[inliers], vu[inliers], rcond=None)
        coef_y, _, _, _ = np.linalg.lstsq(ay_mat[inliers], vv[inliers], rcond=None)

    flow_res = np.hypot(vu - (coef_x[0] * px + coef_x[1]), vv - (coef_y[0] * py + coef_y[1]))
    p90_res = float(np.percentile(flow_res, 90.0))
    indep_ratio = float(np.mean(flow_res > 0.85))

    warped_f0, valid_mask = _bilinear_warp_gray(
        f0, float(coef_x[0]), float(coef_x[1]), float(coef_y[0]), float(coef_y[1])
    )
    if int(np.sum(valid_mask)) > 100:
        comp_diff = float(np.mean(np.abs(f1[valid_mask] - warped_f0[valid_mask])))
    else:
        comp_diff = raw_diff

    return {
        "raw_diff": raw_diff,
        "comp_diff": comp_diff,
        "p90_flow_res_px": p90_res,
        "indep_ratio": indep_ratio,
        "textured_patches": n_tex,
    }


def detect_presentation_graphic_metrics(img_rgb: Image.Image) -> tuple[float, float, bool]:
    """
    Detect PowerPoint-style slides, multi-box statistic panels, or dense charts:
      - `flat_pixel_ratio`: share of pixels with near-zero local gradient (`< 1.4` gray levels)
      - `grid_box_edge_score`: concentration of strictly horizontal/vertical UI box lines
      - `is_dense_presentation_slide`: True when layout resembles a slide/chart dashboard rather
        than natural documentary photography/footage.
    """
    small = img_rgb.convert("L").resize((240, int(max(120, round(240 * img_rgb.height / max(1, img_rgb.width))))), Image.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    gx = np.abs(np.diff(arr, axis=1, prepend=arr[:, :1]))
    gy = np.abs(np.diff(arr, axis=0, prepend=arr[:1, :]))
    grad = np.hypot(gx, gy)

    flat_ratio = float(np.mean(grad < 1.35))
    # Axis-aligned crisp box borders / text rows produce strong row/col mean edge spikes
    row_peaks = float(np.percentile(np.mean(gy, axis=1), 95.0) / max(1.0, float(np.median(np.mean(gy, axis=1))) + 0.5))
    col_peaks = float(np.percentile(np.mean(gx, axis=0), 95.0) / max(1.0, float(np.median(np.mean(gx, axis=0))) + 0.5))
    grid_score = round(0.5 * (row_peaks + col_peaks), 3)

    # Count distinct horizontal bands of text/boxes on flat background
    high_contrast_sharp = float(np.mean(grad > 28.0))
    is_slide = bool(
        (flat_ratio >= 0.52 and grid_score >= 3.2 and high_contrast_sharp >= 0.035)
        or (flat_ratio >= 0.65 and high_contrast_sharp >= 0.045)
    )
    return round(flat_ratio, 3), grid_score, is_slide


def inspect_media_authenticity(
    media_path: Path,
    start_s: float = 0.0,
    duration_s: float = 4.0,
    sample_fps: float = 8.0,
    metadata_hint: str = "",
) -> MediaAuthenticityAudit:
    """
    Decode actual media frames and distinguish:
      - Static photograph / scientific image / infographic (`STILL_PHOTO` / `SCIENTIFIC_IMAGE` / `INFOGRAPHIC`)
      - Baked-in animated photograph / Ken Burns pan-zoom MP4 (`ANIMATED_STILL`)
      - Dense PowerPoint / dashboard chart MP4 (`INFOGRAPHIC`)
      - Genuine recorded moving video with localized subject/process motion (`REAL_VIDEO_ACTION`)
      - Genuine recorded establishing landscape/aerial drift (`REAL_VIDEO_ESTABLISHING`)
      - Genuine time-lapse (`REAL_TIME_LAPSE`)
    """
    if not media_path.exists():
        return MediaAuthenticityAudit(
            valid=False,
            container_kind="missing",
            sampled_frames=0,
            width=0,
            height=0,
            raw_mean_diff=0.0,
            raw_median_diff=0.0,
            affine_compensated_diff=0.0,
            residual_to_raw_ratio=0.0,
            p90_local_flow_residual_px=0.0,
            independent_motion_patch_ratio=0.0,
            flat_graphic_pixel_ratio=0.0,
            grid_box_edge_score=0.0,
            is_frozen_static=True,
            is_baked_animated_still=False,
            is_dense_presentation_graphic=False,
            has_localized_action_motion=False,
            is_real_moving_footage=False,
            inferred_media_class=SourceMediaClass.STILL_PHOTO.value,
            diagnostic_note=f"File not found: {media_path}",
        )

    suf = media_path.suffix.lower()
    if suf in STILL_EXTENSIONS:
        with Image.open(media_path) as im:
            rgb = im.convert("RGB")
            w, h = rgb.size
            flat_r, grid_s, is_slide = detect_presentation_graphic_metrics(rgb)
        if INFOGRAPHIC_PATTERN.search(metadata_hint) or is_slide:
            mcls = SourceMediaClass.INFOGRAPHIC.value
        elif SCIENTIFIC_STILL_PATTERN.search(metadata_hint):
            mcls = SourceMediaClass.SCIENTIFIC_IMAGE.value
        else:
            mcls = SourceMediaClass.STILL_PHOTO.value
        return MediaAuthenticityAudit(
            valid=True,
            container_kind="still_file",
            sampled_frames=1,
            width=w,
            height=h,
            raw_mean_diff=0.0,
            raw_median_diff=0.0,
            affine_compensated_diff=0.0,
            residual_to_raw_ratio=0.0,
            p90_local_flow_residual_px=0.0,
            independent_motion_patch_ratio=0.0,
            flat_graphic_pixel_ratio=flat_r,
            grid_box_edge_score=grid_s,
            is_frozen_static=True,
            is_baked_animated_still=False,
            is_dense_presentation_graphic=is_slide,
            has_localized_action_motion=False,
            is_real_moving_footage=False,
            inferred_media_class=mcls,
            diagnostic_note="Native static image file.",
        )

    # Probe native video dimensions
    w_nat, h_nat = 0, 0
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(media_path)],
        capture_output=True,
        text=True,
    )
    if pr.returncode == 0:
        try:
            st = (json.loads(pr.stdout).get("streams") or [{}])[0]
            w_nat = int(st.get("width", 0) or 0)
            h_nat = int(st.get("height", 0) or 0)
        except Exception:
            pass

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, start_s):.2f}",
            "-t",
            f"{max(1.2, duration_s):.2f}",
            "-i",
            str(media_path),
            "-vf",
            f"fps={sample_fps},scale=256:-2",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
    )
    sig = b"\x89PNG\r\n\x1a\n"
    parts = proc.stdout.split(sig)[1:]
    rgb_frames: list[Image.Image] = []
    gray_frames: list[np.ndarray] = []
    for p in parts:
        try:
            im = Image.open(io.BytesIO(sig + p)).convert("RGB")
            rgb_frames.append(im)
            gray_frames.append(np.asarray(im.convert("L"), dtype=np.float32))
        except Exception:
            continue

    if len(gray_frames) < 3:
        return MediaAuthenticityAudit(
            valid=False,
            container_kind="video_file",
            sampled_frames=len(gray_frames),
            width=w_nat,
            height=h_nat,
            raw_mean_diff=0.0,
            raw_median_diff=0.0,
            affine_compensated_diff=0.0,
            residual_to_raw_ratio=0.0,
            p90_local_flow_residual_px=0.0,
            independent_motion_patch_ratio=0.0,
            flat_graphic_pixel_ratio=0.0,
            grid_box_edge_score=0.0,
            is_frozen_static=True,
            is_baked_animated_still=False,
            is_dense_presentation_graphic=False,
            has_localized_action_motion=False,
            is_real_moving_footage=False,
            inferred_media_class=SourceMediaClass.STILL_PHOTO.value,
            diagnostic_note="Fewer than 3 decodable video frames.",
        )

    flat_r, grid_s, is_slide = detect_presentation_graphic_metrics(rgb_frames[len(rgb_frames) // 2])
    pair_stats = [_estimate_pair_motion_decomposition(gray_frames[i], gray_frames[i + 1]) for i in range(len(gray_frames) - 1)]

    raw_diffs = [s["raw_diff"] for s in pair_stats]
    comp_diffs = [s["comp_diff"] for s in pair_stats]
    flow_res = [s["p90_flow_res_px"] for s in pair_stats]
    indep_ratios = [s["indep_ratio"] for s in pair_stats]

    raw_mean = float(np.mean(raw_diffs))
    raw_med = float(np.median(raw_diffs))
    comp_med = float(np.median(comp_diffs))
    p90_flow_med = float(np.median(flow_res))
    indep_med = float(np.median(indep_ratios))
    res_ratio = comp_med / max(0.35, raw_med)

    is_frozen = raw_med < 0.45

    # Baked-in Ken Burns / animated still detection:
    # Raw pixel diff is high (>= 0.45) because of global crop zoom/pan, YET once global 2D
    # scale+translation is compensated, both local flow divergence (`p90_flow_med`) and
    # warped pixel residual collapse (`res_ratio` small & `indep_med` low).
    is_ken_burns = bool(
        not is_frozen
        and p90_flow_med < 1.35
        and indep_med < 0.25
        and (comp_med < 5.50 and res_ratio < 0.42)
    )

    # Metadata overrides for synthetic/non-camera classes
    if AI_GENERATED_PATTERN.search(metadata_hint):
        mcls = SourceMediaClass.AI_GENERATED.value
        is_real = False
        has_action = False
        note = "Flagged as AI-generated visual; barred from counting as real footage."
    elif REENACTMENT_PATTERN.search(metadata_hint):
        mcls = SourceMediaClass.REENACTMENT.value
        is_real = False
        has_action = False
        note = "Staged reenactment; excluded from genuine documentary footage metrics."
    elif INFOGRAPHIC_PATTERN.search(metadata_hint) or is_slide:
        mcls = SourceMediaClass.INFOGRAPHIC.value
        is_real = False
        has_action = False
        note = "Presentation chart/diagram/infographic layout detected."
    elif ANIMATION_PATTERN.search(metadata_hint):
        mcls = SourceMediaClass.REAL_ANIMATION.value
        is_real = False
        has_action = False
        note = "Scientific animation or simulation; reported under Scientific Visualization."
    elif is_frozen:
        mcls = SourceMediaClass.STILL_PHOTO.value
        is_real = False
        has_action = False
        note = f"Frozen/static frame sequence inside video container (median_diff={raw_med:.3f})."
    elif is_ken_burns:
        mcls = SourceMediaClass.ANIMATED_STILL.value
        is_real = False
        has_action = False
        note = (
            f"Artificial pan/zoom over static image detected (raw_diff={raw_med:.2f}, "
            f"compensated_diff={comp_med:.2f}, ratio={res_ratio:.2f}, p90_flow_res={p90_flow_med:.2f}px)."
        )
    elif TIME_LAPSE_PATTERN.search(metadata_hint):
        mcls = SourceMediaClass.REAL_TIME_LAPSE.value
        is_real = True
        has_action = False
        note = "Genuine recorded time-lapse footage."
    else:
        is_real = True
        has_local_activity = (p90_flow_med >= 0.85 and indep_med >= 0.16) or (comp_med >= 2.25 and indep_med >= 0.12)
        explicit_action_meta = bool(ACTION_CUE_PATTERN.search(metadata_hint)) and not bool(ESTABLISHING_ONLY_PATTERN.search(metadata_hint))
        explicit_estab_meta = bool(ESTABLISHING_ONLY_PATTERN.search(metadata_hint)) and not bool(ACTION_CUE_PATTERN.search(metadata_hint))

        if explicit_estab_meta and not (p90_flow_med >= 2.2 and indep_med >= 0.35):
            has_action = False
            mcls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            note = "Genuine establishing aerial/landscape video."
        elif has_local_activity or explicit_action_meta:
            has_action = True
            mcls = SourceMediaClass.REAL_VIDEO_ACTION.value
            note = (
                f"Genuine moving footage with localized subject/process activity "
                f"(p90_flow_res={p90_flow_med:.2f}px, indep_patches={indep_med:.0%})."
            )
        else:
            has_action = False
            mcls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            note = (
                f"Genuine moving location/establishing footage without distinct localized action "
                f"(p90_flow_res={p90_flow_med:.2f}px)."
            )

    return MediaAuthenticityAudit(
        valid=True,
        container_kind="video_file",
        sampled_frames=len(gray_frames),
        width=w_nat,
        height=h_nat,
        raw_mean_diff=round(raw_mean, 3),
        raw_median_diff=round(raw_med, 3),
        affine_compensated_diff=round(comp_med, 3),
        residual_to_raw_ratio=round(res_ratio, 3),
        p90_local_flow_residual_px=round(p90_flow_med, 3),
        independent_motion_patch_ratio=round(indep_med, 3),
        flat_graphic_pixel_ratio=flat_r,
        grid_box_edge_score=grid_s,
        is_frozen_static=is_frozen,
        is_baked_animated_still=is_ken_burns,
        is_dense_presentation_graphic=is_slide,
        has_localized_action_motion=has_action,
        is_real_moving_footage=is_real,
        inferred_media_class=mcls,
        diagnostic_note=note,
    )


def infer_asset_source_media_class(
    asset: Any,
    resolved_path: Optional[Path] = None,
    probe_pixels: bool = False,
) -> str:
    """
    Determine the canonical 10-category `SourceMediaClass` of a registered source asset,
    strictly preserving original source lineage (a JPEG converted into MP4 remains a still!).
    """
    explicit = getattr(asset, "source_media_class", None)
    orig_file = str(getattr(asset, "original_media_file", "") or "")
    local_file = str(getattr(asset, "local_file", "") or "")
    legacy_mtype = str(getattr(asset, "media_type", "") or "").lower()
    is_first_party = bool(getattr(asset, "is_first_party_original", False))
    meta_text = " ".join(
        str(getattr(asset, k, "") or "")
        for k in ("title", "intended_use", "depicted_action", "depicted_subject", "local_file")
    )

    # Hard rule (Part 2 Section 4): A JPEG/PNG converted into MP4 MUST remain a still photograph!
    if orig_file and Path(orig_file).suffix.lower() in STILL_EXTENSIONS:
        if SCIENTIFIC_STILL_PATTERN.search(meta_text):
            return SourceMediaClass.SCIENTIFIC_IMAGE.value
        if INFOGRAPHIC_PATTERN.search(meta_text):
            return SourceMediaClass.INFOGRAPHIC.value
        if Path(local_file).suffix.lower() in VIDEO_EXTENSIONS:
            return SourceMediaClass.ANIMATED_STILL.value
        return SourceMediaClass.STILL_PHOTO.value

    if explicit in {c.value for c in SourceMediaClass}:
        # Still guard against someone mislabeling a `.jpg` as REAL_VIDEO_*
        if Path(local_file).suffix.lower() in STILL_EXTENSIONS and explicit in GENUINE_MOVING_CLASSES:
            return SourceMediaClass.STILL_PHOTO.value
        if legacy_mtype == "photo" and explicit in GENUINE_MOVING_CLASSES:
            return SourceMediaClass.ANIMATED_STILL.value if Path(local_file).suffix.lower() in VIDEO_EXTENSIONS else SourceMediaClass.STILL_PHOTO.value
        return str(explicit)

    if AI_GENERATED_PATTERN.search(meta_text):
        return SourceMediaClass.AI_GENERATED.value
    if REENACTMENT_PATTERN.search(meta_text):
        return SourceMediaClass.REENACTMENT.value

    suf = Path(local_file).suffix.lower()
    if is_first_party or legacy_mtype == "diagram":
        if ANIMATION_PATTERN.search(meta_text) and suf in VIDEO_EXTENSIONS and not INFOGRAPHIC_PATTERN.search(meta_text):
            return SourceMediaClass.REAL_ANIMATION.value
        return SourceMediaClass.INFOGRAPHIC.value

    if suf in STILL_EXTENSIONS or legacy_mtype == "photo":
        if INFOGRAPHIC_PATTERN.search(meta_text):
            return SourceMediaClass.INFOGRAPHIC.value
        if SCIENTIFIC_STILL_PATTERN.search(meta_text):
            return SourceMediaClass.SCIENTIFIC_IMAGE.value
        if suf in VIDEO_EXTENSIONS:
            return SourceMediaClass.ANIMATED_STILL.value
        return SourceMediaClass.STILL_PHOTO.value

    if probe_pixels and resolved_path is not None and resolved_path.exists():
        audit = inspect_media_authenticity(resolved_path, metadata_hint=meta_text)
        if audit.valid:
            return audit.inferred_media_class

    if ANIMATION_PATTERN.search(meta_text):
        return SourceMediaClass.REAL_ANIMATION.value
    if INFOGRAPHIC_PATTERN.search(meta_text):
        return SourceMediaClass.INFOGRAPHIC.value
    if TIME_LAPSE_PATTERN.search(meta_text):
        return SourceMediaClass.REAL_TIME_LAPSE.value

    depicts_action = getattr(asset, "depicts_meaningful_action", None)
    if depicts_action is True:
        return SourceMediaClass.REAL_VIDEO_ACTION.value
    if depicts_action is False:
        return SourceMediaClass.REAL_VIDEO_ESTABLISHING.value

    if ESTABLISHING_ONLY_PATTERN.search(meta_text) and not ACTION_CUE_PATTERN.search(meta_text):
        return SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
    if ACTION_CUE_PATTERN.search(meta_text):
        return SourceMediaClass.REAL_VIDEO_ACTION.value
    return SourceMediaClass.REAL_VIDEO_ESTABLISHING.value


def classify_timeline_shot_media(
    shot: Any,
    assets_by_name: dict[str, Any],
    manifest: Optional[Any] = None,
    probe_pixels: bool = False,
) -> dict[str, Any]:
    """
    Classify how `shot` behaves on the rendered timeline while preserving `source_media_class`.
    Crucially:
      - If `source_media_class` is `STILL_PHOTO` or `SCIENTIFIC_IMAGE` and the shot applies
        pan/zoom/2.5D parallax (`still_parallax_25d`, `z0 != z1`, `cx0 != cx1`, `cy0 != cy1`,
        or `parallax_px > 0`), `effective_media_class` becomes `ANIMATED_STILL` (still 0%
        genuine moving footage!).
      - If `shot.kind == "triptych_hook"`, computes exact 1/3 panel-weighted class durations
        across `src_file`, `secondary_src_file`, and `tertiary_src_file` so static JPEG panels
        inside a split-screen hook NEVER inflate `genuine_moving_footage_ratio`.
    """
    dur = max(0.0, float(shot.end_s) - float(shot.start_s))

    def _resolve_file(fname: str) -> Optional[Path]:
        if not fname:
            return None
        if manifest is not None:
            for d in manifest.all_asset_search_dirs():
                p = d / fname
                if p.exists():
                    return p
        direct = Path(fname)
        return direct if direct.exists() else None

    def _classify_single_file(fname: str, is_primary: bool = True) -> tuple[str, str, Optional[MediaAuthenticityAudit]]:
        aspec = assets_by_name.get(fname)
        rpath = _resolve_file(fname)
        shot_context = " ".join(
            str(getattr(shot, k, "") or "")
            for k in ("visible_action", "story_beat", "visual_desc", "camera_perspective")
        )
        src_cls = (
            infer_asset_source_media_class(aspec, resolved_path=rpath, probe_pixels=probe_pixels)
            if aspec is not None
            else (
                SourceMediaClass.STILL_PHOTO.value
                if Path(fname).suffix.lower() in STILL_EXTENSIONS
                else SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            )
        )
        audit_obj: Optional[MediaAuthenticityAudit] = None
        if probe_pixels and rpath is not None and rpath.exists() and Path(fname).suffix.lower() in VIDEO_EXTENSIONS:
            meta_hint = f"{getattr(aspec, 'title', '') if aspec else ''} {shot_context}"
            audit_obj = inspect_media_authenticity(
                rpath,
                start_s=float(getattr(shot, "src_in", 0.0) if is_primary else 0.0),
                duration_s=min(4.5, max(1.2, dur)),
                metadata_hint=meta_hint,
            )
            if audit_obj.valid and audit_obj.inferred_media_class in (
                SourceMediaClass.ANIMATED_STILL.value,
                SourceMediaClass.STILL_PHOTO.value,
                SourceMediaClass.INFOGRAPHIC.value,
            ):
                # Never allow a baked-in Ken Burns or static slide MP4 to masquerade as REAL_VIDEO_*
                src_cls = audit_obj.inferred_media_class

        if not bool(getattr(shot, "is_real_evidence", True)) or getattr(shot, "kind", "") == "diagram":
            if src_cls not in (SourceMediaClass.REAL_ANIMATION.value, SourceMediaClass.AI_GENERATED.value, SourceMediaClass.REENACTMENT.value):
                src_cls = SourceMediaClass.INFOGRAPHIC.value

        # Refine REAL_VIDEO_ESTABLISHING vs REAL_VIDEO_ACTION using shot-level visible_action / human interaction
        if src_cls in (SourceMediaClass.REAL_VIDEO_ACTION.value, SourceMediaClass.REAL_VIDEO_ESTABLISHING.value):
            vis_act = str(getattr(shot, "visible_action", "") or "")
            has_hum = bool(getattr(shot, "has_human_interaction", False))
            persp = str(getattr(shot, "camera_perspective", "") or "")
            explicit_no_action = getattr(aspec, "depicts_meaningful_action", None) is False
            if explicit_no_action:
                src_cls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            elif has_hum or (vis_act and ACTION_CUE_PATTERN.search(vis_act)):
                src_cls = SourceMediaClass.REAL_VIDEO_ACTION.value
            elif persp in ("wide_establishing", "aerial_orbital") and ESTABLISHING_ONLY_PATTERN.search(shot_context) and not ACTION_CUE_PATTERN.search(shot_context):
                src_cls = SourceMediaClass.REAL_VIDEO_ESTABLISHING.value
            elif ACTION_CUE_PATTERN.search(shot_context) and not ESTABLISHING_ONLY_PATTERN.search(shot_context):
                src_cls = SourceMediaClass.REAL_VIDEO_ACTION.value

        eff_cls = src_cls
        if is_primary and src_cls in (SourceMediaClass.STILL_PHOTO.value, SourceMediaClass.SCIENTIFIC_IMAGE.value):
            has_digital_cam_motion = (
                getattr(shot, "kind", "") == "still_parallax_25d"
                or float(getattr(shot, "parallax_px", 0.0) or 0.0) > 0.5
                or abs(float(getattr(shot, "z1", 1.0)) - float(getattr(shot, "z0", 1.0))) > 0.004
                or abs(float(getattr(shot, "cx1", 0.5)) - float(getattr(shot, "cx0", 0.5))) > 0.004
                or abs(float(getattr(shot, "cy1", 0.5)) - float(getattr(shot, "cy0", 0.5))) > 0.004
            )
            if bool(getattr(shot, "disable_artificial_still_motion", False)):
                has_digital_cam_motion = False
            if has_digital_cam_motion and src_cls == SourceMediaClass.STILL_PHOTO.value:
                eff_cls = SourceMediaClass.ANIMATED_STILL.value
        return src_cls, eff_cls, audit_obj

    if getattr(shot, "kind", "") == "triptych_hook":
        panel_files = [
            str(getattr(shot, "src_file", "") or ""),
            str(getattr(shot, "secondary_src_file", "") or ""),
            str(getattr(shot, "tertiary_src_file", "") or ""),
        ]
        valid_panels = [f for f in panel_files if f]
        class_seconds: dict[str, float] = {}
        panel_details: list[dict[str, Any]] = []
        share = dur / float(max(1, len(valid_panels)))
        for idx, pf in enumerate(valid_panels):
            s_cls, e_cls, aud = _classify_single_file(pf, is_primary=(idx == 0))
            class_seconds[e_cls] = class_seconds.get(e_cls, 0.0) + share
            panel_details.append({"file": pf, "source_media_class": s_cls, "effective_media_class": e_cls})
        primary_src = panel_details[0]["source_media_class"] if panel_details else SourceMediaClass.STILL_PHOTO.value
        primary_eff = panel_details[0]["effective_media_class"] if panel_details else SourceMediaClass.STILL_PHOTO.value
        return {
            "sid": shot.sid,
            "duration_s": round(dur, 4),
            "source_media_class": primary_src,
            "effective_media_class": primary_eff,
            "is_multi_panel": True,
            "panel_breakdown": panel_details,
            "class_duration_s": {k: round(v, 4) for k, v in class_seconds.items()},
            "counts_as_genuine_moving_footage": all(p["effective_media_class"] in GENUINE_MOVING_CLASSES for p in panel_details),
            "pixel_audit": None,
        }

    src_cls, eff_cls, audit_obj = _classify_single_file(shot.src_file, is_primary=True)
    return {
        "sid": shot.sid,
        "duration_s": round(dur, 4),
        "source_media_class": src_cls,
        "effective_media_class": eff_cls,
        "is_multi_panel": False,
        "panel_breakdown": [],
        "class_duration_s": {eff_cls: round(dur, 4)},
        "counts_as_genuine_moving_footage": eff_cls in GENUINE_MOVING_CLASSES,
        "pixel_audit": asdict(audit_obj) if audit_obj is not None else None,
    }


def compute_visual_coverage_metrics(
    timed_shots: list[Any],
    assets_register: list[Any],
    manifest: Optional[Any] = None,
    probe_pixels: bool = False,
) -> dict[str, Any]:
    """
    Compute the 5 required source-honest visual coverage metrics (Part 2 Section 5):
      A. `genuine_moving_footage_ratio`
      B. `meaningful_action_footage_ratio`
      C. `establishing_footage_ratio`
      D. `static_image_ratio`
      E. `scientific_visualization_ratio`
    Never inflates moving footage using `ANIMATED_STILL` pan/zoom/parallax or static triptych panels.
    """
    assets_by_name = {a.local_file: a for a in assets_register}
    class_totals_s: dict[str, float] = {c.value: 0.0 for c in SourceMediaClass}
    shot_classifications: list[dict[str, Any]] = []

    total_dur = 0.0
    for s in timed_shots:
        info = classify_timeline_shot_media(s, assets_by_name, manifest=manifest, probe_pixels=probe_pixels)
        shot_classifications.append(info)
        total_dur += float(info["duration_s"])
        for cls_name, sec in info["class_duration_s"].items():
            class_totals_s[cls_name] = class_totals_s.get(cls_name, 0.0) + float(sec)

    denom = max(1e-6, total_dur)
    genuine_moving_s = sum(class_totals_s[c] for c in GENUINE_MOVING_CLASSES)
    meaningful_action_s = sum(class_totals_s[c] for c in MEANINGFUL_ACTION_CLASSES)
    establishing_s = sum(class_totals_s[c] for c in ESTABLISHING_CLASSES)
    time_lapse_s = class_totals_s[SourceMediaClass.REAL_TIME_LAPSE.value]
    static_image_s = sum(class_totals_s[c] for c in STATIC_IMAGE_CLASSES)
    sci_viz_s = sum(class_totals_s[c] for c in SCIENTIFIC_VISUALIZATION_CLASSES)
    ai_gen_s = class_totals_s[SourceMediaClass.AI_GENERATED.value]
    reenact_s = class_totals_s[SourceMediaClass.REENACTMENT.value]

    return {
        "total_timeline_duration_s": round(total_dur, 3),
        # A. Genuine Moving Footage Ratio
        "genuine_moving_footage_s": round(genuine_moving_s, 3),
        "genuine_moving_footage_ratio": round(genuine_moving_s / denom, 4),
        "genuine_moving_footage_pct": round(100.0 * genuine_moving_s / denom, 2),
        # B. Meaningful Action Footage Ratio
        "meaningful_action_footage_s": round(meaningful_action_s, 3),
        "meaningful_action_footage_ratio": round(meaningful_action_s / denom, 4),
        "meaningful_action_footage_pct": round(100.0 * meaningful_action_s / denom, 2),
        # C. Establishing Footage Ratio
        "establishing_footage_s": round(establishing_s, 3),
        "establishing_footage_ratio": round(establishing_s / denom, 4),
        "establishing_footage_pct": round(100.0 * establishing_s / denom, 2),
        # Time-lapse (separately identified subset of genuine moving footage)
        "real_time_lapse_s": round(time_lapse_s, 3),
        "real_time_lapse_ratio": round(time_lapse_s / denom, 4),
        "real_time_lapse_pct": round(100.0 * time_lapse_s / denom, 2),
        # D. Static Image Ratio (STILL_PHOTO + ANIMATED_STILL + SCIENTIFIC_IMAGE)
        "static_image_s": round(static_image_s, 3),
        "static_image_ratio": round(static_image_s / denom, 4),
        "static_image_pct": round(100.0 * static_image_s / denom, 2),
        "animated_still_s": round(class_totals_s[SourceMediaClass.ANIMATED_STILL.value], 3),
        "animated_still_pct": round(100.0 * class_totals_s[SourceMediaClass.ANIMATED_STILL.value] / denom, 2),
        "pure_still_photo_s": round(class_totals_s[SourceMediaClass.STILL_PHOTO.value], 3),
        "scientific_image_s": round(class_totals_s[SourceMediaClass.SCIENTIFIC_IMAGE.value], 3),
        # E. Scientific Visualization Ratio (INFOGRAPHIC + REAL_ANIMATION)
        "scientific_visualization_s": round(sci_viz_s, 3),
        "scientific_visualization_ratio": round(sci_viz_s / denom, 4),
        "scientific_visualization_pct": round(100.0 * sci_viz_s / denom, 2),
        "infographic_s": round(class_totals_s[SourceMediaClass.INFOGRAPHIC.value], 3),
        "real_animation_s": round(class_totals_s[SourceMediaClass.REAL_ANIMATION.value], 3),
        # Non-documentary / staged disclosures
        "ai_generated_s": round(ai_gen_s, 3),
        "reenactment_s": round(reenact_s, 3),
        "by_media_class_s": {k: round(v, 3) for k, v in class_totals_s.items()},
        "by_media_class_pct": {k: round(100.0 * v / denom, 2) for k, v in class_totals_s.items()},
        "shot_classifications": shot_classifications,
    }
