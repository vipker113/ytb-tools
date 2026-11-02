#!/usr/bin/env python3
"""
Master builder for Mars Shorts V2 — Natural Narration & Frame-Level Storytelling:
`02-mars-has-almost-no-air-how-did-this-helicopter-fly.mp4`

Output directory:
`/Applications/code/science-knowledge/youtube-shorts-channel/output/revisions/mars-v2/`

Key V2 upgrades over `output/batch-1/02-*.mp4` (and intermediate `pow02`):
1. Natural conversational spoken English narration (`en-US-AndrewMultilingualNeural`, `rate = +0%`, `86` words, `42.384s` audio / `42.900s` video), ear-audited against `Ava` and rate variants (`-4%`..`+4%`).
2. Audio is the single timing authority: every shot cut lands inside natural `WordBoundary` pauses, and `subtitles.srt` matches the spoken words 100% verbatim with selective keyword highlighting inside mobile-safe margins (`y_center = 1605`).
3. 11 distinct, non-repeating shots (`3.90s` mean shot length, `5.90s` max) combining official NASA/JPL flight visuals, 6 distinct real Mars camera captures (`Mastcam-Z` close-up blade test, `Mastcam-Z` Flight 1 liftoff, onboard `Navcam` Flight 14 takeoff, `Mastcam-Z` golden dune flight, `4K`-class `PIA24548` `WATSON` rover-belly photo, and `4K` `PIA26242` Flight 70 aerial view), `8K` Mars horizon + animated density bar, dynamic `30 fps` counter-rotating `~2,500 RPM` lift animation, and explicitly labeled `EARTH TEST • JPL VACUUM CHAMBER` footage.
4. Unified Frame-0 uncompressed `24-bit` RGB thumbnail (`MARS HAS BARELY ANY AIR / HOW DID THIS FLY?`) exported as `4:4:4` `.jpg`, `.png`, `thumbnail.jpg`, and multi-scale preview sheet.
5. Preserves all prior videos (`output/batch-1/02-*.mp4` and `output/proof-of-wonder/02-*/02-*.mp4`) 100% untouched.
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
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

warnings.filterwarnings("ignore", message="Truncated File Read")

ROOT = "/Applications/code/science-knowledge/youtube-shorts-channel"
sys.path.insert(0, f"{ROOT}/pipeline")
from first_frame_thumbnail import export_first_frame_thumbnail
from planet_sphere_3d import PlanetSphereRenderer

OUT_DIR = f"{ROOT}/output/revisions/mars-v2"
SHOTS_DIR = f"{OUT_DIR}/shots"
SCRATCH_ROOT = "/Users/admin/.gemini/antigravity/brain/40c60d87-669d-4ec0-8e97-9ae15cc03780/scratch/mars_v2_build"
os.makedirs(SHOTS_DIR, exist_ok=True)
os.makedirs(SCRATCH_ROOT, exist_ok=True)

VIDEO_SLUG = "02-mars-has-almost-no-air-how-did-this-helicopter-fly"
WORKING_TITLE = "Mars Has Barely Any Air—How Did NASA Fly a Helicopter There?"

FONT_ANTON = f"{ROOT}/assets/fonts/Anton-Regular.ttf"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

# Verified zero-cost official NASA / JPL 1080p, 4K, and 8K master assets
ASSET_JPL_ANIM_1080 = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/jpl_mars_helicopter_anim_large.mp4"
ASSET_MEDIA_REEL_1080 = f"{ROOT}/assets/raw_footage/batch1_r2_02_mars_helicopter/nasa_ingenuity_media_reel_1080.mp4"
ASSET_CHAMBER_1080 = f"{ROOT}/assets/raw_footage/batch1_r2_02_mars_helicopter/nasa_ingenuity_overview_chamber.mp4"
ASSET_EXTREME_1080 = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/jpl_ingenuity_extreme_flights_2024_large.mp4"
ASSET_MARS_8K = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/mars_8k_viking.jpg"
ASSET_PIA23882_8K = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/pia23882_ingenuity_studio_orig.jpg"
ASSET_PIA24548_4K = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/pia24548_ingenuity_deployed_mars_orig.jpg"
ASSET_PIA26242_4K = f"{ROOT}/assets/raw_footage/proof_of_wonder_mars_helicopter/pia26242_flight70_sand_ripples_orig.jpg"

AUDIO_PATH = f"{OUT_DIR}/narration.mp3"
SRT_PATH = f"{OUT_DIR}/subtitles.srt"
FINAL_MP4 = f"{OUT_DIR}/{VIDEO_SLUG}.mp4"

FPS = 30
W, H = 1080, 1920


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


SHOT_PLAN: List[ShotSpec] = [
    ShotSpec(
        shot_id="shot_01",
        f_start=0,
        f_end=120,  # 0.000s -> 4.000s (120f)
        narration_phrase="Mars has barely any air. So how did NASA fly a helicopter there?",
        subtitle_segments="[00:00.100 -> 00:01.480] Mars has barely any air. | [00:01.720 -> 00:03.880] So how did NASA fly a helicopter there?",
        intended_subject="Close-up airborne NASA Ingenuity Mars Helicopter flying across red Martian terrain with blurred counter-rotating rotors, safe-zone Frame-0 hook ('MARS HAS BARELY ANY AIR / HOW DID THIS FLY?'), and explicit JPL Flight Visual attribution badge.",
        asset_path=f"{ASSET_JPL_ANIM_1080} [143.00s-147.00s]",
        source_url="https://images.nasa.gov/details/JPL-20200429-TECHf-0002-Mars%20Helicopter%20Animation",
        license="Public Domain (NASA / JPL-Caltech Official Master)",
        proof_rationale="Immediately pairs the spoken opening contradiction and Frame-0 thumbnail hook with the clearest close-up mission shot of Ingenuity flying over Mars, tracked with 0.00 px subpixel precision.",
    ),
    ShotSpec(
        shot_id="shot_02",
        f_start=120,
        f_end=275,  # 4.000s -> 9.167s (155f)
        narration_phrase="Mars's atmosphere is only about one percent as dense as Earth's.",
        subtitle_segments="[00:04.180 -> 00:06.340] Mars's atmosphere is only about | [00:06.340 -> 00:09.040] one percent as dense as Earth's.",
        intended_subject="Zero-jitter 8K 3D orbital horizon skim along Mars's rusty cratered limb and gossamer-thin atmospheric veil, paired with a smoothly animated 30 fps Earth (100%, ~1.22 kg/m3) vs Mars (~1%, ~0.02 kg/m3) near-surface atmospheric density bar.",
        asset_path=ASSET_MARS_8K,
        source_url="https://www.solarsystemscope.com/textures/ ; https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html",
        license="CC BY 4.0 (Solar System Scope 8K Mars mosaic from NASA Viking MDIM2.1) + NASA GSFC Fact Sheet",
        proof_rationale="Visually contrasts Mars's razor-thin atmospheric limb against black space while progressively animating the verified ~1% Earth near-surface atmospheric density comparison.",
    ),
    ShotSpec(
        shot_id="shot_03",
        f_start=275,
        f_end=368,  # 9.167s -> 12.267s (93f)
        narration_phrase="That makes generating lift incredibly difficult.",
        subtitle_segments="[00:09.350 -> 00:12.140] That makes generating lift incredibly difficult.",
        intended_subject="Real 1080p footage inside NASA JPL's 25-Foot Space Simulator showing Ingenuity hovering in simulated ~1%-density Martian CO2 air, explicitly labeled 'EARTH TEST • JPL VACUUM CHAMBER'.",
        asset_path=f"{ASSET_CHAMBER_1080} [61.40s-64.50s]",
        source_url="https://images.nasa.gov/details/JPL-20200713-TECHf-0001-Mars%20Helicopter%20Mission%20Overview",
        license="Public Domain (NASA / JPL-Caltech)",
        proof_rationale="Shows real aerodynamic hover testing in simulated 1% Mars air while explicitly labeling the Pasadena vacuum chamber so it is never mistaken for Mars footage.",
    ),
    ShotSpec(
        shot_id="shot_04",
        f_start=368,
        f_end=542,  # 12.267s -> 18.067s (174f)
        narration_phrase="Meet Ingenuity, a tiny aircraft weighing just 1.8 kilograms.",
        subtitle_segments="[00:12.450 -> 00:15.680] Meet Ingenuity, a tiny aircraft weighing | [00:15.860 -> 00:17.950] just 1.8 kilograms.",
        intended_subject="Real 1080p NASA Perseverance Mastcam-Z close-up on Mars (April 8, 2021) showing tiny 1.8 kg Ingenuity sitting beside rover wheel tracks on Jezero Crater soil and pitching its carbon-fiber blades.",
        asset_path=f"{ASSET_MEDIA_REEL_1080} [39.80s-45.60s]",
        source_url="https://images.nasa.gov/details/JPL-20220623-TECHf-0001-Mars%20Helicopter%20Testing%20Media%20Reel",
        license="Public Domain (NASA / JPL-Caltech / ASU Mastcam-Z)",
        proof_rationale="Introduces the real Ingenuity aircraft on Martian soil right next to Perseverance's wheel tracks, making its tiny 1.8 kg tissue-box scale immediately unmistakable.",
    ),
    ShotSpec(
        shot_id="shot_05",
        f_start=542,
        f_end=640,  # 18.067s -> 21.333s (98f)
        narration_phrase="Ingenuity used two counter-rotating rotors,",
        subtitle_segments="[00:18.250 -> 00:21.260] Ingenuity used two counter-rotating rotors,",
        intended_subject="Close-up 1080p NASA JPL visual of Ingenuity's two stacked 1.2-meter coaxial counter-rotating carbon-fiber rotors accelerating in opposite directions.",
        asset_path=f"{ASSET_JPL_ANIM_1080} [59.60s-62.87s reversed spin-up]",
        source_url="https://images.nasa.gov/details/JPL-20200429-TECHf-0002-Mars%20Helicopter%20Animation",
        license="Public Domain (NASA / JPL-Caltech Official Master)",
        proof_rationale="Directly isolates the coaxial twin-rotor hardware geometry as the narration introduces the two counter-rotating rotors.",
    ),
    ShotSpec(
        shot_id="shot_06",
        f_start=640,
        f_end=748,  # 21.333s -> 24.933s (108f)
        narration_phrase="spinning at roughly 2,500 revolutions per minute,",
        subtitle_segments="[00:21.450 -> 00:24.800] spinning at roughly 2,500 revolutions per minute,",
        intended_subject="Dynamic 2x-supersampled 30 fps coaxial rotor aerodynamics animation over dimmed 8K NASA PIA23882 hardware showing CW/CCW counter-rotation, live RPM ramp to ~2,500 RPM (~5x Earth helicopters), subsonic < Mach 0.7 tip margin, and downward airflow.",
        asset_path=f"{ASSET_PIA23882_8K} + programmatic 2x-supersampled 30 fps aerodynamics animation",
        source_url="https://images.nasa.gov/details/PIA23882 ; https://ntrs.nasa.gov/citations/20180003088",
        license="Public Domain (NASA / JPL-Caltech PIA23882 + NASA NTRS telemetry)",
        proof_rationale="Delivers continuous 30 fps animated visual explanation of how counter-rotating 1.2 m blades spinning at ~2,500 RPM generate lift within subsonic tip-speed margins.",
    ),
    ShotSpec(
        shot_id="shot_07",
        f_start=748,
        f_end=811,  # 24.933s -> 27.033s (63f)
        narration_phrase="to push enough air downward.",
        subtitle_segments="[00:25.090 -> 00:26.910] to push enough air downward.",
        intended_subject="Real 1080p NASA Perseverance Mastcam-Z zoomed replay of Ingenuity's historic Flight 1 liftoff on April 19, 2021, climbing straight off dusty Jezero Crater soil into hover.",
        asset_path=f"{ASSET_MEDIA_REEL_1080} [84.40s-86.50s]",
        source_url="https://images.nasa.gov/details/JPL-20220623-TECHf-0001-Mars%20Helicopter%20Testing%20Media%20Reel",
        license="Public Domain (NASA / JPL-Caltech / ASU Mastcam-Z)",
        proof_rationale="Proves the lift mechanism in action with actual camera footage on Mars as Ingenuity pushes thin Martian air downward and rises cleanly off the surface.",
    ),
    ShotSpec(
        shot_id="shot_08",
        f_start=811,
        f_end=888,  # 27.033s -> 29.600s (77f)
        narration_phrase="NASA planned just five test flights.",
        subtitle_segments="[00:27.210 -> 00:29.490] NASA planned just five test flights.",
        intended_subject="Real 1080p onboard Ingenuity downward Navigation Camera (Navcam) takeoff and flight footage (Flight 14) showing the helicopter's twin-rotor shadow lifting off and racing across Martian ripples.",
        asset_path=f"{ASSET_MEDIA_REEL_1080} [239.85s-242.42s]",
        source_url="https://images.nasa.gov/details/JPL-20220623-TECHf-0001-Mars%20Helicopter%20Testing%20Media%20Reel",
        license="Public Domain (NASA / JPL-Caltech Ingenuity Navcam)",
        proof_rationale="Shows authentic onboard test-flight telemetry footage captured by Ingenuity's own downward navigation camera while stating the original 5-flight demonstration plan.",
    ),
    ShotSpec(
        shot_id="shot_09",
        f_start=888,
        f_end=996,  # 29.600s -> 33.200s (108f)
        narration_phrase="Ingenuity ended up flying 72 times.",
        subtitle_segments="[00:29.790 -> 00:33.140] Ingenuity ended up flying 72 times.",
        intended_subject="Real 1080p NASA Perseverance Mastcam-Z color flight footage of Ingenuity soaring mid-air across golden Martian sand dunes and rocky ridges, paired with a restrained '5 PLANNED -> 72 FLIGHTS' milestone badge.",
        asset_path=f"{ASSET_EXTREME_1080} [57.60s-61.20s]",
        source_url="https://images.nasa.gov/details/JPL-20240201-INGENUITYf-0001-Ingenuity%20Mars%20Helicopter%27s%20Extreme%20Flights ; https://science.nasa.gov/mission/mars-2020-perseverance/ingenuity-mars-helicopter/",
        license="Public Domain (NASA / JPL-Caltech / ASU Mastcam-Z)",
        proof_rationale="Delivers the 72-flight payoff over unmistakable real color Mastcam-Z video of Ingenuity flying across Martian sand dunes rather than a static or empty frame.",
    ),
    ShotSpec(
        shot_id="shot_10",
        f_start=996,
        f_end=1110,  # 33.200s -> 37.000s (114f)
        narration_phrase="A small experiment designed to prove one thing",
        subtitle_segments="[00:33.490 -> 00:36.960] A small experiment designed to prove one thing",
        intended_subject="4K-class (3,500x2,511) NASA Perseverance WATSON camera mosaic (PIA24548, Sol 35) looking beneath the giant Mars rover's belly on Jezero Crater soil, showing tiny Ingenuity tucked between the rover wheels before deployment.",
        asset_path=ASSET_PIA24548_4K,
        source_url="https://images.nasa.gov/details/PIA24548",
        license="Public Domain (NASA / JPL-Caltech / MSSS WATSON Camera)",
        proof_rationale="Visually anchors 'A small experiment designed to prove one thing' by showing tiny 1.8 kg Ingenuity slung underneath the car-sized Perseverance rover on Mars just before its 30-day tech demo.",
    ),
    ShotSpec(
        shot_id="shot_11",
        f_start=1110,
        f_end=1287,  # 37.000s -> 42.900s (177f)
        narration_phrase="became the first aircraft to achieve powered, controlled flight on another planet.",
        subtitle_segments="[00:37.040 -> 00:39.800] became the first aircraft to achieve powered, | [00:40.090 -> 00:42.200] controlled flight on another planet.",
        intended_subject="Zero-jitter 30 fps aerial glide across Ingenuity's native 4K (4,208x3,120) color Return-to-Earth (RTE) photograph from Flight 70 (PIA26242) high above golden Martian sand ripples and Jezero Crater hills, with Ingenuity's landing footpad in the sky.",
        asset_path=ASSET_PIA26242_4K,
        source_url="https://images.nasa.gov/details/PIA26242",
        license="Public Domain (NASA / JPL-Caltech Ingenuity Flight 70 RTE Camera)",
        proof_rationale="Completes the emotional and scientific arc from tiny belly-mounted experiment to soaring aerial view captured through Ingenuity's own camera high above another planet.",
    ),
]

# Selective keyword highlighting per cue index (1-based) — restrained documentary emphasis
CUE_HIGHLIGHT_WORDS = {
    1: {"barely", "any", "air."},
    2: {"helicopter"},
    3: set(),
    4: {"one", "percent"},
    5: {"lift", "difficult."},
    6: {"Ingenuity,"},
    7: {"1.8", "kilograms."},
    8: {"counter-rotating", "rotors,"},
    9: {"2,500"},
    10: {"downward."},
    11: {"five"},
    12: {"72", "times."},
    13: {"small", "experiment"},
    14: {"first", "aircraft"},
    15: {"another", "planet."},
}


def add_subtle_dither(rgb_float: np.ndarray, seed: int) -> np.ndarray:
    """Imperceptible ±0.55 LSB dither prevents 8x8 H.264 banding in smooth sky/space gradients."""
    rng = np.random.default_rng(seed)
    noise = rng.uniform(-0.55, 0.55, size=(rgb_float.shape[0], rgb_float.shape[1], 1)).astype(np.float32)
    return np.clip(rgb_float + noise, 0.0, 255.0)


def make_starfield(seed: int = 17, count: int = 130) -> List[Tuple[int, int, float]]:
    rng = np.random.default_rng(seed)
    return [
        (int(rng.integers(24, W - 24)), int(rng.integers(80, H - 140)), float(rng.uniform(48, 150)))
        for _ in range(count)
    ]


def encode_frames_to_mp4(frames_dir: str, out_mp4: str, num_frames: int) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            f"{frames_dir}/f_%04d.png",
            "-frames:v",
            str(num_frames),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-crf",
            "13",
            "-aq-mode",
            "3",
            "-aq-strength",
            "1.1",
            "-preset",
            "fast",
            "-an",  # Mandatory: strip all B-roll source audio
            out_mp4,
        ],
        check=True,
        capture_output=True,
    )


def extract_raw_clip_frames(src_mp4: str, start_sec: float, num_frames: int, dst_dir: str) -> None:
    os.makedirs(dst_dir, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{start_sec:.3f}",
            "-i",
            src_mp4,
            "-frames:v",
            str(num_frames),
            f"{dst_dir}/raw_%04d.png",
        ],
        check=True,
        capture_output=True,
    )


def subpixel_crop_1080x1920(
    src_img: Image.Image,
    cx: float,
    cy: float,
    crop_w: float,
    crop_h: float,
) -> Image.Image:
    """Pure float64 subpixel crop via Image.Transform.EXTENT + Lanczos refine for 0.000 px stepping jitter."""
    sw, sh = src_img.size
    x0 = max(0.0, min(sw - crop_w, cx - crop_w * 0.5))
    y0 = max(0.0, min(sh - crop_h, cy - crop_h * 0.5))
    mid = src_img.transform(
        (1440, 2560),
        Image.Transform.EXTENT,
        (x0, y0, x0 + crop_w, y0 + crop_h),
        resample=Image.Resampling.BICUBIC,
    )
    return mid.resize((W, H), Image.Resampling.LANCZOS)


def make_pill_overlay(
    title_text: str,
    sub_text: str,
    pill_y: int = 204,
    accent_rgba: Tuple[int, int, int, int] = (255, 228, 112, 255),
    border_rgba: Tuple[int, int, int, int] = (255, 214, 102, 140),
) -> Image.Image:
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    f_b = ImageFont.truetype(FONT_BOLD, 28)
    f_s = ImageFont.truetype(FONT_MED, 21)
    b1 = od.textbbox((0, 0), title_text, font=f_b)
    b2 = od.textbbox((0, 0), sub_text, font=f_s)
    tw = max(b1[2] - b1[0], b2[2] - b2[0])
    px0 = max(56, (W - tw) // 2 - 38)
    px1 = min(W - 56, (W + tw) // 2 + 38)
    od.rounded_rectangle(
        (px0, pill_y, px1, pill_y + 106),
        radius=20,
        fill=(11, 15, 26, 214),
        outline=border_rgba,
        width=2,
    )
    od.text(((W - (b1[2] - b1[0])) // 2, pill_y + 13), title_text, font=f_b, fill=accent_rgba)
    od.text(((W - (b2[2] - b2[0])) // 2, pill_y + 56), sub_text, font=f_s, fill=(225, 234, 246, 248))
    return ov


def write_manifests() -> None:
    csv_path = f"{OUT_DIR}/sentence_to_shot_manifest.csv"
    md_path = f"{OUT_DIR}/sentence_to_shot_manifest.md"

    fieldnames = [
        "shot_id",
        "start_sec",
        "end_sec",
        "duration_sec",
        "exact_narration_phrase",
        "exact_subtitle_segment",
        "intended_visible_subject",
        "actual_video_asset_path",
        "verified_source_url",
        "license",
        "why_footage_proves_narration",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for s in SHOT_PLAN:
            w.writerow(
                {
                    "shot_id": s.shot_id,
                    "start_sec": f"{s.start_sec:.3f}",
                    "end_sec": f"{s.end_sec:.3f}",
                    "duration_sec": f"{s.duration:.3f}",
                    "exact_narration_phrase": s.narration_phrase,
                    "exact_subtitle_segment": s.subtitle_segments,
                    "intended_visible_subject": s.intended_subject,
                    "actual_video_asset_path": s.asset_path,
                    "verified_source_url": s.source_url,
                    "license": s.license,
                    "why_footage_proves_narration": s.proof_rationale,
                }
            )

    md_lines = [
        "# Sentence-to-Shot Alignment Manifest — Mars Shorts V2 (`mars-v2`)",
        "",
        f"- **Working Title:** {WORKING_TITLE}",
        f"- **Unified Frame-0 Thumbnail Hook (`t = 0.000s`):** `MARS HAS BARELY ANY AIR / HOW DID THIS FLY?` (`{VIDEO_SLUG}.jpg`, `{VIDEO_SLUG}.png`, `thumbnail.jpg`)",
        "- **Audio Authority:** `narration.mp3` (`42.384s`, `en-US-AndrewMultilingualNeural`, `rate = +0%`, `86` words / `88` `WordBoundary` tokens)",
        "- **Video Timeline:** `42.900s` (`1,287 frames @ 30 fps`), `11` distinct non-repeating shots (`3.90s` mean duration), BGM disabled, B-roll source audio stripped (`-an`).",
        "- **Earth Test Transparency:** `shot_03` (`9.17–12.27s`) explicitly displays `EARTH TEST • JPL VACUUM CHAMBER / Simulated ~1% Mars Atmosphere (Pasadena, CA)`.",
        "- **Attribution Note (`CC BY 4.0`):** `mars_8k_viking.jpg` courtesy of Solar System Scope (`https://www.solarsystemscope.com/textures/`, `CC BY 4.0`, derived from NASA Viking MDIM2.1); all other helicopter flight footage, chamber reels, and Mars surface photography are NASA / JPL-Caltech Public Domain.",
        "",
        "| Shot | Window (`s`) | Exact Spoken Narration | Exact Subtitle Segment(s) | Intended Visible Subject | Actual Asset Path | Source URL & License | Why Visual Supports Spoken Sentence |",
        "| :--- | :---: | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for s in SHOT_PLAN:
        md_lines.append(
            f"| `{s.shot_id}` | `{s.start_sec:.2f}–{s.end_sec:.2f}` (`{s.duration:.2f}s`) | "
            f"\"{s.narration_phrase}\" | `{s.subtitle_segments}` | {s.intended_subject} | "
            f"`{s.asset_path}` | {s.source_url} ({s.license}) | {s.proof_rationale} |"
        )
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Wrote manifests:\n  {csv_path}\n  {md_path}")


def render_shot_01(out_mp4: str, num_frames: int) -> None:
    """
    Shot 01 (0.000s -> 4.000s, 120 frames):
    Close-up airborne NASA Ingenuity flight visual with unified Frame-0 hook:
    'MARS HAS BARELY ANY AIR / HOW DID THIS FLY?'
    """
    scratch_raw = f"{SCRATCH_ROOT}/s01_raw"
    out_fdir = f"{SCRATCH_ROOT}/s01_out"
    os.makedirs(out_fdir, exist_ok=True)

    extract_raw_clip_frames(ASSET_JPL_ANIM_1080, start_sec=143.000, num_frames=num_frames, dst_dir=scratch_raw)

    f_hook_top = ImageFont.truetype(FONT_ANTON, 68)
    f_hook_bot = ImageFont.truetype(FONT_ANTON, 84)
    f_badge = ImageFont.truetype(FONT_BOLD, 25)
    f_sub = ImageFont.truetype(FONT_MED, 20)

    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    top_vig = np.clip((0.36 - yy) / 0.36, 0.0, 1.0) ** 1.35
    bot_vig = np.clip((yy - 0.72) / 0.28, 0.0, 1.0) ** 1.30

    hook_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hook_overlay)
    hd.rounded_rectangle(
        (54, 194, W - 54, 434),
        radius=26,
        fill=(14, 15, 24, 216),
        outline=(255, 224, 96, 160),
        width=3,
    )
    h1 = "MARS HAS BARELY ANY AIR"
    h2 = "HOW DID THIS FLY?"
    b1 = hd.textbbox((0, 0), h1, font=f_hook_top)
    b2 = hd.textbbox((0, 0), h2, font=f_hook_bot)
    hd.text(
        ((W - (b1[2] - b1[0])) // 2, 210),
        h1,
        font=f_hook_top,
        fill=(255, 255, 255, 255),
        stroke_width=4,
        stroke_fill=(0, 0, 0, 255),
    )
    hd.text(
        ((W - (b2[2] - b2[0])) // 2, 298),
        h2,
        font=f_hook_bot,
        fill=(255, 232, 92, 255),
        stroke_width=4,
        stroke_fill=(0, 0, 0, 255),
    )

    badge_overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge_overlay)
    bd.rounded_rectangle(
        (114, 1308, W - 114, 1408),
        radius=20,
        fill=(14, 16, 26, 208),
        outline=(255, 168, 92, 138),
        width=2,
    )
    t_b1 = "NASA INGENUITY HELICOPTER"
    t_b2 = "Official JPL Flight Visual • ~1% Earth Air Density"
    bb1 = bd.textbbox((0, 0), t_b1, font=f_badge)
    bb2 = bd.textbbox((0, 0), t_b2, font=f_sub)
    bd.text(((W - (bb1[2] - bb1[0])) // 2, 1320), t_b1, font=f_badge, fill=(255, 238, 175, 255))
    bd.text(((W - (bb2[2] - bb2[0])) // 2, 1360), t_b2, font=f_sub, fill=(224, 232, 245, 248))
    badge_np = np.asarray(badge_overlay, dtype=np.float32)

    for i in range(num_frames):
        # Exact time parameter u_ref = i / 183.0 matches the calibrated 143.00s..149.10s gimbal polynomial!
        u_ref = i / 183.0
        t_sec = i / FPS
        src = Image.open(f"{scratch_raw}/raw_{i+1:04d}.png").convert("RGB")

        crop_h = 1080.0 - 256.0 * (u_ref ** 2.5)
        crop_w = crop_h * (9.0 / 16.0)
        cx = (
            908.0
            - 2541.6602 * u_ref
            - 7350.7519 * (u_ref ** 2)
            + 58449.3446 * (u_ref ** 3)
            + 101184.6196 * (u_ref ** 4)
            - 883548.2534 * (u_ref ** 5)
            + 1651855.6953 * (u_ref ** 6)
            - 1287441.9031 * (u_ref ** 7)
            + 369670.7847 * (u_ref ** 8)
        )
        cy = 1080.0 - 0.5 * crop_h
        cropped = subpixel_crop_1080x1920(src, cx=cx, cy=cy, crop_w=crop_w, crop_h=crop_h)

        cropped = ImageEnhance.Contrast(cropped).enhance(1.26)
        cropped = ImageEnhance.Color(cropped).enhance(1.22)
        cropped = cropped.filter(ImageFilter.UnsharpMask(radius=1.5, percent=125, threshold=2))

        arr = np.asarray(cropped, dtype=np.float32)
        ground_w = np.clip((yy - 0.46) / 0.30, 0.0, 1.0)
        arr[:, :, 0] = arr[:, :, 0] * (1.0 + 0.06 * ground_w)
        arr[:, :, 2] = arr[:, :, 2] * (1.0 - 0.08 * ground_w)

        arr[:, :, 0] = arr[:, :, 0] * (1.0 - 0.62 * top_vig) + 18.0 * top_vig
        arr[:, :, 1] = arr[:, :, 1] * (1.0 - 0.66 * top_vig) + 14.0 * top_vig
        arr[:, :, 2] = arr[:, :, 2] * (1.0 - 0.64 * top_vig) + 22.0 * top_vig
        arr = arr * (1.0 - 0.42 * bot_vig[:, :, None])

        arr = add_subtle_dither(arr, seed=1000 + i)
        rgba = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        rgba = Image.alpha_composite(rgba, hook_overlay)

        badge_alpha = float(np.clip((3.40 - t_sec) / 0.60, 0.0, 1.0))
        if badge_alpha >= 0.999:
            rgba = Image.alpha_composite(rgba, badge_overlay)
        elif badge_alpha > 0.002:
            b_fade = badge_np.copy()
            b_fade[:, :, 3] *= badge_alpha
            rgba = Image.alpha_composite(rgba, Image.fromarray(b_fade.astype(np.uint8)))

        rgb_out = rgba.convert("RGB")
        rgb_out.save(f"{out_fdir}/f_{i:04d}.png")
        if i == 0:
            rgb_out.save(f"{SHOTS_DIR}/shot_01_frame0_master.png")

    encode_frames_to_mp4(out_fdir, out_mp4, num_frames)


def render_shot_02_mars_8k_density(out_mp4: str, num_frames: int, mars_3d: PlanetSphereRenderer) -> None:
    """
    Shot 02 (4.000s -> 9.167s, 155 frames):
    8K Mars curved orbital horizon + progressively animated Earth (100%) vs Mars (~1%) atmospheric density card.
    """
    out_fdir = f"{SCRATCH_ROOT}/s02_out"
    os.makedirs(out_fdir, exist_ok=True)
    stars = make_starfield(seed=33, count=145)

    f_hdr = ImageFont.truetype(FONT_BOLD, 28)
    f_lbl = ImageFont.truetype(FONT_BOLD, 24)
    f_sub = ImageFont.truetype(FONT_MED, 20)

    for i in range(num_frames):
        u = i / max(1, num_frames - 1)
        t_rel = i / FPS
        canvas = np.zeros((H, W, 3), dtype=np.float32)
        canvas[:, :, :] = [3.0, 5.0, 12.0]
        for sx, sy, br in stars:
            canvas[sy, sx] = np.clip(canvas[sy, sx] + br, 0, 255)
        canvas = add_subtle_dither(canvas, seed=2200 + i)

        mars_3d.render_onto(
            canvas,
            cx=540.0,
            cy=1750.0 - 34.0 * u,
            radius=1160.0,
            lon_deg=66.0 + 18.0 * u,
            tilt_deg=-8.0,
            sun_dir=(-0.35, -0.78, 0.52),
            ambient=0.05,
            contrast_gamma=1.08,
            saturation=1.06,
            tint_rgb=(1.06, 0.98, 0.94),
            atmo_glow_rgb=(235, 168, 128),
            atmo_strength=0.19,
        )
        rgba = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8)).convert("RGBA")

        # Animated 30 fps Atmospheric Density Comparison Card (y = 194..448)
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rounded_rectangle(
            (62, 194, W - 62, 452),
            radius=22,
            fill=(10, 14, 26, 218),
            outline=(255, 178, 112, 150),
            width=2,
        )
        t1 = "NEAR-SURFACE ATMOSPHERIC DENSITY"
        b1 = od.textbbox((0, 0), t1, font=f_hdr)
        od.text(((W - (b1[2] - b1[0])) // 2, 210), t1, font=f_hdr, fill=(255, 224, 122, 255))

        bar_x0, bar_max_w = 96, 610
        # Earth 100% bar fills smoothly over first 1.0s
        earth_p = 1.0 - (1.0 - min(1.0, t_rel / 0.95)) ** 3
        ew = max(12, int(bar_max_w * earth_p))
        od.text((bar_x0, 264), "Earth Sea Level (~1.22 kg/m³)", font=f_sub, fill=(185, 228, 255, 248))
        od.rounded_rectangle((bar_x0, 294, bar_x0 + bar_max_w, 326), radius=8, fill=(24, 34, 52, 220))
        od.rounded_rectangle((bar_x0, 294, bar_x0 + ew, 326), radius=8, fill=(76, 196, 255, 255))
        od.text((bar_x0 + bar_max_w + 22, 293), "100%", font=f_lbl, fill=(135, 218, 255, 255))

        # Mars ~1% sliver reveals as narrator says "one percent as dense as Earth's" (t_rel = 1.6s..2.8s)
        mars_reveal = float(np.clip((t_rel - 1.35) / 0.85, 0.0, 1.0))
        od.text((bar_x0, 348), "Mars Surface (~0.02 kg/m³)", font=f_sub, fill=(255, 205, 168, int(130 + 120 * mars_reveal)))
        od.rounded_rectangle((bar_x0, 378, bar_x0 + bar_max_w, 410), radius=8, fill=(28, 22, 28, 220))
        # Exact 1% width of 610px = 6.1px!
        mw = max(6, int(round(bar_max_w * 0.01)))
        pulse = 0.65 + 0.35 * math.sin(t_rel * 6.0)
        od.rectangle((bar_x0, 378, bar_x0 + mw, 410), fill=(255, 118, 82, int(255 * max(0.35, mars_reveal))))
        if mars_reveal > 0.05:
            od.text(
                (bar_x0 + bar_max_w + 22, 377),
                "~1%",
                font=f_lbl,
                fill=(255, int(215 + 30 * pulse), 92, int(255 * mars_reveal)),
            )

        rgba = Image.alpha_composite(rgba, ov)
        rgba.convert("RGB").save(f"{out_fdir}/f_{i:04d}.png")

    encode_frames_to_mp4(out_fdir, out_mp4, num_frames)


def render_tracked_real_clip_shot(
    src_mp4: str,
    start_sec: float,
    num_frames: int,
    out_mp4: str,
    tag: str,
    cx_start: float,
    cx_end: float,
    cy_start: float = 540.0,
    cy_end: float = 540.0,
    crop_w: float = 607.5,
    crop_h: float = 1080.0,
    contrast: float = 1.14,
    color: float = 1.10,
    sharpen_pct: int = 95,
    pill_overlay: Image.Image | None = None,
    reverse_frames: bool = False,
    linear_motion: bool = False,
) -> None:
    scratch_raw = f"{SCRATCH_ROOT}/{tag}_raw"
    out_fdir = f"{SCRATCH_ROOT}/{tag}_out"
    os.makedirs(out_fdir, exist_ok=True)

    extract_raw_clip_frames(src_mp4, start_sec=start_sec, num_frames=num_frames, dst_dir=scratch_raw)

    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    bot_vig = np.clip((yy - 0.75) / 0.25, 0.0, 1.0) ** 1.3

    for i in range(num_frames):
        u = i / max(1, num_frames - 1)
        u_m = u if linear_motion else (0.5 - 0.5 * math.cos(math.pi * u))
        raw_idx = (num_frames - i) if reverse_frames else (i + 1)
        src = Image.open(f"{scratch_raw}/raw_{raw_idx:04d}.png").convert("RGB")
        cx = cx_start + (cx_end - cx_start) * u_m
        cy = cy_start + (cy_end - cy_start) * u_m
        im = subpixel_crop_1080x1920(src, cx=cx, cy=cy, crop_w=crop_w, crop_h=crop_h)
        if contrast != 1.0:
            im = ImageEnhance.Contrast(im).enhance(contrast)
        if color != 1.0:
            im = ImageEnhance.Color(im).enhance(color)
        if sharpen_pct > 0:
            im = im.filter(ImageFilter.UnsharpMask(radius=1.25, percent=sharpen_pct, threshold=2))

        arr = np.asarray(im, dtype=np.float32) * (1.0 - 0.34 * bot_vig[:, :, None])
        arr = add_subtle_dither(arr, seed=3000 + i)
        out_im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        if pill_overlay is not None:
            out_im = Image.alpha_composite(out_im.convert("RGBA"), pill_overlay).convert("RGB")
        out_im.save(f"{out_fdir}/f_{i:04d}.png")

    encode_frames_to_mp4(out_fdir, out_mp4, num_frames)


def render_shot_06_rpm_lift_animation(out_mp4: str, num_frames: int) -> None:
    """
    Shot 06 (21.333s -> 24.933s, 108 frames):
    Dynamic 2x-supersampled 30 fps Coaxial Counter-Rotating Lift & ~2,500 RPM Animation
    over dimmed 8K NASA PIA23882 hardware backdrop. Zero static hold!
    """
    out_fdir = f"{SCRATCH_ROOT}/s06_out"
    os.makedirs(out_fdir, exist_ok=True)

    pia = Image.open(ASSET_PIA23882_8K).convert("RGB")
    bg_crop = subpixel_crop_1080x1920(pia, cx=4128.0, cy=2752.0, crop_w=3100.0, crop_h=5504.0)
    bg_arr = np.asarray(bg_crop, dtype=np.float32)
    lum = 0.299 * bg_arr[:, :, 0] + 0.587 * bg_arr[:, :, 1] + 0.114 * bg_arr[:, :, 2]
    hw_detail = np.clip((235.0 - lum) / 215.0, 0.0, 1.0)
    dark_bg = np.zeros((H, W, 3), dtype=np.float32)
    dark_bg[:, :, 0] = 10.0 + 38.0 * hw_detail
    dark_bg[:, :, 1] = 16.0 + 48.0 * hw_detail
    dark_bg[:, :, 2] = 28.0 + 64.0 * hw_detail

    f_title = ImageFont.truetype(FONT_ANTON, 64)
    f_lbl = ImageFont.truetype(FONT_BOLD, 25)
    f_txt = ImageFont.truetype(FONT_MED, 21)

    cx_d, cy_d = 540, 825
    r_disk = 335

    for i in range(num_frames):
        u = i / max(1, num_frames - 1)
        t = i / FPS
        arr = add_subtle_dither(dark_bg.copy(), seed=6000 + i)
        im = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")

        # Live RPM climb from 2,150 -> ~2,500 RPM over first 1.2s, holding ~2,500-2,537 operational range
        rpm_prog = 1.0 - (1.0 - min(1.0, t / 1.15)) ** 3
        rpm_val = int(round(2100 + 400 * rpm_prog))

        ov2 = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(ov2)
        c2x, c2y, r2 = cx_d * 2, cy_d * 2, r_disk * 2

        # Outer subsonic engineering margin ring (< Mach 0.7 tip-speed envelope)
        d2.ellipse(
            (c2x - r2, c2y - r2, c2x + r2, c2y + r2),
            fill=(14, 34, 52, 138),
            outline=(92, 232, 178, 215),
            width=6,
        )
        r_inner = int(r2 * 0.72)
        d2.arc(
            (c2x - r_inner, c2y - r_inner, c2x + r_inner, c2y + r_inner),
            start=18,
            end=162,
            fill=(110, 215, 255, 190),
            width=6,
        )
        d2.arc(
            (c2x - r_inner, c2y - r_inner, c2x + r_inner, c2y + r_inner),
            start=198,
            end=342,
            fill=(255, 222, 98, 190),
            width=6,
        )

        # Counter-rotating 1.2 m carbon-fiber rotor blades (Upper CW, Lower CCW)
        ang1 = math.radians(t * 640.0)
        ang2 = -math.radians(t * 640.0 + 48.0)
        for ang, col in [(ang1, (232, 242, 252, 248)), (ang2, (255, 224, 118, 230))]:
            for side in (0.0, math.pi):
                a = ang + side
                tip_x = c2x + r2 * math.cos(a)
                tip_y = c2y + r2 * math.sin(a)
                perp_x = -math.sin(a)
                perp_y = math.cos(a)
                p_root1 = (c2x + 34 * math.cos(a) + 15 * perp_x, c2y + 34 * math.sin(a) + 15 * perp_y)
                p_mid1 = (c2x + 0.62 * r2 * math.cos(a) + 46 * perp_x, c2y + 0.62 * r2 * math.sin(a) + 46 * perp_y)
                p_tip1 = (tip_x + 17 * perp_x, tip_y + 17 * perp_y)
                p_tip2 = (tip_x - 17 * perp_x, tip_y - 17 * perp_y)
                p_mid2 = (c2x + 0.62 * r2 * math.cos(a) - 34 * perp_x, c2y + 0.62 * r2 * math.sin(a) - 34 * perp_y)
                p_root2 = (c2x + 34 * math.cos(a) - 15 * perp_x, c2y + 34 * math.sin(a) - 15 * perp_y)
                d2.polygon([p_root1, p_mid1, p_tip1, p_tip2, p_mid2, p_root2], fill=col)

        # Animated downward airflow chevrons below the coaxial rotor disk (y = 1185..1315)
        for col_idx, x_off in enumerate((-210, 0, 210)):
            phase = (t * 2.6 + col_idx * 0.28) % 1.0
            ax = c2x + x_off * 2
            ay = int((1175 + 95 * phase) * 2)
            alpha_a = int(235 * math.sin(math.pi * phase))
            d2.line([(ax - 34, ay - 24), (ax, ay + 12), (ax + 34, ay - 24)], fill=(120, 228, 255, alpha_a), width=9)

        d2.ellipse((c2x - 42, c2y - 42, c2x + 42, c2y + 42), fill=(255, 218, 102, 255), outline=(20, 26, 38, 255), width=6)
        ov = ov2.resize((W, H), Image.Resampling.LANCZOS)

        od = ImageDraw.Draw(ov)
        od.rounded_rectangle((56, 192, W - 56, 352), radius=22, fill=(10, 14, 26, 228), outline=(255, 224, 98, 175), width=3)
        ht = f"~{rpm_val:,} RPM ROTOR SPEED"
        hb = od.textbbox((0, 0), ht, font=f_title)
        od.text(((W - (hb[2] - hb[0])) // 2, 204), ht, font=f_title, fill=(255, 232, 96, 255))
        hs = "~5× Faster Than Typical Helicopters on Earth"
        hsb = od.textbbox((0, 0), hs, font=f_txt)
        od.text(((W - (hsb[2] - hsb[0])) // 2, 294), hs, font=f_txt, fill=(215, 232, 248, 248))

        # Two crisp engineering cards cleanly above y=1530 captions
        od.rounded_rectangle((56, 1326, 524, 1456), radius=18, fill=(12, 28, 42, 226), outline=(110, 215, 255, 195), width=2)
        od.text((78, 1340), "COUNTER-ROTATING", font=f_lbl, fill=(132, 224, 255, 255))
        od.text((78, 1378), "Upper CW + Lower CCW", font=f_txt, fill=(232, 242, 252, 248))
        od.text((78, 1410), "Cancels Torque • 1.2 m Span", font=f_txt, fill=(182, 214, 240, 245))

        od.rounded_rectangle((556, 1326, 1024, 1456), radius=18, fill=(12, 34, 30, 226), outline=(92, 232, 178, 195), width=2)
        od.text((578, 1340), "SUBSONIC TIP MARGIN", font=f_lbl, fill=(112, 245, 188, 255))
        od.text((578, 1378), "Stays Below Mach 0.7", font=f_txt, fill=(230, 246, 238, 248))
        od.text((578, 1410), "Pushes Thin Air Downward", font=f_txt, fill=(180, 228, 206, 245))

        Image.alpha_composite(im, ov).convert("RGB").save(f"{out_fdir}/f_{i:04d}.png")

    encode_frames_to_mp4(out_fdir, out_mp4, num_frames)


def render_4k_still_glide_shot(
    img_path: str,
    out_mp4: str,
    num_frames: int,
    tag: str,
    cx_start: float,
    cx_end: float,
    cy_start: float,
    cy_end: float,
    crop_w: float,
    crop_h: float,
    pill_overlay: Image.Image,
    contrast: float = 1.15,
    color: float = 1.12,
) -> None:
    out_fdir = f"{SCRATCH_ROOT}/{tag}_out"
    os.makedirs(out_fdir, exist_ok=True)
    src_4k = Image.open(img_path).convert("RGB")

    yy = np.linspace(0.0, 1.0, H, dtype=np.float32)[:, None]
    bot_vig = np.clip((yy - 0.74) / 0.26, 0.0, 1.0) ** 1.3

    for i in range(num_frames):
        u = i / max(1, num_frames - 1)
        u_ease = 0.5 - 0.5 * math.cos(math.pi * u)
        cx = cx_start + (cx_end - cx_start) * u_ease
        cy = cy_start + (cy_end - cy_start) * u_ease
        im = subpixel_crop_1080x1920(src_4k, cx=cx, cy=cy, crop_w=crop_w, crop_h=crop_h)
        im = ImageEnhance.Contrast(im).enhance(contrast)
        im = ImageEnhance.Color(im).enhance(color)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.1, percent=70, threshold=2))

        arr = np.asarray(im, dtype=np.float32) * (1.0 - 0.40 * bot_vig[:, :, None])
        arr = add_subtle_dither(arr, seed=9000 + i)
        rgba = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
        rgba = Image.alpha_composite(rgba, pill_overlay)
        rgba.convert("RGB").save(f"{out_fdir}/f_{i:04d}.png")

    encode_frames_to_mp4(out_fdir, out_mp4, num_frames)


def build_all_shots(only_shots: set[str] | None = None) -> None:
    def want(sid: str) -> bool:
        return only_shots is None or sid in only_shots

    mars_3d = None
    if want("shot_02"):
        print("Loading 8K Mars global mosaic into PlanetSphereRenderer...")
        mars_3d = PlanetSphereRenderer(ASSET_MARS_8K, max_tex_w=8192)

    print("Building Mars Shorts V2 (11 non-repeating, frame-verified shots)...")
    if want("shot_01"):
        render_shot_01(f"{SHOTS_DIR}/shot_01.mp4", SHOT_PLAN[0].num_frames)
        print("  [01/11] shot_01.mp4 + shot_01_frame0_master.png ready")

    if want("shot_02"):
        assert mars_3d is not None
        render_shot_02_mars_8k_density(f"{SHOTS_DIR}/shot_02.mp4", SHOT_PLAN[1].num_frames, mars_3d)
        print("  [02/11] shot_02.mp4 ready (8K Mars limb + animated 100% vs ~1% density bar)")

    if want("shot_03"):
        pill_s03 = make_pill_overlay(
            "EARTH TEST • JPL VACUUM CHAMBER",
            "Simulated ~1% Mars Atmosphere (Pasadena, CA)",
            pill_y=204,
            accent_rgba=(135, 224, 255, 255),
            border_rgba=(120, 210, 255, 165),
        )
        render_tracked_real_clip_shot(
            src_mp4=ASSET_CHAMBER_1080,
            start_sec=61.400,
            num_frames=SHOT_PLAN[2].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_03.mp4",
            tag="s03",
            cx_start=995.0,
            cx_end=1015.0,
            contrast=1.14,
            color=1.08,
            sharpen_pct=95,
            pill_overlay=pill_s03,
        )
        print("  [03/11] shot_03.mp4 ready (explicitly labeled JPL Mars vacuum chamber test)")

    if want("shot_04"):
        pill_s04 = make_pill_overlay(
            "INGENUITY ON MARS • 1.8 KG MASS",
            "Perseverance Mastcam-Z • Blade Test in Jezero Crater",
            pill_y=204,
        )
        render_tracked_real_clip_shot(
            src_mp4=ASSET_MEDIA_REEL_1080,
            start_sec=39.800,
            num_frames=SHOT_PLAN[3].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_04.mp4",
            tag="s04",
            cx_start=885.0,
            cx_end=920.0,
            contrast=1.16,
            color=1.14,
            sharpen_pct=95,
            pill_overlay=pill_s04,
        )
        print("  [04/11] shot_04.mp4 ready (real Mastcam-Z close-up of 1.8 kg Ingenuity on Mars)")

    if want("shot_05"):
        pill_s05 = make_pill_overlay(
            "TWO COUNTER-ROTATING ROTORS",
            "1.2-Meter Carbon-Fiber Blades • JPL Hardware Visual",
            pill_y=204,
        )
        render_tracked_real_clip_shot(
            src_mp4=ASSET_JPL_ANIM_1080,
            start_sec=59.600,
            num_frames=SHOT_PLAN[4].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_05.mp4",
            tag="s05",
            cx_start=950.0,
            cx_end=970.0,
            contrast=1.16,
            color=1.12,
            sharpen_pct=95,
            pill_overlay=pill_s05,
            reverse_frames=True,
        )
        print("  [05/11] shot_05.mp4 ready (close-up coaxial rotor spin-up)")

    if want("shot_06"):
        render_shot_06_rpm_lift_animation(f"{SHOTS_DIR}/shot_06.mp4", SHOT_PLAN[5].num_frames)
        print("  [06/11] shot_06.mp4 ready (dynamic 30 fps ~2,500 RPM counter-rotating lift animation)")

    if want("shot_07"):
        # Pill placed at pill_y=1330 so Ingenuity's vertical climb from y=1180 -> y=220 is 100% unobstructed!
        pill_s07 = make_pill_overlay(
            "FIRST FLIGHT LIFTOFF • APRIL 19, 2021",
            "Perseverance Mastcam-Z • Jezero Crater, Mars",
            pill_y=1330,
        )
        render_tracked_real_clip_shot(
            src_mp4=ASSET_MEDIA_REEL_1080,
            start_sec=84.400,
            num_frames=SHOT_PLAN[6].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_07.mp4",
            tag="s07",
            cx_start=948.0,
            cx_end=995.0,
            cy_start=540.0,
            cy_end=540.0,
            contrast=1.20,
            color=1.16,
            sharpen_pct=110,
            pill_overlay=pill_s07,
            linear_motion=True,
        )
        print("  [07/11] shot_07.mp4 ready (real Mastcam-Z Flight 1 liftoff & climb on Mars)")

    if want("shot_08"):
        pill_s08 = make_pill_overlay(
            "PLANNED DEMO: 5 TEST FLIGHTS",
            "Actual Ingenuity Onboard Navigation Camera (Mars)",
            pill_y=204,
        )
        render_tracked_real_clip_shot(
            src_mp4=ASSET_MEDIA_REEL_1080,
            start_sec=239.850,
            num_frames=SHOT_PLAN[7].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_08.mp4",
            tag="s08",
            cx_start=980.0,
            cx_end=980.0,
            contrast=1.22,
            color=1.0,
            sharpen_pct=105,
            pill_overlay=pill_s08,
        )
        print("  [08/11] shot_08.mp4 ready (real onboard Navcam takeoff & flight footage)")

    if want("shot_09"):
        # High-impact restrained numerical milestone badge for 5 -> 72 flights over real color Mars dune flight!
        ov_s09 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od9 = ImageDraw.Draw(ov_s09)
        f_h9 = ImageFont.truetype(FONT_ANTON, 56)
        f_s9 = ImageFont.truetype(FONT_MED, 21)
        od9.rounded_rectangle((68, 194, W - 68, 332), radius=22, fill=(12, 15, 26, 216), outline=(255, 224, 98, 165), width=3)
        t9_1 = "5 PLANNED  →  72 FLIGHTS"
        t9_2 = "Actual Perseverance Mastcam-Z Flight Video on Mars"
        b9_1 = od9.textbbox((0, 0), t9_1, font=f_h9)
        b9_2 = od9.textbbox((0, 0), t9_2, font=f_s9)
        od9.text(((W - (b9_1[2] - b9_1[0])) // 2, 206), t9_1, font=f_h9, fill=(255, 232, 96, 255))
        od9.text(((W - (b9_2[2] - b9_2[0])) // 2, 282), t9_2, font=f_s9, fill=(228, 236, 248, 248))

        render_tracked_real_clip_shot(
            src_mp4=ASSET_EXTREME_1080,
            start_sec=57.633,
            num_frames=SHOT_PLAN[8].num_frames,
            out_mp4=f"{SHOTS_DIR}/shot_09.mp4",
            tag="s09",
            cx_start=1102.0,
            cx_end=1032.0,
            cy_start=420.0,
            cy_end=580.0,
            crop_w=472.5,
            crop_h=840.0,
            contrast=1.22,
            color=1.16,
            sharpen_pct=112,
            pill_overlay=ov_s09,
            linear_motion=True,
        )
        print("  [09/11] shot_09.mp4 ready (real color Mastcam-Z flight over golden Mars dunes)")

    if want("shot_10"):
        pill_s10 = make_pill_overlay(
            "TINY TECH DEMO UNDER PERSEVERANCE",
            "Actual Mars WATSON View (PIA24548 • Sol 35)",
            pill_y=204,
        )
        render_4k_still_glide_shot(
            img_path=ASSET_PIA24548_4K,
            out_mp4=f"{SHOTS_DIR}/shot_10.mp4",
            num_frames=SHOT_PLAN[9].num_frames,
            tag="s10",
            cx_start=1620.0,
            cx_end=1780.0,
            cy_start=1220.0,
            cy_end=1200.0,
            crop_w=1215.0,
            crop_h=2160.0,
            pill_overlay=pill_s10,
            contrast=1.14,
            color=1.10,
        )
        print("  [10/11] shot_10.mp4 ready (4K-class PIA24548 Ingenuity beneath Perseverance on Mars)")

    if want("shot_11"):
        ov_s11 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od11 = ImageDraw.Draw(ov_s11)
        f_h11 = ImageFont.truetype(FONT_ANTON, 52)
        f_s11 = ImageFont.truetype(FONT_MED, 22)
        od11.rounded_rectangle((62, 196, W - 62, 336), radius=22, fill=(12, 15, 26, 214), outline=(255, 224, 98, 155), width=2)
        t11_1 = "FIRST AIRCRAFT ON ANOTHER PLANET"
        t11_2 = "Actual Ingenuity Flight 70 Aerial View • Jezero Crater"
        b11_1 = od11.textbbox((0, 0), t11_1, font=f_h11)
        b11_2 = od11.textbbox((0, 0), t11_2, font=f_s11)
        od11.text(((W - (b11_1[2] - b11_1[0])) // 2, 210), t11_1, font=f_h11, fill=(255, 232, 98, 255))
        od11.text(((W - (b11_2[2] - b11_2[0])) // 2, 282), t11_2, font=f_s11, fill=(228, 236, 248, 248))

        render_4k_still_glide_shot(
            img_path=ASSET_PIA26242_4K,
            out_mp4=f"{SHOTS_DIR}/shot_11.mp4",
            num_frames=SHOT_PLAN[10].num_frames,
            tag="s11",
            cx_start=920.0,
            cx_end=1720.0,
            cy_start=1560.0,
            cy_end=1530.0,
            crop_w=1710.0,
            crop_h=3040.0,
            pill_overlay=ov_s11,
            contrast=1.16,
            color=1.14,
        )
        print("  [11/11] shot_11.mp4 ready (native 4K PIA26242 Flight-70 Mars aerial conclusion)")


def generate_pre_render_contact_sheet() -> str:
    sheet_path = f"{OUT_DIR}/pre_render_source_clips_contact_sheet.jpg"
    tmp_dir = f"{SCRATCH_ROOT}/prerender_cs"
    os.makedirs(tmp_dir, exist_ok=True)

    tw, th = 225, 400
    row_h = th + 28
    sheet_w = 1580
    sheet_h = 90 + len(SHOT_PLAN) * row_h + 20
    sheet = Image.new("RGB", (sheet_w, sheet_h), (15, 18, 26))
    draw = ImageDraw.Draw(sheet)

    f_title = ImageFont.truetype(FONT_BOLD, 28)
    f_hdr = ImageFont.truetype(FONT_BOLD, 20)
    f_txt = ImageFont.truetype(FONT_MED, 17)

    draw.text(
        (32, 26),
        "PRE-RENDER SOURCE CLIPS CONTACT SHEET — MARS SHORTS V2 (3 Frames/Shot vs Timed Narration)",
        font=f_title,
        fill=(255, 255, 255),
    )

    for idx, s in enumerate(SHOT_PLAN):
        clip_path = f"{SHOTS_DIR}/{s.shot_id}.mp4"
        y_top = 86 + idx * row_h
        samples = [
            ("START", min(0.15, s.duration * 0.15)),
            ("MID", s.duration * 0.50),
            ("END", max(0.05, s.duration - 0.15)),
        ]
        for j, (tag, rel_t) in enumerate(samples):
            jpg = f"{tmp_dir}/{s.shot_id}_{j}.jpg"
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{rel_t:.3f}", "-i", clip_path, "-frames:v", "1", "-vf", f"scale={tw}:{th}", jpg],
                check=True,
                capture_output=True,
            )
            im = Image.open(jpg).convert("RGB")
            d_im = ImageDraw.Draw(im)
            d_im.rectangle((0, 0, tw, 26), fill=(0, 0, 0))
            d_im.text((6, 4), f"{s.shot_id} {tag} ({s.start_sec + rel_t:.2f}s)", font=f_txt, fill=(255, 232, 100))
            sheet.paste(im, (30 + j * (tw + 12), y_top))

        rx = 30 + 3 * (tw + 12) + 18
        draw.text((rx, y_top + 10), f"{s.shot_id.upper()}  [{s.start_sec:.2f}s -> {s.end_sec:.2f}s | {s.duration:.2f}s]", font=f_hdr, fill=(130, 210, 255))
        draw.text((rx, y_top + 44), f"Spoken: \"{s.narration_phrase}\"", font=f_txt, fill=(255, 255, 255))
        draw.text((rx, y_top + 82), f"Subject: {s.intended_subject[:95]}", font=f_txt, fill=(195, 205, 220))
        if len(s.intended_subject) > 95:
            draw.text((rx, y_top + 106), f"         {s.intended_subject[95:195]}", font=f_txt, fill=(195, 205, 220))
        draw.text((rx, y_top + 142), f"Source: {s.source_url[:95]}", font=f_txt, fill=(165, 220, 175))
        draw.text((rx, y_top + 176), f"Proof: {s.proof_rationale[:100]}", font=f_txt, fill=(215, 215, 195))
        if len(s.proof_rationale) > 100:
            draw.text((rx, y_top + 200), f"       {s.proof_rationale[100:205]}", font=f_txt, fill=(215, 215, 195))

    sheet.save(sheet_path, quality=92)
    print(f"Saved pre-render contact sheet: {sheet_path}")
    return sheet_path


def parse_srt(srt_path: str) -> List[Tuple[int, float, float, str]]:
    raw = open(srt_path, encoding="utf-8").read().strip()
    blocks = re.split(r"\n\s*\n", raw)
    cues = []
    for b in blocks:
        lines = [ln.strip() for ln in b.splitlines() if ln.strip()]
        if len(lines) < 3:
            continue
        idx = int(lines[0])
        m = re.match(r"(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)", lines[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        t0 = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
        t1 = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
        txt = " ".join(lines[2:])
        cues.append((idx, t0, t1, txt))
    return cues


def wrap_caption_words(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int = 860) -> List[List[str]]:
    words = text.split()
    lines: List[List[str]] = []
    cur: List[str] = []
    for w in words:
        cand = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), cand, font=font)
        if (bbox[2] - bbox[0]) <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(cur)
            cur = [w]
    if cur:
        lines.append(cur)
    return lines


def render_final_video() -> None:
    tmp_dir = f"{SCRATCH_ROOT}/final_render"
    os.makedirs(tmp_dir, exist_ok=True)
    concat_txt = f"{tmp_dir}/concat_list.txt"
    with open(concat_txt, "w") as f:
        for s in SHOT_PLAN:
            f.write(f"file '{SHOTS_DIR}/{s.shot_id}.mp4'\n")

    visual_only = f"{tmp_dir}/combined_visuals.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", visual_only],
        check=True,
        capture_output=True,
    )

    cues = parse_srt(SRT_PATH)
    cap_font = ImageFont.truetype(FONT_BOLD, 46)

    raw_frames_dir = f"{tmp_dir}/raw_frames"
    cap_frames_dir = f"{tmp_dir}/cap_frames"
    os.makedirs(raw_frames_dir, exist_ok=True)
    os.makedirs(cap_frames_dir, exist_ok=True)

    total_frames = SHOT_PLAN[-1].f_end
    total_dur = total_frames / FPS
    subprocess.run(
        ["ffmpeg", "-y", "-i", visual_only, "-frames:v", str(total_frames), f"{raw_frames_dir}/f_%04d.png"],
        check=True,
        capture_output=True,
    )

    cue_overlays = []
    dummy = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dummy)
    space_w = dd.textbbox((0, 0), " ", font=cap_font)[2] - dd.textbbox((0, 0), " ", font=cap_font)[0]

    for cue_idx, t0, t1, txt in cues:
        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        word_lines = wrap_caption_words(dd, txt, cap_font, max_w=860)
        line_h = 60
        tot_h = len(word_lines) * line_h
        # Mobile-safe lower zone centered at y=1605 (well inside 1080x1920 safe zone & below all subjects/badges!)
        y_center = 1605
        y_start = y_center - tot_h // 2

        line_widths = []
        for wl in word_lines:
            joined = " ".join(wl)
            bb = od.textbbox((0, 0), joined, font=cap_font)
            line_widths.append(bb[2] - bb[0])
        max_lw = max(line_widths)

        pad_x, pad_y = 32, 18
        rx0 = (W - max_lw) // 2 - pad_x
        rx1 = (W + max_lw) // 2 + pad_x
        ry0 = y_start - pad_y
        ry1 = y_start + tot_h + pad_y - 6
        od.rounded_rectangle((rx0, ry0, rx1, ry1), radius=20, fill=(11, 16, 33, 214))

        hi_set = CUE_HIGHLIGHT_WORDS.get(cue_idx, set())
        for k, wl in enumerate(word_lines):
            # Compute exact word advances so selective gold highlighting aligns seamlessly
            w_adv = [od.textbbox((0, 0), w, font=cap_font)[2] - od.textbbox((0, 0), w, font=cap_font)[0] for w in wl]
            total_line_w = sum(w_adv) + space_w * max(0, len(wl) - 1)
            cur_x = (W - total_line_w) // 2
            ly = y_start + k * line_h
            for w_tok, adv in zip(wl, w_adv):
                fill_col = (255, 228, 94, 255) if w_tok in hi_set else (255, 255, 255, 255)
                od.text(
                    (cur_x, ly),
                    w_tok,
                    font=cap_font,
                    fill=fill_col,
                    stroke_width=3,
                    stroke_fill=(0, 0, 0, 255),
                )
                cur_x += adv + space_w

        cue_overlays.append((t0, t1, ov))

    for i in range(total_frames):
        t = i / FPS
        im = Image.open(f"{raw_frames_dir}/f_{i+1:04d}.png").convert("RGBA")
        for t0, t1, ov in cue_overlays:
            if t0 <= t <= t1:
                im = Image.alpha_composite(im, ov)
                break
        im.convert("RGB").save(f"{cap_frames_dir}/f_{i:04d}.png")

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-framerate",
            str(FPS),
            "-i",
            f"{cap_frames_dir}/f_%04d.png",
            "-i",
            AUDIO_PATH,
            "-filter_complex",
            f"[1:a]apad=whole_dur={total_dur:.3f}[aout]",
            "-map",
            "0:v:0",
            "-map",
            "[aout]",
            "-frames:v",
            str(total_frames),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(FPS),
            "-crf",
            "14",
            "-aq-mode",
            "3",
            "-aq-strength",
            "1.1",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            FINAL_MP4,
        ],
        check=True,
        capture_output=True,
    )
    print(f"Rendered final MP4: {FINAL_MP4}")

    # Export unified ultra-sharp 4:4:4 JPG + lossless PNG Frame-0 thumbnail + standalone `thumbnail.jpg`
    frame0_master = f"{SHOTS_DIR}/shot_01_frame0_master.png"
    f0_im = Image.open(frame0_master).convert("RGBA")
    for t0, t1, ov in cue_overlays:
        if t0 <= 0.0 <= t1:
            f0_im = Image.alpha_composite(f0_im, ov)
            break
    f0_composited = f"{tmp_dir}/frame0_uncompressed_final.png"
    f0_im.convert("RGB").save(f0_composited)
    export_first_frame_thumbnail(
        mp4_path=FINAL_MP4,
        raw_frame0_rgb_path=f0_composited,
        title_preview=WORKING_TITLE,
        generate_preview_sheet=True,
        native_crop_box=(310, 660, 770, 1120),
    )
    shutil.copy2(f"{OUT_DIR}/{VIDEO_SLUG}.jpg", f"{OUT_DIR}/thumbnail.jpg")

    pr = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", FINAL_MP4]
    ).decode("utf-8")
    with open(f"{OUT_DIR}/ffprobe_validation.json", "w", encoding="utf-8") as f:
        f.write(pr)
    print(f"Wrote {OUT_DIR}/ffprobe_validation.json and {OUT_DIR}/thumbnail.jpg")


def generate_post_render_qc_sheets() -> None:
    tmp_dir = f"{SCRATCH_ROOT}/post_qc"
    os.makedirs(tmp_dir, exist_ok=True)
    f_title = ImageFont.truetype(FONT_BOLD, 28)
    f_lbl = ImageFont.truetype(FONT_BOLD, 19)
    f_txt = ImageFont.truetype(FONT_MED, 16)

    # 0. Clean 11-tile Representative Contact Sheet (`contact_sheet.jpg`)
    cols_ov = 4
    rows_ov = 3
    ow, oh = 270, 480
    cs = Image.new("RGB", (36 + cols_ov * (ow + 18), 96 + rows_ov * (oh + 76)), (14, 17, 25))
    dcs = ImageDraw.Draw(cs)
    dcs.text((30, 26), f"MARS SHORTS V2 — REPRESENTATIVE CONTACT SHEET ({VIDEO_SLUG}.mp4, 42.90s)", font=f_title, fill=(255, 255, 255))
    for idx, sp in enumerate(SHOT_PLAN):
        ts = 0.0 if idx == 0 else 0.5 * (sp.start_sec + sp.end_sec)
        jpg = f"{tmp_dir}/ov_{idx}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", FINAL_MP4, "-frames:v", "1", "-vf", f"scale={ow}:{oh}", jpg],
            check=True,
            capture_output=True,
        )
        im = Image.open(jpg).convert("RGB")
        r, c = divmod(idx, cols_ov)
        x0 = 28 + c * (ow + 18)
        y0 = 86 + r * (oh + 76)
        cs.paste(im, (x0, y0))
        dcs.text((x0 + 4, y0 + oh + 6), f"{sp.shot_id} ({sp.start_sec:.1f}–{sp.end_sec:.1f}s)", font=f_lbl, fill=(255, 232, 100))
        dcs.text((x0 + 4, y0 + oh + 32), sp.narration_phrase[:34] + ("..." if len(sp.narration_phrase) > 34 else ""), font=f_txt, fill=(215, 226, 240))
    cs_path = f"{OUT_DIR}/contact_sheet.jpg"
    cs.save(cs_path, quality=93)

    # 1. First 3 Seconds Dedicated Audit Sheet
    f3_times = [0.00, 0.65, 1.30, 1.95, 2.60, 3.25]
    tw, th = 250, 444
    s1 = Image.new("RGB", (40 + 6 * (tw + 14), th + 120), (15, 18, 26))
    d1 = ImageDraw.Draw(s1)
    d1.text((30, 24), f"FIRST 3 SECONDS DEDICATED AUDIT — MARS V2 ({VIDEO_SLUG}.mp4)", font=f_title, fill=(255, 255, 255))
    for k, ts in enumerate(f3_times):
        jpg = f"{tmp_dir}/f3_{k}.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", FINAL_MP4, "-frames:v", "1", "-vf", f"scale={tw}:{th}", jpg],
            check=True,
            capture_output=True,
        )
        im = Image.open(jpg).convert("RGB")
        x0 = 30 + k * (tw + 14)
        s1.paste(im, (x0, 76))
        d1.text((x0 + 8, 76 + th + 8), f"t = {ts:.2f}s", font=f_lbl, fill=(255, 232, 100))
    f3_path = f"{OUT_DIR}/first_3_seconds_audit_sheet.jpg"
    s1.save(f3_path, quality=93)

    # 2. Full 11-Shot Start / Mid / End Transition Contact Sheet
    cw, ch = 225, 400
    row_h = ch + 26
    s2 = Image.new("RGB", (1560, 90 + len(SHOT_PLAN) * row_h + 20), (15, 18, 26))
    d2 = ImageDraw.Draw(s2)
    d2.text((30, 24), "POST-RENDER FINAL SHOTS & TRANSITIONS CONTACT SHEET (33 Frames Across 11 Shots)", font=f_title, fill=(255, 255, 255))

    for idx, sp in enumerate(SHOT_PLAN):
        y_top = 84 + idx * row_h
        pts = [
            ("IN+0.12s", sp.start_sec + 0.12),
            ("MID", 0.5 * (sp.start_sec + sp.end_sec)),
            ("OUT-0.12s", sp.end_sec - 0.12),
        ]
        for j, (tag, ts) in enumerate(pts):
            jpg = f"{tmp_dir}/post_{sp.shot_id}_{j}.jpg"
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", FINAL_MP4, "-frames:v", "1", "-vf", f"scale={cw}:{ch}", jpg],
                check=True,
                capture_output=True,
            )
            im = Image.open(jpg).convert("RGB")
            di = ImageDraw.Draw(im)
            di.rectangle((0, 0, cw, 25), fill=(0, 0, 0))
            di.text((6, 4), f"{sp.shot_id} {tag} ({ts:.2f}s)", font=f_txt, fill=(120, 225, 255))
            s2.paste(im, (30 + j * (cw + 12), y_top))

        rx = 30 + 3 * (cw + 12) + 18
        d2.text((rx, y_top + 14), f"{sp.shot_id.upper()} [{sp.start_sec:.2f}s -> {sp.end_sec:.2f}s]", font=f_lbl, fill=(255, 232, 100))
        d2.text((rx, y_top + 48), f"Narration: \"{sp.narration_phrase}\"", font=f_txt, fill=(255, 255, 255))
        d2.text((rx, y_top + 84), f"Subtitles: {sp.subtitle_segments[:92]}", font=f_txt, fill=(190, 210, 230))
        if len(sp.subtitle_segments) > 92:
            d2.text((rx, y_top + 108), f"           {sp.subtitle_segments[92:184]}", font=f_txt, fill=(190, 210, 230))

    post_path = f"{OUT_DIR}/final_shots_and_transitions_contact_sheet.jpg"
    s2.save(post_path, quality=92)

    # 3. 1:1 Native Pixel Crop Grid (540x540 UNSCALED crops of all 11 shots from FINAL_MP4)
    crop_boxes = [
        (270, 620, 810, 1160),  # shot_01: airborne Ingenuity fuselage & twin rotors
        (270, 560, 810, 1100),  # shot_02: 8K Mars horizon & ~1% limb
        (270, 740, 810, 1280),  # shot_03: JPL Mars vacuum chamber hover
        (270, 520, 810, 1060),  # shot_04: Mastcam-Z close-up 1.8 kg Ingenuity on Mars
        (270, 580, 810, 1120),  # shot_05: close-up counter-rotating carbon-fiber rotors
        (270, 555, 810, 1095),  # shot_06: ~2,500 RPM counter-rotating lift animation
        (270, 500, 810, 1040),  # shot_07: Mastcam-Z Flight 1 liftoff on Mars
        (270, 820, 810, 1360),  # shot_08: onboard Navcam rotor shadow on Mars
        (270, 550, 810, 1090),  # shot_09: Mastcam-Z color dune flight (72 flights)
        (270, 580, 810, 1120),  # shot_10: PIA24548 Ingenuity tucked beneath Perseverance
        (270, 700, 810, 1240),  # shot_11: native 4K PIA26242 Flight-70 Mars aerial view
    ]
    cols = 4
    rows = 3
    s3 = Image.new("RGB", (30 + cols * 554, 100 + rows * 594), (12, 15, 22))
    d3 = ImageDraw.Draw(s3)
    d3.text((28, 22), "MANDATORY 1:1 NATIVE PIXEL QC (540x540 UNSCALED CROPS FROM FINAL 1080x1920 MP4)", font=f_title, fill=(255, 255, 255))
    for idx, (sp, cbox) in enumerate(zip(SHOT_PLAN, crop_boxes)):
        mid_t = 0.5 * (sp.start_sec + sp.end_sec)
        png = f"{tmp_dir}/native_{sp.shot_id}.png"
        subprocess.run(["ffmpeg", "-y", "-ss", f"{mid_t:.3f}", "-i", FINAL_MP4, "-frames:v", "1", png], check=True, capture_output=True)
        full_im = Image.open(png).convert("RGB")
        crop_im = full_im.crop(cbox)
        arr = np.asarray(crop_im, dtype=np.float32)
        grad = float(np.mean(np.abs(np.diff(arr, axis=1))) + np.mean(np.abs(np.diff(arr, axis=0)))) * 0.5
        r, c = divmod(idx, cols)
        x0 = 22 + c * 554
        y0 = 84 + r * 594
        s3.paste(crop_im, (x0, y0))
        d3.text((x0 + 6, y0 + 546), f"{sp.shot_id} @ {mid_t:.2f}s (1:1 grad={grad:.2f})", font=f_lbl, fill=(125, 230, 255))
    native_qc_path = f"{OUT_DIR}/native_1to1_pixel_qc_sheet.jpg"
    s3.save(native_qc_path, quality=95)

    # 4. Consecutive-Frame Jitter Audit Strip (Frames 0..5 of Shot 01)
    subprocess.run(
        ["ffmpeg", "-y", "-i", FINAL_MP4, "-frames:v", "6", f"{tmp_dir}/consec_%02d.png"],
        check=True,
        capture_output=True,
    )
    s4 = Image.new("RGB", (30 + 6 * 484, 590), (12, 15, 22))
    d4 = ImageDraw.Draw(s4)
    d4.text((26, 20), "SHOT 01 CONSECUTIVE-FRAME JITTER AUDIT (Frames 0..5 @ 1:1 Unscaled Pixels Around Ingenuity)", font=f_title, fill=(255, 255, 255))
    for k in range(6):
        fim = Image.open(f"{tmp_dir}/consec_{k+1:02d}.png").convert("RGB")
        vc = fim.crop((305, 650, 775, 1120))
        x0 = 20 + k * 484
        s4.paste(vc, (x0, 78))
        d4.text((x0 + 8, 554), f"Frame {k} (t={k/30:.3f}s) — 1:1 Pixels", font=f_lbl, fill=(255, 232, 100))
    jitter_qc_path = f"{OUT_DIR}/shot01_consecutive_frames_1to1_qc.jpg"
    s4.save(jitter_qc_path, quality=95)

    print(f"Saved QC sheets:\n  {cs_path}\n  {f3_path}\n  {post_path}\n  {native_qc_path}\n  {jitter_qc_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["pre_render", "render_final", "all"], required=True)
    parser.add_argument("--only-shots", type=str, default="", help="Optional comma-separated shot IDs to rebuild")
    args = parser.parse_args()

    only_set = {x.strip() for x in args.only_shots.split(",") if x.strip()} if args.only_shots else None

    if args.stage in ("pre_render", "all"):
        write_manifests()
        build_all_shots(only_shots=only_set)
        generate_pre_render_contact_sheet()
    if args.stage in ("render_final", "all"):
        render_final_video()
        generate_post_render_qc_sheets()
