#!/usr/bin/env python3
"""
Part 11, Section 14: Versioned Documentary Production Manifest Exporter
(`pow_studio.manifest_v6` v6.0).

Exports `production_manifest_v6.json` recording all 14 required lineage, creative,
licensing, timing, rendering, and QA fields for reproducible documentary production
while preserving full compatibility with existing YAML manifests.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schema import EpisodeManifest, resolve_timed_shots
from .voice_studio import verify_voice_approval_lock


def export_versioned_production_manifest(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    qc: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Build and save `production_manifest_v6.json` in `manifest.output_dir` recording all
    14 required fields from Part 11, Section 14.
    """
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fps = style.output.fps

    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)
    script_text = "\n\n".join(s.text for s in manifest.narration_segments)
    script_sha = hashlib.sha256(script_text.encode("utf-8")).hexdigest()

    # Load optional stage artifacts if present
    thumb_manifest_p = out_dir / "thumbnail_concepts_manifest.json"
    thumb_data = (
        json.loads(thumb_manifest_p.read_text(encoding="utf-8"))
        if thumb_manifest_p.exists()
        else {
            "concepts": [
                {
                    "concept_id": "A",
                    "path": str(out_dir / "thumbnail.jpg"),
                    "headline_text": manifest.thumbnail_spec.headline_text if manifest.thumbnail_spec else "",
                }
            ]
        }
    )

    bench_p = out_dir / "render_benchmarks.json"
    bench_data = json.loads(bench_p.read_text(encoding="utf-8")) if bench_p.exists() else {}

    audio_rep_p = out_dir / "audio_engineering_report.json"
    audio_rep = json.loads(audio_rep_p.read_text(encoding="utf-8")) if audio_rep_p.exists() else {}

    srt_p = out_dir / "subtitles.srt"
    srt_cue_count = len(srt_p.read_text(encoding="utf-8").strip().split("\n\n")) if srt_p.exists() and srt_p.stat().st_size > 0 else 0

    voice_lock = verify_voice_approval_lock(manifest)

    payload = {
        "schema_name": "proof_of_wonder_production_manifest",
        "manifest_version": manifest.manifest_version or "6.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "slug": manifest.slug,
        "channel_name": manifest.channel_name,
        "category_playlist": manifest.playlist,
        # 1. Topic
        "topic": manifest.topic or manifest.primary_title,
        # 2. Production profile
        "production_profile": {
            "profile_name": style.profile_name,
            "profile_version": style.profile_version,
            "style_overrides": manifest.style_overrides,
            "visual_scoring_weights": style.asset_selection.scoring_weights.model_dump(),
        },
        # 3. Script version
        "script_version": {
            "version": manifest.script_version,
            "script_sha256": script_sha,
            "segment_count": len(manifest.narration_segments),
            "word_count": sum(len(s.text.split()) for s in manifest.narration_segments),
            "opening_hook_type": manifest.opening_hook_type,
            "layer2_pivot_seg_id": manifest.editorial_formula.layer2_pivot_seg_id,
            "scientific_caveat_seg_id": manifest.editorial_formula.scientific_caveat_seg_id,
            "factual_references": [r.model_dump() for r in manifest.factual_references],
        },
        # 4. Voice direction profile
        "voice_direction_profile": {
            "voice_input_mode": manifest.voice_input_mode,
            "profile_id": manifest.voice_direction_profile or style.sound_design.default_voice_profile,
            "voice_identity": wt.get("voice", manifest.voice),
            "annotated_voice_script_file": manifest.annotated_voice_script_file,
            "approval_lock": voice_lock,
        },
        # 5. Audio source and final narration
        "audio_source_and_final_narration": {
            "voice_input_mode": manifest.voice_input_mode,
            "uploaded_narration_file": manifest.uploaded_narration_file,
            "voice_reference_file": manifest.voice_reference_file,
            "voice_owner_consent": manifest.voice_owner_consent,
            "narration_mp3": str(out_dir / "narration.mp3"),
            "final_audio_mix_mp3": str(out_dir / "final_audio_mix.mp3"),
            "word_timings_json": str(out_dir / "word_timings.json"),
            "total_duration_s": wt.get("total_duration_s"),
            "total_frames_30fps": wt.get("total_frames_30fps"),
            "five_layer_stems": audio_rep.get("stems", {}),
            "audio_diagnostics": audio_rep.get("diagnostics", wt.get("audio_diagnostics", {})),
        },
        # 6. Source assets
        "source_assets": [
            {
                "local_file": a.local_file,
                "media_type": a.media_type,
                "priority_tier": a.priority_tier,
                "title": a.title,
                "creator_agency": a.creator_agency,
                "source_page_url": a.source_page_url,
                "direct_media_url": a.direct_media_url,
                "is_first_party_original": a.is_first_party_original,
            }
            for a in manifest.assets_register
        ],
        # 7. Licensing metadata
        "licensing_metadata": {
            "strict_zero_cost_budget": True,
            "source_register_csv": str(out_dir / "source_register.csv"),
            "source_register_md": str(out_dir / "source_register.md"),
            "excluded_sources_notes": manifest.excluded_sources_notes,
            "licenses": [
                {
                    "local_file": a.local_file,
                    "license": a.license,
                    "license_url": a.license_url,
                    "required_attribution": a.required_attribution,
                }
                for a in manifest.assets_register
            ],
        },
        # 8. Shot list
        "shot_list": [
            {
                "sid": s.sid,
                "kind": s.kind,
                "src_file": s.src_file,
                "camera_perspective": s.camera_perspective,
                "visual_complexity": s.visual_complexity,
                "spoken_importance": s.spoken_importance,
                "camera_movement": s.camera_movement,
                "reframe_mode": s.reframe_mode,
                "transition_in": s.transition_in,
                "transition_duration_s": s.transition_duration_s,
                "scene_audio_layers": list(s.scene_audio_layers),
                "is_real_evidence": s.is_real_evidence,
                "has_human_interaction": s.has_human_interaction,
                "story_beat": s.story_beat,
                "editorial_rationale": s.editorial_rationale or s.associated_narration_concept,
            }
            for s in manifest.shots
        ],
        # 9. Scene timing
        "scene_timing": {
            "fps": fps,
            "semantic_timeline_manifest_json": str(out_dir / "semantic_timeline_manifest.json"),
            "timed_scenes": [
                {
                    "sid": ts.sid,
                    "start_s": ts.start_s,
                    "end_s": ts.end_s,
                    "duration_s": round(ts.end_s - ts.start_s, 4),
                    "start_frame": int(round(ts.start_s * fps)),
                    "end_frame": int(round(ts.end_s * fps)),
                }
                for ts in timed_shots
            ],
        },
        # 10. Subtitle version
        "subtitle_version": {
            "version": manifest.subtitle_version,
            "style": style.subtitles.style,
            "emphasis_mode": style.subtitles.emphasis_mode,
            "word_by_word_animation": style.subtitles.word_by_word_animation,
            "cue_count": srt_cue_count,
            "srt_path": str(srt_p),
        },
        # 11. Thumbnail variants
        "thumbnail_variants": {
            "primary_thumbnail_jpg": str(out_dir / "thumbnail.jpg"),
            "mobile_preview_sheet_jpg": str(out_dir / "thumbnail_small_preview_sheet.jpg"),
            "concepts_comparison_sheet_jpg": str(out_dir / "thumbnail_concepts_comparison_sheet.jpg"),
            "concepts": thumb_data.get("concepts", []),
        },
        # 12. Rendering configuration
        "rendering_configuration": {
            "output_spec": style.output.model_dump(),
            "color_science": style.color_science.model_dump(),
            "benchmarks": bench_data,
        },
        # 13. QA results
        "qa_results": {
            "qc_measurements_json": str(out_dir / "qc_measurements.json"),
            "qc_report_md": str(out_dir / "qc_report.md"),
            "summary": (
                {
                    "overall_pass": qc.get("overall_studio_v6_pass", True),
                    "failed_gates_count": qc.get("failed_gates_count", 0),
                    "moving_footage_pct": qc.get("visual_evidence_breakdown", {}).get("moving_footage_pct"),
                    "whisper_normalized_match_ratio": qc.get("subtitles_qc", {}).get("normalized_word_match_ratio"),
                    "integrated_lufs": qc.get("loudness", {}).get("integrated_LUFS"),
                    "true_peak_dbtp": qc.get("loudness", {}).get("true_peak_dBTP"),
                    "protected_projects_intact": qc.get("protected_projects_qc", {}).get("all_intact"),
                }
                if qc
                else None
            ),
        },
        # 14. Final output locations
        "studio_v7_intelligence": {
            "adaptive_audio_profile": audio_rep.get("adaptive_audio_profile", wt.get("adaptive_audio_profile", "auto")),
            "music_plan_json": str(out_dir / "music_plan.json"),
            "ambience_plan_json": str(out_dir / "ambience_plan.json"),
            "sfx_plan_json": str(out_dir / "sfx_plan.json"),
            "scene_optimization_report_json": str(out_dir / "scene_optimization_report.json"),
            "unified_av_timeline_json": str(out_dir / "unified_av_timeline.json"),
            "creative_qa_report_json": str(out_dir / "creative_qa_report.json"),
            "scene_optimization_counts": audio_rep.get("scene_optimization_counts", wt.get("scene_optimization_counts", {})),
            "music_sections_count": audio_rep.get("music_sections_count", wt.get("music_sections_count", 0)),
            "ambience_sections_count": audio_rep.get("ambience_sections_count", wt.get("ambience_sections_count", 0)),
            "approved_sfx_count": audio_rep.get("approved_sfx_count", len(wt.get("sfx_applied", []))),
            "creative_qa_pass": (qc or {}).get("creative_qa", {}).get("creative_qa_pass", True),
        },
        "final_output_locations": {
            "output_dir": str(out_dir.resolve()),
            "master_mp4": str((out_dir / f"{manifest.slug}.mp4").resolve()),
            "primary_thumbnail_jpg": str((out_dir / "thumbnail.jpg").resolve()),
            "subtitles_srt": str(srt_p.resolve()),
            "script_md": str((out_dir / "script.md").resolve()),
            "retention_plan_md": str((out_dir / "retention_plan.md").resolve()),
            "storyboard_manifest_md": str((out_dir / "storyboard_and_shot_manifest.md").resolve()),
            "youtube_metadata_md": str((out_dir / "youtube_metadata.md").resolve()),
            "qc_report_md": str((out_dir / "qc_report.md").resolve()),
        },
    }

    manifest_out = out_dir / "production_manifest_v6.json"
    manifest_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "production_manifest_v7.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
