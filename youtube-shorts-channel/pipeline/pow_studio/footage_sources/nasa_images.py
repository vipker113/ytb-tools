"""NASA Image & Video Library adapter (Public Domain). Wraps the proven v8 search and adds v9 metadata."""

from __future__ import annotations

import urllib.parse

from .base import LicenseEvidence, VideoCandidate, now_iso


class NasaImagesSource:
    name = "nasa_images"
    display_name = "NASA Image & Video Library"
    default_enabled = True

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        from ..video_sourcing import search_nasa_public_domain_videos

        out = search_nasa_public_domain_videos(query, max_results=limit, purpose=purpose)
        for c in out:
            c.source_repo = self.name
            nid = urllib.parse.quote(c.asset_id)
            c.preview_image_url = f"https://images-assets.nasa.gov/video/{nid}/{nid}~thumb.jpg"
            c.creator_agency = "NASA"
            c.required_attribution = "NASA (Public Domain)"
            c.license_url = "https://www.nasa.gov/nasa-brand-center/images-and-media/"
            c.license_evidence = LicenseEvidence(
                source_repo=self.name,
                page_url=c.page_url,
                raw_rights_text="NASA Image and Video Library item; no copyright/permission markers in credit metadata.",
                normalized_license="Public Domain (NASA)",
                license_url=c.license_url,
                required_attribution=c.required_attribution,
                fetched_at=now_iso(),
                verified=True,
            ).to_dict()
        return out
