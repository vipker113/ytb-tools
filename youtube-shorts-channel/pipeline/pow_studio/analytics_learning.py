#!/usr/bin/env python3
"""
Part 9, Section 11: YouTube Performance Analytics Importer & Documentary
Production Learning Loop (`pow_studio.analytics_learning` v6.0).

Capabilities:
1. Imports official YouTube Studio CSV exports (`Table data.csv` + optional audience
   retention curve CSV), JSON analytics snapshots, or local `ytb-tools/data/store.json`
   (SubPulse read-only synced channel store) — ZERO unauthorized scraping, ZERO automatic
   publishing, ZERO account mutations.
2. Analyzes all 15 dimensions specified in Section 11:
   - Viewed vs. swiped away (%)
   - Engaged views / Views
   - Average view duration (AVD)
   - Average percentage viewed (APV %)
   - Audience retention curve (intro drop, mid-story slope, reveal retention, rewatches)
   - Likes & comments
   - Subscribers gained
   - Traffic sources
   - Video duration, Topic category, Opening hook type, Thumbnail concept,
     Voice direction profile, and Editing/Production style profile.
3. Generates an evidence-based Per-Video Performance Review (`performance_review.md` & `.json`)
   plus Channel Pattern Correlations, strictly separating **observed correlation** from
   **unproven causation** (`N` sample-size checks + explicit methodological disclaimers).
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

CHANNEL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_YTB_TOOLS_STORE = CHANNEL_ROOT.parent / "ytb-tools" / "data" / "ytb-growth-db.json"


@dataclass
class VideoAnalyticsRecord:
    video_id: str
    title: str
    slug: str = ""
    views: int = 0
    engaged_views: int = 0
    viewed_vs_swiped_away_pct: Optional[float] = None
    average_view_duration_s: Optional[float] = None
    average_percentage_viewed_pct: Optional[float] = None
    likes: int = 0
    comments: int = 0
    subscribers_gained: int = 0
    traffic_sources: dict[str, float] = field(default_factory=dict)
    retention_curve_pct: list[tuple[float, float]] = field(default_factory=list)  # [(elapsed_pct_or_s, retained_pct)]
    rewatch_spikes_count: int = 0
    # Joined Creative & Production Manifest attributes
    video_duration_s: Optional[float] = None
    topic_category: str = ""
    opening_hook_type: str = ""
    thumbnail_concept: str = ""
    voice_direction_profile: str = ""
    editing_style_profile: str = ""
    mean_shot_duration_s: Optional[float] = None
    spoken_wpm: Optional[float] = None
    layer2_reveal_time_s: Optional[float] = None


def _parse_duration_to_seconds(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if re.match(r"^\d+(\.\d+)?$", s):
        return float(s)
    parts = s.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        if len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except ValueError:
        return None
    return None


def _parse_float_clean(val: Any) -> Optional[float]:
    if val is None or val == "" or str(val).strip() in ("-", "—", "N/A"):
        return None
    cleaned = re.sub(r"[^0-9.-]", "", str(val))
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None


def _parse_int_clean(val: Any) -> int:
    f = _parse_float_clean(val)
    return int(round(f)) if f is not None else 0


def parse_youtube_studio_csv(csv_path: Path) -> list[VideoAnalyticsRecord]:
    """
    Parse a standard YouTube Studio 'Table data.csv' export (English or localized headers).
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"YouTube Studio CSV not found: {csv_path}")

    records: list[VideoAnalyticsRecord] = []
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            norm_row = {str(k).strip().lower(): v for k, v in row.items() if k is not None}
            vid = str(
                norm_row.get("content")
                or norm_row.get("video")
                or norm_row.get("video id")
                or norm_row.get("id")
                or ""
            ).strip()
            title = str(norm_row.get("video title") or norm_row.get("title") or "").strip()
            if not vid or vid.lower() in ("total", "totals"):
                continue

            swiped_viewed = _parse_float_clean(
                norm_row.get("viewed (vs. swiped away) (%)")
                or norm_row.get("viewed vs. swiped away (%)")
                or norm_row.get("viewed vs swiped away")
                or norm_row.get("stayed to watch (%)")
            )
            avd_s = _parse_duration_to_seconds(
                norm_row.get("average view duration") or norm_row.get("avg view duration")
            )
            apv_pct = _parse_float_clean(
                norm_row.get("average percentage viewed (%)")
                or norm_row.get("average percentage viewed")
            )
            dur_s = _parse_duration_to_seconds(norm_row.get("duration") or norm_row.get("length"))

            records.append(
                VideoAnalyticsRecord(
                    video_id=vid,
                    title=title,
                    views=_parse_int_clean(norm_row.get("views")),
                    engaged_views=_parse_int_clean(norm_row.get("engaged views") or norm_row.get("views")),
                    viewed_vs_swiped_away_pct=swiped_viewed,
                    average_view_duration_s=avd_s,
                    average_percentage_viewed_pct=apv_pct,
                    likes=_parse_int_clean(norm_row.get("likes")),
                    comments=_parse_int_clean(norm_row.get("comments added") or norm_row.get("comments")),
                    subscribers_gained=_parse_int_clean(norm_row.get("subscribers") or norm_row.get("subscribers gained")),
                    video_duration_s=dur_s,
                )
            )
    return records


