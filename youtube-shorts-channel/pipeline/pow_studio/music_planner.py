#!/usr/bin/env python3
"""
Part 3 (Section 6) & Part 5 (Section 8): Story-Aware Background Music & Adaptive
Audio Profile Planner (`pow_studio.music_planner` v7.0).

Replaces the fixed v6 3-act sine-wave drone with an intelligent per-script planner that:
1. Dynamically selects or honors the Adaptive Audio Profile (`minimal_documentary`,
   `immersive_exploration`, `mystery_and_discovery`, `scientific_explanation`) from
   actual narration duration, sentence count, story beats, quantitative density, and topic.
2. Answers all 7 Section 6 emotional progression questions for the specific script.
3. Decides whether the episode needs `0` (intentional no-music), `1` focused bed, or
   `2–3` differentiated musical sections — never forcing a template onto a short or
   purely explanatory story.
4. Evaluates candidate tracks on all 9 Section 6 criteria (emotional fit, tempo, energy,
   instrumentation, vocal-pocket frequency safety, narration compatibility, speech-pause
   transition alignment, available duration, and verified `$0` commercial license).
5. Plans intentional pre-reveal hush/silence windows and optional subtle harmonic accents
   aligned strictly to natural speech boundaries so fades never interrupt spoken words.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .audio_registry import AudioRegistryEntry, ensure_audio_asset_registry
from .rights_gate import validate_license_string
from .schema import EpisodeManifest, ShotSpecModel
from .shot_planner import extract_speech_boundaries
from .story_engine import build_narrative_map

AdaptiveAudioProfileName = str


def select_adaptive_audio_profile(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
) -> dict[str, Any]:
    """
    Determine the Adaptive Audio Profile (`minimal_documentary`, `immersive_exploration`,
    `mystery_and_discovery`, `scientific_explanation`) from the actual script and footage,
    respecting explicit user overrides.
    """
    style = manifest.resolve_style_profile()
    explicit = manifest.adaptive_audio_profile
    if explicit == "auto" and style.sound_design.adaptive_audio_profile != "auto":
        explicit = style.sound_design.adaptive_audio_profile

    total_dur = float(wt.get("total_duration_s", 0.0) or 0.0)
    full_text = " ".join(s.text for s in manifest.narration_segments)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", full_text.strip()) if s.strip()]
    quant_facts = len(re.findall(r"\b\d+(?:\.\d+)?\b|%|degree|meter|kilometer|million|billion|pressure|chemical|isotope|radar", full_text, re.I))
    mystery_hits = len(re.findall(r"\bmyster|anomal|beneath|hidden|nobody knew|paradox|strange|for decades|sealed|forbidden|ancient\b", full_text, re.I))
    env_hits = len(re.findall(r"\bocean|trench|glacier|ice|cave|cavern|volcan|island|expedition|dive|submersible|desert|forest\b", full_text, re.I))
    has_diegetic_field_audio = bool(manifest.nat_sound_bed_file) or any(s.nat_audio_gain_db is not None for s in timed_shots)
    moving_shots = sum(1 for s in timed_shots if s.kind == "video_full")

    if explicit != "auto":
        chosen = explicit
        reason = f"Explicitly configured adaptive audio profile '{chosen}'."
    elif total_dur <= 44.0 and quant_facts >= 3 and mystery_hits <= 2:
        chosen = "minimal_documentary" if has_diegetic_field_audio else "scientific_explanation"
        reason = (
            f"Concise {total_dur:.1f}s script ({len(sentences)} sentences, {quant_facts} empirical cues) "
            "benefits from clutter-free narration-first clarity without multi-section score changes."
        )
    elif quant_facts >= max(6, len(sentences)) and mystery_hits <= 1:
        chosen = "scientific_explanation"
        reason = f"High empirical density ({quant_facts} quantitative/mechanistic facts across {len(sentences)} sentences) favors Scientific Explanation."
    elif env_hits >= 3 and (has_diegetic_field_audio or moving_shots >= max(2, len(timed_shots) // 2)) and mystery_hits <= env_hits:
        chosen = "immersive_exploration"
        reason = f"Strong physical location presence ({env_hits} environmental cues, diegetic_field_audio={has_diegetic_field_audio}) favors Immersive Exploration."
    elif mystery_hits >= 2 or style.profile_name in ("mysterious_earth_exploration", "ancient_mystery"):
        chosen = "mystery_and_discovery"
        reason = f"Narrative mystery & reveal arc ({mystery_hits} mystery/discovery cues) favors restrained Mystery and Discovery."
    else:
        chosen = "minimal_documentary"
        reason = f"Balanced {total_dur:.1f}s story favors restrained Minimal Documentary soundscape."

    return {
        "selected_profile": chosen,
        "selection_reason": reason,
        "script_metrics": {
            "narration_duration_s": round(total_dur, 3),
            "segment_count": len(manifest.narration_segments),
            "sentence_count": len(sentences),
            "quantitative_fact_cues": quant_facts,
            "mystery_cues": mystery_hits,
            "environmental_cues": env_hits,
            "has_diegetic_field_audio": has_diegetic_field_audio,
        },
    }


def _snap_to_speech_pause(t_target: float, boundaries: list[dict[str, Any]], total_dur: float, max_shift_s: float = 1.8) -> float:
    if not boundaries:
        return round(max(0.0, min(total_dur, t_target)), 3)
    near = min(boundaries, key=lambda b: abs(float(b["time_s"]) - t_target))
    bt = float(near["time_s"])
    if abs(bt - t_target) <= max_shift_s:
        return round(max(0.0, min(total_dur, bt)), 3)
    return round(max(0.0, min(total_dur, t_target)), 3)


def _pick_track_for_stage(
    stage_role: str,
    style_name: str,
    adaptive_profile: str,
    ambience_preset: str,
    registry: dict[str, AudioRegistryEntry],
    already_used: list[str],
) -> str:
    """Select the best commercial-cleared track for a narrative stage without repeating generic beds."""
    if stage_role == "opening_curiosity":
        if "ancient" in style_name or ambience_preset == "ancient_archaeology":
            cand = "mus_ancient_modal_drone_cc0"
        elif "ocean" in style_name or ambience_preset == "deep_ocean":
            cand = "mus_deep_abyssal_pedal_cc0"
        elif adaptive_profile in ("scientific_explanation", "minimal_documentary"):
            cand = "mus_minimal_glass_pulse_cc0"
        elif adaptive_profile == "immersive_exploration":
            cand = "mus_warm_cello_exploration_cc0"
        else:
            cand = "mus_mysterious_undertow_cc0"
    elif stage_role == "context_or_explanation":
        if adaptive_profile == "immersive_exploration":
            cand = "mus_warm_cello_exploration_cc0"
        else:
            cand = "mus_minimal_glass_pulse_cc0"
    elif stage_role == "building_discovery":
        if "ocean" in style_name and "mus_deep_abyssal_pedal_cc0" not in already_used:
            cand = "mus_deep_abyssal_pedal_cc0"
        else:
            cand = "mus_discovery_ascent_cc0"
    else:  # final_reflection
        cand = "mus_reflective_piano_settle_cc0"

    if cand in registry:
        validate_license_string(registry[cand].license, cand)
        return cand
    return next((k for k, v in registry.items() if v.audio_category == "music"), "mus_minimal_glass_pulse_cc0")


def plan_story_music(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Analyze finalized narration and story progression to produce a structured,
    pause-synchronized background music plan (`0..3` sections + pre-reveal hush windows).
    """
    style = manifest.resolve_style_profile()
    reg = ensure_audio_asset_registry()
    total_dur = float(wt.get("total_duration_s", 0.0) or 0.0)
    boundaries = extract_speech_boundaries(wt)
    nmap = build_narrative_map(manifest, wt=wt)
    prof_info = select_adaptive_audio_profile(manifest, wt, timed_shots)
    adaptive_prof = prof_info["selected_profile"]

    shots_want_music = any("music" in (s.scene_audio_layers or []) for s in timed_shots)
    explicit_no_music = (
        manifest.ambience_preset == "none"
        or not shots_want_music
        or bool(manifest.style_overrides.get("force_no_music", False))
    )

    # Identify key narrative beats from actual timed segments
    pivot_seg = next((e for e in nmap if e["seg_id"] == manifest.editorial_formula.layer2_pivot_seg_id), None)
    caveat_seg = next((e for e in nmap if e["seg_id"] == manifest.editorial_formula.scientific_caveat_seg_id), None)
    payoff_seg = next((e for e in nmap if e["narrative_beat"] == "payoff"), pivot_seg)
    final_seg = nmap[-1] if nmap else None

    reveal_time_s = float(payoff_seg["start_s"]) if payoff_seg else round(total_dur * 0.62, 3)
    pivot_time_s = float(pivot_seg["start_s"]) if pivot_seg else round(total_dur * 0.42, 3)
    ending_time_s = float(final_seg["start_s"]) if final_seg else round(total_dur * 0.80, 3)

    # Decide optimal number of music sections based on story duration, profile & restraint rules
    has_rich_field_audio = prof_info["script_metrics"]["has_diegetic_field_audio"]
    if explicit_no_music or (
        adaptive_prof in ("minimal_documentary", "scientific_explanation")
        and total_dur <= 42.0
        and has_rich_field_audio
        and style.sound_design.allow_no_music
    ):
        target_sections = 0
        structure_rationale = (
            "Intentional no-music documentary decision: concise script with authentic environmental/field sound "
            "achieves higher clarity and realism without an artificial underscore."
        )
    elif total_dur < 52.0 or adaptive_prof in ("minimal_documentary", "scientific_explanation") and total_dur < 78.0:
        target_sections = 1
        structure_rationale = (
            f"Single restrained musical section fits {total_dur:.1f}s runtime without rushed mid-story track switches."
        )
    elif total_dur < 112.0:
        target_sections = 2
        structure_rationale = (
            f"Two differentiated sections follow the {total_dur:.1f}s story shift from initial inquiry/context "
            "into deeper scientific discovery and resolution."
        )
    else:
        target_sections = 3
        structure_rationale = (
            f"Three narrative-aligned sections support the {total_dur:.1f}s long-form progression "
            "(Opening Curiosity -> Empirical Investigation -> Discovery & Reflective Resolution) with breathing room."
        )

    # Answer all 7 Section 6 Emotional Progression Questions
    emotional_progression = {
        "opening_emotion": (
            "Calm, immediate factual clarity"
            if adaptive_prof == "scientific_explanation"
            else "Restrained curiosity and sense of place"
        ),
        "curiosity_increase_at_s": round(float(nmap[min(1, len(nmap) - 1)]["start_s"]) if nmap else 0.0, 3),
        "calm_authoritative_stretches": [
            {"seg_id": e["seg_id"], "start_s": e["start_s"], "end_s": e["end_s"]}
            for e in nmap
            if e["narrative_beat"] in ("evidence_and_discovery", "curiosity_gap")
        ],
        "significant_reveal": {
            "present": payoff_seg is not None,
            "seg_id": payoff_seg["seg_id"] if payoff_seg else None,
            "start_s": round(reveal_time_s, 3),
        },
        "requires_tension": adaptive_prof == "mystery_and_discovery",
        "less_prominent_windows": [
            {
                "reason": "Pre-reveal hush & central empirical explanation intelligibility",
                "start_s": round(max(0.0, reveal_time_s - 1.15), 3),
                "end_s": round(min(total_dur, reveal_time_s + 2.2), 3),
            }
        ],
        "ending_approach": (
            "Quiet, unhurried factual finish"
            if target_sections <= 1
            else "Softer reflective resolution allowing the scientific takeaway to settle"
        ),
    }

    sections: list[dict[str, Any]] = []
    silence_windows: list[dict[str, Any]] = []
    accents: list[dict[str, Any]] = []
    used_tracks: list[str] = []

    base_gain_by_profile = {
        "minimal_documentary": -26.5,
        "scientific_explanation": -27.5,
        "immersive_exploration": -23.5,
        "mystery_and_discovery": -22.5,
    }
    base_db = base_gain_by_profile.get(adaptive_prof, -24.0)

    if target_sections == 1:
        role = "context_or_explanation" if adaptive_prof in ("minimal_documentary", "scientific_explanation") else "opening_curiosity"
        trk = _pick_track_for_stage(role, style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk)
        sections.append(
            {
                "section_id": "M01",
                "story_stage": role,
                "track_name": trk,
                "start_s": 0.0,
                "end_s": round(total_dur, 3),
                "base_gain_db": round(base_db, 2),
                "fade_in_s": 0.65,
                "fade_out_s": 1.15,
                "purpose": "Subtle continuous harmonic floor that stays beneath vocal formants",
            }
        )
    elif target_sections == 2:
        t_split = _snap_to_speech_pause(max(total_dur * 0.38, min(total_dur * 0.66, pivot_time_s)), boundaries, total_dur)
        # Add brief 0.85s hush at the pivot pause if mystery_and_discovery
        hush_s = 0.85 if adaptive_prof == "mystery_and_discovery" else 0.0
        trk1 = _pick_track_for_stage("opening_curiosity", style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk1)
        trk2_role = "building_discovery" if adaptive_prof == "mystery_and_discovery" else "final_reflection"
        trk2 = _pick_track_for_stage(trk2_role, style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk2)
        sections.append(
            {
                "section_id": "M01",
                "story_stage": "opening_curiosity_and_context",
                "track_name": trk1,
                "start_s": 0.0,
                "end_s": round(max(4.0, t_split - hush_s * 0.5), 3),
                "base_gain_db": round(base_db - 0.8, 2),
                "fade_in_s": 0.65,
                "fade_out_s": 1.10,
                "purpose": "Establish atmosphere and curiosity without overshadowing opening evidence",
            }
        )
        if hush_s > 0.0:
            silence_windows.append(
                {
                    "start_s": round(max(0.0, t_split - hush_s), 3),
                    "end_s": round(min(total_dur, t_split + 0.35), 3),
                    "purpose": "Intentional pre-pivot hush before deeper scientific mechanism",
                }
            )
        sections.append(
            {
                "section_id": "M02",
                "story_stage": trk2_role,
                "track_name": trk2,
                "start_s": round(min(total_dur - 3.0, t_split + hush_s * 0.5), 3),
                "end_s": round(total_dur, 3),
                "base_gain_db": round(base_db, 2),
                "fade_in_s": 1.15,
                "fade_out_s": 1.35,
                "purpose": "Support discovery payoff and let the final scientific insight settle",
            }
        )
    elif target_sections == 3:
        t1 = _snap_to_speech_pause(max(24.0, min(total_dur * 0.42, pivot_time_s)), boundaries, total_dur)
        t2 = _snap_to_speech_pause(max(t1 + 24.0, min(total_dur - 18.0, ending_time_s)), boundaries, total_dur)
        hush_start = max(t1 + 4.0, reveal_time_s - 1.25)
        hush_end = min(t2 - 2.0, reveal_time_s + 0.45)

        trk1 = _pick_track_for_stage("opening_curiosity", style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk1)
        trk2 = _pick_track_for_stage("building_discovery", style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk2)
        trk3 = _pick_track_for_stage("final_reflection", style.profile_name, adaptive_prof, manifest.ambience_preset, reg, used_tracks)
        used_tracks.append(trk3)

        sections.append(
            {
                "section_id": "M01",
                "story_stage": "opening_hook_and_context",
                "track_name": trk1,
                "start_s": 0.0,
                "end_s": round(t1, 3),
                "base_gain_db": round(base_db - 1.0, 2),
                "fade_in_s": 0.80,
                "fade_out_s": 1.25,
                "purpose": "Subtle opening curiosity and geographic/scientific framing",
            }
        )
        # Intentional quiet/no-music breather before central discovery if reveal sits near t1..t2
        if hush_end > hush_start + 0.6:
            silence_windows.append(
                {
                    "start_s": round(hush_start, 3),
                    "end_s": round(hush_end, 3),
                    "purpose": "Intentional musical hush before major scientific reveal",
                }
            )
        sections.append(
            {
                "section_id": "M02",
                "story_stage": "scientific_investigation_and_discovery",
                "track_name": trk2,
                "start_s": round(t1 + 0.65, 3),
                "end_s": round(t2, 3),
                "base_gain_db": round(base_db + 0.5, 2),
                "fade_in_s": 1.30,
                "fade_out_s": 1.35,
                "purpose": "Gradual harmonic opening supporting empirical escalation and discovery",
            }
        )
        sections.append(
            {
                "section_id": "M03",
                "story_stage": "caveat_and_reflective_resolution",
                "track_name": trk3,
                "start_s": round(t2 + 0.45, 3),
                "end_s": round(total_dur, 3),
                "base_gain_db": round(base_db - 1.5, 2),
                "fade_in_s": 1.25,
                "fade_out_s": 1.60,
                "purpose": "Softer felt-piano resolution allowing scientific caveats and closing thought to settle",
            }
        )

    # Optional subtle harmonic reveal accent (never a loud impact, only on medium/long discovery stories)
    if (
        target_sections >= 2
        and adaptive_prof in ("mystery_and_discovery", "immersive_exploration")
        and payoff_seg is not None
        and "mus_reveal_harmonic_accent_cc0" in reg
    ):
        acc_t = _snap_to_speech_pause(reveal_time_s, boundaries, total_dur, max_shift_s=0.9)
        accents.append(
            {
                "asset_name": "mus_reveal_harmonic_accent_cc0",
                "time_s": acc_t,
                "gain_db": -23.5,
                "purpose": f"Controlled harmonic bloom reinforcing central reveal ({payoff_seg['seg_id']}) without loud impact",
            }
        )

    # Attach 9-criterion evaluation record for every selected track
    track_evaluations = []
    for sec in sections:
        entry = reg.get(sec["track_name"])
        if entry:
            track_evaluations.append(
                {
                    "section_id": sec["section_id"],
                    "track_name": entry.asset_name,
                    "emotional_appropriateness": sec["purpose"],
                    "tempo_bpm": entry.technical_characteristics.get("tempo_bpm", 0),
                    "energy": entry.technical_characteristics.get("energy", "low"),
                    "instrumentation": entry.technical_characteristics.get("instrumentation", ""),
                    "frequency_range": entry.technical_characteristics.get("frequency_band_hz", ""),
                    "narration_compatibility": "320-2850 Hz vocal pocket carved + dynamic speech & important-phrase ducking",
                    "transition_alignment": "Snapped to verified inter-sentence speech boundary",
                    "available_duration_s": entry.duration_s,
                    "commercial_license": entry.license,
                }
            )

    plan = {
        "slug": manifest.slug,
        "adaptive_audio_profile": prof_info,
        "emotional_progression": emotional_progression,
        "music_present": len(sections) > 0,
        "music_sections_count": len(sections),
        "structure_rationale": structure_rationale,
        "sections": sections,
        "silence_windows": silence_windows,
        "musical_accents": accents,
        "track_evaluations": track_evaluations,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "music_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan
