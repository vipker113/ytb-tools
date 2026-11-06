---
name: pow-qa-and-release
description: Runs Proof of Wonder quality gates (14-gate technical QA, 6-pillar QA, creative QA, visual contact sheets), reviews them visually, and hands the approved episode to ytb-tools for the user's review. Use when checking a rendered episode, preparing delivery, or when the user asks whether a video is ready to post.
---

# QA & Release Handoff

## Run all gates

```bash
$PY $STUDIO stage6-quality -m $EP                      # 14 technical gates + deliverables + production manifest
$PY $STUDIO qa-6pillar -m $EP --out-dir <out>/qa       # Media, Semantic, Repetition, Timeline, Technical, Creative
$PY $STUDIO creative-qc -m $EP                         # severity-graded creative issues
```

Release requires **both** `technical_approval` and `creative_approval`, zero CRITICAL/MAJOR creative
issues, storyboard approval matching the current hash (v9 manifests), and voice lock synchronized.

## Look at the sheets yourself

Open and inspect (you can read images): `first_3_seconds_audit_sheet.jpg`,
`transitions_contact_sheet.jpg` / `contact_sheet.jpg`, `native_1to1_pixel_qc_sheet.jpg`,
`thumbnail_small_preview_sheet.jpg`, `ending_audit_sheet.jpg`. Check: frame 0 shows the real subject
with the hook text in the top safe zone and no subtitle bar; no macroblocking in dark areas; no
jitter; captions never cover the subject; overlays inside safe zones; thumbnail readable at 160×284.

## Handoff

1. Confirm `youtube_metadata.md` (title without hashtags, description with sources and credits,
   tags, pinned comment) and thumbnails `thumbnail.jpg` / `thumbnail_variant_B.jpg` / `_C.jpg` exist.
2. Tell the user to open `http://localhost:3000` → "Mac Studio Review" → "Quét lại Output".
3. **Stop.** Publishing/scheduling (default golden window 17:15 VN) happens only on the user's explicit
   instruction for this episode.

## Failing QA

Use the send-back loop in `pow-executive-producer` (max 2 rounds), then report remaining issues.
