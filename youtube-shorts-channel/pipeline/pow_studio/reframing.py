#!/usr/bin/env python3
"""
Intelligent Full-Screen Vertical Reframing Engine (`pow_studio.reframing`).

Implements reusable 9:16 (1080x1920) subject-aware cropping and trajectory tracking:
1. Estimates primary subject position via spatial edge-gradient + local chromatic saliency
   while respecting mobile subtitle safe zones.
2. Evaluates crop feasibility before rendering (never stretches aspect ratio, never invents
   pixels, and flags low-resolution or wide-axis-chart sources that cannot cleanly fill 9:16).
3. Computes smooth subpixel subject-tracking trajectories across horizontal moving video clips
   (either automatically from multi-frame saliency or via explicit director keyframes).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

import numpy as np
from PIL import Image


@dataclass
class CropFeasibilityResult:
    source_width: int
    source_height: int
    crop_width_px: float
    crop_height_px: float
    upscale_factor: float
    feasible: bool
    warnings: list[str]


def evaluate_crop_feasibility(
    source_width: int,
    source_height: int,
    target_w: int = 1080,
    target_h: int = 1920,
    max_zoom: float = 1.04,
    min_cropped_source_height_px: int = 540,
    max_upscale_warn: float = 2.35,
    contains_wide_axes_or_text: bool = False,
) -> CropFeasibilityResult:
    """
    Verify whether cropping `(source_width, source_height)` edge-to-edge into `(target_w, target_h)`
    preserves image fidelity and essential subject information without stretching.
    """
    warnings: list[str] = []
    if source_width <= 0 or source_height <= 0:
        return CropFeasibilityResult(source_width, source_height, 0.0, 0.0, 99.0, False, ["Invalid zero-size media"])

    target_aspect = target_w / float(target_h)
    src_aspect = source_width / float(source_height)
    zoom = max(1.0, float(max_zoom))

    if src_aspect > target_aspect:
        base_h = float(source_height)
        base_w = base_h * target_aspect
    else:
        base_w = float(source_width)
        base_h = base_w / target_aspect

    crop_w = base_w / zoom
    crop_h = base_h / zoom
    upscale = max(target_w / max(1.0, crop_w), target_h / max(1.0, crop_h))

    feasible = True
    if contains_wide_axes_or_text and src_aspect > 0.85:
        feasible = False
        warnings.append(
            f"Source ({source_width}x{source_height}) contains wide chart axes/text that would be destroyed by 9:16 full-bleed crop."
        )
    if crop_h < min_cropped_source_height_px:
        feasible = False
        warnings.append(
            f"Cropped vertical resolution ({crop_h:.0f}px) is below minimum quality threshold ({min_cropped_source_height_px}px)."
        )
    if upscale > max_upscale_warn:
        warnings.append(
            f"Effective upscale factor ({upscale:.2f}x) exceeds crisp HD target ({max_upscale_warn:.2f}x)."
        )
        if upscale > 3.1:
            feasible = False

    return CropFeasibilityResult(
        source_width=source_width,
        source_height=source_height,
        crop_width_px=round(crop_w, 1),
        crop_height_px=round(crop_h, 1),
        upscale_factor=round(upscale, 3),
        feasible=feasible,
        warnings=warnings,
    )


def estimate_salient_subject_center(
    img_rgb: Image.Image,
    keep_above_subtitle_ratio: float = 0.77,
) -> tuple[float, float]:
    """
    Estimate normalized `(cx, cy)` in `[0..1]` of the primary visual subject using
    local structural gradient + chromatic contrast saliency, gently regularized so
    the main subject stays clear of the bottom subtitle zone.
    """
    small_w = 192
    small_h = max(64, int(round(img_rgb.height * (small_w / float(max(1, img_rgb.width))))))
    arr = np.asarray(img_rgb.resize((small_w, small_h), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0

    luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    gx = np.abs(np.diff(luma, axis=1, prepend=luma[:, :1]))
    gy = np.abs(np.diff(luma, axis=0, prepend=luma[:1, :]))
    edge_energy = np.hypot(gx, gy)

    # Chromatic distinctness from scene median color (captures e.g. iron-red plume on white glacier,
    # turquoise brine rim in dark sea, brightly lit organism in dark field)
    med_rgb = np.median(arr.reshape(-1, 3), axis=0)
    chroma_dist = np.linalg.norm(arr - med_rgb[None, None, :], axis=2)

    yy, xx = np.mgrid[0:small_h, 0:small_w]
    nx = (xx + 0.5) / float(small_w)
    ny = (yy + 0.5) / float(small_h)

    # Soft center-vertical prior avoiding extreme frame borders and bottom caption strip
    prior = np.exp(-((nx - 0.50) ** 2) / (2 * 0.28**2)) * np.exp(-((ny - 0.46) ** 2) / (2 * 0.24**2))
    saliency = (0.52 * edge_energy + 0.48 * chroma_dist) * prior

    # Keep top 12% most salient cells to prevent broad sky/snow fields from diluting the centroid
    thresh = float(np.percentile(saliency, 88.0))
    mask = np.maximum(0.0, saliency - thresh)
    total = float(np.sum(mask))
    if total < 1e-6:
        return (0.50, 0.48)

    cx = float(np.sum(nx * mask) / total)
    cy = float(np.sum(ny * mask) / total)

    # Shift slightly upward if subject sits too close to bottom subtitle zone so cropping places
    # the subject comfortably in the upper-middle documentary viewport
    cy = min(cy, keep_above_subtitle_ratio)
    return (round(max(0.18, min(0.82, cx)), 4), round(max(0.22, min(0.76, cy)), 4))


def compute_video_reframe_trajectory(
    video_path: Path,
    src_in_s: float,
    duration_s: float,
    n_samples: int = 6,
) -> list[tuple[float, float, float]]:
    """
    Sample `n_samples` frames across `[src_in_s, src_in_s + duration_s]` of a moving video,
    combining spatial saliency with inter-frame motion energy to produce a smooth,
    jitter-free `(norm_u, cx, cy)` subject-tracking trajectory for 9:16 reframing.
    """
    n_samples = max(2, int(n_samples))
    times = [src_in_s + (k / float(n_samples - 1)) * max(0.2, duration_s - 0.05) for k in range(n_samples)]
    frames_arr: list[np.ndarray] = []
    centers: list[tuple[float, float]] = []

    small_w = 192
    for t in times:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, t):.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            import io

            im = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
            centers.append(estimate_salient_subject_center(im))
            sh = max(64, int(round(im.height * (small_w / float(max(1, im.width))))))
            frames_arr.append(np.asarray(im.resize((small_w, sh), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0)
        else:
            centers.append((0.50, 0.48))

    # Blend inter-frame motion centroid when genuine localized subject movement is present
    refined_cx = [c[0] for c in centers]
    refined_cy = [c[1] for c in centers]
    if len(frames_arr) == n_samples:
        for k in range(n_samples):
            k_other = min(n_samples - 1, k + 1) if k < n_samples - 1 else max(0, k - 1)
            diff = np.mean(np.abs(frames_arr[k] - frames_arr[k_other]), axis=2)
            p90 = float(np.percentile(diff, 90.0))
            if p90 > 0.025:
                wmask = np.maximum(0.0, diff - p90)
                wtot = float(np.sum(wmask))
                if wtot > 1e-5:
                    sh, sw = diff.shape
                    yy, xx = np.mgrid[0:sh, 0:sw]
                    mcx = float(np.sum(((xx + 0.5) / sw) * wmask) / wtot)
                    mcy = float(np.sum(((yy + 0.5) / sh) * wmask) / wtot)
                    refined_cx[k] = 0.65 * refined_cx[k] + 0.35 * mcx
                    refined_cy[k] = 0.70 * refined_cy[k] + 0.30 * mcy

    # Heavy temporal smoothing (3-tap binomial pass x2) so camera follows subject like a fluid head tripod,
    # never jerking on transient waves or particles
    cx_np = np.array(refined_cx, dtype=np.float64)
    cy_np = np.array(refined_cy, dtype=np.float64)
    for _ in range(2):
        if len(cx_np) >= 3:
            cx_pad = np.pad(cx_np, (1, 1), mode="edge")
            cy_pad = np.pad(cy_np, (1, 1), mode="edge")
            cx_np = 0.25 * cx_pad[:-2] + 0.50 * cx_pad[1:-1] + 0.25 * cx_pad[2:]
            cy_np = 0.25 * cy_pad[:-2] + 0.50 * cy_pad[1:-1] + 0.25 * cy_pad[2:]

    keyframes: list[tuple[float, float, float]] = []
    for k in range(n_samples):
        u = round(k / float(n_samples - 1), 4)
        keyframes.append(
            (
                u,
                round(float(np.clip(cx_np[k], 0.18, 0.82)), 4),
                round(float(np.clip(cy_np[k], 0.22, 0.74)), 4),
            )
        )
    return keyframes


def interpolate_reframe_keyframes(
    keyframes: Sequence[tuple[float, float, float]],
    u: float,
) -> tuple[float, float]:
    """
    Smoothly interpolate `(cx, cy)` at normalized shot progress `u` in `[0..1]`
    across `[(u_k, cx_k, cy_k), ...]` using C1-continuous Hermite/smoothstep blending.
    """
    if not keyframes:
        return (0.50, 0.50)
    pts = sorted(keyframes, key=lambda x: x[0])
    if u <= pts[0][0]:
        return (pts[0][1], pts[0][2])
    if u >= pts[-1][0]:
        return (pts[-1][1], pts[-1][2])

    for (u0, x0, y0), (u1, x1, y1) in zip(pts, pts[1:]):
        if u0 <= u <= u1:
            span = max(1e-6, u1 - u0)
            t = max(0.0, min(1.0, (u - u0) / span))
            s = t * t * (3.0 - 2.0 * t)
            return (x0 + s * (x1 - x0), y0 + s * (y1 - y0))
    return (pts[-1][1], pts[-1][2])


def crop_subpixel_full_canvas(
    img: Image.Image,
    cx: float,
    cy: float,
    zoom: float,
    out_w: int = 1080,
    out_h: int = 1920,
) -> Image.Image:
    """
    Subpixel-continuous aspect-preserving crop to `(out_w, out_h)` (`9:16` full bleed).
    Guaranteed never to stretch aspect ratio or fabricate out-of-frame pixels.
    """
    iw, ih = img.size
    target_aspect = out_w / float(out_h)
    src_aspect = iw / float(ih)
    z = max(1.0, float(zoom))

    if src_aspect > target_aspect:
        base_h = float(ih)
        base_w = base_h * target_aspect
    else:
        base_w = float(iw)
        base_h = base_w / target_aspect

    win_w = base_w / z
    win_h = base_h / z
    half_w = 0.5 * win_w
    half_h = 0.5 * win_h

    cx_px = max(half_w, min(iw - half_w, cx * iw))
    cy_px = max(half_h, min(ih - half_h, cy * ih))
    x0 = cx_px - half_w
    y0 = cy_px - half_h
    sx = win_w / float(out_w)
    sy = win_h / float(out_h)

    return img.transform(
        (out_w, out_h),
        Image.Transform.AFFINE,
        (sx, 0.0, x0, 0.0, sy, y0),
        resample=Image.Resampling.BICUBIC,
    )


def measure_post_crop_sharpness(img_rgb: Image.Image) -> float:
    """Compute discrete Laplacian standard deviation on luma to detect blurry over-zoomed compression."""
    arr = np.asarray(img_rgb.resize((540, 960), Image.Resampling.BILINEAR), dtype=np.float32)
    luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    lap = (
        4.0 * luma[1:-1, 1:-1]
        - luma[:-2, 1:-1]
        - luma[2:, 1:-1]
        - luma[1:-1, :-2]
        - luma[1:-1, 2:]
    )
    return round(float(np.std(lap)), 3)
