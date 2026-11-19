#!/usr/bin/env python3
"""
2.5D Anime Character Idle Animator & 1080p Video Composer (`render_ki_idle_video.py`).

Brings static AI character art (Goku, Luffy, etc.) to life with fighting-game / Live2D-style
idle motion so the video is NEVER a frozen still image:
  1. Chest & shoulder rhythmic breathing deformation (face protected from distortion, gentle head bob).
  2. Hair spikes & gi/sash wind ripple in the rising Ki updraft.
  3. Upward roaring Ki aura flame turbulence + rhythmic power glow pulse.
  4. Rising glowing Ki energy orbs/sparks & optional crackling bio-lightning arcs.
  5. Seamless 3.0s (90 frames @ 30fps) loop hardware-encoded via Apple Silicon VideoToolbox to 1920x1080 MP4,
     OR full pass-through if the user provides an animated MP4/WebM character loop!
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("OPENCV_LOG_LEVEL", "OFF")

import cv2
import numpy as np


def hex_to_bgr(hex_str: str) -> tuple[int, int, int]:
    h = (hex_str or "#38bdf8").strip().lstrip("#")
    if len(h) != 6:
        return (248, 189, 56)
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b, g, r)


def has_videotoolbox() -> bool:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return "h264_videotoolbox" in (proc.stdout or "")


def fit_cover_bgr(
    img_bgr: np.ndarray, target_w: int, target_h: int, shift_x: int = 0
) -> np.ndarray:
    ih, iw = img_bgr.shape[:2]
    scale = max(float(target_w) / float(max(1, iw)), float(target_h) / float(max(1, ih)))
    nw = max(target_w, int(round(iw * scale)))
    nh = max(target_h, int(round(ih * scale)))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    x0 = (nw - target_w) // 2
    y0 = max(0, int((nh - target_h) * 0.10))
    cropped = resized[y0 : y0 + target_h, x0 : x0 + target_w].copy()
    if shift_x != 0:
        M = np.float32([[1, 0, float(shift_x)], [0, 1, 0.0]])
        cropped = cv2.warpAffine(
            cropped,
            M,
            (target_w, target_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
    return cropped


def make_mystery_silhouette(img_bgr: np.ndarray, aura_bgr: tuple[int, int, int]) -> np.ndarray:
    """
    Creates a true pitch-black anime character silhouette surrounded by a glowing colored Ki aura rim.
    Uses `isnet-anime.onnx` when cached in `~/.u2net/isnet-anime.onnx`, falling back cleanly to GrabCut.
    """
    h, w = img_bgr.shape[:2]
    fg: np.ndarray | None = None

    onnx_path = Path.home() / ".u2net" / "isnet-anime.onnx"
    if onnx_path.exists():
        try:
            import onnxruntime as ort  # type: ignore

            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            in_name = sess.get_inputs()[0].name
            rgb = (
                cv2.cvtColor(cv2.resize(img_bgr, (1024, 1024)), cv2.COLOR_BGR2RGB).astype(
                    np.float32
                )
                / 255.0
            )
            inp = rgb.transpose(2, 0, 1)[None, ...]
            pred = sess.run(None, {in_name: inp})[0][0, 0]
            pred = (pred - pred.min()) / max(1e-6, float(pred.max() - pred.min()))
            fg = cv2.resize(pred.astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
        except Exception:
            fg = None

    if fg is None:
        sw, sh = 240, 270
        small = cv2.resize(img_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
        mask = np.zeros((sh, sw), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        rect = (int(sw * 0.12), int(sh * 0.02), int(sw * 0.76), int(sh * 0.97))
        cv2.grabCut(small, mask, rect, bgd_model, fgd_model, 3, cv2.GC_INIT_WITH_RECT)
        fg_small = np.where((mask == cv2.GC_BGD) | (mask == cv2.GC_PR_BGD), 0.0, 1.0).astype(
            np.float32
        )
        fg = cv2.GaussianBlur(
            cv2.resize(fg_small, (w, h), interpolation=cv2.INTER_LINEAR), (0, 0), sigmaX=3.5
        )

    k_size = max(31, int(round(w * 0.065)) | 1)
    dil = cv2.dilate(
        (fg > 0.40).astype(np.uint8) * 255,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_size, k_size)),
    )
    halo = cv2.GaussianBlur(dil.astype(np.float32) / 255.0, (0, 0), sigmaX=max(8.0, w * 0.038))
    edge = np.clip(halo - fg, 0.0, 1.0)

    bg_dark = img_bgr.astype(np.float32) * 0.22
    aura_col = np.array(aura_bgr, dtype=np.float32)[None, None, :]
    white_col = np.array([255.0, 255.0, 255.0], dtype=np.float32)[None, None, :]
    with_halo = (
        bg_dark
        + halo[:, :, None] * aura_col * 0.88
        + (edge[:, :, None] ** 1.4) * (aura_col * 0.85 + white_col * 0.30)
    )

    inner = np.clip((fg - 0.32) / 0.24, 0.0, 1.0)[:, :, None]
    sil_color = np.array([12.0, 9.0, 7.0], dtype=np.float32)[None, None, :]
    out = with_halo * (1.0 - inner) + sil_color * inner
    return np.clip(out, 0, 255).astype(np.uint8)


class CharacterIdleAnimator:
    """
    Precomputes spatial masks for a `(w, h)` portrait card and synthesizes smooth 30fps
    anatomical breathing, hair/cloth wind sway, rising Ki aura shimmer, particles & lightning.
    """

    def __init__(
        self,
        base_bgr: np.ndarray,
        w: int,
        h: int,
        aura_bgr: tuple[int, int, int],
        motion_scale: float = 1.0,
        enable_lightning: bool = False,
        seed: int = 42,
        shift_x: int = 0,
    ):
        self.w = w
        self.h = h
        self.base = fit_cover_bgr(base_bgr, w, h, shift_x=shift_x)
        self.aura_bgr = np.array(aura_bgr, dtype=np.float32)
        self.motion_scale = motion_scale
        self.enable_lightning = enable_lightning

        # Coordinate grids
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        self.xx = xx
        self.yy = yy
        nx = xx / float(max(1, w))  # 0..1
        ny = yy / float(max(1, h))  # 0..1
        self.nx = nx
        self.ny = ny

        # 1. Face & Character rigid protection: keep 2D cel ink lines 100% crisp (NO wavy jelly distortion!)
        # Gentle vertical breathing/floating motion only (peaks at chest/head, planted at boots)
        ground_anchor = np.clip((0.92 - ny) / 0.14, 0.0, 1.0).astype(np.float32)
        body_d2 = ((nx - 0.50) / 0.36) ** 2 + ((ny - 0.36) / 0.38) ** 2
        self.upper_body_mask = (np.exp(-0.5 * body_d2) * ground_anchor).astype(np.float32)

        # Very subtle chest breathing expansion (no face/hair/arm line warping)
        face_protect = np.exp(-0.5 * (((nx - 0.50) / 0.16) ** 2 + ((ny - 0.18) / 0.10) ** 2))
        chest_d2 = ((nx - 0.50) / 0.24) ** 2 + ((ny - 0.38) / 0.14) ** 2
        self.chest_mask = (
            np.exp(-0.5 * chest_d2).astype(np.float32)
            * (1.0 - face_protect)
            * ground_anchor
        )

        self.edge_safe = (
            np.clip(nx / 0.05, 0.0, 1.0)
            * np.clip((1.0 - nx) / 0.05, 0.0, 1.0)
            * np.clip(ny / 0.05, 0.0, 1.0)
            * np.clip((1.0 - ny) / 0.05, 0.0, 1.0)
        ).astype(np.float32)

        # Extract ONLY the outer glowing aura region (excluding solid character ink/skin/gi) for rhythmic glow pulse
        core_body = np.exp(-0.5 * (((nx - 0.50) / 0.18) ** 2 + ((ny - 0.48) / 0.36) ** 2))
        base_f = self.base.astype(np.float32) / 255.0
        luma = cv2.cvtColor(self.base, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        sat = np.max(base_f, axis=2) - np.min(base_f, axis=2)
        corner_luma = float(np.median(luma[:24, :24]))

        if corner_luma > 0.50:
            diff_bg = np.abs(luma - corner_luma)
            aura_raw = np.clip((sat - 0.10) * 2.5 + np.clip(luma - corner_luma - 0.04, 0.0, 1.0) * 3.0, 0.0, 1.0)
            aura_bright = aura_raw * (1.0 - 0.85 * core_body) * np.clip(diff_bg * 5.0, 0.0, 1.0)
        else:
            aura_bright = np.clip((luma - 0.24) / 0.55, 0.0, 1.0) * (1.0 - 0.78 * core_body)

        self.aura_glow_layer = cv2.GaussianBlur(aura_bright.astype(np.float32), (0, 0), sigmaX=10.0)[
            :, :, None
        ]

        # Deterministic subtle fine Ki embers (clean, understated, non-distracting)
        rng = np.random.default_rng(seed)
        n_particles = 14 if motion_scale >= 0.8 else 6
        self.particles = []
        for _ in range(n_particles):
            self.particles.append(
                {
                    "x0": float(rng.uniform(0.15, 0.85)),
                    "y0": float(rng.uniform(0.0, 1.0)),
                    "speed_cycles": int(rng.choice([1, 2])),
                    "radius": int(rng.integers(1, 4)),
                    "amp_x": float(rng.uniform(0.008, 0.022)),
                    "phase": float(rng.uniform(0.0, 2.0 * math.pi)),
                    "alpha": float(rng.uniform(0.30, 0.70)),
                }
            )

        self.rng = np.random.default_rng(seed + 999)

    def render_frame(self, phase_0_1: float, frame_idx: int) -> np.ndarray:
        """
        `phase_0_1` in `[0.0, 1.0)` represents position in the 3.0-second seamless loop!
        All frequencies are integer multiples of `2 * pi * phase_0_1` -> 100% seamless loop!
        """
        theta = 2.0 * math.pi * phase_0_1
        ms = self.motion_scale

        # 1) Clean rigid-style fighting-stance breathing & subtle float (ZERO wavy ink-line distortion!)
        breath = math.sin(theta)  # -1..+1
        bob_dy = -3.2 * ms * breath * self.upper_body_mask
        chest_expand_dx = 1.4 * ms * breath * ((self.nx - 0.50) / 0.24) * self.chest_mask
        chest_lift_dy = -1.6 * ms * breath * self.chest_mask

        total_dx = chest_expand_dx * self.edge_safe
        total_dy = (bob_dy + chest_lift_dy) * self.edge_safe

        # Note: subtract displacement in inverse-mapping `remap` so positive dy moves visual content down/up naturally
        map_x = (self.xx - total_dx).astype(np.float32)
        map_y = (self.yy - total_dy).astype(np.float32)

        warped = cv2.remap(
            self.base,
            map_x,
            map_y,
            interpolation=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )

        # 4) Rhythmic Ki Aura Glow Pulse (2 cycles per 3.0s)
        pulse = 0.5 + 0.5 * math.sin(2.0 * theta)
        glow_strength = (0.08 + 0.16 * pulse) * ms
        out_f = warped.astype(np.float32) + self.aura_glow_layer * self.aura_bgr[None, None, :] * glow_strength

        # Subtle upward moving light bands on aura ring
        wave_band = (0.5 + 0.5 * np.sin(self.ny * 14.0 - 3.0 * theta))[:, :, None]
        out_f += (
            wave_band
            * self.aura_glow_layer
            * self.aura_bgr[None, None, :]
            * (0.10 * ms)
        )
        frame = np.clip(out_f, 0, 255).astype(np.uint8)

        # 5) Rising Ki Sparks / Orbs
        particle_overlay = frame.copy()
        bright_core = tuple(int(min(255, c * 0.5 + 140)) for c in self.aura_bgr)
        outer_col = tuple(int(c) for c in self.aura_bgr)

        for p in self.particles:
            prog = (p["y0"] - phase_0_1 * p["speed_cycles"]) % 1.0
            py = int(prog * self.h)
            px_norm = p["x0"] + p["amp_x"] * math.sin(2.0 * math.pi * prog * 2.0 + p["phase"])
            px = int(max(4, min(self.w - 5, px_norm * self.w)))
            # Fade in at bottom, fade out at top
            edge_fade = math.sin(prog * math.pi)
            alpha = p["alpha"] * edge_fade * min(1.0, ms * 1.1)
            if alpha < 0.08:
                continue
            r = p["radius"]
            cv2.circle(particle_overlay, (px, py), r + 3, outer_col, -1, lineType=cv2.LINE_AA)
            cv2.circle(particle_overlay, (px, py), max(1, r - 1), bright_core, -1, lineType=cv2.LINE_AA)

        frame = cv2.addWeighted(particle_overlay, 0.55, frame, 0.45, 0)

        # 6) Optional Crackling Bio-Lightning Arcs (intermittent bursts)
        if self.enable_lightning and (frame_idx % 14 in (0, 1, 2, 7, 8)):
            bolt_layer = np.zeros_like(frame)
            bolt_rng = np.random.default_rng(1000 + (frame_idx // 2) * 37)
            for _ in range(2):
                bx = int(bolt_rng.integers(int(self.w * 0.18), int(self.w * 0.82)))
                by = int(bolt_rng.integers(int(self.h * 0.18), int(self.h * 0.72)))
                pts = [(bx, by)]
                for _s in range(6):
                    bx += int(bolt_rng.integers(-28, 29))
                    by += int(bolt_rng.integers(14, 38))
                    bx = max(8, min(self.w - 8, bx))
                    by = max(8, min(self.h - 8, by))
                    pts.append((bx, by))
                pts_np = np.array(pts, dtype=np.int32)
                cv2.polylines(bolt_layer, [pts_np], False, (255, 225, 90), 4, lineType=cv2.LINE_AA)
                cv2.polylines(bolt_layer, [pts_np], False, (255, 255, 255), 2, lineType=cv2.LINE_AA)
            bolt_glow = cv2.GaussianBlur(bolt_layer, (0, 0), sigmaX=3.0)
            frame = cv2.add(frame, bolt_glow)

        return frame


def parse_box(box_str: str) -> tuple[int, int, int, int]:
    parts = [int(round(float(x))) for x in box_str.split(",")]
    return parts[0], parts[1], parts[2], parts[3]


def is_video_file(p: Path) -> bool:
    return p.suffix.lower() in {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def main() -> None:
    t0 = time.time()
    parser = argparse.ArgumentParser()
    parser.add_argument("--silhouette-only", default="", help="Generate only 960x1080 silhouette JPG for input image")
    parser.add_argument("--ui-overlay", default="", help="1920x1080 RGBA PNG with transparent character slots")
    parser.add_argument("--current-media", default="", help="Image or video path for Current Form")
    parser.add_argument("--next-media", default="", help="Image path for Next Form")
    parser.add_argument("--out", required=True, help="Output 1920x1080 MP4 (or silhouette JPG) path")
    parser.add_argument("--left-box", default="0,0,960,1080")
    parser.add_argument("--right-box", default="960,0,960,1080")
    parser.add_argument("--current-aura", default="#38bdf8")
    parser.add_argument("--next-aura", default="#facc15")
    parser.add_argument("--mystery-next", default="false")
    parser.add_argument("--lightning", default="false")
    parser.add_argument("--duration", type=int, default=15)
    parser.add_argument(
        "--audio-mode",
        default="epic_hum",
        choices=["epic_hum", "builtin_bgm", "custom_audio", "silent"],
    )
    parser.add_argument("--bgm-path", default="")
    parser.add_argument("--audio-start", type=float, default=0.0)
    parser.add_argument("--audio-end", type=float, default=0.0)

    args = parser.parse_args()

    try:
        if args.silhouette_only:
            src_img = cv2.imread(str(Path(args.silhouette_only).resolve()), cv2.IMREAD_COLOR)
            if src_img is None:
                raise RuntimeError("Không đọc được ảnh nhân vật để tạo bóng đen.")
            sil_bgr = make_mystery_silhouette(fit_cover_bgr(src_img, 960, 1080), hex_to_bgr(args.next_aura))
            out_sil = Path(args.out).resolve()
            out_sil.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out_sil), sil_bgr, [cv2.IMWRITE_JPEG_QUALITY, 93])
            print(json.dumps({"ok": True, "out_path": str(out_sil)}))
            return
        overlay_rgba = cv2.imread(str(Path(args.ui_overlay).resolve()), cv2.IMREAD_UNCHANGED)
        if overlay_rgba is None or overlay_rgba.shape[2] < 4:
            raise RuntimeError("Không đọc được lớp giao diện RGBA.")
        oh, ow = overlay_rgba.shape[:2]
        if (ow, oh) not in ((1920, 1080), (1080, 1920)):
            target_size = (1080, 1920) if oh > ow else (1920, 1080)
            overlay_rgba = cv2.resize(overlay_rgba, target_size, interpolation=cv2.INTER_LANCZOS4)
        out_h, out_w = overlay_rgba.shape[:2]

        ui_bgr = overlay_rgba[:, :, :3].astype(np.float32)
        ui_alpha = (overlay_rgba[:, :, 3:4].astype(np.float32)) / 255.0

        lx, ly, lw, lh = parse_box(args.left_box)
        rx, ry, rw, rh = parse_box(args.right_box)
        cur_aura = hex_to_bgr(args.current_aura)
        nxt_aura = hex_to_bgr(args.next_aura)
        mystery_next = str(args.mystery_next).lower() in ("1", "true", "yes")
        enable_lightning = str(args.lightning).lower() in ("1", "true", "yes")

        cur_path = Path(args.current_media).resolve()
        nxt_path = Path(args.next_media).resolve()

        nxt_img = cv2.imread(str(nxt_path), cv2.IMREAD_COLOR)
        if nxt_img is None:
            raise RuntimeError(f"Không đọc được ảnh cấp độ tiếp theo: {nxt_path}")
        shift_px = 72 if out_w == 1920 else 0
        if mystery_next:
            cached_sil_path = nxt_path.with_name(f"{nxt_path.stem}_sil.jpg")
            cached_sil = (
                cv2.imread(str(cached_sil_path), cv2.IMREAD_COLOR)
                if cached_sil_path.exists()
                else None
            )
            if cached_sil is not None:
                nxt_img = fit_cover_bgr(cached_sil, rw, rh, shift_x=shift_px)
            else:
                nxt_img = make_mystery_silhouette(
                    fit_cover_bgr(nxt_img, rw, rh, shift_x=shift_px), nxt_aura
                )
        else:
            nxt_img = fit_cover_bgr(nxt_img, rw, rh, shift_x=shift_px)

        right_anim = CharacterIdleAnimator(
            nxt_img,
            rw,
            rh,
            aura_bgr=nxt_aura,
            motion_scale=0.55 if mystery_next else 0.72,
            enable_lightning=False,
            seed=202,
            shift_x=0,
        )

        fps = 30
        dur_s = max(5, min(60, int(args.duration)))
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)

        use_vt = has_videotoolbox()
        v_enc = (
            [
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                "14M",
                "-maxrate",
                "18M",
                "-bufsize",
                "28M",
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

        fade_out_st = max(0.0, dur_s - 1.0)
        audio_inputs: list[str] = []
        audio_maps: list[str] = []

        if (
            args.audio_mode in ("builtin_bgm", "custom_audio")
            and args.bgm_path
            and Path(args.bgm_path).exists()
        ):
            a_start = max(0.0, float(args.audio_start or 0.0))
            a_end = float(args.audio_end or 0.0)
            if a_end > a_start + 0.3:
                trim_filter = f"atrim=start={a_start:.3f}:end={a_end:.3f},asetpts=PTS-STARTPTS,"
            elif a_start > 0.01:
                trim_filter = f"atrim=start={a_start:.3f},asetpts=PTS-STARTPTS,"
            else:
                trim_filter = ""

            audio_inputs = ["-stream_loop", "-1", "-i", str(Path(args.bgm_path).resolve())]
            audio_maps = [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-af",
                (
                    f"{trim_filter}"
                    f"aloop=loop=-1:size=2000000000,"
                    f"atrim=0:{dur_s},asetpts=PTS-STARTPTS,"
                    f"afade=t=in:st=0:d=0.35,afade=t=out:st={fade_out_st}:d=0.9,volume=0.90"
                ),
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]
        elif args.audio_mode == "epic_hum":
            expr = (
                "0.16*sin(2*PI*55*t)*(0.7+0.3*sin(2*PI*1.8*t))"
                "+0.10*sin(2*PI*110*t)"
                "+0.06*sin(2*PI*165*t)*(0.6+0.4*sin(2*PI*0.9*t))"
            )
            audio_inputs = ["-f", "lavfi", "-i", f"aevalsrc='{expr}':s=44100:d={dur_s}"]
            audio_maps = [
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-af",
                f"lowpass=f=920,afade=t=in:st=0:d=0.5,afade=t=out:st={fade_out_st}:d=1.0",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
            ]
        else:
            audio_maps = ["-map", "0:v:0", "-an"]

        if not is_video_file(cur_path):
            # Fast 90-frame (3.0s @ 30fps) seamless 2.5D Idle loop -> hardware encode full `dur_s`!
            cur_img = cv2.imread(str(cur_path), cv2.IMREAD_COLOR)
            if cur_img is None:
                raise RuntimeError(f"Không đọc được ảnh nhân vật hiện tại: {cur_path}")

            left_anim = CharacterIdleAnimator(
                cur_img,
                lw,
                lh,
                aura_bgr=cur_aura,
                motion_scale=1.0,
                enable_lightning=enable_lightning,
                seed=101,
                shift_x=-shift_px,
            )

            loop_frames = 90  # Exact 3.0s @ 30fps
            loop_mp4 = out_path.with_name(f"_loop_tmp_{out_path.stem}.mp4")

            loop_cmd = [
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
                f"{out_w}x{out_h}",
                "-r",
                str(fps),
                "-i",
                "-",
                "-vf",
                "setsar=1",
                *v_enc,
                "-an",
                str(loop_mp4),
            ]
            enc_loop = subprocess.Popen(loop_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert enc_loop.stdin is not None

            canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
            for idx in range(loop_frames):
                phase = idx / float(loop_frames)
                l_card = left_anim.render_frame(phase, idx)
                r_card = right_anim.render_frame(phase, idx)

                canvas.fill(10)
                canvas[ly : ly + lh, lx : lx + lw] = l_card
                canvas[ry : ry + rh, rx : rx + rw] = r_card

                # Composite crisp UI overlay RGBA over animated character viewports
                comp = canvas.astype(np.float32) * (1.0 - ui_alpha) + ui_bgr * ui_alpha
                enc_loop.stdin.write(comp.astype(np.uint8).tobytes())

            enc_loop.stdin.close()
            loop_err = enc_loop.stderr.read().decode("utf-8", errors="ignore") if enc_loop.stderr else ""
            if enc_loop.wait() != 0:
                raise RuntimeError(loop_err.strip()[:400] or "Lỗi dựng vòng lặp Idle 3s")

            # Mux seamless video loop (-stream_loop -1 -c:v copy!) + full-length audio in 0.2s!
            mux_cmd = [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-stream_loop",
                "-1",
                "-i",
                str(loop_mp4),
                *audio_inputs,
                *audio_maps,
                "-c:v",
                "copy",
                "-t",
                str(dur_s),
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            mux_proc = subprocess.run(mux_cmd, capture_output=True, text=True)
            try:
                loop_mp4.unlink(missing_ok=True)
            except Exception:
                pass
            if mux_proc.returncode != 0:
                raise RuntimeError((mux_proc.stderr or "Lỗi ghép âm thanh video Idle").strip()[:400])

        else:
            # User provided an animated MP4/WebM character loop for Current Form!
            cap = cv2.VideoCapture(str(cur_path))
            if not cap.isOpened():
                raise RuntimeError(f"Không mở được video nhân vật: {cur_path}")

            total_frames = dur_s * fps
            full_cmd = [
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
                f"{out_w}x{out_h}",
                "-r",
                str(fps),
                "-i",
                "-",
                *audio_inputs,
                *audio_maps,
                "-vf",
                "setsar=1",
                *v_enc,
                "-t",
                str(dur_s),
                "-movflags",
                "+faststart",
                str(out_path),
            ]
            enc_full = subprocess.Popen(full_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            assert enc_full.stdin is not None

            canvas = np.zeros((out_h, out_w, 3), dtype=np.uint8)
            for idx in range(total_frames):
                ok, vframe = cap.read()
                if not ok or vframe is None:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, vframe = cap.read()
                if vframe is None:
                    break
                l_card = fit_cover_bgr(vframe, lw, lh)
                r_card = right_anim.render_frame((idx % 90) / 90.0, idx)

                canvas.fill(10)
                canvas[ly : ly + lh, lx : lx + lw] = l_card
                canvas[ry : ry + rh, rx : rx + rw] = r_card
                comp = canvas.astype(np.float32) * (1.0 - ui_alpha) + ui_bgr * ui_alpha
                enc_full.stdin.write(comp.astype(np.uint8).tobytes())

            cap.release()
            enc_full.stdin.close()
            full_err = enc_full.stderr.read().decode("utf-8", errors="ignore") if enc_full.stderr else ""
            if enc_full.wait() != 0:
                raise RuntimeError(full_err.strip()[:400] or "Lỗi render video clip Idle")

        elapsed_s = round(time.time() - t0, 2)
        size_mb = round(out_path.stat().st_size / (1024.0 * 1024.0), 2)
        print(
            json.dumps(
                {
                    "ok": True,
                    "out_file": out_path.name,
                    "out_path": str(out_path),
                    "size_mb": size_mb,
                    "duration_s": dur_s,
                    "elapsed_s": elapsed_s,
                }
            )
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
