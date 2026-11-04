#!/usr/bin/env python3
"""
Stage 3 & Stage 5: Story-Aware Voice-First Documentary Audio Mixing & Mastering Engine
(`pow_studio.audio_engine` v7.0).

Upgrades the Proof of Wonder audio pipeline (Parts 3, 4, 5, 7, 8, 9):
1. Voice-First Timing Authority (`pow_studio.voice_studio`):
   - `directed_tts` (ElevenLabs model-capability-aware + `$0` `edge-tts` fallback, contrast-balanced
     segment direction, raised-cosine boundary fades, continuity audit, dependent cache invalidation).
   - `uploaded_narration` (Mode A) & `voice_reference` (Mode B with explicit consent).
2. Intelligent Scene & Soundscape Planning (active by default; `legacy_v6_fallback` preserved):
   - Runs `optimize_episode_scenes` (`Keep`/`Replace`/`Merge`/`Remove`) before building stems.
   - Plans `0..3` story-aware music sections (`music_planner`), continuous location ambience
     (`ambience_planner`), and 6-question context-aware SFX (`sfx_planner`), plus exports
     `unified_av_timeline.json` & `.md` (`timeline_builder`).
3. Voice-First Relative Mixing & Per-Layer Automation:
   - Separate automation envelopes for Music, Ambience, Natural Field Audio, and Context SFX.
   - Standard speech ducking + configurable deeper ducking during important phrases & reveals.
   - Ceiling-only relative bed calibration (NEVER boosts quiet or music-free mixes upward).
   - Vocal-pocket EQ, linear dynamic-preserving master calibration, and True-Peak limiting.
   - Exports both `audio_engineering_report.json` and `audio_engineering_report.md`.
"""

from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .ambience_planner import plan_environmental_ambience
from .audio_registry import ensure_audio_asset_registry, resolve_registered_audio_path
from .music_planner import plan_story_music
from .rights_gate import validate_license_string
from .scene_editor import optimize_episode_scenes
from .schema import EpisodeManifest, ShotSpecModel, resolve_timed_shots
from .sfx_library import ensure_sfx_library
from .sfx_planner import plan_context_sfx
from .shot_planner import extract_speech_boundaries
from .timeline_builder import build_unified_av_timeline
from .voice_studio import (
    analyze_voice_reference,
    ingest_uploaded_narration,
    synthesize_directed_narration,
)

SR = 48000
FPS = 30


def _read_wav_stereo_f32(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        sr = wf.getframerate()
        raw = wf.readframes(wf.getnframes())
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    st = arr.reshape(-1, 2) if ch == 2 else np.stack([arr, arr], axis=1)
    if sr != SR and len(st) > 1:
        new_n = max(1, int(round(len(st) * SR / float(sr))))
        x_old = np.linspace(0.0, 1.0, len(st), dtype=np.float32)
        x_new = np.linspace(0.0, 1.0, new_n, dtype=np.float32)
        st = np.stack([np.interp(x_new, x_old, st[:, 0]), np.interp(x_new, x_old, st[:, 1])], axis=1).astype(np.float32)
    return st


def _write_wav_stereo(path: Path, stereo: np.ndarray) -> None:
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def _resolve_asset_file(manifest: EpisodeManifest, filename: str) -> Optional[Path]:
    for d in manifest.all_asset_search_dirs():
        cand = d / filename
        if cand.exists():
            return cand
    direct = Path(filename)
    if direct.exists():
        return direct
    rel_chan = Path(__file__).resolve().parents[2] / filename
    return rel_chan if rel_chan.exists() else None


def _lowpass_fft(sig: np.ndarray, cutoff_hz: float) -> np.ndarray:
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / SR)
    spec = np.fft.rfft(sig)
    gain = 1.0 / np.sqrt(1.0 + (freqs / cutoff_hz) ** 8)
    return np.fft.irfft(spec * gain, n=len(sig)).astype(np.float32)


def _bandpass_fft(sig: np.ndarray, lo_hz: float, hi_hz: float) -> np.ndarray:
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / SR)
    spec = np.fft.rfft(sig)
    hp = 1.0 / np.sqrt(1.0 + (max(lo_hz, 1e-2) / np.maximum(freqs, 1e-2)) ** 6)
    lp = 1.0 / np.sqrt(1.0 + (freqs / hi_hz) ** 6)
    return np.fft.irfft(spec * hp * lp, n=len(sig)).astype(np.float32)


def _speech_duck_envelope(voice_stereo: np.ndarray, duck_depth: float = 0.52) -> np.ndarray:
    """Smooth non-pumping sidechain ducking envelope: 1.0 in pauses, `(1 - duck_depth)` during speech."""
    v_mono = 0.5 * (np.abs(voice_stereo[:, 0]) + np.abs(voice_stereo[:, 1]))
    win = int(0.24 * SR)
    v_rms = np.convolve(v_mono, np.ones(win, dtype=np.float32) / float(win), mode="same")
    speaking = np.clip(v_rms / 0.034, 0.0, 1.0)
    # Long smooth release kernel avoids pumping between adjacent words in a sentence
    smooth_win = int(0.32 * SR)
    speaking = np.convolve(speaking, np.ones(smooth_win, dtype=np.float32) / float(smooth_win), mode="same")
    return (1.0 - duck_depth * np.clip(speaking, 0.0, 1.0)).astype(np.float32)


