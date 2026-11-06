"""
Internet Archive adapter (PD / CC0 / CC BY) — v9 fix: resolves the real video file and its true
dimensions through the Metadata API instead of linking the item folder with a hardcoded 1280x720.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Optional

from .base import LicenseEvidence, VideoCandidate, http_request, license_is_commercial_safe, now_iso, strip_html

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".ogv", ".mpeg", ".mpg", ".mkv")


def license_label_from_url(lic_url: str) -> str:
    low = lic_url.lower()
    if "publicdomain/mark" in low:
        return "Public Domain"
    if "publicdomain/zero" in low:
        return "CC0"
    if "/licenses/by/" in low:
        ver = low.rstrip("/").split("/")[-1]
        return f"CC BY {ver}" if ver.replace(".", "").isdigit() else "CC BY"
    return ""


def pick_best_video_file(files: list[dict[str, Any]], min_height: int = 720) -> Optional[dict[str, Any]]:
    """Choose the highest-resolution playable video file (prefer originals, then h.264 derivatives)."""
    best: Optional[dict[str, Any]] = None
    best_key: tuple = ()
    for f in files:
        name = str(f.get("name", ""))
        if not name.lower().endswith(VIDEO_EXTS):
            continue
        try:
            h = int(float(f.get("height") or 0))
            w = int(float(f.get("width") or 0))
        except ValueError:
            h = w = 0
        if h and h < min_height:
            continue
        mp4_pref = 1 if name.lower().endswith((".mp4", ".m4v", ".mov")) else 0
        orig_pref = 1 if f.get("source") == "original" else 0
        key = (h, mp4_pref, orig_pref, w)
        if best is None or key > best_key:
            best, best_key = f, key
    if best is not None and not int(float(best.get("height") or 0)):
        return best if min_height <= 0 else None
    return best


class InternetArchiveSource:
    name = "internet_archive"
    display_name = "Internet Archive"
    default_enabled = True

    def __init__(self, min_height: int = 720) -> None:
        self.min_height = min_height

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        from ..video_sourcing import LECTURE_TALKING_HEAD_MARKERS, _infer_candidate_media_class, _score_human_interaction_text

        # Lucene: slashes must be escaped (unescaped `*/by/*` makes the whole query error → 0 results,
        # a silent v8 bug). Multi-word queries are phrase-quoted to avoid e.g. "Sega Saturn" for "Saturn V".
        phrase = f'"{query}"' if " " in query.strip() and '"' not in query else query
        q_expr = (
            f"{phrase} AND mediatype:(movies) AND "
            r"(licenseurl:*publicdomain* OR licenseurl:*zero* OR licenseurl:*licenses\/by\/*)"
        )
        api = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
            [("q", q_expr), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "licenseurl"), ("rows", int(limit)), ("page", 1), ("output", "json")]
        )
        try:
            data = http_request(api)
        except RuntimeError:
            return []

        out: list[VideoCandidate] = []
        for doc in data.get("response", {}).get("docs", [])[:limit]:
            ident = str(doc.get("identifier", "")).strip()
            if not ident:
                continue
            try:
                meta = http_request(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
            except RuntimeError:
                continue
            md = meta.get("metadata", {}) or {}
            lic_url = str(md.get("licenseurl", "") or doc.get("licenseurl", ""))
            lic = license_label_from_url(lic_url)
            if not lic or not license_is_commercial_safe(lic):
                continue
            title = strip_html(str(md.get("title", ident)))
            raw_desc = md.get("description", "")
            desc = strip_html(" ".join(raw_desc) if isinstance(raw_desc, list) else str(raw_desc))
            if any(bad in f"{title} {desc}".lower() for bad in LECTURE_TALKING_HEAD_MARKERS):
                continue
            f = pick_best_video_file(meta.get("files", []) or [], self.min_height)
            if not f:
                continue
            creator = md.get("creator", "")
            creator = ", ".join(creator) if isinstance(creator, list) else str(creator)
            page_url = f"https://archive.org/details/{urllib.parse.quote(ident)}"
            attribution = f"{creator or 'Internet Archive uploader'} via Internet Archive ({lic})"
            evidence = LicenseEvidence(
                source_repo=self.name,
                page_url=page_url,
                raw_rights_text=f"licenseurl={lic_url}; rights={strip_html(str(md.get('rights', '')))[:300]}",
                normalized_license=lic,
                license_url=lic_url,
                required_attribution=attribution,
                fetched_at=now_iso(),
                verified=True,
            )
            out.append(
                VideoCandidate(
                    source_repo=self.name,
                    asset_id=ident,
                    title=title,
                    description=desc[:400],
                    page_url=page_url,
                    download_url=f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(str(f['name']))}",
                    license_label=lic,
                    width=int(float(f.get("width") or 0)),
                    height=int(float(f.get("height") or 0)),
                    human_interaction_score=_score_human_interaction_text(title, desc),
                    relevance_notes="open_archive_film",
                    inferred_media_class=_infer_candidate_media_class(title, desc),
                    query_purpose=purpose,
                    preview_image_url=f"https://archive.org/services/img/{urllib.parse.quote(ident)}",
                    duration_s=float(f.get("length") or 0.0) if str(f.get("length", "")).replace(".", "").isdigit() else 0.0,
                    license_url=lic_url,
                    required_attribution=attribution,
                    creator_agency=creator,
                    source_flags=["reupload_verify_origin"] if ident.lower().startswith(("youtube-", "yt-")) else [],
                    license_evidence=evidence.to_dict(),
                )
            )
        return out
