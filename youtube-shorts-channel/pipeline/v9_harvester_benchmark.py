#!/usr/bin/env python3
"""
Studio v9 M2 acceptance benchmark: usable real-footage candidates, v8 sources (NASA + Commons + IA)
vs all v9 sources, using the SAME planned queries per topic.

"Usable" = commercial-safe license, height >= 720 (or unknown-but-resolvable), not a low-res lead,
and metadata class in genuine moving footage (action / establishing / time-lapse).

Usage: .venv/bin/python pipeline/v9_harvester_benchmark.py --out docs/v9_harvester_benchmark.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PIPELINE_DIR = Path(__file__).resolve().parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.footage_sources.discover import run_discovery  # noqa: E402

TOPICS = [
    "hydrothermal vent black smoker",
    "aurora borealis solar wind",
    "Apollo Saturn V rocket launch",
]
V8_SOURCES = ["nasa_images", "wikimedia", "internet_archive"]
MOVING = {"REAL_VIDEO_ACTION", "REAL_VIDEO_ESTABLISHING", "REAL_TIME_LAPSE"}


def usable(rows: list[dict]) -> tuple[int, int]:
    u = [r for r in rows if r["inferred_media_class"] in MOVING and "low_res_lead" not in r.get("source_flags", []) and (r["height"] == 0 or r["height"] >= 720)]
    return len(u), sum(1 for r in u if r["inferred_media_class"] == "REAL_VIDEO_ACTION")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()
    lines = [
        "# Studio v9 Harvester Benchmark (M2 acceptance)",
        "",
        "- **v8 shipped**: v8 `discover_footage_first_by_purpose` (verbose planner queries; note its Internet Archive",
        "  query was silently broken — unescaped `*/by/*` — and is counted here AFTER the v9 escape fix, i.e. generous to v8).",
        "- **v8 sources / v9 sources**: same v9 compact queries, restricted to NASA+Commons+IA vs all enabled v9 sources.",
        "",
        "| Topic | v8 shipped usable (action) | v8 sources usable (action) | v9 sources usable (action) | v9 low-res leads | v9 non-camera visuals | v9 / v8 shipped |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    summary = []
    for t in TOPICS:
        from pow_studio.video_sourcing import discover_footage_first_by_purpose

        r_old = discover_footage_first_by_purpose(t, max_per_query=args.limit)
        rows_old = [r for rs in r_old["results_by_purpose"].values() for r in rs]
        r8 = run_discovery(t, sources=V8_SOURCES, max_per_query=args.limit)
        r9 = run_discovery(t, sources=None, max_per_query=args.limit)
        rows8 = [r for rs in r8["results_by_purpose"].values() for r in rs]
        rows9 = [r for rs in r9["results_by_purpose"].values() for r in rs]
        uo, ao = usable(rows_old)
        u8, a8 = usable(rows8)
        u9, a9 = usable(rows9)
        leads = sum(1 for r in rows9 if "low_res_lead" in r.get("source_flags", []))
        noncam = sum(1 for r in rows9 if r["inferred_media_class"] not in MOVING)
        ratio = (u9 / uo) if uo else float("inf") if u9 else 0.0
        summary.append({"topic": t, "v8_shipped": uo, "v8_usable": u8, "v9_usable": u9, "v9_action": a9, "leads": leads, "noncamera": noncam, "v9_source_stats": r9["source_stats"]})
        lines.append(f"| {t} | {uo} ({ao}) | {u8} ({a8}) | {u9} ({a9}) | {leads} | {noncam} | {ratio:.2f}x |")
    lines += ["", "Per-source stats (v9):", "", "```json", json.dumps({s["topic"]: s["v9_source_stats"] for s in summary}, indent=1), "```"]
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
