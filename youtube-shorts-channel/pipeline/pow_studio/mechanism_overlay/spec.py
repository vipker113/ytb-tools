#!/usr/bin/env python3
"""
Schema validation & template registry metadata for Studio v9 Mechanism Overlays
(`pow_studio.mechanism_overlay.spec`).
"""

from __future__ import annotations

from typing import Any

from ..schema import EpisodeManifest, MechanismOverlaySpec, OverlayAnchorSpec, OverlayRegionSpec

KNOWN_OVERLAY_TEMPLATES: tuple[str, ...] = (
    "pressure_ripple",
    "wave_frequency_scale",
    "value_callout_gauge",
    "flow_arrows",
    "scale_bar_compare",
    "trajectory_trace",
    "label_leader",
)

MAX_OVERLAYS_PER_EPISODE = 4
MIN_OVERLAY_HOLD_S = 1.2
SAFE_ZONE_Y_MIN_PX = 215
SAFE_ZONE_Y_MAX_PX = 1380


def is_graphics_available() -> tuple[bool, str]:
    """Return `(available, diagnostic_note)` for ManimCE without rendering."""
    try:
        import manim  # noqa: F401
        import manimpango  # noqa: F401
    except ImportError as exc:
        return False, f"Optional graphics group not installed ({exc}); install requirements-graphics.txt"
    return True, f"manim {manim.__version__} ready"


def extract_overlay_visible_texts(ov: MechanismOverlaySpec) -> list[str]:
    """Collect human-visible text strings configured in `ov.params` for caption-dedup QA."""
    texts: list[str] = []
    p = ov.params or {}
    for k in ("label", "title", "subtitle", "text", "length_label", "reference_label", "marker_label", "unit"):
        val = p.get(k)
        if isinstance(val, str) and val.strip():
            texts.append(val.strip())
    ticks = p.get("ticks")
    if isinstance(ticks, list):
        for item in ticks:
            if isinstance(item, dict):
                for tk in ("label", "sub"):
                    if isinstance(item.get(tk), str) and item[tk].strip():
                        texts.append(item[tk].strip())
            elif isinstance(item, (list, tuple)) and len(item) >= 2 and isinstance(item[1], str):
                texts.append(item[1].strip())
    return texts


def validate_overlay_specs(manifest: EpisodeManifest) -> list[dict[str, Any]]:
    """
    Validate all `manifest.mechanism_overlays` against Studio v9 honesty & layout rules:
      - known template name (never arbitrary code),
      - max 4 overlays per episode,
      - min 1.2s hold duration,
      - `claim_ref` points to a real entry in `manifest.factual_references`,
      - normalized `region` falls inside vertical safe zone `y in [215, 1380]` px.
    Returns structured QA issue dicts (`severity`, `code`, `overlay_id`, `message`).
    """
    issues: list[dict[str, Any]] = []
    overlays = list(getattr(manifest, "mechanism_overlays", []) or [])
    if not overlays:
        return issues

    if len(overlays) > MAX_OVERLAYS_PER_EPISODE:
        issues.append(
            {
                "severity": "MAJOR",
                "code": "too_many_mechanism_overlays",
                "overlay_id": "*",
                "message": f"Episode declares {len(overlays)} mechanism overlays (max {MAX_OVERLAYS_PER_EPISODE}).",
            }
        )

    seen_ids: set[str] = set()
    n_refs = len(getattr(manifest, "factual_references", []) or [])

    for ov in overlays:
        oid = ov.overlay_id
        if oid in seen_ids:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "duplicate_overlay_id",
                    "overlay_id": oid,
                    "message": f"Duplicate overlay_id '{oid}'.",
                }
            )
        seen_ids.add(oid)

        if ov.template not in KNOWN_OVERLAY_TEMPLATES:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "unknown_overlay_template",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' requests unknown template '{ov.template}'. Allowed: {list(KNOWN_OVERLAY_TEMPLATES)}.",
                }
            )

        if float(ov.hold_s) < MIN_OVERLAY_HOLD_S - 1e-6:
            issues.append(
                {
                    "severity": "MAJOR",
                    "code": "overlay_hold_too_short",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' hold_s={ov.hold_s:.2f}s is shorter than {MIN_OVERLAY_HOLD_S}s minimum readability floor.",
                }
            )

        if ov.claim_ref is None:
            issues.append(
                {
                    "severity": "MAJOR",
                    "code": "missing_overlay_claim_ref",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' is missing `claim_ref` into `factual_references`.",
                }
            )
        elif int(ov.claim_ref) < 0 or int(ov.claim_ref) >= n_refs:
            issues.append(
                {
                    "severity": "MAJOR",
                    "code": "invalid_overlay_claim_ref",
                    "overlay_id": oid,
                    "message": f"Overlay '{oid}' claim_ref={ov.claim_ref} out of range (factual_references has {n_refs} entries).",
                }
            )

        y_top_px = ov.region.y * 1920.0
        y_bot_px = (ov.region.y + ov.region.h) * 1920.0
        if y_top_px < SAFE_ZONE_Y_MIN_PX - 2.0 or y_bot_px > SAFE_ZONE_Y_MAX_PX + 2.0:
            issues.append(
                {
                    "severity": "CRITICAL",
                    "code": "overlay_region_outside_safe_zone",
                    "overlay_id": oid,
                    "message": (
                        f"Overlay '{oid}' region y=[{y_top_px:.0f}, {y_bot_px:.0f}]px violates "
                        f"safe zone [{SAFE_ZONE_Y_MIN_PX}, {SAFE_ZONE_Y_MAX_PX}]px (UI/caption collision)."
                    ),
                }
            )

    return issues


__all__ = [
    "KNOWN_OVERLAY_TEMPLATES",
    "MAX_OVERLAYS_PER_EPISODE",
    "MIN_OVERLAY_HOLD_S",
    "MechanismOverlaySpec",
    "OverlayAnchorSpec",
    "OverlayRegionSpec",
    "SAFE_ZONE_Y_MAX_PX",
    "SAFE_ZONE_Y_MIN_PX",
    "extract_overlay_visible_texts",
    "is_graphics_available",
    "validate_overlay_specs",
]
