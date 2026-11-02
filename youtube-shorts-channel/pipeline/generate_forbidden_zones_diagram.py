#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 scientific diagram
for Earth's Strictest Forbidden Zones (`pow_documentary_v3` v4.0):
`assets/raw_footage/hidden_earth_forbidden_zones_v4/forbidden_zones_comparison_v4.mp4`

Compares the three inverted scientific mechanisms behind Earth's strictest human bans
over real CC BY 2.0 Surtsey volcanic basalt & North Atlantic texture (`surtsey_island_ccby.jpg`):
1. Chernobyl Exclusion Zone (2,600 km²): Sealed to protect humans from fallout — wildlife & melanin fungi thrive.
2. Lascaux Cave (17,000-yr art): Sealed because human breath (CO2, heat & spores) feeds wall-destroying fungi.
3. Surtsey Island (born 1963): Quarantined from birth so scientists can observe life colonizing barren lava from zero.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Applications/code/science-knowledge/youtube-shorts-channel")
RAW = ROOT / "assets" / "raw_footage" / "hidden_earth_forbidden_zones_v4"
OUT_MP4 = RAW / "forbidden_zones_comparison_v4.mp4"
BG_TEX = RAW / "surtsey_island_ccby.jpg"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

W, H, FPS = 1080, 1920, 30
DUR_S = 8.4
NFRAMES = int(round(DUR_S * FPS))


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fb_kicker = ImageFont.truetype(FONT_MED, 22)
    fb_title = ImageFont.truetype(FONT_BOLD, 38)
    fb_zone = ImageFont.truetype(FONT_BOLD, 27)
    fm_body = ImageFont.truetype(FONT_MED, 22)
    fb_out = ImageFont.truetype(FONT_BOLD, 22)

    src = Image.open(BG_TEX).convert("RGB")
    sw, sh = src.size
    crop_w = int(sh * (9.0 / 16.0))
    x0 = max(0, (sw - crop_w) // 2)
    tex_crop = src.crop((x0, 0, x0 + crop_w, sh)).resize((W, H), Image.Resampling.LANCZOS)
    tex_arr = np.asarray(tex_crop, dtype=np.float32)

    y_norm = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    slate_tint = np.concatenate(
        [
            12.0 + 10.0 * y_norm,
            16.0 + 12.0 * y_norm,
            24.0 + 14.0 * y_norm,
        ],
        axis=2,
    )
    bg_rgb = np.clip(tex_arr * 0.28 + slate_tint, 10.0, 255.0)

    bands = [
        {
            "y0": 395,
            "y1": 655,
            "accent": (255, 146, 72),
            "fill": (48, 24, 18),
            "header": "1. CHERNOBYL ZONE • 2,600 KM²",
            "cause": "Threat: Fallout & reactor gamma rays bar normal life",
            "outcome": "Flip: Gray wolves, wild horses & melanin fungi thrive",
            "reveal_s": 0.15,
        },
        {
            "y0": 700,
            "y1": 960,
            "accent": (88, 204, 255),
            "fill": (16, 36, 52),
            "header": "2. LASCAUX CAVE • SEALED SINCE 1963",
            "cause": "Threat: Human breath adds CO2, heat & fungal spores",
            "outcome": "Flip: Humans banned to save 17,000-year cave art",
            "reveal_s": 1.35,
        },
        {
            "y0": 1005,
            "y1": 1265,
            "accent": (98, 232, 156),
            "fill": (16, 44, 32),
            "header": "3. SURTSEY ISLAND • BORN IN 1963",
            "cause": "Threat: Even one seed on a human boot ruins the test",
            "outcome": "Flip: Gulls & waves build a 60-species world from zero",
            "reveal_s": 2.55,
        },
    ]

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
        "-frames:v",
        str(NFRAMES),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "15",
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    for fi in range(NFRAMES):
        t = fi / float(FPS)
        # Subtle slow vertical drift on textured background so frame-delta motion is ultra-smooth
        shift_px = int(round(10.0 * math.sin(t * 0.35)))
        rolled = np.roll(bg_rgb, shift_px, axis=0)
        im = Image.fromarray(rolled.astype(np.uint8)).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        # Header block (clean borderless typography inside safe zone y >= 225)
        od.text((74, 232), "EARTH'S STRICTEST QUARANTINES", font=fb_kicker, fill=(178, 202, 228, 235))
        od.text((74, 268), "Why Humans Are Locked Out", font=fb_title, fill=(250, 252, 255, 255))
        od.line([(74, 332), (1006, 332)], fill=(168, 190, 216, 135), width=2)

        for b in bands:
            dt = max(0.0, t - b["reveal_s"])
            alpha_f = min(1.0, dt / 0.55) if t >= b["reveal_s"] else 0.18
            y0, y1 = b["y0"], b["y1"]
            ar, ag, ab = b["accent"]
            fr, fg, fb_c = b["fill"]

            # Clean translucent horizontal band (full-width architectural strip, zero inset border box)
            od.rectangle((0, y0, W, y1), fill=(fr, fg, fb_c, int(172 * alpha_f)))
            # Left vertical accent bar
            bar_w = 10
            od.rectangle((64, y0 + 18, 64 + bar_w, y1 - 18), fill=(ar, ag, ab, int(245 * alpha_f)))

            # Subtle animated progress rule along bottom of active band
            prog = min(1.0, max(0.08, (t - b["reveal_s"]) / 3.2)) if t >= b["reveal_s"] else 0.08
            od.line(
                [(64, y1 - 2), (64 + int(942 * prog), y1 - 2)],
                fill=(ar, ag, ab, int(195 * alpha_f)),
                width=3,
            )

            tx = 96
            od.text((tx, y0 + 26), b["header"], font=fb_zone, fill=(ar, ag, ab, int(255 * alpha_f)))
            od.text((tx, y0 + 78), b["cause"], font=fm_body, fill=(230, 236, 245, int(245 * alpha_f)))
            od.text((tx, y0 + 122), b["outcome"], font=fb_out, fill=(252, 253, 255, int(255 * alpha_f)))

            # Source citation note in subtle muted text
        od.text(
            (74, 1308),
            "Sources: Current Biology (2015) • PLOS ONE (2007) • Microbiology (2010) • Surtsey Research (2014)",
            font=ImageFont.truetype(FONT_MED, 17),
            fill=(176, 190, 208, 205),
        )

        comp = Image.alpha_composite(im, ov).convert("RGB")
        proc.stdin.write(comp.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg diagram encode failed with code {rc}")
    return out_mp4


if __name__ == "__main__":
    p = build_diagram_mp4()
    print(f"Rendered diagram: {p} ({p.stat().st_size / (1024 * 1024):.2f} MB)")
