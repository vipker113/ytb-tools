"""
U.S. National Archives (NARA) Catalog API v2 adapter — optional, enabled only with `NARA_API_KEY`.

Only records whose use restriction is "Unrestricted" are kept. The response parser is defensive
because the key (requested by email) was not yet available when this adapter was written; it must
be validated against live responses once `NARA_API_KEY` is set.
"""

from __future__ import annotations

import os
import urllib.parse
from typing import Any

from .base import LicenseEvidence, VideoCandidate, http_request, now_iso, strip_html

API = "https://catalog.archives.gov/api/v2/records/search"
VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".mpg", ".mpeg", ".avi", ".wmv", ".webm")


def _load_key() -> str:
    key = os.environ.get("NARA_API_KEY", "").strip()
    if key:
        return key
    from .base import CHANNEL_ROOT

    env_p = CHANNEL_ROOT / ".env"
    if env_p.exists():
        for ln in env_p.read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("NARA_API_KEY="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _records(payload: Any) -> list[dict[str, Any]]:
    hits = (((payload or {}).get("body") or {}).get("hits") or {}).get("hits") or []
    out = []
    for h in hits:
        src = h.get("_source") or {}
        rec = src.get("record") or src
        if isinstance(rec, dict):
            out.append(rec)
    return out


class NaraSource:
    name = "nara"
    display_name = "U.S. National Archives (optional)"

    @property
    def default_enabled(self) -> bool:
        return bool(_load_key())

    def is_available(self) -> tuple[bool, str]:
        return (True, "NARA_API_KEY set") if _load_key() else (False, "set NARA_API_KEY in youtube-shorts-channel/.env")

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        key = _load_key()
        if not key:
            return []
        url = API + "?" + urllib.parse.urlencode({"q": query, "typeOfMaterials": "Moving Images", "limit": int(limit)})
        try:
            payload = http_request(url, headers={"x-api-key": key, "Content-Type": "application/json"})
        except RuntimeError:
            return []
        out: list[VideoCandidate] = []
        for rec in _records(payload):
            restriction = str(((rec.get("useRestriction") or {}).get("status")) or "").lower()
            if restriction != "unrestricted":
                continue
            naid = str(rec.get("naId", ""))
            title = strip_html(str(rec.get("title", naid)))
            desc = strip_html(str(rec.get("scopeAndContentNote", "")))[:400]
            for obj in rec.get("digitalObjects") or []:
                ourl = str(obj.get("objectUrl") or obj.get("url") or "")
                if not ourl.lower().endswith(VIDEO_EXTS):
                    continue
                page_url = f"https://catalog.archives.gov/id/{naid}"
                evidence = LicenseEvidence(
                    source_repo=self.name,
                    page_url=page_url,
                    raw_rights_text=f"useRestriction.status={restriction}",
                    normalized_license="Public Domain (NARA)",
                    license_url="https://www.archives.gov/global-pages/privacy.html#copyright",
                    required_attribution="U.S. National Archives and Records Administration",
                    fetched_at=now_iso(),
                    verified=True,
                )
                out.append(
                    VideoCandidate(
                        source_repo=self.name,
                        asset_id=f"nara-{naid}-{ourl.rsplit('/', 1)[-1]}",
                        title=title,
                        description=desc,
                        page_url=page_url,
                        download_url=ourl,
                        license_label="Public Domain (NARA)",
                        width=0,
                        height=0,
                        human_interaction_score=0.0,
                        relevance_notes="nara_archival_film",
                        inferred_media_class="REAL_VIDEO_ESTABLISHING",
                        query_purpose=purpose,
                        required_attribution=evidence.required_attribution,
                        license_url=evidence.license_url,
                        creator_agency="NARA",
                        source_flags=["archival_verify_era", "verify_resolution"],
                        license_evidence=evidence.to_dict(),
                    )
                )
                break
        return out
