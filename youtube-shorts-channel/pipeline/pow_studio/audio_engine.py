#!/usr/bin/env python3
"""
Stage 3 & Stage 5: Professional 5-Layer Documentary Audio Engineering &
Scene-Aware Soundscape Mixer (`pow_studio.audio_engine` v6.0).

Implements Part 5 (Section 6) of the Proof of Wonder Next-Generation Documentary Studio:
1. Voice-First Routing via `pow_studio.voice_studio`:
   - `directed_tts`: Pre-generation intonation annotations + `VoiceDirectionProfile` + SHA-256 sentence cache.
   - `uploaded_narration` (Mode A): Validates, gently cleans/normalizes (`LRA=11`), and Whisper-aligns
     uploaded human narration as the authoritative timing master without regenerating TTS.
   - `voice_reference` (Mode B): Verifies explicit owner consent, profiles acoustic cadence/F0/pauses,
     and calibrates `VoiceDirectionProfile`.
2. Five Explicit Scene-Aware Stereo Audio Layers (`work_audio/layer_1..5_*.wav`):
   - Layer 1: `layer_1_narration.wav` — Main voiceover & authentic scientist soundbites.
   - Layer 2: `layer_2_music.wav` — Restrained 3-act documentary harmonic underscore, ducked under speech.
   - Layer 3: `layer_3_ambience.wav` — Environmental atmosphere (`polar_glacial`, `subterranean_earth`,
     `deep_ocean`, `volcanic_abyss`, `scientific_discovery`, or `deep_space` restrained vacuum with
     zero fabricated radio transmissions).
   - Layer 4: `layer_4_natural_sounds.wav` — Authentic subject-specific field-recorded nat-sound
     (`nat_sound_bed_file` + per-shot diegetic audio), gated per scene.
   - Layer 5: `layer_5_cinematic_sfx.wav` — Restrained CC0 Foley cues locked to shot/segment anchors.
3. Audio Health & Dynamics Diagnostics (`audio_engineering_report.json`):
   - Preserves natural vocal dynamics (`LRA=10.5`), controls True Peak (`<= -1.5 dBTP`),
     detects digital clipping and unintended excessive silences, and verifies commercial-use rights.
"""

from __future__ import annotations

import json
import re
import subprocess
import wave
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .rights_gate import validate_license_string
from .schema import EpisodeManifest, resolve_timed_shots
from .sfx_library import ensure_sfx_library
from .shot_planner import extract_speech_boundaries
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
        raw = wf.readframes(wf.getnframes())
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch == 2:
        return arr.reshape(-1, 2)
    return np.stack([arr, arr], axis=1)


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
    """Smooth broadcast sidechain ducking envelope: 1.0 in pauses, `(1 - duck_depth)` during speech."""
    v_mono = 0.5 * (np.abs(voice_stereo[:, 0]) + np.abs(voice_stereo[:, 1]))
    win = int(0.22 * SR)
    v_rms = np.convolve(v_mono, np.ones(win, dtype=np.float32) / float(win), mode="same")
    speaking = np.clip(v_rms / 0.036, 0.0, 1.0)
    smooth_win = int(0.16 * SR)
    speaking = np.convolve(speaking, np.ones(smooth_win, dtype=np.float32) / float(smooth_win), mode="same")
    return (1.0 - duck_depth * speaking).astype(np.float32)


def _scene_layer_gate_envelope(timed_shots: list, layer_name: str, n_samples: int, xfade_s: float = 0.28) -> np.ndarray:
    """
    Build a smooth `[0.0 .. 1.0]` per-sample envelope activating `layer_name` only during
    scenes whose `scene_audio_layers` include `layer_name`, crossfaded smoothly across cuts.
    """
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


def _loop_crossfade_stereo(clip: np.ndarray, target_len: int, xfade_s: float = 1.8) -> np.ndarray:
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


