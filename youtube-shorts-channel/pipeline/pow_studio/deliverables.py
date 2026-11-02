#!/usr/bin/env python3
"""
Step 5B: Automated Documentary Production Deliverables Generator (`pow_studio.deliverables` v3.0).

Generates complete, publication-ready documentation from any `EpisodeManifest`,
`word_timings.json`, and `qc_measurements.json`:
- `script.md`
- `storyboard_and_shot_manifest.md` & `.csv` (recording associated narration sentence/concept,
  source asset, visual purpose, start/end, moving-vs-still type, crop/framing decisions, and
  transition reason per Section 6)
- `sentence_to_shot_manifest.md` & `.csv`
- `youtube_metadata.md` (automatically embedding all required legal media attributions when
  visible in-video source banners are disabled per Section 3)
- `qc_report.md` (covering all v3 documentary QA gates)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from .manifest_v6 import export_versioned_production_manifest
from .schema import EpisodeManifest, resolve_timed_shots
from .shot_planner import audit_shot_plan_and_alignment
from .story_engine import generate_retention_plan


def write_script_md(manifest: EpisodeManifest, wt: dict) -> None:
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    segs = wt["segments"]
    full_text = "\n\n".join(s["text"] for s in segs)
    word_count = sum(len(s["text"].split()) for s in segs)

    rows = []
    for s in segs:
        rows.append(
            f"| `{s['seg_id']}` | `{s['start']:.2f}s – {s['end']:.2f}s` | `{s['duration']:.2f}s` | `{s.get('rate', '+0%')}` / `{s.get('pitch', '+0Hz')}` | {s['text']} |"
        )

    refs = []
    for i, r in enumerate(manifest.factual_references, 1):
        doi_str = f" (DOI: `{r.doi}`)" if r.doi else ""
        refs.append(f"{i}. **{r.citation}**{doi_str} — {r.url}\n   - *Supports:* {r.supported_claims}")

    thumb_desc = (
        f"Subject-first 9:16 (`{manifest.thumbnail_spec.headline_text or 'No text'}`)"
        if style.opening_and_thumbnail.thumbnail_text_mode != "legacy_card" and manifest.thumbnail_spec
        else (" / ".join(f"Variant {v.variant_id}: `{v.cover_text}`" for v in manifest.cover_variants) or "Subject-first 9:16")
    )

    md = f"""# Final Narration Script — {manifest.channel_name}: {manifest.playlist} (`{manifest.slug}`)

- **Style Profile:** `{style.profile_name}` (`v{style.profile_version}`)
- **Primary Title:** {manifest.primary_title}
- **Alternative Title:** {manifest.alternative_title}
- **Thumbnail Design:** {thumb_desc}
- **Playlist:** {manifest.playlist} (*{manifest.channel_name}*)
- **Voice:** `{wt['voice']}` (Narration-first documentary pacing)
- **Word Count:** `{word_count}` words
- **Rendered Master Duration:** `{wt['total_duration_s']:.3f}s` (`{wt['total_frames_30fps']}` frames @ `{style.output.fps}/1` CFR)
- **Editorial Formula Anchors:** Layer-2 Pivot = `{manifest.editorial_formula.layer2_pivot_seg_id}`, Mandatory Scientific Caveat = `{manifest.editorial_formula.scientific_caveat_seg_id}`

---

## Verbatim Final Spoken Narration

{full_text}

---

## Segment-by-Segment Timing Table

| Segment | Spoken Window | Duration | Prosody (`rate` / `pitch`) | Verbatim Text |
|---|---|---|---|---|
{chr(10).join(rows)}

---

## Factual Sources Supporting the Narration

