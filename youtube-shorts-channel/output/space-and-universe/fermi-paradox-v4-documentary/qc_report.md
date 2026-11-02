# Documentary Pipeline v4.0 Post-Render Quality Assurance Report — `fermi-paradox-v4-documentary`

- **Style Profile:** `pow_documentary_v3`
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/cosmic-mysteries/fermi-paradox-v4-documentary/fermi-paradox-v4-documentary.mp4`
- **Duration:** `82.900 seconds` (`2487` exact frames @ `30/1` CFR; target `62–88s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-15.9 LUFS`, True Peak `-2.2 dBFS`, Speech Dominance `+21.7 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `62–88s`, `0` frame drift | **PASS** | `1080×1920`, `82.900s` (`2487` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `19/19` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | `>= 80%` moving video goal (`<= 15%` photos); human interaction prioritized | **PASS** | **`88.0%` moving video** (`73.0s`), **`8` human-interaction shots** (`33.8%`), `5.2%` photos, **`93.2%` authentic** |
| **6. Pacing & Speech Alignment** | Deliberate shots + cuts/dissolves at speech boundaries | **PASS** | Mean `4.36s` (`19` shots), `16` cuts + `2` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `99.30%`, max `2` lines, contrast `12.07:1`, median offset `0.046s` |
| **8. Clean Subject-First Thumbnail** | `1080×1920`, `< 2 MB`, clean mobile shelf preview | **PASS** | `1743.6 KB` (`cinema_hook`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.23` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `20` commercial-safe assets; `3` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop `<= 0.55s`, audible nat-sound, boxless type | **PASS** | Motion @ `0.00s`, LLM clichés=`0`, tail=`0.24s`, nat-sound=`True` (`+21.7 LU`), subs=`cinema_boxless` |

## Shot-Planner Notes & Warnings

- [S05:eso_alma_control_room_5.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S08:eso_alma_control_room_10.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S09:eso_alma_control_room_1.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S13:eso_alma_control_room_3.m4v] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
