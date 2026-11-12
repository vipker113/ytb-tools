# Documentary Studio v6.0 Post-Render Quality Assurance Report — `space-nasa-spacesuit-evolution-v8`

- **Production Profile:** `space_discovery`
- **Overall Studio v6 Pass:** **`PASS`** (`0` failed gates)
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/space-and-universe/space-nasa-spacesuit-evolution-v8/space-nasa-spacesuit-evolution-v8.mp4`
- **Duration:** `110.667 seconds` (`3320` exact frames @ `30/1` CFR; target `75–115s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.1 LUFS`, True Peak `-1.3 dBFS`, Speech Dominance `+29.7 LU`, LRA `2.3 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `75–115s`, `0` frame drift | **PASS** | `1080×1920`, `110.667s` (`3320` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `22/22` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`90.1%` moving video** (`99.7s`), **`12` human shots** (`53.9%`), **`5` perspectives**, **`100.0%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `5.03s` (`22` shots), `21` cuts + `0` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `96.91%`, max `2` lines, contrast `12.07:1`, median offset `0.037s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `855.2 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.65` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `25` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `3.83s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H2` (`9.03`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9533`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`True`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.008s`
- **Timeline Assembly & Subtitle Mux:** `98.371s`
- **Multi-Concept Thumbnail Studio:** `2.189s`
- **Total Master Render Time:** `100.864s` (`32.92 fps` effective)
