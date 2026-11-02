#!/usr/bin/env python3
"""
Proof of Wonder #03 — "How High Could You Jump on Other Planets?"

Output directory:
  youtube-shorts-channel/output/proof-of-wonder/03-how-high-could-you-jump-on-other-planets/

Physics model (stated on screen and in script.md):
  * Same takeoff speed everywhere: v0 = sqrt(2 * 9.80 * 0.50) = 3.13 m/s (a 0.50 m standing jump on Earth).
  * Jump height h = v0^2 / (2 g)  ->  h = 0.50 m / (g / g_Earth).
  * Airtime T = 2 v0 / g.
  * Gravity ratios: NASA GSFC Planetary Fact Sheet (Ratio to Earth); Pluto 0.62 m/s^2 (NASA GSFC Pluto Fact Sheet).
  * Gas giants (Jupiter, Saturn) have no solid surface; gravity is quoted at the 1-bar cloud level, so the
    video shows an explicitly labelled hypothetical floating platform.

Every jumping figure is a clearly explanatory animation driven by the exact parabolic trajectory
for that world's gravity (real-time unless labelled "2x SPEED"). Planet surfaces use real mapped
imagery (Solar System Scope CC BY 4.0 maps derived from NASA data; NASA MESSENGER Mercury mosaic;
NASA New Horizons PIA19857 Pluto). Saturn establishing shot is real NASA Goddard footage.
"""

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore", message="Truncated File Read")
Image.MAX_IMAGE_PIXELS = None

ROOT = "/Applications/code/science-knowledge/youtube-shorts-channel"
sys.path.insert(0, f"{ROOT}/pipeline")
from first_frame_thumbnail import export_first_frame_thumbnail  # noqa: E402
from planet_sphere_3d import PlanetSphereRenderer  # noqa: E402

OUT_DIR = f"{ROOT}/output/proof-of-wonder/03-how-high-could-you-jump-on-other-planets"
SHOTS_DIR = f"{OUT_DIR}/shots"
SCRATCH = "/Users/admin/.gemini/antigravity/brain/40c60d87-669d-4ec0-8e97-9ae15cc03780/scratch/pow03_build"
os.makedirs(SHOTS_DIR, exist_ok=True)
os.makedirs(SCRATCH, exist_ok=True)

VIDEO_SLUG = "03-how-high-could-you-jump-on-other-planets"
WORKING_TITLE = "How High Could You Jump on Other Planets?"

FONT_ANTON = f"{ROOT}/assets/fonts/Anton-Regular.ttf"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

RAW = f"{ROOT}/assets/raw_footage"
TEX = {
    "earth": f"{RAW}/pow_jump_planets/8k_earth_daymap.jpg",
    "moon": f"{RAW}/pow_jump_planets/8k_moon.jpg",
    "jupiter": f"{RAW}/pow_jump_planets/8k_jupiter.jpg",
    "saturn": f"{RAW}/pow_jump_planets/8k_saturn.jpg",
    "mars": f"{RAW}/proof_of_wonder_mars_helicopter/mars_8k_viking.jpg",
    "mercury": f"{RAW}/proof_of_wonder_venus/mercury_messenger_11k_bdr.jpg",
    "pluto": f"{RAW}/pow_jump_planets/pluto_equirect_from_pia19857.jpg",
}
ASSET_SATURN_SVS = f"{RAW}/batch1_r2_03_saturn_rings/nasa_saturn_rings_svs.mp4"

AUDIO_PATH = f"{OUT_DIR}/narration.mp3"
SRT_PATH = f"{OUT_DIR}/subtitles.srt"
FINAL_MP4 = f"{OUT_DIR}/{VIDEO_SLUG}.mp4"

FPS = 30
W, H = 1080, 1920
G_EARTH = 9.80
H_EARTH = 0.50
V0 = math.sqrt(2.0 * G_EARTH * H_EARTH)  # 3.130 m/s
FIG_H = 1.75  # figure height in meters

# Gravity ratios to Earth (NASA GSFC Planetary Fact Sheet; Pluto from GSFC Pluto Fact Sheet 0.62 m/s^2)
RATIO = {
    "earth": 1.000,
    "mercury": 0.378,
    "mars": 0.377,
    "moon": 0.166,
    "jupiter": 2.36,
    "saturn": 0.916,
    "pluto": 0.62 / G_EARTH,
}
NAME = {
    "earth": "Earth", "mercury": "Mercury", "mars": "Mars", "moon": "Moon",
    "jupiter": "Jupiter", "saturn": "Saturn", "pluto": "Pluto",
}


def g_of(body: str) -> float:
    return RATIO[body] * G_EARTH


def apex_of(body: str) -> float:
    return V0 * V0 / (2.0 * g_of(body))


def airtime_of(body: str) -> float:
    return 2.0 * V0 / g_of(body)


# ------------------------------------------------------------------------------------------------
# Shot plan (frame cuts placed inside natural WordBoundary pauses of narration.mp3)
# ------------------------------------------------------------------------------------------------
@dataclass
class ShotSpec:
    shot_id: str
    f_start: int
    f_end: int
    narration_phrase: str
    subtitle_segments: str
    intended_subject: str
    asset_path: str
    source_url: str
    license: str
    proof_rationale: str

    @property
    def start_sec(self) -> float:
        return self.f_start / FPS

    @property
    def end_sec(self) -> float:
        return self.f_end / FPS

    @property
    def num_frames(self) -> int:
        return self.f_end - self.f_start

    @property
    def duration(self) -> float:
        return self.num_frames / FPS


SSS = "https://www.solarsystemscope.com/textures/"
SSS_LIC = "CC BY 4.0 (Solar System Scope maps based on NASA mission data)"
FACT = "https://nssdc.gsfc.nasa.gov/planetary/factsheet/planet_table_ratio.html"
ANIM_LIC = "Original channel physics animation (data: NASA GSFC Planetary Fact Sheet)"

