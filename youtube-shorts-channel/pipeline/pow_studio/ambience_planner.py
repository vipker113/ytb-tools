#!/usr/bin/env python3
"""
Part 4, Part 5 & Part 7: Continuous Scene-Connected Environmental Ambience Planner
(`pow_studio.ambience_planner` v7.0).

Designs environmental sound beds that:
1. Stay continuous across connected shots in the same physical location so ambience never
   cuts abruptly at image boundaries unless the story physically changes location.
2. Enforce strict physical realism in outer space (`space_vacuum_silent` -> zero invented
   external atmosphere or fake radio chatter; subtle cabin/observatory room tone only when
   inside a telescope dome or spacecraft interior).
3. Prefer genuine expedition field recordings (`nat_sound_bed_file` / diegetic video audio /
   registered Wikimedia/US-Gov field recordings) over synthetic noise beds, and clearly label
   the provenance of every ambience section.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .schema import EpisodeManifest, ShotSpecModel


def _infer_shot_environment(shot: ShotSpecModel, manifest: EpisodeManifest, style_scene_profile: str) -> str:
    if "ambience" not in (shot.scene_audio_layers or []) and "natural_sounds" not in (shot.scene_audio_layers or []):
        return "silent"
    if manifest.ambience_preset == "none":
        return "silent"

    desc = f"{shot.visual_desc} {shot.story_beat} {shot.associated_narration_concept}".lower()

    # Check outer space vacuum vs interior observatory/ISS
    is_space_episode = manifest.ambience_preset == "deep_space" or style_scene_profile == "space_vacuum_restrained"
    if re.search(r"\b(?:galaxy|galaxies|nebula|exoplanet|deep space|vacuum|orbit|solar wind|black hole|cosmos|interstellar)\b", desc):
        if re.search(r"\b(?:observatory|control room|astronaut inside|cabin|cupola|laboratory|dome)\b", desc):
            return "laboratory_observatory"
        return "space_vacuum_silent"
    if is_space_episode and not re.search(r"\b(?:observatory|laboratory|desert|earth|launchpad|control room|iss interior)\b", desc):
        return "space_vacuum_silent"

    if re.search(r"\b(?:microscope|laboratory|cleanroom|spectrometer|instrument|observatory|telescope dome|diagram)\b", desc) or shot.kind == "diagram":
        return "laboratory_observatory"
    if re.search(r"\b(?:underwater|submersible|rov|seafloor|brine pool|abyssal|trench|hydrophone|deep ocean|coral|marine)\b", desc):
        return "deep_ocean"
    if re.search(r"\b(?:glacier|antarctica|ice sheet|crevasse|katabatic|polar|snow|iceberg|subglacial)\b", desc):
        return "polar_glacial"
    if re.search(r"\b(?:cave|cavern|karst|lava tube|underground|subterranean|shaft|mine)\b", desc):
        return "subterranean_earth"
    if re.search(r"\b(?:volcano|fumarole|crater|magma|hydrothermal|geothermal|acid lake|lava)\b", desc):
        return "volcanic_abyss"
    if re.search(r"\b(?:ruin|temple|megalith|excavation|archaeolog|stone|desert|canyon)\b", desc):
        return "ancient_archaeology"
    if re.search(r"\b(?:aerial|island|coast|ridge|cliff|forest|canopy|jungle)\b", desc):
        return "aerial_natural_wind"

    preset_map = {
        "polar_glacial": "polar_glacial",
        "deep_ocean": "deep_ocean",
        "subterranean_earth": "subterranean_earth",
        "volcanic_abyss": "volcanic_abyss",
        "ancient_archaeology": "ancient_archaeology",
        "minimal_investigation": "laboratory_observatory",
        "scientific_discovery": "laboratory_observatory",
        "wildlife_field": "aerial_natural_wind",
        "deep_space": "space_vacuum_silent",
    }
    return preset_map.get(manifest.ambience_preset, "laboratory_observatory")


_ENV_PARAMS: dict[str, dict[str, Any]] = {
    "polar_glacial": {
        "band_hz": (115.0, 480.0),
        "base_gain_db": -27.5,
        "label": "Restrained Antarctic katabatic air floor",
    },
    "deep_ocean": {
        "band_hz": (62.0, 290.0),
        "base_gain_db": -26.5,
        "label": "Deep-water hydrophone pressure floor",
    },
    "subterranean_earth": {
        "band_hz": (75.0, 360.0),
        "base_gain_db": -27.5,
        "label": "Resonant subterranean cavern air stillness",
    },
    "volcanic_abyss": {
        "band_hz": (70.0, 380.0),
        "base_gain_db": -27.0,
        "label": "Low geothermal crater atmospheric floor",
    },
    "ancient_archaeology": {
        "band_hz": (105.0, 440.0),
        "base_gain_db": -29.0,
        "label": "Open-air stone site stillness",
    },
    "aerial_natural_wind": {
        "band_hz": (120.0, 510.0),
        "base_gain_db": -28.0,
        "label": "Subtle natural open-air wind horizon",
    },
    "laboratory_observatory": {
        "band_hz": (90.0, 340.0),
        "base_gain_db": -32.0,
        "label": "Quiet observatory / laboratory room tone",
    },
    "space_vacuum_silent": {
        "band_hz": (0.0, 0.0),
        "base_gain_db": -90.0,
        "label": "Intentional outer-space vacuum silence (zero fabricated space sound)",
    },
    "silent": {
        "band_hz": (0.0, 0.0),
        "base_gain_db": -90.0,
        "label": "Intentional silence",
    },
}


def plan_environmental_ambience(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: list[ShotSpecModel],
    adaptive_audio_profile: str = "minimal_documentary",
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Group consecutive connected scenes sharing an environment into continuous ambience
    sections with smooth `1.2s` crossfades ONLY across genuine location transitions.
    """
    style = manifest.resolve_style_profile()
    raw_spans: list[dict[str, Any]] = []

    for s in timed_shots:
        env = _infer_shot_environment(s, manifest, style.sound_design.scene_audio_profile)
        if raw_spans and raw_spans[-1]["environment"] == env:
            raw_spans[-1]["end_s"] = round(s.end_s, 3)
            raw_spans[-1]["shot_ids"].append(s.sid)
        else:
            raw_spans.append(
                {
                    "environment": env,
                    "start_s": round(s.start_s, 3),
                    "end_s": round(s.end_s, 3),
                    "shot_ids": [s.sid],
                }
            )

    # Absorb fleeting 1-shot micro-shifts (< 2.6s) when flanked by identical environments to avoid jumpy ambience
    merged_spans: list[dict[str, Any]] = []
    i = 0
    while i < len(raw_spans):
        cur = raw_spans[i]
        if (
            0 < i < len(raw_spans) - 1
            and (cur["end_s"] - cur["start_s"]) < 2.6
            and raw_spans[i - 1]["environment"] == raw_spans[i + 1]["environment"]
            and cur["environment"] != "space_vacuum_silent"
        ):
            merged_spans[-1]["end_s"] = raw_spans[i + 1]["end_s"]
            merged_spans[-1]["shot_ids"].extend(cur["shot_ids"] + raw_spans[i + 1]["shot_ids"])
            i += 2
            continue
        merged_spans.append(cur)
        i += 1

    profile_atten_db = -3.0 if adaptive_audio_profile in ("minimal_documentary", "scientific_explanation") else 0.0
    has_authentic_bed = bool(manifest.nat_sound_bed_file)

    sections: list[dict[str, Any]] = []
    audible_sections_count = 0
    for idx, sp in enumerate(merged_spans, start=1):
        env = sp["environment"]
        meta = _ENV_PARAMS.get(env, _ENV_PARAMS["laboratory_observatory"])
        is_audible = env not in ("space_vacuum_silent", "silent")
        if is_audible:
            audible_sections_count += 1
        gain_db = round(float(meta["base_gain_db"]) + profile_atten_db, 2) if is_audible else -90.0
        sections.append(
            {
                "ambience_id": f"A{idx:02d}",
                "environment": env,
                "label": meta["label"],
                "start_s": sp["start_s"],
                "end_s": sp["end_s"],
                "duration_s": round(sp["end_s"] - sp["start_s"], 3),
                "shot_ids": sp["shot_ids"],
                "audible": is_audible,
                "band_hz": list(meta["band_hz"]),
                "target_gain_db": gain_db,
                "crossfade_s": 1.20 if idx > 1 else 0.45,
                "authentic_field_bed_file": manifest.nat_sound_bed_file if (is_audible and has_authentic_bed) else None,
                "provenance": (
                    "authentic_expedition_field_audio"
                    if (is_audible and has_authentic_bed)
                    else ("intentional_vacuum_silence" if not is_audible else "restrained_acoustic_room_air_tone")
                ),
            }
        )

    plan = {
        "slug": manifest.slug,
        "ambience_sections_total": len(sections),
        "audible_ambience_sections_count": audible_sections_count,
        "silent_or_vacuum_sections_count": len(sections) - audible_sections_count,
        "continuous_across_connected_scenes": True,
        "sections": sections,
    }
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "ambience_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan
