#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 optical mechanism diagram
for Lava Cave Gold v4.0 (`pow_documentary_v3` Zero-AI-Smell standard):
`assets/raw_footage/hidden_earth_lava_cave_gold_v4/cave_gold_optics_v4.mp4`

Illustrates the exact physical/biological mechanism documented by NPS & Northup/Lavoie et al.:
1. Dark volcanic basalt cave ceiling (photo-textured from NPS Public Domain Golden Dome Cave).
2. Water-repellent (hydrophobic) Actinobacteria microbial mat feeding on rock minerals in darkness.
3. Condensed cave moisture beading into spherical micro-droplets instead of soaking flat.
4. Caver headlamp rays entering spherical droplets and retro-reflecting back as a metallic gold sheen.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "assets" / "raw_footage" / "hidden_earth_lava_cave_gold_v4"
OUT_MP4 = RAW / "cave_gold_optics_v4.mp4"
NPS_TEX = RAW / "nps_golden_dome_0.jpg"
FONT_BOLD = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS = 1080, 1920, 30
DUR_S = 6.0
NFRAMES = int(DUR_S * FPS)


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fb_kicker = ImageFont.truetype(FONT_MED, 22)
    fb_title = ImageFont.truetype(FONT_BOLD, 36)
    fb_lbl = ImageFont.truetype(FONT_BOLD, 25)
    fm_lbl = ImageFont.truetype(FONT_MED, 21)

    tex_src = Image.open(NPS_TEX).convert("L").resize((W, H), Image.Resampling.LANCZOS)
    tex_arr = np.asarray(tex_src, dtype=np.float32)
    tex_arr = (tex_arr - np.mean(tex_arr)) / (np.std(tex_arr) + 1e-5)

    yy = np.arange(H, dtype=np.float32)[:, None]
    depth_u = yy / float(H)

    # Pitch-dark humid cave air background with subtle optical haze
    cave_bg = np.zeros((H, W, 3), dtype=np.float32)
    cave_bg[:, :, 0] = 14.0 + 10.0 * (1.0 - depth_u) + tex_arr * 1.8
    cave_bg[:, :, 1] = 13.0 + 9.0 * (1.0 - depth_u) + tex_arr * 1.7
    cave_bg[:, :, 2] = 16.0 + 11.0 * (1.0 - depth_u) + tex_arr * 1.9
    cave_bg = np.clip(cave_bg, 0.0, 255.0)

    # Photo-textured dark vesicular basalt ceiling rock (top y=0..560)
    rock_rgb = np.zeros((H, W, 3), dtype=np.float32)
    rock_rgb[:, :, 0] = 44.0 + tex_arr * 13.5
    rock_rgb[:, :, 1] = 39.0 + tex_arr * 12.0
    rock_rgb[:, :, 2] = 36.0 + tex_arr * 10.8
    rock_img = Image.fromarray(np.clip(rock_rgb, 0, 255).astype(np.uint8)).convert("RGBA")

    rock_mask = Image.new("L", (W, H), 0)
    rm_d = ImageDraw.Draw(rock_mask)
    ceiling_poly = [(0, 0), (W, 0)]
    for x in range(W, -1, -12):
        ry = 515.0 + 18.0 * math.sin(x * 0.009) + 8.0 * math.cos(x * 0.023)
        ceiling_poly.append((x, ry))
    rm_d.polygon(ceiling_poly, fill=255)

    # Golden-ochre hydrophobic Actinobacteria mat coating ceiling
    mat_mask = Image.new("L", (W, H), 0)
    mm_d = ImageDraw.Draw(mat_mask)
    mat_poly = []
    for x in range(0, W + 1, 12):
        ry = 515.0 + 18.0 * math.sin(x * 0.009) + 8.0 * math.cos(x * 0.023)
        mat_poly.append((x, ry - 4))
    for x in range(W, -1, -12):
        ry = 578.0 + 18.0 * math.sin(x * 0.009) + 10.0 * math.sin(x * 0.031 + 1.1)
        mat_poly.append((x, ry))
    mm_d.polygon(mat_poly, fill=235)

    mat_rgb = np.zeros((H, W, 3), dtype=np.float32)
    mat_rgb[:, :, 0] = 192.0 + tex_arr * 22.0
    mat_rgb[:, :, 1] = 152.0 + tex_arr * 19.0
    mat_rgb[:, :, 2] = 42.0 + tex_arr * 9.0
    mat_img = Image.fromarray(np.clip(mat_rgb, 0, 255).astype(np.uint8)).convert("RGBA")

    # 5 macro spherical condensed water droplets hanging/perched on hydrophobic filaments
    droplets = [
        (210, 622, 48),
        (378, 636, 56),
        (548, 628, 62),
        (724, 634, 54),
        (882, 618, 46),
    ]

    rng = np.random.default_rng(20261030)

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
        im = Image.fromarray(cave_bg.astype(np.uint8)).convert("RGBA")
        im.paste(rock_img, (0, 0), rock_mask)
        im.paste(mat_img, (0, 0), mat_mask)

        ray_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ray_layer)

        # Draw microscopic water-repellent fuzz filaments along ceiling
        for x in range(85, 995, 14):
            base_y = 574.0 + 18.0 * math.sin(x * 0.009) + 9.0 * math.sin(x * 0.031 + 1.1)
            sway = 2.0 * math.sin(t * 1.8 + x * 0.05)
            rd.line([(x, base_y - 6), (x + sway, base_y + 18)], fill=(232, 192, 74, 155), width=2)

        # Sweeping headlamp origin at bottom-left/center (simulating caver looking up)
        src_x = 250.0 + 95.0 * math.sin(t * 0.85)
        src_y = 1320.0

        # Broad soft headlamp cone
        rd.polygon(
            [(src_x, src_y), (130, 590), (950, 590)],
            fill=(235, 242, 255, 22),
        )

        # Incident white rays + internal droplet refraction + bright golden retro-reflection
        pulse = 0.82 + 0.18 * math.sin(t * 2.6)
        for idx, (dx, dy, rad) in enumerate(droplets):
            # Incident cool-white beam from headlamp to droplet
            rd.line([(src_x, src_y), (dx - 10, dy + rad * 0.45)], fill=(225, 238, 255, 128), width=4)

            # Droplet body (translucent cave moisture sphere)
            rd.ellipse(
                (dx - rad, dy - rad, dx + rad, dy + rad),
                fill=(42, 54, 68, 168),
                outline=(215, 232, 248, 215),
                width=3,
            )
            # Golden internal bounce off top hydrophobic bacterial interface
            rd.arc(
                (dx - rad + 5, dy - rad + 5, dx + rad - 5, dy + rad - 5),
                start=200,
                end=340,
                fill=(255, 214, 64, int(245 * pulse)),
                width=7,
            )
            # Specular diamond highlight
            hx, hy = dx - rad * 0.32, dy + rad * 0.28
            rd.ellipse((hx - 8, hy - 8, hx + 8, hy + 8), fill=(255, 250, 220, 245))

            # Retro-reflected golden ray returning toward viewer/caver eye line
            ret_x = src_x + 48.0 + idx * 14.0
            ret_y = 1285.0
            rd.line(
                [(dx + 8, dy + rad * 0.5), (ret_x, ret_y)],
                fill=(255, 206, 56, int(188 * pulse)),
                width=5,
            )

        im = Image.alpha_composite(im, ray_layer)
        d = ImageDraw.Draw(im)

        # Clean, restrained borderless documentary labels (strictly above y=1340)
        d.text((68, 128), "OPTICAL MECHANISM • ZERO GOLD METAL", font=fb_kicker, fill=(255, 212, 78, 235))
        d.text((68, 162), "How Bacteria Glitter Like Solid Gold", font=fb_title, fill=(248, 250, 252, 250))

        d.text((68, 392), "SEALED VOLCANIC BASALT CEILING", font=fb_lbl, fill=(232, 236, 242, 238))
        d.text((68, 424), "Iron & manganese minerals feed microbes in total darkness", font=fm_lbl, fill=(188, 196, 206, 225))

        d.text((68, 742), "WATER-REPELLENT ACTINOBACTERIA MAT", font=fb_lbl, fill=(255, 216, 84, 245))
        d.text((68, 774), "Hydrophobic fuzz forces moisture into spherical lens droplets", font=fm_lbl, fill=(232, 224, 198, 232))

        d.text((68, 1148), "RETRO-REFLECTED HEADLAMP BEAM", font=fb_lbl, fill=(255, 214, 72, 245))
        d.text((68, 1182), "Spherical droplets bounce golden light straight back to your eyes", font=fm_lbl, fill=(238, 242, 246, 230))

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
