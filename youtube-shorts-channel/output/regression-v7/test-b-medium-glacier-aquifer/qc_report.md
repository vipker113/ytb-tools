# Documentary Studio v6.0 Post-Render Quality Assurance Report — `test-b-medium-glacier-aquifer`

- **Production Profile:** `mysterious_earth_exploration`
- **Overall Studio v6 Pass:** **`FAIL`** (`3` failed gates)
- **Master File:** `C:\Users\Admin\Desktop\code\science-knowledge\youtube-shorts-channel\output\regression-v7\test-b-medium-glacier-aquifer\test-b-medium-glacier-aquifer.mp4`
- **Duration:** `81.067 seconds` (`2432` exact frames @ `30/1` CFR; target `20–240s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.0 LUFS`, True Peak `-1.5 dBFS`, Speech Dominance `+23.8 LU`, LRA `1.7 LU`
- **Black Frames (`blackdetect`):** `1` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `20–240s`, `0` frame drift | **PASS** | `1080×1920`, `81.067s` (`2432` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **FAIL** | `1` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `7/7` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`100.0%` moving video** (`81.1s`), **`4` human shots** (`56.0%`), **`5` perspectives**, **`100.0%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `11.58s` (`7` shots), `4` cuts + `2` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `99.26%`, max `2` lines, contrast `12.07:1`, median offset `0.038s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `580.9 KB` (`2` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.27` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **FAIL** | `4` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.45s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H01` (`9.53`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9494`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`False`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.016s`
- **Timeline Assembly & Subtitle Mux:** `148.435s`
- **Multi-Concept Thumbnail Studio:** `3.6s`
- **Total Master Render Time:** `152.247s` (`15.97 fps` effective)

## Shot-Planner Notes & Warnings

- [S01:nasa_helheim_glacier_aquifer.mp4] Effective upscale factor (2.77x) exceeds crisp HD target (2.35x).
- [S04:nasa_helheim_glacier_aquifer.mp4] Effective upscale factor (2.77x) exceeds crisp HD target (2.35x).
- [S07:nasa_helheim_glacier_aquifer.mp4] Effective upscale factor (2.77x) exceeds crisp HD target (2.35x).
- Asset 'nasa_helheim_glacier_aquifer.mp4' used 3 times (exceeds max_uses_per_asset=2).
- Asset 'nasa_helheim_glacier_aquifer.mp4' occupies 42.9% of runtime (exceeds 30% cap).
- Asset 'nasa_exports_twilight_ocean.mp4' occupies 30.1% of runtime (exceeds 30% cap).
