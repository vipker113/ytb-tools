#!/usr/bin/env python3
"""
Studio v9 Golden Render Equality Check.

Renders a scratch copy of an existing episode (never touching its real output folder) and
records / compares per-frame video MD5s (`ffmpeg -f framemd5`). Used after every v9
milestone to prove that, with v9 features switched off, the rendered video is unchanged.

Usage:
  .venv/bin/python pipeline/v9_golden_render.py --manifest episodes/<ep>.yaml --record
  .venv/bin/python pipeline/v9_golden_render.py --manifest episodes/<ep>.yaml --compare
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml

PIPELINE_DIR = Path(__file__).resolve().parent
CHANNEL_ROOT = PIPELINE_DIR.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.compositor import render_episode_master  # noqa: E402
from pow_studio.schema import EpisodeManifest  # noqa: E402

GOLDEN_ROOT = CHANNEL_ROOT / ".golden"


def _prepare_scratch(manifest_path: Path) -> tuple[Path, Path]:
    src_ep = EpisodeManifest.from_yaml(manifest_path)
    src_out = Path(src_ep.output_dir)
    if not (src_out / "word_timings.json").exists() or not (src_out / "work_audio" / "final_audio_mix.wav").exists():
        raise SystemExit(f"Source episode lacks word_timings.json or work_audio/final_audio_mix.wav: {src_out}")

    scratch_out = GOLDEN_ROOT / f"{src_ep.slug}__golden"
    if scratch_out.exists():
        shutil.rmtree(scratch_out)
    (scratch_out / "work_audio").mkdir(parents=True)

    for p in src_out.glob("*.json"):
        shutil.copy2(p, scratch_out / p.name)
    shutil.copy2(src_out / "work_audio" / "final_audio_mix.wav", scratch_out / "work_audio" / "final_audio_mix.wav")
    if (src_out / "work_clips").is_dir():
        shutil.copytree(src_out / "work_clips", scratch_out / "work_clips")

    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    data["output_dir"] = str(scratch_out)
    data["raw_assets_dir"] = src_ep.raw_assets_dir
    data["extra_assets_dirs"] = list(src_ep.extra_assets_dirs)
    if data.get("annotated_voice_script_file"):
        data["annotated_voice_script_file"] = src_ep.annotated_voice_script_file
    scratch_yaml = scratch_out / "golden_manifest.yaml"
    scratch_yaml.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return scratch_yaml, scratch_out


def _framemd5(mp4: Path) -> list[str]:
    r = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-map", "0:v:0", "-f", "framemd5", "-"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [ln for ln in r.stdout.splitlines() if ln and not ln.startswith("#")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--mode", default="master", choices=["draft", "master"])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--record", action="store_true")
    g.add_argument("--compare", action="store_true")
    args = ap.parse_args()

    manifest_path = args.manifest.resolve()
    scratch_yaml, scratch_out = _prepare_scratch(manifest_path)
    ep = EpisodeManifest.from_yaml(scratch_yaml)
    wt = json.loads((scratch_out / "word_timings.json").read_text(encoding="utf-8"))

    t0 = time.perf_counter()
    mp4 = render_episode_master(ep, wt, encode_mode=args.mode)
    elapsed = time.perf_counter() - t0
    frames = _framemd5(mp4)

    ref = GOLDEN_ROOT / f"{ep.slug}.{args.mode}.framemd5.json"
    if args.record:
        ref.write_text(json.dumps({"slug": ep.slug, "mode": args.mode, "frames": frames}, indent=0), encoding="utf-8")
        print(f"RECORDED {len(frames)} frames -> {ref} (render {elapsed:.1f}s)")
        return 0

    if not ref.exists():
        print(f"No golden reference at {ref}; run with --record first.")
        return 2
    old = json.loads(ref.read_text(encoding="utf-8"))["frames"]
    if old == frames:
        print(f"GOLDEN MATCH: {len(frames)}/{len(frames)} frames identical (render {elapsed:.1f}s)")
        return 0
    n_diff = sum(1 for a, b in zip(old, frames) if a != b) + abs(len(old) - len(frames))
    first = next((i for i, (a, b) in enumerate(zip(old, frames)) if a != b), min(len(old), len(frames)))
    print(f"GOLDEN MISMATCH: {n_diff} differing frames (first at index {first}); old={len(old)} new={len(frames)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
