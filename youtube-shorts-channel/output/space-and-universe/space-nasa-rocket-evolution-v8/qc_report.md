# Documentary Studio v6.0 Post-Render Quality Assurance Report — `space-nasa-rocket-evolution-v8`

- **Production Profile:** `space_discovery`
- **Overall Studio v6 Pass:** **`PASS`** (`0` failed gates)
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/space-and-universe/space-nasa-rocket-evolution-v8/space-nasa-rocket-evolution-v8.mp4`
- **Duration:** `107.000 seconds` (`3210` exact frames @ `30/1` CFR; target `75–112s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.1 LUFS`, True Peak `-1.5 dBFS`, Speech Dominance `+27.8 LU`, LRA `2.5 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `75–112s`, `0` frame drift | **PASS** | `1080×1920`, `107.000s` (`3210` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `20/20` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`89.4%` moving video** (`95.7s`), **`4` human shots** (`20.5%`), **`5` perspectives**, **`97.1%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `5.35s` (`20` shots), `19` cuts + `0` dissolves, `94.7%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `96.95%`, max `2` lines, contrast `12.07:1`, median offset `0.039s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `696.0 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `2.04` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `20` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **WARN** | Motion @ `11.30s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`1`, Hook=`H2` (`8.93`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9389`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`True`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.009s`
- **Timeline Assembly & Subtitle Mux:** `94.258s`
- **Multi-Concept Thumbnail Studio:** `2.184s`
- **Total Master Render Time:** `96.646s` (`33.21 fps` effective)

## Shot-Planner Notes & Warnings

- [S03] Cut at 7.40s is 3.13s from nearest speech pause
- [S06:jpl_explorer1_1958_archive.webm] Effective upscale factor (2.93x) exceeds crisp HD target (2.35x).
- [S07:mercury_atlas_glenn_broll_720p.webm] Effective upscale factor (3.04x) exceeds crisp HD target (2.35x).
- [S09:mercury_atlas_glenn_broll_720p.webm] Effective upscale factor (3.09x) exceeds crisp HD target (2.35x).
- [S11:gemini_titan2_launch_hd049.mp4] Effective upscale factor (2.99x) exceeds crisp HD target (2.35x).
- [S15:apollo11_f1_500fps_camera_e8_720p.ogv] Effective upscale factor (2.93x) exceeds crisp HD target (2.35x).
- [S16:shuttle_atlantis_sts129_launch_720p.webm] Effective upscale factor (3.07x) exceeds crisp HD target (2.35x).
- [S17:stennis_rs25_engine_test_hd.mp4] Effective upscale factor (3.04x) exceeds crisp HD target (2.35x).
- [N05] Sentence has 31 words (> 24): 'Beneath its hull hung five cavernous F-1 nozzles—each nearly four meters...'
- [N07] Sentence has 25 words (> 24): 'Yet today, NASA's Artemis super-rocket fuses four laser-upgraded RS-25 e...'
