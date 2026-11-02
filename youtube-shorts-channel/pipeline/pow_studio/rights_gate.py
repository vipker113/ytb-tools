#!/usr/bin/env python3
"""
Step 2: Automated Commercial Rights & Provenance Gate (`pow_studio.rights_gate` v3.0).

Hard-blocks rendering if any visual or audio asset lacks verified commercial-reuse
clearance (Public Domain, CC0, CC BY, or 100% first-party original) or originates
from unverified stock folders (such as `MoneyPrinterTurbo/resource/songs/`).
Maintains a complete off-screen source & attribution register (`source_register.csv` / `.md`)
so visible source banners can be cleanly omitted from the video without ever omitting
legally required attribution.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from .schema import EpisodeManifest

HEADERS = {
    "User-Agent": "ProofOfWonderRightsGate/3.0 (https://github.com/proof-of-wonder; commercial-compliance-audit)"
}

FORBIDDEN_LICENSE_TOKENS = (
    "NC",
    "NONCOMMERCIAL",
    "NON-COMMERCIAL",
    "ND",
    "NODERIV",
    "NO-DERIV",
    "NO DERIV",
    "ALL RIGHTS RESERVED",
    "FAIR USE",
    "UNVERIFIED",
    "UNKNOWN",
    "EDITORIAL ONLY",
)

ALLOWED_COMMERCIAL_PREFIXES = (
    "PUBLIC DOMAIN",
    "CC0",
    "CC BY",
    "CC-BY",
    "CREATIVE COMMONS ATTRIBUTION",
    "100% ORIGINAL",
    "FIRST-PARTY",
)


class RightsViolationError(RuntimeError):
    """Raised when an asset fails commercial licensing or provenance checks."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def validate_license_string(lic: str, asset_name: str) -> None:
    norm = re.sub(r"\s+", " ", lic.strip()).upper()
    if not norm:
        raise RightsViolationError(f"[{asset_name}] Empty license string.")

    words = set(re.split(r"[^A-Z0-9]+", norm))
    if "NC" in words or "ND" in words:
        raise RightsViolationError(f"[{asset_name}] Prohibited NonCommercial/NoDerivatives license: '{lic}'")

    for bad in FORBIDDEN_LICENSE_TOKENS[2:]:
        if bad in norm:
            raise RightsViolationError(f"[{asset_name}] Prohibited or unverified license '{lic}' (matched '{bad}').")

    if "SA" in words or "SHAREALIKE" in norm or "SHARE-ALIKE" in norm:
        raise RightsViolationError(
            f"[{asset_name}] ShareAlike (CC BY-SA) license '{lic}' requires viral relicensing of the entire video; use Public Domain, CC0, or CC BY instead."
        )

    if not any(norm.startswith(p) or p in norm for p in ALLOWED_COMMERCIAL_PREFIXES):
        raise RightsViolationError(f"[{asset_name}] License '{lic}' is not in commercial-safe whitelist (PD / CC0 / CC BY / Original).")


def _verify_commons_api(source_page_url: str, cache: dict) -> dict:
    if source_page_url in cache:
        return cache[source_page_url]
    parsed = urllib.parse.urlparse(source_page_url)
    if "commons.wikimedia.org" not in parsed.netloc or "/wiki/File:" not in parsed.path:
        return {"api_checked": False}

    file_title = "File:" + urllib.parse.unquote(parsed.path.split("/wiki/File:", 1)[1]).replace("_", " ")
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": file_title,
            "prop": "imageinfo",
            "iiprop": "extmetadata|url",
            "format": "json",
        }
    )
    try:
        req = urllib.request.Request(f"https://commons.wikimedia.org/w/api.php?{params}", headers=HEADERS)
        payload = json.loads(urllib.request.urlopen(req, timeout=15).read().decode("utf-8"))
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values()), {})
        ii = (page.get("imageinfo") or [{}])[0]
        ext = ii.get("extmetadata", {})
        api_lic = re.sub(r"<[^>]+>", "", ext.get("LicenseShortName", {}).get("value", "")).strip()
        nonfree = ext.get("NonFree", {}).get("value", "").strip().lower()
        res = {
            "api_checked": True,
            "commons_license": api_lic,
            "nonfree": nonfree == "true",
        }
        cache[source_page_url] = res
        return res
    except Exception as exc:
        return {"api_checked": False, "note": f"offline_or_timeout ({exc})"}


