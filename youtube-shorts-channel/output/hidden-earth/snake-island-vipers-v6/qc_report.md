# Documentary Studio v6.0 Post-Render Quality Assurance Report — `snake-island-vipers-v6`

- **Production Profile:** `mysterious_earth_exploration`
- **Overall Studio v6 Pass:** **`PASS`** (`0` failed gates)
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/hidden-earth/snake-island-vipers-v6/snake-island-vipers-v6.mp4`
- **Duration:** `72.033 seconds` (`2161` exact frames @ `30/1` CFR; target `66–90s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.1 LUFS`, True Peak `-1.7 dBFS`, Speech Dominance `+9.9 LU`, LRA `1.5 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `66–90s`, `0` frame drift | **PASS** | `1080×1920`, `72.033s` (`2161` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `19/19` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`86.2%` moving video** (`62.1s`), **`2` human shots** (`7.4%`), **`8` perspectives**, **`95.4%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `3.79s` (`19` shots), `16` cuts + `2` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `99.49%`, max `2` lines, contrast `12.07:1`, median offset `0.024s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `841.1 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.33` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `18` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H1` (`9.35`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9302`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`True`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.007s`
- **Timeline Assembly & Subtitle Mux:** `75.405s`
- **Multi-Concept Thumbnail Studio:** `4.381s`
- **Total Master Render Time:** `79.964s` (`27.02 fps` effective)

## Shot-Planner Notes & Warnings

- [S02:queimada_grande_coast_itanhaem.jpg] Effective upscale factor (2.71x) exceeds crisp HD target (2.35x).
- [S14:pit_viper_strike_nature_srep.ogv] Effective upscale factor (2.78x) exceeds crisp HD target (2.35x).
