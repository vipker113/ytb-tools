#!/usr/bin/env python3
"""Studio v9 foundation tests: event log, schema v9 fields, style-profile v9 configs (offline)."""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

PIPELINE_DIR = Path(__file__).resolve().parent.parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.events import (  # noqa: E402
    EVENTS_FILENAME,
    STATE_FILENAME,
    emit_event,
    read_studio_events,
    read_studio_state,
    set_gate,
    stage_events,
)
from pow_studio.schema import EpisodeManifest, MechanismOverlaySpec, OverlayAnchorSpec  # noqa: E402
from pow_studio.style_profile import load_style_profile  # noqa: E402


def test_emit_event_writes_jsonl_and_state(tmp_path: Path) -> None:
    emit_event(tmp_path, "stage1-research", "start", "running", slug="demo")
    emit_event(tmp_path, "stage1-research", "end", "passed", detail="ok", artifacts=["a.json"], slug="demo")
    rows = read_studio_events(tmp_path)
    assert [r["event"] for r in rows] == ["start", "end"]
    state = read_studio_state(tmp_path)
    st = state["stages"]["stage1-research"]
    assert state["slug"] == "demo"
    assert st["status"] == "passed" and st["artifacts"] == ["a.json"]
    assert st["duration_s"] >= 0.0
    assert not list(tmp_path.glob(".*.tmp")), "atomic write must not leave temp files"


def test_stage_events_records_failure_and_reraises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        with stage_events(tmp_path, "stage5-edit"):
            raise ValueError("boom")
    st = read_studio_state(tmp_path)["stages"]["stage5-edit"]
    assert st["status"] == "failed" and "boom" in st["detail"]


def test_stage_events_treats_exit_code_zero_as_pass(tmp_path: Path) -> None:
    class _Exit(Exception):
        exit_code = 0

    with pytest.raises(_Exit):
        with stage_events(tmp_path, "feasibility"):
            raise _Exit()
    assert read_studio_state(tmp_path)["stages"]["feasibility"]["status"] == "passed"


def test_set_gate_updates_state_and_logs(tmp_path: Path) -> None:
    set_gate(tmp_path, "storyboard_approval", "blocked", detail="hash mismatch")
    state = read_studio_state(tmp_path)
    assert state["gates"]["storyboard_approval"]["status"] == "blocked"
    assert read_studio_events(tmp_path)[-1]["stage"] == "gate:storyboard_approval"


def test_events_never_written_into_protected_completed_dir(tmp_path: Path) -> None:
    protected = tmp_path / "blood-falls-v3-documentary"
    protected.mkdir()
    (protected / "blood-falls-v3-documentary.mp4").write_bytes(b"\x00")
    assert emit_event(protected, "qa", "start", "running") is None
    set_gate(protected, "qa_six_pillar", "passed")
    assert not (protected / EVENTS_FILENAME).exists()
    assert not (protected / STATE_FILENAME).exists()


def test_all_existing_manifests_load_with_v9_defaults_off() -> None:
    paths = sorted(glob.glob(str(CHANNEL_ROOT / "episodes" / "*.yaml")))
    assert paths, "expected episode manifests"
    for p in paths:
        ep = EpisodeManifest.from_yaml(p)
        assert ep.visual_corpus_mode == "off"
        assert ep.require_storyboard_approval is False
        assert ep.mechanism_overlays == []


def test_overlay_anchor_requires_phrase_or_start() -> None:
    with pytest.raises(ValueError):
        OverlayAnchorSpec(seg_id="N02")
    assert OverlayAnchorSpec(start_s=3.2).start_s == 3.2
    spec = MechanismOverlaySpec(
        overlay_id="OV1",
        template="value_callout_gauge",
        anchor={"seg_id": "N02", "phrase": "three hundred sixty"},
        params={"value_to": 360},
        claim_ref=2,
    )
    assert spec.region.w == pytest.approx(0.84)
    assert spec.honesty_label == "illustrative_model"
    assert json.loads(spec.model_dump_json())["anchor"]["phrase"] == "three hundred sixty"


def test_style_profile_v9_defaults() -> None:
    style = load_style_profile("pow_documentary_v3")
    assert style.visual_corpus.visual_weight_when_on == pytest.approx(0.20)
    assert style.mechanism_overlays.max_alpha_area_ratio == pytest.approx(0.35)
    assert style.mechanism_overlays.safe_zone_y_max_px == 1380
    legacy = load_style_profile("legacy_v2")
    assert legacy.mechanism_overlays.max_overlays_per_video == 4
