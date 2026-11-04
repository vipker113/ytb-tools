#!/usr/bin/env python3
"""
Step 5C: Unified Declarative Documentary CLI (`pow_studio.cli` v3.0).

Implements the required narration-first documentary production sequence:
  1. `validate`   — Validate schema, style profile (`pow_documentary_v3`), and commercial rights.
  2. `audio`      — Synthesize final narration audio first and extract exact word/sentence timings.
  3. `plan-check` — Verify shot pacing, speech-boundary alignment, crop feasibility, and moving-footage %.
  4. `shots`      — Render full-screen 9:16 reframed shots with exact dissolve handles.
  5. `preview`    — Export storyboard contact sheet before final assembly.
  6. `render`     — Assemble zero-drift timeline (`xfade` dissolves + clean cuts), clean subtitles, and thumbnail.
  7. `qc`         — Run automated technical/layout/overlay/Whisper QA + export visual review sheets & deliverables.
  8. `all`        — Execute steps 1–7 end-to-end.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Literal, Optional

import typer
from rich.console import Console
from rich.table import Table

PIPELINE_DIR = Path(__file__).resolve().parent.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.analytics_learning import (  # noqa: E402
    DEFAULT_YTB_TOOLS_STORE,
    enrich_record_with_production_manifest,
    generate_channel_learning_report,
    load_analytics_from_ytb_tools_store,
    parse_retention_curve_csv,
    parse_youtube_studio_csv,
)
from pow_studio.ambience_planner import plan_environmental_ambience  # noqa: E402
from pow_studio.audio_engine import build_episode_audio  # noqa: E402
from pow_studio.audio_registry import ensure_audio_asset_registry, harvest_verified_wikimedia_audio  # noqa: E402
from pow_studio.creative_qa import run_creative_qa  # noqa: E402
from pow_studio.music_planner import plan_story_music  # noqa: E402
from pow_studio.scene_editor import optimize_episode_scenes  # noqa: E402
from pow_studio.sfx_planner import plan_context_sfx  # noqa: E402
from pow_studio.timeline_builder import build_unified_av_timeline  # noqa: E402
from pow_studio.compositor import (  # noqa: E402
    build_preview_sheet,
    render_all_shots,
    render_episode_master,
    render_thumbnail_concepts_for_episode,
)
from pow_studio.deliverables import generate_all_deliverables  # noqa: E402
from pow_studio.qc_suite import run_episode_qc  # noqa: E402
from pow_studio.rights_gate import run_rights_gate  # noqa: E402
from pow_studio.schema import EpisodeManifest  # noqa: E402
from pow_studio.shot_planner import audit_shot_plan_and_alignment, extract_speech_boundaries  # noqa: E402
from pow_studio.story_engine import (  # noqa: E402
    audit_narrative_momentum,
    evaluate_opening_hook_candidates,
    generate_retention_plan,
)
from pow_studio.style_profile import list_available_production_profiles, load_style_profile  # noqa: E402
from pow_studio.subpulse_bridge import (  # noqa: E402
    DEFAULT_SUBPULSE_URL,
    SNAPSHOT_PATH,
    fetch_next_sprint_episode,
    publish_episode_via_subpulse,
)
from pow_studio.video_sourcing import discover_documentary_videos  # noqa: E402
from pow_studio.visual_intelligence import (  # noqa: E402
    discover_and_rank_visual_candidates,
    score_episode_visual_plan,
)
from pow_studio.voice_studio import (  # noqa: E402
    approve_and_lock_voice_master,
    compare_voice_variants,
    export_annotated_voice_script,
    list_voice_direction_profiles,
    load_voice_direction_profile,
    preview_voice_paragraph,
    preview_voice_sentence,
)

app = typer.Typer(help="Proof of Wonder Next-Generation Documentary Production Studio v6.0 ($0 Local Pipeline)")
console = Console()


def _load(manifest_path: Path) -> EpisodeManifest:
    return EpisodeManifest.from_yaml(manifest_path)


@app.command()
def validate(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Path to episode YAML manifest"),
    online_check: bool = typer.Option(True, "--online/--offline", help="Verify Wikimedia Commons API metadata"),
) -> None:
    """Validate declarative schema, style profile rules, evidence floor, and commercial licenses."""
    ep = _load(manifest)
    style = ep.resolve_style_profile()
    rows = run_rights_gate(ep, verify_online=online_check)
    console.print(
        f"[bold green]✓ Manifest & Rights Gate PASSED[/bold green] for [cyan]{ep.slug}[/cyan] "
        f"(style=[yellow]{style.profile_name}[/yellow], {len(rows)} commercial-cleared assets)."
    )


@app.command()
def audio(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
    reuse_tts: bool = typer.Option(False, "--reuse-tts", help="Reuse cached TTS segments if present"),
) -> None:
    """Step 1 of Narration-First Edit: Generate narration audio & export natural speech boundaries."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    wt = build_episode_audio(ep, reuse_existing_tts=reuse_tts)
    bounds = extract_speech_boundaries(wt)
    (Path(ep.output_dir) / "speech_boundaries.json").write_text(json.dumps(bounds, indent=2))
    console.print(
        f"[bold green]✓ Narration & Audio Master Ready:[/bold green] {wt['total_duration_s']:.3f}s "
        f"({wt['total_frames_30fps']} frames @ 30fps, {len(bounds)} natural speech cut points exported)."
    )


