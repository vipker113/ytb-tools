"""Wikimedia Commons video adapter (PD / CC0 / CC BY only) with poster frames for visual pre-screening."""

from __future__ import annotations

import urllib.parse

from .base import LicenseEvidence, VideoCandidate, http_request, license_is_commercial_safe, now_iso, strip_html

API = "https://commons.wikimedia.org/w/api.php"

KNOWN_AGENCIES = {
    "ifremer": "Ifremer", "noaa": "NOAA", "nasa": "NASA", "usgs": "USGS", "nps.gov": "U.S. National Park Service",
    "esa": "ESA", "terra x": "ZDF Terra X", "schmidt ocean": "Schmidt Ocean Institute", "mbari": "MBARI",
}


def clean_commons_credit(artist: str, credit: str, credit_html: str, title: str) -> str:
    """Commons templates often render 'null, null'; the Credit field is frequently just a link titled
    like the file. Prefer a real artist, else the agency from the file title or the credit link domain."""
    import re

    a = re.sub(r"\bnull\b", "", artist or "", flags=re.I)
    a = re.sub(r"[\s,;]+", " ", a).strip(" ,;")
    if a:
        return a[:200]
    m = re.search(r"\(([A-Za-z][A-Za-z .&-]{1,40}?)\s+[\d][\d\- ]*\)", title or "")
    if m:
        return m.group(1).strip()
    blob = f"{credit_html} {credit} {title}".lower()
    for needle, name in KNOWN_AGENCIES.items():
        if needle in blob:
            return name
    c = (credit or "").strip()
    return c[:200] if c and c.lower() not in (title or "").lower() else "Wikimedia Commons contributor"


class WikimediaCommonsSource:
    name = "wikimedia"
    display_name = "Wikimedia Commons"
    default_enabled = True

    def __init__(self, min_height: int = 720) -> None:
        self.min_height = min_height

    def is_available(self) -> tuple[bool, str]:
        return True, "no key required"

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]:
        from ..video_sourcing import LECTURE_TALKING_HEAD_MARKERS, _infer_candidate_media_class, _score_human_interaction_text

        s_url = f"{API}?" + urllib.parse.urlencode(
            {
                "action": "query",
                "list": "search",
                "srnamespace": 6,
                "srlimit": int(limit),
                "format": "json",
                "srsearch": f"{query} filetype:video",
            }
        )
        try:
            sdata = http_request(s_url)
        except RuntimeError:
            return []
        titles = [str(x.get("title", "")) for x in sdata.get("query", {}).get("search", []) if x.get("title")]
        if not titles:
            return []
        i_url = f"{API}?" + urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url|size|mediatype|extmetadata",
                "iiurlwidth": 640,
                "format": "json",
                "titles": "|".join(titles[:20]),
            }
        )
        try:
            idata = http_request(i_url)
        except RuntimeError:
            return []

        out: list[VideoCandidate] = []
        for pg in idata.get("query", {}).get("pages", {}).values():
            title = str(pg.get("title", ""))
            ii = (pg.get("imageinfo") or [{}])[0]
            w, h = int(ii.get("width") or 0), int(ii.get("height") or 0)
            if h < self.min_height:
                continue
            ext = ii.get("extmetadata", {}) or {}

            def _v(key: str) -> str:
                return strip_html(str((ext.get(key) or {}).get("value", "")))

            lic = _v("LicenseShortName")
            if not lic or not license_is_commercial_safe(lic) or _v("NonFree").lower() == "true":
                continue
            desc = _v("ImageDescription")
            if any(bad in f"{title} {desc}".lower() for bad in LECTURE_TALKING_HEAD_MARKERS):
                continue
            artist = _v("Artist")
            credit = _v("Credit")
            attribution = clean_commons_credit(artist, credit, str((ext.get("Credit") or {}).get("value", "")), title)
            page_url = str(ii.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}")
            evidence = LicenseEvidence(
                source_repo=self.name,
                page_url=page_url,
                raw_rights_text=f"LicenseShortName={lic}; UsageTerms={_v('UsageTerms')}; Artist={artist}; Credit={credit}",
                normalized_license=lic,
                license_url=_v("LicenseUrl"),
                required_attribution=f"{attribution} ({lic})",
                fetched_at=now_iso(),
                verified=True,
            )
            out.append(
                VideoCandidate(
                    source_repo=self.name,
                    asset_id=title,
                    title=title.replace("File:", ""),
                    description=desc[:400],
                    page_url=page_url,
                    download_url=str(ii.get("url", "")).split("?")[0],
                    license_label=lic,
                    width=w,
                    height=h,
                    human_interaction_score=_score_human_interaction_text(title, desc),
                    relevance_notes="hd_open_video",
                    inferred_media_class=_infer_candidate_media_class(title, desc),
                    query_purpose=purpose,
                    preview_image_url=str(ii.get("thumburl", "")).split("?")[0],
                    duration_s=float(ii.get("duration") or 0.0),
                    license_url=_v("LicenseUrl"),
                    required_attribution=evidence.required_attribution,
                    creator_agency=attribution,
                    license_evidence=evidence.to_dict(),
                )
            )
        return out
