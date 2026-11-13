#!/usr/bin/env python3
"""
Hardware-Accelerated Video Quality Enhancer & Copyright-Safe BGM Replacer (`reup_video_remaster.py`).

Features:
- Auto-detects and crops pillarbox/letterbox black bars (e.g. 16:9 wrapper around vertical 9:16 Douyin/TikTok clips)
  across multiple timestamps so the subject is never clipped.
- Upscales sub-HD videos to crisp Full HD (>= 1080px short edge, e.g. 1080x1920 @ 15 Mbps) using Lanczos +
  3D temporal/spatial compression denoiser (`hqdn3d`) + AMD FidelityFX Contrast-Adaptive Sharpening (`cas`) +
  flattering portrait glow (`eq`).
- Optional horizontal mirror (`hflip`) for anti-duplicate reup framing.
- 4 Audio Copyright modes:
  1. `replace_bgm`: Replaces 100% of original audio with a royalty-free preset track or user's custom MP3/M4A/WAV
     (seamless loop + start offset + smooth fade-in/out).
  2. `anti_id_shift`: Keeps dance sync while shifting pitch (+3.8%), micro-tempo, and EQ warmth.
  3. `mute`: Strips audio completely so trending music can be added inside YouTube Shorts mobile app.
  4. `keep_original`: Preserves original audio untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Optional

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

import cv2
import numpy as np


def probe_media(video_path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=index,codec_type,width,height,r_frame_rate,side_data_list:format=duration,bit_rate",
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

    dur_raw = (data.get("format") or {}).get("duration")
    duration_s = max(0.3, float(dur_raw) if dur_raw else 10.0)
    fps_str = str(v_stream.get("r_frame_rate") or "30/1")
    if "/" in fps_str:
        num, den = fps_str.split("/", 1)
        fps = float(num) / max(1.0, float(den))
    else:
        fps = float(fps_str or 30.0)

    return {
        "width": w,
        "height": h,
        "duration_s": duration_s,
        "fps": min(60.0, max(15.0, round(fps, 2))),
        "has_audio": has_audio,
    }


def detect_active_content_box(video_path: Path, orig_w: int, orig_h: int, duration_s: float) -> Optional[tuple[int, int, int, int]]:
    """
    Sample up to 6 frames across the video to safely find pure black pillarbox/letterbox bars
    without ever clipping moving limbs/hair. Returns `(crop_w, crop_h, x0, y0)` or `None` if no bars.
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
    stack = np.frombuffer(proc.stdout[: n_frames * frame_bytes], dtype=np.uint8).reshape((n_frames, an_h, an_w))
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
        return (cw, ch, x0, y0)
    return None