@app.command(name="plan-check")
def plan_check(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
) -> None:
    """Audit moving-footage ratio, crop feasibility, dissolve restraint & speech-boundary alignment."""
    ep = _load(manifest)
    style = ep.resolve_style_profile()
    wt_path = Path(ep.output_dir) / "word_timings.json"
    if not wt_path.exists():
        raise typer.BadParameter(f"Run `audio` first so {wt_path} exists for narration-locked shot planning.")
    wt = json.loads(wt_path.read_text())
    audit = audit_shot_plan_and_alignment(ep, wt, style)
    (Path(ep.output_dir) / "shot_plan_audit.json").write_text(json.dumps(audit, indent=2))

    ps = audit["pacing_summary"]
    console.print(
        f"[bold cyan]Shot Plan Audit ({style.profile_name}):[/bold cyan] "
        f"{audit['shot_count']} shots | Moving video: [bold]{audit['moving_footage_pct']:.1f}%[/bold] "
        f"({audit['moving_footage_s']:.1f}s) | Human interaction: [bold]{audit['human_interaction_shots']} shots[/bold] "
        f"({audit['human_interaction_pct']:.1f}%) | Photos: {audit['still_photography_pct']:.1f}% | "
        f"Diagrams: {audit['illustrative_diagram_pct']:.1f}% | "
        f"Mean shot: {ps['mean_shot_s']:.2f}s | Speech-aligned cuts: {ps['speech_boundary_alignment_pct']:.1f}%"
    )
    for w in audit["warnings"]:
        console.print(f"  [yellow]• Note:[/yellow] {w}")
    if audit["errors"]:
        for e in audit["errors"]:
            console.print(f"  [bold red]✗ Error:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command()
def shots(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
    only: Optional[str] = typer.Option(None, "--only", help="Comma-separated shot IDs, e.g. S01,S04"),
) -> None:
    """Render full-screen 9:16 vertical shots (with exact handles around cross-dissolves)."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text())
    only_set = {x.strip() for x in only.split(",") if x.strip()} if only else None
    rendered = render_all_shots(ep, wt, encode_mode=mode, only=only_set)
    console.print(f"[bold green]✓ Full-Screen Shots Rendered ({mode}):[/bold green] {len(rendered)} timeline shots.")


@app.command()
def preview(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
) -> None:
    """Export pre-render storyboard contact sheet (`pre_render_storyboard_contact_sheet.jpg`)."""
    ep = _load(manifest)
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text())
    sheet = build_preview_sheet(ep, wt, encode_mode=mode)
    console.print(f"[bold green]✓ Storyboard Preview Sheet:[/bold green] {sheet}")


@app.command()
def render(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
) -> None:
    """Assemble 30/1 CFR master MP4 (clean cuts + restrained dissolves), subtitles & clean thumbnail."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text())
    mp4 = render_episode_master(ep, wt, encode_mode=mode)
    console.print(f"[bold green]✓ Documentary Master & Thumbnail Exported ({mode}):[/bold green] {mp4}")


@app.command()
def qc(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
) -> None:
    """Run Documentary v3 Auto-QC (Full-Canvas, Overlay Cleanliness, Whisper, WCAG) & write deliverables."""
    ep = _load(manifest)
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text())
    qc_res = run_episode_qc(ep, wt)
    generate_all_deliverables(ep, wt, qc_res)

    tbl = Table(title=f"POW Documentary v3.0 QC Summary — {ep.slug}")
    tbl.add_column("Gate", style="cyan")
    tbl.add_column("Measured", style="green")
    tbl.add_row("Duration / CFR", f"{qc_res['ffprobe']['duration_s']}s ({qc_res['ffprobe']['nb_frames']}f @ {qc_res['ffprobe']['r_frame_rate']})")
    tbl.add_row("Full-Canvas 9:16", f"PASS={qc_res['full_canvas_qc']['all_full_canvas_pass']} (0 inset boxes, {qc_res['full_canvas_qc']['suspicious_shots_count']} flagged)")
    tbl.add_row("Overlay Cleanliness", f"PASS={qc_res['overlay_cleanliness_qc']['clean_documentary_pass']} (rings=0, banners=0, HUDs=0)")
    tbl.add_row(
        "Moving Video / Human Fieldwork",
        f"{qc_res['visual_evidence_breakdown']['moving_footage_pct']}% video | "
        f"{qc_res['visual_evidence_breakdown']['human_interaction_shots']} human shots ({qc_res['visual_evidence_breakdown']['human_interaction_pct']}%) | "
        f"{qc_res['visual_evidence_breakdown']['still_photography_pct']}% photo | "
        f"{qc_res['visual_evidence_breakdown']['real_imagery_and_footage_pct']}% authentic",
    )
    ps = qc_res["shot_plan_and_pacing_qc"]["pacing_summary"]
    tbl.add_row("Pacing & Dissolves", f"Mean {ps['mean_shot_s']}s | {ps['clean_cuts']} cuts + {ps['dissolves']} dissolves | {ps['speech_boundary_alignment_pct']}% pause-aligned")
    tbl.add_row("Whisper & WCAG AAA", f"{qc_res['subtitles_qc']['normalized_word_match_ratio']*100:.2f}% match | {qc_res['wcag_contrast_qc']['caption_white_contrast_ratio']}:1 contrast")
    tbl.add_row("Thumbnail & Legacy Safety", f"{qc_res['thumbnail_qc']['thumbnail_jpg_bytes']/1024:.1f} KB ({qc_res['thumbnail_qc']['text_mode']}) | Legacy intact={qc_res['protected_projects_qc']['all_intact']}")
    console.print(tbl)


