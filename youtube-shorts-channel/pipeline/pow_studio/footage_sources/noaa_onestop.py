"""
NOAA Ocean Exploration adapter via the public NOAA OneStop granule search API (Public Domain).

Finding (2026-11 spike): direct HTTP links are the portal's compressed `*_Low.mp4` (640x360);
HD masters require the NCEI order basket. Candidates are therefore flagged `low_res_lead`:
they prove footage exists and pinpoint the dive/segment, but are not used as 1080x1920 masters.
"""

from __future__ import annotations

import re

from .base import LicenseEvidence, VideoCandidate, http_request, now_iso

ONESTOP = "https://data.noaa.gov/onestop/api/search/search/granule"
FORMATS = [
    "MP4 WRAPPED/.MP4, CODEC=H.264, 360P, 1.5MBPS",
    "HIGH RESOLUTION FILE: MP4 (MPEG 4), CODEC=H.264, 720X480 PIXELS, 63MB/MIN, AUDIO 48 KHZ & 128 KBPS. "
    "LOW RESOLUTION: MP4 WRAPPED/.MP4, CODEC=H.264, 360P, 1.5MBPS.",
]


class NoaaOneStopSource:
    name = "noaa_onestop"
    display_name = "NOAA Ocean Exploration (OneStop)"
    default_enabled = True

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        body = {
            "queries": [{"type": "queryText", "value": query}],
            "filters": [
                {"type": "facet", "name": "projects", "values": ["NOAAOceanExploration"]},
                {"type": "facet", "name": "dataFormats", "values": FORMATS},
            ],
            "facets": False,
            "page": {"max": int(limit), "offset": 0},
        }
        try:
            res = http_request(ONESTOP, method="POST", json_body=body)
        except RuntimeError:
            return []
        out: list[VideoCandidate] = []
        for g in res.get("data", [])[:limit]:
            a = g.get("attributes", {}) or {}
            links = a.get("links") or []
            mp4 = next((str(l.get("linkUrl", "")) for l in links if str(l.get("linkUrl", "")).lower().endswith(".mp4")), "")
            portal = next((str(l.get("linkUrl", "")) for l in links if "oerkey=" in str(l.get("linkUrl", ""))), "")
            if not mp4:
                continue
            title = str(a.get("title", "")).strip()
            cam = "ROV" if "ROVHD" in mp4 else ("camera platform" if "CPHD" in mp4 else "camera")
            low = mp4.endswith("_Low.mp4")
            dive = re.search(r"(EX\d{4})_.*?(DIVE\d+)", mp4)
            asset_id = mp4.rsplit("/", 1)[-1]
            evidence = LicenseEvidence(
                source_repo=self.name,
                page_url=portal or mp4,
                raw_rights_text="NOAA Ocean Exploration video (U.S. Government work, public domain). Credit requested.",
                normalized_license="Public Domain (NOAA)",
                license_url="https://oceanexplorer.noaa.gov/image-use.html",
                required_attribution="Video courtesy of NOAA Ocean Exploration",
                fetched_at=now_iso(),
                verified=True,
            )
            out.append(
                VideoCandidate(
                    source_repo=self.name,
                    asset_id=asset_id,
                    title=f"{title} ({cam})",
                    description=f"NOAA Okeanos Explorer {dive.group(1) + ' ' + dive.group(2) if dive else ''} {cam} footage. Query: {query}",
                    page_url=portal or mp4,
                    download_url=mp4,
                    license_label="Public Domain (NOAA)",
                    width=640 if low else 0,
                    height=360 if low else 0,
                    human_interaction_score=1.5 if cam == "ROV" else 0.0,
                    relevance_notes="noaa_rov_segment",
                    inferred_media_class="REAL_VIDEO_ACTION" if cam == "ROV" else "REAL_VIDEO_ESTABLISHING",
                    query_purpose=purpose,
                    required_attribution=evidence.required_attribution,
                    license_url=evidence.license_url,
                    creator_agency="NOAA Ocean Exploration",
                    source_flags=["low_res_lead"] if low else [],
                    license_evidence=evidence.to_dict(),
                )
            )
        return out
