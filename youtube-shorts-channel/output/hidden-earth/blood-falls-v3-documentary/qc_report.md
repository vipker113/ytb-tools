# Documentary Pipeline v4.0 Post-Render Quality Assurance Report — `blood-falls-v3-documentary`

- **Style Profile:** `pow_documentary_v3`
- **Master File:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/hidden-earth/blood-falls-v3-documentary/blood-falls-v3-documentary.mp4`
- **Duration:** `72.767 seconds` (`2183` exact frames @ `30/1` CFR; target `68–90s`)
- **Video Stream:** `1080 × 1920` (`9:16`), `h264` (`High`, `yuv420p`, `bt709`)
- **Audio Stream:** `aac` stereo @ `48000 Hz`, Integrated `-15.9 LUFS`, True Peak `-2.5 dBFS`, Speech Dominance `+21.8 LU`
- **Black Frames (`blackdetect`):** `0` (`0` unintended black flashes)

---

## Automated Verification Matrix

| Gate | Requirement | Status | Measured Value |
|---|---|---|---|
| **1. Resolution, CFR & Duration** | `1080×1920` (`9:16`), `30/1` CFR, `68–90s`, `0` frame drift | **PASS** | `1080×1920`, `72.767s` (`2183` frames) |
| **2. Zero Black Frames** | `0` unintended black frames (`blackdetect`) | **PASS** | `0` black segments |
| **3. Full-Canvas 9:16 Coverage** | Edge-to-edge vertical fill (`0` letterbox bars, `0` inset frame borders) | **PASS** | `18/18` shots clean (`0` inset boxes) |
| **4. Overlay Cleanliness** | `0` circles/rings, `0` source banners, `0` HUDs, `0` burned-in title cards | **PASS** | Rings=`0`, SourceBanners=`0`, HUDs=`0`, CoverCard=`False` |
| **5. Moving Footage & Human Fieldwork** | `>= 80%` moving video goal (`<= 15%` photos); human interaction prioritized | **PASS** | **`86.3%` moving video** (`62.8s`), **`9` human-interaction shots** (`55.6%`), `8.8%` photos, **`95.1%` authentic** |
| **6. Pacing & Speech Alignment** | Deliberate shots + cuts/dissolves at speech boundaries | **PASS** | Mean `4.04s` (`18` shots), `13` cuts + `4` dissolves, `100.0%` pause-aligned |
| **7. Whisper Subtitle Sync & WCAG** | `>= 96%` normalized match, `<= 2` lines/cue, `>= 7.0:1` WCAG AAA | **PASS** | Match `97.66%`, max `2` lines, contrast `12.07:1`, median offset `0.053s` |
| **8. Clean Subject-First Thumbnail** | `1080×1920`, `< 2 MB`, clean mobile shelf preview | **PASS** | `1039.2 KB` (`minimal_headline`) |
| **9. Motion Smoothness** | Smooth camera reframing with zero mid-shot jump spikes | **PASS** | Worst frame-delta jump ratio `1.54` |
| **10. Rights & Existing Project Safety** | `0` NC/ND/SA assets + existing completed episodes preserved | **PASS** | `13` commercial-safe assets; `3` legacy episodes verified intact |
| **11. Viral Retention & Zero-AI-Smell** | Real motion `<= 2.3s`, `0` LLM clichés, seamless loop `<= 0.55s`, audible nat-sound, boxless type | **PASS** | Motion @ `2.20s`, LLM clichés=`0`, tail=`0.28s`, nat-sound=`True` (`+21.8 LU`), subs=`cinema_boxless` |

## Shot-Planner Notes & Warnings

- [S03:nasa_svs_3482_lima_flyover.mp4] Effective upscale factor (2.88x) exceeds crisp HD target (2.35x).
- [S04:wiki_zdf_ice_core_lab_720p.webm] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- [S07:nasa_svs_3482_lima_flyover.mp4] Effective upscale factor (2.88x) exceeds crisp HD target (2.35x).
- [S08:nasa_svs_11621_across_ross_720p.mov] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- [S09:nasa_m11707_mcmurdo_black_island.mp4] Effective upscale factor (3.07x) exceeds crisp HD target (2.35x).
- [S11:wiki_zdf_ice_core_lab_720p.webm] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- [S12:micro_diatom_seah.webm] Effective upscale factor (2.83x) exceeds crisp HD target (2.35x).
- [S14:nasa_svs_11621_across_ross_720p.mov] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- [S15:nasa_svs_10028_mcmurdo_oib_720p.mov] Effective upscale factor (2.80x) exceeds crisp HD target (2.35x).
- [N03] Sentence has 27 words (> 24): 'Deep under the ice sits a trapped reservoir of hyper-salty brine—likely ...'
- [N05] Sentence has 26 words (> 24): 'Testing 167 ice, sediment, air, and ocean samples across the region, a f...'