SHOT_PLAN: List[ShotSpec] = [
    ShotSpec("shot_01", 0, 60,
             "How high could you jump on other planets?",
             "[00:00.100 -> 00:01.850] How high could you jump on other planets?",
             "Seven tiny worlds (Jupiter, Earth, Saturn, Mercury, Mars, Moon, Pluto) in ascending order, each with a figure frozen at its true jump apex and a '?' tag; Frame-0 hook 'HOW HIGH COULD YOU JUMP / ON OTHER PLANETS?'.",
             "Programmatic animation + 7 planet maps", f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "The opening visual is the question itself: the same person at seven very different heights, numbers withheld until each world is explained."),
    ShotSpec("shot_02", 60, 136,
             "Say you manage half a meter on Earth.",
             "[00:02.170 -> 00:04.430] Say you manage half a meter on Earth.",
             "Figure on Earth's curved horizon performing a real-time 0.50 m standing jump (0.64 s airtime) beside a metric ruler.",
             TEX["earth"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "Establishes the 0.50 m baseline and the takeoff speed (3.13 m/s) reused on every other world."),
    ShotSpec("shot_03", 136, 266,
             "On Mars, the same jump reaches about 1.3 meters.",
             "[00:04.710 -> 00:06.730] On Mars, the same jump reaches | [00:06.750 -> 00:08.750] about 1.3 meters.",
             "Figure on Mars's horizon jumping 1.33 m in real time (1.69 s airtime) next to a translucent Earth-jump ghost (0.50 m).",
             TEX["mars"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "Same takeoff speed under 0.377 g gives h = 0.50/0.377 = 1.33 m, shown against the Earth ghost."),
    ShotSpec("shot_04", 266, 338,
             "Tiny Mercury? Almost the same.",
             "[00:09.050 -> 00:09.970] Tiny Mercury? | [00:10.280 -> 00:11.170] Almost the same.",
             "Figure on Mercury's cratered horizon (NASA MESSENGER mosaic) jumping 1.32 m with Earth ghost; header notes Mars = 1.33 m.",
             TEX["mercury"], "https://astrogeology.usgs.gov/search/map/mercury_messenger_global_mosaic_166m ; " + FACT,
             f"Public Domain (NASA/JHUAPL/CIW MESSENGER) + {ANIM_LIC}",
             "Mercury (0.378 g) gives 1.32 m, practically identical to Mars, despite being the smaller planet."),
    ShotSpec("shot_05", 338, 492,
             "On the Moon, you'd rise 3 meters and float for nearly four seconds.",
             "[00:11.460 -> 00:13.790] On the Moon, you'd rise 3 meters | [00:13.820 -> 00:16.300] and float for nearly four seconds.",
             "Figure on the Moon's horizon jumping 3.01 m in real time with a live airtime counter reaching 3.85 s.",
             TEX["moon"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "0.166 g gives h = 3.01 m and airtime 2*v0/g = 3.85 s, shown in real time ('no spacesuit' noted)."),
    ShotSpec("shot_06", 492, 588,
             "On Jupiter, from a platform in its clouds,",
             "[00:16.590 -> 00:19.490] On Jupiter, from a platform in its clouds,",
             "Zoom from the whole of Jupiter down to a tiny labelled hypothetical platform floating at cloud-top level.",
             TEX["jupiter"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "Makes clear Jupiter has no solid ground; its quoted gravity applies at the 1-bar cloud level."),
    ShotSpec("shot_07", 588, 684,
             "you'd barely clear 20 centimeters.",
             "[00:19.770 -> 00:22.690] you'd barely clear 20 centimeters.",
             "Figure on the cloud-level platform managing only 0.21 m hops (0.27 s airtime) beside the Earth ghost (0.50 m).",
             TEX["jupiter"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "2.36 g gives h = 0.50/2.36 = 0.21 m, visibly lower than the Earth ghost."),
    ShotSpec("shot_08", 684, 774,
             "Saturn has 95 times Earth's mass,",
             "[00:23.010 -> 00:25.700] Saturn has 95 times Earth's mass,",
             "Real NASA Goddard visualization of Saturn and its rings with a '95x EARTH'S MASS' card.",
             f"{ASSET_SATURN_SVS} [15.50s-18.50s]", "https://images.nasa.gov/details/GSFC_20181217_Saturn_m12672_Rings ; https://science.nasa.gov/saturn/facts/",
             "Public Domain (NASA / Goddard Space Flight Center)",
             "Shows the giant planet whose 95x Earth mass sets up the counter-intuitive result."),
    ShotSpec("shot_09", 774, 851,
             "yet you'd jump a bit higher there than at home.",
             "[00:25.970 -> 00:28.270] yet you'd jump a bit higher there than at home.",
             "Figure on a cloud-level platform above Saturn jumping 0.55 m vs the Earth ghost's 0.50 m.",
             TEX["saturn"], f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "Saturn's huge radius dilutes its gravity to 0.916 g at the clouds, so h = 0.55 m > 0.50 m."),
    ShotSpec("shot_10", 851, 971,
             "And on Pluto, one push sends you nearly 8 meters up.",
             "[00:28.560 -> 00:29.480] And on Pluto, | [00:29.770 -> 00:32.270] one push sends you nearly 8 meters up.",
             "Figure on Pluto's horizon (NASA New Horizons PIA19857 true-color mapping) launching to 7.90 m, shown at labelled 2x speed.",
             TEX["pluto"], "https://images.nasa.gov/details/PIA19857 ; https://nssdc.gsfc.nasa.gov/planetary/factsheet/plutofact.html",
             f"Public Domain (NASA/JHUAPL/SwRI New Horizons) + {ANIM_LIC}",
             "0.62 m/s^2 gives h = 7.90 m; the 10.1 s real airtime is shown at an explicitly labelled 2x speed."),
    ShotSpec("shot_11", 971, 1140,
             "Same legs. Same jump. Gravity decides the rest.",
             "[00:32.570 -> 00:33.510] Same legs. | [00:33.790 -> 00:34.550] Same jump. | [00:34.850 -> 00:36.900] Gravity decides the rest.",
             "All seven figures launch together in real time from their worlds with their exact apex heights labelled; Pluto is still rising at the end.",
             "Programmatic animation + 7 planet maps", f"{SSS} ; {FACT}", f"{SSS_LIC} + {ANIM_LIC}",
             "Answers the opening question with the identical lineup: one takeoff speed, seven outcomes set only by gravity."),
]

CUE_HIGHLIGHT_WORDS = {
    1: {"other", "planets?"}, 2: {"half", "meter"}, 3: {"Mars,"}, 4: {"1.3", "meters."},
    5: {"Mercury?"}, 6: {"same."}, 7: {"Moon,", "3", "meters"}, 8: {"four", "seconds."},
    9: {"Jupiter,"}, 10: {"20", "centimeters."}, 11: {"95", "times"}, 12: {"higher"},
    13: {"Pluto,"}, 14: {"8", "meters"}, 15: set(), 16: set(), 17: {"Gravity"},
}

# ------------------------------------------------------------------------------------------------
# Generic helpers
# ------------------------------------------------------------------------------------------------
_TEX_CACHE: Dict[Tuple[str, int], PlanetSphereRenderer] = {}


def renderer(body: str, max_w: int) -> PlanetSphereRenderer:
    key = (body, max_w)
    if key not in _TEX_CACHE:
        _TEX_CACHE[key] = PlanetSphereRenderer(TEX[body], max_tex_w=max_w)
    return _TEX_CACHE[key]


def drop_big_textures() -> None:
    for k in [k for k in _TEX_CACHE if k[1] > 2048]:
        del _TEX_CACHE[k]


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def ease(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return 0.5 - 0.5 * math.cos(math.pi * u)


def add_dither(arr: np.ndarray, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(arr + rng.uniform(-0.55, 0.55, size=(arr.shape[0], arr.shape[1], 1)).astype(np.float32), 0, 255)


def starfield(seed: int, count: int = 170) -> List[Tuple[int, int, float, float]]:
    rng = np.random.default_rng(seed)
    return [(int(rng.integers(8, W - 8)), int(rng.integers(8, H - 8)), float(rng.uniform(50, 175)), float(rng.uniform(0, 6.28)))
            for _ in range(count)]


def space_canvas(stars, t: float) -> np.ndarray:
    c = np.zeros((H, W, 3), dtype=np.float32)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    c[:, :, 0] = 4 + 6 * yy
    c[:, :, 1] = 5 + 6 * yy
    c[:, :, 2] = 12 + 10 * yy
    for sx, sy, br, ph in stars:
        b = br * (0.82 + 0.18 * math.sin(t * 2.1 + ph))
        c[sy, sx] += b
        if br > 150:
            c[sy, sx - 1] += b * 0.35
            c[sy, sx + 1] += b * 0.35
            c[sy - 1, sx] += b * 0.35
            c[sy + 1, sx] += b * 0.35
    return np.clip(c, 0, 255)


def encode_frames(frames_dir: str, out_mp4: str, n: int) -> None:
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{frames_dir}/f_%04d.png", "-frames:v", str(n),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-crf", "13", "-aq-mode", "3",
                    "-aq-strength", "1.1", "-preset", "fast", "-an", out_mp4], check=True, capture_output=True)


def text_center(d: ImageDraw.ImageDraw, y: int, s: str, f, fill, stroke: int = 0, x_center: int = W // 2) -> None:
    b = d.textbbox((0, 0), s, font=f, stroke_width=stroke)
    d.text((x_center - (b[2] - b[0]) // 2 - b[0], y), s, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def header_card(title: str, sub: str, accent=(255, 226, 96, 255), y0: int = 190, title_size: int = 58) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    ft = font(FONT_ANTON, title_size)
    fs = font(FONT_MED, 23)
    bt = d.textbbox((0, 0), title, font=ft)
    bs = d.textbbox((0, 0), sub, font=fs)
    tw = max(bt[2] - bt[0], bs[2] - bs[0])
    x0 = max(48, (W - tw) // 2 - 40)
    x1 = min(W - 48, (W + tw) // 2 + 40)
    d.rounded_rectangle((x0, y0, x1, y0 + 136), radius=22, fill=(11, 14, 26, 218), outline=accent[:3] + (150,), width=2)
    text_center(d, y0 + 10, title, ft, accent)
    text_center(d, y0 + 92, sub, fs, (226, 234, 246, 250))
    return ov


# ------------------------------------------------------------------------------------------------
# Jump kinematics & figure drawing
# ------------------------------------------------------------------------------------------------
CROUCH_T, PUSH_T, LAND_T = 0.30, 0.18, 0.30


@dataclass
class JumpState:
    h: float          # feet height above ground (m)
    crouch: float     # 0..1
    arm: float        # arm angle (rad): 0 = down, + = forward/up
    airborne: bool
    air_elapsed: float  # seconds of airtime so far (scene time)
    apex_reached: bool


def jump_state(t: float, launches: List[float], g: float) -> JumpState:
    """Scene-time kinematics for a figure that launches at each time in `launches` with speed V0."""
    T = 2.0 * V0 / g
    best = None
    for tl in launches:
        if t >= tl - CROUCH_T - PUSH_T:
            best = tl
    apex_reached = any(t >= tl + T / 2 for tl in launches)
    if best is None:
        return JumpState(0.0, 0.0, 0.10 + 0.03 * math.sin(t * 2.0), False, 0.0, apex_reached)
    tl = best
    if t < tl - PUSH_T:  # crouch down
        u = ease((t - (tl - CROUCH_T - PUSH_T)) / CROUCH_T)
        return JumpState(0.0, u, 0.10 - 0.95 * u, False, 0.0, apex_reached)
    if t < tl:  # explosive push
        u = (t - (tl - PUSH_T)) / PUSH_T
        u2 = u * u
        return JumpState(0.0, 1.0 - u2, -0.85 + 3.35 * ease(u), False, 0.0, apex_reached)
    if t < tl + T:  # ballistic flight
        tau = t - tl
        h = V0 * tau - 0.5 * g * tau * tau
        u = tau / T
        arm = 2.50 - 1.70 * ease(u)
        tuck = 0.10 * math.sin(math.pi * u)
        return JumpState(max(0.0, h), tuck, arm, True, tau, apex_reached)
    if t < tl + T + LAND_T:  # landing absorption
        u = (t - tl - T) / LAND_T
        return JumpState(0.0, 0.55 * math.sin(math.pi * u), 0.80 - 0.70 * ease(u), False, T, apex_reached)
    return JumpState(0.0, 0.0, 0.10 + 0.03 * math.sin(t * 2.0), False, T, apex_reached)


def _ik_knee(ankle, hip, l1=0.46, l2=0.46):
    dx, dy = hip[0] - ankle[0], hip[1] - ankle[1]
    d = max(1e-6, math.hypot(dx, dy))
    d = min(d, l1 + l2 - 1e-4)
    a = (l2 * l2 - l1 * l1 + d * d) / (2 * d)
    hgt = math.sqrt(max(0.0, l2 * l2 - a * a))
    mx, my = ankle[0] + a * dx / d, ankle[1] + a * dy / d
    # knee forward (+x) of the ankle-hip line
    px, py = -dy / d, dx / d
    if px < 0:
        px, py = -px, -py
    return (mx + hgt * px, my + hgt * py)


def draw_person(d: ImageDraw.ImageDraw, fx: float, feet_y: float, s: float, st: JumpState,
                col=(250, 244, 232, 255), back_col=(196, 190, 180, 255), outline=(10, 12, 20, 255), ss: float = 2.0) -> None:
    """Side-view human figure (meters -> px). `fx`, `feet_y`, `s` already in 1x px; drawn on an ss-x canvas."""
    c = st.crouch

    def P(x, y):
        return ((fx + x * s) * ss, (feet_y - y * s) * ss)

    ankle = (0.0, 0.09)
    hip = (-0.10 * c, 0.93 - 0.34 * c)
    knee = _ik_knee(ankle, hip)
    lean = 0.62 * c + 0.05
    sh = (hip[0] + 0.52 * math.sin(lean), hip[1] + 0.52 * math.cos(lean))
    head = (sh[0] + 0.21 * math.sin(lean) + 0.02, sh[1] + 0.21 * math.cos(lean))

    def arm_pts(a):
        el = (sh[0] + 0.30 * math.sin(a), sh[1] - 0.30 * math.cos(a))
        a2 = a + 0.35
        hd = (el[0] + 0.27 * math.sin(a2), el[1] - 0.27 * math.cos(a2))
        return el, hd

    def seg(p0, p1, w_m, color):
        w = max(2, int(round(w_m * s * ss)))
        a, b = P(*p0), P(*p1)
        d.line([a, b], fill=color, width=w)
        r = w / 2.0
        for q in (a, b):
            d.ellipse((q[0] - r, q[1] - r, q[0] + r, q[1] + r), fill=color)

    o = 0.035  # outline thickness (m)
    layers = [(outline, o), (None, 0.0)]
    for oc, extra in layers:
        # back leg & back arm
        bk = (knee[0] - 0.05, knee[1])
        el_b, hd_b = arm_pts(st.arm + 0.22)
        for p0, p1, wm in [((hip[0] - 0.03, hip[1]), bk, 0.15), (bk, (ankle[0] - 0.04, ankle[1]), 0.12),
                           ((ankle[0] - 0.08, 0.03), (ankle[0] + 0.15, 0.03), 0.08), (sh, el_b, 0.09), (el_b, hd_b, 0.08)]:
            seg(p0, p1, wm + extra, oc or back_col)
        # torso, front leg, front arm, head
        el_f, hd_f = arm_pts(st.arm)
        for p0, p1, wm in [(hip, sh, 0.27), (hip, knee, 0.16), (knee, ankle, 0.125),
                           ((ankle[0] - 0.05, 0.035), (ankle[0] + 0.19, 0.035), 0.085), (sh, el_f, 0.095), (el_f, hd_f, 0.085)]:
            seg(p0, p1, wm + extra, oc or col)
        hr = (0.118 + extra * 0.5) * s * ss
        hx, hy = P(*head)
        d.ellipse((hx - hr, hy - hr, hx + hr, hy + hr), fill=oc or col)


def draw_shadow(d: ImageDraw.ImageDraw, fx: float, ground_y: float, s: float, h: float, ss: float = 2.0, alpha: int = 120) -> None:
    k = 1.0 / (1.0 + 0.9 * h)
    rw = 0.36 * s * k * ss
    rh = 0.05 * s * k * ss
    cx, cy = (fx + 0.04 * s) * ss, ground_y * ss
    d.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=(0, 0, 0, int(alpha * k)))


# ------------------------------------------------------------------------------------------------
# Planet-surface jump scene
# ------------------------------------------------------------------------------------------------
@dataclass
class SceneCfg:
    body: str
    scale: float              # px per meter
    launches: List[float]     # scene-time launch instants (s)
    title: str
    sub: str
    tilt: float
    lon: float
    sun: Tuple[float, float, float] = (-0.35, -0.80, 0.50)
    atmo: Optional[Tuple[int, int, int]] = None
    atmo_strength: float = 0.0
    gas_giant: bool = False
    ghost: bool = True
    time_scale: float = 1.0   # scene seconds per real second
    show_airtime: bool = False
    tint: Tuple[float, float, float] = (1.0, 1.0, 1.0)
    saturation: float = 1.0
    ruler_major: float = 0.5
    ruler_minor: float = 0.1
    badge: Optional[str] = None
    extra_note: Optional[str] = None


GROUND_Y = 1400
RULER_X = 118
TOP_Y = 470
MAIN_X = 470
GHOST_X = 820
PLANET_R = 1300


def render_jump_scene(cfg: SceneCfg, n_frames: int, out_mp4: str, tag: str, frame0_master: Optional[str] = None,
                      preview_frames: Optional[List[int]] = None) -> None:
    out_dir = f"{SCRATCH}/{tag}_out" if preview_frames is None else f"{SCRATCH}/preview"
    os.makedirs(out_dir, exist_ok=True)
    rend = renderer(cfg.body, 8192)
    stars = starfield(hash(tag) % 1000)
    g = g_of(cfg.body)
    apex = apex_of(cfg.body)
    s = cfg.scale
    surface_y = GROUND_Y + (130 if cfg.gas_giant else 0)

    f_tag = font(FONT_BOLD, 24)
    f_small = font(FONT_BOLD, 22)
    f_ruler = font(FONT_BOLD, 21)
    f_air = font(FONT_BOLD, 30)
    hdr = header_card(cfg.title, cfg.sub)

    for i in (preview_frames if preview_frames is not None else range(n_frames)):
        t_real = i / FPS
        t = t_real * cfg.time_scale
        canvas = space_canvas(stars, t_real)
        rend.render_onto(canvas, cx=540.0, cy=surface_y + PLANET_R, radius=PLANET_R, lon_deg=cfg.lon + 0.25 * t_real,
                         tilt_deg=cfg.tilt, sun_dir=cfg.sun, ambient=0.06, contrast_gamma=1.04,
                         saturation=cfg.saturation, tint_rgb=cfg.tint, atmo_glow_rgb=cfg.atmo, atmo_strength=cfg.atmo_strength)
        # soft darkening of the lower surface so captions stay legible
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        canvas *= 1.0 - 0.45 * np.clip((yy - 0.80) / 0.20, 0, 1)
        canvas = add_dither(canvas, 7000 + i)
        base = Image.fromarray(canvas.astype(np.uint8)).convert("RGBA")

        ov2 = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(ov2)

        # Hypothetical floating platform for gas giants
        if cfg.gas_giant:
            px0, px1 = 330, 1010
            d2.ellipse((px0 * 2, (GROUND_Y - 6) * 2, px1 * 2, (GROUND_Y + 40) * 2), fill=(70, 80, 96, 255), outline=(170, 190, 215, 255), width=4)
            d2.ellipse((px0 * 2 + 8, (GROUND_Y - 12) * 2, px1 * 2 - 8, (GROUND_Y + 22) * 2), fill=(118, 132, 150, 255))
            for k in range(3):
                gy = GROUND_Y + 44 + 16 * k
                d2.ellipse(((px0 + 120 + 30 * k) * 2, gy * 2, (px1 - 120 - 30 * k) * 2, (gy + 10) * 2), fill=(140, 200, 255, 70 - 20 * k))

        sm = jump_state(t, cfg.launches, g)
        draw_shadow(d2, MAIN_X, GROUND_Y, s, sm.h)
        if cfg.ghost:
            sg = jump_state(t, cfg.launches, G_EARTH)
            draw_shadow(d2, GHOST_X, GROUND_Y, s, sg.h, alpha=60)
            ghost_layer = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
            gd = ImageDraw.Draw(ghost_layer)
            draw_person(gd, GHOST_X, GROUND_Y - sg.h * s, s, sg, col=(120, 214, 255, 255), back_col=(84, 168, 214, 255),
                        outline=(20, 50, 80, 255))
            ga = np.asarray(ghost_layer).copy()
            ga[:, :, 3] = (ga[:, :, 3].astype(np.float32) * 0.55).astype(np.uint8)
            ov2 = Image.alpha_composite(ov2, Image.fromarray(ga))
            d2 = ImageDraw.Draw(ov2)
        draw_person(d2, MAIN_X, GROUND_Y - sm.h * s, s, sm)

        # Dashed reference lines (2x canvas)
        def dashed(y, x0, x1, color, w=3):
            x = x0
            while x < x1:
                d2.line([(x * 2, y * 2), (min(x + 18, x1) * 2, y * 2)], fill=color, width=w * 2)
                x += 30

        if cfg.ghost:
            dashed(GROUND_Y - H_EARTH * s, RULER_X + 40, 1040, (120, 214, 255, 200))
        if sm.apex_reached or cfg.body == "earth" and sm.apex_reached:
            dashed(GROUND_Y - apex * s, RULER_X + 40, 1040, (255, 220, 92, 235))

        ov = ov2.reduce(2)
        d = ImageDraw.Draw(ov)

        # Metric ruler
        d.line([(RULER_X, TOP_Y), (RULER_X, GROUND_Y)], fill=(230, 236, 246, 210), width=3)
        m = 0.0
        while GROUND_Y - m * s >= TOP_Y - 0.5:
            y = GROUND_Y - m * s
            is_major = abs((m / cfg.ruler_major) - round(m / cfg.ruler_major)) < 1e-6
            ln = 26 if is_major else 12
            d.line([(RULER_X - ln // 2, y), (RULER_X + ln // 2, y)], fill=(230, 236, 246, 230 if is_major else 150), width=3 if is_major else 2)
            if is_major and m > 0:
                lab = f"{m:g} m"
                bbl = d.textbbox((0, 0), lab, font=f_ruler)
                d.text((RULER_X - 18 - (bbl[2] - bbl[0]), y - 13), lab, font=f_ruler, fill=(226, 232, 244, 235), stroke_width=2, stroke_fill=(0, 0, 0, 255))
            m = round(m + cfg.ruler_minor, 6)

        # Live feet-height marker on the ruler
        fy = GROUND_Y - sm.h * s
        d.polygon([(RULER_X + 6, fy), (RULER_X + 30, fy - 12), (RULER_X + 30, fy + 12)], fill=(255, 220, 92, 255))
        d.text((RULER_X + 36, fy - 15), f"{sm.h:.2f} m", font=f_tag, fill=(255, 226, 100, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

        # Labels on reference lines
        if cfg.ghost:
            yl = GROUND_Y - H_EARTH * s
            d.text((RULER_X + 150, yl + 6), "Earth 0.50 m", font=f_small, fill=(140, 220, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))
        if sm.apex_reached:
            ya = GROUND_Y - apex * s
            lab = f"{NAME[cfg.body]} {apex:.2f} m"
            bb = d.textbbox((0, 0), lab, font=f_tag)
            d.text((1040 - (bb[2] - bb[0]), ya - 36), lab, font=f_tag, fill=(255, 226, 100, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

        if cfg.show_airtime:
            air = min(sm.air_elapsed, airtime_of(cfg.body))
            txt = f"AIRTIME  {air:.2f} s"
            d.rounded_rectangle((W // 2 - 150, 346, W // 2 + 150, 396), radius=16, fill=(11, 14, 26, 210), outline=(255, 226, 96, 140), width=2)
            text_center(d, 352, txt, f_air, (255, 232, 110, 255))
        if cfg.badge:
            d.rounded_rectangle((W // 2 - 140, 346, W // 2 + 140, 394), radius=16, fill=(60, 18, 22, 220), outline=(255, 120, 110, 200), width=2)
            text_center(d, 354, cfg.badge, f_air, (255, 196, 186, 255))
        if cfg.extra_note:
            text_center(d, GROUND_Y + (64 if cfg.gas_giant else 24), cfg.extra_note, f_small, (215, 225, 240, 235), stroke=2)

        frame = Image.alpha_composite(base, ov)
        frame = Image.alpha_composite(frame, hdr).convert("RGB")
        if preview_frames is not None:
            frame.save(f"{out_dir}/{tag}_f{i:04d}.jpg", quality=90)
            continue
        frame.save(f"{out_dir}/f_{i:04d}.png")
        if i == 0 and frame0_master:
            frame.save(frame0_master)
    if preview_frames is None:
        encode_frames(out_dir, out_mp4, n_frames)


# ------------------------------------------------------------------------------------------------
# Lineup (opening question) & finale (answer)
# ------------------------------------------------------------------------------------------------
LINEUP = ["jupiter", "earth", "saturn", "mercury", "mars", "moon", "pluto"]  # ascending jump height
LINEUP_S = 95.0
LINEUP_FEET = 1385
DISC_R = 52
DISC_VIEW = {  # tilt, lon, atmo
    "jupiter": (12, 0, (230, 205, 170)), "earth": (18, 20, (110, 170, 255)), "saturn": (14, 0, (235, 215, 170)),
    "mercury": (10, 30, None), "mars": (12, 0, (235, 168, 128)), "moon": (6, 0, None), "pluto": (20, 10, None),
}


def col_x(i: int) -> float:
    return 77.0 + 154.0 * i


def draw_lineup_base(canvas: np.ndarray, t: float) -> None:
    for i, b in enumerate(LINEUP):
        tilt, lon, atmo = DISC_VIEW[b]
        renderer(b, 2048).render_onto(canvas, cx=col_x(i), cy=LINEUP_FEET + DISC_R + 2, radius=DISC_R, lon_deg=lon + 8 * t,
                                      tilt_deg=tilt, sun_dir=(-0.45, -0.55, 0.70), ambient=0.10,
                                      atmo_glow_rgb=atmo, atmo_strength=0.25 if atmo else 0.0)


def render_lineup(n_frames: int, out_mp4: str, tag: str, finale: bool, frame0_master: Optional[str] = None,
                  launch_t: float = 0.50) -> None:
    out_dir = f"{SCRATCH}/{tag}_out"
    os.makedirs(out_dir, exist_ok=True)
    stars = starfield(77)
    s = LINEUP_S
    f_name = font(FONT_BOLD, 21)
    f_q = font(FONT_ANTON, 44)
    f_val = font(FONT_BOLD, 23)

    if finale:
        hdr = header_card("SAME JUMP • SEVEN WORLDS", "Same 3.1 m/s takeoff • only gravity changes")
    else:
        hdr = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(hdr)
        hd.rounded_rectangle((50, 192, W - 50, 432), radius=26, fill=(14, 15, 24, 220), outline=(255, 224, 96, 165), width=3)
        text_center(hd, 206, "HOW HIGH COULD YOU JUMP", font(FONT_ANTON, 74), (255, 255, 255, 255), stroke=4)
        text_center(hd, 304, "ON OTHER PLANETS?", font(FONT_ANTON, 88), (255, 232, 92, 255), stroke=4)

    for i in range(n_frames):
        t = i / FPS
        canvas = space_canvas(stars, t)
        draw_lineup_base(canvas, t)
        canvas = add_dither(canvas, 9100 + i + (5000 if finale else 0))
        base = Image.fromarray(canvas.astype(np.uint8)).convert("RGBA")
        ov2 = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(ov2)
        for k, b in enumerate(LINEUP):
            x = col_x(k)
            ap = apex_of(b)
            if finale:
                st = jump_state(t, [launch_t], g_of(b))
                # target segment at the exact apex
                ya = LINEUP_FEET - ap * s
                for xx in range(int(x - 58), int(x + 58), 16):
                    d2.line([(xx * 2, ya * 2), ((xx + 9) * 2, ya * 2)], fill=(255, 220, 92, 220), width=5)
            else:
                st = JumpState(ap, 0.08, 2.0, True, 0.0, False)
                # dotted rise line from disc to apex feet
                for yy in range(int(LINEUP_FEET - 6), int(LINEUP_FEET - ap * s), -14):
                    d2.ellipse(((x - 2) * 2, (yy - 2) * 2, (x + 2) * 2, (yy + 2) * 2), fill=(255, 220, 92, 170))
            draw_shadow(d2, x, LINEUP_FEET, s, st.h, alpha=90)
            draw_person(d2, x - 4, LINEUP_FEET - st.h * s, s, st)
        ov = ov2.reduce(2)
        d = ImageDraw.Draw(ov)
        for k, b in enumerate(LINEUP):
            x = int(col_x(k))
            text_center(d, LINEUP_FEET + 2 * DISC_R + 14, NAME[b], f_name, (232, 238, 248, 255), stroke=2, x_center=x)
            ap = apex_of(b)
            head_top = LINEUP_FEET - ap * s - FIG_H * s
            if finale:
                text_center(d, int(head_top - 34), f"{ap:.2f} m", f_val, (255, 226, 100, 255), stroke=3, x_center=x)
            else:
                pulse = 1.0 + 0.06 * math.sin(t * 6.0 + k)
                fq = font(FONT_ANTON, int(44 * pulse))
                text_center(d, int(head_top + 6), "?", fq, (255, 226, 100, 255), stroke=3, x_center=x + 46)
        frame = Image.alpha_composite(base, ov)
        if not finale:
            # gentle camera push-in (content only), hook card stays fixed
            z = 1.0 + 0.035 * ease(t / max(1e-6, (n_frames - 1) / FPS))
            cw, ch = W / z, H / z
            x0, y0 = (W - cw) / 2, 470.0 * (1.0 - 1.0 / z)
            frame = frame.transform((W, H), Image.Transform.EXTENT, (x0, y0, x0 + cw, y0 + ch), resample=Image.Resampling.BICUBIC)
        frame = Image.alpha_composite(frame, hdr).convert("RGB")
        frame.save(f"{out_dir}/f_{i:04d}.png")
        if i == 0 and frame0_master:
            frame.save(frame0_master)
    encode_frames(out_dir, out_mp4, n_frames)


# ------------------------------------------------------------------------------------------------
# Jupiter establishing zoom & Saturn real footage
# ------------------------------------------------------------------------------------------------
def render_jupiter_establish(n_frames: int, out_mp4: str, tag: str) -> None:
    out_dir = f"{SCRATCH}/{tag}_out"
    os.makedirs(out_dir, exist_ok=True)
    rend = renderer("jupiter", 8192)
    stars = starfield(311)
    hdr = header_card("JUPITER HAS NO SOLID GROUND", "Imagine a platform where cloud pressure ≈ Earth's sea level")
    f_lab = font(FONT_BOLD, 22)
    dur = (n_frames - 1) / FPS
    for i in range(n_frames):
        t = i / FPS
        u = ease(t / dur)
        R = 400.0 * (1 - u) + 1500.0 * u
        top = 640.0 * (1 - u) + 1330.0 * u
        canvas = space_canvas(stars, t)
        rend.render_onto(canvas, cx=540.0, cy=top + R, radius=R, lon_deg=20 + 3 * t, tilt_deg=8 + 70 * u,
                         sun_dir=(-0.45, -0.60, 0.66), ambient=0.06, atmo_glow_rgb=(230, 205, 170), atmo_strength=0.18)
        canvas = add_dither(canvas, 6100 + i)
        base = Image.fromarray(canvas.astype(np.uint8)).convert("RGBA")
        ov2 = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(ov2)
        s = R * 0.055 / FIG_H * 1.6
        feet = top - 0.06 * R
        pw = 2.4 * s
        d2.ellipse(((540 - pw) * 2, (feet - 0.06 * s) * 2, (540 + pw) * 2, (feet + 0.22 * s) * 2), fill=(118, 132, 150, 255), outline=(180, 200, 225, 255), width=3)
        d2.ellipse(((540 - pw * 0.6) * 2, (feet + 0.3 * s) * 2, (540 + pw * 0.6) * 2, (feet + 0.55 * s) * 2), fill=(140, 200, 255, 80))
        draw_person(d2, 540, feet, s, JumpState(0.0, 0.0, 0.10 + 0.03 * math.sin(t * 2), False, 0.0, False))
        ov = ov2.reduce(2)
        d = ImageDraw.Draw(ov)
        la = int(255 * min(1.0, t / 0.5))
        text_center(d, int(feet + 0.7 * s + 18), "Hypothetical platform", f_lab, (220, 232, 248, la), stroke=2)
        frame = Image.alpha_composite(Image.alpha_composite(base, ov), hdr).convert("RGB")
        frame.save(f"{out_dir}/f_{i:04d}.png")
    encode_frames(out_dir, out_mp4, n_frames)


def render_saturn_footage(n_frames: int, out_mp4: str, tag: str) -> None:
    raw = f"{SCRATCH}/{tag}_raw"
    out_dir = f"{SCRATCH}/{tag}_out"
    os.makedirs(raw, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-ss", "15.500", "-i", ASSET_SATURN_SVS, "-frames:v", str(n_frames), f"{raw}/r_%04d.png"],
                   check=True, capture_output=True)
    stars = starfield(512)
    hdr = header_card("SATURN • 95× EARTH'S MASS", "Real NASA Goddard visualization of Saturn")
    crop_w = 1440.0
    out_w = 1080
    out_h = int(round(1080 * out_w / crop_w))
    y_off = 960 - out_h // 2 + 10
    feather = np.ones((out_h, 1), dtype=np.float32)
    fz = 70
    ramp = np.linspace(0, 1, fz, dtype=np.float32)
    feather[:fz, 0] = ramp
    feather[-fz:, 0] = ramp[::-1]
    for i in range(n_frames):
        u = i / max(1, n_frames - 1)
        src = Image.open(f"{raw}/r_{i + 1:04d}.png").convert("RGB")
        cx = 1005.0 + 40.0 * u
        x0 = max(0.0, min(1920 - crop_w, cx - crop_w / 2))
        clip = src.transform((out_w * 2, out_h * 2), Image.Transform.EXTENT, (x0, 0, x0 + crop_w, 1080),
                             resample=Image.Resampling.BICUBIC).resize((out_w, out_h), Image.Resampling.LANCZOS)
        canvas = space_canvas(stars, i / FPS)
        region = canvas[y_off:y_off + out_h]
        c_arr = np.asarray(clip, dtype=np.float32)
        a = feather[:, :, None]
        canvas[y_off:y_off + out_h] = np.maximum(region * (1 - a), 0) + np.maximum(c_arr, region) * a
        canvas = add_dither(canvas, 8800 + i)
        frame = Image.alpha_composite(Image.fromarray(canvas.astype(np.uint8)).convert("RGBA"), hdr).convert("RGB")
        frame.save(f"{out_dir}/f_{i:04d}.png")
    encode_frames(out_dir, out_mp4, n_frames)


# ------------------------------------------------------------------------------------------------
# Build all shots
# ------------------------------------------------------------------------------------------------
def scene_configs() -> Dict[str, SceneCfg]:
    return {
        "shot_02": SceneCfg("earth", 330, [0.70, 2.00], "EARTH • 9.8 m/s²", "Starting point: a 0.50 m standing jump",
                            tilt=70, lon=15, atmo=(110, 170, 255), atmo_strength=0.38, ghost=False),
        "shot_03": SceneCfg("mars", 290, [0.70, 3.15], "MARS • 38% OF EARTH'S GRAVITY", "Same takeoff speed as the 0.50 m Earth jump",
                            tilt=84, lon=-20, atmo=(235, 168, 128), atmo_strength=0.20),
        "shot_04": SceneCfg("mercury", 290, [0.30], "MERCURY • 38% OF EARTH'S GRAVITY", "Smaller than Mars, but denser  •  Mars: 1.33 m",
                            tilt=80, lon=40),
        "shot_05": SceneCfg("moon", 190, [0.50], "THE MOON • 17% OF EARTH'S GRAVITY", "Same takeoff speed  •  no spacesuit",
                            tilt=86, lon=0, show_airtime=True, ruler_major=1.0, ruler_minor=0.5),
        "shot_07": SceneCfg("jupiter", 330, [0.55, 1.65, 2.75], "JUPITER • 2.4× EARTH'S GRAVITY", "Hypothetical platform at cloud level  •  23.1 m/s²",
                            tilt=80, lon=20, atmo=(230, 205, 170), atmo_strength=0.18, gas_giant=True),
        "shot_09": SceneCfg("saturn", 330, [0.55, 2.10], "SATURN • 92% OF EARTH'S GRAVITY", "Hypothetical platform at cloud level  •  9.0 m/s²",
                            tilt=80, lon=0, atmo=(235, 215, 170), atmo_strength=0.18, gas_giant=True),
        "shot_10": SceneCfg("pluto", 95, [2.78], "PLUTO • 6% OF EARTH'S GRAVITY", "0.62 m/s²  •  real airtime ≈ 10 s",
                            tilt=100, lon=10, time_scale=2.0, ruler_major=1.0, ruler_minor=0.5, badge="2× SPEED"),
    }


def build_all(only: Optional[set] = None) -> None:
    def want(sid):
        return only is None or sid in only

    sp = {s.shot_id: s for s in SHOT_PLAN}
    cfgs = scene_configs()
    if want("shot_01"):
        render_lineup(sp["shot_01"].num_frames, f"{SHOTS_DIR}/shot_01.mp4", "s01", finale=False,
                      frame0_master=f"{SHOTS_DIR}/shot_01_frame0_master.png")
        print("  shot_01 ready (question lineup)")
    for sid in ["shot_02", "shot_03", "shot_04", "shot_05"]:
        if want(sid):
            render_jump_scene(cfgs[sid], sp[sid].num_frames, f"{SHOTS_DIR}/{sid}.mp4", sid)
            drop_big_textures()
            print(f"  {sid} ready ({cfgs[sid].body})")
    if want("shot_06"):
        render_jupiter_establish(sp["shot_06"].num_frames, f"{SHOTS_DIR}/shot_06.mp4", "s06")
        print("  shot_06 ready (Jupiter establishing zoom)")
    if want("shot_07"):
        render_jump_scene(cfgs["shot_07"], sp["shot_07"].num_frames, f"{SHOTS_DIR}/shot_07.mp4", "shot_07")
        drop_big_textures()
        print("  shot_07 ready (jupiter)")
    if want("shot_08"):
        render_saturn_footage(sp["shot_08"].num_frames, f"{SHOTS_DIR}/shot_08.mp4", "s08")
        print("  shot_08 ready (real NASA Saturn footage)")
    for sid in ["shot_09", "shot_10"]:
        if want(sid):
            render_jump_scene(cfgs[sid], sp[sid].num_frames, f"{SHOTS_DIR}/{sid}.mp4", sid)
            drop_big_textures()
            print(f"  {sid} ready ({cfgs[sid].body})")
    if want("shot_11"):
        render_lineup(sp["shot_11"].num_frames, f"{SHOTS_DIR}/shot_11.mp4", "s11", finale=True)
        print("  shot_11 ready (finale)")


# ------------------------------------------------------------------------------------------------
# Manifests, captions, final render, QC
# ------------------------------------------------------------------------------------------------
def write_manifests() -> None:
    fields = ["shot_id", "start_sec", "end_sec", "duration_sec", "exact_narration_phrase", "exact_subtitle_segment",
              "intended_visible_subject", "actual_media_path", "verified_source_url", "license", "why_visual_supports_sentence"]
    with open(f"{OUT_DIR}/sentence_to_shot_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for s in SHOT_PLAN:
            w.writerow({"shot_id": s.shot_id, "start_sec": f"{s.start_sec:.3f}", "end_sec": f"{s.end_sec:.3f}",
                        "duration_sec": f"{s.duration:.3f}", "exact_narration_phrase": s.narration_phrase,
                        "exact_subtitle_segment": s.subtitle_segments, "intended_visible_subject": s.intended_subject,
                        "actual_media_path": s.asset_path, "verified_source_url": s.source_url, "license": s.license,
                        "why_visual_supports_sentence": s.proof_rationale})
    lines = [
        "# Sentence-to-Shot Alignment Manifest — Proof of Wonder #03",
        "",
        f"- **Working Title:** {WORKING_TITLE}",
        "- **Frame-0 Thumbnail Hook:** `HOW HIGH COULD YOU JUMP / ON OTHER PLANETS?`",
        "- **Audio Authority:** `narration.mp3` (`en-US-AndrewMultilingualNeural`, `rate = -3%`, `91` `WordBoundary` tokens)",
        "- **Timeline:** `38.000s` (`1,140 frames @ 30 fps`), `11` distinct shots, BGM disabled, source audio stripped (`-an`).",
        "- **Physics:** identical takeoff speed `v0 = 3.13 m/s` (0.50 m Earth jump); `h = v0²/2g`, `T = 2v0/g`. Real-time motion except `shot_10` (labelled `2× SPEED`).",
        "- **Attribution:** planet maps © Solar System Scope (`CC BY 4.0`, based on NASA data); Mercury MESSENGER mosaic, Pluto `PIA19857`, and Saturn Goddard footage are NASA Public Domain.",
        "",
        "| Shot | Window (s) | Spoken Phrase | Subtitle Segment(s) | Visible Subject | Media Path | Source & License | Why It Supports the Sentence |",
        "| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for s in SHOT_PLAN:
        lines.append(f"| `{s.shot_id}` | `{s.start_sec:.2f}–{s.end_sec:.2f}` | \"{s.narration_phrase}\" | `{s.subtitle_segments}` | "
                     f"{s.intended_subject} | `{s.asset_path}` | {s.source_url} ({s.license}) | {s.proof_rationale} |")
    open(f"{OUT_DIR}/sentence_to_shot_manifest.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")


def parse_srt(path: str):
    blocks = re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip())
    cues = []
    for b in blocks:
        ls = [x.strip() for x in b.splitlines() if x.strip()]
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", ls[1])
        g = [int(x) for x in m.groups()]
        cues.append((int(ls[0]), g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000, " ".join(ls[2:])))
    return cues


def caption_overlay(idx: int, txt: str, f_cap) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    words = txt.split()
    lines, cur = [], []
    for wd in words:
        cand = " ".join(cur + [wd])
        bb = d.textbbox((0, 0), cand, font=f_cap)
        if bb[2] - bb[0] <= 860 or not cur:
            cur.append(wd)
        else:
            lines.append(cur)
            cur = [wd]
    if cur:
        lines.append(cur)
    lh = 60
    y0 = 1605 - len(lines) * lh // 2
    sp_w = d.textbbox((0, 0), "a b", font=f_cap)[2] - d.textbbox((0, 0), "ab", font=f_cap)[2]
    widths = [d.textbbox((0, 0), " ".join(l), font=f_cap)[2] for l in lines]
    mw = max(widths)
    d.rounded_rectangle(((W - mw) // 2 - 32, y0 - 18, (W + mw) // 2 + 32, y0 + len(lines) * lh + 12), radius=20, fill=(11, 16, 33, 214))
    hi = CUE_HIGHLIGHT_WORDS.get(idx, set())
    for k, l in enumerate(lines):
        adv = [d.textbbox((0, 0), wd, font=f_cap)[2] - d.textbbox((0, 0), wd, font=f_cap)[0] for wd in l]
        x = (W - (sum(adv) + sp_w * (len(l) - 1))) // 2
        for wd, a in zip(l, adv):
            d.text((x, y0 + k * lh), wd, font=f_cap, fill=(255, 228, 94, 255) if wd in hi else (255, 255, 255, 255),
                   stroke_width=3, stroke_fill=(0, 0, 0, 255))
            x += a + sp_w
    return ov


def render_final() -> None:
    tmp = f"{SCRATCH}/final"
    os.makedirs(f"{tmp}/raw", exist_ok=True)
    os.makedirs(f"{tmp}/cap", exist_ok=True)
    with open(f"{tmp}/concat.txt", "w") as f:
        for s in SHOT_PLAN:
            f.write(f"file '{SHOTS_DIR}/{s.shot_id}.mp4'\n")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/concat.txt", "-c", "copy", f"{tmp}/visual.mp4"],
                   check=True, capture_output=True)
    total = SHOT_PLAN[-1].f_end
    subprocess.run(["ffmpeg", "-y", "-i", f"{tmp}/visual.mp4", "-frames:v", str(total), f"{tmp}/raw/f_%04d.png"], check=True, capture_output=True)
    f_cap = font(FONT_BOLD, 46)
    cues = [(t0, t1, caption_overlay(i, txt, f_cap)) for i, t0, t1, txt in parse_srt(SRT_PATH)]
    for i in range(total):
        t = i / FPS
        im = Image.open(f"{tmp}/raw/f_{i + 1:04d}.png").convert("RGBA")
        for t0, t1, ov in cues:
            if t0 <= t <= t1:
                im = Image.alpha_composite(im, ov)
                break
        im.convert("RGB").save(f"{tmp}/cap/f_{i:04d}.png")
    dur = total / FPS
    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{tmp}/cap/f_%04d.png", "-i", AUDIO_PATH,
                    "-filter_complex", f"[1:a]apad=whole_dur={dur:.3f}[a]", "-map", "0:v:0", "-map", "[a]",
                    "-frames:v", str(total), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS), "-crf", "15",
                    "-aq-mode", "3", "-aq-strength", "1.1", "-preset", "medium", "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                    "-movflags", "+faststart", FINAL_MP4], check=True, capture_output=True)
    print("Rendered", FINAL_MP4)

    f0 = Image.open(f"{SHOTS_DIR}/shot_01_frame0_master.png").convert("RGBA")
    for t0, t1, ov in cues:
        if t0 <= 0.0 <= t1:
            f0 = Image.alpha_composite(f0, ov)
    f0p = f"{tmp}/frame0_final.png"
    f0.convert("RGB").save(f0p)
    export_first_frame_thumbnail(mp4_path=FINAL_MP4, raw_frame0_rgb_path=f0p, title_preview=WORKING_TITLE,
                                 generate_preview_sheet=True, native_crop_box=(620, 560, 1080, 1020))
    shutil.copy2(f"{OUT_DIR}/{VIDEO_SLUG}.jpg", f"{OUT_DIR}/thumbnail.jpg")
    pr = subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", FINAL_MP4]).decode()
    open(f"{OUT_DIR}/ffprobe_validation.json", "w").write(pr)


def grab(ts: float, path: str, scale: Optional[Tuple[int, int]] = None) -> Image.Image:
    cmd = ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", FINAL_MP4, "-frames:v", "1"]
    if scale:
        cmd += ["-vf", f"scale={scale[0]}:{scale[1]}"]
    subprocess.run(cmd + [path], check=True, capture_output=True)
    return Image.open(path).convert("RGB")


def qc_sheets() -> None:
    tmp = f"{SCRATCH}/qc"
    os.makedirs(tmp, exist_ok=True)
    ft = font(FONT_BOLD, 28)
    fl = font(FONT_BOLD, 19)
    fx = font(FONT_MED, 16)
    # contact sheet (1 frame per shot)
    ow, oh = 270, 480
    cs = Image.new("RGB", (36 + 4 * (ow + 18), 96 + 3 * (oh + 76)), (14, 17, 25))
    d = ImageDraw.Draw(cs)
    d.text((30, 26), f"PROOF OF WONDER #03 — CONTACT SHEET ({VIDEO_SLUG}.mp4)", font=ft, fill=(255, 255, 255))
    for k, s in enumerate(SHOT_PLAN):
        ts = 0.0 if k == 0 else s.start_sec + s.duration * 0.62
        im = grab(ts, f"{tmp}/cs_{k}.jpg", (ow, oh))
        r, c = divmod(k, 4)
        x0, y0 = 28 + c * (ow + 18), 86 + r * (oh + 76)
        cs.paste(im, (x0, y0))
        d.text((x0 + 4, y0 + oh + 6), f"{s.shot_id} ({s.start_sec:.1f}–{s.end_sec:.1f}s)", font=fl, fill=(255, 232, 100))
        d.text((x0 + 4, y0 + oh + 32), s.narration_phrase[:34] + ("..." if len(s.narration_phrase) > 34 else ""), font=fx, fill=(215, 226, 240))
    cs.save(f"{OUT_DIR}/contact_sheet.jpg", quality=93)
    # transitions sheet
    cw, ch = 225, 400
    rh = ch + 26
    s2 = Image.new("RGB", (1560, 90 + len(SHOT_PLAN) * rh + 20), (15, 18, 26))
    d2 = ImageDraw.Draw(s2)
    d2.text((30, 24), "FINAL SHOTS & TRANSITIONS (IN / MID / OUT per shot)", font=ft, fill=(255, 255, 255))
    for k, s in enumerate(SHOT_PLAN):
        y0 = 84 + k * rh
        for j, (tg, ts) in enumerate([("IN", s.start_sec + 0.10), ("MID", (s.start_sec + s.end_sec) / 2), ("OUT", s.end_sec - 0.10)]):
            im = grab(ts, f"{tmp}/tr_{k}_{j}.jpg", (cw, ch))
            ImageDraw.Draw(im).text((6, 4), f"{tg} {ts:.2f}s", font=fx, fill=(120, 225, 255), stroke_width=2, stroke_fill=(0, 0, 0))
            s2.paste(im, (30 + j * (cw + 12), y0))
        rx = 30 + 3 * (cw + 12) + 18
        d2.text((rx, y0 + 14), f"{s.shot_id.upper()} [{s.start_sec:.2f}s -> {s.end_sec:.2f}s]", font=fl, fill=(255, 232, 100))
        d2.text((rx, y0 + 48), f"\"{s.narration_phrase}\"", font=fx, fill=(255, 255, 255))
        d2.text((rx, y0 + 80), s.intended_subject[:100], font=fx, fill=(190, 210, 230))
        d2.text((rx, y0 + 104), s.intended_subject[100:200], font=fx, fill=(190, 210, 230))
    s2.save(f"{OUT_DIR}/final_shots_and_transitions_contact_sheet.jpg", quality=92)
    # first 3 seconds
    tw, th = 250, 444
    s1 = Image.new("RGB", (40 + 6 * (tw + 14), th + 120), (15, 18, 26))
    d1 = ImageDraw.Draw(s1)
    d1.text((30, 24), "FIRST 3 SECONDS AUDIT", font=ft, fill=(255, 255, 255))
    for k, ts in enumerate([0.0, 0.6, 1.2, 1.8, 2.4, 3.0]):
        s1.paste(grab(ts, f"{tmp}/f3_{k}.jpg", (tw, th)), (30 + k * (tw + 14), 76))
        d1.text((38 + k * (tw + 14), 84 + th), f"t = {ts:.2f}s", font=fl, fill=(255, 232, 100))
    s1.save(f"{OUT_DIR}/first_3_seconds_audit_sheet.jpg", quality=93)
    # 1:1 native crops at each shot's mid-point around the main subject
    boxes = {"shot_01": (540, 380, 1080, 920), "shot_06": (270, 1000, 810, 1540), "shot_08": (270, 650, 810, 1190), "shot_11": (540, 380, 1080, 920)}
    s3 = Image.new("RGB", (30 + 4 * 554, 100 + 3 * 594), (12, 15, 22))
    d3 = ImageDraw.Draw(s3)
    d3.text((28, 22), "1:1 NATIVE PIXEL QC (540x540 unscaled crops from the final MP4)", font=ft, fill=(255, 255, 255))
    for k, s in enumerate(SHOT_PLAN):
        ts = (s.start_sec + s.end_sec) / 2
        full = grab(ts, f"{tmp}/n_{k}.png")
        crop = full.crop(boxes.get(s.shot_id, (300, 700, 840, 1240)))
        r, c = divmod(k, 4)
        s3.paste(crop, (22 + c * 554, 84 + r * 594))
        d3.text((28 + c * 554, 84 + r * 594 + 546), f"{s.shot_id} @ {ts:.2f}s", font=fl, fill=(125, 230, 255))
    s3.save(f"{OUT_DIR}/native_1to1_pixel_qc_sheet.jpg", quality=95)
    print("QC sheets written")


def preview_sheet() -> None:
    """Render one representative frame per scene for fast composition tuning (no video encode)."""
    out = f"{SCRATCH}/preview"
    os.makedirs(out, exist_ok=True)
    print("preview: use --stage pre_render --only-shots to render individual shots")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["pre_render", "render_final", "all"], required=True)
    ap.add_argument("--only-shots", default="")
    a = ap.parse_args()
    only = {x.strip() for x in a.only_shots.split(",") if x.strip()} or None
    if a.stage in ("pre_render", "all"):
        write_manifests()
        build_all(only)
    if a.stage in ("render_final", "all"):
        render_final()
        qc_sheets()