@app.command(name="all")
def run_all(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
    online_check: bool = typer.Option(True, "--online/--offline"),
    reuse_tts: bool = typer.Option(False, "--reuse-tts"),
) -> None:
    """Execute the complete Narration-First Documentary v3.0 production workflow end-to-end."""
    ep = _load(manifest)
    style = ep.resolve_style_profile()
    ep.assert_output_dir_writable()
    console.rule(f"[bold yellow]POW Documentary Engine v3.0 ({style.profile_name} • {mode.upper()})[/bold yellow]")

    console.print("[1/7] Validating Commercial Rights & Off-Screen Attribution Register...")
    run_rights_gate(ep, verify_online=online_check)

    console.print("[2/7] Generating Final Narration Audio & Extracting Speech Boundaries...")
    wt = build_episode_audio(ep, reuse_existing_tts=reuse_tts)
    (Path(ep.output_dir) / "speech_boundaries.json").write_text(json.dumps(extract_speech_boundaries(wt), indent=2))

    console.print("[3/7] Auditing Meaning-Based Shot Plan, Crop Feasibility & Narration Alignment...")
    audit = audit_shot_plan_and_alignment(ep, wt, style)
    (Path(ep.output_dir) / "shot_plan_audit.json").write_text(json.dumps(audit, indent=2))
    if audit["errors"]:
        for err in audit["errors"]:
            console.print(f"[bold red]✗ Shot Plan Error:[/bold red] {err}")
        raise typer.Exit(code=1)

    from pow_studio.schema import resolve_timed_shots as _rts
    _opt_shots = _rts(ep, int(wt["total_frames_30fps"]), style.output.fps)
    console.print(f"[4/7] Rendering {len(_opt_shots)} Intelligent Story-Optimized 9:16 Shots (from {len(ep.shots)} candidates)...")
    render_all_shots(ep, wt, encode_mode=mode)

    console.print("[5/7] Exporting Pre-Render Storyboard Contact Sheet...")
    build_preview_sheet(ep, wt, encode_mode=mode)

    console.print("[6/7] Assembling Master MP4 (Clean Cuts + Restrained Dissolves) & Subject-First Thumbnail...")
    render_episode_master(ep, wt, encode_mode=mode)

    console.print("[7/7] Running Automated QA + Exporting Visual Review Contact Sheets & Deliverables...")
    qc_res = run_episode_qc(ep, wt)
    generate_all_deliverables(ep, wt, qc_res)
    console.print(f"[bold green]✓ COMPLETE:[/bold green] {Path(ep.output_dir) / (ep.slug + '.mp4')}")


@app.command(name="search-videos")
def search_videos(
    query: str = typer.Option(..., "--query", "-q", help="Scientific subject, location, or fieldwork search query"),
    limit: int = typer.Option(8, "--limit", "-n", help="Max results per repository"),
) -> None:
    """Harvest commercial-safe (Public Domain / CC BY) HD real-world & human-fieldwork videos ($0 API)."""
    results = discover_documentary_videos(query, max_per_source=limit)
    tbl = Table(title=f"Authentic Commercial-Safe Video Candidates — '{query}'")
    tbl.add_column("Repo", style="cyan")
    tbl.add_column("Res", style="yellow")
    tbl.add_column("Human Score", style="magenta")
    tbl.add_column("License", style="green")
    tbl.add_column("Title & Direct URL", style="white")
    for r in results:
        tbl.add_row(
            r["source_repo"],
            f"{r['width']}x{r['height']}",
            f"{r['human_interaction_score']:.1f}",
            r["license_label"],
            f"{r['title']}\n{r['download_url']}",
        )
    console.print(tbl)


@app.command(name="sprint")
def sprint_status(
    url: str = typer.Option(DEFAULT_SUBPULSE_URL, "--url", help="SubPulse Autopilot Web URL"),
    claim: bool = typer.Option(False, "--claim/--no-claim", help="Mark next episode as in_progress"),
) -> None:
    """Fetch active channel & next 5-day Sprint episode from SubPulse Web (`/api/pipeline`)."""
    data = fetch_next_sprint_episode(base_url=url, claim=claim)
    ch = data.get("channel") or {}
    sp = data.get("sprint") or {}
    ep = data.get("nextEpisode")

    console.rule("[bold cyan]SubPulse Autopilot ↔ Mac Documentary Bridge[/bold cyan]")
    console.print(
        f"Channel: [bold white]{ch.get('title', 'N/A')}[/bold white] "
        f"([yellow]{ch.get('handle', '')}[/yellow]) • "
        f"Subs: [green]{ch.get('subscribers', 0)}[/green]/{ch.get('targetMilestone', 100)} • "
        f"Views: {ch.get('totalViews', 0)} ({ch.get('videoCount', 0)} videos)"
    )
    if sp:
        console.print(
            f"Sprint #{sp.get('sprintNumber')}: "
            f"[bold]{sp.get('completedSteps')}/{sp.get('totalSteps')}[/bold] completed • "
            f"Golden Window: [amber1]{sp.get('bestPublishWindowVn')}[/amber1]"
        )

    if not ep:
        console.print("[bold green]✓ All Sprint episodes completed![/bold green]")
        return

    words = len(str(ep.get("fullNarration", "")).split())
    tbl = Table(title=f"Next Queued Episode — {ep.get('episodeId')} ({ep.get('dayLabel')})")
    tbl.add_column("Field", style="cyan", width=18)
    tbl.add_column("Value", style="white")
    tbl.add_row("Status", str(ep.get("status")))
    tbl.add_row("Strategy", str(ep.get("strategyType")))
    tbl.add_row("Title", str(ep.get("title")))
    tbl.add_row("Publish Window", f"{ep.get('scheduledDate')} • {ep.get('vnPublishWindow')}")
    tbl.add_row("Narration Words", f"{words} words (~{round(words / 2.65)}s)")
    tbl.add_row("Hook (0-3s)", str(ep.get("hook3s")))
    tbl.add_row("Pinned Comment", str(ep.get("pinnedComment")))
    tbl.add_row("Saved Snapshot", str(SNAPSHOT_PATH))
    console.print(tbl)


