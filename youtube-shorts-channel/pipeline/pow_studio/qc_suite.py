#!/usr/bin/env python3
"""
Step 6: Documentary Quality Assurance & Visual Review Suite (`pow_studio.qc_suite` v3.0).

Implements Section 11 of the Proof of Wonder Documentary Workflow:
1. Container, codec, resolution (`1080x1920`), `9:16` aspect ratio, `30/1` CFR, and exact
   narration-locked duration verification.
2. Zero unintended black frames (`blackdetect`) and EBU R128 loudness / speech-margin audit.
3. Programmatic Full-Canvas & Zero-Letterbox / Zero-Inset-Frame Audit (`audit_full_canvas_coverage`)
   detecting black bars, blurred pillarbox/letterbox margins, or inset rectangle borders.
4. Programmatic Overlay-Cleanliness Regression Audit (`audit_overlay_cleanliness`) verifying
   zero rings, zero source banners, zero HUDs, zero warning pills, and zero burned-in title cards
   in `pow_documentary_v3` mode.
5. Shot-plan, moving-footage ratio, speech-boundary alignment, and dissolve audit via `shot_planner`.
6. Faster-Whisper (`medium.en`, `vad_filter=True`) lexical & subtitle timing verification + WCAG AAA.
7. Non-destructive preservation verification for existing completed episodes.
8. Exports comprehensive visual contact sheets (`contact_sheet.jpg`, `transitions_contact_sheet.jpg`,
   `first_3_seconds_audit_sheet.jpg`, `ending_audit_sheet.jpg`, `native_1to1_pixel_qc_sheet.jpg`).
"""

from __future__ import annotations

