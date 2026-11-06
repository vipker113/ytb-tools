#!/usr/bin/env python3
"""
Studio v9 footage discovery orchestration (`pow_studio.footage_sources.discover`).

Runs Subject + Action multi-intent queries across all enabled sources, deduplicates, enforces the
commercial license whitelist, assigns stable candidate IDs and PERSISTS results to
`<out_dir>/footage_discovery.{json,md}` (v8 `discover-footage` only printed a table).
"""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path
from typing import Any, Optional

from . import resolve_sources
from .base import license_is_commercial_safe, now_iso


def candidate_id(source_repo: str, asset_id: str, download_url: str) -> str:
    return hashlib.sha1(f"{source_repo}|{asset_id}|{download_url}".encode("utf-8")).hexdigest()[:10]


def _rank_key(c: dict[str, Any]) -> tuple:
    honest_moving = c["inferred_media_class"] in ("REAL_VIDEO_ACTION", "REAL_VIDEO_ESTABLISHING", "REAL_TIME_LAPSE")
    return (
        0 if "low_res_lead" in c.get("source_flags", []) else 1,
        1 if c["inferred_media_class"] == "REAL_VIDEO_ACTION" else 0,
        1 if honest_moving else 0,
        c.get("human_interaction_score", 0.0),
        c.get("height", 0),
    )


FILLER_WORDS = {
    "footage", "documentary", "aerial", "active", "process", "formations", "formation", "close-up", "closeup",
    "expedition", "fieldwork", "scientists", "scientist", "video", "clip", "real", "hd", "4k", "the", "of", "a", "an",
}
ACTION_HINT_WORDS = {"sampling": "sampling", "expedition": "ROV", "close_up_evidence": "close up"}


def compact_query(query: str, max_words: int = 4) -> str:
    """Archive search engines match short keyword queries; strip planner filler words."""
    words = [w for w in query.replace(",", " ").split() if w.lower() not in FILLER_WORDS]
    return " ".join(words[:max_words]).strip()


def plan_archive_queries(topic: str, planned: list[dict[str, Any]], max_queries: int) -> list[dict[str, Any]]:
    """Topic-level query first, then compact purpose queries (deduplicated, order-preserving)."""
    out: list[dict[str, Any]] = [{"purpose": "core_topic", "query": compact_query(topic, 5) or topic, "target_media_class": "REAL_VIDEO_ACTION"}]
    seen = {out[0]["query"].lower()}
    core_words = (compact_query(topic, 6) or topic).split()
    if len(core_words) >= 3:
        for sub in (" ".join(core_words[:2]), " ".join(core_words[-2:])):
            if sub.lower() not in seen:
                seen.add(sub.lower())
                out.append({"purpose": "core_topic", "query": sub, "target_media_class": "REAL_VIDEO_ACTION"})
    for q in planned:
        cq = compact_query(q["query"])
        if q.get("purpose") == "scientific_sampling" and "sampling" not in cq.lower():
            cq = f"{compact_query(topic, 3)} sampling"
        if cq and cq.lower() not in seen:
            seen.add(cq.lower())
            out.append({**q, "query": cq, "planner_query": q["query"]})
    return out[:max_queries]


def run_discovery(
    topic: str,
    beats: Optional[list[Any]] = None,
    sources: Optional[list[str]] = None,
    max_per_query: int = 4,
    max_queries: int = 8,
    extra_queries: Optional[list[str]] = None,
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    from ..action_storytelling import generate_footage_search_queries

    planned = plan_archive_queries(topic, generate_footage_search_queries(topic, beats=beats), max_queries)
    for q in extra_queries or []:
        planned.append({"purpose": "user_query", "query": q, "target_media_class": "REAL_VIDEO_ACTION"})
    srcs = resolve_sources(sources)

    seen: set[str] = set()
    by_purpose: dict[str, list[dict[str, Any]]] = {}
    source_stats: dict[str, dict[str, Any]] = {s.name: {"returned": 0, "kept": 0, "rejected_license": 0} for s in srcs}

    def _one(src: Any, q: dict[str, Any]) -> tuple[Any, dict[str, Any], list[Any], Optional[str]]:
        try:
            return src, q, src.search(q["query"], purpose=q["purpose"], limit=max_per_query), None
        except Exception as exc:  # noqa: BLE001 - a broken adapter must not stop discovery
            return src, q, [], str(exc)[:200]

    jobs = [(src, q) for q in planned for src in srcs]
    with ThreadPoolExecutor(max_workers=max(1, min(8, len(srcs)))) as pool:
        results = list(pool.map(lambda job: _one(*job), jobs))  # map keeps deterministic order

    for src, q, found, err in results:
        if err:
            source_stats[src.name]["errors"] = source_stats[src.name].get("errors", 0) + 1
            source_stats[src.name]["last_error"] = err
            continue
        source_stats[src.name]["returned"] += len(found)
        for c in found:
            key = c.download_url or c.page_url
            if key in seen:
                continue
            seen.add(key)
            if not license_is_commercial_safe(c.license_label):
                source_stats[src.name]["rejected_license"] += 1
                continue
            row = asdict(c)
            row["candidate_id"] = candidate_id(c.source_repo, c.asset_id, c.download_url)
            row["query"] = q["query"]
            by_purpose.setdefault(q["purpose"], []).append(row)
            source_stats[src.name]["kept"] += 1

    for rows in by_purpose.values():
        rows.sort(key=_rank_key, reverse=True)

    report = {
        "topic": topic,
        "generated_at": now_iso(),
        "sources_used": [s.name for s in srcs],
        "planned_queries": planned,
        "source_stats": source_stats,
        "total_unique_candidates": sum(len(v) for v in by_purpose.values()),
        "results_by_purpose": by_purpose,
    }
    if out_dir:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "footage_discovery.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        (out_dir / "footage_discovery.md").write_text(render_discovery_markdown(report), encoding="utf-8")
    return report


def render_discovery_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Footage Discovery — {report['topic']}",
        "",
        f"Generated {report['generated_at']} · sources: {', '.join(report['sources_used'])} · "
        f"{report['total_unique_candidates']} commercial-safe candidates",
        "",
        "| Source | Returned | Kept | License rejected | Errors |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, st in report["source_stats"].items():
        lines.append(f"| {name} | {st['returned']} | {st['kept']} | {st['rejected_license']} | {st.get('errors', 0)} |")
    for purpose, rows in report["results_by_purpose"].items():
        lines += ["", f"## {purpose}", "", "| ID | Source | Class (metadata hint) | Res | License | Flags | Title |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            title = r["title"].replace("|", "/")[:90]
            res = f"{r['width']}x{r['height']}" if r["height"] else "?"
            lines.append(
                f"| `{r['candidate_id']}` | {r['source_repo']} | {r['inferred_media_class']} | {res} | "
                f"{r['license_label']} | {', '.join(r.get('source_flags', []))} | [{title}]({r['page_url']}) |"
            )
    lines += [
        "",
        "> Media class here is a metadata hint only. `download-footage` re-classifies from decoded pixels; "
        "animations/visualizations are never upgraded to camera footage.",
    ]
    return "\n".join(lines) + "\n"
