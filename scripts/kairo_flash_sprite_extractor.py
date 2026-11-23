#!/usr/bin/env python3
"""
Kairo Spark — Locked 2D Flash Sprite Extractor & MyInstants Clean SFX Fetcher
1. Builds locked Anti-AI 2D Flash prompts referencing `reference_flash_poses_props_locked.jpg`
2. Extracts transparent RGBA PNG sprites from white-background sheets (preserving interior white heads/papers)
3. Searches & downloads clean non-meme editorial SFX from MyInstants US
"""

import argparse
import os
import re
import subprocess
import urllib.parse
import urllib.request
import cv2
import numpy as np
from PIL import Image

FLASH_PACK_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack"
SFX_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/sfx"
LOCKED_SCENE_REF = os.path.join(FLASH_PACK_DIR, "reference_flash_scenes_locked.jpg")
LOCKED_SPRITE_REF = os.path.join(FLASH_PACK_DIR, "reference_flash_poses_props_locked.jpg")

LOCKED_FLASH_STYLE_PROMPT = (
    "Raw 2D Adobe Flash / Adobe Animate flat bucket-fill stickman illustration matching the reference image 1:1. "
    "CRITICAL RULES: (1) Pure crisp #FFFFFF white background/head, NO warm sepia or yellow AI filter; "
    "(2) The character's torso MUST be a SINGLE black ink stick line (|) with single-line black stick arms and legs, "
    "NO white shirt torso block; (3) ONLY two accessories on the stick figure: a flat red necktie hanging directly "
    "from the neck over the single black stick spine, and a small yellow sticky note (#FFE600) with a black '?' or '!' "
    "on the forehead of the pure white round circle head; (4) Uniform 4px black marker outline, flat matte colors, "
    "NO 3D shading, NO gradients, NO text labels or borders."
)


