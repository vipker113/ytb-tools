#!/usr/bin/env python3
"""
Source-Lineage Deduplication, Perceptual Hashing (`dHash`/`pHash`) &
Meaningful Scene Progression Engine (`pow_studio.deduplication` v8.0).

Implements Part 5 (Sections 11 & 12) and Repetition/Timeline QA (Section 15):
1. Local `$0` Perceptual Similarity:
   - 64-bit Difference Hash (`compute_dhash_64`)
   - 64-bit 2D-DCT Perceptual Hash (`compute_phash_64`)
   - Spatial 4x4 RGB/Luma Composition Signature (`compute_composition_signature`)
2. Canonical Source Lineage (`resolve_canonical_source_id`):
   - Multiple crops (`crop_box`, `cx/cy/z`) of one photograph or sub-clips from one
     single archive page/shoot resolve to ONE canonical source ID and are NEVER counted
     as distinct assets.
3. 6-Mode Redundancy Detection:
   - Same clip reused without `intentional_callback`
   - Same photograph with different crops (`multi_crop_single_photo`)
   - Visually near-duplicate compositions (`near_duplicate_composition`)
   - Repeated establishing shots (`repeated_establishing_shot`)
   - Multiple shots communicating identical information (`identical_information_repeat`)
   - Single clip split into multiple scenes without meaningful change (`split_clip_no_progression`)
4. Meaningful Scene Progression & Stale-Visual-Across-Topic-Shifts Detection:
   - Verifies every consecutive shot introduces at least one of the 7 progression dimensions:
     `new_action`, `new_information`, `new_perspective`, `new_subject`, `new_evidence`,
     `new_process_stage`, or `environment_change`.
   - Flags shots that remain frozen/looping on screen while spoken narration shifts to
     new claims, locations, or topics.
"""

from __future__ import annotations

import io
import re
import subprocess
import urllib.parse
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from .media_classifier import STILL_EXTENSIONS, VIDEO_EXTENSIONS, classify_timeline_shot_media

PROGRESSION_DIMENSIONS = (
    "new_action",
    "new_information",
    "new_perspective",
    "new_subject",
    "new_evidence",
    "new_process_stage",
    "environment_change",
)

_STOP_WORDS = {
    "the", "and", "for", "with", "from", "into", "under", "over", "that", "this",
    "these", "those", "their", "there", "where", "when", "what", "which", "while",
    "have", "has", "had", "were", "was", "are", "been", "being", "than", "then",
    "only", "more", "most", "some", "such", "very", "just", "even", "still", "also",
    "shot", "view", "wide", "close", "medium", "full", "video", "photo", "image",
}


def _tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]{3,}", (text or "").lower())
        if w not in _STOP_WORDS
    }


@lru_cache(maxsize=1)
def _dct_matrix_32() -> np.ndarray:
    """Orthogonal 32x32 Type-II DCT matrix in pure NumPy."""
    n = 32
    k = np.arange(n, dtype=np.float64)[:, None]
    i = np.arange(n, dtype=np.float64)[None, :]
    mat = np.cos(np.pi * (2.0 * i + 1.0) * k / (2.0 * n))
    mat[0, :] *= np.sqrt(1.0 / n)
    mat[1:, :] *= np.sqrt(2.0 / n)
    return mat


def compute_dhash_64(img: Image.Image) -> int:
    """Compute 64-bit horizontal gradient difference hash (`9x8` grayscale)."""
    small = np.asarray(img.convert("L").resize((9, 8), Image.Resampling.BILINEAR), dtype=np.float32)
    diff = (small[:, 1:] > small[:, :-1]).reshape(-1)
    val = 0
    for bit in diff:
        val = (val << 1) | int(bool(bit))
    return val


def compute_phash_64(img: Image.Image) -> int:
    """Compute 64-bit 2D-DCT perceptual hash (`32x32` -> top-left `8x8` AC frequencies)."""
    small = np.asarray(img.convert("L").resize((32, 32), Image.Resampling.BILINEAR), dtype=np.float64)
    c = _dct_matrix_32()
    dct = c @ small @ c.T
    low = dct[:8, :8].copy()
    ac = low.reshape(-1)[1:]  # exclude DC term [0,0]
    med = float(np.median(ac))
    bits = (low.reshape(-1) > med)
    val = 0
    for bit in bits:
        val = (val << 1) | int(bool(bit))
    return val


