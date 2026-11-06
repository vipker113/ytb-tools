#!/usr/bin/env python3
"""Studio v9 Mechanism Overlay tests: spec validation, phrase anchoring, QA, honesty reclassification, and live Manim cache."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.media_classifier import compute_visual_coverage_metrics  # noqa: E402
from pow_studio.mechanism_overlay import (  # noqa: E402
    build_ffmpeg_overlay_mux_plan,
    extract_overlay_rgba_frame,
    is_graphics_available,
    render_single_overlay_cached,
    resolve_overlay_timings,
    run_mechanism_overlay_qa,
    validate_overlay_specs,
)
from pow_studio.schema import (  # noqa: E402
    EpisodeManifest,
    MechanismOverlaySpec,
    OverlayAnchorSpec,
    OverlayRegionSpec,
    resolve_timed_shots,
)
from pow_studio.voice_studio import invalidate_dependent_timing_artifacts  # noqa: E402

PERSEUS_V6_YAML = CHANNEL_ROOT / "episodes" / "space_perseus_black_hole_v6_documentary.yaml"


def _load_test_manifest(tmp_path: Path, overlays: list[MechanismOverlaySpec]) -> EpisodeManifest:
    ep = EpisodeManifest.from_yaml(PERSEUS_V6_YAML)
    return ep.model_copy(
        update={
            "slug": "perseus-v9-overlay-unit-test",
            "output_dir": tmp_path,
            "mechanism_overlays": overlays,
        }
    )


def _sample_wt() -> dict:
    return {
        "total_duration_s": 70.633,
        "total_frames_30fps": 2119,
        "segments": [
            {"seg_id": "N01", "start": 0.0, "end": 5.6},
            {"seg_id": "N04", "start": 38.9, "end": 43.5},
        ],
        "words": [
            {"seg_id": "N01", "word": "Space", "start": 0.20, "end": 0.60},
            {"seg_id": "N01", "word": "silent", "start": 0.65, "end": 1.10},
            {"seg_id": "N04", "word": "A", "start": 39.20, "end": 39.35},
            {"seg_id": "N04", "word": "B-flat", "start": 39.40, "end": 39.75},
            {"seg_id": "N04", "word": "fifty-seven", "start": 39.80, "end": 40.30},
            {"seg_id": "N04", "word": "octaves", "start": 40.35, "end": 40.85},
            {"seg_id": "N04", "word": "below", "start": 40.90, "end": 41.25},
            {"seg_id": "N04", "word": "middle", "start": 41.30, "end": 41.65},
            {"seg_id": "N04", "word": "C.", "start": 41.70, "end": 42.10},
        ],
    }


def test_validate_overlay_specs_claim_ref_safe_zone_and_count(tmp_path: Path) -> None:
    good = MechanismOverlaySpec(
        overlay_id="ov_good",
        template="wave_frequency_scale",
        anchor=OverlayAnchorSpec(phrase="57 octaves below", seg_id="N04"),
        hold_s=3.2,
        region=OverlayRegionSpec(x=0.08, y=0.14, w=0.84, h=0.32),
        claim_ref=0,
    )
    ep_ok = _load_test_manifest(tmp_path, [good])
    assert validate_overlay_specs(ep_ok) == []

    bad_claim = good.model_copy(update={"overlay_id": "ov_bad_claim", "claim_ref": 999})
    bad_safe = good.model_copy(
        update={
            "overlay_id": "ov_bad_safe",
            "region": OverlayRegionSpec(x=0.08, y=0.04, w=0.84, h=0.30),  # y_top = 77px < 215px
        }
    )
    too_many = [good.model_copy(update={"overlay_id": f"ov_{i}"}) for i in range(5)]

    issues_bad = validate_overlay_specs(_load_test_manifest(tmp_path, [bad_claim, bad_safe]))
    codes = {i["code"] for i in issues_bad}
    assert "invalid_overlay_claim_ref" in codes
    assert "overlay_region_outside_safe_zone" in codes

    issues_many = validate_overlay_specs(_load_test_manifest(tmp_path, too_many))
    assert any(i["code"] == "too_many_mechanism_overlays" for i in issues_many)


def test_resolve_overlay_timings_phrase_hook_and_cut_rules(tmp_path: Path) -> None:
    wt = _sample_wt()
    ov_phrase = MechanismOverlaySpec(
        overlay_id="ov_phrase",
        template="wave_frequency_scale",
        anchor=OverlayAnchorSpec(phrase="57 octaves below", seg_id="N04"),
        hold_s=2.4,
        claim_ref=0,
    )
    ov_hook = MechanismOverlaySpec(
        overlay_id="ov_hook",
        template="pressure_ripple",
        anchor=OverlayAnchorSpec(start_s=0.4),
        hold_s=1.8,
        claim_ref=0,
    )
    ov_cut_blocked = MechanismOverlaySpec(
        overlay_id="ov_cut_blocked",
        template="label_leader",
        anchor=OverlayAnchorSpec(start_s=34.5),
        hold_s=3.5,  # spans S09 -> S10 hard cut at 36.013s
        span_cut=False,
        claim_ref=0,
    )
    ov_cut_allowed = ov_cut_blocked.model_copy(update={"overlay_id": "ov_cut_ok", "span_cut": True})

    ep = _load_test_manifest(tmp_path, [ov_phrase, ov_hook, ov_cut_blocked, ov_cut_allowed])
    timed_shots = resolve_timed_shots(ep, 2119, fps=30)
    resolved = resolve_overlay_timings(ep, wt, timed_shots=timed_shots, fps=30)
    by_id = {r.overlay_id: r for r in resolved}

    assert by_id["ov_phrase"].anchor_source == "phrase_in_N04"
    assert abs(by_id["ov_phrase"].start_s - 39.80) < 0.08
    assert not by_id["ov_phrase"].in_hook_zone

    assert by_id["ov_hook"].in_hook_zone is True
    assert by_id["ov_cut_blocked"].crosses_hard_cut is True

    qa_rep = run_mechanism_overlay_qa(
        manifest=ep,
        resolved_timings=resolved,
        rendered_paths={},
        timed_shots=timed_shots,
        cues=[{"start": 39.5, "end": 42.2, "text": "fifty-seven octaves below middle C"}],
        total_duration_s=70.633,
        out_dir=tmp_path,
    )
    codes = {i["code"] for i in qa_rep["issues"]}
    assert "overlay_in_opening_hook" in codes
    assert "overlay_crosses_hard_cut" in codes
    assert not any(
        i["code"] == "overlay_crosses_hard_cut" and i["overlay_id"] == "ov_cut_ok" for i in qa_rep["issues"]
    )


def test_caption_duplication_and_honesty_reclassification(tmp_path: Path) -> None:
    wt = _sample_wt()
    ov_dup = MechanismOverlaySpec(
        overlay_id="ov_dup",
        template="label_leader",
        anchor=OverlayAnchorSpec(start_s=39.8),
        hold_s=2.2,
        claim_ref=0,
        params={"text": "57 octaves below middle C"},
    )
    ep = _load_test_manifest(tmp_path, [ov_dup])
    # Replace S11 with genuine moving footage so we can test honesty preservation vs reclassification
    real_shots = [
        s.model_copy(
            update={
                "src_file": "perseus_sonification_chandra_1080p.mp4",
                "camera_perspective": "satellite_or_telescope",
                "is_real_evidence": True,
                "subject_match_kind": "direct_subject",
            }
        )
        if s.sid == "S11"
        else s
        for s in ep.shots
    ]
    ep = ep.model_copy(update={"shots": real_shots})
    timed_shots = resolve_timed_shots(ep, 2119, fps=30)
    resolved = resolve_overlay_timings(ep, wt, timed_shots=timed_shots, fps=30)

    qa_rep = run_mechanism_overlay_qa(
        manifest=ep,
        resolved_timings=resolved,
        rendered_paths={},
        timed_shots=timed_shots,
        cues=[{"start": 39.5, "end": 42.5, "text": "A B-flat 57 octaves below middle C."}],
        total_duration_s=70.633,
        out_dir=tmp_path,
    )
    assert any(i["code"] == "overlay_text_duplicates_caption" for i in qa_rep["issues"])

    # Case 1: alpha <= 35% (no reclassified_infographic_intervals) -> genuine_moving_footage stays intact!
    cov_intact = compute_visual_coverage_metrics(timed_shots, ep.assets_register, manifest=ep, probe_pixels=False)
    assert cov_intact["mechanism_overlay_s"] == pytest.approx(2.2, abs=0.05)
    assert cov_intact["reclassified_overlay_infographic_s"] == 0.0

    # Case 2: alpha > 35% for > 1.0s -> interval subtracted from REAL_VIDEO_* and added to INFOGRAPHIC
    qa_reclass = dict(qa_rep)
    qa_reclass["reclassified_infographic_intervals"] = [
        {"overlay_id": "ov_dup", "start_s": 39.8, "end_s": 42.0, "duration_s": 2.2, "max_alpha_area_ratio": 0.48}
    ]
    (tmp_path / "mechanism_overlay_qa.json").write_text(json.dumps(qa_reclass), encoding="utf-8")
    cov_reclass = compute_visual_coverage_metrics(timed_shots, ep.assets_register, manifest=ep, probe_pixels=False)
    assert cov_reclass["reclassified_overlay_infographic_s"] == pytest.approx(2.2, abs=0.1)
    assert cov_reclass["genuine_moving_footage_s"] == pytest.approx(
        cov_intact["genuine_moving_footage_s"] - cov_reclass["reclassified_overlay_infographic_s"],
        abs=0.05,
    )
    assert cov_reclass["infographic_s"] == pytest.approx(
        cov_intact["infographic_s"] + cov_reclass["reclassified_overlay_infographic_s"],
        abs=0.05,
    )


def test_invalidate_dependent_timing_artifacts_cleans_overlays(tmp_path: Path) -> None:
    (tmp_path / "mechanism_overlay_qa.json").write_text("{}", encoding="utf-8")
    ov_dir = tmp_path / "overlays"
    ov_dir.mkdir()
    (ov_dir / "ov1_deadbeef.mov").write_bytes(b"0" * 2048)

    removed = invalidate_dependent_timing_artifacts(tmp_path, "sig_old", "sig_new")
    assert "mechanism_overlay_qa.json" in removed
    assert any("overlays/*.mov" in r for r in removed)
    assert not (tmp_path / "mechanism_overlay_qa.json").exists()
    assert list(ov_dir.glob("*.mov")) == []


@pytest.mark.graphics
def test_live_manim_render_alpha_safe_zone_and_cache(tmp_path: Path) -> None:
    ok_gfx, note = is_graphics_available()
    if not ok_gfx:
        pytest.skip(note)

    wt = _sample_wt()
    ov_scale = MechanismOverlaySpec(
        overlay_id="ov_scale",
        template="wave_frequency_scale",
        anchor=OverlayAnchorSpec(phrase="fifty-seven octaves below", seg_id="N04"),
        hold_s=2.0,
        region=OverlayRegionSpec(x=0.08, y=0.15, w=0.84, h=0.34),
        claim_ref=0,
        params={
            "title": "ACOUSTIC FREQUENCY DROP",
            "marker_label": "-57 OCTAVES",
            "ticks": [
                {"label": "261.6 Hz  MIDDLE C", "sub": "Piano reference"},
                {"label": "20 Hz  EAR LIMIT", "sub": "Lowest human pitch"},
                {"label": "PERSEUS B-FLAT", "sub": "1 wave / 10M yr"},
            ],
        },
    )
    ov_ripple = MechanismOverlaySpec(
        overlay_id="ov_ripple",
        template="pressure_ripple",
        anchor=OverlayAnchorSpec(start_s=13.0),
        hold_s=1.8,
        region=OverlayRegionSpec(x=0.14, y=0.18, w=0.72, h=0.34),
        claim_ref=0,
        params={"center": [0.50, 0.34], "rings": 4, "label": "PRESSURE RIPPLES"},
    )

    ep = _load_test_manifest(tmp_path, [ov_ripple, ov_scale])
    timed_shots = resolve_timed_shots(ep, 2119, fps=30)
    timings = resolve_overlay_timings(ep, wt, timed_shots=timed_shots, fps=30)
    overlays_dir = tmp_path / "overlays"

    rendered_paths: dict[str, Path] = {}
    for rt, spec in zip(timings, [ov_ripple, ov_scale]):
        mov_p, cached_1, elapsed_1 = render_single_overlay_cached(spec, rt, overlays_dir, fps=30, use_cache=True)
        assert mov_p.exists() and mov_p.stat().st_size > 4096
        assert cached_1 is False and elapsed_1 > 0.0

        # Second call with identical spec + frame count MUST hit SHA-256 cache in 0.0s
        mov_p2, cached_2, elapsed_2 = render_single_overlay_cached(spec, rt, overlays_dir, fps=30, use_cache=True)
        assert mov_p2 == mov_p
        assert cached_2 is True and elapsed_2 == 0.0
        rendered_paths[rt.overlay_id] = mov_p

    rgba_mid = extract_overlay_rgba_frame(rendered_paths["ov_scale"], 1.0)
    assert rgba_mid is not None and rgba_mid.size == (1080, 1920) and rgba_mid.mode == "RGBA"

    qa_rep = run_mechanism_overlay_qa(
        manifest=ep,
        resolved_timings=timings,
        rendered_paths=rendered_paths,
        timed_shots=timed_shots,
        cues=[{"start": 39.5, "end": 42.2, "text": "A B-flat fifty-seven octaves below middle C."}],
        total_duration_s=70.633,
        out_dir=tmp_path,
    )
    assert qa_rep["qa_passed"] is True, f"Unexpected QA issues: {qa_rep['issues']}"
    for ov_item in qa_rep["overlays"]:
        am = ov_item["alpha_metrics"]
        assert am["valid"] is True
        assert 0.005 < am["max_alpha_area_ratio"] <= 0.35
        x0, y0, x1, y1 = am["bbox_1080x1920"]
        assert 215 - 4 <= y0 < y1 <= 1380 + 4

    # Verify mux plan for <= 6 overlays
    extra_in, f_pref, next_idx, temps = build_ffmpeg_overlay_mux_plan(
        timings=timings,
        rendered_paths=rendered_paths,
        scratch_dir=tmp_path,
        total_frames=2119,
        fps=30,
    )
    assert len(extra_in) == 4  # two `-i <mov>` pairs
    assert "[v_mech]" in f_pref and next_idx == 3 and temps == []
