#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 scientific diagram
for Gemstone Mines & Deep-Mantle Diamond Time Capsules (`pow_documentary_v3` v4.0):
`assets/raw_footage/hidden_earth_gemstone_mines_v4/deep_diamond_ice7_diagram_v4.mp4`

Illustrates deep-mantle diamond transport & inclusion preservation over real Public Domain
South African kimberlite rock texture (`diamond_in_kimberlite_pd.jpg`, Géry Parent):
1. Deepest human hard-rock mines reach < 4 km into continental crust.
2. Between 410 and 660+ km (Mantle Transition Zone & uppermost lower mantle), super-deep
   diamonds crystallize around hydrous ringwoodite (~1.4 wt% H2O, Pearson et al., Nature 2014)
   and high-pressure aqueous fluid that locks into cubic Ice-VII (Tschauner et al., Science 2018).
3. Fast kimberlite eruptions blast those diamonds to shallow mines intact as gigapascal capsules.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/Applications/code/science-knowledge/youtube-shorts-channel")
RAW = ROOT / "assets" / "raw_footage" / "hidden_earth_gemstone_mines_v4"
OUT_MP4 = RAW / "deep_diamond_ice7_diagram_v4.mp4"
ROCK_TEX = RAW / "diamond_in_kimberlite_pd.jpg"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

