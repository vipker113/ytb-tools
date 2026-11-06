#!/usr/bin/env python3
"""
Append-only & incremental Visual Corpus storage (`pow_studio.visual_corpus.corpus`).

Disk layout under `assets/visual_corpus/` (gitignored):
  - `index.jsonl`        : 1 JSON record per scene-cut-clean media window (`key = sha256[:16]_start`)
  - `embeddings.npy`     : `(N, D)` float32 L2-normalized visual frame embeddings
  - `tag_embeddings.npy` : `(N, D)` float32 L2-normalized metadata/tag embeddings
  - `thumbs/`            : `<window_id>.jpg` 320px midpoint thumbnails for contact strips & Backlot
  - `corpus_meta.json`   : active model metadata, file inventory, and unlicensed file quarantine log
  - `usage_ledger.json`  : cross-episode window usage history (penalizes recent hero-shot reuse)
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from ..deduplication import compute_phash_64, resolve_canonical_source_id
from ..footage_sources.download import reconcile_media_class, sha256_file, sidecar_path
from ..media_classifier import (
    GENUINE_MOVING_CLASSES,
    STILL_EXTENSIONS,
    VIDEO_EXTENSIONS,
    inspect_media_authenticity,
)
from ..rights_gate import RightsViolationError, validate_license_string
from .embedder import DEFAULT_MODEL_ALIAS, VisualEmbedder, _l2_normalize, get_embedder
from .windowing import MediaWindow, build_media_windows, sample_window_frames

CORPUS_VERSION = "9.0"


def default_corpus_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "visual_corpus"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _atomic_save_npy(path: Path, arr: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.stem}.{os.getpid()}.tmp.npy")
    np.save(tmp, np.asarray(arr, dtype=np.float32))
    os.replace(tmp, path)


def make_window_id(file_sha256: str, start_s: float) -> str:
    return f"{file_sha256[:16]}_{float(start_s):07.2f}"


def _evaluate_provenance_file(media_path: Path) -> tuple[str, dict[str, Any]]:
    """
    Inspect `<media>.provenance.json` and classify `license_status`:
      - `verified` : downloaded with online license evidence + passes `validate_license_string`
      - `declared` : backfilled from manifest + passes `validate_license_string`
      - `rejected` : sidecar exists, license fails `validate_license_string`
      - `unknown`  : no provenance sidecar on disk (quarantined from production retrieval)
    """
    sp = sidecar_path(media_path)
    if not sp.exists():
        return "unknown", {}
    try:
        prov = json.loads(sp.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unknown", {}

    lic = str(prov.get("license") or "").strip()
    if not lic:
        return "unknown", prov
    try:
        validate_license_string(lic, media_path.name)
    except RightsViolationError:
        return "rejected", prov

    ev = prov.get("license_evidence") or {}
    if prov.get("provenance_source") == "download-footage" or bool(ev.get("verified")):
        return "verified", prov
    return "declared", prov


def _build_metadata_text(media_path: Path, raw_root: Path, prov: dict[str, Any]) -> str:
    try:
        rel_folder = media_path.parent.relative_to(raw_root).as_posix()
    except ValueError:
        rel_folder = media_path.parent.name
    folder_words = re.sub(r"[_\-/]+", " ", rel_folder)
    stem_words = re.sub(r"[_\-]+", " ", media_path.stem)
    parts = [
        str(prov.get("title") or ""),
        str(prov.get("depicted_subject") or ""),
        str(prov.get("depicted_action") or ""),
        str(prov.get("depicted_location") or ""),
        str(prov.get("intended_use") or ""),
        folder_words,
        stem_words,
    ]
    cleaned = re.sub(r"\s+", " ", " ".join(p for p in parts if p)).strip()
    return cleaned or media_path.stem


@dataclass
class LoadedCorpus:
    corpus_dir: Path
    records: list[dict[str, Any]]
    embeddings: np.ndarray
    tag_embeddings: np.ndarray
    meta: dict[str, Any]

    @property
    def size(self) -> int:
        return len(self.records)


def load_corpus(
    corpus_dir: Optional[Path] = None,
    model_alias: Optional[str] = None,
    repair_on_mismatch: bool = True,
) -> LoadedCorpus:
    """
    Load `index.jsonl` + `.npy` matrices. If a previous ingest was interrupted between writing
    JSONL and `.npy`, automatically truncate to `min_rows` so indices align 1:1.
    """
    cdir = Path(corpus_dir) if corpus_dir else default_corpus_dir()
    idx_path = cdir / "index.jsonl"
    meta_path = cdir / "corpus_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    active_model = meta.get("model_alias", DEFAULT_MODEL_ALIAS)
    if model_alias and model_alias != active_model:
        mdir = cdir / "models" / model_alias
        emb_path = mdir / "embeddings.npy"
        tag_path = mdir / "tag_embeddings.npy"
    else:
        emb_path = cdir / "embeddings.npy"
        tag_path = cdir / "tag_embeddings.npy"

    if not idx_path.exists() or not emb_path.exists() or not tag_path.exists():
        return LoadedCorpus(
            corpus_dir=cdir,
            records=[],
            embeddings=np.zeros((0, int(meta.get("embed_dim") or 512)), dtype=np.float32),
            tag_embeddings=np.zeros((0, int(meta.get("embed_dim") or 512)), dtype=np.float32),
            meta=meta,
        )

    records: list[dict[str, Any]] = []
    for ln in idx_path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            records.append(json.loads(ln))
        except json.JSONDecodeError:
            break

    emb = np.load(emb_path).astype(np.float32)
    tag_emb = np.load(tag_path).astype(np.float32)

    min_rows = min(len(records), int(emb.shape[0]), int(tag_emb.shape[0]))
    if (len(records) != min_rows or emb.shape[0] != min_rows or tag_emb.shape[0] != min_rows):
        records = records[:min_rows]
        emb = emb[:min_rows]
        tag_emb = tag_emb[:min_rows]
        if repair_on_mismatch and (not model_alias or model_alias == active_model):
            tmp_idx = idx_path.with_name(f".index.{os.getpid()}.tmp")
            tmp_idx.write_text(
                "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
                encoding="utf-8",
            )
            os.replace(tmp_idx, idx_path)
            _atomic_save_npy(emb_path, emb)
            _atomic_save_npy(tag_path, tag_emb)

    return LoadedCorpus(
        corpus_dir=cdir,
        records=records,
        embeddings=emb,
        tag_embeddings=tag_emb,
        meta=meta,
    )


def _discover_media_files(raw_root: Path, limit: Optional[int] = None) -> list[Path]:
    allowed = STILL_EXTENSIONS | VIDEO_EXTENSIONS
    files: list[Path] = []
    for p in sorted(raw_root.rglob("*")):
        if not p.is_file() or p.name.startswith(".") or p.name.endswith(".provenance.json"):
            continue
        if p.suffix.lower() in allowed:
            files.append(p)
            if limit and len(files) >= limit:
                break
    return files


def _prepare_file_windows(
    media_path: Path,
    raw_root: Path,
    thumbs_dir: Path,
    max_windows_per_file: int = 36,
) -> dict[str, Any]:
    """Decode windows, midpoint thumbnails, pHash, and pixel motion authenticity for one file."""
    st = media_path.stat()
    sp = sidecar_path(media_path)
    prov_mtime_ns = sp.stat().st_mtime_ns if sp.exists() else 0
    lic_status, prov = _evaluate_provenance_file(media_path)
    f_sha = str(prov.get("sha256") or "") or sha256_file(media_path)
    probe_hint = prov.get("probe") if isinstance(prov.get("probe"), dict) and prov.get("probe") else None

    windows, probe_info = build_media_windows(
        media_path,
        probe=probe_hint,
        max_windows_per_file=max_windows_per_file,
    )
    if not windows:
        return {"media_path": media_path, "windows": [], "error": "unreadable_or_empty"}

    try:
        rel_path = media_path.relative_to(raw_root).as_posix()
    except ValueError:
        rel_path = media_path.name

    meta_text = _build_metadata_text(media_path, raw_root, prov)
    hint_class = str(prov.get("source_media_class") or "")
    canonical_id = str(prov.get("canonical_source_id") or "") or resolve_canonical_source_id(prov or None, media_path.name)
    width = int(probe_info.get("width") or 0)
    height = int(probe_info.get("height") or 0)

    prepared: list[dict[str, Any]] = []
    for win in windows:
        wid = make_window_id(f_sha, win.start_s)
        frames = sample_window_frames(media_path, win, max_width=384)
        if not frames:
            continue
        mid_frame = frames[len(frames) // 2]
        if width <= 0 or height <= 0:
            width, height = mid_frame.size

        # Save 320px midpoint thumbnail
        thumbs_dir.mkdir(parents=True, exist_ok=True)
        thumb_rel = f"thumbs/{wid}.jpg"
        thumb_path = thumbs_dir.parent / thumb_rel
        if not thumb_path.exists():
            tw = min(320, mid_frame.width)
            th = max(2, int(round(mid_frame.height * (tw / float(max(1, mid_frame.width))))))
            mid_frame.resize((tw, th), Image.Resampling.BILINEAR).save(thumb_path, format="JPEG", quality=82)

        phash_hex = f"{compute_phash_64(mid_frame):016x}"

        # Pixel motion authenticity check per window
        if win.is_still:
            audit = inspect_media_authenticity(media_path, metadata_hint=meta_text)
            final_cls = reconcile_media_class(hint_class or audit.inferred_media_class, [audit.inferred_media_class], 0)
        else:
            audit = inspect_media_authenticity(
                media_path,
                start_s=win.start_s,
                duration_s=min(2.4, max(1.2, win.duration_s)),
                sample_fps=4.0,
                metadata_hint=meta_text,
            )
            if audit.valid:
                final_cls = reconcile_media_class(
                    hint_class or audit.inferred_media_class,
                    [audit.inferred_media_class],
                    int(bool(audit.is_baked_animated_still)),
                )
            else:
                final_cls = hint_class or audit.inferred_media_class

        rec = {
            "window_id": wid,
            "rel_path": rel_path,
            "local_file": media_path.name,
            "abs_path": str(media_path.resolve()),
            "sha256": f_sha,
            "file_size": int(st.st_size),
            "file_mtime_ns": int(st.st_mtime_ns),
            "prov_mtime_ns": int(prov_mtime_ns),
            "start_s": round(win.start_s, 2),
            "end_s": round(win.end_s, 2),
            "duration_s": round(win.duration_s, 2),
            "is_still": bool(win.is_still),
            "width": width,
            "height": height,
            "phash_64": phash_hex,
            "thumb_rel": thumb_rel,
            "source_media_class": final_cls,
            "pixel_inferred_class": audit.inferred_media_class,
            "is_real_moving_footage": final_cls in GENUINE_MOVING_CLASSES,
            "has_localized_action_motion": bool(audit.has_localized_action_motion),
            "is_baked_animated_still": bool(audit.is_baked_animated_still),
            "license_status": lic_status,
            "license": str(prov.get("license") or ""),
            "license_url": str(prov.get("license_url") or ""),
            "creator_agency": str(prov.get("creator_agency") or ""),
            "source_page_url": str(prov.get("source_page_url") or ""),
            "canonical_source_id": canonical_id,
            "metadata_text": meta_text,
            "provenance": {
                "title": str(prov.get("title") or ""),
                "depicted_subject": str(prov.get("depicted_subject") or ""),
                "depicted_action": str(prov.get("depicted_action") or ""),
                "depicted_location": str(prov.get("depicted_location") or ""),
                "intended_use": str(prov.get("intended_use") or ""),
                "source_repo": str(prov.get("source_repo") or ""),
            },
        }
        prepared.append({"record": rec, "frames": frames})

    return {"media_path": media_path, "windows": prepared, "error": None}


def ingest_corpus(
    raw_root: Path,
    corpus_dir: Optional[Path] = None,
    model_alias: str = DEFAULT_MODEL_ALIAS,
    embedder: Optional[VisualEmbedder] = None,
    limit: Optional[int] = None,
    workers: int = 4,
    checkpoint_every_files: int = 24,
) -> dict[str, Any]:
    """
    Incrementally index all media files under `raw_root` into `corpus_dir`.
    Unchanged files (`rel_path + file_size + file_mtime_ns`) are skipped in O(1); if only a
    `.provenance.json` sidecar changed, metadata + tag embeddings refresh without re-decoding video.
    """
    t0 = time.perf_counter()
    scan_root = Path(raw_root).resolve()
    cdir = Path(corpus_dir).resolve() if corpus_dir else default_corpus_dir().resolve()
    thumbs_dir = cdir / "thumbs"
    cdir.mkdir(parents=True, exist_ok=True)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    emb_model = embedder or get_embedder(model_alias=model_alias)
    loaded = load_corpus(cdir, repair_on_mismatch=True)

    # If existing corpus used a different model dimension/alias, rebuild embeddings cleanly
    model_changed = bool(loaded.records and loaded.meta.get("model_alias") not in (None, emb_model.model_alias))
    if model_changed:
        loaded = LoadedCorpus(
            corpus_dir=cdir,
            records=[],
            embeddings=np.zeros((0, emb_model.embed_dim), dtype=np.float32),
            tag_embeddings=np.zeros((0, emb_model.embed_dim), dtype=np.float32),
            meta={},
        )

    # Preserve parent raw_root when ingesting a single episode subdirectory inside it
    existing_root_str = str(loaded.meta.get("raw_root") or "").strip()
    existing_root = Path(existing_root_str).resolve() if existing_root_str else None
    is_subdir_scan = bool(
        existing_root
        and existing_root != scan_root
        and existing_root in scan_root.parents
        and existing_root.exists()
    )
    raw_root = existing_root if is_subdir_scan and existing_root is not None else scan_root
    subdir_prefix = (scan_root.relative_to(raw_root).as_posix().rstrip("/") + "/") if is_subdir_scan else ""

    files = _discover_media_files(scan_root, limit=limit)
    on_disk_rels = {f.relative_to(raw_root).as_posix() for f in files}

    # Group existing records by rel_path
    by_rel: dict[str, list[int]] = {}
    for idx, r in enumerate(loaded.records):
        by_rel.setdefault(str(r.get("rel_path") or ""), []).append(idx)

    kept_records: list[dict[str, Any]] = []
    kept_vis_rows: list[np.ndarray] = []
    kept_tag_rows: list[np.ndarray] = []
    prov_refreshed_indices: list[int] = []

    skipped_unchanged = 0
    refreshed_provenance = 0
    to_ingest: list[Path] = []
    known_unreadable: dict[str, dict[str, int]] = dict(loaded.meta.get("unreadable_files") or {})

    for f in files:
        rel = f.relative_to(raw_root).as_posix()
        st = f.stat()
        sp = sidecar_path(f)
        prov_mtime = sp.stat().st_mtime_ns if sp.exists() else 0
        existing_idxs = by_rel.get(rel)

        if existing_idxs:
            r0 = loaded.records[existing_idxs[0]]
            if int(r0.get("file_size", -1)) == int(st.st_size) and int(r0.get("file_mtime_ns", -1)) == int(st.st_mtime_ns):
                if int(r0.get("prov_mtime_ns", -1)) == int(prov_mtime):
                    for old_i in existing_idxs:
                        kept_records.append(loaded.records[old_i])
                        kept_vis_rows.append(loaded.embeddings[old_i])
                        kept_tag_rows.append(loaded.tag_embeddings[old_i])
                    skipped_unchanged += 1
                    continue
                # Only provenance sidecar changed -> update license & metadata without FFmpeg decode!
                lic_status, prov = _evaluate_provenance_file(f)
                meta_text = _build_metadata_text(f, raw_root, prov)
                hint_cls = str(prov.get("source_media_class") or "")
                canon_id = str(prov.get("canonical_source_id") or "") or resolve_canonical_source_id(prov or None, f.name)
                for old_i in existing_idxs:
                    rec = dict(loaded.records[old_i])
                    px_cls = str(rec.get("pixel_inferred_class") or rec.get("source_media_class") or "STILL_PHOTO")
                    final_cls = reconcile_media_class(hint_cls or px_cls, [px_cls], int(bool(rec.get("is_baked_animated_still"))))
                    rec.update(
                        {
                            "prov_mtime_ns": int(prov_mtime),
                            "license_status": lic_status,
                            "license": str(prov.get("license") or ""),
                            "license_url": str(prov.get("license_url") or ""),
                            "creator_agency": str(prov.get("creator_agency") or ""),
                            "source_page_url": str(prov.get("source_page_url") or ""),
                            "canonical_source_id": canon_id,
                            "source_media_class": final_cls,
                            "is_real_moving_footage": final_cls in GENUINE_MOVING_CLASSES,
                            "metadata_text": meta_text,
                        }
                    )
                    prov_refreshed_indices.append(len(kept_records))
                    kept_records.append(rec)
                    kept_vis_rows.append(loaded.embeddings[old_i])
                    kept_tag_rows.append(loaded.tag_embeddings[old_i])
                refreshed_provenance += 1
                continue

        # Check previously unreadable empty/corrupt file cache so re-ingest stays 100% skip
        unread = known_unreadable.get(rel)
        if unread and int(unread.get("file_size", -1)) == int(st.st_size) and int(unread.get("file_mtime_ns", -1)) == int(st.st_mtime_ns):
            skipped_unchanged += 1
            continue

        to_ingest.append(f)

    # Retain records outside the scanned scope (e.g., `--limit` or ingesting a single episode subfolder)
    for rel, idxs in by_rel.items():
        outside_subdir = bool(is_subdir_scan and subdir_prefix and not rel.startswith(subdir_prefix))
        if rel not in on_disk_rels and (limit is not None or outside_subdir):
            for old_i in idxs:
                kept_records.append(loaded.records[old_i])
                kept_vis_rows.append(loaded.embeddings[old_i])
                kept_tag_rows.append(loaded.tag_embeddings[old_i])

    if prov_refreshed_indices:
        new_texts = [kept_records[i]["metadata_text"] for i in prov_refreshed_indices]
        new_tvecs = emb_model.embed_texts(new_texts)
        for pos, i in enumerate(prov_refreshed_indices):
            kept_tag_rows[i] = new_tvecs[pos]

    ingested_files = 0
    failed_files: list[str] = []

    def _flush_checkpoint() -> None:
        vis_mat = (
            np.stack(kept_vis_rows, axis=0).astype(np.float32)
            if kept_vis_rows
            else np.zeros((0, emb_model.embed_dim), dtype=np.float32)
        )
        tag_mat = (
            np.stack(kept_tag_rows, axis=0).astype(np.float32)
            if kept_tag_rows
            else np.zeros((0, emb_model.embed_dim), dtype=np.float32)
        )
        tmp_idx = cdir / f".index.{os.getpid()}.tmp"
        tmp_idx.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept_records),
            encoding="utf-8",
        )
        os.replace(tmp_idx, cdir / "index.jsonl")
        _atomic_save_npy(cdir / "embeddings.npy", vis_mat)
        _atomic_save_npy(cdir / "tag_embeddings.npy", tag_mat)

    # Process new/changed files in chunks for bounded RAM + checkpoint safety
    chunk_size = max(1, int(checkpoint_every_files))
    for start_idx in range(0, len(to_ingest), chunk_size):
        batch_files = to_ingest[start_idx : start_idx + chunk_size]
        if workers > 1 and len(batch_files) > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
                prep_results = list(pool.map(lambda p: _prepare_file_windows(p, raw_root, thumbs_dir), batch_files))
        else:
            prep_results = [_prepare_file_windows(p, raw_root, thumbs_dir) for p in batch_files]

        all_frames: list[Image.Image] = []
        frame_spans: list[tuple[int, int]] = []
        batch_records: list[dict[str, Any]] = []

        for res in prep_results:
            mp: Path = res["media_path"]
            rel = mp.relative_to(raw_root).as_posix()
            if res["error"] or not res["windows"]:
                st = mp.stat()
                known_unreadable[rel] = {"file_size": int(st.st_size), "file_mtime_ns": int(st.st_mtime_ns)}
                failed_files.append(rel)
                continue
            known_unreadable.pop(rel, None)
            ingested_files += 1
            for item in res["windows"]:
                s_pos = len(all_frames)
                all_frames.extend(item["frames"])
                e_pos = len(all_frames)
                frame_spans.append((s_pos, e_pos))
                batch_records.append(item["record"])

        if batch_records:
            frame_embs = emb_model.embed_images(all_frames, batch_size=24)
            win_embs: list[np.ndarray] = []
            for s_pos, e_pos in frame_spans:
                mean_vec = frame_embs[s_pos:e_pos].mean(axis=0)
                win_embs.append(_l2_normalize(mean_vec))
            tag_embs = emb_model.embed_texts([r["metadata_text"] for r in batch_records], batch_size=32)

            for i, rec in enumerate(batch_records):
                kept_records.append(rec)
                kept_vis_rows.append(win_embs[i])
                kept_tag_rows.append(tag_embs[i])

        _flush_checkpoint()

    if not to_ingest and (prov_refreshed_indices or model_changed or not (cdir / "index.jsonl").exists()):
        _flush_checkpoint()

    # Summarize inventory & license quarantine
    videos_seen = sum(1 for f in files if f.suffix.lower() in VIDEO_EXTENSIONS)
    photos_seen = sum(1 for f in files if f.suffix.lower() in STILL_EXTENSIONS)
    unknown_files = sorted({r["rel_path"] for r in kept_records if r.get("license_status") == "unknown"})
    rejected_files = sorted({r["rel_path"] for r in kept_records if r.get("license_status") == "rejected"})
    licensed_windows = sum(1 for r in kept_records if r.get("license_status") in ("verified", "declared"))

    meta_payload = {
        "corpus_version": CORPUS_VERSION,
        "model_alias": emb_model.model_alias,
        "hf_id": emb_model.hf_id,
        "embed_dim": int(emb_model.embed_dim),
        "device": emb_model.device,
        "raw_root": str(raw_root),
        "updated_at": _now_iso(),
        "total_files_scanned": len(files),
        "video_files_scanned": videos_seen,
        "photo_files_scanned": photos_seen,
        "total_windows": len(kept_records),
        "licensed_windows": licensed_windows,
        "unknown_license_files_count": len(unknown_files),
        "rejected_license_files_count": len(rejected_files),
        "unknown_license_files": unknown_files,
        "rejected_license_files": rejected_files,
        "unreadable_files": known_unreadable,
    }
    _atomic_write_json(cdir / "corpus_meta.json", meta_payload)

    ledger_path = cdir / "usage_ledger.json"
    if not ledger_path.exists():
        _atomic_write_json(ledger_path, {"ledger_version": CORPUS_VERSION, "usages": []})

    elapsed_s = round(time.perf_counter() - t0, 2)
    return {
        "corpus_dir": str(cdir),
        "model_alias": emb_model.model_alias,
        "device": emb_model.device,
        "total_files_scanned": len(files),
        "video_files_scanned": videos_seen,
        "photo_files_scanned": photos_seen,
        "ingested_files": ingested_files,
        "skipped_unchanged_files": skipped_unchanged,
        "refreshed_provenance_files": refreshed_provenance,
        "failed_files": failed_files,
        "total_windows": len(kept_records),
        "licensed_windows": licensed_windows,
        "unknown_license_files_count": len(unknown_files),
        "elapsed_s": elapsed_s,
    }


def ensure_model_embeddings(
    corpus_dir: Optional[Path],
    model_alias: str,
    embedder: Optional[VisualEmbedder] = None,
) -> tuple[LoadedCorpus, dict[str, float]]:
    """
    Ensure `(embeddings.npy, tag_embeddings.npy)` exist for `model_alias` on the exact windows
    already indexed in `index.jsonl` (saving auxiliary models under `corpus_dir/models/<alias>/`).
    Returns `(loaded_corpus, perf_metrics)` with throughput and peak memory stats.
    """
    import resource

    cdir = Path(corpus_dir).resolve() if corpus_dir else default_corpus_dir().resolve()
    base = load_corpus(cdir, repair_on_mismatch=True)
    if not base.records:
        raise RuntimeError(f"Corpus at {cdir} is empty; run corpus-ingest first.")

    emb_model = embedder or get_embedder(model_alias=model_alias)
    active_model = base.meta.get("model_alias", DEFAULT_MODEL_ALIAS)

    if model_alias == active_model:
        return base, {"images_per_sec": 0.0, "peak_rss_mb": 0.0, "cached": 1.0}

    mdir = cdir / "models" / model_alias
    emb_path = mdir / "embeddings.npy"
    tag_path = mdir / "tag_embeddings.npy"
    if emb_path.exists() and tag_path.exists():
        loaded_aux = load_corpus(cdir, model_alias=model_alias, repair_on_mismatch=False)
        if len(loaded_aux.records) == len(base.records):
            return loaded_aux, {"images_per_sec": 0.0, "peak_rss_mb": 0.0, "cached": 1.0}

    # Re-embed from cached midpoint thumbnails first (SSD read in <2s for 3k windows; fallback to FFmpeg)
    t0 = time.perf_counter()
    all_imgs: list[Image.Image] = []
    spans: list[tuple[int, int]] = []
    for rec in base.records:
        frames: list[Image.Image] = []
        tp = cdir / str(rec.get("thumb_rel") or "")
        if tp.exists():
            try:
                with Image.open(tp) as im:
                    frames = [im.convert("RGB")]
            except Exception:
                frames = []
        if not frames:
            mp = Path(rec["abs_path"])
            win = MediaWindow(start_s=float(rec["start_s"]), end_s=float(rec["end_s"]), is_still=bool(rec["is_still"]))
            frames = sample_window_frames(mp, win, max_width=384) if mp.exists() else []
        if not frames:
            frames = [Image.new("RGB", (224, 224), (0, 0, 0))]
        s_i = len(all_imgs)
        all_imgs.extend(frames)
        spans.append((s_i, len(all_imgs)))

    t_embed0 = time.perf_counter()
    raw_img_embs = emb_model.embed_images(all_imgs, batch_size=24)
    img_elapsed = max(1e-4, time.perf_counter() - t_embed0)
    vis_rows = [_l2_normalize(raw_img_embs[s_i:e_i].mean(axis=0)) for s_i, e_i in spans]
    vis_mat = np.stack(vis_rows, axis=0).astype(np.float32)
    tag_mat = emb_model.embed_texts([str(r.get("metadata_text") or "") for r in base.records], batch_size=32)

    mdir.mkdir(parents=True, exist_ok=True)
    _atomic_save_npy(emb_path, vis_mat)
    _atomic_save_npy(tag_path, tag_mat)
    # macOS `ru_maxrss` is in bytes on Darwin!
    rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak_rss_mb = round(rss_bytes / (1024.0 * 1024.0), 1)
    perf = {
        "images_embedded": float(len(all_imgs)),
        "embed_seconds": round(img_elapsed, 3),
        "total_seconds": round(time.perf_counter() - t0, 3),
        "images_per_sec": round(len(all_imgs) / img_elapsed, 1),
        "peak_rss_mb": peak_rss_mb,
        "cached": 0.0,
    }
    _atomic_write_json(mdir / "meta.json", {"model_alias": model_alias, "hf_id": emb_model.hf_id, **perf})
    return LoadedCorpus(
        corpus_dir=cdir,
        records=base.records,
        embeddings=vis_mat,
        tag_embeddings=tag_mat,
        meta={**base.meta, "model_alias": model_alias, "embed_dim": int(vis_mat.shape[-1])},
    ), perf


def read_usage_ledger(corpus_dir: Optional[Path] = None) -> list[dict[str, Any]]:
    cdir = Path(corpus_dir) if corpus_dir else default_corpus_dir()
    p = cdir / "usage_ledger.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return list(data.get("usages") or [])
    except (OSError, json.JSONDecodeError):
        return []


def record_episode_usage_in_ledger(
    ep: Any,
    corpus_dir: Optional[Path] = None,
    rendered_at: Optional[str] = None,
) -> int:
    """
    Record windows used by a rendered master episode into `assets/visual_corpus/usage_ledger.json`.
    Idempotent per `ep.slug` (replaces previous entries for the same slug).
    """
    cdir = Path(corpus_dir) if corpus_dir else default_corpus_dir()
    cdir.mkdir(parents=True, exist_ok=True)
    existing = [u for u in read_usage_ledger(cdir) if u.get("slug") != ep.slug]
    ts = rendered_at or _now_iso()

    reg_by_file = {a.local_file: a for a in getattr(ep, "assets_register", [])}
    added = 0
    for idx, sh in enumerate(getattr(ep, "shots", [])):
        src_file = getattr(sh, "src_file", None)
        if not src_file:
            continue
        asset = reg_by_file.get(src_file)
        canon_id = resolve_canonical_source_id(asset, src_file)
        dur = round(max(0.1, float(sh.end_s) - float(sh.start_s)), 2)
        is_hero = bool(idx == 0 or float(sh.start_s) < 4.0 or dur >= 4.0)
        existing.append(
            {
                "slug": ep.slug,
                "rendered_at": ts,
                "shot_id": getattr(sh, "sid", getattr(sh, "id", f"S{idx+1:02d}")),
                "local_file": src_file,
                "canonical_source_id": canon_id,
                "src_in_s": round(float(getattr(sh, "src_in", 0.0) or 0.0), 2),
                "duration_s": dur,
                "is_hero_shot": is_hero,
            }
        )
        added += 1

    _atomic_write_json(cdir / "usage_ledger.json", {"ledger_version": CORPUS_VERSION, "usages": existing})
    return added