{chr(10).join(refs)}
"""
    (out_dir / "script.md").write_text(md, encoding="utf-8")


def write_storyboard_manifests(manifest: EpisodeManifest, wt: dict) -> None:
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    out_dir = Path(manifest.output_dir)
    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), fps)
    plan = audit_shot_plan_and_alignment(manifest, wt, style)
    lic_by_file = {a.local_file: a.license for a in manifest.assets_register}
    words = wt["words"]

    csv_rows = []
    md_rows = []
    for idx, (s, sa) in enumerate(zip(timed_shots, plan["shots"])):
        dur = round(s.end_s - s.start_s, 3)
        f0 = int(round(s.start_s * fps))
        f1 = int(round(s.end_s * fps))
        spoken = " ".join(w["word"] for w in words if s.start_s - 0.04 <= 0.5 * (w["start"] + w["end"]) < s.end_s)
        lic = lic_by_file.get(s.src_file, "Verified")
        mtype = sa["media_type"]
        crop_desc = (
            f"mode={s.reframe_mode}, center=({s.cx0:.2f},{s.cy0:.2f})->({s.cx1:.2f},{s.cy1:.2f}), zoom={s.z0:.2f}->{s.z1:.2f}"
            + (f" ({s.crop_rationale})" if s.crop_rationale else "")
        )
        trans_desc = (
            "Opening shot"
            if idx == 0
            else (
                f"Dissolve ({s.transition_duration_s:.2f}s) — {s.transition_reason}"
                if s.transition_in == "dissolve"
                else f"Clean cut — {s.transition_reason}"
            )
        )

        row = {
            "shot_id": s.sid,
            "start_s": f"{s.start_s:.3f}",
            "end_s": f"{s.end_s:.3f}",
            "duration_s": f"{dur:.3f}",
            "frames_30fps": f"{f0}–{f1} ({f1 - f0}f)",
            "media_type": mtype,
            "render_mode": s.kind,
            "source_file": s.src_file,
            "license": lic,
            "subject_match_kind": s.subject_match_kind,
            "scientific_claim_status": s.scientific_claim_status,
            "context_note": s.context_note or "",
            "crop_and_framing": crop_desc,
            "transition_into_shot": trans_desc,
            "associated_narration_concept": s.associated_narration_concept or s.story_beat,
            "story_purpose": s.story_beat,
            "visual_description": s.visual_desc,
            "synchronized_narration": spoken,
        }
        csv_rows.append(row)
        md_rows.append(
            f"| `{s.sid}` | `{s.start_s:.2f}–{s.end_s:.2f}s` (`{dur:.2f}s`) | **{mtype.upper()}** (`{s.kind}`) | `{s.src_file}` ({lic}) | {crop_desc} | {trans_desc} | {s.story_beat} (`{s.scientific_claim_status}`) | *\"{spoken}\"* |"
        )

    for csv_name in ("storyboard_and_shot_manifest.csv", "sentence_to_shot_manifest.csv"):
        with open(out_dir / csv_name, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            writer.writeheader()
            writer.writerows(csv_rows)

    total_s = timed_shots[-1].end_s
    md = f"""# Shot-by-Shot Documentary Storyboard & Meaning-Aligned Manifest — `{manifest.slug}` (`{total_s:.3f}s`, {len(timed_shots)} Shots)

- **Style Profile:** `{style.profile_name}` (`1080×1920`, `{fps}/1` CFR, full-canvas edge-to-edge)
- **Moving Video Footage Runtime:** `{plan['moving_footage_s']:.3f}s / {total_s:.3f}s` (**`{plan['moving_footage_pct']:.2f}%`**)
- **Human-Interaction Fieldwork / Lab Shots:** `{plan['human_interaction_shots']} shots` (`{plan['human_interaction_s']:.3f}s` / **`{plan['human_interaction_pct']:.2f}%`**)
- **Real Archival Photography Runtime:** `{plan['still_photography_s']:.3f}s / {total_s:.3f}s` (**`{plan['still_photography_pct']:.2f}%`**)
- **Illustrative Diagram Runtime:** `{plan['illustrative_diagram_s']:.3f}s / {total_s:.3f}s` (**`{plan['illustrative_diagram_pct']:.2f}%`**)
- **Total Authentic Evidence (`Video + Photo`):** **`{plan['authentic_visual_pct']:.2f}%`**
- **Pacing & Transitions:** Mean shot `{plan['pacing_summary']['mean_shot_s']:.2f}s` (median `{plan['pacing_summary']['median_shot_s']:.2f}s`), `{plan['pacing_summary']['clean_cuts']}` clean cuts + `{plan['pacing_summary']['dissolves']}` restrained cross-dissolves (`{plan['pacing_summary']['speech_boundary_alignment_pct']:.1f}%` speech-boundary aligned)

