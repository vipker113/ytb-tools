#!/usr/bin/env python3
"""
Part 2 (Sections 3–5): Model-Capability-Aware ElevenLabs Voice Production Provider
(`pow_studio.elevenlabs_provider` v7.0).

Key engineering & creative principles:
1. Never assumes every ElevenLabs model supports identical `voice_settings`, `[audio_tags]`,
   request-stitching parameters (`previous_text`/`next_text`), or discrete stability modes.
2. Strictly enforces documentary restraint: blocks whispering, shouting, exaggerated excitement,
   or theatrical `[audio_tags]`, and caps `style` exaggeration (`<= 0.30`) on models that support it.
3. Supports both whole-narration single-request synthesis (when voice direction is compatible or
   when model continuity requires it, e.g., `eleven_v3`) and request-stitched segmented synthesis
   (`previous_text`, `next_text`, `previous_request_ids`) with character-to-word timestamp decoding.
4. Budget-safe (`$0` default): Only contacts `api.elevenlabs.io` when `ELEVENLABS_API_KEY` is
   explicitly configured by the user; otherwise falls back cleanly to local `$0` providers.
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class ElevenLabsModelCapabilities:
    model_id: str
    display_name: str
    supports_stability: bool
    discrete_stability_values: Optional[tuple[float, ...]]
    supports_similarity_boost: bool
    supports_style: bool
    max_recommended_documentary_style: float
    supports_speaker_boost: bool
    supports_speed: bool
    speed_range: tuple[float, float]
    supports_request_stitching: bool
    supports_inline_audio_tags: bool
    supports_language_code: bool
    supports_with_timestamps: bool
    prefers_whole_or_paragraph_pass: bool
    notes: str


ELEVENLABS_MODEL_CAPABILITIES: dict[str, ElevenLabsModelCapabilities] = {
    "eleven_multilingual_v2": ElevenLabsModelCapabilities(
        model_id="eleven_multilingual_v2",
        display_name="Eleven Multilingual v2 (High-Fidelity Documentary Narration)",
        supports_stability=True,
        discrete_stability_values=None,
        supports_similarity_boost=True,
        supports_style=True,
        max_recommended_documentary_style=0.28,
        supports_speaker_boost=True,
        supports_speed=True,
        speed_range=(0.75, 1.18),
        supports_request_stitching=True,
        supports_inline_audio_tags=False,
        supports_language_code=False,
        supports_with_timestamps=True,
        prefers_whole_or_paragraph_pass=False,
        notes="Supports previous_text/next_text + previous_request_ids continuity stitching; strips inline [audio_tags].",
    ),
    "eleven_v3": ElevenLabsModelCapabilities(
        model_id="eleven_v3",
        display_name="Eleven v3 (Expressive Context-Aware Documentary Model)",
        supports_stability=True,
        discrete_stability_values=(0.0, 0.5, 1.0),
        supports_similarity_boost=True,
        supports_style=False,
        max_recommended_documentary_style=0.0,
        supports_speaker_boost=False,
        supports_speed=True,
        speed_range=(0.75, 1.18),
        supports_request_stitching=False,
        supports_inline_audio_tags=True,
        supports_language_code=True,
        supports_with_timestamps=True,
        prefers_whole_or_paragraph_pass=True,
        notes="Uses discrete stability (0.5 Natural / 1.0 Robust), supports restrained inline tags, prefers paragraph/whole-pass context.",
    ),
    "eleven_turbo_v2_5": ElevenLabsModelCapabilities(
        model_id="eleven_turbo_v2_5",
        display_name="Eleven Turbo v2.5 (Balanced Quality & Speed)",
        supports_stability=True,
        discrete_stability_values=None,
        supports_similarity_boost=True,
        supports_style=True,
        max_recommended_documentary_style=0.22,
        supports_speaker_boost=True,
        supports_speed=True,
        speed_range=(0.75, 1.18),
        supports_request_stitching=True,
        supports_inline_audio_tags=False,
        supports_language_code=True,
        supports_with_timestamps=True,
        prefers_whole_or_paragraph_pass=False,
        notes="Supports continuity stitching and language_code; strips inline [audio_tags].",
    ),
    "eleven_flash_v2_5": ElevenLabsModelCapabilities(
        model_id="eleven_flash_v2_5",
        display_name="Eleven Flash v2.5 (Low-Latency Draft & Rapid Preview)",
        supports_stability=True,
        discrete_stability_values=None,
        supports_similarity_boost=True,
        supports_style=False,
        max_recommended_documentary_style=0.0,
        supports_speaker_boost=False,
        supports_speed=True,
        speed_range=(0.75, 1.18),
        supports_request_stitching=True,
        supports_inline_audio_tags=False,
        supports_language_code=True,
        supports_with_timestamps=True,
        prefers_whole_or_paragraph_pass=True,
        notes="Does NOT support style or use_speaker_boost; omits those fields cleanly.",
    ),
}

# Theatrical / melodramatic tags strictly forbidden in Proof of Wonder documentaries
FORBIDDEN_THEATRICAL_AUDIO_TAGS = {
    "whisper",
    "whispering",
    "whispers",
    "shout",
    "shouting",
    "yell",
    "yelling",
    "scream",
    "screaming",
    "cry",
    "crying",
    "sob",
    "sobbing",
    "laugh",
    "laughing",
    "giggle",
    "gasp",
    "gasps",
    "panting",
    "excitedly",
    "hype",
}

ALLOWED_RESTRAINED_V3_TAGS = {
    "thoughtful",
    "curious",
    "calm",
    "measured",
    "serious",
    "reflective",
}

# Curated default ElevenLabs documentary voice IDs if user has ELEVENLABS_API_KEY set
# but omits an explicit voice_id in the episode YAML.
DEFAULT_DOCUMENTARY_VOICE_IDS: dict[str, str] = {
    "cinematic_documentary": "onwK4e9ZLuTAKqWW03F9",  # Daniel — British authoritative documentary
    "mysterious_discovery": "onwK4e9ZLuTAKqWW03F9",
    "scientific_authority": "JBFqnCBsd6RMkjVDRZzb",   # George — Warm British narrator
    "dramatic_reveal": "onwK4e9ZLuTAKqWW03F9",
    "calm_exploration": "JBFqnCBsd6RMkjVDRZzb",
    "urgent_discovery": "onwK4e9ZLuTAKqWW03F9",
    "emotional_reflection": "JBFqnCBsd6RMkjVDRZzb",
}


def get_elevenlabs_api_key() -> str:
    """Resolve `ELEVENLABS_API_KEY` from environment without hardcoding secrets."""
    return (os.environ.get("ELEVENLABS_API_KEY") or "").strip()


def is_elevenlabs_configured() -> bool:
    return bool(get_elevenlabs_api_key())


def resolve_model_capabilities(model_id: str) -> ElevenLabsModelCapabilities:
    mid = (model_id or "eleven_multilingual_v2").strip()
    if mid in ELEVENLABS_MODEL_CAPABILITIES:
        return ELEVENLABS_MODEL_CAPABILITIES[mid]
    # Conservative safe fallback for unknown future model IDs: omit style/tags/speaker_boost
    return ElevenLabsModelCapabilities(
        model_id=mid,
        display_name=f"Custom ElevenLabs Model ({mid})",
        supports_stability=True,
        discrete_stability_values=None,
        supports_similarity_boost=True,
        supports_style=False,
        max_recommended_documentary_style=0.0,
        supports_speaker_boost=False,
        supports_speed=True,
        speed_range=(0.80, 1.15),
        supports_request_stitching=False,
        supports_inline_audio_tags=False,
        supports_language_code=False,
        supports_with_timestamps=True,
        prefers_whole_or_paragraph_pass=True,
        notes="Unknown model ID: conservatively omits model-specific style/stitching/inline-tags.",
    )


def sanitize_text_for_elevenlabs_model(
    text: str,
    caps: ElevenLabsModelCapabilities,
    delivery_label: str = "MEASURED_EVIDENCE",
) -> tuple[str, list[str]]:
    """
    Ensure inline bracket tags match model capabilities and documentary anti-overdrama rules:
    - Non-v3 models: strip ALL `[tag]` inline audio markers so TTS never speaks them literally.
    - `eleven_v3`: strip forbidden theatrical tags (`[whispering]`, `[shouting]`, etc.) and retain
      only restrained documentary tags when appropriate.
    """
    notes: list[str] = []

    def _tag_repl(match: re.Match[str]) -> str:
        raw_tag = match.group(1).strip().lower()
        if not caps.supports_inline_audio_tags:
            notes.append(f"Stripped inline tag '[{raw_tag}]' (unsupported by {caps.model_id})")
            return ""
        if raw_tag in FORBIDDEN_THEATRICAL_AUDIO_TAGS:
            notes.append(f"Blocked theatrical tag '[{raw_tag}]' per documentary restraint rule")
            return ""
        if raw_tag in ALLOWED_RESTRAINED_V3_TAGS:
            return f"[{raw_tag}]"
        notes.append(f"Omitted non-standard inline tag '[{raw_tag}]'")
        return ""

    cleaned = re.sub(r"\[([A-Za-z_\-\s]{2,28})\]", _tag_repl, text)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    # Optional subtle v3 cue only on calm/reflective/mysterious lines if none present
    if caps.supports_inline_audio_tags and "[" not in cleaned:
        dl = delivery_label.upper().replace(" ", "_")
        if dl in ("EMOTIONAL_REFLECTION", "QUIET_RESONANCE", "FINAL_IMPRESSION"):
            cleaned = f"[thoughtful] {cleaned}"
            notes.append("Applied restrained v3 '[thoughtful]' cue")
        elif dl in ("MYSTERIOUS", "CALM_EXPLORATION"):
            cleaned = f"[calm] {cleaned}"
            notes.append("Applied restrained v3 '[calm]' cue")

    return cleaned, notes


def map_direction_to_elevenlabs_voice_settings(
    caps: ElevenLabsModelCapabilities,
    rate_pct: int = 0,
    energy_level: int = 3,
    delivery_label: str = "MEASURED_EVIDENCE",
    emotional_intensity: Optional[float] = None,
    vocal_consistency: str = "locked",
) -> tuple[dict[str, Any], list[str]]:
    """
    Translate sentence/segment voice direction into exact model-valid `voice_settings`.
    Never sends unsupported fields (e.g., `style` on `eleven_flash_v2_5` or `eleven_v3`).
    """
    dl = delivery_label.upper().replace(" ", "_")
    notes: list[str] = []
    settings: dict[str, Any] = {}

    # 1. Stability: higher for vocal_consistency=="locked" and scientific explanation;
    #    moderately expressive (but never erratic) for discovery/reveal moments.
    base_stab = 0.64 if vocal_consistency == "locked" else 0.54
    if dl in ("SCIENTIFIC_AUTHORITY", "MEASURED_EVIDENCE", "CLEAR_MECHANISM", "CAVEAT", "HONEST_CAVEAT"):
        raw_stab = base_stab + 0.08
    elif dl in ("CINEMATIC_REVEAL", "DRAMATIC_REVEAL", "URGENT_DISCOVERY"):
        raw_stab = base_stab - 0.06
    else:
        raw_stab = base_stab
    raw_stab = max(0.42, min(0.85, raw_stab))

    if caps.supports_stability:
        if caps.discrete_stability_values:
            snapped = min(caps.discrete_stability_values, key=lambda v: abs(v - raw_stab))
            # Avoid 0.0 ("Creative") for documentary voice consistency unless explicitly unlocked
            if snapped == 0.0 and vocal_consistency == "locked":
                snapped = 0.5
            settings["stability"] = float(snapped)
            notes.append(f"Snapped stability {raw_stab:.2f} -> discrete {snapped:.1f} for {caps.model_id}")
        else:
            settings["stability"] = round(raw_stab, 3)

    # 2. Similarity boost: preserve consistent narrator identity across segments
    if caps.supports_similarity_boost:
        settings["similarity_boost"] = 0.80 if vocal_consistency == "locked" else 0.74

    # 3. Style exaggeration (ONLY on models supporting it, strictly capped <= max_recommended_documentary_style)
    if caps.supports_style:
        if emotional_intensity is not None:
            raw_style = float(emotional_intensity) * caps.max_recommended_documentary_style
        else:
            energy_norm = max(0.0, min(1.0, (energy_level - 1) / 4.0))
            raw_style = (0.06 + 0.18 * energy_norm)
            if dl in ("MEASURED_EVIDENCE", "SCIENTIFIC_AUTHORITY", "CALM_EXPLANATION"):
                raw_style = min(raw_style, 0.10)
        settings["style"] = round(min(caps.max_recommended_documentary_style, max(0.0, raw_style)), 3)
    else:
        notes.append(f"Omitted 'style' (not supported by {caps.model_id})")

    # 4. Speaker boost
    if caps.supports_speaker_boost:
        settings["use_speaker_boost"] = True

    # 5. Speaking speed (bounded to natural documentary range)
    if caps.supports_speed:
        lo, hi = caps.speed_range
        speed_val = 1.0 + (float(rate_pct) / 100.0)
        clamped_speed = round(max(lo, min(hi, speed_val)), 3)
        settings["speed"] = clamped_speed

    return settings, notes


def build_elevenlabs_request_payload(
    text: str,
    model_id: str = "eleven_multilingual_v2",
    rate_pct: int = 0,
    energy_level: int = 3,
    delivery_label: str = "MEASURED_EVIDENCE",
    emotional_intensity: Optional[float] = None,
    vocal_consistency: str = "locked",
    previous_text: Optional[str] = None,
    next_text: Optional[str] = None,
    previous_request_ids: Optional[list[str]] = None,
    language_code: Optional[str] = "en",
    pronunciation_dictionary_locators: Optional[list[dict[str, str]]] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Construct a verified JSON request body for ElevenLabs TTS, returning `(payload, audit_metadata)`.
    """
    caps = resolve_model_capabilities(model_id)
    clean_text, text_notes = sanitize_text_for_elevenlabs_model(text, caps, delivery_label=delivery_label)
    v_settings, setting_notes = map_direction_to_elevenlabs_voice_settings(
        caps=caps,
        rate_pct=rate_pct,
        energy_level=energy_level,
        delivery_label=delivery_label,
        emotional_intensity=emotional_intensity,
        vocal_consistency=vocal_consistency,
    )

    payload: dict[str, Any] = {
        "text": clean_text,
        "model_id": caps.model_id,
        "voice_settings": v_settings,
    }

    stitching_used = False
    if caps.supports_request_stitching:
        if previous_text:
            payload["previous_text"] = previous_text[-480:]
            stitching_used = True
        if next_text:
            payload["next_text"] = next_text[:480]
            stitching_used = True
        if previous_request_ids:
            payload["previous_request_ids"] = list(previous_request_ids[-3:])
            stitching_used = True

    if caps.supports_language_code and language_code:
        payload["language_code"] = language_code

    if pronunciation_dictionary_locators:
        payload["pronunciation_dictionary_locators"] = pronunciation_dictionary_locators

    audit = {
        "model_id": caps.model_id,
        "model_display_name": caps.display_name,
        "capabilities": asdict(caps),
        "stitching_used": stitching_used,
        "applied_notes": text_notes + setting_notes,
        "voice_settings": v_settings,
    }
    return payload, audit