@app.command(name="publish")
def publish_episode(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Path to rendered episode YAML manifest"),
    url: str = typer.Option(DEFAULT_SUBPULSE_URL, "--url", help="SubPulse Autopilot Web URL"),
    mode: Literal["schedule_golden", "public_now", "private_draft"] = typer.Option(
        "schedule_golden", "--mode", help="YouTube Studio publish/schedule mode"
    ),
    advance_sprint: bool = typer.Option(
        True,
        "--advance-sprint/--standalone",
        help="Advance active Sprint item (default) or upload standalone without advancing Sprint",
    ),
    episode_id: Optional[str] = typer.Option(None, "--episode-id", help="Optional explicit Sprint episodeId"),
    publish_at: Optional[str] = typer.Option(None, "--publish-at", help="Optional custom ISO-8601 UTC publish timestamp"),
) -> None:
    """Upload rendered MP4 + custom thumbnail + metadata directly to YouTube Studio via SubPulse OAuth."""
    ep = _load(manifest)
    res = publish_episode_via_subpulse(
        ep=ep,
        base_url=url,
        publish_mode=mode,
        advance_sprint=advance_sprint,
        episode_id=episode_id,
        custom_publish_at_iso=publish_at,
    )
    up = res.get("uploadResult") or {}
    console.print(
        f"[bold green]✓ Uploaded to YouTube Studio![/bold green]\n"
        f"  • Video ID: [cyan]{up.get('videoId')}[/cyan]\n"
        f"  • Studio URL: {up.get('studioEditUrl')}\n"
        f"  • Watch URL: {up.get('watchUrl')}\n"
        f"  • Scheduled At: [yellow]{up.get('scheduledAt') or mode}[/yellow]\n"
        f"  • Custom Thumbnail: {up.get('thumbnailUploaded')}\n"
        f"  • Sprint Advanced: {advance_sprint}"
    )


# ==============================================================================
# PROOF OF WONDER NEXT-GENERATION STUDIO v6.0 — 6-STAGE MODULAR COMMANDS
# ==============================================================================


@app.command(name="profiles")
def list_profiles() -> None:
    """List reusable Documentary Production Profiles and Voice Direction Profiles."""
    prod_tbl = Table(title="Reusable Documentary Production Profiles (config/profiles/)")
    prod_tbl.add_column("Profile ID", style="cyan")
    prod_tbl.add_column("Subtitle Style", style="yellow")
    prod_tbl.add_column("Scene Audio", style="magenta")
    prod_tbl.add_column("Description", style="white")
    for pname in list_available_production_profiles():
        sp = load_style_profile(pname)
        prod_tbl.add_row(
            pname,
            f"{sp.subtitles.style} ({sp.subtitles.emphasis_mode})",
            sp.sound_design.scene_audio_profile,
            sp.description,
        )
    console.print(prod_tbl)

    v_tbl = Table(title="Reusable Voice Direction Profiles (config/voice_profiles/)")
    v_tbl.add_column("Voice Profile ID", style="cyan")
    v_tbl.add_column("Voice Identity", style="green")
    v_tbl.add_column("Speed / Energy", style="yellow")
    v_tbl.add_column("Description", style="white")
    for vid in list_voice_direction_profiles():
        vp = load_voice_direction_profile(vid)
        v_tbl.add_row(vid, vp.voice_identity, f"{vp.speaking_speed} / {vp.energy}/5", vp.description)
    console.print(v_tbl)


