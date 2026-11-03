#!/usr/bin/env python3
"""
Generate a 100% first-party original vertical (1080x1920 @ 30fps) geological &
density cutaway animation for the Snake Island documentary (`Studio v6.0`):
`assets/raw_footage/hidden_earth_snake_island_v6/snake_island_density_trap_v6.mp4`

Illustrates two peer-reviewed datasets (Instituto Butantan / Marques et al.):
1. Post-glacial sea-level rise (~11,000 years BP) drowning the 33 km continental
   shelf bridge between Mainland Brazil (São Paulo) and Ilha da Queimada Grande.
2. Field density survey visualization: 43 hectares holding ~2,000-4,000
   Bothrops insularis (~50-90 venomous pit vipers packed into every hectare).
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "assets" / "raw_footage" / "hidden_earth_snake_island_v6"
OUT_MP4 = RAW_DIR / "snake_island_density_trap_v6.mp4"

FONT_BOLD = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS = 1080, 1920, 30
DURATION_S = 8.0
TOTAL_FRAMES = int(round(DURATION_S * FPS))


def _interp_curve(pts: list[tuple[float, float]], xs: np.ndarray) -> np.ndarray:
    px = np.array([p[0] for p in pts], dtype=np.float64)
    py = np.array([p[1] for p in pts], dtype=np.float64)
    return np.interp(xs, px, py)


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xs = np.arange(W, dtype=np.float64)

    # Dark moody slate-emerald background (0 blackdetect trigger: min RGB ~14,18,22)
    bg_top = np.array([14, 20, 26], dtype=np.float32)
    bg_mid = np.array([18, 28, 34], dtype=np.float32)
    t_bg = np.clip(yy / float(H), 0.0, 1.0)[..., None]
    base_bg = bg_top * (1.0 - t_bg) + bg_mid * t_bg

    # Continental shelf profile: Mainland Brazil (left x=0..250) -> drowned bridge (x=250..690) -> Queimada Grande peak (x=760..920)
    land_y = _interp_curve(
        [
            (0, 445),
            (150, 458),
            (255, 520),
            (370, 598),
            (515, 612),
            (655, 590),
            (735, 505),
            (795, 422),
            (835, 408),
            (880, 434),
            (945, 545),
            (1020, 628),
            (1080, 645),
        ],
        xs,
    )

    rng = np.random.default_rng(11000)
    rock_grain = rng.normal(0.0, 4.0, size=(H, W)).astype(np.float32)

    # Pre-generate 90 deterministic viper positions inside the 1-hectare tactical box (x=110..970, y=915..1235)
    viper_pts = []
    for idx in range(90):
        col = idx % 15
        row = idx // 15
        jx = float(rng.uniform(-16.0, 16.0))
        jy = float(rng.uniform(-12.0, 12.0))
        vx = 148.0 + col * 55.5 + jx
        vy = 948.0 + row * 50.0 + jy
        viper_pts.append((vx, vy, float(rng.uniform(0.0, 1.8))))

    f_kicker = ImageFont.truetype(FONT_BOLD, 20)
    f_title = ImageFont.truetype(FONT_BOLD, 40)
    f_label_b = ImageFont.truetype(FONT_BOLD, 26)
    f_label_m = ImageFont.truetype(FONT_MED, 21)
    f_big_num = ImageFont.truetype(FONT_BOLD, 44)
    f_small = ImageFont.truetype(FONT_MED, 18)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{W}x{H}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "15",
        "-pix_fmt",
        "yuv420p",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    for fn in range(TOTAL_FRAMES):
        t = fn / float(FPS)
        # Sea rises smoothly over first 3.2 seconds from y=606 (11,000 BP) to y=508 (Today)
        rise_prog = min(1.0, max(0.0, (t - 0.15) / 3.0))
        rise_smooth = rise_prog * rise_prog * (3.0 - 2.0 * rise_prog)
        sea_level_y = 604.0 - 94.0 * rise_smooth + 2.2 * np.sin(xs / 48.0 + t * 2.4)

        frame_arr = base_bg.copy()

        # Paint ocean water inside geological cutaway panel (y=320..735)
        in_panel = (yy >= 320.0) & (yy <= 735.0)
        in_water = in_panel & (yy >= sea_level_y[None, :]) & (yy < land_y[None, :])
        depth_t = np.clip((yy - sea_level_y[None, :]) / 135.0, 0.0, 1.0)[..., None]
        w_surf = np.array([26, 112, 134], dtype=np.float32)
        w_deep = np.array([12, 44, 62], dtype=np.float32)
        frame_arr = np.where(in_water[..., None], w_surf * (1.0 - depth_t) + w_deep * depth_t, frame_arr)

        # Paint continental bedrock & rainforest cap on Mainland + Snake Island
        in_rock = in_panel & (yy >= land_y[None, :])
        rock_t = np.clip((yy - land_y[None, :]) / 220.0, 0.0, 1.0)[..., None]
        r_top = np.array([64, 72, 66], dtype=np.float32)
        r_bot = np.array([32, 36, 40], dtype=np.float32)
        rock_col = r_top * (1.0 - rock_t) + r_bot * rock_t + (0.55 * rock_grain)[..., None]

        # Forest canopy cap above modern sea level
        in_canopy = in_rock & (yy < land_y[None, :] + 18.0) & (land_y[None, :] < sea_level_y[None, :] + 4.0)
        canopy_col = np.array([46, 108, 64], dtype=np.float32)
        rock_col = np.where(in_canopy[..., None], canopy_col, rock_col)
        frame_arr = np.where(in_rock[..., None], rock_col, frame_arr)

        # Subtle caption-zone darkening at bottom while staying safely above blackdetect threshold
        t_cap = np.clip((yy - 1310.0) / 520.0, 0.0, 1.0)[..., None]
        frame_arr = frame_arr * (1.0 - 0.35 * t_cap) + np.array([14, 18, 24], dtype=np.float32) * (0.35 * t_cap)

        img = Image.fromarray(np.clip(frame_arr, 0, 255).astype(np.uint8), mode="RGB")
        d = ImageDraw.Draw(img, "RGBA")

        # Header
        d.text((74, 146), "ILLUSTRATIVE MODEL • INSTITUTO BUTANTAN SURVEY DATA", font=f_kicker, fill=(242, 188, 74, 245))
        d.text((74, 178), "HOW 4,000 VIPERS GOT TRAPPED", font=f_title, fill=(246, 250, 252, 255))

        # Cutaway panel border
        d.rounded_rectangle((64, 316, 1016, 738), radius=16, outline=(88, 118, 132, 165), width=2)

        # Sea surface highlight line
        sea_pts = [(int(x), int(sea_level_y[int(x)])) for x in range(66, 1014, 6)]
        d.line(sea_pts, fill=(96, 214, 236, 220), width=3)

        # Labels on Mainland & Snake Island
        d.text((88, 398), "MAINLAND BRAZIL", font=f_label_b, fill=(232, 240, 244, 245))
        d.text((704, 344), "SNAKE ISLAND", font=f_label_b, fill=(255, 206, 86, 255))
        d.text((704, 376), "43 Hectares • Zero Mammals", font=f_small, fill=(214, 226, 232, 235))

        # 33 km distance arrow once flooded
        if rise_smooth > 0.35:
            al = int(235 * min(1.0, (rise_smooth - 0.35) / 0.45))
            d.line([(268, 492), (728, 492)], fill=(255, 214, 102, al), width=2)
            d.text((386, 462), "33 KM DROWNED LAND BRIDGE", font=f_small, fill=(255, 220, 120, al))

        yr_val = int(round(11000 * (1.0 - rise_smooth)))
        yr_lbl = f"{yr_val:,} YEARS AGO" if yr_val > 250 else "PRESENT DAY — ISOLATED"
        d.rounded_rectangle((84, 672, 412, 718), radius=8, fill=(12, 20, 28, 215), outline=(96, 214, 236, 150), width=1)
        d.text((102, 683), yr_lbl, font=f_label_m, fill=(148, 232, 248, 250))

        # Lower Panel: Real Survey Density Grid (Up to 90 Golden Lanceheads per Hectare)
        d.rounded_rectangle((64, 792, 1016, 1272), radius=18, fill=(16, 22, 28, 230), outline=(218, 92, 68, 185), width=2)
        d.text((92, 818), "FIELD SURVEY DENSITY (1 HECTARE = 100m × 100m)", font=f_kicker, fill=(255, 132, 102, 245))
        d.text((92, 850), "UP TO 90 DEADLY VIPERS PER HECTARE", font=f_big_num, fill=(255, 244, 236, 255))

        # Subtle grid lines inside 1-hectare box
        gx0, gy0, gx1, gy1 = 96, 916, 984, 1244
        d.rectangle((gx0, gy0, gx1, gy1), fill=(20, 28, 26, 240), outline=(72, 92, 84, 160), width=1)
        for gx in range(gx0 + 88, gx1, 88):
            d.line([(gx, gy0), (gx, gy1)], fill=(44, 58, 52, 110), width=1)
        for gy in range(gy0 + 65, gy1, 65):
            d.line([(gx0, gy), (gx1, gy)], fill=(44, 58, 52, 110), width=1)

        # Reveal up to 90 pulsing amber-red viper markers
        active_count = int(min(90, max(12, round(18 + 72 * min(1.0, t / 3.6)))))
        for idx in range(active_count):
            vx, vy, ph = viper_pts[idx]
            pulse = 0.5 + 0.5 * math.sin(t * 5.2 + ph)
            r_glow = int(9 + 4 * pulse)
            d.ellipse((vx - r_glow, vy - r_glow, vx + r_glow, vy + r_glow), fill=(235, 78, 48, int(68 + 65 * pulse)))
            d.ellipse((vx - 5, vy - 5, vx + 5, vy + 5), fill=(255, 206, 76, 252))

        d.text((96, 1288), "Source: Instituto Butantan population surveys (~2,000–4,000 Bothrops insularis across 43 ha)", font=f_small, fill=(168, 184, 194, 215))

        proc.stdin.write(img.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    return out_mp4


if __name__ == "__main__":
    out = build_diagram_mp4()
    print(f"Generated {out} ({out.stat().st_size / (1024*1024):.2f} MB)")
