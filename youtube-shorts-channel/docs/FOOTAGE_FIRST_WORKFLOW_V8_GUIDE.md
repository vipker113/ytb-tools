# Proof of Wonder — Studio v8.0 Footage-First & Action-Based Production Workflow Guide

> **Reusable Production Architecture Documentation (`pipeline/pow_studio` v8.0)**  
> **Cost Policy:** Strictly `$0` (`0₫`) — zero paid APIs, zero subscriptions, zero paid stock libraries, zero Google Cloud Vertex AI.

---

## 1. Core Architectural Shift (v6/v7 → v8.0)

Prior versions of `pow_studio` treated visual selection primarily as **keyword matching + timeline slot filling**, which permitted:
- Static photographs animated via Ken Burns zoom/pan or 2.5D depth parallax (`still_parallax_25d`) to bypass consecutive-still guards (`allow_25d_pair`) or masquerade as moving footage when pre-rendered to `.mp4`.
- Multi-panel composites (`triptych_hook`) containing static JPEGs to count as `100%` moving footage.
- Single photographs split via `crop_box` (`S14 -> S15`) or multiple clips from a single unrelated shoot (`nasa_mauna_loa`) to inflate scene counts.
- Proxy environments (e.g., Hawaiian basalt lava caves or Yellowstone mudpots) to stand in silently for narrated locations (e.g., Ethiopian acid pools or Mexican selenite caverns) due to naive keyword overlap.
- Episode scripts to lock before checking whether authentic commercial-safe video footage actually existed.

**Studio v8.0 (`Footage-First & Action-Based Storytelling`)** enforces four hard architectural invariants across all future videos:
1. **Immutable Source-Level Media Honesty:** Every asset and timeline shot is classified into an explicit **10-class taxonomy** (`SourceMediaClass`). Converting a `.jpg` to `.mp4` or applying digital camera drift (`z0 -> z1`, 2.5D parallax) **never** upgrades a static image into `REAL_VIDEO_*`.
2. **Pre-Production Visual Feasibility Gate:** Before locking any script or synthesizing narration, `feasibility` verifies beat-by-beat visual evidence coverage and blocks production when essential physical events lack authentic footage (unless `user_accepted_limited_visuals=True`).
3. **Action-Based Scene Planning & Canonical Deduplication:** Every shot requires a concrete physical action/process match, canonical source-lineage tracking (`resolve_canonical_source_id`), perceptual `dHash`/`pHash` deduplication, and at least one verified **Progression Dimension** over the preceding scene.
4. **Separated Technical vs. Creative 6-Pillar QA:** Technical encoding health (`technical_approval`) can no longer mask editorial/visual storytelling defects (`creative_approval`). Release requires **both** approvals.

---

## 2. 10-Category Source-Level Media Classification (`pow_studio.media_classifier`)

Defined in [`media_classifier.py`](../pipeline/pow_studio/media_classifier.py):

| `SourceMediaClass` | Genuine Moving Footage | Coverage Bucket | Description & Honesty Rule |
| :--- | :---: | :--- | :--- |
| `REAL_VIDEO_ACTION` | **Yes** | Meaningful Action (`B`) | Real camera recording of physical activity, fieldwork, sampling, fluid/animal motion, or active natural processes. |
| `REAL_VIDEO_ESTABLISHING` | **Yes** | Establishing (`C`) | Real camera flyover, landscape pan, or ambient location video without primary foreground action. |
| `REAL_TIME_LAPSE` | **Yes** *(reported separately)* | Genuine Moving (`A`) | Real camera time-lapse of clouds, ice, stars, or geological/biological change; tracked distinctly from real-time action. |
| `STILL_PHOTO` | **No** | Static Image (`D`) | Unanimated documentary/expedition photograph held cleanly without fake motion (`auto_animate_stills_by_default=False`). |
| `ANIMATED_STILL` | **No** | Static Image (`D`) | Still image with pan, zoom, Ken Burns, or `still_parallax_25d` — **including** pre-rendered `.mp4` slide/zoom clips detected via affine warp compensation. |
| `SCIENTIFIC_IMAGE` | **No** | Static Image (`D`) | Authentic microscope micrograph, telescope frame, satellite earth-observation frame, or instrument readout. |
| `INFOGRAPHIC` | **No** | Sci-Visualization (`E`) | Custom diagram, map, or scale comparison. Multi-box PowerPoint-style slide cards are rejected by `detect_presentation_graphic_metrics()`. |
| `REAL_ANIMATION` | **No** | Sci-Visualization (`E`) | Genuine 3D/2D scientific simulation or orbital/molecular model (never counted as real camera footage). |
| `AI_GENERATED` | **No** | Excluded from real footage | Synthetic AI imagery/video; blocked from masquerading as real documentary evidence. |
| `REENACTMENT` | **No** | Excluded from action proof | Staged dramatic reconstruction; must never be presented as primary scientific evidence. |

