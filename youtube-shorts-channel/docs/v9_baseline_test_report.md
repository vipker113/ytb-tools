# Studio v9 Baseline Verification & Golden Render Report (M0)

## 1. Environment & Pre-Modification Test Suite
- **Machine:** Apple M2 Pro (`arm64`), 16 GB unified memory, macOS `15.6.1`
- **Toolchain:** Python `3.11.17` (`youtube-shorts-channel/.venv` built via `uv`), FFmpeg `9.0.2`, Node.js `v20.19.5`
- **Baseline Test Result (before any Studio v9 code modifications):**
  - Command: `.venv/bin/python -m pytest pipeline/tests -q -p no:cacheprovider`
  - Result: **`28 passed in 71.70s`** (0 failures, 0 errors)
- **Manifest Compatibility Check:**
  - All 20 existing `episodes/*.yaml` manifests load cleanly with Studio v9 optional fields at defaults (`visual_corpus_mode="off"`, `require_storyboard_approval=False`, `mechanism_overlays=[]`).

## 2. Golden Render Equality Baseline
- **Episode:** `episodes/space_perseus_black_hole_v6_documentary.yaml` (full local voice, SFX, and footage present on disk; rendered into isolated scratch slug `perseus-black-hole-sound-v6__golden` without touching protected completed directories)
- **Reference Checksum File:** `.golden/perseus-black-hole-sound-v6.master.framemd5.json` (gitignored)
- **Baseline Frame Count:** `2119` frames (`1080x1920 @ 30fps`)
- **Post-M0/M2 Equality Verification:**
  - Command: `.venv/bin/python pipeline/v9_golden_render.py --compare`
  - Result: **`GOLDEN MATCH: 2119/2119 frames identical`**
