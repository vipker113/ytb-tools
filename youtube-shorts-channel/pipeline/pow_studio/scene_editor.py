#!/usr/bin/env python3
"""
Part 6 (Section 9): Intelligent Scene Selection & Redundant Scene Removal Engine
(`pow_studio.scene_editor` v7.0).

Evaluates every candidate scene against the finalized narration (`word_timings.json`)
and actual available source media, answering all 6 Section 9 editorial questions:
  1. Which exact narration segment it supports (`supported_seg_id`).
  2. What information it communicates (`communicated_information`).
  3. Why this visual is necessary (`why_necessary`).
  4. Whether it introduces something new (`introduces_new_information`).
  5. Whether another scene already communicates the same idea (`duplicate_of_sid`).
  6. How long the viewer needs to understand it (`comprehension_duration_s`).

Applies one of four explicit editorial decisions to every candidate shot:
  - `Keep`: Directly supports a necessary story beat with novel visual evidence.
  - `Merge`: Combines consecutive shots that show essentially the same subject/idea.
  - `Replace`: Swaps a repeated or weak asset for a stronger registered asset when needed.
  - `Remove`: Eliminates filler, decorative, or redundant micro-cuts while preserving
    contiguous narrative clarity, clip-duration bounds, and `0.000ms` frame lock.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from .deduplication import resolve_canonical_source_id
from .schema import AssetLicenseSpec, EpisodeManifest, ShotSpecModel
from .style_profile import DocumentaryStyleProfile

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "over", "under",
    "beneath", "inside", "their", "there", "where", "when", "what", "which", "while",
    "have", "has", "had", "were", "was", "are", "been", "being", "than", "then",
    "only", "more", "most", "some", "such", "very", "just", "even", "still", "also",
    "shot", "view", "wide", "close", "medium", "full", "video", "photo", "image",
    "showing", "shows", "scene", "footage",
}


def _subject_tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) >= 3 and w not in _STOPWORDS
    }


def _probe_video_duration_s(manifest: EpisodeManifest, filename: str, cache: dict[str, float]) -> float:
    if filename in cache:
        return cache[filename]
    resolved: Optional[Path] = None
    for d in manifest.all_asset_search_dirs():
        cand = d / filename
        if cand.exists():
            resolved = cand
            break
    if resolved is None:
        direct = Path(filename)
        if direct.exists():
            resolved = direct
    if resolved is None or resolved.suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".ogv"):
        cache[filename] = 9999.0
        return 9999.0
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(resolved)],
        capture_output=True,
        text=True,
    )
    dur = 9999.0
    if proc.returncode == 0:
        try:
            dur = float((json.loads(proc.stdout).get("format") or {}).get("duration", 9999.0) or 9999.0)
        except Exception:
            dur = 9999.0
    cache[filename] = dur
    return dur


def _media_kind(shot: ShotSpecModel, reg: dict[str, AssetLicenseSpec]) -> str:
    a = reg.get(shot.src_file)
    if not shot.is_real_evidence or shot.kind == "diagram" or (a and a.media_type == "diagram"):
        return "diagram"
    if shot.kind in ("video_full", "triptych_hook", "svs_flyover", "microscopy_dual") or (a and a.media_type == "video"):
        return "video"
    return "photo"


def _can_shot_hold_duration(
    shot: ShotSpecModel,
    new_dur_s: float,
    manifest: EpisodeManifest,
    style: DocumentaryStyleProfile,
    reg: dict[str, AssetLicenseSpec],
    vid_dur_cache: dict[str, float],
) -> tuple[bool, float]:
    """
    Check if `shot` can cleanly hold `new_dur_s` without running past source video duration
    or violating still-photo hold limits. Returns `(ok, adjusted_src_in)`.
    """
    if new_dur_s > style.pacing.max_shot_duration_s + 1.5:
        return (False, shot.src_in)
    mk = _media_kind(shot, reg)
    if mk == "photo":
        if getattr(shot, "essential_historical_or_scientific_evidence", False) and style.asset_selection.allow_extended_still_for_essential_evidence:
            return (new_dur_s <= max(10.0, style.asset_selection.max_single_still_duration_s * 1.8), shot.src_in)
        limit = style.asset_selection.max_single_still_duration_s
        return (new_dur_s <= limit, shot.src_in)
    if mk == "video":
        vdur = _probe_video_duration_s(manifest, shot.src_file, vid_dur_cache)
        if shot.src_in + new_dur_s <= vdur + 0.15:
            return (True, shot.src_in)
        if vdur >= new_dur_s - 0.05:
            return (True, round(max(0.0, vdur - new_dur_s - 0.05), 3))
        return (False, shot.src_in)
    return (True, shot.src_in)


def _compute_wt_fingerprint(wt: dict[str, Any], shots: list[ShotSpecModel]) -> str:
    payload = {
        "total_frames_30fps": wt.get("total_frames_30fps"),
        "words_count": len(wt.get("words", [])),
        "shots": [(s.sid, s.src_file, s.start_s, s.end_s, s.story_beat) for s in shots],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _extract_pause_boundaries_local(wt: dict[str, Any]) -> list[float]:
    total_d = round(float(wt.get("total_duration_s", 0.0) or 0.0), 3)
    pts = {0.0, total_d}
    seg_ends = {round(float(s["end"]), 3) for s in wt.get("segments", [])}
    words = wt.get("words", [])
    for idx, w in enumerate(words):
        t_end = float(w["end"])
        nxt_start = float(words[idx + 1]["start"]) if idx + 1 < len(words) else total_d
        gap = max(0.0, nxt_start - t_end)
        txt = str(w.get("word", "")).strip()
        is_seg_end = any(abs(t_end - se) < 0.05 for se in seg_ends) or (idx == len(words) - 1)
        is_sent_end = txt.endswith((".", "?", "!"))
        is_clause_end = txt.endswith((",", ";", ":", "—")) or ("—" in txt)
        if is_seg_end or is_sent_end or is_clause_end or gap >= 0.16:
            mid = round(t_end + 0.5 * min(gap, 0.45), 3) if idx + 1 < len(words) else total_d
            pts.add(mid)
    return sorted(pts)


def _estimate_comprehension_duration_s(
    shot: ShotSpecModel,
    spoken_word_count: int,
    quant_fact_count: int,
    is_video: bool,
    style: DocumentaryStyleProfile,
) -> float:
    base = 2.6 if is_video else 2.8
    if shot.visual_complexity == "high":
        base += 1.1
    elif shot.visual_complexity == "medium":
        base += 0.45
    if shot.spoken_importance == "central_reveal":
        base += 1.0
    elif shot.spoken_importance == "key_fact":
        base += 0.45
    base += min(1.4, 0.35 * quant_fact_count)
    speech_dur = max(1.8, spoken_word_count / 2.65)
    est = 0.55 * base + 0.45 * speech_dur
    return round(max(style.pacing.min_shot_duration_s, min(style.pacing.max_shot_duration_s, est)), 2)


def optimize_episode_scenes(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    fps: int = 30,
    persist_report: bool = True,
) -> dict[str, Any]:
    """
    Evaluate all candidate scenes in `manifest.shots` against `wt`, executing
    `Keep`, `Replace`, `Merge`, and `Remove` decisions and snapping surviving
    scenes to speech boundaries and exact `1/fps` frame boundaries.
    """
    style = manifest.resolve_style_profile()
    total_frames = int(wt.get("total_frames_30fps", 0) or 0)
    total_dur = round(total_frames / float(fps), 4) if total_frames > 0 else float(wt.get("total_duration_s", 0.0) or 0.0)
    reg = {a.local_file: a for a in manifest.assets_register}
    vid_dur_cache: dict[str, float] = {}

    # Proportional initial mapping to actual narration duration
    raw_shots = [s.model_copy(deep=True) for s in manifest.shots]
    t_manifest = max(1e-6, raw_shots[-1].end_s)
    for k, s in enumerate(raw_shots):
        s.start_s = round((s.start_s / t_manifest) * total_dur, 4) if k > 0 else 0.0
        s.end_s = round((s.end_s / t_manifest) * total_dur, 4) if k < len(raw_shots) - 1 else total_dur

    if manifest.legacy_v6_fallback or not manifest.enable_intelligent_scene_editing or not style.pacing.enable_intelligent_scene_editing:
        snapped = _snap_shots_to_frames(raw_shots, total_frames, fps)
        return {
            "slug": manifest.slug,
            "intelligent_editing_active": False,
            "fingerprint": _compute_wt_fingerprint(wt, manifest.shots),
            "original_scene_count": len(raw_shots),
            "final_scene_count": len(snapped),
            "counts": {"Keep": len(snapped), "Merge": 0, "Replace": 0, "Remove": 0},
            "decisions": [],
            "optimized_shots": [s.model_dump() for s in snapped],
        }

    segs = wt.get("segments", [])
    words = wt.get("words", [])
    pause_pts = _extract_pause_boundaries_local(wt)

    decisions: list[dict[str, Any]] = []
    working: list[ShotSpecModel] = []
    seen_ideas: list[tuple[str, str, set[str]]] = []  # (sid, src_file, subject_tokens)
    used_photo_files: Counter[str] = Counter()
    used_asset_counts: Counter[str] = Counter()

    idx = 0
    while idx < len(raw_shots):
        cand = raw_shots[idx]
        dur = round(cand.end_s - cand.start_s, 3)
        t_mid = 0.5 * (cand.start_s + cand.end_s)

        # 1. Identify supported narration segment & spoken text
        best_seg = None
        if cand.associated_seg_id:
            best_seg = next((sg for sg in segs if sg["seg_id"] == cand.associated_seg_id), None)
        if best_seg is None and segs:
            best_seg = min(
                segs,
                key=lambda sg: 0.0
                if float(sg["start"]) <= t_mid <= float(sg["end"])
                else min(abs(t_mid - float(sg["start"])), abs(t_mid - float(sg["end"]))),
            )
        seg_id = str((best_seg or {}).get("seg_id", cand.associated_seg_id or "S_UNK"))
        shot_words = [
            w["word"] for w in words if cand.start_s - 0.04 <= 0.5 * (float(w["start"]) + float(w["end"])) < cand.end_s
        ]
        spoken_txt = " ".join(shot_words).strip() or str((best_seg or {}).get("text", ""))
        quant_cnt = len(re.findall(r"\d+", spoken_txt))
        mk = _media_kind(cand, reg)
        comp_dur = _estimate_comprehension_duration_s(cand, len(shot_words), quant_cnt, mk == "video", style)

        vis_tokens = _subject_tokens(f"{cand.visual_desc} {cand.story_beat} {cand.associated_narration_concept}")
        narr_tokens = _subject_tokens(spoken_txt)
        is_explicit_filler = bool(
            re.search(
                r"\b(?:decorative|filler|b-roll filler|generic establishing|padding|unused repeat)\b",
                f"{cand.story_beat} {cand.editorial_rationale} {cand.visual_desc}",
                re.I,
            )
        )

        # Check duplicate idea against previous surviving shot or earlier shots (using canonical source ID!)
        duplicate_of_sid: Optional[str] = None
        prev_shot = working[-1] if working else None
        prev_tokens = seen_ideas[-1][2] if seen_ideas else set()
        cand_canon = resolve_canonical_source_id(reg.get(cand.src_file), cand.src_file)
        prev_canon = resolve_canonical_source_id(reg.get(prev_shot.src_file), prev_shot.src_file) if prev_shot is not None else ""
        is_intentional_cb = bool(getattr(cand, "intentional_callback", False) and getattr(cand, "callback_purpose", ""))
        consec_same_asset = prev_shot is not None and (prev_shot.src_file == cand.src_file or prev_canon == cand_canon) and not is_intentional_cb
        consec_jacc = (
            len(vis_tokens & prev_tokens) / float(max(1, len(vis_tokens | prev_tokens)))
            if (prev_shot is not None and vis_tokens and prev_tokens)
            else 0.0
        )
        if consec_same_asset or (consec_jacc >= 0.62 and not is_intentional_cb):
            duplicate_of_sid = prev_shot.sid if prev_shot else None
        elif not is_intentional_cb:
            for old_sid, old_file, old_toks in seen_ideas[:-1]:
                old_canon = resolve_canonical_source_id(reg.get(old_file), old_file)
                jacc = len(vis_tokens & old_toks) / float(max(1, len(vis_tokens | old_toks))) if (vis_tokens and old_toks) else 0.0
                if (old_canon == cand_canon and mk == "photo") or (old_canon == cand_canon and jacc >= 0.65):
                    duplicate_of_sid = old_sid
                    break

        has_protected_overlay = bool(cand.chapter_stamp or cand.context_note or cand.scale_annotation or cand.locator_annotation)
        is_essential_opening = idx == 0

        # ---- Decision A: MERGE with previous shot if consecutive duplicate subject/asset ----
        if (
            not is_essential_opening
            and prev_shot is not None
            and not has_protected_overlay
            and (consec_same_asset or (consec_jacc >= 0.62 and prev_shot.associated_seg_id == cand.associated_seg_id))
        ):
            combined_dur = round(cand.end_s - prev_shot.start_s, 4)
            can_hold, new_src_in = _can_shot_hold_duration(prev_shot, combined_dur, manifest, style, reg, vid_dur_cache)
            if can_hold:
                prev_shot.end_s = cand.end_s
                prev_shot.src_in = new_src_in
                decisions.append(
                    {
                        "sid": cand.sid,
                        "decision": "Merge",
                        "merged_into_sid": prev_shot.sid,
                        "supported_seg_id": seg_id,
                        "communicated_information": cand.story_beat,
                        "why_necessary": f"Same visual idea already carried by {prev_shot.sid} ('{prev_shot.src_file}')",
                        "introduces_new_information": False,
                        "duplicate_of_sid": prev_shot.sid,
                        "comprehension_duration_s": comp_dur,
                        "reason": (
                            f"Merged consecutive duplicate-subject shot {cand.sid} into {prev_shot.sid} "
                            f"(new hold {combined_dur:.2f}s) to eliminate an unnecessary cut."
                        ),
                    }
                )
                idx += 1
                continue

        # ---- Decision B: REMOVE decorative/filler/over-rapid redundant shot ----
        too_brief_redundant = (
            not is_essential_opening
            and dur < style.pacing.min_shot_duration_s * 0.82
            and cand.spoken_importance == "context"
            and not has_protected_overlay
        )
        should_try_remove = (
            not is_essential_opening
            and not has_protected_overlay
            and (is_explicit_filler or too_brief_redundant or (duplicate_of_sid is not None and cand.spoken_importance == "context" and len(vis_tokens & narr_tokens) == 0))
        )
        if should_try_remove and prev_shot is not None:
            # Verify removing `cand` won't create consecutive static photos (`prev` photo + `next` photo)
            next_shot = raw_shots[idx + 1] if (idx + 1) < len(raw_shots) else None
            prev_mk = _media_kind(prev_shot, reg)
            next_mk = _media_kind(next_shot, reg) if next_shot else "none"
            would_collide_photos = (
                style.asset_selection.forbid_consecutive_still_shots
                and prev_mk == "photo"
                and next_mk == "photo"
            )
            combined_dur = round(cand.end_s - prev_shot.start_s, 4)
            can_hold, new_src_in = _can_shot_hold_duration(prev_shot, combined_dur, manifest, style, reg, vid_dur_cache)
            if can_hold and not would_collide_photos:
                prev_shot.end_s = cand.end_s
                prev_shot.src_in = new_src_in
                decisions.append(
                    {
                        "sid": cand.sid,
                        "decision": "Remove",
                        "absorbed_by_sid": prev_shot.sid,
                        "supported_seg_id": seg_id,
                        "communicated_information": cand.story_beat,
                        "why_necessary": "Not necessary — decorative/filler or over-rapid cut adding zero new evidence",
                        "introduces_new_information": False,
                        "duplicate_of_sid": duplicate_of_sid,
                        "comprehension_duration_s": comp_dur,
                        "reason": (
                            f"Removed unnecessary shot {cand.sid} ('{cand.src_file}', {dur:.2f}s) and extended "
                            f"{prev_shot.sid} to {combined_dur:.2f}s so the viewer can absorb the visual cleanly."
                        ),
                    }
                )
                idx += 1
                continue
            if next_shot is not None and not would_collide_photos:
                next_combined_dur = round(next_shot.end_s - cand.start_s, 4)
                can_hold_next, next_src_in = _can_shot_hold_duration(
                    next_shot, next_combined_dur, manifest, style, reg, vid_dur_cache
                )
                if can_hold_next:
                    next_shot.start_s = cand.start_s
                    next_shot.src_in = next_src_in
                    decisions.append(
                        {
                            "sid": cand.sid,
                            "decision": "Remove",
                            "absorbed_by_sid": next_shot.sid,
                            "supported_seg_id": seg_id,
                            "communicated_information": cand.story_beat,
                            "why_necessary": "Not necessary — decorative/filler or over-rapid cut adding zero new evidence",
                            "introduces_new_information": False,
                            "duplicate_of_sid": duplicate_of_sid,
                            "comprehension_duration_s": comp_dur,
                            "reason": (
                                f"Removed unnecessary shot {cand.sid} ('{cand.src_file}', {dur:.2f}s) and pulled "
                                f"{next_shot.sid} earlier ({next_combined_dur:.2f}s hold) to preserve clean continuity."
                            ),
                        }
                    )
                    idx += 1
                    continue

        # ---- Decision C: REPLACE weak or repeated still asset when a better registered asset exists ----
        repeated_still = mk == "photo" and used_photo_files[cand.src_file] >= 1 and style.asset_selection.forbid_repeated_same_image_zoom
        weak_irrelevant_asset = (
            len(vis_tokens & narr_tokens) == 0
            and bool(re.search(r"\b(?:weak|unrelated|placeholder)\b", f"{cand.editorial_rationale} {cand.visual_desc}", re.I))
        )
        if repeated_still or weak_irrelevant_asset:
            next_cand = raw_shots[idx + 1] if (idx + 1) < len(raw_shots) else None
            replacement_asset = _find_replacement_asset(
                cand=cand,
                dur=dur,
                narr_tokens=narr_tokens,
                manifest=manifest,
                style=style,
                reg=reg,
                used_photo_files=used_photo_files,
                used_asset_counts=used_asset_counts,
                prev_shot=prev_shot,
                next_shot=next_cand,
                vid_dur_cache=vid_dur_cache,
            )
            if replacement_asset is not None:
                old_file = cand.src_file
                cand.src_file = replacement_asset.local_file
                cand.src_in = 0.0
                cand.kind = "video_full" if replacement_asset.media_type == "video" else "still_full"
                cand.visual_desc = replacement_asset.title
                mk = _media_kind(cand, reg)
                used_asset_counts[cand.src_file] += 1
                if mk == "photo":
                    used_photo_files[cand.src_file] += 1
                working.append(cand)
                seen_ideas.append((cand.sid, cand.src_file, _subject_tokens(f"{cand.visual_desc} {cand.story_beat}")))
                decisions.append(
                    {
                        "sid": cand.sid,
                        "decision": "Replace",
                        "replaced_asset": old_file,
                        "new_asset": cand.src_file,
                        "supported_seg_id": seg_id,
                        "communicated_information": cand.story_beat,
                        "why_necessary": f"Story beat ({seg_id}) is essential, but '{old_file}' was repeated/weak",
                        "introduces_new_information": True,
                        "duplicate_of_sid": duplicate_of_sid,
                        "comprehension_duration_s": comp_dur,
                        "reason": f"Replaced '{old_file}' with stronger registered evidence '{cand.src_file}'.",
                    }
                )
                idx += 1
                continue

        # ---- Decision D: KEEP purposeful story-supporting shot ----
        cand.associated_seg_id = cand.associated_seg_id or seg_id
        used_asset_counts[cand.src_file] += 1
        if mk == "photo":
            used_photo_files[cand.src_file] += 1
        working.append(cand)
        seen_ideas.append((cand.sid, cand.src_file, vis_tokens))
        decisions.append(
            {
                "sid": cand.sid,
                "decision": "Keep",
                "supported_seg_id": seg_id,
                "communicated_information": cand.story_beat,
                "why_necessary": cand.editorial_rationale or f"Provides authentic visual evidence for {seg_id}",
                "introduces_new_information": duplicate_of_sid is None,
                "duplicate_of_sid": duplicate_of_sid,
                "comprehension_duration_s": comp_dur,
                "reason": f"Kept purposeful {mk} shot '{cand.src_file}' ({dur:.2f}s) supporting {seg_id}.",
            }
        )
        idx += 1

    # Restrain excessive transitions (no back-to-back dissolves; honor max_dissolve_fraction_of_cuts)
    _restrain_excessive_transitions(working, style)

    # Gently snap internal cuts to natural speech pauses when safe for both neighbors
    _snap_internal_cuts_to_speech_pauses(working, pause_pts, segs, words, manifest, style, reg, vid_dur_cache)

    # Snap to exact 1/fps frame integers matching total_frames (`0.000ms` drift)
    final_shots = _snap_shots_to_frames(working, total_frames, fps)

    counts = Counter(d["decision"] for d in decisions)
    report = {
        "slug": manifest.slug,
        "intelligent_editing_active": True,
        "fingerprint": _compute_wt_fingerprint(wt, manifest.shots),
        "narration_duration_s": round(total_dur, 3),
        "original_scene_count": len(raw_shots),
        "final_scene_count": len(final_shots),
        "counts": {
            "Keep": int(counts.get("Keep", 0)),
            "Merge": int(counts.get("Merge", 0)),
            "Replace": int(counts.get("Replace", 0)),
            "Remove": int(counts.get("Remove", 0)),
        },
        "decisions": decisions,
        "optimized_shots": [s.model_dump() for s in final_shots],
    }

    out_dir = Path(manifest.output_dir)
    if persist_report and out_dir.exists():
        (out_dir / "scene_optimization_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        _write_scene_optimization_markdown(out_dir / "scene_optimization_report.md", report)
    return report


def _find_replacement_asset(
    cand: ShotSpecModel,
    dur: float,
    narr_tokens: set[str],
    manifest: EpisodeManifest,
    style: DocumentaryStyleProfile,
    reg: dict[str, AssetLicenseSpec],
    used_photo_files: Counter[str],
    used_asset_counts: Counter[str],
    prev_shot: Optional[ShotSpecModel],
    next_shot: Optional[ShotSpecModel],
    vid_dur_cache: dict[str, float],
) -> Optional[AssetLicenseSpec]:
    prev_mk = _media_kind(prev_shot, reg) if prev_shot else "none"
    next_mk = _media_kind(next_shot, reg) if next_shot else "none"
    neighbor_files = {
        s.src_file for s in (prev_shot, next_shot) if s is not None
    }
    best: Optional[AssetLicenseSpec] = None
    best_score = -1.0
    for asset in manifest.assets_register:
        if asset.local_file == cand.src_file or asset.media_type == "audio":
            continue
        if asset.local_file in neighbor_files:
            continue
        if asset.media_type == "photo" and used_photo_files[asset.local_file] > 0:
            continue
        if asset.media_type == "photo" and (prev_mk == "photo" or next_mk == "photo") and style.asset_selection.forbid_consecutive_still_shots:
            continue
        if used_asset_counts[asset.local_file] >= style.asset_selection.max_uses_per_asset:
            continue
        if asset.media_type == "video":
            vdur = _probe_video_duration_s(manifest, asset.local_file, vid_dur_cache)
            if vdur < dur - 0.05:
                continue
        if asset.media_type == "photo" and dur > style.asset_selection.max_single_still_duration_s:
            continue
        atoks = _subject_tokens(f"{asset.title} {asset.intended_use}")
        overlap = len(atoks & narr_tokens)
        unused_bonus = 2.5 if used_asset_counts[asset.local_file] == 0 else 0.0
        score = overlap * 3.0 + unused_bonus + (1.5 if asset.media_type == "video" else 1.0) - used_asset_counts[asset.local_file]
        if score > best_score:
            best_score = score
            best = asset
    return best


def _restrain_excessive_transitions(shots: list[ShotSpecModel], style: DocumentaryStyleProfile) -> None:
    if len(shots) <= 1:
        return
    shots[0].transition_in = "cut"
    shots[0].transition_duration_s = 0.0
    max_dissolves = int(round(style.pacing.max_dissolve_fraction_of_cuts * max(1, len(shots) - 1)))
    dissolve_indices = [i for i in range(1, len(shots)) if shots[i].transition_in == "dissolve"]

    # Never allow back-to-back dissolves
    prev_was_dissolve = False
    kept = 0
    for i in range(1, len(shots)):
        if shots[i].transition_in == "dissolve":
            if prev_was_dissolve or kept >= max_dissolves:
                shots[i].transition_in = "cut"
                shots[i].transition_duration_s = 0.0
                shots[i].transition_reason = "Converted decorative/excessive dissolve to clean documentary cut"
                prev_was_dissolve = False
            else:
                kept += 1
                prev_was_dissolve = True
        else:
            prev_was_dissolve = False


def _snap_internal_cuts_to_speech_pauses(
    shots: list[ShotSpecModel],
    pause_pts: list[float],
    segs: list[dict[str, Any]],
    words: list[dict[str, Any]],
    manifest: EpisodeManifest,
    style: DocumentaryStyleProfile,
    reg: dict[str, AssetLicenseSpec],
    vid_dur_cache: dict[str, float],
) -> None:
    if len(shots) <= 1 or not pause_pts:
        return
    seg_by_id = {str(sg.get("seg_id", "")): sg for sg in segs}
    max_seg_nudge = max(2.85, 0.048 * float(shots[-1].end_s))
    for i in range(1, len(shots)):
        prev_s = shots[i - 1]
        cur_s = shots[i]
        t_cut = cur_s.start_s

        target_p: Optional[float] = None
        if prev_s.associated_seg_id and cur_s.associated_seg_id and prev_s.associated_seg_id != cur_s.associated_seg_id:
            sg_prev = seg_by_id.get(prev_s.associated_seg_id)
            sg_cur = seg_by_id.get(cur_s.associated_seg_id)
            if sg_prev and sg_cur:
                t_end = float(sg_prev["end"])
                gap = max(0.0, float(sg_cur["start"]) - t_end)
                seg_mid = round(t_end + 0.5 * min(gap, 0.45), 3)
                if abs(seg_mid - t_cut) <= max_seg_nudge:
                    target_p = seg_mid

        if target_p is None:
            slices_word = any(float(w["start"]) + 0.06 < t_cut < float(w["end"]) - 0.06 for w in words)
            nearest_p = min(pause_pts, key=lambda p: abs(p - t_cut))
            dist = abs(nearest_p - t_cut)
            max_nudge = 2.45 if (slices_word or dist > style.pacing.speech_pause_snap_tolerance_s) else style.pacing.speech_pause_snap_tolerance_s
            if dist <= 0.02 or dist > max_nudge:
                continue
            target_p = nearest_p

        new_prev_dur = target_p - prev_s.start_s
        new_cur_dur = cur_s.end_s - target_p
        if new_prev_dur < style.pacing.min_shot_duration_s * 0.85 or new_cur_dur < style.pacing.min_shot_duration_s * 0.85:
            continue
        ok_prev, prev_in = _can_shot_hold_duration(prev_s, new_prev_dur, manifest, style, reg, vid_dur_cache)
        ok_cur, cur_in = _can_shot_hold_duration(cur_s, new_cur_dur, manifest, style, reg, vid_dur_cache)
        if ok_prev and ok_cur:
            prev_s.end_s = round(target_p, 4)
            prev_s.src_in = prev_in
            cur_s.start_s = round(target_p, 4)
            cur_s.src_in = cur_in


def _snap_shots_to_frames(shots: list[ShotSpecModel], total_frames: int, fps: int = 30) -> list[ShotSpecModel]:
    out = [s.model_copy(deep=True) for s in shots]
    n = len(out)
    if n == 0 or total_frames <= n:
        return out
    t_end = max(1e-6, out[-1].end_s)
    frame_bounds = [0]
    for k in range(1, n):
        scaled_f = int(round((out[k].start_s / t_end) * total_frames))
        lo = frame_bounds[-1] + 1
        hi = total_frames - (n - k)
        frame_bounds.append(max(lo, min(hi, scaled_f)))
    frame_bounds.append(total_frames)
    for k, s in enumerate(out):
        s.start_s = round(frame_bounds[k] / float(fps), 4)
        s.end_s = round(frame_bounds[k + 1] / float(fps), 4)
    return out


def _write_scene_optimization_markdown(path: Path, report: dict[str, Any]) -> None:
    c = report["counts"]
    lines = [
        f"# Intelligent Scene Selection & Redundancy Report — `{report['slug']}`",
        "",
        f"- **Original Candidate Scenes:** `{report['original_scene_count']}`",
        f"- **Final Timeline Scenes:** `{report['final_scene_count']}`",
        f"- **Decisions:** Keep=`{c['Keep']}`, Merge=`{c['Merge']}`, Replace=`{c['Replace']}`, Remove=`{c['Remove']}`",
        "",
        "| Scene ID | Decision | Seg ID | Comprehension Hold | Novel Info | Reason |",
        "|---|---|---|---:|---|---|",
    ]
    for d in report["decisions"]:
        lines.append(
            f"| `{d['sid']}` | **{d['decision']}** | `{d['supported_seg_id']}` | "
            f"{d['comprehension_duration_s']:.2f}s | `{'YES' if d['introduces_new_information'] else 'NO'}` | {d['reason']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_or_optimize_timed_shots(
    manifest: EpisodeManifest,
    total_frames_30fps: int,
    fps: int = 30,
) -> Optional[list[ShotSpecModel]]:
    """
    Used by `schema.resolve_timed_shots` so every downstream stage (`audio_engine`,
    `compositor`, `shot_planner`, `qc_suite`, `deliverables`) transparently consumes
    the exact optimized scene list whenever `word_timings.json` is present.
    """
    if manifest.legacy_v6_fallback or not manifest.enable_intelligent_scene_editing:
        return None
    out_dir = Path(manifest.output_dir)
    wt_p = out_dir / "word_timings.json"
    if not wt_p.exists():
        return None
    try:
        wt = json.loads(wt_p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if int(wt.get("total_frames_30fps", -1)) != int(total_frames_30fps):
        return None

    expected_fp = _compute_wt_fingerprint(wt, manifest.shots)
    rep_p = out_dir / "scene_optimization_report.json"
    if rep_p.exists():
        try:
            rep = json.loads(rep_p.read_text(encoding="utf-8"))
            if rep.get("fingerprint") == expected_fp and rep.get("optimized_shots"):
                return [ShotSpecModel.model_validate(x) for x in rep["optimized_shots"]]
        except Exception:
            pass

    from .schema import PROTECTED_COMPLETED_OUTPUT_DIRS

    can_persist = out_dir.name not in PROTECTED_COMPLETED_OUTPUT_DIRS or bool(getattr(manifest, "allow_overwrite_protected", False))
    rep = optimize_episode_scenes(manifest, wt, fps=fps, persist_report=can_persist)
    return [ShotSpecModel.model_validate(x) for x in rep["optimized_shots"]]
