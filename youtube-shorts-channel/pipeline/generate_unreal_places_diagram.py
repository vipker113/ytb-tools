#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 scientific diagram
for 3 Places on Earth That Look Fake (`pow_documentary_v3` v4.0):
`assets/raw_footage/hidden_earth_unreal_places_v4/unreal_places_extremes_v4.mp4`

Compares the three extreme geophysical mechanisms over real CC BY 2.5 Dallol hydrothermal
mineral texture (`dallol_pools_ccby.jpg`):
1. Kawah Ijen (Indonesia): 600°C sulfur gas ignites in air & flows as burning liquid sulfur.
2. Dallol (Ethiopia): Shallow magma boils iron-rich sulfuric brines below pH 0 — zero microbes.
3. Naica Crystal Cave (Mexico): 58°C & 95% humidity — hotter than lungs, condensing water inside airways.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Applications/code/science-knowledge/youtube-shorts-channel")
RAW = ROOT / "assets" / "raw_footage" / "hidden_earth_unreal_places_v4"
OUT_MP4 = RAW / "unreal_places_extremes_v4.mp4"
BG_TEX = RAW / "dallol_pools_ccby.jpg"
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
    fm_cite = ImageFont.truetype(FONT_MED, 17)

    src = Image.open(BG_TEX).convert("RGB")
    sw, sh = src.size
    crop_w = int(sh * (9.0 / 16.0))
    x0 = max(0, (sw - crop_w) // 2)
    tex_crop = src.crop((x0, 0, x0 + crop_w, sh)).resize((W, H), Image.Resampling.LANCZOS)
    tex_arr = np.asarray(tex_crop, dtype=np.float32)

    y_norm = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    slate_tint = np.concatenate(
        [
            10.0 + 10.0 * y_norm,
            15.0 + 12.0 * y_norm,
            24.0 + 14.0 * y_norm,
        ],
        axis=2,
    )
    bg_rgb = np.clip(tex_arr * 0.25 + slate_tint, 10.0, 255.0)

    bands = [
        {
            "y0": 395,
            "y1": 655,
            "accent": (74, 190, 255),
            "fill": (14, 34, 58),
            "header": "1. KAWAH IJEN • 600°C SULFUR GAS",
            "cause": "Physics: Pressurized sulfur gas ignites on contact with air",
            "outcome": "Result: Condenses into burning electric-blue liquid rivers",
            "reveal_s": 0.15,
        },
        {
            "y0": 700,
            "y1": 960,
            "accent": (182, 248, 78),
            "fill": (34, 44, 14),
            "header": "2. DALLOL POOLS • NEGATIVE pH (< 0)",
            "cause": "Physics: Shallow magma boils iron salts & sulfuric acid",
            "outcome": "Result: Zero active microbial life even in liquid water",
            "reveal_s": 1.35,
        },
        {
            "y0": 1005,
            "y1": 1265,
            "accent": (255, 178, 72),
            "fill": (48, 28, 16),
            "header": "3. NAICA CAVE • 58°C & 95% HUMIDITY",
            "cause": "Physics: Air inside is hotter than 37°C human lungs",
            "outcome": "Result: Water vapor condenses directly inside airways",
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
        shift_px = int(round(10.0 * math.sin(t * 0.35)))
        rolled = np.roll(bg_rgb, shift_px, axis=0)
        im = Image.fromarray(rolled.astype(np.uint8)).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        od.text((74, 232), "EXTREME TERRESTRIAL CHEMISTRY", font=fb_kicker, fill=(178, 202, 228, 235))
        od.text((74, 268), "Why Humans Barely Survive Inside", font=fb_title, fill=(250, 252, 255, 255))
        od.line([(74, 332), (1006, 332)], fill=(168, 190, 216, 135), width=2)

        for b in bands:
            dt = max(0.0, t - b["reveal_s"])
            alpha_f = min(1.0, dt / 0.55) if t >= b["reveal_s"] else 0.18
            y0, y1 = b["y0"], b["y1"]
            ar, ag, ab = b["accent"]
            fr, fg, fb_c = b["fill"]

            od.rectangle((0, y0, W, y1), fill=(fr, fg, fb_c, int(176 * alpha_f)))
            bar_w = 10
            od.rectangle((64, y0 + 18, 64 + bar_w, y1 - 18), fill=(ar, ag, ab, int(245 * alpha_f)))

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

        od.text(
            (74, 1308),
            "Sources: JVGR (2000) • Nature Ecology & Evolution (2019) • Geology (2007) • PNAS (2011)",
            font=fm_cite,
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