def _important_phrase_duck_envelope(
    n_samples: int,
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
    extra_duck_db: float = -3.5,
) -> np.ndarray:
    """
    Apply additional smooth attenuation (`extra_duck_db`) to music during central reveals,
    caveats, and emphasized scientific keywords so pivotal spoken phrases stand out clearly.
    """
    env_db = np.zeros(n_samples, dtype=np.float32)
    extra_db = min(0.0, float(extra_duck_db))
    if abs(extra_db) < 0.1:
        return np.ones(n_samples, dtype=np.float32)

    # Central reveal shots
    for s in timed_shots:
        if s.spoken_importance == "central_reveal":
            i0 = max(0, min(n_samples, int(round(s.start_s * SR))))
            i1 = max(i0, min(n_samples, int(round(s.end_s * SR))))
            env_db[i0:i1] = np.minimum(env_db[i0:i1], extra_db)

    # Pivot & caveat narration segments
    important_segs = {
        manifest.editorial_formula.layer2_pivot_seg_id,
        manifest.editorial_formula.scientific_caveat_seg_id,
    }
    for sg in wt.get("segments", []):
        if sg.get("seg_id") in important_segs:
            i0 = max(0, min(n_samples, int(round(float(sg["start"]) * SR))))
            i1 = max(i0, min(n_samples, int(round(float(sg["end"]) * SR))))
            env_db[i0:i1] = np.minimum(env_db[i0:i1], extra_db * 0.85)

    # Emphasis words
    emph_vocab = {
        w.lower().strip(".,!?;:")
        for seg in manifest.narration_segments
        for phr in (seg.emphasis_words or [])
        for w in phr.split()
        if len(w) >= 3
    }
    if emph_vocab:
        for wobj in wt.get("words", []):
            w_clean = str(wobj.get("word", "")).lower().strip(".,!?;:")
            if w_clean in emph_vocab:
                i0 = max(0, min(n_samples, int(round((float(wobj["start"]) - 0.12) * SR))))
                i1 = max(i0, min(n_samples, int(round((float(wobj["end"]) + 0.18) * SR))))
                env_db[i0:i1] = np.minimum(env_db[i0:i1], extra_db)

    xf = max(32, int(0.35 * SR))
    if xf < n_samples:
        kernel = np.hanning(2 * xf + 1).astype(np.float32)
        kernel /= float(np.sum(kernel))
        env_db = np.convolve(env_db, kernel, mode="same").astype(np.float32)
    return (10.0 ** (env_db / 20.0)).astype(np.float32)


def _scene_layer_gate_envelope(timed_shots: list[ShotSpecModel], layer_name: str, n_samples: int, xfade_s: float = 0.35) -> np.ndarray:
    env = np.zeros(n_samples, dtype=np.float32)
    for s in timed_shots:
        if layer_name in (s.scene_audio_layers or []):
            i0 = max(0, min(n_samples, int(round(s.start_s * SR))))
            i1 = max(i0, min(n_samples, int(round(s.end_s * SR))))
            env[i0:i1] = 1.0
    xf = max(16, int(xfade_s * SR))
    if xf < n_samples:
        kernel = np.hanning(2 * xf + 1).astype(np.float32)
        kernel /= float(np.sum(kernel))
        env = np.convolve(env, kernel, mode="same").astype(np.float32)
    return np.clip(env, 0.0, 1.0)