def extract_transparent_sprites(sheet_path: str, out_dir: str, prefix: str = "sprite") -> list[str]:
    """
    Uses OpenCV exterior flood-fill from image borders so the outer #FFFFFF background becomes
    100% transparent (alpha=0) while interior white inside the stickman's head/props stays solid white (alpha=255).
    Also auto-detects connected components to save individual cropped RGBA PNG sprites.
    """
    os.makedirs(out_dir, exist_ok=True)
    bgr = cv2.imread(sheet_path)
    if bgr is None:
        raise FileNotFoundError(f"Cannot read image: {sheet_path}")

    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    barrier = (gray < 232).astype(np.uint8)
    kernel = np.ones((3, 3), np.uint8)
    sealed = cv2.dilate(barrier, kernel, iterations=1)

    ff_mask = np.zeros((h + 2, w + 2), np.uint8)
    ff_copy = sealed.copy()
    for sx in range(0, w, max(1, w // 10)):
        if ff_copy[0, sx] == 0:
            cv2.floodFill(ff_copy, ff_mask, (sx, 0), 128)
        if ff_copy[h - 1, sx] == 0:
            cv2.floodFill(ff_copy, ff_mask, (sx, h - 1), 128)
    for sy in range(0, h, max(1, h // 10)):
        if ff_copy[sy, 0] == 0:
            cv2.floodFill(ff_copy, ff_mask, (0, sy), 128)
        if ff_copy[sy, w - 1] == 0:
            cv2.floodFill(ff_copy, ff_mask, (w - 1, sy), 128)

    ext_bg = (ff_copy == 128) & (gray >= 232)
    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    rgba[ext_bg, 3] = 0

    # Find individual sprites via connected components on non-transparent alpha
    fg_mask = (rgba[:, :, 3] > 0).astype(np.uint8)
    fg_closed = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(fg_closed)

    boxes = []
    for lbl in range(1, num_labels):
        x, y, bw, bh, area = stats[lbl]
        if area < 1500 or bw < 35 or bh < 35:
            continue
        boxes.append((y // (h // 3), x, y, bw, bh))

    boxes.sort(key=lambda b: (b[0], b[1]))
    saved = []
    for idx, (_, x, y, bw, bh) in enumerate(boxes, start=1):
        pad = 10
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(w, x + bw + pad), min(h, y + bh + pad)
        crop = rgba[y0:y1, x0:x1]
        out_path = os.path.join(out_dir, f"{prefix}_{idx:02d}.png")
        Image.fromarray(crop).save(out_path)
        saved.append(out_path)

    return saved


def fetch_myinstants_sfx(
    slug: str,
    query: str,
    out_dir: str = SFX_DIR,
    banned_words: tuple[str, ...] = (
        "patapim",
        "meme",
        "remix",
        "song",
        "tiktok",
        "anime",
        "fortnite",
        "spongebob",
        "earrape",
        "boosted",
        "scream",
        "rant",
    ),
) -> str | None:
    """
    Searches MyInstants US and downloads the first clean editorial foley MP3 whose title matches
    at least one keyword from `query` (avoiding off-topic tag matches and meme/music clips).
    Also updates `sfx_catalog.json`.
    """
    os.makedirs(out_dir, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
    url = f"https://www.myinstants.com/en/search/?name={urllib.parse.quote(query)}"
    html = (
        urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=10)
        .read()
        .decode("utf-8", errors="ignore")
    )
    blocks = re.findall(r'<div class="instant">.*?</div>\s*</div>', html, re.S)
    query_tokens = [
        w.lower()
        for w in re.findall(r"[a-zA-Z0-9]+", query)
        if w.lower() not in ("sound", "effect", "effects", "sfx", "mp3", "audio")
    ]

    for require_token_match in (True, False):
        for b in blocks:
            m_mp3 = re.search(r"play\('(/media/sounds/[^']+\.mp3)'", b)
            m_tit = re.search(r'class="instant-link[^"]*"[^>]*>([^<]+)</a>', b)
            if not (m_mp3 and m_tit):
                continue
            title = m_tit.group(1).strip()
            tl = title.lower()
            if any(bad in tl for bad in banned_words):
                continue
            if require_token_match and query_tokens and not any(tok in tl for tok in query_tokens):
                continue
            mp3_url = "https://www.myinstants.com" + m_mp3.group(1)
            out_mp3 = os.path.join(out_dir, f"{slug}.mp3")
            data = urllib.request.urlopen(urllib.request.Request(mp3_url, headers=headers), timeout=10).read()
            with open(out_mp3, "wb") as f:
                f.write(data)
            rebuild_sfx_catalog(out_dir)
            return out_mp3
    return None


def rebuild_sfx_catalog(out_dir: str = SFX_DIR) -> None:
    import json

    catalog = []
    for fname in sorted(os.listdir(out_dir)):
        if not fname.endswith(".mp3"):
            continue
        fpath = os.path.join(out_dir, fname)
        try:
            dur = float(
                subprocess.check_output(
                    [
                        "/opt/homebrew/bin/ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        fpath,
                    ]
                )
                .decode()
                .strip()
            )
        except Exception:
            dur = 0.0
        catalog.append(
            {
                "id": fname[:-4],
                "file": fname,
                "path": f"/kairo-stickman/sfx/{fname}",
                "durationSec": round(dur, 2),
            }
        )
    with open(os.path.join(out_dir, "sfx_catalog.json"), "w", encoding="utf-8") as f:
        json.dump({"count": len(catalog), "items": catalog}, f, indent=2, ensure_ascii=False)


def ensure_script_sfx(script_path: str, out_dir: str = SFX_DIR) -> list[str]:
    """
    Scans a script/storyboard file for `[SFX: slug]` or `[SFX: slug | search query]` annotations
    and automatically downloads any missing SFX from MyInstants US into `out_dir`.
    """
    with open(script_path, "r", encoding="utf-8") as f:
        text = f.read()
    tags = re.findall(r"\[SFX:\s*([a-zA-Z0-9_-]+)(?:\s*\|\s*([^\]]+))?\]", text)
    fetched = []
    for slug, custom_query in tags:
        target = os.path.join(out_dir, f"{slug}.mp3")
        if os.path.exists(target):
            continue
        q = (custom_query or slug.replace("_", " ")).strip()
        saved = fetch_myinstants_sfx(slug, q, out_dir=out_dir)
        if saved:
            fetched.append(saved)
    rebuild_sfx_catalog(out_dir)
    return fetched


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kairo Spark 2D Flash Sprite & SFX Tool")
    parser.add_argument("--extract", help="Path to white-background 2D Flash sprite sheet to slice into transparent PNGs")
    parser.add_argument("--out-dir", default=FLASH_PACK_DIR, help="Output directory for extracted sprites")
    parser.add_argument("--prefix", default="custom_sprite", help="Filename prefix for extracted sprites")
    parser.add_argument("--sfx-query", help="Search query on MyInstants for clean editorial SFX")
    parser.add_argument("--sfx-slug", default="custom_sfx", help="Output filename slug for downloaded SFX")
    parser.add_argument("--ensure-script-sfx", help="Path to script/storyboard file to auto-download any missing [SFX: slug | query] tags")
    parser.add_argument("--rebuild-catalog", action="store_true", help="Rebuild sfx_catalog.json")
    parser.add_argument("--print-prompt", action="store_true", help="Print the locked Anti-AI 2D Flash prompt")
    args = parser.parse_args()

    if args.print_prompt:
        print(LOCKED_FLASH_STYLE_PROMPT)
    if args.extract:
        files = extract_transparent_sprites(args.extract, args.out_dir, args.prefix)
        print(f"Extracted {len(files)} transparent PNG sprites into {args.out_dir}")
    if args.sfx_query:
        saved = fetch_myinstants_sfx(args.sfx_slug, args.sfx_query)
        print("Saved SFX:", saved)
    if args.ensure_script_sfx:
        new_files = ensure_script_sfx(args.ensure_script_sfx)
        print(f"Auto-downloaded {len(new_files)} new script SFX:", new_files)
    if args.rebuild_catalog:
        rebuild_sfx_catalog()
        print("Rebuilt sfx_catalog.json")
