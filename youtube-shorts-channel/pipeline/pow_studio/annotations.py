#!/usr/bin/env python3
"""
Step 3B: Minimalist Documentary On-Footage Annotations (`pow_studio.annotations`).

Provides clean, Vox / National Geographic-style visual annotations overlaid directly
onto real photography/footage without obscuring visual evidence:
1. `draw_scale_ring_annotation`: Animated hairline ring + leader line + compact scale pill
2. `draw_region_locator` (aliased as `draw_antarctica_locator`): Minimalist corner vector
   map card (`antarctica`, `gulf_of_mexico`, or `red_sea`) with pulsing coordinate pin.
"""

from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFont

from .schema import LocatorPinAnnotation, ScaleCalloutAnnotation

# Simplified accurate normalized [0..1] coastal silhouette of Antarctica
ANTARCTICA_POLY_UV: list[tuple[float, float]] = [
    (0.18, 0.24),
    (0.24, 0.31),
    (0.29, 0.37),
    (0.37, 0.36),
    (0.45, 0.28),
    (0.58, 0.22),
    (0.72, 0.26),
    (0.84, 0.37),
    (0.88, 0.52),
    (0.83, 0.67),
    (0.71, 0.76),
    (0.60, 0.73),
    (0.55, 0.65),
    (0.46, 0.68),
    (0.39, 0.75),
    (0.28, 0.70),
    (0.22, 0.58),
    (0.24, 0.45),
    (0.17, 0.32),
]

# Gulf of Mexico surrounding continental landmass & Western Cuba in normalized [0..1] box
GULF_OF_MEXICO_MAINLAND_UV: list[tuple[float, float]] = [
    (1.00, 0.00),
    (0.00, 0.00),
    (0.00, 1.00),
    (0.62, 1.00),
    (0.62, 0.82),
    (0.58, 0.67),  # Yucatan tip (Cabo Catoche)
    (0.45, 0.69),  # Yucatan shelf
    (0.42, 0.82),  # Campeche
    (0.26, 0.89),  # Bay of Campeche / Veracruz
    (0.14, 0.72),  # Tampico
    (0.14, 0.46),  # Rio Grande / South Texas
    (0.25, 0.26),  # Galveston / Texas-Louisiana shelf
    (0.46, 0.28),  # Mississippi River Delta
    (0.56, 0.20),  # Mobile / Pensacola
    (0.73, 0.24),  # Florida Big Bend
    (0.80, 0.41),  # Tampa Bay
    (0.86, 0.56),  # South Florida tip
    (0.90, 0.41),  # Miami / Atlantic coast
    (0.86, 0.14),
]

GULF_OF_MEXICO_CUBA_UV: list[tuple[float, float]] = [
    (0.72, 0.75),
    (0.86, 0.68),
    (1.00, 0.73),
    (1.00, 0.84),
    (0.84, 0.79),
    (0.72, 0.78),
]

# Northern Red Sea, Sinai Peninsula, Gulf of Suez (left fork) & Gulf of Aqaba (right fork) water polygons
RED_SEA_WATER_UV: list[tuple[float, float]] = [
    (0.92, 1.00),
    (0.52, 1.00),
    (0.38, 0.73),
    (0.26, 0.50),  # Entrance of Gulf of Suez
    (0.11, 0.16),  # Suez head (west shore)
    (0.15, 0.13),  # Suez head (east shore)
    (0.31, 0.44),  # West Sinai coast
    (0.38, 0.48),  # Ras Mohammed (Sinai southern tip)
    (0.44, 0.33),  # Gulf of Aqaba west shore
    (0.49, 0.16),  # Aqaba / Eilat northern head
    (0.53, 0.17),
    (0.48, 0.35),  # Gulf of Aqaba east shore (NEOM / Aragonese Deep)
    (0.44, 0.49),  # Straits of Tiran
    (0.62, 0.63),  # Saudi Red Sea margin
    (0.78, 0.81),
]

RED_SEA_MED_UV: list[tuple[float, float]] = [
    (0.00, 0.00),
    (0.46, 0.00),
    (0.36, 0.08),
    (0.14, 0.09),
    (0.00, 0.07),
]