import difflib
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from .compositor import (
    CAPTION_EMPH_RGBA,
    FONT_BOLD,
    FONT_MED,
    compute_overlay_states,
    get_font,
    wrap_caption_lines,
)
from .schema import PROTECTED_COMPLETED_OUTPUT_DIRS, EpisodeManifest, ShotSpecModel, resolve_timed_shots
from .shot_planner import audit_shot_plan_and_alignment
from .story_engine import audit_narrative_momentum, evaluate_opening_hook_candidates
from .style_profile import DocumentaryStyleProfile
from .visual_intelligence import score_episode_visual_plan
from .voice_studio import verify_voice_approval_lock

ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def _srgb_channel_to_linear(c255: float) -> float:
    c = max(0.0, min(1.0, c255 / 255.0))
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance_rgb(rgb: tuple[float, float, float]) -> float:
    r, g, b = (_srgb_channel_to_linear(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def compute_wcag_contrast_ratio(fg_rgb: tuple[float, float, float], bg_rgb: tuple[float, float, float]) -> float:
    l1 = relative_luminance_rgb(fg_rgb)
    l2 = relative_luminance_rgb(bg_rgb)
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return round((hi + 0.05) / (lo + 0.05), 2)


def blend_rgba_over_rgb(fg_rgba: tuple[int, int, int, int], backdrop_rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    a = fg_rgba[3] / 255.0
    return (
        fg_rgba[0] * a + backdrop_rgb[0] * (1.0 - a),
        fg_rgba[1] * a + backdrop_rgb[1] * (1.0 - a),
        fg_rgba[2] * a + backdrop_rgb[2] * (1.0 - a),
    )


_NUMERAL_EXPANSIONS: dict[str, list[str]] = {
    "2026": ["twenty", "twenty", "six"],
    "2025": ["twenty", "twenty", "five"],
    "2024": ["twenty", "twenty", "four"],
    "2022": ["twenty", "twenty", "two"],
    "2021": ["twenty", "twenty", "one"],
    "2018": ["twenty", "eighteen"],
    "2017": ["twenty", "seventeen"],
    "2014": ["twenty", "fourteen"],
    "2013": ["twenty", "thirteen"],
    "2010": ["twenty", "ten"],
    "1986": ["nineteen", "eighty", "six"],
    "1963": ["nineteen", "sixty", "three"],
    "1960": ["nineteen", "sixty"],
    "17000": ["seventeen", "thousand"],
    "2600": ["two", "thousand", "six", "hundred"],
    "1770": ["one", "thousand", "seven", "hundred", "seventy"],
    "1067": ["one", "thousand", "sixty", "seven"],
    "1000": ["one", "thousand"],
    "800": ["eight", "hundred"],
    "660": ["six", "hundred", "sixty"],
    "600": ["six", "hundred"],
    "500": ["five", "hundred"],
    "410": ["four", "hundred", "ten"],
    "400": ["four", "hundred"],
    "300": ["three", "hundred"],
    "167": ["one", "hundred", "sixty", "seven"],
    "160": ["one", "hundred", "sixty"],
    "150": ["one", "hundred", "fifty"],
    "109": ["one", "hundred", "nine"],
    "95": ["ninety", "five"],
    "60": ["sixty"],
    "58": ["fifty", "eight"],
    "55": ["fifty", "five"],
    "35": ["thirty", "five"],
    "26": ["twenty", "six"],
    "18": ["eighteen"],
    "17": ["seventeen"],
    "14": ["fourteen"],
    "11": ["eleven"],
    "10": ["ten"],
    "7": ["seven"],
    "3": ["three"],
    "2": ["two"],
    "1": ["one"],
    "0": ["zero"],
    "vii": ["seven"],
    "grey": ["gray"],
    "fluoride": ["fluorite"],
    "i7": ["iceseven"],
    "kawa": ["kawah"],
    "fiftyeightdegree": ["fiftyeight", "degree"],
}

_BIGRAM_CANONICAL: dict[tuple[str, str], str] = {
    ("haptic", "fights"): "haptophytes",
    ("hapto", "fights"): "haptophytes",
    ("hapto", "phytes"): "haptophytes",
    ("dino", "flagellates"): "dinoflagellates",
    ("micro", "eukaryotes"): "microeukaryotes",
    ("marine", "related"): "marinerelated",
    ("iron", "rich"): "ironrich",
    ("mc", "murdo"): "mcmurdo",
    ("sub", "glacial"): "subglacial",
    ("sea", "water"): "seawater",
    ("sea", "floor"): "seafloor",
    ("deep", "sea"): "deepsea",
    ("oxygen", "free"): "oxygenfree",
    ("hyper", "saline"): "hypersaline",
    ("chemo", "synthetic"): "chemosynthetic",
    ("chemo", "synthesis"): "chemosynthesis",
    ("bathy", "modiolus"): "bathymodiolus",
    ("tube", "worms"): "tubeworms",
    ("pycno", "cline"): "pycnocline",
    ("halo", "cline"): "halocline",
    ("flash", "floods"): "flashfloods",
    ("mirror", "like"): "mirrorlike",
    ("paper", "thin"): "paperthin",
    ("water", "repellent"): "waterrepellent",
    ("three", "d"): "threed",
    ("lava", "tube"): "lavatube",
    ("rock", "eating"): "rockeating",
    ("space", "faring"): "spacefaring",
    ("sun", "like"): "sunlike",
    ("self", "destruction"): "selfdestruction",
    ("head", "start"): "headstart",
    ("light", "speed"): "lightspeed",
    ("ring", "woodite"): "ringwoodite",
    ("kimber", "lite"): "kimberlite",
    ("pegma", "tite"): "pegmatite",
    ("hard", "rock"): "hardrock",
    ("super", "heated"): "superheated",
    ("super", "deep"): "superdeep",
    ("high", "pressure"): "highpressure",
    ("time", "capsules"): "timecapsules",
    ("time", "capsule"): "timecapsule",
    ("x", "ray"): "xray",
    ("x", "rays"): "xrays",
    ("ice", "seven"): "iceseven",
    ("razor", "sharp"): "razorsharp",
    ("deep", "earth"): "deepearth",
    ("locked", "off"): "lockedoff",
    ("pitch", "black"): "pitchblack",
    ("rust", "red"): "rustred",
    ("under", "sea"): "undersea",
    ("life", "support"): "lifesupport",
    ("electric", "blue"): "electricblue",
    ("neon", "green"): "neongreen",
    ("mineral", "rich"): "mineralrich",
    ("fifty", "five"): "fiftyfive",
    ("fifty", "eight"): "fiftyeight",
    ("ninety", "five"): "ninetyfive",
    ("ground", "water"): "groundwater",
    ("air", "ways"): "airways",
    ("down", "hill"): "downhill",
    ("koto", "paxi"): "cotopaxi",
}

_ONES_WORDS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS_WORDS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _int_to_words(n: int) -> list[str]:
    if n < 20:
        return [_ONES_WORDS[n]]
    if n < 100:
        q, r = divmod(n, 10)
        return [_TENS_WORDS[q]] + ([_ONES_WORDS[r]] if r else [])
    if n < 1000:
        q, r = divmod(n, 100)
        return [_ONES_WORDS[q], "hundred"] + (_int_to_words(r) if r else [])
    if n < 1_000_000:
        q, r = divmod(n, 1000)
        return _int_to_words(q) + ["thousand"] + (_int_to_words(r) if r else [])
    return [str(n)]


def canonicalize_tokens_for_asr(tokens: list[str]) -> list[str]:
    pre_tokens: list[str] = []
    for raw in tokens:
        for part in raw.replace("—", " ").replace("-", " ").split():
            pre_tokens.extend(re.findall(r"\d+|[a-z']+", part.lower()))
    pre_tokens = [t for t in pre_tokens if t]

    joined_nums: list[str] = []
    idx = 0
    while idx < len(pre_tokens):
        cur = pre_tokens[idx]
        if cur.isdigit() and idx + 1 < len(pre_tokens):
            nxt = pre_tokens[idx + 1]
            if nxt.isdigit() and len(nxt) == 3 and len(cur) <= 3:
                joined_nums.append(cur + nxt)
                idx += 2
                continue
        joined_nums.append(cur)
        idx += 1

    expanded: list[str] = []
    for t in joined_nums:
        if t in _NUMERAL_EXPANSIONS:
            expanded.extend(_NUMERAL_EXPANSIONS[t])
        elif t.isdigit() and int(t) < 1_000_000:
            val = int(t)
            if 1800 <= val <= 1999:
                expanded.extend(_int_to_words(val // 100) + (_int_to_words(val % 100) if val % 100 else ["hundred"]))
            else:
                expanded.extend(_int_to_words(val))
        else:
            expanded.append(t)

    cleaned: list[str] = []
    for idx, tok in enumerate(expanded):
        if tok == "and" and idx > 0 and expanded[idx - 1] == "hundred":
            continue
        cleaned.append(tok)

    merged: list[str] = []
    i = 0
    while i < len(cleaned):
        if i + 1 < len(cleaned) and (cleaned[i], cleaned[i + 1]) in _BIGRAM_CANONICAL:
            merged.append(_BIGRAM_CANONICAL[(cleaned[i], cleaned[i + 1])])
            i += 2
        else:
            merged.append(cleaned[i])
            i += 1
    return merged


def _grab_frame(
    mp4: Path,
    t: float,
    dst: Path,
    scale: tuple[int, int] | None = None,
    exact_frame: int | None = None,
) -> Image.Image:
    if exact_frame is not None:
        sc = f",scale={scale[0]}:{scale[1]}" if scale else ""
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(mp4),
                "-vf",
                f"select=eq(n\\,{exact_frame}){sc}",
                "-frames:v",
                "1",
                str(dst),
            ]
        )
    else:
        vf = ["-vf", f"scale={scale[0]}:{scale[1]}"] if scale else []
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, t - 1.5):.3f}",
                "-i",
                str(mp4),
                "-ss",
                f"{min(1.5, t):.3f}",
                "-frames:v",
                "1",
                *vf,
                str(dst),
            ]
        )
    return Image.open(dst).convert("RGB")


def _measure_wav_lufs(wav_path: Path) -> float:
    if not wav_path.exists():
        return -70.0
    err = _run(["ffmpeg", "-hide_banner", "-i", str(wav_path), "-af", "ebur128", "-f", "null", "-"]).stderr
    summ = err[err.rfind("Summary:") :]
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    return float(m.group(1)) if m else -70.0


