#!/usr/bin/env python3
"""
Phrase-to-timestamp anchoring and cut/hook guardrails for Studio v9 Mechanism Overlays
(`pow_studio.mechanism_overlay.anchoring`).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass
from typing import Any, Optional

from ..schema import EpisodeManifest, MechanismOverlaySpec, ShotSpecModel, resolve_timed_shots


_ONES_MAP: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
}
_TENS_MAP: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}


def _norm_words(text: str) -> list[str]:
    raw = [w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if w]
    out: list[str] = []
    i = 0
    while i < len(raw):
        w = raw[i]
        if w in _TENS_MAP:
            val = _TENS_MAP[w]
            if i + 1 < len(raw) and raw[i + 1] in _ONES_MAP and 1 <= _ONES_MAP[raw[i + 1]] <= 9:
                val += _ONES_MAP[raw[i + 1]]
                i += 2
            else:
                i += 1
            out.append(str(val))
        elif w in _ONES_MAP:
            out.append(str(_ONES_MAP[w]))
            i += 1
        else:
            out.append(w)
            i += 1
    return out


@dataclass
class ResolvedOverlayTiming:
    overlay_id: str
    template: str
    start_s: float
    end_s: float
    duration_s: float
    start_frame: int
    n_frames: int
    anchor_source: str
    matched_phrase_score: float
    overlapping_shot_sids: list[str]
    crosses_hard_cut: bool
    in_hook_zone: bool
    span_cut_allowed: bool
    diagnostic_note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _match_phrase_start_in_words(
    words: list[dict[str, Any]],
    phrase: str,
    seg_id: Optional[str] = None,
) -> tuple[Optional[float], float, str]:
    """
    Fuzzy-match `phrase` against `word_timings.json` word tokens (preferring `seg_id` first).
    Returns `(start_s, match_ratio, source_kind)`.
    """
    target_toks = _norm_words(phrase)
    if not target_toks or not words:
        return None, 0.0, "empty"

    def _search_pool(pool: list[dict[str, Any]]) -> tuple[Optional[float], float]:
        expanded: list[tuple[str, float]] = []
        for w in pool:
            wtoks = _norm_words(str(w.get("word") or ""))
            t_start = float(w.get("start") or 0.0)
            for wt in wtoks:
                expanded.append((wt, t_start))
        if not expanded:
            return None, 0.0

        k = len(target_toks)
        target_str = " ".join(target_toks)
        best_score = 0.0
        best_t: Optional[float] = None
        min_win = max(1, k - 1)
        max_win = min(len(expanded), k + 2)
        for win_len in range(min_win, max_win + 1):
            for i in range(0, len(expanded) - win_len + 1):
                cand_str = " ".join(tok for tok, _ in expanded[i : i + win_len])
                ratio = difflib.SequenceMatcher(None, target_str, cand_str).ratio()
                if ratio > best_score:
                    best_score = ratio
                    best_t = expanded[i][1]
        return best_t, best_score

    if seg_id:
        seg_words = [w for w in words if str(w.get("seg_id") or "") == seg_id]
        t_seg, sc_seg = _search_pool(seg_words)
        if t_seg is not None and sc_seg >= 0.62:
            return t_seg, round(sc_seg, 3), f"phrase_in_{seg_id}"

    t_all, sc_all = _search_pool(words)
    if t_all is not None and sc_all >= 0.62:
        return t_all, round(sc_all, 3), "phrase_global"
    return None, round(sc_all, 3), "unmatched"


def resolve_overlay_timings(
    manifest: EpisodeManifest,
    wt: dict[str, Any],
    timed_shots: Optional[list[ShotSpecModel]] = None,
    fps: int = 30,
) -> list[ResolvedOverlayTiming]:
    """
    Resolve every `MechanismOverlaySpec` in `manifest.mechanism_overlays` to frame-accurate
    timeline coordinates `[start_s, end_s]`, detecting Hook-zone (`< 1.5s`) and hard-cut collisions.
    """
    overlays = list(getattr(manifest, "mechanism_overlays", []) or [])
    if not overlays:
        return []

    style = manifest.resolve_style_profile()
    hook_forbid_s = float(style.mechanism_overlays.forbid_in_hook_s)
    total_dur = max(0.2, float(wt.get("total_duration_s") or manifest.shots[-1].end_s))
    n_total_frames = int(wt.get("total_frames_30fps") or round(total_dur * fps))
    shots = timed_shots if timed_shots is not None else resolve_timed_shots(manifest, n_total_frames, fps=fps)

    words = list(wt.get("words") or [])
    segs = {str(s.get("seg_id") or ""): s for s in (wt.get("segments") or [])}

    resolved: list[ResolvedOverlayTiming] = []
    for ov in overlays:
        anch = ov.anchor
        note = ""
        if anch.start_s is not None:
            raw_start = float(anch.start_s) + float(anch.lead_in_s)
            match_score = 1.0
            src_kind = "explicit_start_s"
        else:
            t_match, match_score, src_kind = _match_phrase_start_in_words(
                words,
                phrase=anch.phrase or "",
                seg_id=anch.seg_id,
            )
            if t_match is not None:
                raw_start = t_match + float(anch.lead_in_s)
            elif anch.seg_id and anch.seg_id in segs:
                raw_start = float(segs[anch.seg_id].get("start") or 0.0) + max(0.0, float(anch.lead_in_s))
                src_kind = f"fallback_seg_{anch.seg_id}"
                note = f"Phrase '{anch.phrase}' matched {match_score:.2f}; anchored to segment {anch.seg_id} start."
            else:
                raw_start = 2.0
                src_kind = "fallback_default"
                note = f"Could not resolve anchor phrase '{anch.phrase}'."

        raw_start = max(0.0, min(total_dur - 0.2, raw_start))
        raw_end = min(total_dur, raw_start + float(ov.hold_s))

        # Snap to exact frame grid
        start_frame = max(0, int(round(raw_start * fps)))
        end_frame = min(n_total_frames, max(start_frame + 1, int(round(raw_end * fps))))
        start_s = round(start_frame / float(fps), 4)
        end_s = round(end_frame / float(fps), 4)

        # If not allowed to span a hard cut, trim <=0.18s tail overshoot into next cut cleanly
        if not ov.span_cut:
            primary_shot = next((s for s in shots if s.start_s <= start_s + 0.02 < s.end_s), None)
            if primary_shot is not None and end_s > primary_shot.end_s:
                next_shot = next((s for s in shots if abs(s.start_s - primary_shot.end_s) < 0.05), None)
                is_hard_next = next_shot is None or next_shot.transition_in == "cut"
                overshoot = end_s - primary_shot.end_s
                if is_hard_next and overshoot <= 0.18 and (primary_shot.end_s - start_s) >= 1.2:
                    end_frame = max(start_frame + 1, int(round(primary_shot.end_s * fps)))
                    end_s = round(end_frame / float(fps), 4)

        n_frames = max(1, end_frame - start_frame)
        dur_s = round(n_frames / float(fps), 4)

        # Identify overlapping shots & whether a hard cut is crossed inside (start_s + 0.03, end_s - 0.03)
        ov_shots = [s for s in shots if s.end_s > start_s + 0.035 and s.start_s < end_s - 0.035]
        crosses_cut = False
        if len(ov_shots) > 1:
            for j in range(1, len(ov_shots)):
                if ov_shots[j].transition_in == "cut":
                    crosses_cut = True
                    break

        in_hook = start_s < hook_forbid_s - 1e-4

        resolved.append(
            ResolvedOverlayTiming(
                overlay_id=ov.overlay_id,
                template=ov.template,
                start_s=start_s,
                end_s=end_s,
                duration_s=dur_s,
                start_frame=start_frame,
                n_frames=n_frames,
                anchor_source=src_kind,
                matched_phrase_score=match_score,
                overlapping_shot_sids=[s.sid for s in ov_shots],
                crosses_hard_cut=crosses_cut,
                in_hook_zone=in_hook,
                span_cut_allowed=bool(ov.span_cut),
                diagnostic_note=note,
            )
        )

    return resolved