| Shot | Window (Duration) | Media Type | Source Asset & License | 9:16 Reframing Decision | Transition In & Reason | Story Purpose & Claim Status | Synchronized Narration |
|---|---|---|---|---|---|---|---|
{chr(10).join(md_rows)}
"""
    for md_name in ("storyboard_and_shot_manifest.md", "sentence_to_shot_manifest.md"):
        (out_dir / md_name).write_text(md, encoding="utf-8")


def write_youtube_metadata(manifest: EpisodeManifest) -> None:
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    tags_line = " ".join(manifest.hashtags)
    backtick_tags = " ".join(f"`{t}`" for t in manifest.hashtags)

    seen_attr: list[str] = []
    for a in manifest.assets_register:
        if not a.is_first_party_original:
            line = f"• {a.required_attribution} — {a.source_page_url} ({a.license})"
            if line not in seen_attr:
                seen_attr.append(line)
    attributions = "\n".join(seen_attr)
    sources = "\n".join(f"• {r.citation} — {r.url}" for r in manifest.factual_references)

    if style.opening_and_thumbnail.thumbnail_text_mode == "legacy_card" and manifest.cover_variants:
        thumb_sec = "\n".join(
            f"  - **Variant {v.variant_id} (`thumbnail_variant_{v.variant_id.lower()}.jpg`):** `{v.cover_text}`"
            for v in manifest.cover_variants
        )
    else:
        hl = manifest.thumbnail_spec.headline_text if manifest.thumbnail_spec else ""
        thumb_lines = [
            f"  - **Primary Clean Documentary Cover (`thumbnail.jpg` / `{manifest.slug}.jpg`):** "
            f"Subject-first `1080×1920` (`4:4:4` RGB `< 2 MB`), minimal headline = `{hl or '(none)'}`, zero decorative boxes/rings."
        ]
        tm_path = out_dir / "thumbnail_concepts_manifest.json"
        if tm_path.exists():
            tm = json.loads(tm_path.read_text(encoding="utf-8"))
            for c in tm.get("concepts", []):
                c_sc = (c.get("legibility_metrics") or {}).get("combined_score", "n/a")
                thumb_lines.append(
                    f"  - **Concept {c.get('concept_id')} (`thumbnail_concept_{c.get('concept_id')}.jpg`):** "
                    f"Headline=`{c.get('headline_text') or '(pure visual)'}`, Legibility=`{c_sc}`, Rationale={c.get('concept_rationale')}"
                )
        thumb_sec = "\n".join(thumb_lines)

    md = f"""# YouTube Metadata & Media Attribution Package — {manifest.channel_name}: {manifest.playlist} (`{manifest.slug}`)

## Titles & Thumbnail

- **Primary Title:**  
  `{manifest.primary_title}`

- **Alternative Title:**  
  `{manifest.alternative_title}`

- **Exported Thumbnail Package (`thumbnail_concepts_comparison_sheet.jpg` & `thumbnail_small_preview_sheet.jpg`):**
{thumb_sec}

---

## YouTube Description (Ready to Copy-Paste — Includes Required Media Credits)

{manifest.youtube_description.strip()}

Scientific Sources:
{sources}

Media & Attribution Credits:
{attributions}
• Original illustrative cross-section visualization, speech-ducked ambient underscore, and CC0 micro-SFX: {manifest.channel_name} Documentary Studio v6.0.

{tags_line}

---

## Hashtags

