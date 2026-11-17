#!/usr/bin/env python3
"""
AI Video Super-Resolution, Face Restoration & Pro Mastering Engine (`ai_video_enhancer.py`).

Modes:
  1. `probe`   — Inspects video metadata, detects black pillarbox/letterbox bars, finds best face/sharp
                 timestamp, and extracts an initial reference preview frame.
  2. `preview` — Generates pixel-aligned Before & After comparison frames (+ auto face/detail zoom focus)
                 at any timestamp in < 1s so users can tune settings interactively before full render.
  3. `render`  — Enhances the entire video with live JSON progress updates (`--progress-file`), supporting:
                 - `ai_realesrgan`: Official Real-ESRGAN v3 (`SRVGGNetCompact` x4 + WDN DNI) running in FP16
                   on Apple Silicon MPS GPU + YuNet Landmark-Guided Full-Res Face & Eye Restoration.
                 - `ffmpeg_pro`: Ultra-fast broadcast deblock + 3D denoise + Lanczos + CAS + VideoToolbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

import cv2
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
MODELS_DIR = SCRIPT_DIR / "models"

REALESR_URLS = {
    "realesr-general-x4v3.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
    "realesr-general-wdn-x4v3.pth": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
}
YUNET_PATH = MODELS_DIR / "face_detection_yunet_2023mar.onnx"


def write_progress(progress_file: Optional[Path], payload: dict) -> None:
    if not progress_file:
        return
    try:
        tmp = progress_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(progress_file)
    except Exception:
        pass


def ensure_realesrgan_weights() -> tuple[Path, Path]:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for fname, url in REALESR_URLS.items():
        fpath = MODELS_DIR / fname
        if not fpath.exists() or fpath.stat().st_size < 1_000_000:
            tmp = fpath.with_suffix(".part")
            urllib.request.urlretrieve(url, str(tmp))
            tmp.replace(fpath)
        paths.append(fpath)
    return paths[0], paths[1]


def has_videotoolbox() -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return "h264_videotoolbox" in (proc.stdout or "")


def probe_media(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate,side_data_list:format=duration,bit_rate,size",
        "-of",
        "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    w = int(v_stream.get("width") or 1080)
    h = int(v_stream.get("height") or 1920)
    rot = 0
    for sd in v_stream.get("side_data_list") or []:
        if "rotation" in sd:
            rot = abs(int(round(float(sd["rotation"])))) % 180
    if rot == 90:
        w, h = h, w

    fmt = data.get("format") or {}
    dur_raw = fmt.get("duration")
    duration_s = max(0.2, float(dur_raw) if dur_raw else 10.0)

    fps_str = str(v_stream.get("r_frame_rate") or "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/", 1)
        fps = float(num) / max(1.0, float(den))
    else:
        fps = float(fps_str or 30.0)
    fps = min(60.0, max(12.0, round(fps, 2)))

    br_raw = v_stream.get("bit_rate") or fmt.get("bit_rate") or 0
    bitrate_kbps = int(round(float(br_raw) / 1000.0)) if br_raw else 0
    size_mb = round(float(fmt.get("size") or video_path.stat().st_size) / (1024.0 * 1024.0), 2)

    return {
        "width": w,
        "height": h,
        "duration_s": round(duration_s, 3),
        "fps": fps,
        "total_frames": max(1, int(round(duration_s * fps))),
        "codec": str(v_stream.get("codec_name") or "h264"),
        "bitrate_kbps": bitrate_kbps,
        "size_mb": size_mb,
        "has_audio": has_audio,
    }


def detect_active_content_box(
    video_path: Path, orig_w: int, orig_h: int, duration_s: float
) -> Optional[tuple[int, int, int, int]]:
    """
    Samples up to 6 frames across the video to safely find pure black pillarbox/letterbox bars.
    Returns `(crop_w, crop_h, x0, y0)` or `None` if no bars.
    """
    an_w = 480
    an_h = max(64, int(round((orig_h * (an_w / float(orig_w))) / 2.0) * 2))
    sample_fps = min(4.0, 6.0 / max(0.5, duration_s * 0.85))
    t_ss = min(0.2, duration_s * 0.05)

    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{t_ss:.3f}",
            "-t",
            f"{max(0.3, duration_s * 0.9):.3f}",
            "-i",
            str(video_path),
            "-vf",
            f"fps={sample_fps:.4f},scale={an_w}:{an_h}:flags=fast_bilinear",
            "-frames:v",
            "6",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        capture_output=True,
    )
    frame_bytes = an_w * an_h
    if proc.returncode != 0 or len(proc.stdout) < frame_bytes:
        return None

    n_frames = len(proc.stdout) // frame_bytes
    stack = np.frombuffer(proc.stdout[: n_frames * frame_bytes], dtype=np.uint8).reshape(
        (n_frames, an_h, an_w)
    )
    max_proj = np.percentile(stack, 96, axis=0)

    col_p94 = np.percentile(max_proj, 94, axis=0)
    row_p94 = np.percentile(max_proj, 94, axis=1)
    xs = np.where(col_p94 > 15)[0]
    ys = np.where(row_p94 > 15)[0]
    if len(xs) < an_w * 0.18 or len(ys) < an_h * 0.18:
        return None

    sx = orig_w / float(an_w)
    sy = orig_h / float(an_h)
    x0 = max(0, int(round(xs[0] * sx)) - 2)
    x1 = min(orig_w, int(round((xs[-1] + 1) * sx)) + 2)
    y0 = max(0, int(round(ys[0] * sy)) - 2)
    y1 = min(orig_h, int(round((ys[-1] + 1) * sy)) + 2)

    cw = (x1 - x0) // 2 * 2
    ch = (y1 - y0) // 2 * 2
    x0 = x0 // 2 * 2
    y0 = y0 // 2 * 2

    if cw < orig_w * 0.93 or ch < orig_h * 0.93:
        # Snap vertical pillarboxed clip cleanly to 9:16 if very close
        ratio = cw / float(max(1, ch))
        target_916 = 9.0 / 16.0
        if 0.48 <= ratio <= 0.66 and ch >= orig_h * 0.85:
            ideal_w = min(orig_w, int(round(ch * target_916)) // 2 * 2)
            cx = x0 + cw // 2
            nx0 = max(0, min(orig_w - ideal_w, (cx - ideal_w // 2) // 2 * 2))
            cw, x0 = ideal_w, nx0
        return (cw, ch, x0, y0)
    return None


def get_shorts_canvas_dims(target_res: str) -> tuple[int, int, int]:
    shorts_map = {
        "1080p": (1080, 1920, 18),
        "2k": (1440, 2560, 28),
        "4k": (2160, 3840, 42),
    }
    return shorts_map.get(target_res, (1080, 1920, 18))


def compute_target_dimensions(
    work_w: int,
    work_h: int,
    target_res: str,
    aspect_mode: str = "shorts_fill",
) -> tuple[int, int, int]:
    """
    Returns `(target_w, target_h, target_bitrate_mbps)` with even dimensions.
    When `aspect_mode` is `'shorts_fill'` or `'shorts_blur'`, strictly locks output to
    9:16 YouTube Shorts (`1080x1920`, `1440x2560`, or `2160x3840`).
    """
    if aspect_mode in ("shorts_fill", "shorts_blur"):
        return get_shorts_canvas_dims(target_res)

    short_map = {
        "1080p": (1080, 18),
        "2k": (1440, 28),
        "4k": (2160, 42),
    }
    target_short, bitrate_mbps = short_map.get(target_res, (1080, 18))
    cur_short = max(2, min(work_w, work_h))
    scale = float(target_short) / float(cur_short)
    tw = max(2, int(round((work_w * scale) / 2.0) * 2))
    th = max(2, int(round((work_h * scale) / 2.0) * 2))

    # Clean standard snap (1080x1920, 1440x2560, 2160x3840 and landscape counterparts)
    for std_s, std_l in [(1080, 1920), (1440, 2560), (2160, 3840)]:
        if abs(tw - std_s) <= 6 and abs(th - std_l) <= 10:
            tw, th = std_s, std_l
        elif abs(tw - std_l) <= 10 and abs(th - std_s) <= 6:
            tw, th = std_l, std_s

    return tw, th, bitrate_mbps


def compute_smart_9_16_crop_box(
    video_path: Path,
    orig_w: int,
    orig_h: int,
    duration_s: float,
    base_box: Optional[tuple[int, int, int, int]],
) -> tuple[int, int, int, int]:
    """
    Computes a stabilized 9:16 crop box `(cw, ch, x0, y0)` inside `base_box` (or full frame),
    automatically centered on the detected human face(s) across sampled timestamps so heads/faces
    are never cut off when converting 16:9, 1:1, 4:3, or 3:4 clips into full-screen Shorts!
    """
    bw, bh, bx0, by0 = base_box if base_box is not None else (orig_w, orig_h, 0, 0)
    target_ratio = 9.0 / 16.0
    cur_ratio = float(bw) / float(max(1, bh))

    if abs(cur_ratio - target_ratio) <= 0.012:
        return (bw // 2 * 2, bh // 2 * 2, bx0 // 2 * 2, by0 // 2 * 2)

    detector = create_yunet_detector()
    cx_norms: list[float] = []
    cy_norms: list[float] = []

    if detector is not None:
        fracs = [0.18, 0.38, 0.58, 0.78] if duration_s > 1.2 else [0.4]
        for frac in fracs:
            frame = extract_single_frame_bgr(video_path, duration_s * frac, (bw, bh, bx0, by0))
            if frame is None:
                continue
            faces = detect_faces_scaled(detector, frame)
            if faces:
                fbx, fby, fbw, fbh = faces[0]["bbox"]
                cx_norms.append((fbx + fbw * 0.5) / float(max(1, bw)))
                cy_norms.append((fby + fbh * 0.45) / float(max(1, bh)))

    subj_cx = float(np.median(cx_norms)) if cx_norms else 0.5
    subj_cy = float(np.median(cy_norms)) if cy_norms else 0.38

    if cur_ratio > target_ratio:
        # Source is wider than 9:16 (e.g. 16:9, 4:3, 1:1, 3:4) -> crop width centered on subject
        nh = max(2, bh // 2 * 2)
        nw = max(2, min(bw, int(round(nh * target_ratio)) // 2 * 2))
        ideal_x = int(round(bw * subj_cx - nw * 0.5))
        rel_x = max(0, min(bw - nw, ideal_x)) // 2 * 2
        return (nw, nh, bx0 + rel_x, by0)
    else:
        # Source is narrower/taller than 9:16 (e.g. 9:20 phone screen) -> crop height preserving headroom
        nw = max(2, bw // 2 * 2)
        nh = max(2, min(bh, int(round(nw / target_ratio)) // 2 * 2))
        ideal_y = int(round(bh * subj_cy - nh * 0.38))
        rel_y = max(0, min(bh - nh, ideal_y)) // 2 * 2
        return (nw, nh, bx0, by0 + rel_y)


def compute_blur_pad_inner_dims(
    src_w: int, src_h: int, canvas_w: int, canvas_h: int
) -> tuple[int, int]:
    """
    Fits `(src_w, src_h)` inside `(canvas_w, canvas_h)` preserving aspect ratio with even dimensions.
    """
    scale = min(float(canvas_w) / float(max(1, src_w)), float(canvas_h) / float(max(1, src_h)))
    fw = max(2, min(canvas_w, int(round((src_w * scale) / 2.0) * 2)))
    fh = max(2, min(canvas_h, int(round((src_h * scale) / 2.0) * 2)))
    if abs(fw - canvas_w) <= 6:
        fw = canvas_w
    if abs(fh - canvas_h) <= 6:
        fh = canvas_h
    return fw, fh


def compose_shorts_blur_canvas(
    fg_bgr: np.ndarray, canvas_w: int, canvas_h: int
) -> np.ndarray:
    """
    Places `fg_bgr` centered onto a `canvas_w x canvas_h` (9:16) frame over a smooth, darkened
    ambient Gaussian-blurred backdrop of `fg_bgr` (< 1ms via low-res blur pyramid).
    """
    fh, fw = fg_bgr.shape[:2]
    if fw == canvas_w and fh == canvas_h:
        return fg_bgr

    # Cover-crop `fg_bgr` to 9:16 at tiny 135x240 resolution for ultra-fast silky blur
    bg_small_w, bg_small_h = 136, 242
    cov_scale = max(float(bg_small_w) / float(max(1, fw)), float(bg_small_h) / float(max(1, fh)))
    tmp_w = max(bg_small_w, int(round(fw * cov_scale)))
    tmp_h = max(bg_small_h, int(round(fh * cov_scale)))
    small_cov = cv2.resize(fg_bgr, (tmp_w, tmp_h), interpolation=cv2.INTER_AREA)
    sx0 = (tmp_w - bg_small_w) // 2
    sy0 = (tmp_h - bg_small_h) // 2
    small_crop = small_cov[sy0 : sy0 + bg_small_h, sx0 : sx0 + bg_small_w]
    blurred_small = cv2.GaussianBlur(small_crop, (25, 25), sigmaX=8.5)
    darkened_small = cv2.convertScaleAbs(blurred_small, alpha=0.58, beta=0)
    canvas = cv2.resize(darkened_small, (canvas_w, canvas_h), interpolation=cv2.INTER_LINEAR)

    ox = (canvas_w - fw) // 2
    oy = (canvas_h - fh) // 2
    canvas[oy : oy + fh, ox : ox + fw] = fg_bgr
    return canvas


def compute_ai_prescale_dims(work_w: int, work_h: int, target_res: str) -> tuple[int, int]:
    """
    Computes optimal pre-scale input dimensions `(pre_w, pre_h)` before 4x Real-ESRGAN:
    - Collapses bloated TikTok/Douyin H.264 macroblocks into crisp 1x pixels so 4x SRVGGNetCompact
      synthesizes true high-frequency textures while keeping MPS GPU speed fast and memory safe.
    """
    short_cap_map = {
        "1080p": 400,  # 400 * 4 = 1600p short-edge -> 1.48x supersampled 1080p (~8.5 FPS on M2 Pro)
        "2k": 450,     # 450 * 4 = 1800p short-edge -> 1.25x supersampled 2K
        "4k": 540,     # 540 * 4 = 2160p short-edge -> Native True 4K UHD (2160x3840)
    }
    short_cap = short_cap_map.get(target_res, 400)
    cur_short = min(work_w, work_h)
    scale = min(1.0, float(short_cap) / float(max(1, cur_short)))

    pw = max(16, int(round((work_w * scale) / 2.0) * 2))
    ph = max(16, int(round((work_h * scale) / 2.0) * 2))

    # Memory ceiling guard for ultra-wide aspect ratios (max 525k input pixels -> 8.4M 4x output pixels)
    max_pixels = 540 * 960
    if pw * ph > max_pixels:
        shrink = math.sqrt(float(max_pixels) / float(pw * ph))
        pw = max(16, int(round((pw * shrink) / 2.0) * 2))
        ph = max(16, int(round((ph * shrink) / 2.0) * 2))

    return pw, ph


def create_yunet_detector():
    if not YUNET_PATH.exists():
        return None
    try:
        return cv2.FaceDetectorYN.create(
            str(YUNET_PATH),
            "",
            (320, 320),
            score_threshold=0.55,
            nms_threshold=0.3,
            top_k=5,
        )
    except Exception:
        return None


def detect_faces_scaled(detector, frame_bgr: np.ndarray) -> list[dict]:
    """
    Runs YuNet on a ~320px proxy and returns face dicts mapped back to `frame_bgr` coordinates.
    """
    if detector is None:
        return []
    h, w = frame_bgr.shape[:2]
    long_side = max(w, h)
    scale = 360.0 / float(max(1, long_side))
    dw = max(32, int(round(w * scale)))
    dh = max(32, int(round(h * scale)))
    small = cv2.resize(frame_bgr, (dw, dh), interpolation=cv2.INTER_AREA)
    detector.setInputSize((dw, dh))
    _, raw = detector.detect(small)
    if raw is None or len(raw) == 0:
        return []

    inv = 1.0 / scale
    faces: list[dict] = []
    for row in raw:
        score = float(row[14])
        if score < 0.55:
            continue
        bx, by, bw, bh = row[0] * inv, row[1] * inv, row[2] * inv, row[3] * inv
        lms = [(float(row[4 + i * 2]) * inv, float(row[5 + i * 2]) * inv) for i in range(5)]
        faces.append(
            {
                "bbox": [float(bx), float(by), float(bw), float(bh)],
                "landmarks": lms,  # right_eye, left_eye, nose, mouth_r, mouth_l
                "score": score,
                "area": float(bw * bh),
            }
        )
    faces.sort(key=lambda f: f["area"], reverse=True)
    return faces[:2]


def find_recommended_preview_timestamp(
    video_path: Path, duration_s: float, crop_box: Optional[tuple[int, int, int, int]]
) -> float:
    """
    Samples up to 5 candidate timestamps and picks the frame with the clearest face or highest sharpness.
    """
    if duration_s <= 1.0:
        return round(duration_s * 0.35, 2)

    detector = create_yunet_detector()
    fractions = [0.15, 0.30, 0.50, 0.70, 0.85]
    best_ts = round(duration_s * 0.25, 2)
    best_score = -1.0

    for frac in fractions:
        ts = round(duration_s * frac, 3)
        frame = extract_single_frame_bgr(video_path, ts, crop_box)
        if frame is None:
            continue
        small_gray = cv2.cvtColor(
            cv2.resize(frame, (270, max(150, int(270 * frame.shape[0] / max(1, frame.shape[1]))))),
            cv2.COLOR_BGR2GRAY,
        )
        sharp = float(cv2.Laplacian(small_gray, cv2.CV_64F).var())
        faces = detect_faces_scaled(detector, frame)
        face_bonus = 600.0 * faces[0]["score"] if faces else 0.0
        total = sharp + face_bonus
        if total > best_score:
            best_score = total
            best_ts = ts

    return round(best_ts, 2)


def extract_single_frame_bgr(
    video_path: Path,
    timestamp_s: float,
    crop_box: Optional[tuple[int, int, int, int]] = None,
) -> Optional[np.ndarray]:
    vf_parts = []
    if crop_box is not None:
        cw, ch, x0, y0 = crop_box
        vf_parts.append(f"crop={cw}:{ch}:{x0}:{y0}")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        f"{max(0.0, timestamp_s):.3f}",
        "-i",
        str(video_path),
    ]
    if vf_parts:
        cmd.extend(["-vf", ",".join(vf_parts)])
    cmd.extend(["-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"])

    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        return None
    arr = np.frombuffer(proc.stdout, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


class ColorAndSharpenMaster:
    """
    Fast LUT + Halo-Free Micro-Sharpen post-processor shared identically between Preview & Full Render.
    """

    def __init__(self, color_preset: str, sharpen_strength: float):
        self.color_preset = color_preset
        self.sharpen_amount = max(0.0, min(1.0, sharpen_strength / 100.0)) * 0.58
        self.b_lut, self.g_lut, self.r_lut, self.sat_scale = self._build_luts(color_preset)

    @staticmethod
    def _build_luts(preset: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        x = np.linspace(0.0, 1.0, 256, dtype=np.float32)

        if preset == "auto_vivid":
            # Clean S-curve contrast + slight shadow lift + vibrant saturation
            y = np.clip(0.5 + (x - 0.5) * 1.055 + 0.012 * (1.0 - x), 0.0, 1.0)
            y = np.power(y, 0.97)
            lut = np.clip(np.round(y * 255.0), 0, 255).astype(np.uint8)
            return lut, lut, lut, 1.09

        if preset == "beauty_glow":
            # Soft radiant portrait curve with gentle rosy warmth
            y = np.power(np.clip(x * 1.02 + 0.014 * np.sin(x * math.pi), 0.0, 1.0), 0.95)
            r = np.clip(np.round(np.clip(y * 1.015, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
            g = np.clip(np.round(y * 255.0), 0, 255).astype(np.uint8)
            b = np.clip(np.round(np.clip(y * 0.992 + 0.006, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
            return b, g, r, 1.06

        if preset == "cinema_hdr":
            # Deep blacks, punchy midtone micro-contrast, subtle warm highlights / cool shadows
            s_curve = x - 0.055 * np.sin(2.0 * math.pi * x)
            s_curve = np.clip(s_curve, 0.0, 1.0)
            r = np.clip(np.round(np.clip(s_curve + 0.012 * x, 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
            g = np.clip(np.round(s_curve * 255.0), 0, 255).astype(np.uint8)
            b = np.clip(np.round(np.clip(s_curve + 0.014 * (1.0 - x), 0.0, 1.0) * 255.0), 0, 255).astype(np.uint8)
            return b, g, r, 1.08

        # `natural`
        ident = np.arange(256, dtype=np.uint8)
        return ident, ident, ident, 1.0

    def process(self, bgr: np.ndarray) -> np.ndarray:
        out = bgr
        if self.sharpen_amount > 0.01:
            # Pure SIMD uint8 C++ unsharp mask (`cv2.addWeighted` avoids slow int16/float32 allocations)
            blur = cv2.GaussianBlur(out, (0, 0), sigmaX=1.05)
            out = cv2.addWeighted(out, 1.0 + self.sharpen_amount, blur, -self.sharpen_amount, 0)

        if self.color_preset != "natural":
            b, g, r = cv2.split(out)
            b = cv2.LUT(b, self.b_lut)
            g = cv2.LUT(g, self.g_lut)
            r = cv2.LUT(r, self.r_lut)
            out = cv2.merge((b, g, r))
            if abs(self.sat_scale - 1.0) > 0.01:
                # Subsampled chroma boost in YCrCb at 1/2 res for 4x faster SIMD execution
                h, w = out.shape[:2]
                ycrcb = cv2.cvtColor(out, cv2.COLOR_BGR2YCrCb)
                y_ch, cr, cb = cv2.split(ycrcb)
                cr = cv2.convertScaleAbs(cr, alpha=self.sat_scale, beta=128.0 * (1.0 - self.sat_scale))
                cb = cv2.convertScaleAbs(cb, alpha=self.sat_scale, beta=128.0 * (1.0 - self.sat_scale))
                out = cv2.cvtColor(cv2.merge((y_ch, cr, cb)), cv2.COLOR_YCrCb2BGR)

        return out


class RealEsrganEngine:
    """
    Apple Silicon MPS FP16 Real-ESRGAN v3 (`SRVGGNetCompact` x4 + Dynamic Network Interpolation)
    with Temporal Landmark-Guided Full-Resolution Face & Eye Restoration.
    """

    def __init__(
        self,
        denoise_percent: float,
        face_restore: bool,
        color_preset: str,
        sharpen_percent: float,
    ):
        import torch
        import torch.nn as nn

        self.torch = torch

        class SRVGGNetCompact(nn.Module):
            def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
                super().__init__()
                self.upscale = upscale
                body = [nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
                for _ in range(num_conv):
                    body.extend([nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)])
                body.append(nn.Conv2d(num_feat, num_out_ch * (upscale ** 2), 3, 1, 1))
                self.body = nn.ModuleList(body)
                self.upsampler = nn.PixelShuffle(upscale)

            def forward(self, x):
                out = x
                for layer in self.body:
                    out = layer(out)
                out = self.upsampler(out)
                base = nn.functional.interpolate(x, scale_factor=self.upscale, mode="nearest")
                return out + base

        if torch.backends.mps.is_available():
            self.device = torch.device("mps")
            self.use_half = True
            self.device_label = "Apple Silicon MPS GPU (FP16)"
        elif torch.cuda.is_available():
            self.device = torch.device("cuda")
            self.use_half = True
            self.device_label = "CUDA GPU (FP16)"
        else:
            self.device = torch.device("cpu")
            self.use_half = False
            self.device_label = "CPU (FP32)"

        p_sharp, p_wdn = ensure_realesrgan_weights()
        sd_sharp = torch.load(str(p_sharp), map_location="cpu", weights_only=True)["params"]
        sd_wdn = torch.load(str(p_wdn), map_location="cpu", weights_only=True)["params"]

        w_dn = max(0.0, min(1.0, float(denoise_percent) / 100.0))
        dni_sd = {k: (1.0 - w_dn) * sd_sharp[k] + w_dn * sd_wdn[k] for k in sd_sharp}

        net = SRVGGNetCompact()
        net.load_state_dict(dni_sd, strict=True)
        net.eval()
        if self.use_half:
            net = net.to(self.device).half()
        else:
            net = net.to(self.device)
        self.net = net

        self.face_restore = face_restore
        self.face_detector = create_yunet_detector() if face_restore else None
        self.prev_face_state: Optional[dict] = None
        self.prev_raw_faces: list[dict] = []
        self.frame_counter: int = 0
        self.master = ColorAndSharpenMaster(color_preset, sharpen_percent)

    def _sr_batch_rgb(self, rgb_list: list[np.ndarray]) -> list[np.ndarray]:
        torch = self.torch
        arr = np.stack(rgb_list, axis=0)  # (B, H, W, 3) uint8
        with torch.inference_mode():
            dtype = torch.float16 if self.use_half else torch.float32
            t = torch.from_numpy(arr).to(self.device, non_blocking=True)
            t = t.permute(0, 3, 1, 2).contiguous().to(dtype=dtype).mul_(1.0 / 255.0)
            out = self.net(t)
            out_u8 = out.clamp_(0.0, 1.0).mul_(255.0).round_().to(torch.uint8)
            out_np = out_u8.permute(0, 2, 3, 1).contiguous().cpu().numpy()
        return [out_np[i] for i in range(out_np.shape[0])]

    def _smooth_face_temporally(self, detected_faces: list[dict]) -> list[dict]:
        if not detected_faces:
            self.prev_face_state = None
            return []
        primary = detected_faces[0]
        if self.prev_face_state is not None:
            px, py, pw, ph = self.prev_face_state["bbox"]
            cx, cy, cw, ch = primary["bbox"]
            # Check center proximity so cuts snap immediately without lag
            dist = math.hypot((cx + cw * 0.5) - (px + pw * 0.5), (cy + ch * 0.5) - (py + ph * 0.5))
            if dist < max(cw, ch) * 0.55:
                alpha = 0.52
                sbbox = [
                    alpha * cx + (1 - alpha) * px,
                    alpha * cy + (1 - alpha) * py,
                    alpha * cw + (1 - alpha) * pw,
                    alpha * ch + (1 - alpha) * ph,
                ]
                plms = self.prev_face_state["landmarks"]
                clms = primary["landmarks"]
                slms = [
                    (alpha * clms[i][0] + (1 - alpha) * plms[i][0], alpha * clms[i][1] + (1 - alpha) * plms[i][1])
                    for i in range(5)
                ]
                primary = {**primary, "bbox": sbbox, "landmarks": slms}
        self.prev_face_state = primary
        return [primary] + detected_faces[1:2]

    def _restore_faces_on_frame(
        self,
        orig_crop_bgr: np.ndarray,
        sr_target_bgr: np.ndarray,
        pre_w: int,
        temporal_smooth: bool,
    ) -> tuple[np.ndarray, Optional[tuple[float, float]]]:
        if not self.face_restore or self.face_detector is None:
            return sr_target_bgr, None

        self.frame_counter += 1
        if temporal_smooth and self.prev_raw_faces and (self.frame_counter % 2 == 0):
            faces = self.prev_raw_faces
        else:
            faces = detect_faces_scaled(self.face_detector, orig_crop_bgr)
            self.prev_raw_faces = faces

        if temporal_smooth:
            faces = self._smooth_face_temporally(faces)
        if not faces:
            return sr_target_bgr, None

        oh, ow = orig_crop_bgr.shape[:2]
        th, tw = sr_target_bgr.shape[:2]
        sx = float(tw) / float(max(1, ow))
        sy = float(th) / float(max(1, oh))
        need_extra_roi_sr = ow > int(pre_w * 1.15)

        out_bgr = sr_target_bgr.copy()
        focus_norm: Optional[tuple[float, float]] = None

        for idx, face in enumerate(faces):
            bx, by, bw, bh = face["bbox"]
            lms = face["landmarks"]
            if idx == 0:
                # Center zoom focus right between the two eyes!
                eye_cx = (lms[0][0] + lms[1][0]) * 0.5 / float(max(1, ow))
                eye_cy = (lms[0][1] + lms[1][1]) * 0.5 / float(max(1, oh))
                focus_norm = (
                    round(max(0.1, min(0.9, eye_cx)), 4),
                    round(max(0.1, min(0.9, eye_cy)), 4),
                )

            # Padded square ROI on original un-downscaled frame
            side = max(bw, bh) * 1.38
            cx = bx + bw * 0.5
            cy = by + bh * 0.48
            x0 = max(0, int(round(cx - side * 0.5)))
            y0 = max(0, int(round(cy - side * 0.5)))
            x1 = min(ow, int(round(cx + side * 0.5)))
            y1 = min(oh, int(round(cy + side * 0.5)))
            rw, rh = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
            x1, y1 = x0 + rw, y0 + rh
            if rw < 28 or rh < 28:
                continue

            # Map ROI box onto target output resolution
            tx0 = max(0, int(round(x0 * sx)))
            ty0 = max(0, int(round(y0 * sy)))
            tx1 = min(tw, int(round(x1 * sx)))
            ty1 = min(th, int(round(y1 * sy)))
            trw, trh = tx1 - tx0, ty1 - ty0
            if trw < 32 or trh < 32:
                continue

            if need_extra_roi_sr:
                roi_orig = orig_crop_bgr[y0:y1, x0:x1]
                roi_cap = 168
                if max(rw, rh) > roi_cap:
                    rscale = float(roi_cap) / float(max(rw, rh))
                    in_rw = max(24, int(round((rw * rscale) / 2.0) * 2))
                    in_rh = max(24, int(round((rh * rscale) / 2.0) * 2))
                    roi_in = cv2.resize(roi_orig, (in_rw, in_rh), interpolation=cv2.INTER_AREA)
                else:
                    roi_in = roi_orig

                roi_rgb = cv2.cvtColor(roi_in, cv2.COLOR_BGR2RGB)
                sr_roi_rgb = self._sr_batch_rgb([roi_rgb])[0]
                sr_roi_bgr = cv2.cvtColor(sr_roi_rgb, cv2.COLOR_RGB2BGR)
                face_hi = cv2.resize(sr_roi_bgr, (trw, trh), interpolation=cv2.INTER_LANCZOS4)
            else:
                # Full-frame 4x Real-ESRGAN already processed the face at 100% native input resolution!
                face_hi = sr_target_bgr[ty0:ty1, tx0:tx1]

            # Build landmark masks on a fast 128x128 grid and resize (100x faster than full-res np.exp!)
            gw, gh = 128, 128
            yy, xx = np.ogrid[:gh, :gw]
            detail_grid = np.zeros((gh, gw), dtype=np.float32)
            gsx = float(gw) / float(max(1, trw))
            gsy = float(gh) / float(max(1, trh))

            eye_rad = max(3.0, min(gw, gh) * 0.13)
            for ex_idx in (0, 1):
                lx = (lms[ex_idx][0] - x0) * sx * gsx
                ly = (lms[ex_idx][1] - y0) * sy * gsy
                d2 = ((xx - lx) ** 2) / (eye_rad * 1.45) ** 2 + ((yy - ly) ** 2) / (eye_rad * 1.05) ** 2
                detail_grid = np.maximum(detail_grid, np.exp(-0.5 * d2))

            mx = ((lms[3][0] + lms[4][0]) * 0.5 - x0) * sx * gsx
            my = ((lms[3][1] + lms[4][1]) * 0.5 - y0) * sy * gsy
            m_rad = max(3.0, min(gw, gh) * 0.12)
            md2 = ((xx - mx) ** 2) / (m_rad * 1.5) ** 2 + ((yy - my) ** 2) / (m_rad * 0.95) ** 2
            detail_grid = np.maximum(detail_grid, 0.75 * np.exp(-0.5 * md2))

            nx = (xx - gw * 0.5) / max(1.0, gw * 0.46)
            ny = (yy - gh * 0.5) / max(1.0, gh * 0.46)
            r_norm = np.sqrt(nx * nx + ny * ny)
            feather_grid = np.clip((1.0 - r_norm) / 0.38, 0.0, 1.0)
            feather_grid = ((0.5 - 0.5 * np.cos(feather_grid * math.pi)) * 0.82).astype(np.float32)

            # Bake effective weights on 128x128 grid, then upscale once!
            w_sharp_g = (detail_grid * 0.62 * feather_grid).astype(np.float32)
            w_skin_g = ((1.0 - detail_grid) * 0.34 * feather_grid).astype(np.float32)
            w_sharp = cv2.resize(w_sharp_g, (trw, trh), interpolation=cv2.INTER_LINEAR)[:, :, None]
            w_skin = cv2.resize(w_skin_g, (trw, trh), interpolation=cv2.INTER_LINEAR)[:, :, None]

            # 1) Half-res bilateral porcelain skin polish (4x faster & silkier on skin)
            sm_w, sm_h = max(16, trw // 2), max(16, trh // 2)
            skin_half = cv2.bilateralFilter(
                cv2.resize(face_hi, (sm_w, sm_h), interpolation=cv2.INTER_AREA),
                d=5,
                sigmaColor=16,
                sigmaSpace=14,
            )
            skin_smooth = cv2.resize(skin_half, (trw, trh), interpolation=cv2.INTER_LINEAR)

            # 2) Crisp SIMD eye/lash/lip micro-clarity
            eye_blur = cv2.GaussianBlur(face_hi, (0, 0), sigmaX=1.1)
            eye_sharp = cv2.addWeighted(face_hi, 1.65, eye_blur, -0.65, 0)

            base_patch = out_bgr[ty0:ty1, tx0:tx1]
            if need_extra_roi_sr:
                f_mask = cv2.resize(feather_grid, (trw, trh), interpolation=cv2.INTER_LINEAR)[:, :, None]
                w_face_base = f_mask - w_sharp - w_skin
                blended = (
                    base_patch.astype(np.float32) * (1.0 - f_mask)
                    + face_hi.astype(np.float32) * w_face_base
                    + skin_smooth.astype(np.float32) * w_skin
                    + eye_sharp.astype(np.float32) * w_sharp
                )
            else:
                w_keep = 1.0 - w_sharp - w_skin
                blended = (
                    base_patch.astype(np.float32) * w_keep
                    + skin_smooth.astype(np.float32) * w_skin
                    + eye_sharp.astype(np.float32) * w_sharp
                )
            out_bgr[ty0:ty1, tx0:tx1] = np.clip(blended, 0, 255).astype(np.uint8)

        return out_bgr, focus_norm

    def enhance_frame_batch(
        self,
        orig_frames_bgr: list[np.ndarray],
        pre_w: int,
        pre_h: int,
        tw: int,
        th: int,
        temporal_smooth: bool = True,
    ) -> tuple[list[np.ndarray], Optional[tuple[float, float]]]:
        pre_rgb_list: list[np.ndarray] = []
        for orig_crop_bgr in orig_frames_bgr:
            oh, ow = orig_crop_bgr.shape[:2]
            if (ow, oh) != (pre_w, pre_h):
                pre_bgr = cv2.resize(orig_crop_bgr, (pre_w, pre_h), interpolation=cv2.INTER_AREA)
            else:
                pre_bgr = orig_crop_bgr
            pre_rgb_list.append(cv2.cvtColor(pre_bgr, cv2.COLOR_BGR2RGB))

        sr_rgb_list = self._sr_batch_rgb(pre_rgb_list)

        results: list[np.ndarray] = []
        last_focus: Optional[tuple[float, float]] = None
        for orig_crop_bgr, sr_rgb in zip(orig_frames_bgr, sr_rgb_list):
            sr_bgr = cv2.cvtColor(sr_rgb, cv2.COLOR_RGB2BGR)
            sh, sw = sr_bgr.shape[:2]
            if (sw, sh) != (tw, th):
                interp = cv2.INTER_AREA if sw > tw else cv2.INTER_LANCZOS4
                sr_target_bgr = cv2.resize(sr_bgr, (tw, th), interpolation=interp)
            else:
                sr_target_bgr = sr_bgr

            sr_face_bgr, focus_norm = self._restore_faces_on_frame(
                orig_crop_bgr, sr_target_bgr, pre_w=pre_w, temporal_smooth=temporal_smooth
            )
            if focus_norm is not None:
                last_focus = focus_norm
            results.append(self.master.process(sr_face_bgr))

        return results, last_focus

    def enhance_single_frame(
        self,
        orig_crop_bgr: np.ndarray,
        pre_w: int,
        pre_h: int,
        tw: int,
        th: int,
        temporal_smooth: bool = False,
    ) -> tuple[np.ndarray, Optional[tuple[float, float]]]:
        outs, focus_norm = self.enhance_frame_batch(
            [orig_crop_bgr], pre_w, pre_h, tw, th, temporal_smooth=temporal_smooth
        )
        return outs[0], focus_norm


def resolve_framing_plan(
    video_path: Path,
    orig_w: int,
    orig_h: int,
    dur_s: float,
    crop_bars: bool,
    aspect_mode: str,
    target_res: str,
) -> dict:
    bar_box = (
        detect_active_content_box(video_path, orig_w, orig_h, dur_s)
        if crop_bars
        else None
    )

    if aspect_mode == "shorts_fill":
        s_box = compute_smart_9_16_crop_box(video_path, orig_w, orig_h, dur_s, bar_box)
        if s_box[0] == orig_w and s_box[1] == orig_h and s_box[2] == 0 and s_box[3] == 0:
            effective_crop = None
        else:
            effective_crop = s_box
    else:
        effective_crop = bar_box

    work_w = effective_crop[0] if effective_crop else orig_w
    work_h = effective_crop[1] if effective_crop else orig_h
    canvas_w, canvas_h, bitrate_mbps = compute_target_dimensions(
        work_w, work_h, target_res, aspect_mode
    )

    if aspect_mode == "shorts_blur":
        fg_w, fg_h = compute_blur_pad_inner_dims(work_w, work_h, canvas_w, canvas_h)
        use_blur_pad = fg_w != canvas_w or fg_h != canvas_h
    else:
        fg_w, fg_h = canvas_w, canvas_h
        use_blur_pad = False

    return {
        "bar_box": bar_box,
        "crop_box": effective_crop,
        "work_w": work_w,
        "work_h": work_h,
        "fg_w": fg_w,
        "fg_h": fg_h,
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "use_blur_pad": use_blur_pad,
        "bitrate_mbps": bitrate_mbps,
    }


def build_ffmpeg_pro_vf_chain(
    crop_box: Optional[tuple[int, int, int, int]],
    fg_w: int,
    fg_h: int,
    canvas_w: int,
    canvas_h: int,
    use_blur_pad: bool,
    denoise_percent: float,
    sharpen_percent: float,
    color_preset: str,
    fps_mode: str,
    orig_fps: float,
) -> str:
    parts: list[str] = []
    if crop_box is not None:
        cw, ch, x0, y0 = crop_box
        parts.append(f"crop={cw}:{ch}:{x0}:{y0}")

    dn = max(0.0, min(1.0, denoise_percent / 100.0))
    if dn > 0.08:
        alpha = round(0.035 + dn * 0.09, 3)
        parts.append(f"deblock=filter=weak:block=4:alpha={alpha}:beta={round(alpha*0.6, 3)}")
        luma_sp = round(0.8 + dn * 3.2, 2)
        chroma_sp = round(0.6 + dn * 2.5, 2)
        luma_tmp = round(1.2 + dn * 3.8, 2)
        parts.append(f"hqdn3d={luma_sp}:{chroma_sp}:{luma_tmp}:{round(luma_tmp*0.8, 2)}")

    parts.append(f"scale={fg_w}:{fg_h}:flags=lanczos+accurate_rnd")

    sh = max(0.0, min(1.0, sharpen_percent / 100.0))
    if sh > 0.05:
        cas_val = round(0.18 + sh * 0.68, 2)
        parts.append(f"cas={cas_val}")

    if color_preset == "auto_vivid":
        parts.append("eq=brightness=0.012:contrast=1.05:saturation=1.09:gamma=1.02")
    elif color_preset == "beauty_glow":
        parts.append("eq=brightness=0.022:contrast=1.03:saturation=1.06:gamma=1.04")
        parts.append("colorbalance=rm=0.02:gm=0.0:bm=-0.01:rh=0.02")
    elif color_preset == "cinema_hdr":
        parts.append("eq=brightness=-0.008:contrast=1.08:saturation=1.08:gamma=0.98")
        parts.append("colorbalance=rs=-0.02:bs=0.025:rh=0.025:bh=-0.015")

    base_chain = ",".join(parts)

    post_parts: list[str] = []
    if fps_mode == "smooth_60fps" and orig_fps < 50.0:
        post_parts.append("framerate=fps=60:interp_start=20:interp_end=235:scene=8.2")
    post_parts.append("setsar=1")
    post_chain = ",".join(post_parts)

    if use_blur_pad:
        return (
            f"{base_chain},split[fg][bg];"
            f"[bg]scale={canvas_w}:{canvas_h}:force_original_aspect_ratio=increase,"
            f"crop={canvas_w}:{canvas_h},boxblur=26:3,eq=brightness=-0.16:saturation=1.10[bg2];"
            f"[bg2][fg]overlay=(W-w)/2:(H-h)/2,{post_chain}"
        )

    return f"{base_chain},{post_chain}"


def run_probe_mode(args: argparse.Namespace) -> None:
    in_path = Path(args.video).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = probe_media(in_path)
    crop_box = detect_active_content_box(
        in_path, meta["width"], meta["height"], meta["duration_s"]
    )
    rec_ts = find_recommended_preview_timestamp(in_path, meta["duration_s"], crop_box)

    work_w = crop_box[0] if crop_box else meta["width"]
    work_h = crop_box[1] if crop_box else meta["height"]
    is_native_9_16 = abs((float(work_w) / float(max(1, work_h))) - (9.0 / 16.0)) <= 0.025

    nw_1080, nh_1080, _ = compute_target_dimensions(work_w, work_h, "1080p", "keep_aspect")
    nw_2k, nh_2k, _ = compute_target_dimensions(work_w, work_h, "2k", "keep_aspect")
    nw_4k, nh_4k, _ = compute_target_dimensions(work_w, work_h, "4k", "keep_aspect")

    print(
        json.dumps(
            {
                "ok": True,
                "video_info": {
                    **meta,
                    "has_pillarbox": crop_box is not None,
                    "crop_box": list(crop_box) if crop_box else None,
                    "active_width": work_w,
                    "active_height": work_h,
                    "is_native_9_16": is_native_9_16,
                    "recommended_ts": rec_ts,
                    "shorts_res_options": {
                        "1080p": {"width": 1080, "height": 1920},
                        "2k": {"width": 1440, "height": 2560},
                        "4k": {"width": 2160, "height": 3840},
                    },
                    "res_options": {
                        "1080p": {"width": nw_1080, "height": nh_1080},
                        "2k": {"width": nw_2k, "height": nh_2k},
                        "4k": {"width": nw_4k, "height": nh_4k},
                    },
                },
            },
            ensure_ascii=False,
        )
    )


def run_preview_mode(args: argparse.Namespace) -> None:
    t0 = time.time()
    in_path = Path(args.video).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = probe_media(in_path)
    ts = max(0.0, min(meta["duration_s"] - 0.05, float(args.timestamp)))
    plan = resolve_framing_plan(
        in_path,
        meta["width"],
        meta["height"],
        meta["duration_s"],
        args.crop_bars,
        args.aspect_mode,
        args.target_res,
    )
    crop_box = plan["crop_box"]
    fg_w, fg_h = plan["fg_w"], plan["fg_h"]
    canvas_w, canvas_h = plan["canvas_w"], plan["canvas_h"]
    use_blur_pad = plan["use_blur_pad"]

    orig_crop_bgr = extract_single_frame_bgr(in_path, ts, crop_box)
    if orig_crop_bgr is None:
        raise RuntimeError("Không thể trích xuất khung hình xem thử tại thời điểm này.")

    work_h, work_w = orig_crop_bgr.shape[:2]

    # Pixel-aligned Before image (matches exact target canvas & framing so split slider aligns 100%)
    before_fg = cv2.resize(orig_crop_bgr, (fg_w, fg_h), interpolation=cv2.INTER_LINEAR)
    before_aligned = (
        compose_shorts_blur_canvas(before_fg, canvas_w, canvas_h)
        if use_blur_pad
        else before_fg
    )

    focus_norm = (0.5, 0.38 if not use_blur_pad else 0.5)
    engine_label = "FFmpeg Pro Studio"

    if args.engine == "ai_realesrgan":
        pre_w, pre_h = compute_ai_prescale_dims(work_w, work_h, args.target_res)
        ai = RealEsrganEngine(
            denoise_percent=args.denoise,
            face_restore=args.face_restore,
            color_preset=args.color_preset,
            sharpen_percent=args.sharpen,
        )
        after_fg, detected_focus = ai.enhance_single_frame(
            orig_crop_bgr, pre_w, pre_h, fg_w, fg_h, temporal_smooth=False
        )
        after_bgr = (
            compose_shorts_blur_canvas(after_fg, canvas_w, canvas_h)
            if use_blur_pad
            else after_fg
        )
        engine_label = f"Real-ESRGAN v3 • {ai.device_label}"
        if detected_focus is not None:
            if use_blur_pad:
                ox = (canvas_w - fg_w) * 0.5
                oy = (canvas_h - fg_h) * 0.5
                focus_norm = (
                    round((ox + detected_focus[0] * fg_w) / float(max(1, canvas_w)), 4),
                    round((oy + detected_focus[1] * fg_h) / float(max(1, canvas_h)), 4),
                )
            else:
                focus_norm = detected_focus
    else:
        vf_chain = build_ffmpeg_pro_vf_chain(
            crop_box=crop_box,
            fg_w=fg_w,
            fg_h=fg_h,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            use_blur_pad=use_blur_pad,
            denoise_percent=args.denoise,
            sharpen_percent=args.sharpen,
            color_preset=args.color_preset,
            fps_mode="keep",
            orig_fps=meta["fps"],
        )
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{ts:.3f}",
                "-i",
                str(in_path),
                "-vf",
                vf_chain,
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
            raise RuntimeError("Lỗi tạo khung xem thử FFmpeg Pro.")
        after_bgr = cv2.imdecode(np.frombuffer(proc.stdout, dtype=np.uint8), cv2.IMREAD_COLOR)
        det = create_yunet_detector()
        faces = detect_faces_scaled(det, orig_crop_bgr)
        if faces:
            lms = faces[0]["landmarks"]
            fx = ((lms[0][0] + lms[1][0]) * 0.5) / float(max(1, work_w))
            fy = ((lms[0][1] + lms[1][1]) * 0.5) / float(max(1, work_h))
            if use_blur_pad:
                ox = (canvas_w - fg_w) * 0.5
                oy = (canvas_h - fg_h) * 0.5
                focus_norm = (
                    round((ox + fx * fg_w) / float(max(1, canvas_w)), 4),
                    round((oy + fy * fg_h) / float(max(1, canvas_h)), 4),
                )
            else:
                focus_norm = (
                    round(max(0.1, min(0.9, fx)), 4),
                    round(max(0.1, min(0.9, fy)), 4),
                )

    sig_raw = (
        f"{in_path}_{ts:.2f}_{args.engine}_{args.target_res}_{args.aspect_mode}_"
        f"{args.denoise}_{args.sharpen}_{args.face_restore}_{args.color_preset}_{args.crop_bars}"
    )
    sig = hashlib.md5(sig_raw.encode("utf-8")).hexdigest()[:10]
    before_name = f"prev_before_{sig}.jpg"
    after_name = f"prev_after_{sig}.jpg"

    cv2.imwrite(str(out_dir / before_name), before_aligned, [int(cv2.IMWRITE_JPEG_QUALITY), 96])
    cv2.imwrite(str(out_dir / after_name), after_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 96])

    elapsed_ms = int(round((time.time() - t0) * 1000.0))
    print(
        json.dumps(
            {
                "ok": True,
                "before_file": before_name,
                "after_file": after_name,
                "orig_width": work_w,
                "orig_height": work_h,
                "preview_width": canvas_w,
                "preview_height": canvas_h,
                "aspect_mode": args.aspect_mode,
                "timestamp_s": round(ts, 2),
                "focus_x": focus_norm[0],
                "focus_y": focus_norm[1],
                "did_crop_bars": plan["bar_box"] is not None,
                "engine_label": engine_label,
                "elapsed_ms": elapsed_ms,
            },
            ensure_ascii=False,
        )
    )


def run_render_mode(args: argparse.Namespace) -> None:
    t0 = time.time()
    in_path = Path(args.video).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    prog_path = Path(args.progress_file).expanduser().resolve() if args.progress_file else None

    write_progress(
        prog_path,
        {
            "status": "running",
            "stage": "Đang phân tích cấu trúc khung hình & chuẩn bị GPU...",
            "percent": 2.0,
            "processed_frames": 0,
            "total_frames": 0,
            "fps": 0.0,
            "eta_s": None,
        },
    )

    meta = probe_media(in_path)
    orig_w, orig_h = meta["width"], meta["height"]
    dur_s = meta["duration_s"]
    orig_fps = meta["fps"]
    total_frames = meta["total_frames"]
    has_audio = meta["has_audio"]

    plan = resolve_framing_plan(
        in_path,
        orig_w,
        orig_h,
        dur_s,
        args.crop_bars,
        args.aspect_mode,
        args.target_res,
    )
    crop_box = plan["crop_box"]
    work_w, work_h = plan["work_w"], plan["work_h"]
    fg_w, fg_h = plan["fg_w"], plan["fg_h"]
    tw, th = plan["canvas_w"], plan["canvas_h"]
    use_blur_pad = plan["use_blur_pad"]
    bitrate_mbps = plan["bitrate_mbps"]

    use_vt = has_videotoolbox()
    v_enc = (
        [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            f"{bitrate_mbps}M",
            "-maxrate",
            f"{int(round(bitrate_mbps * 1.35))}M",
            "-bufsize",
            f"{bitrate_mbps * 2}M",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
        ]
        if use_vt
        else [
            "-c:v",
            "libx264",
            "-crf",
            "16",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
        ]
    )

    out_fps = 60.0 if (args.fps_mode == "smooth_60fps" and orig_fps < 50.0) else orig_fps

    if args.engine == "ffmpeg_pro":
        vf_chain = build_ffmpeg_pro_vf_chain(
            crop_box=crop_box,
            fg_w=fg_w,
            fg_h=fg_h,
            canvas_w=tw,
            canvas_h=th,
            use_blur_pad=use_blur_pad,
            denoise_percent=args.denoise,
            sharpen_percent=args.sharpen,
            color_preset=args.color_preset,
            fps_mode=args.fps_mode,
            orig_fps=orig_fps,
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-nostats",
            "-i",
            str(in_path),
            "-vf",
            vf_chain,
            *v_enc,
        ]
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100"])
        else:
            cmd.append("-an")
        cmd.extend(["-movflags", "+faststart", str(out_path)])

        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    us = int(line.split("=", 1)[1])
                    cur_s = max(0.0, us / 1_000_000.0)
                    pct = min(99.0, round((cur_s / max(0.1, dur_s)) * 100.0, 1))
                    done_f = min(total_frames, int(round(cur_s * orig_fps)))
                    elapsed = max(0.05, time.time() - t0)
                    spd_fps = round(done_f / elapsed, 1)
                    eta = max(0, int(round((total_frames - done_f) / max(1.0, spd_fps))))
                    write_progress(
                        prog_path,
                        {
                            "status": "running",
                            "stage": "FFmpeg Pro Studio • Đang khử nhiễu & nâng cấp phần cứng...",
                            "percent": pct,
                            "processed_frames": done_f,
                            "total_frames": total_frames,
                            "fps": spd_fps,
                            "eta_s": eta,
                            "engine_label": "FFmpeg Pro • Apple VideoToolbox",
                        },
                    )
                except Exception:
                    pass
        stderr_out = proc.stderr.read() if proc.stderr else ""
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(stderr_out.strip()[:500] or "FFmpeg Pro render failed")
        engine_used = "FFmpeg Pro • Apple VideoToolbox"

    else:
        # Engine: `ai_realesrgan` (Streaming rawvideo -> PyTorch MPS FP16 -> VideoToolbox hardware encode)
        pre_w, pre_h = compute_ai_prescale_dims(work_w, work_h, args.target_res)
        ai = RealEsrganEngine(
            denoise_percent=args.denoise,
            face_restore=args.face_restore,
            color_preset=args.color_preset,
            sharpen_percent=args.sharpen,
        )
        engine_used = f"Real-ESRGAN v3 • {ai.device_label}"

        dec_vf: list[str] = []
        if crop_box is not None:
            cw, ch, x0, y0 = crop_box
            dec_vf.append(f"crop={cw}:{ch}:{x0}:{y0}")

        dec_cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(in_path)]
        if dec_vf:
            dec_cmd.extend(["-vf", ",".join(dec_vf)])
        dec_cmd.extend(["-f", "rawvideo", "-pix_fmt", "bgr24", "-"])

        enc_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{tw}x{th}",
            "-r",
            f"{orig_fps}",
            "-i",
            "-",
        ]
        if has_audio:
            enc_cmd.extend(["-i", str(in_path), "-map", "0:v:0", "-map", "1:a:0?"])
        else:
            enc_cmd.extend(["-map", "0:v:0"])

        enc_vf_parts: list[str] = []
        if args.fps_mode == "smooth_60fps" and orig_fps < 50.0:
            enc_vf_parts.append("framerate=fps=60:interp_start=20:interp_end=235:scene=8.2")
        enc_vf_parts.append("setsar=1")
        enc_cmd.extend(["-vf", ",".join(enc_vf_parts)])

        enc_cmd.extend(v_enc)
        if has_audio:
            enc_cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-shortest"])
        else:
            enc_cmd.append("-an")
        enc_cmd.extend(["-movflags", "+faststart", str(out_path)])

        decoder = subprocess.Popen(dec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        encoder = subprocess.Popen(enc_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

        frame_bytes = work_w * work_h * 3
        batch_size = 3 if (pre_w * pre_h <= 420 * 750) else 2
        processed = 0
        t_infer_start = time.time()
        last_prog_write = 0.0

        try:
            assert decoder.stdout is not None
            assert encoder.stdin is not None
            eof = False
            while not eof:
                batch_frames: list[np.ndarray] = []
                for _ in range(batch_size):
                    buf = decoder.stdout.read(frame_bytes)
                    if not buf or len(buf) < frame_bytes:
                        eof = True
                        break
                    batch_frames.append(
                        np.frombuffer(buf, dtype=np.uint8).reshape((work_h, work_w, 3)).copy()
                    )
                if not batch_frames:
                    break

                enhanced_list, _ = ai.enhance_frame_batch(
                    batch_frames, pre_w, pre_h, fg_w, fg_h, temporal_smooth=True
                )
                for ef in enhanced_list:
                    out_f = compose_shorts_blur_canvas(ef, tw, th) if use_blur_pad else ef
                    encoder.stdin.write(out_f.tobytes())
                processed += len(enhanced_list)

                now = time.time()
                if now - last_prog_write >= 0.45 or processed == total_frames:
                    last_prog_write = now
                    elapsed = max(0.05, now - t_infer_start)
                    cur_fps = round(processed / elapsed, 1)
                    rem_frames = max(0, total_frames - processed)
                    eta_s = int(round(rem_frames / max(0.2, cur_fps)))
                    pct = min(99.0, round((processed / float(max(1, total_frames))) * 100.0, 1))
                    write_progress(
                        prog_path,
                        {
                            "status": "running",
                            "stage": f"AI Real-ESRGAN đang tái tạo chi tiết ({processed}/{total_frames} frames)...",
                            "percent": pct,
                            "processed_frames": processed,
                            "total_frames": total_frames,
                            "fps": cur_fps,
                            "eta_s": eta_s,
                            "engine_label": engine_used,
                        },
                    )
        finally:
            if encoder.stdin:
                try:
                    encoder.stdin.close()
                except Exception:
                    pass
            if decoder.stdout:
                try:
                    decoder.stdout.close()
                except Exception:
                    pass

        dec_ret = decoder.wait()
        enc_stderr = encoder.stderr.read().decode("utf-8", errors="ignore") if encoder.stderr else ""
        enc_ret = encoder.wait()
        if enc_ret != 0 or processed == 0:
            raise RuntimeError(
                enc_stderr.strip()[:500] or f"AI Video Enhancer render failed (dec={dec_ret}, enc={enc_ret})"
            )

    elapsed_s = round(time.time() - t0, 2)
    size_mb = round(out_path.stat().st_size / (1024.0 * 1024.0), 2)

    result_payload = {
        "ok": True,
        "status": "completed",
        "percent": 100.0,
        "out_file": out_path.name,
        "out_path": str(out_path),
        "orig_width": orig_w,
        "orig_height": orig_h,
        "active_width": work_w,
        "active_height": work_h,
        "out_width": tw,
        "out_height": th,
        "aspect_mode": args.aspect_mode,
        "orig_fps": orig_fps,
        "out_fps": out_fps,
        "did_crop_bars": plan["bar_box"] is not None,
        "duration_s": round(dur_s, 2),
        "size_mb": size_mb,
        "bitrate_mbps": bitrate_mbps,
        "elapsed_s": elapsed_s,
        "engine_label": engine_used,
    }
    write_progress(prog_path, result_payload)
    print(json.dumps(result_payload, ensure_ascii=False))


def str2bool(val: str) -> bool:
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["probe", "preview", "render"])
    parser.add_argument("--video", required=True)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--progress-file", default="")
    parser.add_argument("--timestamp", type=float, default=1.0)
    parser.add_argument("--engine", default="ai_realesrgan", choices=["ai_realesrgan", "ffmpeg_pro"])
    parser.add_argument("--target-res", default="1080p", choices=["1080p", "2k", "4k"])
    parser.add_argument(
        "--aspect-mode",
        default="shorts_fill",
        choices=["shorts_fill", "shorts_blur", "keep_aspect"],
    )
    parser.add_argument("--denoise", type=float, default=55.0)
    parser.add_argument("--sharpen", type=float, default=45.0)
    parser.add_argument("--face-restore", type=str2bool, default=True)
    parser.add_argument(
        "--color-preset",
        default="auto_vivid",
        choices=["natural", "auto_vivid", "beauty_glow", "cinema_hdr"],
    )
    parser.add_argument("--crop-bars", type=str2bool, default=True)
    parser.add_argument("--fps-mode", default="keep", choices=["keep", "smooth_60fps"])

    args = parser.parse_args()
    prog_path = Path(args.progress_file).expanduser().resolve() if args.progress_file else None

    try:
        if args.mode == "probe":
            run_probe_mode(args)
        elif args.mode == "preview":
            run_preview_mode(args)
        elif args.mode == "render":
            run_render_mode(args)
    except Exception as exc:
        err_payload = {"ok": False, "status": "error", "error": str(exc)}
        write_progress(prog_path, err_payload)
        print(json.dumps(err_payload, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