def draw_scale_ring_annotation(
    img_rgba: Image.Image,
    spec: ScaleCalloutAnnotation,
    local_t: float,
    shot_dur: float,
    font_bold: ImageFont.FreeTypeFont,
    font_med: ImageFont.FreeTypeFont,
) -> None:
    if local_t < spec.reveal_delay_s:
        return
    fade_in = min(1.0, (local_t - spec.reveal_delay_s) / 0.40)
    fade_out = min(1.0, max(0.0, (shot_dur - local_t - 0.15) / 0.35))
    alpha = int(round(245 * min(fade_in, fade_out)))
    if alpha < 8:
        return

    w, h = img_rgba.size
    cx = int(round(spec.norm_x * w))
    cy = int(round(spec.norm_y * h))
    r = spec.ring_radius_px

    d = ImageDraw.Draw(img_rgba)

    pulse_r = r + int(round(6.0 + 4.0 * math.sin((local_t - spec.reveal_delay_s) * 4.2)))
    d.ellipse(
        (cx - pulse_r, cy - pulse_r, cx + pulse_r, cy + pulse_r),
        outline=(255, 214, 120, int(alpha * 0.38)),
        width=2,
    )
    sweep_deg = min(360.0, 360.0 * ((local_t - spec.reveal_delay_s) / 0.42))
    d.arc(
        (cx - r, cy - r, cx + r, cy + r),
        start=-90.0,
        end=-90.0 + sweep_deg,
        fill=(255, 224, 130, alpha),
        width=3,
    )

    if sweep_deg < 160.0:
        return

    tw1 = d.textbbox((0, 0), spec.label_title, font=font_bold)[2]
    tw2 = d.textbbox((0, 0), spec.label_subtitle, font=font_med)[2] if spec.label_subtitle else 0
    box_w = max(tw1, tw2) + 32
    box_h = 74 if spec.label_subtitle else 46

    if spec.side == "right":
        bx0 = min(w - box_w - 32, cx + r + 42)
        by0 = max(160, min(h - 520, cy - box_h // 2 - 24))
        lx0, ly0 = cx + int(r * 0.85), cy - int(r * 0.35)
        lx1, ly1 = bx0, by0 + box_h // 2
    elif spec.side == "left":
        bx0 = max(32, cx - r - 42 - box_w)
        by0 = max(160, min(h - 520, cy - box_h // 2 - 24))
        lx0, ly0 = cx - int(r * 0.85), cy - int(r * 0.35)
        lx1, ly1 = bx0 + box_w, by0 + box_h // 2
    else:  # "top"
        bx0 = max(32, min(w - box_w - 32, cx - box_w // 2))
        by0 = max(160, cy - r - 54 - box_h)
        lx0, ly0 = cx, cy - r
        lx1, ly1 = bx0 + box_w // 2, by0 + box_h

    d.line([(lx0, ly0), (lx1, ly1)], fill=(255, 224, 130, int(alpha * 0.9)), width=2)
    d.rounded_rectangle(
        (bx0, by0, bx0 + box_w, by0 + box_h),
        radius=11,
        fill=(10, 15, 26, int(alpha * 0.88)),
        outline=(255, 218, 128, int(alpha * 0.82)),
        width=2,
    )
    d.text((bx0 + 16, by0 + 9), spec.label_title, font=font_bold, fill=(255, 232, 156, alpha))
    if spec.label_subtitle:
        d.text((bx0 + 16, by0 + 40), spec.label_subtitle, font=font_med, fill=(224, 234, 246, alpha))


def draw_region_locator(
    img_rgba: Image.Image,
    spec: LocatorPinAnnotation,
    local_t: float,
    shot_dur: float,
    font_bold: ImageFont.FreeTypeFont,
    font_med: ImageFont.FreeTypeFont,
) -> None:
    if local_t < spec.reveal_delay_s:
        return
    fade_in = min(1.0, (local_t - spec.reveal_delay_s) / 0.35)
    fade_out = min(1.0, max(0.0, (shot_dur - local_t - 0.15) / 0.35))
    alpha = int(round(240 * min(fade_in, fade_out)))
    if alpha < 8:
        return

    w, _ = img_rgba.size
    card_w, card_h = 248, 254
    x0 = w - card_w - 36
    y0 = 122

    d = ImageDraw.Draw(img_rgba)
    d.rounded_rectangle(
        (x0, y0, x0 + card_w, y0 + card_h),
        radius=16,
        fill=(8, 14, 24, int(alpha * 0.86)),
        outline=(140, 182, 218, int(alpha * 0.68)),
        width=2,
    )

    if spec.map_region == "antarctica":
        map_cx, map_cy = x0 + card_w // 2, y0 + 104
        map_r = 76
        for gr in (38, 74):
            d.ellipse(
                (map_cx - gr, map_cy - gr, map_cx + gr, map_cy + gr),
                outline=(90, 128, 165, int(alpha * 0.35)),
                width=1,
            )
        poly_pts = [
            (map_cx + (u - 0.5) * 2.0 * map_r, map_cy + (v - 0.5) * 2.0 * map_r)
            for u, v in ANTARCTICA_POLY_UV
        ]
        d.polygon(poly_pts, fill=(214, 230, 244, int(alpha * 0.86)), outline=(120, 168, 208, alpha))
        px = map_cx + (spec.pin_u - 0.5) * 2.0 * map_r
        py = map_cy + (spec.pin_v - 0.5) * 2.0 * map_r
    else:
        # Rectangular inset ocean/continent chart inside card
        mx0, my0, mw, mh = x0 + 20, y0 + 20, card_w - 40, 152
        if spec.map_region == "gulf_of_mexico":
            d.rectangle((mx0, my0, mx0 + mw, my0 + mh), fill=(12, 30, 52, int(alpha * 0.92)))
            for gv in (0.33, 0.66):
                d.line([(mx0, my0 + int(gv * mh)), (mx0 + mw, my0 + int(gv * mh))], fill=(70, 112, 150, int(alpha * 0.28)), width=1)
                d.line([(mx0 + int(gv * mw), my0), (mx0 + int(gv * mw), my0 + mh)], fill=(70, 112, 150, int(alpha * 0.28)), width=1)
            pts_main = [(mx0 + u * mw, my0 + v * mh) for u, v in GULF_OF_MEXICO_MAINLAND_UV]
            pts_cuba = [(mx0 + u * mw, my0 + v * mh) for u, v in GULF_OF_MEXICO_CUBA_UV]
            d.polygon(pts_main, fill=(192, 212, 230, int(alpha * 0.86)), outline=(118, 168, 208, alpha))
            d.polygon(pts_cuba, fill=(192, 212, 230, int(alpha * 0.86)), outline=(118, 168, 208, alpha))
            d.rectangle((mx0, my0, mx0 + mw, my0 + mh), outline=(118, 162, 202, int(alpha * 0.72)), width=2)
        else:  # "red_sea"
            d.rectangle((mx0, my0, mx0 + mw, my0 + mh), fill=(196, 212, 226, int(alpha * 0.86)))
            pts_sea = [(mx0 + u * mw, my0 + v * mh) for u, v in RED_SEA_WATER_UV]
            pts_med = [(mx0 + u * mw, my0 + v * mh) for u, v in RED_SEA_MED_UV]
            d.polygon(pts_sea, fill=(10, 28, 52, int(alpha * 0.96)), outline=(95, 165, 214, alpha))
            d.polygon(pts_med, fill=(10, 28, 52, int(alpha * 0.96)), outline=(95, 165, 214, alpha))
            d.rectangle((mx0, my0, mx0 + mw, my0 + mh), outline=(118, 162, 202, int(alpha * 0.72)), width=2)

        px = mx0 + spec.pin_u * mw
        py = my0 + spec.pin_v * mh

    pr = 8.0 + 5.0 * (0.5 + 0.5 * math.sin((local_t - spec.reveal_delay_s) * 5.2))
    d.ellipse((px - pr, py - pr, px + pr, py + pr), outline=(255, 88, 64, int(alpha * 0.78)), width=2)
    d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(242, 62, 42, alpha), outline=(255, 255, 255, alpha), width=2)

    tw1 = d.textbbox((0, 0), spec.place_title, font=font_bold)[2]
    tw2 = d.textbbox((0, 0), spec.coords_label, font=font_med)[2]
    d.text((x0 + (card_w - tw1) // 2, y0 + 188), spec.place_title, font=font_bold, fill=(248, 252, 255, alpha))
    d.text((x0 + (card_w - tw2) // 2, y0 + 218), spec.coords_label, font=font_med, fill=(176, 206, 234, alpha))


# Backwards-compatible alias for Episode #1 (`blood-falls-20261028-v2-studio`)
draw_antarctica_locator = draw_region_locator