def decode_elevenlabs_char_alignment_to_words(alignment: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert ElevenLabs `/with-timestamps` character alignment arrays
    (`characters`, `character_start_times_seconds`, `character_end_times_seconds`)
    into word-level `{word, start, end}` entries.
    """
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    n = min(len(chars), len(starts), len(ends))
    words: list[dict[str, Any]] = []
    cur_chars: list[str] = []
    w_start: Optional[float] = None
    w_end: float = 0.0

    for i in range(n):
        ch = str(chars[i])
        st = float(starts[i])
        en = float(ends[i])
        if ch.isspace():
            if cur_chars and w_start is not None:
                words.append({"word": "".join(cur_chars), "start": round(w_start, 4), "end": round(w_end, 4)})
                cur_chars = []
                w_start = None
        else:
            if w_start is None:
                w_start = st
            cur_chars.append(ch)
            w_end = max(w_end, en)

    if cur_chars and w_start is not None:
        words.append({"word": "".join(cur_chars), "start": round(w_start, 4), "end": round(w_end, 4)})
    return words


def synthesize_elevenlabs_segment(
    voice_id: str,
    payload: dict[str, Any],
    out_mp3_path: Path,
    api_key: Optional[str] = None,
    output_format: str = "mp3_44100_192",
    timeout_s: float = 45.0,
) -> dict[str, Any]:
    """
    Execute a live ElevenLabs `/with-timestamps` synthesis request when `ELEVENLABS_API_KEY` is provided.
    Captures `request-id` response headers for multi-segment continuity stitching and decodes exact
    character-level timestamps.
    """
    key = (api_key or get_elevenlabs_api_key()).strip()
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set; refusing unauthenticated ElevenLabs call.")

    vid = voice_id.strip() or DEFAULT_DOCUMENTARY_VOICE_IDS["cinematic_documentary"]
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps?output_format={output_format}"
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body_bytes,
        method="POST",
        headers={
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            req_id = resp.headers.get("request-id") or resp.headers.get("x-request-id") or ""
            resp_obj = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"ElevenLabs API HTTP {exc.code}: {detail}") from exc

    audio_b64 = resp_obj.get("audio_base64") or ""
    if not audio_b64:
        raise RuntimeError("ElevenLabs /with-timestamps returned empty audio_base64.")
    out_mp3_path.parent.mkdir(parents=True, exist_ok=True)
    out_mp3_path.write_bytes(base64.b64decode(audio_b64))

    alignment = resp_obj.get("normalized_alignment") or resp_obj.get("alignment") or {}
    words = decode_elevenlabs_char_alignment_to_words(alignment)
    return {
        "audio_path": str(out_mp3_path),
        "request_id": req_id,
        "words": words,
        "voice_id": vid,
        "model_id": payload.get("model_id", ""),
    }