W, H, FPS = 1080, 1920, 30
DUR_S = 7.2
NFRAMES = int(DUR_S * FPS)


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fb_kicker = ImageFont.truetype(FONT_MED, 22)
    fb_title = ImageFont.truetype(FONT_BOLD, 35)
    fb_lbl = ImageFont.truetype(FONT_BOLD, 25)
    fm_lbl = ImageFont.truetype(FONT_MED, 21)

    # Crop textured kimberlite host rock (off-center so rough diamond highlight doesn't clash with text)
    src = Image.open(ROCK_TEX).convert("RGB")
    sw, sh = src.size
    rock_crop = src.crop((int(sw * 0.04), int(sh * 0.06), int(sw * 0.42), int(sh * 0.94))).resize(
        (W, H), Image.Resampling.LANCZOS
    )
    rock_arr = np.asarray(rock_crop, dtype=np.float32)

    # Vertical depth-temperature tint: cool slate crust at top -> warm deep-mantle glow below y=780
    y_norm = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None, None]
    warm_tint = np.concatenate(
        [
            10.0 + 26.0 * np.clip((y_norm - 0.35) / 0.65, 0.0, 1.0),
            12.0 + 10.0 * np.clip((y_norm - 0.35) / 0.65, 0.0, 1.0),
            16.0 - 4.0 * np.clip((y_norm - 0.35) / 0.65, 0.0, 1.0),
        ],
        axis=2,
    )
    bg_rgb = np.clip(rock_arr * 0.44 + warm_tint, 12.0, 255.0)

    rng = np.random.default_rng(20261030)
    n_plume = 38
    plume_phase = rng.uniform(0.0, 1.0, size=n_plume)
    plume_speed = rng.uniform(0.24, 0.38, size=n_plume)
    plume_offset = rng.uniform(-22.0, 22.0, size=n_plume)

    conduit_x = 835.0
    y_crust = 355.0
    y_mtz_top = 740.0
    y_mtz_bot = 1130.0

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

        # Subtle Mantle Transition Zone (410-660 km) hydrous mineral band
        pulse = 0.85 + 0.15 * math.sin(t * 2.4)
        od.rectangle(
            (68, int(y_mtz_top), 1012, int(y_mtz_bot)),
            fill=(36, 118, 168, int(44 * pulse)),
        )

        # Geological depth horizon markers (crustal base, 410 km, 660 km)
        od.line([(68, int(y_crust)), (1012, int(y_crust))], fill=(188, 198, 214, 120), width=2)
        od.line([(68, int(y_mtz_top)), (1012, int(y_mtz_top))], fill=(96, 198, 255, 190), width=3)
        od.line([(68, int(y_mtz_bot)), (1012, int(y_mtz_bot))], fill=(255, 156, 92, 195), width=3)

        # Vertical Kimberlite Volcanic Pipe Conduit on right side (x ~ 835)
        pipe_top_w = 54.0
        pipe_bot_w = 18.0
        od.polygon(
            [
                (conduit_x - pipe_top_w, y_crust - 48),
                (conduit_x + pipe_top_w, y_crust - 48),
                (conduit_x + pipe_bot_w, y_mtz_bot + 70),
                (conduit_x - pipe_bot_w, y_mtz_bot + 70),
            ],
            fill=(255, 136, 72, 46),
        )
        od.line(
            [(conduit_x - pipe_top_w, y_crust - 48), (conduit_x - pipe_bot_w, y_mtz_bot + 70)],
            fill=(255, 166, 96, 175),
            width=2,
        )
        od.line(
            [(conduit_x + pipe_top_w, y_crust - 48), (conduit_x + pipe_bot_w, y_mtz_bot + 70)],
            fill=(255, 166, 96, 175),
            width=2,
        )

        # Rising kimberlite magma streaks carrying deep crystals upward
        for i in range(n_plume):
            u = (plume_phase[i] + t * plume_speed[i]) % 1.0
            y_cur = (y_mtz_bot + 60.0) - u * ((y_mtz_bot + 60.0) - (y_crust - 40.0))
            half_w = pipe_bot_w + u * (pipe_top_w - pipe_bot_w)
            x_cur = conduit_x + (plume_offset[i] / 22.0) * (half_w * 0.72)
            alpha = int(185 * math.sin(u * math.pi))
            od.line([(x_cur, y_cur + 26.0), (x_cur, y_cur)], fill=(255, 204, 128, alpha), width=2)

        # Ascending octahedral super-deep diamond crystal enclosing blue Ice-VII / Ringwoodite core
        asc_u = min(1.0, 0.10 + (t / DUR_S) * 0.86)
        dy = (y_mtz_bot - 40.0) - asc_u * ((y_mtz_bot - 40.0) - (y_crust + 6.0))
        r_ext = 30.0
        diamond_pts = [
            (conduit_x, dy - r_ext * 1.25),
            (conduit_x + r_ext, dy),
            (conduit_x, dy + r_ext * 1.25),
            (conduit_x - r_ext, dy),
        ]
        od.polygon(diamond_pts, fill=(228, 244, 255, 225), outline=(255, 255, 255, 255))
        # Internal facet lines
        od.line([(conduit_x - r_ext, dy), (conduit_x + r_ext, dy)], fill=(175, 215, 245, 190), width=2)
        od.line([(conduit_x, dy - r_ext * 1.25), (conduit_x, dy + r_ext * 1.25)], fill=(175, 215, 245, 190), width=2)
        # Microscopic blue cubic Ice-VII / Ringwoodite inclusion locked at center
        inc_s = 8.0
        od.rectangle(
            (conduit_x - inc_s, dy - inc_s, conduit_x + inc_s, dy + inc_s),
            fill=(56, 188, 255, 255),
            outline=(225, 250, 255, 255),
        )

        im = Image.alpha_composite(im, ov)
        d = ImageDraw.Draw(im)

        # Clean left-aligned documentary typography (x=68..740, strictly above y=1320 subtitle safe zone)
        d.text((68, 122), "DEEP MANTLE TIME CAPSULES • 410–660 KM", font=fb_kicker, fill=(255, 212, 78, 240))
        d.text((68, 156), "How Mined Diamonds Trap Deep Water", font=fb_title, fill=(248, 250, 252, 252))

        d.text((68, 272), "HUMAN MINES STOP (< 4 KM DEEP)", font=fb_lbl, fill=(236, 242, 248, 242))
        d.text((68, 304), "Shallow gem mines tap cooled crust & kimberlite pipes", font=fm_lbl, fill=(202, 212, 226, 228))

        d.text((68, 505), "KIMBERLITE VOLCANIC ASCENT", font=fb_lbl, fill=(255, 186, 108, 245))
        d.text((68, 537), "Fast eruptions carry rough diamonds up before they melt", font=fm_lbl, fill=(228, 216, 204, 228))

        d.text((68, 774), "410–660 KM: TRANSITION ZONE", font=fb_lbl, fill=(116, 214, 255, 248))
        d.text((68, 806), "Ringwoodite locks ~1.4% water in crystal rock (Nature 2014)", font=fm_lbl, fill=(206, 230, 246, 232))

        d.text((68, 956), "ICE-VII INCLUSIONS (~24 GPa)", font=fb_lbl, fill=(152, 228, 255, 248))
        d.text((68, 988), "Diamond cages keep cubic high-pressure ice sealed (Science 2018)", font=fm_lbl, fill=(208, 232, 246, 232))

        d.text((68, 1166), "LOWER MANTLE (> 660 KM)", font=fb_lbl, fill=(255, 158, 104, 245))
        d.text((68, 1198), "Water stored inside minerals & fluid pockets—not open seas", font=fm_lbl, fill=(232, 214, 204, 228))

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
