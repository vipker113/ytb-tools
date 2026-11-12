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
_X256 = np.arange(256, dtype=np.float32)

# Pre-generated large int16 Gaussian luma grain bank for zero-allocation per-frame slicing
_GRAIN_RNG = np.random.default_rng(20261029)
_GRAIN_BASE_F32 = _GRAIN_RNG.standard_normal((2304, 1408)).astype(np.float32)
_GRAIN_CACHE_I16: dict[float, np.ndarray] = {}


def _get_grain_bank_i16(sigma: float) -> np.ndarray:
    key = round(float(sigma), 2)
    bank = _GRAIN_CACHE_I16.get(key)
    if bank is None:
        bank = np.round(_GRAIN_BASE_F32 * key).astype(np.int16)
        _GRAIN_CACHE_I16[key] = bank
    return bank


def apply_documentary_color_grade(
    img: Image.Image,
    frame_idx: int = 0,
    enable_grade: bool = True,
    cast_tame_strength: float = 0.22,
    luma_grain_sigma: float = 2.4,
) -> Image.Image:
    """
    Apply unified documentary color curve, gentle cast neutralization, and subtle
    monochromatic temporal film grain to an RGB frame at ~1.5ms/frame overhead.
    """
    if not enable_grade and luma_grain_sigma <= 0.0:
        return img

    rgb_im = img.convert("RGB") if img.mode != "RGB" else img

    if enable_grade:
        arr_view = np.asarray(rgb_im, dtype=np.uint8)
        sub = arr_view[::8, ::8].astype(np.float32)
        lum = 0.299 * sub[:, :, 0] + 0.587 * sub[:, :, 1] + 0.114 * sub[:, :, 2]
        mask = (lum > 22.0) & (lum < 232.0)
        if np.count_nonzero(mask) > 64 and cast_tame_strength > 0.0:
            means = sub[mask].mean(axis=0)
            avg_gray = float(means.mean())
            if avg_gray > 10.0:
                gains = avg_gray / np.maximum(means, 12.0)
                gains = np.clip(1.0 + cast_tame_strength * (gains - 1.0), 0.93, 1.07)
                lut_r = _FILMIC_LUT[np.clip(np.round(_X256 * gains[0]), 0, 255).astype(np.uint8)]
                lut_g = _FILMIC_LUT[np.clip(np.round(_X256 * gains[1]), 0, 255).astype(np.uint8)]
                lut_b = _FILMIC_LUT[np.clip(np.round(_X256 * gains[2]), 0, 255).astype(np.uint8)]
                lut_768 = np.concatenate((lut_r, lut_g, lut_b)).tolist()
            else:
                lut_768 = np.tile(_FILMIC_LUT, 3).tolist()
        else:
            lut_768 = np.tile(_FILMIC_LUT, 3).tolist()
        rgb_im = rgb_im.point(lut_768)

    if luma_grain_sigma > 0.05:
        arr = np.asarray(rgb_im, dtype=np.uint8)
        h, w, _ = arr.shape
        bank = _get_grain_bank_i16(luma_grain_sigma)
        bh, bw = bank.shape
        if h <= bh and w <= bw:
            ox = (frame_idx * 73) % max(1, bw - w)
            oy = (frame_idx * 137) % max(1, bh - h)
            grain = bank[oy : oy + h, ox : ox + w]
        else:
            reps_y = (h + bh - 1) // bh
            reps_x = (w + bw - 1) // bw
            grain = np.tile(bank, (reps_y, reps_x))[:h, :w]
        if (frame_idx & 1) == 1:
            out_i16 = arr.astype(np.int16) - grain[:, ::-1, None]
        else:
            out_i16 = arr.astype(np.int16) + grain[:, :, None]
        arr = np.clip(out_i16, 0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    return rgb_im
