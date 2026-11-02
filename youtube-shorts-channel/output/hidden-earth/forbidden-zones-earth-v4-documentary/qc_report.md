# Documentary Pipeline v4.0 Post-Render Quality Assurance Report — `forbidden-zones-earth-v4-documentary`

- **Style Profile:** `pow_documentary_v3`
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/hidden-earth/forbidden-zones-earth-v4-documentary/forbidden-zones-earth-v4-documentary.mp4`
- **Duration:** `106.700 seconds` (`3201` exact frames @ `30/1` CFR; target `92–128s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-15.9 LUFS`, True Peak `-2.0 dBFS`, Speech Dominance `+21.1 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `92–128s`, `0` frame drift | **PASS** | `1080×1920`, `106.700s` (`3201` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `25/25` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | `>= 80%` moving video goal (`<= 15%` photos); human interaction prioritized | **PASS** | **`91.0%` moving video** (`97.1s`), **`8` human-interaction shots** (`38.4%`), `5.1%` photos, **`96.2%` authentic** |
| **6. Pacing & Speech Alignment** | Deliberate shots + cuts/dissolves at speech boundaries | **PASS** | Mean `4.27s` (`25` shots), `22` cuts + `2` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `99.63%`, max `2` lines, contrast `12.07:1`, median offset `0.07s` |
| **8. Clean Subject-First Thumbnail** | `1080×1920`, `< 2 MB`, clean mobile shelf preview | **PASS** | `946.5 KB` (`cinema_hook`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.72` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `19` commercial-safe assets; `3` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop `<= 0.55s`, audible nat-sound, boxless type | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.24s`, nat-sound=`True` (`+21.1 LU`), subs=`cinema_boxless` |

## Shot-Planner Notes & Warnings

- [S01:pripyat_vehicles_dosimeter_720p.mp4] Effective upscale factor (2.91x) exceeds crisp HD target (2.35x).
- [S03:chernobyl_arch_720p.mp4] Effective upscale factor (2.96x) exceeds crisp HD target (2.35x).
- [S05:chernobyl_red_forest_camp_720p.mp4] Effective upscale factor (2.91x) exceeds crisp HD target (2.35x).
- [S08:chernobyl_deer_forest_720p.mp4] Effective upscale factor (2.91x) exceeds crisp HD target (2.35x).
- [S24:chernobyl_red_forest_camp_720p.mp4] Effective upscale factor (2.91x) exceeds crisp HD target (2.35x).
