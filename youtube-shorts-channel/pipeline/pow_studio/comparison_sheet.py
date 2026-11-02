#!/usr/bin/env python3
"""
Side-by-Side Before-and-After Visual Regression Sheet Generator (`pow_studio.comparison_sheet`).

Extracts exact corresponding timestamps and thumbnails from a legacy MP4 vs. a refactored
`pow_documentary_v3` MP4 to provide clear, unedited visual proof of layout, overlay,
framing, moving-footage, and thumbnail improvements.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageDraw, ImageFont

_FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
FONT_BOLD = str(_FONTS_DIR / "BeVietnamPro-Bold.ttf")
FONT_MED = str(_FONTS_DIR / "BeVietnamPro-Medium.ttf")


def _grab_mp4_frame(mp4_path: Path, t_sec: float, size: tuple[int, int]) -> Image.Image:
    import io

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, t_sec):.3f}",
            "-i",
            str(mp4_path),
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "png",
            "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"Failed to grab frame from {mp4_path} at {t_sec:.2f}s")
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB").resize(size, Image.Resampling.LANCZOS)


def build_before_after_comparison_sheet(
    legacy_mp4: Path,
    legacy_thumb: Path,
    refactored_mp4: Path,
    refactored_thumb: Path,
    comparisons: Sequence[dict],
    out_jpg: Path,
    title: str = "PROOF OF WONDER WORKFLOW REFACTOR — BEFORE (LEGACY V2) vs. AFTER (DOCUMENTARY V3)",
) -> Path:
    """
    Build a high-resolution side-by-side comparison grid:
    - Column 0: Thumbnail comparison (Legacy busy card cover vs. Clean subject-first cover)
    - Columns 1..N: Exact corresponding story moments (`legacy_t`, `v3_t`, `heading`, `before_note`, `after_note`).
    """
    fw, fh = 246, 438
    pair_w = fw * 2 + 22
    n_cols = 1 + len(comparisons)
    cols_per_row = 3
    n_rows = (n_cols + cols_per_row - 1) // cols_per_row

    sheet_w = cols_per_row * (pair_w + 26) + 26
    row_h = fh + 132
    sheet_h = n_rows * row_h + 92

    sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 16, 24))
    d = ImageDraw.Draw(sheet)
    f_hdr = ImageFont.truetype(FONT_BOLD, 26)
    f_col = ImageFont.truetype(FONT_BOLD, 18)
    f_tag = ImageFont.truetype(FONT_BOLD, 14)
    f_note = ImageFont.truetype(FONT_MED, 13)

    d.text((26, 20), title, font=f_hdr, fill=(255, 255, 255))
    d.text(
        (26, 54),
        f"Left of each pair = Preserved Legacy Render ({legacy_mp4.name})   |   Right of each pair = Refactored Reusable Pipeline ({refactored_mp4.name})",
        font=f_note,
        fill=(182, 204, 228),
    )

    items = [
        {
            "is_thumb": True,
            "heading": "1. Mobile Cover / Thumbnail",
            "before_note": "BEFORE: Burned card box + kicker + heavy stroke",
            "after_note": "AFTER: Subject-first 9:16 + minimal clean type",
        }
    ] + [{"is_thumb": False, **c} for c in comparisons]

    for idx, item in enumerate(items):
        r, c = divmod(idx, cols_per_row)
        ox = 26 + c * (pair_w + 26)
        oy = 90 + r * row_h

        d.rounded_rectangle((ox - 8, oy - 6, ox + pair_w + 8, oy + fh + 114), radius=14, fill=(18, 24, 35), outline=(56, 76, 102), width=2)
        d.text((ox + 4, oy + 2), item["heading"], font=f_col, fill=(255, 226, 118))

        if item["is_thumb"]:
            im_before = Image.open(legacy_thumb).convert("RGB").resize((fw, fh), Image.Resampling.LANCZOS)
            im_after = Image.open(refactored_thumb).convert("RGB").resize((fw, fh), Image.Resampling.LANCZOS)
            lbl_b = "BEFORE (thumbnail.jpg)"
            lbl_a = "AFTER (thumbnail.jpg)"
        else:
            tb = float(item["legacy_t"])
            ta = float(item["v3_t"])
            im_before = _grab_mp4_frame(legacy_mp4, tb, (fw, fh))
            im_after = _grab_mp4_frame(refactored_mp4, ta, (fw, fh))
            lbl_b = f"BEFORE @ {tb:.1f}s"
            lbl_a = f"AFTER @ {ta:.1f}s"

        iy = oy + 32
        sheet.paste(im_before, (ox, iy))
        sheet.paste(im_after, (ox + fw + 22, iy))

        d.rectangle((ox - 1, iy - 1, ox + fw, iy + fh), outline=(218, 92, 76), width=2)
        d.rectangle((ox + fw + 21, iy - 1, ox + 2 * fw + 22, iy + fh), outline=(88, 214, 152), width=2)

        d.text((ox + 4, iy + fh + 6), lbl_b, font=f_tag, fill=(248, 148, 134))
        d.text((ox + fw + 26, iy + fh + 6), lbl_a, font=f_tag, fill=(134, 238, 182))
        d.text((ox + 4, iy + fh + 28), item["before_note"][:52], font=f_note, fill=(210, 188, 188))
        d.text((ox + 4, iy + fh + 48), item["after_note"][:58], font=f_note, fill=(188, 228, 206))

    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_jpg, format="JPEG", quality=93, subsampling=0)
    return out_jpg
