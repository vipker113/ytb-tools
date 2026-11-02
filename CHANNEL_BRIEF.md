# CHANNEL BRIEF — Mind-Blowing Science (YouTube Shorts)

**Last Updated:** 2026-10-27 (*Proof of Wonder* #01 Venus & #02 Mars *Ingenuity* Packages Completed with Unified Frame-0 Thumbnail Standard)  
**Workspace Root:** `/Applications/code/science-knowledge`  
**Channel Directory:** `/Applications/code/science-knowledge/youtube-shorts-channel`  
**Primary Rendering Toolchain:** `MoneyPrinterTurbo` (`v1.3.9` `.venv`) + Frame-Accurate `FFmpeg` / `Pillow` Narration-Locked Pipeline  
**Current Project Status:** **Proof of Wonder #01 (`01-venus-hotter-than-mercury/`) & #02 (`02-mars-helicopter-1-percent-air/`) Completed & Synchronized 1-to-1**

> **Core Creative Mandate (Approved & Locked):** Creative quality, authentic science-documentary storytelling (`Thumbnail → Question → Proof → Explanation`), exact sentence-to-shot synchronization, scientific accuracy, and audience retention strictly supersede production volume. Never produce generic AI-looking slides, dashboard/HUD layouts, scientifically misleading thumbnails, or loosely matched B-roll.

---

## How Decisions Are Tracked in This Document

Every section below strictly separates:
- **Approved Requirements (Confirmed & Locked):** Decisions explicitly mandated by the user (including `D1`–`D6` and the `2026-10-27` **Proof of Wonder Overhaul**).
- **Pending User Review / Next Stage:** Items staged for user sign-off before resuming multi-video batch rendering.

---

## 1. Channel Positioning & Editorial Rule (`Proof of Wonder`)

### Approved Requirements
- **Channel Concept:** Faceless, English-language science documentary YouTube Shorts channel (working title: *Mind-Blowing Science*).
- **Target Audience:** International English-speaking curiosity-driven viewers across mobile Shorts feeds (general educated public, students, lifelong learners; zero specialist prerequisites assumed).
- **Mandatory Editorial Rule (`Thumbnail → Question → Proof → Explanation` — Locked 2026-10-27):**
  - Every Short **must begin with a direct spoken question** closely connected to its thumbnail and title.
  - The **first `1–2 seconds`** must simultaneously contain:
    1. The actual unmistakable visual subject of the video.
    2. A compelling, concise spoken question (natural spoken English — never generic AI phrasing or article-style prose).
    3. A matching concise on-screen question or short hook inside mobile-safe margins.
    4. A relevant moving shot or strong visual demonstration (never begin with a logo, greeting, slow establishing shot, unrelated spacecraft/footage, or a static copy of the thumbnail).
  - Thumbnail, title, opening question, and first shot must all **promise and deliver the exact same story**.
- **Four-Part Documentary Structure:**
  1. **Hook:** Introduce a specific question or apparent physical contradiction immediately at `0.00s`.
  2. **Evidence:** Show the actual object, event, or planetary/physical phenomenon.
  3. **Mechanism:** Explain the scientific cause with relevant moving footage and restrained `30 fps` explanatory animation (`<= 30%` of runtime).
  4. **Payoff:** Resolve the opening question directly and leave the viewer with one memorable conclusion.
- **Format & Delivery:** Vertical `9:16` YouTube Shorts (`1080 × 1920`, `30 fps`, H.264 video + AAC audio), `35–45 seconds` (`25–45s` outer window) per Short.
- **Publishing Boundary:** Zero automatic or manual uploads to YouTube without explicit prior user approval.

---

## 2. Content Niche, Topic Selection & Zero-Cost Footage Gate

### Approved Requirements
- **Three Core Content Pillars (`D1` — Approved 2026-10-26):**
  1. **Space & Planetary Physics** (planetary atmospheres, orbital & ring mechanics, astrophysics, solar physics).
  2. **Everyday Physics & Engineering** (aerodynamics, thermodynamics, wave propagation, atmospheric optics).
  3. **Human Body & Physiology** (space physiology, neurobiology, sensory perception, autonomic reflexes).
- **Strict Story-Coherence & Footage Gate (Locked 2026-10-27):**
  - Do **not** approve a topic for production merely because its research score is high or a script has already been written.
  - Before rendering any video, verify that an honest, curiosity-driven thumbnail, direct opening question, natural script, and zero-cost HD moving footage **all describe the exact same specific story**.
  - If a strong thumbnail cannot be designed honestly or exact sentence-level footage is unavailable under the `\$0` policy, **defer or re-scope the topic** until the creative/footage problem is solved — never substitute generic exercise clips, unrelated planets, or keyword-matched filler.
- **Approved Pilot `11` Hold (`D2`):** `output/v2/11-why-does-metal-feel-colder-than-wood.mp4` remains preserved and held from publication until matching HD thermal-imaging footage replaces its `16:9` letterboxed and `28.1°C`/`26°C` mismatched clips.

---

## 3. Mandatory Narration-First Timeline & Sentence-to-Shot Alignment

### Approved Requirements (Locked 2026-10-27)
Never generate audio, subtitles, and shot plans as independent deliverables that can drift apart. Every Short must be built in this **strict 8-step execution order**:
1. **Finalize & Fact-Check Spoken Script:** Must sound natural aloud and match verified institutional research; final `script.md` on disk must match rendered narration **word-for-word** (except explicitly labeled non-spoken notes).
2. **Generate Narration Audio:** Synthesize with approved narrator voice **`en-US-AndrewMultilingualNeural`** (`rate = 1.0`, Edge TTS) and ear-audit the full `.mp3`.
3. **Extract Exact Word & Sentence Timings:** Capture exact `WordBoundary` start/end timestamps (`word_timings.json`) directly from the generated audio.
4. **Generate Verbatim Subtitles:** Build `subtitles.srt` directly from the final spoken word timings so captions never drift or cross shot cuts.
5. **Create Frame-Accurate Timed Shot Plan (`Sentence-to-Shot Manifest`):** Lock every shot's `start_sec` and `end_sec` (`integer frames @ 30 fps`) inside natural spoken pauses (`>= 180 ms`). For every shot, log:
   - Start & end timestamps (`s`)
   - Exact narration sentence or phrase
   - Exact subtitle segment(s)
   - Intended visible subject or event
   - Actual video asset path
   - Verified source URL & license
   - Short explanation of why the footage proves or illustrates that exact narration
6. **Select & Multi-Frame Inspect Actual Visual Assets (Pre-Render QC):** Never trust API titles or single midpoint frames. Inspect 1-second multi-frame strips of candidate source clips (checking for internal cuts, webcam talking heads, spacecraft boom obstructions, burned-in trailer titles, or end fades) and generate a **Pre-Render Source-Clip Contact Sheet** (`start`, `mid`, `end` frames per shot vs. timed narration) before final rendering.
7. **Render Final Video (Studio-Master Bitrate & Subpixel Stability):**
   - Never crop moving planets/objects via per-frame brightness thresholding or integer `round()` pixel snapping (use pure `float64`/`float32` subpixel analytical geometry such as `pipeline/planet_sphere_3d.py`).
   - Prefer official studio-master `.mp4` reels (e.g., NASA GSFC SVS `18–58 Mbps` `1080p`/`4K` vertical masters) and `4K`–`11.5K` planetary mosaics over compressed Wikimedia `.webm` transcodes or upscaled vintage SD footage.
   - Concatenate integer-frame shots frame-accurately (`>= 70%` real moving planetary/spacecraft/documentary visuals, `<= 30%` restrained `30 fps` mechanism animations), burn clean `D4` sentence captions (`BeVietnamPro-Bold.ttf`, `#FFFFFF` on translucent `#0B1021` pill at `y = 82%`), mix `44.1 kHz` AAC narration (`--bgm-type none`), and encode with `-crf 14 -aq-mode 3 -aq-strength 1.1` + subtle micro-dithering to prevent dark-space `8×8` macroblocking. Ensure all upper/diagram labels stay strictly within `y ∈ [215, 1380]`.
8. **Post-Render Multi-Frame, `1:1` Native-Pixel & Temporal Jitter Inspection:** Downscaled `225×400` thumbnails hide compression macroblocks and 30 Hz jitter. Every rendered Short must pass four visual QC sheets before delivery:
   - **First-3-Seconds Audit Sheet** (`6` dense frames across `0.15s–3.20s`).
   - **Consecutive-Frame Jitter Audit Strip** (`Frames 0–5` consecutive `1:1` unscaled crops verifying `0.00 px` subject/UI jitter).
   - **`1:1` Native-Pixel Sharpness Sheet** (`540 × 540` unscaled `1:1` crops from the final `1080 × 1920` MP4 across every shot verifying zero macroblocks and zero upscaled SD blur).
   - **Post-Render Shots & Transitions Contact Sheet** (`IN+0.12s`, `MID`, `OUT-0.12s` across every shot = `30` frames).

---

## 4. Unified First-Frame (`t = 0.000s`) Thumbnail Standard & Same-Directory Workflow

### Approved Requirements (`Proof of Wonder` Frame-0 Standard — Locked 2026-10-27)
- **Unified Frame-0 (`t = 0.000s`) Thumbnail Rule:** Every Short's official thumbnail is exported **directly from the exact first frame (`Frame 0`, `t = 0.000s`) of the video** via `pipeline/first_frame_thumbnail.py`.
- **Zero-Loss Uncompressed RGB Master Source:** Always export Frame `0` from the **uncompressed `24-bit` RGB master frame (`shot_01_frame0_master.png`)** *before* `yuv420p` H.264 video compression (ensuring `4:4:4` `subsampling=0` chroma clarity on text edges and planetary rims, with `< 2.0 MB` JPEG size for YouTube Studio).
- **Same-Directory Sidecar Convention:** Save `<video-slug>.jpg` (`4:4:4`, `q=96`, `< 2 MB`) and `<video-slug>.png` (lossless `24-bit` RGB) **in the exact same directory as `<video-slug>.mp4`** (never hidden inside a separate `thumbnails/` subfolder).
- **Clean Bottom Zone at `t = 0.000s`:** Spoken subtitle Cue 1 starts at `t >= 0.08s`, keeping `Frame 0` (`t = 0.000s`) completely free of bottom spoken-subtitle bars while displaying the dominant subject(s), factual visual situation, and top safe-zone question hook.
- **Scientific Visual Honesty & Instant Motion:** Frame `0` is the real Frame `0` of a moving `30 fps` opening shot (never a frozen static poster frame held across multiple frames, and never an orange/lava false-color misrepresentation).
- **Mandatory Small-Preview & `1:1` Pixel Verification:** Automatically generate and inspect `thumbnail_small_preview_sheet.jpg` (`9:16` full view + `160 × 284 px` mobile shelf clean/with YT title overlay + `1:1` crop + `1:1` unscaled native pixel check) alongside every rendered Short.

---

## 5. Scientific Accuracy, Provenance & Zero-Cost Toolchain

### Approved Requirements
- **Minimum Two Primary Institutional/Peer-Reviewed Sources Per Video:** Verified URLs from NASA, ESA, NOAA, NTRS, Chandra, NIH/PubMed/PMC, or peer-reviewed journals.
- **100% Visual-Verbal Numerical Agreement:** Every visible label, temperature, distance, percentage, and physical process must agree with the spoken narration and verified sources (e.g., distinguishing Venus's `~75%` visible-light cloud reflectivity from outgoing thermal infrared trapped by its `96.5%` $\text{CO}_2$ atmosphere at `464°C` vs. airless Mercury's `+430°C` day / `-180°C` night).
- **Strict `\$0` Budget (`D1`):** Free local tools (`FFmpeg 9.0.2`, `Pillow`, `NumPy`, `MoviePy`, `edge-tts`, SIL OFL fonts) and rights-cleared open repositories (`Public Domain`, `CC0`, `CC BY`, `CC BY-SA`) only. Zero paid API calls and zero credential prompts.

---

## 6. Current Deliverables Inventory & Next Stage

| Deliverable | Exact Path | Status |
| :--- | :--- | :--- |
| **Proof of Wonder #01 — Venus Hotter Than Mercury (Complete Package)** | `youtube-shorts-channel/output/proof-of-wonder/01-venus-hotter-than-mercury/` | **Completed & Verified (2026-10-27)** — Includes `01-venus-reflects-most-sunlight-why-is-it-hotter-than-mercury.mp4`, matching same-directory Frame-0 thumbnails `01-venus-reflects-most-sunlight-why-is-it-hotter-than-mercury.{jpg,png}`, `thumbnail_small_preview_sheet.jpg`, `script.md`, `narration.mp3`, `word_timings.json`, `subtitles.srt`, `sentence_to_shot_manifest.{csv,md}`, `pre_render_source_clips_contact_sheet.jpg`, `first_3_seconds_audit_sheet.jpg`, `shot01_consecutive_frames_1to1_qc.jpg`, `native_1to1_pixel_qc_sheet.jpg`, and `final_shots_and_transitions_contact_sheet.jpg`. |
| **Proof of Wonder #02 — Mars *Ingenuity* Helicopter in 1% Air (Complete Package)** | `youtube-shorts-channel/output/proof-of-wonder/02-mars-helicopter-1-percent-air/` | **Completed & Synchronized 1-to-1 (2026-10-27)** — Includes `02-mars-has-almost-no-air-how-did-this-helicopter-fly.mp4` (`44.200s`, `1080×1920 @ 30 fps`), matching same-directory Frame-0 thumbnails `02-mars-has-almost-no-air-how-did-this-helicopter-fly.{jpg,png}`, `thumbnail_small_preview_sheet.jpg`, `script.md`, `narration.mp3`, `word_timings.json`, `subtitles.srt`, `sentence_to_shot_manifest.{csv,md}`, `ffprobe_validation.json`, and all 5 pre/post-render visual QC sheets. |
| **Proof of Wonder Quality & Batch-1 Alignment Audit Report** | `youtube-shorts-channel/reports/proof-of-wonder-venus-audit-and-batch1-review.md` | **Completed (2026-10-27)** — Documents all 7 forensic defects fixed from the prior Venus video + full alignment audit and action plan for `R2-02`, `R2-03`, `R2-04`, and `R2-05`. |
| **Preserved Prior Batch 1 Outputs (`01`–`05`)** | `youtube-shorts-channel/output/batch-1/01..05-*.mp4` & `output/batch-1/thumbnails/` | **Preserved Untouched on Disk** — Kept intact for side-by-side comparison; superseded editorially by `output/proof-of-wonder/`. |
| **Round-2 Topic, Market & Voice Audition Archives** | `sources/topic-research-round-2.csv`, `reports/market-and-topic-research-round-2.md`, `assets/voice_audition/` | **Preserved Untouched** |
| **Legacy `v2` Pilots & Deprecated `v1` Assets** | `output/v2/`, `output/shorts/`, `scripts/01..30.md`, `thumbnails/01..30.{png,jpg}` | **Preserved Untouched** |

### Pending User Confirmation (Next Stage)
- **Next Candidate Topics Ready After User Review:** `R2-03` (Saturn's Giant Rings Thinner Than a House), `R2-05` (Why Space Is Silent — Except Inside the Perseus Galaxy Cluster), or everyday/human-body *Proof of Wonder* candidates (`#28` Water-Wrinkled Fingers Nerve Grip Test, `#22` Why You Can't Tickle Yourself). Await explicit user selection before rendering the next Short.
