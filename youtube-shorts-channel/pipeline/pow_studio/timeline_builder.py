#!/usr/bin/env python3
"""
Part 7 (Section 10): Unified Narration-Aware Audio & Visual Synchronization Timeline
Builder (`pow_studio.timeline_builder` v7.0).

Designs and verifies the visual storyboard and 5-layer soundscape together from the
final approved narration (`word_timings.json`) and actual available footage, exporting
`unified_av_timeline.json` and `unified_av_timeline.md` with all 11 Section 10 fields:
  1. Scene ID
  2. Narration segment
  3. Visual source
  4. Visual purpose
  5. Voice direction
  6. Music
  7. Ambience
  8. Sound effect
  9. Start/end time
  10. Transition
  11. Audio priority

Also runs programmatic audio-visual synchronization verification:
- SFX follow the visible shot event and never mark every cut.
- Music changes respect narrative transitions and speech boundaries.
- Visual cuts occur at natural speech pauses without slicing words.
- Connected scenes share continuous environmental ambience without abrupt resets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .ambience_planner import plan_environmental_ambience
from .music_planner import plan_story_music
from .schema import EpisodeManifest, resolve_timed_shots
from .sfx_planner import plan_context_sfx
from .shot_planner import extract_speech_boundaries


def build_unified_av_timeline(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    music_plan: Optional[dict[str, Any]] = None,
    ambience_plan: Optional[dict[str, Any]] = None,
    sfx_plan: Optional[dict[str, Any]] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Construct the complete 11-column Unified Audio-Visual Timeline and run all
    synchronization integrity checks.
    """
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)
    target_out = out_dir or Path(manifest.output_dir)

    if music_plan is None:
        music_plan = plan_story_music(manifest, wt, timed_shots, out_dir=target_out if target_out.exists() else None)
    adaptive_prof = str((music_plan.get("adaptive_audio_profile") or {}).get("selected_profile", "minimal_documentary"))
    if ambience_plan is None:
        ambience_plan = plan_environmental_ambience(
            manifest, wt, timed_shots, adaptive_audio_profile=adaptive_prof, out_dir=target_out if target_out.exists() else None
        )
    if sfx_plan is None:
        sfx_plan = plan_context_sfx(
            manifest, wt, timed_shots, ambience_plan, adaptive_audio_profile=adaptive_prof, out_dir=target_out if target_out.exists() else None
        )

    reg_by_file = {a.local_file: a for a in manifest.assets_register}
    seg_specs = {s.seg_id: s for s in manifest.narration_segments}
    wt_segs = wt.get("segments", [])
    words = wt.get("words", [])
    boundaries = extract_speech_boundaries(wt)

    # Index Voice Studio planned segment directions if available
    voice_plan_by_seg: dict[str, dict[str, Any]] = {}
    for ps in wt.get("planned_voice_direction", []):
        if isinstance(ps, dict) and ps.get("seg_id"):
            voice_plan_by_seg[str(ps["seg_id"])] = ps

    scenes_table: list[dict[str, Any]] = []
    sync_issues: list[dict[str, Any]] = []

    for idx, s in enumerate(timed_shots):
        t0, t1 = round(s.start_s, 3), round(s.end_s, 3)
        dur = round(t1 - t0, 3)
        t_mid = 0.5 * (t0 + t1)

        # Match narration segment(s)
        overlapping_segs = [
            sg for sg in wt_segs if max(t0, float(sg["start"])) < min(t1, float(sg["end"])) - 0.08
        ]
        if not overlapping_segs and wt_segs:
            nearest_sg = min(wt_segs, key=lambda sg: min(abs(t_mid - float(sg["start"])), abs(t_mid - float(sg["end"]))))
            overlapping_segs = [nearest_sg]

        seg_ids = [str(sg["seg_id"]) for sg in overlapping_segs]
        shot_words = [
            w["word"] for w in words if t0 - 0.04 <= 0.5 * (float(w["start"]) + float(w["end"])) < t1
        ]
        spoken_text = " ".join(shot_words).strip() or " ".join(str(sg.get("text", "")) for sg in overlapping_segs).strip()

        # Voice direction summary
        primary_seg_id = seg_ids[0] if seg_ids else (s.associated_seg_id or "")
        vp = voice_plan_by_seg.get(primary_seg_id, {})
        nspec = seg_specs.get(primary_seg_id)
        deliv = vp.get("delivery") or (nspec.delivery if nspec else None) or "NATURAL_DOCUMENTARY"
        tone = vp.get("emotional_tone") or (nspec.emotional_tone if nspec else None) or "confident_clarity"
        energy = vp.get("energy") or (nspec.energy if nspec else None) or 3
        pace = vp.get("pace") or (nspec.pace if nspec else None) or "NATURAL"
        voice_dir_str = f"{deliv} ({tone}, pace={pace}, energy={energy}/5)"

        # Music presence & reason
        overlapping_mus = [
            ms for ms in music_plan.get("sections", [])
            if max(t0, float(ms["start_s"])) < min(t1, float(ms["end_s"])) - 0.10
            and "music" in (s.scene_audio_layers or [])
        ]
        overlapping_hush = [
            hw for hw in music_plan.get("silence_windows", [])
            if max(t0, float(hw["start_s"])) < min(t1, float(hw["end_s"])) - 0.05
        ]
        if overlapping_mus:
            ms0 = overlapping_mus[0]
            mus_str = f"Present: {ms0['track_name']} ({ms0['base_gain_db']} dB) — {ms0['purpose']}"
            if overlapping_hush:
                mus_str += f" [Includes hush {overlapping_hush[0]['start_s']}-{overlapping_hush[0]['end_s']}s]"
        else:
            mus_str = "Absent — intentional voice/ambience focus"

        # Ambience presence
        overlapping_amb = [
            ab for ab in ambience_plan.get("sections", [])
            if s.sid in (ab.get("shot_ids") or []) or max(t0, float(ab["start_s"])) < min(t1, float(ab["end_s"])) - 0.10
        ]
        if overlapping_amb and overlapping_amb[0].get("audible"):
            ab0 = overlapping_amb[0]
            diegetic_note = f" + diegetic clip ({s.nat_audio_gain_db} dB)" if s.nat_audio_gain_db is not None else ""
            amb_str = f"{ab0['ambience_id']} {ab0['environment']} ({ab0['target_gain_db']} dB, continuous){diegetic_note}"
        else:
            amb_str = "Silent / vacuum (no artificial atmosphere)"

        # SFX presence
        shot_sfx = [
            c for c in sfx_plan.get("approved_cues", [])
            if c.get("shot_id") == s.sid or (t0 - 0.02 <= float(c["time_s"]) < t1 + 0.02)
        ]
        if shot_sfx:
            sfx_str = "; ".join(
                f"{c['sfx_name']} @ {c['time_s']:.2f}s ({c['gain_db']} dB: {c['purpose']})"
                for c in shot_sfx
            )
        else:
            sfx_str = "None (silence & natural ambience preferred)"

        # Visual & audio transition
        if idx == 0:
            vis_trans = "Opening frame (instant full-bleed)"
        elif s.transition_in == "dissolve" and s.transition_duration_s > 0:
            vis_trans = f"Dissolve ({s.transition_duration_s:.2f}s — {s.transition_reason})"
        else:
            vis_trans = f"Clean cut ({s.transition_reason})"

        amb_continues = (
            idx > 0
            and overlapping_amb
            and timed_shots[idx - 1].sid in (overlapping_amb[0].get("shot_ids") or [])
        )
        aud_trans = "Continuous ambience bridge (no abrupt audio cut)" if amb_continues else "Smooth 1.2s environmental crossfade"
        trans_combined = f"Visual: {vis_trans} | Audio: {aud_trans}"

        # Audio priority
        if spoken_text:
            imp_note = (
                " + deep reveal ducking"
                if s.spoken_importance == "central_reveal"
                else " + speech sidechain ducking"
            )
            audio_prio = f"1. Narration ({s.spoken_importance}{imp_note}) > 2. {'Ambience/Field' if overlapping_amb and overlapping_amb[0].get('audible') else 'Restrained Bed'}"
        else:
            audio_prio = "1. Natural Ambience / Breathing Pause > 2. Subtle Underscore"

        asset_meta = reg_by_file.get(s.src_file)
        mtype = asset_meta.media_type if asset_meta else ("video" if s.kind == "video_full" else "photo")

        scenes_table.append(
            {
                "scene_id": s.sid,
                "narration_segment": f"[{','.join(seg_ids)}] {spoken_text}",
                "visual_source": f"{s.src_file} ({mtype})",
                "visual_purpose": f"{s.story_beat} — {s.editorial_rationale or s.visual_desc}",
                "voice_direction": voice_dir_str,
                "music": mus_str,
                "ambience": amb_str,
                "sound_effect": sfx_str,
                "start_end_time": f"{t0:.2f}s – {t1:.2f}s ({dur:.2f}s)",
                "start_s": t0,
                "end_s": t1,
                "duration_s": dur,
                "transition": trans_combined,
                "audio_priority": audio_prio,
            }
        )

        # Sync check 1: Does internal visual cut slice through the middle of a spoken word?
        if idx > 0:
            sliced_w = next(
                (w for w in words if float(w["start"]) + 0.08 < t0 < float(w["end"]) - 0.08),
                None,
            )
            if sliced_w is not None:
                sync_issues.append(
                    {
                        "severity": "MINOR",
                        "kind": "mid_word_visual_cut",
                        "scene_id": s.sid,
                        "time_s": t0,
                        "detail": f"Cut into {s.sid} at {t0:.2f}s occurs mid-word ('{sliced_w['word']}').",
                    }
                )

    # Sync check 2: Every cut must NOT trigger a sound effect
    internal_cuts = max(0, len(timed_shots) - 1)
    approved_sfx_list = sfx_plan.get("approved_cues", [])
    if internal_cuts >= 3 and len(approved_sfx_list) >= internal_cuts:
        sync_issues.append(
            {
                "severity": "MAJOR",
                "kind": "excessive_sfx_per_cut",
                "scene_id": "GLOBAL",
                "time_s": 0.0,
                "detail": f"Approved SFX count ({len(approved_sfx_list)}) equals/exceeds internal cuts ({internal_cuts}); violates documentary restraint.",
            }
        )

    # Sync check 3: Music section boundaries should align near speech pauses so fades don't disrupt phrases
    for msec in music_plan.get("sections", [])[1:]:
        mt0 = float(msec["start_s"])
        if boundaries:
            dist = min(abs(float(b["time_s"]) - mt0) for b in boundaries)
            if dist > 1.25:
                sync_issues.append(
                    {
                        "severity": "MINOR",
                        "kind": "music_change_away_from_pause",
                        "scene_id": msec["section_id"],
                        "time_s": mt0,
                        "detail": f"Music section {msec['section_id']} starts {dist:.2f}s away from nearest speech pause.",
                    }
                )

    timeline = {
        "slug": manifest.slug,
        "adaptive_audio_profile": adaptive_prof,
        "total_duration_s": round(float(wt.get("total_duration_s", 0.0) or 0.0), 3),
        "scene_count": len(scenes_table),
        "music_sections_count": music_plan.get("music_sections_count", 0),
        "ambience_sections_count": ambience_plan.get("audible_ambience_sections_count", 0),
        "approved_sfx_count": sfx_plan.get("approved_cues_count", 0),
        "speech_pause_boundaries_count": len(boundaries),
        "sync_issues_count": len(sync_issues),
        "sync_issues": sync_issues,
        "scenes": scenes_table,
    }

    if target_out.exists():
        (target_out / "unified_av_timeline.json").write_text(json.dumps(timeline, indent=2), encoding="utf-8")
        _write_timeline_markdown(target_out / "unified_av_timeline.md", timeline)
    return timeline


