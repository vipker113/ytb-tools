#!/usr/bin/env python3
"""
Subprocess renderer, deterministic SHA-256 caching, and pre-merge helper for Studio v9
Mechanism Overlays (`pow_studio.mechanism_overlay.renderer`).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

from ..schema import EpisodeManifest, MechanismOverlaySpec, resolve_timed_shots
from .anchoring import ResolvedOverlayTiming, resolve_overlay_timings
from .qa import run_mechanism_overlay_qa
from .spec import KNOWN_OVERLAY_TEMPLATES, is_graphics_available

RENDERER_CACHE_VERSION = "9.0.2"


def _manim_version_str() -> str:
    try:
        import manim

        return str(manim.__version__)
    except ImportError:
        return "missing"


def compute_overlay_cache_hash(
    ov: MechanismOverlaySpec,
    n_frames: int,
    fps: int = 30,
) -> str:
    payload = {
        "renderer_version": RENDERER_CACHE_VERSION,
        "manim_version": _manim_version_str(),
        "template": ov.template,
        "region": ov.region.model_dump(),
        "params": ov.params,
        "honesty_label": ov.honesty_label,
        "n_frames": int(n_frames),
        "fps": int(fps),
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def render_single_overlay_cached(
    ov: MechanismOverlaySpec,
    timing: ResolvedOverlayTiming,
    overlays_dir: Path,
    fps: int = 30,
    use_cache: bool = True,
) -> tuple[Path, bool, float]:
    """
    Render `ov` via an isolated subprocess (arg list, never shell=True) into
    `<overlays_dir>/<overlay_id>_<sha256>.mov`. Returns `(mov_path, was_cached, elapsed_s)`.
    """
    if ov.template not in KNOWN_OVERLAY_TEMPLATES:
        raise ValueError(f"Untrusted or unknown overlay template '{ov.template}'.")

    overlays_dir.mkdir(parents=True, exist_ok=True)
    cache_hash = compute_overlay_cache_hash(ov, n_frames=timing.n_frames, fps=fps)
    out_mov = overlays_dir / f"{ov.overlay_id}_{cache_hash}.mov"

    if use_cache and out_mov.exists() and out_mov.stat().st_size > 1024:
        return out_mov, True, 0.0

    ok_gfx, note = is_graphics_available()
    if not ok_gfx:
        raise RuntimeError(f"Cannot render mechanism overlay '{ov.overlay_id}': {note}")

    t0 = time.perf_counter()
    job_payload = {
        "overlay_id": ov.overlay_id,
        "template": ov.template,
        "params": ov.params,
        "region": ov.region.model_dump(),
        "honesty_label": ov.honesty_label,
        "duration_s": timing.duration_s,
        "n_frames": timing.n_frames,
        "fps": fps,
        "output_mov": str(out_mov.resolve()),
    }

    pipeline_dir = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    existing_py = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{pipeline_dir}:{existing_py}" if existing_py else str(pipeline_dir)

    with tempfile.NamedTemporaryFile("w", suffix=".json", prefix="pow_ov_job_", delete=False, encoding="utf-8") as tf:
        json.dump(job_payload, tf, ensure_ascii=False)
        job_path = Path(tf.name)

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pow_studio.mechanism_overlay.worker", "--spec-json", str(job_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        if proc.returncode != 0 or not out_mov.exists():
            err_tail = (proc.stderr or proc.stdout or "")[-1500:]
            raise RuntimeError(f"Manim worker failed for '{ov.overlay_id}' ({ov.template}):\n{err_tail}")
    finally:
        job_path.unlink(missing_ok=True)

    # Remove stale cached hashes for the same overlay_id
    for old_p in overlays_dir.glob(f"{ov.overlay_id}_*.mov"):
        if old_p != out_mov:
            old_p.unlink(missing_ok=True)

    return out_mov, False, round(time.perf_counter() - t0, 3)


def render_episode_overlays(
    manifest: EpisodeManifest,
    wt: Optional[dict[str, Any]] = None,
    cues: Optional[list[dict[str, Any]]] = None,
    use_cache: bool = True,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Resolve, render (with SHA-256 cache), and run QA on all `manifest.mechanism_overlays`.
    Returns summary including `resolved_timings`, `rendered_paths`, and `qa_report`.
    """
    manifest.assert_output_dir_writable()
    target_out = Path(out_dir) if out_dir else Path(manifest.output_dir)
    overlays_dir = target_out / "overlays"
    style = manifest.resolve_style_profile()
    fps = int(style.output.fps)

    if wt is None:
        wt_p = Path(manifest.output_dir) / "word_timings.json"
        if wt_p.exists():
            wt = json.loads(wt_p.read_text(encoding="utf-8"))
        else:
            from ..creative_qa import _synthetic_wt_from_manifest

            wt = _synthetic_wt_from_manifest(manifest, fps=fps)

    nframes = int(wt.get("total_frames_30fps") or round(float(wt["total_duration_s"]) * fps))
    timed_shots = resolve_timed_shots(manifest, nframes, fps=fps)
    timings = resolve_overlay_timings(manifest, wt, timed_shots=timed_shots, fps=fps)

    if not timings:
        return {
            "overlay_count": 0,
            "resolved_timings": [],
            "rendered_paths": {},
            "cache_hits": 0,
            "render_elapsed_s": 0.0,
            "qa_report": None,
        }

    overlays_by_id = {ov.overlay_id: ov for ov in manifest.mechanism_overlays}
    rendered_paths: dict[str, Path] = {}
    cache_hits = 0
    total_render_s = 0.0

    for rt in timings:
        ov = overlays_by_id[rt.overlay_id]
        mov_p, was_cached, elapsed = render_single_overlay_cached(
            ov=ov,
            timing=rt,
            overlays_dir=overlays_dir,
            fps=fps,
            use_cache=use_cache,
        )
        rendered_paths[rt.overlay_id] = mov_p
        cache_hits += int(was_cached)
        total_render_s += elapsed

    if cues is None:
        try:
            from ..compositor import build_cues

            cues = build_cues(manifest, wt)
        except Exception:
            cues = None

    qa_rep = run_mechanism_overlay_qa(
        manifest=manifest,
        resolved_timings=timings,
        rendered_paths=rendered_paths,
        timed_shots=timed_shots,
        cues=cues,
        total_duration_s=float(wt["total_duration_s"]),
        out_dir=target_out,
    )
    return {
        "overlay_count": len(timings),
        "resolved_timings": timings,
        "rendered_paths": rendered_paths,
        "cache_hits": cache_hits,
        "render_elapsed_s": round(total_render_s, 3),
        "qa_report": qa_rep,
    }


