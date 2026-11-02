#!/usr/bin/env python3
"""
Generate a 100% first-party original vertical (1080x1920 @ 30fps) geological
cross-section diagram for the Bermuda Triangle documentary (`Studio v6.0`):
`assets/raw_footage/hidden_earth_bermuda_abyss_v6/bermuda_rock_raft_cutaway_v6.mp4`

Illustrates the seismic discovery beneath Bermuda (Frazer, Park & Olugboji,
Geophysical Research Letters / Carnegie Institution):
- Atlantic Ocean & Bermuda Volcanic Seamount rising from the seafloor.
- Surrounding Bermuda Swell held ~500 meters higher than normal seafloor.
- Oceanic Crust (~7 km thick).
- Newly identified ~20-kilometer-thick underplated "geological raft" of frozen,
  lower-density mantle rock directly beneath the crust providing buoyant uplift.
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "assets" / "raw_footage" / "hidden_earth_bermuda_abyss_v6"
OUT_MP4 = RAW_DIR / "bermuda_rock_raft_cutaway_v6.mp4"

FONT_BOLD = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS = 1080, 1920, 30
DURATION_S = 10.0
TOTAL_FRAMES = int(round(DURATION_S * FPS))


def _interp_curve(pts: list[tuple[float, float]], xs: np.ndarray) -> np.ndarray:
    px = np.array([p[0] for p in pts], dtype=np.float64)
    py = np.array([p[1] for p in pts], dtype=np.float64)
    return np.interp(xs, px, py)


def _build_base_layers() -> tuple[np.ndarray, dict[str, np.ndarray]]:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    xs = np.arange(W, dtype=np.float64)

    # 1. Night-slate documentary atmosphere above sea level (y = 0..465)
    sky_top = np.array([10, 17, 29], dtype=np.float32)
    sky_hzn = np.array([24, 44, 68], dtype=np.float32)
    t_sky = np.clip(yy / 465.0, 0.0, 1.0)[..., None]
    canvas = sky_top * (1.0 - t_sky) + sky_hzn * t_sky

    # Sea level y = 465
    sea_y = 465.0 + 3.0 * np.sin(xs / 65.0)

    # Seafloor & Bermuda volcanic seamount + +500m Bermuda Swell
    # Normal abyssal floor at edges ~ y=690, raised swell ~ y=635, Bermuda island peak ~ y=438
    seafloor_y = _interp_curve(
        [
            (0, 695),
            (130, 682),
            (250, 642),
            (380, 622),
            (465, 535),
            (515, 446),
            (540, 438),
            (565, 447),
            (615, 538),
            (700, 622),
            (830, 642),
            (950, 682),
            (1080, 695),
        ],
        xs,
    )

    # Base of ~7 km Oceanic Crust
    crust_bot_y = _interp_curve(
        [
            (0, 815),
            (160, 804),
            (320, 775),
            (540, 756),
            (760, 775),
            (920, 804),
            (1080, 815),
        ],
        xs,
    )

    # 20 km Underplated Frozen Mantle Rock "Raft" lens (x = 145..935, thickest in center y=756..1115)
    raft_bot_y = _interp_curve(
        [
            (0, 815),
            (140, 810),
            (235, 935),
            (365, 1068),
            (540, 1118),
            (715, 1068),
            (845, 935),
            (940, 810),
            (1080, 815),
        ],
        xs,
    )

    # Procedural subtle rock grain for geological realism (deterministic seed)
    rng = np.random.default_rng(42)
    grain_fine = rng.normal(0.0, 4.5, size=(H, W)).astype(np.float32)
    strata_wave = 5.5 * np.sin(yy / 11.0 + 0.015 * xx)

    # Paint Atlantic Ocean water column
    in_ocean = (yy >= sea_y[None, :]) & (yy < seafloor_y[None, :])
    t_water = np.clip((yy - 465.0) / 235.0, 0.0, 1.0)[..., None]
    water_top = np.array([22, 118, 168], dtype=np.float32)
    water_deep = np.array([8, 34, 66], dtype=np.float32)
    water_col = water_top * (1.0 - t_water) + water_deep * t_water
    canvas = np.where(in_ocean[..., None], water_col, canvas)

    # Paint Deep Upper Mantle (below crust/raft down to bottom H)
    in_mantle = yy >= np.maximum(crust_bot_y[None, :], raft_bot_y[None, :])
    t_mantle = np.clip((yy - 820.0) / 900.0, 0.0, 1.0)[..., None]
    mantle_top = np.array([38, 28, 32], dtype=np.float32)
    mantle_bot = np.array([16, 14, 20], dtype=np.float32)
    mantle_col = mantle_top * (1.0 - t_mantle) + mantle_bot * t_mantle + (0.45 * grain_fine)[..., None]
    canvas = np.where(in_mantle[..., None], mantle_col, canvas)

    # Paint Oceanic Crust + Bermuda Volcanic Pedestal
    in_crust = (yy >= seafloor_y[None, :]) & (yy < crust_bot_y[None, :])
    t_crust = np.clip((yy - seafloor_y[None, :]) / 190.0, 0.0, 1.0)[..., None]
    crust_top = np.array([68, 82, 98], dtype=np.float32)
    crust_bot = np.array([44, 54, 68], dtype=np.float32)
    crust_col = crust_top * (1.0 - t_crust) + crust_bot * t_crust + (0.65 * grain_fine + 0.4 * strata_wave)[..., None]
    # Highlight subaerial Bermuda limestone cap above sea level
    in_island_cap = (yy >= seafloor_y[None, :]) & (yy < sea_y[None, :] + 6.0)
    cap_col = np.array([196, 188, 162], dtype=np.float32)
    crust_col = np.where(in_island_cap[..., None], cap_col, crust_col)
    canvas = np.where(in_crust[..., None], crust_col, canvas)

    # Paint the 20-KM FROZEN MANTLE ROCK "RAFT" (warm copper-amber crystalline lens)
    in_raft = (yy >= crust_bot_y[None, :]) & (yy < raft_bot_y[None, :]) & ((raft_bot_y - crust_bot_y)[None, :] > 4.0)
    t_raft = np.clip((yy - crust_bot_y[None, :]) / np.maximum(1.0, (raft_bot_y - crust_bot_y)[None, :]), 0.0, 1.0)[..., None]
    raft_core = np.array([178, 108, 46], dtype=np.float32)
    raft_edge = np.array([106, 62, 32], dtype=np.float32)
    raft_col = raft_core * (1.0 - 0.65 * np.abs(t_raft - 0.45)) + raft_edge * (0.65 * np.abs(t_raft - 0.45))
    raft_col = raft_col + (0.7 * grain_fine + 0.8 * strata_wave)[..., None]
    canvas = np.where(in_raft[..., None], raft_col, canvas)

    # Soft vignette in caption zone (y > 1350) so subtitles pop cleanly
    t_bot = np.clip((yy - 1260.0) / 520.0, 0.0, 1.0)[..., None]
    canvas = canvas * (1.0 - 0.58 * t_bot) + np.array([8, 12, 18], dtype=np.float32) * (0.58 * t_bot)

    curves = {
        "sea_y": sea_y,
        "seafloor_y": seafloor_y,
        "crust_bot_y": crust_bot_y,
        "raft_bot_y": raft_bot_y,
    }
    return np.clip(canvas, 0, 255).astype(np.uint8), curves


def build_diagram_mp4(out_mp4: Path = OUT_MP4) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    base_rgb, curves = _build_base_layers()

    f_kicker = ImageFont.truetype(FONT_BOLD, 21)
    f_title = ImageFont.truetype(FONT_BOLD, 38)
    f_label_b = ImageFont.truetype(FONT_BOLD, 26)
    f_label_m = ImageFont.truetype(FONT_MED, 21)
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
        "-frames:v",
        str(TOTAL_FRAMES),
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

    seafloor_pts = [(int(x), int(round(curves["seafloor_y"][x]))) for x in range(0, W, 8)]
    crust_pts = [(int(x), int(round(curves["crust_bot_y"][x]))) for x in range(140, 941, 8)]
    raft_pts = [(int(x), int(round(curves["raft_bot_y"][x]))) for x in range(140, 941, 8)]

    for fi in range(TOTAL_FRAMES):
        t = fi / float(FPS)
        im = Image.fromarray(base_rgb).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        # Header title block (safe top zone y = 215..345)
        od.text((120, 222), "SEISMIC CROSS-SECTION • ILLUSTRATIVE MODEL", font=f_kicker, fill=(116, 198, 244, 235))
        od.text((120, 256), "BERMUDA'S 20 KM ROCK 'RAFT'", font=f_title, fill=(246, 249, 252, 255))
        od.line([(120, 314), (490, 314)], fill=(245, 174, 82, 220), width=3)

        # Crisp horizon & geological boundary strokes
        od.line([(0, 465), (1080, 465)], fill=(120, 212, 255, 175), width=2)
        od.line(seafloor_pts, fill=(176, 206, 228, 190), width=3)
        od.line(crust_pts, fill=(255, 208, 136, 215), width=3)
        od.line(raft_pts, fill=(255, 168, 78, 235), width=4)

        # Animated seismic wavefront rings propagating from Bermuda station (x=540, y=442)
        for ring_idx in range(3):
            prog = ((t * 0.42 + ring_idx / 3.0) % 1.0)
            rad = int(80 + prog * 720)
            alpha = int(145 * math.sin(prog * math.pi))
            if alpha > 12:
                bbox = [540 - rad, 442 - int(rad * 0.55), 540 + rad, 442 + rad]
                od.arc(bbox, start=22, end=158, fill=(130, 220, 255, alpha), width=2)

        # Reference normal seafloor dashed baseline at y=692 showing +500m Bermuda Swell uplift
        for dx in range(145, 935, 26):
            od.line([(dx, 692), (dx + 14, 692)], fill=(148, 178, 204, 130), width=2)

        # Upward buoyancy arrows inside the 20 km rock raft (animated gentle lift)
        bob = int(round(6.0 * math.sin(t * 2.4)))
        for ax in (350, 540, 730):
            ay_bot = 1035 + bob
            ay_top = 835 + bob
            od.line([(ax, ay_bot), (ax, ay_top)], fill=(255, 222, 148, 215), width=4)
            od.polygon([(ax, ay_top - 14), (ax - 11, ay_top + 6), (ax + 11, ay_top + 6)], fill=(255, 222, 148, 230))

        # Clean documentary labels (all strictly inside x=120..960, y=380..1295)
        # 1) Bermuda Island
        od.rounded_rectangle((418, 376, 662, 422), radius=8, fill=(14, 26, 42, 220), outline=(130, 214, 255, 190), width=2)
        od.text((438, 387), "BERMUDA ISLAND", font=f_label_m, fill=(244, 248, 252, 255))

        # 2) +500m Seafloor Swell callout (right side)
        if t >= 0.35:
            a1 = min(255, int((t - 0.35) * 450))
            od.rounded_rectangle((650, 526, 956, 602), radius=10, fill=(12, 30, 50, min(225, a1)), outline=(104, 206, 255, a1), width=2)
            od.text((668, 536), "+500 M SEAFLOOR SWELL", font=f_label_m, fill=(126, 222, 255, a1))
            od.text((668, 566), "Held higher than normal abyss", font=f_small, fill=(222, 234, 245, a1))

        # 3) Oceanic Crust (~7 km)
        od.text((136, 722), "OCEANIC CRUST (~7 KM)", font=f_small, fill=(214, 224, 236, 235))

        # 4) Central reveal: 20 KM Frozen Mantle Rock Raft
        if t >= 0.75:
            a2 = min(255, int((t - 0.75) * 420))
            od.rounded_rectangle((222, 878, 858, 996), radius=12, fill=(28, 18, 12, min(230, a2)), outline=(255, 186, 92, a2), width=2)
            od.text((250, 892), "20 KM FROZEN MANTLE ROCK 'RAFT'", font=f_label_b, fill=(255, 208, 122, a2))
            od.text((250, 932), "Lower-density underplated layer (~15–35 km deep)", font=f_label_m, fill=(242, 236, 228, a2))
            od.text((250, 962), "Buoyantly supports Bermuda without an active plume", font=f_small, fill=(208, 198, 186, a2))

        # 5) Upper Mantle + Source citation (above y=1310 subtitle guard)
        od.text((402, 1168), "DEEP UPPER MANTLE (> 35 KM)", font=f_label_m, fill=(186, 174, 178, 215))
        od.text(
            (120, 1268),
            "Source: Seismic receiver-function model (Frazer, Park & Olugboji / Carnegie Institution)",
            font=f_small,
            fill=(164, 182, 200, 195),
        )

        comp = Image.alpha_composite(im, ov).convert("RGB")
        proc.stdin.write(comp.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with {rc}")
    return out_mp4


if __name__ == "__main__":
    p = build_diagram_mp4()
    print(f"Built geological cutaway: {p} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
