#!/usr/bin/env python3
"""
Part 9 (Section 12): Verified Commercial-Safe Audio Asset Registry & Sourcing (`pow_studio.audio_registry` v7.0).

Maintains a persistent, non-destructive reusable audio asset registry at
`assets/audio_library/audio_asset_registry.json` and `AUDIO_ASSET_REGISTRY.md`
recording all 11 required metadata fields for every local, first-party CC0,
and verified Public Domain / CC0 / CC BY external recording:
  1. Asset name (`asset_name`)
  2. Source URL (`source_url`)
  3. Creator (`creator`)
  4. License (`license`)
  5. Attribution requirements (`attribution_requirements`)
  6. Duration (`duration_s`)
  7. Audio category (`audio_category`)
  8. Tags (`tags`)
  9. Technical characteristics (`technical_characteristics`)
  10. Intended usage (`intended_usage`)
  11. Downloaded file location (`downloaded_file_location`)

Strict Honesty & Non-Destructive Rules:
- Never overwrites original audio files on disk.
- Preserves all rights and licensing records even when an audio asset is NOT used in a final edit.
- Never presents procedurally synthesized textures as authentic wildlife/field recordings
  (`origin_type` explicitly distinguishes `authentic_field_or_archival_recording` vs
  `first_party_acoustic_synthesis`).
- Flags decorative legacy transition whooshes/booms (`allow_in_v7_creative_edit=False`) while
  keeping their files and registry records intact for `legacy_v6_fallback`.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any, Optional

import numpy as np
from pydantic import BaseModel, Field

from .rights_gate import validate_license_string
from .sfx_library import ensure_sfx_library

CHANNEL_ROOT = Path(__file__).resolve().parents[2]
AUDIO_LIB_DIR = CHANNEL_ROOT / "assets" / "audio_library"
MUSIC_BEDS_DIR = AUDIO_LIB_DIR / "music_beds"
AMBIENCE_BEDS_DIR = AUDIO_LIB_DIR / "ambience_beds"
FIELD_RECORDINGS_DIR = AUDIO_LIB_DIR / "field_recordings"
REGISTRY_JSON_PATH = AUDIO_LIB_DIR / "audio_asset_registry.json"
REGISTRY_MD_PATH = AUDIO_LIB_DIR / "AUDIO_ASSET_REGISTRY.md"

SR = 48000

DEPRECATED_DECORATIVE_SFX = {
    "chapter_whoosh_soft",
    "subterranean_gate_boom",
    "locator_ping_soft",
    "paper_data_reveal",
}


class AudioRegistryEntry(BaseModel):
    asset_name: str
    source_url: str
    creator: str
    license: str
    attribution_requirements: str
    duration_s: float
    audio_category: str = Field(
        description="'music' | 'music_accent' | 'ambience' | 'authentic_field_recording' | 'sfx' | 'deprecated_transition_sfx'"
    )
    tags: list[str] = Field(default_factory=list)
    technical_characteristics: dict[str, Any] = Field(default_factory=dict)
    intended_usage: str
    downloaded_file_location: str
    origin_type: str = Field(
        default="first_party_acoustic_synthesis",
        description="'authentic_field_or_archival_recording' | 'first_party_acoustic_synthesis'",
    )
    monetization_safe: bool = True
    allow_in_v7_creative_edit: bool = True


def _write_wav_stereo_non_destructive(path: Path, stereo: np.ndarray) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def _measure_wav_tech(path: Path, extra: Optional[dict[str, Any]] = None) -> tuple[float, dict[str, Any]]:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        sr = wf.getframerate()
        nf = wf.getnframes()
        raw = wf.readframes(nf)
    dur = round(nf / float(max(1, sr)), 3)
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    peak = float(np.max(np.abs(arr))) if len(arr) else 0.0
    rms = float(np.sqrt(np.mean(arr * arr))) if len(arr) else 0.0
    tech: dict[str, Any] = {
        "sample_rate_hz": sr,
        "channels": ch,
        "peak_dbfs": round(20.0 * np.log10(max(1e-6, peak)), 2),
        "rms_dbfs": round(20.0 * np.log10(max(1e-6, rms)), 2),
    }
    if extra:
        tech.update(extra)
    return dur, tech


def _lowpass(sig: np.ndarray, cutoff_hz: float) -> np.ndarray:
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / SR)
    spec = np.fft.rfft(sig)
    gain = 1.0 / np.sqrt(1.0 + (freqs / cutoff_hz) ** 6)
    return np.fft.irfft(spec * gain, n=len(sig)).astype(np.float32)


def _carve_vocal_pocket(sig: np.ndarray, lo_hz: float = 320.0, hi_hz: float = 2850.0, depth_db: float = -7.5) -> np.ndarray:
    """Attenuate the 320-2850 Hz speech intelligibility band so music never masks narration."""
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / SR)
    spec = np.fft.rfft(sig)
    center = np.sqrt(lo_hz * hi_hz)
    width = (hi_hz - lo_hz) * 0.55
    bell = np.exp(-0.5 * ((freqs - center) / max(1.0, width)) ** 2)
    min_gain = 10.0 ** (depth_db / 20.0)
    gain = 1.0 - (1.0 - min_gain) * bell
    return np.fft.irfft(spec * gain, n=len(sig)).astype(np.float32)


def _ensure_first_party_music_beds() -> list[dict[str, Any]]:
    """
    Synthesize distinct, non-repetitive, vocal-pocket-safe CC0 documentary music beds
    (only if not already present on disk). Each bed has a genuinely distinct harmonic
    vocabulary, register, rhythm, and emotional character.
    """
    MUSIC_BEDS_DIR.mkdir(parents=True, exist_ok=True)
    dur_s = 28.0
    n = int(dur_s * SR)
    t = np.arange(n, dtype=np.float64) / float(SR)

    specs: list[dict[str, Any]] = []

    # 1. Minimal Glass Pulse — Scientific Explanation / Minimal Documentary
    p_min = MUSIC_BEDS_DIR / "mus_minimal_glass_pulse_cc0.wav"
    if not p_min.exists():
        notes = [220.0, 329.63, 293.66, 246.94]  # A3, E4, D4, B3 sparse soft harmonic notes
        L = np.zeros(n, dtype=np.float64)
        R = np.zeros(n, dtype=np.float64)
        for idx in range(8):
            t0 = idx * 3.5
            f0 = notes[idx % len(notes)]
            mask = t >= t0
            dt = np.maximum(0.0, t - t0)
            env = mask * (1.0 - np.exp(-dt * 12.0)) * np.exp(-dt * 0.85)
            L += 0.28 * env * np.sin(2.0 * np.pi * f0 * dt) + 0.06 * env * np.sin(2.0 * np.pi * (f0 * 2.0) * dt)
            R += 0.28 * env * np.sin(2.0 * np.pi * (f0 * 1.0008) * dt + 0.2) + 0.06 * env * np.sin(2.0 * np.pi * (f0 * 2.0) * dt)
        L += 0.14 * np.sin(2.0 * np.pi * 110.0 * t) * (0.65 + 0.35 * np.sin(2.0 * np.pi * 0.04 * t))
        R += 0.14 * np.sin(2.0 * np.pi * 110.05 * t + 0.15) * (0.65 + 0.35 * np.sin(2.0 * np.pi * 0.04 * t))
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 920.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 920.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.42
        _write_wav_stereo_non_destructive(p_min, st)
    specs.append(
        {
            "asset_name": "mus_minimal_glass_pulse_cc0",
            "path": p_min,
            "audio_category": "music",
            "tags": ["minimal", "scientific_explanation", "calm", "sparse", "high_intelligibility"],
            "tempo_bpm": 54,
            "energy": "very_low",
            "instrumentation": "Sparse damped glass-harmonic intervals over soft A2 pedal",
            "frequency_band_hz": "110-920 Hz (320-2850 Hz vocal pocket attenuated)",
            "intended_usage": "Scientific explanation and minimal documentary context where speech clarity is paramount",
        }
    )

    # 2. Warm Cello Exploration — Immersive Exploration / Establishing Context
    p_cel = MUSIC_BEDS_DIR / "mus_warm_cello_exploration_cc0.wav"
    if not p_cel.exists():
        # Warm bowed fifth progression: D2-A2 -> G2-D3 -> E2-B2 -> A1-E2
        chords = [(73.42, 110.0), (98.0, 146.83), (82.41, 123.47), (55.0, 82.41)]
        L = np.zeros(n, dtype=np.float64)
        R = np.zeros(n, dtype=np.float64)
        seg_len = dur_s / len(chords)
        for ci, (f1, f2) in enumerate(chords):
            c_center = (ci + 0.5) * seg_len
            win = np.exp(-0.5 * ((t - c_center) / (seg_len * 0.52)) ** 2)
            vib = 0.0022 * np.sin(2.0 * np.pi * 4.4 * t)
            cello1 = np.sin(2.0 * np.pi * f1 * (1.0 + vib) * t) + 0.35 * np.sin(4.0 * np.pi * f1 * t) + 0.14 * np.sin(6.0 * np.pi * f1 * t)
            cello2 = np.sin(2.0 * np.pi * f2 * (1.0 - vib) * t + 0.3) + 0.25 * np.sin(4.0 * np.pi * f2 * t)
            L += win * (0.36 * cello1 + 0.24 * cello2)
            R += win * (0.34 * cello1 + 0.26 * np.roll(cello2, 24))
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 640.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 640.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.46
        _write_wav_stereo_non_destructive(p_cel, st)
    specs.append(
        {
            "asset_name": "mus_warm_cello_exploration_cc0",
            "path": p_cel,
            "audio_category": "music",
            "tags": ["exploration", "establishing_context", "warm", "cello", "documentary"],
            "tempo_bpm": 60,
            "energy": "low_moderate",
            "instrumentation": "Warm bowed low-string open fifth progression (D2-G2-E2-A1)",
            "frequency_band_hz": "55-640 Hz (vocal pocket carved)",
            "intended_usage": "Establishing geography, fieldwork exploration, and steady documentary storytelling",
        }
    )

    # 3. Mysterious Undertow — Opening Hook / Curiosity Gap (Restrained, non-horror)
    p_mys = MUSIC_BEDS_DIR / "mus_mysterious_undertow_cc0.wav"
    if not p_mys.exists():
        # Dorian modal movement (C2 + G2 + D3 gentle shimmer, no harsh dissonance)
        breath = 0.55 + 0.45 * np.sin(2.0 * np.pi * 0.062 * t - 0.5)
        pulse = 0.72 + 0.28 * np.sin(2.0 * np.pi * (52.0 / 60.0 * 0.25) * t)
        L = (
            0.44 * np.sin(2.0 * np.pi * 65.41 * t) * breath
            + 0.22 * np.sin(2.0 * np.pi * 98.00 * t + 0.15) * pulse
            + 0.14 * np.sin(2.0 * np.pi * 146.83 * t) * (1.0 - 0.4 * breath)
        )
        R = (
            0.44 * np.sin(2.0 * np.pi * 65.44 * t + 0.08) * breath
            + 0.22 * np.sin(2.0 * np.pi * 98.04 * t - 0.12) * pulse
            + 0.14 * np.sin(2.0 * np.pi * 146.90 * t + 0.35) * (1.0 - 0.4 * breath)
        )
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 480.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 480.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.44
        _write_wav_stereo_non_destructive(p_mys, st)
    specs.append(
        {
            "asset_name": "mus_mysterious_undertow_cc0",
            "path": p_mys,
            "audio_category": "music",
            "tags": ["mystery", "opening_hook", "curiosity_gap", "restrained_tension", "earth"],
            "tempo_bpm": 52,
            "energy": "low",
            "instrumentation": "Restrained Dorian modal low-register resonance (C2-G2-D3)",
            "frequency_band_hz": "65-480 Hz (below primary vocal formants)",
            "intended_usage": "Opening curiosity hooks and mysterious scientific anomalies without horror clichés",
        }
    )

    # 4. Discovery Ascent — Building Discovery / Escalation -> Payoff
    p_asc = MUSIC_BEDS_DIR / "mus_discovery_ascent_cc0.wav"
    if not p_asc.exists():
        u = np.linspace(0.0, 1.0, n, dtype=np.float64)
        chords = [(73.42, 110.0, 185.0), (87.31, 130.81, 220.0), (98.0, 146.83, 246.94), (110.0, 164.81, 277.18)]
        L = np.zeros(n, dtype=np.float64)
        R = np.zeros(n, dtype=np.float64)
        seg_len = dur_s / len(chords)
        for ci, (f1, f2, f3) in enumerate(chords):
            c_center = (ci + 0.5) * seg_len
            win = np.exp(-0.5 * ((t - c_center) / (seg_len * 0.55)) ** 2)
            bloom = 0.55 + 0.45 * u
            L += win * bloom * (0.38 * np.sin(2.0 * np.pi * f1 * t) + 0.25 * np.sin(2.0 * np.pi * f2 * t) + 0.14 * np.sin(2.0 * np.pi * f3 * t))
            R += win * bloom * (0.38 * np.sin(2.0 * np.pi * f1 * t + 0.1) + 0.25 * np.sin(2.0 * np.pi * f2 * t + 0.25) + 0.14 * np.sin(2.0 * np.pi * (f3 * 1.001) * t))
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 760.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 760.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.48
        _write_wav_stereo_non_destructive(p_asc, st)
    specs.append(
        {
            "asset_name": "mus_discovery_ascent_cc0",
            "path": p_asc,
            "audio_category": "music",
            "tags": ["building_discovery", "escalation", "payoff", "awe", "cinematic_science"],
            "tempo_bpm": 66,
            "energy": "moderate",
            "instrumentation": "Ascending warm major-sixth harmonic progression (D-F-G-A)",
            "frequency_band_hz": "73-760 Hz (vocal pocket carved)",
            "intended_usage": "Building scientific discovery and central mechanism payoff sections",
        }
    )

    # 5. Reflective Piano Settle — Final Explanation / Emotional Reflection
    p_ref = MUSIC_BEDS_DIR / "mus_reflective_piano_settle_cc0.wav"
    if not p_ref.exists():
        notes = [(146.83, 220.0), (130.81, 196.0), (110.0, 164.81), (146.83, 220.0)]
        L = np.zeros(n, dtype=np.float64)
        R = np.zeros(n, dtype=np.float64)
        for idx in range(len(notes)):
            t0 = idx * 6.8 + 0.2
            f1, f2 = notes[idx]
            dt = np.maximum(0.0, t - t0)
            mask = t >= t0
            # Soft felt-hammer attack + warm exponential decay
            env = mask * (1.0 - np.exp(-dt * 18.0)) * np.exp(-dt * 0.42)
            tone_l = 0.34 * np.sin(2.0 * np.pi * f1 * dt) + 0.20 * np.sin(2.0 * np.pi * f2 * dt) + 0.05 * np.sin(4.0 * np.pi * f1 * dt)
            tone_r = 0.34 * np.sin(2.0 * np.pi * (f1 * 1.0005) * dt) + 0.20 * np.sin(2.0 * np.pi * (f2 * 0.9995) * dt + 0.18)
            L += env * tone_l
            R += env * tone_r
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 700.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 700.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.42
        _write_wav_stereo_non_destructive(p_ref, st)
    specs.append(
        {
            "asset_name": "mus_reflective_piano_settle_cc0",
            "path": p_ref,
            "audio_category": "music",
            "tags": ["reflective", "final_explanation", "ending", "soft", "felt_piano"],
            "tempo_bpm": 48,
            "energy": "very_low",
            "instrumentation": "Soft damped felt-piano fifths with long natural decay",
            "frequency_band_hz": "110-700 Hz (vocal pocket carved)",
            "intended_usage": "Final reflection, scientific caveats, and calm documentary conclusions",
        }
    )

    # 6. Deep Abyssal Pedal — Deep Ocean Exploration / Space Discovery
    p_aby = MUSIC_BEDS_DIR / "mus_deep_abyssal_pedal_cc0.wav"
    if not p_aby.exists():
        swell = 0.50 + 0.50 * np.sin(2.0 * np.pi * 0.036 * t - 1.1)
        L = 0.52 * np.sin(2.0 * np.pi * 49.00 * t) * swell + 0.24 * np.sin(2.0 * np.pi * 73.42 * t) + 0.10 * np.sin(2.0 * np.pi * 146.83 * t) * swell
        R = 0.52 * np.sin(2.0 * np.pi * 49.03 * t + 0.12) * swell + 0.24 * np.sin(2.0 * np.pi * 73.46 * t - 0.1) + 0.10 * np.sin(2.0 * np.pi * 146.90 * t + 0.25) * swell
        st = np.stack([_lowpass(L.astype(np.float32), 310.0), _lowpass(R.astype(np.float32), 310.0)], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.45
        _write_wav_stereo_non_destructive(p_aby, st)
    specs.append(
        {
            "asset_name": "mus_deep_abyssal_pedal_cc0",
            "path": p_aby,
            "audio_category": "music",
            "tags": ["deep_ocean", "space", "spacious", "low_frequency", "immersive"],
            "tempo_bpm": 44,
            "energy": "low",
            "instrumentation": "Deep spacious G1-D2 sub-harmonic pedal below speech band",
            "frequency_band_hz": "49-310 Hz (strictly below speech band)",
            "intended_usage": "Deep ocean abyssal trenches and spacious cosmic scale moments",
        }
    )

    # 7. Ancient Modal Drone — Ancient Mystery / Historical Evidence
    p_anc = MUSIC_BEDS_DIR / "mus_ancient_modal_drone_cc0.wav"
    if not p_anc.exists():
        # Open fifth D2 + A2 + gentle modal C3 inflection
        mod = 0.6 + 0.4 * np.sin(2.0 * np.pi * 0.05 * t)
        L = 0.42 * np.sin(2.0 * np.pi * 73.42 * t) + 0.28 * np.sin(2.0 * np.pi * 110.0 * t) * mod + 0.12 * np.sin(2.0 * np.pi * 130.81 * t) * (1.0 - 0.5 * mod)
        R = 0.42 * np.sin(2.0 * np.pi * 73.45 * t + 0.09) + 0.28 * np.sin(2.0 * np.pi * 110.04 * t - 0.14) * mod + 0.12 * np.sin(2.0 * np.pi * 130.88 * t + 0.22) * (1.0 - 0.5 * mod)
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 520.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 520.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.44
        _write_wav_stereo_non_destructive(p_anc, st)
    specs.append(
        {
            "asset_name": "mus_ancient_modal_drone_cc0",
            "path": p_anc,
            "audio_category": "music",
            "tags": ["ancient_mystery", "archaeology", "historical", "evidence", "modal"],
            "tempo_bpm": 56,
            "energy": "low_moderate",
            "instrumentation": "Restrained open-fifth acoustic modal resonance (D2-A2-C3)",
            "frequency_band_hz": "73-520 Hz (vocal pocket carved)",
            "intended_usage": "Ancient geological or archaeological mysteries and evidence-led progression",
        }
    )

    # 8. Controlled Reveal Harmonic Accent (4.2s — subtle harmonic bloom, NOT a trailer boom)
    p_acc = MUSIC_BEDS_DIR / "mus_reveal_harmonic_accent_cc0.wav"
    if not p_acc.exists():
        na = int(4.2 * SR)
        ta = np.arange(na, dtype=np.float64) / float(SR)
        env = (1.0 - np.exp(-ta * 4.5)) * np.exp(-ta * 0.78)
        L = env * (0.42 * np.sin(2.0 * np.pi * 98.0 * ta) + 0.30 * np.sin(2.0 * np.pi * 146.83 * ta) + 0.18 * np.sin(2.0 * np.pi * 220.0 * ta))
        R = env * (0.42 * np.sin(2.0 * np.pi * 98.05 * ta + 0.1) + 0.30 * np.sin(2.0 * np.pi * 146.9 * ta + 0.2) + 0.18 * np.sin(2.0 * np.pi * 220.1 * ta))
        st = np.stack([_carve_vocal_pocket(_lowpass(L.astype(np.float32), 680.0)), _carve_vocal_pocket(_lowpass(R.astype(np.float32), 680.0))], axis=1)
        st = st / max(1e-6, float(np.max(np.abs(st)))) * 0.45
        _write_wav_stereo_non_destructive(p_acc, st)
    specs.append(
        {
            "asset_name": "mus_reveal_harmonic_accent_cc0",
            "path": p_acc,
            "audio_category": "music_accent",
            "tags": ["reveal", "discovery", "subtle_accent", "non_impact"],
            "tempo_bpm": 0,
            "energy": "controlled_accent",
            "instrumentation": "Warm 4.2s G2-D3-A3 harmonic swell (replaces loud trailer impacts)",
            "frequency_band_hz": "98-680 Hz",
            "intended_usage": "Subtle musical accent reinforcing a major scientific reveal without masking speech",
        }
    )

    return specs


def harvest_verified_wikimedia_audio(
    query: str,
    max_results: int = 3,
    download: bool = True,
) -> list[AudioRegistryEntry]:
    """
    Search Wikimedia Commons ($0 public API) for genuine commercial-safe (Public Domain / CC0 / CC BY)
    environmental or acoustic audio recordings, verify exact license & attribution metadata,
    optionally download without overwriting existing files, and register them.
    """
    FIELD_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:audio {query}",
            "gsrnamespace": "6",
            "gsrlimit": str(max(1, min(10, max_results * 2))),
            "prop": "imageinfo",
            "iiprop": "url|size|mime|extmetadata",
            "format": "json",
        }
    )
    url = f"https://commons.wikimedia.org/w/api.php?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "ProofOfWonderDocumentaryStudio/7.0 (https://github.com/vipker113)"})
    entries: list[AudioRegistryEntry] = []
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return entries

    pages = (payload.get("query") or {}).get("pages") or {}
    for _, page in pages.items():
        infos = page.get("imageinfo") or []
        if not infos:
            continue
        ii = infos[0]
        ext = ii.get("extmetadata") or {}
        lic_short = str((ext.get("LicenseShortName") or {}).get("value", "")).strip()
        usage_terms = str((ext.get("UsageTerms") or {}).get("value", "")).strip()
        lic_str = lic_short or usage_terms
        try:
            validate_license_string(lic_str, page.get("title", "commons_audio"))
        except Exception:
            continue

        direct_url = str(ii.get("url", ""))
        desc_url = str(ii.get("descriptionurl", ""))
        if not direct_url or int(ii.get("size", 0)) > 18 * 1024 * 1024:
            continue

        artist_raw = str((ext.get("Artist") or {}).get("value", "Wikimedia Commons Contributor"))
        import re as _re

        creator = _re.sub(r"<[^>]+>", "", artist_raw).strip() or "Wikimedia Commons Contributor"
        attr_req_flag = str((ext.get("AttributionRequired") or {}).get("value", "true")).lower()
        attr_text = (
            "No attribution legally required (Public Domain / CC0); archived in registry."
            if attr_req_flag == "false" or "cc0" in lic_str.lower() or "public domain" in lic_str.lower()
            else f"Credit in off-screen source register / video description: {creator} ({lic_str}, {desc_url})"
        )

        raw_name = Path(urllib.parse.unquote(direct_url)).name
        safe_stem = _re.sub(r"[^A-Za-z0-9_.-]+", "_", raw_name)
        dst_path = FIELD_RECORDINGS_DIR / safe_stem

        if download and not dst_path.exists():
            try:
                dl_req = urllib.request.Request(
                    direct_url,
                    headers={"User-Agent": "ProofOfWonderDocumentaryStudio/7.0 (https://github.com/vipker113)"},
                )
                with urllib.request.urlopen(dl_req, timeout=20) as dl_resp:
                    dst_path.write_bytes(dl_resp.read())
            except Exception:
                continue

        dur_s = 0.0
        tech: dict[str, Any] = {"mime": ii.get("mime", "audio/ogg"), "bytes": int(ii.get("size", 0))}
        if dst_path.exists():
            import subprocess as _sp

            pr = _sp.run(
                ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(dst_path)],
                capture_output=True,
                text=True,
            )
            if pr.returncode == 0:
                pinfo = json.loads(pr.stdout)
                dur_s = round(float((pinfo.get("format") or {}).get("duration", 0.0) or 0.0), 3)
                astream = next((s for s in pinfo.get("streams", []) if s.get("codec_type") == "audio"), {})
                tech["sample_rate_hz"] = int(astream.get("sample_rate", 48000) or 48000)
                tech["channels"] = int(astream.get("channels", 2) or 2)
                tech["codec"] = astream.get("codec_name", "unknown")

        entry = AudioRegistryEntry(
            asset_name=Path(safe_stem).stem,
            source_url=desc_url or direct_url,
            creator=creator,
            license=lic_str,
            attribution_requirements=attr_text,
            duration_s=dur_s,
            audio_category="authentic_field_recording",
            tags=[t for t in _re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2],
            technical_characteristics=tech,
            intended_usage=f"Verified authentic archival/field audio matching '{query}'",
            downloaded_file_location=str(dst_path.relative_to(CHANNEL_ROOT)).replace("\\", "/") if dst_path.exists() else direct_url,
            origin_type="authentic_field_or_archival_recording",
            monetization_safe=True,
            allow_in_v7_creative_edit=True,
        )
        entries.append(entry)
        if len(entries) >= max_results:
            break

    if entries:
        register_audio_entries(entries)
    return entries


def ensure_audio_asset_registry() -> dict[str, AudioRegistryEntry]:
    """
    Initialize or update the persistent commercial-safe Audio Asset Registry without
    overwriting or deleting any previously registered entries or audio files.
    """
    AUDIO_LIB_DIR.mkdir(parents=True, exist_ok=True)
    existing: dict[str, AudioRegistryEntry] = {}
    if REGISTRY_JSON_PATH.exists():
        try:
            raw = json.loads(REGISTRY_JSON_PATH.read_text(encoding="utf-8"))
            for item in raw.get("assets", []):
                e = AudioRegistryEntry.model_validate(item)
                existing[e.asset_name] = e
        except Exception:
            pass

    # 1. Register all first-party CC0 acoustic music beds
    for m in _ensure_first_party_music_beds():
        dur_s, tech = _measure_wav_tech(
            m["path"],
            extra={
                "tempo_bpm": m["tempo_bpm"],
                "energy": m["energy"],
                "instrumentation": m["instrumentation"],
                "frequency_band_hz": m["frequency_band_hz"],
            },
        )
        name = m["asset_name"]
        if name not in existing:
            existing[name] = AudioRegistryEntry(
                asset_name=name,
                source_url="first-party://pow_studio/audio_registry.py",
                creator="Proof of Wonder Studio (First-Party Acoustic Synthesis)",
                license="CC0 1.0 Public Domain Dedication (First-Party Original)",
                attribution_requirements="None required (100% first-party original synthesis)",
                duration_s=dur_s,
                audio_category=m["audio_category"],
                tags=m["tags"],
                technical_characteristics=tech,
                intended_usage=m["intended_usage"],
                downloaded_file_location=str(m["path"].relative_to(CHANNEL_ROOT)).replace("\\", "/"),
                origin_type="first_party_acoustic_synthesis",
                monetization_safe=True,
                allow_in_v7_creative_edit=True,
            )

    # 2. Register existing local `assets/sfx_cc0/*.wav` stems (honestly classified, preserving deprecated ones)
    sfx_dir = ensure_sfx_library()
    sfx_descriptions: dict[str, tuple[list[str], str]] = {
        "glacial_sub_drop": (["glacier", "ice", "subglacial", "reveal_low"], "Subtle low-frequency ice-mass resonance when glacier fracture or subglacial cavity is visible"),
        "ice_creak_subtle": (["ice", "glacier", "crevasse", "polar"], "Subtle structural ice stress creak only when glacier/ice surface is directly shown on screen"),
        "katabatic_wind_gust": (["wind", "polar", "aerial", "ridge", "island"], "Restrained filtered air movement for exposed polar or high-altitude aerial geography"),
        "hydrophone_current_swell": (["ocean", "underwater", "current", "brine", "deep_sea"], "Restrained low-pass underwater current swell for submerged ocean/ROV footage"),
        "sonar_ping_deep": (["sonar", "bathymetry", "rov", "mapping", "instrument"], "Acoustic mapping ping ONLY when bathymetric sonar/ROV instrument operation is narrated and shown"),
        "microscope_slide_click": (["microscope", "laboratory", "instrument", "sample"], "Subtle mechanical detent ONLY when laboratory/microscopy equipment handling is visible"),
        "boiling_acid_brine": (["hydrothermal", "geothermal", "vent", "acid_pool"], "Low-level thermal bubbling texture ONLY when active geothermal vents/pools are visible"),
        "fumarole_gas_jet": (["volcano", "fumarole", "steam", "vent"], "Restrained volcanic gas vent hiss ONLY when active fumarole plume is on screen"),
        "cave_flood_rush": (["cave", "water", "underground_river", "karst"], "Subterranean water flow texture ONLY when flowing cave water is visible"),
        "cavern_heartbeat_pulse": (["subterranean", "deep_earth", "pulse"], "Ultra-subtle deep acoustic pulse for rare geological reveals"),
        "chapter_whoosh_soft": (["deprecated", "transition", "whoosh"], "LEGACY v6 ONLY: Decorative transition whoosh — preserved for fallback, disallowed in Studio v7"),
        "subterranean_gate_boom": (["deprecated", "impact", "boom"], "LEGACY v6 ONLY: Decorative low boom — preserved for fallback, disallowed in Studio v7"),
        "locator_ping_soft": (["deprecated", "ui_ping", "map"], "LEGACY v6 ONLY: Decorative UI map ping — preserved for fallback, disallowed in Studio v7"),
        "paper_data_reveal": (["deprecated", "ui_click", "data"], "LEGACY v6 ONLY: Decorative card sound — preserved for fallback, disallowed in Studio v7"),
    }
    for wav_p in sorted(sfx_dir.glob("*.wav")):
        stem = wav_p.stem
        if stem in existing:
            continue
        dur_s, tech = _measure_wav_tech(wav_p)
        tags, usage = sfx_descriptions.get(stem, (["sfx"], "First-party CC0 synthesized sound stem"))
        is_deprecated = stem in DEPRECATED_DECORATIVE_SFX
        existing[stem] = AudioRegistryEntry(
            asset_name=stem,
            source_url="first-party://pow_studio/sfx_library.py",
            creator="Proof of Wonder Studio (First-Party Procedural Synthesis — NOT authentic field audio)",
            license="CC0 1.0 Public Domain Dedication (First-Party Original)",
            attribution_requirements="None required; must NOT be misrepresented as authentic wildlife/field recording",
            duration_s=dur_s,
            audio_category="deprecated_transition_sfx" if is_deprecated else "sfx",
            tags=tags,
            technical_characteristics=tech,
            intended_usage=usage,
            downloaded_file_location=str(wav_p.relative_to(CHANNEL_ROOT)).replace("\\", "/"),
            origin_type="first_party_acoustic_synthesis",
            monetization_safe=True,
            allow_in_v7_creative_edit=not is_deprecated,
        )

    # 3. Register authentic field-audio tracks present inside local raw expedition footage
    nansen_mp4 = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "nasa_m12666_nansen_scientists_ice.mp4"
    if nansen_mp4.exists() and "nasa_m12666_antarctic_wind_field_audio" not in existing:
        existing["nasa_m12666_antarctic_wind_field_audio"] = AudioRegistryEntry(
            asset_name="nasa_m12666_antarctic_wind_field_audio",
            source_url="https://svs.gsfc.nasa.gov/12666",
            creator="NASA Goddard Space Flight Center / Operation IceBridge Field Team",
            license="Public Domain (17 U.S.C. § 105 US Government Work)",
            attribution_requirements="Credit NASA Goddard Space Flight Center in off-screen source register",
            duration_s=37.0,
            audio_category="authentic_field_recording",
            tags=["antarctica", "wind", "ice", "fieldwork", "authentic", "polar"],
            technical_characteristics={"sample_rate_hz": 48000, "channels": 2, "slice_s": [1.0, 38.0]},
            intended_usage="Genuine Antarctic ice-sheet field wind and expedition atmosphere",
            downloaded_file_location=str(nansen_mp4.relative_to(CHANNEL_ROOT)).replace("\\", "/"),
            origin_type="authentic_field_or_archival_recording",
            monetization_safe=True,
            allow_in_v7_creative_edit=True,
        )

    _save_registry(existing)
    return existing


def register_audio_entries(entries: list[AudioRegistryEntry]) -> dict[str, AudioRegistryEntry]:
    reg = ensure_audio_asset_registry()
    for e in entries:
        validate_license_string(e.license, e.asset_name)
        reg[e.asset_name] = e
    _save_registry(reg)
    return reg


def _save_registry(reg: dict[str, AudioRegistryEntry]) -> None:
    AUDIO_LIB_DIR.mkdir(parents=True, exist_ok=True)
    ordered = [reg[k].model_dump() for k in sorted(reg.keys())]
    REGISTRY_JSON_PATH.write_text(
        json.dumps(
            {
                "registry_version": "7.0",
                "budget_usd": 0.0,
                "asset_count": len(ordered),
                "assets": ordered,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        "# Proof of Wonder — Reusable Commercial-Safe Audio Asset Registry (`v7.0`)",
        "",
        "All assets below are verified for monetized YouTube distribution (`$0` cost). Unused assets remain permanently cataloged so rights and provenance are never lost.",
        "",
        "| Asset Name | Category | Origin | License | Duration | Creator | File Location | V7 Eligible | Intended Usage |",
        "|---|---|---|---|---:|---|---|---|---|",
    ]
    for item in ordered:
        lines.append(
            f"| `{item['asset_name']}` | `{item['audio_category']}` | `{item['origin_type']}` | "
            f"{item['license']} | {item['duration_s']:.2f}s | {item['creator']} | "
            f"`{item['downloaded_file_location']}` | `{'YES' if item['allow_in_v7_creative_edit'] else 'LEGACY_ONLY'}` | "
            f"{item['intended_usage']} |"
        )
    REGISTRY_MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def resolve_registered_audio_path(asset_name: str) -> Optional[Path]:
    reg = ensure_audio_asset_registry()
    entry = reg.get(asset_name)
    if not entry:
        return None
    p = CHANNEL_ROOT / entry.downloaded_file_location
    if p.exists():
        return p
    direct = Path(entry.downloaded_file_location)
    return direct if direct.exists() else None
