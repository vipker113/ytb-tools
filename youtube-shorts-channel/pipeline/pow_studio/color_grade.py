#!/usr/bin/env python3
"""
Reusable 35mm Documentary Color Science & Organic Luma Grain (`pow_studio.color_grade`).

Eliminates the "stitched digital stock / AI slideshow" look across heterogeneous archival
sources (satellite passes, cold-lab cameras, field camcorders, and high-res stills) by:
1. Gentle white-balance / color-cast taming (neutralizes harsh green/cyan/tungsten casts
   while preserving intentional subject colors like iron-oxide crimson and polar red parkas).
2. Filmic highlight roll-off & shadow toe LUT (tames harsh 255 digital snow clipping into
   creamy cinema highlights with rich documentary shadow density).
3. Subtle temporal monochromatic 35mm luminance grain (unifies mixed-resolution sources
   and breathes living optical texture into brief archival photographs without fake warping).
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _build_filmic_lut() -> np.ndarray:
    """Precompute 256-entry filmic S-curve with smooth snow-highlight shoulder roll-off."""
    x = np.linspace(0.0, 1.0, 256, dtype=np.float32)
    # Gentle S-curve centered at mid-grey
    s = x - 0.042 * np.sin(2.0 * np.pi * x)
    # Soft cinema toe (lift dead digital 0 -> ~6/255) and creamy highlight roll-off (cap harsh 255 -> 249)
    toe_shoulder = 0.022 + 0.954 * (s / (1.0 + 0.065 * (s**3))) * 1.062
    return np.clip(np.round(toe_shoulder * 255.0), 0, 255).astype(np.uint8)


_FILMIC_LUT = _build_filmic_lut()

# Pre-generated tileable 256x256 zero-mean Gaussian luma grain bank for ultra-fast per-frame indexing
_GRAIN_RNG = np.random.default_rng(20261029)
_GRAIN_TILE = _GRAIN_RNG.standard_normal((512, 512)).astype(np.float32)


def apply_documentary_color_grade(
    img: Image.Image,
    frame_idx: int = 0,
    enable_grade: bool = True,
    cast_tame_strength: float = 0.22,
    luma_grain_sigma: float = 2.4,
) -> Image.Image:
    """
    Apply unified documentary color curve, gentle cast neutralization, and subtle
    monochromatic temporal film grain to an RGB frame at ~3ms/frame overhead.
    """
    if not enable_grade and luma_grain_sigma <= 0.0:
        return img

    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)

    if enable_grade:
        # 1. Gentle gray-world midtone cast taming (ignores clipped highlights >235 & deep shadows <20)
        sub = arr[::8, ::8].astype(np.float32)
        lum = 0.299 * sub[:, :, 0] + 0.587 * sub[:, :, 1] + 0.114 * sub[:, :, 2]
        mask = (lum > 22.0) & (lum < 232.0)
        if np.count_nonzero(mask) > 64 and cast_tame_strength > 0.0:
            means = sub[mask].mean(axis=0)  # [R, G, B]
            avg_gray = float(means.mean())
            if avg_gray > 10.0:
                gains = avg_gray / np.maximum(means, 12.0)
                # Clamp correction tightly (+/- 7%) so crimson ice or red parkas stay vivid!
                gains = np.clip(1.0 + cast_tame_strength * (gains - 1.0), 0.93, 1.07)
                arr_f = arr.astype(np.float32) * gains[None, None, :]
                arr = np.clip(arr_f, 0.0, 255.0).astype(np.uint8)

        # 2. Filmic tone curve via fast LUT lookup
        arr = _FILMIC_LUT[arr]

    # 3. Monochromatic temporal luma grain (seeded deterministically per frame_idx)
    if luma_grain_sigma > 0.05:
        h, w, _ = arr.shape
        ox = (frame_idx * 73) % 256
        oy = (frame_idx * 137) % 256
        tile = _GRAIN_TILE[oy : oy + 256, ox : ox + 256]
        reps_y = (h + 255) // 256
        reps_x = (w + 255) // 256
        grain = np.tile(tile, (reps_y, reps_x))[:h, :w] * float(luma_grain_sigma)
        if (frame_idx & 1) == 1:
            grain = -grain[:, ::-1]
        out_i16 = arr.astype(np.int16) + np.round(grain).astype(np.int16)[:, :, None]
        arr = np.clip(out_i16, 0, 255).astype(np.uint8)

    return Image.fromarray(arr)