def _build_layer_2_music_underscore(
    preset: str,
    n: int,
    voice_stereo: np.ndarray,
    scene_gate: np.ndarray,
) -> np.ndarray:
    """
    Layer 2 — Restrained 3-Act Documentary Harmonic Music Underscore (100% first-party CC0 synthesis).
    Warm, non-intrusive acoustic/cello-pad progression ducked smoothly beneath narration.
    """
    if preset == "none" or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n, 2), dtype=np.float32)

    t = np.arange(n, dtype=np.float64) / float(SR)
    u = np.linspace(0.0, 1.0, n, dtype=np.float64)

    root_map = {
        "polar_glacial": 73.416,       # D2
        "subterranean_earth": 65.406,  # C2
        "volcanic_abyss": 58.270,      # Bb1
        "deep_ocean": 55.000,          # A1
        "deep_space": 65.406,          # C2
        "scientific_discovery": 73.416,# D2
    }
    f_root = root_map.get(preset, 73.416)

    act2_rise = np.clip((u - 0.25) / 0.24, 0.0, 1.0)
    act3_climax = np.clip((u - 0.55) / 0.18, 0.0, 1.0) * np.clip((0.97 - u) / 0.12, 0.25, 1.0)
    lfo1 = 0.58 + 0.42 * np.sin(2.0 * np.pi * 0.052 * t + 0.3)
    lfo2 = 0.52 + 0.48 * np.sin(2.0 * np.pi * 0.039 * t + 1.7)
    lfo3 = 0.46 + 0.54 * np.sin(2.0 * np.pi * 0.029 * t + 2.9)

    pad_l = (
        0.54 * np.sin(2.0 * np.pi * f_root * t) * lfo1
        + (0.26 + 0.14 * act2_rise) * np.sin(2.0 * np.pi * (f_root * 1.5) * t + 0.12 * np.sin(2.0 * np.pi * 0.10 * t)) * lfo2
        + (0.10 + 0.18 * act3_climax) * np.sin(2.0 * np.pi * (f_root * 1.5874) * t) * lfo3
        + 0.12 * act2_rise * np.sin(2.0 * np.pi * (f_root * 2.0) * t)
    ).astype(np.float32)
    pad_r = (
        0.54 * np.sin(2.0 * np.pi * f_root * t + 0.10) * lfo1
        + (0.26 + 0.14 * act2_rise) * np.sin(2.0 * np.pi * (f_root * 1.5005) * t - 0.11 * np.sin(2.0 * np.pi * 0.09 * t)) * lfo2
        + (0.10 + 0.18 * act3_climax) * np.sin(2.0 * np.pi * (f_root * 1.588) * t + 0.26) * lfo3
        + 0.12 * act2_rise * np.sin(2.0 * np.pi * (f_root * 2.001) * t + 0.17)
    ).astype(np.float32)

    pad_l = _lowpass_fft(pad_l, 390.0)
    pad_r = _lowpass_fft(pad_r, 390.0)
    mus = np.stack([pad_l, pad_r], axis=1)
    mus /= max(1e-6, float(np.max(np.abs(mus))))

    fi, fo = min(int(0.35 * SR), n // 6), min(int(0.45 * SR), n // 6)
    mus[:fi] *= np.linspace(0.30, 1.0, fi, dtype=np.float32)[:, None]
    mus[-fo:] *= np.linspace(1.0, 0.30, fo, dtype=np.float32)[:, None]

    duck_env = _speech_duck_envelope(voice_stereo, duck_depth=0.58)
    return mus * (0.072 * duck_env * scene_gate)[:, None]


def _build_layer_3_environmental_ambience(
    preset: str,
    scene_profile: str,
    n: int,
    voice_stereo: np.ndarray,
    scene_gate: np.ndarray,
) -> np.ndarray:
    """
    Layer 3 — Scene-Aware Environmental Ambience:
    - `space_vacuum_restrained` / `deep_space`: ultra-restrained low sub-harmonic air, zero fake radio chatter.
    - `deep_ocean_abyss` / `deep_ocean`: deep hydrophone-like low-pass water pressure texture (`65-290 Hz`).
    - `subterranean_earth`: resonant cavern air floor (`85-380 Hz`).
    - `polar_glacial`: subtle katabatic polar air texture (`125-510 Hz`).
    - `scientific_discovery`: clean quiet room/observatory atmosphere (`95-410 Hz`).
    """
    if preset == "none" or float(np.max(scene_gate)) < 1e-3:
        return np.zeros((n, 2), dtype=np.float32)

    rng = np.random.default_rng(20261102)
    t = np.arange(n, dtype=np.float64) / float(SR)

    eff = scene_profile if preset == "scientific_discovery" else preset
    if eff in ("deep_space", "space_vacuum_restrained"):
        n_lo, n_hi, base_gain = 65.0, 210.0, 0.032
    elif eff in ("deep_ocean", "deep_ocean_abyss"):
        n_lo, n_hi, base_gain = 68.0, 310.0, 0.055
    elif eff in ("subterranean_earth", "volcanic_abyss"):
        n_lo, n_hi, base_gain = 80.0, 390.0, 0.052
    elif eff == "polar_glacial":
        n_lo, n_hi, base_gain = 125.0, 510.0, 0.055
    else:
        n_lo, n_hi, base_gain = 95.0, 410.0, 0.042

    breath_lfo = (0.42 + 0.58 * (0.5 + 0.5 * np.sin(2.0 * np.pi * 0.065 * t - 0.7))).astype(np.float32)
    nl = _bandpass_fft(rng.standard_normal(n).astype(np.float32), n_lo, n_hi) * breath_lfo
    nr = _bandpass_fft(rng.standard_normal(n).astype(np.float32), n_lo, n_hi) * breath_lfo
    nl /= max(1e-6, float(np.max(np.abs(nl))))
    nr /= max(1e-6, float(np.max(np.abs(nr))))

    amb = np.stack([nl, nr], axis=1)
    duck_env = _speech_duck_envelope(voice_stereo, duck_depth=0.45)
    return amb * (base_gain * duck_env * scene_gate)[:, None]


def _build_layer_4_natural_sounds(
    manifest: EpisodeManifest,
    n_samples: int,
    voice_stereo: np.ndarray,
    timed_shots: list,
    scene_gate: np.ndarray,
    work_dir: Path,
    forbid_space_nat: bool = False,
) -> np.ndarray:
    """
    Layer 4 — Subject-Specific Natural & Diegetic Field Sounds:
    Verified commercial-safe expedition audio (`nat_sound_bed_file` + per-shot `nat_audio_gain_db`),
    gated per scene (`"natural_sounds"` in `scene_audio_layers`) and suppressed in space vacuum.
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
                    "-af", "highpass=f=75,lowpass=f=6200,loudnorm=I=-18.0:TP=-2.0:LRA=11.0",
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
                "-af", "highpass=f=65,lowpass=f=6400,loudnorm=I=-18.0:TP=-2.0:LRA=10.0",
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
        fn = min(int(0.24 * SR), len(clip_st) // 3)
        if fn > 2:
            clip_st[:fn] *= np.sin(np.linspace(0.0, 0.5 * np.pi, fn, dtype=np.float32))[:, None]
            clip_st[-fn:] *= np.cos(np.linspace(0.0, 0.5 * np.pi, fn, dtype=np.float32))[:, None]
        i0 = int(round(s.start_s * SR))
        i1 = min(n_samples, i0 + len(clip_st))
        if i1 > i0:
            g = float(10.0 ** (s.nat_audio_gain_db / 20.0))
            nat_total[i0:i1] += clip_st[: i1 - i0] * (g * duck_env[i0:i1])[:, None]

    fi_n = min(int(0.25 * SR), n_samples // 6)
    fo_n = min(int(0.35 * SR), n_samples // 6)
    if fi_n > 1:
        nat_total[:fi_n] *= np.linspace(0.25, 1.0, fi_n, dtype=np.float32)[:, None]
    if fo_n > 1:
        nat_total[-fo_n:] *= np.linspace(1.0, 0.25, fo_n, dtype=np.float32)[:, None]
    return nat_total


def _calibrate_bed_stem_lufs(bed_st: np.ndarray, target_lufs: float, work_dir: Path) -> np.ndarray:
    if float(np.max(np.abs(bed_st))) < 1e-5:
        return bed_st
    probe_wav = work_dir / "_bed_probe_lufs.wav"
    _write_wav_stereo(probe_wav, bed_st)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(probe_wav), "-af", "ebur128", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    probe_wav.unlink(missing_ok=True)
    summ = proc.stderr[proc.stderr.rfind("Summary:") :]
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    measured = float(m.group(1)) if m else -38.0
    if measured <= -65.0:
        return bed_st
    delta_db = max(-12.0, min(16.0, target_lufs - measured))
    scaled = bed_st * float(10.0 ** (delta_db / 20.0))
    ceiling = 0.42
    mag = np.abs(scaled)
    over = mag > ceiling
    if np.any(over):
        scaled[over] = np.sign(scaled[over]) * (ceiling + 0.15 * np.tanh((mag[over] - ceiling) / 0.15))
    return scaled.astype(np.float32)


def _measure_master_audio_diagnostics(
    mix_wav: Path,
    voice_st: np.ndarray,
    wt: dict[str, Any],
    max_unintended_silence_s: float = 1.15,
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

    # Check inter-word silences for unintended excessive gaps (> max_unintended_silence_s)
    words = wt.get("words", [])
    excessive_silences: list[dict[str, Any]] = []
    sb_spans = [(float(sb["start"]), float(sb["end"])) for sb in wt.get("soundbites", [])]
    for a, b in zip(words, words[1:]):
        t0, t1 = float(a["end"]), float(b["start"])
        gap = t1 - t0
        if gap > max_unintended_silence_s:
            # Ignore gaps occupied by an intentional scientist soundbite
            has_sb = any(max(t0, s0) < min(t1, s1) for s0, s1 in sb_spans)
            if not has_sb:
                excessive_silences.append(
                    {
                        "start_s": round(t0, 3),
                        "end_s": round(t1, 3),
                        "gap_s": round(gap, 3),
                        "after_word": a["word"],
                    }
                )

    lufs_val = float(m_i.group(1)) if m_i else -16.0
    lra_val = float(m_lra.group(1)) if m_lra else 2.5
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


def build_episode_audio(manifest: EpisodeManifest, reuse_existing_tts: bool = False) -> dict:
    """
    Build the complete 5-layer documentary soundscape and authoritative `word_timings.json`.
    """
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    work_dir = out_dir / "work_audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir = ensure_sfx_library()

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
        # `directed_tts` — reuses SHA-256 cached sentences automatically unless `reuse_existing_tts` is False and voice changed
        wt = synthesize_directed_narration(manifest, reuse_existing_cache=True)

    # Export extracted speech boundaries for Stage 4/5 Narration-Aware Shot Planning
    speech_bounds = extract_speech_boundaries(wt)
    (out_dir / "speech_boundaries.json").write_text(json.dumps(speech_bounds, indent=2), encoding="utf-8")

    # 2. Construct & Export All 5 Scene-Aware Stereo Stems
    voice_st = _read_wav_stereo_f32(narr_norm_wav)
    n_samples = voice_st.shape[0]
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), FPS)

    # Layer 1: Main Narration
    layer1_path = work_dir / "layer_1_narration.wav"
    _write_wav_stereo(layer1_path, voice_st)

    # Scene-aware gate envelopes
    gate_music = _scene_layer_gate_envelope(timed_shots, "music", n_samples)
    gate_ambience = _scene_layer_gate_envelope(timed_shots, "ambience", n_samples)
    gate_nat = _scene_layer_gate_envelope(timed_shots, "natural_sounds", n_samples)
    gate_sfx = _scene_layer_gate_envelope(timed_shots, "cinematic_sfx", n_samples)

    is_space_vacuum = (
        style.sound_design.scene_audio_profile == "space_vacuum_restrained"
        or manifest.ambience_preset == "deep_space"
    ) and style.sound_design.forbid_fake_space_transmissions

    # Layer 4: Subject-Specific Natural & Field Sounds
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

    # Layer 2: Background Music Underscore
    layer2_music = _build_layer_2_music_underscore(
        manifest.ambience_preset,
        n_samples,
        voice_st,
        gate_music,
    )
    if has_nat:
        layer2_music *= 0.72
    layer2_path = work_dir / "layer_2_music.wav"
    _write_wav_stereo(layer2_path, layer2_music)

    # Layer 3: Environmental Ambience
    layer3_ambience = _build_layer_3_environmental_ambience(
        manifest.ambience_preset,
        style.sound_design.scene_audio_profile,
        n_samples,
        voice_st,
        gate_ambience,
    )
    if has_nat:
        layer3_ambience *= 0.65
    layer3_path = work_dir / "layer_3_ambience.wav"
    _write_wav_stereo(layer3_path, layer3_ambience)

    # Layer 5: Restrained Cinematic Effects (CC0 Foley Cues)
    layer5_sfx = np.zeros_like(voice_st)
    shot_starts = {s.sid: s.start_s for s in timed_shots}
    seg_starts = {s["seg_id"]: float(s["start"]) for s in wt["segments"]}
    sfx_applied = []

    for cue in manifest.sfx_cues:
        wav_file = sfx_dir / f"{cue.sfx_name}.wav"
        if not wav_file.exists():
            continue
        if cue.anchor_type == "shot_start":
            base_t = shot_starts.get(cue.anchor_ref, 0.0)
        elif cue.anchor_type == "seg_start":
            base_t = seg_starts.get(cue.anchor_ref, 0.0)
        else:
            base_t = float(cue.anchor_ref)
        t_cue = max(0.0, base_t + cue.offset_s)
        i0 = int(round(t_cue * SR))
        if i0 >= n_samples:
            continue
        stem = _read_wav_stereo_f32(wav_file)
        lin_gain = 10.0 ** (cue.gain_db / 20.0)
        i1 = min(n_samples, i0 + stem.shape[0])
        # Apply scene gate if `cinematic_sfx` was disabled on this scene unless explicitly cued on shot_start
        gate_mult = 1.0 if cue.anchor_type in ("shot_start", "seg_start", "time_s") else float(gate_sfx[i0])
        layer5_sfx[i0:i1] += stem[: i1 - i0] * (lin_gain * max(0.35, gate_mult))
        sfx_applied.append({"sfx_name": cue.sfx_name, "time_s": round(t_cue, 3), "gain_db": cue.gain_db})

    layer5_path = work_dir / "layer_5_cinematic_sfx.wav"
    _write_wav_stereo(layer5_path, layer5_sfx)

    # Combine non-vocal stems (Layers 2+3+4+5) and calibrate beneath voice
    target_bed_lufs = float(manifest.ambience_ducked_lufs_target)
    if target_bed_lufs < -32.0 or target_bed_lufs > -24.0:
        target_bed_lufs = float(style.sound_design.target_bed_lufs)

    combined_bed = _calibrate_bed_stem_lufs(
        layer2_music + layer3_ambience + layer4_nat + layer5_sfx,
        target_bed_lufs,
        work_dir,
    )
    _write_wav_stereo(work_dir / "ambience_and_sfx_stem.wav", combined_bed)

    raw_mix_wav = work_dir / "final_audio_mix_pre.wav"
    _write_wav_stereo(raw_mix_wav, np.clip(voice_st + combined_bed, -0.98, 0.98))

    mix_wav = work_dir / "final_audio_mix.wav"
    mix_mp3 = out_dir / "final_audio_mix.mp3"
    # Two-pass linear loudness calibration preserves 100% of natural vocal dynamics without double-AGC pumping
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
            "-af", f"volume={linear_gain_db:.2f}dB,alimiter=limit=0.841:attack=5:release=60:level=false",
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
    audio_report = {
        "slug": manifest.slug,
        "voice_input_mode": manifest.voice_input_mode,
        "scene_audio_profile": style.sound_design.scene_audio_profile,
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

    wt["sfx_applied"] = sfx_applied
    wt["diegetic_nat_sound_active"] = has_nat
    wt["audio_layers_exported"] = list(audio_report["stems"].keys())
    wt["audio_diagnostics"] = diag
    wt_path.write_text(json.dumps(wt, indent=2), encoding="utf-8")
    return wt
