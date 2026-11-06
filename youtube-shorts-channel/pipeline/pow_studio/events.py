#!/usr/bin/env python3
"""
Studio v9 Production Event Log (`pow_studio.events`).

Every v9-aware CLI stage appends structured events to `<output_dir>/studio_events.jsonl`
and keeps a compact `<output_dir>/studio_state.json` summary. Both files are read by:
  - the `pow-executive-producer` agent skill (to know where production stands), and
  - the ytb-tools "Studio Backlot" tab (live filmstrip, gate rail, activity feed, replay).

Writes are atomic (temp file + rename) and never touch protected completed episode folders.
"""

from __future__ import annotations

import functools
import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

EVENTS_FILENAME = "studio_events.jsonl"
STATE_FILENAME = "studio_state.json"
STATE_VERSION = "9.0"

GATE_ORDER = (
    "feasibility",
    "voice_lock",
    "storyboard_approval",
    "render_master",
    "qa_six_pillar",
    "publish",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _is_protected_completed_dir(out_dir: Path) -> bool:
    from .schema import PROTECTED_COMPLETED_OUTPUT_DIRS

    try:
        return out_dir.name in PROTECTED_COMPLETED_OUTPUT_DIRS and any(out_dir.glob("*.mp4"))
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def read_studio_state(out_dir: Path) -> dict[str, Any]:
    p = Path(out_dir) / STATE_FILENAME
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"state_version": STATE_VERSION, "slug": Path(out_dir).name, "stages": {}, "gates": {}}


def read_studio_events(out_dir: Path, limit: Optional[int] = None) -> list[dict[str, Any]]:
    p = Path(out_dir) / EVENTS_FILENAME
    if not p.exists():
        return []
    rows: list[dict[str, Any]] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return rows[-limit:] if limit else rows


def emit_event(
    out_dir: Path | str,
    stage: str,
    event: str,
    status: str,
    detail: str = "",
    artifacts: Optional[list[str]] = None,
    data: Optional[dict[str, Any]] = None,
    slug: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Append one event and fold it into `studio_state.json`. Returns the event (or None if skipped)."""
    out_p = Path(out_dir)
    if _is_protected_completed_dir(out_p):
        return None
    out_p.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {
        "ts": _now_iso(),
        "stage": stage,
        "event": event,
        "status": status,
        "detail": detail,
        "artifacts": [str(a) for a in (artifacts or [])],
    }
    if data:
        row["data"] = data
    with open(out_p / EVENTS_FILENAME, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    state = read_studio_state(out_p)
    state["state_version"] = STATE_VERSION
    if slug:
        state["slug"] = slug
    state["updated_at"] = row["ts"]
    st = state.setdefault("stages", {}).setdefault(stage, {})
    if event == "start":
        st.update({"status": "running", "started_at": row["ts"], "finished_at": None, "detail": detail})
    else:
        st.update({"status": status, "finished_at": row["ts"], "detail": detail})
        if st.get("started_at"):
            try:
                t0 = datetime.fromisoformat(st["started_at"])
                st["duration_s"] = round((datetime.fromisoformat(row["ts"]) - t0).total_seconds(), 3)
            except ValueError:
                pass
        if artifacts:
            st["artifacts"] = row["artifacts"]
    _atomic_write_json(out_p / STATE_FILENAME, state)
    return row


def set_gate(
    out_dir: Path | str,
    gate: str,
    status: str,
    detail: str = "",
    data: Optional[dict[str, Any]] = None,
) -> None:
    """Record a production gate status (`pending` | `passed` | `blocked` | `skipped`)."""
    out_p = Path(out_dir)
    if _is_protected_completed_dir(out_p):
        return
    state = read_studio_state(out_p)
    state.setdefault("gates", {})[gate] = {
        "status": status,
        "detail": detail,
        "updated_at": _now_iso(),
        **({"data": data} if data else {}),
    }
    state["updated_at"] = _now_iso()
    _atomic_write_json(out_p / STATE_FILENAME, state)
    emit_event(out_p, f"gate:{gate}", "gate", status, detail=detail)


@contextmanager
def stage_events(out_dir: Path | str, stage: str, slug: Optional[str] = None) -> Iterator[dict[str, Any]]:
    """Context manager emitting start/end events; yields a dict to collect `artifacts` / `detail`."""
    ctx: dict[str, Any] = {"artifacts": [], "detail": ""}
    t0 = time.perf_counter()
    emit_event(out_dir, stage, "start", "running", slug=slug)
    try:
        yield ctx
    except BaseException as exc:  # noqa: BLE001 - re-raised after logging
        code = getattr(exc, "exit_code", None)
        if code == 0:
            emit_event(out_dir, stage, "end", "passed", detail=ctx["detail"], artifacts=ctx["artifacts"], slug=slug)
        else:
            msg = ctx["detail"] or f"{type(exc).__name__}: {str(exc)[:400]}"
            emit_event(out_dir, stage, "end", "failed", detail=msg, artifacts=ctx["artifacts"], slug=slug)
        raise
    else:
        detail = ctx["detail"] or f"completed in {time.perf_counter() - t0:.1f}s"
        emit_event(out_dir, stage, "end", "passed", detail=detail, artifacts=ctx["artifacts"], slug=slug)


def studio_stage(stage: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Decorator for Typer commands taking a `manifest: Path` option. Resolves the episode output
    directory and wraps the command in `stage_events`. Commands without a manifest run unchanged.
    """

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            manifest_path = kwargs.get("manifest")
            if manifest_path is None:
                return fn(*args, **kwargs)
            try:
                from .schema import EpisodeManifest

                ep = EpisodeManifest.from_yaml(manifest_path)
                out_dir, slug = Path(ep.output_dir), ep.slug
            except Exception:  # noqa: BLE001 - let the command itself report manifest errors
                return fn(*args, **kwargs)
            with stage_events(out_dir, stage, slug=slug):
                return fn(*args, **kwargs)

        return wrapper

    return deco