def hamming_distance_64(h1: int, h2: int) -> int:
    """Bitwise Hamming distance between two 64-bit perceptual hashes."""
    return int((int(h1) ^ int(h2)).bit_count())


def compute_composition_signature(img: Image.Image) -> np.ndarray:
    """Normalized `6x6x3` spatial RGB composition vector for cosine similarity."""
    arr = np.asarray(img.convert("RGB").resize((6, 6), Image.Resampling.BILINEAR), dtype=np.float32) / 255.0
    vec = arr.reshape(-1)
    norm = float(np.linalg.norm(vec))
    return vec / max(1e-6, norm)


def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    return float(np.dot(v1, v2) / max(1e-6, float(np.linalg.norm(v1) * np.linalg.norm(v2))))


def extract_representative_frame(
    media_path: Path,
    src_in_s: float = 0.0,
    crop_box: Optional[tuple[int, int, int, int]] = None,
) -> Optional[Image.Image]:
    """Load an image or decode a representative video frame for perceptual hashing."""
    if not media_path.exists():
        return None
    suf = media_path.suffix.lower()
    im: Optional[Image.Image] = None
    if suf in STILL_EXTENSIONS:
        try:
            with Image.open(media_path) as raw_im:
                im = raw_im.convert("RGB")
        except Exception:
            return None
    elif suf in VIDEO_EXTENSIONS:
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, src_in_s + 0.35):.2f}",
                "-i",
                str(media_path),
                "-frames:v",
                "1",
                "-vf",
                "scale=320:-2",
                "-f",
                "image2pipe",
                "-vcodec",
                "png",
                "-",
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and proc.stdout:
            try:
                im = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
            except Exception:
                im = None
    if im is not None and crop_box and len(crop_box) == 4 and suf in STILL_EXTENSIONS:
        x0, y0, x1, y1 = crop_box
        x0 = max(0, min(im.width - 1, int(x0)))
        y0 = max(0, min(im.height - 1, int(y0)))
        x1 = max(x0 + 1, min(im.width, int(x1)))
        y1 = max(y0 + 1, min(im.height, int(y1)))
        im = im.crop((x0, y0, x1, y1))
    return im


def resolve_canonical_source_id(asset: Optional[Any], fallback_filename: str = "") -> str:
    """
    Compute a canonical source-lineage identifier so:
      1. Multiple crops of the same photograph resolve to 1 canonical asset.
      2. Multiple local sub-clips cut from the same archive URL (`source_page_url`)
         resolve to 1 canonical source shoot.
      3. A JPEG transcoded to MP4 (`original_media_file`) keeps its original source ID.
    """
    if asset is None:
        stem = re.sub(r"_(?:crop\d+|zoom\d+|part\d+|\d+p)$", "", Path(fallback_filename).stem.lower())
        return f"file:{stem}"

    explicit_id = str(getattr(asset, "canonical_source_id", "") or "").strip()
    if explicit_id:
        return explicit_id.lower()

    orig_file = str(getattr(asset, "original_media_file", "") or "").strip()
    if orig_file:
        return f"orig:{Path(orig_file).stem.lower()}"

    page_url = str(getattr(asset, "source_page_url", "") or "").strip()
    if page_url and not page_url.startswith("local://"):
        parsed = urllib.parse.urlparse(page_url)
        clean_path = parsed.path.rstrip("/").lower()
        # Distinguish specific Wikimedia Commons `File:...` pages vs generic agency homepages
        if clean_path and clean_path not in ("", "/", "/wiki", "/images", "/videos"):
            return f"url:{parsed.netloc.lower()}{clean_path}"

    direct_url = str(getattr(asset, "direct_media_url", "") or "").strip()
    if direct_url and not direct_url.startswith("local://"):
        parsed_d = urllib.parse.urlparse(direct_url)
        clean_d = parsed_d.path.rstrip("/").lower()
        if clean_d and clean_d not in ("", "/"):
            return f"media:{parsed_d.netloc.lower()}{clean_d}"

    local_f = str(getattr(asset, "local_file", "") or fallback_filename)
    stem = re.sub(r"_(?:crop\d+|zoom\d+|pan\d+|part\d+)$", "", Path(local_f).stem.lower())
    return f"file:{stem}"


