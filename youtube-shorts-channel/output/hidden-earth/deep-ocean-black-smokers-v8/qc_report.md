# Documentary Studio v6.0 Post-Render Quality Assurance Report — `deep-ocean-black-smokers-v8`

- **Production Profile:** `deep_ocean_exploration`
- **Overall Studio v6 Pass:** **`FAIL`** (`1` failed gates)
- **Master File:** `C:\Users\Admin\Desktop\code\science-knowledge\youtube-shorts-channel\output\hidden-earth\deep-ocean-black-smokers-v8\deep-ocean-black-smokers-v8.mp4`
- **Duration:** `68.800 seconds` (`2064` exact frames @ `30/1` CFR; target `60–78s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.0 LUFS`, True Peak `-1.4 dBFS`, Speech Dominance `+25.8 LU`, LRA `1.9 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `60–78s`, `0` frame drift | **PASS** | `1080×1920`, `68.800s` (`2064` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `10/10` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`88.3%` moving video** (`60.8s`), **`4` human shots** (`40.2%`), **`4` perspectives**, **`100.0%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `6.88s` (`10` shots), `8` cuts + `1` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `97.02%`, max `2` lines, contrast `12.07:1`, median offset `0.021s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `634.9 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.08` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `10` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H1` (`9.53`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9505`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`False`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.018s`
- **Timeline Assembly & Subtitle Mux:** `119.061s`
- **Multi-Concept Thumbnail Studio:** `5.422s`
- **Total Master Render Time:** `124.762s` (`16.54 fps` effective)

## Shot-Planner Notes & Warnings

- [S08:ifremer_biobaz_sampling_81111.webm] Reclassified from video to 'ANIMATED_STILL' (Artificial pan/zoom over static image detected (raw_diff=6.37, compensated_diff=2.39, ratio=0.38, p90_flow_res=0.19px).).
- [S09] Dissolve duration 0.00s outside recommended 0.45–0.95s.
- Moving footage ratio is 88.3% (goal >= 90% where authentic moving material is available).
