#!/usr/bin/env python3
"""
Milestone M6 Tests — Outlier Video Reference Analyst (`pow_studio.outlier_analyst`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image, ImageDraw

PIPELINE_DIR = Path(__file__).resolve().parent.parent
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from pow_studio.outlier_analyst import (  # noqa: E402
    MEDIA_EXTS,
    aggregate_outlier_patterns,
    analyze_outlier_video,
    classify_opening_hook,
    detect_cta_position,
    validate_video_id,
)


def _build_synthetic_4scene_mp4(dst_mp4: Path) -> Path:
    """Create an 8s 270x480@15fps MP4 with 4 distinct 2s visual scenes (and matching start/end for loop test)."""
    frames_dir = dst_mp4.parent / "_synth_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    fps = 15
    # 4 scenes x 2.0s = 120 frames (cuts at 2.0s, 4.0s, 6.0s -> 3 cuts, 4 scenes)
    for f_idx in range(120):
        t = f_idx / float(fps)
        if t < 2.0:
            im = Image.new("RGB", (270, 480), (20, 40, 95))
            d = ImageDraw.Draw(im)
            ox = int(30 + (f_idx % 30) * 6)
            d.ellipse((ox, 160, ox + 90, 250), fill=(250, 200, 60))
            d.rectangle((0, 360, 270, 480), fill=(40, 80, 160))
        elif t < 4.0:
            im = Image.new("RGB", (270, 480), (235, 240, 245))
            d = ImageDraw.Draw(im)
            for row_y in range(60, 420, 55):
                d.rectangle((24, row_y, 246, row_y + 32), outline=(25, 30, 40), width=3)
        elif t < 6.0:
            im = Image.new("RGB", (270, 480), (16, 85, 52))
            d = ImageDraw.Draw(im)
            oy = int(80 + ((f_idx - 60) % 30) * 8)
            d.rectangle((70, oy, 200, oy + 110), fill=(90, 245, 160))
        else:
            # Matches scene 1 layout closely to exercise loop similarity dHash
            im = Image.new("RGB", (270, 480), (20, 40, 95))
            d = ImageDraw.Draw(im)
            d.ellipse((36, 160, 126, 250), fill=(250, 200, 60))
            d.rectangle((0, 360, 270, 480), fill=(40, 80, 160))
        im.save(frames_dir / f"f_{f_idx:04d}.jpg", format="JPEG", quality=90)

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "f_%04d.jpg"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(dst_mp4),
        ],
        check=True,
    )
    return dst_mp4


def test_validate_video_id_strict_regex() -> None:
    assert validate_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert validate_video_id("A_1-b2C3d4E") == "A_1-b2C3d4E"
    for bad in ("", "short", "way_too_long_video_id_123", "../etc/pass", "abc;rm -rf", "https://youtu.be/dQw4w9WgXcQ"):
        with pytest.raises(ValueError):
            validate_video_id(bad)


def test_hook_and_cta_classifiers() -> None:
    q_words = [{"word": w, "start": i * 0.3, "end": (i + 1) * 0.3} for i, w in enumerate("Why does boiling water freeze faster?".split())]
    assert classify_opening_hook(q_words) == "question"

    n_words = [{"word": w, "start": i * 0.3, "end": (i + 1) * 0.3} for i, w in enumerate("360 degrees underwater at two miles deep".split())]
    assert classify_opening_hook(n_words) == "numeric_shock"

    cta_words = [
        {"word": "Amazing", "start": 10.0, "end": 10.4},
        {"word": "physics.", "start": 10.4, "end": 10.8},
        {"word": "Subscribe", "start": 28.5, "end": 29.0},
        {"word": "for", "start": 29.0, "end": 29.2},
        {"word": "more!", "start": 29.2, "end": 29.6},
    ]
    assert detect_cta_position(cta_words) == 28.5


def test_local_4scene_video_cut_detection_and_brief_generation(tmp_path: Path) -> None:
    mp4 = _build_synthetic_4scene_mp4(tmp_path / "synth_short.mp4")
    out_root = tmp_path / "outliers"

    brief = analyze_outlier_video(local_video_path=mp4, out_root=out_root)
    assert brief["scene_count"] == 4
    assert brief["cut_count"] == 3
    assert brief["hook_and_loop"]["loop_similarity_score"] is not None
    assert brief["hook_and_loop"]["loop_similarity_score"] >= 0.75

    ep_dir = out_root / brief["target_id"]
    assert (ep_dir / "outlier_anatomy_brief.json").exists()
    assert (ep_dir / "outlier_anatomy_brief.md").exists()
    assert (ep_dir / "contact_sheet.jpg").exists()


def test_youtube_download_mode_auto_deletes_temp_video_even_after_completion_or_failure(tmp_path: Path) -> None:
    synth_mp4 = _build_synthetic_4scene_mp4(tmp_path / "source.mp4")
    out_root = tmp_path / "outliers"
    vid = "AbCdEfGh123"

    def _fake_meta(video_id: str, timeout_s: int = 45):
        return {
            "video_id": video_id,
            "title": "Why Space Sounds Terrifying",
            "channel": "TestScienceChannel",
            "channel_id": "UC123",
            "uploader_id": "@testsci",
            "duration_s": 8.0,
            "view_count": 500000,
            "like_count": 25000,
            "comment_count": 400,
            "upload_date": "20260101",
            "tags": ["space"],
            "categories": ["Science"],
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        }

    created_temp_files: list[Path] = []

    def _fake_download(video_id: str, tmp_dir: Path, timeout_s: int = 120) -> Path:
        dst = tmp_dir / "outlier_media.mp4"
        dst.write_bytes(synth_mp4.read_bytes())
        created_temp_files.append(dst)
        return dst

    def _fake_transcript(video_id, video_path):
        words = [
            {"word": "Why", "start": 0.15, "end": 0.4},
            {"word": "is", "start": 0.4, "end": 0.6},
            {"word": "space", "start": 0.6, "end": 1.0},
            {"word": "loud?", "start": 1.0, "end": 1.4},
        ]
        return words, "Why is space loud?", "mock_transcript"

    with (
        patch("pow_studio.outlier_analyst.fetch_youtube_metadata", side_effect=_fake_meta),
        patch("pow_studio.outlier_analyst.download_temp_480p_video", side_effect=_fake_download),
        patch("pow_studio.outlier_analyst.fetch_transcript_words", side_effect=_fake_transcript),
    ):
        brief = analyze_outlier_video(video_id=vid, mode="download", keep_media=False, out_root=out_root)

    assert brief["media_deleted"] is True
    assert len(created_temp_files) == 1
    assert not created_temp_files[0].exists(), "Temporary downloaded MP4 must be deleted immediately!"
    leftover_media = [p for p in (out_root / vid).rglob("*") if p.is_file() and p.suffix.lower() in MEDIA_EXTS]
    assert leftover_media == []

    # Aggregate patterns across the generated competitor brief
    agg = aggregate_outlier_patterns(out_root=out_root)
    assert agg["competitor_outliers_count"] == 1
    assert agg["competitor_channels_count"] == 1
    assert (out_root / "outlier_patterns.json").exists()
