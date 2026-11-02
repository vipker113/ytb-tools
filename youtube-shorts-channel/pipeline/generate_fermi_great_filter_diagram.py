#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 scientific diagram
for The Fermi Paradox & The Great Filter (`pow_documentary_v3` v4.0 standard):
`assets/raw_footage/space_and_universe_fermi_paradox_v4/great_filter_bottleneck_v4.mp4`

Illustrates Robin Hanson's (1998) Great Filter probability bottleneck over real ESO CC BY 4.0
Milky Way starfield texture:
1. Hundreds of millions of rocky habitable-zone worlds (Bryson et al., AJ 2021) enter from top.
2. Nearly all evolutionary trajectories halt at a critical bottleneck ("The Great Filter").
3. Either the bottleneck lies behind us (rare leap to complex brains) or ahead of us (technological self-destruction).
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Applications/code/science-knowledge/youtube-shorts-channel")
RAW = ROOT / "assets" / "raw_footage" / "space_and_universe_fermi_paradox_v4"
OUT_MP4 = RAW / "great_filter_bottleneck_v4.mp4"
STAR_TEX = RAW / "eso_potw1036a_vlt_laser_milky_way.jpg"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

W, H, FPS = 1080, 1920, 30
DUR_S = 7.2
NFRAMES = int(DUR_S * FPS)


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fb_kicker = ImageFont.truetype(FONT_MED, 22)
    fb_title = ImageFont.truetype(FONT_BOLD, 36)
    fb_lbl = ImageFont.truetype(FONT_BOLD, 25)
    fm_lbl = ImageFont.truetype(FONT_MED, 21)

    # Real Milky Way starfield crop from top half of ESO CC BY 4.0 image (avoiding ground dome)
    src = Image.open(STAR_TEX).convert("RGB")
    sw, sh = src.size
    star_crop = src.crop((int(sw * 0.12), 0, int(sw * 0.44), int(sh * 0.56))).resize(
        (W, H), Image.Resampling.LANCZOS
    )
    star_arr = np.asarray(star_crop, dtype=np.float32)
    # Deepen exposure into rich documentary night sky (mean luma ~20, full edge-to-edge starfield)
    bg_rgb = np.clip(star_arr * 0.42 + np.array([6.0, 8.0, 14.0], dtype=np.float32), 9.0, 255.0)

    rng = np.random.default_rng(20261031)
    n_tracks = 54
    track_x0 = rng.uniform(110.0, 970.0, size=n_tracks)
    track_phase = rng.uniform(0.0, 1.0, size=n_tracks)
    track_speed = rng.uniform(0.24, 0.34, size=n_tracks)
    track_sway = rng.uniform(-28.0, 28.0, size=n_tracks)

    filter_y = 770.0
    gap_x = 540.0

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
        "-i", "-",
        "-frames:v", str(NFRAMES),
        "-c:v", "libx264", "-preset", "medium", "-crf", "15", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None

    for fi in range(NFRAMES):
        t = fi / float(FPS)
        im = Image.fromarray(bg_rgb.astype(np.uint8)).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        # Subtle funnel guide lines converging toward the Great Filter bottleneck
        od.line([(120, 285), (492, int(filter_y))], fill=(140, 165, 205, 52), width=2)
        od.line([(960, 285), (588, int(filter_y))], fill=(140, 165, 205, 52), width=2)

        # Horizontal Great Filter barrier with narrow central survival aperture (x=514..566)
        pulse = 0.84 + 0.16 * math.sin(t * 2.8)
        glow_a = int(68 * pulse)
        od.rectangle((68, int(filter_y - 14), 512, int(filter_y + 14)), fill=(225, 86, 62, glow_a))
        od.rectangle((568, int(filter_y - 14), 1012, int(filter_y + 14)), fill=(225, 86, 62, glow_a))
        od.line([(68, int(filter_y)), (512, int(filter_y))], fill=(255, 132, 92, 235), width=5)
        od.line([(568, int(filter_y)), (1012, int(filter_y))], fill=(255, 132, 92, 235), width=5)

        # Many rocky-world trajectories approaching & halting at the Great Filter
        for i in range(n_tracks):
            u = (track_phase[i] + t * track_speed[i]) % 1.0
            y_cur = 285.0 + u * (filter_y - 293.0)
            # Gently converge x toward the barrier band
            x_cur = track_x0[i] * (1.0 - 0.36 * u) + gap_x * (0.36 * u) + track_sway[i] * math.sin(u * math.pi)
            if abs(x_cur - gap_x) < 34.0:
                x_cur += 46.0 if (i % 2 == 0) else -46.0
            fade = min(1.0, (1.0 - u) * 3.8)
            alpha = int(195 * fade)
            y_tail = max(285.0, y_cur - 44.0)
            x_tail = track_x0[i] * (1.0 - 0.36 * max(0.0, u - 0.09)) + gap_x * (0.36 * max(0.0, u - 0.09))
            od.line([(x_tail, y_tail), (x_cur, y_cur)], fill=(255, 224, 152, int(alpha * 0.65)), width=2)
            od.ellipse((x_cur - 4, y_cur - 4, x_cur + 4, y_cur + 4), fill=(255, 236, 185, alpha))

        # Single rare Pale-Blue-Dot survivor trajectory threading cleanly through the bottleneck
        surv_u = min(1.0, 0.18 + t / (DUR_S * 0.85))
        surv_y_end = 285.0 + surv_u * (1260.0 - 285.0)
        od.line([(gap_x, 285.0), (gap_x, surv_y_end)], fill=(108, 206, 255, 228), width=4)
        od.ellipse(
            (gap_x - 8, surv_y_end - 8, gap_x + 8, surv_y_end + 8),
            fill=(185, 238, 255, 255),
        )

        im = Image.alpha_composite(im, ov)
        d = ImageDraw.Draw(im)

        # Clean borderless documentary typography (strictly within safe margins x=68..1000, y<1320)
        d.text((68, 126), "THE GREAT FILTER • EVOLUTIONARY BOTTLENECK", font=fb_kicker, fill=(255, 212, 78, 238))
        d.text((68, 160), "Why 300 Million Worlds Stay Silent", font=fb_title, fill=(248, 250, 252, 252))

        d.text((68, 342), "300,000,000+ HABITABLE ROCKY WORLDS", font=fb_lbl, fill=(255, 228, 150, 242))
        d.text((68, 374), "Kepler data shows sun-like stars commonly host Earth-sized worlds", font=fm_lbl, fill=(204, 214, 228, 228))

        d.text((68, 692), "THE GREAT FILTER BARRIER", font=fb_lbl, fill=(255, 142, 104, 248))
        d.text((68, 724), "Nearly every trajectory stalls before reaching starflight", font=fm_lbl, fill=(236, 210, 202, 232))

        d.text((68, 868), "IF BEHIND US: RARE COMPLEX LIFE", font=fb_lbl, fill=(138, 216, 255, 245))
        d.text((68, 900), "Microbes stalled ~2 billion years before complex cells emerged", font=fm_lbl, fill=(208, 224, 238, 230))

        d.text((68, 1022), "IF AHEAD OF US: SELF-DESTRUCTION", font=fb_lbl, fill=(255, 198, 88, 245))
        d.text((68, 1054), "Technological species may perish before leaving their home star", font=fm_lbl, fill=(228, 224, 212, 230))

        rgb = np.asarray(im.convert("RGB"), dtype=np.float32)
        grain = rng.normal(0.0, 2.3, size=(H, W, 1)).astype(np.float32)
        rgb = np.clip(rgb + grain, 0.0, 255.0).astype(np.uint8)
        proc.stdin.write(rgb.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with {rc}")
    return out_mp4


if __name__ == "__main__":
    p = build_diagram_mp4()
    print(f"Generated {p} ({p.stat().st_size / 1e6:.2f} MB)")
