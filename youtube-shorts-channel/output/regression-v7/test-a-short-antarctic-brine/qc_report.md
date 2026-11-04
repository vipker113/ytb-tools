# Documentary Studio v6.0 Post-Render Quality Assurance Report — `test-a-short-antarctic-brine`

- **Production Profile:** `scientific_investigation`
- **Overall Studio v6 Pass:** **`FAIL`** (`1` failed gates)
- **Master File:** `C:\Users\Admin\Desktop\code\science-knowledge\youtube-shorts-channel\output\regression-v7\test-a-short-antarctic-brine\test-a-short-antarctic-brine.mp4`
- **Duration:** `37.067 seconds` (`1112` exact frames @ `30/1` CFR; target `20–240s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-16.1 LUFS`, True Peak `-1.5 dBFS`, Speech Dominance `+26.4 LU`, LRA `1.6 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated 14-Gate Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `20–240s`, `0` frame drift | **PASS** | `1080×1920`, `37.067s` (`1112` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `5/5` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | Authentic footage prioritized; human fieldwork & camera variety | **PASS** | **`77.5%` moving video** (`28.7s`), **`2` human shots** (`48.1%`), **`3` perspectives**, **`100.0%` authentic** |
| **6. Pacing & Speech Alignment** | Adaptive shot durations + cuts/dissolves at speech boundaries | **WARN** | Mean `7.41s` (`5` shots), `4` cuts + `0` dissolves, `75.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `100.00%`, max `2` lines, contrast `12.07:1`, median offset `0.015s` |
| **8. Multi-Concept Thumbnail Studio** | `1080×1920`, `< 2 MB`, mobile comparison sheet (`160×284`) | **PASS** | `1265.4 KB` (`2` concepts, mobile sheet=`True`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.22` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **FAIL** | `4` commercial-safe assets; `11` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop, audible bed | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.42s`, subs=`scientific_plain` |
| **12. Narrative Momentum & Hook Promise** | `0` momentum errors, strong opening hook, promised payoff delivered | **PASS** | Errors=`0`, Warnings=`1`, Hook=`H01` (`9.06`) |
| **13. 7-Criterion Visual Relevance** | All shots pass relevance floor (`0` decorative irrelevant visuals) | **PASS** | Mean weighted score=`0.952`, Mismatches=`0` |
| **14. Voice Studio & 5-Layer Audio Health** | `0` clipped samples, `0` dead silences, natural LRA, 5 stems exported | **PASS** | Mode=`directed_tts` (`scientific_authority`), Lock=`False`, Stems=`5`, Clipped=`0`, Silences=`0` |

## Render & Production Benchmarks

- **Encode Mode:** `master`
- **Shots Render / Cache Pass:** `0.021s`
- **Timeline Assembly & Subtitle Mux:** `57.567s`
- **Multi-Concept Thumbnail Studio:** `4.024s`
- **Total Master Render Time:** `61.763s` (`18.0 fps` effective)

## Shot-Planner Notes & Warnings

- [S01:nasa_m12666_nansen_scientists_ice.mp4] Effective upscale factor (2.77x) exceeds crisp HD target (2.35x).
- [S07] Cut at 28.43s is 0.52s from nearest speech pause
- [S07:nasa_m12666_nansen_scientists_ice.mp4] Effective upscale factor (2.77x) exceeds crisp HD target (2.35x).
- Asset 'nasa_m12666_nansen_scientists_ice.mp4' occupies 48.1% of runtime (exceeds 30% cap).