def evaluate_consecutive_shot_progression(
    prev_shot: Any,
    curr_shot: Any,
    prev_cls_info: dict[str, Any],
    curr_cls_info: dict[str, Any],
    prev_canon_id: str,
    curr_canon_id: str,
) -> dict[str, Any]:
    """
    Verify that transitioning from `prev_shot` -> `curr_shot` introduces at least one
    meaningful progression dimension (Part 5 Section 12):
      - `new_action`, `new_information`, `new_perspective`, `new_subject`,
        `new_evidence`, `new_process_stage`, `environment_change`.
    """
    dims: list[str] = []
    explicit_prog = str(getattr(curr_shot, "progression_type", "") or "").strip()
    if explicit_prog in PROGRESSION_DIMENSIONS:
        dims.append(explicit_prog)

    prev_act = _tokens(f"{getattr(prev_shot, 'visible_action', '')} {getattr(prev_shot, 'story_beat', '')}")
    curr_act = _tokens(f"{getattr(curr_shot, 'visible_action', '')} {getattr(curr_shot, 'story_beat', '')}")
    if curr_act and (len(curr_act - prev_act) >= 2):
        dims.append("new_action")

    prev_info = _tokens(f"{getattr(prev_shot, 'associated_narration_concept', '')} {getattr(prev_shot, 'visual_objective', '')}")
    curr_info = _tokens(f"{getattr(curr_shot, 'associated_narration_concept', '')} {getattr(curr_shot, 'visual_objective', '')}")
    if (curr_info and len(curr_info - prev_info) >= 2) or (
        getattr(prev_shot, "associated_seg_id", None) != getattr(curr_shot, "associated_seg_id", None)
        and getattr(curr_shot, "associated_seg_id", None) is not None
    ):
        dims.append("new_information")

    prev_persp = str(getattr(prev_shot, "camera_perspective", "auto") or "auto")
    curr_persp = str(getattr(curr_shot, "camera_perspective", "auto") or "auto")
    if prev_persp != "auto" and curr_persp != "auto" and prev_persp != curr_persp:
        dims.append("new_perspective")

    prev_vis = _tokens(getattr(prev_shot, "visual_desc", ""))
    curr_vis = _tokens(getattr(curr_shot, "visual_desc", ""))
    vis_jacc = len(prev_vis & curr_vis) / float(max(1, len(prev_vis | curr_vis))) if (prev_vis or curr_vis) else 1.0
    if vis_jacc < 0.45 and prev_canon_id != curr_canon_id:
        dims.append("new_subject")

    if prev_canon_id != curr_canon_id and curr_cls_info.get("effective_media_class") != prev_cls_info.get("effective_media_class"):
        dims.append("new_evidence")

    # However, if both shots use the EXACT SAME canonical photo or same video window with only a crop tweak,
    # strip superficial claims of progression!
    is_same_still_recrop = (
        prev_canon_id == curr_canon_id
        and curr_cls_info.get("source_media_class") in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE")
    )
    is_unmotivated_clip_split = (
        prev_canon_id == curr_canon_id
        and prev_shot.src_file == curr_shot.src_file
        and curr_cls_info.get("source_media_class") in ("REAL_VIDEO_ACTION", "REAL_VIDEO_ESTABLISHING", "REAL_TIME_LAPSE")
        and abs(float(getattr(curr_shot, "src_in", 0.0)) - (float(getattr(prev_shot, "src_in", 0.0)) + (prev_shot.end_s - prev_shot.start_s))) < 2.2
        and prev_persp == curr_persp
    )
    if is_same_still_recrop or is_unmotivated_clip_split:
        dims = []

    dedup_dims = list(dict.fromkeys(dims))
    return {
        "from_sid": prev_shot.sid,
        "to_sid": curr_shot.sid,
        "meaningful_progression": len(dedup_dims) > 0,
        "progression_dimensions": dedup_dims,
        "is_same_still_recrop": is_same_still_recrop,
        "is_unmotivated_clip_split": is_unmotivated_clip_split,
    }