def audit_full_canvas_coverage(
    mp4: Path,
    timed_shots: list[ShotSpecModel],
    style: DocumentaryStyleProfile,
    qc_scr: Path,
) -> dict[str, Any]:
    """
    Programmatically verify that every rendered shot fills the 1080x1920 vertical canvas
    edge-to-edge without black letterbox/pillarbox bands or inset rectangle borders.
    """
    suspicious_shots: list[dict[str, Any]] = []
    per_shot_metrics: list[dict[str, Any]] = []
    max_band_px = style.qa.max_letterbox_or_border_band_px

    for s in timed_shots:
        tm = 0.5 * (s.start_s + s.end_s)
        im = _grab_frame(mp4, tm, qc_scr / f"fc_{s.sid}.png")
        arr = np.asarray(im, dtype=np.float32)
        luma = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]

        # 1. Detect solid black/constant digital letterbox rows from top/bottom and pillarbox cols from left/right.
        # Distinguish flat digital letterbox bars (row_mean < 4.5 and row_std < 0.85) from natural 35mm-grained
        # night sky or subterranean cave shadows so human scale silhouettes at frame edges are never cropped out.
        row_std = np.std(luma, axis=1)
        row_mean = np.mean(luma, axis=1)
        col_std = np.std(luma, axis=0)
        col_mean = np.mean(luma, axis=0)

        top_black_px = int(np.argmax(~((row_mean < 4.5) & (row_std < 0.85))))
        if np.all((row_mean < 4.5) & (row_std < 0.85)):
            top_black_px = luma.shape[0]
        bot_black_px = int(np.argmax(~((row_mean[::-1] < 4.5) & (row_std[::-1] < 0.85))))
        left_black_px = int(np.argmax(~((col_mean < 4.5) & (col_std < 0.85))))
        right_black_px = int(np.argmax(~((col_mean[::-1] < 4.5) & (col_std[::-1] < 0.85))))

        # 2. Detect inset rectangle frame border (legacy `still_window` / `video_window` signature:
        #    sharp vertical edge lines near x=30..46 and x=1034..1050 spanning y=320..1280)
        gx_mid = np.abs(luma[340:1240, 1:] - luma[340:1240, :-1])
        col_edge_profile = np.mean(gx_mid, axis=0)
        left_border_spike = float(np.max(col_edge_profile[26:48]) / max(1.0, float(np.median(col_edge_profile))))
        right_border_spike = float(np.max(col_edge_profile[1030:1052]) / max(1.0, float(np.median(col_edge_profile))))
        has_inset_border = (left_border_spike > 7.5 and right_border_spike > 7.5)

        max_black_bar = max(top_black_px, bot_black_px, left_black_px, right_black_px)
        flagged = (max_black_bar > max_band_px) or has_inset_border

        entry = {
            "sid": s.sid,
            "kind": s.kind,
            "sample_t_s": round(tm, 2),
            "top_black_px": top_black_px,
            "bottom_black_px": bot_black_px,
            "left_black_px": left_black_px,
            "right_black_px": right_black_px,
            "left_inset_spike_ratio": round(left_border_spike, 2),
            "right_inset_spike_ratio": round(right_border_spike, 2),
            "has_inset_border": has_inset_border,
            "full_canvas_pass": not flagged,
        }
        per_shot_metrics.append(entry)
        if flagged:
            suspicious_shots.append(entry)

    return {
        "audited_shots": len(per_shot_metrics),
        "suspicious_shots_count": len(suspicious_shots),
        "suspicious_shots": suspicious_shots,
        "all_full_canvas_pass": len(suspicious_shots) == 0,
        "shots": per_shot_metrics,
    }


def audit_overlay_cleanliness(
    manifest: EpisodeManifest,
    wt: dict,
    style: DocumentaryStyleProfile,
) -> dict[str, Any]:
    """
    Regression check verifying that AI-looking decorative graphics (rings, HUD locators,
    source banners, warning pills, burned-in opening cover cards, closing credit cards)
    are absent from the rendered state timeline when disabled by the style profile.
    """
    states, _, _, timed_shots, _ = compute_overlay_states(manifest, wt)

    rings_active = sum(
        1 for s in timed_shots if s.scale_annotation is not None and style.overlays.show_animated_circles_or_rings
    )
    locators_active = sum(
        1 for s in timed_shots if s.locator_annotation is not None and style.overlays.show_locator_hud_cards
    )
    source_banners_active = sum(1 for _, _, st in states if st.get("label"))
    callouts_active = sum(1 for _, _, st in states if st.get("callout"))
    cover_burned = any(bool(st.get("cover")) for _, _, st in states)
    credit_burned = any(bool(st.get("credit")) for _, _, st in states)
    context_notes_used = sorted({str(st["context_note"]) for _, _, st in states if st.get("context_note")})

    violations: list[str] = []
    if not style.overlays.show_animated_circles_or_rings and rings_active > 0:
        violations.append(f"Animated circles/rings active on {rings_active} shots")
    if not style.overlays.show_locator_hud_cards and locators_active > 0:
        violations.append(f"Corner locator HUD active on {locators_active} shots")
    if not style.overlays.show_source_banners_in_video and source_banners_active > 0:
        violations.append(f"Visible source banners active in {source_banners_active} timeline states")
    if not style.overlays.show_callout_warning_badges and callouts_active > 0:
        violations.append(f"Warning callout pills active in {callouts_active} timeline states")
    if not style.overlays.burn_opening_cover_card_into_video and cover_burned:
        violations.append("Burned-in opening cover card active on Frame 0")
    if not style.overlays.show_closing_credit_card_in_video and credit_burned:
        violations.append("Closing credit card burned into video")
    if len(context_notes_used) > style.overlays.max_context_labels_per_video:
        violations.append(f"Too many context notes ({len(context_notes_used)} > {style.overlays.max_context_labels_per_video})")

    return {
        "style_profile": style.profile_name,
        "scale_rings_rendered": rings_active,
        "locator_huds_rendered": locators_active,
        "source_banners_rendered": source_banners_active,
        "callout_badges_rendered": callouts_active,
        "opening_cover_card_burned": cover_burned,
        "closing_credit_burned": credit_burned,
        "minimal_context_notes_used": context_notes_used,
        "violations": violations,
        "clean_documentary_pass": len(violations) == 0,
    }


