#!/usr/bin/env python3
"""
Stage 4: Advanced Cinematic Visual Intelligence & Configurable 7-Criterion
Asset Relevance Scorer (`pow_studio.visual_intelligence` v6.0).

Implements Part 3 (Sections 4.1-4.5) of the Proof of Wonder Documentary Studio:
1. Configurable 7-Criterion Weighted Asset Scoring (`VisualScoringWeightsConfig`):
   - Direct relevance to narration (`30%` default)
   - Visual clarity and subject recognition (`20%` default)
   - Actual footage and authenticity (`20%` default)
   - Resolution and technical quality (`10%` default)
   - Composition and cinematic potential (`10%` default)
   - Motion and storytelling value (`5%` default)
   - Source and licensing verification (`5%` default)
2. Hard Documentary Guardrails:
   - Visually beautiful but irrelevant assets (`direct_relevance < min_direct_relevance_floor`)
     are flagged ineligible so they can NEVER be chosen merely for visual variety.
   - High-quality authentic photographs naturally outrank misleading/proxy video clips.
   - AI-generated imagery is scored `0.0` for authenticity and barred from real-evidence shots.
3. Multi-Archive Zero-Cost (`$0`) Photo & Video Discovery with strict institutional credit
   screening (NASA Images API + Wikimedia Commons API covering NOAA, USGS, ESA CC-BY, NPS,
   universities, and peer-reviewed journals).
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageOps

from .reframing import evaluate_crop_feasibility, measure_post_crop_sharpness
from .rights_gate import RightsViolationError, validate_license_string
from .style_profile import VisualScoringWeightsConfig
from .video_sourcing import (
    USER_AGENT,
    _http_get_json,
    _is_commercial_safe_license_string,
    audit_clip_real_motion,
    search_nasa_public_domain_videos,
    search_wikimedia_commons_videos,
)

THIRD_PARTY_RESTRICTION_MARKERS = (
    "copyright",
    "©",
    "all rights reserved",
    "used with permission",
    "permission of",
    "courtesy of",
    "not in the public domain",
    "non-commercial",
    "by-nc",
    "by-nd",
)

STOP_TOKENS = {
    "the", "and", "for", "with", "from", "into", "under", "over", "that", "this",
    "these", "those", "their", "there", "where", "when", "what", "which", "while",
    "hits", "sits", "comes", "shows", "showing", "right", "across", "around",
}


def nasa_metadata_is_clean_public_domain(meta: dict[str, Any]) -> tuple[bool, str]:
    """
    Verify NASA Images API item metadata does NOT carry third-party copyright notices
    (Part 3, Section 4.1: 'Do not assume that all material from an institution is
    automatically free for commercial reuse. Check the actual asset's usage conditions,
    credits, and third-party restrictions.').
    """
    sec_creator = str(meta.get("secondary_creator", "") or "")
    photographer = str(meta.get("photographer", "") or "")
    desc = str(meta.get("description", "") or "")
    center = str(meta.get("center", "") or "")
    combined = f"{sec_creator} {photographer} {desc}".lower()

    for bad in THIRD_PARTY_RESTRICTION_MARKERS:
        if bad in combined:
            return (False, f"Excluded due to potential third-party restriction marker ('{bad}') in NASA metadata.")
    return (True, f"Public Domain (NASA {center or 'Federal Archive'})")


@dataclass
class AssetScoreBreakdown:
    asset_id: str
    media_type: str  # "video", "photo", "diagram", "ai_generated"
    narration_target: str
    direct_relevance: float
    visual_clarity: float
    authenticity: float
    technical_quality: float
    composition_potential: float
    motion_storytelling: float
    license_verification: float
    weighted_score: float
    eligible_for_selection: bool
    disqualification_reason: str = ""


def _semantic_keyword_relevance(narration_text: str, asset_text: str, subject_match_kind: str = "") -> float:
    ntoks = {
        w.lower()
        for w in re.findall(r"[a-zA-Z0-9]{3,}", narration_text)
        if w.lower() not in STOP_TOKENS
    }
    atoks = {
        w.lower()
        for w in re.findall(r"[a-zA-Z0-9]{3,}", asset_text)
        if w.lower() not in STOP_TOKENS
    }
    if not ntoks:
        lexical = 0.55
    else:
        hits = len(ntoks & atoks)
        lexical = min(1.0, hits / float(max(1, min(len(ntoks), 4))))

    match_prior = {
        "direct_subject": 0.96,
        "direct_location": 0.86,
        "contextual_fieldwork": 0.78,
        "representative_organism_microscopy": 0.70,
        "illustrative_diagram": 0.65,
        "unrelated": 0.08,
    }.get(subject_match_kind, 0.0)

    if subject_match_kind == "unrelated":
        return round(min(0.25, 0.5 * lexical + 0.05), 3)
    if match_prior > 0.0:
        return round(min(1.0, 0.62 * match_prior + 0.38 * max(0.35, lexical)), 3)
    return round(lexical, 3)


def score_asset_candidate(
    asset_id: str,
    narration_text: str,
    asset_metadata_text: str,
    media_type: str,
    license_str: str,
    width: int = 1920,
    height: int = 1080,
    subject_match_kind: str = "",
    is_authentic_real_capture: bool = True,
    is_ai_generated: bool = False,
    has_verified_motion: Optional[bool] = None,
    sharpness_laplacian_std: Optional[float] = None,
    allow_cropping: bool = True,
    weights: Optional[VisualScoringWeightsConfig] = None,
) -> AssetScoreBreakdown:
    """
    Compute the 7-dimension weighted documentary relevance score (`[0.0 .. 1.0]`).
    Enforces:
    1. Commercial license compliance (`RightsViolationError` -> `license_verification = 0.0`, ineligible).
    2. Direct relevance floor (`< min_direct_relevance_floor` -> ineligible regardless of visual beauty).
    3. Authentic high-res photo preference over misleading/irrelevant video.
    4. Zero AI-generated imagery posing as real evidence.
    """
    w = weights or VisualScoringWeightsConfig()
    disq: list[str] = []

    # 1. Direct relevance to narration (default 30%)
    rel = _semantic_keyword_relevance(narration_text, asset_metadata_text, subject_match_kind=subject_match_kind)
    if rel < w.min_direct_relevance_floor:
        disq.append(
            f"Direct relevance ({rel:.2f}) is below floor ({w.min_direct_relevance_floor:.2f}); "
            "visually attractive but irrelevant assets cannot be selected."
        )

    # 2. Visual clarity & subject recognition (default 20%)
    if sharpness_laplacian_std is not None:
        clarity = min(1.0, max(0.15, sharpness_laplacian_std / 12.0))
    else:
        clarity = 0.88 if min(width, height) >= 720 else (0.65 if min(width, height) >= 540 else 0.35)

    # 3. Actual footage & authenticity (default 20%)
    if is_ai_generated:
        auth = 0.0
        disq.append("AI-generated imagery is never permitted as documentary visual evidence.")
    elif is_authentic_real_capture and media_type == "video":
        auth = 1.0 if subject_match_kind in ("direct_subject", "direct_location", "") else 0.90
    elif is_authentic_real_capture and media_type == "photo":
        auth = 0.92 if subject_match_kind in ("direct_subject", "direct_location", "") else 0.84
    elif media_type == "diagram":
        auth = 0.62
    else:
        auth = 0.20

    # 4. Resolution & technical quality (default 10%)
    feas = evaluate_crop_feasibility(
        width,
        height,
        contains_wide_axes_or_text=not allow_cropping,
    )
    if height >= 1080 and feas.feasible:
        tech = 0.98
    elif height >= 720 and feas.feasible:
        tech = 0.84
    elif feas.feasible:
        tech = 0.68
    else:
        tech = 0.20
        disq.append(f"9:16 crop infeasible ({'; '.join(feas.warnings)})")

    # 5. Composition & cinematic potential (default 10%)
    comp = 0.90 if feas.feasible and feas.upscale_factor <= 2.1 else (0.72 if feas.feasible else 0.25)

    # 6. Motion & storytelling value (default 5%)
    if media_type == "video":
        if has_verified_motion is False:
            motion = 0.25
        else:
            motion = 0.96
    elif media_type == "diagram":
        motion = 0.70
    else:
        motion = 0.42  # Authentic still photo: lower motion score, high authenticity/relevance!

    # 7. Source & licensing verification (default 5%)
    try:
        validate_license_string(license_str, asset_id)
        lic_score = 1.0
    except RightsViolationError as exc:
        lic_score = 0.0
        disq.append(str(exc))

    total_w = (
        w.direct_relevance
        + w.visual_clarity
        + w.authenticity
        + w.technical_quality
        + w.composition_potential
        + w.motion_storytelling
        + w.license_verification
    )
    norm_div = max(1e-6, total_w)

    raw_weighted = (
        w.direct_relevance * rel
        + w.visual_clarity * clarity
        + w.authenticity * auth
        + w.technical_quality * tech
        + w.composition_potential * comp
        + w.motion_storytelling * motion
        + w.license_verification * lic_score
    ) / norm_div

    eligible = len(disq) == 0
    final_score = round(raw_weighted if eligible else min(0.34, raw_weighted * 0.45), 4)

    return AssetScoreBreakdown(
        asset_id=asset_id,
        media_type=media_type,
        narration_target=narration_text[:90],
        direct_relevance=round(rel, 3),
        visual_clarity=round(clarity, 3),
        authenticity=round(auth, 3),
        technical_quality=round(tech, 3),
        composition_potential=round(comp, 3),
        motion_storytelling=round(motion, 3),
        license_verification=round(lic_score, 3),
        weighted_score=final_score,
        eligible_for_selection=eligible,
        disqualification_reason="; ".join(disq),
    )


def score_episode_visual_plan(
    manifest: Any,
    weights: Optional[VisualScoringWeightsConfig] = None,
) -> dict[str, Any]:
    """
    Evaluate every shot in an `EpisodeManifest` using the 7-dimension `AssetRelevanceScorer`,
    probing actual local media resolution, sharpness, and temporal motion when present on disk.
    """
    style = manifest.resolve_style_profile()
    eff_weights = weights or style.asset_selection.scoring_weights
    reg = {a.local_file: a for a in manifest.assets_register}
    search_dirs = manifest.all_asset_search_dirs()

    shot_scores: list[dict[str, Any]] = []
    for s in manifest.shots:
        asset = reg.get(s.src_file)
        lic = asset.license if asset else "Unknown"
        meta_txt = " ".join(
            [
                s.associated_narration_concept,
                s.story_beat,
                s.visual_desc,
                asset.title if asset else "",
                asset.intended_use if asset else "",
            ]
        )
        mtype = (asset.media_type if asset and asset.media_type else None) or (
            "diagram" if s.kind == "diagram" else ("video" if "video" in s.kind or s.kind == "triptych_hook" else "photo")
        )
        resolved = next((d / s.src_file for d in search_dirs if (d / s.src_file).exists()), None)
        w_px, h_px = 1920, 1080
        sharp = None
        has_mot = None
        if resolved is not None:
            if mtype == "photo":
                im = ImageOps.exif_transpose(Image.open(resolved)).convert("RGB")
                w_px, h_px = im.size
                sharp = measure_post_crop_sharpness(im)
            elif mtype == "video":
                mot = audit_clip_real_motion(resolved, start_s=s.src_in, duration_s=min(3.0, max(1.0, s.end_s - s.start_s)))
                if mot.get("valid"):
                    has_mot = bool(mot.get("is_real_moving_footage"))

        bd = score_asset_candidate(
            asset_id=s.src_file,
            narration_text=s.associated_narration_concept or s.story_beat,
            asset_metadata_text=meta_txt,
            media_type=mtype,
            license_str=lic,
            width=w_px,
            height=h_px,
            subject_match_kind=s.subject_match_kind,
            is_authentic_real_capture=bool(s.is_real_evidence),
            is_ai_generated=False,
            has_verified_motion=has_mot,
            sharpness_laplacian_std=sharp,
            allow_cropping=bool(asset.allow_cropping) if asset else True,
            weights=eff_weights,
        )
        row = asdict(bd)
        row["sid"] = s.sid
        row["camera_perspective"] = s.camera_perspective
        shot_scores.append(row)

    mean_score = round(sum(r["weighted_score"] for r in shot_scores) / max(1, len(shot_scores)), 4)
    ineligible = [r for r in shot_scores if not r["eligible_for_selection"]]
    return {
        "slug": manifest.slug,
        "weights_used": eff_weights.model_dump(),
        "mean_weighted_score": mean_score,
        "ineligible_shots_count": len(ineligible),
        "all_shots_eligible": len(ineligible) == 0,
        "shots": shot_scores,
    }


def search_wikimedia_commons_photos(query: str, max_results: int = 8, min_height: int = 900) -> list[dict[str, Any]]:
    """
    Search Wikimedia Commons high-resolution authentic photographs (`filetype:bitmap`)
    covering NSF, NOAA, USGS, NASA, ESA CC-BY, National Parks, and research expeditions ($0 API).
    """
    search_url = (
        "https://commons.wikimedia.org/w/api.php?action=query&list=search&srnamespace=6"
        f"&srlimit={int(max_results)}&format=json&srsearch="
        + urllib.parse.quote(f"{query} filetype:bitmap")
    )
    out: list[dict[str, Any]] = []
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
        lic = re.sub(r"<[^>]+>", "", str(ext.get("LicenseShortName", {}).get("value", ""))).strip()
        nonfree = str(ext.get("NonFree", {}).get("value", "")).strip().lower()
        if nonfree == "true" or not _is_commercial_safe_license_string(lic):
            continue
        desc = re.sub(r"<[^>]+>", " ", str(ext.get("ImageDescription", {}).get("value", "")))
        desc = re.sub(r"\s+", " ", desc).strip()
        artist = re.sub(r"<[^>]+>", " ", str(ext.get("Artist", {}).get("value", ""))).strip()
        out.append(
            {
                "source_repo": "wikimedia_commons_photo",
                "media_type": "photo",
                "asset_id": title,
                "title": title.replace("File:", ""),
                "creator": re.sub(r"\s+", " ", artist)[:120],
                "description": desc[:260],
                "page_url": str(ii.get("descriptionurl", "")),
                "download_url": str(ii.get("url", "")),
                "license_label": lic,
                "width": w,
                "height": h,
            }
        )
    return out


def discover_and_rank_visual_candidates(
    query: str,
    narration_line: str,
    max_per_source: int = 6,
    weights: Optional[VisualScoringWeightsConfig] = None,
) -> list[dict[str, Any]]:
    """
    Multi-archive `$0` visual research engine: discovers commercial-cleared videos AND
    high-resolution authentic photographs across NASA + Wikimedia Commons (including NOAA,
    USGS, ESA CC-BY, NPS, and open journals), then ranks them using the 7-dimension scorer.
    """
    vids = [asdict(v) | {"media_type": "video"} for v in search_nasa_public_domain_videos(query, max_results=max_per_source)]
    vids += [asdict(v) | {"media_type": "video"} for v in search_wikimedia_commons_videos(query, max_results=max_per_source)]
    photos = search_wikimedia_commons_photos(query, max_results=max_per_source)

    ranked: list[dict[str, Any]] = []
    for item in vids + photos:
        meta_blob = f"{item.get('title', '')} {item.get('description', '')}"
        bd = score_asset_candidate(
            asset_id=str(item.get("asset_id", "")),
            narration_text=narration_line or query,
            asset_metadata_text=meta_blob,
            media_type=str(item.get("media_type", "video")),
            license_str=str(item.get("license_label", "")),
            width=int(item.get("width", 1920)),
            height=int(item.get("height", 1080)),
            is_authentic_real_capture=True,
            weights=weights,
        )
        merged = dict(item)
        merged["score_breakdown"] = asdict(bd)
        merged["weighted_score"] = bd.weighted_score
        merged["eligible_for_selection"] = bd.eligible_for_selection
        ranked.append(merged)

    ranked.sort(key=lambda r: (r["eligible_for_selection"], r["weighted_score"]), reverse=True)
    return ranked
