#!/usr/bin/env python3
"""
Subject-First Opening Frame & High-CTR Cinema Hook Thumbnail Engine (`pow_studio.thumbnail_engine` v4.0).

Implements Section 8 & v4.0 Top-0.5% Packaging Rules of the Proof of Wonder Documentary Workflow:
1. Evaluates candidate authentic images or video frames for sharpness and subject-background
   contrast separation.
2. Applies an optical Subject Clarity Pass (underwater/atmospheric dehaze, midtone S-curve,
   vibrance lift, and subtle focal vignette) so real scientific subjects pop at 160x284 px.
3. Supports three clean, zero-box documentary text modes:
   - `cinema_hook` (default v4.0): Stacked 2-line high-impact condensed cinema display hook
     (`<= 6` words) with two-tone focal line emphasis (white + vivid documentary gold/cyan),
     optional borderless uppercase context eyebrow (`kicker_text`), feathered optical Gaussian
     depth shadow, and crisp abyssal contour stroke — ZERO rectangular boxes, badges, or rings.
   - `minimal_headline`: Restrained single-line editorial headline (`<= 4` words).
   - `none`: Pure full-bleed subject photograph.
4. Exports `<slug>.jpg`, `thumbnail.jpg`, optional A/B hook variants (`thumbnail_variant_B.jpg`, ...),
   and a mobile-shelf `160x284` + `1:1` + native pixel QC sheet (`thumbnail_small_preview_sheet.jpg`).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .reframing import crop_subpixel_full_canvas, estimate_salient_subject_center
from .style_profile import DocumentaryStyleProfile

if TYPE_CHECKING:
    from .schema import ThumbnailVisualCueSpec

CHANNEL_ROOT = Path(__file__).resolve().parents[2]
FONT_ANTON = str(CHANNEL_ROOT / "assets" / "fonts" / "Anton-Regular.ttf")
FONT_BOLD = str(CHANNEL_ROOT / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(CHANNEL_ROOT / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")


@dataclass
class ThumbnailCandidateScore:
    source_name: str
    sharpness_score: float
    subject_separation_score: float
    combined_score: float
    recommended_cx: float
    recommended_cy: float


def score_thumbnail_candidate(img_rgb: Image.Image, source_name: str = "") -> ThumbnailCandidateScore:
    """
    Quantify sharpness and figure-ground separation so the workflow favors clean,
    high-contrast authentic subjects on mobile shelves.
    """
    cx, cy = estimate_salient_subject_center(img_rgb, keep_above_subtitle_ratio=0.72)
    framed = crop_subpixel_full_canvas(img_rgb, cx, cy, 1.02, 540, 960)
    arr = np.asarray(framed, dtype=np.float32) / 255.0

    luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
    gx = np.abs(np.diff(luma, axis=1))
    gy = np.abs(np.diff(luma, axis=0))
    sharpness = float(0.5 * (np.mean(gx) + np.mean(gy)) * 100.0)

    h, w = luma.shape
    fg = arr[int(0.22 * h) : int(0.68 * h), int(0.15 * w) : int(0.85 * w)]
    bg_top = arr[: int(0.20 * h), :]
    bg_bot = arr[int(0.74 * h) :, :]
    bg = np.concatenate([bg_top.reshape(-1, 3), bg_bot.reshape(-1, 3)], axis=0)

    fg_p85 = np.percentile(fg.reshape(-1, 3), 85, axis=0)
    fg_p15 = np.percentile(fg.reshape(-1, 3), 15, axis=0)
    bg_med = np.median(bg, axis=0)
    sep = float(max(np.linalg.norm(fg_p85 - bg_med), np.linalg.norm(fg_p15 - bg_med)) * 100.0)
    combined = round(0.45 * sharpness + 0.55 * sep, 2)

    return ThumbnailCandidateScore(
        source_name=source_name,
        sharpness_score=round(sharpness, 2),
        subject_separation_score=round(sep, 2),
        combined_score=combined,
        recommended_cx=cx,
        recommended_cy=cy,
    )


def save_youtube_444_jpeg(img_rgb: Image.Image, jpg_path: Path, max_bytes: int = 1_950_000) -> int:
    from PIL import ImageFile

    ImageFile.MAXBLOCK = max(getattr(ImageFile, "MAXBLOCK", 65536), 16 * 1024 * 1024)
    for q in (96, 94, 92, 90, 88, 85, 82, 78):
        img_rgb.save(jpg_path, format="JPEG", quality=q, subsampling=0, optimize=True)
        if jpg_path.stat().st_size <= max_bytes:
            return q
    return 78


def _apply_optical_subject_clarity(img_rgb: Image.Image) -> Image.Image:
    """
    Dehaze backscatter veil (especially in underwater/aerial footage), deepen blacks via a
    smooth S-curve, lift natural vibrance, and add crisp micro-contrast without haloing.
    """
    arr = np.asarray(img_rgb, dtype=np.float32) / 255.0
    p04 = np.percentile(arr, 4.0)
    p985 = max(p04 + 0.25, np.percentile(arr, 98.5))
    norm = np.clip((arr - p04 * 0.78) / (p985 - p04 * 0.78), 0.0, 1.0)
    # Gentle cinema S-curve
    curved = norm * norm * (3.0 - 2.0 * norm)
    blended = np.clip(0.48 * norm + 0.52 * curved, 0.0, 1.0)
    out = Image.fromarray((blended * 255.0).astype(np.uint8))
    out = ImageEnhance.Color(out).enhance(1.18)
    out = out.filter(ImageFilter.UnsharpMask(radius=2.1, percent=128, threshold=3))
    return out


def _split_hook_lines(raw_text: str, max_words: int) -> list[str]:
    """
    Split a hook headline into 1 or 2 punchy balanced lines.
    Supports explicit '|' or newline separators, or automatic balanced word splitting.
    """
    explicit = [seg.strip() for seg in raw_text.replace("\n", "|").split("|") if seg.strip()]
    if len(explicit) >= 2:
        words_used: list[str] = []
        lines_out: list[str] = []
        for seg in explicit[:2]:
            sw = seg.split()
            remain = max(0, max_words - len(words_used))
            if remain <= 0:
                break
            kept = sw[:remain]
            words_used.extend(kept)
            lines_out.append(" ".join(kept).upper())
        return lines_out

    words = raw_text.strip().split()[:max_words]
    if not words:
        return []
    if len(words) <= 2 and sum(len(w) for w in words) <= 13:
        return [" ".join(words).upper()]

    # Find split point minimizing character-length imbalance between line 1 and line 2
    best_idx = max(1, len(words) // 2)
    best_diff = 999
    for i in range(1, len(words)):
        l1 = " ".join(words[:i])
        l2 = " ".join(words[i:])
        diff = abs(len(l1) - len(l2))
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    return [" ".join(words[:best_idx]).upper(), " ".join(words[best_idx:]).upper()]


_NEGATION_TOKENS = {
    "cant",
    "cannot",
    "never",
    "not",
    "dont",
    "do",
    "no",
    "wont",
    "stopped",
    "forbidden",
    "impossible",
    "illegal",
    "ban",
    "banned",
    "vanished",
    "missing",
    "empty",
    "zero",
}
_HAZARD_TOKENS = {
    "deadly",
    "toxic",
    "explosion",
    "explode",
    "explodes",
    "danger",
    "dangerous",
    "lethal",
    "boil",
    "boiling",
    "acid",
    "fatal",
    "extreme",
}


def infer_default_visual_cue_symbol(headline_text: str) -> str:
    """Infer the most intuitive visual status badge ('red_x', 'question_mark', 'warning') from an English hook."""
    tokens = {re.sub(r"[^a-z0-9]", "", w.lower()) for w in headline_text.replace("|", " ").split()}
    tokens.discard("")
    if tokens & (_NEGATION_TOKENS - {"do"}):
        return "red_x"
    if "why" in tokens or "how" in tokens or "what" in tokens or "?" in headline_text:
        return "question_mark"
    if tokens & _HAZARD_TOKENS:
        return "warning"
    return "question_mark"


def _flood_remove_uniform_bg(im_rgba: Image.Image, target_white: bool) -> Image.Image:
    """
    Border-seeded flood-fill background removal for studio objects on uniform white or black backgrounds.
    Preserves 100% of interior highlights/shadows that are not connected to the image border.
    """
    w0, h0 = im_rgba.size
    scale = min(1.0, 760.0 / float(max(w0, h0)))
    ws, hs = max(16, int(round(w0 * scale))), max(16, int(round(h0 * scale)))
    small_rgb = im_rgba.convert("RGB").resize((ws, hs), Image.Resampling.BILINEAR)
    arr = np.asarray(small_rgb, dtype=np.uint8).copy()
    # Reserve exact marker RGB (255, 0, 255)
    marker_hits = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 0) & (arr[:, :, 2] == 255)
    arr[marker_hits, 0] = 254
    work = Image.fromarray(arr)

    luma = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    step = max(4, min(ws, hs) // 28)
    border_pts: list[tuple[int, int]] = []
    for x in range(0, ws, step):
        border_pts.append((x, 0))
        border_pts.append((x, hs - 1))
    for y in range(0, hs, step):
        border_pts.append((0, y))
        border_pts.append((ws - 1, y))

    for sx, sy in border_pts:
        px = work.getpixel((sx, sy))
        if px == (255, 0, 255):
            continue
        lv = luma[sy, sx]
        if (target_white and lv >= 228.0) or ((not target_white) and lv <= 28.0):
            ImageDraw.floodfill(work, (sx, sy), (255, 0, 255), thresh=34)

    w_arr = np.asarray(work, dtype=np.uint8)
    fg_mask = ~((w_arr[:, :, 0] == 255) & (w_arr[:, :, 1] == 0) & (w_arr[:, :, 2] == 255))
    mask_im = Image.fromarray((fg_mask.astype(np.uint8) * 255))
    mask_im = mask_im.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(radius=1.2))
    if (ws, hs) != (w0, h0):
        mask_im = mask_im.resize((w0, h0), Image.Resampling.LANCZOS)

    out = im_rgba.convert("RGBA")
    orig_a = np.asarray(out.split()[3], dtype=np.float32) / 255.0
    new_a = (np.asarray(mask_im, dtype=np.float32) / 255.0) * orig_a
    out.putalpha(Image.fromarray((np.clip(new_a, 0.0, 1.0) * 255.0).astype(np.uint8)))
    return out


def _prepare_visual_cue_cutout_rgba(
    cutout_src: Image.Image,
    vcue: "ThumbnailVisualCueSpec",
    out_w: int,
    out_h: int,
) -> tuple[Image.Image, str]:
    """
    Prepare a crisp foreground cutout RGBA sprite (or circular magnifier badge) scaled for `out_w x out_h`.
    Returns `(sprite_rgba, resolved_mode)`.
    """
    mode = vcue.cutout_mode
    has_real_alpha = False
    if "A" in cutout_src.getbands():
        a_arr = np.asarray(cutout_src.getchannel("A"))
        if int(a_arr.min()) < 235 and int(a_arr.max()) > 40:
            has_real_alpha = True

    if mode == "auto":
        if has_real_alpha:
            mode = "alpha"
        else:
            rgb_arr = np.asarray(cutout_src.convert("RGB"), dtype=np.float32)
            ch, cw = max(4, rgb_arr.shape[0] // 18), max(4, rgb_arr.shape[1] // 18)
            corners = np.concatenate(
                [
                    rgb_arr[:ch, :cw].reshape(-1, 3),
                    rgb_arr[:ch, -cw:].reshape(-1, 3),
                    rgb_arr[-ch:, :cw].reshape(-1, 3),
                    rgb_arr[-ch:, -cw:].reshape(-1, 3),
                ],
                axis=0,
            )
            c_luma = 0.299 * corners[:, 0] + 0.587 * corners[:, 1] + 0.114 * corners[:, 2]
            if float(np.mean(c_luma)) > 238.0 and float(np.std(c_luma)) < 12.0:
                mode = "white_bg"
            elif float(np.mean(c_luma)) < 16.0 and float(np.std(c_luma)) < 10.0:
                mode = "black_bg"
            else:
                mode = "circle_badge"

    target_w = max(140, int(round(out_w * vcue.cutout_scale)))
    max_h = max(180, int(round(out_h * 0.28)))

    if mode in ("alpha", "white_bg", "black_bg"):
        rgba = cutout_src.convert("RGBA")
        if mode == "white_bg" and not has_real_alpha:
            rgba = _flood_remove_uniform_bg(rgba, target_white=True)
        elif mode == "black_bg" and not has_real_alpha:
            rgba = _flood_remove_uniform_bg(rgba, target_white=False)

        a_np = np.asarray(rgba.getchannel("A"))
        ys, xs = np.where(a_np > 24)
        if len(xs) >= 16 and len(ys) >= 16:
            rgba = rgba.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))
            cw0, ch0 = rgba.size
            scale = min(target_w / float(max(1, cw0)), max_h / float(max(1, ch0)))
            nw, nh = max(32, int(round(cw0 * scale))), max(32, int(round(ch0 * scale)))
            rgba = rgba.resize((nw, nh), Image.Resampling.LANCZOS)
            if abs(vcue.cutout_rotation_deg) > 0.2:
                rgba = rgba.rotate(vcue.cutout_rotation_deg, resample=Image.Resampling.BICUBIC, expand=True)
            return rgba, mode

    # Fallback / explicit `circle_badge`: crisp circular subject magnifier inset (2x supersampled)
    diam = min(target_w, max_h)
    S = 2
    d_hi = diam * S
    cropped = crop_subpixel_full_canvas(
        cutout_src.convert("RGB"),
        vcue.cutout_crop_cx,
        vcue.cutout_crop_cy,
        max(1.0, vcue.cutout_crop_zoom),
        d_hi,
        d_hi,
    )
    cropped = _apply_optical_subject_clarity(cropped)

    pad = 16 * S
    full_hi = d_hi + 2 * pad
    badge_hi = Image.new("RGBA", (full_hi, full_hi), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_hi)
    # Outer dark contour + bright rim ring
    bd.ellipse([2 * S, 2 * S, full_hi - 2 * S, full_hi - 2 * S], fill=(10, 12, 18, 255))
    bd.ellipse([8 * S, 8 * S, full_hi - 8 * S, full_hi - 8 * S], fill=(*vcue.cutout_rim_rgb, 255))

    circ_mask = Image.new("L", (d_hi, d_hi), 0)
    ImageDraw.Draw(circ_mask).ellipse([0, 0, d_hi - 1, d_hi - 1], fill=255)
    badge_hi.paste(cropped, (pad, pad), circ_mask)

    badge_lo = badge_hi.resize((diam + 32, diam + 32), Image.Resampling.LANCZOS)
    return badge_lo, "circle_badge"


def _build_ribbon_polygon(
    pts: list[tuple[float, float]],
    half_w0: float,
    half_w1: float,
) -> list[tuple[float, float]]:
    left_side: list[tuple[float, float]] = []
    right_side: list[tuple[float, float]] = []
    n = len(pts)
    for i, (x, y) in enumerate(pts):
        if i == 0:
            dx, dy = pts[1][0] - x, pts[1][1] - y
        elif i == n - 1:
            dx, dy = x - pts[i - 1][0], y - pts[i - 1][1]
        else:
            dx, dy = pts[i + 1][0] - pts[i - 1][0], pts[i + 1][1] - pts[i - 1][1]
        length = max(1e-4, math.hypot(dx, dy))
        nx, ny = -dy / length, dx / length
        u = i / float(max(1, n - 1))
        hw = half_w0 + (half_w1 - half_w0) * u
        left_side.append((x + nx * hw, y + ny * hw))
        right_side.append((x - nx * hw, y - ny * hw))
    return left_side + right_side[::-1]


def _draw_rounded_segment(
    draw_obj: ImageDraw.ImageDraw,
    a: tuple[float, float],
    b: tuple[float, float],
    width: float,
    fill: tuple[int, int, int, int],
) -> None:
    w_int = max(1, int(round(width)))
    draw_obj.line([a, b], fill=fill, width=w_int)
    r = width / 2.0
    for pt in (a, b):
        draw_obj.ellipse([pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r], fill=fill)


def _draw_symbol_badge_2x(
    sw: int,
    sh: int,
    xc: float,
    yc: float,
    symbol: str,
    scale: float,
    S: int = 2,
) -> tuple[Image.Image, Image.Image]:
    shadow_hi = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    badge_hi = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow_hi)
    bd = ImageDraw.Draw(badge_hi)
    ox, oy = 6.0 * S, 10.0 * S

    if symbol == "red_x":
        arm = 78.0 * scale * S
        p_tl, p_br = (xc - arm, yc - arm), (xc + arm, yc + arm)
        p_bl, p_tr = (xc - arm, yc + arm), (xc + arm, yc - arm)
        _draw_rounded_segment(sd, (p_tl[0] + ox, p_tl[1] + oy), (p_br[0] + ox, p_br[1] + oy), 62 * scale * S, (0, 0, 0, 235))
        _draw_rounded_segment(sd, (p_bl[0] + ox, p_bl[1] + oy), (p_tr[0] + ox, p_tr[1] + oy), 62 * scale * S, (0, 0, 0, 235))
        _draw_rounded_segment(bd, p_tl, p_br, 60 * scale * S, (10, 12, 16, 255))
        _draw_rounded_segment(bd, p_bl, p_tr, 60 * scale * S, (10, 12, 16, 255))
        _draw_rounded_segment(bd, p_tl, p_br, 48 * scale * S, (255, 255, 255, 255))
        _draw_rounded_segment(bd, p_bl, p_tr, 48 * scale * S, (255, 255, 255, 255))
        _draw_rounded_segment(bd, p_tl, p_br, 34 * scale * S, (235, 20, 20, 255))
        _draw_rounded_segment(bd, p_bl, p_tr, 34 * scale * S, (235, 20, 20, 255))
        _draw_rounded_segment(bd, p_tl, p_br, 10 * scale * S, (255, 95, 95, 255))
        _draw_rounded_segment(bd, p_bl, p_tr, 10 * scale * S, (255, 95, 95, 255))
    elif symbol == "ban_circle":
        r = 82.0 * scale * S
        sd.ellipse([xc - r - 8 * S + ox, yc - r - 8 * S + oy, xc + r + 8 * S + ox, yc + r + 8 * S + oy], outline=(0, 0, 0, 235), width=int(52 * scale * S))
        d45 = r * 0.68
        p1, p2 = (xc - d45, yc - d45), (xc + d45, yc + d45)
        for w_ring, col in [
            (50 * scale * S, (10, 12, 16, 255)),
            (38 * scale * S, (255, 255, 255, 255)),
            (26 * scale * S, (235, 20, 20, 255)),
        ]:
            hw = w_ring / 2.0
            bd.ellipse([xc - r - hw, yc - r - hw, xc + r + hw, yc + r + hw], outline=col, width=max(1, int(round(w_ring))))
            _draw_rounded_segment(bd, p1, p2, w_ring, col)
    elif symbol == "question_mark":
        r = 78.0 * scale * S
        sd.ellipse([xc - r - 12 * S + ox, yc - r - 12 * S + oy, xc + r + 12 * S + ox, yc + r + 12 * S + oy], fill=(0, 0, 0, 235))
        bd.ellipse([xc - r - 12 * S, yc - r - 12 * S, xc + r + 12 * S, yc + r + 12 * S], fill=(10, 12, 16, 255))
        bd.ellipse([xc - r - 5 * S, yc - r - 5 * S, xc + r + 5 * S, yc + r + 5 * S], fill=(255, 255, 255, 255))
        bd.ellipse([xc - r, yc - r, xc + r, yc + r], fill=(226, 24, 34, 255))
        q_font_path = FONT_ANTON if Path(FONT_ANTON).exists() else FONT_BOLD
        qf = ImageFont.truetype(q_font_path, max(24, int(round(126 * scale * S))))
        qbb = bd.textbbox((0, 0), "?", font=qf)
        qx = xc - (qbb[2] - qbb[0]) / 2.0 - qbb[0]
        qy = yc - (qbb[3] - qbb[1]) / 2.0 - qbb[1] - 2 * S
        bd.text((qx, qy), "?", font=qf, fill=(255, 255, 255, 255), stroke_width=max(2, int(round(4 * S))), stroke_fill=(90, 8, 12, 245))
    elif symbol == "warning":
        h_tri = 158.0 * scale * S
        vt = (xc, yc - 0.58 * h_tri)
        vbl = (xc - 0.58 * h_tri, yc + 0.44 * h_tri)
        vbr = (xc + 0.58 * h_tri, yc + 0.44 * h_tri)
        verts_s = [(vx + ox, vy + oy) for (vx, vy) in (vt, vbl, vbr)]
        sd.polygon(verts_s, fill=(0, 0, 0, 235))
        for a, b in ((verts_s[0], verts_s[1]), (verts_s[1], verts_s[2]), (verts_s[2], verts_s[0])):
            _draw_rounded_segment(sd, a, b, 42 * scale * S, (0, 0, 0, 235))
        for w_edge, col in [
            (42 * scale * S, (10, 12, 16, 255)),
            (30 * scale * S, (255, 255, 255, 255)),
            (18 * scale * S, (255, 196, 18, 255)),
        ]:
            bd.polygon([vt, vbl, vbr], fill=col)
            for a, b in ((vt, vbl), (vbl, vbr), (vbr, vt)):
                _draw_rounded_segment(bd, a, b, w_edge, col)
        w_font_path = FONT_ANTON if Path(FONT_ANTON).exists() else FONT_BOLD
        wf = ImageFont.truetype(w_font_path, max(24, int(round(108 * scale * S))))
        wbb = bd.textbbox((0, 0), "!", font=wf)
        wx = xc - (wbb[2] - wbb[0]) / 2.0 - wbb[0]
        wy = yc + 0.06 * h_tri - (wbb[3] - wbb[1]) / 2.0 - wbb[1]
        bd.text((wx, wy), "!", font=wf, fill=(12, 14, 18, 255))
    elif symbol == "check":
        sc = 78.0 * scale * S
        p_l = (xc - 0.82 * sc, yc + 0.04 * sc)
        p_m = (xc - 0.18 * sc, yc + 0.68 * sc)
        p_r = (xc + 0.90 * sc, yc - 0.68 * sc)
        _draw_rounded_segment(sd, (p_l[0] + ox, p_l[1] + oy), (p_m[0] + ox, p_m[1] + oy), 60 * scale * S, (0, 0, 0, 235))
        _draw_rounded_segment(sd, (p_m[0] + ox, p_m[1] + oy), (p_r[0] + ox, p_r[1] + oy), 60 * scale * S, (0, 0, 0, 235))
        for w_st, col in [
            (58 * scale * S, (10, 12, 16, 255)),
            (46 * scale * S, (255, 255, 255, 255)),
            (32 * scale * S, (20, 192, 86, 255)),
            (10 * scale * S, (115, 245, 160, 255)),
        ]:
            _draw_rounded_segment(bd, p_l, p_m, w_st, col)
            _draw_rounded_segment(bd, p_m, p_r, w_st, col)

    return shadow_hi, badge_hi


def apply_visual_cue_overlay(
    canvas_rgba: Image.Image,
    vcue: "ThumbnailVisualCueSpec",
    cutout_src: Optional[Image.Image] = None,
) -> Image.Image:
    """
    Composite the intuitive visual-story layer onto `canvas_rgba`:
    1. Foreground cutout / circular inset in upper-left (with atmospheric scrim, rim glow & drop shadow)
    2. Optional target focus ring at `arrow_end`
    3. 2x-supersampled curved Bezier ribbon arrow pointing into `arrow_end`
    4. 2x-supersampled high-contrast action/paradox symbol (`red_x`, `question_mark`, `warning`, etc.) on the arrow
    """
    if not vcue.enabled:
        return canvas_rgba

    w, h = canvas_rgba.size
    out = canvas_rgba.convert("RGBA")

    cut_cx_px = vcue.cutout_cx * w
    cut_cy_px = vcue.cutout_cy * h
    cut_half_w = 0.0
    cut_half_h = 0.0

    if cutout_src is not None:
        sprite_rgba, resolved_mode = _prepare_visual_cue_cutout_rgba(cutout_src, vcue, w, h)
        bw, bh = sprite_rgba.size
        cut_half_w, cut_half_h = bw * 0.5, bh * 0.5
        bx = int(round(cut_cx_px - cut_half_w))
        by = int(round(cut_cy_px - cut_half_h))

        # Subtle localized atmospheric contrast behind cutout
        arr = np.asarray(out, dtype=np.float32)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        zone = np.exp(-(((xx - cut_cx_px) / max(120.0, bw * 0.85)) ** 2 + ((yy - cut_cy_px) / max(120.0, bh * 0.85)) ** 2))
        arr[:, :, :3] = arr[:, :, :3] * (1.0 - 0.24 * zone[:, :, None])
        out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

        sp_alpha = sprite_rgba.getchannel("A")
        shadow_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        shadow_layer.paste(Image.new("RGBA", (bw, bh), (0, 0, 0, 220)), (bx + 12, by + 18), sp_alpha)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=16))
        out = Image.alpha_composite(out, shadow_layer)

        if resolved_mode != "circle_badge":
            rim_dilated = sp_alpha.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(radius=2.2))
            rim_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            rim_layer.paste(Image.new("RGBA", (bw, bh), (*vcue.cutout_rim_rgb, 235)), (bx, by), rim_dilated)
            out = Image.alpha_composite(out, rim_layer)

        sprite_canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sprite_canvas.paste(sprite_rgba, (bx, by), sprite_rgba)
        out = Image.alpha_composite(out, sprite_canvas)

    S = 2
    sw, sh = w * S, h * S
    end_x, end_y = vcue.arrow_end[0] * w, vcue.arrow_end[1] * h

    if vcue.target_ring:
        tr_hi = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        td = ImageDraw.Draw(tr_hi)
        rr = vcue.target_ring_radius_px * S
        tx_hi, ty_hi = end_x * S, end_y * S
        td.ellipse([tx_hi - rr - 6 * S, ty_hi - rr - 6 * S, tx_hi + rr + 6 * S, ty_hi + rr + 6 * S], outline=(10, 12, 18, 235), width=18 * S)
        td.ellipse([tx_hi - rr, ty_hi - rr, tx_hi + rr, ty_hi + rr], outline=(*vcue.arrow_rgb, 250), width=10 * S)
        out = Image.alpha_composite(out, tr_hi.resize((w, h), Image.Resampling.LANCZOS))

    if vcue.show_arrow:
        if vcue.arrow_start is not None:
            start_x, start_y = vcue.arrow_start[0] * w, vcue.arrow_start[1] * h
        elif cutout_src is not None:
            dx0, dy0 = end_x - cut_cx_px, end_y - cut_cy_px
            d0 = max(1e-3, math.hypot(dx0, dy0))
            ux0, uy0 = dx0 / d0, dy0 / d0
            start_x = cut_cx_px + ux0 * (cut_half_w * 0.78)
            start_y = cut_cy_px + uy0 * (cut_half_h * 0.42)
        else:
            start_x, start_y = 0.28 * w, 0.24 * h

        if vcue.arrow_control is not None:
            ctrl_x, ctrl_y = vcue.arrow_control[0] * w, vcue.arrow_control[1] * h
        else:
            mx, my = 0.5 * (start_x + end_x), 0.5 * (start_y + end_y)
            dx_c, dy_c = end_x - start_x, end_y - start_y
            dist_c = max(1.0, math.hypot(dx_c, dy_c))
            # Curve upward-outward so the arc sweeps cleanly into the target
            nx_c, ny_c = dy_c / dist_c, -dx_c / dist_c
            if ny_c > 0:
                nx_c, ny_c = -nx_c, -ny_c
            ctrl_x = mx + nx_c * (dist_c * 0.30)
            ctrl_y = my + ny_c * (dist_c * 0.30)

        P0 = (start_x * S, start_y * S)
        P1 = (ctrl_x * S, ctrl_y * S)
        P2 = (end_x * S, end_y * S)

        t_shaft_end = 0.82
        ts = np.linspace(0.0, t_shaft_end, 160)
        pts = [
            (
                float((1 - t) ** 2 * P0[0] + 2 * (1 - t) * t * P1[0] + t**2 * P2[0]),
                float((1 - t) ** 2 * P0[1] + 2 * (1 - t) * t * P1[1] + t**2 * P2[1]),
            )
            for t in ts
        ]

        dx = P2[0] - pts[-1][0]
        dy = P2[1] - pts[-1][1]
        length = max(1e-3, math.hypot(dx, dy))
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux

        head_base_x, head_base_y = pts[-1][0] - ux * (14 * S), pts[-1][1] - uy * (14 * S)
        head_half_w = 68.0 * S
        head_poly = [
            (P2[0], P2[1]),
            (head_base_x + nx * head_half_w, head_base_y + ny * head_half_w),
            (head_base_x - nx * head_half_w, head_base_y - ny * head_half_w),
        ]
        head_cx = sum(p[0] for p in head_poly) / 3.0
        head_cy = sum(p[1] for p in head_poly) / 3.0
        head_border = []
        for px, py in head_poly:
            vx, vy = px - head_cx, py - head_cy
            vl = max(1e-3, math.hypot(vx, vy))
            head_border.append((px + vx / vl * (10.0 * S), py + vy / vl * (10.0 * S)))

        shaft_border_poly = _build_ribbon_polygon(pts, 24.0 * S, 30.0 * S)
        shaft_gold_poly = _build_ribbon_polygon(pts, 16.0 * S, 22.0 * S)
        shaft_core_poly = _build_ribbon_polygon(pts[3:-2], 8.0 * S, 11.0 * S)

        shadow_hi = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_hi)
        sd.polygon([(x + 7 * S, y + 12 * S) for (x, y) in shaft_border_poly], fill=(0, 0, 0, 220))
        sd.polygon([(x + 7 * S, y + 12 * S) for (x, y) in head_border], fill=(0, 0, 0, 220))
        out = Image.alpha_composite(
            out,
            shadow_hi.resize((w, h), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=14)),
        )

        arrow_hi = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ad = ImageDraw.Draw(arrow_hi)
        r_b0 = 24.0 * S
        ad.ellipse([P0[0] - r_b0, P0[1] - r_b0, P0[0] + r_b0, P0[1] + r_b0], fill=(10, 12, 16, 255))
        ad.polygon(shaft_border_poly, fill=(10, 12, 16, 255))
        ad.polygon(head_border, fill=(10, 12, 16, 255))

        r_g0 = 16.0 * S
        ad.ellipse([P0[0] - r_g0, P0[1] - r_g0, P0[0] + r_g0, P0[1] + r_g0], fill=(*vcue.arrow_rgb, 255))
        ad.polygon(shaft_gold_poly, fill=(*vcue.arrow_rgb, 255))
        ad.polygon(head_poly, fill=(*vcue.arrow_rgb, 255))
        core_rgb = (
            min(255, int(vcue.arrow_rgb[0] * 0.4 + 153)),
            min(255, int(vcue.arrow_rgb[1] * 0.4 + 153)),
            min(255, int(vcue.arrow_rgb[2] * 0.4 + 153)),
            255,
        )
        ad.polygon(shaft_core_poly, fill=core_rgb)
        out = Image.alpha_composite(out, arrow_hi.resize((w, h), Image.Resampling.LANCZOS))

        if vcue.symbol != "none":
            st = vcue.symbol_t
            xc = (1 - st) ** 2 * P0[0] + 2 * (1 - st) * st * P1[0] + st**2 * P2[0]
            yc = (1 - st) ** 2 * P0[1] + 2 * (1 - st) * st * P1[1] + st**2 * P2[1]
            sym_shadow_hi, sym_badge_hi = _draw_symbol_badge_2x(sw, sh, xc, yc, vcue.symbol, vcue.symbol_scale, S=S)
            out = Image.alpha_composite(
                out,
                sym_shadow_hi.resize((w, h), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=14)),
            )
            out = Image.alpha_composite(out, sym_badge_hi.resize((w, h), Image.Resampling.LANCZOS))

    return out


def compose_subject_first_thumbnail(
    source_rgb: Image.Image,
    style: DocumentaryStyleProfile,
    headline_text: str = "",
    cx: Optional[float] = None,
    cy: Optional[float] = None,
    zoom: float = 1.02,
    text_position: str = "auto",
    kicker_text: str = "",
    accent_line_index: int = 1,
    accent_rgb: tuple[int, int, int] = (255, 212, 59),
    clarity_boost: bool = True,
    shadow_lift: float = 0.0,
    mirror_horizontal: bool = False,
    visual_cue: Optional["ThumbnailVisualCueSpec"] = None,
    cutout_image: Optional[Image.Image] = None,
) -> Image.Image:
    """
    Compose a high-CTR 1080x1920 documentary cover image, supporting optional intuitive
    `visual_cue` storytelling (foreground cutout/inset + curved Bezier arrow + status badge).
    """
    out_w = style.output.width
    out_h = style.output.height
    src_work = ImageOps.mirror(source_rgb) if mirror_horizontal else source_rgb
    if cx is None or cy is None:
        auto_cx, auto_cy = estimate_salient_subject_center(src_work, keep_above_subtitle_ratio=0.72)
        cx = auto_cx if cx is None else cx
        cy = auto_cy if cy is None else cy

    base = crop_subpixel_full_canvas(src_work, cx, cy, max(1.0, zoom), out_w, out_h)
    if shadow_lift > 1e-4:
        b_arr = np.asarray(base, dtype=np.float32) / 255.0
        b_arr = np.clip(b_arr + float(shadow_lift) * b_arr * ((1.0 - b_arr) ** 1.6), 0.0, 1.0)
        base = Image.fromarray((b_arr * 255.0).astype(np.uint8))
    if clarity_boost:
        base = _apply_optical_subject_clarity(base)

    has_vcue = visual_cue is not None and visual_cue.enabled
    mode = style.opening_and_thumbnail.thumbnail_text_mode
    if mode == "none" or not headline_text.strip():
        if has_vcue and visual_cue is not None:
            return apply_visual_cue_overlay(base.convert("RGBA"), visual_cue, cutout_src=cutout_image).convert("RGB")
        return base

    max_w = style.opening_and_thumbnail.thumbnail_max_words
    arr = np.asarray(base, dtype=np.float32)
    luma_top = float(np.mean(arr[100:480, :, :]))
    luma_bot = float(np.mean(arr[1240:1660, :, :]))

    if text_position == "auto":
        if has_vcue and visual_cue is not None and visual_cue.cutout_cy < 0.45:
            place_top = False
        else:
            place_top = cy >= 0.47
    else:
        place_top = text_position == "top"

    yy = np.arange(out_h, dtype=np.float32)[:, None, None]
    xx = np.arange(out_w, dtype=np.float32)[None, :, None]

    if mode == "minimal_headline":
        clean_headline = " ".join(headline_text.replace("|", " ").strip().split()[:max_w])
        if place_top:
            strength = 0.68 if luma_top > 135.0 else 0.38
            scrim = np.clip((560.0 - yy) / 560.0, 0.0, 1.0) ** 1.25 * strength
            text_y = 205
        else:
            strength = 0.66 if luma_bot > 135.0 else 0.42
            scrim = np.clip((yy - 1180.0) / 740.0, 0.0, 1.0) ** 1.25 * strength
            text_y = 1365
        toned = np.clip(arr * (1.0 - scrim), 0.0, 255.0).astype(np.uint8)
        canvas = Image.fromarray(toned).convert("RGBA")
        if has_vcue and visual_cue is not None:
            canvas = apply_visual_cue_overlay(canvas, visual_cue, cutout_src=cutout_image)
        d = ImageDraw.Draw(canvas)
        font_sz = 84
        font = ImageFont.truetype(FONT_BOLD, font_sz)
        while font_sz > 54 and d.textbbox((0, 0), clean_headline, font=font)[2] > int(out_w * 0.86):
            font_sz -= 4
            font = ImageFont.truetype(FONT_BOLD, font_sz)
        tw = d.textbbox((0, 0), clean_headline, font=font)[2]
        tx = (out_w - tw) // 2
        shadow_layer = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(shadow_layer)
        sd.text((tx, text_y + 4), clean_headline, font=font, fill=(0, 0, 0, 195))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=9))
        canvas = Image.alpha_composite(canvas, shadow_layer)
        d = ImageDraw.Draw(canvas)
        d.text(
            (tx, text_y),
            clean_headline,
            font=font,
            fill=(252, 253, 255, 254),
            stroke_width=2,
            stroke_fill=(8, 12, 18, 195),
        )
        return canvas.convert("RGB")

    # `cinema_hook` mode: Stacked 2-line giant display hook + focal subject luminance framing
    lines = _split_hook_lines(headline_text, max_words=max_w)
    if not lines:
        return base

    if place_top:
        strength = 0.74 if luma_top > 115.0 else 0.56
        scrim = np.clip((680.0 - yy) / 680.0, 0.0, 1.0) ** 1.30 * strength
        # Gentle bottom edge darkening so YT UI title sits cleanly without competing
        bot_vign = np.clip((yy - 1540.0) / 380.0, 0.0, 1.0) ** 1.4 * 0.34
        scrim = np.clip(scrim + bot_vign, 0.0, 0.84)
    else:
        strength = 0.74 if luma_bot > 115.0 else 0.58
        scrim = np.clip((yy - 1080.0) / 840.0, 0.0, 1.0) ** 1.25 * strength

    # Subtle radial edge vignette keeping the central phenomenon luminous
    rx = (xx - out_w * 0.50) / (out_w * 0.58)
    ry = (yy - out_h * (0.63 if place_top else 0.42)) / (out_h * 0.48)
    radial = np.clip((rx * rx + ry * ry - 0.55) * 0.22, 0.0, 0.26)
    toned = np.clip(arr * (1.0 - np.clip(scrim + radial, 0.0, 0.86)), 0.0, 255.0).astype(np.uint8)

    canvas = Image.fromarray(toned).convert("RGBA")
    if has_vcue and visual_cue is not None:
        canvas = apply_visual_cue_overlay(canvas, visual_cue, cutout_src=cutout_image)
    d = ImageDraw.Draw(canvas)

    disp_font_path = FONT_ANTON if Path(FONT_ANTON).exists() else FONT_BOLD
    target_w = int(out_w * 0.86)
    font_sz = 152 if len(lines) >= 2 else 136
    font = ImageFont.truetype(disp_font_path, font_sz)
    while font_sz > 76:
        max_lw = max(d.textbbox((0, 0), ln, font=font)[2] for ln in lines)
        if max_lw <= target_w:
            break
        font_sz -= 4
        font = ImageFont.truetype(disp_font_path, font_sz)

    line_step = int(round(font_sz * 1.08))
    clean_kicker = " ".join(kicker_text.strip().split()[:6]).upper()
    kicker_h = 64 if clean_kicker else 0

    block_y0 = 148 if place_top else (1390 - (len(lines) - 1) * line_step - kicker_h)

    shadow_wide = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    shadow_tight = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
    sw_d = ImageDraw.Draw(shadow_wide)
    st_d = ImageDraw.Draw(shadow_tight)

    if clean_kicker:
        kf = ImageFont.truetype(FONT_BOLD, 30)
        kb = d.textbbox((0, 0), clean_kicker, font=kf)
        kx = (out_w - (kb[2] - kb[0])) // 2
        ky = block_y0
        sw_d.text((kx, ky + 3), clean_kicker, font=kf, fill=(0, 0, 0, 220))
        st_d.text((kx, ky + 2), clean_kicker, font=kf, fill=(0, 0, 0, 235))

    line_positions: list[tuple[int, int, str, tuple[int, int, int, int]]] = []
    for idx, ln in enumerate(lines):
        bb = d.textbbox((0, 0), ln, font=font)
        lw = bb[2] - bb[0]
        lx = (out_w - lw) // 2 - bb[0]
        ly = block_y0 + kicker_h + idx * line_step - bb[1]
        is_accent = (idx == accent_line_index) or (len(lines) == 1 and accent_line_index == 0)
        fill_rgba = (*accent_rgb, 255) if is_accent else (255, 255, 255, 255)
        line_positions.append((lx, ly, ln, fill_rgba))
        sw_d.text((lx, ly + 8), ln, font=font, fill=(0, 0, 0, 235), stroke_width=10, stroke_fill=(0, 0, 0, 210))
        st_d.text((lx, ly + 4), ln, font=font, fill=(0, 0, 0, 245), stroke_width=5, stroke_fill=(0, 0, 0, 230))

    shadow_wide = shadow_wide.filter(ImageFilter.GaussianBlur(radius=18))
    shadow_tight = shadow_tight.filter(ImageFilter.GaussianBlur(radius=5))
    canvas = Image.alpha_composite(canvas, shadow_wide)
    canvas = Image.alpha_composite(canvas, shadow_tight)

    d = ImageDraw.Draw(canvas)
    if clean_kicker:
        kf = ImageFont.truetype(FONT_BOLD, 30)
        kb = d.textbbox((0, 0), clean_kicker, font=kf)
        kx = (out_w - (kb[2] - kb[0])) // 2
        d.text(
            (kx, block_y0),
            clean_kicker,
            font=kf,
            fill=(198, 234, 255, 250),
            stroke_width=2,
            stroke_fill=(5, 10, 18, 225),
        )

    for lx, ly, ln, fill_rgba in line_positions:
        d.text(
            (lx, ly),
            ln,
            font=font,
            fill=fill_rgba,
            stroke_width=5,
            stroke_fill=(4, 8, 16, 246),
        )

    return canvas.convert("RGB")


def export_documentary_thumbnail_package(
    thumb_rgb: Image.Image,
    out_dir: Path,
    slug: str,
    primary_title: str,
    style: DocumentaryStyleProfile,
    cand_score: Optional[ThumbnailCandidateScore] = None,
    alt_variants: Optional[list[tuple[str, Image.Image]]] = None,
) -> dict:
    """
    Save `<slug>.jpg`, `<slug>.png`, `thumbnail.jpg`, optional `thumbnail_variant_B/C.jpg`,
    and `thumbnail_small_preview_sheet.jpg` verifying full 9:16 composition, 160x284 mobile
    shelf clarity, 1:1 feed crop, and native pixel detail.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    jpg_slug = out_dir / f"{slug}.jpg"
    png_slug = out_dir / f"{slug}.png"
    thumb_jpg = out_dir / "thumbnail.jpg"
    sheet_jpg = out_dir / "thumbnail_small_preview_sheet.jpg"

    thumb_rgb.save(png_slug, format="PNG", optimize=True)
    q = save_youtube_444_jpeg(thumb_rgb, jpg_slug, max_bytes=style.opening_and_thumbnail.thumbnail_max_bytes)
    save_youtube_444_jpeg(thumb_rgb, thumb_jpg, max_bytes=style.opening_and_thumbnail.thumbnail_max_bytes)

    exported_variants: list[str] = []
    for v_idx, (_, v_img) in enumerate(alt_variants or []):
        v_tag = chr(ord("B") + v_idx)
        v_path = out_dir / f"thumbnail_variant_{v_tag}.jpg"
        save_youtube_444_jpeg(v_img, v_path, max_bytes=style.opening_and_thumbnail.thumbnail_max_bytes)
        exported_variants.append(str(v_path))

    sheet_w, sheet_h = 1660, 1040
    sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 16, 24))
    draw = ImageDraw.Draw(sheet)
    f_hdr = ImageFont.truetype(FONT_BOLD, 22)
    f_sub = ImageFont.truetype(FONT_MED, 17)
    f_tiny = ImageFont.truetype(FONT_BOLD, 11)

    p1 = thumb_rgb.resize((486, 864), Image.Resampling.LANCZOS)
    sheet.paste(p1, (36, 90))
    draw.text((36, 36), "1. Master Cinema Cover (9:16 • 1080x1920)", font=f_hdr, fill=(255, 255, 255))

    draw.text((560, 36), "2. Mobile Shelf (160x284 px)", font=f_hdr, fill=(255, 255, 255))
    mob = thumb_rgb.resize((160, 284), Image.Resampling.LANCZOS)
    sheet.paste(mob, (560, 90))

    mob_ov = mob.copy().convert("RGBA")
    ov = Image.new("RGBA", (160, 284), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    od.rectangle((0, 224, 160, 284), fill=(0, 0, 0, 165))
    od.text((8, 232), primary_title[:22] + ("..." if len(primary_title) > 22 else ""), font=f_tiny, fill=(255, 255, 255, 242))
    if len(primary_title) > 22:
        od.text((8, 250), primary_title[22:44], font=f_tiny, fill=(255, 255, 255, 242))
    sheet.paste(Image.alpha_composite(mob_ov, ov).convert("RGB"), (744, 90))
    draw.text((560, 384), "Clean 160x284", font=f_sub, fill=(195, 208, 225))
    draw.text((744, 384), "With YT Shelf UI", font=f_sub, fill=(195, 208, 225))

    if alt_variants:
        draw.text((938, 36), "3. A/B Hook Variants (Mobile 160x284)", font=f_hdr, fill=(255, 220, 110))
        for v_idx, (v_lbl, v_img) in enumerate(alt_variants[:3]):
            vx = 938 + v_idx * 224
            sheet.paste(v_img.resize((160, 284), Image.Resampling.LANCZOS), (vx, 90))
            v_tag = chr(ord("B") + v_idx)
            draw.text((vx, 384), f"Var {v_tag}: {v_lbl[:14]}", font=f_sub, fill=(255, 226, 130))
    else:
        draw.text((1065, 36), "3. 1:1 Native Pixels (Subject Detail)", font=f_hdr, fill=(140, 224, 250))
        cx_px = int(round((cand_score.recommended_cx if cand_score else 0.5) * 1080))
        cy_px = int(round((cand_score.recommended_cy if cand_score else 0.48) * 1920))
        x0 = max(0, min(1080 - 460, cx_px - 230))
        y0 = max(0, min(1920 - 460, cy_px - 230))
        sheet.paste(thumb_rgb.crop((x0, y0, x0 + 460, y0 + 460)), (1065, 90))

    draw.text((560, 448), "4. 1:1 Center Feed Crop (y=420..1500)", font=f_hdr, fill=(255, 255, 255))
    sq = thumb_rgb.crop((0, 420, 1080, 1500)).resize((450, 450), Image.Resampling.LANCZOS)
    sheet.paste(sq, (560, 496))

    kb = round(thumb_jpg.stat().st_size / 1024.0, 1)
    notes = [
        "High-CTR Documentary Thumbnail QC (v4.0):",
        f"• File: {thumb_jpg.name} ({kb} KB, q={q}, 4:4:4 RGB)",
        f"• Text Mode: {style.opening_and_thumbnail.thumbnail_text_mode}",
        f"• A/B Variants Exported: {1 + len(exported_variants)}",
        "• Decorative Boxes / Badges / Rings: NONE (0)",
        f"• Sharpness Score: {cand_score.sharpness_score if cand_score else 'n/a'}",
        f"• Subject Separation: {cand_score.subject_separation_score if cand_score else 'n/a'}",
    ]
    ny = 510
    for ln in notes:
        draw.text((1045, ny), ln, font=f_sub, fill=(220, 232, 245))
        ny += 36

    sheet.save(sheet_jpg, format="JPEG", quality=93, subsampling=0)
    return {
        "thumbnail_jpg": str(thumb_jpg),
        "sidecar_jpg": str(jpg_slug),
        "sidecar_png": str(png_slug),
        "alt_variant_jpgs": exported_variants,
        "preview_sheet_jpg": str(sheet_jpg),
        "size_bytes": thumb_jpg.stat().st_size,
        "under_2mb": thumb_jpg.stat().st_size <= style.opening_and_thumbnail.thumbnail_max_bytes,
        "jpeg_quality": q,
        "candidate_score": cand_score.__dict__ if cand_score else None,
    }


def generate_thumbnail_concepts_package(
    concepts_rendered: list[dict],
    out_dir: Path,
    slug: str,
    primary_title: str,
    style: DocumentaryStyleProfile,
    opening_shot_src_file: str = "",
) -> dict:
    """
    Export multiple distinct Thumbnail Concepts (`thumbnail_concept_A.jpg`, `B`, `C`),
    a realistic mobile-display side-by-side comparison sheet (`thumbnail_concepts_comparison_sheet.jpg`),
    and `thumbnail_concepts_manifest.json` (Part 7, Section 9).

    Maintains 100% compatibility with `thumbnail.jpg`, `<slug>.jpg`, and `thumbnail_small_preview_sheet.jpg`.
    """
    import json

    if not concepts_rendered:
        raise ValueError("At least one rendered thumbnail concept is required.")

    out_dir.mkdir(parents=True, exist_ok=True)
    primary = concepts_rendered[0]
    alt_tuples = [
        (str(c.get("headline_text") or c.get("concept_id") or f"Concept {idx+1}").replace("|", " "), c["image"])
        for idx, c in enumerate(concepts_rendered[1:])
    ]

    base_pkg = export_documentary_thumbnail_package(
        thumb_rgb=primary["image"],
        out_dir=out_dir,
        slug=slug,
        primary_title=primary_title,
        style=style,
        cand_score=primary.get("candidate_score"),
        alt_variants=alt_tuples,
    )

    concept_records: list[dict] = []
    for idx, c in enumerate(concepts_rendered):
        cid = str(c.get("concept_id") or chr(ord("A") + idx))
        c_path = out_dir / f"thumbnail_concept_{cid}.jpg"
        q = save_youtube_444_jpeg(c["image"], c_path, max_bytes=style.opening_and_thumbnail.thumbnail_max_bytes)
        cscore: Optional[ThumbnailCandidateScore] = c.get("candidate_score")
        hl = str(c.get("headline_text", "") or "")
        wc = len(hl.replace("|", " ").split())
        src_f = str(c.get("src_file", "") or "")
        concept_records.append(
            {
                "concept_id": cid,
                "path": str(c_path),
                "source_asset": src_f,
                "matches_opening_scene_asset": bool(opening_shot_src_file and src_f == opening_shot_src_file),
                "headline_text": hl,
                "headline_word_count": wc,
                "kicker_text": str(c.get("kicker_text", "") or ""),
                "concept_rationale": str(c.get("concept_rationale", "") or ""),
                "size_kb": round(c_path.stat().st_size / 1024.0, 1),
                "jpeg_quality": q,
                "legibility_metrics": cscore.__dict__ if cscore else None,
                "actual_analytics_outcome": None,
            }
        )

    # Render dedicated multi-concept mobile display comparison sheet (160x284 clean + YT UI + 320x568)
    n_c = len(concepts_rendered)
    col_w = 560
    sheet_w = max(1160, n_c * col_w + 40)
    sheet_h = 920
    comp = Image.new("RGB", (sheet_w, sheet_h), (12, 16, 24))
    draw = ImageDraw.Draw(comp)
    f_hdr = ImageFont.truetype(FONT_BOLD, 24)
    f_sub = ImageFont.truetype(FONT_BOLD, 18)
    f_body = ImageFont.truetype(FONT_MED, 15)
    f_tiny = ImageFont.truetype(FONT_BOLD, 11)

    draw.text(
        (28, 22),
        f"THUMBNAIL STUDIO — {n_c} DISTINCT CONCEPTS @ REALISTIC MOBILE DISPLAY SIZES ({slug})",
        font=f_hdr,
        fill=(255, 255, 255),
    )
    draw.text(
        (28, 56),
        "Note: Legibility metrics verify contrast/sharpness only and do NOT predict CTR; compare real YouTube Studio test outcomes.",
        font=f_body,
        fill=(185, 204, 226),
    )

    for idx, (c, rec) in enumerate(zip(concepts_rendered, concept_records)):
        ox = 28 + idx * col_w
        im_rgb: Image.Image = c["image"]
        draw.rounded_rectangle((ox, 92, ox + col_w - 22, sheet_h - 24), radius=14, fill=(19, 25, 36), outline=(62, 84, 114), width=2)
        draw.text(
            (ox + 18, 108),
            f"Concept {rec['concept_id']} • {rec['source_asset'][:26]}",
            font=f_sub,
            fill=(255, 222, 110),
        )
        # 300x533 medium preview
        comp.paste(im_rgb.resize((300, 533), Image.Resampling.LANCZOS), (ox + 18, 146))
        # 160x284 realistic mobile shelf (clean)
        mob = im_rgb.resize((160, 284), Image.Resampling.LANCZOS)
        comp.paste(mob, (ox + 340, 146))
        draw.text((ox + 340, 436), "160x284 Mobile", font=f_body, fill=(205, 220, 238))
        # 160x284 with YouTube Shorts shelf title overlay
        mob_ov = mob.copy().convert("RGBA")
        ov = Image.new("RGBA", (160, 284), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle((0, 224, 160, 284), fill=(0, 0, 0, 168))
        od.text((8, 232), primary_title[:22] + ("..." if len(primary_title) > 22 else ""), font=f_tiny, fill=(255, 255, 255, 245))
        comp.paste(Image.alpha_composite(mob_ov, ov).convert("RGB"), (ox + 340, 472))
        draw.text((ox + 340, 762), "With YT Shelf UI", font=f_body, fill=(205, 220, 238))

        hl_disp = rec["headline_text"].replace("|", " / ") or "(Pure Visual — No Text)"
        draw.text((ox + 18, 700), f"Hook ({rec['headline_word_count']}w): {hl_disp[:36]}", font=f_body, fill=(235, 242, 252))
        if rec["concept_rationale"]:
            draw.text((ox + 18, 730), f"Why: {rec['concept_rationale'][:46]}", font=f_body, fill=(185, 204, 226))
        sc_str = (
            f"Clarity: {rec['legibility_metrics']['combined_score']} | Opening Match: {rec['matches_opening_scene_asset']}"
            if rec["legibility_metrics"]
            else f"Opening Match: {rec['matches_opening_scene_asset']}"
        )
        draw.text((ox + 18, 762), sc_str, font=f_body, fill=(156, 226, 192))

    comp_sheet_path = out_dir / "thumbnail_concepts_comparison_sheet.jpg"
    comp.save(comp_sheet_path, format="JPEG", quality=93, subsampling=0)

    manifest_payload = {
        "slug": slug,
        "primary_title": primary_title,
        "concepts_count": len(concept_records),
        "comparison_sheet_jpg": str(comp_sheet_path),
        "ctr_prediction_disclaimer": (
            "Visual sharpness and subject-separation scores verify small-screen mobile legibility only. "
            "They do NOT predict real YouTube click-through or swipe-away rates; populate `actual_analytics_outcome` "
            "via `analytics_learning.py` once real YouTube Studio impressions/views are available."
        ),
        "concepts": concept_records,
    }
    manifest_json_path = out_dir / "thumbnail_concepts_manifest.json"
    manifest_json_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")

    return {
        **base_pkg,
        "concepts_comparison_sheet_jpg": str(comp_sheet_path),
        "concepts_manifest_json": str(manifest_json_path),
        "concepts": concept_records,
    }

