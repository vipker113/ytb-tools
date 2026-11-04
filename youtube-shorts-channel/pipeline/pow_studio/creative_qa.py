#!/usr/bin/env python3
"""
Automated & Creative Documentary Quality Assurance Engine (`pow_studio.creative_qa` v8.0).

Implements:
- Part 8 (Section 15): 6-Pillar Future-Video Quality Assurance (`run_six_pillar_workflow_qa`):
  1. `media_qa`      — Original 10-class media type, source/license, native vs cropped resolution
                       honesty, motion authenticity (catches animated stills & slideshows).
  2. `semantic_qa`   — Visible subject, visible action, exact narration match, keyword-trap
                       lecture/talking-head detection, undisclosed proxy-location detection,
                       and filler scenes without storytelling purpose.
  3. `repetition_qa` — Duplicated clips, perceptual `dHash`/`pHash` near-duplicates, multiple
                       artificial crops from one source, unnecessary repeated photographs.
  4. `timeline_qa`   — Adaptive shot durations, meaningful scene progression, voice/visual
                       speech-boundary sync, transition restraint, stale visuals across topic shifts.
  5. `technical_qa`  — Encoded dimensions (`1080x1920`, `9:16`), frame rate (`30 FPS`), H.264/AAC,
                       audio-video synchronization, subtitle timing, full-canvas borderless render.
  6. `creative_qa`   — Coherent story arc, every shot justified, real activity shown when actions
                       are narrated, slideshow-section detection, repetition, ending payoff.

  Separates `technical_approval` from `creative_approval` so a technically flawless encode
  NEVER automatically receives creative approval when visuals are misleading, repetitive,
  or slideshow-like. Also works pre-render (`dry_run=True`) to flag projects before rendering!

- Studio v7 Voice, Music & Effect Creative QA (`run_creative_qa`) preserved with full
  backward compatibility and enriched with `six_pillar_qa`.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Optional

from .action_storytelling import evaluate_action_visual_match, extract_narration_visual_beats
from .audio_registry import DEPRECATED_DECORATIVE_SFX
from .deduplication import audit_visual_repetition_and_progression
from .media_classifier import (
    GENUINE_MOVING_CLASSES,
    STATIC_IMAGE_CLASSES,
    SourceMediaClass,
    compute_visual_coverage_metrics,
    inspect_media_authenticity,
)
from .reframing import evaluate_crop_feasibility
from .rights_gate import RightsViolationError, validate_license_string
from .schema import EpisodeManifest, resolve_timed_shots

SeverityLevel = Literal["CRITICAL", "MAJOR", "MINOR", "INFO"]


def _synthetic_wt_from_manifest(manifest: EpisodeManifest, fps: int = 30) -> dict[str, Any]:
    """Construct deterministic narration timing metadata for pre-render dry-run QA when `word_timings.json` does not exist yet."""
    total_dur = max(1.0, float(manifest.shots[-1].end_s))
    n_segs = max(1, len(manifest.narration_segments))
    seg_dur = total_dur / float(n_segs)
    segments = []
    words = []
    for idx, seg in enumerate(manifest.narration_segments):
        s0 = round(idx * seg_dur, 3)
        s1 = round((idx + 1) * seg_dur - 0.18, 3)
        toks = seg.text.split()
        wd = max(0.05, (s1 - s0) / float(max(1, len(toks))))
        for wi, tok in enumerate(toks):
            words.append(
                {
                    "seg_id": seg.seg_id,
                    "word": tok,
                    "start": round(s0 + wi * wd, 3),
                    "end": round(s0 + (wi + 0.85) * wd, 3),
                }
            )
        segments.append({"seg_id": seg.seg_id, "text": seg.text, "start": s0, "end": s1})
    return {
        "total_duration_s": round(total_dur, 3),
        "total_frames_30fps": int(round(total_dur * fps)),
        "segments": segments,
        "words": words,
    }


def run_six_pillar_workflow_qa(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    rendered_mp4: Optional[Path] = None,
    probe_pixels: bool = True,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Execute the complete 6-Pillar Future-Video QA audit (Media, Semantic, Repetition,
    Timeline, Technical, Creative) either pre-render (dry-run) or post-render.
    """
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    eff_wt = wt if (wt and wt.get("total_frames_30fps")) else _synthetic_wt_from_manifest(manifest, fps=fps)
    timed_shots = resolve_timed_shots(manifest, int(eff_wt["total_frames_30fps"]), fps=fps)
    total_dur = max(0.1, float(eff_wt["total_duration_s"]))
    assets_by_name = {a.local_file: a for a in manifest.assets_register}
    search_dirs = manifest.all_asset_search_dirs()

    def _resolve_asset(fname: str) -> Optional[Path]:
        for d in search_dirs:
            cand = d / fname
            if cand.exists():
                return cand
        direct = Path(fname)
        return direct if direct.exists() else None

    issues: list[dict[str, Any]] = []

    def _flag(severity: SeverityLevel, pillar: str, code: str, message: str, sid: str = "") -> None:
        issues.append(
            {
                "severity": severity,
                "pillar": pillar,
                "code": code,
                "sid": sid,
                "message": message,
            }
        )

    # ==========================================================================
    # PILLAR 1: MEDIA QA
    # ==========================================================================
    coverage = compute_visual_coverage_metrics(
        timed_shots,
        manifest.assets_register,
        manifest=manifest,
        probe_pixels=probe_pixels,
    )

    for a in manifest.assets_register:
        try:
            validate_license_string(a.license, a.local_file)
        except RightsViolationError as exc:
            _flag("CRITICAL", "media_qa", "unverified_commercial_license", str(exc))
        if not a.source_page_url or not a.creator_agency:
            _flag("MAJOR", "media_qa", "missing_source_provenance", f"Asset '{a.local_file}' lacks complete source_page_url or creator_agency.")

    shot_cls_map = {sc["sid"]: sc for sc in coverage["shot_classifications"]}
    resolution_records: list[dict[str, Any]] = []

    for sh in timed_shots:
        sc = shot_cls_map[sh.sid]
        aspec = assets_by_name.get(sh.src_file)
        rpath = _resolve_asset(sh.src_file)

        if sc["source_media_class"] == SourceMediaClass.AI_GENERATED.value and sh.is_real_evidence:
            _flag(
                "CRITICAL",
                "media_qa",
                "ai_generated_misrepresented_as_real",
                f"Shot {sh.sid} ('{sh.src_file}') is AI_GENERATED and must NEVER be presented as real documentary footage.",
                sid=sh.sid,
            )
        if sc["source_media_class"] == SourceMediaClass.REENACTMENT.value and not sh.context_note:
            _flag(
                "MAJOR",
                "media_qa",
                "undisclosed_reenactment",
                f"Shot {sh.sid} ('{sh.src_file}') is a staged REENACTMENT without an explicit context_note disclosure.",
                sid=sh.sid,
            )

        # Detect video files claiming to be moving video that are actually animated stills or dense slides
        if probe_pixels and rpath is not None and rpath.exists():
            aud = inspect_media_authenticity(
                rpath,
                start_s=sh.src_in,
                duration_s=min(4.0, max(1.2, sh.end_s - sh.start_s)),
                metadata_hint=f"{getattr(aspec, 'title', '') if aspec else ''} {sh.visual_desc} {sh.story_beat}",
            )
            if aud.valid:
                if aud.width > 0 and aud.height > 0:
                    feas = evaluate_crop_feasibility(
                        aud.width,
                        aud.height,
                        target_w=style.output.width,
                        target_h=style.output.height,
                        max_zoom=max(sh.z0, sh.z1),
                        min_cropped_source_height_px=style.composition.min_cropped_source_height_px,
                        max_upscale_warn=style.composition.max_upscale_factor_warn,
                        contains_wide_axes_or_text=bool(aspec and not aspec.allow_cropping),
                    )
                    is_native_fhd = feas.crop_width_px >= style.output.width - 1 and feas.crop_height_px >= style.output.height - 1
                    resolution_records.append(
                        {
                            "sid": sh.sid,
                            "src_file": sh.src_file,
                            "native_resolution": f"{aud.width}x{aud.height}",
                            "cropped_9x16_px": f"{feas.crop_width_px:.0f}x{feas.crop_height_px:.0f}",
                            "upscale_factor": feas.upscale_factor,
                            "is_native_full_hd_vertical": is_native_fhd,
                        }
                    )
                    if not feas.feasible:
                        _flag(
                            "MAJOR",
                            "media_qa",
                            "low_resolution_or_infeasible_crop",
                            f"Shot {sh.sid} ('{sh.src_file}', {aud.width}x{aud.height}) fails 9:16 quality floor: {'; '.join(feas.warnings)}",
                            sid=sh.sid,
                        )
                if sh.kind == "video_full" and aud.is_baked_animated_still:
                    _flag(
                        "MAJOR",
                        "media_qa",
                        "animated_still_disguised_as_video",
                        f"Shot {sh.sid} ('{sh.src_file}') is a static image with artificial pan/zoom baked into MP4 ({aud.diagnostic_note}).",
                        sid=sh.sid,
                    )
                if sh.kind == "video_full" and aud.is_frozen_static:
                    _flag(
                        "MAJOR",
                        "media_qa",
                        "frozen_clip_disguised_as_video",
                        f"Shot {sh.sid} ('{sh.src_file}') contains zero genuine temporal motion ({aud.diagnostic_note}).",
                        sid=sh.sid,
                    )
                if style.asset_selection.forbid_presentation_slide_graphics and aud.is_dense_presentation_graphic and (sh.end_s - sh.start_s) > style.asset_selection.max_single_infographic_duration_s:
                    _flag(
                        "MAJOR",
                        "media_qa",
                        "dense_presentation_slide_graphic",
                        f"Shot {sh.sid} ('{sh.src_file}', {sh.end_s - sh.start_s:.1f}s) is a dense presentation-style graphic held over narration.",
                        sid=sh.sid,
                    )

    # ==========================================================================
    # PILLAR 2: SEMANTIC QA
    # ==========================================================================
    seg_beats = extract_narration_visual_beats(manifest.narration_segments, topic=manifest.topic or manifest.primary_title)
    beats_by_seg: dict[str, list[Any]] = {}
    for b in seg_beats:
        beats_by_seg.setdefault(b.seg_id, []).append(b)

    for sh in timed_shots:
        aspec = assets_by_name.get(sh.src_file)
        if style.asset_selection.forbid_muted_talking_heads and sh.is_talking_head:
            _flag(
                "MAJOR",
                "semantic_qa",
                "muted_talking_head_filler",
                f"Shot {sh.sid} ('{sh.src_file}') shows a muted talking head under narration.",
                sid=sh.sid,
            )

        if re.search(r"\b(?:decorative filler|b-roll filler|generic scenery filler|padding)\b", f"{sh.story_beat} {sh.editorial_rationale} {sh.visual_desc}", re.I):
            _flag(
                "MAJOR",
                "semantic_qa",
                "no_storytelling_purpose",
                f"Shot {sh.sid} ('{sh.src_file}') is generic/decorative filler with no meaningful storytelling purpose.",
                sid=sh.sid,
            )

        # Action & Location match against associated narration segment
        seg_id = sh.associated_seg_id
        if not seg_id and eff_wt.get("segments"):
            t_mid = 0.5 * (sh.start_s + sh.end_s)
            best_sg = min(
                eff_wt["segments"],
                key=lambda sg: 0.0 if float(sg["start"]) <= t_mid <= float(sg["end"]) else min(abs(t_mid - float(sg["start"])), abs(t_mid - float(sg["end"]))),
            )
            seg_id = str(best_sg.get("seg_id", ""))

        rel_beats = beats_by_seg.get(seg_id or "", [])
        if rel_beats and sh.kind != "triptych_hook":
            cand_payload = {
                "local_file": sh.src_file,
                "title": getattr(aspec, "title", "") if aspec else "",
                "description": f"{getattr(aspec, 'intended_use', '') if aspec else ''} {sh.visual_desc} {sh.visible_action} {sh.story_beat}",
                "depicted_subject": getattr(aspec, "depicted_subject", "") if aspec else "",
                "depicted_action": sh.visible_action or (getattr(aspec, "depicted_action", "") if aspec else ""),
                "depicted_location": getattr(aspec, "depicted_location", "") if aspec else "",
                "historical_era": getattr(aspec, "historical_era", "") if aspec else "",
                "license": getattr(aspec, "license", "Public Domain") if aspec else "Public Domain",
                "source_media_class": shot_cls_map[sh.sid]["effective_media_class"],
                "is_talking_head": sh.is_talking_head,
                "explicit_analog_comparison": bool(sh.explicit_analog_comparison or sh.context_note),
            }
            evals = [evaluate_action_visual_match(rb, cand_payload) for rb in rel_beats]
            best_ev = max(evals, key=lambda x: (x["eligible"], x["overall_relevance"]))
            if not best_ev["eligible"] and best_ev["rejection_reason"]:
                if "Keyword-trap" in best_ev["rejection_reason"] or "proxy-location" in best_ev["rejection_reason"] or "Historical" in best_ev["rejection_reason"] or "Generic scenic" in best_ev["rejection_reason"]:
                    _flag(
                        "MAJOR",
                        "semantic_qa",
                        "semantic_action_or_location_mismatch",
                        f"Shot {sh.sid} ('{sh.src_file}'): {best_ev['rejection_reason']}",
                        sid=sh.sid,
                    )

    # ==========================================================================
    # PILLAR 3: REPETITION QA
    # ==========================================================================
    rep_audit = audit_visual_repetition_and_progression(
        manifest,
        timed_shots,
        wt=eff_wt,
        probe_pixels=probe_pixels,
    )
    for r_iss in rep_audit["issues"]:
        if r_iss["kind"] in ("stale_visual_across_topic_shift", "weak_scene_progression"):
            continue  # Routed to Timeline QA below
        _flag(
            r_iss["severity"],  # type: ignore[arg-type]
            "repetition_qa",
            r_iss["kind"],
            r_iss["detail"],
            sid=str(r_iss.get("sid", "")),
        )

    # ==========================================================================
    # PILLAR 4: TIMELINE QA
    # ==========================================================================
    words = eff_wt.get("words", [])
    dissolves = 0
    for idx, sh in enumerate(timed_shots):
        dur = sh.end_s - sh.start_s
        if dur < 1.5:
            _flag(
                "MAJOR",
                "timeline_qa",
                "rushed_shot_duration",
                f"Shot {sh.sid} lasts {dur:.2f}s (< 1.50s viewer comprehension floor).",
                sid=sh.sid,
            )
        if idx > 0:
            if sh.transition_in == "dissolve":
                dissolves += 1
            sliced = next(
                (w["word"] for w in words if float(w["start"]) + 0.08 < sh.start_s < float(w["end"]) - 0.08),
                None,
            )
            if sliced:
                _flag(
                    "MINOR",
                    "timeline_qa",
                    "mid_word_cut",
                    f"Cut into {sh.sid} at {sh.start_s:.2f}s occurs mid-word ('{sliced}').",
                    sid=sh.sid,
                )

    if len(timed_shots) > 2 and (dissolves / float(len(timed_shots) - 1)) > style.pacing.max_dissolve_fraction_of_cuts:
        _flag(
            "MINOR",
            "timeline_qa",
            "excessive_dissolves",
            f"Dissolve ratio {dissolves}/{len(timed_shots)-1} exceeds {style.pacing.max_dissolve_fraction_of_cuts:.0%} documentary restraint.",
        )

    for r_iss in rep_audit["issues"]:
        if r_iss["kind"] in ("stale_visual_across_topic_shift", "weak_scene_progression"):
            _flag(
                r_iss["severity"],  # type: ignore[arg-type]
                "timeline_qa",
                r_iss["kind"],
                r_iss["detail"],
                sid=str(r_iss.get("sid", "")),
            )

    # ==========================================================================
    # PILLAR 5: TECHNICAL QA
    # ==========================================================================
    tech_details: dict[str, Any] = {
        "target_resolution": f"{style.output.width}x{style.output.height}",
        "target_aspect_ratio": style.output.aspect_ratio,
        "target_fps": style.output.fps,
        "target_video_codec": style.output.video_codec_master,
        "target_audio_codec": style.output.audio_codec,
        "mode": "post_render_mp4" if (rendered_mp4 and rendered_mp4.exists()) else "dry_run_export_config",
    }
    if style.output.width != 1080 or style.output.height != 1920 or style.output.fps != 30:
        _flag(
            "CRITICAL",
            "technical_qa",
            "non_standard_shorts_export_target",
            f"Export config targets {style.output.width}x{style.output.height} @ {style.output.fps}fps instead of standard 1080x1920 @ 30fps.",
        )

    if rendered_mp4 is not None and rendered_mp4.exists():
        pr = subprocess.run(
            ["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(rendered_mp4)],
            capture_output=True,
            text=True,
        )
        if pr.returncode != 0:
            _flag("CRITICAL", "technical_qa", "ffprobe_failed", f"Unable to decode rendered MP4: {rendered_mp4}")
        else:
            pdata = json.loads(pr.stdout)
            v_st = next((s for s in pdata.get("streams", []) if s.get("codec_type") == "video"), {})
            a_st = next((s for s in pdata.get("streams", []) if s.get("codec_type") == "audio"), {})
            enc_w = int(v_st.get("width", 0) or 0)
            enc_h = int(v_st.get("height", 0) or 0)
            v_codec = str(v_st.get("codec_name", ""))
            a_codec = str(a_st.get("codec_name", ""))
            r_fps = str(v_st.get("r_frame_rate", ""))
            v_dur = float(v_st.get("duration") or pdata.get("format", {}).get("duration") or 0.0)
            a_dur = float(a_st.get("duration") or v_dur)
            av_drift = abs(v_dur - a_dur)
            tech_details.update(
                {
                    "encoded_width": enc_w,
                    "encoded_height": enc_h,
                    "video_codec": v_codec,
                    "audio_codec": a_codec,
                    "r_frame_rate": r_fps,
                    "av_sync_drift_s": round(av_drift, 4),
                }
            )
            if (enc_w, enc_h) != (1080, 1920):
                _flag("CRITICAL", "technical_qa", "wrong_encoded_dimensions", f"Encoded MP4 is {enc_w}x{enc_h} (expected 1080x1920).")
            if r_fps not in ("30/1", "30"):
                _flag("CRITICAL", "technical_qa", "wrong_frame_rate", f"Encoded frame rate is {r_fps} (expected 30/1 CFR).")
            if v_codec != "h264":
                _flag("MAJOR", "technical_qa", "unexpected_video_codec", f"Video codec is '{v_codec}' (expected 'h264').")
            if a_codec != "aac":
                _flag("MAJOR", "technical_qa", "unexpected_audio_codec", f"Audio codec is '{a_codec}' (expected 'aac').")
            if av_drift > 0.08:
                _flag("MAJOR", "technical_qa", "av_sync_drift", f"Audio/video stream duration drift is {av_drift:.3f}s (> 0.08s).")

    # ==========================================================================
    # PILLAR 6: CREATIVE QA
    # ==========================================================================
    # 1. Slideshow-section detector: consecutive STILL_PHOTO / ANIMATED_STILL stretches or excessive static image ratio
    consec_static_s = 0.0
    consec_static_sids: list[str] = []
    for sh in timed_shots:
        sc = shot_cls_map[sh.sid]
        if sc["effective_media_class"] in STATIC_IMAGE_CLASSES:
            consec_static_s += float(sc["duration_s"])
            consec_static_sids.append(sh.sid)
            if len(consec_static_sids) >= 2 and not getattr(manifest, "legacy_v6_fallback", False):
                _flag(
                    "MAJOR",
                    "creative_qa",
                    "slideshow_section_detected",
                    f"Consecutive static/animated-still sequence ({' -> '.join(consec_static_sids)}, {consec_static_s:.1f}s) feels like an automated photo slideshow.",
                    sid=sh.sid,
                )
        else:
            consec_static_s = 0.0
            consec_static_sids = []

    if coverage["static_image_ratio"] > max(style.asset_selection.max_static_image_ratio + 0.12, 0.35):
        _flag(
            "MAJOR",
            "creative_qa",
            "excessive_static_slideshow_ratio",
            f"Static/animated-still images occupy {coverage['static_image_pct']:.1f}% of runtime (target <= {style.asset_selection.max_static_image_ratio*100:.0f}%).",
        )

    if coverage["scientific_visualization_ratio"] > max(style.asset_selection.max_scientific_visualization_ratio + 0.10, 0.22):
        _flag(
            "MAJOR",
            "creative_qa",
            "infographic_domination",
            f"Diagrams/infographics occupy {coverage['scientific_visualization_pct']:.1f}% of runtime (target <= {style.asset_selection.max_scientific_visualization_ratio*100:.0f}%).",
        )

    # 2. Action coverage vs narrated actions
    essential_action_beats = [b for b in seg_beats if b.genuine_footage_essential]
    if len(essential_action_beats) >= 2 and coverage["meaningful_action_footage_ratio"] < 0.20:
        _flag(
            "MAJOR",
            "creative_qa",
            "missing_real_activity_for_narrated_actions",
            f"Script describes {len(essential_action_beats)} active physical events, but Meaningful Action Footage is only "
            f"{coverage['meaningful_action_footage_pct']:.1f}% (target >= {style.asset_selection.target_meaningful_action_footage_ratio*100:.0f}%).",
        )

    # 3. Story coherence & promised ending payoff check
    seg_ids = {s.seg_id for s in manifest.narration_segments}
    if manifest.editorial_formula.layer2_pivot_seg_id not in seg_ids or manifest.editorial_formula.scientific_caveat_seg_id not in seg_ids:
        _flag("MAJOR", "creative_qa", "missing_story_payoff_anchor", "Manifest lacks valid pivot or scientific payoff segment anchor.")
    last_seg_text = manifest.narration_segments[-1].text.strip()
    if re.search(r"\b(?:like and subscribe|follow for part 2|smash that like)\b", last_seg_text, re.I):
        _flag("MAJOR", "creative_qa", "generic_cta_ending_weakens_payoff", "Ending uses generic subscribe CTA instead of delivering documentary payoff.")

    # Compute per-pillar pass/fail and strict separation of Technical vs Creative approval
    pillars = ("media_qa", "semantic_qa", "repetition_qa", "timeline_qa", "technical_qa", "creative_qa")
    pillar_verdicts: dict[str, dict[str, Any]] = {}
    for p in pillars:
        p_issues = [x for x in issues if x["pillar"] == p]
        c_cnt = sum(1 for x in p_issues if x["severity"] == "CRITICAL")
        m_cnt = sum(1 for x in p_issues if x["severity"] == "MAJOR")
        pillar_verdicts[p] = {
            "passed": (c_cnt == 0 and m_cnt == 0),
            "critical_count": c_cnt,
            "major_count": m_cnt,
            "minor_count": sum(1 for x in p_issues if x["severity"] == "MINOR"),
            "issues": p_issues,
        }

    technical_approval = pillar_verdicts["technical_qa"]["passed"]
    creative_approval = all(
        pillar_verdicts[p]["passed"]
        for p in ("media_qa", "semantic_qa", "repetition_qa", "timeline_qa", "creative_qa")
    )

    out_report = {
        "slug": manifest.slug,
        "technical_approval": technical_approval,
        "creative_approval": creative_approval,
        "overall_release_approval": bool(technical_approval and creative_approval),
        "visual_coverage_metrics": {
            "genuine_moving_footage_pct": coverage["genuine_moving_footage_pct"],
            "meaningful_action_footage_pct": coverage["meaningful_action_footage_pct"],
            "establishing_footage_pct": coverage["establishing_footage_pct"],
            "real_time_lapse_pct": coverage["real_time_lapse_pct"],
            "static_image_pct": coverage["static_image_pct"],
            "animated_still_pct": coverage["animated_still_pct"],
            "scientific_visualization_pct": coverage["scientific_visualization_pct"],
        },
        "canonical_asset_summary": {
            "distinct_canonical_assets": rep_audit["distinct_canonical_assets_count"],
            "raw_unique_filenames": rep_audit["raw_unique_filenames_count"],
            "meaningful_progression_pct": round(100.0 * rep_audit["meaningful_progression_ratio"], 1),
        },
        "resolution_honesty_records": resolution_records,
        "technical_details": tech_details,
        "pillars": pillar_verdicts,
        "issues": issues,
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "six_pillar_qa_report.json").write_text(json.dumps(out_report, indent=2), encoding="utf-8")
        md_lines = [
            f"# 6-Pillar Future-Video QA Report — `{manifest.slug}`",
            "",
            f"- **Technical Approval:** `{'PASS' if technical_approval else 'FAIL'}`",
            f"- **Creative Approval:** `{'PASS' if creative_approval else 'FAIL'}`",
            f"- **Overall Release Approval:** `{'APPROVED' if out_report['overall_release_approval'] else 'BLOCKED_FOR_REVISION'}`",
            "",
            "## 5-Part Source-Honest Visual Coverage Metrics",
            f"- **A. Genuine Moving Footage Ratio:** `{coverage['genuine_moving_footage_pct']}%` (Time-lapse subset: `{coverage['real_time_lapse_pct']}%`)",
            f"- **B. Meaningful Action Footage Ratio:** `{coverage['meaningful_action_footage_pct']}%`",
            f"- **C. Establishing Footage Ratio:** `{coverage['establishing_footage_pct']}%`",
            f"- **D. Static Image Ratio:** `{coverage['static_image_pct']}%` (Animated stills: `{coverage['animated_still_pct']}%`)",
            f"- **E. Scientific Visualization Ratio:** `{coverage['scientific_visualization_pct']}%`",
            "",
            "## 6-Pillar Gate Summary",
            "| Pillar | Verdict | Critical | Major | Minor |",
            "|---|---|---|---|---|",
        ]
        for p in pillars:
            pv = pillar_verdicts[p]
            md_lines.append(
                f"| `{p}` | **{'PASS' if pv['passed'] else 'FAIL'}** | {pv['critical_count']} | {pv['major_count']} | {pv['minor_count']} |"
            )
        if issues:
            md_lines.extend(["", "## Detailed QA Findings", "| Severity | Pillar | Shot | Code | Message |", "|---|---|---|---|---|"])
            for iss in issues:
                md_lines.append(
                    f"| **{iss['severity']}** | `{iss['pillar']}` | `{iss['sid'] or '-'}` | `{iss['code']}` | {iss['message']} |"
                )
        (out_dir / "six_pillar_qa_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    return out_report


def run_creative_qa(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    subtitles_word_match_ratio: Optional[float] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Execute Studio v7 Voice QA, Music & Effect QA, and Visual & Audio Creative QA
    on the episode (plus attach `six_pillar_qa`) and export `creative_qa_report.json` / `.md`.
    """
    style = manifest.resolve_style_profile()
    target_dir = out_dir or Path(manifest.output_dir)
    fps = style.output.fps
    timed_shots = resolve_timed_shots(manifest, int(wt.get("total_frames_30fps", 300)), fps)
    total_dur = max(0.1, float(wt.get("total_duration_s", 0.0) or 0.1))

    def _load_json(name: str) -> dict[str, Any]:
        p = target_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    continuity_rep = _load_json("voice_continuity_report.json")
    audio_rep = _load_json("audio_engineering_report.json")
    music_plan = _load_json("music_plan.json")
    ambience_plan = _load_json("ambience_plan.json")
    sfx_plan = _load_json("sfx_plan.json")
    timeline_rep = _load_json("unified_av_timeline.json")

    issues: list[dict[str, Any]] = []

    def _add(severity: SeverityLevel, pillar: str, code: str, message: str) -> None:
        issues.append({"severity": severity, "pillar": pillar, "code": code, "message": message})

    # 1. VOICE QA
    words = wt.get("words", [])
    wpm = (len(words) / total_dur) * 60.0 if words else 0.0
    if words and (wpm < 95.0 or wpm > 210.0):
        _add("MAJOR", "voice_qa", "unnatural_speaking_rate", f"Measured speaking rate is {wpm:.1f} WPM (outside natural 95–210 WPM documentary cadence).")

    voices_seen = {
        str(s.get("voice_identity"))
        for s in wt.get("planned_voice_direction", [])
        if isinstance(s, dict) and s.get("voice_identity")
    }
    if len(voices_seen) > 1:
        _add("CRITICAL", "voice_qa", "inconsistent_voice_identity", f"Multiple narrator voice identities detected across segments: {sorted(voices_seen)}.")

    max_jump_db = float(
        continuity_rep.get("max_adjacent_rms_jump_db", continuity_rep.get("max_boundary_rms_jump_db", 0.0)) or 0.0
    )
    if max_jump_db > 7.5:
        _add("MAJOR", "voice_qa", "audible_segment_volume_jump", f"Segment join RMS jump of {max_jump_db:.2f} dB exceeds 7.5 dB continuity threshold.")
    elif max_jump_db > 5.0:
        _add("MINOR", "voice_qa", "mild_segment_volume_jump", f"Segment join RMS variation of {max_jump_db:.2f} dB noted.")

    if continuity_rep and not continuity_rep.get("continuity_pass", True):
        for c_iss in continuity_rep.get("issues", []):
            _add("MINOR", "voice_qa", "continuity_note", str(c_iss))

    high_drama_segs = 0
    theatrical_tags_found: list[str] = []
    for seg in manifest.narration_segments:
        d_up = (seg.delivery or "").upper()
        if any(k in d_up for k in ("DRAMATIC", "REVEAL", "URGENT")) or (seg.energy is not None and seg.energy >= 4):
            high_drama_segs += 1
        raw_annot = f"{seg.annotated_text or ''} {seg.tts_text or ''}"
        for bad_tag in ("whisper", "shouting", "screaming", "crying"):
            if re.search(rf"\[\s*{bad_tag}", raw_annot, re.I):
                theatrical_tags_found.append(f"{seg.seg_id}:{bad_tag}")

    if theatrical_tags_found:
        _add("MAJOR", "voice_qa", "theatrical_voice_tags", f"Exaggerated theatrical voice tags detected ({', '.join(theatrical_tags_found)}).")
    if len(manifest.narration_segments) >= 3 and (high_drama_segs / float(len(manifest.narration_segments))) > 0.55:
        _add(
            "MAJOR",
            "voice_qa",
            "over_dramatic_narration",
            f"{high_drama_segs}/{len(manifest.narration_segments)} narration segments use high-intensity/dramatic delivery; narrator lacks calm contrast.",
        )

    diag = audio_rep.get("diagnostics", wt.get("audio_diagnostics", {}))
    if int(diag.get("clipped_samples_count", 0)) > 0:
        _add("CRITICAL", "voice_qa", "audio_clipping", f"Detected {diag['clipped_samples_count']} clipped audio samples.")
    if int(diag.get("excessive_silence_count", 0)) > 0:
        _add("MAJOR", "voice_qa", "unnatural_pause", f"Detected {diag['excessive_silence_count']} unintended excessive silence gap(s).")
    if subtitles_word_match_ratio is not None and subtitles_word_match_ratio < 0.90:
        _add("MAJOR", "voice_qa", "pronunciation_or_asr_mismatch", f"Normalized Whisper word match ratio {subtitles_word_match_ratio:.2%} indicates pronunciation or word-cut defect.")

    # 2. MUSIC AND EFFECT QA
    margin_lu = float(audio_rep.get("voice_to_bed_margin_lu", 18.0))
    if margin_lu < 9.5:
        _add("CRITICAL", "music_and_effect_qa", "music_overpowering_narration", f"Voice-to-bed margin is only {margin_lu:.2f} LU (< 9.5 LU minimum); background sound overpowers narrator.")
    elif margin_lu < 11.0:
        _add("MINOR", "music_and_effect_qa", "tight_music_margin", f"Voice-to-bed margin is {margin_lu:.2f} LU; verify dense phrases remain effortless to understand.")

    applied_sfx = wt.get("sfx_applied", [])
    for cue in applied_sfx:
        sname = str(cue.get("sfx_name", ""))
        if sname in DEPRECATED_DECORATIVE_SFX or re.search(r"whoosh|boom|swipe|locator_ping", sname, re.I):
            _add("MAJOR", "music_and_effect_qa", "decorative_transition_sfx", f"Decorative transition/UI sound '{sname}' @ {cue.get('time_s')}s violates documentary restraint.")

    sfx_times = sorted(float(c.get("time_s", 0.0)) for c in applied_sfx)
    for t_a, t_b in zip(sfx_times, sfx_times[1:]):
        if (t_b - t_a) < 4.0:
            _add("MAJOR", "music_and_effect_qa", "competing_sfx", f"Two sound effects fire within {t_b - t_a:.2f}s ({t_a:.2f}s and {t_b:.2f}s), competing under speech.")

    for asec in ambience_plan.get("sections", []):
        if asec.get("environment") == "space_vacuum_silent" and asec.get("audible"):
            _add("CRITICAL", "music_and_effect_qa", "fake_space_sound", f"Ambience section {asec.get('ambience_id')} invents audible atmosphere during outer-space vacuum.")
        if asec.get("environment") == "space_vacuum_silent":
            s0, s1 = float(asec.get("start_s", 0.0)), float(asec.get("end_s", 0.0))
            for cue in applied_sfx:
                ct = float(cue.get("time_s", -1.0))
                if s0 <= ct <= s1:
                    _add("CRITICAL", "music_and_effect_qa", "sfx_in_space_vacuum", f"Sound effect '{cue.get('sfx_name')}' @ {ct:.2f}s plays during outer-space vacuum scene.")

    # 3. VISUAL AND AUDIO CREATIVE QA
    for a_sh, b_sh in zip(timed_shots, timed_shots[1:]):
        if a_sh.src_file == b_sh.src_file:
            _add(
                "MAJOR",
                "visual_and_audio_qa",
                "redundant_consecutive_scene",
                f"Consecutive surviving shots {a_sh.sid} and {b_sh.sid} repeat the exact same visual source '{a_sh.src_file}' without narrative reason.",
            )

    short_shots = [s for s in timed_shots if (s.end_s - s.start_s) < 1.5]
    if short_shots:
        _add(
            "MAJOR",
            "visual_and_audio_qa",
            "rushed_incomprehensible_scene",
            f"{len(short_shots)} shot(s) last < 1.5s ({', '.join(s.sid for s in short_shots)}), changing before the viewer can understand the image.",
        )

    for s in timed_shots:
        if re.search(r"\b(?:decorative filler|b-roll filler|unused repeat)\b", f"{s.story_beat} {s.editorial_rationale}", re.I):
            _add("MAJOR", "visual_and_audio_qa", "unremoved_decorative_scene", f"Decorative filler shot {s.sid} remained in the final edit.")

    for si in timeline_rep.get("sync_issues", []):
        sev = str(si.get("severity", "MINOR"))
        if sev not in ("CRITICAL", "MAJOR", "MINOR", "INFO"):
            sev = "MINOR"
        _add(sev, "visual_and_audio_qa", str(si.get("kind", "sync_issue")), str(si.get("detail", "")))  # type: ignore[arg-type]

    if music_plan.get("music_sections_count", 0) == 0:
        _add("INFO", "music_and_effect_qa", "intentional_no_music", "Episode intentionally uses zero background music so narration and authentic environment carry the story.")
    if len(applied_sfx) == 0:
        _add("INFO", "music_and_effect_qa", "intentional_zero_sfx", "Episode intentionally uses zero point SFX; silence and natural ambience preferred over artificial effects.")

    rendered_mp4_cand = target_dir / f"{manifest.slug}.mp4"
    six_pillar = run_six_pillar_workflow_qa(
        manifest=manifest,
        wt=wt,
        rendered_mp4=rendered_mp4_cand if rendered_mp4_cand.exists() else None,
        probe_pixels=True,
        out_dir=target_dir if target_dir.exists() else None,
    )

    sev_counts = Counter(i["severity"] for i in issues)
    creative_pass = (
        (sev_counts.get("CRITICAL", 0) == 0)
        and (sev_counts.get("MAJOR", 0) == 0)
        and bool(six_pillar["creative_approval"])
    )

    report = {
        "slug": manifest.slug,
        "creative_qa_pass": creative_pass,
        "six_pillar_qa": six_pillar,
        "severity_counts": {
            "CRITICAL": int(sev_counts.get("CRITICAL", 0)),
            "MAJOR": int(sev_counts.get("MAJOR", 0)),
            "MINOR": int(sev_counts.get("MINOR", 0)),
            "INFO": int(sev_counts.get("INFO", 0)),
        },
        "voice_metrics": {
            "speaking_rate_wpm": round(wpm, 1),
            "max_boundary_rms_jump_db": round(max_jump_db, 2),
            "high_drama_segment_ratio": round(high_drama_segs / float(max(1, len(manifest.narration_segments))), 3),
        },
        "soundscape_metrics": {
            "adaptive_audio_profile": audio_rep.get("adaptive_audio_profile", "auto"),
            "music_sections_count": music_plan.get("music_sections_count", 0),
            "audible_ambience_sections_count": ambience_plan.get("audible_ambience_sections_count", 0),
            "approved_sfx_count": len(applied_sfx),
            "rejected_sfx_for_silence_count": sfx_plan.get("rejected_for_silence_count", 0),
            "voice_to_bed_margin_lu": margin_lu,
        },
        "editing_metrics": {
            "final_scene_count": len(timed_shots),
            "mean_scene_duration_s": round(total_dur / float(max(1, len(timed_shots))), 2),
            "sync_issues_count": timeline_rep.get("sync_issues_count", 0),
        },
        "issues": issues,
    }

    if target_dir.exists():
        (target_dir / "creative_qa_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        _write_creative_qa_markdown(target_dir / "creative_qa_report.md", report)
    return report


def _write_creative_qa_markdown(path: Path, report: dict[str, Any]) -> None:
    sc = report["severity_counts"]
    sm = report["soundscape_metrics"]
    vm = report["voice_metrics"]
    em = report["editing_metrics"]
    sp = report.get("six_pillar_qa", {})
    vc = sp.get("visual_coverage_metrics", {})
    lines = [
        f"# Studio v8 Creative & 6-Pillar Quality Control Report — `{report['slug']}`",
        "",
        f"- **Creative QA Verdict:** `{'PASS' if report['creative_qa_pass'] else 'FAIL'}` "
        f"(CRITICAL=`{sc['CRITICAL']}`, MAJOR=`{sc['MAJOR']}`, MINOR=`{sc['MINOR']}`, INFO=`{sc['INFO']}`)",
        f"- **6-Pillar Approval:** Technical=`{sp.get('technical_approval')}` | Creative=`{sp.get('creative_approval')}` | Release=`{sp.get('overall_release_approval')}`",
        f"- **5-Part Coverage:** Genuine Moving=`{vc.get('genuine_moving_footage_pct', 0)}%` | Meaningful Action=`{vc.get('meaningful_action_footage_pct', 0)}%` | Establishing=`{vc.get('establishing_footage_pct', 0)}%` | Static=`{vc.get('static_image_pct', 0)}%` | Sci-Viz=`{vc.get('scientific_visualization_pct', 0)}%`",
        f"- **Voice QA:** `{vm['speaking_rate_wpm']} WPM` | Max join jump `{vm['max_boundary_rms_jump_db']} dB` | High-drama ratio `{vm['high_drama_segment_ratio']*100:.0f}%`",
        f"- **Music & Effect QA:** Profile=`{sm['adaptive_audio_profile']}` | Music sections=`{sm['music_sections_count']}` | "
        f"Ambience sections=`{sm['audible_ambience_sections_count']}` | SFX=`{sm['approved_sfx_count']}` (rejected for silence=`{sm['rejected_sfx_for_silence_count']}`) | Voice margin=`{sm['voice_to_bed_margin_lu']} LU`",
        f"- **Editing & Sync QA:** `{em['final_scene_count']}` scenes (mean `{em['mean_scene_duration_s']}s`) | Sync issues=`{em['sync_issues_count']}`",
        "",
        "## Findings by Severity",
        "",
        "| Severity | Pillar | Code | Finding |",
        "|---|---|---|---|",
    ]
    for iss in report["issues"]:
        lines.append(f"| **{iss['severity']}** | `{iss['pillar']}` | `{iss['code']}` | {iss['message']} |")
    if not report["issues"]:
        lines.append("| **INFO** | `all` | `clean_pass` | Zero creative or synchronization defects detected. |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