def run_rights_gate(manifest: EpisodeManifest, verify_online: bool = True) -> list[dict]:
    """
    Validate all assets, soundbites, and references in `manifest`.
    Writes `source_register.csv` and `source_register.md` to `manifest.output_dir`.
    """
    search_dirs = manifest.all_asset_search_dirs()
    out_dir = Path(manifest.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_path = out_dir / ".rights_verification_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    for sb in manifest.soundbites:
        if "MoneyPrinterTurbo/resource/songs" in sb.audio_file:
            raise RightsViolationError(f"Soundbite {sb.bite_id} references unverified MoneyPrinterTurbo stock audio!")

    shot_usage: dict[str, list[str]] = {}
    for s in manifest.shots:
        shot_usage.setdefault(s.src_file, []).append(f"{s.sid} ({s.start_s:.2f}–{s.end_s:.2f}s)")
        if s.secondary_src_file:
            shot_usage.setdefault(s.secondary_src_file, []).append(f"{s.sid} ({s.start_s:.2f}–{s.end_s:.2f}s)")
    if manifest.thumbnail_spec and manifest.thumbnail_spec.src_file:
        shot_usage.setdefault(manifest.thumbnail_spec.src_file, []).append("thumbnail")

    verified_rows = []
    for idx, asset in enumerate(manifest.assets_register, 1):
        if "MoneyPrinterTurbo/resource/songs" in asset.local_file or "MoneyPrinterTurbo/resource/songs" in asset.direct_media_url:
            raise RightsViolationError(f"[{asset.local_file}] Unverified MoneyPrinterTurbo/resource/songs MP3 is prohibited.")

        validate_license_string(asset.license, asset.local_file)

        candidate_paths = [d / asset.local_file for d in search_dirs] + [Path(asset.local_file)]
        resolved = next((p for p in candidate_paths if p.exists()), None)
        if resolved is None and not asset.is_first_party_original:
            raise RightsViolationError(
                f"[{asset.local_file}] Asset file missing on disk (checked {[str(d) for d in search_dirs]})."
            )

        sha16 = _sha256_file(resolved) if resolved and resolved.exists() else "generated-on-build"
        api_info = (
            _verify_commons_api(asset.source_page_url, cache)
            if (verify_online and not asset.is_first_party_original)
            else {"api_checked": False}
        )
        if api_info.get("api_checked"):
            if api_info.get("nonfree"):
                raise RightsViolationError(f"[{asset.local_file}] Commons API marked NonFree=true!")
            if api_info.get("commons_license"):
                validate_license_string(api_info["commons_license"], f"{asset.local_file} [Commons API]")

        verified_rows.append(
            {
                "asset_index": idx,
                "local_file": asset.local_file,
                "media_type": asset.media_type or "photo",
                "priority_tier": asset.priority_tier,
                "sha256_16": sha16,
                "used_in_shots": ", ".join(shot_usage.get(asset.local_file, ["(registered/aux)"])),
                "intended_use": asset.intended_use,
                "title": asset.title,
                "creator_agency": asset.creator_agency,
                "license": asset.license,
                "license_url": asset.license_url,
                "api_verified": "YES (Commons API)"
                if api_info.get("api_checked")
                else ("FIRST-PARTY" if asset.is_first_party_original else "DECLARED-URL"),
                "source_page_url": asset.source_page_url,
                "direct_media_url": asset.direct_media_url,
                "required_attribution": asset.required_attribution,
            }
        )

    cache_path.write_text(json.dumps(cache, indent=2))

    csv_path = out_dir / "source_register.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(verified_rows[0].keys()))
        w.writeheader()
        w.writerows(verified_rows)

    md_lines = [
        f"# Source & Commercial Licensing Register — {manifest.channel_name}: {manifest.playlist} (`{manifest.slug}`)",
        "",
        "Automated `pow_studio.rights_gate` v3.0 passed with **0 commercial-rights violations**.",
        "Visible source banners inside the video are disabled by default per `pow_documentary_v3`; all required media attributions are preserved below and injected automatically into `youtube_metadata.md`.",
        "",
        "## 1. Cleared Visual & Media Assets",
        "",
        "| # | File (`SHA-256`) | Type (Tier) | Shots | Creator / Agency | License | Verification | Source | Required Attribution |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in verified_rows:
        src_link = f"[Link]({r['source_page_url']})" if r["source_page_url"].startswith("http") else r["source_page_url"]
        md_lines.append(
            f"| {r['asset_index']} | `{r['local_file']}` (`{r['sha256_16']}`) | `{r['media_type']}` (T{r['priority_tier']}) | `{r['used_in_shots']}` | {r['creator_agency']} | `{r['license']}` | `{r['api_verified']}` | {src_link} | {r['required_attribution']} |"
        )

    if manifest.excluded_sources_notes:
        md_lines.extend(["", "## 2. Deliberately Excluded Candidate Sources (Rights / Scientific Accuracy Gate)", ""])
        for note in manifest.excluded_sources_notes:
            md_lines.append(f"- {note}")

    md_lines.extend(["", "## 3. Factual Scientific References", ""])
    for ref in manifest.factual_references:
        doi_str = f" (`DOI: {ref.doi}`)" if ref.doi else ""
        md_lines.append(f"- **{ref.citation}**{doi_str} — {ref.url}  \n  *Supports:* {ref.supported_claims}")

    (out_dir / "source_register.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return verified_rows
