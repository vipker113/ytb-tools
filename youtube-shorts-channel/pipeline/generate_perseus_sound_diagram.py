#!/usr/bin/env python3
"""
Generate a 100% first-party original vertical (1080x1920 @ 30fps) acoustic physics
visualization for the Perseus Black Hole Sound documentary (`Studio v6.0`):
`assets/raw_footage/space_perseus_black_hole_v6/perseus_57_octaves_diagram_v6.mp4`

Illustrates two peer-reviewed NASA Chandra datasets (Fabian et al., MNRAS 2003; NASA 2022):
1. Concentric X-ray pressure ripples (~30,000 light-year wavelength, ~9.6M-year period)
   driven by relativistic black hole cavities through Perseus Cluster superheated plasma.
2. Acoustic frequency scale plunging 57 octaves below middle C (261.6 Hz) —
   144 quadrillion times below the human hearing floor.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "assets" / "raw_footage" / "space_perseus_black_hole_v6"
OUT_MP4 = RAW_DIR / "perseus_57_octaves_diagram_v6.mp4"

FONT_BOLD = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS = 1080, 1920, 30
DURATION_S = 8.0
TOTAL_FRAMES = int(round(DURATION_S * FPS))


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    f_kicker = ImageFont.truetype(FONT_BOLD, 24)
    f_title = ImageFont.truetype(FONT_BOLD, 40)
    f_sub = ImageFont.truetype(FONT_MED, 25)
    f_label = ImageFont.truetype(FONT_BOLD, 28)
    f_small = ImageFont.truetype(FONT_MED, 22)
    f_big = ImageFont.truetype(FONT_BOLD, 54)

    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # Precompute base cosmic deep-space nebula gradient + seeded starfield
    # (ensures rich visual texture across all 1920 rows with zero flat black bands)
    bg_f = np.zeros((H, W, 3), dtype=np.float32)
    norm_y = yy / float(H)
    radial_bg = np.exp(-(((xx - 540.0) / 680.0) ** 2 + ((yy - 960.0) / 1050.0) ** 2))
    lower_nebula = np.exp(-(((xx - 540.0) / 620.0) ** 2 + ((yy - 1680.0) / 360.0) ** 2))
    bg_f[:, :, 0] = 22.0 + 14.0 * (1.0 - norm_y) + 18.0 * radial_bg + 26.0 * lower_nebula
    bg_f[:, :, 1] = 24.0 + 16.0 * (1.0 - norm_y) + 14.0 * radial_bg + 16.0 * lower_nebula
    bg_f[:, :, 2] = 42.0 + 28.0 * (1.0 - norm_y) + 26.0 * radial_bg + 30.0 * lower_nebula

    rng = np.random.default_rng(200309)
    for _ in range(520):
        sx = int(rng.integers(12, W - 12))
        sy = int(rng.integers(12, H - 12))
        sb = float(rng.uniform(55.0, 165.0))
        sr = 1 if sb < 110.0 else 2
        y0, y1 = max(0, sy - sr), min(H, sy + sr + 1)
        x0, x1 = max(0, sx - sr), min(W, sx + sr + 1)
        bg_f[y0:y1, x0:x1, 0] += sb * 0.92
        bg_f[y0:y1, x0:x1, 1] += sb * 0.96
        bg_f[y0:y1, x0:x1, 2] += sb * 1.10

    bg = np.clip(bg_f, 0, 255).astype(np.uint8)

    # Upper panel center for Perseus X-ray acoustic ripple field
    cx, cy = 540.0, 562.0
    rr = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)

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

    for fi in range(TOTAL_FRAMES):
        t = fi / float(FPS)
        frame = bg.copy().astype(np.float32)

        # Animated concentric X-ray pressure waves inside top panel (y=292..832)
        mask_top = (yy >= 292) & (yy <= 832) & (xx >= 70) & (xx <= 1010)
        envelope = np.exp(-((rr / 320.0) ** 1.65))
        wave_phase = np.sin((rr / 54.0) * (2.0 * math.pi) - t * 3.1)
        ripple = (0.55 + 0.45 * wave_phase) * envelope

        # Warm Chandra X-ray crimson/gold palette
        r_add = 215.0 * ripple + 90.0 * np.exp(-((rr / 48.0) ** 2))
        g_add = 68.0 * (ripple ** 1.35) + 145.0 * np.exp(-((rr / 32.0) ** 2))
        b_add = 38.0 * (ripple ** 1.8) + 185.0 * np.exp(-((rr / 20.0) ** 2))

        frame[:, :, 0] = np.where(mask_top, np.clip(frame[:, :, 0] + r_add, 0, 255), frame[:, :, 0])
        frame[:, :, 1] = np.where(mask_top, np.clip(frame[:, :, 1] + g_add, 0, 255), frame[:, :, 1])
        frame[:, :, 2] = np.where(mask_top, np.clip(frame[:, :, 2] + b_add, 0, 255), frame[:, :, 2])

        img = Image.fromarray(frame.astype(np.uint8))
        draw = ImageDraw.Draw(img, "RGBA")

        # Header (shifted cleanly below top-left context_note safe zone)
        draw.text((76, 166), "CHANDRA X-RAY ACOUSTIC DATA  |  PERSEUS CLUSTER", fill=(255, 176, 92, 235), font=f_kicker)
        draw.text((76, 200), "57 OCTAVES BELOW MIDDLE C", fill=(248, 250, 255, 255), font=f_title)
        draw.text((76, 248), "250 million light-years away  •  Superheated 10,000,000°C gas", fill=(182, 196, 220, 230), font=f_sub)

        # Top card border & wavelength callout
        draw.rounded_rectangle((70, 292, 1010, 832), radius=24, outline=(255, 140, 82, 145), width=2)
        # Wavelength bracket between two ripple crests
        r1 = 108
        r2 = 162
        y_br = int(cy)
        draw.line((int(cx + r1), y_br, int(cx + r2), y_br), fill=(255, 224, 130, 240), width=4)
        draw.line((int(cx + r1), y_br - 12, int(cx + r1), y_br + 12), fill=(255, 224, 130, 240), width=3)
        draw.line((int(cx + r2), y_br - 12, int(cx + r2), y_br + 12), fill=(255, 224, 130, 240), width=3)
        draw.rounded_rectangle((718, 520, 988, 604), radius=12, fill=(10, 14, 26, 215), outline=(255, 214, 110, 180), width=2)
        draw.text((736, 532), "~30,000 LIGHT-YEARS", fill=(255, 222, 120, 255), font=f_small)
        draw.text((736, 562), "1 wave = ~9.6M years", fill=(214, 225, 242, 235), font=f_small)

        draw.text((98, 314), "X-RAY PRESSURE RIPPLES (NGC 1275 BLACK HOLE)", fill=(255, 236, 214, 240), font=f_small)
        draw.ellipse((int(cx - 10), int(cy - 10), int(cx + 10), int(cy + 10)), fill=(255, 255, 255, 255))

        # Bottom card: Frequency Scale Plunge (y=860..1392 — leaves y=1420..1560 subtitle zone 100% unobstructed)
        draw.rounded_rectangle((70, 860, 1010, 1392), radius=24, fill=(14, 20, 38, 228), outline=(112, 154, 235, 140), width=2)
        draw.text((100, 886), "FREQUENCY COMPARISON  (LOGARITHMIC OCTAVE SCALE)", fill=(150, 192, 255, 235), font=f_small)

        # Vertical scale spine
        spine_x = 185
        y_top_scale = 966
        y_bot_scale = 1318
        draw.line((spine_x, y_top_scale, spine_x, y_bot_scale), fill=(88, 116, 168, 200), width=6)

        # Animated drop progress (0..1 over first 2.6s, then gentle pulse)
        prog = min(1.0, t / 2.4)
        prog_smooth = 1.0 - (1.0 - prog) ** 3
        cur_y = int(y_top_scale + (y_bot_scale - y_top_scale) * prog_smooth)
        draw.line((spine_x, y_top_scale, spine_x, cur_y), fill=(255, 132, 74, 245), width=8)

        # 3 benchmark nodes
        nodes = [
            (966, "MIDDLE C  (PIANO)", "261.6 Hz  •  Human musical reference", (132, 210, 255, 255)),
            (1082, "HUMAN HEARING FLOOR", "20 Hz  •  Lowest sound ears detect", (180, 224, 255, 245)),
            (1318, "PERSEUS BLACK HOLE  (B-FLAT)", "57 octaves below  •  144 quadrillion× lower", (255, 146, 84, 255)),
        ]
        for ny, ntitle, nsub, ncol in nodes:
            active = cur_y >= ny - 6
            r_dot = 13 if active else 9
            draw.ellipse((spine_x - r_dot, ny - r_dot, spine_x + r_dot, ny + r_dot), fill=ncol if active else (90, 105, 135, 200))
            draw.text((230, ny - 26), ntitle, fill=ncol if active else (150, 164, 190, 190), font=f_label)
            draw.text((230, ny + 10), nsub, fill=(215, 226, 245, 230) if active else (128, 140, 165, 175), font=f_small)

        # Mid-drop badge "-57 OCTAVES"
        pulse = int(215 + 38 * math.sin(t * 4.2))
        draw.rounded_rectangle((230, 1148, 805, 1246), radius=16, fill=(36, 18, 22, 235), outline=(255, 138, 76, pulse), width=3)
        draw.text((256, 1162), "-57 OCTAVES", fill=(255, 186, 92, 255), font=f_big)
        draw.text((682, 1182), "DROP", fill=(255, 226, 182, 240), font=f_label)

        proc.stdin.write(np.asarray(img, dtype=np.uint8).tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    return out_mp4


if __name__ == "__main__":
    p = build_diagram_mp4()
    print(f"Generated diagram: {p} ({p.stat().st_size / (1024*1024):.2f} MB)")
