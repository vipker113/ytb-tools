#!/usr/bin/env python3
"""
Proof of Wonder #06 — "A Day in the Life of an Astronaut in Space"

Documentary Short assembled from authentic NASA footage + five original, music-free astronaut sound bites
(NASA in-flight downlink events), bridged by a TTS narrator (edge-tts en-US-AndrewMultilingualNeural, +0%).

Stages:
  python build_day_in_space_pow06.py --stage audio     # assemble narration + sound bites -> narration_mix.wav, timeline.json
  python build_day_in_space_pow06.py --stage preview   # one frame per shot (with overlays) -> preview sheet
  python build_day_in_space_pow06.py --stage render    # shots -> concat -> overlays -> final MP4 + thumbnails
  python build_day_in_space_pow06.py --stage all

Editorial / rights rules enforced here:
  * Every B-roll clip is muted. Only the five verified in-flight sound bites carry original audio.
  * Sound bites are never overlapped by narration; each gets ~0.3 s of its own room tone before/after.
  * Sources whose audio contains a third-party music bed (25-yr tour, Rubio, Pettit, AlNeyadi STEMonstration,
    Step Inside the Station) are used for PICTURE ONLY.
  * Illustrative (not literal) footage is labelled on screen.
"""
from __future__ import annotations

import argparse, json, math, os, re, shutil, subprocess, sys
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = "/Applications/code/science-knowledge/youtube-shorts-channel"
sys.path.insert(0, f"{ROOT}/pipeline")
from first_frame_thumbnail import export_first_frame_thumbnail  # noqa: E402

SLUG = "06-day-in-the-life-of-an-astronaut"
TITLE = "A Day in the Life of an Astronaut in Space"
OUT = f"{ROOT}/output/proof-of-wonder/{SLUG}"
SEGDIR = f"{OUT}/narration_segments"
SHOTS = f"{OUT}/shots"
SCR = "/Users/admin/.gemini/antigravity/brain/40c60d87-669d-4ec0-8e97-9ae15cc03780/scratch/pow06_build"
RAW = f"{ROOT}/assets/raw_footage/pow06_day_in_space"
RAWB = f"{ROOT}/assets/raw_footage/batch1_r2_04_spine_space"
for d in (OUT, SHOTS, SCR):
    os.makedirs(d, exist_ok=True)

FONT_ANTON = f"{ROOT}/assets/fonts/Anton-Regular.ttf"
FONT_BOLD = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Bold.ttf"
FONT_MED = "/Applications/code/science-knowledge/MoneyPrinterTurbo/resource/fonts/BeVietnamPro-Medium.ttf"

W, H, FPS, SR = 1080, 1920, 30, 48000
FINAL_MP4 = f"{OUT}/{SLUG}.mp4"
MIX_WAV = f"{OUT}/narration_and_soundbites_mix.wav"
NARR_MP3 = f"{OUT}/narration.mp3"
TIMELINE = f"{OUT}/timeline.json"
SRT = f"{OUT}/subtitles.srt"

# ------------------------------------------------------------------------------------------------
# Media sources (all verified NASA-produced; see source_register.md)
# ------------------------------------------------------------------------------------------------
SRC = {
    "rubio_year": f"{RAW}/nasa_frank_rubio_year_of_science_large.mp4",
    "clean_tour": f"{RAW}/nasa_step_inside_station_clean_large.mp4",
    "kitchen": f"{RAW}/nasa_frank_rubio_space_kitchen_es_large.mp4",
    "treadmill": f"{RAW}/nasa_frank_rubio_treadmill_es_large.mp4",
    "water_mann": f"{RAW}/nasa_stemonstrations_water_nicole_mann_large.mp4",
    "alneyadi": f"{RAW}/nasa_stemonstrations_communication_alneyadi_large.mp4",
    "pettit": f"{RAW}/nasa_don_pettit_science_large.mp4",
    "morgan": f"{RAWB}/wiki_iss_cupola_andrew_morgan.webm",
    "epps": f"{RAW}/inflight_epps_sleep.mov",
    "vandehei": f"{RAW}/inflight_vandehei_morning_cupola.mov",
    "marshburn": f"{RAW}/inflight_exp66_glenn_hygiene.mov",
    "bowen": f"{RAW}/inflight_bowen_npr_typical_day.mov",
    "ayers": f"{RAW}/inflight_exp73_family_calls.mov",
}

# ------------------------------------------------------------------------------------------------
# Original astronaut sound bites (times are inside the excerpt files; excerpt offsets in source_register)
# ------------------------------------------------------------------------------------------------
BITES = {
    "B_EPPS": dict(src="epps", t0=10.34, t1=18.44, cut_in=10.22, cut_out=18.56, fi=0.05, fo=0.08,
                   speaker="Jeanette Epps", role="NASA astronaut",
                   context="ISS in-flight education event, May 2024",
                   text="So we sleep in a sleeping bag and we float in our sleeping bag, and just to keep us in one place, otherwise we would float off everywhere."),
    "B_VANDEHEI": dict(src="vandehei", t0=43.60, t1=53.00, cut_in=43.58, cut_out=53.10, fi=0.03, fo=0.08,
                       speaker="Mark Vande Hei", role="NASA astronaut",
                       context="ISS in-flight interview, Jan. 2022",
                       text="Every morning I get up, have a cup of coffee and some snack, and then I go over to the Cupola, and I spend 20 minutes meditating lately with my eyes open and just watching."),
    "B_MARSHBURN": dict(src="marshburn", t0=6.00, t1=14.46, cut_in=5.96, cut_out=14.54, fi=0.04, fo=0.04,
                        speaker="Tom Marshburn", role="NASA astronaut",
                        context="ISS in-flight education event, Mar. 2022",
                        text="The way we stay clean is we use wet wipes. We don't have running water up here. We can't take showers or baths like you might think, but it's actually pretty nice."),
    "B_BOWEN": dict(src="bowen", t0=26.30, t1=34.06, cut_in=26.14, cut_out=34.18, fi=0.06, fo=0.08,
                    speaker="Stephen Bowen", role="NASA astronaut",
                    context="ISS in-flight interview, Mar. 2023",
                    text="You also have to work out, do a load-bearing exercise for two hours every day to ensure that you maintain the bone density and muscle mass."),
    "B_AYERS": dict(src="ayers", t0=13.94, t1=22.70, cut_in=13.82, cut_out=22.80, fi=0.05, fo=0.08,
                    speaker="Nichole Ayers", role="NASA astronaut",
                    context="ISS in-flight education event, May 2025",
                    text="We've got satellites that we use to get the connection with them, so we can call our family, and actually that's who I call. I like to call my family and friends on the weekends when we get some free time."),
}