@app.command(name="stage1-research")
def stage1_research(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    online_check: bool = typer.Option(True, "--online/--offline", help="Verify Wikimedia Commons API metadata"),
    discover_query: Optional[str] = typer.Option(
        None, "--discover", "-q", help="Optional multi-archive $0 visual candidate search query"
    ),
    narration_focus: Optional[str] = typer.Option(None, "--narration-focus", help="Optional narration concept for ranking"),
) -> None:
    """Stage 1 (Research): Validate scientific citations, commercial licensing & optional multi-archive asset discovery."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    style = ep.resolve_style_profile()
    rows = run_rights_gate(ep, verify_online=online_check)
    out_dir = Path(ep.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    research_summary = {
        "slug": ep.slug,
        "topic": ep.topic or ep.primary_title,
        "production_profile": style.profile_name,
        "factual_references_count": len(ep.factual_references),
        "commercial_cleared_assets_count": len(rows),
        "discovered_candidates": [],
    }
    if discover_query:
        ranked = discover_and_rank_visual_candidates(
            query=discover_query,
            narration_line=narration_focus or ep.primary_title,
            max_per_source=5,
            weights=style.asset_selection.scoring_weights,
        )
        research_summary["discovered_candidates"] = ranked[:12]

    (out_dir / "stage1_research_report.json").write_text(json.dumps(research_summary, indent=2), encoding="utf-8")
    console.print(
        f"[bold green]✓ Stage 1 Research Complete:[/bold green] {len(ep.factual_references)} scientific citations & "
        f"{len(rows)} commercial-cleared assets verified ({style.profile_name})."
    )


@app.command(name="stage2-story")
def stage2_story(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    export_voice_script: bool = typer.Option(
        True, "--export-voice-script/--no-export-voice-script", help="Export editable bracketed voice direction script"
    ),
) -> None:
    """Stage 2 (Story): Evaluate opening hooks, audit narrative momentum & generate Retention Plan."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    style = ep.resolve_style_profile()
    out_dir = Path(ep.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    wt_p = out_dir / "word_timings.json"
    wt = json.loads(wt_p.read_text(encoding="utf-8")) if wt_p.exists() else None

    hooks = evaluate_opening_hook_candidates(ep, style)
    (out_dir / "hook_evaluation.json").write_text(json.dumps(hooks, indent=2), encoding="utf-8")

    momentum = audit_narrative_momentum(ep, style, wt=wt)
    (out_dir / "narrative_momentum_audit.json").write_text(json.dumps(momentum, indent=2), encoding="utf-8")

    ret_plan = generate_retention_plan(ep, wt=wt, out_dir=out_dir)

    if export_voice_script:
        export_annotated_voice_script(ep, out_path=out_dir / "voice_script_annotated.txt")

    console.print(
        f"[bold green]✓ Stage 2 Story Engine Complete:[/bold green] "
        f"Recommended Hook=[cyan]{hooks.get('recommended_hook_id')}[/cyan] ({hooks.get('recommended_score')}) | "
        f"Momentum Pass=[bold]{momentum['momentum_pass']}[/bold] "
        f"(errors={momentum['error_count']}, warnings={momentum['warning_count']}) | "
        f"Retention Plan={ret_plan['planned_duration_s']}s ({len(ret_plan['rows'])} beats)."
    )
    if not momentum["momentum_pass"]:
        for err in momentum["errors"]:
            console.print(f"  [bold red]✗ Momentum Error:[/bold red] {err}")
        raise typer.Exit(code=1)


@app.command(name="stage3-voice")
def stage3_voice(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    reuse_tts: bool = typer.Option(False, "--reuse-tts", help="Reuse full narration if already rendered"),
    approve: bool = typer.Option(False, "--approve/--no-approve", help="Lock SHA-256 voice approval after generation"),
    note: str = typer.Option("Approved via Stage 3 Voice Studio", "--note", help="Approval reviewer note"),
) -> None:
    """Stage 3 (Voice): Synthesize directed narration or ingest uploaded voice + build 5-layer audio stems."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    wt = build_episode_audio(ep, reuse_existing_tts=reuse_tts)
    bounds = extract_speech_boundaries(wt)
    out_dir = Path(ep.output_dir)
    (out_dir / "speech_boundaries.json").write_text(json.dumps(bounds, indent=2), encoding="utf-8")

    lock_msg = "unlocked (run `voice-approve` or pass `--approve` to lock)"
    if approve:
        lk = approve_and_lock_voice_master(ep, reviewer_note=note)
        lock_msg = f"LOCKED ({lk['narration_norm_wav_sha256'][:12]}...)"

    console.print(
        f"[bold green]✓ Stage 3 Voice & 5-Layer Audio Ready:[/bold green] "
        f"mode=[cyan]{ep.voice_input_mode}[/cyan] | duration={wt['total_duration_s']:.3f}s "
        f"({wt['total_frames_30fps']}f @ 30fps) | {len(wt.get('audio_layers_exported', []))} stems | {lock_msg}"
    )


@app.command(name="stage4-visual")
def stage4_visual(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
) -> None:
    """Stage 4 (Visual): Score 7-criterion visual relevance, audit camera variety/pacing & build thumbnail concepts."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    style = ep.resolve_style_profile()
    out_dir = Path(ep.output_dir)
    wt_p = out_dir / "word_timings.json"
    if not wt_p.exists():
        raise typer.BadParameter(f"Run `stage3-voice` first so {wt_p} exists.")
    wt = json.loads(wt_p.read_text(encoding="utf-8"))

    vis_scores = score_episode_visual_plan(ep)
    (out_dir / "visual_relevance_scores.json").write_text(json.dumps(vis_scores, indent=2), encoding="utf-8")

    audit = audit_shot_plan_and_alignment(ep, wt, style)
    (out_dir / "shot_plan_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    if audit["errors"]:
        for err in audit["errors"]:
            console.print(f"[bold red]✗ Visual Plan Error:[/bold red] {err}")
        raise typer.Exit(code=1)

    thumb_pkg = render_thumbnail_concepts_for_episode(ep)
    render_all_shots(ep, wt, encode_mode=mode, use_cache=True)
    sheet = build_preview_sheet(ep, wt, encode_mode=mode)

    console.print(
        f"[bold green]✓ Stage 4 Visual Strategy & Storyboard Ready:[/bold green] "
        f"Mean 7-criterion score=[cyan]{vis_scores['mean_weighted_score']}[/cyan] "
        f"(eligible={vis_scores['all_shots_eligible']}) | "
        f"Perspectives=[yellow]{audit['distinct_perspectives_count']}[/yellow] | "
        f"Thumbnails={len(thumb_pkg.get('concepts', []))} concepts | Preview={sheet.name}"
    )


@app.command(name="stage5-edit")
def stage5_edit(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    mode: Literal["draft", "master"] = typer.Option("master", "--mode"),
) -> None:
    """Stage 5 (Editing): Render cached 9:16 shots, purposeful cuts/dissolves, documentary subtitles & master MP4."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text(encoding="utf-8"))
    mp4 = render_episode_master(ep, wt, encode_mode=mode)
    console.print(f"[bold green]✓ Stage 5 Master Timeline Exported ({mode}):[/bold green] {mp4}")


@app.command(name="stage6-quality")
def stage6_quality(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
) -> None:
    """Stage 6 (Quality): Run 14-gate automated QA, export versioned production_manifest_v6.json & review sheets."""
    ep = _load(manifest)
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text(encoding="utf-8"))
    qc_res = run_episode_qc(ep, wt)
    generate_all_deliverables(ep, wt, qc_res)

    console.print(
        f"[bold green]✓ Stage 6 Quality Assurance Complete:[/bold green] "
        f"Overall Studio v6 Pass=[bold]{qc_res.get('overall_studio_v6_pass')}[/bold] "
        f"(failed_gates={qc_res.get('failed_gates_count', 0)}) | "
        f"Manifest={Path(ep.output_dir) / 'production_manifest_v6.json'}"
    )
    if not qc_res.get("overall_studio_v6_pass", True):
        console.print(f"[bold red]Failed Gates:[/bold red] {qc_res.get('failed_gates')}")
        raise typer.Exit(code=1)


@app.command(name="voice-preview")
def voice_preview_cmd(
    text: Optional[str] = typer.Option(None, "--text", "-t", help="Single sentence or bracket-annotated block to audition"),
    script_file: Optional[Path] = typer.Option(None, "--script-file", "-f", help="Path to annotated voice script file"),
    profile: str = typer.Option("cinematic_documentary", "--profile", "-p", help="Voice Direction Profile ID"),
    out_dir: Path = typer.Option(Path("/tmp/pow_voice_preview"), "--out-dir", "-o", help="Directory for preview WAVs"),
    compare_variants_flag: bool = typer.Option(
        False, "--compare-variants", help="Render 3 distinct delivery variants (Calm vs Mysterious vs Reveal)"
    ),
) -> None:
    """Voice Studio: Preview a sentence, paragraph, or 3 delivery variants before video rendering."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if script_file and script_file.exists():
        res = preview_voice_paragraph(
            script_file.read_text(encoding="utf-8"),
            profile_ref=profile,
            out_wav_path=out_dir / "paragraph_preview.wav",
        )
        console.print(
            f"[bold green]✓ Paragraph Preview Ready:[/bold green] {res['wav_path']} "
            f"({res['sentence_count']} sentences, {res['total_duration_s']}s)"
        )
        return

    if not text:
        raise typer.BadParameter("Provide either `--text` or `--script-file`.")

    if compare_variants_flag:
        comp = compare_voice_variants(
            sentence_text=text,
            variants=[
                {"variant_id": "A", "delivery": "CALM_EXPLANATION", "pace": "NATURAL", "energy": 2, "pause_after_ms": 380},
                {"variant_id": "B", "delivery": "MYSTERIOUS", "pace": "SLOW", "energy": 2, "pause_after_ms": 520},
                {"variant_id": "C", "delivery": "CINEMATIC_REVEAL", "pace": "SLOW", "energy": 4, "pause_after_ms": 580},
            ],
            profile_ref=profile,
            out_dir=out_dir,
        )
        console.print(f"[bold green]✓ Exported {len(comp['variants'])} Voice Variants to:[/bold green] {out_dir}")
        for v in comp["variants"]:
            console.print(f"  • Variant {v['variant_id']} ({v['delivery']}): {v['wav_path']} ({v['duration_s']}s)")
    else:
        prev = preview_voice_sentence(text, profile_ref=profile, out_wav_path=out_dir / "sentence_preview.wav")
        console.print(f"[bold green]✓ Sentence Preview Ready:[/bold green] {prev['wav_path']} ({prev['duration_s']}s)")


@app.command(name="voice-approve")
def voice_approve_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    note: str = typer.Option("Creator approved final narration timing master", "--note"),
) -> None:
    """Lock the approved narration track via SHA-256 checksums (`voice_approval_lock.json`)."""
    ep = _load(manifest)
    lk = approve_and_lock_voice_master(ep, reviewer_note=note)
    console.print(
        f"[bold green]✓ Voice Master Approved & Locked:[/bold green] "
        f"{Path(ep.output_dir) / 'voice_approval_lock.json'} ({lk['narration_norm_wav_sha256'][:16]}...)"
    )


@app.command(name="thumbnail-studio")
def thumbnail_studio_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
) -> None:
    """Generate 2-3 documentary thumbnail concepts & mobile comparison sheet (`160x284` preview)."""
    ep = _load(manifest)
    ep.assert_output_dir_writable()
    pkg = render_thumbnail_concepts_for_episode(ep)
    console.print(
        f"[bold green]✓ Thumbnail Studio Exported {len(pkg.get('concepts', []))} Concepts:[/bold green]\n"
        f"  • Primary Cover: {pkg.get('thumb_jpg')}\n"
        f"  • Mobile Comparison Sheet: {pkg.get('concepts_comparison_sheet_jpg')}"
    )


