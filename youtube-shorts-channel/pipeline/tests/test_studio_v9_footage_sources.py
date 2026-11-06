#!/usr/bin/env python3
"""Studio v9 M2 tests: footage source adapters (mocked HTTP), discovery persistence, provenance, honesty rules."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.footage_sources import base as fs_base  # noqa: E402
from pow_studio.footage_sources import discover as fs_discover  # noqa: E402
from pow_studio.footage_sources import download as fs_download  # noqa: E402
from pow_studio.footage_sources.base import license_is_commercial_safe  # noqa: E402
from pow_studio.footage_sources.esa_djangoplicity import EsaDjangoplicitySource  # noqa: E402
from pow_studio.footage_sources.internet_archive import InternetArchiveSource, license_label_from_url, pick_best_video_file  # noqa: E402
from pow_studio.footage_sources.nara import NaraSource  # noqa: E402
from pow_studio.footage_sources.nasa_svs import NasaSvsSource  # noqa: E402
from pow_studio.footage_sources.noaa_onestop import NoaaOneStopSource  # noqa: E402
from pow_studio.footage_sources.wikimedia import WikimediaCommonsSource  # noqa: E402
from pow_studio.video_sourcing import VideoCandidate  # noqa: E402


def _router(routes: dict[str, object]):
    """Return a fake `http_request` that matches URL substrings to canned payloads."""

    def fake(url: str, **kwargs):  # noqa: ANN003
        for needle, payload in routes.items():
            if needle in url:
                return payload
        raise RuntimeError(f"unexpected URL in test: {url}")

    return fake


def test_license_whitelist_defers_to_rights_gate() -> None:
    assert license_is_commercial_safe("CC BY 4.0")
    assert license_is_commercial_safe("Public Domain (NOAA)")
    assert license_is_commercial_safe("CC0")
    assert not license_is_commercial_safe("CC BY-SA 3.0 IGO")
    assert not license_is_commercial_safe("CC BY-NC 4.0")
    assert not license_is_commercial_safe("JAXA Digital Archives License (educational use)")


def test_video_candidate_is_backward_compatible() -> None:
    c = VideoCandidate("r", "id", "t", "d", "p", "u", "CC0", 1920, 1080, 0.0, "n")
    assert c.inferred_media_class == "REAL_VIDEO_ESTABLISHING" and c.preview_image_url == "" and c.source_flags == []


def test_internet_archive_picks_real_file_and_true_dimensions(monkeypatch: pytest.MonkeyPatch) -> None:
    assert license_label_from_url("http://creativecommons.org/publicdomain/zero/1.0/") == "CC0"
    assert license_label_from_url("https://creativecommons.org/licenses/by/4.0/") == "CC BY 4.0"
    assert license_label_from_url("https://creativecommons.org/licenses/by-nc/4.0/") == ""
    files = [
        {"name": "a_512kb.mp4", "format": "512Kb MPEG4", "width": "320", "height": "240", "source": "derivative"},
        {"name": "a.mp4", "format": "h.264 HD", "width": "1920", "height": "1080", "source": "derivative", "length": "61.2"},
        {"name": "a.mpeg", "format": "MPEG2", "width": "1920", "height": "1080", "source": "original"},
    ]
    assert pick_best_video_file(files)["name"] == "a.mp4"
    assert pick_best_video_file(files[:1]) is None
    monkeypatch.setattr(
        "pow_studio.footage_sources.internet_archive.http_request",
        _router(
            {
                "advancedsearch.php": {"response": {"docs": [{"identifier": "ocean_film"}]}},
                "archive.org/metadata/ocean_film": {
                    "metadata": {"title": "ROV sampling vent fluid", "licenseurl": "http://creativecommons.org/publicdomain/mark/1.0/", "creator": "NOAA"},
                    "files": files,
                },
            }
        ),
    )
    out = InternetArchiveSource().search("vent", limit=2)
    assert len(out) == 1
    c = out[0]
    assert c.download_url.endswith("/ocean_film/a.mp4") and (c.width, c.height) == (1920, 1080)
    assert c.license_label == "Public Domain" and c.license_evidence["verified"] is True
    assert c.duration_s == pytest.approx(61.2)


def test_wikimedia_rejects_sharealike_and_keeps_poster(monkeypatch: pytest.MonkeyPatch) -> None:
    def ii(lic: str, w: int = 1920, h: int = 1080) -> dict:
        return {
            "width": w, "height": h, "duration": 63.3, "url": "https://upload.wikimedia.org/x.webm",
            "thumburl": "https://thumb.wikimedia.org/x.webm.jpg?utm=1", "descriptionurl": "https://commons.wikimedia.org/wiki/File:X.webm",
            "extmetadata": {"LicenseShortName": {"value": lic}, "Artist": {"value": "<a>Ifremer</a>"}, "ImageDescription": {"value": "ROV probe in vent"}},
        }

    monkeypatch.setattr(
        "pow_studio.footage_sources.wikimedia.http_request",
        _router(
            {
                "list=search": {"query": {"search": [{"title": "File:A.webm"}, {"title": "File:B.webm"}, {"title": "File:C.webm"}]}},
                "prop=imageinfo": {"query": {"pages": {"1": {"title": "File:A.webm", "imageinfo": [ii("CC BY 4.0")]},
                                                          "2": {"title": "File:B.webm", "imageinfo": [ii("CC BY-SA 4.0")]},
                                                          "3": {"title": "File:C.webm", "imageinfo": [ii("CC0", 640, 360)]}}}},
            }
        ),
    )
    out = WikimediaCommonsSource().search("vent")
    assert [c.asset_id for c in out] == ["File:A.webm"]
    assert out[0].preview_image_url.endswith(".jpg") and "?" not in out[0].preview_image_url
    assert "Ifremer" in out[0].required_attribution


def test_svs_animation_is_never_camera_footage(monkeypatch: pytest.MonkeyPatch) -> None:
    page = {
        "page_type": "Animation", "title": "Enceladus", "description": "vents",
        "media_groups": [{"items": [{"instance": {"url": "http://svs.gsfc.nasa.gov/vis/a/OceanVents_web.mp4", "media_type": "Movie", "width": 1920, "height": 1080, "filename": "OceanVents_web.mp4"}},
                                    {"instance": {"url": "http://svs.gsfc.nasa.gov/vis/a/OceanVents_ProRes.mov", "media_type": "Movie", "width": 3840, "height": 2160, "filename": "OceanVents_ProRes.mov"}}]}],
    }
    monkeypatch.setattr(
        "pow_studio.footage_sources.nasa_svs.http_request",
        _router({"api/search": {"results": [{"id": 20384, "result_type": "Animation"}]}, "api/20384": page}),
    )
    out = NasaSvsSource().search("vent", limit=5)
    assert len(out) == 1, "one file per visual stem"
    c = out[0]
    assert c.inferred_media_class == "REAL_ANIMATION"
    assert c.third_party_audio_risk is True and "visualization_not_camera_footage" in c.source_flags
    assert c.download_url.startswith("https://") and c.download_url.endswith("OceanVents_web.mp4")


def test_esa_parses_credit_strips_music_and_flags_pans(monkeypatch: pytest.MonkeyPatch) -> None:
    search_html = '<a href="/videos/search/"></a><a href="/videos/weic2331a/"></a><a href="/videos/weic9999a/"></a>'
    detail = (
        "<title>Pan of star cluster IC 348 | ESA/Webb</title>"
        '<strong>Credit:</strong> <div class="credit"><p>NASA, ESA, CSA, STScI, N. Bartmann (ESA/Webb)<br />Music: Noizefield</p></div>'
        '<a href="https://cdn.esawebb.org/archives/videos/hd_1080p25_screen/weic2331a.mp4">HD</a>'
    )
    interview = "<title>Interview with a scientist | ESA/Webb</title><div class=\"credit\"><p>ESA</p></div>" \
                '<a href="https://cdn.esawebb.org/archives/videos/hd_1080p25_screen/weic9999a.mp4">HD</a>'
    monkeypatch.setattr(
        "pow_studio.footage_sources.esa_djangoplicity.http_request",
        _router({"videos/?search": search_html, "videos/weic2331a/": detail, "videos/weic9999a/": interview}),
    )
    out = EsaDjangoplicitySource("esawebb.org", "esa_webb", "ESA/Webb").search("cluster")
    assert len(out) == 1, "identifiable-people items are skipped"
    c = out[0]
    assert c.license_label == "CC BY 4.0" and c.inferred_media_class == "ANIMATED_STILL"
    assert "Music" not in c.required_attribution and "Bartmann" in c.required_attribution
    assert c.third_party_audio_risk is True and "credited_music" in c.source_flags


def test_noaa_marks_low_res_leads(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"data": [{"attributes": {"title": "Video segment from DIVE02 of EX-22-05", "links": [
        {"linkUrl": "https://www.nodc.noaa.gov/oer/video/?oerkey=fileIdentifier:EX2205_DIVE02_ROVHD"},
        {"linkUrl": "https://www.ncei.noaa.gov/data/oceans/oer/video/EX2205/Video/EX2205_DIVE02_20220721/Compressed/EX2205_VID_ROVHD_Low.mp4"},
    ]}}]}
    monkeypatch.setattr("pow_studio.footage_sources.noaa_onestop.http_request", _router({"onestop": payload}))
    out = NoaaOneStopSource().search("hydrothermal")
    assert len(out) == 1 and out[0].height == 360 and "low_res_lead" in out[0].source_flags
    assert out[0].license_label == "Public Domain (NOAA)" and out[0].inferred_media_class == "REAL_VIDEO_ACTION"


def test_nara_disabled_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NARA_API_KEY", raising=False)
    monkeypatch.setattr("pow_studio.footage_sources.nara._load_key", lambda: "")
    src = NaraSource()
    assert src.default_enabled is False and src.is_available()[0] is False and src.search("apollo") == []


def test_discovery_persists_dedupes_and_filters(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class FakeSource:
        name, display_name, default_enabled = "fake", "Fake", True

        def is_available(self):
            return True, ""

        def search(self, query, purpose="general", limit=6):
            return [
                VideoCandidate("fake", "a", "ROV arm", "", "p1", "https://x/a.mp4", "CC BY 4.0", 1920, 1080, 3.0, "", "REAL_VIDEO_ACTION", purpose),
                VideoCandidate("fake", "b", "Lead", "", "p2", "https://x/b.mp4", "Public Domain (NOAA)", 640, 360, 0.0, "", "REAL_VIDEO_ACTION", purpose, source_flags=["low_res_lead"]),
                VideoCandidate("fake", "c", "SA clip", "", "p3", "https://x/c.mp4", "CC BY-SA 4.0", 1920, 1080, 0.0, "", "REAL_VIDEO_ACTION", purpose),
            ]

    monkeypatch.setattr(fs_discover, "resolve_sources", lambda names=None: [FakeSource()])
    rep = fs_discover.run_discovery("hydrothermal vents", max_queries=3, out_dir=tmp_path)
    assert rep["total_unique_candidates"] == 2, "deduped across queries, SA rejected"
    assert rep["source_stats"]["fake"]["rejected_license"] == 1
    first_bucket = next(iter(rep["results_by_purpose"].values()))
    assert first_bucket[0]["asset_id"] == "a", "low-res leads rank after usable footage"
    saved = json.loads((tmp_path / "footage_discovery.json").read_text())
    assert len(saved["results_by_purpose"]) >= 1 and (tmp_path / "footage_discovery.md").exists()
    assert len(first_bucket[0]["candidate_id"]) == 10


@pytest.mark.parametrize(
    "hint,classes,baked,expected",
    [
        ("REAL_ANIMATION", ["REAL_VIDEO_ACTION"], 0, "REAL_ANIMATION"),
        ("ANIMATED_STILL", ["REAL_VIDEO_ACTION"], 0, "ANIMATED_STILL"),
        ("SCIENTIFIC_IMAGE", ["ANIMATED_STILL"], 1, "ANIMATED_STILL"),
        ("REAL_VIDEO_ESTABLISHING", ["REAL_VIDEO_ACTION", "REAL_VIDEO_ESTABLISHING"], 0, "REAL_VIDEO_ACTION"),
        ("REAL_VIDEO_ACTION", ["ANIMATED_STILL", "ANIMATED_STILL", "REAL_VIDEO_ACTION"], 2, "ANIMATED_STILL"),
        ("REAL_VIDEO_ACTION", ["STILL_PHOTO"], 0, "STILL_PHOTO"),
        ("REAL_VIDEO_ACTION", [], 0, "REAL_VIDEO_ACTION"),
    ],
)
def test_reconcile_media_class_only_downgrades(hint: str, classes: list[str], baked: int, expected: str) -> None:
    assert fs_download.reconcile_media_class(hint, classes, baked) == expected


def test_download_writes_provenance_and_strips_audio(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=30:duration=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)],
        check=True,
    )
    disc = {"results_by_purpose": {"p": [{
        "candidate_id": "abc1234567", "source_repo": "nasa_svs", "asset_id": "svs-1", "title": "Ocean vent flythrough",
        "description": "", "page_url": "https://svs.gsfc.nasa.gov/1/", "download_url": "https://example.org/OceanVents_web.mp4",
        "license_label": "Public Domain (NASA SVS)", "license_url": "", "required_attribution": "NASA SVS", "creator_agency": "NASA SVS",
        "inferred_media_class": "REAL_ANIMATION", "third_party_audio_risk": True, "source_flags": [], "license_evidence": {"verified": True},
        "query": "vent", "query_purpose": "p",
    }]}}
    dp = tmp_path / "planning" / "footage_discovery.json"
    dp.parent.mkdir()
    dp.write_text(json.dumps(disc))
    monkeypatch.setattr(fs_download, "stream_download", lambda url, dest, max_bytes=0: (dest.write_bytes(src.read_bytes()), dest)[1])
    res = fs_download.download_candidates(dp, ["abc1234567", "missing"], tmp_path / "raw", audit=False)
    assert res[0]["ok"] and not res[1]["ok"]
    local = Path(res[0]["local_path"])
    prov = json.loads(fs_download.sidecar_path(local).read_text())
    assert prov["audio_stripped"] is True and prov["probe"]["has_audio"] is False
    assert prov["source_media_class"] == "REAL_ANIMATION" and prov["license"] == "Public Domain (NASA SVS)"
    assert len(prov["sha256"]) == 64 and "local_file:" in res[0]["assets_register_yaml"]


def test_http_cache_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(fs_base, "HTTP_CACHE_DIR", tmp_path)
    calls = {"n": 0}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            calls["n"] += 1
            return b'{"ok": 1}'

    monkeypatch.setattr(fs_base.urllib.request, "urlopen", lambda req, timeout=0: _Resp())
    monkeypatch.setattr(fs_base, "_respect_rate_limit", lambda url: None)
    assert fs_base.http_request("https://example.org/a") == {"ok": 1}
    assert fs_base.http_request("https://example.org/a") == {"ok": 1}
    assert calls["n"] == 1, "second call served from disk cache"
    assert np.isfinite(len(list(tmp_path.glob("*.json"))))


def test_rights_gate_provenance_sidecar(tmp_path: Path) -> None:
    import hashlib

    from pow_studio.rights_gate import RightsViolationError, _check_provenance_sidecar

    media = tmp_path / "clip.mp4"
    media.write_bytes(b"abc")
    assert _check_provenance_sidecar(media, "CC BY 4.0", "clip.mp4") == ""
    sha = hashlib.sha256(b"abc").hexdigest()
    sp = media.with_name(media.name + ".provenance.json")
    sp.write_text(json.dumps({"license": "CC BY 4.0", "sha256": sha, "source_repo": "wikimedia",
                              "license_evidence": {"verified": True, "evidence_sha256": "deadbeef00"}}))
    assert _check_provenance_sidecar(media, "CC BY 4.0", "clip.mp4").startswith("YES (provenance: wikimedia")
    assert "MANIFEST-LICENSE-DIFFERS" in _check_provenance_sidecar(media, "Public Domain", "clip.mp4")
    media.write_bytes(b"tampered")
    with pytest.raises(RightsViolationError):
        _check_provenance_sidecar(media, "CC BY 4.0", "clip.mp4")
    sp.write_text(json.dumps({"license": "CC BY-SA 4.0"}))
    with pytest.raises(RightsViolationError):
        _check_provenance_sidecar(media, "CC BY 4.0", "clip.mp4")


def test_compact_archive_queries() -> None:
    planned = [
        {"purpose": "scientific_sampling", "query": "Scientists sampling hydrothermal vent black smoker", "target_media_class": "REAL_VIDEO_ACTION"},
        {"purpose": "establishing_location", "query": "hydrothermal vent black smoker aerial documentary footage", "target_media_class": "REAL_VIDEO_ESTABLISHING"},
    ]
    qs = fs_discover.plan_archive_queries("hydrothermal vent black smoker", planned, max_queries=8)
    texts = [q["query"] for q in qs]
    assert texts[0] == "hydrothermal vent black smoker"
    assert "hydrothermal vent" in texts and "black smoker" in texts
    assert all("footage" not in t and "documentary" not in t for t in texts)
    assert len(texts) == len({t.lower() for t in texts})


def test_commons_credit_cleanup_and_ascii_filenames() -> None:
    from pow_studio.footage_sources.wikimedia import clean_commons_credit

    t = "Cheminées hydrothermales sur le site Lucky Strike (Ifremer 01096-120768 - 518753).webm"
    assert clean_commons_credit("null, null\n \nnull, null", "Cheminées hydrothermales", '<a href="https://image.ifremer.fr/x">x</a>', t) == "Ifremer"
    assert clean_commons_credit("Jane Doe", "", "", t) == "Jane Doe"
    assert clean_commons_credit("null", "", 'href="https://www.noaa.gov/x"', "Seep.webm") == "NOAA"
    name = fs_download.safe_filename("wikimedia", "Cheminées hydrothermales", "abc", "https://x/y.webm")
    assert name == "wikimedia_cheminees_hydrothermales_abc.webm"