SEQUENCE = ["N01", "N02", "B_EPPS", "N03", "B_VANDEHEI", "N04", "B_MARSHBURN", "N05", "N06", "N07", "B_BOWEN",
            "N08", "N09", "B_AYERS", "N10", "N11", "N12"]
GAP_NN = 0.10      # extra silence between two narration segments (TTS already has ~0.28 s of trailing silence)
GAP_TO_BITE = 0.25  # clean pause before each original sound bite
GAP_FROM_BITE = 0.28
TAIL = 1.65         # end card after final line

# ------------------------------------------------------------------------------------------------
# Shot plan. Each shot is anchored to an element of SEQUENCE plus optional word-index split.
#   anchor: (element_id, "start"|word index) for shot start; shots run until next shot's start.
#   mode: "fill" (full 9:16 crop) or "tall" (4:5 crop on blurred background).
# ------------------------------------------------------------------------------------------------
@dataclass
class Shot:
    sid: str
    anchor: Tuple[str, object]
    src: str
    src_in: float
    mode: str = "tall"
    cx: float = 0.5          # horizontal crop centre (0..1)
    cy: float = 0.5
    zoom: float = 1.0        # >1 crops tighter
    label: str = ""          # top source label
    illustrative: bool = False
    action: str = ""
    why: str = ""
    keep_audio: bool = False  # True only for sound-bite shots that show the speaker (audio still comes from mix)
    rotate180: bool = False   # orientation-only change (no up/down in microgravity); disclosed in QC report