def detect_stale_visual_topic_drift(
    timed_shots: list[Any],
    wt: Optional[dict[str, Any]],
    narration_segments: Optional[list[Any]] = None,
) -> list[dict[str, Any]]:
    """
    Identify timeline periods where a single shot stays on screen while the narration
    introduces multiple distinct topics/ideas that the shot no longer depicts
    (Part 1 Section 1, Part 5 Section 12, Part 8 Section 15 Timeline QA).
    """
    if not wt or not wt.get("segments"):
        return []
    segs = wt.get("segments", [])
    seg_meta_by_id = {getattr(s, "seg_id", ""): s for s in (narration_segments or [])}
    findings: list[dict[str, Any]] = []

    for sh in timed_shots:
        dur = float(sh.end_s) - float(sh.start_s)
        is_static_kind = getattr(sh, "kind", "") in ("still_full", "still_parallax_25d", "diagram", "still_window")
        min_hold_s = 7.2 if is_static_kind else 9.0
        if dur < min_hold_s:
            continue
        overlapping_segs = [
            sg for sg in segs
            if min(float(sh.end_s), float(sg.get("end", 0.0))) - max(float(sh.start_s), float(sg.get("start", 0.0))) >= 2.2
        ]
        if len(overlapping_segs) < 2:
            continue

        seg_token_sets = [_tokens(str(sg.get("text", ""))) for sg in overlapping_segs]
        first_toks = seg_token_sets[0]
        last_toks = seg_token_sets[-1]
        jacc = len(first_toks & last_toks) / float(max(1, len(first_toks | last_toks)))
        shot_toks = _tokens(
            f"{getattr(sh, 'visual_desc', '')} {getattr(sh, 'story_beat', '')} {getattr(sh, 'visible_action', '')}"
        )
        late_overlap = len(shot_toks & last_toks)

        # Also check if narrative_beat shifted significantly (e.g. opening_hook -> escalation)
        s0_meta = seg_meta_by_id.get(str(overlapping_segs[0].get("seg_id", "")))
        s1_meta = seg_meta_by_id.get(str(overlapping_segs[-1].get("seg_id", "")))
        beat_shifted = (
            s0_meta is not None
            and s1_meta is not None
            and getattr(s0_meta, "narrative_beat", None) != getattr(s1_meta, "narrative_beat", None)
        )

        if (
            (len(overlapping_segs) >= 3 and late_overlap == 0)
            or (is_static_kind and jacc < 0.12 and late_overlap == 0)
            or (dur >= 9.0 and jacc < 0.08 and late_overlap == 0 and beat_shifted)
        ):
            findings.append(
                {
                    "sid": sh.sid,
                    "src_file": sh.src_file,
                    "duration_s": round(dur, 2),
                    "spanned_segments": [str(sg.get("seg_id", "")) for sg in overlapping_segs],
                    "topic_jaccard": round(jacc, 3),
                    "detail": (
                        f"Shot {sh.sid} ('{sh.src_file}', {dur:.1f}s) remains on screen across {len(overlapping_segs)} "
                        f"distinct narration segments ({', '.join(str(sg.get('seg_id')) for sg in overlapping_segs)}) "
                        "whose spoken subject shifts away from the visual."
                    ),
                }
            )
    return findings


