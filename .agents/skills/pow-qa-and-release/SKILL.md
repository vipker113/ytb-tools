---
name: pow-qa-and-release
description: Verifies the final 1 video + 3 sample thumbnails deliverable package and hands off to ytb-tools (Phòng Duyệt & Đăng) for the user's review. Use when checking a rendered episode, preparing delivery, or when the user asks whether a video is ready to post.
---

# Proof of Wonder — Fast Deliverable Verification & Release Handoff

## Clean Output Deliverable Standard

Every completed episode folder (`youtube-shorts-channel/output/<playlist>/<slug>/`) must stay fast and clean, containing **only**:
- `<slug>.mp4` (`1` final rendered `1080×1920` `30fps` video)
- `thumbnail.jpg` (Sample Thumbnail A — Primary)
- `thumbnail_variant_B.jpg` (Sample Thumbnail B)
- `thumbnail_variant_C.jpg` (Sample Thumbnail C)
- `youtube_metadata.md`, `subtitles.srt`, `script.md` (lightweight text metadata read by `ytb-tools` `Phòng Duyệt & Đăng`)

Running `$PY $STUDIO all -m $EP --mode master` automatically generates these files and prunes all intermediate build directories (`shots/`, `overlays/`, `work_audio/`, `board/`, `planning/`, `qa/`, contact sheets, and JSON/CSV reports).

## Handoff to `ytb-tools` (`Phòng Duyệt & Đăng`)

1. Visually inspect `thumbnail.jpg`, `thumbnail_variant_B.jpg`, and `thumbnail_variant_C.jpg` (via `read_file`) to confirm:
   - Each follows the **Visual-Cue Thumbnail Standard**: clear foreground cutout/inset + smooth curved arrow pointing directly at the phenomenon + unmistakable status badge (`✕` / `?` / `!` / `✓`) on the arrow + legible 2-line English hook headline (`<= 8` words) with zero text/graphic collisions.
2. Verify `http://localhost:3000` is running (`curl -sI http://localhost:3000/api/mac-outputs | head -n 5`).
3. Present the finished `<slug>.mp4` and the 3 sample thumbnails (`thumbnail.jpg`, `thumbnail_variant_B.jpg`, `thumbnail_variant_C.jpg`) to the user in Vietnamese.
4. **Never publish to YouTube yourself** (`cli.py publish` or `/api/youtube/upload`) unless the user explicitly instructs you to upload/publish.