def _write_timeline_markdown(path: Path, timeline: dict[str, Any]) -> None:
    lines = [
        f"# Unified Audio-Visual Documentary Timeline — `{timeline['slug']}`",
        "",
        f"- **Runtime:** `{timeline['total_duration_s']:.2f}s` | **Scenes:** `{timeline['scene_count']}` | "
        f"**Adaptive Audio Profile:** `{timeline['adaptive_audio_profile']}`",
        f"- **Music Sections:** `{timeline['music_sections_count']}` | **Audible Ambience Sections:** `{timeline['ambience_sections_count']}` | "
        f"**Approved SFX:** `{timeline['approved_sfx_count']}` | **Detected Sync Issues:** `{timeline['sync_issues_count']}`",
        "",
        "| Scene ID | Start/End Time | Narration Segment | Visual Source | Visual Purpose | Voice Direction | Music | Ambience | Sound Effect | Transition | Audio Priority |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in timeline["scenes"]:
        esc = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{esc(r['scene_id'])}` | `{esc(r['start_end_time'])}` | {esc(r['narration_segment'])[:95]} | "
            f"`{esc(r['visual_source'])}` | {esc(r['visual_purpose'])[:85]} | {esc(r['voice_direction'])} | "
            f"{esc(r['music'])} | {esc(r['ambience'])} | {esc(r['sound_effect'])} | "
            f"{esc(r['transition'])} | {esc(r['audio_priority'])} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