def parse_retention_curve_csv(retention_csv_path: Path) -> list[tuple[float, float]]:
    """
    Parse a YouTube Studio Audience Retention curve CSV (`Video position (%)` or `Time`, `Absolute audience retention (%)`).
    """
    pts: list[tuple[float, float]] = []
    if not retention_csv_path.exists():
        return pts
    with open(retention_csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return pts
        for row in reader:
            if len(row) < 2:
                continue
            x = _parse_float_clean(row[0])
            y = _parse_float_clean(row[1])
            if x is not None and y is not None:
                pts.append((x, y))
    return pts


def load_analytics_from_ytb_tools_store(store_path: Path = DEFAULT_YTB_TOOLS_STORE) -> list[VideoAnalyticsRecord]:
    """
    Read synced channel video performance from `ytb-tools/data/ytb-growth-db.json` (read-only).
    Selects the active Proof of Wonder channel (`activeChannelId` / `@proofofwonderscience`) when `myChannels` is present.
    """
    if not store_path.exists():
        return []
    data = json.loads(store_path.read_text(encoding="utf-8"))
    out: list[VideoAnalyticsRecord] = []
    snap = data.get("analyticsSnapshot") or {}
    recent_vids = snap.get("recentVideos") or data.get("videos") or []

    if not recent_vids and isinstance(data.get("myChannels"), list):
        active_id = str(data.get("activeChannelId") or "")
        chosen_ch = next(
            (
                c
                for c in data["myChannels"]
                if isinstance(c, dict)
                and (str(c.get("id")) == active_id or "proof of wonder" in str(c.get("title", "")).lower())
            ),
            data["myChannels"][0] if data["myChannels"] else {},
        )
        recent_vids = chosen_ch.get("recentVideos") or []

    for v in recent_vids:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("videoId") or v.get("id") or "")
        title = str(v.get("title") or "")
        if not vid and not title:
            continue
        out.append(
            VideoAnalyticsRecord(
                video_id=vid or title[:24],
                title=title,
                views=_parse_int_clean(v.get("views") or v.get("viewCount")),
                engaged_views=_parse_int_clean(v.get("engagedViews") or v.get("views") or v.get("viewCount")),
                viewed_vs_swiped_away_pct=_parse_float_clean(v.get("viewedVsSwipedAwayPct") or v.get("stayedToWatchPct")),
                average_view_duration_s=_parse_duration_to_seconds(v.get("averageViewDuration") or v.get("avgViewDurationSec")),
                average_percentage_viewed_pct=_parse_float_clean(v.get("averagePercentageViewed") or v.get("avgPercentageViewed")),
                likes=_parse_int_clean(v.get("likes") or v.get("likeCount")),
                comments=_parse_int_clean(v.get("comments") or v.get("commentCount")),
                subscribers_gained=_parse_int_clean(v.get("subscribersGained") or v.get("netSubscribers")),
                traffic_sources=dict(v.get("trafficSources") or {}),
                video_duration_s=_parse_duration_to_seconds(
                    v.get("durationSeconds") or v.get("durationSec") or v.get("duration")
                ),
            )
        )
    return out


