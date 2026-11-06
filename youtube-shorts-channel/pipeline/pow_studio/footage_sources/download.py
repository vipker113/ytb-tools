#!/usr/bin/env python3
"""
Studio v9 footage download + provenance (`pow_studio.footage_sources.download`).

For each selected discovery candidate:
  1. stream-download with resume (`.part`) and a size cap,
  2. strip audio when the source carries third-party music risk (SVS / ESA),
  3. ffprobe + affine-compensated pixel motion audit on 3 windows,
  4. reconcile the media class (metadata hint vs pixels — never upgrades animations/stills),
  5. write `<file>.provenance.json` (all `AssetLicenseSpec` fields + license evidence + audits),
  6. return a ready-to-paste `assets_register` YAML entry.

`backfill_provenance()` writes sidecars for media already registered in existing episode manifests.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Optional

import yaml

from .base import USER_AGENT, now_iso

PROVENANCE_VERSION = "9.0"
NON_CAMERA_CLASSES = {"REAL_ANIMATION", "INFOGRAPHIC", "AI_GENERATED", "REENACTMENT"}
STILL_CLASSES = {"STILL_PHOTO", "ANIMATED_STILL", "SCIENTIFIC_IMAGE"}
MOVING_CLASSES = {"REAL_VIDEO_ACTION", "REAL_VIDEO_ESTABLISHING", "REAL_TIME_LAPSE"}


def sidecar_path(media_path: Path) -> Path:
    return media_path.with_name(media_path.name + ".provenance.json")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_filename(source: str, title: str, cid: str, url: str) -> str:
    import unicodedata

    ext = Path(url.split("?")[0]).suffix.lower() or ".mp4"
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"[^a-z0-9]+", "_", ascii_title.lower()).strip("_")[:48] or "clip"
    return f"{source}_{stem}_{cid}{ext}"


def reconcile_media_class(hint: str, audit_classes: list[str], baked_still_votes: int = 0) -> str:
    """Honesty-first merge of metadata hint and pixel audits. Pixels may only DOWNGRADE a claim."""
    if hint in NON_CAMERA_CLASSES:
        return hint
    if hint in STILL_CLASSES:
        return "ANIMATED_STILL" if ("ANIMATED_STILL" in audit_classes or baked_still_votes) else hint
    if not audit_classes:
        return hint
    if baked_still_votes * 2 >= len(audit_classes):
        return "ANIMATED_STILL"
    if "REAL_VIDEO_ACTION" in audit_classes:
        return "REAL_VIDEO_ACTION"
    for cls in ("REAL_TIME_LAPSE", "REAL_VIDEO_ESTABLISHING"):
        if cls in audit_classes:
            return cls
    return "STILL_PHOTO"


def ffprobe_media(path: Path) -> dict[str, Any]:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate:format=duration,size,bit_rate", "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        return {}
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), {})
    fmt = d.get("format", {})
    return {
        "width": int(v.get("width") or 0),
        "height": int(v.get("height") or 0),
        "video_codec": v.get("codec_name", ""),
        "fps": v.get("r_frame_rate", ""),
        "has_audio": bool(a),
        "duration_s": round(float(fmt.get("duration") or 0.0), 3),
        "bytes": int(fmt.get("size") or 0),
        "bitrate_kbps": round(int(fmt.get("bit_rate") or 0) / 1000.0, 1),
    }


def stream_download(url: str, dest: Path, max_bytes: int = 2_500_000_000, timeout_s: float = 60.0) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if have:
        headers["Range"] = f"bytes={have}-"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        mode = "ab" if (have and resp.status == 206) else "wb"
        written = have if mode == "ab" else 0
        with open(part, mode) as fh:
            while True:
                chunk = resp.read(1 << 20)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise RuntimeError(f"Download exceeds cap ({max_bytes} bytes): {url}")
                fh.write(chunk)
    part.replace(dest)
    return dest


def strip_audio_inplace(path: Path) -> bool:
    tmp = path.with_name(path.stem + ".noaudio" + path.suffix)
    r = subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:v:0", "-c", "copy", "-an", str(tmp)], capture_output=True)
    if r.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(path)
    return True


def audit_motion_windows(path: Path, duration_s: float, hint: str = "") -> dict[str, Any]:
    from ..video_sourcing import audit_clip_real_motion

    if duration_s <= 0.5:
        return {"windows": [], "classes": [], "baked_still_votes": 0}
    win = min(3.0, max(1.0, duration_s * 0.25))
    starts = sorted({round(max(0.0, min(duration_s - win, duration_s * f)), 2) for f in (0.10, 0.45, 0.75)})
    windows, classes, baked = [], [], 0
    for s in starts:
        try:
            a = audit_clip_real_motion(path, start_s=s, duration_s=win, sample_fps=6.0, metadata_hint=hint)
        except Exception as exc:  # noqa: BLE001 - audit failure must not lose the download
            windows.append({"start_s": s, "error": str(exc)[:200]})
            continue
        windows.append({"start_s": s, "duration_s": win, **{k: a[k] for k in ("inferred_media_class", "is_real_moving_footage", "is_baked_animated_still", "has_localized_action_motion", "diagnostic_note")}})
        if a.get("valid", True):
            classes.append(str(a["inferred_media_class"]))
            baked += int(bool(a["is_baked_animated_still"]))
    return {"windows": windows, "classes": classes, "baked_still_votes": baked}


def build_provenance(cand: dict[str, Any], local: Path, probe: dict[str, Any], motion: dict[str, Any], final_class: str, audio_stripped: bool) -> dict[str, Any]:
    return {
        "provenance_version": PROVENANCE_VERSION,
        "provenance_source": "download-footage",
        "candidate_id": cand.get("candidate_id", ""),
        "local_file": local.name,
        "title": cand.get("title", ""),
        "creator_agency": cand.get("creator_agency") or cand.get("source_repo", ""),
        "source_page_url": cand.get("page_url", ""),
        "direct_media_url": cand.get("download_url", ""),
        "license": cand.get("license_label", ""),
        "license_url": cand.get("license_url", ""),
        "required_attribution": cand.get("required_attribution", ""),
        "media_type": "video",
        "source_media_class": final_class,
        "metadata_media_class_hint": cand.get("inferred_media_class", ""),
        "canonical_source_id": f"{cand.get('source_repo', '')}:{cand.get('asset_id', '')}",
        "depicted_subject": "",
        "depicted_action": "",
        "depicted_location": "",
        "intended_use": f"Candidate for query '{cand.get('query', '')}' ({cand.get('query_purpose', '')})",
        "source_repo": cand.get("source_repo", ""),
        "source_flags": cand.get("source_flags", []),
        "third_party_audio_risk": bool(cand.get("third_party_audio_risk")),
        "audio_stripped": audio_stripped,
        "sha256": sha256_file(local),
        "probe": probe,
        "motion_audit": motion,
        "license_evidence": cand.get("license_evidence", {}),
        "downloaded_at": now_iso(),
    }


def assets_register_yaml(prov: dict[str, Any]) -> str:
    keys = [
        "local_file", "title", "creator_agency", "source_page_url", "direct_media_url", "license", "license_url",
        "required_attribution", "media_type", "source_media_class", "canonical_source_id", "depicted_subject",
        "depicted_action", "depicted_location", "intended_use",
    ]
    entry = {k: prov.get(k, "") for k in keys}
    return yaml.safe_dump([entry], sort_keys=False, allow_unicode=True, width=1000)


def download_candidates(
    discovery_json: Path,
    candidate_ids: list[str],
    dest_dir: Path,
    max_bytes: int = 2_500_000_000,
    audit: bool = True,
) -> list[dict[str, Any]]:
    report = json.loads(Path(discovery_json).read_text(encoding="utf-8"))
    pool = {r["candidate_id"]: r for rows in report.get("results_by_purpose", {}).values() for r in rows}
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for cid in candidate_ids:
        cand = pool.get(cid)
        if not cand:
            results.append({"candidate_id": cid, "ok": False, "error": "candidate_id not in discovery report"})
            continue
        dest = Path(dest_dir) / safe_filename(cand["source_repo"], cand["title"], cid, cand["download_url"])
        try:
            if not dest.exists():
                stream_download(cand["download_url"], dest, max_bytes=max_bytes)
            stripped = strip_audio_inplace(dest) if cand.get("third_party_audio_risk") else False
            probe = ffprobe_media(dest)
            motion = audit_motion_windows(dest, probe.get("duration_s", 0.0), hint=f"{cand['title']} {cand.get('description', '')}") if audit else {"windows": [], "classes": [], "baked_still_votes": 0}
            final_class = reconcile_media_class(cand.get("inferred_media_class", ""), motion["classes"], motion["baked_still_votes"])
            prov = build_provenance(cand, dest, probe, motion, final_class, stripped)
            sidecar_path(dest).write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
            results.append({"candidate_id": cid, "ok": True, "local_path": str(dest), "source_media_class": final_class, "probe": probe, "assets_register_yaml": assets_register_yaml(prov)})
        except Exception as exc:  # noqa: BLE001 - report per-candidate failures, continue with the rest
            results.append({"candidate_id": cid, "ok": False, "error": str(exc)[:300]})
    return results


def backfill_provenance(manifest_paths: list[Path], overwrite: bool = False) -> dict[str, Any]:
    """Write sidecars for media already registered in episode manifests (license as declared, unverified online)."""
    from ..schema import EpisodeManifest

    stats = {"assets_seen": 0, "sidecars_written": 0, "already_present": 0, "missing_files": [], "manifests": 0}
    for mp in manifest_paths:
        try:
            ep = EpisodeManifest.from_yaml(mp)
        except Exception as exc:  # noqa: BLE001
            stats.setdefault("manifest_errors", []).append(f"{mp}: {str(exc)[:160]}")
            continue
        stats["manifests"] += 1
        search_dirs = [Path(ep.raw_assets_dir), *[Path(d) for d in ep.extra_assets_dirs], Path(ep.output_dir) / "work_clips"]
        for a in ep.assets_register:
            if a.media_type == "audio":
                continue
            stats["assets_seen"] += 1
            local = next((d / a.local_file for d in search_dirs if (d / a.local_file).exists()), None)
            if local is None:
                stats["missing_files"].append(f"{ep.slug}:{a.local_file}")
                continue
            sp = sidecar_path(local)
            if sp.exists() and not overwrite:
                stats["already_present"] += 1
                continue
            prov = {
                "provenance_version": PROVENANCE_VERSION,
                "provenance_source": "backfill_from_manifest",
                "backfilled_from_manifest": str(mp),
                **json.loads(a.model_dump_json()),
                "sha256": sha256_file(local),
                "probe": ffprobe_media(local) if local.suffix.lower() not in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp") else {},
                "license_evidence": {
                    "source_repo": "manifest_declaration",
                    "page_url": a.source_page_url,
                    "raw_rights_text": a.license,
                    "normalized_license": a.license,
                    "verified": False,
                    "notes": "Declared in a QA-passed episode manifest; run rights_gate --online to re-verify.",
                },
                "downloaded_at": None,
            }
            sp.write_text(json.dumps(prov, indent=2, ensure_ascii=False), encoding="utf-8")
            stats["sidecars_written"] += 1
    stats["missing_files_count"] = len(stats["missing_files"])
    return stats
