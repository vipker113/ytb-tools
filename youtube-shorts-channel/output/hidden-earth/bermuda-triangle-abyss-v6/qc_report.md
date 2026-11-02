# Documentary Studio v6.0 Post-Render Quality Assurance Report — `bermuda-triangle-abyss-v6`

- **Production Profile:** `deep_ocean_documentary`
- **Overall Studio v6 Pass:** **`PASS`** (`0` failed gates)
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/hidden-earth/bermuda-triangle-abyss-v6/bermuda-triangle-abyss-v6.mp4`
- **Duration:** `80.267 seconds` (`2408` exact frames @ `30/1` CFR; target `66–90s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.0 LUFS`, True Peak `-2.6 dBFS`, Speech Dominance `+10.5 LU`, LRA `1.6 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `66–90s`, `0` frame drift | **PASS** | `1080×1920`, `80.267s` (`2408` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `16/16` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`89.6%` moving video** (`71.9s`), **`3` human shots** (`21.9%`), **`8` perspectives**, **`93.1%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `5.02s` (`16` shots), `11` cuts + `4` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `98.10%`, max `2` lines, contrast `12.07:1`, median offset `0.01s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `663.9 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `2.27` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `20` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H1` (`9.38`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9181`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`True`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `31.122s`
- **Timeline Assembly & Subtitle Mux:** `99.867s`
- **Multi-Concept Thumbnail Studio:** `3.754s`
- **Total Master Render Time:** `134.949s` (`17.84 fps` effective)

## Shot-Planner Notes & Warnings

- [S03:noaa_sonar_mapping_720p.mp4] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S09:noaa_ex1903_new_seep_1080p.mp4] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S10:noaa_ex1903_new_seep_1080p.mp4] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S11:noaa_boxcore_scientists_720p.mp4] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- Opening hook sentence is 20 words (> 18); tighten first sentence so the core contradiction lands within 2.5 seconds.
- [N03] Sentence has 34 words (> 24): 'Where the fast, warm Gulf Stream slams into Atlantic storms, sudden thir...'
- [N06] Sentence has 27 words (> 24): 'Directly beneath Bermuda's crust sits an unusual twenty-kilometer-thick ...'