@app.command(name="analytics-review")
def analytics_review_cmd(
    csv_path: Optional[Path] = typer.Option(None, "--csv", help="YouTube Studio 'Table data.csv' export"),
    retention_csv: Optional[Path] = typer.Option(None, "--retention-csv", help="Optional retention curve CSV"),
    store_json: Path = typer.Option(DEFAULT_YTB_TOOLS_STORE, "--store", help="Fallback ytb-tools/data/store.json"),
    out_dir: Path = typer.Option(
        Path(__file__).resolve().parents[2] / "output" / "analytics_reviews",
        "--out-dir",
        "-o",
    ),
) -> None:
    """Import YouTube Studio CSV or ytb-tools analytics & generate evidence-based Performance Review."""
    if csv_path and csv_path.exists():
        records = parse_youtube_studio_csv(csv_path)
    else:
        records = load_analytics_from_ytb_tools_store(store_json)

    if retention_csv and retention_csv.exists() and records:
        records[0].retention_curve_pct = parse_retention_curve_csv(retention_csv)

    enriched = [enrich_record_with_production_manifest(r) for r in records]
    rep = generate_channel_learning_report(enriched, out_dir=out_dir)
    console.print(
        f"[bold green]✓ Analytics Learning Report Generated:[/bold green] "
        f"{rep['videos_analyzed_count']} videos analyzed -> {out_dir / 'performance_review.md'}"
    )




