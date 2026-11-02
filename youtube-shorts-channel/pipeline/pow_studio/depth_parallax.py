#!/usr/bin/env python3
"""
Step 3A: Monocular Depth-Anything-V2 2.5D Parallax Engine (`pow_studio.depth_parallax`).

Uses the open-source Apache-2.0 `onnx-community/depth-anything-v2-small` ONNX model
with Apple Silicon CoreML / CPU execution to infer dense relative depth maps on
4K–6K archival photographs, then performs Jacobian-safe, subpixel-continuous
vectorized bilinear 2.5D parallax warping with zero hallucinated pixels.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
MODEL_ONNX = ROOT / "assets" / "models" / "depth_anything_v2" / "onnx" / "model_fp16.onnx"
DEPTH_CACHE_DIR = ROOT / "assets" / "models" / "depth_cache"

_ORT_SESSION: Optional[ort.InferenceSession] = None


def _get_depth_session() -> ort.InferenceSession:
    global _ORT_SESSION
    if _ORT_SESSION is None:
        if not MODEL_ONNX.exists():
            import urllib.request

            MODEL_ONNX.parent.mkdir(parents=True, exist_ok=True)
            hf_url = "https://huggingface.co/onnx-community/depth-anything-v2-small/resolve/main/onnx/model_fp16.onnx"
            urllib.request.urlretrieve(hf_url, str(MODEL_ONNX))
        so = ort.SessionOptions()
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
        providers = [p for p in ("CoreMLExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        _ORT_SESSION = ort.InferenceSession(str(MODEL_ONNX), sess_options=so, providers=providers or ["CPUExecutionProvider"])
    return _ORT_SESSION


def infer_smoothed_depth(img_rgb: Image.Image, cache_key: str) -> Image.Image:
    """
    Return a smoothed grayscale depth PIL.Image ('L', 0=far background, 255=near foreground)
    matching `img_rgb.size`, cached on disk by `cache_key`.
    """
    DEPTH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(f"{cache_key}:{img_rgb.size[0]}x{img_rgb.size[1]}".encode()).hexdigest()[:16]
    cache_png = DEPTH_CACHE_DIR / f"depth_{digest}.png"
    if cache_png.exists():
        return Image.open(cache_png).convert("L")

    sess = _get_depth_session()
    in_size = 518
    resized = img_rgb.resize((in_size, in_size), Image.Resampling.BICUBIC)
    arr = np.asarray(resized, dtype=np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    norm = ((arr - mean) / std).transpose(2, 0, 1)[None, ...]  # (1, 3, 518, 518)

    inp_name = sess.get_inputs()[0].name
    pred = sess.run(None, {inp_name: norm})[0][0].astype(np.float32)  # (518, 518)

    p_lo, p_hi = float(np.percentile(pred, 2.0)), float(np.percentile(pred, 98.0))
    depth01 = np.clip((pred - p_lo) / max(1e-5, p_hi - p_lo), 0.0, 1.0)
    depth_u8 = (depth01 * 255.0).astype(np.uint8)

    # Upsample to full source resolution and apply Jacobian-safe Gaussian smoothing so
    # depth discontinuities glide smoothly without tearing real photographic edges.
    iw, ih = img_rgb.size
    blur_r = max(8.0, min(iw, ih) * 0.012)
    depth_full = Image.fromarray(depth_u8).resize((iw, ih), Image.Resampling.BICUBIC).filter(
        ImageFilter.GaussianBlur(radius=blur_r)
    )
    depth_full.save(cache_png, format="PNG")
    return depth_full


def render_25d_parallax_frame(
    img_rgb: Image.Image,
    depth_l: Image.Image,
    cx: float,
    cy: float,
    zoom: float,
    u_progress: float,
    parallax_px: float,
    out_w: int,
    out_h: int,
) -> Image.Image:
    """
    Subpixel-continuous affine crop + 2.5D depth-map parallax warp.
    `u_progress` in [0, 1]: shifts foreground vs. background smoothly from -0.5 to +0.5
    of `parallax_px` along the camera motion vector while preserving 100% authentic pixels.
    """
    # Render a slightly padded overscan canvas (+72px margin) so edge shifts never clip
    pad = int(max(36, abs(parallax_px) * 1.6))
    pw, ph = out_w + 2 * pad, out_h + 2 * pad

    iw, ih = img_rgb.size
    target_aspect = pw / float(ph)
    src_aspect = iw / float(ih)
    if src_aspect >= target_aspect:
        base_h = float(ih)
        base_w = base_h * target_aspect
    else:
        base_w = float(iw)
        base_h = base_w / target_aspect

    win_w = base_w / zoom
    win_h = base_h / zoom
    half_w, half_h = win_w * 0.5, win_h * 0.5
    cx_px = max(half_w, min(iw - half_w, cx * iw))
    cy_px = max(half_h, min(ih - half_h, cy * ih))
    x0, y0 = cx_px - half_w, cy_px - half_h
    sx, sy = win_w / float(pw), win_h / float(ph)

    aff = (sx, 0.0, x0, 0.0, sy, y0)
    rgb_pad = np.asarray(
        img_rgb.transform((pw, ph), Image.Transform.AFFINE, aff, resample=Image.Resampling.BICUBIC),
        dtype=np.float32,
    )
    dep_pad = (
        np.asarray(
            depth_l.transform((pw, ph), Image.Transform.AFFINE, aff, resample=Image.Resampling.BILINEAR),
            dtype=np.float32,
        )
        / 255.0
    )

    # Centered disparity [-0.5, +0.5]: foreground moves faster than background as camera glides
    phase = u_progress - 0.5  # [-0.5 .. +0.5]
    disp = dep_pad[pad : pad + out_h, pad : pad + out_w] - 0.45
    dx = (-phase * parallax_px) * disp
    dy = (-phase * parallax_px * 0.32) * disp

    yy, xx = np.mgrid[pad : pad + out_h, pad : pad + out_w].astype(np.float32)
    xs = np.clip(xx + dx, 0.0, pw - 1.001)
    ys = np.clip(yy + dy, 0.0, ph - 1.001)

    ix0 = np.floor(xs).astype(np.int32)
    iy0 = np.floor(ys).astype(np.int32)
    ix1 = ix0 + 1
    iy1 = iy0 + 1
    wx = (xs - ix0)[..., None]
    wy = (ys - iy0)[..., None]

    c00 = rgb_pad[iy0, ix0]
    c10 = rgb_pad[iy0, ix1]
    c01 = rgb_pad[iy1, ix0]
    c11 = rgb_pad[iy1, ix1]

    warped = (1.0 - wy) * ((1.0 - wx) * c00 + wx * c10) + wy * ((1.0 - wx) * c01 + wx * c11)
    return Image.fromarray(np.clip(warped, 0.0, 255.0).astype(np.uint8))