### Affine-Compensated Optical Motion Inspection
`inspect_media_authenticity()` decodes clip frames via FFmpeg and fits a 2D global pan/zoom model (`u(x,y) = ax*x + bx`, `v(x,y) = ay*y + by`) across spatial patches before bilinearly warping frame `t` onto `t+1`:
- **Pure pan/zoom over a static image:** High raw frame diff (`> 1.0`), high `global_motion_explained_ratio`, near-zero localized motion residual → classified as `ANIMATED_STILL` (`is_real_moving_footage=False`).
- **Genuine action video:** Localized foreground residual (`p90_patch_residual / median_patch_residual`) exceeds camera drift → classified as `REAL_VIDEO_ACTION` (`is_real_moving_footage=True`).

---

## 3. 5-Part Timeline Visual Coverage Metrics

Computed by `compute_visual_coverage_metrics()` in [`media_classifier.py`](../pipeline/pow_studio/media_classifier.py) with fractional panel weighting (`1/3` per panel for `triptych_hook`):

- **A. Genuine Moving Footage Ratio (`genuine_moving_footage_pct`)** — Target default: **`>= 70%`** (`REAL_VIDEO_ACTION + REAL_VIDEO_ESTABLISHING + REAL_TIME_LAPSE`).
- **B. Meaningful Action Footage Ratio (`meaningful_action_footage_pct`)** — Target default: **`>= 50%`** (`REAL_VIDEO_ACTION`).
- **C. Establishing Footage Ratio (`establishing_footage_pct`)** — Contextual cap so passive scenery does not dominate narrated action.
- **D. Static Image Ratio (`static_image_pct`)** — Default cap: **`<= 20%`** (`STILL_PHOTO + ANIMATED_STILL + SCIENTIFIC_IMAGE`), unless `allow_extended_still_for_essential_evidence=True` on verified historical/microscopy beats.
- **E. Scientific Visualization Ratio (`scientific_visualization_pct`)** — Default cap: **`<= 10%`** (`INFOGRAPHIC + REAL_ANIMATION`).

All thresholds are configurable in `config/profiles/*.yaml` (`AssetSelectionRules` in [`style_profile.py`](../pipeline/pow_studio/style_profile.py)) and adapt to topic evidence constraints rather than forcing fake visual variety.

---

## 4. Reusable CLI Commands (`pipeline/pow_studio/cli.py`)

Run from `youtube-shorts-channel` with `$env:PYTHONUTF8="1"`:

### Step A — Multi-Purpose Subject + Action Footage Discovery (`$0`)
Queries **NASA Image & Video Library**, **Wikimedia Commons**, and **Internet Archive** (`archive.org`) across differentiated action intents (`scientific_sampling`, `fieldwork_expedition`, `active_environmental_process`, `equipment_operation`, `closeup_evidence`, `establishing_context`):
```powershell
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py discover-footage -t "Dallol Ethiopia hydrothermal acid pools" --online
```

