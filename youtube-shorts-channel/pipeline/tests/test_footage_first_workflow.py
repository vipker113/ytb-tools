#!/usr/bin/env python3
"""
Unit & Integration Validation Suite for Proof of Wonder Studio v8.0
(`PROOF OF WONDER — FUTURE VIDEO PRODUCTION WORKFLOW OPTIMIZATION`, Parts 1–10 / Section 17).

Validates all reusable Footage-First & Action-Based Storytelling upgrades using synthetic
media metadata, local temporary test clips, dry-run storyboards, and simulated timelines —
WITHOUT touching, editing, or regenerating `3 Places That Look Fake—Inside Earth's Deadliest Zones.mp4`
or any existing project/asset.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.action_storytelling import (  # noqa: E402
    analyze_visual_feasibility,
    build_action_storyboard_plan,
    evaluate_action_visual_match,
    extract_narration_visual_beats,
    generate_footage_search_queries,
)
from pow_studio.creative_qa import run_six_pillar_workflow_qa  # noqa: E402
from pow_studio.deduplication import (  # noqa: E402
    audit_visual_repetition_and_progression,
    compute_dhash_64,
    compute_phash_64,
    hamming_distance_64,
    resolve_canonical_source_id,
)
from pow_studio.media_classifier import (  # noqa: E402
    SourceMediaClass,
    compute_visual_coverage_metrics,
    detect_presentation_graphic_metrics,
    inspect_media_authenticity,
)
from pow_studio.qc_suite import verify_protected_projects_intact  # noqa: E402
from pow_studio.reframing import crop_subpixel_full_canvas  # noqa: E402
from pow_studio.schema import AssetLicenseSpec, EpisodeManifest  # noqa: E402
from pow_studio.shot_planner import audit_shot_plan_and_alignment  # noqa: E402
from pow_studio.video_sourcing import audit_clip_real_motion  # noqa: E402


def _encode_frames_to_mp4(frames: list[Image.Image], out_path: Path, fps: int = 24, with_silent_aac: bool = False) -> Path:
    w, h = frames[0].size
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{w}x{h}",
        "-r",
        str(fps),
        "-i",
        "-",
    ]
    if with_silent_aac:
        dur = len(frames) / float(fps)
        cmd += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000"]
    cmd += [
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "16",
    ]
    if with_silent_aac:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(out_path))

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for im in frames:
        proc.stdin.write(np.asarray(im.convert("RGB"), dtype=np.uint8).tobytes())
    proc.stdin.close()
    rc = proc.wait()
    assert rc == 0, f"FFmpeg test encode failed ({rc})"
    return out_path


def test_distinguish_genuine_moving_clip_from_animated_photograph(tmp_path: Path):
    """
    Part 9 Section 17 Mandatory Proof #1:
    Demonstrate that the improved production system accurately distinguishes:
      (a) an animated photograph (Ken Burns zoom/pan baked into `.mp4`) -> `ANIMATED_STILL`, `is_real_moving_footage=False`
      (b) a genuine moving clip with localized independent activity -> `REAL_VIDEO_ACTION`, `is_real_moving_footage=True`
      (c) a JPEG converted to MP4 in `AssetLicenseSpec` -> preserves `photo` / `ANIMATED_STILL` lineage
      (d) a 3-panel `triptych_hook` (1 video + 2 JPEGs) -> exact 1/3 genuine moving ratio (not 100%!).
    """
    src_jpg = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "bf_2010_12_14.jpg"
    base_photo = Image.open(src_jpg).convert("RGB")

    # (a) Synthesize a smooth Ken Burns pan+zoom MP4 from the static photograph (48 frames @ 24fps = 2.0s)
    kb_frames: list[Image.Image] = []
    for i in range(48):
        u = i / 47.0
        cx = 0.43 + 0.12 * u
        cy = 0.52 - 0.08 * u
        zz = 1.02 + 0.10 * u
        kb_frames.append(crop_subpixel_full_canvas(base_photo, cx, cy, zz, 540, 960))
    kb_mp4 = _encode_frames_to_mp4(kb_frames, tmp_path / "ken_burns_from_jpeg.mp4", fps=24)

    kb_mot = audit_clip_real_motion(kb_mp4, start_s=0.0, duration_s=2.0)
    assert kb_mot["valid"] is True
    # Notice raw pixel diff IS high (> 0.6) because of camera zoom/pan — old v6 was fooled here!
    assert kb_mot["median_temporal_diff"] > 0.60
    # New v8 affine-compensated analyzer catches the static underlying photo!
    assert kb_mot["is_baked_animated_still"] is True
    assert kb_mot["is_real_moving_footage"] is False
    assert kb_mot["inferred_media_class"] == SourceMediaClass.ANIMATED_STILL.value

    # (b) Synthesize a clip with genuine localized non-rigid subject & rising plume motion over textured terrain
    rng = np.random.default_rng(42)
    bg_arr = np.asarray(crop_subpixel_full_canvas(base_photo, 0.5, 0.5, 1.04, 540, 960), dtype=np.float32)
    act_frames: list[Image.Image] = []
    for i in range(48):
        fr_arr = bg_arr.copy()
        # Independent moving field researcher + descending sampling cable + rising turbulent plume bubbles
        im = Image.fromarray(np.clip(fr_arr, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)
        sx = int(140 + 4.8 * i)
        sy = int(420 + 1.5 * np.sin(i * 0.4) * 10)
        d.rectangle((sx, sy, sx + 64, sy + 130), fill=(215, 68, 38), outline=(250, 240, 220), width=3)
        # Lowering probe cable moving vertically
        probe_y = int(220 + 7.5 * i)
        d.line((360, 120, 360, probe_y), fill=(230, 238, 245), width=5)
        d.ellipse((342, probe_y - 18, 378, probe_y + 22), fill=(60, 180, 220), outline=(255, 255, 255), width=2)
        # Turbulent bubbling vents moving upward in opposite direction
        for b_idx in range(10):
            bx = int(200 + b_idx * 26 + 9 * np.sin(0.5 * i + b_idx))
            by = int(820 - ((i * 11 + b_idx * 43) % 340))
            rad = 10 + (b_idx % 4) * 4
            d.ellipse((bx - rad, by - rad, bx + rad, by + rad), fill=(245, 210, 75))
        # Subtle real sensor grain
        noisy = np.clip(np.asarray(im, dtype=np.float32) + rng.normal(0.0, 1.8, (960, 540, 3)), 0, 255).astype(np.uint8)
        act_frames.append(Image.fromarray(noisy))
    act_mp4 = _encode_frames_to_mp4(act_frames, tmp_path / "genuine_sampling_action.mp4", fps=24)

    act_mot = audit_clip_real_motion(act_mp4, start_s=0.0, duration_s=2.0, metadata_hint="Scientists lowering probe sampling brine")
    assert act_mot["valid"] is True
    assert act_mot["is_baked_animated_still"] is False
    assert act_mot["is_real_moving_footage"] is True
    assert act_mot["has_localized_action_motion"] is True
    assert act_mot["inferred_media_class"] == SourceMediaClass.REAL_VIDEO_ACTION.value

    # (c) Verify manifest lineage rule: JPEG converted to MP4 stays a photo (`ANIMATED_STILL`)
    transcoded_spec = AssetLicenseSpec(
        local_file=str(kb_mp4.name),
        original_media_file="bf_2010_12_14.jpg",
        title="Blood Falls Photograph Converted to MP4",
        creator_agency="NSF",
        source_page_url="https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
        direct_media_url="https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
        license="Public Domain",
        license_url="https://creativecommons.org/publicdomain/mark/1.0/",
        required_attribution="NSF",
    )
    assert transcoded_spec.media_type == "photo"
    assert transcoded_spec.source_media_class == "ANIMATED_STILL"

    # (d) Verify 3-panel triptych_hook (1 video + 2 JPEGs) reports 33.33% genuine moving video, NOT 100%!
    other_jpg = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3" / "bf_aerial_2013.jpg"
    ep = EpisodeManifest.model_validate(
        {
            "slug": "test-triptych-honesty",
            "primary_title": "Test Coverage Metrics",
            "alternative_title": "Alt",
            "youtube_description": "Desc",
            "hashtags": ["#science"],
            "raw_assets_dir": str(tmp_path),
            "extra_assets_dirs": [str(src_jpg.parent)],
            "output_dir": str(tmp_path / "out_cov"),
            "editorial_formula": {
                "hook_max_start_s": 2.0,
                "layer2_pivot_seg_id": "N02",
                "scientific_caveat_seg_id": "N02",
                "min_real_evidence_ratio": 0.80,
            },
            "narration_segments": [
                {"seg_id": "N01", "text": "Three extreme zones on Earth."},
                {"seg_id": "N02", "text": "Caveat: researchers are still studying their limits."},
            ],
            "shots": [
                {
                    "sid": "S01",
                    "start_s": 0.0,
                    "end_s": 3.0,
                    "kind": "triptych_hook",
                    "src_file": act_mp4.name,
                    "secondary_src_file": src_jpg.name,
                    "tertiary_src_file": other_jpg.name,
                    "story_beat": "Opening 3-panel comparison",
                    "visual_desc": "Split comparison of 1 video and 2 photos",
                },
                {
                    "sid": "S02",
                    "start_s": 3.0,
                    "end_s": 6.0,
                    "kind": "video_full",
                    "src_file": kb_mp4.name,
                    "story_beat": "Animated photo disguised as video",
                    "visual_desc": "Panning across Blood Falls photo",
                },
            ],
            "assets_register": [
                {
                    "local_file": act_mp4.name,
                    "title": "Scientists sampling active vent",
                    "creator_agency": "USGS",
                    "source_page_url": "https://www.usgs.gov/video1",
                    "direct_media_url": "https://www.usgs.gov/video1.mp4",
                    "license": "Public Domain",
                    "license_url": "https://www.usgs.gov",
                    "required_attribution": "USGS",
                },
                {
                    "local_file": kb_mp4.name,
                    "title": "Ken Burns still clip",
                    "creator_agency": "NSF",
                    "source_page_url": "https://www.nsf.gov/kb1",
                    "direct_media_url": "https://www.nsf.gov/kb1.mp4",
                    "license": "Public Domain",
                    "license_url": "https://www.nsf.gov",
                    "required_attribution": "NSF",
                },
                {
                    "local_file": src_jpg.name,
                    "title": "Blood Falls Photo 1",
                    "creator_agency": "NSF",
                    "source_page_url": "https://www.nsf.gov/p1",
                    "direct_media_url": "https://www.nsf.gov/p1.jpg",
                    "license": "Public Domain",
                    "license_url": "https://www.nsf.gov",
                    "required_attribution": "NSF",
                },
                {
                    "local_file": other_jpg.name,
                    "title": "Blood Falls Photo 2",
                    "creator_agency": "NSF",
                    "source_page_url": "https://www.nsf.gov/p2",
                    "direct_media_url": "https://www.nsf.gov/p2.jpg",
                    "license": "Public Domain",
                    "license_url": "https://www.nsf.gov",
                    "required_attribution": "NSF",
                },
            ],
            "factual_references": [{"citation": "Ref", "url": "https://www.nsf.gov", "supported_claims": "Claim"}],
        }
    )
    cov = compute_visual_coverage_metrics(ep.shots, ep.assets_register, manifest=ep, probe_pixels=True)
    # Out of 6.0s total: S01 contributes only 1.0s genuine video + 2.0s static photo; S02 (baked Ken Burns) contributes 0.0s video + 3.0s ANIMATED_STILL!
    assert abs(cov["genuine_moving_footage_s"] - 1.0) < 0.05
    assert abs(cov["genuine_moving_footage_pct"] - 16.67) < 0.5
    assert abs(cov["static_image_s"] - 5.0) < 0.05


def test_detect_irrelevant_keyword_trap_and_proxy_location_clips():
    """
    Part 9 Section 17 Mandatory Proof #2:
    Demonstrate that the system detects and rejects irrelevant clips EVEN WHEN their
    titles contain matching keywords (lectures, talking heads, lab portraits, paper
    screenshots, generic scenic filler, and undisclosed proxy locations).
    """
    beats = extract_narration_visual_beats(
        [
            {
                "seg_id": "N01",
                "text": "Scientists lowered instruments into the acidic ponds at Dallol in Ethiopia to collect brine samples.",
            },
            {
                "seg_id": "N02",
                "text": "In 1960, Bathyscaphe Trieste descended into the Mariana Trench.",
            },
        ],
        topic="Dallol Ethiopia extreme brine sampling",
    )
    sampling_beat = beats[0]
    historical_beat = beats[1]
    assert sampling_beat.genuine_footage_essential is True
    assert historical_beat.is_historical_event is True

    # 1. Title has ALL keywords ("Scientists", "Sampling", "Dallol", "Brine", "Ethiopia") -> Keynote Lecture trap!
    trap_lecture = {
        "local_file": "dallol_keynote_lecture.mp4",
        "title": "Scientists Sampling Dallol Brine in Ethiopia — University Keynote Lecture",
        "description": "Conference symposium talk about Dallol acidic ponds",
        "license": "CC BY 4.0",
        "source_media_class": "REAL_VIDEO_ACTION",
    }
    ev_lec = evaluate_action_visual_match(sampling_beat, trap_lecture)
    assert ev_lec["eligible"] is False
    assert "Keyword-trap rejected" in ev_lec["rejection_reason"]

    # 2. Idle lab portrait with matching keywords
    trap_lab = {
        "local_file": "dallol_lab_portrait.mp4",
        "title": "Dallol Ethiopia Brine Study — Random Scientist Standing in Laboratory Portrait",
        "description": "Indoor portrait of researcher in office",
        "license": "CC BY 4.0",
    }
    ev_lab = evaluate_action_visual_match(sampling_beat, trap_lab)
    assert ev_lab["eligible"] is False

    # 3. Undisclosed proxy location (Hawaii Mauna Loa lava cave substituted for Dallol Ethiopia!)
    trap_proxy = {
        "local_file": "nasa_mauna_loa_sampling.mp4",
        "title": "Scientists Collecting Samples in Mauna Loa Lava Tube, Hawaii",
        "description": "Fieldwork swabbing dry volcanic cave rock in Hawaii",
        "license": "Public Domain",
        "source_media_class": "REAL_VIDEO_ACTION",
    }
    ev_proxy = evaluate_action_visual_match(sampling_beat, trap_proxy)
    assert ev_proxy["eligible"] is False
    assert "proxy-location mismatch" in ev_proxy["rejection_reason"]

    # 4. Modern clip pretending to depict the 1960 Trieste historical descent
    trap_modern_for_1960 = {
        "local_file": "modern_rov_2024.mp4",
        "title": "Mariana Trench Submersible Descent",
        "description": "Contemporary ROV dive",
        "historical_era": "modern",
        "license": "Public Domain",
    }
    ev_hist_bad = evaluate_action_visual_match(historical_beat, trap_modern_for_1960)
    assert ev_hist_bad["eligible"] is False
    assert "Modern footage cannot pretend" in ev_hist_bad["rejection_reason"]

    # 5. Authentic field action footage at Dallol -> APPROVED with high relevance!
    good_fieldwork = {
        "local_file": "dallol_expedition_sampling_ccby.mp4",
        "title": "Expedition Scientists Lowering Sampling Probe into Dallol Acidic Brine Ponds, Ethiopia",
        "description": "Field researchers collecting hydrothermal brine water samples at Dallol crater",
        "license": "CC BY 4.0",
        "source_media_class": "REAL_VIDEO_ACTION",
    }
    ev_good = evaluate_action_visual_match(sampling_beat, good_fieldwork)
    assert ev_good["eligible"] is True
    assert ev_good["overall_relevance"] >= 0.80


def test_reject_visual_repetition_multi_crop_and_near_duplicates(tmp_path: Path):
    """
    Part 9 Section 17 Mandatory Proof #3:
    Demonstrate that the system detects & rejects:
      - Splitting one photograph into multiple scenes via different `crop_box` / `still_parallax_25d`
      - Counting multiple crops of one photograph as distinct source assets
      - Perceptually identical photos saved under different filenames (`dHash`/`pHash`)
      - Multiple local sub-clips cut from the same archive URL (`same_source_shoot_overuse`)
      - While permitting explicit `intentional_callback=True` payoffs.
    """
    raw_dir = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3"
    orig_photo = Image.open(raw_dir / "bf_2010_12_14.jpg").convert("RGB")
    dup_photo_path = tmp_path / "renamed_duplicate_photo.jpg"
    orig_photo.save(dup_photo_path, quality=92)

    # Confirm perceptual hash closeness
    assert hamming_distance_64(compute_dhash_64(orig_photo), compute_dhash_64(Image.open(dup_photo_path))) <= 2
    assert hamming_distance_64(compute_phash_64(orig_photo), compute_phash_64(Image.open(dup_photo_path))) <= 2

    # Build manifest with S02 + S03 splitting 1 photo via `still_parallax_25d` + `crop_box` (the exact old loophole!)
    ep = EpisodeManifest.model_validate(
        {
            "slug": "test-dedup-v8",
            "style_profile": "mysterious_earth_exploration",
            "style_overrides": {"asset_selection": {"location_authentic_mode": True}},
            "enable_intelligent_scene_editing": False,
            "primary_title": "Test Repetition Detection",
            "alternative_title": "Alt",
            "youtube_description": "Desc",
            "hashtags": ["#science"],
            "raw_assets_dir": str(raw_dir),
            "extra_assets_dirs": [str(tmp_path)],
            "output_dir": str(tmp_path / "out_dedup"),
            "editorial_formula": {
                "hook_max_start_s": 2.0,
                "layer2_pivot_seg_id": "N02",
                "scientific_caveat_seg_id": "N03",
                "min_real_evidence_ratio": 0.80,
            },
            "narration_segments": [
                {"seg_id": "N01", "text": "Scientists cross the Antarctic glacier."},
                {"seg_id": "N02", "text": "Iron brine pours across the ice face."},
                {"seg_id": "N03", "text": "Caveat: researchers are still studying subglacial conduits."},
            ],
            "shots": [
                {
                    "sid": "S01",
                    "start_s": 0.0,
                    "end_s": 3.5,
                    "kind": "video_full",
                    "src_file": "nasa_m12666_nansen_scientists_ice.mp4",
                    "story_beat": "Scientists traversing glacier",
                    "visual_desc": "Field team walking on glacier ice",
                    "associated_seg_id": "N01",
                    "has_human_interaction": True,
                },
                {
                    "sid": "S02",
                    "start_s": 3.5,
                    "end_s": 7.0,
                    "kind": "still_parallax_25d",
                    "parallax_px": 14.0,
                    "src_file": "bf_2010_12_14.jpg",
                    "crop_box": [0, 0, 800, 900],
                    "story_beat": "Wide view of Blood Falls",
                    "visual_desc": "Crimson outflow on Taylor Glacier",
                    "associated_seg_id": "N02",
                },
                {
                    "sid": "S03",
                    "start_s": 7.0,
                    "end_s": 10.5,
                    "kind": "still_parallax_25d",
                    "parallax_px": 16.0,
                    "src_file": "bf_2010_12_14.jpg",
                    "crop_box": [120, 80, 760, 880],
                    "story_beat": "Tighter fake scene crop of exact same photo",
                    "visual_desc": "Cropped crimson outflow on Taylor Glacier",
                    "associated_seg_id": "N02",
                },
                {
                    "sid": "S04",
                    "start_s": 10.5,
                    "end_s": 14.0,
                    "kind": "still_full",
                    "src_file": "renamed_duplicate_photo.jpg",
                    "story_beat": "Perceptual duplicate saved under another filename",
                    "visual_desc": "Duplicate photo of Blood Falls",
                    "associated_seg_id": "N03",
                },
            ],
            "assets_register": [
                {
                    "local_file": "nasa_m12666_nansen_scientists_ice.mp4",
                    "title": "NASA Scientists on Nansen Ice Sheet",
                    "creator_agency": "NASA",
                    "source_page_url": "https://svs.gsfc.nasa.gov/12666",
                    "direct_media_url": "https://svs.gsfc.nasa.gov/12666.mp4",
                    "license": "Public Domain",
                    "license_url": "https://www.nasa.gov",
                    "required_attribution": "NASA",
                },
                {
                    "local_file": "bf_2010_12_14.jpg",
                    "title": "Blood Falls Taylor Glacier",
                    "creator_agency": "NSF",
                    "source_page_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
                    "direct_media_url": "https://commons.wikimedia.org/wiki/File:Blood_Falls.jpg",
                    "license": "Public Domain",
                    "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
                    "required_attribution": "NSF",
                },
                {
                    "local_file": "renamed_duplicate_photo.jpg",
                    "title": "Re-uploaded copy",
                    "creator_agency": "NSF",
                    "source_page_url": "https://commons.wikimedia.org/wiki/File:Another_Name.jpg",
                    "direct_media_url": "https://commons.wikimedia.org/wiki/File:Another_Name.jpg",
                    "license": "Public Domain",
                    "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
                    "required_attribution": "NSF",
                },
            ],
            "factual_references": [{"citation": "Ref", "url": "https://www.nsf.gov", "supported_claims": "Claim"}],
        }
    )

    rep = audit_visual_repetition_and_progression(ep, ep.shots, probe_pixels=True)
    issue_kinds = {x["kind"] for x in rep["issues"]}
    assert "multi_crop_single_photo" in issue_kinds
    assert "duplicate_photo_different_filename" in issue_kinds
    assert rep["repetition_and_progression_pass"] is False

    # Also verify `audit_shot_plan_and_alignment` now blocks consecutive `still_parallax_25d` AND multi-crop reuse!
    wt = {
        "total_duration_s": 14.0,
        "total_frames_30fps": 420,
        "segments": [
            {"seg_id": "N01", "text": "Scientists cross the Antarctic glacier.", "start": 0.0, "end": 3.3},
            {"seg_id": "N02", "text": "Iron brine pours across the ice face.", "start": 3.5, "end": 10.2},
            {"seg_id": "N03", "text": "Caveat: researchers are still studying subglacial conduits.", "start": 10.5, "end": 13.8},
        ],
        "words": [
            {"seg_id": "N01", "word": "Scientists", "start": 0.1, "end": 0.6},
            {"seg_id": "N02", "word": "Iron", "start": 3.6, "end": 4.0},
            {"seg_id": "N03", "word": "Caveat:", "start": 10.6, "end": 11.1},
        ],
    }
    Path(ep.output_dir).mkdir(parents=True, exist_ok=True)
    plan_audit = audit_shot_plan_and_alignment(ep, wt, ep.resolve_style_profile())
    assert any("reused multiple times" in e for e in plan_audit["errors"])
    assert any("Consecutive static photo shots" in e for e in plan_audit["errors"])

    # Verify canonical source ID groups 2 local sub-clips from the same NASA page URL as 1 source!
    c1 = resolve_canonical_source_id(
        AssetLicenseSpec(
            local_file="mauna_loa_clip_a.mp4",
            title="Clip A",
            creator_agency="NASA",
            source_page_url="https://plus.nasa.gov/video/astrobiology-mauna-loa/",
            direct_media_url="https://plus.nasa.gov/a.mp4",
            license="Public Domain",
            license_url="https://www.nasa.gov",
            required_attribution="NASA",
        )
    )
    c2 = resolve_canonical_source_id(
        AssetLicenseSpec(
            local_file="mauna_loa_clip_b.mp4",
            title="Clip B",
            creator_agency="NASA",
            source_page_url="https://plus.nasa.gov/video/astrobiology-mauna-loa",
            direct_media_url="https://plus.nasa.gov/b.mp4",
            license="Public Domain",
            license_url="https://www.nasa.gov",
            required_attribution="NASA",
        )
    )
    assert c1 == c2


def test_preproduction_visual_feasibility_and_six_pillar_creative_qa_blocking(tmp_path: Path):
    """
    Validate:
      1. Pre-Production Feasibility Gate blocks a 5-event story when the asset library
         can only illustrate 1 event (unless `user_accepted_limited_visuals=True`).
      2. 6-Pillar QA separates `technical_approval` from `creative_approval`: a technically
         valid `1080x1920` `30fps` `H.264/AAC` render with animated stills + a dense
         PowerPoint-style dashboard slide passes `technical_qa` (`True`) yet FAILS
         `creative_approval` (`False`)!
    """
    five_event_segments = [
        {"seg_id": "N01", "text": "Explorers climb down the flooded sinkhole shaft in Mexico."},
        {"seg_id": "N02", "text": "Divers swim past submerged stalactites in pitch darkness."},
        {"seg_id": "N03", "text": "Scientists lower sterile sensors into the halocline layer."},
        {"seg_id": "N04", "text": "Microbiologists collect live extremophile samples from the cave wall."},
        {"seg_id": "N05", "text": "Engineers operate portable spectrometers inside the chamber."},
    ]
    sparse_library = [
        {
            "local_file": "mexico_cenote_divers.mp4",
            "title": "Divers swimming past submerged stalactites in Mexico cenote cave",
            "description": "Underwater cave diving exploration in Mexico",
            "license": "CC BY 4.0",
            "source_media_class": "REAL_VIDEO_ACTION",
        }
    ]
    feas_blocked = analyze_visual_feasibility(
        topic="Mexico submerged cave sampling expedition",
        narration_segments=five_event_segments,
        available_assets=sparse_library,
        user_accepted_limited_visuals=False,
        out_dir=tmp_path / "feas_out",
    )
    assert feas_blocked["essential_action_beats"] == 5
    assert feas_blocked["can_proceed_to_production"] is False
    assert feas_blocked["feasibility_status"] == "INSUFFICIENT_FOOTAGE_RESTRUCTURE_REQUIRED"
    assert (tmp_path / "feas_out" / "visual_feasibility_report.md").exists()

    feas_accepted = analyze_visual_feasibility(
        topic="Mexico submerged cave sampling expedition",
        narration_segments=five_event_segments,
        available_assets=sparse_library,
        user_accepted_limited_visuals=True,
    )
    assert feas_accepted["can_proceed_to_production"] is True

    # Synthesize a dense PowerPoint-style dashboard graphic (`1080x1920`) and verify detection
    slide = Image.new("RGB", (1080, 1920), (14, 18, 28))
    d = ImageDraw.Draw(slide)
    for row in range(4):
        top = 180 + row * 380
        d.rectangle((60, top, 1020, top + 320), fill=(22, 30, 46), outline=(90, 160, 230), width=4)
        for bar in range(5):
            bx = 100 + bar * 170
            d.rectangle((bx, top + 80, bx + 110, top + 280), fill=(235, 95, 65))
            d.line((bx, top + 45, bx + 130, top + 45), fill=(255, 255, 255), width=3)
    flat_r, grid_s, is_slide = detect_presentation_graphic_metrics(slide)
    assert is_slide is True

    slide_mp4 = _encode_frames_to_mp4([slide] * 30, tmp_path / "powerpoint_dashboard.mp4", fps=30)
    master_mp4 = _encode_frames_to_mp4([slide] * 180, tmp_path / "slideshow-ep.mp4", fps=30, with_silent_aac=True)

    raw_dir = CHANNEL_ROOT / "assets" / "raw_footage" / "hidden_earth_blood_falls_v3"
    ep_bad = EpisodeManifest.model_validate(
        {
            "slug": "slideshow-ep",
            "enable_intelligent_scene_editing": False,
            "primary_title": "Slideshow Test",
            "alternative_title": "Alt",
            "youtube_description": "Desc",
            "hashtags": ["#science"],
            "raw_assets_dir": str(raw_dir),
            "extra_assets_dirs": [str(tmp_path)],
            "output_dir": str(tmp_path),
            "editorial_formula": {
                "hook_max_start_s": 2.0,
                "layer2_pivot_seg_id": "N02",
                "scientific_caveat_seg_id": "N02",
                "min_real_evidence_ratio": 0.80,
            },
            "narration_segments": [
                {"seg_id": "N01", "text": "Scientists drill deep into the glacier and lower sampling probes."},
                {"seg_id": "N02", "text": "Caveat: researchers are still studying how microbes survive."},
            ],
            "shots": [
                {
                    "sid": "S01",
                    "start_s": 0.0,
                    "end_s": 2.5,
                    "kind": "still_full",
                    "src_file": "bf_2010_12_14.jpg",
                    "story_beat": "Static photo 1",
                    "visual_desc": "Glacier photo",
                    "associated_seg_id": "N01",
                },
                {
                    "sid": "S02",
                    "start_s": 2.5,
                    "end_s": 5.0,
                    "kind": "still_full",
                    "src_file": "bf_aerial_2013.jpg",
                    "story_beat": "Static photo 2 right after photo 1",
                    "visual_desc": "Second glacier photo",
                    "associated_seg_id": "N01",
                },
                {
                    "sid": "S03",
                    "start_s": 5.0,
                    "end_s": 6.0,
                    "kind": "diagram",
                    "is_real_evidence": False,
                    "src_file": slide_mp4.name,
                    "story_beat": "Dense chart",
                    "visual_desc": "Multi-box chart",
                    "associated_seg_id": "N02",
                },
            ],
            "assets_register": [
                {
                    "local_file": "bf_2010_12_14.jpg",
                    "title": "Photo 1",
                    "creator_agency": "NSF",
                    "source_page_url": "https://www.nsf.gov/1",
                    "direct_media_url": "https://www.nsf.gov/1.jpg",
                    "license": "Public Domain",
                    "license_url": "https://www.nsf.gov",
                    "required_attribution": "NSF",
                },
                {
                    "local_file": "bf_aerial_2013.jpg",
                    "title": "Photo 2",
                    "creator_agency": "NSF",
                    "source_page_url": "https://www.nsf.gov/2",
                    "direct_media_url": "https://www.nsf.gov/2.jpg",
                    "license": "Public Domain",
                    "license_url": "https://www.nsf.gov",
                    "required_attribution": "NSF",
                },
                {
                    "local_file": slide_mp4.name,
                    "title": "Dashboard Slide",
                    "creator_agency": "POW",
                    "source_page_url": "local://slide",
                    "direct_media_url": "local://slide.mp4",
                    "license": "100% Original First-Party Graphic",
                    "license_url": "N/A",
                    "required_attribution": "Original",
                    "is_first_party_original": True,
                },
            ],
            "factual_references": [{"citation": "Ref", "url": "https://www.nsf.gov", "supported_claims": "Claim"}],
        }
    )

    qa6 = run_six_pillar_workflow_qa(ep_bad, rendered_mp4=master_mp4, probe_pixels=True, out_dir=tmp_path / "qa6_out")
    assert qa6["technical_approval"] is True
    assert qa6["creative_approval"] is False
    assert qa6["overall_release_approval"] is False
    codes = {x["code"] for x in qa6["issues"]}
    assert "slideshow_section_detected" in codes


def test_multi_topic_dry_run_storyboards_and_reference_video_untouched(tmp_path: Path):
    """
    Part 9 Section 16 & 17 + Part 10 Deliverable #12:
    Validate reusable multi-topic dry-run plans across Snake Island, Mariana Trench,
    and Dallol Brine Pools, and assert zero modifications to the reference video
    and all protected completed episodes.
    """
    # Topic 1: Snake Island (Ilha da Queimada Grande)
    snake_segs = [
        {"seg_id": "N01", "text": "Forty miles off Brazil's coast, waves crash against Ilha da Queimada Grande."},
        {"seg_id": "N02", "text": "Golden lancehead vipers slither through canopy branches and strike migratory birds mid-perch."},
        {"seg_id": "N03", "text": "Navy-escorted herpetologists climb the forested ridge and collect venom samples for medical research."},
    ]
    snake_assets = [
        {
            "local_file": "queimada_grande_coast_aerial.mp4",
            "title": "Ilha da Queimada Grande rocky Atlantic island coastline aerial footage, Brazil",
            "creator_agency": "Instituto Butantan / Wikimedia CC BY",
            "source_page_url": "https://commons.wikimedia.org/wiki/File:Queimada_Grande_Aerial.webm",
            "license": "CC BY 4.0",
            "source_media_class": "REAL_VIDEO_ESTABLISHING",
            "depicted_action": "Ocean swells striking steep forested island cliffs off Sao Paulo coast",
        },
        {
            "local_file": "bothrops_insularis_arboreal_motion.mp4",
            "title": "Bothrops insularis golden lancehead viper slithering and striking in Atlantic forest canopy, Snake Island Brazil",
            "creator_agency": "Peer-Reviewed Herpetology Archive (CC BY 4.0)",
            "source_page_url": "https://commons.wikimedia.org/wiki/File:Bothrops_insularis_canopy.webm",
            "license": "CC BY 4.0",
            "source_media_class": "REAL_VIDEO_ACTION",
            "depicted_action": "Golden lancehead viper moving across tree branch hunting prey",
        },
        {
            "local_file": "butantan_field_herpetologists_sampling.mp4",
            "title": "Scientists collecting venom samples from golden lancehead viper during Snake Island Brazil expedition",
            "creator_agency": "Instituto Butantan Open Science (CC BY 4.0)",
            "source_page_url": "https://commons.wikimedia.org/wiki/File:Butantan_expedition_sampling.webm",
            "license": "CC BY 4.0",
            "source_media_class": "REAL_VIDEO_ACTION",
            "depicted_action": "Field researchers safely handling viper with snake hook and collecting venom sample",
        },
    ]
    snake_queries = generate_footage_search_queries("Snake Island Brazil golden lancehead vipers", extract_narration_visual_beats(snake_segs, "Snake Island Brazil"))
    assert len(snake_queries) >= 5
    snake_plan = build_action_storyboard_plan(
        slug="dryrun-snake-island",
        topic="Snake Island Brazil (Ilha da Queimada Grande)",
        narration_segments=snake_segs,
        available_assets=snake_assets,
        total_duration_s=36.0,
        out_dir=tmp_path / "dryrun_snake_island",
    )
    assert snake_plan["coverage_metrics"]["genuine_moving_footage_pct"] >= 95.0
    assert snake_plan["coverage_metrics"]["meaningful_action_footage_pct"] >= 60.0
    for req_field in (
        "scene_id", "narration_segment", "visual_objective", "visible_action",
        "asset", "source", "media_type", "shot_perspective", "relevance", "duration", "continuity",
    ):
        assert req_field in snake_plan["scenes"][0]

    # Topic 2: Mariana Trench Deep-Ocean Exploration
    trench_segs = [
        {"seg_id": "N01", "text": "Nearly eleven kilometers beneath the Pacific, NOAA's ROV descends along the Mariana Trench wall."},
        {"seg_id": "N02", "text": "Translucent snailfish swim across the abyssal sediment while robotic manipulators collect core samples."},
    ]
    trench_assets = [
        {
            "local_file": "noaa_okeanos_mariana_rov_descent.mp4",
            "title": "NOAA Okeanos Explorer Deep Discoverer ROV descending Mariana Trench wall",
            "creator_agency": "NOAA Office of Ocean Exploration and Research",
            "source_page_url": "https://oceanexplorer.noaa.gov/okeanos/explorations/ex1605/",
            "license": "Public Domain",
            "source_media_class": "REAL_VIDEO_ACTION",
            "depicted_action": "ROV descending steep basaltic wall under LED floodlights",
        },
        {
            "local_file": "noaa_mariana_snailfish_and_coring.mp4",
            "title": "Mariana Trench hadal snailfish swimming and ROV manipulator collecting sediment core sample",
            "creator_agency": "NOAA OER",
            "source_page_url": "https://oceanexplorer.noaa.gov/okeanos/explorations/ex1605/logs/",
            "license": "Public Domain",
            "source_media_class": "REAL_VIDEO_ACTION",
            "depicted_action": "Hadal fauna swimming and robotic arm pushing push-core tube into seafloor",
        },
    ]
    trench_plan = build_action_storyboard_plan(
        slug="dryrun-mariana-trench",
        topic="Mariana Trench Deep Ocean ROV Exploration",
        narration_segments=trench_segs,
        available_assets=trench_assets,
        total_duration_s=28.0,
        out_dir=tmp_path / "dryrun_mariana_trench",
    )
    assert trench_plan["coverage_metrics"]["genuine_moving_footage_pct"] == 100.0
    assert trench_plan["coverage_metrics"]["meaningful_action_footage_pct"] == 100.0

    # Assert Protected Projects & Diagnostic Reference Video are 100% Untouched!
    prot = verify_protected_projects_intact()
    assert prot["all_intact"] is True

    ref_candidates = list(Path(r"C:\Users\Admin\Downloads").glob("*Deadliest Zones.mp4"))
    if ref_candidates:
        assert ref_candidates[0].stat().st_size == 15_446_802