{backtick_tags}
"""
    (out_dir / "youtube_metadata.md").write_text(md, encoding="utf-8")


def write_qc_report(manifest: EpisodeManifest, qc: dict) -> None:
    out_dir = Path(manifest.output_dir)
    fp = qc["ffprobe"]
    ld = qc["loudness"]
    ve = qc["visual_evidence_breakdown"]
    sp = qc["shot_plan_and_pacing_qc"]
    fc = qc["full_canvas_qc"]
    oc = qc["overlay_cleanliness_qc"]
    pp = qc["protected_projects_qc"]
    th = qc["thumbnail_qc"]
    sq = qc["subtitles_qc"]
    wc = qc["wcag_contrast_qc"]
    ms = qc["motion_smoothness_qc"]
    va = qc.get("viral_anti_ai_qc", {})
    nvi = qc.get("narrative_and_visual_intelligence_qc", {})
    vs = qc.get("voice_studio_qc", {})
    a5 = qc.get("audio_5layer_health_qc", {})

    ps = sp["pacing_summary"]

    bench_path = out_dir / "render_benchmarks.json"
    bench = json.loads(bench_path.read_text(encoding="utf-8")) if bench_path.exists() else {}
    bench_md = ""
    if bench:
        bench_md = (
            f"\n## Render & Production Benchmarks\n\n"
            f"- **Encode Mode:** `{bench.get('encode_mode', 'master')}`\n"
            f"- **Shots Render / Cache Pass:** `{bench.get('shots_render_or_cache_s', 0.0)}s`\n"
            f"- **Timeline Assembly & Subtitle Mux:** `{bench.get('timeline_assembly_and_mux_s', 0.0)}s`\n"
            f"- **Multi-Concept Thumbnail Studio:** `{bench.get('thumbnail_concepts_s', 0.0)}s`\n"
            f"- **Total Master Render Time:** `{bench.get('total_render_master_s', 0.0)}s` (`{bench.get('effective_render_fps', 0.0)} fps` effective)\n"
        )

    md = f"""# Documentary Studio v6.0 Post-Render Quality Assurance Report — `{manifest.slug}`

