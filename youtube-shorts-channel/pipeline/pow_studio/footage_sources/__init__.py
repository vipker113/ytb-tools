"""
Studio v9 multi-source footage harvesting (`pow_studio.footage_sources`).

Sources (all $0, commercial-safe after `rights_gate` normalization):
  nasa_images, wikimedia, internet_archive, nasa_svs, esa_webb, esa_hubble, noaa_onestop, nara (key).

Excluded by policy: ESA main multimedia (CC BY-SA IGO), JAXA (non-commercial), Pexels/Pixabay
(not documentary evidence). Library of Congress is excluded because loc.gov serves an anti-bot
challenge to scripted clients; it is not bypassed.

The registry is imported lazily so `pow_studio.video_sourcing` can re-export `VideoCandidate`
without circular imports.
"""

from __future__ import annotations

from typing import Any


def get_registry() -> dict[str, Any]:
    from .esa_djangoplicity import EsaDjangoplicitySource
    from .internet_archive import InternetArchiveSource
    from .nara import NaraSource
    from .nasa_images import NasaImagesSource
    from .nasa_svs import NasaSvsSource
    from .noaa_onestop import NoaaOneStopSource
    from .wikimedia import WikimediaCommonsSource

    sources = [
        NasaImagesSource(),
        WikimediaCommonsSource(),
        InternetArchiveSource(),
        NasaSvsSource(),
        EsaDjangoplicitySource("esawebb.org", "esa_webb", "ESA/Webb"),
        EsaDjangoplicitySource("esahubble.org", "esa_hubble", "ESA/Hubble"),
        NoaaOneStopSource(),
        NaraSource(),
    ]
    return {s.name: s for s in sources}


def resolve_sources(names: list[str] | None = None) -> list[Any]:
    """Return enabled + available sources (explicit `names` overrides `default_enabled`)."""
    reg = get_registry()
    chosen = [reg[n] for n in names if n in reg] if names else [s for s in reg.values() if s.default_enabled]
    return [s for s in chosen if s.is_available()[0]]
