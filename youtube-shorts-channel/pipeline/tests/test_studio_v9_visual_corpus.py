#!/usr/bin/env python3
"""Offline + @pytest.mark.ml unit tests for Studio v9 Visual Corpus (`pow_studio.visual_corpus`)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pow_studio.action_storytelling import (
    NarrationVisualBeat,
    analyze_visual_feasibility,
    evaluate_action_visual_match,
)
from pow_studio.footage_sources.download import sidecar_path
from pow_studio.visual_corpus.corpus import (
    ingest_corpus,
    load_corpus,
    record_episode_usage_in_ledger,
)
from pow_studio.visual_corpus.embedder import HashMockEmbedder, get_embedder, is_ml_available
from pow_studio.visual_corpus.retrieval import (
    compute_empirical_percentiles,
    rank_online_candidates_by_thumbnail,
    search_corpus,
)
from pow_studio.visual_corpus.windowing import split_duration_into_windows


def _write_prov(media_path: Path, license_str: str = "Public Domain (NASA)", title: str = "", cls: str = "STILL_PHOTO") -> None:
    payload = {
        "provenance_version": "9.0",
        "provenance_source": "download-footage",
        "local_file": media_path.name,
        "title": title or media_path.stem,
        "license": license_str,
        "source_media_class": cls,
        "canonical_source_id": f"test:{media_path.stem}",
        "license_evidence": {"verified": True},
    }
    sidecar_path(media_path).write_text(json.dumps(payload), encoding="utf-8")


def test_windowing_splits_cuts_and_chunks_long_segments() -> None:
    # Cut at 0.9s creates a 0.9s sliver (<1.5s) -> dropped so no window crosses the cut;
    # segment [0.9, 14.9] is 14.0s (>8.0s) -> split into 3 uniform ~4.67s windows (<=6.0s, >=1.5s).
    wins = split_duration_into_windows(duration_s=14.9, cut_times=[0.9])
    assert len(wins) == 3
    for w in wins:
        assert w.start_s >= 0.9
        assert 1.5 <= w.duration_s <= 6.01
        ts = w.sample_timestamps()
        assert len(ts) == 3
        assert w.start_s < ts[0] < ts[1] < ts[2] < w.end_s

    # Short clip (<1.5s) falls back to single full-duration window
    short_wins = split_duration_into_windows(duration_s=1.1, cut_times=[])
    assert len(short_wins) == 1
    assert short_wins[0].duration_s == pytest.approx(1.1, abs=0.02)


def test_incremental_ingest_skips_unchanged_and_quarantines_unlicensed(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cdir = tmp_path / "corpus"
    raw.mkdir()

    # 1. Licensed red volcanic photo
    p_red = raw / "red_vent_plume.jpg"
    Image.new("RGB", (320, 240), (235, 30, 25)).save(p_red)
    _write_prov(p_red, "Public Domain (NOAA)", title="Red hydrothermal vent fire plume")

    # 2. Licensed blue ocean photo
    p_blue = raw / "deep_blue_ocean.jpg"
    Image.new("RGB", (320, 240), (20, 60, 230)).save(p_blue)
    _write_prov(p_blue, "CC BY 4.0", title="Deep blue ocean water column")

    # 3. Unlicensed file (no provenance sidecar) -> must NEVER be returned
    p_unlic = raw / "mystery_unlicensed_red.jpg"
    Image.new("RGB", (320, 240), (245, 20, 20)).save(p_unlic)

    # 4. Rejected SA license -> must NEVER be returned
    p_sa = raw / "rejected_bysa_blue.jpg"
    Image.new("RGB", (320, 240), (15, 50, 240)).save(p_sa)
    _write_prov(p_sa, "CC BY-SA 4.0", title="Blue ocean sharealike")

    emb = HashMockEmbedder()
    st1 = ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)
    assert st1["total_files_scanned"] == 4
    assert st1["ingested_files"] == 4
    assert st1["skipped_unchanged_files"] == 0
    assert st1["licensed_windows"] == 2
    assert st1["unknown_license_files_count"] == 1

    # Second run: 100% unchanged files skipped
    st2 = ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)
    assert st2["ingested_files"] == 0
    assert st2["skipped_unchanged_files"] == 4

    # Search must ONLY return the 2 commercially licensed files
    hits = search_corpus("red fire vent", top_k=10, corpus_dir=cdir, embedder=emb)
    returned_files = {h["local_file"] for h in hits}
    assert returned_files == {"red_vent_plume.jpg", "deep_blue_ocean.jpg"}
    assert hits[0]["local_file"] == "red_vent_plume.jpg"

    # Adding a valid sidecar refreshes provenance without re-ingesting pixels
    _write_prov(p_unlic, "CC0 1.0", title="Verified red magma glow")
    st3 = ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)
    assert st3["ingested_files"] == 0
    assert st3["refreshed_provenance_files"] == 1
    assert st3["licensed_windows"] == 3


def test_crash_recovery_truncates_mismatched_rows(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cdir = tmp_path / "corpus"
    raw.mkdir()
    for i in range(3):
        p = raw / f"img_{i}.jpg"
        Image.new("RGB", (160, 160), (40 * i, 80, 180)).save(p)
        _write_prov(p, "Public Domain")

    emb = HashMockEmbedder()
    ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)

    # Simulate crash where index.jsonl got a 4th line appended before embeddings.npy flushed
    with open(cdir / "index.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"window_id": "orphan_0000", "local_file": "orphan.jpg"}) + "\n")

    repaired = load_corpus(cdir, repair_on_mismatch=True)
    assert repaired.size == 3
    assert repaired.embeddings.shape[0] == 3
    assert repaired.tag_embeddings.shape[0] == 3
    assert len((cdir / "index.jsonl").read_text(encoding="utf-8").strip().splitlines()) == 3


def test_usage_ledger_hero_shot_soft_penalty_and_mmr(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    cdir = tmp_path / "corpus"
    raw.mkdir()

    for name in ("blue_a.jpg", "blue_b.jpg"):
        p = raw / name
        Image.new("RGB", (200, 200), (20, 65, 235)).save(p)
        _write_prov(p, "Public Domain (NASA)", title="Blue ocean abyss")

    emb = HashMockEmbedder()
    ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)

    class _DummyAsset:
        local_file = "blue_a.jpg"
        canonical_source_id = "test:blue_a"
        source_page_url = ""
        direct_media_url = ""

    class _DummyShot:
        sid = "S01"
        src_file = "blue_a.jpg"
        src_in = 0.0
        start_s = 0.0
        end_s = 4.5

    class _DummyEp:
        slug = "previous-ocean-ep"
        assets_register = [_DummyAsset()]
        shots = [_DummyShot()]

    record_episode_usage_in_ledger(_DummyEp(), corpus_dir=cdir)
    hits = search_corpus(
        "blue ocean abyss",
        top_k=2,
        corpus_dir=cdir,
        embedder=emb,
        current_episode_slug="new-ocean-ep",
    )
    assert hits[0]["local_file"] == "blue_b.jpg"
    assert hits[1]["local_file"] == "blue_a.jpg"
    assert hits[1]["recent_hero_reuse_slug"] == "previous-ocean-ep"


def test_action_visual_match_modes_and_mislabel_flag() -> None:
    beat = NarrationVisualBeat(
        beat_id="B01",
        seg_id="N01",
        clause_index=0,
        narration_text="ROV lowers a temperature probe into a deep-sea black smoker chimney.",
        subject="black smoker",
        action="lowering",
        location="mid-atlantic ridge",
        object_item="temperature probe",
        scientific_process="hydrothermal venting",
        intended_information="High-temperature vent fluid measurement",
        evidence_required="Real ROV lowering probe",
        visual_perspective="close_up",
        suitable_shot_type="REAL_VIDEO_ACTION",
        genuine_footage_essential=True,
        action_category="equipment_deployment",
        is_historical_event=False,
    )
    cand = {
        "local_file": "rov_probe_smoker.mp4",
        "title": "ROV lowering temperature probe into black smoker hydrothermal vent",
        "license": "Public Domain (NOAA)",
        "source_media_class": "REAL_VIDEO_ACTION",
    }

    ev_off = evaluate_action_visual_match(beat, cand)
    ev_shadow_low = evaluate_action_visual_match(beat, cand, visual_semantic_pct=0.12, visual_corpus_mode="shadow")
    ev_on_high = evaluate_action_visual_match(beat, cand, visual_semantic_pct=0.98, visual_corpus_mode="on")
    ev_on_low = evaluate_action_visual_match(beat, cand, visual_semantic_pct=0.05, visual_corpus_mode="on")

    # Shadow mode MUST NOT alter overall_relevance or eligibility!
    assert ev_shadow_low["overall_relevance"] == ev_off["overall_relevance"]
    assert ev_shadow_low["eligible"] == ev_off["eligible"]
    # High text score (>=0.70) + low visual percentile (<=0.25) -> flagged for agent visual review
    assert ev_shadow_low["possible_mislabeled_asset"] is True
    # Mode "on" adjusts relevance in direction of visual_semantic_pct
    assert ev_on_high["overall_relevance"] > ev_on_low["overall_relevance"]


def test_online_thumbnail_prescreening_offline() -> None:
    emb = HashMockEmbedder()
    thumbs = {
        "https://example.org/blue.jpg": Image.new("RGB", (64, 64), (15, 60, 235)),
        "https://example.org/red.jpg": Image.new("RGB", (64, 64), (235, 25, 20)),
    }
    cands = [
        {"candidate_id": "c_blue", "preview_image_url": "https://example.org/blue.jpg", "height": 1080},
        {"candidate_id": "c_red", "preview_image_url": "https://example.org/red.jpg", "height": 1080},
    ]
    ranked = rank_online_candidates_by_thumbnail(
        "red fire lava",
        cands,
        embedder=emb,
        image_fetcher=lambda u: thumbs.get(u),
    )
    assert ranked[0]["candidate_id"] == "c_red"
    assert ranked[0]["thumbnail_visual_pct"] > ranked[1]["thumbnail_visual_pct"]


def test_empirical_percentiles_invariant_to_linear_scaling() -> None:
    raw_clip = np.array([0.19, 0.24, 0.31, 0.22], dtype=np.float32)
    raw_siglip = raw_clip * 3.5 - 0.85
    assert np.allclose(compute_empirical_percentiles(raw_clip), compute_empirical_percentiles(raw_siglip))


def test_subdirectory_ingest_preserves_parent_records(tmp_path: Path) -> None:
    raw = tmp_path / "raw_footage"
    ep1 = raw / "episode_one"
    ep2 = raw / "episode_two"
    cdir = tmp_path / "corpus"
    ep1.mkdir(parents=True)
    ep2.mkdir(parents=True)

    p1 = ep1 / "corona_wispr.jpg"
    Image.new("RGB", (240, 240), (240, 180, 40)).save(p1)
    _write_prov(p1, "Public Domain (NASA)", title="Solar corona WISPR streamer")

    p2 = ep2 / "deep_sea_vent.jpg"
    Image.new("RGB", (240, 240), (20, 80, 220)).save(p2)
    _write_prov(p2, "Public Domain (NOAA)", title="Hydrothermal vent plume")

    emb = HashMockEmbedder()
    st_full = ingest_corpus(raw_root=raw, corpus_dir=cdir, embedder=emb, workers=1)
    assert st_full["total_windows"] == 2

    # Add a new file inside episode_two and run ingest scoped ONLY to episode_two
    p3 = ep2 / "new_rov_arm.jpg"
    Image.new("RGB", (240, 240), (40, 200, 120)).save(p3)
    _write_prov(p3, "Public Domain (NOAA)", title="ROV robotic arm sampling")

    st_sub = ingest_corpus(raw_root=ep2, corpus_dir=cdir, embedder=emb, workers=1)
    assert st_sub["ingested_files"] == 1
    assert st_sub["skipped_unchanged_files"] == 1
    assert st_sub["total_windows"] == 3

    loaded = load_corpus(cdir)
    assert Path(loaded.meta["raw_root"]).resolve() == raw.resolve()
    rels = {r["rel_path"] for r in loaded.records}
    assert rels == {
        "episode_one/corona_wispr.jpg",
        "episode_two/deep_sea_vent.jpg",
        "episode_two/new_rov_arm.jpg",
    }


@pytest.mark.ml
@pytest.mark.skipif(not is_ml_available()[0], reason="Optional ML group not installed")
def test_live_clip_embedder_on_mps_or_cpu() -> None:
    emb = get_embedder("clip-b32")
    imgs = [
        Image.new("RGB", (224, 224), (230, 35, 25)),
        Image.new("RGB", (224, 224), (20, 65, 225)),
    ]
    ivecs = emb.embed_images(imgs, batch_size=2)
    tvecs = emb.embed_texts(["bright red color", "deep blue ocean water"])
    assert ivecs.shape == (2, 512)
    assert tvecs.shape == (2, 512)
    assert np.isfinite(ivecs).all() and np.isfinite(tvecs).all()
    assert np.allclose(np.linalg.norm(ivecs, axis=-1), 1.0, atol=1e-4)
    # Red image aligns closer to "bright red color" than blue image does
    sims_red_text = ivecs @ tvecs[0]
    assert sims_red_text[0] > sims_red_text[1]
