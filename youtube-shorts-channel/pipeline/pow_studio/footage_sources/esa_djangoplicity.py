"""
ESA/Webb (esawebb.org) and ESA/Hubble (esahubble.org) video adapter — CC BY 4.0 with mandatory credit.

Policy notes (https://esawebb.org/copyright/):
- Credit line from the page is mandatory and must be visible (we put it in the description/credits).
- No logos, no implied ESA endorsement, identifiable people need separate consent → such items skipped.
- Credits often list "Music: ..." → third-party music → audio stripped on download.
- Most items are pans/zooms over stills or artist animations → never treated as camera footage.
"""

from __future__ import annotations

import re
import urllib.parse

from .base import LicenseEvidence, VideoCandidate, http_request, now_iso, strip_html

ANIMATED_STILL_HINTS = re.compile(r"\b(pan|panning|zoom|zooming|close[- ]up of|flight through|fly[- ]?through|3d|tour of)\b", re.I)
ANIMATION_HINTS = re.compile(r"\b(artist'?s|animation|impression|illustration|simulation|visuali[sz]ation|cgi)\b", re.I)
PEOPLE_HINTS = re.compile(r"\b(interview|astronaut|portrait|scientist talks|presenter|podcast|episode|briefing|press)\b", re.I)
FORMAT_PREF = ("hd_1080p25_screen", "hd_and_apple", "ultra_hd", "medium_podcast")


class EsaDjangoplicitySource:
    default_enabled = True

    def __init__(self, site: str, name: str, display_name: str, max_items: int = 8) -> None:
        self.site = site
        self.name = name
        self.display_name = display_name
        self.max_items = max_items

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def _detail(self, vid: str) -> dict:
        page_url = f"https://{self.site}/videos/{vid}/"
        html = http_request(page_url, as_json=False)
        title_m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
        title = strip_html(title_m.group(1)).split(" | ")[0] if title_m else vid
        credit_m = re.search(r'<div class="credit">(.*?)</div>', html, re.S | re.I)
        credit_raw = strip_html(credit_m.group(1)) if credit_m else ""
        desc_m = re.search(r'<div class="col-md-9[^"]*"[^>]*>(.*?)<strong>Credit', html, re.S | re.I)
        desc = strip_html(desc_m.group(1))[:500] if desc_m else ""
        site_re = re.escape(self.site)
        links = re.findall(rf"https?://cdn\.{site_re}/archives/videos/([a-z0-9_]+)/{re.escape(vid)}\.(mp4|m4v|mov)", html)
        files = {fmt: f"https://cdn.{self.site}/archives/videos/{fmt}/{vid}.{ext}" for fmt, ext in links}
        return {"page_url": page_url, "title": title, "credit": credit_raw, "desc": desc, "files": files}

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        search_url = f"https://{self.site}/videos/?" + urllib.parse.urlencode({"search": query})
        try:
            html = http_request(search_url, as_json=False)
        except RuntimeError:
            return []
        ids = []
        for vid in re.findall(r'href="/videos/([a-z0-9]+)/"', html):
            if vid in ("search", "feed", "archive", "page", "list") or vid in ids:
                continue
            ids.append(vid)
        out: list[VideoCandidate] = []
        for vid in ids[: min(limit, self.max_items)]:
            try:
                d = self._detail(vid)
            except RuntimeError:
                continue
            blob = f"{d['title']} {d['desc']}"
            if PEOPLE_HINTS.search(blob):
                continue
            url = next((d["files"][f] for f in FORMAT_PREF if f in d["files"]), "")
            if not url:
                continue
            credit_lines = [ln.strip() for ln in d["credit"].split("\n") if ln.strip()]
            visual_credit = " ".join(ln for ln in credit_lines if not ln.lower().startswith("music"))
            has_music = any(ln.lower().startswith("music") for ln in credit_lines)
            if ANIMATION_HINTS.search(blob):
                mclass = "REAL_ANIMATION"
            elif ANIMATED_STILL_HINTS.search(blob):
                mclass = "ANIMATED_STILL"
            else:
                mclass = "SCIENTIFIC_IMAGE"
            attribution = f"{visual_credit or self.display_name} ({self.display_name}, CC BY 4.0)"
            evidence = LicenseEvidence(
                source_repo=self.name,
                page_url=d["page_url"],
                raw_rights_text=f"Credit: {d['credit']} | Policy: https://{self.site}/copyright/ (CC BY 4.0 unless stated)",
                normalized_license="CC BY 4.0",
                license_url="https://creativecommons.org/licenses/by/4.0/",
                required_attribution=attribution,
                fetched_at=now_iso(),
                verified=True,
                notes="Cropped/reframed to 9:16 — state modification in credits. No ESA logos, no endorsement.",
            )
            out.append(
                VideoCandidate(
                    source_repo=self.name,
                    asset_id=f"{self.name}-{vid}",
                    title=d["title"],
                    description=d["desc"],
                    page_url=d["page_url"],
                    download_url=url,
                    license_label="CC BY 4.0",
                    width=1920 if "1080p" in url or "hd_and_apple" in url else (3840 if "ultra_hd" in url else 1280),
                    height=1080 if "1080p" in url or "hd_and_apple" in url else (2160 if "ultra_hd" in url else 720),
                    human_interaction_score=0.0,
                    relevance_notes=f"{self.name}_video",
                    inferred_media_class=mclass,
                    query_purpose=purpose,
                    preview_image_url=f"https://cdn.{self.site}/archives/videos/videoframe/{vid}.jpg",
                    license_url=evidence.license_url,
                    required_attribution=attribution,
                    creator_agency=visual_credit or self.display_name,
                    third_party_audio_risk=True,  # ESA videos commonly embed licensed music
                    source_flags=["not_camera_footage"] + (["credited_music"] if has_music else []),
                    license_evidence=evidence.to_dict(),
                )
            )
        return out
