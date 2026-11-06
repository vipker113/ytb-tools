"""
NASA Scientific Visualization Studio adapter (Public Domain visuals).

Honesty rules:
- SVS pages are mostly visualizations/animations → classified `REAL_ANIMATION` (never real footage)
  unless the page type is a produced video, which stays "verify pixels".
- Embedded SVS soundtracks are frequently licensed third-party music → `third_party_audio_risk=True`
  (audio is stripped on download).
"""

from __future__ import annotations

import urllib.parse
from typing import Any

from .base import LicenseEvidence, VideoCandidate, http_request, now_iso, strip_html

SEARCH = "https://svs.gsfc.nasa.gov/api/search/"
PAGE = "https://svs.gsfc.nasa.gov/api/{id}"

ANIMATION_TYPES = {"animation", "visualization", "hyperwall visual", "infographic"}


def _iter_movies(page: dict[str, Any]) -> list[dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}

    def walk(o: Any) -> None:
        if isinstance(o, dict):
            url = str(o.get("url", ""))
            if o.get("media_type") == "Movie" and url.lower().endswith((".mp4", ".mov", ".webm")):
                found.setdefault(url, o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(page.get("media_groups", []))
    walk(page.get("main_video", {}))
    return list(found.values())


def _pick_per_stem(movies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One file per visual: group by alt text (same visual, many encodes), else by normalized file stem."""
    import re

    by_stem: dict[str, list[dict[str, Any]]] = {}
    for m in movies:
        fname = str(m.get("filename") or m.get("url", "").rsplit("/", 1)[-1])
        stem = fname.rsplit(".", 1)[0]
        stem = re.sub(r"(_ProRes|_web|_webm|_\d{3,4}p|_4k|_V\d+|_v\d+|\.\d{5})", "", stem, flags=re.I)
        key = str(m.get("alt_text") or "").strip().lower() or stem.lower()
        by_stem.setdefault(key, []).append(m)
    picks = []
    for items in by_stem.values():
        def key(m: dict[str, Any]) -> tuple:
            url = str(m.get("url", "")).lower()
            h = int(m.get("height") or 0)
            return (1 if h >= 1080 else 0, 1 if url.endswith(".mp4") else 0, -abs(h - 1080), h)

        picks.append(sorted(items, key=key, reverse=True)[0])
    return picks


class NasaSvsSource:
    name = "nasa_svs"
    display_name = "NASA Scientific Visualization Studio"
    default_enabled = True

    def __init__(self, min_height: int = 720, max_pages: int = 4) -> None:
        self.min_height = min_height
        self.max_pages = max_pages

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        url = SEARCH + "?" + urllib.parse.urlencode({"search": query, "limit": max(1, min(self.max_pages, limit))})
        try:
            res = http_request(url)
        except RuntimeError:
            return []
        out: list[VideoCandidate] = []
        for r in (res.get("results") or [])[: self.max_pages]:
            pid = r.get("id")
            if not pid:
                continue
            try:
                page = http_request(PAGE.format(id=pid))
            except RuntimeError:
                continue
            ptype = str(page.get("page_type") or r.get("result_type") or "").lower()
            is_animation = any(t in ptype for t in ANIMATION_TYPES)
            title = strip_html(str(page.get("title", "")))
            desc = strip_html(str(page.get("description", "")))[:500]
            page_url = f"https://svs.gsfc.nasa.gov/{pid}/"
            for m in _pick_per_stem(_iter_movies(page)):
                h = int(m.get("height") or 0)
                if h and h < self.min_height:
                    continue
                murl = str(m.get("url", "")).replace("http://", "https://")
                alt = strip_html(str(m.get("alt_text", "")))
                evidence = LicenseEvidence(
                    source_repo=self.name,
                    page_url=page_url,
                    raw_rights_text="NASA SVS content (U.S. Government work). SVS soundtracks may be licensed third-party music; audio stripped.",
                    normalized_license="Public Domain (NASA SVS)",
                    license_url="https://svs.gsfc.nasa.gov/help/#apis-mediausage",
                    required_attribution="NASA's Scientific Visualization Studio",
                    fetched_at=now_iso(),
                    verified=True,
                )
                out.append(
                    VideoCandidate(
                        source_repo=self.name,
                        asset_id=f"svs-{pid}-{murl.rsplit('/', 1)[-1]}",
                        title=f"{title} — {alt}" if alt else title,
                        description=desc,
                        page_url=page_url,
                        download_url=murl,
                        license_label="Public Domain (NASA SVS)",
                        width=int(m.get("width") or 0),
                        height=h,
                        human_interaction_score=0.0,
                        relevance_notes=f"svs_{ptype or 'page'}",
                        inferred_media_class="REAL_ANIMATION" if is_animation else "REAL_VIDEO_ESTABLISHING",
                        query_purpose=purpose,
                        preview_image_url=murl.rsplit(".", 1)[0] + ".00100_print.jpg",
                        license_url=evidence.license_url,
                        required_attribution=evidence.required_attribution,
                        creator_agency="NASA SVS",
                        third_party_audio_risk=True,
                        source_flags=["visualization_not_camera_footage"] if is_animation else ["verify_pixels"],
                        license_evidence=evidence.to_dict(),
                    )
                )
                if len(out) >= limit:
                    return out
        return out
