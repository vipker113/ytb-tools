---
name: pow-executive-producer
description: Orchestrates a full Proof of Wonder science Short from topic to approved master (Studio v9). Use when the user asks to make, produce, render, redo, or continue an episode/video/Short for the Proof of Wonder channel, or says "làm tập", "dựng video", "sản xuất tập mới".
---

# Proof of Wonder — Executive Producer (Studio v9)

You orchestrate production end to end. You do NOT improvise the workflow: follow the stage order,
read the stage skills, run the CLI, check the gates, and stop at the user pause points.

## Environment

```bash
cd /Applications/code/science-knowledge/youtube-shorts-channel
PY=.venv/bin/python
STUDIO=pipeline/pow_studio/cli.py
EP=episodes/<episode>.yaml
```

Always know where production stands before acting: read `<output_dir>/studio_state.json`
(stage statuses + gates) and the tail of `<output_dir>/studio_events.jsonl`.

## Stage order (do not reorder)

| # | Stage | Command(s) | Gate / output | Skill to read |
|---|---|---|---|---|
| 0 | Topic intake | `$PY $STUDIO sprint` (reads ytb-tools `/api/pipeline`) | topic, hook, title | — |
| 1 | Footage research | `discover-footage`, `download-footage`, `corpus-ingest`, `match-beats` | candidates on disk with provenance | `pow-footage-research` |
| 2 | Script + manifest | write `episodes/<slug>_v9_documentary.yaml` (`manifest_version: "9.0"`) | schema-valid manifest | `pow-script-and-voice` |
| 3 | Feasibility gate | `$PY $STUDIO feasibility -m $EP --out-dir <out>/planning` | **must pass** (exit 0) | `pow-footage-research` |
| 4 | Story | `$PY $STUDIO stage2-story -m $EP` | hook + momentum pass | `pow-script-and-voice` |
| 5 | Voice | `$PY $STUDIO stage3-voice -m $EP` then **PAUSE** for user listen | user runs/approves `voice-approve` | `pow-script-and-voice` |
| 6 | Visual plan | `render-overlays -m $EP`, `stage4-visual -m $EP --mode draft`, `optimize-scenes`, `plan-soundscape` | preview sheet, `mechanism_overlay_qa.json` | `pow-mechanism-overlay` |
| 7 | Storyboard approval | `export-storyboard -m $EP` → **PAUSE**: user approves in ytb-tools "Studio Backlot" | `storyboard_approval.json` hash matches | — |
| 8 | Master render | `$PY $STUDIO stage5-edit -m $EP --mode master` | MP4 + thumbnails | — |
| 9 | QA | `stage6-quality -m $EP`, `qa-6pillar -m $EP --out-dir <out>/qa`, `creative-qc -m $EP` | technical + creative approval | `pow-qa-and-release` |
| 10 | Handoff | user reviews in ytb-tools "Mac Studio Review" | **PAUSE**: never publish yourself | `pow-qa-and-release` |

## Send-back loop (max 2 rounds)

If `qa-6pillar` reports `creative_approval=False`, or `creative-qc` has CRITICAL/MAJOR issues:
1. Read the report and map each issue to its stage (media → research/visual plan, semantic → shot
   choice, repetition → `optimize-scenes`, timeline → shots/overlays, technical → render).
2. Fix at that stage, re-run from there, re-run QA.
3. After 2 rounds without passing, stop and report to the user with the remaining issues and options
   (re-scope topic, accept limited visuals, swap footage). Never paper over a failing gate.

Record each send-back decision so it appears in the Backlot feed:

```python
from pow_studio.events import emit_event
emit_event(out_dir, "send-back", "decision", "info", detail="QA semantic MAJOR on S04 -> replaced footage")
```

## Reading user storyboard notes

When the user requests changes in Backlot, `storyboard_approval.json` has `decision:
"changes_requested"`, `notes`, and `shotNotes: {sid: text}`. Apply each note in the episode YAML,
re-run `render-overlays` (if an overlay changed) + `export-storyboard -m $EP`, and ask for approval
again in `http://localhost:3000` → **Studio Backlot** (`storyboard_sha256` changes automatically, so
the old approval is invalidated).

## Hard rules

- New episode = new slug and output_dir. Never write into protected folders.
- Narration on disk (`script.md`) must match the rendered voice word-for-word.
- Frame 0 must be the real first frame of a moving shot with the hook question in the top safe zone.
- Report progress to the user in Vietnamese, concise, with links to the key artifacts.