def extract_overlay_rgba_frame(mov_path: Path, local_t_s: float) -> Optional[Image.Image]:
    """Decode a single `1080x1920` RGBA frame at `local_t_s` from a rendered `.mov` for preview sheets."""
    if not mov_path.exists():
        return None
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, float(local_t_s)):.3f}",
            "-i",
            str(mov_path),
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-",
        ],
        capture_output=True,
    )
    expected = 1080 * 1920 * 4
    if proc.returncode != 0 or len(proc.stdout) < expected:
        return None
    arr = np.frombuffer(proc.stdout[:expected], dtype=np.uint8).reshape((1920, 1080, 4))
    return Image.fromarray(arr)


def build_ffmpeg_overlay_mux_plan(
    timings: list[ResolvedOverlayTiming],
    rendered_paths: dict[str, Path],
    scratch_dir: Path,
    total_frames: int,
    fps: int = 30,
) -> tuple[list[str], str, int, list[Path]]:
    """
    Build FFmpeg input flags and filtergraph chain to composite mechanism overlays above `[0:v]`
    (`base_mp4`) and below the subtitle `overlay_qtrle.mov` input!
    If `> 6` overlays are active, pre-merges them into a single `qtrle` RGBA track first.

    Returns `(extra_input_args, filter_prefix, next_input_idx, temp_files_to_cleanup)` where:
      - `[0:v]` is `base_mp4`
      - `extra_input_args` are `-i <mov>` flags inserted BEFORE `ovl_mov` and `mix_wav`
      - `filter_prefix` produces `[v_mech]` ready for `[v_mech][o]overlay=...`!
    """
    active = [(rt, rendered_paths[rt.overlay_id]) for rt in timings if rt.overlay_id in rendered_paths]
    if not active:
        return [], "", 1, []

    temps: list[Path] = []
    if len(active) > 6:
        # Pre-merge onto a transparent 1080x1920 @ fps canvas
        merged_mov = scratch_dir / "_merged_mechanism_overlays.mov"
        total_dur = total_frames / float(fps)
        in_args: list[str] = [
            "-f",
            "lavfi",
            "-i",
            f"color=c=black@0.0:s=1080x1920:r={fps}:d={total_dur:.3f},format=rgba",
        ]
        f_parts: list[str] = []
        prev_lbl = "[0:v]"
        for i, (rt, mp) in enumerate(active, start=1):
            in_args.extend(["-i", str(mp)])
            ov_lbl = f"[mo{i}]"
            out_lbl = f"[m{i}]"
            f_parts.append(f"[{i}:v]format=rgba,setpts=PTS+{rt.start_s:.4f}/TB{ov_lbl}")
            f_parts.append(
                f"{prev_lbl}{ov_lbl}overlay=0:0:format=auto:eof_action=pass:enable='between(t,{rt.start_s:.4f},{rt.end_s:.4f})'{out_lbl}"
            )
            prev_lbl = out_lbl
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                *in_args,
                "-filter_complex",
                ";".join(f_parts),
                "-map",
                prev_lbl,
                "-frames:v",
                str(total_frames),
                "-c:v",
                "qtrle",
                "-pix_fmt",
                "argb",
                str(merged_mov),
            ],
            check=True,
            capture_output=True,
        )
        temps.append(merged_mov)
        extra_inputs = ["-i", str(merged_mov)]
        filter_prefix = "[1:v]format=rgba[mo_all];[0:v][mo_all]overlay=0:0:format=auto:shortest=1[v_mech];"
        return extra_inputs, filter_prefix, 2, temps

    extra_inputs = []
    f_parts = []
    prev_lbl = "[0:v]"
    for idx, (rt, mp) in enumerate(active, start=1):
        extra_inputs.extend(["-i", str(mp)])
        ov_lbl = f"[mo{idx}]"
        out_lbl = "[v_mech]" if idx == len(active) else f"[vm{idx}]"
        f_parts.append(f"[{idx}:v]format=rgba,setpts=PTS+{rt.start_s:.4f}/TB{ov_lbl}")
        f_parts.append(
            f"{prev_lbl}{ov_lbl}overlay=0:0:format=auto:eof_action=pass:enable='between(t,{rt.start_s:.4f},{rt.end_s:.4f})'{out_lbl}"
        )
        prev_lbl = out_lbl

    return extra_inputs, ";".join(f_parts) + ";", 1 + len(active), temps
