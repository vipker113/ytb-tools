---
name: pow-executive-producer
description: Orchestrates a fast, single-pass Proof of Wonder science Short from topic to 1 Master Video + 3 Sample Thumbnails. Use when the user asks to make, produce, render, redo, or continue an episode/video/Short for the Proof of Wonder channel, or says "làm tập", "dựng video", "sản xuất tập mới".
---

# Proof of Wonder — Fast Single-Pass Executive Producer

You produce complete Proof of Wonder Shorts in a **single uninterrupted pass** without stopping for intermediate approvals (`Studio Backlot` and `voice-approve` are retired). Your target deliverable for every episode is:
1. **`1` Master Video (`<slug>.mp4`)** — `1080×1920` (`9:16`), `30fps`, real documentary footage, 5-layer audio, cinema boxless subtitles, optional ManimCE alpha overlays.
2. **`3` Intuitive Visual-Cue Thumbnails (`thumbnail.jpg`, `thumbnail_variant_B.jpg`, `thumbnail_variant_C.jpg`)** — 3 distinct `9:16` visual-story concepts (`[Upper-Left Cutout/Inset] ──(Curved Arrow + ✕/?/!)──► [Real Phenomenon] + [2-Line English Hook]`) ready to pick in `ytb-tools` (`Phòng Duyệt & Đăng`).
3. **Lightweight YouTube Metadata (`youtube_metadata.md`, `subtitles.srt`, `script.md`)** — so `ytb-tools` loads the episode immediately.

## Environment

```bash
cd /Applications/code/science-knowledge/youtube-shorts-channel
PY=.venv/bin/python
STUDIO=pipeline/pow_studio/cli.py
EP=episodes/<episode>.yaml
```

## Streamlined 3-Step Production Workflow (Do Not Run Bloated Intermediate Stages)

| Step | Action | Command | Output |
|---|---|---|---|
| **1. Footage + Cutout** | Search & download commercial-safe (`PD / CC0 / CC BY`) real moving clips (`>=90%` real moving video, `0` burned-in open captions in cropped 9:16 zone) **plus 1 foreground object image/PNG cutout** for the thumbnail `visual_cue` | `$PY $STUDIO discover-footage -t "<topic>"` + `$PY $STUDIO download-footage ... --no-audit` | Verified clips + cutout in `assets/raw_footage/<dir>/` (or `assets/thumbnail_sprites/`) |
| **2. Manifest** | Write `episodes/<slug>.yaml` (`require_storyboard_approval: false`, `visual_corpus_mode: "off"`, 3 `thumbnail_concepts` A/B/C with `visual_cue`, 0–2 `mechanism_overlays`) | Edit YAML directly | Schema-valid episode YAML |
| **3. Single-Pass Render** | Synthesize directed narration + 5-layer audio, render shots in parallel via in-memory pipe, mux `<slug>.mp4` + 3 visual-cue thumbnails, and auto-prune all intermediate build files | `$PY $STUDIO all -m $EP --mode master` | `<slug>.mp4` + `thumbnail.jpg` + `thumbnail_variant_B.jpg` + `thumbnail_variant_C.jpg` |

## Visual-Cue Thumbnail Standard (Mandatory for All 3 Sample Thumbnails)

Every episode MUST define 3 distinct `thumbnail_concepts` (`A`, `B`, `C`) using the declarative `visual_cue` schema so viewers grasp the scientific paradox in `0.3s`:
- **Foreground Cutout (`cutout_file`):** Isolated object (`RGBA PNG` or clean white/black background photo via `cutout_mode: "auto"`, or `circle_badge` subject close-up) placed in the upper-left (`cutout_cx: 0.23, cutout_cy: 0.21`), leaving the main phenomenon unobstructed in the middle/right (`x ≈ 0.55–0.85, y ≈ 0.45–0.60`). Use `mirror_horizontal: true` on text-free background frames whenever flipping places the phenomenon directly under `arrow_end`.
- **Curved Ribbon Arrow + Status Badge (`symbol`):** Point `arrow_end` directly into the phenomenon and pick the matching badge on the arrow shaft:
  - `red_x` (`✕`) or `ban_circle`: *"Why can't we / Never / Forbidden / Impossible / Vanished"* (e.g., `WHY CAN'T WE DUMP | TRASH INTO LAVA?`)
  - `question_mark` (`?`): *"Why / How / Unsolved scientific mystery"*
  - `warning` (`!`): *"Deadly physics / Explosive trigger / Extreme hazard"*
  - `check` (`✓`): *"How it actually survived / Counterintuitive mechanism"*
- **2-Line English Curiosity Headline (`headline_text`):** Clear, everyday English (`<= 8` words, split with `|`), paired with a short uppercase `kicker_text`.

```yaml
thumbnail_concepts:
  - concept_id: "A"
    src_file: "<phenomenon_clip_A.mp4>"
    src_time_s: 12.0
    headline_text: "WHY CAN'T WE DUMP|TRASH INTO LAVA?"
    kicker_text: "1,600× STEAM EXPLOSION"
    cx: 0.52
    cy: 0.54
    zoom: 1.04
    text_position: "bottom"
    accent_rgb: [255, 212, 59]
    visual_cue:
      cutout_file: "<foreground_object_cutout.png>"
      cutout_mode: "auto"
      cutout_cx: 0.23
      cutout_cy: 0.21
      cutout_scale: 0.36
      cutout_rotation_deg: -14.0
      arrow_end: [0.72, 0.51]
      symbol: "red_x"
```
*(To regenerate ONLY the 3 thumbnails of an existing episode in ~2 seconds, run `$PY $STUDIO thumbnail-studio -m $EP`.)*

## What NOT to Run During Normal Episode Creation

To keep episode creation fast, **do NOT run** these slow/redundant commands unless explicitly debugging a specific failure:
- Do NOT run `corpus-ingest` or `match-beats` (CLIP neural network indexing across the whole library).
- Do NOT run `export-storyboard` or wait for `Studio Backlot` approval.
- Do NOT run `voice-approve` or pause after `stage3-voice`.
- Do NOT render twice (`--mode draft` then `--mode master`) — run `$PY $STUDIO all -m $EP --mode master` once!
- Do NOT run `stage6-quality`, `qa-6pillar`, or `creative-qc` (which re-transcribe audio with Whisper and generate 6 contact sheet JPEGs). Instead, verify clean framing on your source clips before/during step 1.

## Hard Rules

- New episode = new slug and `output_dir`. Never write into `PROTECTED_COMPLETED_OUTPUT_DIRS`.
- Never run `$PY $STUDIO publish` or upload to YouTube unless the user explicitly asks you to publish that specific episode.
- Report completion concisely in Vietnamese with clickable links to `<slug>.mp4` and the 3 sample thumbnails (`thumbnail.jpg`, `thumbnail_variant_B.jpg`, `thumbnail_variant_C.jpg`).
