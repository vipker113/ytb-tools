# Documentary Studio v6.0 Post-Render Quality Assurance Report — `perseus-black-hole-sound-v6`

- **Production Profile:** `space_discovery`
- **Overall Studio v6 Pass:** **`PASS`** (`0` failed gates)
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/space-and-universe/perseus-black-hole-sound-v6/perseus-black-hole-sound-v6.mp4`
- **Duration:** `70.633 seconds` (`2119` exact frames @ `30/1` CFR; target `66–90s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.0 LUFS`, True Peak `-1.4 dBFS`, Speech Dominance `+10.0 LU`, LRA `1.9 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `66–90s`, `0` frame drift | **PASS** | `1080×1920`, `70.633s` (`2119` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `18/18` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`81.3%` moving video** (`57.4s`), **`2` human shots** (`11.3%`), **`9` perspectives**, **`93.5%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **PASS** | Mean `3.92s` (`18` shots), `15` cuts + `2` dissolves, `82.4%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `100.00%`, max `2` lines, contrast `12.07:1`, median offset `0.034s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `888.4 KB` (`3` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.57` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `15` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.34s`, subs=`cinema_boxless` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`0`, Hook=`H2` (`9.28`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.9351`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`mysterious_discovery`), Lock=`True`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.007s`
- **Timeline Assembly & Subtitle Mux:** `59.051s`
- **Multi-Concept Thumbnail Studio:** `3.078s`
- **Total Master Render Time:** `62.274s` (`34.03 fps` effective)

## Shot-Planner Notes & Warnings

- [S05:eso_alma_control_room_10.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S06] Cut at 21.67s is 3.28s from nearest speech pause
- [S13:eso_alma_control_room_1.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S14] Cut at 51.27s is 2.09s from nearest speech pause
- [S15] Cut at 56.37s is 0.71s from nearest speech pause
- Asset 'perseus_sonification_chandra_1080p.mp4' used 3 times (exceeds max_uses_per_asset=2).