def _loop_crossfade_stereo(clip: np.ndarray, target_len: int, xfade_s: float = 2.0) -> np.ndarray:
    if len(clip) >= target_len:
        return clip[:target_len].copy()
    xf = min(int(xfade_s * SR), len(clip) // 3)
    if xf < 64:
        reps = (target_len + len(clip) - 1) // len(clip)
        return np.tile(clip, (reps, 1))[:target_len].copy()

    out = clip.copy()
    fade_out = np.cos(np.linspace(0.0, 0.5 * np.pi, xf, dtype=np.float32))[:, None]
    fade_in = np.sin(np.linspace(0.0, 0.5 * np.pi, xf, dtype=np.float32))[:, None]
    while len(out) < target_len:
        overlap = out[-xf:] * fade_out + clip[:xf] * fade_in
        out = np.concatenate([out[:-xf], overlap, clip[xf:]], axis=0)
    return out[:target_len].copy()


def _build_v7_story_music_stem(
    music_plan: dict[str, Any],
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
    n_samples: int,
    voice_stereo: np.ndarray,
    scene_gate: np.ndarray,
    speech_duck_db: float,
    important_phrase_duck_db: float,
) -> np.ndarray:
    """
    Render the planned `0..3` story-aware background music sections with pause-aligned
    fades, intentional pre-reveal silence windows, subtle harmonic accents, and
    dual-stage speech + important-phrase ducking.
    """
    sections = music_plan.get("sections", [])
    accents = music_plan.get("musical_accents", [])
    if (not sections and not accents) or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n_samples, 2), dtype=np.float32)

    mus_total = np.zeros((n_samples, 2), dtype=np.float32)

    for sec in sections:
        trk_path = resolve_registered_audio_path(str(sec["track_name"]))
        if trk_path is None or not trk_path.exists():
            continue
        i0 = max(0, min(n_samples, int(round(float(sec["start_s"]) * SR))))
        i1 = max(i0, min(n_samples, int(round(float(sec["end_s"]) * SR))))
        seg_len = i1 - i0
        if seg_len < 128:
            continue

        raw_clip = _read_wav_stereo_f32(trk_path)
        # Normalize clip peak to 0 dBFS before applying exact planned base_gain_db
        pk = float(np.max(np.abs(raw_clip)))
        if pk > 1e-5:
            raw_clip = raw_clip / pk
        seg_audio = _loop_crossfade_stereo(raw_clip, seg_len, xfade_s=2.2)

        fi = min(int(float(sec.get("fade_in_s", 0.8)) * SR), seg_len // 3)
        fo = min(int(float(sec.get("fade_out_s", 1.1)) * SR), seg_len // 3)
        if fi > 2:
            seg_audio[:fi] *= np.sin(np.linspace(0.0, 0.5 * np.pi, fi, dtype=np.float32))[:, None]
        if fo > 2:
            seg_audio[-fo:] *= np.cos(np.linspace(0.0, 0.5 * np.pi, fo, dtype=np.float32))[:, None]

        lin_gain = float(10.0 ** (float(sec.get("base_gain_db", -24.0)) / 20.0))
        mus_total[i0:i1] += seg_audio * lin_gain

    # Apply intentional pre-reveal hush / silence windows smoothly
    hush_env = np.ones(n_samples, dtype=np.float32)
    for hw in music_plan.get("silence_windows", []):
        h0 = max(0, min(n_samples, int(round(float(hw["start_s"]) * SR))))
        h1 = max(h0, min(n_samples, int(round(float(hw["end_s"]) * SR))))
        if h1 > h0:
            hush_env[h0:h1] = 0.12  # -18.4 dB hush so reveal lands out of quiet stillness
    xf_h = max(32, int(0.32 * SR))
    if xf_h < n_samples and music_plan.get("silence_windows"):
        k_h = np.hanning(2 * xf_h + 1).astype(np.float32)
        k_h /= float(np.sum(k_h))
        hush_env = np.convolve(hush_env, k_h, mode="same").astype(np.float32)
    mus_total *= hush_env[:, None]

    # Add optional controlled harmonic reveal accents
    for acc in accents:
        acc_p = resolve_registered_audio_path(str(acc["asset_name"]))
        if acc_p is None or not acc_p.exists():
            continue
        i0 = max(0, min(n_samples, int(round(float(acc["time_s"]) * SR))))
        aclip = _read_wav_stereo_f32(acc_p)
        apk = float(np.max(np.abs(aclip)))
        if apk > 1e-5:
            aclip = aclip / apk
        i1 = min(n_samples, i0 + len(aclip))
        if i1 > i0:
            lg = float(10.0 ** (float(acc.get("gain_db", -23.5)) / 20.0))
            mus_total[i0:i1] += aclip[: i1 - i0] * lg

    # Speech ducking + configurable deeper ducking during important phrases
    duck_lin = 1.0 - float(10.0 ** (min(0.0, float(speech_duck_db)) / 20.0))
    speech_env = _speech_duck_envelope(voice_stereo, duck_depth=max(0.20, min(0.75, duck_lin)))
    extra_phrase_db = float(important_phrase_duck_db) - float(speech_duck_db)
    phrase_env = _important_phrase_duck_envelope(n_samples, manifest, wt, timed_shots, extra_duck_db=min(0.0, extra_phrase_db))

    return (mus_total * (speech_env * phrase_env * scene_gate)[:, None]).astype(np.float32)


def _build_v7_ambience_stem(
    ambience_plan: dict[str, Any],
    n_samples: int,
    voice_stereo: np.ndarray,
    scene_gate: np.ndarray,
) -> np.ndarray:
    """
    Render continuous scene-connected environmental ambience sections (`A01`, `A02`, ...)
    with `1.2s` smooth crossfades across physical location shifts and strict `0.0`
    silence in outer-space vacuum scenes.
    """
    sections = ambience_plan.get("sections", [])
    if not sections or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n_samples, 2), dtype=np.float32)

    rng = np.random.default_rng(20261104)
    t = np.arange(n_samples, dtype=np.float64) / float(SR)
    breath_lfo = (0.52 + 0.48 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 0.055 * t - 0.6))).astype(np.float32)
    base_noise_l = rng.standard_normal(n_samples).astype(np.float32)
    base_noise_r = rng.standard_normal(n_samples).astype(np.float32)

    amb_total = np.zeros((n_samples, 2), dtype=np.float32)
    for sec in sections:
        if not sec.get("audible"):
            continue
        lo_hz, hi_hz = sec.get("band_hz", [95.0, 380.0])
        if hi_hz <= lo_hz or hi_hz <= 1.0:
            continue
        i0 = max(0, min(n_samples, int(round(float(sec["start_s"]) * SR))))
        i1 = max(i0, min(n_samples, int(round(float(sec["end_s"]) * SR))))
        xf = int(round(float(sec.get("crossfade_s", 1.0)) * SR))
        p0 = max(0, i0 - xf // 2)
        p1 = min(n_samples, i1 + xf // 2)
        seg_len = p1 - p0
        if seg_len < 128:
            continue

        nl = _bandpass_fft(base_noise_l[p0:p1], float(lo_hz), float(hi_hz)) * breath_lfo[p0:p1]
        nr = _bandpass_fft(base_noise_r[p0:p1], float(lo_hz), float(hi_hz)) * breath_lfo[p0:p1]
        nl /= max(1e-6, float(np.max(np.abs(nl))))
        nr /= max(1e-6, float(np.max(np.abs(nr))))
        seg_st = np.stack([nl, nr], axis=1)

        fi = min(xf, seg_len // 3)
        fo = min(xf, seg_len // 3)
        if fi > 2 and p0 > 0:
            seg_st[:fi] *= np.sin(np.linspace(0.0, 0.5 * np.pi, fi, dtype=np.float32))[:, None]
        if fo > 2 and p1 < n_samples:
            seg_st[-fo:] *= np.cos(np.linspace(0.0, 0.5 * np.pi, fo, dtype=np.float32))[:, None]

        lin_gain = float(10.0 ** (float(sec.get("target_gain_db", -28.0)) / 20.0))
        amb_total[p0:p1] += seg_st * lin_gain

    duck_env = _speech_duck_envelope(voice_stereo, duck_depth=0.40)
    return (amb_total * (duck_env * scene_gate)[:, None]).astype(np.float32)


def _build_legacy_v6_layer_2_music(preset: str, n: int, voice_stereo: np.ndarray, scene_gate: np.ndarray) -> np.ndarray:
    """Preserved verbatim for `--legacy-v6-fallback` regression comparisons."""
    if preset == "none" or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n, 2), dtype=np.float32)
    t = np.arange(n, dtype=np.float64) / float(SR)
    u = np.linspace(0.0, 1.0, n, dtype=np.float64)
    root_map = {
        "polar_glacial": 73.416,
        "subterranean_earth": 65.406,
        "volcanic_abyss": 58.270,
        "deep_ocean": 55.000,
        "deep_space": 65.406,
        "scientific_discovery": 73.416,
    }
    f_root = root_map.get(preset, 73.416)
    act2_rise = np.clip((u - 0.25) / 0.24, 0.0, 1.0)
    act3_climax = np.clip((u - 0.55) / 0.18, 0.0, 1.0) * np.clip((0.97 - u) / 0.12, 0.25, 1.0)
    lfo1 = 0.58 + 0.42 * np.sin(2.0 * np.pi * 0.052 * t + 0.3)
    lfo2 = 0.52 + 0.48 * np.sin(2.0 * np.pi * 0.039 * t + 1.7)
    lfo3 = 0.46 + 0.54 * np.sin(2.0 * np.pi * 0.029 * t + 2.9)
    pad_l = (
        0.54 * np.sin(2.0 * np.pi * f_root * t) * lfo1
        + (0.26 + 0.14 * act2_rise) * np.sin(2.0 * np.pi * (f_root * 1.5) * t) * lfo2
        + (0.10 + 0.18 * act3_climax) * np.sin(2.0 * np.pi * (f_root * 1.5874) * t) * lfo3
        + 0.12 * act2_rise * np.sin(2.0 * np.pi * (f_root * 2.0) * t)
    ).astype(np.float32)
    pad_r = (
        0.54 * np.sin(2.0 * np.pi * f_root * t + 0.10) * lfo1
        + (0.26 + 0.14 * act2_rise) * np.sin(2.0 * np.pi * (f_root * 1.5005) * t) * lfo2
        + (0.10 + 0.18 * act3_climax) * np.sin(2.0 * np.pi * (f_root * 1.588) * t + 0.26) * lfo3
        + 0.12 * act2_rise * np.sin(2.0 * np.pi * (f_root * 2.001) * t + 0.17)
    ).astype(np.float32)
    mus = np.stack([_lowpass_fft(pad_l, 390.0), _lowpass_fft(pad_r, 390.0)], axis=1)
    mus /= max(1e-6, float(np.max(np.abs(mus))))
    duck_env = _speech_duck_envelope(voice_stereo, duck_depth=0.58)
    return mus * (0.072 * duck_env * scene_gate)[:, None]


def _build_layer_4_natural_sounds(
    manifest: EpisodeManifest,
    n_samples: int,
    voice_stereo: np.ndarray,
    timed_shots: list[ShotSpecModel],
    scene_gate: np.ndarray,
    work_dir: Path,
    forbid_space_nat: bool = False,
) -> np.ndarray:
    """
    Layer 4 — Subject-Specific Authentic Natural & Diegetic Field Sounds:
    Verified commercial-safe expedition audio (`nat_sound_bed_file` + per-shot `nat_audio_gain_db`),
    cleaned gently (`highpass` + rumble/hiss roll-off), gated per scene, and suppressed in space vacuum.
    """
    if forbid_space_nat or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n_samples, 2), dtype=np.float32)

    reg_by_file = {a.local_file: a for a in manifest.assets_register}
    nat_total = np.zeros((n_samples, 2), dtype=np.float32)
    duck_env = _speech_duck_envelope(voice_stereo, duck_depth=0.55)

    if manifest.nat_sound_bed_file:
        if manifest.nat_sound_bed_file in reg_by_file:
            validate_license_string(reg_by_file[manifest.nat_sound_bed_file].license, manifest.nat_sound_bed_file)
        bed_src = _resolve_asset_file(manifest, manifest.nat_sound_bed_file)
        if bed_src is not None:
            t0, t1 = manifest.nat_sound_bed_range_s
            bed_wav = work_dir / "_nat_bed_clean.wav"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", f"{max(0.0, t0):.3f}",
                    "-to", f"{max(t0 + 1.0, t1):.3f}",
                    "-i", str(bed_src),
                    "-af", "highpass=f=75,lowpass=f=6000,afftdn=nf=-28,loudnorm=I=-19.0:TP=-2.0:LRA=11.0",
                    "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
                    str(bed_wav),
                ],
                check=True,
            )
            bed_clip = _read_wav_stereo_f32(bed_wav)
            looped = _loop_crossfade_stereo(bed_clip, n_samples, xfade_s=1.8)
            lin_gain = float(10.0 ** (manifest.nat_sound_gain_db / 20.0))
            nat_total += looped * (lin_gain * duck_env * scene_gate)[:, None]

    for s in timed_shots:
        if s.nat_audio_gain_db is None or s.kind != "video_full":
            continue
        if "natural_sounds" not in (s.scene_audio_layers or []):
            continue
        src_p = _resolve_asset_file(manifest, s.src_file)
        if src_p is None:
            continue
        dur = max(0.3, s.end_s - s.start_s)
        shot_wav = work_dir / f"_nat_shot_{s.sid}.wav"
        res = subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{max(0.0, s.src_in):.3f}",
                "-t", f"{dur:.3f}",
                "-i", str(src_p),
                "-af", "highpass=f=70,lowpass=f=6200,loudnorm=I=-19.0:TP=-2.0:LRA=10.0",
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
                str(shot_wav),
            ],
            capture_output=True,
        )
        if res.returncode != 0 or not shot_wav.exists():
            continue
        clip_st = _read_wav_stereo_f32(shot_wav)
        if len(clip_st) < 64:
            continue
        fn = min(int(0.28 * SR), len(clip_st) // 3)
        if fn > 2:
            clip_st[:fn] *= np.sin(np.linspace(0.0, 0.5 * np.pi, fn, dtype=np.float32))[:, None]
            clip_st[-fn:] *= np.cos(np.linspace(0.0, 0.5 * np.pi, fn, dtype=np.float32))[:, None]
        i0 = int(round(s.start_s * SR))
        i1 = min(n_samples, i0 + len(clip_st))
        if i1 > i0:
            g = float(10.0 ** (s.nat_audio_gain_db / 20.0))
            nat_total[i0:i1] += clip_st[: i1 - i0] * (g * duck_env[i0:i1])[:, None]

    fi_n = min(int(0.30 * SR), n_samples // 6)
    fo_n = min(int(0.45 * SR), n_samples // 6)
    if fi_n > 1:
        nat_total[:fi_n] *= np.linspace(0.25, 1.0, fi_n, dtype=np.float32)[:, None]
    if fo_n > 1:
        nat_total[-fo_n:] *= np.linspace(1.0, 0.25, fo_n, dtype=np.float32)[:, None]
    return nat_total


def _measure_array_lufs(stereo: np.ndarray, probe_path: Path) -> float:
    if float(np.max(np.abs(stereo))) < 1e-5:
        return -70.0
    _write_wav_stereo(probe_path, stereo)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(probe_path), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    probe_path.unlink(missing_ok=True)
    summ = proc.stderr[proc.stderr.rfind("Summary:") :] if "Summary:" in proc.stderr else proc.stderr
    m = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", summ)
    return float(m.group(1)) if m else -70.0


def _calibrate_bed_relative_to_voice(
    bed_st: np.ndarray,
    voice_lufs: float,
    adaptive_audio_profile: str,
    target_bed_lufs: float,
    work_dir: Path,
    legacy_upward_boost: bool = False,
) -> tuple[np.ndarray, dict[str, float]]:
    """
    Voice-First Relative Mixing (Part 8, Section 11):
    - Measures actual `voice_lufs` and ensures the combined non-vocal bed stays at least
      `min_margin_lu` below narration (`ceiling_lufs = min(target_bed_lufs, voice_lufs - min_margin_lu)`).
    - NEVER boosts quiet, minimal, or music-free beds upward in v7 mode (`delta_db <= 0.0` unless
      `legacy_upward_boost=True`), so restrained mixes stay genuinely restrained.
    """
    measured = _measure_array_lufs(bed_st, work_dir / "_bed_probe_lufs.wav")
    if measured <= -65.0:
        return bed_st, {"pre_bed_lufs": measured, "applied_bed_gain_db": 0.0, "post_bed_lufs": measured}

    min_margin_by_profile = {
        "scientific_explanation": 14.5,
        "minimal_documentary": 13.5,
        "immersive_exploration": 11.5,
        "mystery_and_discovery": 11.5,
    }
    min_margin = min_margin_by_profile.get(adaptive_audio_profile, 12.5)
    ceiling_lufs = min(float(target_bed_lufs), float(voice_lufs) - min_margin)

    if legacy_upward_boost:
        delta_db = max(-12.0, min(16.0, float(target_bed_lufs) - measured))
    else:
        # Ceiling-only protection: attenuate if louder than ceiling; allow mild trim if within 3dB; never boost quiet stems!
        delta_db = min(0.0, max(-18.0, ceiling_lufs - measured))

    scaled = (bed_st * float(10.0 ** (delta_db / 20.0))).astype(np.float32)
    ceiling = 0.40
    mag = np.abs(scaled)
    over = mag > ceiling
    if np.any(over):
        scaled[over] = np.sign(scaled[over]) * (ceiling + 0.14 * np.tanh((mag[over] - ceiling) / 0.14))

    post_lufs = round(measured + delta_db, 2)
    return scaled.astype(np.float32), {
        "pre_bed_lufs": round(measured, 2),
        "ceiling_lufs": round(ceiling_lufs, 2),
        "applied_bed_gain_db": round(delta_db, 2),
        "post_bed_lufs": post_lufs,
    }


def _measure_master_audio_diagnostics(
    mix_wav: Path,
    voice_st: np.ndarray,
    wt: dict[str, Any],
    max_unintended_silence_s: float = 1.25,
) -> dict[str, Any]:
    """Measure integrated LUFS, LRA, True Peak, sample clipping, and unintended dead silences."""
    ebu = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(mix_wav), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    summ = ebu.stderr[ebu.stderr.rfind("Summary:") :] if "Summary:" in ebu.stderr else ebu.stderr
    m_i = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", summ)
    m_lra = re.search(r"LRA:\s+([\d.]+)\s+LU", summ)
    m_tp = re.search(r"Peak:\s+(-?[\d.]+)\s+dBFS", summ)

    mix_st = _read_wav_stereo_f32(mix_wav)
    clipped_samples = int(np.sum(np.abs(mix_st) >= 0.998))

    # Build intentional segment boundary pauses so deliberate reflective pauses aren't misflagged as accidental dropouts
    intentional_pause_windows: list[tuple[float, float]] = [
        (float(sb["start"]), float(sb["end"])) for sb in wt.get("soundbites", [])
    ]
    segs = wt.get("segments", [])
    for s_a, s_b in zip(segs, segs[1:]):
        intentional_pause_windows.append((float(s_a["end"]) - 0.05, float(s_b["start"]) + 0.05))

    words = wt.get("words", [])
    excessive_silences: list[dict[str, Any]] = []
    for a, b in zip(words, words[1:]):
        t0, t1 = float(a["end"]), float(b["start"])
        gap = t1 - t0
        # Within-sentence gap > max_unintended_silence_s OR inter-segment gap > 2.2s is flagged
        is_inter_seg = any(max(t0, p0) < min(t1, p1) for p0, p1 in intentional_pause_windows)
        limit = max(2.25, max_unintended_silence_s * 1.7) if is_inter_seg else max_unintended_silence_s
        if gap > limit:
            excessive_silences.append(
                {
                    "start_s": round(t0, 3),
                    "end_s": round(t1, 3),
                    "gap_s": round(gap, 3),
                    "after_word": a["word"],
                }
            )

    lufs_val = float(m_i.group(1)) if m_i else -16.0
    lra_val = float(m_lra.group(1)) if m_lra else 3.2
    tp_val = float(m_tp.group(1)) if m_tp else -1.5
    return {
        "integrated_lufs": lufs_val,
        "loudness_range_lra_lu": lra_val,
        "true_peak_dbtp": tp_val,
        "speech_crest_factor_db": round(tp_val - lufs_val, 2),
        "clipped_samples_count": clipped_samples,
        "excessive_silence_count": len(excessive_silences),
        "excessive_silences": excessive_silences,
        "voice_peak_dbfs": round(float(20.0 * np.log10(max(1e-6, float(np.max(np.abs(voice_st)))))), 2),
    }


def _write_audio_engineering_markdown(path: Path, report: dict[str, Any]) -> None:
    d = report["diagnostics"]
    sl = report["stem_loudness_lufs"]
    lines = [
        f"# Documentary Audio Engineering & Mastering Report — `{report['slug']}`",
        "",
        f"- **Engine Mode:** `{'legacy_v6_fallback' if report.get('legacy_v6_fallback') else 'Studio v7 Voice-First Adaptive Engine'}`",
        f"- **Adaptive Audio Profile:** `{report.get('adaptive_audio_profile')}`",
        f"- **Master Integrated Loudness:** `{d['integrated_lufs']} LUFS` | **LRA:** `{d['loudness_range_lra_lu']} LU` | **True Peak:** `{d['true_peak_dbtp']} dBTP`",
        f"- **Voice-to-Bed Margin:** `{report.get('voice_to_bed_margin_lu')} LU` (`clipped_samples={d['clipped_samples_count']}`, `excessive_silences={d['excessive_silence_count']}`)",
        "",
        "## Per-Layer Stem Loudness",
        "",
        "| Stem | Active | Integrated Loudness | Notes |",
        "|---|---|---:|---|",
        f"| `layer_1_narration` | `True` | `{sl['narration']} LUFS` | Authoritative timing & intelligibility master |",
        f"| `layer_2_music` | `{report['layers_active']['music']}` | `{sl['music']} LUFS` | `{report.get('music_sections_count', 0)}` section(s); speech & important-phrase ducked |",
        f"| `layer_3_ambience` | `{report['layers_active']['ambience']}` | `{sl['ambience']} LUFS` | `{report.get('ambience_sections_count', 0)}` continuous environment section(s) |",
        f"| `layer_4_natural_sounds` | `{report['layers_active']['natural_sounds']}` | `{sl['natural_sounds']} LUFS` | Verified expedition/diegetic field audio |",
        f"| `layer_5_cinematic_sfx` | `{report['layers_active']['cinematic_sfx']}` | `{sl['cinematic_sfx']} LUFS` | `{report.get('approved_sfx_count', 0)}` approved / `{report.get('rejected_sfx_count', 0)}` rejected for silence |",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_episode_audio(manifest: EpisodeManifest, reuse_existing_tts: bool = False) -> dict:
    """
    Build the authoritative narration timing master, run intelligent scene optimization,
    plan story-aware music / continuous ambience / 6-question context SFX, mix with
    voice-first relative calibration, and export comprehensive audio diagnostics.
    """
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    work_dir = out_dir / "work_audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir = ensure_sfx_library()
    ensure_audio_asset_registry()

    wt_path = out_dir / "word_timings.json"
    narr_norm_wav = work_dir / "narration_norm.wav"

    # 1. Stage 3 Voice Studio Routing (Mode A / Mode B / Directed TTS)
    if manifest.voice_input_mode == "uploaded_narration":
        if not manifest.uploaded_narration_file:
            raise ValueError("`voice_input_mode='uploaded_narration'` requires `uploaded_narration_file`.")
        up_p = _resolve_asset_file(manifest, manifest.uploaded_narration_file) or Path(manifest.uploaded_narration_file)
        wt = ingest_uploaded_narration(
            manifest,
            uploaded_file=up_p,
            clean_noise=manifest.uploaded_narration_clean_noise,
        )
    elif manifest.voice_input_mode == "voice_reference":
        if not manifest.voice_reference_file:
            raise ValueError("`voice_input_mode='voice_reference'` requires `voice_reference_file`.")
        ref_p = _resolve_asset_file(manifest, manifest.voice_reference_file) or Path(manifest.voice_reference_file)
        cal_yaml = work_dir / f"calibrated_reference_{manifest.slug}.yaml"
        ref_report = analyze_voice_reference(
            reference_audio_path=ref_p,
            voice_owner_consent=manifest.voice_owner_consent,
            profile_id=f"calibrated_{manifest.slug}",
            out_profile_yaml=cal_yaml,
        )
        (out_dir / "voice_reference_report.json").write_text(json.dumps(ref_report, indent=2), encoding="utf-8")
        manifest_copy = manifest.model_copy(
            update={
                "voice_direction_profile": str(cal_yaml),
                "voice": ref_report["calibrated_profile"]["voice_identity"],
            }
        )
        wt = synthesize_directed_narration(manifest_copy, reuse_existing_cache=True)
        wt["voice_reference_summary"] = {
            "consent_verified": ref_report["consent_verified"],
            "zero_shot_voice_cloning_active": ref_report["zero_shot_voice_cloning_active"],
            "measured_wpm": ref_report["acoustic_metrics"]["measured_wpm"],
            "median_f0_hz": ref_report["acoustic_metrics"]["median_f0_hz"],
        }
        wt_path.write_text(json.dumps(wt, indent=2), encoding="utf-8")
    else:
        wt = synthesize_directed_narration(manifest, reuse_existing_cache=True)

    # Export extracted speech boundaries for Stage 4/5 Narration-Aware Shot Planning
    speech_bounds = extract_speech_boundaries(wt)
    (out_dir / "speech_boundaries.json").write_text(json.dumps(speech_bounds, indent=2), encoding="utf-8")

    # 2. Intelligent Scene Optimization (`Keep` / `Replace` / `Merge` / `Remove`) locked to real narration
    scene_opt = optimize_episode_scenes(manifest, wt, fps=FPS, persist_report=True)
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), FPS)

    # 3. Construct & Export All 5 Scene-Aware Stereo Stems
    voice_st = _read_wav_stereo_f32(narr_norm_wav)
    n_samples = voice_st.shape[0]
    voice_lufs = _measure_array_lufs(voice_st, work_dir / "_voice_probe.wav")

    layer1_path = work_dir / "layer_1_narration.wav"
    _write_wav_stereo(layer1_path, voice_st)

    gate_music = _scene_layer_gate_envelope(timed_shots, "music", n_samples)
    gate_ambience = _scene_layer_gate_envelope(timed_shots, "ambience", n_samples)
    gate_nat = _scene_layer_gate_envelope(timed_shots, "natural_sounds", n_samples)
    gate_sfx = _scene_layer_gate_envelope(timed_shots, "cinematic_sfx", n_samples)

    is_space_vacuum = (
        style.sound_design.scene_audio_profile == "space_vacuum_restrained"
        or manifest.ambience_preset == "deep_space"
    ) and style.sound_design.forbid_fake_space_transmissions

    # Layer 4: Authentic Natural & Expedition Field Sounds
    layer4_nat = np.zeros_like(voice_st)
    if style.sound_design.enable_diegetic_nat_sound:
        layer4_nat = _build_layer_4_natural_sounds(
            manifest,
            n_samples,
            voice_st,
            timed_shots,
            gate_nat,
            work_dir,
            forbid_space_nat=is_space_vacuum and not manifest.nat_sound_bed_file,
        )
    has_nat = bool(np.max(np.abs(layer4_nat)) > 1e-4)
    layer4_path = work_dir / "layer_4_natural_sounds.wav"
    _write_wav_stereo(layer4_path, layer4_nat)

    sfx_applied: list[dict[str, Any]] = []
    music_plan: dict[str, Any] = {}
    ambience_plan: dict[str, Any] = {}
    sfx_plan: dict[str, Any] = {}
    adaptive_prof = "legacy_v6"

    if manifest.legacy_v6_fallback:
        layer2_music = _build_legacy_v6_layer_2_music(manifest.ambience_preset, n_samples, voice_st, gate_music)
        if has_nat:
            layer2_music *= 0.72
        ambience_plan = plan_environmental_ambience(manifest, wt, timed_shots, adaptive_audio_profile="immersive_exploration", out_dir=out_dir)
        layer3_ambience = _build_v7_ambience_stem(ambience_plan, n_samples, voice_st, gate_ambience)
        layer5_sfx = np.zeros_like(voice_st)
        shot_starts = {s.sid: s.start_s for s in timed_shots}
        seg_starts = {s["seg_id"]: float(s["start"]) for s in wt["segments"]}
        for cue in manifest.sfx_cues:
            wav_file = sfx_dir / f"{cue.sfx_name}.wav"
            if not wav_file.exists():
                continue
            base_t = (
                shot_starts.get(cue.anchor_ref, 0.0)
                if cue.anchor_type == "shot_start"
                else (seg_starts.get(cue.anchor_ref, 0.0) if cue.anchor_type == "seg_start" else float(cue.anchor_ref))
            )
            t_cue = max(0.0, base_t + cue.offset_s)
            i0 = int(round(t_cue * SR))
            if i0 >= n_samples:
                continue
            stem = _read_wav_stereo_f32(wav_file)
            i1 = min(n_samples, i0 + stem.shape[0])
            layer5_sfx[i0:i1] += stem[: i1 - i0] * float(10.0 ** (cue.gain_db / 20.0))
            sfx_applied.append({"sfx_name": cue.sfx_name, "time_s": round(t_cue, 3), "gain_db": cue.gain_db})
    else:
        # Studio v7 Story-Aware Music, Continuous Ambience & 6-Question Context SFX
        music_plan = plan_story_music(manifest, wt, timed_shots, out_dir=out_dir)
        adaptive_prof = str((music_plan.get("adaptive_audio_profile") or {}).get("selected_profile", "minimal_documentary"))
        ambience_plan = plan_environmental_ambience(
            manifest, wt, timed_shots, adaptive_audio_profile=adaptive_prof, out_dir=out_dir
        )
        sfx_plan = plan_context_sfx(
            manifest, wt, timed_shots, ambience_plan, adaptive_audio_profile=adaptive_prof, out_dir=out_dir
        )
        build_unified_av_timeline(
            manifest, wt, music_plan=music_plan, ambience_plan=ambience_plan, sfx_plan=sfx_plan, out_dir=out_dir
        )

        layer2_music = _build_v7_story_music_stem(
            music_plan=music_plan,
            manifest=manifest,
            wt=wt,
            timed_shots=timed_shots,
            n_samples=n_samples,
            voice_stereo=voice_st,
            scene_gate=gate_music,
            speech_duck_db=style.sound_design.music_duck_under_speech_db,
            important_phrase_duck_db=style.sound_design.music_duck_important_phrase_db,
        )
        if has_nat:
            layer2_music *= 0.78

        layer3_ambience = _build_v7_ambience_stem(ambience_plan, n_samples, voice_st, gate_ambience)
        if has_nat:
            layer3_ambience *= 0.62

        # Layer 5: Context-verified SFX ONLY (`gate_sfx` strictly respected!)
        layer5_sfx = np.zeros_like(voice_st)
        sfx_duck = _speech_duck_envelope(voice_st, duck_depth=0.28)
        for approved_cue in sfx_plan.get("approved_cues", []):
            wav_file = resolve_registered_audio_path(str(approved_cue["sfx_name"])) or (sfx_dir / f"{approved_cue['sfx_name']}.wav")
            if not wav_file.exists():
                continue
            t_cue = float(approved_cue["time_s"])
            i0 = int(round(t_cue * SR))
            if i0 >= n_samples or float(gate_sfx[min(n_samples - 1, i0)]) < 0.15:
                continue
            stem = _read_wav_stereo_f32(wav_file)
            i1 = min(n_samples, i0 + stem.shape[0])
            lin_gain = float(10.0 ** (float(approved_cue["gain_db"]) / 20.0))
            env_slice = gate_sfx[i0:i1] * sfx_duck[i0:i1]
            layer5_sfx[i0:i1] += stem[: i1 - i0] * (lin_gain * env_slice)[:, None]
            sfx_applied.append(
                {
                    "sfx_name": approved_cue["sfx_name"],
                    "time_s": round(t_cue, 3),
                    "gain_db": approved_cue["gain_db"],
                    "shot_id": approved_cue.get("shot_id", ""),
                    "purpose": approved_cue.get("purpose", ""),
                }
            )

    layer2_path = work_dir / "layer_2_music.wav"
    layer3_path = work_dir / "layer_3_ambience.wav"
    layer5_path = work_dir / "layer_5_cinematic_sfx.wav"
    _write_wav_stereo(layer2_path, layer2_music)
    _write_wav_stereo(layer3_path, layer3_ambience)
    _write_wav_stereo(layer5_path, layer5_sfx)

    # Voice-first relative bed calibration (ceiling-only in v7; upward-boost only in legacy_v6_fallback)
    target_bed_lufs = float(manifest.ambience_ducked_lufs_target)
    if target_bed_lufs < -36.0 or target_bed_lufs > -24.0:
        target_bed_lufs = float(style.sound_design.target_bed_lufs)

    combined_bed, bed_cal_info = _calibrate_bed_relative_to_voice(
        bed_st=layer2_music + layer3_ambience + layer4_nat + layer5_sfx,
        voice_lufs=voice_lufs,
        adaptive_audio_profile=adaptive_prof,
        target_bed_lufs=target_bed_lufs,
        work_dir=work_dir,
        legacy_upward_boost=manifest.legacy_v6_fallback,
    )
    _write_wav_stereo(work_dir / "ambience_and_sfx_stem.wav", combined_bed)

    raw_mix_wav = work_dir / "final_audio_mix_pre.wav"
    _write_wav_stereo(raw_mix_wav, np.clip(voice_st + combined_bed, -0.98, 0.98))

    mix_wav = work_dir / "final_audio_mix.wav"
    mix_mp3 = out_dir / "final_audio_mix.mp3"
    pre_ebu = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(raw_mix_wav), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    pre_summ = pre_ebu.stderr[pre_ebu.stderr.rfind("Summary:") :] if "Summary:" in pre_ebu.stderr else pre_ebu.stderr
    m_pre_i = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", pre_summ)
    measured_pre_i = float(m_pre_i.group(1)) if m_pre_i else style.output.target_loudness_lufs
    linear_gain_db = max(-10.0, min(10.0, float(style.output.target_loudness_lufs) - measured_pre_i))
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_mix_wav),
            "-af", f"highpass=f=32,volume={linear_gain_db:.2f}dB,alimiter=limit=0.841:attack=5:release=60:level=false",
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            str(mix_wav),
        ],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mix_wav), "-c:a", "libmp3lame", "-b:a", "256k", str(mix_mp3)],
        check=True,
    )

    diag = _measure_master_audio_diagnostics(
        mix_wav=mix_wav,
        voice_st=voice_st,
        wt=wt,
        max_unintended_silence_s=style.sound_design.max_unintended_silence_s,
    )
    stem_lufs = {
        "narration": round(voice_lufs, 2),
        "music": round(_measure_array_lufs(layer2_music, work_dir / "_m_probe.wav"), 2),
        "ambience": round(_measure_array_lufs(layer3_ambience, work_dir / "_a_probe.wav"), 2),
        "natural_sounds": round(_measure_array_lufs(layer4_nat, work_dir / "_n_probe.wav"), 2),
        "cinematic_sfx": round(_measure_array_lufs(layer5_sfx, work_dir / "_s_probe.wav"), 2),
        "combined_bed": bed_cal_info["post_bed_lufs"],
    }
    voice_margin_lu = round(voice_lufs - bed_cal_info["post_bed_lufs"], 2)

    audio_report = {
        "slug": manifest.slug,
        "engine_version": "6.0-fallback" if manifest.legacy_v6_fallback else "7.0",
        "legacy_v6_fallback": manifest.legacy_v6_fallback,
        "voice_input_mode": manifest.voice_input_mode,
        "scene_audio_profile": style.sound_design.scene_audio_profile,
        "adaptive_audio_profile": adaptive_prof,
        "scene_optimization_counts": scene_opt.get("counts", {}),
        "music_sections_count": music_plan.get("music_sections_count", 1 if manifest.legacy_v6_fallback else 0),
        "ambience_sections_count": ambience_plan.get("audible_ambience_sections_count", 0),
        "approved_sfx_count": len(sfx_applied),
        "rejected_sfx_count": sfx_plan.get("rejected_for_silence_count", 0),
        "bed_calibration": bed_cal_info,
        "voice_to_bed_margin_lu": voice_margin_lu,
        "stem_loudness_lufs": stem_lufs,
        "stems": {
            "layer_1_narration": str(layer1_path),
            "layer_2_music": str(layer2_path),
            "layer_3_ambience": str(layer3_path),
            "layer_4_natural_sounds": str(layer4_path),
            "layer_5_cinematic_sfx": str(layer5_path),
        },
        "layers_active": {
            "narration": True,
            "music": bool(np.max(np.abs(layer2_music)) > 1e-4),
            "ambience": bool(np.max(np.abs(layer3_ambience)) > 1e-4),
            "natural_sounds": has_nat,
            "cinematic_sfx": len(sfx_applied) > 0,
        },
        "diagnostics": diag,
    }
    (out_dir / "audio_engineering_report.json").write_text(json.dumps(audio_report, indent=2), encoding="utf-8")
    _write_audio_engineering_markdown(out_dir / "audio_engineering_report.md", audio_report)

    wt["sfx_applied"] = sfx_applied
    wt["diegetic_nat_sound_active"] = has_nat
    wt["adaptive_audio_profile"] = adaptive_prof
    wt["music_sections_count"] = audio_report["music_sections_count"]
    wt["ambience_sections_count"] = audio_report["ambience_sections_count"]
    wt["scene_optimization_counts"] = scene_opt.get("counts", {})
    wt["audio_layers_exported"] = list(audio_report["stems"].keys())
    wt["audio_diagnostics"] = diag
    wt_path.write_text(json.dumps(wt, indent=2), encoding="utf-8")
    return wt