def compute_crop_and_scale(
    orig_w: int,
    orig_h: int,
    crop_mode: str,
    detected_box: Optional[tuple[int, int, int, int]],
) -> tuple[Optional[str], int, int, bool]:
    """
    Returns `(crop_filter_or_None, target_hd_w, target_hd_h, did_crop_bars)`.
    Guarantees even Full HD output dimensions (short edge == 1080px).
    """
    work_w, work_h = orig_w, orig_h
    crop_filter: Optional[str] = None
    did_crop = False

    if crop_mode == "auto_remove_bars" and detected_box is not None:
        cw, ch, x0, y0 = detected_box
        # If pillarboxed vertical content is very close to 9:16, snap cleanly to 9:16
        ratio = cw / float(max(1, ch))
        target_916 = 9.0 / 16.0
        if 0.48 <= ratio <= 0.66 and ch >= orig_h * 0.85:
            ideal_w = min(orig_w, int(round(ch * target_916)) // 2 * 2)
            cx = x0 + cw // 2
            nx0 = max(0, min(orig_w - ideal_w, (cx - ideal_w // 2) // 2 * 2))
            cw, x0 = ideal_w, nx0
        crop_filter = f"crop={cw}:{ch}:{x0}:{y0}"
        work_w, work_h = cw, ch
        did_crop = True
    elif crop_mode == "force_9_16":
        base_box = detected_box if detected_box is not None else (orig_w, orig_h, 0, 0)
        bw, bh, bx0, by0 = base_box
        target_ratio = 9.0 / 16.0
        cur_ratio = bw / float(max(1, bh))
        if abs(cur_ratio - target_ratio) > 0.02 or detected_box is not None:
            if cur_ratio > target_ratio:
                nw = max(64, int(round(bh * target_ratio)) // 2 * 2)
                nh = bh // 2 * 2
                nx = (bx0 + (bw - nw) // 2) // 2 * 2
                ny = by0 // 2 * 2
            else:
                nw = bw // 2 * 2
                nh = max(64, int(round(bw / target_ratio)) // 2 * 2)
                nx = bx0 // 2 * 2
                ny = (by0 + (bh - nh) // 2) // 2 * 2
            crop_filter = f"crop={nw}:{nh}:{nx}:{ny}"
            work_w, work_h = nw, nh
            did_crop = True

    # Compute Full HD target dimensions (short edge = 1080px, e.g. 1080x1920 or 1920x1080)
    short_edge = min(work_w, work_h)
    scale = 1080.0 / float(max(1, short_edge))
    tw = max(2, int(round((work_w * scale) / 2.0) * 2))
    th = max(2, int(round((work_h * scale) / 2.0) * 2))
    if abs(tw - 1080) <= 4:
        tw = 1080
    if abs(th - 1920) <= 6:
        th = 1920
    if abs(tw - 1920) <= 6:
        tw = 1920
    if abs(th - 1080) <= 4:
        th = 1080

    return crop_filter, tw, th, did_crop


def has_videotoolbox() -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return "h264_videotoolbox" in (proc.stdout or "")


def run_remaster(args: argparse.Namespace) -> None:
    t0 = time.time()
    in_path = Path(args.video).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta = probe_media(in_path)
    orig_w, orig_h = meta["width"], meta["height"]
    dur_s = meta["duration_s"]
    has_audio = meta["has_audio"]

    detected_box = (
        detect_active_content_box(in_path, orig_w, orig_h, dur_s)
        if args.crop_mode in ("auto_remove_bars", "force_9_16")
        else None
    )
    crop_flt, tw, th, did_crop = compute_crop_and_scale(
        orig_w, orig_h, args.crop_mode, detected_box
    )

    vf_parts: list[str] = []
    if crop_flt:
        vf_parts.append(crop_flt)
    if args.mirror:
        vf_parts.append("hflip")

    if args.quality_preset == "beauty_hd":
        vf_parts.extend(
            [
                "hqdn3d=2.2:1.8:3.0:2.4",
                f"scale={tw}:{th}:flags=lanczos",
                "cas=0.52",
                "eq=brightness=0.020:contrast=1.035:saturation=1.07:gamma=1.03",
            ]
        )
    elif args.quality_preset == "crisp_hd":
        vf_parts.extend(
            [
                "hqdn3d=1.4:1.2:2.2:1.8",
                f"scale={tw}:{th}:flags=lanczos",
                "cas=0.70",
                "eq=contrast=1.04:saturation=1.05",
            ]
        )
    else:
        vf_parts.append(f"scale={tw}:{th}:flags=lanczos")

    vf_chain = ",".join(vf_parts)

    use_vt = has_videotoolbox()
    v_enc = (
        [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            "15M",
            "-maxrate",
            "20M",
            "-bufsize",
            "30M",
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
            "17",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
        ]
    )

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(in_path)]

    audio_mode = args.audio_mode
    fade_out_st = max(0.0, dur_s - 0.85)

    if audio_mode == "replace_bgm":
        if not args.bgm_path:
            raise ValueError("Chế độ thay nhạc nền yêu cầu chọn bài nhạc nền (--bgm-path).")
        bgm_file = Path(args.bgm_path).expanduser().resolve()
        if not bgm_file.exists():
            raise FileNotFoundError(f"Không tìm thấy file nhạc nền: {bgm_file}")

        bgm_ss = max(0.0, float(args.bgm_start or 0.0))
        bgm_vol = max(0.1, min(2.0, float(args.bgm_volume or 1.0)))
        orig_mix = max(0.0, min(0.6, float(args.orig_mix or 0.0)))

        cmd.extend(["-stream_loop", "-1", "-ss", f"{bgm_ss:.2f}", "-i", str(bgm_file)])

        if orig_mix > 0.01 and has_audio:
            af_complex = (
                f"[0:a]volume={orig_mix:.2f}[oa];"
                f"[1:a]atrim=0:{dur_s:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out_st:.3f}:d=0.85,"
                f"volume={bgm_vol:.2f}[ba];"
                f"[oa][ba]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
            cmd.extend(
                [
                    "-filter_complex",
                    f"[0:v]{vf_chain}[vout];{af_complex}",
                    "-map",
                    "[vout]",
                    "-map",
                    "[aout]",
                ]
            )
        else:
            af_bgm = (
                f"atrim=0:{dur_s:.3f},asetpts=PTS-STARTPTS,"
                f"afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out_st:.3f}:d=0.85,"
                f"volume={bgm_vol:.2f}"
            )
            cmd.extend(
                [
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-vf",
                    vf_chain,
                    "-af",
                    af_bgm,
                    "-shortest",
                ]
            )
        cmd.extend([*v_enc, "-c:a", "aac", "-b:a", "192k", "-ar", "44100"])

    elif audio_mode == "anti_id_shift":
        cmd.extend(["-vf", vf_chain, *v_enc])
        if has_audio:
            # +3.8% pitch shift + gentle tempo compensation + warm stereo echo EQ
            af_shift = (
                "asetrate=44100*1.038,aresample=44100,atempo=0.985,"
                "equalizer=f=125:width_type=o:width=2:g=1.6,"
                "equalizer=f=9000:width_type=o:width=2:g=1.4,"
                f"afade=t=out:st={fade_out_st:.3f}:d=0.5"
            )
            cmd.extend(["-af", af_shift, "-c:a", "aac", "-b:a", "192k", "-ar", "44100"])
        else:
            cmd.append("-an")

    elif audio_mode == "mute":
        cmd.extend(["-vf", vf_chain, *v_enc, "-an"])

    else:
        # `keep_original`
        cmd.extend(["-vf", vf_chain, *v_enc])
        if has_audio:
            cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "44100"])
        else:
            cmd.append("-an")

    cmd.extend(["-t", f"{dur_s:.3f}", "-movflags", "+faststart", str(out_path)])

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "FFmpeg remaster error").strip()[:600])

    elapsed_s = round(time.time() - t0, 2)
    size_mb = round(out_path.stat().st_size / (1024.0 * 1024.0), 2)

    print(
        json.dumps(
            {
                "ok": True,
                "out_file": out_path.name,
                "out_path": str(out_path),
                "orig_width": orig_w,
                "orig_height": orig_h,
                "out_width": tw,
                "out_height": th,
                "did_crop_bars": did_crop,
                "duration_s": round(dur_s, 2),
                "size_mb": size_mb,
                "elapsed_s": elapsed_s,
                "encoder": "Apple M2 VideoToolbox" if use_vt else "libx264",
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--quality-preset",
        default="beauty_hd",
        choices=["beauty_hd", "crisp_hd", "clean_upscale"],
    )
    parser.add_argument(
        "--crop-mode",
        default="auto_remove_bars",
        choices=["auto_remove_bars", "force_9_16", "keep_original"],
    )
    parser.add_argument("--mirror", action="store_true")
    parser.add_argument(
        "--audio-mode",
        default="replace_bgm",
        choices=["replace_bgm", "anti_id_shift", "mute", "keep_original"],
    )
    parser.add_argument("--bgm-path", default="")
    parser.add_argument("--bgm-start", type=float, default=0.0)
    parser.add_argument("--bgm-volume", type=float, default=1.0)
    parser.add_argument("--orig-mix", type=float, default=0.0)

    args = parser.parse_args()
    try:
        run_remaster(args)
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
