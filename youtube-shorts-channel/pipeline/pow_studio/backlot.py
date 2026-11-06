#!/usr/bin/env python3
"""
Studio v9 Storyboard Backlot Exporter & Cryptographic Approval Gate (`pow_studio.backlot`).

Bridges the Python documentary pipeline with the Next.js 16 `Studio Backlot` tab in `ytb-tools`:
  - `export_storyboard_board`: joins YAML shots × `word_timings` × `assets_register` ×
    `scene_optimization_report` × motion authenticity × `beat_matches` × `mechanism_overlays`,
    extracts `360x640` IN/MID/OUT filmstrip frames (`IN+0.12s`, `MID`, `OUT-0.12s`), and writes
    `<output_dir>/board/storyboard_board.json`.
  - `compute_storyboard_sha256`: canonical SHA-256 over editorial shot + overlay decisions
    (excluding thumbnail JPEGs/timestamps), invalidating stale approvals automatically on edit.
  - `verify_storyboard_approval`: blocks `--mode master` renders when `require_storyboard_approval`
    is enabled unless `storyboard_approval.json` matches the current `storyboard_sha256`
    (draft renders remain unblocked; `--skip-storyboard-gate` logs an explicit audit event).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps

from .events import emit_event, read_studio_events, read_studio_state, set_gate
from .media_classifier import compute_visual_coverage_metrics
from .mechanism_overlay import resolve_overlay_timings
from .schema import PROTECTED_COMPLETED_OUTPUT_DIRS, EpisodeManifest, ShotSpecModel, resolve_timed_shots

BOARD_DIRNAME = "board"
BOARD_JSON_NAME = "storyboard_board.json"
APPROVAL_JSON_NAME = "storyboard_approval.json"
FILMSTRIP_W = 360
FILMSTRIP_H = 640


def is_protected_completed_dir(path: str | Path) -> bool:
    p = Path(path).resolve()
    return p.name in PROTECTED_COMPLETED_OUTPUT_DIRS


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _read_json_if_exists(path: Path) -> Optional[dict[str, Any]]:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def compute_storyboard_sha256(
    manifest: EpisodeManifest,
    timed_shots: list[ShotSpecModel],
) -> str:
    """
    Compute canonical SHA-256 of editorial decisions (shots + mechanism overlays).
    Excludes derived thumbnails/timestamps so re-exporting unchanged YAML preserves the hash,
    while any shot timing, asset, crop, transition, or overlay change invalidates old approvals.
    """
    shots_payload = [
        {
            "sid": s.sid,
            "src_file": s.src_file,
            "secondary_src_file": s.secondary_src_file,
            "tertiary_src_file": s.tertiary_src_file,
            "src_in": round(float(s.src_in), 3),
            "start_s": round(float(s.start_s), 3),
            "end_s": round(float(s.end_s), 3),
            "kind": s.kind,
            "reframe_mode": s.reframe_mode,
            "cx0": round(float(s.cx0), 3),
            "cy0": round(float(s.cy0), 3),
            "cx1": round(float(s.cx1), 3),
            "cy1": round(float(s.cy1), 3),
            "z0": round(float(s.z0), 3),
            "z1": round(float(s.z1), 3),
            "crop_box": list(s.crop_box) if s.crop_box else None,
            "transition_in": s.transition_in,
            "transition_duration_s": round(float(s.transition_duration_s), 3),
        }
        for s in timed_shots
    ]
    overlays_payload = [
        {
            "overlay_id": ov.overlay_id,
            "template": ov.template,
            "anchor": ov.anchor.model_dump(),
            "hold_s": round(float(ov.hold_s), 3),
            "region": ov.region.model_dump(),
            "params": ov.params,
            "claim_ref": ov.claim_ref,
            "honesty_label": ov.honesty_label,
            "span_cut": bool(ov.span_cut),
        }
        for ov in (getattr(manifest, "mechanism_overlays", None) or [])
    ]
    canonical = json.dumps(
        {
            "slug": manifest.slug,
            "shots": shots_payload,
            "mechanism_overlays": overlays_payload,
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_raw_asset(src_file: str, manifest: EpisodeManifest) -> Optional[Path]:
    if not src_file:
        return None
    for d in manifest.all_asset_search_dirs():
        cand = d / src_file
        if cand.exists():
            return cand
    return None


def _crop_photo_9x16_thumb(src_path: Path, cx: float, cy: float, zoom: float, dst_jpg: Path) -> bool:
    try:
        with Image.open(src_path) as raw_im:
            im = ImageOps.exif_transpose(raw_im).convert("RGB")
        w, h = im.size
        target_aspect = FILMSTRIP_W / float(FILMSTRIP_H)
        if w / float(max(1, h)) > target_aspect:
            base_h = float(h)
            base_w = base_h * target_aspect
        else:
            base_w = float(w)
            base_h = base_w / target_aspect
        z = max(1.0, float(zoom))
        cw = max(16.0, base_w / z)
        ch = max(16.0, base_h / z)
        px = float(cx) * w
        py = float(cy) * h
        x0 = max(0.0, min(w - cw, px - 0.5 * cw))
        y0 = max(0.0, min(h - ch, py - 0.5 * ch))
        cropped = im.crop((int(round(x0)), int(round(y0)), int(round(x0 + cw)), int(round(y0 + ch))))
        resized = cropped.resize((FILMSTRIP_W, FILMSTRIP_H), Image.Resampling.LANCZOS)
        dst_jpg.parent.mkdir(parents=True, exist_ok=True)
        resized.save(dst_jpg, format="JPEG", quality=84)
        return True
    except Exception:
        return False


def _extract_video_9x16_thumb(video_path: Path, seek_s: float, dst_jpg: Path, already_vertical: bool) -> bool:
    dst_jpg.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"scale={FILMSTRIP_W}:{FILMSTRIP_H}"
        if already_vertical
        else f"scale={FILMSTRIP_W}:{FILMSTRIP_H}:force_original_aspect_ratio=increase,crop={FILMSTRIP_W}:{FILMSTRIP_H}"
    )
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, float(seek_s)):.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            "4",
            str(dst_jpg),
        ],
        capture_output=True,
    )
    return proc.returncode == 0 and dst_jpg.exists() and dst_jpg.stat().st_size > 256


def _extract_shot_filmstrip(
    shot: ShotSpecModel,
    manifest: EpisodeManifest,
    out_dir: Path,
    board_dir: Path,
    overlay_sources: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Optional[str]]:
    """
    Extract `<sid>_{in,mid,out}.jpg` (`360x640`) at `IN+0.12s`, `MID`, `OUT-0.12s`.
    Prefers rendered `<out_dir>/shots/<sid>.mp4` if available; falls back to raw source media
    so unrendered episodes still render full filmstrips on Studio Backlot.
    When rendered mechanism overlays (`overlays/*.mov`) overlap the timestamp, composites their
    alpha frame onto the 360x640 preview so reviewers see exact overlay placement before master render.
    """
    from .mechanism_overlay.renderer import extract_overlay_rgba_frame

    dur = max(0.25, float(shot.end_s - shot.start_s))
    offsets = {
        "in": min(dur * 0.45, 0.12),
        "mid": 0.5 * dur,
        "out": max(0.0, dur - min(dur * 0.45, 0.12)),
    }
    shot_mp4 = out_dir / "shots" / f"{shot.sid}.mp4"
    raw_src = _resolve_raw_asset(shot.src_file, manifest)
    is_photo = raw_src is not None and raw_src.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

    rel_paths: dict[str, Optional[str]] = {"in": None, "mid": None, "out": None}
    for key, rel_t in offsets.items():
        dst = board_dir / f"{shot.sid}_{key}.jpg"
        ok = False
        if shot_mp4.exists():
            ok = _extract_video_9x16_thumb(shot_mp4, rel_t, dst, already_vertical=True)
        elif raw_src is not None:
            if is_photo:
                u = rel_t / max(0.1, dur)
                cx = shot.cx0 + u * (shot.cx1 - shot.cx0)
                cy = shot.cy0 + u * (shot.cy1 - shot.cy0)
                zm = shot.z0 + u * (shot.z1 - shot.z0)
                ok = _crop_photo_9x16_thumb(raw_src, cx=cx, cy=cy, zoom=zm, dst_jpg=dst)
            else:
                ok = _extract_video_9x16_thumb(raw_src, float(shot.src_in) + rel_t, dst, already_vertical=False)
        if ok:
            abs_t = float(shot.start_s) + float(rel_t)
            if overlay_sources:
                for ov_src in overlay_sources:
                    ov_start = float(ov_src.get("start_s", 0.0))
                    ov_end = float(ov_src.get("end_s", 0.0))
                    mov_p = Path(str(ov_src.get("mov_path") or ""))
                    if ov_start <= abs_t <= ov_end and mov_p.is_file():
                        ov_rgba = extract_overlay_rgba_frame(mov_p, abs_t - ov_start)
                        if ov_rgba is not None:
                            with Image.open(dst) as base_im:
                                base_rgba = base_im.convert("RGBA")
                            ov_small = ov_rgba.resize((FILMSTRIP_W, FILMSTRIP_H), Image.Resampling.LANCZOS)
                            merged = Image.alpha_composite(base_rgba, ov_small).convert("RGB")
                            merged.save(dst, format="JPEG", quality=86)
            rel_paths[key] = f"{BOARD_DIRNAME}/{dst.name}"
    return rel_paths


def read_storyboard_approval(out_dir: Path) -> Optional[dict[str, Any]]:
    return _read_json_if_exists(out_dir / APPROVAL_JSON_NAME)


def inspect_storyboard_approval_status(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """Non-throwing inspection of storyboard approval lock vs current manifest SHA-256."""
    target_dir = Path(out_dir) if out_dir else Path(manifest.output_dir)
    style = manifest.resolve_style_profile()
    fps = int(style.output.fps)

    if wt is None:
        wt = _read_json_if_exists(target_dir / "word_timings.json")
    if wt is not None and wt.get("total_frames_30fps"):
        nframes = int(wt["total_frames_30fps"])
    else:
        nframes = max(30, int(round(float(manifest.shots[-1].end_s) * fps)))

    timed_shots = resolve_timed_shots(manifest, nframes, fps=fps)
    current_sha = compute_storyboard_sha256(manifest, timed_shots)
    approval = read_storyboard_approval(target_dir)
    required = bool(getattr(manifest, "require_storyboard_approval", False))

    if approval is None:
        return {
            "required": required,
            "status": "pending" if required else "not_required",
            "approved": False,
            "hash_matches": False,
            "current_storyboard_sha256": current_sha,
            "approved_storyboard_sha256": None,
            "decision": None,
            "approved_at": None,
            "notes": "",
            "shot_notes": {},
        }

    saved_sha = str(approval.get("storyboard_sha256") or "")
    decision = str(approval.get("decision") or "")
    hash_ok = bool(saved_sha and saved_sha == current_sha)
    is_approved = decision == "approved" and hash_ok

    if decision == "changes_requested":
        status = "changes_requested"
    elif decision == "approved" and not hash_ok:
        status = "stale_hash_mismatch"
    elif is_approved:
        status = "approved"
    else:
        status = "pending"

    return {
        "required": required,
        "status": status,
        "approved": is_approved,
        "hash_matches": hash_ok,
        "current_storyboard_sha256": current_sha,
        "approved_storyboard_sha256": saved_sha or None,
        "decision": decision or None,
        "approved_at": approval.get("approved_at"),
        "notes": str(approval.get("notes") or ""),
        "shot_notes": dict(approval.get("shotNotes") or approval.get("shot_notes") or {}),
    }


def write_storyboard_approval_decision(
    out_dir: Path,
    decision: str,
    storyboard_sha256: str,
    notes: str = "",
    shot_notes: Optional[dict[str, str]] = None,
    gate: str = "storyboard_approval",
    slug: Optional[str] = None,
) -> dict[str, Any]:
    """Write `storyboard_approval.json` and synchronize `studio_state.json` + `studio_events.jsonl`."""
    if is_protected_completed_dir(out_dir):
        raise RuntimeError(f"Refusing to modify protected completed output directory: {out_dir}")
    if decision not in ("approved", "changes_requested"):
        raise ValueError(f"Invalid storyboard decision '{decision}'. Expected 'approved' or 'changes_requested'.")

    clean_shot_notes = {
        str(k).strip(): str(v).strip()
        for k, v in (shot_notes or {}).items()
        if str(k).strip() and str(v).strip()
    }
    payload = {
        "gate": gate,
        "decision": decision,
        "storyboard_sha256": storyboard_sha256,
        "notes": notes.strip(),
        "shotNotes": clean_shot_notes,
        "approved_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    _atomic_write_json(out_dir / APPROVAL_JSON_NAME, payload)

    gate_status = "passed" if decision == "approved" else "changes_requested"
    detail = f"{decision} (sha256={storyboard_sha256[:12]})"
    if notes.strip():
        detail += f" — {notes.strip()[:120]}"
    set_gate(out_dir, "storyboard_approval", gate_status, detail=detail)
    return payload


def verify_storyboard_approval(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    skip_gate: bool = False,
) -> dict[str, Any]:
    """
    Enforce Studio v9 Storyboard Approval Gate before `--mode master` render when
    `manifest.require_storyboard_approval` is True.
    """
    info = inspect_storyboard_approval_status(manifest, wt=wt)
    out_dir = Path(manifest.output_dir)

    if not info["required"]:
        return {**info, "blocking": False, "skipped": False}

    if info["approved"]:
        set_gate(
            out_dir,
            "storyboard_approval",
            "passed",
            detail=f"Verified sha256={info['current_storyboard_sha256'][:12]}",
        )
        return {**info, "blocking": False, "skipped": False}

    if skip_gate:
        emit_event(
            out_dir,
            "gate:storyboard_approval",
            "override",
            "skipped",
            detail=f"Emergency --skip-storyboard-gate used (status={info['status']}, sha={info['current_storyboard_sha256'][:12]})",
            slug=manifest.slug,
        )
        return {**info, "blocking": False, "skipped": True}

    reason_map = {
        "pending": "storyboard has not been approved yet (`storyboard_approval.json` missing)",
        "changes_requested": f"reviewer requested changes ({info['notes'] or 'see shotNotes in storyboard_approval.json'})",
        "stale_hash_mismatch": (
            f"storyboard changed since last approval "
            f"(approved={str(info['approved_storyboard_sha256'])[:12]} vs current={info['current_storyboard_sha256'][:12]})"
        ),
    }
    reason = reason_map.get(info["status"], f"status={info['status']}")
    set_gate(out_dir, "storyboard_approval", "blocked", detail=reason)
    raise RuntimeError(
        f"Storyboard Approval Gate blocked master render for '{manifest.slug}': {reason}. "
        f"Run `export-storyboard -m <manifest>` and approve in ytb-tools Studio Backlot (or pass `--skip-storyboard-gate` in emergencies)."
    )


def export_storyboard_board(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    extract_frames: bool = True,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Build `<output_dir>/board/storyboard_board.json` + `board/<sid>_{in,mid,out}.jpg` (`360x640`)
    for the Next.js `Studio Backlot` review & approval workspace.
    """
    target_dir = Path(out_dir) if out_dir else Path(manifest.output_dir)
    if is_protected_completed_dir(target_dir):
        raise RuntimeError(f"Refusing to write board into protected completed directory: {target_dir}")

    style = manifest.resolve_style_profile()
    fps = int(style.output.fps)
    board_dir = target_dir / BOARD_DIRNAME
    board_dir.mkdir(parents=True, exist_ok=True)

    if wt is None:
        wt = _read_json_if_exists(target_dir / "word_timings.json")
    has_real_voice = wt is not None and bool(wt.get("words"))
    if wt is None:
        from .creative_qa import _synthetic_wt_from_manifest

        wt = _synthetic_wt_from_manifest(manifest, fps=fps)

    nframes = int(wt.get("total_frames_30fps") or max(30, round(float(wt["total_duration_s"]) * fps)))
    total_dur = float(wt.get("total_duration_s") or (nframes / float(fps)))
    timed_shots = resolve_timed_shots(manifest, nframes, fps=fps)
    storyboard_sha = compute_storyboard_sha256(manifest, timed_shots)

    # Join supporting artifacts if present
    assets_by_file = {a.local_file: a for a in manifest.assets_register}
    scene_opt = _read_json_if_exists(target_dir / "scene_optimization_report.json") or {}
    opt_by_sid = {
        str(d.get("sid")): d for d in (scene_opt.get("decisions") or scene_opt.get("scene_decisions") or []) if isinstance(d, dict)
    }

    beat_matches = (
        _read_json_if_exists(target_dir / "planning" / "beat_matches.json")
        or _read_json_if_exists(target_dir / "beat_matches.json")
        or {}
    )
    beats_by_seg: dict[str, list[dict[str, Any]]] = {}
    for b in beat_matches.get("beats") or []:
        if isinstance(b, dict) and b.get("seg_id"):
            beats_by_seg.setdefault(str(b["seg_id"]), []).append(b)

    coverage = compute_visual_coverage_metrics(
        timed_shots=timed_shots,
        assets_register=manifest.assets_register,
        manifest=manifest,
        probe_pixels=False,
    )
    cls_by_sid = {str(c["sid"]): c for c in coverage.get("shot_classifications", [])}

    ov_timings = resolve_overlay_timings(manifest, wt, timed_shots=timed_shots, fps=fps)
    ov_qa = _read_json_if_exists(target_dir / "mechanism_overlay_qa.json") or {}
    ov_qa_by_id = {str(o.get("overlay_id")): o for o in (ov_qa.get("overlays") or []) if isinstance(o, dict)}

    six_pillar = _read_json_if_exists(target_dir / "six_pillar_qa_report.json") or {}
    qa_issues_by_sid: dict[str, list[dict[str, Any]]] = {}
    for iss in six_pillar.get("issues") or []:
        if isinstance(iss, dict) and iss.get("sid"):
            qa_issues_by_sid.setdefault(str(iss["sid"]), []).append(iss)

    approval_info = inspect_storyboard_approval_status(manifest, wt=wt, out_dir=target_dir)
    shot_notes_map = approval_info.get("shot_notes") or {}

    words = list(wt.get("words") or [])
    segs_by_id = {s.seg_id: s for s in manifest.narration_segments}

    shot_cards: list[dict[str, Any]] = []
    for idx, sh in enumerate(timed_shots):
        dur = round(float(sh.end_s - sh.start_s), 3)
        spoken = " ".join(
            str(w.get("word") or "")
            for w in words
            if sh.start_s - 0.04 <= 0.5 * (float(w.get("start") or 0.0) + float(w.get("end") or 0.0)) < sh.end_s
        ).strip()
        if not spoken and sh.associated_seg_id and sh.associated_seg_id in segs_by_id:
            spoken = sh.associated_narration_concept or segs_by_id[sh.associated_seg_id].text

        asset = assets_by_file.get(sh.src_file)
        cls_info = cls_by_sid.get(sh.sid, {})
        opt_info = opt_by_sid.get(sh.sid, {})

        # Match CLIP score & mislabel flag if beat_matches exist for this segment/file
        clip_pct: Optional[float] = None
        possible_mislabel = False
        for bm in beats_by_seg.get(sh.associated_seg_id or "", []):
            sel = bm.get("selected_asset_eval") or {}
            if sel.get("local_file") == sh.src_file or bm.get("best_manifest_asset") == sh.src_file:
                if sel.get("visual_semantic_pct") is not None:
                    clip_pct = float(sel["visual_semantic_pct"])
                possible_mislabel = bool(sel.get("possible_mislabeled_asset") or bm.get("possible_mislabeled_asset"))
                break
            for hit in bm.get("corpus_top_windows") or []:
                if isinstance(hit, dict) and hit.get("local_file") == sh.src_file:
                    clip_pct = float(hit.get("hybrid_percentile") or hit.get("visual_percentile") or 0.0)
                    break

        active_overlays = []
        ov_sources_for_shot = []
        for rt in ov_timings:
            if rt.end_s > sh.start_s + 0.04 and rt.start_s < sh.end_s - 0.04:
                qa_ov = ov_qa_by_id.get(rt.overlay_id, {})
                mov_p_str = str(qa_ov.get("mov_path") or "")
                if not mov_p_str and (target_dir / "overlays").is_dir():
                    cands = sorted((target_dir / "overlays").glob(f"{rt.overlay_id}_*.mov"))
                    if cands:
                        mov_p_str = str(cands[0])
                if mov_p_str:
                    ov_sources_for_shot.append({"start_s": rt.start_s, "end_s": rt.end_s, "mov_path": mov_p_str})
                active_overlays.append(
                    {
                        "overlay_id": rt.overlay_id,
                        "template": rt.template,
                        "start_s": rt.start_s,
                        "end_s": rt.end_s,
                        "max_alpha_area_ratio": (qa_ov.get("alpha_metrics") or {}).get("max_alpha_area_ratio"),
                    }
                )

        frames = (
            _extract_shot_filmstrip(sh, manifest, target_dir, board_dir, overlay_sources=ov_sources_for_shot)
            if extract_frames
            else {
                k: (f"{BOARD_DIRNAME}/{sh.sid}_{k}.jpg" if (board_dir / f"{sh.sid}_{k}.jpg").exists() else None)
                for k in ("in", "mid", "out")
            }
        )

        shot_cards.append(
            {
                "index": idx + 1,
                "sid": sh.sid,
                "start_s": round(float(sh.start_s), 3),
                "end_s": round(float(sh.end_s), 3),
                "duration_s": dur,
                "kind": sh.kind,
                "src_file": sh.src_file,
                "src_in": round(float(sh.src_in), 3),
                "associated_seg_id": sh.associated_seg_id,
                "story_beat": sh.story_beat,
                "visual_desc": sh.visual_desc,
                "narration_text": spoken,
                "transition_in": "opening" if idx == 0 else sh.transition_in,
                "transition_duration_s": 0.0 if idx == 0 else round(float(sh.transition_duration_s), 2),
                "reframe": {
                    "mode": sh.reframe_mode,
                    "cx0": sh.cx0,
                    "cy0": sh.cy0,
                    "cx1": sh.cx1,
                    "cy1": sh.cy1,
                    "z0": sh.z0,
                    "z1": sh.z1,
                },
                "media_class": cls_info.get("effective_media_class", "UNKNOWN"),
                "source_media_class": cls_info.get("source_media_class", "UNKNOWN"),
                "counts_as_genuine_moving": bool(cls_info.get("counts_as_genuine_moving_footage", False)),
                "license": asset.license if asset else "Unregistered",
                "creator_agency": asset.creator_agency if asset else "",
                "source_page_url": asset.source_page_url if asset else "",
                "clip_percentile": round(clip_pct, 3) if clip_pct is not None else None,
                "possible_mislabeled_asset": possible_mislabel,
                "scene_editor_decision": opt_info.get("action") or opt_info.get("decision") or "Keep",
                "overlays": active_overlays,
                "qa_issues": qa_issues_by_sid.get(sh.sid, []),
                "reviewer_note": shot_notes_map.get(sh.sid, ""),
                "frames": frames,
            }
        )

    # Collect thumbnail concepts available on disk
    thumb_manifest = _read_json_if_exists(target_dir / "thumbnail_concepts_manifest.json") or {}
    thumb_concepts: list[dict[str, Any]] = []
    for c_item in thumb_manifest.get("concepts") or []:
        if not isinstance(c_item, dict):
            continue
        cid = str(c_item.get("concept_id") or "A")
        fname = f"thumbnail_concept_{cid}.jpg"
        if (target_dir / fname).exists():
            thumb_concepts.append(
                {
                    "concept_id": cid,
                    "file": fname,
                    "headline_text": c_item.get("headline_text", ""),
                    "kicker_text": c_item.get("kicker_text", ""),
                    "rationale": c_item.get("concept_rationale", ""),
                }
            )
    if not thumb_concepts:
        for cid, fname in (("A", "thumbnail.jpg"), ("B", "thumbnail_variant_b.jpg"), ("C", "thumbnail_variant_c.jpg")):
            if (target_dir / fname).exists():
                thumb_concepts.append({"concept_id": cid, "file": fname, "headline_text": "", "kicker_text": "", "rationale": ""})

    mp4_path = target_dir / f"{manifest.slug}.mp4"
    board_payload = {
        "board_version": "9.0",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "slug": manifest.slug,
        "playlist": manifest.playlist,
        "primary_title": manifest.primary_title,
        "alternative_title": manifest.alternative_title,
        "topic": manifest.topic or manifest.primary_title,
        "manifest_version": manifest.manifest_version,
        "style_profile": style.profile_name,
        "visual_corpus_mode": manifest.visual_corpus_mode,
        "require_storyboard_approval": bool(manifest.require_storyboard_approval),
        "storyboard_sha256": storyboard_sha,
        "has_locked_voice": (target_dir / "voice_approval_lock.json").exists(),
        "has_real_word_timings": has_real_voice,
        "has_rendered_mp4": mp4_path.exists(),
        "total_duration_s": round(total_dur, 3),
        "shot_count": len(shot_cards),
        "coverage_metrics": {
            "genuine_moving_footage_pct": coverage["genuine_moving_footage_pct"],
            "meaningful_action_footage_pct": coverage["meaningful_action_footage_pct"],
            "establishing_footage_pct": coverage["establishing_footage_pct"],
            "static_image_pct": coverage["static_image_pct"],
            "animated_still_pct": coverage["animated_still_pct"],
            "scientific_visualization_pct": coverage["scientific_visualization_pct"],
            "mechanism_overlay_pct": coverage.get("mechanism_overlay_pct", 0.0),
        },
        "qa_summary": {
            "six_pillar_present": bool(six_pillar),
            "technical_approval": six_pillar.get("technical_approval"),
            "creative_approval": six_pillar.get("creative_approval"),
            "overall_release_approval": six_pillar.get("overall_release_approval"),
            "issues_count": len(six_pillar.get("issues") or []),
            "issues": (six_pillar.get("issues") or [])[:25],
        },
        "approval": approval_info,
        "thumbnail_concepts": thumb_concepts,
        "shots": shot_cards,
        "studio_state": read_studio_state(target_dir),
        "recent_events": read_studio_events(target_dir, limit=50),
    }

    _atomic_write_json(board_dir / BOARD_JSON_NAME, board_payload)

    # Sync gate state if approval is required and became stale or pending
    if manifest.require_storyboard_approval and not approval_info["approved"]:
        set_gate(
            target_dir,
            "storyboard_approval",
            approval_info["status"],
            detail=f"Exported board sha256={storyboard_sha[:12]} ({len(shot_cards)} shots)",
        )

    return board_payload