SHOT_PLAN: List[Shot] = [
    Shot("S01", ("N01", "start"), "clean_tour", 213.40, "fill", cx=0.50, rotate180=True,
         label="NASA • Cupola photography, Oct. 2022",
         action="An astronaut floats in the Cupola photographing Earth through the windows (frame rotated 180°)",
         why="Frame 0 / thumbnail: a real astronaut floating inside the ISS with Earth beyond the windows."),
    Shot("S02", ("N01", 10), "rubio_year", 18.40, "fill", cx=0.55, label="NASA • Frank Rubio in the Cupola, 2023",
         action="Frank Rubio laughing beneath the Cupola windows",
         why="Puts a human face on 'your home'."),
    Shot("S03", ("N01", 14), "clean_tour", 2.40, "fill", cx=0.55, label="NASA • ISS interior, Oct. 2022",
         action="Astronaut floats past the camera through the station's modules",
         why="The 'home' moving at 28,000 km/h is a spacecraft people float through."),
    Shot("S04", ("N02", "start"), "clean_tour", 116.80, "tall", cx=0.50, label="NASA • Harmony crew quarters",
         action="Camera floats down the Node 2 Harmony crew-quarters hub and pitches into a private sleep cabin",
         why="Literal match for 'a crew cabin about the size of a phone booth'."),
    Shot("S05", ("B_EPPS", "start"), "epps", 0.0, "tall", cx=0.50, label="NASA • In-flight event, May 2024", keep_audio=True,
         action="Jeanette Epps speaking on camera aboard the ISS (lip-synced to her sound bite)",
         why="The speaker herself explaining how astronauts sleep."),
    Shot("S06", ("B_EPPS", 7), "epps", 12.62, "tall", cx=0.52, label="NASA • ISS sleeping bag (illustrative)",
         illustrative=True, action="Astronaut strapping into a tethered vertical sleeping bag aboard the ISS",
         why="Shows an astronaut floating inside a tethered sleeping bag as Epps describes."),
    Shot("S07", ("B_EPPS", 14), "clean_tour", 121.00, "tall", cx=0.55, label="NASA • Sleeping bag, Harmony cabin",
         action="Astronaut zipped inside a blue tethered sleeping bag inside a Harmony crew cabin",
         why="Shows how the tethered bag holds the sleeping astronaut in one place."),
    Shot("S08", ("N03", "start"), "treadmill", 1.50, "tall", cx=0.50, label="NASA • Frank Rubio, Node 3",
         action="Astronaut floats through a hatch into the next module",
         why="Moving through the station as the day starts."),
    Shot("S09", ("N03", 13), "pettit", 100.30, "tall", cx=0.50, label="NASA • Don Pettit in the Cupola",
         action="Astronaut floating in the Cupola with a camera, Earth through the windows",
         why="'For some, the first stop is the window.'"),
    Shot("S10", ("B_VANDEHEI", "start"), "vandehei", 0.0, "tall", cx=0.31, label="NASA • In-flight interview, Jan. 2022",
         keep_audio=True, action="Mark Vande Hei (left, holding microphone) answering aboard the ISS (lip-synced)",
         why="The speaker describing his own morning ritual."),
    Shot("S11", ("B_VANDEHEI", 19), "morgan", 22.00, "tall", cx=0.42, label="NASA • Cupola, 2019 (illustrative)",
         illustrative=True, action="An astronaut silently watching Earth from the Cupola windows",
         why="Illustrates Vande Hei's quiet minutes at the Cupola (different astronaut)."),
    Shot("S12", ("N04", "start"), "water_mann", 186.20, "tall", cx=0.50, label="NASA • Nicole Mann, 2023 (illustrative)",
         illustrative=True, action="Astronaut holds a washcloth and a water pouch",
         why="Sets up the hygiene question with a real washcloth aboard the ISS."),
    Shot("S13", ("B_MARSHBURN", "start"), "marshburn", 0.0, "tall", cx=0.63, label="NASA • In-flight event, Mar. 2022",
         keep_audio=True, action="Tom Marshburn (right, holding microphone) answering aboard the ISS (lip-synced)",
         why="The speaker explaining how astronauts stay clean."),
    Shot("S14", ("B_MARSHBURN", 17), "water_mann", 204.60, "tall", cx=0.50, label="NASA • Washcloth demo (illustrative)",
         illustrative=True, action="Water clings to a wet washcloth in microgravity instead of dripping",
         why="Shows why wet towels, not running water, are how crews wash."),
    Shot("S15", ("N05", 6), "kitchen", 24.60, "tall", cx=0.48, label="NASA • Frank Rubio in the galley",
         action="Frank Rubio holds up a vacuum-sealed food pouch in the Node 1 galley",
         why="'Breakfast comes in pouches.'"),
    Shot("S16", ("N05", 10), "kitchen", 44.20, "tall", cx=0.45, label="NASA • Frank Rubio in the galley",
         action="Rubio fills a pouch at the potable-water dispenser, then works it by hand",
         why="'add hot water, knead, and heat.'"),
    Shot("S17", ("N05", 16), "kitchen", 223.80, "tall", cx=0.55, label="NASA • Liquid salt aboard the ISS",
         action="Rubio shows the squeeze bottle of liquid salt",
         why="'Even salt is a liquid.'"),
    Shot("S18", ("N06", "start"), "rubio_year", 34.60, "tall", cx=0.50, label="NASA • Frank Rubio, 2023",
         action="Rubio floats toward the camera, then works hands-on in a glovebox",
         why="The workday beginning: crew at work in the lab."),
    Shot("S19", ("N06", 10), "rubio_year", 53.60, "tall", cx=0.40, label="NASA • VEG-05 plant experiment",
         action="Astronaut tends tomato plants under pink LED grow lights",
         why="'experiments' — a real ISS plant-growth investigation."),
    Shot("S20", ("N07", "start"), "clean_tour", 258.80, "tall", cx=0.42, label="NASA • Spacesuit work, Quest airlock",
         action="Astronaut working on spacesuits in the Quest airlock",
         why="'repairs' / a busy day of hands-on maintenance."),
    Shot("S21", ("B_BOWEN", "start"), "bowen", 0.0, "tall", cx=0.40, label="NASA • In-flight interview, Mar. 2023",
         keep_audio=True, action="Stephen Bowen answering on camera aboard the ISS (lip-synced)",
         why="The speaker on daily exercise."),
    Shot("S22", ("B_BOWEN", 10), "treadmill", 70.00, "tall", cx=0.55, label="NASA • T2 treadmill, Node 3",
         action="Astronaut runs on the wall-mounted treadmill, held down by a bungee harness",
         why="The load-bearing exercise Bowen describes."),
    Shot("S23", ("N08", "start"), "treadmill", 47.50, "tall", cx=0.52, label="NASA • T2 bungee-harness straps",
         action="Close-up of white bungee-cord straps clipping onto the T2 treadmill deck",
         why="'a treadmill with a bungee harness'."),
    Shot("S24", ("N08", 8), "clean_tour", 139.60, "tall", cx=0.62, label="NASA • CEVIS bike (no seat)",
         action="Astronaut pedalling the seatless CEVIS cycle",
         why="'a bike with no seat'."),
    Shot("S25", ("N08", 13), "clean_tour", 200.40, "tall", cx=0.68, label="NASA • ARED weight machine",
         action="Astronaut performing resistive squats on the Advanced Resistive Exercise Device (ARED)",
         why="'a weight machine that uses vacuum cylinders'."),
    Shot("S26", ("N08", 21), "treadmill", 83.20, "tall", cx=0.38, label="NASA • Node 3 exercise bay",
         action="Two astronauts in Node 3 as one runs harnessed to the wall-mounted T2 treadmill",
         why="Holds on exercise while the bone-loss consequence is explained."),
    Shot("S27", ("N09", "start"), "alneyadi", 58.00, "tall", cx=0.42, label="NASA • Internet phone call from the ISS",
         action="Astronaut with headset placing a call from a station laptop (UAE astronaut Sultan AlNeyadi)",
         why="Personal time: calling home."),
    Shot("S28", ("B_AYERS", "start"), "ayers", 0.0, "tall", cx=0.36, label="NASA • In-flight event, May 2025",
         keep_audio=True, action="Nichole Ayers (left, holding microphone) answering aboard the ISS (lip-synced)",
         why="The speaker on calling family."),
    Shot("S29", ("N10", "start"), "clean_tour", 275.80, "tall", cx=0.50, label="NASA • Crew meal, Node 1",
         action="Crew members float around the galley table sharing a meal",
         why="'Crews share dinners'."),
    Shot("S30", ("N10", 6), "pettit", 105.00, "tall", cx=0.50, label="NASA • Aurora photographed from the ISS",
         action="Green aurora over Earth, photographed from the station",
         why="'photograph the planet below'."),
    Shot("S31", ("N11", "start"), "clean_tour", 834.40, "fill", cx=0.42, label="NASA • Resting in Crew Dragon, 2022 (illustrative)",
         illustrative=True, action="An astronaut lies back with eyes closed beside a spacecraft window",
         why="Winding down for sleep at the end of the scheduled day."),
    Shot("S32", ("N12", "start"), "morgan", 107.40, "tall", cx=0.46, label="NASA • Earth from the ISS Cupola",
         action="Earth's curved blue horizon, clouds, and sunlit coastline rolling past through an ISS Cupola window",
         why="Closing thought: an authentic view of Earth from 400 km above."),
]