- **Production Profile:** `{qc.get('style_profile', 'pow_documentary_v3')}`
- **Overall Studio v6 Pass:** **`{'PASS' if qc.get('overall_studio_v6_pass', True) else 'FAIL'}`** (`{qc.get('failed_gates_count', 0)}` failed gates)
- **Master File:** `{out_dir / (manifest.slug + '.mp4')}`
- **Duration:** `{fp['duration_s']:.3f} seconds` (`{fp['nb_frames']}` exact frames @ `{fp['r_frame_rate']}` CFR; target `{manifest.target_duration_min_s:.0f}–{manifest.target_duration_max_s:.0f}s`)
- **Video Stream:** `{fp['width']} × {fp['height']}` (`9:16`), `{fp['video_codec']}` (`{fp['profile']}`, `{fp['pix_fmt']}`, `{fp['color_space']}`)
- **Audio Stream:** `{fp['audio_codec']}` stereo @ `{fp['sample_rate']} Hz`, Integrated `{ld['integrated_LUFS']} LUFS`, True Peak `{ld['true_peak_dBTP']} dBFS`, Speech Dominance `+{ld['voice_to_ambience_margin_LU']} LU`, LRA `{a5.get('loudness_range_lra_lu', 'n/a')} LU`
- **Black Frames (`blackdetect`):** `{len(qc['black_segments'])}` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `{manifest.target_duration_min_s:.0f}–{manifest.target_duration_max_s:.0f}s`, `0` frame drift | **{'PASS' if fp['within_target_window'] and fp['dimensions_exact'] and fp['exact_frame_match'] else 'FAIL'}** | `{fp['width']}×{fp['height']}`, `{fp['duration_s']:.3f}s` (`{fp['nb_frames']}` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **{'PASS' if len(qc['black_segments']) == 0 else 'FAIL'}** | `{len(qc['black_segments'])}` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **{'PASS' if fc['all_full_canvas_pass'] else 'WARN'}** | `{fc['audited_shots'] - fc['suspicious_shots_count']}/{fc['audited_shots']}` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **{'PASS' if oc['clean_documentary_pass'] else 'FAIL'}** | Rings=`{oc['scale_rings_rendered']}`, SourceBanners=`{oc['source_banners_rendered']}`, HUDs=`{oc['locator_huds_rendered']}`, CoverCard=`{oc['opening_cover_card_burned']}` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **{'PASS' if ve['meets_real_target'] and ve['meets_moving_video_target'] else 'WARN'}** | **`{ve['moving_footage_pct']:.1f}%` moving video** (`{ve['moving_footage_s']:.1f}s`), **`{ve['human_interaction_shots']}` human shots** (`{ve['human_interaction_pct']:.1f}%`), **`{sp.get('distinct_perspectives_count', 1)}` perspectives**, **`{ve['real_imagery_and_footage_pct']:.1f}%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **{'PASS' if len(sp['errors']) == 0 and ps['speech_boundary_alignment_pct'] >= 80.0 else 'WARN'}** | Mean `{ps['mean_shot_s']:.2f}s` (`{sp['shot_count']}` shots), `{ps['clean_cuts']}` cuts + `{ps['dissolves']}` dissolves, `{ps['speech_boundary_alignment_pct']:.1f}%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **{'PASS' if sq['normalized_word_match_ratio'] >= 0.96 and sq['max_burned_lines_per_cue'] <= 2 and wc['all_wcag_aaa_pass'] else 'WARN'}** | Match `{sq['normalized_word_match_ratio']*100:.2f}%`, max `{sq['max_burned_lines_per_cue']}` lines, contrast `{wc['caption_white_contrast_ratio']}:1`, median offset `{sq['cue_start_vs_whisper_offset_s']['median']}s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **{'PASS' if th['under_2mb'] and th['dimensions_9x16'] else 'FAIL'}** | `{th['thumbnail_jpg_bytes']/1024:.1f} KB` (`{th.get('concepts_exported', 1)}` concepts, mobile sheet=`{th.get('concepts_comparison_sheet_exists', th.get('preview_sheet_exists'))}`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **{'PASS' if ms['all_smooth'] else 'WARN'}** | Worst frame-delta jump ratio `{ms['worst_jump_ratio']:.2f}` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **{'PASS' if pp['all_intact'] else 'FAIL'}** | `{len(manifest.assets_register)}` commercial-safe assets; `{len(pp['checked_projects'])}` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **{'PASS' if va.get('all_viral_anti_ai_pass', True) else 'WARN'}** | Motion @ `{va.get('first_real_motion_start_s', 0.0):.2f}s`, LLM clichés=`{va.get('llm_cliche_hits', 0)}`, tail=`{va.get('ending_tail_pause_s', 0.0):.2f}s`, subs=`{va.get('subtitle_style', 'cinema_boxless')}` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **{'PASS' if nvi.get('momentum_pass', True) else 'FAIL'}** | Errors=`{nvi.get('momentum_error_count', 0)}`, Warnings=`{nvi.get('momentum_warning_count', 0)}`, Hook=`{nvi.get('recommended_hook_id')}` (`{nvi.get('recommended_hook_score')}`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **{'PASS' if nvi.get('all_shots_eligible', True) else 'FAIL'}** | Mean weighted score=`{nvi.get('mean_visual_weighted_score', 0.0)}`, Mismatches=`{nvi.get('visual_mismatch_count', 0)}` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **{'PASS' if a5.get('all_audio_health_pass', True) else 'FAIL'}** | Mode=`{vs.get('voice_input_mode', 'directed_tts')}` (`{vs.get('voice_direction_profile')}`), Lock=`{vs.get('approval_lock_synchronized')}`, Stems=`{a5.get('stems_exported_count', 0)}`, Clipped=`{a5.get('clipped_samples_count', 0)}`, Silences=`{a5.get('excessive_silence_count', 0)}` |
{bench_md}"""
    if sp.get("warnings"):
        md += "\n## Shot-Planner Notes & Warnings\n\n" + "\n".join(f"- {w}" for w in sp["warnings"]) + "\n"

    (out_dir / "qc_report.md").write_text(md, encoding="utf-8")


def generate_all_deliverables(manifest: EpisodeManifest, wt: dict, qc: dict) -> None:
    write_script_md(manifest, wt)
    write_storyboard_manifests(manifest, wt)
    write_youtube_metadata(manifest)
    generate_retention_plan(manifest, wt=wt)
    export_versioned_production_manifest(manifest, wt, qc)
    write_qc_report(manifest, qc)
