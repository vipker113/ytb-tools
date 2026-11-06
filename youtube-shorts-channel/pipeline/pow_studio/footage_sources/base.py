#!/usr/bin/env python3
"""
Studio v9 Footage Source base layer (`pow_studio.footage_sources.base`).

- `VideoCandidate` (re-exported by `pow_studio.video_sourcing` for backward compatibility).
- Polite cached HTTP client (per-host rate limit, retries with backoff, on-disk JSON/text cache).
- License normalization that defers to `rights_gate.validate_license_string` (the single authority).
- `LicenseEvidence` snapshots so every downloaded file carries auditable proof of its rights.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Protocol

CHANNEL_ROOT = Path(__file__).resolve().parents[3]
HTTP_CACHE_DIR = CHANNEL_ROOT / ".cache" / "http"
USER_AGENT = "ProofOfWonderHarvester/9.0 (science-documentary-pipeline; zero-cost; contact via repo owner)"

_HOST_MIN_INTERVAL_S = 0.6
_host_last_call: dict[str, float] = {}
_host_lock = threading.Lock()


@dataclass
class VideoCandidate:
    source_repo: str
    asset_id: str
    title: str
    description: str
    page_url: str
    download_url: str
    license_label: str
    width: int
    height: int
    human_interaction_score: float
    relevance_notes: str
    inferred_media_class: str = "REAL_VIDEO_ESTABLISHING"
    query_purpose: str = "general"
    # Studio v9 optional enrichment (defaults keep v8 behavior unchanged)
    preview_image_url: str = ""
    duration_s: float = 0.0
    license_url: str = ""
    required_attribution: str = ""
    creator_agency: str = ""
    third_party_audio_risk: bool = False
    source_flags: list[str] = field(default_factory=list)
    license_evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class LicenseEvidence:
    source_repo: str
    page_url: str
    raw_rights_text: str
    normalized_license: str
    license_url: str
    required_attribution: str
    fetched_at: str
    verified: bool
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence_sha256"] = hashlib.sha256(
            json.dumps({k: v for k, v in d.items() if k != "fetched_at"}, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]
        return d


class FootageSource(Protocol):
    name: str
    display_name: str
    default_enabled: bool

    def is_available(self) -> tuple[bool, str]: ...

    def search(self, query: str, purpose: str = "general", limit: int = 6) -> list[VideoCandidate]: ...


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def license_is_commercial_safe(label: str) -> bool:
    """Single authority: `rights_gate.validate_license_string` (rejects NC, ND, SA, unverified)."""
    from ..rights_gate import RightsViolationError, validate_license_string

    try:
        validate_license_string(label, "candidate")
        return True
    except RightsViolationError:
        return False


def _respect_rate_limit(url: str) -> None:
    """Per-host politeness: reserve the next slot under the lock, sleep outside it (hosts don't block each other)."""
    host = urllib.parse.urlparse(url).netloc
    with _host_lock:
        now = time.monotonic()
        slot = max(now, _host_last_call.get(host, 0.0) + _HOST_MIN_INTERVAL_S)
        _host_last_call[host] = slot
    wait = slot - time.monotonic()
    if wait > 0:
        time.sleep(wait)


def _cache_path(key: str) -> Path:
    return HTTP_CACHE_DIR / f"{hashlib.sha1(key.encode('utf-8')).hexdigest()}.json"


def http_request(
    url: str,
    *,
    method: str = "GET",
    json_body: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    as_json: bool = True,
    timeout_s: float = 20.0,
    retries: int = 2,
    cache_ttl_s: float = 7 * 24 * 3600,
) -> Any:
    """Polite HTTP with on-disk cache. Raises on final failure (callers decide how to degrade)."""
    body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    cache_key = f"{method} {url} {body.decode('utf-8') if body else ''} {as_json}"
    cp = _cache_path(cache_key)
    if cache_ttl_s > 0 and cp.exists() and (time.time() - cp.stat().st_mtime) < cache_ttl_s:
        try:
            return json.loads(cp.read_text(encoding="utf-8"))["payload"]
        except (json.JSONDecodeError, KeyError, OSError):
            pass

    hdrs = {"User-Agent": USER_AGENT, "Accept": "application/json" if as_json else "text/html,*/*"}
    if body is not None:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})

    last_exc: Optional[Exception] = None
    for attempt in range(retries + 1):
        _respect_rate_limit(url)
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            payload: Any = json.loads(raw) if as_json else raw
            if cache_ttl_s > 0:
                HTTP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                tmp = cp.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps({"url": url, "payload": payload}), encoding="utf-8")
                os.replace(tmp, cp)
            return payload
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in (400, 401, 403, 404):
                break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ConnectionError) as exc:
            last_exc = exc
        time.sleep(0.8 * (2**attempt))
    raise RuntimeError(f"HTTP failed for {url}: {last_exc}")


def probe_remote_video(url: str, timeout_s: float = 25.0) -> dict[str, Any]:
    """ffprobe a remote media URL (reads headers only). Returns {} on failure."""
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height,codec_name:format=duration",
                "-of", "json", "-user_agent", USER_AGENT, url,
            ],
            capture_output=True, text=True, timeout=timeout_s,
        )
        if r.returncode != 0:
            return {}
        d = json.loads(r.stdout or "{}")
        st = (d.get("streams") or [{}])[0]
        return {
            "width": int(st.get("width") or 0),
            "height": int(st.get("height") or 0),
            "codec": st.get("codec_name", ""),
            "duration_s": float((d.get("format") or {}).get("duration") or 0.0),
        }
    except (subprocess.TimeoutExpired, OSError, ValueError, json.JSONDecodeError):
        return {}


def strip_html(text: str) -> str:
    import html
    import re

    t = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    return re.sub(r"[ \t]+", " ", t).strip()
