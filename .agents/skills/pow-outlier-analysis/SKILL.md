---
name: pow-outlier-analysis
description: Analyzes the pacing and hook anatomy of a competitor outlier YouTube Short (or our own episode) and turns it into differentiated ideas for Proof of Wonder. Use when the user asks to analyze, dissect, or learn from a competitor/outlier video, or compare our pacing with top channels.
---

# Outlier Video Reference Analysis (Studio v9 M6)

Purpose: learn structure (pacing, hook mechanics, visual mix), never copy content.

## Commands

```bash
$PY $STUDIO analyze-outlier --video-id <11-char id>        # temp 480p download, deleted after analysis
$PY $STUDIO analyze-outlier --video-id <id> --mode transcript_only
$PY $STUDIO analyze-outlier --local output/<pl>/<slug>/<slug>.mp4   # our own episode, for comparison
$PY $STUDIO outlier-patterns                                # aggregate + pacing gap report
```

Outputs: `youtube-shorts-channel/research/outliers/<id>/outlier_anatomy_brief.{json,md}`,
`contact_sheet.jpg`. The downloaded video is deleted unless `--keep-media` is passed (only for debugging;
never reuse competitor footage in any episode).

## Your part after the tool runs

Look at `contact_sheet.jpg` and the hook keyframes, then fill `agent_annotations` in the brief:
- **Hook, 5 aspects:** Subject · Subject motion · Scene (overlays listed separately, POV, setting) ·
  Spatial framing · Camera. Mark N/A explicitly.
- **What works:** 2–3 concrete mechanics (e.g. "question spoken at 0.3 s over the subject in motion",
  "2 cuts inside the first 3 s", "number on screen before it is spoken").
- **Differentiation seeds (≥ 2):** angles the competitor missed that real footage can prove for us.

## Rules

- Do not copy sentences, titles, thumbnails, or footage. Paraphrasing a competitor's script is copying.
- Keep only derived metrics and small keyframes; the analysis is private research.
- Feed results into ideas via ytb-tools ("Lưu ý tưởng kèm giải phẫu") or the episode brief.