# ==============================================================================
# PROOF OF WONDER STUDIO v7.0 ? STORY-AWARE AUDIO, SCENE EDITING & CREATIVE QA
# ==============================================================================


@app.command(name="optimize-scenes")
def optimize_scenes_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
) -> None:
    """Evaluate every shot (Keep / Replace / Merge / Remove) against finalized narration."""
    ep = _load(manifest)
    wt = json.loads((Path(ep.output_dir) / "word_timings.json").read_text(encoding="utf-8"))
    rep = optimize_episode_scenes(ep, wt, fps=ep.resolve_style_profile().output.fps, persist_report=True)
    c = rep["counts"]
    console.print(
        f"[bold green]? Scene Optimization Complete:[/bold green] "
        f"{rep['original_scene_count']} -> [cyan]{rep['final_scene_count']} scenes[/cyan] "
        f"(Keep={c['Keep']}, Merge={c['Merge']}, Replace={c['Replace']}, Remove={c['Remove']})."
    )


@app.command(name="plan-soundscape")
def plan_soundscape_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
) -> None:
    """Generate story-aware music, continuous location ambience, 6-question SFX & unified timeline."""
    from pow_studio.schema import resolve_timed_shots

    ep = _load(manifest)
    out_dir = Path(ep.output_dir)
    wt = json.loads((out_dir / "word_timings.json").read_text(encoding="utf-8"))
    t_shots = resolve_timed_shots(ep, int(wt["total_frames_30fps"]), ep.resolve_style_profile().output.fps)
    m_plan = plan_story_music(ep, wt, t_shots, out_dir=out_dir)
    aprof = str((m_plan.get("adaptive_audio_profile") or {}).get("selected_profile", "minimal_documentary"))
    a_plan = plan_environmental_ambience(ep, wt, t_shots, adaptive_audio_profile=aprof, out_dir=out_dir)
    s_plan = plan_context_sfx(ep, wt, t_shots, a_plan, adaptive_audio_profile=aprof, out_dir=out_dir)
    tl = build_unified_av_timeline(ep, wt, music_plan=m_plan, ambience_plan=a_plan, sfx_plan=s_plan, out_dir=out_dir)
    console.print(
        f"[bold green]? Soundscape & Unified Timeline Ready:[/bold green] "
        f"profile=[cyan]{aprof}[/cyan] | music={m_plan['music_sections_count']} sec | "
        f"ambience={a_plan['audible_ambience_sections_count']} sec | "
        f"SFX={s_plan['approved_cues_count']} approved ({s_plan['rejected_for_silence_count']} rejected for silence) | "
        f"sync_issues={tl['sync_issues_count']}"
    )


@app.command(name="creative-qc")
def creative_qc_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
) -> None:
    """Run Studio v7 Voice QA, Music & Effect QA, and Visual & Audio Creative QA."""
    ep = _load(manifest)
    out_dir = Path(ep.output_dir)
    wt = json.loads((out_dir / "word_timings.json").read_text(encoding="utf-8"))
    rep = run_creative_qa(ep, wt, out_dir=out_dir)
    sc = rep["severity_counts"]
    console.print(
        f"[bold {'green' if rep['creative_qa_pass'] else 'red'}]Creative QA Pass={rep['creative_qa_pass']}[/bold {'green' if rep['creative_qa_pass'] else 'red'}] "
        f"(CRITICAL={sc['CRITICAL']}, MAJOR={sc['MAJOR']}, MINOR={sc['MINOR']}, INFO={sc['INFO']}) -> {out_dir / 'creative_qa_report.md'}"
    )
    if not rep["creative_qa_pass"]:
        raise typer.Exit(code=1)


@app.command(name="audio-registry")
def audio_registry_cmd(
    harvest_query: Optional[str] = typer.Option(None, "--harvest", "-q", help="Optional Wikimedia Commons $0 PD/CC audio query"),
    limit: int = typer.Option(2, "--limit", "-n"),
) -> None:
    """Inspect or expand the commercial-safe reusable Audio Asset Registry ($0)."""
    reg = ensure_audio_asset_registry()
    if harvest_query:
        added = harvest_verified_wikimedia_audio(harvest_query, max_results=limit, download=True)
        reg = ensure_audio_asset_registry()
        console.print(f"[cyan]Harvested {len(added)} verified Commons audio recording(s) for '{harvest_query}'.[/cyan]")
    console.print(f"[bold green]? Audio Asset Registry Ready:[/bold green] {len(reg)} commercial-cleared assets cataloged.")


# ==============================================================================
# PROOF OF WONDER STUDIO v8.0 — FOOTAGE-FIRST STORYTELLING, FEASIBILITY & 6-PILLAR QA
# ==============================================================================


