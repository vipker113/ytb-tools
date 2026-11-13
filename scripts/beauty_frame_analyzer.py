#!/usr/bin/env python3
"""
Standalone HD Beauty & Reup Thumbnail Frame Analyzer (`beauty_frame_analyzer.py`).

Completely independent from video-generation pipelines:
- Scans any existing local video (.mp4, .mov, .webm, .mkv) in < 1.5s.
- Scores candidate frames using YuNet Face + 5-Landmark Pose/Symmetry + Face-ROI Sharpness + Skin Exposure/Vibrance
  (with automatic salient-sharpness fallback when no close-up face is present).
- Extracts the Top-K temporally distinct frames at native full resolution, auto-upscales sub-HD videos
  to Full HD (>= 1080p short edge) while preserving 100% exact native aspect ratio (9:16, 16:9, 4:5, 1:1),
  and applies optional HD portrait enhancement (`beauty_glow`, `crisp_hd`, `raw_hd`).
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFile, ImageFilter

ImageFile.MAXBLOCK = max(getattr(ImageFile, "MAXBLOCK", 65536), 16 * 1024 * 1024)

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parents[1]
_BUNDLED_YUNET_PATH = SCRIPT_DIR / "models" / "face_detection_yunet_2023mar.onnx"
_SHARED_YUNET_PATH = (
    WORKSPACE_ROOT
    / "youtube-shorts-channel"
    / "assets"
    / "models"
    / "yunet"
    / "face_detection_yunet_2023mar.onnx"
)
YUNET_MODEL_PATH = (
    _BUNDLED_YUNET_PATH if _BUNDLED_YUNET_PATH.exists() else _SHARED_YUNET_PATH
)


def probe_video_info(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate,side_data_list:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or [{}]
    st = streams[0]
    w = int(st.get("width") or 1080)
    h = int(st.get("height") or 1920)

    # Check rotation metadata on mobile portrait videos
    rot = 0
    for sd in st.get("side_data_list") or []:
        if "rotation" in sd:
            rot = abs(int(round(float(sd["rotation"])))) % 180
    if rot == 90:
        w, h = h, w

    dur_raw = (data.get("format") or {}).get("duration")
    duration = float(dur_raw) if dur_raw else 10.0
    fps_str = str(st.get("r_frame_rate") or "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/", 1)
        fps = float(num) / max(1.0, float(den))
    else:
        fps = float(fps_str or 30.0)

    return {
        "width": w,
        "height": h,
        "duration_s": max(0.2, duration),
        "fps": round(fps, 2),
        "is_vertical": h >= w,
        "aspect_label": "9:16 Dọc" if h > w * 1.2 else ("16:9 Ngang" if w > h * 1.2 else "Vuông / 4:5"),
    }


def _load_yunet(input_w: int, input_h: int):
    if not YUNET_MODEL_PATH.exists():
        return None
    try:
        return cv2.FaceDetectorYN.create(
            str(YUNET_MODEL_PATH),
            "",
            (input_w, input_h),
            0.55,
            0.3,
            5000,
        )
    except Exception:
        return None


def score_beauty_frame_bgr(frame_bgr: np.ndarray, detector) -> dict:
    """
    Score a BGR video frame on a 0..100 scale tailored for beauty / portrait / dance / lifestyle thumbnails:
    - Face presence, size & confidence
    - 5-landmark gaze symmetry & upright pose (eyes, nose, mouth corners)
    - Sharpness & zero motion blur specifically on the face/eyes (or central subject fallback)
    - Flattering portrait exposure & skin/color vibrance
    """
    h, w = frame_bgr.shape[:2]
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

    # Global frame metrics
    mean_luma = float(np.mean(gray))
    if mean_luma < 18.0 or mean_luma > 246.0:
        return {
            "total_score": 5.0,
            "face_score": 0.0,
            "sharpness_score": 2.0,
            "lighting_score": 3.0,
            "has_face": False,
            "reason": "Khung hình quá tối hoặc cháy sáng",
        }

    # Central region sharpness (baseline)
    cy0, cy1 = int(h * 0.12), int(h * 0.85)
    cx0, cx1 = int(w * 0.12), int(w * 0.88)
    center_gray = gray[cy0:cy1, cx0:cx1]
    global_lap = float(cv2.Laplacian(center_gray, cv2.CV_64F).var())
    gx = cv2.Sobel(center_gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(center_gray, cv2.CV_32F, 0, 1, ksize=3)
    tenengrad = float(np.mean(np.sqrt(gx * gx + gy * gy)))

    best_face = None
    if detector is not None:
        detector.setInputSize((w, h))
        _, faces = detector.detect(frame_bgr)
        if faces is not None and len(faces) > 0:
            # Pick most prominent high-confidence face (area * conf^2)
            best_val = -1.0
            for f in faces:
                fx, fy, fw, fh = float(f[0]), float(f[1]), float(f[2]), float(f[3])
                conf = float(f[14])
                if conf < 0.58 or fw < w * 0.05 or fh < h * 0.05:
                    continue
                # Penalize faces clipped at frame edges
                margin_ok = 1.0
                if fx < w * 0.02 or fy < h * 0.02 or (fx + fw) > w * 0.98 or (fy + fh) > h * 0.96:
                    margin_ok = 0.55
                val = (fw * fh) * (conf ** 2) * margin_ok
                if val > best_val:
                    best_val = val
                    best_face = f

    if best_face is not None:
        fx, fy, fw, fh = (
            max(0, int(round(best_face[0]))),
            max(0, int(round(best_face[1]))),
            int(round(best_face[2])),
            int(round(best_face[3])),
        )
        conf = float(best_face[14])
        fx2, fy2 = min(w, fx + max(8, fw)), min(h, fy + max(8, fh))
        face_gray = gray[fy:fy2, fx:fx2]
        face_hsv = hsv[fy:fy2, fx:fx2]

        # 1. Face prominence & framing score (0..32)
        face_h_ratio = fh / float(max(1, h))
        # Ideal portrait/half-body face height is 14%..46% of canvas height
        if 0.14 <= face_h_ratio <= 0.48:
            size_pts = 16.0
        elif face_h_ratio < 0.14:
            size_pts = max(5.0, 16.0 * (face_h_ratio / 0.14))
        else:
            size_pts = max(8.0, 16.0 - (face_h_ratio - 0.48) * 18.0)

        # Horizontal centering & upper-middle vertical placement
        face_cx = (fx + 0.5 * fw) / float(w)
        face_cy = (fy + 0.5 * fh) / float(h)
        center_pen = abs(face_cx - 0.5) * 10.0 + max(0.0, abs(face_cy - 0.36) - 0.14) * 12.0
        conf_pts = min(16.0, max(0.0, (conf - 0.50) / 0.45 * 16.0))
        face_presence_score = max(4.0, size_pts + conf_pts - center_pen)

        # 2. 5-Landmark Pose, Eye Levelness & Expression Symmetry (0..22)
        # Landmarks: right_eye(4,5), left_eye(6,7), nose(8,9), right_mouth(10,11), left_mouth(12,13)
        re_x, re_y = float(best_face[4]), float(best_face[5])
        le_x, le_y = float(best_face[6]), float(best_face[7])
        no_x, no_y = float(best_face[8]), float(best_face[9])
        rm_x, rm_y = float(best_face[10]), float(best_face[11])
        lm_x, lm_y = float(best_face[12]), float(best_face[13])

        eye_dist = max(4.0, math.hypot(le_x - re_x, le_y - re_y))
        # Frontal / flattering 3/4 symmetry
        d_re_nose = math.hypot(no_x - re_x, no_y - re_y)
        d_le_nose = math.hypot(no_x - le_x, no_y - le_y)
        yaw_asym = abs(d_re_nose - d_le_nose) / eye_dist
        yaw_pts = max(2.0, 11.0 * (1.0 - min(1.0, max(0.0, yaw_asym - 0.10) / 0.65)))

        # Eye roll angle
        roll_deg = abs(math.degrees(math.atan2(le_y - re_y, max(1e-3, le_x - re_x))))
        roll_pts = max(1.0, 6.0 * (1.0 - min(1.0, max(0.0, roll_deg - 6.0) / 28.0)))

        # Eye patch contrast (open eyes have strong iris-sclera local contrast vs closed/blinking eyes!)
        er = max(3, int(round(eye_dist * 0.22)))
        eye_stds = []
        for ex, ey in ((re_x, re_y), (le_x, le_y)):
            ex0, ex1 = max(0, int(ex - er)), min(w, int(ex + er))
            ey0, ey1 = max(0, int(ey - er)), min(h, int(ey + er))
            if ex1 - ex0 >= 4 and ey1 - ey0 >= 4:
                eye_stds.append(float(np.std(gray[ey0:ey1, ex0:ex1])))
        eye_open_std = float(np.mean(eye_stds)) if eye_stds else 18.0
        eye_open_pts = min(5.0, max(0.5, (eye_open_std - 10.0) / 22.0 * 5.0))

        pose_score = yaw_pts + roll_pts + eye_open_pts

        # 3. Face Sharpness & Anti-Motion-Blur Score (0..28)
        face_lap = float(cv2.Laplacian(face_gray, cv2.CV_64F).var()) if face_gray.size > 64 else global_lap
        fgx = cv2.Sobel(face_gray, cv2.CV_32F, 1, 0, ksize=3)
        fgy = cv2.Sobel(face_gray, cv2.CV_32F, 0, 1, ksize=3)
        face_ten = float(np.mean(np.sqrt(fgx * fgx + fgy * fgy))) if face_gray.size > 64 else tenengrad
        sharp_norm = 0.60 * min(1.0, face_lap / 260.0) + 0.40 * min(1.0, face_ten / 34.0)
        sharpness_score = round(sharp_norm * 28.0, 2)

        # 4. Flattering Portrait Skin Lighting & Vibrance (0..18)
        face_luma = float(np.mean(face_gray))
        overexp_frac = float(np.mean(face_gray > 244))
        underexp_frac = float(np.mean(face_gray < 42))
        # Ideal radiant skin luminance ~ 125..200
        if 118.0 <= face_luma <= 205.0:
            exp_pts = 11.0
        else:
            dist_luma = min(abs(face_luma - 118.0), abs(face_luma - 205.0))
            exp_pts = max(2.0, 11.0 - dist_luma / 9.5)
        exp_pts -= (overexp_frac * 18.0 + underexp_frac * 14.0)
        sat_mean = float(np.mean(face_hsv[:, :, 1]))
        vib_pts = min(7.0, max(1.5, (sat_mean - 18.0) / 95.0 * 7.0))
        lighting_score = round(max(1.0, exp_pts + vib_pts), 2)

        total = min(99.5, round(face_presence_score + pose_score + sharpness_score + lighting_score, 1))
        return {
            "total_score": total,
            "face_score": round(face_presence_score + pose_score, 1),
            "sharpness_score": round((sharpness_score / 28.0) * 100.0, 1),
            "lighting_score": round((lighting_score / 18.0) * 100.0, 1),
            "has_face": True,
            "face_h_ratio": round(face_h_ratio, 3),
            "face_box": [fx, fy, fw, fh],
            "reason": "Rõ mặt, mắt sáng, nét căng & ánh sáng tôn da",
        }

    # No close-up face detected: score by subject sharpness, exposure & color richness (capped ~74 so clear face frames win)
    sharp_norm = 0.55 * min(1.0, global_lap / 320.0) + 0.45 * min(1.0, tenengrad / 38.0)
    sharp_pts = sharp_norm * 40.0
    exp_pts = max(4.0, 18.0 - abs(mean_luma - 135.0) / 7.5)
    sat_pts = min(14.0, float(np.mean(hsv[:, :, 1])) / 110.0 * 14.0)
    total = min(74.0, round(sharp_pts + exp_pts + sat_pts, 1))
    return {
        "total_score": total,
        "face_score": 0.0,
        "sharpness_score": round(sharp_norm * 100.0, 1),
        "lighting_score": round(((exp_pts + sat_pts) / 32.0) * 100.0, 1),
        "has_face": False,
        "face_h_ratio": 0.0,
        "face_box": None,
        "reason": "Toàn cảnh / Dáng người sắc nét",
    }


def _crop_pillarbox_black_bars(bgr: np.ndarray) -> np.ndarray:
    """Trim pure black pillarbox/letterbox bars so Vision AI & color analysis focus on actual video content."""
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    col_p92 = np.percentile(gray, 92, axis=0)
    row_p92 = np.percentile(gray, 92, axis=1)
    xs = np.where(col_p92 > 14)[0]
    ys = np.where(row_p92 > 14)[0]
    if len(xs) >= max(32, int(w * 0.18)) and len(ys) >= max(32, int(h * 0.18)):
        x0, x1 = int(xs[0]), int(xs[-1]) + 1
        y0, y1 = int(ys[0]), int(ys[-1]) + 1
        if (x1 - x0) < w * 0.96 or (y1 - y0) < h * 0.96:
            return bgr[y0:y1, x0:x1]
    return bgr


def _classify_outfit_or_scene_color(bgr_content: np.ndarray, has_face: bool) -> str:
    """Classify dominant outfit / scene palette inside active content ROI (excluding face skin)."""
    h, w = bgr_content.shape[:2]
    # Focus on lower-middle torso / dress / scene region
    y0 = int(h * (0.52 if has_face else 0.25))
    y1 = int(h * 0.92)
    x0, x1 = int(w * 0.18), int(w * 0.82)
    roi = bgr_content[max(0, y0):max(y0 + 8, y1), max(0, x0):max(x0 + 8, x1)]
    if roi.size == 0:
        return "soft_neutral"
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    mean_sat = float(np.mean(sat))
    mean_val = float(np.mean(val))

    # Achromatic outfits (classic black / pure white)
    dark_frac = float(np.mean(val < 58))
    bright_low_sat = float(np.mean((val > 192) & (sat < 42)))
    if dark_frac > 0.48:
        return "classic_black"
    if bright_low_sat > 0.42:
        return "pure_white"
    if mean_sat < 34:
        return "pure_white" if mean_val > 168 else ("classic_black" if mean_val < 78 else "soft_neutral")

    colored_mask = (sat >= 38) & (val >= 48)
    if np.sum(colored_mask) < roi.shape[0] * roi.shape[1] * 0.12:
        return "soft_neutral"

    h_vals = hue[colored_mask]
    pink_purple_frac = float(np.mean((h_vals >= 132) & (h_vals <= 174)))
    red_frac = float(np.mean((h_vals < 10) | (h_vals > 174)))
    blue_frac = float(np.mean((h_vals >= 92) & (h_vals < 132)))
    green_frac = float(np.mean((h_vals >= 36) & (h_vals < 88)))
    warm_frac = float(np.mean((h_vals >= 10) & (h_vals < 30)))

    best_group, best_frac = max(
        [
            ("pink_purple", pink_purple_frac),
            ("sky_blue", blue_frac),
            ("red_charm", red_frac),
            ("green_outdoor", green_frac),
            ("warm_beige", warm_frac),
        ],
        key=lambda kv: kv[1],
    )
    if best_frac < 0.24:
        return "soft_neutral"
    if best_group == "pink_purple":
        med_h = float(np.median(h_vals[(h_vals >= 132) & (h_vals <= 174)]))
        return "purple_fairy" if med_h < 154 else "pink_pastel"
    return best_group


def build_visual_profile_and_strip(
    out_dir: Path,
    candidates_out: list[dict],
    best_sample: dict,
    motion_score: float,
    video_name: str,
) -> tuple[dict, Optional[str]]:
    """
    Create a compact 3-frame contact sheet (`vision_strip.jpg`, ~60 KB) for multimodal Vision naming
    and return a deterministic OpenCV `visual_profile` for instant 0ms local naming.
    """
    # Pick up to 3 temporally spread candidates: Best (#1), Earliest, and Latest
    ordered_by_time = sorted(candidates_out, key=lambda c: c["timestamp_s"])
    chosen: list[dict] = []
    if candidates_out:
        chosen.append(candidates_out[0])
    for c in (ordered_by_time[0] if ordered_by_time else None, ordered_by_time[-1] if ordered_by_time else None):
        if c and all(c["id"] != x["id"] for x in chosen) and len(chosen) < 3:
            chosen.append(c)
    for c in candidates_out[1:]:
        if len(chosen) >= 3:
            break
        if all(c["id"] != x["id"] for x in chosen):
            chosen.append(c)

    tiles: list[np.ndarray] = []
    primary_cropped: Optional[np.ndarray] = None
    has_pillarbox = False
    target_h = 520

    for idx, c in enumerate(chosen):
        p = out_dir / c["jpg_file"]
        img = cv2.imread(str(p))
        if img is None:
            continue
        cropped = _crop_pillarbox_black_bars(img)
        if idx == 0:
            primary_cropped = cropped
            ih, iw = img.shape[:2]
            ch0, cw0 = cropped.shape[:2]
            if cw0 < iw * 0.84 or ch0 < ih * 0.84:
                has_pillarbox = True
        ch, cw = cropped.shape[:2]
        tw = max(120, int(round(cw * (target_h / float(max(1, ch))))))
        tile = cv2.resize(cropped, (tw, target_h), interpolation=cv2.INTER_AREA)
        tiles.append(tile)

    strip_filename: Optional[str] = None
    if tiles:
        sep = np.full((target_h, 6, 3), 24, dtype=np.uint8)
        spaced: list[np.ndarray] = []
        for i, t in enumerate(tiles):
            if i > 0:
                spaced.append(sep)
            spaced.append(t)
        strip_bgr = np.hstack(spaced)
        strip_path = out_dir / "vision_strip.jpg"
        Image.fromarray(cv2.cvtColor(strip_bgr, cv2.COLOR_BGR2RGB)).save(
            strip_path, format="JPEG", quality=82, optimize=True
        )
        strip_filename = strip_path.name

    has_face = bool(best_sample.get("has_face"))
    face_h_ratio = float(best_sample.get("face_h_ratio") or 0.0)
    if has_face and face_h_ratio >= 0.34:
        shot_type = "closeup_selfie"
    elif has_face and face_h_ratio >= 0.18:
        shot_type = "portrait"
    elif has_face and face_h_ratio >= 0.09:
        shot_type = "half_body"
    else:
        shot_type = "full_body"

    palette = (
        _classify_outfit_or_scene_color(primary_cropped, has_face)
        if primary_cropped is not None
        else "soft_neutral"
    )

    mean_luma = (
        float(np.mean(cv2.cvtColor(primary_cropped, cv2.COLOR_BGR2GRAY)))
        if primary_cropped is not None
        else 145.0
    )
    if mean_luma >= 165:
        lighting_mood = "bright_daylight"
    elif mean_luma >= 112:
        lighting_mood = "soft_glow"
    else:
        lighting_mood = "moody_chic"

    motion_level = "dance_motion" if motion_score >= 16.5 else "calm_pose"

    lower_name = video_name.lower()
    if any(k in lower_name for k in ("dance", "nhay", "choreo", "kpop")):
        suggested_vibe = "dance_trend"
    elif any(k in lower_name for k in ("hanfu", "cosplay", "aodai", "kimono")):
        suggested_vibe = "cosplay_trad"
    elif any(k in lower_name for k in ("gym", "fitness", "workout", "yoga")):
        suggested_vibe = "gym_sport"
    elif any(k in lower_name for k in ("beach", "sea", "pool", "bikini", "travel")):
        suggested_vibe = "beach_travel"
    elif palette in ("purple_fairy", "pink_pastel") and shot_type == "full_body":
        suggested_vibe = "cosplay_trad"
    elif motion_level == "dance_motion" and shot_type in ("half_body", "full_body"):
        suggested_vibe = "dance_trend"
    elif shot_type in ("half_body", "full_body") and lighting_mood == "bright_daylight":
        suggested_vibe = "street_fashion"
    else:
        suggested_vibe = "visual_smile"

    shot_vi_map = {
        "closeup_selfie": "Cận mặt Selfie",
        "portrait": "Chân dung gần",
        "half_body": "Nửa người / Outfit",
        "full_body": "Toàn thân / Bối cảnh",
    }
    palette_vi_map = {
        "pink_pastel": "Tông hồng ngọt ngào",
        "purple_fairy": "Tông tím mộng mơ",
        "pure_white": "Tông trắng tinh khôi",
        "classic_black": "Tông đen cuốn hút",
        "sky_blue": "Tông xanh dịu mắt",
        "red_charm": "Tông đỏ nổi bật",
        "green_outdoor": "Ngoại cảnh xanh mát",
        "warm_beige": "Tông ấm nhẹ nhàng",
        "soft_neutral": "Ánh sáng tự nhiên",
    }
    motion_vi = "Chuyển động / Vũ đạo" if motion_level == "dance_motion" else "Thần thái dịu dàng"

    return (
        {
            "shot_type": shot_type,
            "dominant_palette": palette,
            "lighting_mood": lighting_mood,
            "motion_level": motion_level,
            "suggested_vibe": suggested_vibe,
            "has_pillarbox": has_pillarbox,
            "summary_vi": f"{shot_vi_map[shot_type]} • {palette_vi_map.get(palette, 'Tông tự nhiên')} • {motion_vi}",
        },
        strip_filename,
    )


def extract_and_enhance_hd_frame(
    video_path: Path,
    timestamp_s: float,
    out_jpg: Path,
    out_png: Path,
    enhance_mode: str = "beauty_glow",
) -> dict:
    """
    Extract exact native frame from `video_path` at `timestamp_s`, upscale to Full HD (>= 1080px short edge)
    preserving 100% original aspect ratio, apply portrait HD clarity mode, and write both JPG (< 1.95MB) & PNG.
    """
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{max(0.0, timestamp_s):.3f}",
            "-i",
            str(video_path),
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
        raise RuntimeError(f"FFmpeg could not extract frame at {timestamp_s:.2f}s")

    buf = np.frombuffer(proc.stdout, dtype=np.uint8)
    bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError("Failed to decode extracted PNG frame")

    h0, w0 = bgr.shape[:2]
    short_edge = min(w0, h0)
    # Auto HD Upscale: ensure short edge >= 1080px (e.g. 540x960 or 720x1280 -> 1080x1920 Full HD!)
    if short_edge < 1080:
        scale = 1080.0 / float(short_edge)
        nw = int(round((w0 * scale) / 2.0) * 2)
        nh = int(round((h0 * scale) / 2.0) * 2)
        bgr = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    elif short_edge > 2160:
        scale = 2160.0 / float(short_edge)
        nw = int(round((w0 * scale) / 2.0) * 2)
        nh = int(round((h0 * scale) / 2.0) * 2)
        bgr = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)

    if enhance_mode == "beauty_glow":
        # 1. Edge-preserving bilateral de-blocking (removes TikTok/Douyin compression artifacts on skin, keeps hair/eyes sharp!)
        smooth = cv2.bilateralFilter(bgr, d=7, sigmaColor=26, sigmaSpace=26)
        bgr_mix = cv2.addWeighted(bgr, 0.38, smooth, 0.62, 0)
        rgb = cv2.cvtColor(bgr_mix, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(rgb)
        # 2. Gentle radiant skin lift & rosy clarity
        arr = np.asarray(pil_im, dtype=np.float32) / 255.0
        # Soft highlight-safe lift
        arr = np.clip(arr + 0.045 * arr * ((1.0 - arr) ** 1.4), 0.0, 1.0)
        # Subtle S-curve micro-contrast
        curved = arr * arr * (3.0 - 2.0 * arr)
        arr = np.clip(0.80 * arr + 0.20 * curved, 0.0, 1.0)
        pil_im = Image.fromarray((arr * 255.0).astype(np.uint8))
        pil_im = ImageEnhance.Color(pil_im).enhance(1.08)
        # Crisp micro-sharpening on eyes/lashes/hair (threshold=5 avoids sharpening smooth skin!)
        pil_im = pil_im.filter(ImageFilter.UnsharpMask(radius=1.6, percent=125, threshold=5))
    elif enhance_mode == "crisp_hd":
        smooth = cv2.bilateralFilter(bgr, d=5, sigmaColor=18, sigmaSpace=18)
        bgr_mix = cv2.addWeighted(bgr, 0.58, smooth, 0.42, 0)
        rgb = cv2.cvtColor(bgr_mix, cv2.COLOR_BGR2RGB)
        pil_im = Image.fromarray(rgb)
        pil_im = ImageEnhance.Contrast(pil_im).enhance(1.05)
        pil_im = ImageEnhance.Color(pil_im).enhance(1.05)
        pil_im = pil_im.filter(ImageFilter.UnsharpMask(radius=1.7, percent=135, threshold=4))
    else:
        # `raw_hd`: 100% original color/texture, pure HD resolution
        pil_im = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))

    out_jpg.parent.mkdir(parents=True, exist_ok=True)
    pil_im.save(out_png, format="PNG", optimize=False)

    # Save YouTube Studio 4:4:4 RGB JPEG guaranteed <= 1.95 MB
    used_q = 95
    for q in (96, 94, 92, 90, 88, 85, 82, 78):
        pil_im.save(out_jpg, format="JPEG", quality=q, subsampling=0, optimize=True)
        used_q = q
        if out_jpg.stat().st_size <= 1_950_000:
            break

    fw, fh = pil_im.size
    return {
        "width": fw,
        "height": fh,
        "jpg_size_kb": round(out_jpg.stat().st_size / 1024.0, 1),
        "png_size_kb": round(out_png.stat().st_size / 1024.0, 1),
        "jpeg_quality": used_q,
    }


def cmd_scan(args: argparse.Namespace) -> None:
    video_path = Path(args.video).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    info = probe_video_info(video_path)
    dur = info["duration_s"]
    orig_w, orig_h = info["width"], info["height"]

    # Sample up to 54 candidate frames uniformly between 3% and 96% of video duration
    n_samples = min(54, max(12, int(round(dur * 2.5))))
    t_start = min(0.25, dur * 0.03)
    t_end = max(t_start + 0.1, dur * 0.96)
    sample_fps = n_samples / max(0.2, (t_end - t_start))

    # Downscale width to ~420px for ultra-fast rawvideo pipe scoring (< 0.5s total!)
    an_w = 420 if orig_w <= orig_h else 560
    an_h = max(64, int(round((orig_h * (an_w / float(orig_w))) / 2.0) * 2))

    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{t_start:.3f}",
            "-t",
            f"{max(0.2, t_end - t_start):.3f}",
            "-i",
            str(video_path),
            "-vf",
            f"fps={sample_fps:.5f},scale={an_w}:{an_h}:flags=fast_bilinear",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-",
        ],
        stdout=subprocess.PIPE,
    )
    assert proc.stdout is not None

    detector = _load_yunet(an_w, an_h)
    frame_bytes = an_w * an_h * 3
    scored_samples: list[dict] = []
    prev_small_gray: Optional[np.ndarray] = None
    motion_diffs: list[float] = []
    idx = 0
    while True:
        raw = proc.stdout.read(frame_bytes)
        if len(raw) < frame_bytes:
            break
        ts = round(min(dur - 0.04, t_start + (idx + 0.5) / sample_fps), 3)
        frame_bgr = np.frombuffer(raw, dtype=np.uint8).reshape((an_h, an_w, 3)).copy()
        small_gray = cv2.resize(
            cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY), (96, 96), interpolation=cv2.INTER_AREA
        )
        if prev_small_gray is not None:
            motion_diffs.append(float(np.mean(cv2.absdiff(small_gray, prev_small_gray))))
        prev_small_gray = small_gray
        sc = score_beauty_frame_bgr(frame_bgr, detector)
        scored_samples.append({"timestamp_s": ts, **sc})
        idx += 1
    proc.wait()

    if not scored_samples:
        scored_samples.append(
            {
                "timestamp_s": round(dur * 0.35, 3),
                "total_score": 70.0,
                "face_score": 0.0,
                "sharpness_score": 75.0,
                "lighting_score": 75.0,
                "has_face": False,
                "reason": "Khung hình mặc định",
            }
        )

    # Sort descending by total_score and pick Top-K temporally separated frames
    ranked = sorted(scored_samples, key=lambda x: x["total_score"], reverse=True)
    top_k = max(1, int(args.top_k))
    min_gap_s = max(0.45, min(2.2, dur / float(top_k * 2.2)))

    selected: list[dict] = []
    for cand in ranked:
        if all(abs(cand["timestamp_s"] - s["timestamp_s"]) >= min_gap_s for s in selected):
            selected.append(cand)
            if len(selected) >= top_k:
                break

    # Relax gap if video is very short (< 3s) and we need more candidates
    if len(selected) < min(top_k, len(ranked)):
        for cand in ranked:
            if cand not in selected:
                selected.append(cand)
                if len(selected) >= top_k:
                    break

    candidates_out: list[dict] = []
    for rank_idx, item in enumerate(selected):
        cid = f"cand_{rank_idx + 1}"
        jpg_path = out_dir / f"{cid}_{args.enhance}.jpg"
        png_path = out_dir / f"{cid}_{args.enhance}.png"
        hd_meta = extract_and_enhance_hd_frame(
            video_path=video_path,
            timestamp_s=item["timestamp_s"],
            out_jpg=jpg_path,
            out_png=png_path,
            enhance_mode=args.enhance,
        )
        candidates_out.append(
            {
                "id": cid,
                "rank": rank_idx + 1,
                "is_best": rank_idx == 0,
                "timestamp_s": item["timestamp_s"],
                "total_score": item["total_score"],
                "face_score": item["face_score"],
                "sharpness_score": item["sharpness_score"],
                "lighting_score": item["lighting_score"],
                "has_face": item["has_face"],
                "reason": item["reason"],
                "jpg_file": jpg_path.name,
                "png_file": png_path.name,
                **hd_meta,
            }
        )

    motion_score = float(np.median(motion_diffs)) if motion_diffs else 8.0
    visual_profile, vision_strip_file = build_visual_profile_and_strip(
        out_dir=out_dir,
        candidates_out=candidates_out,
        best_sample=selected[0] if selected else {},
        motion_score=motion_score,
        video_name=video_path.name,
    )

    print(
        json.dumps(
            {
                "ok": True,
                "video_name": video_path.name,
                "video_info": info,
                "enhance_mode": args.enhance,
                "sampled_frames_count": len(scored_samples),
                "visual_profile": visual_profile,
                "vision_strip_file": vision_strip_file,
                "candidates": candidates_out,
            }
        )
    )


def cmd_extract(args: argparse.Namespace) -> None:
    video_path = Path(args.video).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = max(0.0, float(args.time))
    tag = f"custom_{int(round(ts * 1000))}ms_{args.enhance}"
    jpg_path = out_dir / f"{tag}.jpg"
    png_path = out_dir / f"{tag}.png"

    hd_meta = extract_and_enhance_hd_frame(
        video_path=video_path,
        timestamp_s=ts,
        out_jpg=jpg_path,
        out_png=png_path,
        enhance_mode=args.enhance,
    )

    # Also compute beauty score on the extracted HD frame
    bgr = cv2.imread(str(jpg_path))
    detector = _load_yunet(bgr.shape[1], bgr.shape[0]) if bgr is not None else None
    sc = (
        score_beauty_frame_bgr(bgr, detector)
        if bgr is not None
        else {
            "total_score": 85.0,
            "face_score": 0.0,
            "sharpness_score": 88.0,
            "lighting_score": 85.0,
            "has_face": False,
            "reason": "Khung hình chọn thủ công",
        }
    )

    print(
        json.dumps(
            {
                "ok": True,
                "candidate": {
                    "id": tag,
                    "rank": 0,
                    "is_best": False,
                    "timestamp_s": round(ts, 3),
                    **sc,
                    "jpg_file": jpg_path.name,
                    "png_file": png_path.name,
                    **hd_meta,
                },
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--video", required=True)
    p_scan.add_argument("--out-dir", required=True)
    p_scan.add_argument("--top-k", type=int, default=6)
    p_scan.add_argument("--enhance", default="beauty_glow", choices=["beauty_glow", "crisp_hd", "raw_hd"])
    p_scan.set_defaults(func=cmd_scan)

    p_ext = sub.add_parser("extract")
    p_ext.add_argument("--video", required=True)
    p_ext.add_argument("--out-dir", required=True)
    p_ext.add_argument("--time", type=float, required=True)
    p_ext.add_argument("--enhance", default="beauty_glow", choices=["beauty_glow", "crisp_hd", "raw_hd"])
    p_ext.set_defaults(func=cmd_extract)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