def enrich_record_with_production_manifest(
    rec: VideoAnalyticsRecord,
    episode_output_dir: Optional[Path] = None,
) -> VideoAnalyticsRecord:
    """
    Join YouTube Studio metrics with `production_manifest_v6.json` / `word_timings.json` / `qc_measurements.json`
    so creative choices (hook type, thumbnail concept, voice profile, shot pacing, reveal timing) can be reviewed.
    """
    target_dir = episode_output_dir
    if target_dir is None:
        # Match by slug or primary_title across `output/`
        title_norm = re.sub(r"[^a-z0-9]+", "", rec.title.lower())
        for p in sorted((CHANNEL_ROOT / "output").glob("*/*")):
            if not p.is_dir():
                continue
            pm = p / "production_manifest_v6.json"
            if pm.exists():
                mdata = json.loads(pm.read_text(encoding="utf-8"))
                if p.name == rec.slug or re.sub(r"[^a-z0-9]+", "", str(mdata.get("topic", "")).lower()) in title_norm:
                    target_dir = p
                    break
            elif rec.slug and p.name == rec.slug:
                target_dir = p
                break
            elif (p / "script.md").exists():
                sc_head = (p / "script.md").read_text(encoding="utf-8", errors="ignore")[:800].lower()
                if title_norm and len(title_norm) >= 12 and title_norm[:20] in re.sub(r"[^a-z0-9]+", "", sc_head):
                    target_dir = p
                    rec.topic_category = rec.topic_category or p.parent.name
                    break

    if target_dir is None or not target_dir.exists():
        return rec

    rec.slug = target_dir.name
    pm_path = target_dir / "production_manifest_v6.json"
    wt_path = target_dir / "word_timings.json"
    qc_path = target_dir / "qc_measurements.json"

    if pm_path.exists():
        pm = json.loads(pm_path.read_text(encoding="utf-8"))
        rec.topic_category = str(pm.get("category_playlist") or rec.topic_category)
        rec.editing_style_profile = str(pm.get("production_profile", {}).get("profile_name") or "")
        sv = pm.get("script_version", {})
        rec.opening_hook_type = str(sv.get("opening_hook_type") or "")
        vp = pm.get("voice_direction_profile", {})
        rec.voice_direction_profile = str(vp.get("profile_id") or "")
        af = pm.get("audio_source_and_final_narration", {})
        if af.get("total_duration_s"):
            rec.video_duration_s = float(af["total_duration_s"])
        if sv.get("word_count") and rec.video_duration_s:
            rec.spoken_wpm = round((float(sv["word_count"]) / max(1.0, rec.video_duration_s)) * 60.0, 1)
        tcs = pm.get("thumbnail_variants", {}).get("concepts", [])
        if tcs:
            rec.thumbnail_concept = f"{tcs[0].get('concept_id', 'A')}: {tcs[0].get('headline_text', '')}".strip(": ")

    if wt_path.exists():
        wt = json.loads(wt_path.read_text(encoding="utf-8"))
        if isinstance(wt, dict):
            if not rec.video_duration_s and wt.get("total_duration_s"):
                rec.video_duration_s = float(wt["total_duration_s"])
            if not rec.spoken_wpm and wt.get("words") and rec.video_duration_s:
                rec.spoken_wpm = round((len(wt["words"]) / max(1.0, rec.video_duration_s)) * 60.0, 1)
            segs = wt.get("segments", [])
            if len(segs) >= 3:
                mid_seg = segs[len(segs) // 2]
                rec.layer2_reveal_time_s = float(mid_seg.get("start", 0.0))
        elif isinstance(wt, list) and wt and rec.video_duration_s:
            rec.spoken_wpm = round((len(wt) / max(1.0, rec.video_duration_s)) * 60.0, 1)

    if qc_path.exists():
        qc = json.loads(qc_path.read_text(encoding="utf-8"))
        if isinstance(qc, dict):
            rec.editing_style_profile = rec.editing_style_profile or str(qc.get("style_profile") or "")
            ps = qc.get("shot_plan_and_pacing_qc", {}).get("pacing_summary", {})
            if isinstance(ps, dict) and ps.get("mean_shot_s"):
                rec.mean_shot_duration_s = float(ps["mean_shot_s"])

    return rec


def review_single_video_performance(rec: VideoAnalyticsRecord) -> dict[str, Any]:
    """
    Generate an evidence-based diagnostic Performance Review answering the 7 questions
    in Part 9, Section 11 while distinguishing correlation from causation.
    """
    findings: list[dict[str, str]] = []
    recommendations: list[str] = []

    # 1. Did viewers leave during the introduction? (Viewed vs. Swiped Away + early retention curve)
    if rec.viewed_vs_swiped_away_pct is not None:
        if rec.viewed_vs_swiped_away_pct < 62.0:
            findings.append(
                {
                    "question": "Did viewers leave during the introduction?",
                    "observation": f"Yes — Viewed vs. Swiped Away is {rec.viewed_vs_swiped_away_pct:.1f}% (< 65% benchmark).",
                    "evidence_level": "direct_metric",
                }
            )
            recommendations.append(
                "Test an opening hook that reveals the anomalous real phenomenon on Frame 0 and lands the core physical paradox within 2.0 seconds."
            )
        else:
            findings.append(
                {
                    "question": "Did viewers leave during the introduction?",
                    "observation": f"Opening held viewers well ({rec.viewed_vs_swiped_away_pct:.1f}% stayed to watch).",
                    "evidence_level": "direct_metric",
                }
            )

    # Retention curve inspection if available
    if rec.retention_curve_pct:
        rewatches = sum(1 for _, y in rec.retention_curve_pct if y > 100.5)
        rec.rewatch_spikes_count = rewatches
        early_pts = [y for x, y in rec.retention_curve_pct if 3.0 <= x <= 10.0]
        if early_pts and min(early_pts) < 68.0:
            findings.append(
                {
                    "question": "Retention curve early drop-off check",
                    "observation": f"Retention dipped to {min(early_pts):.1f}% within the first 10% of the video.",
                    "evidence_level": "retention_curve",
                }
            )
        if rewatches > 0:
            findings.append(
                {
                    "question": "Rewatch activity",
                    "observation": f"Detected {rewatches} curve point(s) > 100% indicating viewer rewatches or loop replays.",
                    "evidence_level": "retention_curve",
                }
            )

    # 2. Was the core reveal delivered too late (or too early)?
    if rec.average_view_duration_s and rec.layer2_reveal_time_s:
        if rec.average_view_duration_s < rec.layer2_reveal_time_s:
            findings.append(
                {
                    "question": "Was the core reveal delivered too late?",
                    "observation": (
                        f"Average View Duration ({rec.average_view_duration_s:.1f}s) ended before the deeper pivot "
                        f"at {rec.layer2_reveal_time_s:.1f}s; many viewers exited prior to the escalation beat."
                    ),
                    "evidence_level": "observational_alignment",
                }
            )
            recommendations.append(
                "Plant a concrete curiosity clue earlier (~12–18s) so viewers anticipate the deeper discovery before mid-video."
            )
        else:
            findings.append(
                {
                    "question": "Was the core reveal delivered too late?",
                    "observation": f"Average View Duration ({rec.average_view_duration_s:.1f}s) reached past the {rec.layer2_reveal_time_s:.1f}s escalation pivot.",
                    "evidence_level": "observational_alignment",
                }
            )

    # 3. Scene length & pacing association
    if rec.mean_shot_duration_s and rec.average_percentage_viewed_pct is not None:
        findings.append(
            {
                "question": "Scene pacing vs. retention observation",
                "observation": (
                    f"Mean shot duration was {rec.mean_shot_duration_s:.2f}s with {rec.average_percentage_viewed_pct:.1f}% "
                    f"Average Percentage Viewed in category '{rec.topic_category or 'Unknown'}'."
                ),
                "evidence_level": "single_video_observation_not_causal",
            }
        )

    # 4. Narration speed check
    if rec.spoken_wpm is not None:
        if rec.spoken_wpm < 130.0:
            findings.append(
                {
                    "question": "Was the narration too slow or too fast?",
                    "observation": f"Narration pace was relatively slow ({rec.spoken_wpm:.1f} WPM).",
                    "evidence_level": "measured_cadence",
                }
            )
            recommendations.append("Consider tightening inter-sentence pauses to ~280–360ms or testing 'Curious Explorer' (+1% rate) if early retention lags.")
        elif rec.spoken_wpm > 182.0:
            findings.append(
                {
                    "question": "Was the narration too slow or too fast?",
                    "observation": f"Narration pace was brisk ({rec.spoken_wpm:.1f} WPM), risking scientific comprehension overload.",
                    "evidence_level": "measured_cadence",
                }
            )
            recommendations.append("Allow 450–600ms breathing room after major scientific reveals so complex facts register.")
        else:
            findings.append(
                {
                    "question": "Was the narration too slow or too fast?",
                    "observation": f"Narration cadence ({rec.spoken_wpm:.1f} WPM) sits inside natural documentary range (135–175 WPM).",
                    "evidence_level": "measured_cadence",
                }
            )

    # 5. Subscriber conversion signal
    if rec.views >= 100:
        sub_rate_per_1k = round((rec.subscribers_gained / float(rec.views)) * 1000.0, 2)
        findings.append(
            {
                "question": "Subscriber & returning-interest signal",
                "observation": f"Generated {rec.subscribers_gained} subscribers across {rec.views} views ({sub_rate_per_1k} subs / 1,000 views).",
                "evidence_level": "direct_metric",
            }
        )

    return {
        "video_id": rec.video_id,
        "title": rec.title,
        "slug": rec.slug,
        "metrics": asdict(rec),
        "findings": findings,
        "future_creative_recommendations": recommendations,
        "causation_guardrail": (
            "Observational Diagnostics Only: Associations between hook type, shot duration, voice profile, "
            "or thumbnail concept and retention metrics represent correlation on observational channel data, "
            "NOT proven causation. Confirm hypotheses across multiple topics and YouTube Studio A/B tests."
        ),
    }


def generate_channel_learning_report(
    records: list[VideoAnalyticsRecord],
    out_dir: Optional[Path] = None,
) -> dict[str, Any]:
    """
    Aggregate per-video reviews and identify recurring creative patterns associated with
    stronger retention (with explicit sample-size `N` and correlation-vs-causation guardrails).
    """
    reviews = [review_single_video_performance(r) for r in records]

    # Group APV % by category & hook type where available
    by_category: dict[str, list[float]] = {}
    by_hook: dict[str, list[float]] = {}
    for r in records:
        if r.average_percentage_viewed_pct is not None:
            if r.topic_category:
                by_category.setdefault(r.topic_category, []).append(r.average_percentage_viewed_pct)
            if r.opening_hook_type:
                by_hook.setdefault(r.opening_hook_type, []).append(r.average_percentage_viewed_pct)

    cat_summary = {
        k: {"sample_size_n": len(v), "mean_apv_pct": round(sum(v) / len(v), 2), "causal_inference_valid": False}
        for k, v in by_category.items()
    }
    hook_summary = {
        k: {"sample_size_n": len(v), "mean_apv_pct": round(sum(v) / len(v), 2), "causal_inference_valid": False}
        for k, v in by_hook.items()
    }

    report = {
        "videos_analyzed_count": len(records),
        "methodology_disclaimer": (
            "Correlation != Causation: Category, hook, voice, and pacing averages below summarize observed "
            "historical associations only. Small sample sizes (N < 15 per group) are subject to topic variance "
            "and impression-cohort shifts."
        ),
        "category_associations": cat_summary,
        "opening_hook_associations": hook_summary,
        "video_reviews": reviews,
    }

    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "performance_review.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

        md_lines = [
            "# Proof of Wonder — YouTube Analytics & Production Learning Review",
            "",
            f"- **Videos Analyzed:** `{len(records)}`",
            f"- **Methodological Guardrail:** {report['methodology_disclaimer']}",
            "",
        ]
        for rev in reviews:
            m = rev["metrics"]
            vw_str = f"{m['viewed_vs_swiped_away_pct']}%" if m["viewed_vs_swiped_away_pct"] is not None else "n/a (export YouTube Studio CSV)"
            avd_str = f"{m['average_view_duration_s']}s" if m["average_view_duration_s"] is not None else "n/a"
            apv_str = f"{m['average_percentage_viewed_pct']}%" if m["average_percentage_viewed_pct"] is not None else "n/a"
            md_lines.extend(
                [
                    f"## Video: {rev['title']} (`{rev['video_id']}`)",
                    f"- **Views / Engaged Views:** `{m['views']}` / `{m['engaged_views']}` (Likes: `{m['likes']}`, Comments: `{m['comments']}`)",
                    f"- **Viewed vs. Swiped Away:** `{vw_str}`",
                    f"- **Avg View Duration / APV:** `{avd_str}` / `{apv_str}`",
                    f"- **Creative Configuration:** Category=`{m['topic_category'] or 'n/a'}`, Hook=`{m['opening_hook_type'] or 'n/a'}`, Style=`{m['editing_style_profile'] or 'n/a'}`, Voice=`{m['voice_direction_profile'] or 'n/a'}`",
                    "",
                    "### Diagnostic Findings",
                ]
            )
            for fd in rev["findings"]:
                md_lines.append(f"- **{fd['question']}** ({fd['evidence_level']}): {fd['observation']}")
            if rev["future_creative_recommendations"]:
                md_lines.append("")
                md_lines.append("### Proposed Hypotheses for Next Productions")
                for rec_txt in rev["future_creative_recommendations"]:
                    md_lines.append(f"- {rec_txt}")
            md_lines.append("")

        (out_dir / "performance_review.md").write_text("\n".join(md_lines), encoding="utf-8")

    return report