def audit_motion_smoothness(mp4: Path, timed_shots: list[ShotSpecModel], scratch_qc: Path, fps: int = 30) -> dict:
    """
    Sample 12 consecutive frames (0.40s @ 30fps) inside up to 4 full-screen shots,
    verifying smooth frame-to-frame continuity with zero mid-shot jump spikes.
    """
    candidates = [
        s
        for s in timed_shots
        if s.kind in ("video_full", "still_full", "still_parallax_25d", "triptych_hook") and (s.end_s - s.start_s) >= 3.2
    ][:4]
    sampled = []
    worst_ratio = 1.0
    all_smooth = True

    for s in candidates:
        t_mid = 0.5 * (s.start_s + s.end_s) - 0.20
        t_mid = max(s.start_s + 0.8, min(s.end_s - 0.8, t_mid))
        t_mid = round(t_mid * fps) / float(fps)
        seq_dir = scratch_qc / f"mot_{s.sid}"
        seq_dir.mkdir(parents=True, exist_ok=True)
        for old in seq_dir.glob("*.png"):
            old.unlink()
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, t_mid - 2.0):.4f}",
                "-i",
                str(mp4),
                "-ss",
                f"{min(2.0, t_mid):.4f}",
                "-vf",
                "crop=880:760:100:360",
                "-frames:v",
                "13",
                str(seq_dir / "m_%02d.png"),
            ]
        )
        frames = sorted(seq_dir.glob("m_*.png"))[1:]
        if len(frames) < 4:
            continue
        lums = [np.asarray(Image.open(fp).convert("L"), dtype=np.float32) for fp in frames]
        deltas = [float(np.mean(np.abs(lums[k + 1] - lums[k]))) for k in range(len(lums) - 1)]
        med_d = max(1e-4, float(np.median(deltas)))
        min_d = float(np.min(deltas))
        max_d = float(np.max(deltas))
        jump_ratio = max_d / med_d
        worst_ratio = max(worst_ratio, jump_ratio)
        ok = jump_ratio < 5.5
        if not ok:
            all_smooth = False
        sampled.append(
            {
                "sid": s.sid,
                "kind": s.kind,
                "min_frame_delta_luma": round(min_d, 4),
                "median_frame_delta_luma": round(med_d, 4),
                "max_to_median_ratio": round(jump_ratio, 3),
                "smooth": ok,
            }
        )

    return {
        "sampled_shots": sampled,
        "worst_jump_ratio": round(worst_ratio, 3),
        "all_smooth": all_smooth,
    }


def verify_protected_projects_intact() -> dict[str, Any]:
    """Verify existing completed projects were not deleted or truncated during refactored runs."""
    bases = [ROOT / "output" / "hidden-earth", ROOT / "output" / "space-and-universe"]
    checked: dict[str, Any] = {}
    all_intact = True
    for slug in sorted(PROTECTED_COMPLETED_OUTPUT_DIRS):
        for base in bases:
            d = base / slug
            if d.exists():
                mp4s = sorted(d.glob("*.mp4"))
                mp4 = (d / f"{slug}.mp4") if (d / f"{slug}.mp4").exists() else (mp4s[0] if mp4s else d / f"{slug}.mp4")
                exists_ok = mp4.exists() and mp4.stat().st_size > 1_000_000
                checked[slug] = {
                    "mp4_exists": mp4.exists(),
                    "size_mb": round(mp4.stat().st_size / (1024 * 1024), 2) if mp4.exists() else 0.0,
                    "intact": exists_ok,
                }
                if not exists_ok:
                    all_intact = False
    return {"checked_projects": checked, "all_intact": all_intact}