### Step B — Pre-Production Visual Feasibility Gate
Evaluates every clause-level story beat against verified commercial-safe assets **before** locking narration or rendering, outputting `visual_feasibility_report.md` and `.json`:
```powershell
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py feasibility -m episodes/<your_episode>.yaml --out-dir output/<slug>/planning
```
If essential visual beats lack real footage, production exits with code `1` and recommends concrete topic/angle adjustments unless `--accept-limited` is explicitly passed.

### Step C — 11-Field Action Storyboard Dry-Run Planner
Generates a complete scene-by-scene dry-run storyboard (`action_storyboard_plan.md` & `.json`) containing all 11 documentary planning fields (`scene_id`, `time_range`, `narration_excerpt`, `narrative_purpose`, `visual_description`, `media_type`, `source_reference`, `relevance_explanation`, `why_this_shot_moves_story_forward`, `crop_framing_notes`, `transition_type`):
```powershell
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py plan-storyboard -m episodes/<your_episode>.yaml --out-dir output/<slug>/planning
```

### Step D — 6-Pillar Future-Video QA Gate
Executes **Media QA**, **Semantic QA**, **Repetition QA**, **Timeline QA**, **Technical QA**, and **Creative QA**, reporting `technical_approval` and `creative_approval` separately:
```powershell
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py qa-6pillar -m episodes/<your_episode>.yaml --out-dir output/<slug>/qa
```

---

## 5. Honest Status: Implemented vs. Proposed Future Capabilities

### Implemented & Automated Today (`$0` Local Python)
- **10-Class `SourceMediaClass` taxonomy & immutable source-lineage tracking** (`media_classifier.py`, `schema.py`).
- **Affine-compensated 2D patch motion inspector** separating baked Ken Burns `.mp4`s (`ANIMATED_STILL`) from genuine camera action (`REAL_VIDEO_ACTION`) (`media_classifier.py`, `video_sourcing.py`).
- **Presentation-slide / multi-box infographic detector** blocking PowerPoint-style dashboard cards and unreadable micro-labels (`detect_presentation_graphic_metrics`).
- **Subject + Action multi-intent footage discovery** across NASA, Wikimedia Commons, and Internet Archive (`video_sourcing.py`, `action_storytelling.py`).
- **Clause-level 10-field visual beat extraction, anti-keyword-trap & anti-proxy-location relevance scoring, pre-production feasibility gate, and 11-field storyboard planner** (`action_storytelling.py`).
- **64-bit `dHash` + 2D-DCT `pHash` + composition cosine similarity + canonical source IDs + 7-dimension progression & stale-visual-topic-drift detection** (`deduplication.py`).
- **Adaptive still handling (`auto_animate_stills_by_default=False`) & strict consecutive-still / multi-crop enforcement** (`shot_planner.py`, `compositor.py`, `scene_editor.py`).
- **6-Pillar QA (`run_six_pillar_workflow_qa`) separating `technical_approval` from `creative_approval` + native `>=1080x1920` source honesty checks** (`creative_qa.py`, `qc_suite.py`).

### Proposed Future Enhancements (`P2` / `P3`) & Remaining Human Judgment
- **Open-weights local vision-language verification (`P2`, optional local VLM/CLIP):** Current `$0` CPU semantic verification combines rich archive metadata, action-verb/rejection-marker parsing, proxy-geography conflict rules, and pixel-level optical/slide inspection. If an archive file is mislabeled by its uploader (e.g., an uploader titled a video *"Dallol acid sampling"* when the pixels show a tourist parking lot), human visual review or an optional local open-weights VLM (`CLIP` / `Qwen2.5-VL` local GGUF) is required to catch mislabeled uploads.
- **Automated Open-Data Map & Telemetry Rendering (`P3`):** Replacing legacy diagram slides with procedural terrain/bathymetry renders from public USGS/GEBCO DEM tiles.
- **Editorial Nuance & Scientific Irony:** Deciding when an archive's visual scarcity warrants pivoting the episode's narrative angle vs. intentionally framing the story as a rare historical-photograph mystery remains an editorial human decision assisted by `feasibility`.
