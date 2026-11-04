#!/usr/bin/env python3
"""
Stage 4 & Stage 5: Adaptive Narration-Aware Shot Planner, Cinematic Perspective
Variety Auditor & Semantic Visual Synchronization Engine (`pow_studio.shot_planner` v6.0).

Implements Part 3 (Section 4.3) and Part 6 (Sections 7.1-7.3) of the Proof of Wonder
Next-Generation Documentary Studio:
1. Extracts exact sentence/clause boundaries and natural speech pauses from rendered narration
   (`word_timings.json`) so narration meaning—not a fixed timer—drives the edit.
2. `calculate_adaptive_shot_duration()` — Computes ideal scene duration ranges from:
   - Visual complexity (`low` / `medium` / `high`)
   - Importance of spoken information (`context` / `key_fact` / `central_reveal`)
   - Viewer recognition time (wide/aerial/diagram vs. close-up detail)
   - Amount of new information (words & quantitative entities)
   - Camera movement (`static` / `gentle_drift` / `tracking` / `aerial_sweep` / `handheld_field`)
   - Static archival photo vs. live moving footage
   - Natural speech rhythm (snapping to nearest natural pause)
3. Audits cinematic visual variety across 10 shot perspectives (`extreme_wide`, `wide`, `medium`,
   `close_up`, `macro`, `aerial`, `first_person_pov`, `scientific_fieldwork`,
   `satellite_or_telescope`, `labeled_visualization`) and prevents artificial repeated zoom-ins
   on the same image.
4. `build_semantic_timeline_manifest()` — Maintains the complete semantic synchronization record
   for every scene (`scene_id`, `associated_seg_id`, `narration_start/end`, `asset`, `license`,
   `visual_purpose`, `perspective`, `crop_and_framing`, `transition`, `audio_design`, `rationale`).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from .deduplication import audit_visual_repetition_and_progression, resolve_canonical_source_id
from .media_classifier import compute_visual_coverage_metrics
from .reframing import evaluate_crop_feasibility
from .schema import EpisodeManifest, ShotSpecModel, resolve_timed_shots
from .script_linter import audit_viral_shorts_script
from .style_profile import DocumentaryStyleProfile
from .video_sourcing import audit_clip_real_motion


def extract_speech_boundaries(wt: dict, min_pause_s: float = 0.16) -> list[dict[str, Any]]:
    """
    Identify natural semantic cut opportunities from `word_timings.json`:
    - Segment endings (completed narration paragraphs/ideas)
    - Sentence endings (`.`, `?`, `!`)
    - Clause pauses (`—`, `,`, `:`, `;` or inter-word acoustic silence >= `min_pause_s`).
    """
    words = wt.get("words", [])
    seg_ends = {round(float(s["end"]), 3) for s in wt.get("segments", [])}
    boundaries: list[dict[str, Any]] = [{"time_s": 0.0, "kind": "start", "pause_s": 0.0}]

    for idx, w in enumerate(words):
        t_end = float(w["end"])
        nxt_start = float(words[idx + 1]["start"]) if idx + 1 < len(words) else float(wt.get("total_duration_s", t_end))
        gap = max(0.0, nxt_start - t_end)
        txt = str(w.get("word", "")).strip()

        is_seg_end = any(abs(t_end - se) < 0.05 for se in seg_ends) or (idx == len(words) - 1)
        is_sent_end = txt.endswith((".", "?", "!"))
        is_clause_end = txt.endswith((",", ";", ":", "—")) or ("—" in txt)

        if is_seg_end or is_sent_end or is_clause_end or gap >= min_pause_s:
            b_kind = (
                "segment_end"
                if is_seg_end
                else ("sentence_end" if is_sent_end else ("clause_end" if is_clause_end else "breath_pause"))
            )
            mid_pause = round(t_end + 0.5 * min(gap, 0.45), 3) if idx + 1 < len(words) else round(float(wt["total_duration_s"]), 3)
            boundaries.append(
                {
                    "time_s": mid_pause,
                    "word_end_s": round(t_end, 3),
                    "next_word_start_s": round(nxt_start, 3),
                    "pause_s": round(gap, 3),
                    "kind": b_kind,
                    "after_word": txt,
                }
            )
    return boundaries


def calculate_adaptive_shot_duration(
    visual_complexity: str = "medium",
    spoken_importance: str = "key_fact",
    camera_perspective: str = "wide",
    camera_movement: str = "gentle_drift",
    is_moving_footage: bool = True,
    spoken_word_count: int = 10,
    quantitative_fact_count: int = 0,
    style: Optional[DocumentaryStyleProfile] = None,
) -> dict[str, Any]:
    """
    Calculate adaptive scene duration bounds `(min_rec_s, ideal_s, max_rec_s)` based on
    the 7 documentary editorial factors in Part 6, Section 7.1.
    """
    ref_lo, ref_hi = style.pacing.reference_shot_duration_range_s if style else (3.6, 7.2)
    base_s = 0.5 * (ref_lo + ref_hi)

    # 1. Viewer recognition time by camera perspective
    recognition_adj = {
        "extreme_wide": 0.85,
        "aerial": 0.70,
        "satellite_or_telescope": 0.75,
        "labeled_visualization": 0.80,
        "wide": 0.35,
        "scientific_fieldwork": 0.30,
        "first_person_pov": 0.20,
        "medium": 0.0,
        "close_up": -0.45,
        "macro": -0.35,
    }.get(camera_perspective, 0.0)

    # 2. Visual complexity
    comp_adj = {"low": -0.45, "medium": 0.0, "high": 0.80}.get(visual_complexity, 0.0)

    # 3. Importance of spoken information
    imp_adj = {"context": -0.30, "key_fact": 0.15, "central_reveal": 0.85}.get(spoken_importance, 0.0)

    # 4. Amount of new information (spoken density & numbers)
    speech_need_s = max(2.0, spoken_word_count / 2.65) + 0.22 * min(3, quantitative_fact_count)

    # 5 & 6. Camera movement & moving-vs-static nature
    motion_adj = {
        "aerial_sweep": 0.45,
        "tracking": 0.35,
        "handheld_field": 0.20,
        "gentle_drift": 0.0,
        "static": -0.40,
    }.get(camera_movement, 0.0)

    raw_ideal = 0.52 * (base_s + recognition_adj + comp_adj + imp_adj + motion_adj) + 0.48 * speech_need_s

    if not is_moving_footage:
        still_cap = style.asset_selection.max_single_still_duration_s if style else 5.5
        raw_ideal = min(raw_ideal, still_cap - 0.5)
        max_rec = still_cap
    else:
        max_rec = min(
            style.pacing.max_shot_duration_s if style else 14.0,
            max(raw_ideal + 2.4, ref_hi + 1.5),
        )

    min_floor = style.pacing.min_shot_duration_s if style else 2.2
    min_rec = max(min_floor, min(raw_ideal - 1.5, ref_lo))
    ideal_s = max(min_rec, min(max_rec, raw_ideal))

    return {
        "min_recommended_s": round(min_rec, 2),
        "ideal_duration_s": round(ideal_s, 2),
        "max_recommended_s": round(max_rec, 2),
        "factors": {
            "visual_complexity": visual_complexity,
            "spoken_importance": spoken_importance,
            "camera_perspective": camera_perspective,
            "camera_movement": camera_movement,
            "is_moving_footage": is_moving_footage,
            "spoken_word_count": spoken_word_count,
        },
    }


def _infer_shot_perspective(s: ShotSpecModel, mtype: str) -> str:
    """Infer cinematic perspective when legacy manifests omit explicit `camera_perspective`."""
    if s.camera_perspective != "wide":
        return s.camera_perspective
    blob = f"{s.story_beat} {s.visual_desc} {s.src_file}".lower()
    if s.kind == "diagram" or not s.is_real_evidence:
        return "labeled_visualization"
    if any(k in blob for k in ("microscop", "diatom", "flagellate", "tweezers", "macro")):
        return "macro"
    if any(k in blob for k in ("landsat", "satellite", "telescope", "jwst", "hubble", "lima 3d")):
        return "satellite_or_telescope"
    if any(k in blob for k in ("helicopter sweep", "aerial", "sweeping aerial", "mountain peaks", "flyover")):
        return "aerial"
    if s.has_human_interaction or any(k in blob for k in ("scientist", "researcher", "glaciologist", "parka", "radar")):
        return "scientific_fieldwork"
    if any(k in blob for k in ("close-up", "closeup", "detail")):
        return "close_up"
    if any(k in blob for k in ("vast", "panoram", "valley", "horizon")):
        return "extreme_wide"
    return "wide" if mtype == "photo" else "medium"


def _probe_media_dimensions_and_type(path: Path) -> tuple[int, int, str, float]:
    """Return `(width, height, detected_media_type, duration_s)` via ffprobe/Pillow."""
    suf = path.suffix.lower()
    if suf in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"):
        from PIL import Image, ImageOps

        im = ImageOps.exif_transpose(Image.open(path))
        return (im.width, im.height, "photo", 0.0)

    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return (0, 0, "unknown", 0.0)
    info = json.loads(proc.stdout)
    v = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), {})
    dur = float(info.get("format", {}).get("duration", v.get("duration", 0.0)) or 0.0)
    return (int(v.get("width", 0)), int(v.get("height", 0)), "video", dur)


def build_semantic_timeline_manifest(
    manifest: EpisodeManifest,
    wt: dict,
    style: Optional[DocumentaryStyleProfile] = None,
) -> dict[str, Any]:
    """
    Build the authoritative Semantic Visual Synchronization Manifest (Part 6, Section 7.2)
    recording for every scene:
    - Scene ID (`sid`), associated script segment (`associated_seg_id`), narration start & end,
      selected asset, verified source & license, visual purpose, camera perspective,
      crop & framing, transition type, 5-layer audio design, adaptive duration score,
      and why the shot belongs at that exact point.
    """
    style = style or manifest.resolve_style_profile()
    fps = style.output.fps
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)
    assets_by_name = {a.local_file: a for a in manifest.assets_register}
    segs = wt.get("segments", [])
    words = wt.get("words", [])

    scenes: list[dict[str, Any]] = []
    for idx, s in enumerate(timed_shots):
        dur = round(s.end_s - s.start_s, 3)
        asset = assets_by_name.get(s.src_file)
        mtype = (
            "diagram"
            if (not s.is_real_evidence or s.kind == "diagram" or (asset and asset.media_type == "diagram"))
            else ("video" if (s.kind in ("video_full", "triptych_hook") or (asset and asset.media_type == "video")) else "photo")
        )
        persp = _infer_shot_perspective(s, mtype)

        # Match primary narration segment overlapping shot midpoint
        t_mid = 0.5 * (s.start_s + s.end_s)
        assoc_seg_id = s.associated_seg_id
        if not assoc_seg_id and segs:
            best_seg = min(
                segs,
                key=lambda sg: 0.0
                if float(sg["start"]) <= t_mid <= float(sg["end"])
                else min(abs(t_mid - float(sg["start"])), abs(t_mid - float(sg["end"]))),
            )
            assoc_seg_id = str(best_seg["seg_id"])

        shot_words = [
            w for w in words if s.start_s - 0.04 <= 0.5 * (float(w["start"]) + float(w["end"])) < s.end_s
        ]
        spoken_txt = " ".join(w["word"] for w in shot_words).strip()
        narr_start = round(float(shot_words[0]["start"]), 3) if shot_words else s.start_s
        narr_end = round(float(shot_words[-1]["end"]), 3) if shot_words else s.end_s
        num_facts = len(re.findall(r"\d+", spoken_txt))

        adap = calculate_adaptive_shot_duration(
            visual_complexity=s.visual_complexity,
            spoken_importance=s.spoken_importance,
            camera_perspective=persp,
            camera_movement=s.camera_movement,
            is_moving_footage=(mtype == "video"),
            spoken_word_count=len(shot_words),
            quantitative_fact_count=num_facts,
            style=style,
        )

        scenes.append(
            {
                "scene_id": s.sid,
                "associated_seg_id": assoc_seg_id or "",
                "timeline_start_s": s.start_s,
                "timeline_end_s": s.end_s,
                "duration_s": dur,
                "narration_start_s": narr_start,
                "narration_end_s": narr_end,
                "spoken_narration": spoken_txt,
                "selected_asset": s.src_file,
                "media_type": mtype,
                "source_creator": asset.creator_agency if asset else "Unknown",
                "source_url": asset.source_page_url if asset else "",
                "license": asset.license if asset else "Unverified",
                "visual_purpose": s.story_beat,
                "camera_perspective": persp,
                "crop_and_framing": {
                    "reframe_mode": s.reframe_mode,
                    "center_start": [s.cx0, s.cy0],
                    "center_end": [s.cx1, s.cy1],
                    "zoom_range": [s.z0, s.z1],
                    "rationale": s.crop_rationale,
                },
                "transition": {
                    "type": "opening" if idx == 0 else s.transition_in,
                    "duration_s": s.transition_duration_s if (idx > 0 and s.transition_in == "dissolve") else 0.0,
                    "reason": s.transition_reason,
                },
                "audio_design": {
                    "active_layers": list(s.scene_audio_layers),
                    "diegetic_nat_gain_db": s.nat_audio_gain_db,
                },
                "adaptive_duration_evaluation": adap,
                "why_shot_belongs_here": s.editorial_rationale or s.associated_narration_concept or s.story_beat,
            }
        )

    out_p = Path(manifest.output_dir) / "semantic_timeline_manifest.json"
    if Path(manifest.output_dir).exists():
        out_p.write_text(json.dumps({"slug": manifest.slug, "scenes": scenes}, indent=2), encoding="utf-8")
    return {"slug": manifest.slug, "scene_count": len(scenes), "scenes": scenes}


def audit_shot_plan_and_alignment(
    manifest: EpisodeManifest,
    wt: dict,
    style: DocumentaryStyleProfile,
) -> dict[str, Any]:
    """
    Comprehensive pre- and post-render audit of:
    1. Moving footage ratio vs. static photos vs. illustrative diagrams.
    2. Asset reuse, duration-share caps, and anti-repeated-still-zoom rule.
    3. Crop feasibility & source resolution quality for 9:16 full-screen composition.
    4. Meaning-based adaptive shot pacing, dissolve restraint, and speech-boundary alignment.
    5. Cinematic perspective variety across the 10 documentary shot perspectives.
    6. Explicit visual-to-narration matching and scientific claim qualification.
    """
    fps = style.output.fps
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)
    total_dur = max(1e-6, float(wt["total_duration_s"]))
    boundaries = extract_speech_boundaries(wt)
    assets_by_name = {a.local_file: a for a in manifest.assets_register}

    moving_video_s = 0.0
    still_photo_s = 0.0
    diagram_s = 0.0
    human_interaction_s = 0.0
    human_interaction_shots = 0
    prev_mtype = ""
    asset_uses: Counter[str] = Counter()
    asset_dur: Counter[str] = Counter()
    still_photo_uses: Counter[str] = Counter()
    perspectives_seq: list[str] = []

    durations: list[float] = []
    dissolve_count = 0
    boundary_aligned_cuts = 0
    total_internal_cuts = max(0, len(timed_shots) - 1)

    warnings: list[str] = []
    errors: list[str] = []
    shot_audits: list[dict[str, Any]] = []

    words = wt.get("words", [])

    for idx, s in enumerate(timed_shots):
        dur = round(s.end_s - s.start_s, 3)
        durations.append(dur)
        asset_uses[s.src_file] += 1
        asset_dur[s.src_file] += dur

        asset_spec = assets_by_name.get(s.src_file)
        cand_paths = [d / s.src_file for d in manifest.all_asset_search_dirs()] + [Path(s.src_file)]
        resolved_path = next((p for p in cand_paths if p.exists()), None)

        if style.asset_selection.forbid_muted_talking_heads and s.is_talking_head:
            errors.append(
                f"[{s.sid}] Muted talking-head footage ('{s.src_file}') is forbidden under voiceover in {style.profile_name}; "
                "use direct phenomenon/fieldwork visuals instead."
            )

        if not s.is_real_evidence or s.kind == "diagram" or (asset_spec and asset_spec.media_type == "diagram"):
            mtype = "diagram"
            diagram_s += dur
        elif s.kind in ("triptych_hook", "video_full", "video_window", "svs_flyover", "microscopy_dual") or (
            asset_spec and asset_spec.media_type == "video"
        ):
            mtype = "video"
            moving_video_s += dur
        else:
            mtype = "photo"
            still_photo_s += dur
            canon_still_id = resolve_canonical_source_id(asset_spec, s.src_file)
            still_photo_uses[canon_still_id] += 1
            is_permitted_callback = bool(getattr(s, "intentional_callback", False) and getattr(s, "callback_purpose", ""))
            if (
                (style.asset_selection.forbid_repeated_same_image_zoom or style.asset_selection.forbid_multi_crop_single_photo)
                and still_photo_uses[canon_still_id] > 1
                and not is_permitted_callback
            ):
                errors.append(
                    f"[{s.sid}] Still photograph '{s.src_file}' is reused multiple times (canonical source '{canon_still_id}'); "
                    "splitting or re-cropping one photograph into multiple fake scenes is forbidden."
                )
            if idx == 0 and dur > style.viral_retention.max_opening_still_duration_s + 0.08:
                errors.append(
                    f"[{s.sid}] Opening shot is a static photo lasting {dur:.2f}s (> {style.viral_retention.max_opening_still_duration_s:.2f}s viral hook cap); "
                    "cut to real live-action moving footage within ~2s so viewers never swipe away on a slow photo pan."
                )
            elif dur > style.asset_selection.max_single_still_duration_s + 0.05 and not (
                getattr(s, "essential_historical_or_scientific_evidence", False)
                and style.asset_selection.allow_extended_still_for_essential_evidence
            ):
                warnings.append(
                    f"[{s.sid}] Static photo duration {dur:.2f}s exceeds max_single_still_duration_s ({style.asset_selection.max_single_still_duration_s:.2f}s)."
                )
            # Footage-First v8 fix: NEVER exempt consecutive 2.5D parallax or re-cropped still photos unless running legacy_v6_fallback!
            allow_25d_pair = (
                bool(getattr(manifest, "legacy_v6_fallback", False))
                and style.asset_selection.location_authentic_mode
                and s.kind == "still_parallax_25d"
                and s.parallax_px >= 8.0
                and (idx == 0 or timed_shots[idx - 1].src_file != s.src_file or timed_shots[idx - 1].crop_box != s.crop_box)
            )
            if style.asset_selection.forbid_consecutive_still_shots and prev_mtype == "photo" and not allow_25d_pair:
                errors.append(
                    f"[{s.sid}] Consecutive static photo shots ({timed_shots[idx - 1].sid} -> {s.sid}, including animated stills) are forbidden in {style.profile_name}; interleave real moving footage."
                )

        persp = _infer_shot_perspective(s, mtype)
        perspectives_seq.append(persp)

        if s.has_human_interaction:
            human_interaction_shots += 1
            human_interaction_s += dur
        prev_mtype = mtype

        # Check spoken narration during this shot
        spoken_words = [
            w["word"]
            for w in words
            if s.start_s - 0.04 <= 0.5 * (float(w["start"]) + float(w["end"])) < s.end_s
        ]
        spoken_text = " ".join(spoken_words).strip()

        # Adaptive shot duration evaluation
        adap_eval = calculate_adaptive_shot_duration(
            visual_complexity=s.visual_complexity,
            spoken_importance=s.spoken_importance,
            camera_perspective=persp,
            camera_movement=s.camera_movement,
            is_moving_footage=(mtype == "video"),
            spoken_word_count=len(spoken_words),
            quantitative_fact_count=len(re.findall(r"\d+", spoken_text)),
            style=style,
        )

        # Check speech-boundary alignment at cut INTO this shot (`idx > 0`)
        cut_aligned = True
        nearest_boundary_dist = 0.0
        nearest_boundary_kind = "start"
        if idx > 0:
            sliced_word = next(
                (
                    w["word"]
                    for w in words
                    if float(w["start"]) + 0.07 < s.start_s < float(w["end"]) - 0.07
                ),
                None,
            )
            nearest = min(boundaries, key=lambda b: abs(float(b["time_s"]) - s.start_s))
            nearest_boundary_dist = round(abs(float(nearest["time_s"]) - s.start_s), 3)
            nearest_boundary_kind = str(nearest["kind"])
            cut_aligned = (sliced_word is None) and (
                nearest_boundary_dist <= style.pacing.speech_pause_snap_tolerance_s
            )
            if cut_aligned:
                boundary_aligned_cuts += 1
            else:
                warnings.append(
                    f"[{s.sid}] Cut at {s.start_s:.2f}s is {nearest_boundary_dist:.2f}s from nearest speech pause"
                    + (f" (slices word '{sliced_word}')" if sliced_word else "")
                )

        # Check shot duration bounds
        if dur < style.pacing.min_shot_duration_s:
            warnings.append(
                f"[{s.sid}] Shot duration {dur:.2f}s is shorter than minimum {style.pacing.min_shot_duration_s:.2f}s."
            )
        if dur > style.pacing.max_shot_duration_s:
            warnings.append(
                f"[{s.sid}] Shot duration {dur:.2f}s exceeds maximum {style.pacing.max_shot_duration_s:.2f}s."
            )

        # Check transition rules
        if idx > 0 and s.transition_in == "dissolve":
            dissolve_count += 1
            d_lo, d_hi = style.pacing.dissolve_range_s
            if not (d_lo - 0.05 <= s.transition_duration_s <= d_hi + 0.05):
                warnings.append(
                    f"[{s.sid}] Dissolve duration {s.transition_duration_s:.2f}s outside recommended {d_lo:.2f}–{d_hi:.2f}s."
                )

        # Check crop feasibility if source media exists on disk
        crop_info = None
        if resolved_path is not None and mtype in ("video", "photo"):
            sw, sh, _, vid_dur = _probe_media_dimensions_and_type(resolved_path)
            if s.crop_box:
                sw = max(1, s.crop_box[2] - s.crop_box[0])
                sh = max(1, s.crop_box[3] - s.crop_box[1])
            feas = evaluate_crop_feasibility(
                sw,
                sh,
                target_w=style.output.width,
                target_h=style.output.height,
                max_zoom=max(s.z0, s.z1),
                min_cropped_source_height_px=style.composition.min_cropped_source_height_px,
                max_upscale_warn=style.composition.max_upscale_factor_warn,
                contains_wide_axes_or_text=bool(asset_spec and not asset_spec.allow_cropping),
            )
            crop_info = {
                **feas.__dict__,
                "is_native_full_hd_vertical": bool(feas.crop_width_px >= style.output.width - 1 and feas.crop_height_px >= style.output.height - 1),
                "honest_quality_tier": (
                    "native_1080x1920"
                    if (feas.crop_width_px >= style.output.width - 1 and feas.crop_height_px >= style.output.height - 1)
                    else ("hd_vertical_reframe" if feas.crop_height_px >= 960 else "upscaled_sub_hd_crop")
                ),
            }
            for cw_msg in feas.warnings:
                warnings.append(f"[{s.sid}:{s.src_file}] {cw_msg}")
            if mtype == "video" and vid_dur > 0 and (s.src_in + dur) > vid_dur + 0.35:
                errors.append(
                    f"[{s.sid}] Video window [{s.src_in:.2f}s..{s.src_in + dur:.2f}s] exceeds clip duration {vid_dur:.2f}s ({s.src_file})."
                )
            if mtype == "video":
                mot = audit_clip_real_motion(
                    resolved_path,
                    start_s=s.src_in,
                    duration_s=min(dur, 3.5),
                    metadata_hint=f"{getattr(asset_spec, 'title', '') if asset_spec else ''} {s.visual_desc} {s.story_beat}",
                )
                if mot.get("valid") and not mot.get("is_real_moving_footage"):
                    # Do NOT let an animated JPEG or frozen slide masquerade as moving footage!
                    moving_video_s = max(0.0, moving_video_s - dur)
                    if mot.get("is_dense_presentation_graphic"):
                        diagram_s += dur
                        mtype = "diagram"
                    else:
                        still_photo_s += dur
                        mtype = "photo"
                    warnings.append(
                        f"[{s.sid}:{s.src_file}] Reclassified from video to '{mot.get('inferred_media_class')}' ({mot.get('diagnostic_note')})."
                    )

        # Scientific integrity & representative-material disclosure check
        if s.subject_match_kind in ("representative_organism_microscopy", "illustrative_diagram") and s.kind != "diagram":
            if not s.context_note:
                errors.append(
                    f"[{s.sid}] Shot uses '{s.subject_match_kind}' ({s.src_file}) without a restrained `context_note` clarifying illustrative status."
                )

        if style.asset_selection.require_narration_alignment_audit and idx < len(timed_shots) - 1:
            if not spoken_text and dur > 2.5:
                warnings.append(f"[{s.sid}] No narration words spoken during shot ({s.start_s:.2f}–{s.end_s:.2f}s).")

        shot_audits.append(
            {
                "sid": s.sid,
                "start_s": s.start_s,
                "end_s": s.end_s,
                "duration_s": dur,
                "adaptive_duration_eval": adap_eval,
                "media_type": mtype,
                "kind": s.kind,
                "camera_perspective": persp,
                "src_file": s.src_file,
                "transition_in": s.transition_in if idx > 0 else "opening",
                "transition_duration_s": s.transition_duration_s if (idx > 0 and s.transition_in == "dissolve") else 0.0,
                "transition_reason": s.transition_reason,
                "cut_speech_boundary_aligned": cut_aligned,
                "nearest_speech_boundary_s": nearest_boundary_dist,
                "nearest_speech_boundary_kind": nearest_boundary_kind,
                "subject_match_kind": s.subject_match_kind,
                "scientific_claim_status": s.scientific_claim_status,
                "context_note": s.context_note,
                "spoken_narration": spoken_text,
                "story_beat": s.story_beat,
                "crop_feasibility": crop_info,
            }
        )

    # Perspective variety checks (Part 3, Section 4.3)
    distinct_perspectives = sorted(set(perspectives_seq))
    if len(timed_shots) >= 8 and len(distinct_perspectives) < style.asset_selection.min_distinct_perspectives:
        warnings.append(
            f"Episode uses only {len(distinct_perspectives)} distinct shot perspectives ({', '.join(distinct_perspectives)}); "
            f"target >= {style.asset_selection.min_distinct_perspectives} for cinematic documentary variety."
        )
    for k in range(len(perspectives_seq) - 3):
        if perspectives_seq[k] == perspectives_seq[k + 1] == perspectives_seq[k + 2] == perspectives_seq[k + 3]:
            warnings.append(
                f"Four consecutive shots ({timed_shots[k].sid}..{timed_shots[k + 3].sid}) repeat '{perspectives_seq[k]}' perspective; "
                "vary scale/angle (wide -> fieldwork -> close-up/macro)."
            )

    # Asset overuse checks
    for fname, count in asset_uses.items():
        if count > style.asset_selection.max_uses_per_asset:
            warnings.append(
                f"Asset '{fname}' used {count} times (exceeds max_uses_per_asset={style.asset_selection.max_uses_per_asset})."
            )
        share = asset_dur[fname] / total_dur
        if share > style.asset_selection.max_duration_share_per_asset:
            warnings.append(
                f"Asset '{fname}' occupies {share*100:.1f}% of runtime (exceeds {style.asset_selection.max_duration_share_per_asset*100:.0f}% cap)."
            )

    moving_ratio = moving_video_s / total_dur
    still_ratio = still_photo_s / total_dur
    authentic_ratio = (moving_video_s + still_photo_s) / total_dur
    diagram_ratio = diagram_s / total_dur
    dissolve_fraction = dissolve_count / max(1, total_internal_cuts)

    if dissolve_fraction > style.pacing.max_dissolve_fraction_of_cuts:
        warnings.append(
            f"Dissolve fraction {dissolve_fraction*100:.1f}% exceeds max_dissolve_fraction_of_cuts ({style.pacing.max_dissolve_fraction_of_cuts*100:.0f}%)."
        )

    eff_moving_target = (
        min(style.asset_selection.target_moving_footage_ratio, 0.50)
        if style.asset_selection.location_authentic_mode
        else style.asset_selection.target_moving_footage_ratio
    )
    eff_max_still = (
        max(style.asset_selection.max_still_photo_ratio, 0.46)
        if style.asset_selection.location_authentic_mode
        else style.asset_selection.max_still_photo_ratio
    )

    if moving_ratio < eff_moving_target:
        warnings.append(
            f"Moving footage ratio is {moving_ratio*100:.1f}% (goal >= {eff_moving_target*100:.0f}% where authentic moving material is available)."
        )
    if still_ratio > eff_max_still + 0.005:
        warnings.append(
            f"Static photo ratio is {still_ratio*100:.1f}% (exceeds max_still_photo_ratio={eff_max_still*100:.0f}%)."
        )
    if (
        style.asset_selection.prefer_human_fieldwork_interaction
        and human_interaction_shots < style.asset_selection.min_human_interaction_shots
    ):
        warnings.append(
            f"Only {human_interaction_shots} human-interaction shot(s) found (target >= {style.asset_selection.min_human_interaction_shots} where fieldwork footage exists)."
        )

    script_audit = audit_viral_shorts_script(manifest, style)
    errors.extend(script_audit["errors"])
    warnings.extend(script_audit["warnings"])

    first_motion_s = 0.0
    if shot_audits and shot_audits[0]["media_type"] != "video":
        first_vid = next((sa for sa in shot_audits if sa["media_type"] == "video"), None)
        first_motion_s = float(first_vid["start_s"]) if first_vid else total_dur

    coverage_v8 = compute_visual_coverage_metrics(
        timed_shots,
        manifest.assets_register,
        manifest=manifest,
        probe_pixels=True,
    )
    rep_audit = audit_visual_repetition_and_progression(
        manifest,
        timed_shots,
        wt=wt,
        probe_pixels=True,
    )
    # Use source-honest v8 coverage whenever static panels inside triptychs or animated stills would have inflated moving_video_s
    if coverage_v8["genuine_moving_footage_s"] < moving_video_s - 0.05:
        moving_video_s = float(coverage_v8["genuine_moving_footage_s"])
        still_photo_s = float(coverage_v8["static_image_s"])
        diagram_s = float(coverage_v8["scientific_visualization_s"])
        moving_ratio = moving_video_s / total_dur
        still_ratio = still_photo_s / total_dur
        diagram_ratio = diagram_s / total_dur
        authentic_ratio = (moving_video_s + still_photo_s) / total_dur

    build_semantic_timeline_manifest(manifest, wt, style)

    return {
        "style_profile": style.profile_name,
        "total_duration_s": round(total_dur, 3),
        "shot_count": len(timed_shots),
        "distinct_source_assets_count": rep_audit["distinct_canonical_assets_count"],
        "raw_unique_filenames_count": len(asset_uses),
        "distinct_perspectives": distinct_perspectives,
        "distinct_perspectives_count": len(distinct_perspectives),
        "first_real_motion_start_s": round(first_motion_s, 3),
        "viral_script_audit": script_audit,
        "moving_footage_s": round(moving_video_s, 3),
        "moving_footage_pct": round(moving_ratio * 100.0, 2),
        "meets_moving_footage_goal": moving_ratio >= eff_moving_target - 0.02,
        "still_photography_s": round(still_photo_s, 3),
        "still_photography_pct": round(100.0 * still_photo_s / total_dur, 2),
        "human_interaction_shots": human_interaction_shots,
        "human_interaction_s": round(human_interaction_s, 3),
        "human_interaction_pct": round(100.0 * human_interaction_s / total_dur, 2),
        "illustrative_diagram_s": round(diagram_s, 3),
        "illustrative_diagram_pct": round(diagram_ratio * 100.0, 2),
        "authentic_visual_pct": round(authentic_ratio * 100.0, 2),
        # 5-Part Footage-First v8.0 Coverage Metrics (Part 2, Section 5)
        "visual_coverage_v8": coverage_v8,
        "genuine_moving_footage_pct": coverage_v8["genuine_moving_footage_pct"],
        "meaningful_action_footage_pct": coverage_v8["meaningful_action_footage_pct"],
        "establishing_footage_pct": coverage_v8["establishing_footage_pct"],
        "static_image_pct": coverage_v8["static_image_pct"],
        "scientific_visualization_pct": coverage_v8["scientific_visualization_pct"],
        "repetition_and_progression": rep_audit,
        "pacing_summary": {
            "min_shot_s": round(min(durations), 3) if durations else 0.0,
            "median_shot_s": round(sorted(durations)[len(durations) // 2], 3) if durations else 0.0,
            "mean_shot_s": round(sum(durations) / max(1, len(durations)), 3),
            "max_shot_s": round(max(durations), 3) if durations else 0.0,
            "internal_cuts": total_internal_cuts,
            "clean_cuts": total_internal_cuts - dissolve_count,
            "dissolves": dissolve_count,
            "dissolve_fraction": round(dissolve_fraction, 3),
            "speech_boundary_aligned_cuts": boundary_aligned_cuts,
            "speech_boundary_alignment_pct": round(100.0 * boundary_aligned_cuts / max(1, total_internal_cuts), 1),
        },
        "errors": errors,
        "warnings": warnings,
        "shots": shot_audits,
    }