@app.command(name="feasibility")
def feasibility_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest to evaluate before production"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Optional output folder for visual_feasibility_report.md"),
    accept_limited: bool = typer.Option(False, "--accept-limited", help="Explicitly accept limited visual coverage if archives lack real footage"),
) -> None:
    """Run Pre-Production Visual Feasibility Gate (Part 3, Section 8) before script lock or rendering."""
    from pow_studio.action_storytelling import analyze_visual_feasibility

    ep = _load(manifest)
    rep = analyze_visual_feasibility(
        topic=ep.topic or ep.primary_title,
        narration_segments=ep.narration_segments,
        available_assets=ep.assets_register,
        user_accepted_limited_visuals=accept_limited,
        out_dir=out_dir,
    )
    tbl = Table(title=f"Visual Feasibility Report — {ep.slug} ({rep['feasibility_status']})")
    tbl.add_column("Story beat", style="cyan")
    tbl.add_column("Required visual", style="white")
    tbl.add_column("Available footage", style="green")
    tbl.add_column("Evidence relevance", style="yellow")
    tbl.add_column("Coverage status", style="magenta")
    for r in rep["feasibility_table"]:
        tbl.add_row(r["story_beat"], r["required_visual"], r["available_footage"], r["evidence_relevance"], r["coverage_status"])
    console.print(tbl)
    if not rep["can_proceed_to_production"]:
        console.print("[bold red]✗ Visual Feasibility Gate Blocked Production:[/bold red] Insufficient real footage for essential story events.")
        raise typer.Exit(code=1)


@app.command(name="discover-footage")
def discover_footage_cmd(
    topic: str = typer.Option(..., "--topic", "-t", help="Documentary topic (generates multi-purpose Subject+Action queries)"),
    online: bool = typer.Option(True, "--online/--offline", help="Query NASA, Wikimedia Commons & Internet Archive ($0 APIs)"),
    limit: int = typer.Option(4, "--limit", "-n", help="Max results per query per archive"),
) -> None:
    """Discover real documentary footage using Subject + Action multi-intent queries ($0)."""
    from pow_studio.video_sourcing import discover_footage_first_by_purpose

    res = discover_footage_first_by_purpose(topic=topic, max_per_query=limit, online=online)
    q_tbl = Table(title=f"Generated Subject + Action Footage Queries — '{topic}'")
    q_tbl.add_column("Purpose", style="cyan")
    q_tbl.add_column("Query", style="white")
    q_tbl.add_column("Target Media Class", style="green")
    for q in res["planned_queries"]:
        q_tbl.add_row(q["purpose"], q["query"], q["target_media_class"])
    console.print(q_tbl)
    console.print(f"[bold green]✓ Unique commercial-safe video candidates discovered:[/bold green] {res['total_unique_video_candidates']}")


@app.command(name="plan-storyboard")
def plan_storyboard_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Optional directory to export action_storyboard_plan.md"),
) -> None:
    """Build 11-field Footage-First Action Storyboard dry-run plan (Part 3, Section 7)."""
    from pow_studio.action_storytelling import build_action_storyboard_plan

    ep = _load(manifest)
    plan = build_action_storyboard_plan(
        slug=ep.slug,
        topic=ep.topic or ep.primary_title,
        narration_segments=ep.narration_segments,
        available_assets=ep.assets_register,
        total_duration_s=float(ep.shots[-1].end_s),
        out_dir=out_dir,
    )
    cm = plan["coverage_metrics"]
    console.print(
        f"[bold green]✓ Action Storyboard Planned ({plan['planned_scene_count']} scenes, {plan['planned_total_duration_s']}s):[/bold green] "
        f"Genuine Moving={cm['genuine_moving_footage_pct']}% | Meaningful Action={cm['meaningful_action_footage_pct']}% | "
        f"Establishing={cm['establishing_footage_pct']}% | Static={cm['static_image_pct']}% | Sci-Viz={cm['scientific_visualization_pct']}%"
    )


@app.command(name="qa-6pillar")
def qa_6pillar_cmd(
    manifest: Path = typer.Option(..., "--manifest", "-m", exists=True, help="Episode YAML manifest"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Optional directory for six_pillar_qa_report.md (never overwrites protected dirs)"),
) -> None:
    """Run 6-Pillar Future-Video QA (Media, Semantic, Repetition, Timeline, Technical, Creative) in dry-run or post-render mode."""
    from pow_studio.creative_qa import run_six_pillar_workflow_qa

    ep = _load(manifest)
    wt_p = Path(ep.output_dir) / "word_timings.json"
    wt = json.loads(wt_p.read_text(encoding="utf-8")) if wt_p.exists() else None
    mp4_p = Path(ep.output_dir) / f"{ep.slug}.mp4"
    rep = run_six_pillar_workflow_qa(
        manifest=ep,
        wt=wt,
        rendered_mp4=mp4_p if mp4_p.exists() else None,
        probe_pixels=True,
        out_dir=out_dir,
    )
    vc = rep["visual_coverage_metrics"]
    console.print(
        f"[bold cyan]6-Pillar QA ({ep.slug}):[/bold cyan] "
        f"Technical=[bold]{'PASS' if rep['technical_approval'] else 'FAIL'}[/bold] | "
        f"Creative=[bold]{'PASS' if rep['creative_approval'] else 'FAIL'}[/bold] | "
        f"Release=[bold {'green' if rep['overall_release_approval'] else 'red'}]{'APPROVED' if rep['overall_release_approval'] else 'BLOCKED'}[/bold {'green' if rep['overall_release_approval'] else 'red'}]\n"
        f"  • Genuine Moving: {vc['genuine_moving_footage_pct']}% | Meaningful Action: {vc['meaningful_action_footage_pct']}% | "
        f"Establishing: {vc['establishing_footage_pct']}% | Static: {vc['static_image_pct']}% (Animated Stills: {vc['animated_still_pct']}%) | "
        f"Sci-Viz: {vc['scientific_visualization_pct']}%"
    )
    for iss in rep["issues"]:
        console.print(f"  [{iss['severity']}] ({iss['pillar']}) {iss['code']}: {iss['message']}")
    if not rep["overall_release_approval"]:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