# ------------------------------------------------------------------------------------------------
# Audio assembly
# ------------------------------------------------------------------------------------------------
def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(" ".join(cmd[:6]) + "...\n" + r.stderr[-1500:])
    return r


def read_wav(path):
    import wave
    with wave.open(path) as w:
        assert w.getframerate() == SR and w.getnchannels() == 1
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path, x):
    import wave
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def loudnorm_to_wav(src, dst, t0=None, t1=None, target=-16.0, extra_af=""):
    """Two-pass EBU R128 normalisation of a (sub)clip into mono 48 kHz WAV."""
    pre = ["-ss", f"{t0:.3f}", "-to", f"{t1:.3f}"] if t0 is not None else []
    af0 = (extra_af + "," if extra_af else "")
    r = run(["ffmpeg", "-hide_banner", "-y", *pre, "-i", src, "-vn", "-ac", "1", "-ar", str(SR),
             "-af", af0 + f"loudnorm=I={target}:TP=-2:LRA=9:print_format=json", "-f", "null", "-"])
    js = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    af = af0 + (f"loudnorm=I={target}:TP=-2:LRA=9:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
                f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    run(["ffmpeg", "-hide_banner", "-y", *pre, "-i", src, "-vn", "-ac", "1", "-ar", str(SR), "-af", af, "-c:a", "pcm_s16le", dst])
    return float(js["input_i"])


def measure_lufs(x):
    tmp = f"{SCR}/_lufs.wav"; write_wav(tmp, x)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", tmp, "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    r = r[r.rfind("Summary:"):]
    return float(re.search(r"I:\s+(-?[\d.]+) LUFS", r).group(1))


def match_speech_loudness(seg, s0, s1, target=-16.0):
    """Gain-match the speech region of a segment to `target` LUFS (whole segment scaled)."""
    L = measure_lufs(seg[int(s0 * SR):int(s1 * SR)])
    return seg * (10 ** ((target - L) / 20.0)), L


def fade(x, n_in, n_out):
    x = x.copy()
    if n_in > 0:
        x[:n_in] *= np.linspace(0, 1, n_in) ** 1.5
    if n_out > 0:
        x[-n_out:] *= np.linspace(1, 0, n_out) ** 1.5
    return x


def build_audio():
    tmp = f"{SCR}/audio"; os.makedirs(tmp, exist_ok=True)
    tl, parts, t = [], [], 0.0
    prev_kind = None
    for el in SEQUENCE:
        if el.startswith("N"):
            meta = json.load(open(f"{SEGDIR}/andrew_0pct_{el}.json"))
            wav = f"{tmp}/{el}.wav"
            loudnorm_to_wav(f"{SEGDIR}/andrew_0pct_{el}.mp3", wav, target=-16.0)
            x = read_wav(wav)
            w0, w1 = meta["words"][0]["start"], meta["words"][-1]["end"]
            a, b = max(0.0, w0 - 0.06), min(len(x) / SR, w1 + 0.22)
            seg = fade(x[int(a * SR):int(b * SR)], int(0.008 * SR), int(0.05 * SR))
            seg, _ = match_speech_loudness(seg, w0 - a, w1 - a)
            if prev_kind == "N":
                t += GAP_NN
            elif prev_kind == "B":
                t += GAP_FROM_BITE
            words = [{"text": w["text"], "start": round(t + w["start"] - a, 3), "end": round(t + w["end"] - a, 3)} for w in meta["words"]]
            tl.append({"id": el, "kind": "narration", "start": round(t, 3), "end": round(t + len(seg) / SR, 3),
                       "speech_start": words[0]["start"], "speech_end": words[-1]["end"], "text": meta["text"], "words": words})
            parts.append((t, seg)); t += len(seg) / SR; prev_kind = "N"
        else:
            bt = BITES[el]
            src = SRC[bt["src"]]
            wav = f"{tmp}/{el}.wav"
            a, b = bt["cut_in"], bt["cut_out"]
            fi, fo = bt["fi"], bt["fo"]
            loudnorm_to_wav(src, wav, a, b, target=-15.0, extra_af="highpass=f=90,lowpass=f=9000,afftdn=nf=-30,acompressor=threshold=-26dB:ratio=3:attack=8:release=150:makeup=3")
            x = fade(read_wav(wav), int(fi * SR), int(fo * SR))
            x, _ = match_speech_loudness(x, bt["t0"] - a, bt["t1"] - a)
            t += GAP_TO_BITE if prev_kind else 0.0
            tdir = "/Users/admin/.gemini/antigravity/brain/40c60d87-669d-4ec0-8e97-9ae15cc03780/scratch/pow06/transcripts"
            stem = os.path.basename(src)[:-4]
            tjs = next(f"{tdir}/{g}" for g in sorted(os.listdir(tdir)) if g.startswith(f"{stem}_0.0_") and g.endswith(".json"))
            ws = json.load(open(tjs))["words"]
            ws = [w for w in ws if bt["t0"] - 0.20 <= w["start"] <= bt["t1"] + 0.02 and w["end"] > bt["cut_in"] - 0.12]
            merged = []
            for w in ws:
                # Filter prior-sentence end token when t0-0.20 catches e.g. 'call.' (19.16-19.34)
                if w["end"] <= bt["cut_in"] - 0.15:
                    continue
                if el == "B_EPPS" and w["text"].strip() == "just" and w["end"] - w["start"] > 1.0:
                    merged.append({"text": "and", "start": 14.80, "end": 15.15, "p": 0.95})
                    merged.append({"text": "just", "start": 15.38, "end": w["end"], "p": 0.95})
                elif w["text"].startswith("-") and merged:          # "load" + "-bearing" -> "load-bearing"
                    merged[-1] = {**merged[-1], "text": merged[-1]["text"] + w["text"], "end": w["end"]}
                elif w.get("p", 1.0) < 0.25 and len(w["text"].strip(",.")) <= 2:   # faint filler syllable (e.g. "a")
                    continue
                else:
                    w2 = dict(w)
                    if w2["start"] < a:
                        w2["start"] = round(a + 0.04, 3)
                        w2["end"] = max(w2["end"], round(w2["start"] + 0.06, 3))
                    merged.append(w2)
            ws = merged
            words = [{"text": w["text"], "start": round(t + (w["start"] - a), 3), "end": round(t + (w["end"] - a), 3)} for w in ws]
            tl.append({"id": el, "kind": "soundbite", "start": round(t, 3), "end": round(t + len(x) / SR, 3),
                       "speech_start": round(t + (bt["t0"] - a), 3), "speech_end": round(t + (bt["t1"] - a), 3),
                       "text": bt["text"], "speaker": bt["speaker"], "role": bt["role"], "context": bt["context"],
                       "source_file": src, "source_in": bt["t0"], "source_out": bt["t1"],
                       "cut_in": a, "cut_out": b, "words": words})
            parts.append((t, x)); t += len(x) / SR; prev_kind = "B"
    total = t + TAIL
    total = math.ceil(total * FPS) / FPS
    mix = np.zeros(int(round(total * SR)) + 1, dtype=np.float32)
    for t0, seg in parts:
        i = int(round(t0 * SR)); mix[i:i + len(seg)] += seg
    write_wav(f"{tmp}/mix_pre_limit.wav", mix)
    run(["ffmpeg", "-y", "-i", f"{tmp}/mix_pre_limit.wav", "-af", "alimiter=limit=0.84:attack=3:release=60:level=disabled",
         "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", MIX_WAV])
    mix = read_wav(MIX_WAV)
    # narration-only track (TTS segments only) for the deliverable `narration.mp3`
    narr = np.zeros_like(mix)
    for (t0, seg), el in zip(parts, SEQUENCE):
        if el.startswith("N"):
            i = int(round(t0 * SR)); narr[i:i + len(seg)] += seg
    write_wav(f"{tmp}/narr_only.wav", narr)
    run(["ffmpeg", "-y", "-i", f"{tmp}/narr_only.wav", "-c:a", "libmp3lame", "-b:a", "192k", NARR_MP3])
    json.dump({"total_sec": round(total, 3), "frames": int(round(total * FPS)), "elements": tl}, open(TIMELINE, "w"), indent=1)
    print(f"Audio timeline: {total:.2f}s  ({int(round(total*FPS))} frames)")
    for e in tl:
        print(f"  {e['id']:12s} {e['kind']:9s} {e['start']:7.2f} -> {e['end']:7.2f}  ({e['end']-e['start']:5.2f}s)")
    return tl, total


# ------------------------------------------------------------------------------------------------
# Timeline helpers
# ------------------------------------------------------------------------------------------------
def load_timeline():
    d = json.load(open(TIMELINE))
    return {e["id"]: e for e in d["elements"]}, d["total_sec"]


def anchor_time(els, anchor):
    el, w = anchor
    e = els[el]
    if w == "start":
        return e["start"] if el != SEQUENCE[0] else 0.0
    words = e["words"]
    i = min(int(w), len(words) - 1)
    # cut just before the word starts (2 frames lead)
    return max(e["start"], words[i]["start"] - 0.07)


def shot_windows():
    els, total = load_timeline()
    starts = [round(anchor_time(els, s.anchor) * FPS) for s in SHOT_PLAN]
    starts[0] = 0
    ends = starts[1:] + [int(round(total * FPS))]
    out = []
    for s, f0, f1 in zip(SHOT_PLAN, starts, ends):
        if s.keep_audio:
            el = s.anchor[0]; bt = BITES[el]
            # exact lip-sync: source frame = bite cut_in + offset from bite start on the timeline
            s.src_in = round(bt["cut_in"] + (f0 / FPS - els[el]["start"]), 3)
        out.append((s, f0, f1))
    return out, els, total


# ------------------------------------------------------------------------------------------------
# Video shots
# ------------------------------------------------------------------------------------------------
def src_size(path):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", path])
    w, h = r.stdout.strip().split(",")[:2]
    return int(w), int(h)


def vf_for(shot: Shot):
    sw, sh = src_size(SRC[shot.src])
    if shot.mode == "fill":
        ch = sh / shot.zoom; cw = ch * 9 / 16
        x = min(max(0, shot.cx * sw - cw / 2), sw - cw); y = min(max(0, shot.cy * sh - ch / 2), sh - ch)
        rot = ",hflip,vflip" if shot.rotate180 else ""
        return (f"fps={FPS},crop={cw:.0f}:{ch:.0f}:{x:.0f}:{y:.0f}{rot},scale={W}:{H}:flags=lanczos,setsar=1")
    # tall: 4:5 foreground (1080x1350) over blurred, darkened full-frame background
    ch = sh / shot.zoom; cw = ch * 4 / 5
    x = min(max(0, shot.cx * sw - cw / 2), sw - cw); y = min(max(0, shot.cy * sh - ch / 2), sh - ch)
    fg_y = 236
    return (f"fps={FPS},split=2[a][b];"
            f"[a]scale=-2:{H},crop={W}:{H},boxblur=40:3,eq=brightness=-0.16:saturation=0.85[bg];"
            f"[b]crop={cw:.0f}:{ch:.0f}:{x:.0f}:{y:.0f},scale={W}:1350:flags=lanczos[fg];"
            f"[bg][fg]overlay=0:{fg_y},setsar=1")


def render_shots(only=None):
    wins, els, total = shot_windows()
    for s, f0, f1 in wins:
        if only and s.sid not in only:
            continue
        dur = (f1 - f0) / FPS
        out = f"{SHOTS}/{s.sid}.mp4"
        vf = vf_for(s)
        cmd = ["ffmpeg", "-y", "-ss", f"{s.src_in:.3f}", "-i", SRC[s.src], "-t", f"{dur + 0.5:.3f}", "-an",
               "-filter_complex", f"[0:v]{vf}[v]", "-map", "[v]", "-frames:v", str(f1 - f0),
               "-c:v", "libx264", "-crf", "12", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", str(FPS), out]
        run(cmd)
        print(f"  [{s.sid}] {f0/FPS:6.2f}-{f1/FPS:6.2f}s ({dur:4.2f}s) {s.src}@{s.src_in:.2f} {s.mode}")


# ------------------------------------------------------------------------------------------------
# Overlays: captions, speaker lower-thirds, source labels, title, end card
# ------------------------------------------------------------------------------------------------
def font(p, s):
    return ImageFont.truetype(p, s)


def chunk_words(words, max_chars=30, max_dur=2.6):
    cues, cur = [], []
    for w in words:
        cand = " ".join(x["text"] for x in cur + [w])
        too_long = len(cand) > max_chars * 2 or (cur and w["end"] - cur[0]["start"] > max_dur)
        if cur and too_long:
            cues.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.?!]$", w["text"]) or (re.search(r"[,:;]$", w["text"]) and len(" ".join(x["text"] for x in cur)) > 22):
            cues.append(cur); cur = []
    if cur:
        cues.append(cur)
    return cues


def normalise_bite_text(words, canonical):
    """Map Whisper tokens onto the verified canonical transcript (same word count), keeping timings."""
    canon = canonical.split()
    if len(canon) != len(words):
        raise ValueError(f"Word count mismatch for bite: {len(canon)} vs {len(words)}: {canonical} | {' '.join(w['text'] for w in words)}")
    return [{"text": c, "start": w["start"], "end": w["end"]} for c, w in zip(canon, words)]


def build_cues():
    els, total = load_timeline()
    cues = []
    for el in SEQUENCE:
        e = els[el]
        words = e["words"]
        kind = e["kind"]
        if kind == "soundbite":
            words = normalise_bite_text(words, BITES[el]["text"])
        else:
            words = normalise_bite_text(words, e["text"])
        # edge-tts emits "28,000" etc. as single tokens; split only on spaces for display
        for grp in chunk_words(words):
            t0, t1 = grp[0]["start"], grp[-1]["end"]
            cues.append({"start": round(max(0.10, t0 - 0.04), 3), "end": round(t1 + 0.12, 3), "text": " ".join(w["text"] for w in grp),
                         "kind": kind, "el": el})
    # make cues non-overlapping and not past the next cue
    for a, b in zip(cues, cues[1:]):
        a["end"] = min(a["end"], b["start"] - 0.02)
    return cues


def write_srt(cues):
    def ts(t):
        ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for i, c in enumerate(cues, 1):
        txt = c["text"]
        if c["kind"] == "soundbite":
            txt = f"{BITES[c['el']]['speaker'].upper()}: {txt}" if c is next(x for x in cues if x["el"] == c["el"]) else txt
        lines += [str(i), f"{ts(c['start'])} --> {ts(c['end'])}", txt, ""]
    open(SRT, "w", encoding="utf-8").write("\n".join(lines))


def wrap(d, text, f, maxw):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if d.textbbox((0, 0), cand, font=f)[2] <= maxw or not cur:
            cur = cand
        else:
            lines.append(cur); cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_caption(img, cue):
    d = ImageDraw.Draw(img)
    soundbite = cue["kind"] == "soundbite"
    f = font(FONT_BOLD, 46)
    lines = wrap(d, cue["text"], f, 900)
    lh = 60
    y0 = 1668 - (len(lines) * lh) // 2
    widths = [d.textbbox((0, 0), l, font=f)[2] for l in lines]
    mw = max(widths)
    box = ((W - mw) // 2 - 30, y0 - 16, (W + mw) // 2 + 30, y0 + len(lines) * lh + 10)
    d.rounded_rectangle(box, radius=18, fill=(8, 12, 22, 200))
    col = (255, 236, 170, 255) if soundbite else (255, 255, 255, 255)
    for k, l in enumerate(lines):
        tw = d.textbbox((0, 0), l, font=f)[2]
        d.text(((W - tw) // 2, y0 + k * lh), l, font=f, fill=col, stroke_width=3, stroke_fill=(0, 0, 0, 255))


def draw_label(img, text, illustrative=False):
    d = ImageDraw.Draw(img)
    f = font(FONT_MED, 25)
    tw = d.textbbox((0, 0), text, font=f)[2]
    x, y = 44, 176
    d.rounded_rectangle((x - 14, y - 9, x + tw + 14, y + 37), radius=12, fill=(8, 12, 22, 175))
    d.text((x, y), text, font=f, fill=(225, 233, 245, 235))


def draw_lower_third(img, bite):
    d = ImageDraw.Draw(img)
    f1 = font(FONT_BOLD, 40); f2 = font(FONT_MED, 26)
    name = bite["speaker"]; sub = f"{bite['role']} • {bite['context']} • original audio"
    w1 = d.textbbox((0, 0), name, font=f1)[2]; w2 = d.textbbox((0, 0), sub, font=f2)[2]
    x, y = 44, 1400
    bw = max(w1, w2) + 44
    d.rounded_rectangle((x, y, x + bw, y + 106), radius=16, fill=(8, 12, 22, 215))
    d.rectangle((x, y + 10, x + 7, y + 96), fill=(255, 205, 90, 255))
    d.text((x + 24, y + 12), name, font=f1, fill=(255, 255, 255, 255))
    d.text((x + 24, y + 62), sub, font=f2, fill=(255, 222, 150, 255))


def draw_title(img, alpha=1.0):
    d = ImageDraw.Draw(img)
    a = int(255 * alpha)
    f1 = font(FONT_ANTON, 118); f2 = font(FONT_BOLD, 38)
    t1 = "A DAY IN SPACE"; t2 = "What's an ordinary day 400 km above Earth?"
    w1 = d.textbbox((0, 0), t1, font=f1)[2]; w2 = d.textbbox((0, 0), t2, font=f2)[2]
    y_top = 1264
    d.rounded_rectangle(((W - max(w1, w2)) // 2 - 40, y_top, (W + max(w1, w2)) // 2 + 40, y_top + 216),
                        radius=26, fill=(6, 10, 20, int(175 * alpha)))
    d.text(((W - w1) // 2, y_top + 2), t1, font=f1, fill=(255, 255, 255, a), stroke_width=5, stroke_fill=(0, 0, 0, a))
    d.text(((W - w2) // 2, y_top + 150), t2, font=f2, fill=(255, 220, 120, a), stroke_width=3, stroke_fill=(0, 0, 0, a))


def draw_endcard(img):
    d = ImageDraw.Draw(img)
    f = font(FONT_MED, 30); fb = font(FONT_BOLD, 34)
    lines = [("Footage & astronaut voices: NASA", fb), ("Astronaut audio: original NASA in-flight recordings", f),
             ("Narration: AI-generated voice", f), ("Not affiliated with or endorsed by NASA", f)]
    y = 1500
    d.rounded_rectangle((90, y - 26, W - 90, y + 4 * 50 + 6), radius=22, fill=(6, 10, 20, 205))
    for txt, ff in lines:
        tw = d.textbbox((0, 0), txt, font=ff)[2]
        d.text(((W - tw) // 2, y), txt, font=ff, fill=(235, 240, 250, 250)); y += 50


def overlay_states():
    """Return list of (t0, t1, state) where state determines the overlay image."""
    wins, els, total = shot_windows()
    cues = build_cues()
    write_srt(cues)
    bite_spans = {el: (els[el]["start"], els[el]["end"]) for el in BITES}
    title_end = round((wins[0][2] - 1) / FPS, 3)
    end_start = els["N12"]["speech_end"] + 0.45
    bounds = {0.0, total}
    for s, f0, f1 in wins:
        bounds |= {f0 / FPS, f1 / FPS}
    for c in cues:
        bounds |= {c["start"], c["end"]}
    for el, (a, b) in bite_spans.items():
        bounds |= {a + 0.15, b - 0.15}
    bounds |= {title_end, end_start}
    pts = sorted(round(b * FPS) / FPS for b in bounds if 0 <= b <= total)
    pts = sorted(set(pts))
    states = []
    for a, b in zip(pts, pts[1:]):
        if b - a < 1e-6:
            continue
        m = (a + b) / 2
        shot = next(s for s, f0, f1 in wins if f0 / FPS <= m < f1 / FPS)
        cue = next((c for c in cues if c["start"] <= m < c["end"]), None)
        bite = next((el for el, (x, y) in bite_spans.items() if x + 0.15 <= m < y - 0.15), None)
        lower = bite if (bite and shot.keep_audio) else None
        st = {"label": None if (m < title_end or m >= end_start) else shot.label, "illustrative": shot.illustrative,
              "cue": cue, "lower": lower, "title": m < title_end, "end": m >= end_start}
        states.append((a, b, st))
    return states


def render_overlay_png(st, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if st["title"]:
        draw_title(img)
    if st["label"]:
        draw_label(img, st["label"], st["illustrative"])
    if st["lower"]:
        draw_lower_third(img, BITES[st["lower"]])
    if st["end"]:
        draw_endcard(img)
    if st["cue"]:
        draw_caption(img, st["cue"])
    img.save(path)


def build_overlay_track():
    tmp = f"{SCR}/ovl"; shutil.rmtree(tmp, ignore_errors=True); os.makedirs(tmp)
    states = overlay_states()
    cache, lines = {}, ["ffconcat version 1.0"]
    for i, (a, b, st) in enumerate(states):
        key = json.dumps({k: (v["text"] if k == "cue" and v else v) for k, v in st.items()}, sort_keys=True)
        if key not in cache:
            p = f"{tmp}/o_{len(cache):04d}.png"; render_overlay_png(st, p); cache[key] = p
        fa, fb = round(a * FPS), round(b * FPS)
        lines += [f"file '{cache[key]}'", f"duration {(fb - fa) / FPS:.6f}"]
    lines.append(f"file '{cache[key]}'")
    open(f"{tmp}/overlay.ffconcat", "w").write("\n".join(lines) + "\n")
    print(f"Overlay track: {len(states)} states, {len(cache)} unique PNGs")
    return f"{tmp}/overlay.ffconcat"


# ------------------------------------------------------------------------------------------------
# Final render
# ------------------------------------------------------------------------------------------------
def render_final():
    wins, els, total = shot_windows()
    nframes = int(round(total * FPS))
    tmp = f"{SCR}/final"; os.makedirs(tmp, exist_ok=True)
    with open(f"{tmp}/concat.txt", "w") as f:
        for s, f0, f1 in wins:
            f.write(f"file '{SHOTS}/{s.sid}.mp4'\n")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"{tmp}/concat.txt", "-c", "copy", f"{tmp}/base.mp4"])
    ovl = build_overlay_track()
    run(["ffmpeg", "-y", "-i", f"{tmp}/base.mp4", "-f", "concat", "-safe", "0", "-i", ovl, "-i", MIX_WAV,
         "-filter_complex", f"[1:v]fps={FPS},format=rgba[o];[0:v][o]overlay=0:0:format=auto:shortest=0,format=yuv420p[v]",
         "-map", "[v]", "-map", "2:a", "-frames:v", str(nframes), "-r", str(FPS),
         "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-movflags", "+faststart", FINAL_MP4])
    print("Final:", FINAL_MP4)
    # Frame-0 thumbnail exports from an uncompressed master
    f0 = f"{tmp}/frame0_master.png"
    run(["ffmpeg", "-y", "-ss", f"{SHOT_PLAN[0].src_in:.3f}", "-i", SRC[SHOT_PLAN[0].src], "-frames:v", "1",
         "-filter_complex", f"[0:v]{vf_for(SHOT_PLAN[0])}[v]", "-map", "[v]", f"{tmp}/frame0_base.png"])
    base = Image.open(f"{tmp}/frame0_base.png").convert("RGBA")
    st0 = overlay_states()[0][2]
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if st0["title"]:
        draw_title(o)
    Image.alpha_composite(base, o).convert("RGB").save(f0)
    export_first_frame_thumbnail(mp4_path=FINAL_MP4, raw_frame0_rgb_path=f0, title_preview=TITLE,
                                 generate_preview_sheet=True, native_crop_box=(270, 600, 810, 1140))
    shutil.copy2(f"{OUT}/{SLUG}.jpg", f"{OUT}/thumbnail.jpg")
    pr = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", FINAL_MP4]).stdout
    open(f"{OUT}/ffprobe_validation.json", "w").write(pr)


def preview():
    wins, els, total = shot_windows()
    states = overlay_states()
    pw, ph = 216, 384
    cols = 8
    rows = (len(wins) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (pw + 10) + 10, rows * (ph + 54) + 60), (14, 17, 25))
    d = ImageDraw.Draw(sheet)
    d.text((14, 14), f"POW #06 PREVIEW — {len(wins)} shots, {total:.2f}s", font=font(FONT_BOLD, 26), fill=(255, 255, 255))
    for k, (s, f0, f1) in enumerate(wins):
        tm = (f0 + f1) / 2 / FPS
        local = tm - f0 / FPS
        p = f"{SCR}/pv_{s.sid}.png"
        run(["ffmpeg", "-y", "-ss", f"{s.src_in + local:.3f}", "-i", SRC[s.src], "-frames:v", "1",
             "-filter_complex", f"[0:v]{vf_for(s)}[v]", "-map", "[v]", p])
        im = Image.open(p).convert("RGBA")
        st = next(st for a, b, st in states if a <= tm < b)
        o = Image.new("RGBA", (W, H), (0, 0, 0, 0)); render_overlay_png(st, f"{SCR}/pv_o.png")
        im = Image.alpha_composite(im, Image.open(f"{SCR}/pv_o.png"))
        r, c = divmod(k, cols)
        x, y = 10 + c * (pw + 10), 56 + r * (ph + 54)
        sheet.paste(im.convert("RGB").resize((pw, ph), Image.Resampling.LANCZOS), (x, y))
        d.text((x + 2, y + ph + 4), f"{s.sid} {f0/FPS:.1f}-{f1/FPS:.1f}s", font=font(FONT_BOLD, 15), fill=(255, 228, 96))
        d.text((x + 2, y + ph + 24), f"{s.src}@{s.src_in:.1f}", font=font(FONT_MED, 13), fill=(200, 210, 230))
    sheet.save(f"{OUT}/pre_render_storyboard_contact_sheet.jpg", quality=90)
    print("preview saved")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["audio", "preview", "shots", "render", "all"], required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    only = {x for x in a.only.split(",") if x} or None
    if a.stage in ("audio", "all"):
        build_audio()
    if a.stage in ("preview", "all"):
        preview()
    if a.stage in ("shots", "all"):
        render_shots(only)
    if a.stage in ("render", "all"):
        if a.stage == "render":
            render_shots(only)
        render_final()
