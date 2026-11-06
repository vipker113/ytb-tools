# Studio v9 Milestone M4 — Alpha Mechanism Overlay Benchmark & Verification

## 1. Architecture & Spike Verification
- **Engine:** `manim==0.22.1`, `manimpango==0.7.1`, `pycairo==1.29.2` in `youtube-shorts-channel/.venv` (`Python 3.11.17` on Apple Silicon).
- **Zero-LaTeX Typography:** Bundled `BeVietnamPro-Bold.ttf`, `BeVietnamPro-Medium.ttf`, and `Anton-Regular.ttf` registered directly via `manimpango.register_font` + Unicode scientific symbols (`°C`, `×`, `²`). No MacTeX (~5 GB) dependency required.
- **Transparent Codec:** `1080×1920 @ 30fps` `qtrle` (`argb` lossless RGBA), composited in `compositor.py` above `[0:v]` (`base_mp4`) and below `[o]` (`overlay_qtrle.mov` subtitles) without touching per-shot `.mp4` caches.
- **Trusted Templates (7):** `pressure_ripple`, `wave_frequency_scale`, `value_callout_gauge`, `flow_arrows`, `scale_bar_compare`, `trajectory_trace`, `label_leader`.

## 2. Perseus Remake Benchmark (`v6` vs `perseus-black-hole-sound-v9-overlay-test`)

| Metric | Studio v6 (`perseus-black-hole-sound-v6`) | Studio v9 (`perseus-black-hole-sound-v9-overlay-test`) | Delta / Acceptance |
|---|---|---|---|
| **Diagram Authoring LOC** | `193` lines (`pipeline/generate_perseus_sound_diagram.py`) | `34` YAML lines (`mechanism_overlays[]`) | **`17.6%` of v6 LOC** (`< 25%` target PASS) |
| **`Genuine Moving Footage`** | `80.23%` | **`86.88%`** | **`+6.65` pts** (PASS) |
| **`Sci-Viz / Infographic`** | `6.65%` (`S11` full-screen Pillow diagram) | **`0.00%`** (`S11` real 4K Chandra plasma + `27.7%`-alpha overlay) | **`-6.65` pts** |
| **Cold Manim Render (2 overlays)** | N/A | **`3.679s`** (`OV1_RIPPLE` + `OV2_57_OCTAVES`) | Subprocess isolated |
| **Warm SHA-256 Cache Hit** | N/A | **`0.000s`** (`cache_hits=2`) | Deterministic cache PASS |
| **Safe Zone (`y ∈ [215, 1380]` px)** | Manual pixel coordinates | `OV1`: `[276, 424, 804, 1044]`, `OV2`: `[104, 284, 976, 944]` | `0` CRITICAL/MAJOR QA issues |
| **Peak Alpha Area Ratio (`≤ 35%`)** | `100%` opaque diagram | `OV1`: `4.2%`, `OV2`: `27.7%` | Preserves `REAL_VIDEO_ESTABLISHING` |

## 3. Regression & Golden Render Verification
- **Unit & Live Graphics Suite:** `70 passed` (`pipeline/tests/test_studio_v9_mechanism_overlay.py` + full test suite).
- **Golden Render Equality (`perseus-black-hole-sound-v6`, `mechanism_overlays=[]`):** **`2119/2119` frames `framemd5` identical**.
