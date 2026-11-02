"""
Two-way bridge between Proof of Wonder Documentary Engine (`pow_studio`) and
SubPulse Autopilot Web (`ytb-tools` running at http://localhost:3000).

Zero-cost ($0) local integration:
  - `fetch_next_sprint_episode`: GET /api/pipeline (optionally claims `in_progress`).
  - `publish_episode_via_subpulse`: POST /api/youtube/upload using `localEpisodeSlug`
    so Next.js streams `<slug>.mp4` + `thumbnail.jpg` directly from Mac SSD to
    YouTube Data API v3, sets golden-hour schedule (17:15 VN / 10:15 UTC), and
    advances the 5-day Sprint when `advance_sprint=True`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Literal

from pow_studio.schema import EpisodeManifest

DEFAULT_SUBPULSE_URL = "http://localhost:3000"
SNAPSHOT_PATH = (
    Path(__file__).resolve().parent.parent.parent / "output" / ".subpulse_next_episode.json"
)

PublishMode = Literal["schedule_golden", "public_now", "private_draft"]


def _json_request(
    url: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error") or err_body
        except json.JSONDecodeError:
            msg = err_body
        raise RuntimeError(f"SubPulse HTTP {exc.code} ({url}): {msg}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot connect to SubPulse Web at {url} ({exc.reason}). "
            "Make sure `npm run dev` is running in /Applications/code/science-knowledge/ytb-tools."
        ) from exc


def _multipart_form_post(
    url: str,
    fields: dict[str, str],
    timeout_s: float = 300.0,
) -> dict[str, Any]:
    boundary = f"----PoWSubPulseBoundary{uuid.uuid4().hex}"
    lines: list[bytes] = []
    for key, val in fields.items():
        lines.append(f"--{boundary}\r\n".encode("utf-8"))
        lines.append(
            f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8")
        )
        lines.append(f"{val}\r\n".encode("utf-8"))
    lines.append(f"--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(lines)

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error") or err_body
        except json.JSONDecodeError:
            msg = err_body
        raise RuntimeError(f"SubPulse Upload HTTP {exc.code}: {msg}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot connect to SubPulse Web at {url} ({exc.reason})."
        ) from exc


def fetch_next_sprint_episode(
    base_url: str = DEFAULT_SUBPULSE_URL,
    claim: bool = False,
) -> dict[str, Any]:
    """Fetch active channel & next pending Sprint episode from SubPulse `/api/pipeline`."""
    clean_base = base_url.rstrip("/")
    data = _json_request(f"{clean_base}/api/pipeline", method="GET")
    if not data.get("ok"):
        raise RuntimeError(f"SubPulse /api/pipeline returned error: {data}")

    next_ep = data.get("nextEpisode")
    if claim and isinstance(next_ep, dict) and next_ep.get("episodeId"):
        claim_res = _json_request(
            f"{clean_base}/api/pipeline",
            method="POST",
            payload={
                "action": "in_progress",
                "episodeId": str(next_ep["episodeId"]),
            },
        )
        if claim_res.get("nextEpisode"):
            data["nextEpisode"] = claim_res["nextEpisode"]

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return data


def publish_episode_via_subpulse(
    ep: EpisodeManifest,
    base_url: str = DEFAULT_SUBPULSE_URL,
    publish_mode: PublishMode = "schedule_golden",
    advance_sprint: bool = True,
    episode_id: str | None = None,
    custom_publish_at_iso: str | None = None,
) -> dict[str, Any]:
    """
    Trigger direct Mac SSD -> YouTube Studio upload via SubPulse `/api/youtube/upload`.
    Automatically attaches `<slug>.mp4`, `thumbnail.jpg`, and `youtube_metadata.md`.
    """
    mp4_path = Path(ep.output_dir) / f"{ep.slug}.mp4"
    if not mp4_path.is_file():
        raise FileNotFoundError(
            f"Master MP4 not found at {mp4_path}. Run `render` and `qc` before `publish`."
        )

    fields: dict[str, str] = {
        "localEpisodeSlug": ep.slug,
        "publishMode": publish_mode,
        "advanceSprint": "true" if advance_sprint else "false",
    }
    if episode_id:
        fields["episodeId"] = episode_id
    if custom_publish_at_iso:
        fields["customPublishAtIso"] = custom_publish_at_iso

    clean_base = base_url.rstrip("/")
    res = _multipart_form_post(f"{clean_base}/api/youtube/upload", fields=fields)
    if not res.get("ok"):
        raise RuntimeError(res.get("error") or f"Upload failed: {res}")
    return res
