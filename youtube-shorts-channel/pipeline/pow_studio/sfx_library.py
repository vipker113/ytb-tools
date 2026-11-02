#!/usr/bin/env python3
"""
Step 4A: 100% Rights-Owned First-Party CC0 Documentary Micro-SFX Library (`pow_studio.sfx_library`).

Mathematically synthesizes subtle, broadcast-grade documentary Foley & transition stems
in `/Applications/code/science-knowledge/youtube-shorts-channel/assets/sfx_cc0/` with
zero third-party copyright dependencies ($0.00, 100% commercial-cleared).
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SFX_DIR = ROOT / "assets" / "sfx_cc0"
SR = 48000


def _write_stereo_wav(path: Path, stereo: np.ndarray) -> None:
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def _bandpass(sig: np.ndarray, lo_hz: float, hi_hz: float) -> np.ndarray:
    freqs = np.fft.rfftfreq(len(sig), d=1.0 / SR)
    spec = np.fft.rfft(sig)
    hp = 1.0 / np.sqrt(1.0 + (max(lo_hz, 1e-2) / np.maximum(freqs, 1e-2)) ** 6)
    lp = 1.0 / np.sqrt(1.0 + (freqs / hi_hz) ** 6)
    out = np.fft.irfft(spec * hp * lp, n=len(sig)).astype(np.float32)
    m = float(np.max(np.abs(out)))
    return out / m if m > 1e-6 else out


def ensure_sfx_library() -> Path:
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261028)

    # 1. glacial_sub_drop.wav (1.6s deep sub-bass documentary transition, 74 Hz -> 36 Hz)
    p1 = SFX_DIR / "glacial_sub_drop.wav"
    if not p1.exists():
        n = int(1.6 * SR)
        t = np.linspace(0.0, 1.6, n, dtype=np.float64)
        phase = 2.0 * np.pi * (74.0 * t - 11.8 * (t**2))
        env = np.minimum(1.0, t / 0.035) * np.exp(-2.3 * t)
        sig = (0.85 * np.sin(phase) + 0.15 * np.sin(2.0 * phase)) * env
        _write_stereo_wav(p1, np.stack([sig, sig * 0.98], axis=1).astype(np.float32))

    # 2. ice_creak_subtle.wav (1.8s low resonant glacial ice stress texture)
    p2 = SFX_DIR / "ice_creak_subtle.wav"
    if not p2.exists():
        n = int(1.8 * SR)
        t = np.linspace(0.0, 1.8, n, dtype=np.float64)
        env = np.maximum(0.0, np.sin(np.pi * (t / 1.8))) ** 1.6
        mod = np.sin(2.0 * np.pi * 6.5 * t)
        creak_l = (0.55 * np.sin(2.0 * np.pi * (146.8 * t + 0.8 * mod)) + 0.30 * np.sin(2.0 * np.pi * (220.0 * t - 0.5 * mod))) * env
        creak_r = (0.55 * np.sin(2.0 * np.pi * (147.2 * t + 0.7 * mod)) + 0.30 * np.sin(2.0 * np.pi * (219.5 * t - 0.6 * mod))) * env
        tex = _bandpass(rng.standard_normal(n).astype(np.float32), 180.0, 620.0) * env.astype(np.float32) * 0.22
        _write_stereo_wav(p2, np.stack([creak_l + tex, creak_r + tex], axis=1).astype(np.float32) * 0.85)

    # 3. katabatic_wind_gust.wav (2.6s soft polar air swell)
    p3 = SFX_DIR / "katabatic_wind_gust.wav"
    if not p3.exists():
        n = int(2.6 * SR)
        t = np.linspace(0.0, 2.6, n, dtype=np.float32)
        env = (np.sin(np.pi * (t / 2.6)) ** 2.0).astype(np.float32)
        wl = _bandpass(rng.standard_normal(n).astype(np.float32), 150.0, 680.0) * env
        wr = _bandpass(rng.standard_normal(n).astype(np.float32), 150.0, 680.0) * env
        _write_stereo_wav(p3, np.stack([wl, wr], axis=1) * 0.85)

    # 4. locator_ping_soft.wav (1.0s warm muted documentary map-pin harmonic in D5/A5)
    p4 = SFX_DIR / "locator_ping_soft.wav"
    if not p4.exists():
        n = int(1.0 * SR)
        t = np.linspace(0.0, 1.0, n, dtype=np.float64)
        env = np.minimum(1.0, t / 0.012) * np.exp(-5.2 * t)
        sig_l = (0.72 * np.sin(2.0 * np.pi * 587.33 * t) + 0.28 * np.sin(2.0 * np.pi * 880.0 * t)) * env
        sig_r = (0.72 * np.sin(2.0 * np.pi * 587.33 * t + 0.12) + 0.28 * np.sin(2.0 * np.pi * 880.4 * t)) * env
        _write_stereo_wav(p4, np.stack([sig_l, sig_r], axis=1).astype(np.float32) * 0.80)

    # 5. microscope_slide_click.wav (0.30s soft damped optical stage click)
    p5 = SFX_DIR / "microscope_slide_click.wav"
    if not p5.exists():
        n = int(0.30 * SR)
        t = np.linspace(0.0, 0.30, n, dtype=np.float32)
        burst1 = _bandpass(rng.standard_normal(n).astype(np.float32), 500.0, 2200.0) * np.exp(-65.0 * t)
        t2 = np.maximum(0.0, t - 0.045)
        burst2 = _bandpass(rng.standard_normal(n).astype(np.float32), 380.0, 1600.0) * np.exp(-55.0 * t2) * (t >= 0.045)
        click = np.clip((burst1 * 0.7 + burst2 * 0.5), -0.95, 0.95)
        _write_stereo_wav(p5, np.stack([click, click * 0.96], axis=1).astype(np.float32))

    # 6. paper_data_reveal.wav (0.95s subtle documentary research card transition)
    p6 = SFX_DIR / "paper_data_reveal.wav"
    if not p6.exists():
        n = int(0.95 * SR)
        t = np.linspace(0.0, 0.95, n, dtype=np.float32)
        env = np.maximum(0.0, np.sin(np.pi * (t / 0.95))) ** 1.8
        air = _bandpass(rng.standard_normal(n).astype(np.float32), 240.0, 950.0) * env * 0.38
        tone = (0.45 * np.sin(2.0 * np.pi * 293.66 * t) + 0.30 * np.sin(2.0 * np.pi * 440.0 * t)) * env * 0.55
        out = np.clip(air + tone, -0.95, 0.95)
        _write_stereo_wav(p6, np.stack([out, out], axis=1).astype(np.float32))

    # 7. sonar_ping_deep.wav (1.45s warm muted deep-submersible acoustic altimeter ping + underwater tail)
    p7 = SFX_DIR / "sonar_ping_deep.wav"
    if not p7.exists():
        n = int(1.45 * SR)
        t = np.linspace(0.0, 1.45, n, dtype=np.float64)
        env_main = np.minimum(1.0, t / 0.010) * np.exp(-5.8 * t)
        t_echo = np.maximum(0.0, t - 0.28)
        env_echo = np.minimum(1.0, t_echo / 0.025) * np.exp(-3.4 * t_echo) * (t >= 0.28)
        ping_l = 0.72 * np.sin(2.0 * np.pi * 987.77 * t) * env_main + 0.24 * np.sin(2.0 * np.pi * 985.5 * t_echo) * env_echo
        ping_r = 0.72 * np.sin(2.0 * np.pi * 987.77 * t + 0.14) * env_main + 0.24 * np.sin(2.0 * np.pi * 986.2 * t_echo + 0.35) * env_echo
        _write_stereo_wav(p7, np.stack([ping_l, ping_r], axis=1).astype(np.float32) * 0.78)

    # 8. hydrophone_current_swell.wav (2.4s deep underwater hydrophone current & pressure swell)
    p8 = SFX_DIR / "hydrophone_current_swell.wav"
    if not p8.exists():
        n = int(2.4 * SR)
        t = np.linspace(0.0, 2.4, n, dtype=np.float32)
        env = (np.maximum(0.0, np.sin(np.pi * (t / 2.4))) ** 1.9).astype(np.float32)
        hl = _bandpass(rng.standard_normal(n).astype(np.float32), 68.0, 320.0) * env
        hr = _bandpass(rng.standard_normal(n).astype(np.float32), 68.0, 320.0) * env
        sub = (0.35 * np.sin(2.0 * np.pi * 55.0 * t)).astype(np.float32) * env
        _write_stereo_wav(p8, np.clip(np.stack([0.72 * hl + sub, 0.72 * hr + sub], axis=1) * 0.85, -0.95, 0.95))

    # 9. fumarole_gas_jet.wav (2.2s pressurized 600C volcanic fumarole gas vent hiss & low rumble)
    p9 = SFX_DIR / "fumarole_gas_jet.wav"
    if not p9.exists():
        n = int(2.2 * SR)
        t = np.linspace(0.0, 2.2, n, dtype=np.float32)
        env = (np.minimum(1.0, t / 0.14) * np.exp(-1.05 * np.maximum(0.0, t - 0.25))).astype(np.float32)
        jet_l = _bandpass(rng.standard_normal(n).astype(np.float32), 650.0, 3800.0) * env * 0.62
        jet_r = _bandpass(rng.standard_normal(n).astype(np.float32), 620.0, 3600.0) * env * 0.62
        roar = _bandpass(rng.standard_normal(n).astype(np.float32), 75.0, 290.0) * env * 0.55
        _write_stereo_wav(p9, np.clip(np.stack([jet_l + roar, jet_r + roar], axis=1) * 0.85, -0.95, 0.95))

    # 10. boiling_acid_brine.wav (2.4s viscous hydrothermal acid cauldron bubbling texture)
    p10 = SFX_DIR / "boiling_acid_brine.wav"
    if not p10.exists():
        n = int(2.4 * SR)
        t = np.linspace(0.0, 2.4, n, dtype=np.float32)
        bed_env = (np.maximum(0.0, np.sin(np.pi * (t / 2.4))) ** 1.4).astype(np.float32)
        bub_l = _bandpass(rng.standard_normal(n).astype(np.float32), 180.0, 920.0) * bed_env * 0.42
        bub_r = _bandpass(rng.standard_normal(n).astype(np.float32), 180.0, 920.0) * bed_env * 0.42
        for bt, bf in ((0.22, 240.0), (0.58, 310.0), (0.96, 195.0), (1.38, 275.0), (1.79, 225.0)):
            dt = np.maximum(0.0, t - bt)
            b_env = (dt / 0.015) * np.exp(-16.0 * dt) * (t >= bt)
            sweep = np.sin(2.0 * np.pi * (bf * dt + 420.0 * (dt**2))).astype(np.float32) * b_env.astype(np.float32)
            bub_l += 0.36 * sweep
            bub_r += 0.34 * sweep
        _write_stereo_wav(p10, np.clip(np.stack([bub_l, bub_r], axis=1) * 0.85, -0.95, 0.95))

    # 11. subterranean_gate_boom.wav (2.0s deep -300m rock cavern acoustic boom & metallic echo)
    p11 = SFX_DIR / "subterranean_gate_boom.wav"
    if not p11.exists():
        n = int(2.0 * SR)
        t = np.linspace(0.0, 2.0, n, dtype=np.float64)
        env = np.minimum(1.0, t / 0.022) * np.exp(-2.1 * t)
        boom = (0.72 * np.sin(2.0 * np.pi * (62.0 * t - 8.5 * t**2)) + 0.24 * np.sin(2.0 * np.pi * 184.0 * t) * np.exp(-4.8 * t)) * env
        cav_l = _bandpass(rng.standard_normal(n).astype(np.float32), 95.0, 520.0) * np.exp(-2.4 * t).astype(np.float32) * 0.32
        cav_r = _bandpass(rng.standard_normal(n).astype(np.float32), 95.0, 520.0) * np.exp(-2.3 * t).astype(np.float32) * 0.32
        _write_stereo_wav(p11, np.clip(np.stack([boom + cav_l, boom * 0.97 + cav_r], axis=1).astype(np.float32) * 0.88, -0.95, 0.95))

    # 12. cavern_heartbeat_pulse.wav (2.1s visceral twin physiological sub-pulse for 58C lung condensation)
    p12 = SFX_DIR / "cavern_heartbeat_pulse.wav"
    if not p12.exists():
        n = int(2.1 * SR)
        t = np.linspace(0.0, 2.1, n, dtype=np.float64)
        sig = np.zeros(n, dtype=np.float64)
        for t0, amp in ((0.06, 0.85), (0.34, 0.62), (1.08, 0.82), (1.36, 0.58)):
            dt = np.maximum(0.0, t - t0)
            be = np.minimum(1.0, dt / 0.018) * np.exp(-11.5 * dt) * (t >= t0)
            sig += amp * np.sin(2.0 * np.pi * (54.0 * dt - 18.0 * dt**2)) * be
        _write_stereo_wav(p12, np.clip(np.stack([sig, sig], axis=1).astype(np.float32) * 0.88, -0.95, 0.95))

    # 13. cave_flood_rush.wav (2.5s deep subterranean groundwater surge)
    p13 = SFX_DIR / "cave_flood_rush.wav"
    if not p13.exists():
        n = int(2.5 * SR)
        t = np.linspace(0.0, 2.5, n, dtype=np.float32)
        env = (np.maximum(0.0, np.sin(np.pi * (t / 2.5))) ** 1.5).astype(np.float32)
        wl = _bandpass(rng.standard_normal(n).astype(np.float32), 110.0, 1450.0) * env * 0.65
        wr = _bandpass(rng.standard_normal(n).astype(np.float32), 110.0, 1450.0) * env * 0.65
        sub = (0.30 * np.sin(2.0 * np.pi * 49.0 * t)).astype(np.float32) * env
        _write_stereo_wav(p13, np.clip(np.stack([wl + sub, wr + sub], axis=1) * 0.85, -0.95, 0.95))

    # 14. chapter_whoosh_soft.wav (0.75s sleek cinema chapter-stamp air transient)
    p14 = SFX_DIR / "chapter_whoosh_soft.wav"
    if not p14.exists():
        n = int(0.75 * SR)
        t = np.linspace(0.0, 0.75, n, dtype=np.float32)
        env = (np.maximum(0.0, np.sin(np.pi * (t / 0.75))) ** 2.2).astype(np.float32)
        al = _bandpass(rng.standard_normal(n).astype(np.float32), 260.0, 1650.0) * env * 0.55
        ar = _bandpass(rng.standard_normal(n).astype(np.float32), 280.0, 1750.0) * env * 0.55
        chime = (0.28 * np.sin(2.0 * np.pi * 220.0 * t) * np.exp(-4.5 * t)).astype(np.float32)
        _write_stereo_wav(p14, np.clip(np.stack([al + chime, ar + chime], axis=1) * 0.82, -0.95, 0.95))

    lic_md = SFX_DIR / "LICENSE_CC0.md"
    if not lic_md.exists():
        lic_md.write_text(
            "# First-Party Procedural Foley & Micro-SFX Library (`CC0 1.0 Public Domain Dedication`)\n\n"
            "All `.wav` stems in this folder are 100% original mathematical waveforms synthesized locally\n"
            "by `pipeline/pow_studio/sfx_library.py` using NumPy harmonic & filtered-noise equations.\n"
            "Zero external samples or third-party recordings were used. Cleared unconditionally for monetized distribution.\n",
            encoding="utf-8",
        )
    return SFX_DIR
