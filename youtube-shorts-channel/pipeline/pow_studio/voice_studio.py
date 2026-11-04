#!/usr/bin/env python3
"""
Stage 3: Custom Voice Studio, Pre-Generation Intonation Engine, Uploaded Narration
Aligner & Reference Voice Profiler (`pow_studio.voice_studio` v6.0).

Implements Part 4 (Sections 5.1-5.5) and Part 12 (Section 16) of the Proof of Wonder
Next-Generation Documentary Studio under a strict `$0` local budget:

1. Two Voice Input Modes + Directed TTS:
   - **Mode A (`uploaded_narration`)**: Validates user-uploaded complete narration audio,
     detects speech/silence & sentence pauses, applies optional gentle noise reduction and
     dynamics-preserving loudness normalization (`LRA=11`), transcribes & word-aligns via
     local `faster-whisper`, and locks the uploaded recording as the authoritative timing master.
   - **Mode B (`voice_reference`)**: Enforces explicit `voice_owner_consent: true`, measures
     the speaker's acoustic cadence/pitch/dynamics (`WPM`, `F0 Hz`, `pause ms`, `LRA`),
     exports a calibrated `VoiceDirectionProfile`, and checks optional local zero-shot
     cloning endpoints (transparently reporting when neural cloning weights are absent so
     voice cloning is never faked).
   - **Directed TTS (`directed_tts`)**: Synthesizes sentence-by-sentence narration with
     bounded human-natural prosody, SHA-256 sentence caching for selective re-rendering,
     matched speech-active RMS across sentences, and continuous studio room-tone continuity.

2. Reusable `VoiceDirectionProfile` & 7 Presets (`config/voice_profiles/*.yaml`):
   - `cinematic_documentary`, `curious_explorer`, `scientific_authority`,
     `mysterious_discovery`, `dramatic_reveal`, `calm_explanation`, `emotional_reflection`.

3. Pre-Generation Script Intonation Format:
   - Parses human-editable bracketed annotations (`[DELIVERY: ...]`, `[PACE: ...]`,
     `[ENERGY: 4/5]`, `[EMPHASIS: "..."]`, `[PAUSE AFTER: 500ms]`) as well as YAML/JSON
     segment fields.

4. Sentence/Paragraph Preview, Variant Comparison & SHA-256 Approval Lock:
   - Audition individual sentences, paragraphs, or delivery variants before video rendering,
     then lock the approved narration master (`voice_approval_lock.json`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import subprocess
import urllib.request
import wave
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional

import edge_tts
import numpy as np
import yaml
from pydantic import BaseModel, Field

from .elevenlabs_provider import (
    DEFAULT_DOCUMENTARY_VOICE_IDS,
    FORBIDDEN_THEATRICAL_AUDIO_TAGS,
    build_elevenlabs_request_payload,
    is_elevenlabs_configured,
    resolve_model_capabilities,
    synthesize_elevenlabs_segment,
)
from .schema import CaptionGroupSpec, EpisodeManifest, NarrationSegmentSpec

SR = 48000
FPS = 30
CHANNEL_ROOT = Path(__file__).resolve().parents[2]
VOICE_PROFILES_DIR = CHANNEL_ROOT / "config" / "voice_profiles"

_WHISPER_ALIGN_CACHE: dict[str, Any] = {}


class SentenceDeliveryPreset(BaseModel):
    rate_delta_pct: int = Field(default=0, ge=-20, le=20)
    pitch_delta_hz: int = Field(default=0, ge=-6, le=6)
    pause_after_ms: int = Field(default=340, ge=60, le=1800)


class VoiceDirectionProfile(BaseModel):
    """Reusable, user-editable Voice Direction Profile (Part 4, Section 5.2)."""

    profile_id: str = "cinematic_documentary"
    display_name: str = "Cinematic Documentary"
    description: str = "Measured, authoritative documentary narration."
    voice_mode: Literal["directed_tts", "uploaded_narration", "voice_reference"] = "directed_tts"
    voice_identity: str = "en-GB-RyanNeural"
    accent: str = "en-GB"
    tone: str = "documentary"
    emotion: str = "wonder"
    energy: int = Field(default=3, ge=1, le=5)
    speaking_speed: Literal["slow", "natural", "moderate", "fast"] = "natural"
    base_rate_pct: int = Field(default=0, ge=-15, le=15)
    base_pitch_hz: int = Field(default=0, ge=-4, le=4)
    default_pause_after_ms: int = Field(default=340, ge=80, le=1500)
    consistency_lock: bool = True
    max_rate_delta_pct: int = Field(default=10, ge=2, le=15)
    max_pitch_delta_hz: int = Field(default=2, ge=0, le=4)
    emphasis_strategy: str = "bounded_cadence_and_subtitle_highlight"
    pronunciation: dict[str, str] = Field(default_factory=dict)
    sentence_delivery_presets: dict[str, SentenceDeliveryPreset] = Field(default_factory=dict)
    local_cloning_endpoint_url: Optional[str] = Field(
        default=None,
        description="Optional local zero-cost OpenAI-compatible TTS/cloning endpoint (e.g. local MIT Chatterbox server)",
    )
    reference_acoustic_metrics: dict[str, Any] = Field(default_factory=dict)


@dataclass
class AnnotatedVoiceSentence:
    sentence_index: int
    seg_id: str
    text: str
    delivery: Optional[str] = None
    emotional_tone: Optional[str] = None
    pace: Optional[str] = None
    energy: Optional[int] = None
    emotional_intensity: Optional[float] = None
    pitch_direction: Optional[str] = None
    sentence_rhythm: Optional[str] = None
    pause_before_ms: int = 0
    emphasis_phrases: list[str] = field(default_factory=list)
    pause_after_ms: Optional[int] = None
    pronunciation_overrides: dict[str, str] = field(default_factory=dict)
    vocal_consistency: str = "locked"
    explicit_rate: Optional[str] = None
    explicit_pitch: Optional[str] = None
    tts_text_override: Optional[str] = None


@dataclass
class ResolvedSentenceProsody:
    sentence_index: int
    seg_id: str
    canonical_text: str
    spoken_tts_text: str
    voice_identity: str
    rate_str: str
    pitch_str: str
    pause_before_ms: int
    pause_after_ms: int
    delivery_label: str
    emotional_tone: str
    pace_label: str
    energy_level: int
    emotional_intensity: float
    pitch_direction: str
    sentence_rhythm: str
    vocal_consistency: str
    emphasis_phrases: list[str]
    emphasis_word_norms: list[str]
    cache_key: str
    applied_approximations: list[str]


# Built-in universal delivery fallbacks when a preset doesn't custom-define a tag
UNIVERSAL_DELIVERY_DELTAS: dict[str, tuple[int, int, int]] = {
    "MYSTERIOUS": (-3, -1, 480),
    "HUSHED": (-3, -1, 450),
    "CALM_EXPLORATION": (-2, 0, 410),
    "SURPRISED_BUT_CONTROLLED": (2, 1, 340),
    "CONTROLLED_SURPRISE": (2, 1, 330),
    "URGENT_DISCOVERY": (3, 1, 290),
    "CINEMATIC_REVEAL": (-4, 0, 620),
    "DRAMATIC_REVEAL": (-4, 0, 640),
    "AWE_REVEAL": (-3, 0, 560),
    "MEASURED_EVIDENCE": (0, 0, 320),
    "EVIDENCE": (0, 0, 320),
    "EMPIRICAL_DETAIL": (0, 0, 300),
    "CALM_EXPLANATION": (-1, 0, 350),
    "CLEAR_MECHANISM": (-1, 0, 340),
    "SCIENTIFIC_AUTHORITY": (-1, -1, 350),
    "CAVEAT": (-2, -1, 360),
    "HONEST_CAVEAT": (-2, -1, 360),
    "RIGOROUS_CAVEAT": (-2, -1, 360),
    "CURIOUS_HOOK": (2, 1, 300),
    "ESCALATION": (2, 1, 320),
    "FINAL_IMPRESSION": (-3, -1, 420),
    "QUIET_RESONANCE": (-4, -1, 460),
    "EMOTIONAL_REFLECTION": (-3, -1, 480),
}

PACE_RATE_DELTAS_PCT: dict[str, int] = {
    "SLOW": -4,
    "NATURAL": 0,
    "MODERATE": 2,
    "FAST": 5,
}


def list_voice_direction_profiles() -> list[str]:
    """List reusable Voice Direction Profile IDs in `config/voice_profiles/`."""
    out = []
    if VOICE_PROFILES_DIR.exists():
        for p in sorted(VOICE_PROFILES_DIR.glob("*.yaml")):
            out.append(p.stem)
    return out or ["cinematic_documentary"]


def load_voice_direction_profile(
    profile_ref: Optional[str] = None,
    overrides: Optional[dict[str, Any]] = None,
) -> VoiceDirectionProfile:
    """Load a `VoiceDirectionProfile` by preset name or YAML file path."""
    ref = profile_ref or "cinematic_documentary"
    direct = Path(ref)
    named = VOICE_PROFILES_DIR / f"{ref}.yaml"
    data: dict[str, Any] = {}
    if direct.exists() and direct.is_file():
        data = yaml.safe_load(direct.read_text(encoding="utf-8")) or {}
    elif named.exists():
        data = yaml.safe_load(named.read_text(encoding="utf-8")) or {}
    else:
        fallback = VOICE_PROFILES_DIR / "cinematic_documentary.yaml"
        if fallback.exists():
            data = yaml.safe_load(fallback.read_text(encoding="utf-8")) or {}
        data["profile_id"] = ref

    if overrides:
        merged = dict(data)
        for k, v in overrides.items():
            if isinstance(v, dict) and isinstance(merged.get(k), dict):
                merged[k] = {**merged[k], **v}
            else:
                merged[k] = v
        data = merged
    return VoiceDirectionProfile.model_validate(data)


def _read_wav_mono_f32(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        arr = arr.reshape(-1, ch).mean(axis=1)
    return arr


def _write_wav_stereo(path: Path, stereo: np.ndarray) -> None:
    pcm = np.clip(stereo * 32767.0, -32768, 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())


def _trim_silence(samples: np.ndarray, thresh: float = 0.0028) -> tuple[np.ndarray, float]:
    idx = np.where(np.abs(samples) > thresh)[0]
    if len(idx) == 0:
        return samples, 0.0
    pad_h, pad_t = int(0.032 * SR), int(0.056 * SR)
    i0 = max(0, int(idx[0]) - pad_h)
    i1 = min(len(samples), int(idx[-1]) + pad_t)
    out = samples[i0:i1].copy()
    fn_in = min(int(0.016 * SR), len(out) // 5)
    fn_out = min(int(0.024 * SR), len(out) // 5)
    if fn_in > 2:
        cos_in = 0.5 * (1.0 - np.cos(np.linspace(0.0, math.pi, fn_in, dtype=np.float32)))
        out[:fn_in] *= cos_in
    if fn_out > 2:
        cos_out = 0.5 * (1.0 + np.cos(np.linspace(0.0, math.pi, fn_out, dtype=np.float32)))
        out[-fn_out:] *= cos_out
    return out, i0 / float(SR)


def _match_sentence_active_rms(samples: np.ndarray, target_rms: float = 0.095) -> np.ndarray:
    """
    Normalize speech-active frames across individual sentence renders so joining sentences
    with different prosody tags never produces sudden volume jumps.
    """
    active = samples[np.abs(samples) > 0.012]
    if len(active) < int(0.05 * SR):
        return samples
    cur_rms = float(np.sqrt(np.mean(active * active)))
    if cur_rms < 1e-5:
        return samples
    gain = max(0.65, min(1.55, target_rms / cur_rms))
    return np.clip(samples * gain, -0.96, 0.96).astype(np.float32)


def _split_into_sentences_preserving_text(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return parts if parts else ([text.strip()] if text.strip() else [])


def parse_annotated_voice_script(
    script_text: str,
    default_seg_prefix: str = "N",
) -> list[AnnotatedVoiceSentence]:
    """
    Parse the human-editable pre-generation voice-direction format (Part 4, Section 5.3):

        "Deep beneath the Antarctic ice..."

        [DELIVERY: MYSTERIOUS]
        [PACE: SLOW]
        [ENERGY: 2/5]
        [EMPHASIS: "Deep beneath"]
        [PAUSE AFTER: 500ms]

    Supports optional `[SEG: N01]` section headers, quoted or unquoted spoken lines,
    multi-phrase `[EMPHASIS: "phrase one", "phrase two"]`, and `ms` or `s` pause units.
    """
    lines = script_text.splitlines()
    current_seg_id: Optional[str] = None
    auto_seg_counter = 1

    sentences: list[AnnotatedVoiceSentence] = []
    pending_text_lines: list[str] = []
    pending_tags: dict[str, Any] = {}

    def _flush_current() -> None:
        nonlocal auto_seg_counter, pending_text_lines, pending_tags
        if not pending_text_lines:
            pending_tags = {}
            return
        joined = " ".join(pending_text_lines).strip()
        # Strip surrounding double quotes if line was wrapped as `"Sentence..."`
        if len(joined) >= 2 and joined.startswith('"') and joined.endswith('"'):
            joined = joined[1:-1].strip()
        if not joined:
            pending_text_lines = []
            pending_tags = {}
            return

        seg_id = current_seg_id or f"{default_seg_prefix}{auto_seg_counter:02d}"
        if current_seg_id is None:
            auto_seg_counter += 1

        sentences.append(
            AnnotatedVoiceSentence(
                sentence_index=len(sentences),
                seg_id=seg_id,
                text=joined,
                delivery=pending_tags.get("delivery"),
                emotional_tone=pending_tags.get("emotional_tone"),
                pace=pending_tags.get("pace"),
                energy=pending_tags.get("energy"),
                emotional_intensity=pending_tags.get("emotional_intensity"),
                pitch_direction=pending_tags.get("pitch_direction"),
                sentence_rhythm=pending_tags.get("sentence_rhythm"),
                pause_before_ms=int(pending_tags.get("pause_before_ms", 0)),
                emphasis_phrases=list(pending_tags.get("emphasis_phrases", [])),
                pause_after_ms=pending_tags.get("pause_after_ms"),
                pronunciation_overrides=dict(pending_tags.get("pronunciation_overrides", {})),
                vocal_consistency=str(pending_tags.get("vocal_consistency", "locked")),
                explicit_rate=pending_tags.get("rate"),
                explicit_pitch=pending_tags.get("pitch"),
            )
        )
        pending_text_lines = []
        pending_tags = {}

    tag_pattern = re.compile(r"\[([A-Za-z0-9 _-]+):\s*(.+?)\]")

    for raw_line in lines:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        tags_on_line = tag_pattern.findall(stripped)
        if tags_on_line and stripped.startswith("[") and stripped.endswith("]"):
            for raw_k, raw_v in tags_on_line:
                key = re.sub(r"\s+", " ", raw_k.strip().upper())
                val = raw_v.strip()
                if key in ("SEG", "SEGMENT", "SCENE"):
                    _flush_current()
                    current_seg_id = val.strip("\"'")
                elif key == "DELIVERY":
                    pending_tags["delivery"] = val.strip("\"'")
                elif key in ("TONE", "EMOTIONAL TONE"):
                    pending_tags["emotional_tone"] = val.strip("\"'").lower()
                elif key in ("PACE", "SPEED"):
                    pending_tags["pace"] = val.strip("\"'").upper()
                elif key == "ENERGY":
                    m_en = re.match(r"(\d+)(?:\s*/\s*5)?", val)
                    if m_en:
                        pending_tags["energy"] = max(1, min(5, int(m_en.group(1))))
                elif key in ("INTENSITY", "EMOTIONAL INTENSITY"):
                    try:
                        pending_tags["emotional_intensity"] = max(0.0, min(1.0, float(val)))
                    except ValueError:
                        pass
                elif key in ("PITCH DIRECTION", "CONTOUR"):
                    pending_tags["pitch_direction"] = val.strip("\"'").lower()
                elif key in ("RHYTHM", "SENTENCE RHYTHM"):
                    pending_tags["sentence_rhythm"] = val.strip("\"'").lower()
                elif key in ("PAUSE BEFORE", "PRE PAUSE"):
                    m_pb = re.match(r"([\d.]+)\s*(ms|s)?", val.lower())
                    if m_pb:
                        num = float(m_pb.group(1))
                        unit = m_pb.group(2) or ("s" if num < 5.0 else "ms")
                        ms = int(round(num * 1000.0)) if unit == "s" else int(round(num))
                        pending_tags["pause_before_ms"] = max(0, min(1200, ms))
                elif key == "EMPHASIS":
                    quoted = re.findall(r'"([^"]+)"|\'([^\']+)\'', val)
                    if quoted:
                        phrases = [q[0] or q[1] for q in quoted if (q[0] or q[1]).strip()]
                    else:
                        phrases = [p.strip() for p in val.split(",") if p.strip()]
                    pending_tags.setdefault("emphasis_phrases", []).extend(phrases)
                elif key in ("PRONOUNCE", "PRONUNCIATION"):
                    for pair in re.findall(r'"?([A-Za-z0-9\'-]+)"?\s*=\s*"?([^",]+)"?', val):
                        pending_tags.setdefault("pronunciation_overrides", {})[pair[0].strip()] = pair[1].strip()
                elif key == "CONSISTENCY":
                    pending_tags["vocal_consistency"] = val.strip("\"'").lower()
                elif key in ("PAUSE AFTER", "PAUSE", "BREAK"):
                    m_ms = re.match(r"([\d.]+)\s*(ms|s)?", val.lower())
                    if m_ms:
                        num = float(m_ms.group(1))
                        unit = m_ms.group(2) or ("s" if num < 10.0 else "ms")
                        ms = int(round(num * 1000.0)) if unit == "s" else int(round(num))
                        pending_tags["pause_after_ms"] = max(60, min(2500, ms))
                elif key == "RATE":
                    pending_tags["rate"] = val.strip("\"'")
                elif key == "PITCH":
                    pending_tags["pitch"] = val.strip("\"'")
            continue

        # New spoken line arriving AFTER tags were already attached to the previous spoken line -> flush!
        if pending_text_lines and pending_tags:
            _flush_current()
        elif pending_text_lines and stripped.startswith('"') and pending_text_lines[-1].endswith('"'):
            _flush_current()

        pending_text_lines.append(stripped)

    _flush_current()
    return sentences


def _infer_narrative_voice_direction_for_segment(
    seg: NarrationSegmentSpec,
    seg_idx: int,
    total_segs: int,
    manifest: EpisodeManifest,
) -> tuple[str, str, int, str]:
    """
    Derive contrast-rich documentary voice direction (`delivery, pace, energy, emotional_tone`)
    from each segment's actual narrative role rather than stamping uniform delivery across the video.
    """
    beat = seg.narrative_beat or ""
    if seg_idx == 0 or beat == "opening_hook":
        if any(k in seg.text.lower() for k in ("beneath", "deep", "dark", "hidden", "nobody", "sealed", "mystery")):
            return ("MYSTERIOUS", "SLOW", 2, "curious_restraint")
        return ("CURIOUS_HOOK", "NATURAL", 3, "engaged_curiosity")
    if seg_idx == total_segs - 1 or beat == "final_impression":
        return ("EMOTIONAL_REFLECTION", "SLOW", 2, "reflective_resonance")
    if seg.seg_id == manifest.editorial_formula.scientific_caveat_seg_id:
        return ("HONEST_CAVEAT", "NATURAL", 3, "credible_precision")
    if seg.seg_id == manifest.editorial_formula.layer2_pivot_seg_id or beat == "escalation":
        return ("SURPRISED_BUT_CONTROLLED", "NATURAL", 4, "controlled_discovery")
    if beat == "payoff":
        return ("CINEMATIC_REVEAL", "SLOW", 4, "earned_significance")
    if beat == "curiosity_gap":
        return ("CALM_EXPLORATION", "NATURAL", 3, "immersive_inquiry")
    return ("SCIENTIFIC_AUTHORITY", "NATURAL", 3, "confident_explanation")


def export_annotated_voice_script(manifest: EpisodeManifest, out_path: Optional[Path] = None) -> str:
    """Export an episode's narration into a contrast-aware, human-editable bracketed Voice Studio script."""
    blocks: list[str] = [
        f"# Proof of Wonder — Voice Direction Script ({manifest.slug})",
        f"# Profile: {manifest.voice_direction_profile or 'cinematic_documentary'} | Voice: {manifest.voice}",
        "",
    ]
    total_segs = len(manifest.narration_segments)
    for seg_idx, seg in enumerate(manifest.narration_segments):
        blocks.append(f"[SEG: {seg.seg_id}]")
        if seg.annotated_text:
            blocks.append(seg.annotated_text.strip())
            blocks.append("")
            continue
        auto_deliv, auto_pace, auto_energy, auto_tone = _infer_narrative_voice_direction_for_segment(
            seg, seg_idx, total_segs, manifest
        )
        sents = _split_into_sentences_preserving_text(seg.text)
        for idx, sent in enumerate(sents):
            is_last = idx == len(sents) - 1
            blocks.append(f'"{sent}"')
            blocks.append("")
            deliv = seg.delivery or (auto_deliv if (idx == 0 or is_last) else "MEASURED_EVIDENCE")
            pace = seg.pace or auto_pace
            energy = seg.energy or (auto_energy if (idx == 0 or is_last) else 3)
            tone = seg.emotional_tone or auto_tone
            pause_ms = int(round(seg.pause_after_s * 1000)) if is_last else 260
            blocks.append(f"[DELIVERY: {deliv}]")
            blocks.append(f"[TONE: {tone}]")
            blocks.append(f"[PACE: {pace}]")
            blocks.append(f"[ENERGY: {energy}/5]")
            if seg.emphasis_words:
                emph_in_sent = [ew for ew in seg.emphasis_words if ew.lower() in sent.lower()]
                if emph_in_sent:
                    quoted = ", ".join(f'"{ew}"' for ew in emph_in_sent)
                    blocks.append(f"[EMPHASIS: {quoted}]")
            blocks.append(f"[PAUSE AFTER: {pause_ms}ms]")
            blocks.append("")
    content = "\n".join(blocks).rstrip() + "\n"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    return content


