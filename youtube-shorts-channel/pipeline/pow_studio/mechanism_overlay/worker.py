#!/usr/bin/env python3
"""
Subprocess worker entrypoint for rendering a single ManimCE mechanism overlay cleanly
(`python -m pow_studio.mechanism_overlay.worker --spec-json <path>`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from .templates import render_template_scene


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a single trusted Studio v9 mechanism overlay.")
    parser.add_argument("--spec-json", required=True, help="Path to JSON render job specification")
    args = parser.parse_args()

    job = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
    out_mov = Path(job["output_mov"])
    out_mov.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="pow_manim_") as td:
        rendered = render_template_scene(
            template=str(job["template"]),
            params=dict(job.get("params") or {}),
            region=dict(job.get("region") or {}),
            honesty_label=str(job.get("honesty_label") or "illustrative_model"),
            duration_s=float(job["duration_s"]),
            fps=int(job.get("fps") or 30),
            media_dir=Path(td),
            output_stem=out_mov.stem,
        )
        tmp_dest = out_mov.with_name(f".{out_mov.name}.tmp")
        shutil.copy2(rendered, tmp_dest)
        tmp_dest.replace(out_mov)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