def run_episode_qc(manifest: EpisodeManifest, wt: dict) -> dict:
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    out_w, out_h = style.output.width, style.output.height
    out_dir = Path(manifest.output_dir)
    mp4 = out_dir / f"{manifest.slug}.mp4"
    qc_scr = out_dir / ".scratch_build" / "qc"
    qc_scr.mkdir(parents=True, exist_ok=True)
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)

    fb = get_font(FONT_BOLD, 20)
    fm = get_font(FONT_MED, 15)
    ft = get_font(FONT_BOLD, 27)

    report: dict[str, Any] = {"style_profile": style.profile_name}

    # 1. ffprobe stream & container validation
    pr = json.loads(_run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(mp4)]).stdout)
    v = next(s for s in pr["streams"] if s["codec_type"] == "video")
    a = next(s for s in pr["streams"] if s["codec_type"] == "audio")
    dur = float(pr["format"]["duration"])
    report["ffprobe"] = {
        "duration_s": round(dur, 3),
        "within_target_window": manifest.target_duration_min_s <= dur <= manifest.target_duration_max_s,
        "exact_frame_match": int(v.get("nb_frames", 0)) == int(wt["total_frames_30fps"]),
        "size_bytes": int(pr["format"]["size"]),
        "size_mb": round(int(pr["format"]["size"]) / (1024 * 1024), 2),
        "video_codec": v["codec_name"],
        "profile": v.get("profile", "hardware/default"),
        "width": int(v["width"]),
        "height": int(v["height"]),
        "dimensions_exact": int(v["width"]) == out_w and int(v["height"]) == out_h,
        "r_frame_rate": v["r_frame_rate"],
        "avg_frame_rate": v["avg_frame_rate"],
        "nb_frames": int(v.get("nb_frames", 0)),
        "pix_fmt": v["pix_fmt"],
        "color_space": v.get("color_space", "bt709"),
        "audio_codec": a["codec_name"],
        "sample_rate": int(a["sample_rate"]),
        "channels": int(a["channels"]),
    }

    # 2. blackdetect & integrated loudness
    bd = _run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-vf", "blackdetect=d=0.04:pix_th=0.10", "-an", "-f", "null", "-"]).stderr
    report["black_segments"] = re.findall(r"black_start:\S+ black_end:\S+ black_duration:\S+", bd)

    ln = _run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"]).stderr
    summ = ln[ln.rfind("Summary:") :]
    voice_lufs = _measure_wav_lufs(out_dir / "work_audio" / "narration_norm.wav")
    amb_lufs = _measure_wav_lufs(out_dir / "work_audio" / "ambience_and_sfx_stem.wav")
    report["loudness"] = {
        "integrated_LUFS": float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1)),
        "LRA_LU": float(re.search(r"LRA:\s+(-?[\d.]+) LU", summ).group(1)),
        "true_peak_dBTP": float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1)),
        "narration_stem_LUFS": voice_lufs,
        "ambience_and_sfx_stem_LUFS": amb_lufs,
        "voice_to_ambience_margin_LU": round(voice_lufs - amb_lufs, 2),
    }

    # 3. Shot Plan, Moving-Footage Ratio, Pacing & Narration Alignment Audit
    plan_audit = audit_shot_plan_and_alignment(manifest, wt, style)
    report["shot_plan_and_pacing_qc"] = plan_audit

    real_s = sum((s.end_s - s.start_s) for s in timed_shots if s.is_real_evidence)
    diag_s = sum((s.end_s - s.start_s) for s in timed_shots if not s.is_real_evidence)
    report["visual_evidence_breakdown"] = {
        "total_shots": len(timed_shots),
        "moving_footage_s": plan_audit["moving_footage_s"],
        "moving_footage_pct": plan_audit["moving_footage_pct"],
        "still_photography_s": plan_audit["still_photography_s"],
        "still_photography_pct": plan_audit["still_photography_pct"],
        "human_interaction_shots": plan_audit["human_interaction_shots"],
        "human_interaction_s": plan_audit["human_interaction_s"],
        "human_interaction_pct": plan_audit["human_interaction_pct"],
        "real_imagery_and_footage_s": round(real_s, 3),
        "real_imagery_and_footage_pct": round(100.0 * real_s / dur, 2),
        "illustrative_diagram_s": round(diag_s, 3),
        "illustrative_diagram_pct": round(100.0 * diag_s / dur, 2),
        "meets_real_target": (real_s / dur) >= manifest.editorial_formula.min_real_evidence_ratio,
        "meets_moving_video_target": plan_audit["meets_moving_footage_goal"],
    }

    first_word_s = float(wt["words"][0]["start"]) if wt.get("words") else 0.0
    seg_map = {s["seg_id"]: s for s in wt.get("segments", [])}
    caveat_txt = seg_map.get(manifest.editorial_formula.scientific_caveat_seg_id, {}).get("text", "").lower()
    has_caveat_language = any(
        k in caveat_txt
        for k in (
            "caveat",
            "doesn't prove",
            "does not prove",
            "doesn't mean",
            "does not mean",
            "still studying",
            "under investigation",
            "open mystery",
            "open question",
            "still don't know",
            "not proof",
            "remains",
            "records show no",
            "no evidence",
            "ruled out",
        )
    )
    report["editorial_formula_qc"] = {
        "first_word_start_s": round(first_word_s, 3),
        "hook_within_limit": first_word_s <= manifest.editorial_formula.hook_max_start_s,
        "layer2_pivot_seg_id": manifest.editorial_formula.layer2_pivot_seg_id,
        "scientific_caveat_seg_id": manifest.editorial_formula.scientific_caveat_seg_id,
        "caveat_explicitly_stated": has_caveat_language,
        "all_passed": (
            first_word_s <= manifest.editorial_formula.hook_max_start_s
            and manifest.editorial_formula.layer2_pivot_seg_id in seg_map
            and has_caveat_language
        ),
    }

    # 4. Programmatic Full-Canvas & Overlay-Cleanliness Regression Checks
    report["full_canvas_qc"] = audit_full_canvas_coverage(mp4, timed_shots, style, qc_scr)
    report["overlay_cleanliness_qc"] = audit_overlay_cleanliness(manifest, wt, style)
    report["protected_projects_qc"] = verify_protected_projects_intact()

    # 5. WCAG 2.1 AAA Contrast Audit + Viral Anti-AI Audit
    snow_bg = (240, 245, 250)
    effective_cushion_rgba = (
        (6, 10, 16, 208)
        if style.subtitles.style in ("cinema_boxless", "minimal_editorial", "scientific_plain")
        else tuple(style.subtitles.scrim_rgba)
    )
    eff_cap_bg = blend_rgba_over_rgb(effective_cushion_rgba, snow_bg)
    c_white = compute_wcag_contrast_ratio(tuple(style.subtitles.text_rgba[:3]), eff_cap_bg)
    c_gold = compute_wcag_contrast_ratio(CAPTION_EMPH_RGBA[:3], eff_cap_bg)
    min_req = style.qa.min_wcag_caption_contrast_ratio
    wcag_ok = (c_white >= min_req) and ((not style.subtitles.enable_keyword_color_flash) or (c_gold >= min_req))
    report["wcag_contrast_qc"] = {
        "subtitle_style": style.subtitles.style,
        "emphasis_mode": style.subtitles.emphasis_mode,
        "backdrop_worst_case_rgb": snow_bg,
        "caption_white_contrast_ratio": c_white,
        "caption_gold_contrast_ratio": c_gold,
        "all_wcag_aaa_pass": wcag_ok,
    }

    vsa = plan_audit.get("viral_script_audit", {})
    first_mot_s = float(plan_audit.get("first_real_motion_start_s", 0.0))
    bed_margin_lu = float(report["loudness"]["voice_to_ambience_margin_LU"])
    audible_bed_ok = bed_margin_lu <= style.sound_design.max_audible_bed_margin_lu
    report["viral_anti_ai_qc"] = {
        "anti_ai_script_pass": bool(vsa.get("anti_ai_script_pass", True)),
        "llm_cliche_hits": int(vsa.get("llm_cliche_hits", 0)),
        "jargon_cluster_hits": int(vsa.get("jargon_cluster_hits", 0)),
        "ending_tail_pause_s": float(vsa.get("ending_tail_pause_s", 0.0)),
        "first_real_motion_start_s": first_mot_s,
        "opening_motion_pass": first_mot_s <= style.viral_retention.max_opening_still_duration_s + 0.08,
        "diegetic_nat_sound_active": bool(wt.get("diegetic_nat_sound_active", False)),
        "audible_location_bed_pass": audible_bed_ok,
        "subtitle_style": style.subtitles.style,
        "filmic_color_grade_enabled": style.color_science.enable_filmic_grade,
        "all_viral_anti_ai_pass": (
            bool(vsa.get("anti_ai_script_pass", True))
            and (first_mot_s <= style.viral_retention.max_opening_still_duration_s + 0.08)
            and audible_bed_ok
        ),
    }

    # 6. Opening Frame & Thumbnail QC (including v6 Multi-Concept Package)
    f0_mp4 = np.asarray(_grab_frame(mp4, 0.0, qc_scr / "f0_mp4.png", exact_frame=0), dtype=np.float32)
    thumb_path = out_dir / "thumbnail.jpg"
    thumb_arr = np.asarray(Image.open(thumb_path).convert("RGB"), dtype=np.float32)
    var_files = sorted(out_dir.glob("thumbnail_variant_*.jpg"))
    concept_files = sorted(out_dir.glob("thumbnail_concept_*.jpg"))
    report["thumbnail_qc"] = {
        "thumbnail_jpg_bytes": thumb_path.stat().st_size,
        "under_2mb": thumb_path.stat().st_size < 2 * 1024 * 1024,
        "width": int(thumb_arr.shape[1]),
        "height": int(thumb_arr.shape[0]),
        "dimensions_9x16": int(thumb_arr.shape[1]) == out_w and int(thumb_arr.shape[0]) == out_h,
        "text_mode": style.opening_and_thumbnail.thumbnail_text_mode,
        "frame0_vs_thumbnail_mae_rgb": round(float(np.mean(np.abs(f0_mp4 - thumb_arr))), 3),
        "cover_variants_exported": len(var_files),
        "concepts_exported": len(concept_files),
        "concepts_comparison_sheet_exists": (out_dir / "thumbnail_concepts_comparison_sheet.jpg").exists(),
        "preview_sheet_exists": (out_dir / "thumbnail_small_preview_sheet.jpg").exists(),
    }

    # 7. Motion Smoothness Audit
    report["motion_smoothness_qc"] = audit_motion_smoothness(mp4, timed_shots, qc_scr, fps=fps)

    # 8. Faster-Whisper (`medium.en`, `vad_filter=True`) + Phonetic/Numeral Normalization
    from faster_whisper import WhisperModel  # noqa: E402

    wav16 = qc_scr / "final_16k.wav"
    _run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", str(wav16)])
    model = WhisperModel("medium.en", device="cpu", compute_type="int8", download_root=str(ROOT / "assets" / "models"))
    segs, _ = model.transcribe(
        str(wav16),
        language="en",
        word_timestamps=True,
        beam_size=5,
        condition_on_previous_text=False,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 450},
    )
    hw = [{"w": re.sub(r"[^a-z0-9']", "", w.word.lower()), "raw_w": w.word, "s": w.start, "e": w.end} for seg in segs for w in seg.words]
    hw = [x for x in hw if x["w"]]

    srt_blocks = (out_dir / "subtitles.srt").read_text(encoding="utf-8").strip().split("\n\n")
    cues = []
    max_lines_rendered = 0
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (out_w, out_h)))
    cap_font = get_font(FONT_BOLD, style.subtitles.font_size_px)
    for blk in srt_blocks:
        ls = blk.splitlines()
        t0_s, t1_s = ls[1].split(" --> ")
        parse_ts = lambda ts: int(ts[:2]) * 3600 + int(ts[3:5]) * 60 + int(ts[6:8]) + int(ts[9:]) / 1000.0
        txt = " ".join(ls[2:])
        wrapped = wrap_caption_lines(dummy_draw, txt, cap_font, style.subtitles.max_line_width_px)
        max_lines_rendered = max(max_lines_rendered, len(wrapped))
        cues.append((parse_ts(t0_s), parse_ts(t1_s), txt))

    raw_ref = [re.sub(r"[^a-z0-9']", "", t.lower()) for _, _, txt in cues for t in txt.replace("—", " ").replace("-", " ").split()]
    raw_ref = [r for r in raw_ref if r]
    raw_hyp = [h["w"] for h in hw]
    sm_raw = difflib.SequenceMatcher(None, raw_ref, raw_hyp, autojunk=False)

    norm_ref = canonicalize_tokens_for_asr([t for _, _, txt in cues for t in txt.replace("—", " ").split()])
    norm_hyp = canonicalize_tokens_for_asr([h["raw_w"] for h in hw])
    sm_norm = difflib.SequenceMatcher(None, norm_ref, norm_hyp, autojunk=False)
    norm_diffs = [(op, " ".join(norm_ref[i1:i2]), " ".join(norm_hyp[j1:j2])) for op, i1, i2, j1, j2 in sm_norm.get_opcodes() if op != "equal"]

    mapping = {}
    for op, i1, i2, j1, j2 in sm_raw.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                mapping[i1 + k] = j1 + k
    offs = []
    ri = 0
    for t0, _, txt in cues:
        toks = [t for t in txt.replace("—", " ").replace("-", " ").split() if re.sub(r"[^a-z0-9']", "", t.lower())]
        if ri in mapping:
            offs.append(round(hw[mapping[ri]]["s"] - t0, 3))
        ri += len(toks)

    report["subtitles_qc"] = {
        "cue_count": len(cues),
        "max_burned_lines_per_cue": max_lines_rendered,
        "raw_word_match_ratio": round(sm_raw.ratio(), 4),
        "normalized_word_match_ratio": round(sm_norm.ratio(), 4),
        "normalized_diffs": norm_diffs[:20],
        "cue_start_vs_whisper_offset_s": {
            "median": round(float(np.median(offs)), 3) if offs else 0.0,
            "p95_abs": round(float(np.percentile(np.abs(offs), 95)), 3) if offs else 0.0,
            "max_abs": round(float(np.max(np.abs(offs))), 3) if offs else 0.0,
        },
    }

    # 9. Source & Licensing Register Check
    report["licensing_register_qc"] = {
        "source_register_csv_exists": (out_dir / "source_register.csv").exists(),
        "source_register_md_exists": (out_dir / "source_register.md").exists(),
        "registered_assets_count": len(manifest.assets_register),
    }

    # 9b. v6 Narrative Momentum, Hook Promise & 7-Criterion Visual Relevance Intelligence QC
    momentum_audit = audit_narrative_momentum(manifest, style, wt=wt)
    hook_eval = evaluate_opening_hook_candidates(manifest, style)
    vis_plan_scores = score_episode_visual_plan(manifest)
    report["narrative_and_visual_intelligence_qc"] = {
        "momentum_pass": bool(momentum_audit.get("momentum_pass", True)),
        "momentum_error_count": int(momentum_audit.get("error_count", 0)),
        "momentum_warning_count": int(momentum_audit.get("warning_count", 0)),
        "hook_candidates_count": len(hook_eval.get("candidates", [])),
        "recommended_hook_id": hook_eval.get("recommended_hook_id"),
        "recommended_hook_score": hook_eval.get("recommended_score"),
        "mean_visual_weighted_score": vis_plan_scores.get("mean_weighted_score", 0.0),
        "visual_mismatch_count": int(vis_plan_scores.get("ineligible_shots_count", 0)),
        "all_shots_eligible": bool(vis_plan_scores.get("all_shots_eligible", True)),
    }

    # 9c. v6 Voice Studio & SHA-256 Approval Lock QC
    voice_lock = verify_voice_approval_lock(manifest)
    report["voice_studio_qc"] = {
        "voice_input_mode": manifest.voice_input_mode,
        "voice_direction_profile": manifest.voice_direction_profile or style.sound_design.default_voice_profile,
        "voice_identity": wt.get("voice", manifest.voice),
        "sentence_count": len(wt.get("sentences", manifest.narration_segments)),
        "approval_lock_present": bool(voice_lock.get("locked", False)),
        "approval_lock_synchronized": bool(voice_lock.get("synchronized", False)),
    }

    # 9d. v6 5-Layer Sound Design & Audio Health QC
    audio_rep_p = out_dir / "audio_engineering_report.json"
    audio_rep = json.loads(audio_rep_p.read_text(encoding="utf-8")) if audio_rep_p.exists() else {}
    ad = audio_rep.get("diagnostics", wt.get("audio_diagnostics", {}))
    stems_map = audio_rep.get("stems", {})
    stems_present = sum(1 for p in stems_map.values() if Path(p).exists()) if stems_map else 0
    clipped_samples = int(ad.get("clipped_samples_count", 0))
    exc_silences = int(ad.get("excessive_silence_count", 0))
    lra_val = float(ad.get("loudness_range_lra_lu", 2.5))
    crest_db = float(ad.get("speech_crest_factor_db", ad.get("true_peak_dbtp", -1.5) - ad.get("integrated_lufs", -16.0)))
    lra_ok = lra_val >= float(style.sound_design.min_natural_dynamics_lra_lu) and crest_db >= float(style.sound_design.min_speech_crest_factor_db)
    report["audio_5layer_health_qc"] = {
        "scene_audio_profile": audio_rep.get("scene_audio_profile", style.sound_design.scene_audio_profile),
        "stems_exported_count": stems_present,
        "clipped_samples_count": clipped_samples,
        "excessive_silence_count": exc_silences,
        "loudness_range_lra_lu": lra_val,
        "speech_crest_factor_db": round(crest_db, 2),
        "natural_dynamics_pass": lra_ok,
        "all_audio_health_pass": (clipped_samples == 0 and exc_silences == 0 and lra_ok),
    }

    # 10. Export Visual Review Contact Sheets
    if style.qa.export_visual_contact_sheets:
        # 10a. Full Episode Contact Sheet
        cw, ch, cols = 252, 448, 4
        rows = (len(timed_shots) + cols - 1) // cols
        cs = Image.new("RGB", (cols * (cw + 14) + 14, rows * (ch + 62) + 72), (14, 17, 25))
        d = ImageDraw.Draw(cs)
        d.text(
            (16, 16),
            f"POW DOCUMENTARY STUDIO V6 MASTER CONTACT SHEET — {manifest.slug} ({dur:.2f}s, {len(timed_shots)} shots, {plan_audit['moving_footage_pct']:.1f}% video)",
            font=ft,
            fill=(255, 255, 255),
        )
        for k, s in enumerate(timed_shots):
            tm = 0.35 if k == 0 else 0.5 * (s.start_s + s.end_s)
            im = _grab_frame(mp4, tm, qc_scr / f"cs_{k:02d}.jpg", (cw, ch))
            r, c = divmod(k, cols)
            X, Y = 14 + c * (cw + 14), 62 + r * (ch + 62)
            cs.paste(im, (X, Y))
            mtag = plan_audit["shots"][k]["media_type"].upper()
            d.text((X + 2, Y + ch + 4), f"{s.sid} {s.start_s:.1f}-{s.end_s:.1f}s [{mtag}]", font=fb, fill=(255, 228, 96))
            d.text((X + 2, Y + ch + 28), f"{s.src_file[:26]}", font=fm, fill=(200, 212, 230))
        cs.save(out_dir / "contact_sheet.jpg", quality=92)

        # 10b. Every Scene Boundary Sheet (showing pre | mid | post for dissolves and f-1 | f for cuts)
        tw, th = 160, 284
        cols_t = 3
        n_trans = max(1, len(timed_shots) - 1)
        rows_t = (n_trans + cols_t - 1) // cols_t
        cell_w = 3 * tw + 24
        ts = Image.new("RGB", (cols_t * cell_w + 18, rows_t * (th + 54) + 68), (14, 17, 25))
        d = ImageDraw.Draw(ts)
        d.text(
            (16, 16),
            f"SCENE BOUNDARIES ({len(timed_shots) - 1} transitions): Pre | Boundary/Mid-Dissolve | Post",
            font=ft,
            fill=(255, 255, 255),
        )
        for k, s_next in enumerate(timed_shots[1:]):
            f_nom = int(round(s_next.start_s * fps))
            r, c = divmod(k, cols_t)
            X, Y = 14 + c * cell_w, 62 + r * (th + 54)
            if s_next.transition_in == "dissolve" and s_next.transition_duration_s > 0:
                df = max(2, int(round(s_next.transition_duration_s * fps)))
                f_pre = max(0, f_nom - df // 2 - 2)
                f_mid = f_nom
                f_post = min(int(wt["total_frames_30fps"]) - 1, f_nom + df // 2 + 2)
                lbl = f"#{k+1} DISSOLVE ({s_next.transition_duration_s:.2f}s) @ {s_next.start_s:.2f}s -> {s_next.sid}"
            else:
                f_pre = max(0, f_nom - 2)
                f_mid = max(0, f_nom - 1)
                f_post = min(int(wt["total_frames_30fps"]) - 1, f_nom)
                lbl = f"#{k+1} CLEAN CUT @ {s_next.start_s:.2f}s -> {s_next.sid}"
            ts.paste(_grab_frame(mp4, 0.0, qc_scr / f"tA_{k:02d}.jpg", (tw, th), exact_frame=f_pre), (X, Y))
            ts.paste(_grab_frame(mp4, 0.0, qc_scr / f"tM_{k:02d}.jpg", (tw, th), exact_frame=f_mid), (X + tw + 4, Y))
            ts.paste(_grab_frame(mp4, 0.0, qc_scr / f"tB_{k:02d}.jpg", (tw, th), exact_frame=f_post), (X + 2 * (tw + 4), Y))
            d.text((X + 2, Y + th + 6), lbl, font=fm, fill=(255, 228, 96))
        ts.save(out_dir / "transitions_contact_sheet.jpg", quality=91)

        # 10c. Opening Frames & First Transition Audit
        fw, fh = 230, 408
        s1_end_f = int(round(timed_shots[0].end_s * fps))
        sample_frames = sorted({0, 15, 30, 60, max(0, s1_end_f - 15), max(0, s1_end_f - 1), min(int(wt["total_frames_30fps"]) - 1, s1_end_f + 8), min(int(wt["total_frames_30fps"]) - 1, 105)})
        f3 = Image.new("RGB", (len(sample_frames) * (fw + 10) + 12, fh + 104), (14, 17, 25))
        d = ImageDraw.Draw(f3)
        d.text((16, 14), "SUBJECT-FIRST OPENING AUDIT (f=0 Clean Full-Bleed Canvas -> S01->S02 Boundary)", font=ft, fill=(255, 255, 255))
        for k, fn in enumerate(sample_frames):
            f3.paste(_grab_frame(mp4, 0.0, qc_scr / f"f3_{k}.jpg", (fw, fh), exact_frame=fn), (12 + k * (fw + 10), 56))
            d.text((14 + k * (fw + 10), 62 + fh), f"f={fn} ({fn/fps:.2f}s)", font=fb, fill=(255, 228, 96))
        f3.save(out_dir / "first_3_seconds_audit_sheet.jpg", quality=92)

        # 10d. Ending Audit Sheet
        en = Image.new("RGB", (6 * (fw + 12) + 12, fh + 106), (14, 17, 25))
        d = ImageDraw.Draw(en)
        d.text((16, 14), "FINAL PAYOFF & CLEAN ENDING AUDIT (last 10 seconds)", font=ft, fill=(255, 255, 255))
        for k, tm in enumerate(np.linspace(max(0.0, dur - 10.0), max(0.05, dur - 0.15), 6)):
            en.paste(_grab_frame(mp4, float(tm), qc_scr / f"en_{k}.jpg", (fw, fh)), (12 + k * (fw + 12), 58))
            d.text((16 + k * (fw + 12), 64 + fh), f"t={tm:.2f}s", font=fb, fill=(255, 228, 96))
        en.save(out_dir / "ending_audit_sheet.jpg", quality=92)

        # 10e. Native 1:1 Unscaled Pixel Sharpness Sheet
        sample_indices = sorted({0, min(2, len(timed_shots) - 1), min(len(timed_shots) // 2, len(timed_shots) - 1), len(timed_shots) - 1})
        while len(sample_indices) < min(4, len(timed_shots)):
            for cand in range(len(timed_shots)):
                if cand not in sample_indices:
                    sample_indices.append(cand)
                    break
        crops = []
        for sidx in sample_indices[:4]:
            sh = timed_shots[sidx]
            tm_s = min(dur - 0.2, 0.5 * (sh.start_s + sh.end_s))
            crops.append((f"{sh.sid} ({sh.kind}, t={tm_s:.1f}s)", tm_s, (270, 500, 810, 1040)))

        p11 = Image.new("RGB", (4 * (540 + 16) + 16, 540 + 104), (14, 17, 25))
        d = ImageDraw.Draw(p11)
        d.text((16, 16), "NATIVE 1:1 UNSCALED PIXEL SHARPNESS AUDIT (540x540 crops from 1080x1920 MP4)", font=ft, fill=(255, 255, 255))
        for k, (lbl, tm, box) in enumerate(crops):
            full = _grab_frame(mp4, tm, qc_scr / f"p11_{k}.png")
            X = 16 + k * (540 + 16)
            p11.paste(full.crop(box), (X, 60))
            d.text((X + 4, 608), lbl, font=fb, fill=(255, 228, 96))
        p11.save(out_dir / "native_1to1_pixel_qc_sheet.jpg", quality=94)

    # Compute aggregated v6 QA summary & reclaim temporary scratch directory
    failed_gates: list[str] = []
    if not (report["ffprobe"]["within_target_window"] and report["ffprobe"]["dimensions_exact"] and report["ffprobe"]["exact_frame_match"]):
        failed_gates.append("1_resolution_cfr_duration")
    if len(report["black_segments"]) > 0:
        failed_gates.append("2_zero_black_frames")
    if not report["overlay_cleanliness_qc"]["clean_documentary_pass"]:
        failed_gates.append("4_overlay_cleanliness")
    if not (report["thumbnail_qc"]["under_2mb"] and report["thumbnail_qc"]["dimensions_9x16"]):
        failed_gates.append("8_thumbnail_spec")
    if not report["protected_projects_qc"]["all_intact"]:
        failed_gates.append("10_protected_projects_safety")
    if not report["narrative_and_visual_intelligence_qc"]["momentum_pass"]:
        failed_gates.append("12_narrative_momentum")
    if not report["narrative_and_visual_intelligence_qc"]["all_shots_eligible"]:
        failed_gates.append("13_visual_relevance_eligibility")
    if not report["audio_5layer_health_qc"]["all_audio_health_pass"]:
        failed_gates.append("14_audio_5layer_health")

    report["failed_gates"] = failed_gates
    report["failed_gates_count"] = len(failed_gates)
    report["overall_studio_v6_pass"] = len(failed_gates) == 0

    shutil.rmtree(out_dir / ".scratch_build", ignore_errors=True)
    (out_dir / "qc_measurements.json").write_text(json.dumps(report, indent=2))
    return report
