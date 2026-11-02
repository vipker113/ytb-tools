#!/usr/bin/env python3
"""
Automated unit & regression test suite for `pow_studio` v3.0 Documentary Engine
(with backward-compatibility coverage for v2 components).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.annotations import draw_antarctica_locator, draw_scale_ring_annotation
from pow_studio.compositor import (
    FONT_BOLD,
    FONT_MED,
    compute_overlay_states,
    compute_transition_handles,
    draw_caption,
    get_font,
)
from pow_studio.depth_parallax import infer_smoothed_depth, render_25d_parallax_frame
from pow_studio.qc_suite import audit_overlay_cleanliness, canonicalize_tokens_for_asr, compute_wcag_contrast_ratio
from pow_studio.reframing import (
    crop_subpixel_full_canvas,
    estimate_salient_subject_center,
    evaluate_crop_feasibility,
    interpolate_reframe_keyframes,
)
from pow_studio.rights_gate import RightsViolationError, validate_license_string
from pow_studio.schema import (
    EpisodeManifest,
    LocatorPinAnnotation,
    ScaleCalloutAnnotation,
    ThumbnailSpecModel,
    resolve_timed_shots,
)
from pow_studio.sfx_library import ensure_sfx_library
from pow_studio.shot_planner import audit_shot_plan_and_alignment, extract_speech_boundaries
from pow_studio.style_profile import load_style_profile
from pow_studio.thumbnail_engine import compose_subject_first_thumbnail, score_thumbnail_candidate


def _minimal_manifest_dict() -> dict:
    return {
        "slug": "test-ep",
        "primary_title": "Test Title",
        "alternative_title": "Alt Title",
        "youtube_description": "Test description",
        "hashtags": ["#Science"],
        "raw_assets_dir": "/tmp",
        "output_dir": "/tmp/test_pow_out",
        "editorial_formula": {
            "hook_max_start_s": 2.0,
            "layer2_pivot_seg_id": "N02",
            "scientific_caveat_seg_id": "N03",
            "min_real_evidence_ratio": 0.80,
        },
        "thumbnail_spec": {
            "headline_text": "WHY IS IT RED?",
        },
        "cover_variants": [
            {"variant_id": "A", "cover_text": "WHY IS IT RED?"},
            {"variant_id": "B", "cover_text": "NOT BLOOD."},
        ],
        "narration_segments": [
            {"seg_id": "N01", "text": "Hook line.", "emphasis_words": ["Hook"]},
            {"seg_id": "N02", "text": "Pivot line."},
            {"seg_id": "N03", "text": "Caveat: this does not prove continuous isolation."},
        ],
        "shots": [
            {
                "sid": "S01",
                "start_s": 0.0,
                "end_s": 4.5,
                "kind": "video_full",
                "src_file": "clip.mp4",
                "is_real_evidence": True,
                "story_beat": "b1",
                "visual_desc": "d1",
            },
            {
                "sid": "S02",
                "start_s": 4.5,
                "end_s": 9.0,
                "kind": "video_full",
                "src_file": "clip.mp4",
                "src_in": 5.0,
                "transition_in": "dissolve",
                "transition_duration_s": 0.6,
                "is_real_evidence": True,
                "story_beat": "b2",
                "visual_desc": "d2",
            },
            {
                "sid": "S03",
                "start_s": 9.0,
                "end_s": 13.5,
                "kind": "still_full",
                "src_file": "a.jpg",
                "is_real_evidence": True,
                "story_beat": "b3",
                "visual_desc": "d3",
            },
            {
                "sid": "S04",
                "start_s": 13.5,
                "end_s": 15.0,
                "kind": "diagram",
                "src_file": "diag.mp4",
                "is_real_evidence": False,
                "story_beat": "b4",
                "visual_desc": "d4",
            },
        ],
        "caption_groups": [
            {"seg_id": "N01", "first_word_idx": 0, "last_word_idx": 1, "text": "Hook line."},
            {"seg_id": "N02", "first_word_idx": 0, "last_word_idx": 1, "text": "Pivot line."},
            {"seg_id": "N03", "first_word_idx": 0, "last_word_idx": 3, "text": "Caveat: this does not"},
            {"seg_id": "N03", "first_word_idx": 4, "last_word_idx": 6, "text": "prove continuous isolation."},
        ],
        "assets_register": [
            {
                "local_file": "clip.mp4",
                "title": "Field Video",
                "creator_agency": "NASA",
                "source_page_url": "https://svs.gsfc.nasa.gov",
                "direct_media_url": "https://svs.gsfc.nasa.gov/clip.mp4",
                "license": "Public Domain (NASA)",
                "license_url": "https://www.nasa.gov",
                "required_attribution": "NASA Goddard SVS (Public Domain)",
            },
            {
                "local_file": "a.jpg",
                "title": "Photo A",
                "creator_agency": "NSF",
                "source_page_url": "https://www.nsf.gov",
                "direct_media_url": "https://www.nsf.gov/a.jpg",
                "license": "Public Domain (NSF)",
                "license_url": "https://www.nsf.gov/policies/reuse.jsp",
                "required_attribution": "NSF (Public Domain)",
            },
            {
                "local_file": "diag.mp4",
                "title": "Diagram",
                "creator_agency": "POW",
                "source_page_url": "local://diagram",
                "direct_media_url": "local://diagram.mp4",
                "license": "100% Original First-Party Graphic",
                "license_url": "N/A",
                "required_attribution": "Original",
                "is_first_party_original": True,
            },
        ],
        "factual_references": [
            {
                "citation": "Zoumplis et al. (2026)",
                "url": "https://www.nature.com/articles/s41561-026-02054-6",
                "supported_claims": "167 samples",
            }
        ],
    }


def test_style_profile_defaults_and_overrides():
    from pow_studio.style_profile import list_available_production_profiles

    v3 = load_style_profile("pow_documentary_v3")
    assert v3.output.width == 1080 and v3.output.height == 1920 and v3.output.fps == 30
    assert v3.composition.fill_canvas_edge_to_edge is True
    assert v3.composition.allow_inset_frames is False
    assert v3.composition.enable_synthetic_25d_parallax is True
    assert v3.overlays.show_animated_circles_or_rings is False
    assert v3.overlays.show_source_banners_in_video is False
    assert v3.overlays.burn_opening_cover_card_into_video is False
    assert v3.asset_selection.target_moving_footage_ratio == 0.80

    # Verify all 4 reusable category Production Profiles resolve cleanly
    avail = list_available_production_profiles()
    for pname in (
        "cinematic_science_documentary",
        "mysterious_earth_exploration",
        "space_discovery",
        "deep_ocean_documentary",
    ):
        assert pname in avail
        prof = load_style_profile(pname)
        assert prof.profile_name == pname
        assert prof.composition.fill_canvas_edge_to_edge is True

    custom = load_style_profile("pow_documentary_v3", {"opening_and_thumbnail": {"thumbnail_text_mode": "none"}})
    assert custom.opening_and_thumbnail.thumbnail_text_mode == "none"
    assert custom.overlays.show_source_banners_in_video is False


def test_v3_rejects_inset_and_dashboard_layouts_by_default():
    for boxed_kind in ("still_window", "video_window", "study_card", "svs_flyover", "microscopy_dual"):
        d = _minimal_manifest_dict()
        d["shots"][0]["kind"] = boxed_kind
        with pytest.raises(ValueError, match="inset/dashboard layout"):
            EpisodeManifest.model_validate(d)


def test_schema_enforces_80pct_real_evidence_and_editorial_anchors():
    d = _minimal_manifest_dict()
    ep = EpisodeManifest.model_validate(d)
    assert ep.assets_register[0].media_type == "video"
    assert ep.assets_register[1].media_type == "photo"
    assert ep.assets_register[2].media_type == "diagram"

    d_bad = _minimal_manifest_dict()
    d_bad["shots"][1]["is_real_evidence"] = False
    d_bad["shots"][2]["is_real_evidence"] = False  # 4.5 / 15.0 = 30% < 80%
    with pytest.raises(ValueError, match="Real visual evidence ratio"):
        EpisodeManifest.model_validate(d_bad)

    resolved = resolve_timed_shots(ep, 450, fps=30)
    assert resolved[0].start_s == 0.0
    assert resolved[-1].end_s == 15.0
    for s_a, s_b in zip(resolved, resolved[1:]):
        assert s_a.end_s == s_b.start_s


def test_intelligent_reframing_and_crop_feasibility():
    # 720p HD video cropped to 9:16 -> feasible (crop_h >= 660px >= 540px)
    ok_720 = evaluate_crop_feasibility(1280, 720, max_zoom=1.04)
    assert ok_720.feasible is True
    assert ok_720.crop_height_px >= 680

    # 360p SD video -> rejected
    bad_360 = evaluate_crop_feasibility(640, 360, max_zoom=1.02)
    assert bad_360.feasible is False

    # Wide multi-axis chart -> rejected when allow_cropping=False
    bad_chart = evaluate_crop_feasibility(1600, 1000, contains_wide_axes_or_text=True)
    assert bad_chart.feasible is False

    raw_img_path = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "bf_aerial_2013.jpg"
    img = Image.open(raw_img_path).convert("RGB").resize((960, 640), Image.Resampling.BICUBIC)
    cx, cy = estimate_salient_subject_center(img)
    assert 0.18 <= cx <= 0.82
    assert 0.22 <= cy <= 0.76
    cropped = crop_subpixel_full_canvas(img, cx, cy, 1.02, 1080, 1920)
    assert cropped.size == (1080, 1920)

    kfs = [(0.0, 0.30, 0.50), (1.0, 0.70, 0.40)]
    mx, my = interpolate_reframe_keyframes(kfs, 0.5)
    assert abs(mx - 0.50) < 1e-4 and abs(my - 0.45) < 1e-4


def test_overlay_cleanliness_and_zero_drift_dissolve_handles():
    d = _minimal_manifest_dict()
    d["output_dir"] = "/tmp/test_pow_overlay_clean"
    Path(d["output_dir"]).mkdir(parents=True, exist_ok=True)
    # Attach legacy clutter attributes onto shots and verify v3 suppresses all of them!
    d["shots"][0]["label"] = "NSF Public Domain Source Banner"
    d["shots"][0]["callout"] = "RED WARNING BADGE"
    d["shots"][0]["scale_annotation"] = {
        "norm_x": 0.5,
        "norm_y": 0.5,
        "label_title": "YELLOW RING",
        "side": "right",
    }
    ep = EpisodeManifest.model_validate(d)
    style = ep.resolve_style_profile()

    fake_wt = {
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [
            {"seg_id": "N01", "start": 0.1, "end": 4.2, "text": "Hook line."},
            {"seg_id": "N02", "start": 4.5, "end": 8.7, "text": "Pivot line."},
            {"seg_id": "N03", "start": 9.0, "end": 14.5, "text": "Caveat: this does not prove continuous isolation."},
        ],
        "words": [
            {"seg_id": "N01", "word": "Hook", "start": 0.1, "end": 0.5},
            {"seg_id": "N01", "word": "line.", "start": 0.5, "end": 1.2},
            {"seg_id": "N02", "word": "Pivot", "start": 4.5, "end": 5.0},
            {"seg_id": "N02", "word": "line.", "start": 5.0, "end": 5.6},
            {"seg_id": "N03", "word": "Caveat:", "start": 9.0, "end": 9.5},
            {"seg_id": "N03", "word": "this", "start": 9.5, "end": 9.8},
            {"seg_id": "N03", "word": "does", "start": 9.8, "end": 10.1},
            {"seg_id": "N03", "word": "not", "start": 10.1, "end": 10.4},
            {"seg_id": "N03", "word": "prove", "start": 10.5, "end": 10.9},
            {"seg_id": "N03", "word": "continuous", "start": 10.9, "end": 11.5},
            {"seg_id": "N03", "word": "isolation.", "start": 11.5, "end": 12.2},
        ],
    }

    oc = audit_overlay_cleanliness(ep, fake_wt, style)
    assert oc["clean_documentary_pass"] is True
    assert oc["scale_rings_rendered"] == 0
    assert oc["source_banners_rendered"] == 0
    assert oc["opening_cover_card_burned"] is False
    assert oc["closing_credit_burned"] is False

    # Verify dissolve handles preserve exact 450 frames
    timed = resolve_timed_shots(ep, 450, fps=30)
    handles = compute_transition_handles(timed, style)
    assert handles[1]["dissolve_in_frames"] == 18  # 0.6s * 30fps
    assert handles[0]["tail_frames"] + handles[1]["head_frames"] == 18
    total_after_xfade = sum(h["nominal_frames"] + h["head_frames"] + h["tail_frames"] for h in handles) - sum(
        h["dissolve_in_frames"] for h in handles
    )
    assert total_after_xfade == 450


def test_subject_first_thumbnail_engine(tmp_path: Path):
    from pow_studio.thumbnail_engine import export_documentary_thumbnail_package

    style = load_style_profile("pow_documentary_v3")
    assert style.opening_and_thumbnail.thumbnail_text_mode == "cinema_hook"
    raw_img_path = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "bf_aerial_2013.jpg"
    img = Image.open(raw_img_path).convert("RGB").resize((1200, 800), Image.Resampling.BICUBIC)
    cscore = score_thumbnail_candidate(img, "bf_aerial_2013.jpg")
    assert cscore.combined_score > 5.0

    thumb = compose_subject_first_thumbnail(
        img,
        style,
        headline_text="A DEADLY LAKE|UNDER THE OCEAN",
        kicker_text="1,770M DEEP • ZERO OXYGEN",
        accent_line_index=1,
        accent_rgb=(255, 212, 59),
        clarity_boost=True,
    )
    assert thumb.size == (1080, 1920)
    alt = compose_subject_first_thumbnail(img, style, headline_text="AN OCEAN LAKE|8X TOO TOXIC")
    res = export_documentary_thumbnail_package(
        thumb_rgb=thumb,
        out_dir=tmp_path,
        slug="test-brine-v4",
        primary_title="Test Brine Pools",
        style=style,
        cand_score=cscore,
        alt_variants=[("AN OCEAN LAKE 8X TOO TOXIC", alt)],
    )
    assert Path(res["thumbnail_jpg"]).exists()
    assert (tmp_path / "thumbnail_variant_B.jpg").exists()
    assert Path(res["preview_sheet_jpg"]).exists()


def test_shot_planner_speech_boundaries_and_illustrative_disclosure():
    d = _minimal_manifest_dict()
    d["shots"][2]["subject_match_kind"] = "representative_organism_microscopy"
    ep_missing_note = EpisodeManifest.model_validate(d)
    style = ep_missing_note.resolve_style_profile()
    fake_wt = {
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [{"seg_id": "N01", "start": 0.1, "end": 14.8, "text": "Test"}],
        "words": [
            {"seg_id": "N01", "word": "First.", "start": 0.1, "end": 4.35},
            {"seg_id": "N01", "word": "Second.", "start": 4.60, "end": 8.85},
            {"seg_id": "N01", "word": "Third.", "start": 9.10, "end": 13.35},
            {"seg_id": "N01", "word": "Fourth.", "start": 13.60, "end": 14.90},
        ],
    }
    bounds = extract_speech_boundaries(fake_wt)
    assert len(bounds) >= 4

    audit_bad = audit_shot_plan_and_alignment(ep_missing_note, fake_wt, style)
    assert any("context_note" in e for e in audit_bad["errors"])

    d["shots"][2]["context_note"] = "Illustrative live microscopy"
    ep_good = EpisodeManifest.model_validate(d)
    audit_good = audit_shot_plan_and_alignment(ep_good, fake_wt, style)
    assert len(audit_good["errors"]) == 0
    assert audit_good["moving_footage_pct"] == 60.0
    assert audit_good["pacing_summary"]["speech_boundary_alignment_pct"] == 100.0


def test_nondestructive_protection_of_completed_episodes():
    v3_yaml = CHANNEL_ROOT / "episodes" / "hidden_earth_blood_falls_v3_documentary.yaml"
    ep_v3 = EpisodeManifest.from_yaml(v3_yaml)
    assert ep_v3.style_profile == "pow_documentary_v3"
    with pytest.raises(RuntimeError, match="Non-destructive protection blocked"):
        ep_v3.assert_output_dir_writable()

    # Also ensure every existing episode YAML in episodes/ parses backward-compatibly
    for yml in sorted((CHANNEL_ROOT / "episodes").glob("*.yaml")):
        if yml.name.startswith("_"):
            continue
        parsed = EpisodeManifest.from_yaml(yml)
        assert len(parsed.shots) >= 4


def test_rights_gate_blocks_noncommercial_noderiv_sharealike_and_allows_commercial():
    validate_license_string("Public Domain (U.S. Federal Government / NSF)", "ok1.jpg")
    validate_license_string("CC BY 4.0", "ok2.png")
    validate_license_string("CC0 1.0", "ok3.wav")
    validate_license_string("100% Original First-Party Graphic", "ok4.mp4")

    for forbidden in ("CC BY-NC 4.0", "CC BY-ND 3.0", "CC BY-SA 4.0", "All Rights Reserved", "Unknown", "Editorial Only"):
        with pytest.raises(RightsViolationError):
            validate_license_string(forbidden, "bad_asset.jpg")


def test_cc0_sfx_library_synthesizes_all_6_broadcast_stems():
    sfx_dir = ensure_sfx_library()
    expected = [
        "glacial_sub_drop.wav",
        "ice_creak_subtle.wav",
        "katabatic_wind_gust.wav",
        "locator_ping_soft.wav",
        "microscope_slide_click.wav",
        "paper_data_reveal.wav",
        "LICENSE_CC0.md",
    ]
    for fn in expected:
        p = sfx_dir / fn
        assert p.exists() and p.stat().st_size > 100


def test_depth_anything_v2_inference_and_25d_parallax_warp():
    raw_img_path = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "bf_aerial_2013.jpg"
    img = Image.open(raw_img_path).convert("RGB").resize((960, 640), Image.Resampling.BICUBIC)
    dep = infer_smoothed_depth(img, "pytest_bf_aerial_960x640")
    assert dep.mode == "L"
    assert dep.size == img.size

    f0 = render_25d_parallax_frame(img, dep, 0.58, 0.45, 1.04, 0.0, 18.0, 540, 960)
    f1 = render_25d_parallax_frame(img, dep, 0.58, 0.45, 1.04, 1.0, 18.0, 540, 960)
    assert f0.size == (540, 960)
    diff = float(np.mean(np.abs(np.asarray(f1, dtype=np.float32) - np.asarray(f0, dtype=np.float32))))
    assert diff > 0.5


def test_annotations_and_keyword_highlighted_captions_and_wcag():
    ov = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    fb = get_font(FONT_BOLD, 20)
    fm = get_font(FONT_MED, 17)
    draw_scale_ring_annotation(
        ov,
        ScaleCalloutAnnotation(norm_x=0.80, norm_y=0.75, label_title="FIELD SCIENTISTS", label_subtitle="Human scale", side="left"),
        local_t=1.2,
        shot_dur=4.0,
        font_bold=fb,
        font_med=fm,
    )
    draw_antarctica_locator(
        ov,
        LocatorPinAnnotation(place_title="TAYLOR GLACIER", coords_label="77.7°S, 162.3°E"),
        local_t=1.2,
        shot_dur=4.0,
        font_bold=fb,
        font_med=fm,
    )
    draw_caption(ov, "Salty, iron-rich water oxidizes as it reaches the air,", active_emph_norms=["ironrich", "oxidizes"])
    alpha_arr = np.asarray(ov)[:, :, 3]
    assert int(np.count_nonzero(alpha_arr)) > 20_000

    assert compute_wcag_contrast_ratio((252, 253, 255), (78, 82, 90)) >= 7.5
    assert compute_wcag_contrast_ratio((255, 222, 118), (45, 50, 59)) >= 7.5

    ref_c = canonicalize_tokens_for_asr(["In", "2026", "Across", "167", "haptophytes", "1,770", "mirror-like"])
    hyp_c = canonicalize_tokens_for_asr(["in", "twenty", "twenty", "six", "across", "one", "hundred", "and", "sixty", "seven", "haptic", "fights", "1", "770", "mirror", "like"])
    assert ref_c == hyp_c


def test_video_first_and_human_interaction_enforcement():
    from pow_studio.video_sourcing import _is_commercial_safe_license_string, _score_human_interaction_text

    assert _is_commercial_safe_license_string("CC BY 4.0") is True
    assert _is_commercial_safe_license_string("Public Domain (NASA)") is True
    assert _is_commercial_safe_license_string("CC BY-NC 4.0") is False
    assert _is_commercial_safe_license_string("CC BY-SA 4.0") is False
    assert _score_human_interaction_text("Scientists drill ice core in Antarctica field camp", "researcher") >= 4.0

    # Verify consecutive static photos are rejected by shot_planner under pow_documentary_v3
    d = _minimal_manifest_dict()
    d["shots"][1]["kind"] = "still_full"
    d["shots"][1]["src_file"] = "a.jpg"
    d["shots"][0]["has_human_interaction"] = True
    ep = EpisodeManifest.model_validate(d)
    style = ep.resolve_style_profile()
    fake_wt = {
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [{"seg_id": "N01", "start": 0.1, "end": 14.8, "text": "Test"}],
        "words": [
            {"seg_id": "N01", "word": "First.", "start": 0.1, "end": 4.35},
            {"seg_id": "N01", "word": "Second.", "start": 4.60, "end": 8.85},
            {"seg_id": "N01", "word": "Third.", "start": 9.10, "end": 13.35},
            {"seg_id": "N01", "word": "Fourth.", "start": 13.60, "end": 14.90},
        ],
    }
    audit = audit_shot_plan_and_alignment(ep, fake_wt, style)
    assert any("Consecutive static photo shots" in e for e in audit["errors"])
    assert audit["human_interaction_shots"] == 1


def test_v4_viral_anti_ai_linter_color_grade_and_boxless_captions():
    from pow_studio.color_grade import apply_documentary_color_grade
    from pow_studio.script_linter import audit_viral_shorts_script

    # 1. Anti-AI script linter blocks LLM clichés, 4-term Latin lists, and 1.4s loop-killing tail silence
    d = _minimal_manifest_dict()
    d["narration_segments"][2]["text"] = (
        "Still, there's an important caveat: micro-eukaryotes, haptophytes, dinoflagellates, and cyanobacteria."
    )
    d["narration_segments"][2]["pause_after_s"] = 1.40
    ep_bad = EpisodeManifest.model_validate(d)
    style = ep_bad.resolve_style_profile()
    res_bad = audit_viral_shorts_script(ep_bad, style)
    assert res_bad["anti_ai_script_pass"] is False
    assert res_bad["llm_cliche_hits"] >= 1
    assert res_bad["jargon_cluster_hits"] >= 1

    # 2. Clean conversational script passes with zero errors
    d_ok = _minimal_manifest_dict()
    d_ok["narration_segments"][0]["rate"] = "+3%"
    d_ok["narration_segments"][2]["pause_after_s"] = 0.28
    ep_ok = EpisodeManifest.model_validate(d_ok)
    res_ok = audit_viral_shorts_script(ep_ok, style)
    assert res_ok["anti_ai_script_pass"] is True

    # 3. Opening static photo > 2.3s is blocked so motion always starts within ~2s
    d_slow_open = _minimal_manifest_dict()
    d_slow_open["shots"][0]["kind"] = "still_full"
    d_slow_open["shots"][0]["src_file"] = "a.jpg"
    ep_slow = EpisodeManifest.model_validate(d_slow_open)
    fake_wt = {
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [{"seg_id": "N01", "start": 0.1, "end": 14.8, "text": "Test"}],
        "words": [{"seg_id": "N01", "word": "First.", "start": 0.1, "end": 14.8}],
    }
    audit_slow = audit_shot_plan_and_alignment(ep_slow, fake_wt, style)
    assert any("Opening shot is a static photo" in e for e in audit_slow["errors"])

    # 4. Unified 35mm documentary color grade + temporal luma grain
    base_im = Image.new("RGB", (320, 568), (242, 245, 250))
    g0 = apply_documentary_color_grade(base_im, frame_idx=0, enable_grade=True, luma_grain_sigma=2.3)
    g1 = apply_documentary_color_grade(base_im, frame_idx=1, enable_grade=True, luma_grain_sigma=2.3)
    assert g0.size == (320, 568)
    assert float(np.mean(np.abs(np.asarray(g1, dtype=np.float32) - np.asarray(g0, dtype=np.float32)))) > 0.5


def test_subpulse_bridge_cli_and_missing_mp4_guard(tmp_path):
    from pow_studio.cli import app as cli_app
    from pow_studio.subpulse_bridge import publish_episode_via_subpulse

    registered = {cmd.name for cmd in cli_app.registered_commands}
    assert "sprint" in registered
    assert "publish" in registered

    d = _minimal_manifest_dict()
    d["output_dir"] = str(tmp_path / "ep_out")
    Path(d["output_dir"]).mkdir(parents=True, exist_ok=True)
    ep = EpisodeManifest.model_validate(d)

    with pytest.raises(FileNotFoundError, match="Master MP4 not found"):
        publish_episode_via_subpulse(ep, base_url="http://127.0.0.1:59999")


def test_phase2_story_engine_topic_hooks_momentum_and_retention_plan(tmp_path: Path):
    from pow_studio.story_engine import (
        TopicAngleCandidate,
        audit_narrative_momentum,
        evaluate_opening_hook_candidates,
        evaluate_topic_opportunity,
        generate_retention_plan,
    )

    # 1. Topic opportunity ranking penalizes sensationalism & rewards evidence + visual potential
    opp = evaluate_topic_opportunity(
        topic_name="Antarctic Subglacial Brine Ecosystem (Blood Falls)",
        category="Hidden Earth",
        angles=[
            TopicAngleCandidate(
                angle_id="A_SENSATIONAL",
                title="Proof of Aliens Bleeding Under Antarctica",
                framing_summary="Sensational mystery claim without evidence",
                archetype="unexplained_mystery",
                surprise_level=9.8,
                visual_reveal_strength=8.5,
                familiarity_balance=6.0,
                meaningful_mystery=7.0,
                counterintuitive_fact=6.0,
                unanswered_question=5.0,
                scientific_explanation_value=3.0,
                authentic_footage_feasibility=3.5,
                credible_evidence_depth=2.5,
                story_arc_completeness=4.0,
                sensationalism_risk=9.5,
            ),
            TopicAngleCandidate(
                angle_id="B_DOCUMENTARY",
                title="Why a Glacier Bleeds Iron-Rich Brine Harboring Ancient Microbes",
                framing_summary="Visual paradox -> iron oxidation chemistry -> 2026 subglacial biosphere pivot",
                archetype="scientific_discovery",
                surprise_level=9.1,
                visual_reveal_strength=9.6,
                familiarity_balance=8.8,
                meaningful_mystery=9.0,
                counterintuitive_fact=9.2,
                unanswered_question=8.6,
                scientific_explanation_value=9.5,
                authentic_footage_feasibility=9.2,
                credible_evidence_depth=9.6,
                story_arc_completeness=9.4,
                sensationalism_risk=0.5,
            ),
        ],
    )
    assert opp["selected_angle_id"] == "B_DOCUMENTARY"
    assert opp["angles"][0]["composite_score"] > opp["angles"][1]["composite_score"] + 2.5

    # 2. Opening hook evaluator ranks authentic paradox hook above generic channel intro
    d = _minimal_manifest_dict()
    d["hook_candidates"] = [
        {
            "hook_id": "H_WEAK_INTRO",
            "archetype": "unexpected_fact",
            "spoken_line": "Welcome back to Proof of Wonder, in today's video we look at Antarctica.",
            "opening_visual": "Logo card",
            "promise_fulfilled_in_seg_id": "N02",
        },
        {
            "hook_id": "H_PARADOX",
            "archetype": "paradox",
            "spoken_line": "A five-story crimson waterfall pours straight out of solid Antarctic ice.",
            "opening_visual": "Aerial close-up of crimson brine plume cutting across Taylor Glacier",
            "src_file": "clip.mp4",
            "promise_fulfilled_in_seg_id": "N03",
        },
    ]
    d["narration_segments"] = [
        {"seg_id": "N01", "text": "A five-story crimson waterfall pours straight out of solid Antarctic ice."},
        {"seg_id": "N02", "text": "Scientists sampled 167 subglacial brine layers beneath Taylor Glacier."},
        {"seg_id": "N03", "text": "Iron-rich brine oxidizes on contact with oxygen, though isolation remains under study."},
    ]
    ep = EpisodeManifest.model_validate(d)
    hooks = evaluate_opening_hook_candidates(ep)
    assert hooks["recommended_hook_id"] == "H_PARADOX"
    assert hooks["candidates"][0]["composite_hook_score"] > hooks["candidates"][1]["composite_hook_score"] + 1.5

    # 3. Narrative momentum audit catches generic intro, unsupported claim, and subscribe CTA
    d_bad = _minimal_manifest_dict()
    d_bad["narration_segments"] = [
        {"seg_id": "N01", "text": "Welcome to Proof of Wonder! Today we explore a waterfall."},
        {"seg_id": "N02", "text": "It defies all laws of physics and no scientist can explain it."},
        {"seg_id": "N03", "text": "Caveat: smash that like and subscribe for more!"},
    ]
    ep_bad = EpisodeManifest.model_validate(d_bad)
    mom_bad = audit_narrative_momentum(ep_bad)
    assert mom_bad["momentum_pass"] is False
    cats = {i["category"] for i in mom_bad["issues"]}
    assert "unnecessary_introduction" in cats
    assert "unsupported_dramatic_claim" in cats
    assert "weak_conclusion_generic_cta" in cats

    # 4. Retention plan emits exact 7-column markdown & JSON
    mom_good = audit_narrative_momentum(ep)
    assert mom_good["momentum_pass"] is True
    rplan = generate_retention_plan(ep, out_dir=tmp_path)
    assert (tmp_path / "retention_plan.md").exists()
    assert (tmp_path / "retention_plan.json").exists()
    assert "| Time | Narrative beat | Viewer question | New information | Visual reveal | Emotional direction | Retention purpose |" in rplan["markdown_table"]
    assert len(rplan["rows"]) == 3


def test_phase2_visual_intelligence_scoring_and_adaptive_shot_planner(tmp_path: Path):
    from pow_studio.shot_planner import build_semantic_timeline_manifest, calculate_adaptive_shot_duration
    from pow_studio.style_profile import VisualScoringWeightsConfig
    from pow_studio.visual_intelligence import nasa_metadata_is_clean_public_domain, score_asset_candidate

    # 1. NASA metadata third-party copyright screening
    clean_ok, _ = nasa_metadata_is_clean_public_domain({"center": "GSFC", "description": "Landsat flyover of Taylor Valley."})
    assert clean_ok is True
    dirty_ok, reason = nasa_metadata_is_clean_public_domain(
        {"center": "HQ", "secondary_creator": "Copyright National Geographic, used with permission"}
    )
    assert dirty_ok is False and "copyright" in reason.lower()

    # 2. Authentic relevant photograph beats visually sharp but irrelevant HD video!
    rel_photo = score_asset_candidate(
        asset_id="bf_aerial_2013.jpg",
        narration_text="Crimson iron-rich brine pours out of Taylor Glacier at Blood Falls.",
        asset_metadata_text="Blood Falls crimson iron brine plume on Taylor Glacier Antarctica",
        media_type="photo",
        license_str="Public Domain (NSF)",
        width=3000,
        height=2000,
        subject_match_kind="direct_subject",
        is_authentic_real_capture=True,
    )
    irrel_video = score_asset_candidate(
        asset_id="tropical_waterfall_4k.mp4",
        narration_text="Crimson iron-rich brine pours out of Taylor Glacier at Blood Falls.",
        asset_metadata_text="Lush green tropical jungle waterfall in Hawaii at sunset",
        media_type="video",
        license_str="CC0 1.0",
        width=3840,
        height=2160,
        subject_match_kind="unrelated",
        is_authentic_real_capture=True,
        has_verified_motion=True,
    )
    assert rel_photo.eligible_for_selection is True
    assert irrel_video.eligible_for_selection is False
    assert rel_photo.weighted_score > irrel_video.weighted_score + 0.45

    # 3. AI-generated imagery is strictly disqualified as documentary evidence
    ai_img = score_asset_candidate(
        asset_id="midjourney_glacier.png",
        narration_text="Crimson iron-rich brine pours out of Taylor Glacier.",
        asset_metadata_text="Crimson iron-rich brine pours out of Taylor Glacier",
        media_type="photo",
        license_str="CC0 1.0",
        is_authentic_real_capture=False,
        is_ai_generated=True,
    )
    assert ai_img.eligible_for_selection is False
    assert ai_img.authenticity == 0.0

    # 4. Configurable weights work deterministically
    custom_w = VisualScoringWeightsConfig(direct_relevance=0.50, authenticity=0.25, visual_clarity=0.10, technical_quality=0.05, composition_potential=0.05, motion_storytelling=0.02, license_verification=0.03)
    custom_scored = score_asset_candidate(
        asset_id="bf_aerial_2013.jpg",
        narration_text="Taylor Glacier Blood Falls iron brine",
        asset_metadata_text="Taylor Glacier Blood Falls iron brine NSF",
        media_type="photo",
        license_str="Public Domain (NSF)",
        weights=custom_w,
    )
    assert custom_scored.weighted_score > 0.85

    # 5. Adaptive shot duration gives complex aerial reveal more time than simple close-up context
    dur_aerial_reveal = calculate_adaptive_shot_duration(
        visual_complexity="high",
        spoken_importance="central_reveal",
        camera_perspective="aerial",
        camera_movement="aerial_sweep",
        is_moving_footage=True,
        spoken_word_count=16,
        quantitative_fact_count=2,
    )
    dur_closeup_ctx = calculate_adaptive_shot_duration(
        visual_complexity="low",
        spoken_importance="context",
        camera_perspective="close_up",
        camera_movement="static",
        is_moving_footage=True,
        spoken_word_count=6,
        quantitative_fact_count=0,
    )
    assert dur_aerial_reveal["ideal_duration_s"] > dur_closeup_ctx["ideal_duration_s"] + 1.8

    # 6. Anti-repeated-still-zoom rule & Semantic Timeline Manifest export
    d = _minimal_manifest_dict()
    d["output_dir"] = str(tmp_path / "sem_out")
    Path(d["output_dir"]).mkdir(parents=True, exist_ok=True)
    d["shots"][0]["camera_perspective"] = "aerial"
    d["shots"][2]["camera_perspective"] = "close_up"
    ep = EpisodeManifest.model_validate(d)
    fake_wt = {
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [{"seg_id": "N01", "start": 0.1, "end": 14.8, "text": "Hook line. Pivot line."}],
        "words": [
            {"seg_id": "N01", "word": "Hook.", "start": 0.1, "end": 4.35},
            {"seg_id": "N01", "word": "Pivot.", "start": 4.60, "end": 8.85},
            {"seg_id": "N01", "word": "Photo.", "start": 9.10, "end": 13.35},
            {"seg_id": "N01", "word": "Diagram.", "start": 13.60, "end": 14.90},
        ],
    }
    sem = build_semantic_timeline_manifest(ep, fake_wt)
    assert sem["scene_count"] == 4
    assert (Path(d["output_dir"]) / "semantic_timeline_manifest.json").exists()
    assert sem["scenes"][0]["camera_perspective"] == "aerial"

    # Reusing the same still photo `a.jpg` twice (even separated by video) is flagged as error
    d_repeat_still = _minimal_manifest_dict()
    d_repeat_still["shots"].append(
        {
            "sid": "S05",
            "start_s": 15.0,
            "end_s": 18.0,
            "kind": "still_full",
            "src_file": "a.jpg",
            "is_real_evidence": True,
            "story_beat": "repeat zoom",
            "visual_desc": "zooming into same photo again",
        }
    )
    ep_rep = EpisodeManifest.model_validate(d_repeat_still)
    fake_wt_18 = dict(fake_wt, total_duration_s=18.0, total_frames_30fps=540)
    audit_rep = audit_shot_plan_and_alignment(ep_rep, fake_wt_18, ep_rep.resolve_style_profile())
    assert any("Still photograph 'a.jpg' is reused multiple times" in e for e in audit_rep["errors"])


def test_phase3_voice_studio_profiles_parser_prosody_and_reference_consent(tmp_path: Path):
    import subprocess
    from pow_studio.voice_studio import (
        analyze_voice_reference,
        list_voice_direction_profiles,
        load_voice_direction_profile,
        parse_annotated_voice_script,
        resolve_sentence_prosody,
    )

    # 1. Verify all 7 reusable Voice Direction Presets load cleanly
    vprofs = list_voice_direction_profiles()
    for pid in (
        "cinematic_documentary",
        "curious_explorer",
        "scientific_authority",
        "mysterious_discovery",
        "dramatic_reveal",
        "calm_explanation",
        "emotional_reflection",
    ):
        assert pid in vprofs
        vp = load_voice_direction_profile(pid)
        assert vp.profile_id == pid

    # 2. Parse exact Section 5.3 pre-generation bracketed voice annotation script
    sample_script = '''
"Deep beneath the Antarctic ice..."

[DELIVERY: MYSTERIOUS]
[PACE: SLOW]
[ENERGY: 2/5]
[EMPHASIS: "Deep beneath"]
[PAUSE AFTER: 500ms]

"Scientists discovered something extraordinary."

[DELIVERY: SURPRISED BUT CONTROLLED]
[PACE: NATURAL]
[ENERGY: 4/5]
[EMPHASIS: "something extraordinary"]
[PAUSE AFTER: 350ms]

"But it wasn't what they expected."

[DELIVERY: CINEMATIC REVEAL]
[PACE: SLOW]
[ENERGY: 3/5]
[EMPHASIS: "wasn't"]
[PAUSE AFTER: 700ms]
'''
    parsed = parse_annotated_voice_script(sample_script)
    assert len(parsed) == 3
    assert parsed[0].text == "Deep beneath the Antarctic ice..."
    assert parsed[0].delivery == "MYSTERIOUS"
    assert parsed[0].pace == "SLOW"
    assert parsed[0].energy == 2
    assert parsed[0].emphasis_phrases == ["Deep beneath"]
    assert parsed[0].pause_after_ms == 500

    assert parsed[1].delivery == "SURPRISED BUT CONTROLLED"
    assert parsed[1].energy == 4
    assert parsed[1].pause_after_ms == 350

    assert parsed[2].delivery == "CINEMATIC REVEAL"
    assert parsed[2].emphasis_phrases == ["wasn't"]
    assert parsed[2].pause_after_ms == 700

    prof = load_voice_direction_profile("mysterious_discovery")
    r0 = resolve_sentence_prosody(parsed[0], prof)
    r1 = resolve_sentence_prosody(parsed[1], prof)
    assert r0.pause_after_ms == 500
    assert "deep" in r0.emphasis_word_norms and "beneath" in r0.emphasis_word_norms
    # Slow mysterious line speaks slower than surprised natural line, within human +/-10% bounds
    assert int(r0.rate_str.replace("%", "")) < int(r1.rate_str.replace("%", ""))
    assert abs(int(r0.rate_str.replace("%", ""))) <= prof.max_rate_delta_pct
    assert abs(int(r0.pitch_str.replace("Hz", ""))) <= prof.max_pitch_delta_hz

    # 3. Mode B Voice Reference: enforce owner consent & calibrate profile from real audio slice
    src_mp3 = CHANNEL_ROOT / "output" / "hidden-earth" / "blood-falls-v3-documentary" / "narration.mp3"
    ref_slice = tmp_path / "owner_voice_sample_10s.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-t", "10", "-i", str(src_mp3), str(ref_slice)],
        check=True,
    )
    with pytest.raises(PermissionError, match="voice_owner_consent=True"):
        analyze_voice_reference(ref_slice, voice_owner_consent=False)

    cal_yaml = tmp_path / "calibrated_owner.yaml"
    ref_res = analyze_voice_reference(ref_slice, voice_owner_consent=True, out_profile_yaml=cal_yaml)
    assert ref_res["consent_verified"] is True
    assert ref_res["zero_shot_voice_cloning_active"] is False
    assert cal_yaml.exists()
    assert 60.0 <= ref_res["acoustic_metrics"]["median_f0_hz"] <= 300.0
    assert ref_res["acoustic_metrics"]["measured_wpm"] > 50.0


def test_phase3_mode_a_uploaded_narration_5layer_audio_and_approval_lock(tmp_path: Path):
    import subprocess
    from pow_studio.audio_engine import build_episode_audio
    from pow_studio.voice_studio import (
        approve_and_lock_voice_master,
        auto_build_caption_groups_from_words,
        verify_voice_approval_lock,
    )

    src_mp3 = CHANNEL_ROOT / "output" / "hidden-earth" / "blood-falls-v3-documentary" / "narration.mp3"
    uploaded_clip = tmp_path / "uploaded_human_take.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-t", "9.5", "-i", str(src_mp3), str(uploaded_clip)],
        check=True,
    )

    d = _minimal_manifest_dict()
    d["output_dir"] = str(tmp_path / "mode_a_ep")
    d["voice_input_mode"] = "uploaded_narration"
    d["uploaded_narration_file"] = str(uploaded_clip)
    d["narration_segments"] = [
        {"seg_id": "N01", "text": "A five-story crimson waterfall pours straight out of solid Antarctic ice.", "emphasis_words": ["crimson"]},
        {"seg_id": "N02", "text": "In 1911 geologists first blamed red algae."},
        {"seg_id": "N03", "text": "Caveat: continuous isolation remains under study."},
    ]
    d["sfx_cues"] = [{"sfx_name": "glacial_sub_drop", "anchor_type": "shot_start", "anchor_ref": "S01", "gain_db": -24.0}]
    ep = EpisodeManifest.model_validate(d)

    wt = build_episode_audio(ep)
    assert wt["voice_input_mode"] == "uploaded_narration"
    assert len(wt["words"]) >= 8

    # Verify all 5 stereo stems & audio diagnostics report exist
    work_audio = Path(d["output_dir"]) / "work_audio"
    for stem_name in (
        "layer_1_narration.wav",
        "layer_2_music.wav",
        "layer_3_ambience.wav",
        "layer_4_natural_sounds.wav",
        "layer_5_cinematic_sfx.wav",
        "final_audio_mix.wav",
    ):
        assert (work_audio / stem_name).exists()

    rep_p = Path(d["output_dir"]) / "audio_engineering_report.json"
    assert rep_p.exists()
    assert wt["audio_diagnostics"]["clipped_samples_count"] == 0

    # Verify auto phrase caption builder & SHA-256 voice approval lock
    auto_cues = auto_build_caption_groups_from_words(wt)
    assert len(auto_cues) >= 2

    lock = approve_and_lock_voice_master(ep, reviewer_note="Mode A pytest lock")
    assert lock["script_sha256"]
    v_ok = verify_voice_approval_lock(ep)
    assert v_ok["locked"] is True and v_ok["synchronized"] is True


def test_phase4_thumbnail_concepts_subtitles_manifest_v6_analytics_and_cli(tmp_path: Path):
    import json
    from pow_studio.analytics_learning import (
        generate_channel_learning_report,
        parse_youtube_studio_csv,
        review_single_video_performance,
    )
    from pow_studio.cli import app
    from pow_studio.compositor import compute_overlay_states, render_thumbnail_concepts_for_episode
    from pow_studio.manifest_v6 import export_versioned_production_manifest

    # 1. Multi-concept Thumbnail Studio + mobile comparison sheet + CTR disclaimer
    d = _minimal_manifest_dict()
    d["output_dir"] = str(tmp_path / "phase4_ep")
    d["raw_assets_dir"] = str(CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3")
    for fn, agency in (
        ("bf_aerial_2013.jpg", "NSF"),
        ("bf_2010_12_14.jpg", "NSF"),
        ("nasa_m12666_nansen_scientists_ice.mp4", "NASA"),
    ):
        d["assets_register"].append(
            {
                "local_file": fn,
                "title": fn,
                "creator_agency": agency,
                "source_page_url": "https://www.nsf.gov",
                "direct_media_url": f"https://www.nsf.gov/{fn}",
                "license": f"Public Domain ({agency})",
                "license_url": "https://www.nsf.gov/policies/reuse.jsp",
                "required_attribution": f"{agency} (Public Domain)",
            }
        )
    d["thumbnail_concepts"] = [
        {
            "concept_id": "A",
            "src_file": "bf_aerial_2013.jpg",
            "headline_text": "WHY GLACIER|BLEEDS RED",
            "kicker_text": "ANTARCTICA",
            "concept_rationale": "Aerial contrast between white glacier and red plume",
        },
        {
            "concept_id": "B",
            "src_file": "bf_2010_12_14.jpg",
            "headline_text": "SEALED FOR|MILLIONS OF YEARS",
            "concept_rationale": "Researcher standing before iron-brine ice cliff",
        },
        {
            "concept_id": "C",
            "src_file": "nasa_m12666_nansen_scientists_ice.mp4",
            "video_time_s": 27.0,
            "headline_text": "",
            "concept_rationale": "Pure documentary helicopter frame with zero text",
        },
    ]
    d["caption_groups"] = []  # Test auto phrase-grouped subtitle fallback when caption_groups is omitted!
    d["style_profile"] = "space_discovery"  # Uses `minimal_editorial` subtitle style
    ep = EpisodeManifest.model_validate(d)

    tpkg = render_thumbnail_concepts_for_episode(ep)
    assert len(tpkg["concepts"]) == 3
    assert (Path(d["output_dir"]) / "thumbnail_concept_A.jpg").exists()
    assert (Path(d["output_dir"]) / "thumbnail_concept_B.jpg").exists()
    assert (Path(d["output_dir"]) / "thumbnail_concept_C.jpg").exists()
    assert (Path(d["output_dir"]) / "thumbnail_concepts_comparison_sheet.jpg").exists()
    tman = json.loads((Path(d["output_dir"]) / "thumbnail_concepts_manifest.json").read_text(encoding="utf-8"))
    assert "do NOT predict real YouTube click-through" in tman["ctr_prediction_disclaimer"]

    # 2. Auto phrase-grouped subtitles + minimal_editorial overlay state computation
    fake_wt = {
        "voice": "en-GB-RyanNeural",
        "total_duration_s": 15.0,
        "total_frames_30fps": 450,
        "segments": [{"seg_id": "N01", "start": 0.1, "end": 14.8, "text": "Hook line. Pivot line."}],
        "words": [
            {"seg_id": "N01", "word": "A", "start": 0.10, "end": 0.25, "emphasis": False},
            {"seg_id": "N01", "word": "crimson", "start": 0.26, "end": 0.65, "emphasis": True},
            {"seg_id": "N01", "word": "plume", "start": 0.66, "end": 1.05, "emphasis": False},
            {"seg_id": "N01", "word": "pours.", "start": 1.06, "end": 1.50, "emphasis": False},
            {"seg_id": "N01", "word": "Iron", "start": 2.10, "end": 2.50, "emphasis": True},
            {"seg_id": "N01", "word": "oxidizes.", "start": 2.52, "end": 3.10, "emphasis": False},
        ],
    }
    states, nframes, _, _, cues = compute_overlay_states(ep, fake_wt)
    assert nframes == 450
    assert len(cues) >= 2
    assert len(states) >= 3

    # 3. Versioned Production Manifest v6 (all 14 Section 14 fields present)
    pm = export_versioned_production_manifest(ep, fake_wt, qc={"overall_studio_v6_pass": True, "failed_gates_count": 0})
    for req_key in (
        "topic",
        "production_profile",
        "script_version",
        "voice_direction_profile",
        "audio_source_and_final_narration",
        "source_assets",
        "licensing_metadata",
        "shot_list",
        "scene_timing",
        "subtitle_version",
        "thumbnail_variants",
        "rendering_configuration",
        "qa_results",
        "final_output_locations",
    ):
        assert req_key in pm, f"Missing required Section 14 field: {req_key}"

    # 4. YouTube Studio CSV Analytics Importer & Correlation-vs-Causation Guardrails
    csv_file = tmp_path / "Table data.csv"
    csv_file.write_text(
        "Content,Video title,Views,Viewed (vs. swiped away) (%),Average view duration,Average percentage viewed (%),Likes,Comments,Subscribers,Duration\n"
        "Total,Total,12000,71.4,0:00:52,81.2,640,42,38,\n"
        "abc123xyz,Why This Antarctic Glacier Bleeds Deep Red,8500,74.2,0:00:56,84.8,510,31,29,66\n"
        "def456uvw,Slow Opening Test Video,3500,54.1,0:00:28,44.0,130,11,9,64\n",
        encoding="utf-8",
    )
    recs = parse_youtube_studio_csv(csv_file)
    assert len(recs) == 2
    assert recs[0].video_id == "abc123xyz"
    assert recs[0].viewed_vs_swiped_away_pct == 74.2
    assert recs[0].average_view_duration_s == 56.0

    rev_slow = review_single_video_performance(recs[1])
    assert "NOT proven causation" in rev_slow["causation_guardrail"]
    assert any("54.1%" in f["observation"] for f in rev_slow["findings"])

    learn_rep = generate_channel_learning_report(recs, out_dir=tmp_path / "analytics_out")
    assert (tmp_path / "analytics_out" / "performance_review.md").exists()
    assert "Correlation != Causation" in learn_rep["methodology_disclaimer"]

    # 5. Verify all 6-stage Studio CLI commands & existing commands are registered
    cmd_names = {c.name or c.callback.__name__ for c in app.registered_commands}
    for expected_cmd in (
        "validate",
        "audio",
        "plan-check",
        "shots",
        "preview",
        "render",
        "qc",
        "all",
        "stage1-research",
        "stage2-story",
        "stage3-voice",
        "stage4-visual",
        "stage5-edit",
        "stage6-quality",
        "voice-preview",
        "voice-approve",
        "thumbnail-studio",
        "analytics-review",
        "profiles",
    ):
        assert expected_cmd in cmd_names, f"Missing CLI command: {expected_cmd}"





