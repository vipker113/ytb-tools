#!/usr/bin/env python3
"""
Generates 6 warm, studio-mastered, 100% Royalty-Free / 0% Content-ID stereo BGM tracks
(`ytb-tools/public/reup-bgm/*.m4a`, 32s seamless loopable @ 44.1kHz AAC 192kbps, -14 LUFS)
tailored for beauty, selfie, fashion, cosplay, and dance Shorts.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from scipy import signal

SR = 44100


def midi_to_hz(note: float) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))


def soft_epiano_note(freq: float, dur: float, vel: float = 0.7) -> np.ndarray:
    n = max(1, int(SR * dur))
    t = np.arange(n, dtype=np.float32) / SR
    # Warm Rhodes-style harmonic profile with gentle bell tine decay
    env_body = np.exp(-t * 2.4) * (1.0 - np.exp(-t * 140.0))
    env_tine = np.exp(-t * 9.5) * (1.0 - np.exp(-t * 260.0))
    mod = 0.35 * env_tine * np.sin(2.0 * math.pi * (freq * 2.0) * t)
    sig = (
        0.68 * np.sin(2.0 * math.pi * freq * t + mod)
        + 0.22 * np.sin(2.0 * math.pi * (freq * 2.0) * t) * np.exp(-t * 3.8)
        + 0.08 * np.sin(2.0 * math.pi * (freq * 3.0) * t) * np.exp(-t * 5.5)
        + 0.05 * np.sin(2.0 * math.pi * (freq * 4.0) * t) * env_tine
    )
    # Gentle release tail to avoid clicks
    rel = min(n // 4, int(0.04 * SR))
    if rel > 4:
        env_body[-rel:] *= np.linspace(1.0, 0.0, rel, dtype=np.float32)
    return (sig * env_body * vel).astype(np.float32)


def pluck_bell_note(freq: float, dur: float, brightness: float = 0.5, vel: float = 0.75) -> np.ndarray:
    n = max(1, int(SR * dur))
    t = np.arange(n, dtype=np.float32) / SR
    attack = 1.0 - np.exp(-t * 320.0)
    decay1 = np.exp(-t * 5.2)
    decay2 = np.exp(-t * 11.0)
    fm = brightness * 0.9 * decay2 * np.sin(2.0 * math.pi * (freq * 2.002) * t)
    sig = (
        0.72 * np.sin(2.0 * math.pi * freq * t + fm) * decay1
        + 0.24 * np.sin(2.0 * math.pi * (freq * 2.0) * t) * decay2
        + 0.09 * np.sin(2.0 * math.pi * (freq * 3.0) * t) * np.exp(-t * 15.0)
    ) * attack
    rel = min(n // 4, int(0.025 * SR))
    if rel > 4:
        sig[-rel:] *= np.linspace(1.0, 0.0, rel, dtype=np.float32)
    return (sig * vel).astype(np.float32)


def warm_sub_bass(freq: float, dur: float, punch: float = 0.5, vel: float = 0.8) -> np.ndarray:
    n = max(1, int(SR * dur))
    t = np.arange(n, dtype=np.float32) / SR
    att = 1.0 - np.exp(-t * 110.0)
    dec = np.exp(-t * (1.8 + punch * 1.4))
    # Pitch drop transient for punchy modern pop/house bass
    p_drop = 1.0 + 0.22 * punch * np.exp(-t * 45.0)
    phase = 2.0 * math.pi * freq * np.cumsum(p_drop) / SR
    raw = np.sin(phase) + 0.32 * np.sin(2.0 * phase) + 0.12 * np.sin(3.0 * phase)
    sig = np.tanh(raw * 1.35) * att * dec
    rel = min(n // 4, int(0.03 * SR))
    if rel > 4:
        sig[-rel:] *= np.linspace(1.0, 0.0, rel, dtype=np.float32)
    return (sig * vel).astype(np.float32)


def lush_pad_chord(freqs: list[float], dur: float, vel: float = 0.35) -> tuple[np.ndarray, np.ndarray]:
    n = max(1, int(SR * dur))
    t = np.arange(n, dtype=np.float32) / SR
    fade_in = np.minimum(1.0, t / max(0.08, min(0.45, dur * 0.25)))
    fade_out = np.minimum(1.0, (dur - t) / max(0.08, min(0.45, dur * 0.25)))
    env = (fade_in * fade_out).astype(np.float32)
    left = np.zeros(n, dtype=np.float32)
    right = np.zeros(n, dtype=np.float32)
    for idx, f in enumerate(freqs):
        # Detuned stereo unison voices
        for det_l, det_r, gain in ((-0.0032, 0.0035, 0.55), (0.0018, -0.0021, 0.45)):
            fl = f * (1.0 + det_l)
            fr = f * (1.0 + det_r)
            ph0 = (idx * 1.17) % (2.0 * math.pi)
            wl = np.sin(2.0 * math.pi * fl * t + ph0) + 0.28 * np.sin(4.0 * math.pi * fl * t)
            wr = np.sin(2.0 * math.pi * fr * t + ph0 + 0.4) + 0.28 * np.sin(4.0 * math.pi * fr * t + 0.4)
            left += gain * wl
            right += gain * wr
    scale = vel / max(1.0, len(freqs))
    return left * env * scale, right * env * scale


def synth_kick(punchy: bool = False) -> np.ndarray:
    dur = 0.22 if punchy else 0.18
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    f_curve = 48.0 + (115.0 if punchy else 78.0) * np.exp(-t * 36.0)
    phase = 2.0 * math.pi * np.cumsum(f_curve) / SR
    env = np.exp(-t * (13.0 if punchy else 16.0))
    click = 0.18 * np.exp(-t * 180.0) * np.sin(2.0 * math.pi * 1100.0 * t)
    return np.tanh((np.sin(phase) * env + click) * 1.4).astype(np.float32)


def synth_snare_or_clap(rng: np.random.Generator, clap: bool = False) -> np.ndarray:
    dur = 0.16 if clap else 0.13
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    sos = signal.butter(2, [950, 5800] if clap else [500, 4200], btype="bandpass", fs=SR, output="sos")
    filt = signal.sosfilt(sos, noise).astype(np.float32)
    if clap:
        env = (
            0.45 * np.exp(-np.maximum(0.0, t) * 95.0)
            + 0.55 * np.exp(-np.maximum(0.0, t - 0.011) * 85.0) * (t >= 0.011)
            + 0.85 * np.exp(-np.maximum(0.0, t - 0.022) * 26.0) * (t >= 0.022)
        )
        return (filt * env * 0.55).astype(np.float32)
    body = 0.35 * np.sin(2.0 * math.pi * 195.0 * t) * np.exp(-t * 38.0)
    env = np.exp(-t * 32.0)
    return ((filt * env * 0.45) + body).astype(np.float32)


def synth_hat(rng: np.random.Generator, open_hat: bool = False) -> np.ndarray:
    dur = 0.14 if open_hat else 0.045
    n = int(SR * dur)
    t = np.arange(n, dtype=np.float32) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    sos = signal.butter(2, 6800, btype="highpass", fs=SR, output="sos")
    filt = signal.sosfilt(sos, noise).astype(np.float32)
    env = np.exp(-t * (18.0 if open_hat else 72.0))
    return (filt * env * 0.22).astype(np.float32)


def add_stereo(mix_l: np.ndarray, mix_r: np.ndarray, start_s: float, mono: np.ndarray, pan: float = 0.0) -> None:
    idx = int(round(start_s * SR))
    if idx < 0 or idx >= len(mix_l):
        return
    end = min(len(mix_l), idx + len(mono))
    seg = mono[: end - idx]
    gl = math.cos((pan + 1.0) * math.pi * 0.25)
    gr = math.sin((pan + 1.0) * math.pi * 0.25)
    mix_l[idx:end] += seg * gl
    mix_r[idx:end] += seg * gr


def apply_stereo_ambience(mix_l: np.ndarray, mix_r: np.ndarray, wet: float = 0.22, delay_s: float = 0.26) -> tuple[np.ndarray, np.ndarray]:
    # Stereo ping-pong echo + multi-tap diffusion for studio depth
    n = len(mix_l)
    dl = np.zeros(n, dtype=np.float32)
    dr = np.zeros(n, dtype=np.float32)
    d1 = int(delay_s * SR)
    d2 = int(delay_s * 1.5 * SR)
    if d1 < n:
        dl[d1:] += mix_r[:-d1] * 0.34
        dr[d1:] += mix_l[:-d1] * 0.34
    if d2 < n:
        dl[d2:] += mix_l[:-d2] * 0.18
        dr[d2:] += mix_r[:-d2] * 0.18
    # Warm lowpass on reverb/delay tail (~5.2kHz) so highs stay silky
    sos = signal.butter(2, 5200, btype="lowpass", fs=SR, output="sos")
    dl = signal.sosfilt(sos, dl).astype(np.float32)
    dr = signal.sosfilt(sos, dr).astype(np.float32)
    return mix_l + dl * wet, mix_r + dr * wet


def render_track_to_m4a(out_path: Path, mix_l: np.ndarray, mix_r: np.ndarray) -> None:
    peak = max(1e-4, float(max(np.max(np.abs(mix_l)), np.max(np.abs(mix_r)))))
    mix_l = np.tanh((mix_l / peak) * 1.15) * 0.88
    mix_r = np.tanh((mix_r / peak) * 1.15) * 0.88

    # Smooth 35ms loop boundary cross-Polish to avoid clicks on -stream_loop -1
    fade = int(0.035 * SR)
    ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
    mix_l[:fade] *= ramp
    mix_r[:fade] *= ramp
    mix_l[-fade:] *= ramp[::-1]
    mix_r[-fade:] *= ramp[::-1]

    stereo = np.stack([mix_l, mix_r], axis=1)
    pcm16 = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_tmp = Path(tf.name)
    try:
        with wave.open(str(wav_tmp), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(SR)
            wf.writeframes(pcm16.tobytes())

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(wav_tmp),
                "-af",
                "loudnorm=I=-14.5:TP=-1.2:LRA=9",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                str(out_path),
            ],
            check=True,
        )
    finally:
        wav_tmp.unlink(missing_ok=True)


TRACK_SPECS = [
    {
        "filename": "sweet_douyin_bell.m4a",
        "bpm": 108,
        "bars": 16,
        "style": "douyin_bell",
        # Fmaj7 -> G6 -> Em7 -> Am7
        "chords": [[65, 69, 72, 76], [67, 71, 74, 76], [64, 67, 71, 74], [69, 72, 76, 79]],
        "bass": [41, 43, 40, 45],
        "melody": [76, 77, 79, 76, 74, 76, 79, 81, 79, 76, 74, 71, 72, 76, 79, 76],
    },
    {
        "filename": "cute_kpop_bounce.m4a",
        "bpm": 118,
        "bars": 16,
        "style": "kpop_bounce",
        # Cadd9 -> G -> Am7 -> Fmaj7
        "chords": [[60, 64, 67, 74], [67, 71, 74, 79], [69, 72, 76, 79], [65, 69, 72, 76]],
        "bass": [36, 43, 45, 41],
        "melody": [79, 76, 74, 76, 79, 81, 79, 74, 76, 79, 81, 84, 81, 79, 77, 76],
    },
    {
        "filename": "dreamy_fairy_chill.m4a",
        "bpm": 92,
        "bars": 12,
        "style": "dreamy_fairy",
        # Dmaj7 -> Bm7 -> Gmaj7 -> Asus4
        "chords": [[62, 66, 69, 73], [59, 62, 66, 69], [55, 59, 62, 66], [57, 62, 64, 69]],
        "bass": [38, 35, 43, 45],
        "melody": [78, 76, 73, 74, 78, 81, 78, 73, 74, 78, 76, 73, 74, 76, 73, 69],
    },
    {
        "filename": "lofi_cafe_smile.m4a",
        "bpm": 86,
        "bars": 12,
        "style": "lofi_cafe",
        # Ebmaj7 -> Cm9 -> Fm9 -> Bb13
        "chords": [[63, 67, 70, 74], [60, 63, 67, 74], [65, 68, 72, 75], [58, 62, 65, 70]],
        "bass": [39, 36, 41, 46],
        "melody": [74, 75, 79, 75, 74, 70, 72, 74, 75, 77, 79, 75, 74, 72, 70, 67],
    },
    {
        "filename": "dance_trend_club.m4a",
        "bpm": 124,
        "bars": 16,
        "style": "dance_club",
        # Am -> F -> C -> G
        "chords": [[57, 60, 64, 69], [53, 57, 60, 65], [60, 64, 67, 72], [55, 59, 62, 67]],
        "bass": [45, 41, 36, 43],
        "melody": [76, 76, 79, 76, 81, 79, 76, 72, 76, 76, 79, 81, 84, 81, 79, 74],
    },
    {
        "filename": "sunny_summer_breeze.m4a",
        "bpm": 112,
        "bars": 16,
        "style": "sunny_summer",
        # G -> D -> Em7 -> Cmaj7
        "chords": [[67, 71, 74, 79], [62, 66, 69, 74], [64, 67, 71, 74], [60, 64, 67, 71]],
        "bass": [43, 38, 40, 36],
        "melody": [79, 83, 81, 79, 78, 74, 76, 78, 79, 83, 86, 83, 81, 79, 76, 74],
    },
]


def build_track(spec: dict, out_dir: Path) -> Path:
    rng = np.random.default_rng(abs(hash(spec["filename"])) % (2**31))
    bpm = float(spec["bpm"])
    beat_s = 60.0 / bpm
    bar_s = beat_s * 4.0
    total_bars = int(spec["bars"])
    dur_s = total_bars * bar_s
    n_samples = int(round(dur_s * SR))

    mix_l = np.zeros(n_samples, dtype=np.float32)
    mix_r = np.zeros(n_samples, dtype=np.float32)
    style = spec["style"]

    kick = synth_kick(punchy=(style in ("dance_club", "kpop_bounce")))
    snare = synth_snare_or_clap(rng, clap=(style in ("kpop_bounce", "dance_club", "sunny_summer")))
    hat_c = synth_hat(rng, open_hat=False)
    hat_o = synth_hat(rng, open_hat=True)

    chords = spec["chords"]
    bass_notes = spec["bass"]
    mel = spec["melody"]

    for bar in range(total_bars):
        t_bar = bar * bar_s
        chord = chords[bar % len(chords)]
        bass_midi = bass_notes[bar % len(bass_notes)]
        freqs = [midi_to_hz(m) for m in chord]

        # 1. Lush stereo pad layer
        pl, pr = lush_pad_chord(freqs, bar_s * 1.02, vel=0.34 if style == "dreamy_fairy" else 0.20)
        idx0 = int(round(t_bar * SR))
        end0 = min(n_samples, idx0 + len(pl))
        mix_l[idx0:end0] += pl[: end0 - idx0]
        mix_r[idx0:end0] += pr[: end0 - idx0]

        # 2. Rhodes / Electric Piano chord comping
        if style in ("lofi_cafe", "douyin_bell"):
            comp_beats = [(0.0, 2.2), (2.5, 1.4)]
        elif style in ("kpop_bounce", "sunny_summer"):
            comp_beats = [(0.0, 0.8), (0.75, 0.8), (1.5, 1.1), (2.5, 0.8), (3.25, 0.7)]
        elif style == "dance_club":
            comp_beats = [(0.5, 0.45), (1.5, 0.45), (2.5, 0.45), (3.5, 0.45)]
        else:
            comp_beats = [(0.0, 3.8)]

        for b_off, b_len in comp_beats:
            for ni, m in enumerate(chord):
                note_wav = soft_epiano_note(midi_to_hz(m), b_len * beat_s, vel=0.22)
                strum = ni * 0.014
                pan = -0.25 + 0.16 * ni
                add_stereo(mix_l, mix_r, t_bar + b_off * beat_s + strum, note_wav, pan=pan)

        # 3. Warm Sub-Bass groove
        if style == "dance_club":
            bass_pat = [(0.0, 0.45), (0.5, 0.45), (1.0, 0.45), (1.5, 0.45), (2.0, 0.45), (2.5, 0.45), (3.0, 0.45), (3.5, 0.45)]
        elif style in ("kpop_bounce", "sunny_summer"):
            bass_pat = [(0.0, 1.3), (1.5, 0.9), (2.5, 1.3)]
        elif style == "dreamy_fairy":
            bass_pat = [(0.0, 3.8)]
        else:
            bass_pat = [(0.0, 1.8), (2.5, 1.4)]

        for ni_b, (b_off, b_len) in enumerate(bass_pat):
            oct_shift = 12 if (style == "dance_club" and ni_b % 2 == 1) else 0
            b_wav = warm_sub_bass(
                midi_to_hz(bass_midi + oct_shift),
                b_len * beat_s,
                punch=0.8 if style in ("dance_club", "kpop_bounce") else 0.35,
                vel=0.44,
            )
            add_stereo(mix_l, mix_r, t_bar + b_off * beat_s, b_wav, pan=0.0)

        # 4. Sparkly Kalimba / Pluck Bell Melody + Arpeggio
        for step in range(8):
            swing = 0.03 * beat_s if (style == "lofi_cafe" and step % 2 == 1) else 0.0
            t_note = t_bar + step * 0.5 * beat_s + swing
            if style == "dreamy_fairy" or (bar % 2 == 1 and step in (1, 5)):
                arp_m = chord[step % len(chord)] + 12
                p_wav = pluck_bell_note(midi_to_hz(arp_m), 0.65 * beat_s, brightness=0.4, vel=0.22)
                add_stereo(mix_l, mix_r, t_note, p_wav, pan=(-0.35 if step % 2 == 0 else 0.35))

            if step % 2 == 0 or (step in (3, 7) and bar % 2 == 0):
                m_note = mel[(bar * 4 + step // 2) % len(mel)]
                p_wav = pluck_bell_note(
                    midi_to_hz(m_note),
                    0.85 * beat_s,
                    brightness=0.65 if style in ("kpop_bounce", "dance_club") else 0.42,
                    vel=0.30,
                )
                add_stereo(mix_l, mix_r, t_note, p_wav, pan=0.12 * math.sin(step))

        # 5. Drums & Percussion (skipped on dreamy_fairy bars 0..1 for soft intro feel, full groove otherwise)
        if style != "dreamy_fairy":
            if style == "dance_club":
                k_beats = [0.0, 1.0, 2.0, 3.0]
                s_beats = [1.0, 3.0]
            elif style in ("kpop_bounce", "sunny_summer"):
                k_beats = [0.0, 1.5, 2.5]
                s_beats = [1.0, 3.0]
            else:
                k_beats = [0.0, 2.5]
                s_beats = [1.0, 3.0]

            for kb in k_beats:
                add_stereo(mix_l, mix_r, t_bar + kb * beat_s, kick * 0.68, pan=0.0)
            for sb in s_beats:
                add_stereo(mix_l, mix_r, t_bar + sb * beat_s, snare * 0.52, pan=0.04)

            for h_step in range(8):
                swing = 0.03 * beat_s if (style == "lofi_cafe" and h_step % 2 == 1) else 0.0
                t_h = t_bar + h_step * 0.5 * beat_s + swing
                if style == "dance_club" and h_step % 2 == 1:
                    add_stereo(mix_l, mix_r, t_h, hat_o * 0.55, pan=-0.15)
                else:
                    add_stereo(mix_l, mix_r, t_h, hat_c * 0.48, pan=0.15 if h_step % 2 == 0 else -0.12)

    mix_l, mix_r = apply_stereo_ambience(
        mix_l,
        mix_r,
        wet=0.34 if style == "dreamy_fairy" else 0.22,
        delay_s=beat_s * 0.75,
    )
    out_file = out_dir / spec["filename"]
    render_track_to_m4a(out_file, mix_l, mix_r)
    return out_file


def main() -> None:
    out_dir = Path(__file__).resolve().parents[1] / "public" / "reup-bgm"
    out_dir.mkdir(parents=True, exist_ok=True)
    for spec in TRACK_SPECS:
        p = build_track(spec, out_dir)
        print(f"GENERATED {p.name} ({p.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
