#!/usr/bin/env python3
"""
Milestone M5 Tests — Studio Backlot Storyboard Exporter & Approval Gate (`pow_studio.backlot`).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.backlot import (  # noqa: E402
    APPROVAL_JSON_NAME,
    BOARD_DIRNAME,
    BOARD_JSON_NAME,
    FILMSTRIP_H,
    FILMSTRIP_W,
    compute_storyboard_sha256,
    export_storyboard_board,
    verify_storyboard_approval,
    write_storyboard_approval_decision,
)
from pow_studio.events import read_studio_events, read_studio_state  # noqa: E402
from pow_studio.schema import EpisodeManifest, resolve_timed_shots  # noqa: E402

PERSEUS_V6_YAML = CHANNEL_ROOT / "episodes" / "space_perseus_black_hole_v6_documentary.yaml"


def _make_sample_manifest(tmp_path: Path, require_approval: bool = True) -> EpisodeManifest:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    out_dir = tmp_path / "output" / "space-and-universe" / "v9-backlot-unit-test"

    base = EpisodeManifest.from_yaml(PERSEUS_V6_YAML)
    s1 = base.shots[0].model_copy(update={"sid": "S01", "start_s": 0.0, "end_s": 3.0, "src_file": "nebula_a.jpg", "kind": "photo"})
    s2 = base.shots[1].model_copy(update={"sid": "S02", "start_s": 3.0, "end_s": 6.0, "src_file": "nebula_b.jpg", "kind": "photo"})

    Image.new("RGB", (1280, 720), (24, 62, 118)).save(assets_dir / "nebula_a.jpg", format="JPEG")
    Image.new("RGB", (1280, 720), (112, 42, 36)).save(assets_dir / "nebula_b.jpg", format="JPEG")

    reg1 = base.assets_register[0].model_copy(
        update={"asset_id": "A1", "local_file": "nebula_a.jpg", "media_type": "photo", "source_media_class": "STATIC_PHOTO_KEN_BURNS"}
    )
    reg2 = base.assets_register[0].model_copy(
        update={"asset_id": "A2", "local_file": "nebula_b.jpg", "media_type": "photo", "source_media_class": "STATIC_PHOTO_KEN_BURNS"}
    )

    return base.model_copy(
        update={
            "manifest_version": "9.0" if require_approval else "8.0",
            "slug": "v9-backlot-unit-test",
            "output_dir": str(out_dir),
            "raw_assets_dir": str(assets_dir),
            "extra_assets_dirs": [],
            "require_storyboard_approval": require_approval,
            "shots": [s1, s2],
            "assets_register": [reg1, reg2],
        }
    )


def test_storyboard_sha256_deterministic_and_sensitive_to_edits(tmp_path: Path) -> None:
    ep = _make_sample_manifest(tmp_path, require_approval=True)
    timed = resolve_timed_shots(ep, total_frames_30fps=180, fps=30)
    sha1 = compute_storyboard_sha256(ep, timed)
    sha2 = compute_storyboard_sha256(ep, timed)
    assert sha1 == sha2 and len(sha1) == 64

    ep_edited = ep.model_copy(deep=True)
    ep_edited.shots[0].z1 = 1.24
    timed_edited = resolve_timed_shots(ep_edited, total_frames_30fps=180, fps=30)
    sha3 = compute_storyboard_sha256(ep_edited, timed_edited)
    assert sha3 != sha1


def test_export_storyboard_board_unrendered_episode_extracts_360x640_filmstrip(tmp_path: Path) -> None:
    ep = _make_sample_manifest(tmp_path, require_approval=True)
    board = export_storyboard_board(ep, extract_frames=True)

    board_file = Path(ep.output_dir) / BOARD_DIRNAME / BOARD_JSON_NAME
    assert board_file.exists()
    assert board["has_rendered_mp4"] is False
    assert board["shot_count"] == 2
    assert len(board["shots"]) == 2

    for sh_card in board["shots"]:
        for key in ("in", "mid", "out"):
            rel = sh_card["frames"][key]
            assert rel is not None
            jpg_path = Path(ep.output_dir) / rel
            assert jpg_path.exists()
            with Image.open(jpg_path) as im:
                assert im.size == (FILMSTRIP_W, FILMSTRIP_H)


def test_pre_v9_manifest_does_not_block_master_render(tmp_path: Path) -> None:
    ep = _make_sample_manifest(tmp_path, require_approval=False)
    res = verify_storyboard_approval(ep)
    assert res["required"] is False
    assert res["blocking"] is False


def test_full_storyboard_approval_lifecycle_and_invalidation_on_edit(tmp_path: Path) -> None:
    ep = _make_sample_manifest(tmp_path, require_approval=True)
    board = export_storyboard_board(ep, extract_frames=False)
    sha_initial = board["storyboard_sha256"]

    # 1. Pending state blocks master verification
    with pytest.raises(RuntimeError, match="storyboard has not been approved yet"):
        verify_storyboard_approval(ep)
    st = read_studio_state(ep.output_dir)
    assert st["gates"]["storyboard_approval"]["status"] == "blocked"

    # 2. Reviewer requests changes with per-shot notes → still blocks & surfaces note on re-export
    write_storyboard_approval_decision(
        Path(ep.output_dir),
        decision="changes_requested",
        storyboard_sha256=sha_initial,
        notes="Adjust Hook zoom",
        shot_notes={"S01": "Zoom closer on core filament"},
        slug=ep.slug,
    )
    with pytest.raises(RuntimeError, match="reviewer requested changes"):
        verify_storyboard_approval(ep)

    re_board = export_storyboard_board(ep, extract_frames=False)
    assert re_board["shots"][0]["reviewer_note"] == "Zoom closer on core filament"
    assert re_board["approval"]["status"] == "changes_requested"

    # 3. Reviewer approves current SHA-256 → master verification passes
    write_storyboard_approval_decision(
        Path(ep.output_dir),
        decision="approved",
        storyboard_sha256=sha_initial,
        notes="LGTM for master render",
        shot_notes={},
        slug=ep.slug,
    )
    ok_res = verify_storyboard_approval(ep)
    assert ok_res["approved"] is True
    assert ok_res["status"] == "approved"
    assert (Path(ep.output_dir) / APPROVAL_JSON_NAME).exists()

    # 4. Editing 1 shot invalidates approval automatically (`stale_hash_mismatch`)
    ep.shots[1].src_file = "nebula_a.jpg"
    board_after_edit = export_storyboard_board(ep, extract_frames=False)
    assert board_after_edit["storyboard_sha256"] != sha_initial
    assert board_after_edit["approval"]["status"] == "stale_hash_mismatch"

    with pytest.raises(RuntimeError, match="storyboard changed since last approval"):
        verify_storyboard_approval(ep)

    # 5. Emergency `--skip-storyboard-gate` passes and logs an audit override event
    skip_res = verify_storyboard_approval(ep, skip_gate=True)
    assert skip_res["skipped"] is True
    events = read_studio_events(ep.output_dir, limit=10)
    assert any(e.get("stage") == "gate:storyboard_approval" and e.get("event") == "override" for e in events)


def test_backlot_refuses_protected_completed_output_dir(tmp_path: Path) -> None:
    ep = _make_sample_manifest(tmp_path, require_approval=True)
    protected = tmp_path / "fermi-paradox-v4-documentary"
    protected.mkdir(parents=True, exist_ok=True)
    with pytest.raises(RuntimeError, match="protected completed"):
        export_storyboard_board(ep, extract_frames=False, out_dir=protected)
    with pytest.raises(RuntimeError, match="protected completed"):
        write_storyboard_approval_decision(protected, decision="approved", storyboard_sha256="a" * 64)
