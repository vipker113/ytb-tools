#!/usr/bin/env python3
"""
Generate a restrained, scientifically defensible vertical (1080x1920 @ 30fps)
illustrative geological cross-section of the Taylor Glacier / Blood Falls subglacial
brine system (~8.5s master clip, trimmed to exact narration cue during assembly).

Strictly labeled as an illustrative cross-section and hypothesis (never presented
as underground footage, and free of futuristic HUD clutter).
"""

from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
FPS = 30
DURATION_S = 9.5
TOTAL_FRAMES = int(round(DURATION_S * FPS))

FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"
FONT_REG = FONT_MED


def _cubic_interp(pts: list[tuple[float, float]], xs: np.ndarray) -> np.ndarray:
    px = np.array([p[0] for p in pts], dtype=np.float64)
    py = np.array([p[1] for p in pts], dtype=np.float64)
    return np.interp(xs, px, py)


def _build_static_geology() -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Build crisp 1080x1920 RGB base geology layer + fissure centerline coordinates."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # Sky / polar atmosphere background (clean slate-navy documentary tone)
    sky_top = np.array([15, 23, 36], dtype=np.float32)
    sky_hzn = np.array([38, 56, 78], dtype=np.float32)
    t_sky = np.clip(yy / 760.0, 0.0, 1.0)[..., None]
    canvas = sky_top * (1.0 - t_sky) + sky_hzn * t_sky

    # Distant Dry Valleys mountain ridge silhouette (subtle)
    xs = np.arange(W, dtype=np.float64)
    ridge_y = _cubic_interp(
        [(0, 560), (190, 515), (390, 540), (610, 495), (820, 535), (960, 575), (1080, 590)],
        xs,
    )
    ridge_mask = yy >= ridge_y[None, :]
    ridge_col = np.array([31, 43, 59], dtype=np.float32)
    canvas = np.where(ridge_mask[..., None], ridge_col, canvas)

    # Bedrock profile (Taylor Valley basin cradling subglacial brine pocket)
    bed_y = _cubic_interp(
        [
            (0, 1080),
            (110, 1145),
            (250, 1235),
            (410, 1255),
            (565, 1195),
            (695, 1075),
            (790, 1038),
            (920, 1068),
            (1080, 1095),
        ],
        xs,
    )

    # Subglacial hypersaline brine reservoir roof (trapped in basin x = 95..655)
    brine_top_y = _cubic_interp(
        [
            (0, 1085),
            (95, 1132),
            (240, 1098),
            (415, 1094),
            (565, 1112),
            (665, 1095),
            (1080, 1100),
        ],
        xs,
    )

    # Glacier surface profile (Taylor Glacier flowing left -> right, terminating in ice cliff at x~765)
    glacier_top_y = _cubic_interp(
        [
            (0, 625),
            (220, 648),
            (460, 682),
            (650, 726),
            (742, 764),
            (776, 978),   # Steep Taylor Glacier terminus cliff (Blood Falls face!)
            (1080, 982),
        ],
        xs,
    )

    # Lake Bonney ice cover & lake water on the right (x >= 772, y = 978..1095)
    lake_surface_y = 978.0
    lake_ice_bottom_y = 1004.0

    # 1) Lake Bonney deep water (below ice cover, above bedrock)
    in_lake = (xx >= 760) & (yy >= lake_ice_bottom_y) & (yy < bed_y[None, :])
    lake_col = np.array([24, 58, 82], dtype=np.float32)
    canvas = np.where(in_lake[..., None], lake_col, canvas)

    # Lake Bonney frozen ice cap
    in_lake_ice = (xx >= 760) & (yy >= lake_surface_y) & (yy < lake_ice_bottom_y)
    lake_ice_col = np.array([196, 220, 238], dtype=np.float32)
    canvas = np.where(in_lake_ice[..., None], lake_ice_col, canvas)

    # 2) Taylor Glacier ice body
    glacier_base_y = np.minimum(bed_y, brine_top_y)
    in_glacier = (xx <= 780) & (yy >= glacier_top_y[None, :]) & (yy < glacier_base_y[None, :])
    # Natural glacial depth gradient + subtle internal flow stratification lines
    depth_frac = np.clip((yy - glacier_top_y[None, :]) / np.maximum(1.0, (glacier_base_y[None, :] - glacier_top_y[None, :])), 0.0, 1.0)
    ice_top = np.array([222, 238, 248], dtype=np.float32)
    ice_bot = np.array([118, 165, 198], dtype=np.float32)
    strata = 0.035 * np.sin((yy - 0.14 * xx) * 0.14)
    ice_rgb = ice_top * (1.0 - depth_frac[..., None]) + ice_bot * depth_frac[..., None] + 255.0 * strata[..., None]
    canvas = np.where(in_glacier[..., None], np.clip(ice_rgb, 0, 255), canvas)

    # 3) Trapped Subglacial Hypersaline Marine Brine Reservoir (deep amber-ferrous anoxic brine)
    in_brine = (xx >= 90) & (xx <= 665) & (yy >= brine_top_y[None, :]) & (yy < bed_y[None, :])
    brine_d = np.clip((yy - brine_top_y[None, :]) / 155.0, 0.0, 1.0)
    brine_top_c = np.array([148, 76, 36], dtype=np.float32)
    brine_bot_c = np.array([92, 36, 18], dtype=np.float32)
    brine_rgb = brine_top_c * (1.0 - brine_d[..., None]) + brine_bot_c * brine_d[..., None]
    canvas = np.where(in_brine[..., None], brine_rgb, canvas)

    # 4) Antarctic Bedrock (McMurdo Dry Valleys basement rock + dark lower caption zone)
    in_bed = yy >= bed_y[None, :]
    bed_d = np.clip((yy - bed_y[None, :]) / 420.0, 0.0, 1.0)
    # Subtle rock grain texture (deterministic procedural)
    grain = 5.5 * np.sin(xx * 0.045 + 1.8 * np.sin(yy * 0.03)) * np.cos(yy * 0.055)
    bed_top_c = np.array([62, 58, 56], dtype=np.float32)
    bed_bot_c = np.array([18, 19, 24], dtype=np.float32)
    bed_rgb = bed_top_c * (1.0 - bed_d[..., None]) + bed_bot_c * bed_d[..., None] + grain[..., None] * (1.0 - 0.75 * bed_d[..., None])
    canvas = np.where(in_bed[..., None], np.clip(bed_rgb, 0, 255), canvas)

    # Fissure / conduit pathway from subglacial brine (x=545, y=1118) up to Blood Falls vent (x=766, y=905)
    # and down the ice cliff to Lake Bonney ice surface (x=792, y=980)
    conduit_pts = [
        (520.0, 1126.0),
        (585.0, 1088.0),
        (648.0, 1035.0),
        (706.0, 972.0),
        (763.0, 906.0),  # Emergence into air (O2) at Blood Falls!
        (775.0, 948.0),
        (792.0, 980.0),
        (838.0, 983.0),
    ]

    # Render crisp boundary strokes via Pillow supersampling
    img = Image.fromarray(canvas.astype(np.uint8))
    draw = ImageDraw.Draw(img, "RGBA")

    # Glacier top outline
    g_pts = [(float(x), float(glacier_top_y[int(x)])) for x in range(0, 782, 4)]
    draw.line(g_pts, fill=(245, 252, 255, 230), width=3)

    # Bedrock contact line
    b_pts = [(float(x), float(bed_y[int(x)])) for x in range(0, W, 4)]
    draw.line(b_pts, fill=(98, 92, 88, 220), width=3)

    # Brine roof line
    br_pts = [(float(x), float(brine_top_y[int(x)])) for x in range(96, 656, 4)]
    draw.line(br_pts, fill=(212, 132, 72, 200), width=2)

    # Subglacial conduit channel dark casing + iron-stained fracture
    draw.line(conduit_pts[:5], fill=(62, 34, 24, 215), width=14, joint="curve")
    draw.line(conduit_pts[:5], fill=(168, 84, 38, 235), width=7, joint="curve")

    return np.asarray(img, dtype=np.uint8), conduit_pts