def audit_visual_repetition_and_progression(
    manifest: Any,
    timed_shots: list[Any],
    wt: Optional[dict[str, Any]] = None,
    probe_pixels: bool = True,
) -> dict[str, Any]:
    """
    Comprehensive Repetition & Scene Progression Audit (Part 5 Sections 11 & 12):
      - Computes canonical source IDs (never counting multi-crops of 1 photo as distinct assets!)
      - Computes `dHash` + `pHash` + spatial color composition similarity when files exist on disk
      - Flags all 6 redundancy patterns while respecting explicit `intentional_callback` shots
      - Audits consecutive scene progression and stale-visual topic drift.
    """
    assets_by_name = {a.local_file: a for a in manifest.assets_register}
    search_dirs = manifest.all_asset_search_dirs() if hasattr(manifest, "all_asset_search_dirs") else []

    def _resolve_path(fname: str) -> Optional[Path]:
        for d in search_dirs:
            cand = d / fname
            if cand.exists():
                return cand
        direct = Path(fname)
        return direct if direct.exists() else None

    shot_records: list[dict[str, Any]] = []
    canonical_uses: Counter[str] = Counter()
    canonical_still_crops: dict[str, list[tuple[str, Any]]] = {}
    canonical_local_files: dict[str, set[str]] = {}
    establishing_seen: list[tuple[str, str, set[str]]] = []
    idea_seen: list[tuple[str, str, set[str], bool]] = []

    issues: list[dict[str, Any]] = []

    for idx, sh in enumerate(timed_shots):
        aspec = assets_by_name.get(sh.src_file)
        canon_id = resolve_canonical_source_id(aspec, sh.src_file)
        cls_info = classify_timeline_shot_media(sh, assets_by_name, manifest=manifest, probe_pixels=False)
        is_callback = bool(getattr(sh, "intentional_callback", False))
        callback_purpose = str(getattr(sh, "callback_purpose", "") or "")

        canonical_uses[canon_id] += 1
        canonical_local_files.setdefault(canon_id, set()).add(sh.src_file)

        dhash_val: Optional[int] = None
        phash_val: Optional[int] = None
        comp_sig: Optional[np.ndarray] = None
        full_img_dhash: Optional[int] = None

        if probe_pixels:
            rpath = _resolve_path(sh.src_file)
            if rpath is not None:
                # Hash the uncropped source image as well so multi-crops of identical photos downloaded under 2 names are caught!
                raw_frame = extract_representative_frame(rpath, src_in_s=float(getattr(sh, "src_in", 0.0)), crop_box=None)
                if raw_frame is not None:
                    full_img_dhash = compute_dhash_64(raw_frame)
                    view_frame = (
                        extract_representative_frame(rpath, src_in_s=float(getattr(sh, "src_in", 0.0)), crop_box=getattr(sh, "crop_box", None))
                        or raw_frame
                    )
                    dhash_val = compute_dhash_64(view_frame)
                    phash_val = compute_phash_64(view_frame)
                    comp_sig = compute_composition_signature(view_frame)

        crop_sig = (
            getattr(sh, "crop_box", None),
            round(float(getattr(sh, "cx0", 0.5)), 2),
            round(float(getattr(sh, "cy0", 0.5)), 2),
            round(float(getattr(sh, "z0", 1.0)), 2),
        )
        if cls_info["source_media_class"] in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"):
            canonical_still_crops.setdefault(canon_id, []).append((sh.sid, crop_sig))

        # 1. Multi-crop / repeated single photograph check
        if cls_info["source_media_class"] in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"):
            prev_uses = canonical_still_crops[canon_id][:-1]
            if prev_uses and not (is_callback and callback_purpose):
                prev_sid, prev_crop = prev_uses[-1]
                kind_code = "multi_crop_single_photo" if prev_crop != crop_sig else "repeated_photograph"
                issues.append(
                    {
                        "severity": "MAJOR",
                        "kind": kind_code,
                        "sid": sh.sid,
                        "reference_sid": prev_sid,
                        "canonical_source_id": canon_id,
                        "detail": (
                            f"Shot {sh.sid} reuses still source '{canon_id}' (first shown in {prev_sid}) "
                            + ("with a different artificial crop/zoom to simulate a new scene." if prev_crop != crop_sig else "without an intentional callback purpose.")
                        ),
                    }
                )

        # 2. Perceptual hash near-duplicate check against earlier shots (catches re-saved files & near-identical compositions)
        if dhash_val is not None and phash_val is not None:
            for prev_rec in shot_records:
                if prev_rec["dhash"] is None or prev_rec["phash"] is None:
                    continue
                if is_callback and callback_purpose:
                    continue
                # Check uncropped photo identity first (catches two separate filenames of the exact same photo!)
                if (
                    full_img_dhash is not None
                    and prev_rec["full_img_dhash"] is not None
                    and cls_info["source_media_class"] in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE")
                    and prev_rec["source_media_class"] in ("STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE")
                    and prev_rec["canonical_source_id"] != canon_id
                    and hamming_distance_64(full_img_dhash, prev_rec["full_img_dhash"]) <= 6
                ):
                    issues.append(
                        {
                            "severity": "MAJOR",
                            "kind": "duplicate_photo_different_filename",
                            "sid": sh.sid,
                            "reference_sid": prev_rec["sid"],
                            "canonical_source_id": canon_id,
                            "detail": (
                                f"Shot {sh.sid} ('{sh.src_file}') is perceptually identical to earlier photo "
                                f"{prev_rec['sid']} ('{prev_rec['src_file']}', dHash distance="
                                f"{hamming_distance_64(full_img_dhash, prev_rec['full_img_dhash'])})."
                            ),
                        }
                    )
                    break

                dh_dist = hamming_distance_64(dhash_val, prev_rec["dhash"])
                ph_dist = hamming_distance_64(phash_val, prev_rec["phash"])
                csim = cosine_similarity(comp_sig, prev_rec["comp_sig"]) if (comp_sig is not None and prev_rec["comp_sig"] is not None) else 0.0
                is_consecutive = prev_rec["index"] == idx - 1
                if (dh_dist <= 7 and ph_dist <= 8) or (is_consecutive and dh_dist <= 9 and ph_dist <= 10 and csim >= 0.975):
                    if prev_rec["canonical_source_id"] != canon_id or is_consecutive:
                        issues.append(
                            {
                                "severity": "MAJOR" if is_consecutive else "MINOR",
                                "kind": "near_duplicate_composition",
                                "sid": sh.sid,
                                "reference_sid": prev_rec["sid"],
                                "canonical_source_id": canon_id,
                                "detail": (
                                    f"Shot {sh.sid} has near-duplicate visual composition to {prev_rec['sid']} "
                                    f"(dHash={dh_dist}, pHash={ph_dist}, color_cos={csim:.3f})."
                                ),
                            }
                        )
                        break

        # 3. Repeated establishing shot check
        if cls_info["effective_media_class"] == "REAL_VIDEO_ESTABLISHING":
            est_toks = _tokens(f"{getattr(sh, 'visual_desc', '')} {getattr(sh, 'story_beat', '')}")
            for prev_est_sid, prev_est_canon, prev_est_toks in establishing_seen:
                est_jacc = len(est_toks & prev_est_toks) / float(max(1, len(est_toks | prev_est_toks))) if (est_toks and prev_est_toks) else 0.0
                if (prev_est_canon == canon_id or est_jacc >= 0.65) and not (is_callback and callback_purpose):
                    issues.append(
                        {
                            "severity": "MINOR",
                            "kind": "repeated_establishing_shot",
                            "sid": sh.sid,
                            "reference_sid": prev_est_sid,
                            "canonical_source_id": canon_id,
                            "detail": f"Shot {sh.sid} repeats establishing scenery already shown in {prev_est_sid}.",
                        }
                    )
                    break
            establishing_seen.append((sh.sid, canon_id, est_toks))

        # 4. Identical communicated information check
        idea_toks = _tokens(f"{getattr(sh, 'story_beat', '')} {getattr(sh, 'visual_objective', '')} {getattr(sh, 'associated_narration_concept', '')}")
        for prev_i_sid, prev_i_canon, prev_i_toks, _ in idea_seen:
            i_jacc = len(idea_toks & prev_i_toks) / float(max(1, len(idea_toks | prev_i_toks))) if (idea_toks and prev_i_toks) else 0.0
            if i_jacc >= 0.78 and prev_i_canon == canon_id and not (is_callback and callback_purpose):
                issues.append(
                    {
                        "severity": "MAJOR",
                        "kind": "identical_information_repeat",
                        "sid": sh.sid,
                        "reference_sid": prev_i_sid,
                        "canonical_source_id": canon_id,
                        "detail": f"Shot {sh.sid} communicates identical visual information to {prev_i_sid} using the same source.",
                    }
                )
                break
        idea_seen.append((sh.sid, canon_id, idea_toks, is_callback))

        shot_records.append(
            {
                "index": idx,
                "sid": sh.sid,
                "src_file": sh.src_file,
                "canonical_source_id": canon_id,
                "source_media_class": cls_info["source_media_class"],
                "effective_media_class": cls_info["effective_media_class"],
                "cls_info": cls_info,
                "dhash": dhash_val,
                "phash": phash_val,
                "full_img_dhash": full_img_dhash,
                "comp_sig": comp_sig,
                "intentional_callback": is_callback,
            }
        )

    # 5. Same-source shoot disguised across multiple local filenames (e.g. 4 files from 1 archive page)
    for canon_id, local_set in canonical_local_files.items():
        total_u = canonical_uses[canon_id]
        if len(local_set) > 1 and total_u >= 3:
            issues.append(
                {
                    "severity": "MAJOR",
                    "kind": "same_source_shoot_overuse",
                    "sid": "MULTIPLE",
                    "reference_sid": "",
                    "canonical_source_id": canon_id,
                    "detail": (
                        f"Canonical source '{canon_id}' is split across {len(local_set)} local files "
                        f"({', '.join(sorted(local_set))}) and used {total_u} times."
                    ),
                }
            )
        elif total_u >= 3:
            non_cb = [r["sid"] for r in shot_records if r["canonical_source_id"] == canon_id and not r["intentional_callback"]]
            if len(non_cb) >= 3:
                issues.append(
                    {
                        "severity": "MAJOR",
                        "kind": "excessive_clip_reuse",
                        "sid": non_cb[-1],
                        "reference_sid": non_cb[0],
                        "canonical_source_id": canon_id,
                        "detail": f"Canonical asset '{canon_id}' is reused {len(non_cb)} times ({', '.join(non_cb)}) without callback justification.",
                    }
                )

    # 6. Consecutive Scene Progression Audit (Section 12)
    progression_steps: list[dict[str, Any]] = []
    for i in range(1, len(timed_shots)):
        prog = evaluate_consecutive_shot_progression(
            timed_shots[i - 1],
            timed_shots[i],
            shot_records[i - 1]["cls_info"],
            shot_records[i]["cls_info"],
            shot_records[i - 1]["canonical_source_id"],
            shot_records[i]["canonical_source_id"],
        )
        progression_steps.append(prog)
        if prog["is_unmotivated_clip_split"]:
            issues.append(
                {
                    "severity": "MAJOR",
                    "kind": "split_clip_no_progression",
                    "sid": timed_shots[i].sid,
                    "reference_sid": timed_shots[i - 1].sid,
                    "canonical_source_id": shot_records[i]["canonical_source_id"],
                    "detail": (
                        f"Consecutive shots {timed_shots[i - 1].sid} -> {timed_shots[i].sid} split the same clip "
                        f"('{timed_shots[i].src_file}') without a meaningful change in action or perspective."
                    ),
                }
            )
        elif not prog["meaningful_progression"] and not shot_records[i]["intentional_callback"]:
            issues.append(
                {
                    "severity": "MINOR",
                    "kind": "weak_scene_progression",
                    "sid": timed_shots[i].sid,
                    "reference_sid": timed_shots[i - 1].sid,
                    "canonical_source_id": shot_records[i]["canonical_source_id"],
                    "detail": f"Transition {timed_shots[i - 1].sid} -> {timed_shots[i].sid} introduces no clear new action, information, perspective, or subject.",
                }
            )

    stale_topic_shifts = detect_stale_visual_topic_drift(
        timed_shots,
        wt,
        narration_segments=getattr(manifest, "narration_segments", None),
    )
    for st in stale_topic_shifts:
        issues.append(
            {
                "severity": "MAJOR",
                "kind": "stale_visual_across_topic_shift",
                "sid": st["sid"],
                "reference_sid": "",
                "canonical_source_id": "",
                "detail": st["detail"],
            }
        )

    raw_local_filenames_count = len({s.src_file for s in timed_shots})
    distinct_canonical_count = len(canonical_uses)
    major_count = sum(1 for x in issues if x["severity"] in ("CRITICAL", "MAJOR"))

    return {
        "total_shots": len(timed_shots),
        "raw_unique_filenames_count": raw_local_filenames_count,
        "distinct_canonical_assets_count": distinct_canonical_count,
        "inflated_asset_count_delta": max(0, raw_local_filenames_count - distinct_canonical_count),
        "canonical_usage_counts": dict(canonical_uses),
        "meaningful_progression_ratio": round(
            sum(1 for p in progression_steps if p["meaningful_progression"]) / float(max(1, len(progression_steps))),
            4,
        )
        if progression_steps
        else 1.0,
        "progression_steps": progression_steps,
        "stale_visual_topic_shifts": stale_topic_shifts,
        "repetition_and_progression_pass": major_count == 0,
        "major_issue_count": major_count,
        "issues": issues,
    }
