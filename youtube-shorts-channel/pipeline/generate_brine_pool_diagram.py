#!/usr/bin/env python3
"""
Generate 100% first-party original photo-textured full-bleed 9:16 geological cross-section
for Brine Pools v4.0 (`pow_documentary_v3` Zero-AI-Smell standard):
`assets/raw_footage/hidden_earth_brine_pools_v4/brine_pool_cutaway_v4.mp4`

Key v4.0 upgrades over legacy v2 diagram:
- Full-bleed 1080x1920 edge-to-edge canvas (ZERO inset rounded frames, ZERO yellow warning pills,
  ZERO floating dashboard boxes).
- Blends real Public Domain NOAA seafloor rock/sediment photographic micro-relief
  (`noaa_methane_venting_4k.jpg`) + temporal monochromatic 35mm optical luma grain (`sigma=2.3`)
  so the cutaway shares the same organic tonal DNA as live ROV footage.
- Restrained borderless editorial typography strictly above `y=1360` (caption-safe).
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT_MP4 = ROOT / "assets" / "raw_footage" / "hidden_earth_brine_pools_v4" / "brine_pool_cutaway_v4.mp4"
NOAA_TEX = ROOT / "assets" / "raw_footage" / "hidden_earth_brine_pools_20261029" / "noaa_methane_venting_4k.jpg"
FONT_BOLD = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(Path(__file__).resolve().parents[1] / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS = 1080, 1920, 30
DUR_S = 8.0
NFRAMES = int(DUR_S * FPS)


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fb_kicker = ImageFont.truetype(FONT_MED, 22)
    fb_title = ImageFont.truetype(FONT_BOLD, 36)
    fb_lbl = ImageFont.truetype(FONT_BOLD, 25)
    fm_lbl = ImageFont.truetype(FONT_MED, 21)

    # Extract real NOAA seafloor sediment luminance relief (Public Domain)
    tex_src = Image.open(NOAA_TEX).convert("L").resize((W, H), Image.Resampling.LANCZOS)
    tex_arr = np.asarray(tex_src, dtype=np.float32)
    tex_arr = (tex_arr - np.mean(tex_arr)) / (np.std(tex_arr) + 1e-5)

    yy = np.arange(H, dtype=np.float32)[:, None]
    xx = np.arange(W, dtype=np.float32)[None, :]

    # Deep abyssal seawater gradient across full 1080x1920 canvas
    depth_u = yy / float(H)
    ocean_r = 6.0 + 8.0 * (1.0 - depth_u)
    ocean_g = 18.0 + 22.0 * (1.0 - depth_u)
    ocean_b = 36.0 + 42.0 * (1.0 - depth_u)
    ocean_bg = np.stack(
        [np.broadcast_to(ocean_r, (H, W)), np.broadcast_to(ocean_g, (H, W)), np.broadcast_to(ocean_b, (H, W))],
        axis=2,
    )
    # Subtle underwater optical scatter texture
    ocean_bg = np.clip(ocean_bg + tex_arr[:, :, None] * 2.8, 0.0, 255.0)

    # Prebuild photo-textured sediment & crystalline salt dome RGB fields
    sed_base = np.zeros((H, W, 3), dtype=np.float32)
    sed_base[:, :, 0] = 56.0 - 18.0 * depth_u + tex_arr * 11.5
    sed_base[:, :, 1] = 50.0 - 16.0 * depth_u + tex_arr * 10.2
    sed_base[:, :, 2] = 44.0 - 12.0 * depth_u + tex_arr * 8.8
    sed_img = Image.fromarray(np.clip(sed_base, 0, 255).astype(np.uint8)).convert("RGBA")

    salt_tex = np.roll(tex_arr, shift=180, axis=0)
    salt_base = np.zeros((H, W, 3), dtype=np.float32)
    salt_base[:, :, 0] = 182.0 + salt_tex * 14.0
    salt_base[:, :, 1] = 198.0 + salt_tex * 14.5
    salt_base[:, :, 2] = 214.0 + salt_tex * 15.0
    salt_img = Image.fromarray(np.clip(salt_base, 0, 255).astype(np.uint8)).convert("RGBA")

    rng = np.random.default_rng(20261029)
    snow_pts = [(float(rng.uniform(40, 1040)), float(rng.uniform(220, 680)), float(rng.uniform(10, 22))) for _ in range(36)]

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
        im = Image.fromarray(ocean_bg.astype(np.uint8)).convert("RGBA")
        d = ImageDraw.Draw(im)

        # Drifting marine snow in oxygenated deep ocean
        for sx, sy, spd in snow_pts:
            yy_s = 220.0 + ((sy - 220.0 + spd * t) % 450.0)
            xx_s = sx + 5.0 * math.sin(t * 1.1 + sy * 0.03)
            d.ellipse((xx_s - 2, yy_s - 2, xx_s + 2, yy_s + 2), fill=(195, 226, 248, 92))

        # Hypersaline anoxic brine lake filling seafloor depression (x=150..930, y=735..985)
        basin_y = 742.0
        brine_pts = []
        for x in range(148, 933, 6):
            wave = 3.6 * math.sin(x * 0.026 - t * 2.3) + 1.6 * math.cos(x * 0.017 + t * 1.6)
            brine_pts.append((x, basin_y + wave))
        brine_poly = list(brine_pts) + [(905, 875), (790, 976), (540, 998), (290, 976), (175, 875)]

        brine_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(brine_layer)
        bd.polygon(brine_poly, fill=(12, 86, 102, 242))
        bd.polygon([(185, 800), (895, 800), (790, 976), (540, 998), (290, 976)], fill=(8, 58, 74, 235))
        bd.line(brine_pts, fill=(116, 244, 236, 238), width=4)
        im = Image.alpha_composite(im, brine_layer)

        # Photo-textured seafloor sediment mask (edge-to-edge x=0..1080, y=700..1920)
        sed_mask = Image.new("L", (W, H), 0)
        sm_d = ImageDraw.Draw(sed_mask)
        seafloor_poly = [
            (0, 704), (92, 712), (152, 742), (186, 882), (288, 978),
            (540, 1002), (792, 978), (894, 882), (928, 742), (988, 712),
            (W, 704), (W, H), (0, H),
        ]
        sm_d.polygon(seafloor_poly, fill=255)
        im.paste(sed_img, (0, 0), sed_mask)

        # Photo-textured buried evaporite salt dome rising from bottom (y=1050..1920)
        salt_mask = Image.new("L", (W, H), 0)
        sa_d = ImageDraw.Draw(salt_mask)
        salt_poly = [
            (180, H), (255, 1480), (330, 1210), (435, 1085),
            (540, 1058), (645, 1085), (750, 1210), (825, 1480), (900, H),
        ]
        sa_d.polygon(salt_poly, fill=242)
        salt_mask = salt_mask.filter(ImageFilter.GaussianBlur(radius=2.0))
        im.paste(salt_img, (0, 0), salt_mask)

        d = ImageDraw.Draw(im)
        # Subtle strata & upward dissolving brine conduits
        rim_pts = [(0, 704), (92, 712), (152, 742), (186, 882), (288, 978), (540, 1002), (792, 978), (894, 882), (928, 742), (988, 712), (W, 704)]
        d.line(rim_pts, fill=(164, 148, 126, 215), width=3)

        for (x0, y0), (x1, y1) in [((420, 1110), (360, 975)), ((540, 1070), (540, 998)), ((660, 1110), (720, 975))]:
            d.line([(x0, y0), (x1, y1)], fill=(116, 224, 222, 165), width=3)
            u_p = (t * 0.72) % 1.0
            px = x0 + u_p * (x1 - x0)
            py = y0 + u_p * (y1 - y0)
            d.ellipse((px - 5, py - 5, px + 5, py + 5), fill=(160, 252, 242, 225))

        # Subtle shoreline mussel rim & rising methane bubbles
        d.line([(88, 712), (154, 742)], fill=(224, 152, 76, 235), width=6)
        d.line([(926, 742), (992, 712)], fill=(224, 152, 76, 235), width=6)
        for side_x in (152, 928):
            for bi in range(3):
                prog = (t * 0.48 + bi * 0.33) % 1.0
                by = 736.0 - prog * 135.0
                bx = side_x + 6.0 * math.sin(prog * 7.5 + bi)
                rad = 3.8 - 1.2 * prog
                d.ellipse((bx - rad, by - rad, bx + rad, by + rad), outline=(185, 244, 255, int(205 * (1.0 - 0.6 * prog))), width=2)

        # Clean borderless documentary typography (zero boxes/pills!)
        txt_shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sd = ImageDraw.Draw(txt_shadow)
        labels = [
            (64, 118, "Illustrative geological cross-section", fb_kicker, (186, 214, 238, 240)),
            (64, 152, "How Buried Salt Forms an Ocean-Floor Lake", fb_title, (250, 253, 255, 255)),
            (64, 488, "Deep Ocean Seawater (~35 PSU)", fb_lbl, (214, 238, 255, 248)),
            (64, 520, "Oxygenated normal seawater", fm_lbl, (172, 204, 232, 235)),
            (590, 636, "Sharp Density Boundary", fb_lbl, (132, 250, 240, 252)),
            (590, 668, "Resists mixing — forms waves & shore", fm_lbl, (205, 240, 242, 238)),
            (318, 828, "Hypersaline Anoxic Brine (3–8× saltier)", fb_lbl, (246, 252, 255, 255)),
            (318, 862, "Zero oxygen  •  Traps methane & H₂S", fm_lbl, (255, 206, 178, 244)),
            (282, 1192, "Buried Ancient Salt Dome (Evaporite)", fb_lbl, (242, 248, 255, 252)),
            (282, 1226, "Dissolves upward into ultra-dense brine", fm_lbl, (198, 222, 244, 238)),
        ]
        for lx, ly, ltxt, lfnt, _ in labels:
            sd.text((lx, ly + 3), ltxt, font=lfnt, fill=(0, 0, 0, 215))
        txt_shadow = txt_shadow.filter(ImageFilter.GaussianBlur(radius=7))
        im = Image.alpha_composite(im, txt_shadow)
        d = ImageDraw.Draw(im)
        d.line([(680, 700), (680, 738)], fill=(132, 250, 240, 210), width=2)
        for lx, ly, ltxt, lfnt, lcol in labels:
            d.text((lx, ly), ltxt, font=lfnt, fill=lcol, stroke_width=2, stroke_fill=(5, 10, 18, 195))

        # Subtle bottom vignette behind caption zone (y=1400..1920) + 35mm optical luma grain
        rgb_arr = np.asarray(im.convert("RGB"), dtype=np.float32)
        bot_v = np.clip((yy - 1380.0) / 540.0, 0.0, 1.0) ** 1.3 * 0.42
        rgb_arr *= (1.0 - bot_v[:, :, None])
        fg_rng = np.random.default_rng(91000 + fi)
        grain = fg_rng.normal(0.0, 2.3, size=(H // 2, W // 2)).astype(np.float32)
        grain_full = np.repeat(np.repeat(grain, 2, axis=0), 2, axis=1)[:H, :W, None]
        rgb_arr = np.clip(rgb_arr + grain_full, 0.0, 255.0)

        proc.stdin.write(rgb_arr.astype(np.uint8).tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Diagram encode failed ({rc})")
    return out_mp4


if __name__ == "__main__":
    p = build_diagram_mp4()
    print(f"[DIAGRAM V4 OK] -> {p} ({p.stat().st_size / 1024:.1f} KB)")
