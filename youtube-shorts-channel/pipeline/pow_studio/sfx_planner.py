#!/usr/bin/env python3
"""
Part 4 (Section 7): Context-Aware Documentary Sound Effect Planner (`pow_studio.sfx_planner` v7.0).

Evaluates every proposed sound effect against all 6 Section 7 documentary sound-design
questions before allowing it into the mix:
  1. What is happening in the narration?
  2. What is visible on screen?
  3. What should the viewer feel or understand?
  4. Does a sound effect materially improve that moment?
  5. Is the sound authentic, relevant, and legally usable?
  6. Would silence or natural ambience work better?

Enforces strict documentary restraint:
- Rejects unrelated whooshes, impacts, clicks, risers, UI pings, and transition booms.
- Rejects sounds in outer-space vacuum scenes.
- Rejects sounds when `"cinematic_sfx"` is disabled on the active shot.
- Rejects sounds whose physical source is not visible in the active shot.
- Enforces minimum spacing (`>= 5.0s`) and profile-specific density caps so SFX never compete.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .audio_registry import DEPRECATED_DECORATIVE_SFX, ensure_audio_asset_registry
from .rights_gate import validate_license_string
from .schema import EpisodeManifest, ShotSpecModel

_SFX_VISUAL_REQUIREMENTS: dict[str, set[str]] = {
    "glacial_sub_drop": {"glacier", "ice", "subglacial", "falls", "antarctica", "crevasse", "brine"},
    "ice_creak_subtle": {"glacier", "ice", "crevasse", "iceberg", "frozen", "sheet", "shelf"},
    "katabatic_wind_gust": {"aerial", "wind", "ridge", "glacier", "island", "summit", "antarctica", "cliff", "desert"},
    "hydrophone_current_swell": {"ocean", "underwater", "seafloor", "submersible", "rov", "brine", "trench", "abyss", "marine", "water"},
    "sonar_ping_deep": {"sonar", "rov", "submersible", "mapping", "bathymetry", "radar", "ping", "scan"},
    "microscope_slide_click": {"microscope", "microscopy", "sample", "slide", "lab", "laboratory", "instrument", "cell"},
    "boiling_acid_brine": {"hydrothermal", "geothermal", "boiling", "acid", "vent", "hotspring", "sulfur", "chimney"},
    "fumarole_gas_jet": {"fumarole", "volcano", "steam", "gas", "vent", "plume", "crater"},
    "cave_flood_rush": {"cave", "cavern", "underground", "river", "water", "karst", "stream", "flood"},
    "cavern_heartbeat_pulse": {"cave", "cavern", "subterranean", "chamber", "crystal", "deep", "abyss"},
}


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3}


def plan_context_sfx(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
    ambience_plan: dict[str, Any],
    adaptive_audio_profile: str = "minimal_documentary",
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Evaluate all candidate `sfx_cues` against finalized narration, visible shot content,
    environmental realism, and documentary restraint rules.
    """
    reg = ensure_audio_asset_registry()
    total_dur = float(wt.get("total_duration_s", 0.0) or 0.0)
    shot_by_id = {s.sid: s for s in timed_shots}
    seg_by_id = {s["seg_id"]: s for s in wt.get("segments", [])}
    words = wt.get("words", [])

    # Max SFX budget adapts to runtime & profile (never a minimum quota — 0 is always valid!)
    if adaptive_audio_profile == "scientific_explanation":
        max_cues = 1 if total_dur >= 45.0 else 0
    elif adaptive_audio_profile == "minimal_documentary":
        max_cues = 1 if total_dur < 80.0 else 2
    else:
        max_cues = 1 if total_dur < 45.0 else (2 if total_dur < 105.0 else 4)

    # Map shot_id -> environment from ambience_plan
    shot_env: dict[str, str] = {}
    for sec in ambience_plan.get("sections", []):
        for sid in sec.get("shot_ids", []):
            shot_env[sid] = str(sec.get("environment", ""))

    approved: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    last_approved_t = -999.0

    for idx, cue in enumerate(manifest.sfx_cues, start=1):
        # Resolve exact timestamp against final locked narration
        if cue.anchor_type == "shot_start":
            if cue.anchor_ref not in shot_by_id:
                rejected.append(
                    {
                        "cue_index": idx,
                        "sfx_name": cue.sfx_name,
                        "decision": "REJECT_FOR_SILENCE",
                        "reason": f"Anchor shot '{cue.anchor_ref}' was removed or merged during intelligent scene optimization.",
                    }
                )
                continue
            base_t = shot_by_id[cue.anchor_ref].start_s
        elif cue.anchor_type == "seg_start":
            base_t = float(seg_by_id.get(cue.anchor_ref, {}).get("start", 0.0))
        else:
            base_t = float(cue.anchor_ref)

        t_cue = round(max(0.0, min(max(0.0, total_dur - 0.25), base_t + cue.offset_s)), 3)

        # Active shot & spoken narration at t_cue
        active_shot = next(
            (s for s in timed_shots if s.start_s - 1e-3 <= t_cue < s.end_s + 1e-3),
            timed_shots[-1] if timed_shots else None,
        )
        active_seg = next(
            (sg for sg in wt.get("segments", []) if float(sg["start"]) - 0.35 <= t_cue <= float(sg["end"]) + 0.35),
            None,
        )
        spoken_near = " ".join(
            w["word"] for w in words if t_cue - 1.5 <= float(w["start"]) <= t_cue + 2.5
        ).strip()
        narr_txt = str((active_seg or {}).get("text", spoken_near))
        vis_txt = (
            f"{active_shot.visual_desc} {active_shot.story_beat} {cue.visual_event}"
            if active_shot
            else cue.visual_event
        )
        env_name = shot_env.get(active_shot.sid, "") if active_shot else ""

        reg_entry = reg.get(cue.sfx_name)
        license_ok = False
        if reg_entry and reg_entry.monetization_safe:
            try:
                validate_license_string(reg_entry.license, cue.sfx_name)
                license_ok = True
            except Exception:
                license_ok = False

        # Evaluate the 6 Section 7 Questions
        is_deprecated_transition = (
            cue.sfx_name in DEPRECATED_DECORATIVE_SFX
            or (reg_entry is not None and not reg_entry.allow_in_v7_creative_edit)
            or bool(re.search(r"\b(?:whoosh|boom|transition|riser|swipe|ui ping)\b", f"{cue.sfx_name} {cue.purpose}", re.I))
        )
        is_space_vacuum = env_name == "space_vacuum_silent"
        layer_enabled = active_shot is not None and ("cinematic_sfx" in (active_shot.scene_audio_layers or []))

        req_tokens = _SFX_VISUAL_REQUIREMENTS.get(cue.sfx_name, set(reg_entry.tags if reg_entry else []))
        vis_tokens = _tokens(vis_txt)
        narr_tokens = _tokens(narr_txt)
        visual_match = bool(req_tokens & vis_tokens) or (
            cue.visual_event != "" and len(_tokens(cue.visual_event) & vis_tokens) > 0
        )
        too_dense = (t_cue - last_approved_t) < 5.0 or len(approved) >= max_cues

        # Also avoid firing directly at 0.00s of every cut merely as a transition marker unless offset >= 0.12s or opening
        is_bare_cut_marker = (
            cue.anchor_type == "shot_start"
            and abs(cue.offset_s) < 0.05
            and active_shot is not None
            and active_shot.sid != timed_shots[0].sid
            and not cue.visual_event
            and not visual_match
        )

        reject_reason: Optional[str] = None
        if not reg_entry or not license_ok:
            reject_reason = "Unregistered or unverified commercial license."
        elif is_deprecated_transition:
            reject_reason = "Decorative transition whoosh/boom/UI sound violates Studio v7 documentary restraint."
        elif is_space_vacuum:
            reject_reason = "Outer-space vacuum scene: silence is physically accurate; never invent space sounds."
        elif not layer_enabled:
            reject_reason = f"Shot {active_shot.sid if active_shot else '?'} excludes 'cinematic_sfx' in scene_audio_layers."
        elif is_bare_cut_marker or not visual_match:
            reject_reason = (
                f"Sound '{cue.sfx_name}' does not match visible on-screen action in "
                f"{active_shot.sid if active_shot else 'scene'} ('{active_shot.visual_desc[:65] if active_shot else ''}'); "
                "silence and natural ambience work better."
            )
        elif too_dense:
            reject_reason = (
                f"Exceeds documentary restraint spacing/cap (max_cues={max_cues} for '{adaptive_audio_profile}'); "
                "preferring uncluttered narration and ambience."
            )

        q_record = {
            "q1_narration_happening": narr_txt[:140],
            "q2_visible_on_screen": vis_txt[:140],
            "q3_viewer_understanding": cue.purpose or (active_shot.story_beat if active_shot else "Documentary focus"),
            "q4_materially_improves_moment": reject_reason is None,
            "q5_authentic_relevant_legal": bool(license_ok and visual_match and not is_deprecated_transition),
            "q6_silence_or_ambience_better": reject_reason is not None,
        }

        if reject_reason is not None:
            rejected.append(
                {
                    "cue_index": idx,
                    "sfx_name": cue.sfx_name,
                    "proposed_time_s": t_cue,
                    "shot_id": active_shot.sid if active_shot else None,
                    "decision": "REJECT_FOR_SILENCE",
                    "reason": reject_reason,
                    "six_question_audit": q_record,
                }
            )
            continue

        # Clamp gain conservatively beneath narration (-28 dB .. -19 dB)
        safe_gain_db = round(max(-30.0, min(-19.5, float(cue.gain_db))), 2)
        # If offset is 0.0 on an internal cut, nudge +0.18s into the visible shot so it follows the image rather than acting as a cut click
        synced_t = round(min(max(0.0, total_dur - 0.35), t_cue + (0.18 if (cue.anchor_type == "shot_start" and cue.offset_s == 0.0 and t_cue > 0.2) else 0.0)), 3)
        last_approved_t = synced_t

        approved.append(
            {
                "cue_id": f"SFX{len(approved) + 1:02d}",
                "sfx_name": cue.sfx_name,
                "time_s": synced_t,
                "gain_db": safe_gain_db,
                "shot_id": active_shot.sid if active_shot else "",
                "purpose": cue.purpose or f"Subtle acoustic reinforcement of visible subject in {active_shot.sid if active_shot else 'scene'}",
                "visual_event": cue.visual_event or (active_shot.visual_desc if active_shot else ""),
                "origin_type": reg_entry.origin_type,
                "license": reg_entry.license,
                "six_question_audit": q_record,
            }
        )

    plan = {
        "slug": manifest.slug,
        "adaptive_audio_profile": adaptive_audio_profile,
        "max_cues_cap": max_cues,
        "proposed_cues_count": len(manifest.sfx_cues),
        "approved_cues_count": len(approved),
        "rejected_for_silence_count": len(rejected),
        "silence_preferred_when_zero": len(approved) == 0,
        "approved_cues": approved,
        "rejected_cues": rejected,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sfx_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan
