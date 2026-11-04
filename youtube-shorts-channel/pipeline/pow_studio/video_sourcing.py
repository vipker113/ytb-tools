#!/usr/bin/env python3
"""
Zero-Cost Authentic Video Harvester, Multi-Purpose Action Discovery &
Optical Motion Authenticity Auditor (`pow_studio.video_sourcing` v8.0).

Searches commercial-safe (`Public Domain`, `CC0`, `CC BY`) scientific & documentary video
repositories without API keys ($0 budget):
1. NASA Images & Video API (`images-api.nasa.gov`) — 1080p/4K Public Domain fieldwork, Earth & space video.
2. Wikimedia Commons MediaWiki API (`commons.wikimedia.org` `filetype:video`) — 4K/1080p/720p `CC BY` & `PD`
   expedition videos, NOAA/USGS/NPS uploads, peer-reviewed journal (`PLOS`, `Scientific Reports`, `eLife`)
   microscopy/experiments, and `ZDF Terra X` (`CC BY 4.0`) documentary science footage.
3. Internet Archive Advanced Search (`archive.org/advancedsearch.php`) — Public Domain / `CC BY` federal
   expedition & institutional science films (NOAA, USGS, NASA, National Archives, universities).

Also provides `audit_clip_real_motion()` backed by `pow_studio.media_classifier.inspect_media_authenticity`
to confirm genuine recorded video motion and reject static-photo Ken Burns slideshows disguised as MP4s.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from .media_classifier import inspect_media_authenticity

USER_AGENT = "ProofOfWonderDocumentaryHarvester/8.0 (science-documentary-pipeline; zero-cost)"

HUMAN_INTERACTION_KEYWORDS = (
    "scientist",
    "researcher",
    "field",
    "sampling",
    "sample",
    "drill",
    "drilling",
    "core",
    "expedition",
    "camp",
    "team",
    "crew",
    "diver",
    "astronaut",
    "technician",
    "laboratory",
    "eislabor",
    "survey",
    "helicopter",
    "traverse",
    "instrument",
    "hands",
    "collect",
    "measuring",
    "bury",
    "submersible",
    "rov",
)

ACTION_PROCESS_KEYWORDS = (
    "sampling",
    "lowering",
    "drilling",
    "bubbling",
    "boiling",
    "erupting",
    "flowing",
    "pouring",
    "venting",
    "swimming",
    "slithering",
    "striking",
    "diving",
    "operating",
    "deploying",
)

BLOCKED_LICENSE_MARKERS = ("by-nc", "noncommercial", "by-nd", "noderivs", "by-sa", "sharealike", "copyrighted")

LECTURE_TALKING_HEAD_MARKERS = (
    "lecture",
    "keynote",
    "webinar",
    "symposium",
    "press conference",
    "podcast",
    "panel discussion",
    "talking head",
)


@dataclass
class VideoCandidate:
    source_repo: str
    asset_id: str
    title: str
    description: str
    page_url: str
    download_url: str
    license_label: str
    width: int
    height: int
    human_interaction_score: float
    relevance_notes: str
    inferred_media_class: str = "REAL_VIDEO_ESTABLISHING"
    query_purpose: str = "general"


def _http_get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _score_human_interaction_text(title: str, description: str) -> float:
    blob = f"{title} {description}".lower()
    if any(bad in blob for bad in LECTURE_TALKING_HEAD_MARKERS):
        return 0.0
    hits = sum(1 for kw in HUMAN_INTERACTION_KEYWORDS if kw in blob)
    proc_hits = sum(1 for kw in ACTION_PROCESS_KEYWORDS if kw in blob)
    return round(min(10.0, hits * 1.5 + proc_hits * 1.2), 2)


def _infer_candidate_media_class(title: str, description: str) -> str:
    blob = f"{title} {description}".lower()
    if any(k in blob for k in ("animation", "simulation", "computer model", "cgi")):
        return "REAL_ANIMATION"
    if any(k in blob for k in ("time-lapse", "timelapse", "hyperlapse")):
        return "REAL_TIME_LAPSE"
    if any(k in blob for k in ACTION_PROCESS_KEYWORDS) or sum(1 for k in HUMAN_INTERACTION_KEYWORDS if k in blob) >= 2:
        return "REAL_VIDEO_ACTION"
    return "REAL_VIDEO_ESTABLISHING"


def _is_commercial_safe_license_string(lic: str) -> bool:
    low = lic.lower().strip()
    if not low:
        return False
    if any(b in low for b in BLOCKED_LICENSE_MARKERS):
        return False
    return any(
        ok in low
        for ok in (
            "public domain",
            "publicdomain",
            "pd",
            "cc0",
            "cc by 4.0",
            "cc by 3.0",
            "cc by 2.0",
            "cc-by",
            "creativecommons.org/licenses/by/",
            "creativecommons.org/publicdomain/",
        )
    )


def search_nasa_public_domain_videos(query: str, max_results: int = 8, purpose: str = "general") -> list[VideoCandidate]:
    """Query NASA Images & Video API (`Public Domain` federal media) and resolve direct MP4/MOV URLs."""
    url = "https://images-api.nasa.gov/search?media_type=video&q=" + urllib.parse.quote(query)
    out: list[VideoCandidate] = []
    try:
        data = _http_get_json(url)
    except Exception:
        return out

    for item in data.get("collection", {}).get("items", [])[:max_results]:
        meta = (item.get("data") or [{}])[0]
        nasa_id = str(meta.get("nasa_id", "")).strip()
        if not nasa_id:
            continue
        title = str(meta.get("title", "")).strip()
        desc = re.sub(r"\s+", " ", str(meta.get("description", "")).strip())
        credit_blob = f"{meta.get('secondary_creator', '')} {meta.get('photographer', '')} {desc}".lower()
        if any(bad in credit_blob for bad in ("copyright", "©", "all rights reserved", "used with permission", "not in the public domain")):
            continue
        if any(bad in f"{title} {desc}".lower() for bad in LECTURE_TALKING_HEAD_MARKERS):
            continue

        dl_url = ""
        try:
            asset_manifest = _http_get_json("https://images-api.nasa.gov/asset/" + urllib.parse.quote(nasa_id))
            hrefs = [
                str(x.get("href", "")).replace("http://", "https://")
                for x in asset_manifest.get("collection", {}).get("items", [])
            ]
            for pref in ("~large.mp4", "~orig.mp4", "~orig.mov", "~medium.mp4"):
                match = next((h for h in hrefs if h.endswith(pref)), None)
                if match:
                    dl_url = match
                    break
        except Exception:
            continue
        if not dl_url:
            continue

        h_score = _score_human_interaction_text(title, desc)
        mcls = _infer_candidate_media_class(title, desc)
        out.append(
            VideoCandidate(
                source_repo="nasa_images_api",
                asset_id=nasa_id,
                title=title,
                description=desc[:260],
                page_url=f"https://images.nasa.gov/details/{urllib.parse.quote(nasa_id)}",
                download_url=dl_url,
                license_label="Public Domain (NASA)",
                width=1920 if ("~large" in dl_url or "~orig" in dl_url) else 1280,
                height=1080 if ("~large" in dl_url or "~orig" in dl_url) else 720,
                human_interaction_score=h_score,
                relevance_notes="human_fieldwork_candidate" if h_score >= 3.0 else "authentic_nasa_video",
                inferred_media_class=mcls,
                query_purpose=purpose,
            )
        )
    return out


def search_wikimedia_commons_videos(
    query: str,
    max_results: int = 10,
    min_height: int = 720,
    purpose: str = "general",
) -> list[VideoCandidate]:
    """Query Wikimedia Commons `filetype:video` and keep only HD `Public Domain` / `CC0` / `CC BY` clips."""
    search_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&list=search&srnamespace=6"
        f"&srlimit={int(max_results)}&format=json&srsearch="
        + urllib.parse.quote(f"{query} filetype:video")
    )
    out: list[VideoCandidate] = []
    try:
        sdata = _http_get_json(search_url)
    except Exception:
        return out

    titles = [str(x.get("title", "")) for x in sdata.get("query", {}).get("search", []) if x.get("title")]
    if not titles:
        return out

    info_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&prop=imageinfo"
        "&iiprop=url|size|extmetadata&format=json&titles="
        + urllib.parse.quote("|".join(titles[:10]))
    )
    try:
        idata = _http_get_json(info_url)
    except Exception:
        return out

    for _, pg in idata.get("query", {}).get("pages", {}).items():
        title = str(pg.get("title", ""))
        ii = (pg.get("imageinfo") or [{}])[0]
        w = int(ii.get("width", 0) or 0)
        h = int(ii.get("height", 0) or 0)
        if h < min_height:
            continue
        ext = ii.get("extmetadata", {})
        lic = str(ext.get("LicenseShortName", {}).get("value", "")).strip()
        if not _is_commercial_safe_license_string(lic):
            continue
        desc_raw = str(ext.get("ImageDescription", {}).get("value", ""))
        desc = re.sub(r"<[^>]+>", " ", desc_raw)
        desc = re.sub(r"\s+", " ", desc).strip()
        if any(bad in f"{title} {desc}".lower() for bad in LECTURE_TALKING_HEAD_MARKERS):
            continue
        dl_url = str(ii.get("url", "")).split("?")[0]
        page_url = str(ii.get("descriptionurl", f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}"))
        h_score = _score_human_interaction_text(title, desc)
        mcls = _infer_candidate_media_class(title, desc)
        out.append(
            VideoCandidate(
                source_repo="wikimedia_commons",
                asset_id=title,
                title=title.replace("File:", ""),
                description=desc[:260],
                page_url=page_url,
                download_url=dl_url,
                license_label=lic,
                width=w,
                height=h,
                human_interaction_score=h_score,
                relevance_notes="human_fieldwork_candidate" if h_score >= 3.0 else "hd_open_video",
                inferred_media_class=mcls,
                query_purpose=purpose,
            )
        )
    return out


def search_internet_archive_videos(
    query: str,
    max_results: int = 6,
    purpose: str = "general",
) -> list[VideoCandidate]:
    """
    Query Internet Archive (`archive.org/advancedsearch.php`) for open commercial-safe
    (`Public Domain`, `CC0`, `CC BY`) scientific, federal, and expedition videos ($0 API).
    """
    q_expr = f"({query}) AND mediatype:(movies) AND (licenseurl:*publicdomain* OR licenseurl:*zero* OR licenseurl:*/by/*)"
    api_url = (
        "https://archive.org/advancedsearch.php?q="
        + urllib.parse.quote(q_expr)
        + f"&fl[]=identifier&fl[]=title&fl[]=description&fl[]=licenseurl&fl[]=creator&rows={int(max_results)}&page=1&output=json"
    )
    out: list[VideoCandidate] = []
    try:
        data = _http_get_json(api_url)
    except Exception:
        return out

    for doc in data.get("response", {}).get("docs", [])[:max_results]:
        ident = str(doc.get("identifier", "")).strip()
        if not ident:
            continue
        lic_url = str(doc.get("licenseurl", "")).strip()
        if not _is_commercial_safe_license_string(lic_url):
            continue
        title = str(doc.get("title", ident)).strip()
        raw_desc = doc.get("description", "")
        if isinstance(raw_desc, list):
            raw_desc = " ".join(str(x) for x in raw_desc)
        desc = re.sub(r"<[^>]+>", " ", str(raw_desc))
        desc = re.sub(r"\s+", " ", desc).strip()
        if any(bad in f"{title} {desc}".lower() for bad in LECTURE_TALKING_HEAD_MARKERS):
            continue

        lic_label = (
            "Public Domain"
            if "publicdomain" in lic_url.lower()
            else ("CC0" if "zero" in lic_url.lower() else "CC BY")
        )
        h_score = _score_human_interaction_text(title, desc)
        mcls = _infer_candidate_media_class(title, desc)
        out.append(
            VideoCandidate(
                source_repo="internet_archive",
                asset_id=ident,
                title=title,
                description=desc[:260],
                page_url=f"https://archive.org/details/{urllib.parse.quote(ident)}",
                download_url=f"https://archive.org/download/{urllib.parse.quote(ident)}",
                license_label=lic_label,
                width=1280,
                height=720,
                human_interaction_score=h_score,
                relevance_notes="open_archive_film",
                inferred_media_class=mcls,
                query_purpose=purpose,
            )
        )
    return out


def discover_documentary_videos(query: str, max_per_source: int = 8, include_internet_archive: bool = True) -> list[dict]:
    """
    Search NASA + Wikimedia Commons (+ Internet Archive) and rank genuine action footage
    above static/establishing clips.
    """
    cands = search_nasa_public_domain_videos(query, max_results=max_per_source) + search_wikimedia_commons_videos(
        query, max_results=max_per_source
    )
    if include_internet_archive:
        cands += search_internet_archive_videos(query, max_results=max(4, max_per_source // 2))

    seen_urls: set[str] = set()
    unique: list[VideoCandidate] = []
    for c in cands:
        key = c.download_url or c.page_url
        if key in seen_urls:
            continue
        seen_urls.add(key)
        unique.append(c)

    unique.sort(
        key=lambda c: (
            1 if c.inferred_media_class == "REAL_VIDEO_ACTION" else 0,
            c.human_interaction_score,
            c.height,
            c.width,
        ),
        reverse=True,
    )
    return [asdict(c) for c in unique]


def discover_footage_first_by_purpose(
    topic: str,
    beats: Optional[list[Any]] = None,
    max_per_query: int = 4,
    online: bool = True,
) -> dict[str, Any]:
    """
    Execute Subject + Action multi-intent footage discovery (Part 2 Section 3):
    Generates differentiated queries for sampling, fieldwork, environmental processes,
    equipment operation, close-ups, and establishing views, returning deduplicated
    footage candidates grouped by visual purpose.
    """
    from .action_storytelling import generate_footage_search_queries

    planned_queries = generate_footage_search_queries(topic, beats=beats)
    results_by_purpose: dict[str, list[dict[str, Any]]] = {}
    all_seen: set[str] = set()

    if online:
        for q_item in planned_queries[:8]:
            purp = q_item["purpose"]
            q_str = q_item["query"]
            found = (
                search_nasa_public_domain_videos(q_str, max_results=max_per_query, purpose=purp)
                + search_wikimedia_commons_videos(q_str, max_results=max_per_query, purpose=purp)
                + search_internet_archive_videos(q_str, max_results=max(2, max_per_query // 2), purpose=purp)
            )
            bucket = results_by_purpose.setdefault(purp, [])
            for fc in found:
                k = fc.download_url or fc.page_url
                if k in all_seen:
                    continue
                all_seen.add(k)
                bucket.append(asdict(fc))

    return {
        "topic": topic,
        "online_executed": online,
        "planned_queries": planned_queries,
        "total_unique_video_candidates": len(all_seen),
        "results_by_purpose": results_by_purpose,
    }


def audit_clip_real_motion(
    video_path: Path,
    start_s: float = 0.0,
    duration_s: float = 4.0,
    sample_fps: float = 8.0,
    metadata_hint: str = "",
) -> dict[str, Any]:
    """
    Inspect actual decoded frames from `video_path` using affine-compensated optical
    motion decomposition (`inspect_media_authenticity`) so BOTH frozen title cards AND
    Ken Burns pan/zoom animations over static JPEGs are rejected (`is_real_moving_footage=False`).
    """
    audit = inspect_media_authenticity(
        media_path=video_path,
        start_s=start_s,
        duration_s=duration_s,
        sample_fps=sample_fps,
        metadata_hint=metadata_hint,
    )
    return {
        "valid": audit.valid,
        "sampled_frames": audit.sampled_frames,
        "mean_temporal_diff": audit.raw_mean_diff,
        "median_temporal_diff": audit.raw_median_diff,
        "affine_compensated_diff": audit.affine_compensated_diff,
        "residual_to_raw_ratio": audit.residual_to_raw_ratio,
        "p90_local_flow_residual_px": audit.p90_local_flow_residual_px,
        "is_baked_animated_still": audit.is_baked_animated_still,
        "is_dense_presentation_graphic": audit.is_dense_presentation_graphic,
        "has_localized_action_motion": audit.has_localized_action_motion,
        "inferred_media_class": audit.inferred_media_class,
        "is_real_moving_footage": audit.is_real_moving_footage,
        "diagnostic_note": audit.diagnostic_note,
    }