def _sample_polyline(pts: list[tuple[float, float]], u: float) -> tuple[float, float]:
    """Sample point at normalized arc-length u in [0, 1] along polyline."""
    segs = []
    total = 0.0
    for i in range(len(pts) - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        d = math.hypot(dx, dy)
        segs.append((d, pts[i], pts[i + 1]))
        total += d
    target = np.clip(u, 0.0, 1.0) * total
    acc = 0.0
    for d, p0, p1 in segs:
        if acc + d >= target or d == 0:
            t = 0.0 if d == 0 else (target - acc) / d
            return (p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1]))
        acc += d
    return pts[-1]


def build_diagram_video(out_mp4: Path) -> Path:
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    base_rgb, conduit_pts = _build_static_geology()

    f_badge = ImageFont.truetype(FONT_BOLD, 23)
    f_title = ImageFont.truetype(FONT_BOLD, 38)
    f_sub = ImageFont.truetype(FONT_MED, 25)
    f_lbl_b = ImageFont.truetype(FONT_BOLD, 26)
    f_lbl_m = ImageFont.truetype(FONT_MED, 22)
    f_small = ImageFont.truetype(FONT_REG, 20)

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
        "16",
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

    for fn in range(TOTAL_FRAMES):
        t = fn / float(FPS)
        frame = Image.fromarray(base_rgb.copy()).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # 1) Top illustrative disclosure pill + clean geological title
        badge_txt = "ILLUSTRATIVE GEOLOGICAL CROSS-SECTION"
        bw_top = d.textbbox((0, 0), badge_txt, font=f_badge)[2] + 44
        d.rounded_rectangle((56, 112, 56 + bw_top, 162), radius=10, fill=(14, 22, 34, 215), outline=(130, 175, 210, 140), width=2)
        d.text((78, 123), badge_txt, font=f_badge, fill=(182, 220, 248, 255))
        d.text((58, 184), "Hypothesized Subglacial Brine System", font=f_title, fill=(246, 250, 255, 255))
        d.text((58, 236), "Taylor Glacier Terminus  •  McMurdo Dry Valleys", font=f_sub, fill=(176, 198, 220, 240))

        # 2) Subtle glacier advance arrows inside Taylor Glacier ice
        arrow_alpha = int(215 * min(1.0, t / 0.8))
        for ax, ay in [(185, 815), (365, 835), (535, 860)]:
            shift = 10.0 * (0.5 - 0.5 * math.cos(t * 1.4))
            x0, x1 = ax + shift, ax + 68 + shift
            d.line([(x0, ay), (x1, ay)], fill=(38, 76, 108, arrow_alpha), width=4)
            d.polygon([(x1 + 12, ay), (x1 - 4, ay - 9), (x1 - 4, ay + 9)], fill=(38, 76, 108, arrow_alpha))

        # 3) Animated upward brine transport pulses along subglacial fissure + rusty oxidation fan at air contact
        # u in [0, 0.73] is anoxic iron-rich brine inside ice; u > 0.73 contacts air O2 and turns rusty red!
        flow_reveal = min(1.0, max(0.0, (t - 0.35) / 2.2))
        # Red oxidized cascade on the terminus cliff (grows smoothly as brine emerges)
        ox_alpha = int(240 * min(1.0, max(0.0, (t - 1.1) / 1.4)))
        if ox_alpha > 5:
            d.line(conduit_pts[4:], fill=(198, 44, 24, ox_alpha), width=11, joint="curve")
            # Oxidized fan on ice cliff & Lake Bonney apron
            d.polygon(
                [(763, 906), (754, 980), (835, 985), (782, 945)],
                fill=(186, 42, 22, int(ox_alpha * 0.82)),
            )

        for k in range(9):
            u = ((t * 0.24) + k / 9.0) % 1.0
            if u > 0.30 + 0.70 * flow_reveal:
                continue
            px, py = _sample_polyline(conduit_pts, u)
            if u < 0.70:
                col = (238, 152, 74, 225)  # Unoxidized ferrous brine (Fe2+)
                r = 5.5
            else:
                col = (232, 58, 32, 245)   # Oxidized ferric rust (Fe3+ oxide) upon air contact
                r = 6.5
            d.ellipse((px - r, py - r, px + r, py + r), fill=col)

        # 4) Crisp, high-contrast scientific callouts (all strictly above y = 1350 caption safe zone!)
        # Taylor Glacier label
        d.text((110, 718), "TAYLOR GLACIER", font=f_lbl_b, fill=(24, 46, 68, 245))
        d.text((110, 750), "Advancing ice (~400 m thick) seals valley", font=f_lbl_m, fill=(36, 64, 92, 235))

        # Subglacial brine pocket callout box (in bedrock below pocket, y = 1256..1356)
        brine_a = int(255 * min(1.0, max(0.0, (t - 0.3) / 0.7)))
        if brine_a > 10:
            t_b1 = "ISOLATED SUBGLACIAL BRINE"
            t_b2 = "Iron-rich, salty water — likely ancient seawater (hypothesis)"
            wb = max(d.textbbox((0, 0), t_b1, font=f_lbl_b)[2], d.textbbox((0, 0), t_b2, font=f_small)[2]) + 44
            d.line([(365, 1170), (365, 1256)], fill=(235, 155, 88, brine_a), width=3)
            d.ellipse((359, 1164, 371, 1176), fill=(235, 155, 88, brine_a))
            d.rounded_rectangle((68, 1256, 68 + wb, 1358), radius=12, fill=(16, 22, 32, int(0.92 * brine_a)), outline=(218, 134, 70, int(0.85 * brine_a)), width=2)
            d.text((90, 1268), t_b1, font=f_lbl_b, fill=(248, 184, 120, brine_a))
            d.text((90, 1306), t_b2, font=f_small, fill=(216, 226, 238, brine_a))

        # Blood Falls oxidation callout (right upper above cliff, y = 736..844)
        bf_a = int(255 * min(1.0, max(0.0, (t - 1.2) / 0.7)))
        if bf_a > 10:
            t_f1 = "BLOOD FALLS OUTFLOW"
            t_f2 = "Iron oxidizes in air (O2)"
            wf = max(d.textbbox((0, 0), t_f1, font=f_lbl_b)[2], d.textbbox((0, 0), t_f2, font=f_lbl_m)[2]) + 44
            bx0 = W - 44 - wf
            d.line([(766, 902), (bx0 + 90, 844)], fill=(238, 78, 52, bf_a), width=3)
            d.ellipse((760, 896, 772, 908), fill=(238, 78, 52, bf_a))
            d.rounded_rectangle((bx0, 738, bx0 + wf, 844), radius=12, fill=(24, 18, 22, int(0.92 * bf_a)), outline=(228, 74, 48, int(0.85 * bf_a)), width=2)
            d.text((bx0 + 22, 750), t_f1, font=f_lbl_b, fill=(255, 122, 98, bf_a))
            d.text((bx0 + 22, 788), t_f2, font=f_lbl_m, fill=(238, 242, 248, bf_a))

        # Lake Bonney label
        d.text((818, 1020), "LAKE BONNEY", font=f_lbl_m, fill=(188, 222, 245, 235))
        d.text((818, 1048), "(Ice-covered)", font=f_small, fill=(154, 192, 218, 215))

        comp = Image.alpha_composite(frame, ov).convert("RGB")
        # Add subtle temporal 35mm luma grain so cutaway matches live footage
        rng_g = np.random.default_rng(20261029 + fn)
        g_tile = rng_g.standard_normal((240, 135)).astype(np.float32) * 2.3
        g_full = np.repeat(np.repeat(g_tile, 8, axis=0), 8, axis=1)[:H, :W, None]
        comp_arr = np.clip(np.asarray(comp, dtype=np.float32) + g_full, 0, 255).astype(np.uint8)
        proc.stdin.write(comp_arr.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {rc}")
    print(f"[diagram] Rendered {out_mp4} ({TOTAL_FRAMES} frames, {DURATION_S}s)")
    return out_mp4


def build_clean_v3_diagram(out_mp4: Path, duration_s: float = 10.5) -> Path:
    """
    Render a clean, borderless v3 documentary geological cross-section (1080x1920 @ 30fps)
    with zero dashboard boxes, zero pill outlines, and clear illustrative hypothesis labeling.
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    base_rgb, conduit_pts = _build_static_geology()
    # Blend real photographic Antarctic glacier & Dry Valleys rock texture into the schematic strata
    photo_tex_path = Path(
        "/Applications/code/science-knowledge/youtube-shorts-channel/assets/raw_footage/hidden_earth_blood_falls_20261028/bf_aerial_2014_01.jpg"
    )
    if photo_tex_path.exists():
        tex_im = Image.open(photo_tex_path).convert("RGB").resize((W, H), Image.Resampling.LANCZOS)
        tex_arr = np.asarray(tex_im, dtype=np.float32)
        tex_luma = (0.299 * tex_arr[:, :, 0] + 0.587 * tex_arr[:, :, 1] + 0.114 * tex_arr[:, :, 2]) / 255.0
        # Modulate schematic strata with real glacier/rock micro-relief (+/- 16%) so it never looks like flat MS Paint
        relief = (0.86 + 0.28 * tex_luma)[:, :, None]
        base_rgb = np.clip(base_rgb.astype(np.float32) * relief, 0, 255).astype(np.uint8)
    n_frames = int(round(duration_s * FPS))

    f_note = ImageFont.truetype(FONT_MED, 24)
    f_title = ImageFont.truetype(FONT_BOLD, 36)
    f_lbl_b = ImageFont.truetype(FONT_BOLD, 25)
    f_lbl_m = ImageFont.truetype(FONT_MED, 22)

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

    for fn in range(n_frames):
        t = fn / float(FPS)
        frame = Image.fromarray(base_rgb.copy()).convert("RGBA")
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)

        # Clean, borderless top context note (clearly marks schematic as illustrative hypothesis)
        d.text(
            (56, 138),
            "Illustrative geological cross-section (hypothesis)",
            font=f_note,
            fill=(192, 214, 236, 235),
        )
        d.text(
            (56, 182),
            "Subglacial Brine Beneath Taylor Glacier",
            font=f_title,
            fill=(246, 250, 255, 250),
        )

        # Subtle glacier flow direction arrows inside Taylor Glacier ice
        arrow_alpha = int(190 * min(1.0, t / 0.8))
        for ax, ay in [(185, 815), (385, 840)]:
            shift = 8.0 * (0.5 - 0.5 * math.cos(t * 1.1))
            x0, x1 = ax + shift, ax + 64 + shift
            d.line([(x0, ay), (x1, ay)], fill=(42, 82, 114, arrow_alpha), width=3)
            d.polygon([(x1 + 10, ay), (x1 - 4, ay - 8), (x1 - 4, ay + 8)], fill=(42, 82, 114, arrow_alpha))

        # Upward brine transport along fissure + rust oxidation at air contact
        flow_reveal = min(1.0, max(0.0, (t - 0.25) / 2.2))
        ox_alpha = int(235 * min(1.0, max(0.0, (t - 1.0) / 1.4)))
        if ox_alpha > 5:
            d.line(conduit_pts[4:], fill=(196, 46, 26, ox_alpha), width=10, joint="curve")
            d.polygon(
                [(763, 906), (754, 980), (835, 985), (782, 945)],
                fill=(184, 42, 24, int(ox_alpha * 0.80)),
            )

        for k in range(8):
            u = ((t * 0.20) + k / 8.0) % 1.0
            if u > 0.30 + 0.70 * flow_reveal:
                continue
            px, py = _sample_polyline(conduit_pts, u)
            col = (234, 150, 74, 215) if u < 0.70 else (228, 58, 34, 240)
            r = 5.0 if u < 0.70 else 6.0
            d.ellipse((px - r, py - r, px + r, py + r), fill=col)

        # Clean borderless geological labels directly integrated into strata
        d.text((96, 716), "Taylor Glacier (~400 m ice)", font=f_lbl_b, fill=(24, 46, 68, 242))
        d.text((812, 1020), "Lake Bonney", font=f_lbl_m, fill=(192, 224, 246, 232))

        brine_a = int(245 * min(1.0, max(0.0, (t - 0.3) / 0.8)))
        if brine_a > 10:
            d.line([(365, 1168), (365, 1252)], fill=(224, 148, 86, brine_a), width=2)
            d.text((96, 1264), "Isolated iron-rich brine", font=f_lbl_b, fill=(246, 188, 128, brine_a))
            d.text((96, 1298), "Hypothesized ancient seawater origin", font=f_lbl_m, fill=(212, 222, 234, brine_a))

        bf_a = int(245 * min(1.0, max(0.0, (t - 1.1) / 0.8)))
        if bf_a > 10:
            d.line([(766, 902), (802, 826)], fill=(232, 82, 56, bf_a), width=2)
            d.text((778, 756), "Blood Falls vent", font=f_lbl_b, fill=(252, 134, 108, bf_a))
            d.text((778, 788), "Oxidizes in air", font=f_lbl_m, fill=(226, 234, 244, bf_a))

        comp = Image.alpha_composite(frame, ov).convert("RGB")
        # Add subtle temporal 35mm luma grain so cutaway matches live footage
        rng_g = np.random.default_rng(20261029 + fn)
        g_tile = rng_g.standard_normal((240, 135)).astype(np.float32) * 2.3
        g_full = np.repeat(np.repeat(g_tile, 8, axis=0), 8, axis=1)[:H, :W, None]
        comp_arr = np.clip(np.asarray(comp, dtype=np.float32) + g_full, 0, 255).astype(np.uint8)
        proc.stdin.write(comp_arr.tobytes())

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed with exit code {rc}")
    print(f"[diagram-v3] Rendered clean {out_mp4} ({n_frames} frames, {duration_s}s)")
    return out_mp4


if __name__ == "__main__":
    dst = Path("/Applications/code/science-knowledge/youtube-shorts-channel/output/hidden-earth/blood-falls-20261028/work_clips/subglacial_brine_diagram.mp4")
    build_diagram_video(dst)
