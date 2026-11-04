#!/usr/bin/env python3
"""
Unit & Integration Tests for Proof of Wonder Studio v7.0
(Advanced Voice, Sound Design & Intelligent Story Editing Engine — Parts 1–12).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.ambience_planner import plan_environmental_ambience  # noqa: E402
from pow_studio.audio_registry import DEPRECATED_DECORATIVE_SFX, ensure_audio_asset_registry  # noqa: E402
from pow_studio.creative_qa import run_creative_qa  # noqa: E402
from pow_studio.elevenlabs_provider import (  # noqa: E402
    map_direction_to_elevenlabs_voice_settings,
    resolve_model_capabilities,
    sanitize_text_for_elevenlabs_model,
)
from pow_studio.music_planner import plan_story_music  # noqa: E402
from pow_studio.scene_editor import optimize_episode_scenes  # noqa: E402
from pow_studio.schema import EpisodeManifest  # noqa: E402
from pow_studio.sfx_planner import plan_context_sfx  # noqa: E402
from pow_studio.style_profile import list_available_production_profiles, load_style_profile  # noqa: E402
from pow_studio.timeline_builder import build_unified_av_timeline  # noqa: E402
from pow_studio.voice_studio import (  # noqa: E402
    AnnotatedVoiceSentence,
    audit_narration_continuity,
    invalidate_dependent_timing_artifacts,
    list_voice_direction_profiles,
    load_voice_direction_profile,
    parse_annotated_voice_script,
    plan_and_rebalance_voice_direction,
)


def _make_base_manifest(tmp_path: Path, style_profile: str = "mysterious_earth_exploration") -> dict:
    raw_dir = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3"
    return {
        "slug": "test-v7-ep",
        "style_profile": style_profile,
        "primary_title": "Why Antarctic Ice Bleeds Iron Brine",
        "alternative_title": "Inside Blood Falls",
        "youtube_description": "Test documentary description.",
        "hashtags": ["#science", "#antarctica"],
        "raw_assets_dir": str(raw_dir),
        "output_dir": str(tmp_path / "out_v7"),
        "editorial_formula": {
            "hook_max_start_s": 2.0,
            "layer2_pivot_seg_id": "N02",
            "scientific_caveat_seg_id": "N03",
            "min_real_evidence_ratio": 0.80,
        },
        "narration_segments": [
            {
                "seg_id": "N01",
                "text": "Deep in Antarctica, crimson brine pours from solid glacier ice.",
                "narrative_beat": "opening_hook",
                "emphasis_words": ["crimson", "brine"],
            },
            {
                "seg_id": "N02",
                "text": "Radar revealed a hypersaline subglacial reservoir sealed for over a million years.",
                "narrative_beat": "payoff",
                "emphasis_words": ["reservoir"],
            },
            {
                "seg_id": "N03",
                "text": "Caveat: researchers are still studying how completely isolated those microbes remain.",
                "narrative_beat": "final_impression",
            },
        ],
        "shots": [
            {
                "sid": "S01",
                "start_s": 0.0,
                "end_s": 4.0,
                "kind": "video_full",
                "src_file": "nasa_m12666_nansen_scientists_ice.mp4",
                "story_beat": "Scientists traversing Antarctic glacier ice",
                "visual_desc": "Scientists walking across Antarctic glacier ice sheet",
                "associated_seg_id": "N01",
                "has_human_interaction": True,
            },
            {
                "sid": "S02",
                "start_s": 4.0,
                "end_s": 7.5,
                "kind": "video_full",
                "src_file": "nasa_m12666_nansen_scientists_ice.mp4",
                "story_beat": "Scientists traversing Antarctic glacier ice again",
                "visual_desc": "Same Antarctic glacier ice sheet traversal",
                "associated_seg_id": "N01",
            },
            {
                "sid": "S03",
                "start_s": 7.5,
                "end_s": 11.0,
                "kind": "still_full",
                "src_file": "bf_2010_12_14.jpg",
                "story_beat": "Crimson iron brine waterfall outflow",
                "visual_desc": "Crimson Blood Falls brine emerging from Taylor Glacier",
                "associated_seg_id": "N02",
                "spoken_importance": "central_reveal",
            },
            {
                "sid": "S04",
                "start_s": 11.0,
                "end_s": 12.2,
                "kind": "still_full",
                "src_file": "bf_aerial_2013.jpg",
                "story_beat": "Decorative filler b-roll",
                "visual_desc": "Decorative filler shot",
                "associated_seg_id": "N02",
                "spoken_importance": "context",
            },
            {
                "sid": "S05",
                "start_s": 12.2,
                "end_s": 16.0,
                "kind": "video_full",
                "src_file": "nasa_m12666_nansen_scientists_ice.mp4",
                "src_in": 4.0,
                "story_beat": "Ongoing field investigation caveat",
                "visual_desc": "Field expedition team studying Antarctic ice",
                "associated_seg_id": "N03",
                "has_human_interaction": True,
            },
        ],
        "assets_register": [
            {
                "local_file": "nasa_m12666_nansen_scientists_ice.mp4",
                "title": "NASA Scientists on Nansen Ice Sheet",
                "creator_agency": "NASA Goddard Space Flight Center",
                "source_page_url": "https://svs.gsfc.nasa.gov/12666",
                "direct_media_url": "https://svs.gsfc.nasa.gov/12666",
                "license": "Public Domain",
                "license_url": "https://www.nasa.gov/nasa-brand-center/images-and-media/",
                "required_attribution": "NASA GSFC",
                "media_type": "video",
            },
            {
                "local_file": "bf_2010_12_14.jpg",
                "title": "Blood Falls Taylor Glacier Outflow",
                "creator_agency": "NSF / Peter Rejcek",
                "source_page_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
                "direct_media_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
                "license": "Public Domain",
                "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
                "required_attribution": "NSF / Peter Rejcek",
                "media_type": "photo",
            },
            {
                "local_file": "bf_aerial_2013.jpg",
                "title": "Blood Falls Aerial Glacier View",
                "creator_agency": "NSF / USAP",
                "source_page_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls_aerial.jpg",
                "direct_media_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls_aerial.jpg",
                "license": "Public Domain",
                "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
                "required_attribution": "NSF",
                "media_type": "photo",
            },
        ],
        "factual_references": [
            {
                "citation": "Mikucki et al. (2009) Science",
                "url": "https://doi.org/10.1126/science.1167350",
                "supported_claims": "Subglacial iron-rich brine ecosystem",
            }
        ],
    }


def _mock_wt(duration_s: float = 16.0) -> dict:
    seg_dur = duration_s / 3.0
    words = []
    segs = [
        ("N01", "Deep in Antarctica crimson brine pours from solid glacier ice."),
        ("N02", "Radar revealed a hypersaline subglacial reservoir sealed for over a million years."),
        ("N03", "Caveat: researchers are still studying how completely isolated those microbes remain."),
    ]
    seg_list = []
    for idx, (sid, txt) in enumerate(segs):
        s0 = round(idx * seg_dur, 3)
        s1 = round((idx + 1) * seg_dur - 0.30, 3)
        toks = txt.split()
        wd = (s1 - s0) / len(toks)
        for wi, tok in enumerate(toks):
            words.append({"word": tok, "start": round(s0 + wi * wd, 3), "end": round(s0 + (wi + 0.85) * wd, 3)})
        seg_list.append({"seg_id": sid, "text": txt, "start": s0, "end": s1})
    return {
        "total_duration_s": duration_s,
        "total_frames_30fps": int(round(duration_s * 30)),
        "segments": seg_list,
        "words": words,
        "soundbites": [],
    }


def test_v7_all_production_and_voice_profiles_load():
    prod_profiles = set(list_available_production_profiles())
    required_prod = {
        "mysterious_earth_exploration",
        "cinematic_science_documentary",
        "deep_ocean_exploration",
        "space_discovery",
        "ancient_mystery",
        "scientific_investigation",
    }
    assert required_prod.issubset(prod_profiles)
    for p in required_prod:
        sp = load_style_profile(p)
        assert sp.pacing.enable_intelligent_scene_editing is True

    voice_profiles = set(list_voice_direction_profiles())
    required_voice = {
        "cinematic_documentary",
        "mysterious_discovery",
        "scientific_authority",
        "dramatic_reveal",
        "calm_exploration",
        "urgent_discovery",
        "emotional_reflection",
    }
    assert required_voice.issubset(voice_profiles)
    for vp_name in required_voice:
        vp = load_voice_direction_profile(vp_name)
        assert vp.voice_identity


def test_v7_elevenlabs_capability_matrix_and_voice_contrast_rebalancer(tmp_path: Path):
    # Flash v2.5 omits style & speaker_boost; strips inline tags
    c_flash = resolve_model_capabilities("eleven_flash_v2_5")
    vs_flash, _ = map_direction_to_elevenlabs_voice_settings(c_flash, rate_pct=-4, energy_level=4, delivery_label="CINEMATIC_REVEAL")
    assert "style" not in vs_flash
    assert "use_speaker_boost" not in vs_flash
    cleaned_f, _ = sanitize_text_for_elevenlabs_model("[whispering] Beneath the ice [calm] water flows.", c_flash)
    assert "[" not in cleaned_f

    # v3 uses discrete stability (0.0/0.5/1.0), blocks [whispering]/[shouting], keeps restrained [thoughtful]
    c_v3 = resolve_model_capabilities("eleven_v3")
    vs_v3, _ = map_direction_to_elevenlabs_voice_settings(c_v3, rate_pct=0, energy_level=3, delivery_label="EMOTIONAL_REFLECTION")
    assert vs_v3["stability"] in (0.0, 0.5, 1.0)
    assert "style" not in vs_v3
    cleaned_v3, _ = sanitize_text_for_elevenlabs_model("[whispering] [shouting] [thoughtful] A quiet horizon.", c_v3)
    assert "[whispering]" not in cleaned_v3
    assert "[shouting]" not in cleaned_v3
    assert "[thoughtful]" in cleaned_v3

    # Over-dramatic script gets rebalanced automatically to preserve vocal contrast
    raw_sents = [
        AnnotatedVoiceSentence(sentence_index=i, seg_id=f"N0{min(3, i+1)}", text=f"Sentence {i} about science.", delivery="DRAMATIC_REVEAL", energy=5)
        for i in range(6)
    ]
    raw_sents[0].delivery = "whispering"
    rebalanced, summary = plan_and_rebalance_voice_direction(raw_sents)
    assert summary["blocked_theatrical_count"] == 1
    assert summary["rebalanced_overdrama_count"] >= 3
    assert summary["contrast_healthy"] is True

    # Annotated parser supports all new v7 tags
    parsed = parse_annotated_voice_script(
        '"Subglacial brine flows." \n[DELIVERY: SCIENTIFIC_AUTHORITY]\n[TONE: calm_clarity]\n[INTENSITY: 0.45]\n[PITCH DIRECTION: falling]\n[RHYTHM: measured]\n[PAUSE BEFORE: 180ms]\n[PRONOUNCE: "Mikucki"="Mih-koo-kee"]\n[PAUSE AFTER: 420ms]\n'
    )
    assert len(parsed) == 1
    assert parsed[0].emotional_tone == "calm_clarity"
    assert parsed[0].pause_before_ms == 180
    assert parsed[0].pronunciation_overrides.get("Mikucki") == "Mih-koo-kee"

    # Continuity audit & cache invalidation
    env = np.hanning(12000).astype(np.float32)
    seg_a = 0.08 * np.sin(np.linspace(0, 200, 12000, dtype=np.float32)) * env
    seg_b = 0.082 * np.sin(np.linspace(0, 200, 12000, dtype=np.float32)) * env
    cont = audit_narration_continuity([seg_a, seg_b], [{"seg_id": "N01"}, {"seg_id": "N02"}], [0.35])
    assert cont["continuity_pass"] is True

    stale_file = tmp_path / "shot_plan_audit.json"
    stale_file.write_text("{}", encoding="utf-8")
    inv = invalidate_dependent_timing_artifacts(tmp_path, "aaa", "bbb")
    assert "shot_plan_audit.json" in inv
    assert not stale_file.exists()


def test_v7_audio_registry_music_ambience_sfx_scene_editor_and_creative_qa(tmp_path: Path):
    reg = ensure_audio_asset_registry()
    assert "mus_minimal_glass_pulse_cc0" in reg
    assert "mus_warm_cello_exploration_cc0" in reg
    assert "mus_discovery_ascent_cc0" in reg
    assert "chapter_whoosh_soft" in reg
    assert reg["chapter_whoosh_soft"].allow_in_v7_creative_edit is False

    d = _make_base_manifest(tmp_path)
    d["sfx_cues"] = [
        {"sfx_name": "chapter_whoosh_soft", "anchor_type": "shot_start", "anchor_ref": "S01", "gain_db": -22.0, "purpose": "transition whoosh"},
        {"sfx_name": "sonar_ping_deep", "anchor_type": "shot_start", "anchor_ref": "S03", "gain_db": -22.0, "purpose": "unrelated underwater sonar on glacier"},
        {"sfx_name": "ice_creak_subtle", "anchor_type": "shot_start", "anchor_ref": "S01", "offset_s": 0.4, "gain_db": -24.0, "purpose": "Glacier ice creak under boots", "visual_event": "Scientists walking across glacier ice"},
    ]
    d["shots"][0]["scene_audio_layers"] = ["narration", "music", "ambience", "natural_sounds", "cinematic_sfx"]
    ep = EpisodeManifest.model_validate(d)
    out_dir = Path(ep.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wt = _mock_wt(duration_s=16.0)
    (out_dir / "word_timings.json").write_text(json.dumps(wt), encoding="utf-8")

    # 1. Scene Editor merges consecutive duplicate S02 into S01 AND removes decorative filler S04!
    opt = optimize_episode_scenes(ep, wt, fps=30, persist_report=True)
    assert opt["counts"]["Merge"] >= 1
    assert opt["counts"]["Remove"] >= 1
    assert opt["final_scene_count"] == 3
    surviving = [EpisodeManifest.model_validate({**d, "shots": opt["optimized_shots"]}).shots][0]
    assert abs(surviving[-1].end_s - 16.0) < 1e-3

    # 2. Music planner adapts section count to runtime (16s -> <=1 section; 150s -> 3 sections)
    m_short = plan_story_music(ep, wt, surviving, out_dir=out_dir)
    assert m_short["music_sections_count"] <= 1

    wt_long = _mock_wt(duration_s=148.0)
    m_long = plan_story_music(ep, wt_long, surviving)
    assert m_long["music_sections_count"] == 3
    assert len({s["track_name"] for s in m_long["sections"]}) >= 2

    # 3. Ambience planner keeps connected polar scenes continuous & silences outer space
    a_plan = plan_environmental_ambience(ep, wt, surviving, out_dir=out_dir)
    assert a_plan["audible_ambience_sections_count"] == 1  # Continuous across all 3 polar shots!

    d_space = _make_base_manifest(tmp_path, style_profile="space_discovery")
    d_space["ambience_preset"] = "deep_space"
    d_space["shots"][0]["visual_desc"] = "Deep space galaxy cluster in vacuum"
    ep_space = EpisodeManifest.model_validate(d_space)
    a_space = plan_environmental_ambience(ep_space, wt, ep_space.shots)
    assert a_space["sections"][0]["environment"] == "space_vacuum_silent"
    assert a_space["sections"][0]["audible"] is False

    # 4. SFX planner rejects transition whoosh & unrelated sonar, approves genuine ice creak
    s_plan = plan_context_sfx(ep, wt, surviving, a_plan, adaptive_audio_profile="immersive_exploration", out_dir=out_dir)
    approved_names = [c["sfx_name"] for c in s_plan["approved_cues"]]
    rejected_names = [c["sfx_name"] for c in s_plan["rejected_cues"]]
    assert "chapter_whoosh_soft" in rejected_names
    assert "sonar_ping_deep" in rejected_names
    assert "ice_creak_subtle" in approved_names

    # 5. Unified Timeline Builder exports all 11 columns
    tl = build_unified_av_timeline(ep, wt, music_plan=m_short, ambience_plan=a_plan, sfx_plan=s_plan, out_dir=out_dir)
    assert tl["scene_count"] == 3
    row0 = tl["scenes"][0]
    for col in ("scene_id", "narration_segment", "visual_source", "visual_purpose", "voice_direction", "music", "ambience", "sound_effect", "start_end_time", "transition", "audio_priority"):
        assert col in row0

    # 6. Creative QA passes clean edit, and FAILS poor creative edit (e.g. decorative whoosh / music overpowering)
    wt["sfx_applied"] = s_plan["approved_cues"]
    cqa_ok = run_creative_qa(ep, wt, subtitles_word_match_ratio=0.98, out_dir=out_dir)
    assert cqa_ok["creative_qa_pass"] is True

    (out_dir / "audio_engineering_report.json").write_text(json.dumps({"voice_to_bed_margin_lu": 4.0}), encoding="utf-8")
    wt_bad = {**wt, "sfx_applied": [{"sfx_name": "chapter_whoosh_soft", "time_s": 4.0}]}
    cqa_bad = run_creative_qa(ep, wt_bad, subtitles_word_match_ratio=0.98, out_dir=out_dir)
    assert cqa_bad["creative_qa_pass"] is False
    assert cqa_bad["severity_counts"]["CRITICAL"] >= 1
    assert cqa_bad["severity_counts"]["MAJOR"] >= 1