def plan_and_rebalance_voice_direction(
    sentences: list[AnnotatedVoiceSentence],
    manifest: Optional[EpisodeManifest] = None,
) -> tuple[list[AnnotatedVoiceSentence], dict[str, Any]]:
    """
    Enforce Part 2 Section 3 Voice Direction & Contrast Rules:
    1. Block forbidden whispering, shouting, or exaggerated hype tags.
    2. When plain sentences lack delivery direction, assign story-meaning contrast
       (quieter/slower mysterious opening -> confident natural explanation -> stronger
       discovery emphasis -> brief pause around surprising facts -> reflective ending).
    3. Rebalance over-dramatic scripts: if >45% of sentences (>=4 total) use high-drama
       tags (`CINEMATIC_REVEAL`, `DRAMATIC_REVEAL`, `URGENT_DISCOVERY`, or `energy >= 4`),
       calm intermediate explanatory lines back to `MEASURED_EVIDENCE` (`energy=3`) so
       genuine reveals actually stand out.
    """
    seg_lookup = {s.seg_id: (idx, s) for idx, s in enumerate(manifest.narration_segments)} if manifest else {}
    total_segs = len(manifest.narration_segments) if manifest else 1
    guardrail_notes: list[str] = []
    blocked_theatrical_count = 0
    rebalanced_overdrama_count = 0

    out: list[AnnotatedVoiceSentence] = []
    for s in sentences:
        item = AnnotatedVoiceSentence(**asdict(s))
        raw_d = (item.delivery or "").strip().lower()

        # 1. Block whispering / shouting / theatrical exaggeration
        if any(bad in raw_d for bad in FORBIDDEN_THEATRICAL_AUDIO_TAGS):
            blocked_theatrical_count += 1
            replacement = "MYSTERIOUS" if "whisper" in raw_d else "URGENT_DISCOVERY"
            guardrail_notes.append(
                f"[sent #{item.sentence_index} {item.seg_id}] Replaced theatrical delivery '{item.delivery}' -> '{replacement}'."
            )
            item.delivery = replacement
            if item.energy and item.energy > 4:
                item.energy = 4

        # 2. Fill missing narrative contrast from story beat & sentence content
        if not item.delivery and manifest and item.seg_id in seg_lookup:
            s_idx, seg_obj = seg_lookup[item.seg_id]
            auto_d, auto_p, auto_e, auto_t = _infer_narrative_voice_direction_for_segment(
                seg_obj, s_idx, total_segs, manifest
            )
            item.delivery = auto_d
            item.pace = item.pace or auto_p
            item.energy = item.energy if item.energy is not None else auto_e
            item.emotional_tone = item.emotional_tone or auto_t
            if re.search(r"\b(?:never|instead|yet|unexpected|surprising|million|billion)\b", item.text, re.I) and item.pause_before_ms == 0 and item.sentence_index > 0:
                item.pause_before_ms = 110

        out.append(item)

    # 3. Anti-All-Dramatic Contrast Rebalancer
    high_drama_keys = {"CINEMATIC_REVEAL", "DRAMATIC_REVEAL", "AWE_REVEAL", "URGENT_DISCOVERY"}
    if len(out) >= 4:
        dramatic_indices = [
            i
            for i, x in enumerate(out)
            if (re.sub(r"[^A-Z0-9]+", "_", (x.delivery or "").upper()).strip("_") in high_drama_keys)
            or ((x.energy or 3) >= 4)
        ]
        if len(dramatic_indices) / float(len(out)) > 0.45:
            # Preserve the primary reveal/pivot climax sentences (at most ~35% of sentences)
            max_keep = max(1, int(len(out) * 0.35))
            # Prefer keeping sentences near pivot/payoff (latter half, excluding very first context lines)
            ranked_to_keep = sorted(
                dramatic_indices,
                key=lambda idx: (
                    1 if (manifest and out[idx].seg_id == manifest.editorial_formula.layer2_pivot_seg_id) else 0,
                    1 if re.search(r"\b(?:discover|reveal|found|actual|hidden|secret|beneath)\b", out[idx].text, re.I) else 0,
                    idx,
                ),
                reverse=True,
            )
            keep_set = set(ranked_to_keep[:max_keep])
            for idx in dramatic_indices:
                if idx not in keep_set:
                    old_d = out[idx].delivery
                    out[idx].delivery = "MEASURED_EVIDENCE"
                    out[idx].energy = 3
                    out[idx].pace = "NATURAL"
                    rebalanced_overdrama_count += 1
                    guardrail_notes.append(
                        f"[sent #{idx} {out[idx].seg_id}] Rebalanced excess dramatic tag '{old_d}' -> 'MEASURED_EVIDENCE' to preserve vocal contrast."
                    )

    distinct_deliveries = sorted({(x.delivery or "DEFAULT").upper() for x in out})
    energies = [x.energy or 3 for x in out]
    contrast_summary = {
        "sentence_count": len(out),
        "distinct_delivery_styles": distinct_deliveries,
        "distinct_delivery_count": len(distinct_deliveries),
        "energy_min": min(energies) if energies else 3,
        "energy_max": max(energies) if energies else 3,
        "energy_span": (max(energies) - min(energies)) if energies else 0,
        "blocked_theatrical_count": blocked_theatrical_count,
        "rebalanced_overdrama_count": rebalanced_overdrama_count,
        "contrast_healthy": (len(out) <= 2) or (len(distinct_deliveries) >= 2),
        "guardrail_notes": guardrail_notes,
    }
    return out, contrast_summary


def build_sentences_from_manifest(manifest: EpisodeManifest) -> list[AnnotatedVoiceSentence]:
    """
    Build the ordered list of `AnnotatedVoiceSentence` items for an episode:
    1. If `manifest.annotated_voice_script_file` exists, parse it directly.
    2. Otherwise expand `manifest.narration_segments` (supporting per-segment `annotated_text`
       or structured `delivery`/`pace`/`energy`/`emphasis_words`/`pause_after_s`/`rate`/`pitch`).
    """
    if manifest.annotated_voice_script_file:
        cand = Path(manifest.annotated_voice_script_file)
        if not cand.is_absolute():
            cand = CHANNEL_ROOT / manifest.annotated_voice_script_file
        if cand.exists():
            parsed = parse_annotated_voice_script(cand.read_text(encoding="utf-8"))
            if parsed:
                return parsed

    out: list[AnnotatedVoiceSentence] = []
    for seg in manifest.narration_segments:
        if seg.annotated_text and seg.annotated_text.strip():
            sub_sents = parse_annotated_voice_script(seg.annotated_text, default_seg_prefix=seg.seg_id)
            for ss in sub_sents:
                ss.seg_id = seg.seg_id
                ss.sentence_index = len(out)
                if not ss.emphasis_phrases and seg.emphasis_words:
                    ss.emphasis_phrases = [ew for ew in seg.emphasis_words if ew.lower() in ss.text.lower()]
                out.append(ss)
            continue

        # Preserve single-block synthesis when `seg.tts_text` is explicitly given so custom phonetic overrides stay 1:1
        if seg.tts_text:
            sents = [seg.text.strip()]
        else:
            sents = _split_into_sentences_preserving_text(seg.text)

        for idx, sent in enumerate(sents):
            is_last = idx == len(sents) - 1
            emph_here = [ew for ew in seg.emphasis_words if ew.lower() in sent.lower()]
            if is_last and not emph_here and len(sents) == 1:
                emph_here = list(seg.emphasis_words)
            out.append(
                AnnotatedVoiceSentence(
                    sentence_index=len(out),
                    seg_id=seg.seg_id,
                    text=sent,
                    delivery=seg.delivery,
                    emotional_tone=seg.emotional_tone,
                    pace=seg.pace,
                    energy=seg.energy,
                    emotional_intensity=seg.emotional_intensity,
                    pitch_direction=seg.pitch_direction,
                    sentence_rhythm=seg.sentence_rhythm,
                    pause_before_ms=int(round(seg.pause_before_s * 1000.0)) if idx == 0 else 0,
                    emphasis_phrases=emph_here,
                    pause_after_ms=int(round(seg.pause_after_s * 1000.0)) if is_last else 240,
                    pronunciation_overrides=dict(seg.pronunciation_overrides or {}),
                    vocal_consistency=seg.vocal_consistency,
                    explicit_rate=seg.rate if seg.rate != "+0%" else None,
                    explicit_pitch=seg.pitch if seg.pitch != "+0Hz" else None,
                    tts_text_override=seg.tts_text if len(sents) == 1 else None,
                )
            )
    return out


def _parse_signed_int(val: Optional[str], suffix: str) -> Optional[int]:
    if not val:
        return None
    m = re.match(rf"^\s*([+-]?\d+)\s*{re.escape(suffix)}\s*$", val, flags=re.I)
    return int(m.group(1)) if m else None


def _apply_pronunciation_map(text: str, pron_map: dict[str, str]) -> tuple[str, dict[str, str]]:
    rev: dict[str, str] = {}
    for orig, spoken in (pron_map or {}).items():
        on = re.sub(r"[^a-z0-9']", "", spoken.lower())
        if on:
            rev[on] = orig
    out = text
    for orig, spoken in (pron_map or {}).items():
        pattern = re.compile(rf"\b{re.escape(orig)}\b", flags=re.IGNORECASE)
        out = pattern.sub(spoken, out)
    return out, rev


def resolve_sentence_prosody(
    sent: AnnotatedVoiceSentence,
    profile: VoiceDirectionProfile,
    extra_pronunciations: Optional[dict[str, str]] = None,
    voice_override: Optional[str] = None,
) -> ResolvedSentenceProsody:
    """
    Map `VoiceDirectionProfile` + sentence intonation tags into bounded, natural prosody
    parameters without robotic pitch warps or syllable stretching (Part 2, Sections 3–4).
    """
    voice_id = voice_override or profile.voice_identity
    merged_pron = {
        **(profile.pronunciation or {}),
        **(extra_pronunciations or {}),
        **(sent.pronunciation_overrides or {}),
    }

    deliv_raw = (sent.delivery or "").strip()
    deliv_key = re.sub(r"[^A-Z0-9]+", "_", deliv_raw.upper()).strip("_") if deliv_raw else "DEFAULT"

    # Base profile rate & pitch
    speed_base = {"slow": -3, "natural": 0, "moderate": 2, "fast": 5}.get(profile.speaking_speed, 0)
    rate_pct = profile.base_rate_pct + speed_base
    pitch_hz = profile.base_pitch_hz
    pause_ms = profile.default_pause_after_ms
    approximations: list[str] = []

    # 1. Apply delivery tag preset (from profile first, then universal table)
    if deliv_key in profile.sentence_delivery_presets:
        dp = profile.sentence_delivery_presets[deliv_key]
        rate_pct += dp.rate_delta_pct
        pitch_hz += dp.pitch_delta_hz
        pause_ms = dp.pause_after_ms
        approximations.append(f"DELIVERY:{deliv_key}->profile_preset(rate={dp.rate_delta_pct:+d}%,pitch={dp.pitch_delta_hz:+d}Hz,pause={dp.pause_after_ms}ms)")
    elif deliv_key in UNIVERSAL_DELIVERY_DELTAS:
        dr, dp_hz, d_pause = UNIVERSAL_DELIVERY_DELTAS[deliv_key]
        rate_pct += dr
        pitch_hz += dp_hz
        pause_ms = d_pause
        approximations.append(f"DELIVERY:{deliv_key}->bounded_prosody(rate={dr:+d}%,pitch={dp_hz:+d}Hz,pause={d_pause}ms)")
    elif deliv_raw:
        approximations.append(f"DELIVERY:{deliv_raw}->preserved_neutral_cadence(unrecognized_style_kept_natural)")

    # 2. Apply explicit `[PACE: ...]` and optional `sentence_rhythm`
    pace_label = (sent.pace or profile.speaking_speed).upper()
    if sent.pace and sent.pace.upper() in PACE_RATE_DELTAS_PCT:
        p_delta = PACE_RATE_DELTAS_PCT[sent.pace.upper()]
        rate_pct = profile.base_rate_pct + p_delta
        approximations.append(f"PACE:{sent.pace.upper()}->rate_pct={rate_pct:+d}%")

    rhythm_label = (sent.sentence_rhythm or "measured").lower()
    if rhythm_label == "reflective_slow":
        rate_pct -= 2
        pause_ms = max(pause_ms, 440)
    elif rhythm_label == "deliberate_staccato":
        rate_pct -= 1

    # 2b. Optional `pitch_direction`
    pdir = (sent.pitch_direction or "steady").lower()
    if pdir == "low_intimate":
        pitch_hz -= 1
    elif pdir == "gentle_rise":
        pitch_hz += 1

    # 3. Apply `[ENERGY: 1..5]` subtly (bounded +/-1..2% rate & +/-1Hz pitch—never shouting/robotic)
    eff_energy = sent.energy if sent.energy is not None else profile.energy
    energy_delta = eff_energy - 3
    if energy_delta != 0:
        rate_pct += energy_delta * 1
        if abs(energy_delta) >= 2:
            pitch_hz += 1 if energy_delta > 0 else -1
        approximations.append(f"ENERGY:{eff_energy}/5->subtle_intensity_nudge")

    # 4. Explicit segment overrides (`rate`, `pitch`, `pause_after_ms`)
    exp_r = _parse_signed_int(sent.explicit_rate, "%")
    if exp_r is not None:
        rate_pct = exp_r
    exp_p = _parse_signed_int(sent.explicit_pitch, "Hz")
    if exp_p is not None:
        pitch_hz = exp_p
    if sent.pause_after_ms is not None:
        pause_ms = sent.pause_after_ms

    # 5. Consistency lock clamping so voice identity remains 100% human & stable
    lock_active = profile.consistency_lock and (sent.vocal_consistency != "expressive_bounded")
    max_r = profile.max_rate_delta_pct if lock_active else min(12, profile.max_rate_delta_pct + 2)
    max_p = profile.max_pitch_delta_hz if lock_active else min(3, profile.max_pitch_delta_hz + 1)
    rate_pct = max(-max_r, min(max_r, rate_pct))
    pitch_hz = max(-max_p, min(max_p, pitch_hz))
    pause_ms = max(80, min(1400, pause_ms))
    pause_before_ms = max(0, min(900, int(sent.pause_before_ms or 0)))

    # 6. Extract normalized emphasis word tokens from phrases (`"Deep beneath"` -> `["deep", "beneath"]`)
    emph_norms: list[str] = []
    for ph in sent.emphasis_phrases:
        for tok in re.findall(r"[A-Za-z0-9']+", ph):
            tn = re.sub(r"[^a-z0-9]", "", tok.lower())
            if tn and tn not in emph_norms:
                emph_norms.append(tn)
    if emph_norms:
        approximations.append("EMPHASIS->word_boundary_highlight_and_measured_articulation")

    base_tts_in = sent.tts_text_override if sent.tts_text_override else sent.text
    spoken_tts, _ = _apply_pronunciation_map(base_tts_in, merged_pron)

    rate_str = f"{rate_pct:+d}%"
    pitch_str = f"{pitch_hz:+d}Hz"
    emo_tone = sent.emotional_tone or profile.emotion
    emo_intensity = float(sent.emotional_intensity) if sent.emotional_intensity is not None else round((eff_energy - 1) / 4.0, 2)

    sig_payload = json.dumps(
        {
            "v": voice_id,
            "t": spoken_tts,
            "r": rate_str,
            "p": pitch_str,
        },
        sort_keys=True,
    )
    ckey = hashlib.sha256(sig_payload.encode("utf-8")).hexdigest()[:20]

    return ResolvedSentenceProsody(
        sentence_index=sent.sentence_index,
        seg_id=sent.seg_id,
        canonical_text=sent.text,
        spoken_tts_text=spoken_tts,
        voice_identity=voice_id,
        rate_str=rate_str,
        pitch_str=pitch_str,
        pause_before_ms=pause_before_ms,
        pause_after_ms=pause_ms,
        delivery_label=deliv_key,
        emotional_tone=emo_tone,
        pace_label=pace_label,
        energy_level=eff_energy,
        emotional_intensity=emo_intensity,
        pitch_direction=pdir,
        sentence_rhythm=rhythm_label,
        vocal_consistency=sent.vocal_consistency,
        emphasis_phrases=list(sent.emphasis_phrases),
        emphasis_word_norms=emph_norms,
        cache_key=ckey,
        applied_approximations=approximations,
    )


async def _synthesize_cached_sentence(
    resolved: ResolvedSentenceProsody,
    rev_pron_map: dict[str, str],
    cache_dir: Path,
    force_regenerate: bool = False,
) -> tuple[Path, list[dict[str, Any]], bool]:
    """
    Synthesize a single sentence via `edge-tts` with `WordBoundary` capture, caching the
    decoded `48kHz` mono WAV + word boundary JSON by `resolved.cache_key` so selective
    re-rendering of edited lines reuses all unchanged sentences instantaneously.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav_p = cache_dir / f"sent_{resolved.cache_key}.wav"
    meta_p = cache_dir / f"sent_{resolved.cache_key}.json"

    if not force_regenerate and wav_p.exists() and meta_p.exists() and wav_p.stat().st_size > 256:
        cached = json.loads(meta_p.read_text(encoding="utf-8"))
        return wav_p, cached.get("words", []), True

    mp3_p = cache_dir / f"sent_{resolved.cache_key}.mp3"
    last_err: Optional[Exception] = None
    words: list[dict[str, Any]] = []
    for attempt in range(5):
        words = []
        try:
            comm = edge_tts.Communicate(
                resolved.spoken_tts_text,
                resolved.voice_identity,
                rate=resolved.rate_str,
                pitch=resolved.pitch_str,
                boundary="WordBoundary",
            )
            with open(mp3_p, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        raw_w = str(chunk["text"])
                        wn_key = re.sub(r"[^a-z0-9']", "", raw_w.lower())
                        canon_w = rev_pron_map.get(wn_key, raw_w)
                        words.append(
                            {
                                "text": canon_w,
                                "offset_s": chunk["offset"] / 10_000_000.0,
                                "duration_s": chunk["duration"] / 10_000_000.0,
                            }
                        )
            if mp3_p.exists() and mp3_p.stat().st_size > 256:
                last_err = None
                break
        except Exception as exc:
            last_err = exc
            await asyncio.sleep(0.8 * (attempt + 1))

    if last_err is not None:
        raise last_err

    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(mp3_p),
            "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le",
            str(wav_p),
        ],
        check=True,
    )
    mp3_p.unlink(missing_ok=True)
    meta_p.write_text(json.dumps({"prosody": asdict(resolved), "words": words}, indent=2), encoding="utf-8")
    return wav_p, words, False


def preview_voice_sentence(
    text_or_annotated: str,
    profile_ref: str = "cinematic_documentary",
    out_wav_path: Optional[Path] = None,
    voice_override: Optional[str] = None,
    extra_pronunciations: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Preview a single sentence (plain or bracket-annotated) before full narration generation
    (Part 4, Section 5.5).
    """
    profile = load_voice_direction_profile(profile_ref)
    parsed = parse_annotated_voice_script(text_or_annotated)
    sent = parsed[0] if parsed else AnnotatedVoiceSentence(sentence_index=0, seg_id="PREVIEW", text=text_or_annotated.strip())
    resolved = resolve_sentence_prosody(sent, profile, extra_pronunciations=extra_pronunciations, voice_override=voice_override)
    _, rev_map = _apply_pronunciation_map(sent.text, {**(profile.pronunciation or {}), **(extra_pronunciations or {})})

    target_wav = out_wav_path or (Path("/tmp/pow_voice_preview") / f"preview_{resolved.cache_key}.wav")
    target_wav.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = target_wav.parent / "_sentence_cache"

    wav_cached, words, cache_hit = asyncio.run(_synthesize_cached_sentence(resolved, rev_map, cache_dir))
    mono = _match_sentence_active_rms(_trim_silence(_read_wav_mono_f32(wav_cached))[0])
    pause_pad = np.zeros(int(round((resolved.pause_after_ms / 1000.0) * SR)), dtype=np.float32)
    full_st = np.stack([np.concatenate([mono, pause_pad])] * 2, axis=1)
    _write_wav_stereo(target_wav, full_st)

    return {
        "preview_kind": "sentence",
        "wav_path": str(target_wav),
        "duration_s": round(full_st.shape[0] / float(SR), 3),
        "cache_hit": cache_hit,
        "resolved_prosody": asdict(resolved),
        "word_count": len(words),
    }


def preview_voice_paragraph(
    annotated_paragraph_text: str,
    profile_ref: str = "cinematic_documentary",
    out_wav_path: Optional[Path] = None,
    voice_override: Optional[str] = None,
    extra_pronunciations: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """
    Preview a multi-sentence paragraph with full inter-sentence pauses and RMS consistency
    before rendering the full video (Part 4, Section 5.5).
    """
    profile = load_voice_direction_profile(profile_ref)
    sents = parse_annotated_voice_script(annotated_paragraph_text)
    if not sents:
        raise ValueError("No spoken sentences found in paragraph text.")

    target_wav = out_wav_path or (Path("/tmp/pow_voice_preview") / "paragraph_preview.wav")
    target_wav.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = target_wav.parent / "_sentence_cache"
    merged_pron = {**(profile.pronunciation or {}), **(extra_pronunciations or {})}
    _, rev_map = _apply_pronunciation_map("", merged_pron)

    async def _run_para() -> tuple[np.ndarray, list[dict[str, Any]]]:
        chunks = [np.zeros(int(0.08 * SR), dtype=np.float32)]
        sent_reports = []
        cursor = 0.08
        for s in sents:
            res = resolve_sentence_prosody(s, profile, extra_pronunciations=extra_pronunciations, voice_override=voice_override)
            wav_c, words, hit = await _synthesize_cached_sentence(res, rev_map, cache_dir)
            mono, _ = _trim_silence(_read_wav_mono_f32(wav_c))
            mono = _match_sentence_active_rms(mono)
            dur = len(mono) / float(SR)
            pause_s = res.pause_after_ms / 1000.0
            chunks.append(mono)
            chunks.append(np.zeros(int(round(pause_s * SR)), dtype=np.float32))
            sent_reports.append(
                {
                    "sentence_index": s.sentence_index,
                    "text": s.text,
                    "start_s": round(cursor, 3),
                    "end_s": round(cursor + dur, 3),
                    "pause_after_ms": res.pause_after_ms,
                    "rate": res.rate_str,
                    "pitch": res.pitch_str,
                    "delivery": res.delivery_label,
                    "cache_hit": hit,
                    "words": len(words),
                }
            )
            cursor += dur + pause_s
        return np.concatenate(chunks), sent_reports

    mono_all, reports = asyncio.run(_run_para())
    _write_wav_stereo(target_wav, np.stack([mono_all, mono_all], axis=1))
    return {
        "preview_kind": "paragraph",
        "wav_path": str(target_wav),
        "profile_id": profile.profile_id,
        "voice_identity": voice_override or profile.voice_identity,
        "sentence_count": len(reports),
        "total_duration_s": round(len(mono_all) / float(SR), 3),
        "sentences": reports,
    }


def compare_voice_variants(
    sentence_text: str,
    variants: list[dict[str, Any]],
    profile_ref: str = "cinematic_documentary",
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Generate side-by-side delivery variants of the same line (e.g. `CALM_EXPLANATION` vs.
    `MYSTERIOUS` vs. `CINEMATIC_REVEAL`) so the creator can compare intonation choices.
    """
    dest = out_dir or Path("/tmp/pow_voice_variants")
    dest.mkdir(parents=True, exist_ok=True)
    results = []
    for idx, var in enumerate(variants):
        vid = str(var.get("variant_id", chr(65 + idx)))
        deliv = str(var.get("delivery", "MEASURED_EVIDENCE"))
        pace = str(var.get("pace", "NATURAL"))
        energy = int(var.get("energy", 3))
        pause_ms = int(var.get("pause_after_ms", 400))
        emph = var.get("emphasis", "")
        emph_line = f'\n[EMPHASIS: "{emph}"]' if emph else ""
        block = (
            f'"{sentence_text.strip()}"\n\n'
            f"[DELIVERY: {deliv}]\n"
            f"[PACE: {pace}]\n"
            f"[ENERGY: {energy}/5]{emph_line}\n"
            f"[PAUSE AFTER: {pause_ms}ms]\n"
        )
        wav_out = dest / f"variant_{vid}_{deliv.lower()}.wav"
        prev = preview_voice_sentence(
            block,
            profile_ref=str(var.get("profile_ref", profile_ref)),
            out_wav_path=wav_out,
            voice_override=var.get("voice_override"),
        )
        results.append(
            {
                "variant_id": vid,
                "delivery": deliv,
                "pace": pace,
                "energy": energy,
                "wav_path": prev["wav_path"],
                "duration_s": prev["duration_s"],
                "rate": prev["resolved_prosody"]["rate_str"],
                "pitch": prev["resolved_prosody"]["pitch_str"],
            }
        )
    comp_json = dest / "voice_variants_comparison.json"
    payload = {"sentence_text": sentence_text, "variants": results}
    comp_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _get_whisper_model(model_size: str = "medium.en"):
    if model_size not in _WHISPER_ALIGN_CACHE:
        from faster_whisper import WhisperModel

        dl_root = CHANNEL_ROOT / "assets" / "models"
        kw = {"download_root": str(dl_root)} if dl_root.exists() else {}
        try:
            _WHISPER_ALIGN_CACHE[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8", **kw)
        except Exception:
            _WHISPER_ALIGN_CACHE[model_size] = WhisperModel("base.en", device="cpu", compute_type="int8", **kw)
    return _WHISPER_ALIGN_CACHE[model_size]


def auto_build_caption_groups_from_words(
    wt: dict[str, Any],
    max_words_per_cue: int = 6,
    max_chars_per_cue: int = 38,
) -> list[CaptionGroupSpec]:
    """
    Automatically group word timings into natural, mobile-readable documentary phrases
    respecting punctuation and clause breaks when `manifest.caption_groups` is empty
    or when timing comes from Mode A uploaded human narration.
    """
    by_seg: dict[str, list[dict[str, Any]]] = {}
    for w in wt.get("words", []):
        by_seg.setdefault(str(w["seg_id"]), []).append(w)

    groups: list[CaptionGroupSpec] = []
    for seg in wt.get("segments", []):
        sid = str(seg["seg_id"])
        swords = by_seg.get(sid, [])
        if not swords:
            continue
        cur_start = 0
        cur_tokens: list[str] = []
        for idx, w in enumerate(swords):
            tok = str(w["word"]).strip()
            cur_tokens.append(tok)
            char_len = len(" ".join(cur_tokens))
            ends_punct = tok.endswith((".", "?", "!", ",", ";", ":", "—"))
            next_gap = (
                float(swords[idx + 1]["start"]) - float(w["end"])
                if idx + 1 < len(swords)
                else 9.9
            )
            clean_tok = re.sub(r"[^a-z]", "", tok.lower())
            is_trailing_determiner = clean_tok in {"a", "an", "the", "of", "in", "to", "at", "by", "for", "with", "from"}
            if (
                is_trailing_determiner
                and idx < len(swords) - 1
                and len(cur_tokens) >= 4
                and not ends_punct
            ):
                # Hold trailing determiner/preposition for the next phrase so cues never end on an orphaned 'a' or 'the'
                held_tok = cur_tokens.pop()
                groups.append(
                    CaptionGroupSpec(
                        seg_id=sid,
                        first_word_idx=cur_start,
                        last_word_idx=idx - 1,
                        text=" ".join(cur_tokens),
                    )
                )
                cur_start = idx
                cur_tokens = [held_tok]
                continue

            should_break = (
                idx == len(swords) - 1
                or len(cur_tokens) >= max_words_per_cue
                or char_len >= max_chars_per_cue
                or (ends_punct and len(cur_tokens) >= 3)
                or (next_gap >= 0.28 and len(cur_tokens) >= 2)
            )
            if should_break:
                groups.append(
                    CaptionGroupSpec(
                        seg_id=sid,
                        first_word_idx=cur_start,
                        last_word_idx=idx,
                        text=" ".join(cur_tokens),
                    )
                )
                cur_start = idx + 1
                cur_tokens = []
    return groups


def _probe_audio_health(audio_path: Path) -> dict[str, Any]:
    """Validate audio container, sample rate, duration, LUFS, LRA, True Peak, and clipping."""
    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(audio_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    info = json.loads(pr.stdout)
    astream = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    if not astream:
        raise ValueError(f"Uploaded file '{audio_path}' contains no decodable audio stream.")

    dur_s = float(info.get("format", {}).get("duration", astream.get("duration", 0.0)) or 0.0)
    if dur_s < 1.5:
        raise ValueError(f"Uploaded audio '{audio_path}' is too short ({dur_s:.2f}s < 1.5s).")

    ebu = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(audio_path), "-af", "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    summ = ebu.stderr[ebu.stderr.rfind("Summary:") :] if "Summary:" in ebu.stderr else ebu.stderr
    m_i = re.search(r"I:\s+(-?[\d.]+)\s+LUFS", summ)
    m_lra = re.search(r"LRA:\s+([\d.]+)\s+LU", summ)
    m_tp = re.search(r"Peak:\s+(-?[\d.]+)\s+dBFS", summ)

    return {
        "codec_name": astream.get("codec_name"),
        "sample_rate_hz": int(astream.get("sample_rate", 0) or 0),
        "channels": int(astream.get("channels", 0) or 0),
        "duration_s": round(dur_s, 4),
        "integrated_lufs": float(m_i.group(1)) if m_i else -23.0,
        "loudness_range_lu": float(m_lra.group(1)) if m_lra else 6.0,
        "true_peak_dbfs": float(m_tp.group(1)) if m_tp else -3.0,
    }


def ingest_uploaded_narration(
    manifest: EpisodeManifest,
    uploaded_file: Path,
    clean_noise: bool = False,
) -> dict[str, Any]:
    """
    Mode A — Uploaded Final Narration (Part 4, Section 5.1):
    - Validates uploaded audio.
    - Detects speech, silence, pauses, and sentence boundaries.
    - Applies optional gentle noise reduction and dynamics-preserving normalization (`LRA=11`).
    - Aligns script segments & word timestamps via local `faster-whisper`.
    - Writes authoritative `word_timings.json` + `work_audio/narration_norm.wav` without
      regenerating or replacing the speaker's voice.
    """
    if not uploaded_file.exists():
        raise FileNotFoundError(f"Uploaded narration file not found: {uploaded_file}")

    health_in = _probe_audio_health(uploaded_file)
    out_dir = Path(manifest.output_dir)
    work_dir = out_dir / "work_audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    narr_norm_wav = work_dir / "narration_norm.wav"
    af_chain = []
    if clean_noise:
        af_chain.append("highpass=f=80,afftdn=nf=-26")
    else:
        af_chain.append("highpass=f=75")
    # Dynamics-preserving loudness normalization (LRA=11.0 preserves natural human expression!)
    af_chain.append("loudnorm=I=-16.0:TP=-1.5:LRA=11.0")

    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(uploaded_file),
            "-af", ",".join(af_chain),
            "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
            str(narr_norm_wav),
        ],
        check=True,
    )

    # Snap exact sample length to 30fps frame grid without trimming human speech
    mono = _read_wav_mono_f32(narr_norm_wav)
    total_frames = max(1, int(round((len(mono) / float(SR)) * FPS)))
    target_samples = int(round((total_frames / float(FPS)) * SR))
    if len(mono) < target_samples:
        mono_padded = np.pad(mono, (0, target_samples - len(mono)))
    else:
        mono_padded = mono[:target_samples]

    with wave.open(str(narr_norm_wav), "rb") as wf:
        ch = wf.getnchannels()
        raw = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    st = raw.reshape(-1, 2) if ch == 2 else np.stack([raw, raw], axis=1)
    if st.shape[0] < target_samples:
        st = np.pad(st, ((0, target_samples - st.shape[0]), (0, 0)))
    else:
        st = st[:target_samples]
    _write_wav_stereo(narr_norm_wav, st)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(narr_norm_wav), "-c:a", "libmp3lame", "-b:a", "256k", str(out_dir / "narration.mp3")],
        check=True,
    )

    # Transcribe with local faster-whisper (`word_timestamps=True`) to extract exact timing
    model = _get_whisper_model("medium.en")
    w_segments, _ = model.transcribe(str(narr_norm_wav), language="en", word_timestamps=True, vad_filter=False)
    asr_words: list[dict[str, Any]] = []
    for ws in w_segments:
        for w in (ws.words or []):
            tok = str(w.word).strip()
            if tok:
                asr_words.append(
                    {
                        "word": tok,
                        "start": round(max(0.0, float(w.start)), 3),
                        "end": round(max(float(w.start) + 0.02, float(w.end)), 3),
                    }
                )

    total_dur_s = round(target_samples / float(SR), 4)
    segs = manifest.narration_segments
    seg_word_counts = [max(1, len(s.text.split())) for s in segs]
    total_manifest_wc = max(1, sum(seg_word_counts))

    # Partition ASR words cleanly across manifest segments using cumulative word proportions + sentence boundaries
    seg_records: list[dict[str, Any]] = []
    all_words: list[dict[str, Any]] = []
    n_asr = len(asr_words)
    cursor_idx = 0
    cum_wc = 0

    for s_idx, seg in enumerate(segs):
        cum_wc += seg_word_counts[s_idx]
        if s_idx == len(segs) - 1:
            end_idx = n_asr
        else:
            ideal_end = int(round((cum_wc / float(total_manifest_wc)) * n_asr))
            ideal_end = max(cursor_idx + 1, min(n_asr - (len(segs) - 1 - s_idx), ideal_end))
            # Snap to nearest punctuation/pause within +/-3 words for clean sentence boundaries
            best_idx = ideal_end
            best_score = -1.0
            for cand_i in range(max(cursor_idx + 1, ideal_end - 3), min(n_asr, ideal_end + 4)):
                prev_w = asr_words[cand_i - 1]
                gap = (asr_words[cand_i]["start"] - prev_w["end"]) if cand_i < n_asr else 0.3
                punct_bonus = 0.5 if str(prev_w["word"]).endswith((".", "?", "!")) else 0.0
                dist_pen = 0.06 * abs(cand_i - ideal_end)
                sc = gap + punct_bonus - dist_pen
                if sc > best_score:
                    best_score = sc
                    best_idx = cand_i
            end_idx = best_idx

        emph_norm = {re.sub(r"[^a-z0-9]", "", ew.lower()) for ew in seg.emphasis_words if ew}
        slice_words = asr_words[cursor_idx:end_idx] if n_asr > 0 else []
        cursor_idx = end_idx

        if slice_words:
            s0 = float(slice_words[0]["start"])
            s1 = float(slice_words[-1]["end"])
            for sw in slice_words:
                wn = re.sub(r"[^a-z0-9]", "", str(sw["word"]).lower())
                all_words.append(
                    {
                        "seg_id": seg.seg_id,
                        "word": sw["word"],
                        "start": sw["start"],
                        "end": sw["end"],
                        "emphasis": wn in emph_norm,
                    }
                )
        else:
            # Fallback proportional span if audio was ultra-short
            s0 = round(((cum_wc - seg_word_counts[s_idx]) / float(total_manifest_wc)) * total_dur_s, 3)
            s1 = round((cum_wc / float(total_manifest_wc)) * total_dur_s, 3)

        pause_after = 0.0
        if s_idx + 1 < len(segs) and cursor_idx < n_asr:
            pause_after = round(max(0.0, float(asr_words[cursor_idx]["start"]) - s1), 3)

        seg_records.append(
            {
                "seg_id": seg.seg_id,
                "text": seg.text,
                "rate": "uploaded_human",
                "pitch": "uploaded_human",
                "start": round(s0, 3),
                "end": round(s1, 3),
                "duration": round(max(0.05, s1 - s0), 3),
                "pause_after": pause_after,
                "emphasis_words": seg.emphasis_words,
            }
        )

    # Detect silence stretches in uploaded audio
    win = int(0.05 * SR)
    n_wins = max(1, len(mono_padded) // win)
    rms_env = np.sqrt(np.mean(mono_padded[: n_wins * win].reshape(n_wins, win) ** 2, axis=1))
    silent_mask = rms_env < 0.004
    pauses_s: list[float] = []
    run = 0
    for is_sil in silent_mask:
        if is_sil:
            run += 1
        elif run > 0:
            dur_p = run * 0.05
            if dur_p >= 0.15:
                pauses_s.append(round(dur_p, 3))
            run = 0

    wt_obj = {
        "voice": f"uploaded_narration:{uploaded_file.name}",
        "voice_input_mode": "uploaded_narration",
        "uploaded_source_file": str(uploaded_file.resolve()),
        "uploaded_audio_health": health_in,
        "detected_pause_count": len(pauses_s),
        "max_detected_pause_s": max(pauses_s) if pauses_s else 0.0,
        "total_duration_s": total_dur_s,
        "total_frames_30fps": total_frames,
        "segments": seg_records,
        "soundbites": [],
        "words": all_words,
    }
    (out_dir / "word_timings.json").write_text(json.dumps(wt_obj, indent=2), encoding="utf-8")
    return wt_obj


def _estimate_f0_autocorr(mono: np.ndarray) -> tuple[float, float]:
    """Estimate speaker median fundamental frequency `F0 (Hz)` & semitone IQR via autocorrelation."""
    frame_len = int(0.040 * SR)
    hop = int(0.020 * SR)
    min_lag = int(SR / 320.0)
    max_lag = int(SR / 70.0)
    f0s: list[float] = []

    for start in range(0, max(0, len(mono) - frame_len), hop):
        fr = mono[start : start + frame_len]
        rms = float(np.sqrt(np.mean(fr * fr)))
        if rms < 0.022:
            continue
        fr_w = (fr - float(np.mean(fr))) * np.hanning(len(fr))
        corr = np.correlate(fr_w, fr_w, mode="full")[len(fr_w) - 1 :]
        if corr[0] <= 1e-6:
            continue
        corr_norm = corr / corr[0]
        seg = corr_norm[min_lag:max_lag]
        if len(seg) == 0:
            continue
        pk_idx = int(np.argmax(seg)) + min_lag
        if corr_norm[pk_idx] >= 0.32:
            f0s.append(float(SR) / float(pk_idx))

    if not f0s:
        return (125.0, 2.5)
    arr = np.array(f0s, dtype=np.float64)
    med = float(np.median(arr))
    st = 12.0 * np.log2(np.maximum(arr, 1.0) / max(med, 1.0))
    iqr_st = float(np.percentile(st, 75) - np.percentile(st, 25))
    return (round(med, 1), round(iqr_st, 2))


def analyze_voice_reference(
    reference_audio_path: Path,
    voice_owner_consent: bool,
    profile_id: str = "custom_reference_profile",
    out_profile_yaml: Optional[Path] = None,
    local_cloning_endpoint_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Mode B — Uploaded Voice Reference Profiler & Lawful Local Capability Evaluator
    (Part 4, Section 5.1):
    1. Strictly enforces explicit `voice_owner_consent == True`.
    2. Extracts objective acoustic signature (`WPM`, `F0 Hz`, `pitch IQR`, `median pause ms`,
       `LUFS`, `LRA`) from the uploaded sample and writes a calibrated `VoiceDirectionProfile`.
    3. Probes optional local zero-shot cloning server (`local_cloning_endpoint_url`), reporting
       honestly when zero-shot neural voice cloning weights are not installed locally at `$0`.
    """
    if not voice_owner_consent:
        raise PermissionError(
            "Voice reference processing denied: explicit `voice_owner_consent=True` is mandatory. "
            "Never clone or adapt third-party voices without authorization."
        )
    if not reference_audio_path.exists():
        raise FileNotFoundError(f"Voice reference file not found: {reference_audio_path}")

    health = _probe_audio_health(reference_audio_path)
    tmp_wav = Path("/tmp") / f"_pow_ref_{hashlib.md5(str(reference_audio_path).encode()).hexdigest()[:10]}.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(reference_audio_path),
            "-t", "60",
            "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le",
            str(tmp_wav),
        ],
        check=True,
    )
    mono = _read_wav_mono_f32(tmp_wav)
    tmp_wav.unlink(missing_ok=True)

    median_f0_hz, pitch_iqr_st = _estimate_f0_autocorr(mono)

    model = _get_whisper_model("base.en")
    segs, _ = model.transcribe(str(reference_audio_path), language="en", word_timestamps=True)
    words = [w for s in segs for w in (s.words or []) if str(w.word).strip()]
    dur_min = max(1e-3, health["duration_s"] / 60.0)
    measured_wpm = round(len(words) / dur_min, 1) if words else 148.0

    gaps_ms = []
    for a, b in zip(words, words[1:]):
        g = (float(b.start) - float(a.end)) * 1000.0
        if 120.0 <= g <= 1800.0:
            gaps_ms.append(g)
    median_pause_ms = int(round(float(np.median(gaps_ms)))) if gaps_ms else 350

    # Calibrate profile parameters from speaker's real delivery cadence
    if measured_wpm < 138:
        spd: Literal["slow", "natural", "moderate", "fast"] = "slow"
        base_rate = -3
    elif measured_wpm <= 162:
        spd = "natural"
        base_rate = 0
    elif measured_wpm <= 178:
        spd = "moderate"
        base_rate = 2
    else:
        spd = "fast"
        base_rate = 4

    # Check if an optional local zero-shot cloning server (e.g. local MIT Chatterbox HTTP) is reachable
    cloning_server_reachable = False
    if local_cloning_endpoint_url:
        try:
            req = urllib.request.Request(local_cloning_endpoint_url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                cloning_server_reachable = resp.status < 500
        except Exception:
            cloning_server_reachable = False

    # Select closest natural preset voice register when zero-shot cloning server is absent
    recommended_preset_voice = "en-GB-RyanNeural" if median_f0_hz < 165.0 else "en-GB-SoniaNeural"

    metrics = {
        "source_file": reference_audio_path.name,
        "duration_s": health["duration_s"],
        "measured_wpm": measured_wpm,
        "median_f0_hz": median_f0_hz,
        "pitch_iqr_semitones": pitch_iqr_st,
        "median_pause_ms": median_pause_ms,
        "integrated_lufs": health["integrated_lufs"],
        "loudness_range_lu": health["loudness_range_lu"],
    }

    calibrated = VoiceDirectionProfile(
        profile_id=profile_id,
        display_name=f"Calibrated Reference ({reference_audio_path.stem})",
        description="Voice Direction Profile calibrated from owner-consented acoustic reference sample.",
        voice_mode="voice_reference",
        voice_identity=recommended_preset_voice,
        speaking_speed=spd,
        base_rate_pct=base_rate,
        base_pitch_hz=-1 if median_f0_hz < 115.0 else (1 if median_f0_hz > 145.0 and median_f0_hz < 165.0 else 0),
        default_pause_after_ms=max(200, min(700, median_pause_ms)),
        energy=4 if pitch_iqr_st >= 3.2 else 3,
        local_cloning_endpoint_url=local_cloning_endpoint_url,
        reference_acoustic_metrics=metrics,
    )

    if out_profile_yaml is not None:
        out_profile_yaml.parent.mkdir(parents=True, exist_ok=True)
        out_profile_yaml.write_text(
            yaml.safe_dump(calibrated.model_dump(), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    return {
        "consent_verified": True,
        "acoustic_metrics": metrics,
        "calibrated_profile": calibrated.model_dump(),
        "saved_profile_yaml": str(out_profile_yaml) if out_profile_yaml else None,
        "zero_shot_voice_cloning_active": cloning_server_reachable,
        "technical_capability_status": (
            "Local zero-shot voice cloning server reachable and enabled."
            if cloning_server_reachable
            else (
                "Honest $0 Local Capability Notice: `edge-tts` cannot clone timbre from reference audio, "
                "and zero-shot neural cloning weights (e.g., MIT Chatterbox / F5-TTS ~2-4 GB PyTorch/MLX) "
                "are not installed on disk. Measured speaker cadence, pause timing, energy, and register "
                "have been calibrated into a reusable `VoiceDirectionProfile`. For 100% authentic personal "
                "voice timbre at $0, use Mode A (`uploaded_narration`) or point `local_cloning_endpoint_url` "
                "to a local MIT Chatterbox server."
            )
        ),
    }


def _spectral_centroid_hz(samples: np.ndarray) -> float:
    """Compute speech-band spectral centroid (Hz) to detect timbre/quality shifts across joined segments."""
    active = samples[np.abs(samples) > 0.012]
    if len(active) < int(0.04 * SR):
        return 0.0
    mag = np.abs(np.fft.rfft(active))
    freqs = np.fft.rfftfreq(len(active), d=1.0 / SR)
    band = (freqs >= 90.0) & (freqs <= 6500.0)
    denom = float(np.sum(mag[band]))
    if denom < 1e-6:
        return 0.0
    return float(np.sum(freqs[band] * mag[band]) / denom)


def audit_narration_continuity(
    sentence_waveforms: list[np.ndarray],
    sentence_records: list[dict[str, Any]],
    pauses_s: list[float],
) -> dict[str, Any]:
    """
    Post-concatenation Audio Continuity Reviewer (Part 2, Section 4):
    Verifies consistent vocal timbre, natural volume across sentence joins, smooth unclipped
    word beginnings/endings, and natural inter-sentence pause durations.
    """
    rms_dbs: list[float] = []
    centroids: list[float] = []
    clipped_boundaries = 0
    join_audits: list[dict[str, Any]] = []
    issues: list[str] = []

    for idx, wav_arr in enumerate(sentence_waveforms):
        active = wav_arr[np.abs(wav_arr) > 0.012]
        rms_val = float(np.sqrt(np.mean(active * active))) if len(active) > 10 else 1e-4
        rms_dbs.append(20.0 * math.log10(max(1e-5, rms_val)))
        centroids.append(_spectral_centroid_hz(wav_arr))

        # Check very first & last 3ms for hard boundary clipping (> -26 dBFS abrupt edge)
        edge_n = min(int(0.003 * SR), max(1, len(wav_arr) // 8))
        if len(wav_arr) > 16:
            head_pk = float(np.max(np.abs(wav_arr[:edge_n])))
            tail_pk = float(np.max(np.abs(wav_arr[-edge_n:])))
            if head_pk > 0.055 or tail_pk > 0.055:
                clipped_boundaries += 1
                issues.append(
                    f"[sent #{idx}] Boundary micro-fade check flagged elevated edge amplitude (head={head_pk:.3f}, tail={tail_pk:.3f})."
                )

    max_rms_jump_db = 0.0
    max_centroid_ratio = 1.0
    unnatural_pause_count = 0

    for k in range(len(sentence_waveforms) - 1):
        rms_jump = abs(rms_dbs[k + 1] - rms_dbs[k])
        max_rms_jump_db = max(max_rms_jump_db, rms_jump)
        c0, c1 = centroids[k], centroids[k + 1]
        c_ratio = (max(c0, c1) / max(80.0, min(c0, c1))) if (c0 > 80.0 and c1 > 80.0) else 1.0
        max_centroid_ratio = max(max_centroid_ratio, c_ratio)
        pause_s = float(pauses_s[k]) if k < len(pauses_s) else 0.30

        if rms_jump > 4.2:
            issues.append(f"[join {k}->{k+1}] Audible volume jump of {rms_jump:.2f} dB between sentences.")
        if c_ratio > 1.65:
            issues.append(f"[join {k}->{k+1}] Spectral timbre shift ratio {c_ratio:.2f}x suggests inconsistent vocal tone.")
        if pause_s < 0.075 or pause_s > 1.45:
            unnatural_pause_count += 1
            issues.append(f"[join {k}->{k+1}] Unnatural inter-sentence pause ({pause_s*1000:.0f} ms).")

        join_audits.append(
            {
                "from_sentence": k,
                "to_sentence": k + 1,
                "rms_jump_db": round(rms_jump, 2),
                "spectral_centroid_ratio": round(c_ratio, 3),
                "pause_s": round(pause_s, 3),
            }
        )

    return {
        "segment_count": len(sentence_waveforms),
        "max_adjacent_rms_jump_db": round(max_rms_jump_db, 2),
        "max_spectral_centroid_ratio": round(max_centroid_ratio, 3),
        "clipped_word_boundaries_count": clipped_boundaries,
        "unnatural_pause_count": unnatural_pause_count,
        "continuity_pass": (
            max_rms_jump_db <= 4.5
            and max_centroid_ratio <= 1.75
            and clipped_boundaries == 0
            and unnatural_pause_count == 0
        ),
        "issues": issues,
        "joins": join_audits,
    }


def invalidate_dependent_timing_artifacts(
    out_dir: Path,
    previous_pron_sig: Optional[str],
    new_pron_sig: str,
) -> list[str]:
    """
    Part 2, Section 5: When narration is regenerated and its timing signature changes,
    automatically invalidate downstream timing-dependent artifacts and cached shot clips
    so every stage rebuilds cleanly against the new authoritative narration master.
    """
    if not previous_pron_sig or previous_pron_sig == new_pron_sig:
        return []

    stale_files = [
        "semantic_timeline_manifest.json",
        "unified_av_timeline.json",
        "unified_av_timeline.md",
        "soundscape_plan.json",
        "scene_optimization_report.json",
        "scene_optimization_report.md",
        "shot_plan_audit.json",
        "subtitles.srt",
        "voice_approval_lock.json",
        "qc_measurements.json",
        "creative_qa_report.json",
    ]
    invalidated: list[str] = []
    for rel in stale_files:
        fp = out_dir / rel
        if fp.exists():
            fp.unlink(missing_ok=True)
            invalidated.append(rel)

    shots_dir = out_dir / "shots"
    if shots_dir.exists():
        removed_shots = 0
        for mp4_p in shots_dir.glob("*.mp4"):
            mp4_p.unlink(missing_ok=True)
            removed_shots += 1
        if removed_shots > 0:
            invalidated.append(f"shots/*.mp4 ({removed_shots} cached clips)")

    return invalidated


def choose_narration_generation_strategy(
    resolved_list: list[ResolvedSentenceProsody],
    manifest: EpisodeManifest,
    active_provider: str,
    elevenlabs_model_id: str = "eleven_multilingual_v2",
) -> dict[str, Any]:
    """
    Decide between `single_request_whole_pass` vs `request_stitched_segmented` vs
    `prosody_matched_segmented` based on voice direction variance and model capabilities.
    """
    rates = {r.rate_str for r in resolved_list}
    pitches = {r.pitch_str for r in resolved_list}
    uniform_prosody = (len(rates) <= 1 and len(pitches) <= 1 and len(manifest.soundbites) == 0)

    if active_provider == "elevenlabs":
        caps = resolve_model_capabilities(elevenlabs_model_id)
        if manifest.prefer_single_pass_narration is True or (
            manifest.prefer_single_pass_narration is None and (uniform_prosody or caps.prefers_whole_or_paragraph_pass)
        ):
            return {
                "method": "single_request_whole_pass",
                "reason": f"{caps.model_id} produces highest acoustic continuity in a unified pass when prosody/tags fit one request.",
            }
        if caps.supports_request_stitching:
            return {
                "method": "elevenlabs_request_stitched_segmented",
                "reason": f"Distinct sentence delivery contrast requested; using {caps.model_id} previous_text/next_text + request-id continuity stitching.",
            }
        return {
            "method": "prosody_matched_segmented",
            "reason": f"Segmented synthesis with active RMS matching and cosine micro-fades for {caps.model_id}.",
        }

    if manifest.prefer_single_pass_narration is True or (uniform_prosody and len(resolved_list) <= 6):
        return {
            "method": "single_pass_or_uniform_cadence",
            "reason": "Uniform rate/pitch across script allows unified cadence without cross-style jumps.",
        }
    return {
        "method": "contrast_directed_rms_matched_segmented",
        "reason": "Multi-beat emotional contrast active; using bounded prosody + active RMS matching + raised-cosine fades + studio room-tone bed.",
    }


def synthesize_directed_narration(
    manifest: EpisodeManifest,
    reuse_existing_cache: bool = True,
) -> dict[str, Any]:
    """
    Synthesize complete episode narration using:
    - Model-capability-aware ElevenLabs engine when `ELEVENLABS_API_KEY` is configured and requested,
      OR `$0` neural `edge-tts` fallback.
    - Contrast & Anti-Overdrama voice direction rebalancing (`plan_and_rebalance_voice_direction`).
    - Raised-cosine boundary fades, RMS continuity matching, studio room-tone floor, transparent
      broadcast vocal EQ/compression (with legacy metallic `aecho` slapback removed!).
    - Post-concatenation `audit_narration_continuity()` + automatic SHA-256 dependent cache invalidation.
    """
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    work_dir = out_dir / "work_audio"
    cache_dir = work_dir / "sentence_cache"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)

    prev_wt_p = out_dir / "word_timings.json"
    prev_pron_sig: Optional[str] = None
    if prev_wt_p.exists():
        try:
            prev_pron_sig = json.loads(prev_wt_p.read_text(encoding="utf-8")).get("pronunciation_sig")
        except Exception:
            prev_pron_sig = None

    profile = load_voice_direction_profile(
        manifest.voice_direction_profile or style.sound_design.default_voice_profile
    )
    voice_id = manifest.voice or profile.voice_identity
    merged_pron = {**(profile.pronunciation or {}), **(manifest.tts_pronunciations or {})}
    _, rev_map = _apply_pronunciation_map("", merged_pron)

    raw_sentences = build_sentences_from_manifest(manifest)
    if manifest.legacy_v6_fallback:
        sentences = raw_sentences
        contrast_summary = {"legacy_v6_fallback": True}
    else:
        sentences, contrast_summary = plan_and_rebalance_voice_direction(raw_sentences, manifest=manifest)

    resolved_list = [
        resolve_sentence_prosody(s, profile, extra_pronunciations=manifest.tts_pronunciations, voice_override=voice_id)
        for s in sentences
    ]

    # Resolve active TTS provider honestly ($0 fallback when ELEVENLABS_API_KEY is absent)
    req_provider = manifest.tts_provider if manifest.tts_provider != "auto" else style.sound_design.tts_provider
    el_model_id = manifest.elevenlabs_model_id or style.sound_design.elevenlabs_model_id or "eleven_multilingual_v2"
    el_voice_id = (
        manifest.elevenlabs_voice_id
        or style.sound_design.elevenlabs_voice_id
        or DEFAULT_DOCUMENTARY_VOICE_IDS.get(profile.profile_id, DEFAULT_DOCUMENTARY_VOICE_IDS["cinematic_documentary"])
    )
    use_elevenlabs = (req_provider == "elevenlabs" and is_elevenlabs_configured()) or (
        req_provider == "auto" and is_elevenlabs_configured() and manifest.elevenlabs_voice_id != ""
    )
    active_provider = "elevenlabs" if use_elevenlabs else "edge_tts"
    strategy = choose_narration_generation_strategy(
        resolved_list, manifest, active_provider=active_provider, elevenlabs_model_id=el_model_id
    )

    voice_plan_path = out_dir / "voice_direction_plan.json"

    async def _run_synth() -> dict[str, Any]:
        lead_in_s = 0.10
        chunks: list[np.ndarray] = [np.zeros(int(lead_in_s * SR), dtype=np.float32)]
        cursor_s = lead_in_s

        sb_by_seg: dict[str, list[Any]] = {}
        for sb in manifest.soundbites:
            sb_by_seg.setdefault(sb.insert_after_seg_id, []).append(sb)
        soundbite_records: list[dict[str, Any]] = []

        sents_by_seg: dict[str, list[ResolvedSentenceProsody]] = {}
        for r in resolved_list:
            sents_by_seg.setdefault(r.seg_id, []).append(r)

        seg_records: list[dict[str, Any]] = []
        all_words: list[dict[str, Any]] = []
        sentence_records: list[dict[str, Any]] = []
        sentence_waveforms: list[np.ndarray] = []
        inter_sentence_pauses_s: list[float] = []
        prev_el_request_ids: list[str] = []
        el_payload_audits: list[dict[str, Any]] = []
        cache_hits = 0

        flat_idx = 0
        for seg in manifest.narration_segments:
            seg_sents = sents_by_seg.get(seg.seg_id, [])
            seg_start_s = cursor_s
            seg_last_speech_end_s = cursor_s
            seg_emph_norms = {re.sub(r"[^a-z0-9]", "", ew.lower()) for ew in seg.emphasis_words if ew}

            for s_idx, res in enumerate(seg_sents):
                if res.pause_before_ms > 0 and flat_idx > 0:
                    pre_s = res.pause_before_ms / 1000.0
                    chunks.append(np.zeros(int(round(pre_s * SR)), dtype=np.float32))
                    cursor_s += pre_s
                    if s_idx == 0:
                        seg_start_s = cursor_s

                if use_elevenlabs:
                    prev_txt = resolved_list[flat_idx - 1].spoken_tts_text if flat_idx > 0 else None
                    next_txt = resolved_list[flat_idx + 1].spoken_tts_text if flat_idx + 1 < len(resolved_list) else None
                    r_int = _parse_signed_int(res.rate_str, "%") or 0
                    el_payload, el_audit = build_elevenlabs_request_payload(
                        text=res.spoken_tts_text,
                        model_id=el_model_id,
                        rate_pct=r_int,
                        energy_level=res.energy_level,
                        delivery_label=res.delivery_label,
                        emotional_intensity=res.emotional_intensity,
                        vocal_consistency=res.vocal_consistency,
                        previous_text=prev_txt,
                        next_text=next_txt,
                        previous_request_ids=prev_el_request_ids,
                    )
                    el_payload_audits.append(el_audit)
                    el_ckey = hashlib.sha256(
                        json.dumps({"vid": el_voice_id, "p": el_payload}, sort_keys=True).encode("utf-8")
                    ).hexdigest()[:20]
                    wav_p = cache_dir / f"el_{el_ckey}.wav"
                    meta_p = cache_dir / f"el_{el_ckey}.json"
                    if reuse_existing_cache and wav_p.exists() and meta_p.exists():
                        cmeta = json.loads(meta_p.read_text(encoding="utf-8"))
                        words = cmeta.get("words", [])
                        hit = True
                    else:
                        cache_dir.mkdir(parents=True, exist_ok=True)
                        mp3_p = cache_dir / f"el_{el_ckey}.mp3"
                        el_res = synthesize_elevenlabs_segment(el_voice_id, el_payload, mp3_p)
                        if el_res.get("request_id"):
                            prev_el_request_ids.append(str(el_res["request_id"]))
                        subprocess.run(
                            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp3_p), "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(wav_p)],
                            check=True,
                        )
                        words = []
                        for ew in el_res.get("words", []):
                            raw_w = str(ew["word"])
                            wn_key = re.sub(r"[^a-z0-9']", "", raw_w.lower())
                            canon_w = rev_map.get(wn_key, raw_w)
                            words.append(
                                {
                                    "text": canon_w,
                                    "offset_s": float(ew["start"]),
                                    "duration_s": max(0.03, float(ew["end"]) - float(ew["start"])),
                                }
                            )
                        meta_p.write_text(json.dumps({"words": words}, indent=2), encoding="utf-8")
                        hit = False
                else:
                    # Also build dry-run capability audit so ElevenLabs settings are inspectable even in $0 mode
                    r_int = _parse_signed_int(res.rate_str, "%") or 0
                    _, el_audit = build_elevenlabs_request_payload(
                        text=res.spoken_tts_text,
                        model_id=el_model_id,
                        rate_pct=r_int,
                        energy_level=res.energy_level,
                        delivery_label=res.delivery_label,
                        emotional_intensity=res.emotional_intensity,
                        vocal_consistency=res.vocal_consistency,
                    )
                    el_payload_audits.append(el_audit)
                    wav_p, words, hit = await _synthesize_cached_sentence(
                        res,
                        rev_map,
                        cache_dir,
                        force_regenerate=not reuse_existing_cache,
                    )

                if hit:
                    cache_hits += 1
                raw = _read_wav_mono_f32(wav_p)
                trimmed, head_s = _trim_silence(raw)
                # Subtle energy-aware target RMS: calm/mysterious openings slightly softer (-1.0 dB) than reveals
                energy_rms_scale = 1.0 + 0.045 * (res.energy_level - 3)
                trimmed = _match_sentence_active_rms(trimmed, target_rms=0.094 * energy_rms_scale)
                sentence_waveforms.append(trimmed)

                dur_s = len(trimmed) / float(SR)
                s0, s1 = cursor_s, cursor_s + dur_s
                seg_last_speech_end_s = s1

                active_emph = seg_emph_norms | set(res.emphasis_word_norms)
                for w in words:
                    ws = max(s0, s0 + (float(w["offset_s"]) - head_s))
                    we = min(s1, ws + float(w["duration_s"]))
                    wnorm = re.sub(r"[^a-z0-9]", "", str(w["text"]).lower())
                    all_words.append(
                        {
                            "seg_id": seg.seg_id,
                            "word": w["text"],
                            "start": round(ws, 3),
                            "end": round(we, 3),
                            "emphasis": wnorm in active_emph,
                        }
                    )

                pause_s = res.pause_after_ms / 1000.0
                inter_sentence_pauses_s.append(pause_s)
                chunks.append(trimmed)
                chunks.append(np.zeros(int(round(pause_s * SR)), dtype=np.float32))
                cursor_s = s1 + pause_s

                sentence_records.append(
                    {
                        "sentence_index": res.sentence_index,
                        "seg_id": seg.seg_id,
                        "text": res.canonical_text,
                        "delivery": res.delivery_label,
                        "emotional_tone": res.emotional_tone,
                        "pace": res.pace_label,
                        "energy": res.energy_level,
                        "emotional_intensity": res.emotional_intensity,
                        "pitch_direction": res.pitch_direction,
                        "sentence_rhythm": res.sentence_rhythm,
                        "rate": res.rate_str,
                        "pitch": res.pitch_str,
                        "pause_before_ms": res.pause_before_ms,
                        "pause_after_ms": res.pause_after_ms,
                        "emphasis_phrases": res.emphasis_phrases,
                        "start_s": round(s0, 3),
                        "end_s": round(s1, 3),
                        "cache_key": res.cache_key,
                        "cache_hit": hit,
                        "elevenlabs_model_settings": el_audit["voice_settings"],
                        "applied_approximations": res.applied_approximations,
                    }
                )
                flat_idx += 1

            last_pause_s = (seg_sents[-1].pause_after_ms / 1000.0) if seg_sents else seg.pause_after_s
            seg_records.append(
                {
                    "seg_id": seg.seg_id,
                    "text": seg.text,
                    "delivery": seg_sents[0].delivery_label if seg_sents else (seg.delivery or "DEFAULT"),
                    "rate": seg_sents[0].rate_str if seg_sents else seg.rate,
                    "pitch": seg_sents[0].pitch_str if seg_sents else seg.pitch,
                    "start": round(seg_start_s, 3),
                    "end": round(seg_last_speech_end_s, 3),
                    "duration": round(max(0.01, seg_last_speech_end_s - seg_start_s), 3),
                    "pause_after": round(last_pause_s, 3),
                    "emphasis_words": seg.emphasis_words,
                }
            )

            # Optional authentic scientist/field soundbites
            for sb in sb_by_seg.get(seg.seg_id, []):
                sb_src = next(
                    (d / sb.audio_file for d in manifest.all_asset_search_dirs() if (d / sb.audio_file).exists()),
                    Path(sb.audio_file),
                )
                sb_wav = work_dir / f"sb_{sb.bite_id}.wav"
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{sb.src_start_s:.3f}", "-to", f"{sb.src_end_s:.3f}",
                        "-i", str(sb_src),
                        "-af", "highpass=f=120,lowpass=f=7200,loudnorm=I=-16.0:TP=-1.5:LRA=8.0",
                        "-ar", str(SR), "-ac", "1", "-c:a", "pcm_s16le", str(sb_wav),
                    ],
                    check=True,
                )
                sb_arr = _read_wav_mono_f32(sb_wav)
                sb_dur = len(sb_arr) / float(SR)
                b0, b1 = cursor_s, cursor_s + sb_dur
                soundbite_records.append(
                    {
                        "bite_id": sb.bite_id,
                        "speaker_name": sb.speaker_name,
                        "speaker_role": sb.speaker_role,
                        "context_label": sb.context_label,
                        "verbatim_transcript": sb.verbatim_transcript,
                        "start": round(b0, 3),
                        "end": round(b1, 3),
                    }
                )
                chunks.append(sb_arr)
                chunks.append(np.zeros(int(sb.pause_after_s * SR), dtype=np.float32))
                cursor_s = b1 + sb.pause_after_s

        # Post-concatenation Audio Continuity Review (Part 2, Section 4)
        continuity_report = audit_narration_continuity(
            sentence_waveforms=sentence_waveforms,
            sentence_records=sentence_records,
            pauses_s=inter_sentence_pauses_s[:-1] if inter_sentence_pauses_s else [],
        )
        (out_dir / "voice_continuity_report.json").write_text(
            json.dumps(continuity_report, indent=2), encoding="utf-8"
        )

        full = np.concatenate(chunks)
        total_frames = int(round((len(full) / float(SR)) * FPS))
        target_samples = int(round((total_frames / float(FPS)) * SR))
        if len(full) < target_samples:
            full = np.pad(full, (0, target_samples - len(full)))
        else:
            full = full[:target_samples]

        # Continuous warm studio room-tone floor (-52 dBFS) across joins so background air never drops to 0.0000
        rt_rng = np.random.default_rng(20261029)
        freqs = np.fft.rfftfreq(len(full), d=1.0 / SR)
        wn_spec = np.fft.rfft(rt_rng.standard_normal(len(full)).astype(np.float32))
        hp = 1.0 / np.sqrt(1.0 + (95.0 / np.maximum(freqs, 1e-2)) ** 6)
        lp = 1.0 / np.sqrt(1.0 + (freqs / 950.0) ** 6)
        room_tone = np.fft.irfft(wn_spec * hp * lp, n=len(full)).astype(np.float32)
        room_tone /= max(1e-6, float(np.max(np.abs(room_tone))))
        rt_amp = float(10.0 ** (style.sound_design.studio_room_tone_dbfs / 20.0))
        full_with_room = full + room_tone * rt_amp

        raw_wav = work_dir / "narration_raw.wav"
        narr_norm_wav = work_dir / "narration_norm.wav"
        _write_wav_stereo(raw_wav, np.stack([full_with_room, full_with_room], axis=1))

        # Studio v7 transparent broadcast vocal chain: clean highpass + warm chest presence +
        # gentle sibilance control + transparent low-ratio optical-style compression (NO metallic aecho!)
        if style.sound_design.enable_broadcast_vocal_mastering and not manifest.legacy_v6_fallback:
            vocal_af = (
                "highpass=f=80,"
                "equalizer=f=160:t=q:w=1.1:g=1.2,"
                "equalizer=f=2950:t=q:w=1.3:g=0.7,"
                "equalizer=f=5400:t=q:w=2.0:g=-1.8,"
                "acompressor=threshold=-21dB:ratio=1.85:attack=18:release=190:makeup=1.0dB,"
                "loudnorm=I=-16.0:TP=-1.5:LRA=11.0"
            )
        elif style.sound_design.enable_broadcast_vocal_mastering and manifest.legacy_v6_fallback:
            vocal_af = (
                "highpass=f=82,"
                "equalizer=f=168:t=q:w=1.1:g=1.6,"
                "equalizer=f=3150:t=q:w=1.4:g=0.8,"
                "equalizer=f=4850:t=q:w=1.8:g=-2.2,"
                "acompressor=threshold=-20dB:ratio=2.0:attack=14:release=160:makeup=1.2dB,"
                "aecho=0.88:0.88:16:0.042,"
                "loudnorm=I=-16.0:TP=-1.5:LRA=10.5"
            )
        else:
            vocal_af = "loudnorm=I=-16.0:TP=-1.5:LRA=11.0"

        subprocess.run(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", str(raw_wav),
                "-af", vocal_af,
                "-ar", str(SR), "-ac", "2", "-c:a", "pcm_s16le",
                str(narr_norm_wav),
            ],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(narr_norm_wav), "-c:a", "libmp3lame", "-b:a", "256k", str(out_dir / "narration.mp3")],
            check=True,
        )

        pron_sig = hashlib.sha256(
            json.dumps(
                {
                    "provider": active_provider,
                    "voice": el_voice_id if use_elevenlabs else voice_id,
                    "profile": profile.profile_id,
                    "keys": [r.cache_key for r in resolved_list],
                    "pauses_before": [r.pause_before_ms for r in resolved_list],
                    "pauses_after": [r.pause_after_ms for r in resolved_list],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()

        invalidated_artifacts = invalidate_dependent_timing_artifacts(out_dir, prev_pron_sig, pron_sig)

        voice_plan = {
            "slug": manifest.slug,
            "active_tts_provider": active_provider,
            "elevenlabs_configured": is_elevenlabs_configured(),
            "elevenlabs_target_model": el_model_id,
            "segmentation_strategy": strategy,
            "voice_input_mode": manifest.voice_input_mode,
            "voice_direction_profile": profile.profile_id,
            "voice_identity": el_voice_id if use_elevenlabs else voice_id,
            "sentence_count": len(sentence_records),
            "sentence_cache_hits": cache_hits,
            "contrast_guardrail_summary": contrast_summary,
            "continuity_review": continuity_report,
            "invalidated_stale_artifacts_on_regeneration": invalidated_artifacts,
            "supported_controls": [
                "elevenlabs_model_capability_aware_settings",
                "elevenlabs_request_stitching_when_supported",
                "sentence_level_speaking_rate_bounded",
                "sentence_level_pitch_bounded",
                "pre_and_post_sentence_pause_ms",
                "custom_pronunciation_dictionary",
                "anti_overdrama_contrast_rebalancer",
                "post_concatenation_continuity_reviewer",
                "automatic_dependent_cache_invalidation",
            ],
            "engine_limitations": (
                ["ElevenLabs API active with model-specific voice_settings."]
                if use_elevenlabs
                else [
                    "ELEVENLABS_API_KEY not set in environment; running $0 neural edge-tts fallback while preserving full ElevenLabs model-specific voice_settings payloads.",
                    "edge-tts does not support zero-shot voice cloning from audio samples.",
                ]
            ),
            "sentences": sentence_records,
        }
        voice_plan_path.write_text(json.dumps(voice_plan, indent=2), encoding="utf-8")

        wt_obj = {
            "voice": el_voice_id if use_elevenlabs else voice_id,
            "active_tts_provider": active_provider,
            "segmentation_method": strategy["method"],
            "voice_input_mode": manifest.voice_input_mode,
            "voice_direction_profile": profile.profile_id,
            "pronunciation_sig": pron_sig,
            "total_duration_s": round(len(full) / float(SR), 4),
            "total_frames_30fps": total_frames,
            "continuity_review": continuity_report,
            "contrast_summary": contrast_summary,
            "invalidated_artifacts": invalidated_artifacts,
            "segments": seg_records,
            "sentences": sentence_records,
            "soundbites": soundbite_records,
            "words": all_words,
        }
        (out_dir / "word_timings.json").write_text(json.dumps(wt_obj, indent=2), encoding="utf-8")
        return wt_obj

    return asyncio.run(_run_synth())


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def approve_and_lock_voice_master(manifest: EpisodeManifest, reviewer_note: str = "Approved as authoritative timing master") -> dict[str, Any]:
    """
    Lock the approved narration track (`narration_norm.wav` + `word_timings.json` + script text)
    via SHA-256 checksums so Stage 5 Editing uses the exact approved voice master (Part 4, Section 5.3).
    """
    out_dir = Path(manifest.output_dir)
    wt_p = out_dir / "word_timings.json"
    wav_p = out_dir / "work_audio" / "narration_norm.wav"
    if not wt_p.exists() or not wav_p.exists():
        raise FileNotFoundError("Cannot lock voice master before generating/ingesting narration (`word_timings.json` & `narration_norm.wav`).")

    script_blob = "\n".join(f"{s.seg_id}:{s.text}" for s in manifest.narration_segments)
    lock_obj = {
        "slug": manifest.slug,
        "script_version": manifest.script_version,
        "voice_input_mode": manifest.voice_input_mode,
        "voice_direction_profile": manifest.voice_direction_profile or "cinematic_documentary",
        "approved_at_utc": datetime.now(timezone.utc).isoformat(),
        "reviewer_note": reviewer_note,
        "script_sha256": hashlib.sha256(script_blob.encode("utf-8")).hexdigest(),
        "narration_norm_wav_sha256": _sha256_file(wav_p),
        "word_timings_sha256": _sha256_file(wt_p),
    }
    lock_p = out_dir / "voice_approval_lock.json"
    lock_p.write_text(json.dumps(lock_obj, indent=2), encoding="utf-8")
    return lock_obj


def verify_voice_approval_lock(manifest: EpisodeManifest) -> dict[str, Any]:
    """Verify whether `voice_approval_lock.json` exists and matches current script & audio."""
    out_dir = Path(manifest.output_dir)
    lock_p = out_dir / "voice_approval_lock.json"
    wt_p = out_dir / "word_timings.json"
    wav_p = out_dir / "work_audio" / "narration_norm.wav"
    if not lock_p.exists():
        return {"locked": False, "synchronized": False, "detail": "No voice_approval_lock.json written yet."}
    if not wt_p.exists() or not wav_p.exists():
        return {"locked": True, "synchronized": False, "detail": "Narration audio or word_timings.json missing."}

    lock = json.loads(lock_p.read_text(encoding="utf-8"))
    script_blob = "\n".join(f"{s.seg_id}:{s.text}" for s in manifest.narration_segments)
    cur_script_sha = hashlib.sha256(script_blob.encode("utf-8")).hexdigest()
    cur_wav_sha = _sha256_file(wav_p)
    cur_wt_sha = _sha256_file(wt_p)

    synced = (
        lock.get("script_sha256") == cur_script_sha
        and lock.get("narration_norm_wav_sha256") == cur_wav_sha
        and lock.get("word_timings_sha256") == cur_wt_sha
    )
    return {
        "locked": True,
        "synchronized": synced,
        "approved_at_utc": lock.get("approved_at_utc"),
        "script_matches": lock.get("script_sha256") == cur_script_sha,
        "audio_matches": lock.get("narration_norm_wav_sha256") == cur_wav_sha,
        "timings_matches": lock.get("word_timings_sha256") == cur_wt_sha,
    }
