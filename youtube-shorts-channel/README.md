# Mind-Blowing Science — Autonomous YouTube Shorts Channel & Production Pipeline

A complete, rights-cleared, English-language YouTube Shorts production pipeline and 30-video catalog built around **[MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)** (`v1.3.9`).

---

## 1. Channel Concept & Specifications

- **Channel Theme:** Mind-Blowing Science (Space & the Universe, Everyday Science, Human Body & Brain)
- **Target Audience:** International English-speaking audience
- **Format:** Vertical faceless YouTube Shorts (`9:16`, `1080 × 1920`, `30 fps`, H.264/AAC MP4)
- **Target Duration:** 35–45 seconds per video (~90–93 spoken words)
- **Voiceover:** Microsoft Edge TTS `en-US-ChristopherNeural-Male` (free, natural documentary narration)
- **Subtitles:** High-contrast synchronized dynamic captions (`BeVietnamPro-Bold.ttf`, SIL Open Font License 1.1) with rounded dark translucent backing at vertical safe position `80.5%`
- **Visual Style:** 5 sequential `1080 × 1920` bespoke scientific diagram & motion scenes per video (`scene_01.mp4`–`scene_05.mp4`), custom-designed for each topic with quantitative metrics, labeled mechanisms, and verified institutional citations
- **Audio & Asset Rights:** 100% rights-cleared (`--bgm-type none` to avoid unverified bundled tracks in `MoneyPrinterTurbo/resource/songs/`; SIL OFL font; original custom-rendered scientific visuals)

---

## 2. Directory Structure

```text
youtube-shorts-channel/
├── README.md                          # Project overview, architecture & reproduction guide
├── scripts/                           # 30 original researched scripts (01..30) with 5-scene plans & sources
│   ├── 01-why-is-space-completely-silent.md
│   ├── ...
│   └── 30-why-do-dreams-feel-so-real.md
├── sources/
│   └── source-register.csv            # 60+ verified authoritative URLs (NASA, ESA, NOAA, USGS, NIH, etc.)
├── assets/
│   └── scenes/                        # 150 custom 1080x1920 PNG keyframes + 150 30fps MP4 scene clips
│       └── <slug>/scene_01..05.{png,mp4}
├── output/
│   ├── shorts/                        # All 30 rendered & ffprobe-validated 1080x1920 MP4 videos
│   │   ├── 01-why-is-space-completely-silent.mp4
│   │   ├── ...
│   │   └── 30-why-do-dreams-feel-so-real.mp4
│   └── subtitles/                     # Synchronized SRT subtitle files for all 30 videos
├── thumbnails/                        # 30 vertical 1080x1920 thumbnails (.png and .jpg)
├── metadata/
│   └── shorts-metadata.csv            # Titles, descriptions, tags, durations, codecs & source URLs
├── pipeline/
│   ├── generate_visuals.py            # Generates 5 scientific scenes (.png + .mp4) & thumbnails per script
│   ├── produce_videos.py              # Orchestrates MoneyPrinterTurbo CLI rendering & ffprobe validation
│   └── generate_metadata.py           # Compiles metadata/shorts-metadata.csv from scripts & rendered MP4s
├── logs/
│   ├── installation.log               # System, Python 3.11.17, uv 0.13.1, FFmpeg 9.0.2 & config log
│   └── generation.log                 # Timestamped MoneyPrinterTurbo CLI render & ffprobe audit log
└── reports/
    ├── pilot-quality-report.md        # Phase Five quality inspection of the 3 pilot videos
    ├── final-production-report.md     # Complete 30-video production summary, audit & policy checklist
    └── pilot_frames/                  # Extracted inspection frames from rendered MP4 videos
```

---

## 3. Reproducing or Extending the Pipeline

### Environment Prerequisites
- **Repository:** `/Applications/code/science-knowledge/MoneyPrinterTurbo`
- **Python Environment:** Python `3.11.17` managed via `uv` (`0.13.1`) at `/Applications/code/science-knowledge/MoneyPrinterTurbo/.venv`
- **Media Tools:** `/opt/homebrew/bin/ffmpeg` (`9.0.2` with `h264_videotoolbox`) and `/opt/homebrew/bin/ffprobe`

### Step 1 — Generate Scientific Visual Scenes & Thumbnails
```bash
/Applications/code/science-knowledge/MoneyPrinterTurbo/.venv/bin/python \
  /Applications/code/science-knowledge/youtube-shorts-channel/pipeline/generate_visuals.py \
  --workers 4
```

### Step 2 — Render YouTube Shorts MP4s via MoneyPrinterTurbo CLI
```bash
/Applications/code/science-knowledge/MoneyPrinterTurbo/.venv/bin/python \
  /Applications/code/science-knowledge/youtube-shorts-channel/pipeline/produce_videos.py \
  --workers 5
```

### Step 3 — Generate Channel Metadata Register
```bash
/Applications/code/science-knowledge/MoneyPrinterTurbo/.venv/bin/python \
  /Applications/code/science-knowledge/youtube-shorts-channel/pipeline/generate_metadata.py
```
