#!/usr/bin/env python3
"""
Step 5A: Full-Screen Documentary Visual Compositor, Handle-Preserving Cross-Dissolve
Assembler, Clean Subtitles & Subject-First Thumbnail Exporter (`pow_studio.compositor` v3.0).

Key v3.0 architectural upgrades:
1. Driven by centralized `DocumentaryStyleProfile` (`pow_documentary_v3` by default):
   - Edge-to-edge 1080x1920 (`9:16`) composition (`video_full`, `still_full`, `diagram`).
   - Intelligent subject reframing (`auto_salient`, `keyframed`, or `manual`) via `pow_studio.reframing`.
   - Synthetic 2.5D Depth-Anything-V2 warping disabled by default; stills use restrained `<= 3.5%`
     optical drift without aspect stretching or outpainting.
2. Decorative overlays disabled by default (`0` yellow circles, `0` source banners, `0` radar-pin
   HUDs, `0` warning pills, `0` burned-in opening cover cards, `0` closing credit boxes).
   Supports optional borderless `context_note` typography (`<= 7` words) only when essential.
3. Zero-drift cross-dissolve timeline assembly (`transition_in="dissolve"`, `0.5–1.0s`):
   renders exact head/tail media handles around dissolve boundaries and merges dissolve chains
   with `ffmpeg xfade=transition=fade` so total rendered frames match `word_timings.json` to the
   single frame (`0.000 ms` narration drift).
4. Subject-first mobile thumbnail generation via `pow_studio.thumbnail_engine` (while retaining
   `legacy_v2` compatibility when requested).
"""

from __future__ import annotations

import difflib
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Literal, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from .annotations import draw_antarctica_locator, draw_scale_ring_annotation
from .color_grade import apply_documentary_color_grade
from .depth_parallax import infer_smoothed_depth, render_25d_parallax_frame
from .reframing import (
    compute_video_reframe_trajectory,
    crop_subpixel_full_canvas,
    estimate_salient_subject_center,
    interpolate_reframe_keyframes,
)
from .schema import CoverVariantSpec, EpisodeManifest, ShotSpecModel, ThumbnailSpecModel, resolve_timed_shots
from .style_profile import DocumentaryStyleProfile, load_style_profile
from .thumbnail_engine import (
    compose_subject_first_thumbnail,
    export_documentary_thumbnail_package,
    generate_thumbnail_concepts_package,
    score_thumbnail_candidate,
)
from .voice_studio import auto_build_caption_groups_from_words

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "pipeline") not in sys.path:
    sys.path.insert(0, str(ROOT / "pipeline"))
from first_frame_thumbnail import _save_youtube_444_jpeg, export_first_frame_thumbnail  # noqa: E402

FONT_ANTON = str(ROOT / "assets" / "fonts" / "Anton-Regular.ttf")
FONT_BOLD = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Bold.ttf")
FONT_MED = str(ROOT / "assets" / "fonts" / "BeVietnamPro-Medium.ttf")

W, H, FPS, SR = 1080, 1920, 30, 48000
CAPTION_BG_RGBA = (6, 10, 18, 180)
CAPTION_WHITE_RGBA = (252, 253, 255, 255)
CAPTION_EMPH_RGBA = (255, 222, 118, 255)

_FONT_CACHE: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    key = (path, size)
    if key not in _FONT_CACHE:
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key]


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd[:8])}...\n{r.stderr[-1800:]}")
    return r


def _smoothstep(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3.0 - 2.0 * u)


def _norm_token(tok: str) -> str:
    return re.sub(r"[^a-z0-9]", "", tok.lower())


def _crop_subpixel_affine(img: Image.Image, cx: float, cy: float, zoom: float, out_w: int, out_h: int) -> Image.Image:
    return crop_subpixel_full_canvas(img, cx, cy, zoom, out_w, out_h)


def _apply_selective_shadow_lift(img: Image.Image, lift: float) -> Image.Image:
    """Lift deep cave/night shadows selectively while preserving bright highlights and color saturation."""
    if lift <= 1e-3:
        return img
    arr = np.asarray(img, dtype=np.float32) / 255.0
    luma = (0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2])[..., None]
    boost = float(lift) * ((1.0 - np.clip(luma, 0.0, 1.0)) ** 2.1)
    out = np.clip(arr + boost * (1.0 - arr), 0.0, 1.0)
    return Image.fromarray((out * 255.0).astype(np.uint8))


def _open_upright_rgb(
    path: Path,
    max_long_edge: int = 3400,
    crop_box: Optional[tuple[int, int, int, int]] = None,
) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    if crop_box is not None:
        x0, y0, x1, y1 = crop_box
        im = im.crop((max(0, x0), max(0, y0), min(im.width, x1), min(im.height, y1)))
    iw, ih = im.size
    if max(iw, ih) > max_long_edge:
        scale = max_long_edge / float(max(iw, ih))
        im = im.resize((int(round(iw * scale)), int(round(ih * scale))), Image.Resampling.LANCZOS)
    return im


def _video_codec_args(
    encode_mode: Literal["draft", "master"],
    style: Optional[DocumentaryStyleProfile] = None,
) -> list[str]:
    if encode_mode == "draft":
        return [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            "10M",
            "-pix_fmt",
            "yuv420p",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
        ]
    crf = str(style.output.video_crf_master) if style else "15"
    preset = style.output.video_preset_master if style else "medium"
    return [
        "-c:v",
        "libx264",
        "-preset",
        preset,
        "-crf",
        crf,
        "-profile:v",
        "high",
        "-pix_fmt",
        "yuv420p",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
    ]


def _pipe_frames_to_mp4(
    out_mp4: Path,
    nframes: int,
    frame_gen,
    encode_mode: Literal["draft", "master"],
    style: Optional[DocumentaryStyleProfile] = None,
) -> None:
    out_w = style.output.width if style else W
    out_h = style.output.height if style else H
    fps = style.output.fps if style else FPS
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{out_w}x{out_h}",
        "-r",
        str(fps),
        "-i",
        "-",
        "-frames:v",
        str(nframes),
        *_video_codec_args(encode_mode, style),
        str(out_mp4),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    for idx in range(nframes):
        rgb = frame_gen(idx)
        proc.stdin.write(np.asarray(rgb, dtype=np.uint8).tobytes())
    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"Shot encode failed for {out_mp4} (rc={rc})")


def _apply_shot_annotations(
    base_rgb: Image.Image,
    s: ShotSpecModel,
    local_t: float,
    shot_dur: float,
    style: DocumentaryStyleProfile,
) -> Image.Image:
    use_ring = (s.scale_annotation is not None) and style.overlays.show_animated_circles_or_rings
    use_loc = (s.locator_annotation is not None) and style.overlays.show_locator_hud_cards
    if not use_ring and not use_loc:
        return base_rgb

    ov = Image.new("RGBA", base_rgb.size, (0, 0, 0, 0))
    fb_scale = get_font(FONT_BOLD, 21)
    fm_scale = get_font(FONT_MED, 18)
    fb_loc = get_font(FONT_BOLD, 20)
    fm_loc = get_font(FONT_MED, 17)
    if use_ring and s.scale_annotation is not None:
        draw_scale_ring_annotation(ov, s.scale_annotation, local_t, shot_dur, fb_scale, fm_scale)
    if use_loc and s.locator_annotation is not None:
        draw_antarctica_locator(ov, s.locator_annotation, local_t, shot_dur, fb_loc, fm_loc)
    return Image.alpha_composite(base_rgb.convert("RGBA"), ov).convert("RGB")


def _resolve_asset_path(filename: str, manifest: EpisodeManifest) -> Path:
    work_clips_dir = Path(manifest.output_dir) / "work_clips"
    candidates = [d / filename for d in manifest.all_asset_search_dirs()] + [
        Path(filename),
        ROOT / "output" / "hidden-earth" / "blood-falls-20261028" / "work_clips" / filename,
    ]
    for p in candidates:
        if p.exists():
            if p.parent != work_clips_dir and filename.endswith(".mp4") and "diagram" in filename:
                work_clips_dir.mkdir(parents=True, exist_ok=True)
                dst = work_clips_dir / filename
                if not dst.exists():
                    shutil.copy2(p, dst)
                return dst
            return p
    raise FileNotFoundError(f"Asset '{filename}' not found in {[str(d) for d in manifest.all_asset_search_dirs()]}")


def compute_transition_handles(
    timed_shots: list[ShotSpecModel],
    style: DocumentaryStyleProfile,
) -> list[dict]:
    """
    Compute exact `(nominal_frames, head_frames, tail_frames, dissolve_in_frames)` per shot
    so cross-dissolves (`xfade=transition=fade`) preserve exact cumulative speech timing (`0.000 ms` drift).
    """
    fps = style.output.fps
    n = len(timed_shots)
    nominals = [max(1, int(round(s.end_s * fps)) - int(round(s.start_s * fps))) for s in timed_shots]
    heads = [0] * n
    tails = [0] * n
    dissolves = [0] * n

    if "dissolve" not in style.pacing.allowed_transitions:
        return [
            {"nominal_frames": nominals[i], "head_frames": 0, "tail_frames": 0, "dissolve_in_frames": 0}
            for i in range(n)
        ]

    for i in range(1, n):
        s_cur = timed_shots[i]
        if s_cur.transition_in == "dissolve":
            dur_s = s_cur.transition_duration_s if s_cur.transition_duration_s > 0 else style.pacing.dissolve_duration_s
            d_frames = max(2, int(round(dur_s * fps)))
            max_safe = max(0, min(nominals[i - 1] - 4, nominals[i] - 4))
            d_frames = min(d_frames, max_safe)
            if d_frames >= 2:
                ideal_head = d_frames // 2
                if s_cur.kind in ("video_full", "video_window", "svs_flyover", "diagram", "triptych_hook"):
                    avail_pre_frames = max(0, int(s_cur.src_in * fps))
                    head_f = min(ideal_head, avail_pre_frames)
                else:
                    head_f = ideal_head
                tail_f = d_frames - head_f
                heads[i] = head_f
                tails[i - 1] = tail_f
                dissolves[i] = d_frames

    return [
        {
            "nominal_frames": nominals[i],
            "head_frames": heads[i],
            "tail_frames": tails[i],
            "dissolve_in_frames": dissolves[i],
        }
        for i in range(n)
    ]


def render_single_shot(
    s: ShotSpecModel,
    manifest: EpisodeManifest,
    encode_mode: Literal["draft", "master"] = "master",
    head_frames: int = 0,
    tail_frames: int = 0,
) -> Path:
    style = manifest.resolve_style_profile()
    out_w, out_h, fps = style.output.width, style.output.height, style.output.fps

    out_dir = Path(manifest.output_dir)
    shots_dir = out_dir / "shots"
    work_clips_dir = out_dir / "work_clips"
    scratch_dir = out_dir / ".scratch_build"
    for d in (shots_dir, work_clips_dir, scratch_dir):
        d.mkdir(parents=True, exist_ok=True)

    f0 = int(round(s.start_s * fps))
    f1 = int(round(s.end_s * fps))
    nominal_frames = max(1, f1 - f0)
    total_frames = head_frames + nominal_frames + tail_frames
    shot_dur = total_frames / float(fps)
    out_mp4 = shots_dir / f"{s.sid}.mp4"

    # Subtle optical readability gradient in lower subtitle region & very top edge
    yy = np.arange(out_h, dtype=np.float32)
    bot_grad = np.clip((yy - 1460.0) / 460.0, 0.0, 1.0)[:, None] * 0.40
    top_grad = np.clip((260.0 - yy) / 260.0, 0.0, 1.0)[:, None] * (0.24 if (s.context_note or s.chapter_stamp) else 0.10)
    keep_mult = (1.0 - np.maximum(bot_grad, top_grad))[..., None]

    if s.kind == "triptych_hook":
        band_h = out_h // 3
        band_specs = [
            (s.src_file, s.src_in, s.triptych_centers_y[0]),
            (s.secondary_src_file or s.src_file, s.secondary_src_in, s.triptych_centers_y[1]),
            (s.tertiary_src_file or s.src_file, s.tertiary_src_in, s.triptych_centers_y[2]),
        ]
        band_sources: list[dict] = []
        tmp_dirs_to_clean: list[Path] = []
        for b_idx, (b_file, b_in, b_cy) in enumerate(band_specs):
            b_path = _resolve_asset_path(b_file, manifest)
            if b_path.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
                b_tmp = scratch_dir / f"trip_{s.sid}_{b_idx}"
                shutil.rmtree(b_tmp, ignore_errors=True)
                b_tmp.mkdir(parents=True, exist_ok=True)
                tmp_dirs_to_clean.append(b_tmp)
                act_in = max(0.0, b_in - (head_frames / float(fps)))
                run_cmd(
                    [
                        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-ss", f"{act_in:.3f}", "-t", f"{shot_dur + 0.35:.3f}",
                        "-i", str(b_path), "-vf", f"fps={fps}",
                        str(b_tmp / "f_%04d.png"),
                    ]
                )
                ffs = sorted(b_tmp.glob("f_*.png"))
                if not ffs:
                    raise RuntimeError(f"Zero frames extracted for triptych band {b_idx} ({b_file})")
                band_sources.append({"is_video": True, "frames": ffs, "cy": b_cy})
            else:
                b_im = _open_upright_rgb(b_path, max_long_edge=3200)
                if s.shadow_lift > 1e-3:
                    b_im = _apply_selective_shadow_lift(b_im, s.shadow_lift)
                band_sources.append({"is_video": False, "img": b_im, "cy": b_cy})

        f_lbl = get_font(FONT_BOLD, 20)

        def gen_triptych(i: int) -> Image.Image:
            u = _smoothstep(i / max(1, total_frames - 1))
            canvas = Image.new("RGB", (out_w, out_h), (8, 10, 14))
            for b_idx, bsrc in enumerate(band_sources):
                bh = band_h if b_idx < 2 else (out_h - 2 * band_h)
                by0 = b_idx * band_h
                dir_sign = 1.0 if (b_idx % 2 == 0) else -1.0
                bcx = 0.50 + dir_sign * (u - 0.5) * 0.04
                bcy = float(bsrc["cy"])
                bzz = 1.04 + 0.05 * u
                if bsrc["is_video"]:
                    ffs = bsrc["frames"]
                    raw_b = Image.open(ffs[min(i, len(ffs) - 1)]).convert("RGB")
                    if s.shadow_lift > 1e-3:
                        raw_b = _apply_selective_shadow_lift(raw_b, s.shadow_lift * 0.7)
                    tile = crop_subpixel_full_canvas(raw_b, bcx, bcy, bzz, out_w, bh)
                else:
                    tile = crop_subpixel_full_canvas(bsrc["img"], bcx, bcy, bzz, out_w, bh)
                if abs(s.contrast_gain - 1.0) > 1e-3:
                    tile = ImageEnhance.Contrast(tile).enhance(s.contrast_gain)
                canvas.paste(tile, (0, by0))

            canvas = apply_documentary_color_grade(
                canvas,
                frame_idx=f0 + i,
                enable_grade=style.color_science.enable_filmic_grade,
                cast_tame_strength=style.color_science.cast_tame_strength,
                luma_grain_sigma=style.color_science.luma_grain_sigma,
            )
            arr = (np.asarray(canvas, dtype=np.float32) * keep_mult).astype(np.uint8)
            comp = Image.fromarray(arr).convert("RGBA")
            ov = Image.new("RGBA", (out_w, out_h), (0, 0, 0, 0))
            od = ImageDraw.Draw(ov)
            for div_y in (band_h, 2 * band_h):
                od.rectangle((0, div_y - 2, out_w, div_y + 1), fill=(255, 218, 108, 196))
            for b_idx, lbl_txt in enumerate(s.triptych_labels[:3]):
                if not lbl_txt:
                    continue
                ly = b_idx * band_h + 22
                sh = Image.new("RGBA", (540, 56), (0, 0, 0, 0))
                sd = ImageDraw.Draw(sh)
                sd.text((18, 12), lbl_txt, font=f_lbl, fill=(4, 8, 14, 215), stroke_width=8, stroke_fill=(4, 8, 14, 215))
                sh = sh.filter(ImageFilter.GaussianBlur(radius=7))
                ov.alpha_composite(sh, (22, max(0, ly - 12)))
                od = ImageDraw.Draw(ov)
                od.rectangle((36, ly + 2, 40, ly + 24), fill=(255, 214, 68, 245))
                od.text((50, ly), lbl_txt, font=f_lbl, fill=(248, 250, 255, 244), stroke_width=2, stroke_fill=(6, 10, 18, 230))
            return Image.alpha_composite(comp, ov).convert("RGB")

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_triptych, encode_mode, style)
        for td in tmp_dirs_to_clean:
            shutil.rmtree(td, ignore_errors=True)
        return out_mp4

    if s.kind in ("still_parallax_25d", "still_full"):
        src_path = _resolve_asset_path(s.src_file, manifest)
        src_im = _open_upright_rgb(src_path, max_long_edge=3400, crop_box=s.crop_box)
        if s.shadow_lift > 1e-3:
            src_im = _apply_selective_shadow_lift(src_im, s.shadow_lift)

        if s.reframe_mode == "auto_salient":
            scx, scy = estimate_salient_subject_center(src_im)
            cx0, cy0 = scx, scy
            cx1, cy1 = min(0.82, scx + 0.015), max(0.22, scy - 0.012)
        else:
            cx0, cy0, cx1, cy1 = s.cx0, s.cy0, s.cx1, s.cy1

        z0 = max(1.0, s.z0)
        max_dz = style.composition.still_max_zoom_delta
        if abs(s.z1 - z0) > max_dz:
            z1 = z0 + (max_dz if s.z1 >= z0 else -max_dz)
            z1 = max(1.0, z1)
        else:
            z1 = max(1.0, s.z1)

        use_25d = (
            style.composition.enable_synthetic_25d_parallax
            and s.kind == "still_parallax_25d"
            and s.parallax_px > 0.0
        )
        dkey = f"{s.src_file}_{s.crop_box}" if s.crop_box else s.src_file
        depth_l = infer_smoothed_depth(src_im, dkey) if use_25d else None

        def gen_still(i: int) -> Image.Image:
            u = _smoothstep(i / max(1, total_frames - 1))
            if s.reframe_mode == "keyframed" and s.reframe_keyframes:
                cx, cy = interpolate_reframe_keyframes(s.reframe_keyframes, u)
            else:
                cx = cx0 + u * (cx1 - cx0)
                cy = cy0 + u * (cy1 - cy0)
            zz = z0 + u * (z1 - z0)
            if depth_l is not None:
                fr = render_25d_parallax_frame(src_im, depth_l, cx, cy, zz, u, s.parallax_px, out_w, out_h)
            else:
                fr = crop_subpixel_full_canvas(src_im, cx, cy, zz, out_w, out_h)
            if abs(s.contrast_gain - 1.0) > 1e-3:
                fr = ImageEnhance.Contrast(fr).enhance(s.contrast_gain)
            fr = apply_documentary_color_grade(
                fr,
                frame_idx=f0 + i,
                enable_grade=style.color_science.enable_filmic_grade,
                cast_tame_strength=style.color_science.cast_tame_strength,
                luma_grain_sigma=style.color_science.luma_grain_sigma,
            )
            arr = (np.asarray(fr, dtype=np.float32) * keep_mult).astype(np.uint8)
            return _apply_shot_annotations(Image.fromarray(arr), s, i / float(fps), shot_dur, style)

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_still, encode_mode, style)
        return out_mp4

    if s.kind in ("video_full", "video_window"):
        src_vid = _resolve_asset_path(s.src_file, manifest)
        tmp_dir = scratch_dir / f"vid_{s.sid}"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        actual_src_in = max(0.0, s.src_in - (head_frames / float(fps)))
        dur = shot_dur + 0.35
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{actual_src_in:.3f}",
                "-t",
                f"{dur:.3f}",
                "-i",
                str(src_vid),
                "-vf",
                f"fps={fps}",
                str(tmp_dir / "f_%04d.png"),
            ]
        )
        frame_files = sorted(tmp_dir.glob("f_*.png"))
        if not frame_files:
            raise RuntimeError(f"Zero frames extracted from {src_vid} at src_in={actual_src_in:.2f}s")

        auto_kfs: list[tuple[float, float, float]] = []
        if s.reframe_mode == "auto_salient":
            auto_kfs = compute_video_reframe_trajectory(src_vid, actual_src_in, shot_dur)
        elif s.reframe_mode == "keyframed" and s.reframe_keyframes:
            auto_kfs = list(s.reframe_keyframes)

        if s.kind == "video_full":
            def gen_vfull(i: int) -> Image.Image:
                u_lin = i / max(1, total_frames - 1)
                u = _smoothstep(u_lin)
                if auto_kfs:
                    cx, cy = interpolate_reframe_keyframes(auto_kfs, u_lin)
                else:
                    cx = s.cx0 + u * (s.cx1 - s.cx0)
                    cy = s.cy0 + u * (s.cy1 - s.cy0)
                zz = max(1.0, s.z0 + u * (s.z1 - s.z0))
                raw = Image.open(frame_files[min(i, len(frame_files) - 1)]).convert("RGB")
                if s.crop_box is not None:
                    raw = raw.crop(s.crop_box)
                if s.shadow_lift > 1e-3:
                    raw = _apply_selective_shadow_lift(raw, s.shadow_lift)
                fr = crop_subpixel_full_canvas(raw, cx, cy, zz, out_w, out_h)
                if abs(s.contrast_gain - 1.0) > 1e-3:
                    fr = ImageEnhance.Contrast(fr).enhance(s.contrast_gain)
                fr = fr.filter(ImageFilter.UnsharpMask(radius=1.0, percent=26, threshold=2))
                fr = apply_documentary_color_grade(
                    fr,
                    frame_idx=f0 + i,
                    enable_grade=style.color_science.enable_filmic_grade,
                    cast_tame_strength=style.color_science.cast_tame_strength,
                    luma_grain_sigma=style.color_science.luma_grain_sigma,
                )
                arr = (np.asarray(fr, dtype=np.float32) * keep_mult).astype(np.uint8)
                return _apply_shot_annotations(Image.fromarray(arr), s, i / float(fps), shot_dur, style)

            _pipe_frames_to_mp4(out_mp4, total_frames, gen_vfull, encode_mode, style)
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return out_mp4

        # Legacy `video_window` retained only for `legacy_v2` backward compatibility
        fb = get_font(FONT_BOLD, 22)
        ft = get_font(FONT_BOLD, 34)
        fm = get_font(FONT_MED, 22)

        def gen_vwin(i: int) -> Image.Image:
            u = _smoothstep(i / max(1, total_frames - 1))
            cx = s.cx0 + u * (s.cx1 - s.cx0)
            cy = s.cy0 + u * (s.cy1 - s.cy0)
            zz = s.z0 + u * (s.z1 - s.z0)
            raw = Image.open(frame_files[min(i, len(frame_files) - 1)]).convert("RGB")
            if s.crop_box is not None:
                raw = raw.crop(s.crop_box)
            bg = raw.resize((out_w, out_h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(radius=40))
            bg = ImageEnhance.Brightness(bg).enhance(0.22)
            has_hdr = bool(s.card_title)
            win_w, win_h = 1016, (930 if has_hdr else 1040)
            wx, wy = (out_w - win_w) // 2, (372 if has_hdr else 300)
            fg = crop_subpixel_full_canvas(raw, cx, cy, zz, win_w, win_h)
            fg = fg.filter(ImageFilter.UnsharpMask(radius=1.0, percent=35, threshold=2))
            bg.paste(fg, (wx, wy))
            d = ImageDraw.Draw(bg)
            d.rectangle((wx - 2, wy - 2, wx + win_w + 1, wy + win_h + 1), outline=(165, 202, 232), width=2)
            if has_hdr:
                if s.card_badge:
                    pw = d.textbbox((0, 0), s.card_badge, font=fb)[2] + 40
                    d.rounded_rectangle((42, 130, 42 + pw, 178), radius=10, fill=(12, 22, 36), outline=(120, 182, 224), width=2)
                    d.text((62, 140), s.card_badge, font=fb, fill=(182, 226, 255))
                d.text((44, 200), s.card_title or "", font=ft, fill=(248, 252, 255))
                if s.card_subtitle:
                    d.text((44, 250), s.card_subtitle, font=fm, fill=(182, 204, 226))
            return _apply_shot_annotations(bg, s, i / float(fps), shot_dur, style)

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_vwin, encode_mode, style)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return out_mp4

    if s.kind == "diagram":
        diag_src = _resolve_asset_path(s.src_file, manifest)
        actual_src_in = max(0.0, s.src_in - (head_frames / float(fps)))
        tmp_dir = scratch_dir / f"diag_{s.sid}"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{actual_src_in:.3f}",
                "-t",
                f"{shot_dur + 0.35:.3f}",
                "-i",
                str(diag_src),
                "-vf",
                f"fps={fps},scale={out_w}:{out_h}",
                str(tmp_dir / "f_%04d.png"),
            ]
        )
        frame_files = sorted(tmp_dir.glob("f_*.png"))
        if not frame_files:
            raise RuntimeError(f"Zero frames extracted from diagram {diag_src}")

        def gen_diag(i: int) -> Image.Image:
            return Image.open(frame_files[min(i, len(frame_files) - 1)]).convert("RGB")

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_diag, encode_mode, style)
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return out_mp4

    # --- Legacy v2 inset/dashboard shot kinds (reachable ONLY when style_profile == "legacy_v2") ---
    if s.kind == "still_window":
        src_path = _resolve_asset_path(s.src_file, manifest)
        src_im = _open_upright_rgb(src_path, max_long_edge=3000, crop_box=s.crop_box)
        dkey = f"{s.src_file}_{s.crop_box}" if s.crop_box else s.src_file
        depth_l = infer_smoothed_depth(src_im, dkey) if (style.composition.enable_synthetic_25d_parallax and s.parallax_px > 0.0) else None
        bg = crop_subpixel_full_canvas(src_im, 0.5, 0.5, 1.05, out_w, out_h).filter(ImageFilter.GaussianBlur(radius=42))
        bg = ImageEnhance.Brightness(bg).enhance(0.24)
        bg = ImageEnhance.Color(bg).enhance(0.65)
        win_w, win_h = 1016, 1060
        wx, wy = (out_w - win_w) // 2, 300

        def gen_win(i: int) -> Image.Image:
            u = _smoothstep(i / max(1, total_frames - 1))
            cx = s.cx0 + u * (s.cx1 - s.cx0)
            cy = s.cy0 + u * (s.cy1 - s.cy0)
            zz = s.z0 + u * (s.z1 - s.z0)
            canvas = bg.copy()
            if depth_l is not None:
                fg = render_25d_parallax_frame(src_im, depth_l, cx, cy, zz, u, s.parallax_px * 0.75, win_w, win_h)
            else:
                fg = crop_subpixel_full_canvas(src_im, cx, cy, zz, win_w, win_h)
            canvas.paste(fg, (wx, wy))
            d = ImageDraw.Draw(canvas)
            d.rectangle((wx - 2, wy - 2, wx + win_w + 1, wy + win_h + 1), outline=(195, 215, 235), width=2)
            return _apply_shot_annotations(canvas, s, i / float(fps), shot_dur, style)

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_win, encode_mode, style)
        return out_mp4

    if s.kind == "study_card":
        src_path = _resolve_asset_path(s.src_file, manifest)
        fig_im = _open_upright_rgb(src_path, max_long_edge=3200, crop_box=s.crop_box)
        fb = get_font(FONT_BOLD, 22)
        ft = get_font(FONT_BOLD, 34)
        fm = get_font(FONT_MED, 22)
        fs = get_font(FONT_BOLD, 23)
        base_bg = Image.new("RGB", (out_w, out_h), (14, 20, 30))
        has_bullets = len(s.card_bullets) > 0
        card_top = 308
        card_bot = 1002 if has_bullets else 1306
        inner_w, inner_h = 988, (card_bot - card_top - 24)
        fill_rgb = (255, 255, 255) if s.card_bg_white else (10, 16, 26)

        def gen_study(i: int) -> Image.Image:
            u = _smoothstep(i / max(1, total_frames - 1))
            zz = 1.0 + max(0.0, (s.z0 - 1.0) + u * (s.z1 - s.z0))
            canvas = base_bg.copy()
            d = ImageDraw.Draw(canvas)
            if s.card_badge:
                pw = d.textbbox((0, 0), s.card_badge, font=fb)[2] + 40
                d.rounded_rectangle((44, 128, 44 + pw, 176), radius=10, fill=(20, 32, 48), outline=(135, 185, 225), width=2)
                d.text((64, 138), s.card_badge, font=fb, fill=(188, 226, 255))
            if s.card_title:
                d.text((44, 196), s.card_title, font=ft, fill=(248, 250, 255))
            if s.card_subtitle:
                d.text((44, 244), s.card_subtitle, font=fm, fill=(178, 200, 222))

            d.rounded_rectangle((34, card_top, 1046, card_bot), radius=16, fill=fill_rgb)
            fit_base = ImageOps.contain(fig_im, (inner_w, inner_h), Image.Resampling.LANCZOS)
            zw = max(1, int(round(fit_base.width * min(1.06, zz))))
            zh = max(1, int(round(fit_base.height * min(1.06, zz))))
            zoomed = fig_im.resize((zw, zh), Image.Resampling.LANCZOS)
            panel = Image.new("RGB", (inner_w, inner_h), fill_rgb)
            panel.paste(zoomed, ((inner_w - zw) // 2, (inner_h - zh) // 2))
            canvas.paste(panel, (46, card_top + 12))
            d.rounded_rectangle((34, card_top, 1046, card_bot), radius=16, outline=(145, 185, 218), width=3)
            if has_bullets:
                d.rounded_rectangle((34, 1028, 1046, 1312), radius=16, fill=(19, 28, 42), outline=(92, 136, 178), width=2)
                d.text((60, 1048), s.card_bullets[0], font=fs, fill=(188, 226, 252))
                for bi, bline in enumerate(s.card_bullets[1:5]):
                    d.text((60, 1096 + bi * 46), bline, font=fm, fill=(228, 238, 248))
            return _apply_shot_annotations(canvas, s, i / float(fps), shot_dur, style)

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_study, encode_mode, style)
        return out_mp4

    if s.kind == "svs_flyover":
        src_vid = _resolve_asset_path(s.src_file, manifest)
        tmp_dir = scratch_dir / f"svs_{s.sid}"
        shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir.mkdir(parents=True, exist_ok=True)
        run_cmd(
            [
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-ss", f"{s.src_in:.3f}", "-t", f"{shot_dur + 0.25:.3f}",
                "-i", str(src_vid), "-vf", f"fps={fps}",
                str(tmp_dir / "f_%04d.png"),
            ]
        )
        frame_files = sorted(tmp_dir.glob("f_*.png"))
        fb, ft, fm = get_font(FONT_BOLD, 23), get_font(FONT_BOLD, 35), get_font(FONT_MED, 23)

        def gen_svs(i: int) -> Image.Image:
            raw = Image.open(frame_files[min(i, len(frame_files) - 1)]).convert("RGB")
            bg = raw.resize((out_w, out_h), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(radius=40))
            bg = ImageEnhance.Brightness(bg).enhance(0.22)
            fg = crop_subpixel_full_canvas(raw, 0.54, 0.56, 1.12, 1016, 920)
            bg.paste(fg, (32, 380))
            d = ImageDraw.Draw(bg)
            d.rectangle((30, 378, 32 + 1016 + 1, 380 + 920 + 1), outline=(165, 202, 232), width=2)
            pill = "NATURAL-COLOR LANDSAT FLYOVER • NASA / USGS LIMA"
            pw = d.textbbox((0, 0), pill, font=fb)[2] + 40
            d.rounded_rectangle((42, 132, 42 + pw, 180), radius=10, fill=(12, 20, 32), outline=(130, 175, 212), width=2)
            d.text((62, 142), pill, font=fb, fill=(185, 222, 250))
            d.text((44, 204), "Taylor Valley & Taylor Glacier", font=ft, fill=(248, 252, 255))
            d.text((44, 254), "McMurdo Dry Valleys, Antarctica (SVS #3482)", font=fm, fill=(182, 202, 224))
            return _apply_shot_annotations(bg, s, i / float(fps), shot_dur, style)

        _pipe_frames_to_mp4(out_mp4, total_frames, gen_svs, encode_mode, style)
        return out_mp4

    if s.kind in ("fig1_map", "fig1_sites", "microscopy_dual"):
        raise ValueError(
            f"Legacy topic-specific dashboard layout '{s.kind}' is deprecated in reusable workflow v3; "
            "use reusable full-screen 'video_full', 'still_full', or 'diagram'."
        )

    raise ValueError(f"Unsupported shot kind: {s.kind}")


def _shot_cache_signature(
    s: ShotSpecModel,
    hinfo: dict,
    encode_mode: str,
    style: DocumentaryStyleProfile,
) -> str:
    payload = {
        "shot": s.model_dump(),
        "head_frames": hinfo["head_frames"],
        "tail_frames": hinfo["tail_frames"],
        "nominal_frames": hinfo["nominal_frames"],
        "encode_mode": encode_mode,
        "output": style.output.model_dump(),
        "color_science": style.color_science.model_dump(),
        "composition": {
            "parallax": style.composition.enable_synthetic_25d_parallax,
            "rings": style.overlays.show_animated_circles_or_rings,
            "locators": style.overlays.show_locator_hud_cards,
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def render_all_shots(
    manifest: EpisodeManifest,
    wt: dict,
    encode_mode: Literal["draft", "master"] = "master",
    only: Optional[set[str]] = None,
    use_cache: bool = True,
) -> list[ShotSpecModel]:
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    shots_dir = out_dir / "shots"
    shots_dir.mkdir(parents=True, exist_ok=True)
    cache_file = shots_dir / ".shot_render_cache.json"
    cache_map: dict[str, str] = {}
    if cache_file.exists():
        try:
            cache_map = json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cache_map = {}

    timed_shots = resolve_timed_shots(manifest, int(wt["total_frames_30fps"]), style.output.fps)
    handles = compute_transition_handles(timed_shots, style)
    for s, hinfo in zip(timed_shots, handles):
        if only and s.sid not in only:
            continue
        sig = _shot_cache_signature(s, hinfo, encode_mode, style)
        sp = shots_dir / f"{s.sid}.mp4"
        if use_cache and sp.exists() and sp.stat().st_size > 1024 and cache_map.get(s.sid) == sig and not only:
            continue
        render_single_shot(
            s,
            manifest,
            encode_mode=encode_mode,
            head_frames=hinfo["head_frames"],
            tail_frames=hinfo["tail_frames"],
        )
        cache_map[s.sid] = sig

    cache_file.write_text(json.dumps(cache_map, indent=2), encoding="utf-8")
    return timed_shots


def _expand_segment_words_atomic(ws: list[dict], emph_norms: set[str]) -> list[dict]:
    expanded = []
    for w in ws:
        parts = [p for p in w["word"].replace("—", " ").split() if _norm_token(p)]
        if not parts:
            continue
        t0, t1 = float(w["start"]), float(w["end"])
        dt = max(0.01, (t1 - t0) / len(parts))
        for k, p in enumerate(parts):
            pn = _norm_token(p)
            expanded.append(
                {
                    "word": p,
                    "norm": pn,
                    "start": round(t0 + k * dt, 3),
                    "end": round(t0 + (k + 1) * dt, 3),
                    "emphasis": bool(w.get("emphasis")) or (pn in emph_norms),
                }
            )
    return expanded


def build_cues(manifest: EpisodeManifest, wt: dict) -> list[dict]:
    by_seg: dict[str, list[dict]] = {}
    for w in wt["words"]:
        by_seg.setdefault(w["seg_id"], []).append(w)

    emph_by_seg = {
        s.seg_id: {_norm_token(ew) for ew in s.emphasis_words if ew}
        for s in manifest.narration_segments
    }
    caption_groups = list(manifest.caption_groups) if manifest.caption_groups else auto_build_caption_groups_from_words(wt)
    groups_by_seg: dict[str, list] = {}
    for cg in caption_groups:
        groups_by_seg.setdefault(cg.seg_id, []).append(cg)

    cues: list[dict] = []
    for seg in manifest.narration_segments:
        sid = seg.seg_id
        cgs = groups_by_seg.get(sid, [])
        if not cgs:
            continue
        exp = _expand_segment_words_atomic(by_seg.get(sid, []), emph_by_seg.get(sid, set()))
        exp_norms = [x["norm"] for x in exp]

        cue_tok_lists = [
            [_norm_token(t) for t in cg.text.replace("—", " ").split() if _norm_token(t)]
            for cg in cgs
        ]
        flat_cue_norms = [tok for lst in cue_tok_lists for tok in lst]

        sm = difflib.SequenceMatcher(None, flat_cue_norms, exp_norms, autojunk=False)
        f2e: dict[int, int] = {}
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                for k in range(i2 - i1):
                    f2e[i1 + k] = j1 + k
            elif op == "replace" and (i2 - i1) > 0 and (j2 - j1) > 0:
                for k in range(i2 - i1):
                    f2e[i1 + k] = min(j2 - 1, j1 + int(k * (j2 - j1) / (i2 - i1)))

        cursor = 0
        for cg, toks in zip(cgs, cue_tok_lists):
            n_t = max(1, len(toks))
            mapped = [f2e[idx] for idx in range(cursor, cursor + n_t) if idx in f2e]
            cursor += len(toks)
            if mapped and exp:
                j0, j1 = min(mapped), max(mapped)
            else:
                j0 = min(cg.first_word_idx, max(0, len(exp) - 1))
                j1 = min(cg.last_word_idx, max(0, len(exp) - 1))
            t_start = float(exp[j0]["start"]) if exp else 0.0
            t_end = (float(exp[j1]["end"]) + 0.10) if exp else (t_start + 1.5)

            emph_events = []
            for item in exp[j0 : j1 + 1]:
                if item["emphasis"]:
                    emph_events.append(
                        {
                            "norm": item["norm"],
                            "activate_at": round(max(t_start, float(item["start"]) - 0.03), 3),
                        }
                    )
            cues.append(
                {
                    "seg_id": sid,
                    "start": round(t_start, 3),
                    "end": round(t_end, 3),
                    "text": cg.text,
                    "emphasis_events": emph_events,
                }
            )

    for idx in range(len(cues) - 1):
        if cues[idx]["end"] > cues[idx + 1]["start"] - 0.03:
            cues[idx]["end"] = round(cues[idx + 1]["start"] - 0.03, 3)
    return cues


def write_srt(cues: list[dict], srt_path: Path) -> None:
    def fmt_ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        hh, ms = divmod(ms, 3_600_000)
        mm, ms = divmod(ms, 60_000)
        ss, ms = divmod(ms, 1000)
        return f"{hh:02d}:{mm:02d}:{ss:02d},{ms:03d}"

    lines = []
    for i, c in enumerate(cues, 1):
        lines.extend([str(i), f"{fmt_ts(c['start'])} --> {fmt_ts(c['end'])}", c["text"], ""])
    srt_path.write_text("\n".join(lines), encoding="utf-8")


def wrap_caption_lines(d: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int = 900) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        if d.textbbox((0, 0), cand, font=f)[2] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_cover_hook(img: Image.Image, variant: CoverVariantSpec) -> None:
    d = ImageDraw.Draw(img)
    f_kick = get_font(FONT_BOLD, 26)
    f_main = get_font(FONT_ANTON, 118)
    kw = d.textbbox((0, 0), variant.kicker_text, font=f_kick)[2]
    mw = d.textbbox((0, 0), variant.cover_text, font=f_main)[2]
    box_w = max(kw, mw) + 76
    x0 = (W - box_w) // 2
    y0 = 1236
    ar, ag, ab = variant.accent_rgb
    d.rounded_rectangle(
        (x0, y0, x0 + box_w, y0 + 206),
        radius=22,
        fill=(8, 12, 20, 204),
        outline=(ar, ag, ab, 210),
        width=2,
    )
    kicker_fill = (min(255, ar + 26), min(255, ag + 106), min(255, ab + 110), 255)
    d.text(((W - kw) // 2, y0 + 18), variant.kicker_text, font=f_kick, fill=kicker_fill)
    d.text(
        ((W - mw) // 2, y0 + 52),
        variant.cover_text,
        font=f_main,
        fill=(255, 255, 255, 255),
        stroke_width=5,
        stroke_fill=(0, 0, 0, 255),
    )


def draw_source_label(img: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(img)
    f = get_font(FONT_MED, 23)
    tw = d.textbbox((0, 0), text, font=f)[2]
    x, y = 42, 132
    d.rounded_rectangle((x - 14, y - 9, x + tw + 16, y + 36), radius=10, fill=(8, 12, 22, 186))
    d.text((x, y), text, font=f, fill=(228, 236, 248, 246))


def draw_callout_pill(img: Image.Image, text: str) -> None:
    d = ImageDraw.Draw(img)
    f = get_font(FONT_BOLD, 26)
    tw = d.textbbox((0, 0), text, font=f)[2]
    x, y = 42, 190
    d.rounded_rectangle((x - 14, y - 8, x + tw + 20, y + 40), radius=10, fill=(26, 14, 16, 214), outline=(232, 82, 58, 212), width=2)
    d.text((x + 2, y), text, font=f, fill=(255, 196, 178, 255))


def draw_minimal_context_note(img: Image.Image, text: str) -> None:
    """
    Restrained, borderless plain-text documentary context label (<= 7 words)
    used ONLY when essential to prevent illustrative microscopy/simulation from
    being mistaken for specimen footage. Zero boxes, pills, or outlines.
    """
    f = get_font(FONT_MED, 24)
    x, y = 52, 136
    # Feathered optical shadow cushion (no box) so bright snow never washes out text
    sh_w, sh_h = min(W, 760), 96
    sh = Image.new("RGBA", (sh_w, sh_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    sd.text((28, 28), text, font=f, fill=(4, 8, 14, 190), stroke_width=8, stroke_fill=(4, 8, 14, 190))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=9))
    img.alpha_composite(sh, (max(0, x - 28), max(0, y - 28)))

    d = ImageDraw.Draw(img)
    d.text(
        (x, y),
        text,
        font=f,
        fill=(242, 246, 252, 238),
        stroke_width=2,
        stroke_fill=(6, 10, 18, 224),
    )


def draw_cinema_chapter_stamp(img: Image.Image, stamp_text: str) -> None:
    """
    Borderless theatrical documentary location/chapter stamp (zero boxes, zero pills, zero rings).
    Format supported: '01 // KAWAH IJEN, INDONESIA • 600°C' -> gold kicker + crisp white location title.
    """
    if "//" in stamp_text:
        left_p, right_p = [p.strip() for p in stamp_text.split("//", 1)]
        if "•" in right_p:
            loc_title, metric_tag = [p.strip() for p in right_p.split("•", 1)]
            eyebrow = f"LOCATION {left_p}  •  {metric_tag}"
        else:
            eyebrow = f"LOCATION {left_p}"
            loc_title = right_p
    else:
        eyebrow = ""
        loc_title = stamp_text.strip()

    f_eye = get_font(FONT_BOLD, 21)
    f_loc = get_font(FONT_BOLD, 33)
    x, y = 54, 126

    sh_w, sh_h = min(W, 880), 136
    sh = Image.new("RGBA", (sh_w, sh_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    if eyebrow:
        sd.text((34, 24), eyebrow, font=f_eye, fill=(4, 8, 14, 220), stroke_width=9, stroke_fill=(4, 8, 14, 220))
        sd.text((34, 54), loc_title, font=f_loc, fill=(4, 8, 14, 225), stroke_width=11, stroke_fill=(4, 8, 14, 225))
    else:
        sd.text((34, 34), loc_title, font=f_loc, fill=(4, 8, 14, 225), stroke_width=11, stroke_fill=(4, 8, 14, 225))
    sh = sh.filter(ImageFilter.GaussianBlur(radius=11))
    img.alpha_composite(sh, (max(0, x - 22), max(0, y - 22)))

    d = ImageDraw.Draw(img)
    bar_h = 68 if eyebrow else 42
    d.rectangle((x, y + 4, x + 5, y + 4 + bar_h), fill=(255, 214, 68, 248))
    if eyebrow:
        d.text(
            (x + 18, y + 2),
            eyebrow,
            font=f_eye,
            fill=(255, 222, 108, 250),
            stroke_width=2,
            stroke_fill=(6, 10, 18, 236),
        )
        d.text(
            (x + 18, y + 32),
            loc_title,
            font=f_loc,
            fill=(252, 253, 255, 252),
            stroke_width=3,
            stroke_fill=(6, 10, 18, 240),
        )
    else:
        d.text(
            (x + 18, y + 8),
            loc_title,
            font=f_loc,
            fill=(252, 253, 255, 252),
            stroke_width=3,
            stroke_fill=(6, 10, 18, 240),
        )


def draw_caption(
    img: Image.Image,
    text: str,
    active_emph_norms: list[str] | None = None,
    style: Optional[DocumentaryStyleProfile] = None,
) -> None:
    """
    Draw <= 2-line mobile-safe documentary subtitle in the lower safe region without
    covering the primary subject.
    Supports configurable documentary styles (`Part 8, Section 10`):
    - `cinema_boxless`: Bold editorial documentary typography + localized optical shadow (zero boxes).
    - `minimal_editorial`: Medium-weight cinema subtitle typography + localized optical shadow (zero boxes).
    - `scientific_plain`: Clean broadcast typography without distracting color flash (zero boxes).
    - `clean_scrim` / `legacy_pill`: Retained for explicit backward compatibility.
    """
    sub_cfg = style.subtitles if style else load_style_profile().subtitles
    if not sub_cfg.enabled:
        return

    d = ImageDraw.Draw(img)
    font_path = FONT_MED if sub_cfg.style in ("minimal_editorial", "scientific_plain") else FONT_BOLD
    f = get_font(font_path, sub_cfg.font_size_px)
    lines = wrap_caption_lines(d, text, f, sub_cfg.max_line_width_px)
    lh = sub_cfg.line_height_px
    y0 = sub_cfg.vertical_center_y_px - (len(lines) * lh) // 2
    widths = [d.textbbox((0, 0), ln, font=f)[2] for ln in lines]
    mw = max(widths)

    if sub_cfg.style in ("cinema_boxless", "minimal_editorial", "scientific_plain"):
        # Feathered optical drop-shadow cushion localized strictly around glyphs (ZERO boxes!)
        pad_y = 44
        band_y0 = max(0, y0 - pad_y)
        band_y1 = min(H, y0 + len(lines) * lh + pad_y)
        sh = Image.new("RGBA", (W, max(1, band_y1 - band_y0)), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sh)
        for k, ln in enumerate(lines):
            lw = widths[k]
            xs = (W - lw) // 2
            yl = (y0 - band_y0) + k * lh + 3
            sd.text(
                (xs, yl),
                ln,
                font=f,
                fill=(4, 8, 14, 220),
                stroke_width=14,
                stroke_fill=(4, 8, 14, 210),
            )
        sh = sh.filter(ImageFilter.GaussianBlur(radius=14))
        img.alpha_composite(sh, (0, band_y0))
        d = ImageDraw.Draw(img)
    else:
        pad_x = 24 if sub_cfg.style == "clean_scrim" else 28
        radius = 12 if sub_cfg.style == "clean_scrim" else 16
        box = ((W - mw) // 2 - pad_x, y0 - 13, (W + mw) // 2 + pad_x, y0 + len(lines) * lh + 10)
        d.rounded_rectangle(box, radius=radius, fill=tuple(sub_cfg.scrim_rgba))

    emph_mode = "none" if (sub_cfg.style == "scientific_plain" and sub_cfg.emphasis_mode == "none") else sub_cfg.emphasis_mode
    if not sub_cfg.enable_keyword_color_flash or emph_mode == "none":
        emph_set: set[str] = set()
    else:
        emph_set = set(active_emph_norms or [])

    emph_rgba = (255, 240, 192, 255) if emph_mode == "subtle_warm" else CAPTION_EMPH_RGBA
    text_fill = tuple(sub_cfg.text_rgba)
    sw = sub_cfg.stroke_width_px
    stroke_rgba = (6, 10, 16, 248)

    for k, ln in enumerate(lines):
        tokens = ln.split(" ")
        line_w = widths[k]
        x_start = (W - line_w) // 2
        y_line = y0 + k * lh
        if not emph_set:
            d.text((x_start, y_line), ln, font=f, fill=text_fill, stroke_width=sw, stroke_fill=stroke_rgba)
            continue

        prefix = ""
        for idx, tok in enumerate(tokens):
            dx = int(round(f.getlength(prefix))) if prefix else 0
            tn = _norm_token(tok)
            sub_norms = [_norm_token(p) for p in tok.replace("—", " ").split("-") if _norm_token(p)]
            is_emph = (tn in emph_set) or any(sn in emph_set for sn in sub_norms)
            fill = emph_rgba if is_emph else text_fill
            d.text((x_start + dx, y_line), tok, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke_rgba)
            prefix += tok + (" " if idx < len(tokens) - 1 else "")


def draw_closing_credit(img: Image.Image, manifest: EpisodeManifest) -> None:
    d = ImageDraw.Draw(img)
    fb = get_font(FONT_BOLD, 25)
    fm = get_font(FONT_MED, 21)
    l1 = manifest.closing_credits_line1 or f"Sources: Verified Scientific Literature • {manifest.channel_name}"
    l2 = f"Media: Verified Public Domain & CC BY • {manifest.channel_name}: {manifest.playlist}"
    w1 = d.textbbox((0, 0), l1, font=fb)[2]
    w2 = d.textbbox((0, 0), l2, font=fm)[2]
    bw = max(w1, w2) + 52
    x0 = (W - bw) // 2
    y0 = 1575
    d.rounded_rectangle((x0, y0, x0 + bw, y0 + 104), radius=16, fill=(8, 12, 22, 214))
    d.text(((W - w1) // 2, y0 + 16), l1, font=fb, fill=(242, 246, 252, 250))
    d.text(((W - w2) // 2, y0 + 56), l2, font=fm, fill=(186, 206, 228, 240))


def compute_overlay_states(
    manifest: EpisodeManifest,
    wt: dict,
) -> tuple[list[tuple[float, float, dict]], int, float, list[ShotSpecModel], list[dict]]:
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    out_dir = Path(manifest.output_dir)
    total_dur = float(wt["total_duration_s"])
    nframes = int(wt["total_frames_30fps"])
    timed_shots = resolve_timed_shots(manifest, nframes, fps)
    cues = build_cues(manifest, wt)
    write_srt(cues, out_dir / "subtitles.srt")

    burn_cover = style.overlays.burn_opening_cover_card_into_video and bool(manifest.cover_variants)
    burn_credit = style.overlays.show_closing_credit_card_in_video
    cover_end = 2.500 if burn_cover else 0.0
    credit_start = round(float(wt["segments"][-1]["end"]) + 0.25, 3)

    bounds = {0.0, total_dur}
    if burn_cover:
        bounds.add(cover_end)
    if burn_credit:
        bounds.add(credit_start)
    for s in timed_shots:
        bounds.add(s.start_s)
        bounds.add(s.end_s)
        if s.chapter_stamp and style.overlays.allow_cinema_chapter_stamps:
            cs0 = min(s.end_s, s.start_s + 0.08)
            cs1 = min(s.end_s, s.start_s + s.chapter_stamp_duration_s)
            bounds.add(cs0)
            bounds.add(cs1)
    for c in cues:
        bounds.add(c["start"])
        bounds.add(c["end"])
        if style.subtitles.enable_keyword_color_flash:
            for ev in c.get("emphasis_events", []):
                bounds.add(float(ev["activate_at"]))

    pts = sorted(set(round(b * fps) / fps for b in bounds if 0.0 <= b <= total_dur))
    if not pts or pts[-1] < total_dur - 1e-4:
        pts.append(round(nframes / float(fps), 4))

    states = []
    for a, b in zip(pts, pts[1:]):
        if b - a < 1e-6:
            continue
        m = 0.5 * (a + b)
        shot = next((s for s in timed_shots if s.start_s <= m < s.end_s), timed_shots[-1])
        cue = next((c for c in cues if c["start"] <= m < c["end"]), None)
        show_cover = burn_cover and (m < cover_end)
        show_credit = burn_credit and (m >= credit_start)
        active_emph = []
        if style.subtitles.enable_keyword_color_flash and cue and not (show_cover and m < 0.16):
            active_emph = sorted({ev["norm"] for ev in cue.get("emphasis_events", []) if m >= float(ev["activate_at"])})

        active_chapter = None
        if (
            shot.chapter_stamp
            and style.overlays.allow_cinema_chapter_stamps
            and (shot.start_s + 0.08) <= m < min(shot.end_s, shot.start_s + shot.chapter_stamp_duration_s)
        ):
            active_chapter = shot.chapter_stamp

        st = {
            "cover": show_cover,
            "label": shot.label if style.overlays.show_source_banners_in_video else None,
            "callout": (shot.callout if not show_cover else None) if style.overlays.show_callout_warning_badges else None,
            "chapter_stamp": active_chapter,
            "context_note": (
                shot.context_note
                if (style.overlays.allow_minimal_context_captions and not active_chapter)
                else None
            ),
            "caption": None if (show_cover and m < 0.16) else (cue["text"] if cue else None),
            "active_emph": active_emph,
            "credit": show_credit,
        }
        states.append((a, b, st))
    return states, nframes, total_dur, timed_shots, cues


def render_overlay_rgba(
    st: dict,
    manifest: EpisodeManifest,
    cover_variant: Optional[CoverVariantSpec] = None,
    style: Optional[DocumentaryStyleProfile] = None,
) -> Image.Image:
    resolved_style = style or manifest.resolve_style_profile()
    img = Image.new("RGBA", (resolved_style.output.width, resolved_style.output.height), (0, 0, 0, 0))
    if st.get("label"):
        draw_source_label(img, st["label"])
    if st.get("callout"):
        draw_callout_pill(img, st["callout"])
    if st.get("chapter_stamp"):
        draw_cinema_chapter_stamp(img, st["chapter_stamp"])
    if st.get("context_note"):
        draw_minimal_context_note(img, st["context_note"])
    if st.get("cover") and (cover_variant or manifest.cover_variants):
        draw_cover_hook(img, cover_variant or manifest.cover_variants[0])
    if st.get("credit"):
        draw_closing_credit(img, manifest)
    if st.get("caption"):
        draw_caption(img, st["caption"], st.get("active_emph", []), style=resolved_style)
    return img


def build_overlay_mov(
    states: list[tuple[float, float, dict]],
    nframes: int,
    manifest: EpisodeManifest,
    scratch_dir: Path,
) -> Path:
    style = manifest.resolve_style_profile()
    out_w, out_h, fps = style.output.width, style.output.height, style.output.fps
    ovl_mov = scratch_dir / "overlay_qtrle.mov"
    proc = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgba",
            "-s",
            f"{out_w}x{out_h}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-frames:v",
            str(nframes),
            "-c:v",
            "qtrle",
            "-pix_fmt",
            "argb",
            str(ovl_mov),
        ],
        stdin=subprocess.PIPE,
    )
    assert proc.stdin is not None
    cache: dict[str, bytes] = {}
    written = 0
    last_bytes = b"\x00" * (out_w * out_h * 4)

    for a, b, st in states:
        key = json.dumps(st, sort_keys=True)
        if key not in cache:
            im = render_overlay_rgba(st, manifest, style=style)
            cache[key] = np.asarray(im, dtype=np.uint8).tobytes()
        raw = cache[key]
        last_bytes = raw
        fa, fb = int(round(a * fps)), int(round(b * fps))
        for _ in range(max(0, fb - fa)):
            if written < nframes:
                proc.stdin.write(raw)
                written += 1

    while written < nframes:
        proc.stdin.write(last_bytes)
        written += 1

    proc.stdin.close()
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"qtrle overlay encode failed ({rc})")
    return ovl_mov


def _assemble_base_timeline_mp4(
    timed_shots: list[ShotSpecModel],
    handles: list[dict],
    shots_dir: Path,
    scratch_dir: Path,
    encode_mode: Literal["draft", "master"],
    style: DocumentaryStyleProfile,
) -> Path:
    """
    Assemble all rendered shot clips into `base_concat.mp4` with exact frame count.
    Hard-cut segments are concatenated losslessly; contiguous cross-dissolve groups
    are blended via `ffmpeg xfade=transition=fade` using the exact pre-rendered handles.
    """
    fps = style.output.fps
    n = len(timed_shots)
    groups: list[list[int]] = []
    cur: list[int] = [0]
    for i in range(1, n):
        if handles[i]["dissolve_in_frames"] > 0:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)

    segment_mp4s: list[Path] = []
    for g_idx, grp in enumerate(groups):
        if len(grp) == 1:
            idx = grp[0]
            segment_mp4s.append(shots_dir / f"{timed_shots[idx].sid}.mp4")
            continue

        grp_out = scratch_dir / f"xfade_group_{g_idx:02d}.mp4"
        inputs: list[str] = []
        for idx in grp:
            inputs.extend(["-i", str((shots_dir / f"{timed_shots[idx].sid}.mp4").resolve())])

        # Build chained xfade filtergraph with exact frame-derived offsets
        filter_parts: list[str] = []
        for local_k in range(len(grp)):
            filter_parts.append(f"[{local_k}:v]fps={fps},settb=AVTB[v{local_k}]")

        accum_nominal_frames = handles[grp[0]]["nominal_frames"]
        prev_lbl = "v0"
        for local_k in range(1, len(grp)):
            shot_idx = grp[local_k]
            d_frames = handles[shot_idx]["dissolve_in_frames"]
            head_f = handles[shot_idx]["head_frames"]
            offset_frames = accum_nominal_frames - head_f
            dur_s = d_frames / float(fps)
            off_s = max(0.0, offset_frames / float(fps))
            out_lbl = f"xf{local_k}"
            filter_parts.append(
                f"[{prev_lbl}][v{local_k}]xfade=transition=fade:duration={dur_s:.6f}:offset={off_s:.6f}[{out_lbl}]"
            )
            prev_lbl = out_lbl
            accum_nominal_frames += handles[shot_idx]["nominal_frames"]

        expected_grp_frames = sum(handles[idx]["nominal_frames"] for idx in grp)
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                *inputs,
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{prev_lbl}]",
                "-frames:v",
                str(expected_grp_frames),
                "-r",
                str(fps),
                *_video_codec_args(encode_mode, style),
                str(grp_out),
            ]
        )
        segment_mp4s.append(grp_out)

    base_mp4 = scratch_dir / "base_concat.mp4"
    if len(segment_mp4s) == 1:
        shutil.copy2(segment_mp4s[0], base_mp4)
        return base_mp4

    # Normalize stream parameters if mixing direct shot clips with xfade groups
    concat_txt = scratch_dir / "concat_shots.txt"
    concat_txt.write_text("\n".join(f"file '{p.resolve()}'" for p in segment_mp4s) + "\n")
    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-c",
            "copy",
            str(base_mp4),
        ]
    )
    return base_mp4


def build_preview_sheet(
    manifest: EpisodeManifest,
    wt: dict,
    encode_mode: Literal["draft", "master"] = "master",
) -> Path:
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    shots_dir = out_dir / "shots"
    scratch_dir = out_dir / ".scratch_build"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    states, _, total_dur, timed_shots, _ = compute_overlay_states(manifest, wt)
    handles = compute_transition_handles(timed_shots, style)

    pw, ph = 240, 426
    cols = 4
    rows = (len(timed_shots) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (pw + 16) + 16, rows * (ph + 62) + 72), (14, 17, 25))
    d = ImageDraw.Draw(sheet)
    ft = get_font(FONT_BOLD, 25)
    fb = get_font(FONT_BOLD, 16)
    fm = get_font(FONT_MED, 13)
    d.text(
        (18, 18),
        f"{manifest.playlist.upper()} ({manifest.slug}) — {style.profile_name.upper()} STORYBOARD ({len(timed_shots)} shots, {total_dur:.2f}s)",
        font=ft,
        fill=(255, 255, 255),
    )

    tmp_png = scratch_dir / "_pv_shot.png"
    for k, (s, hinfo) in enumerate(zip(timed_shots, handles)):
        shot_mp4 = shots_dir / f"{s.sid}.mp4"
        if not shot_mp4.exists():
            render_single_shot(
                s,
                manifest,
                encode_mode=encode_mode,
                head_frames=hinfo["head_frames"],
                tail_frames=hinfo["tail_frames"],
            )
        tm = 0.25 if k == 0 else 0.5 * (s.start_s + s.end_s)
        local_t = max(0.0, (tm - s.start_s) + (hinfo["head_frames"] / float(style.output.fps)))
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{local_t:.3f}",
                "-i",
                str(shot_mp4),
                "-frames:v",
                "1",
                str(tmp_png),
            ]
        )
        base = Image.open(tmp_png).convert("RGBA")
        st = next((st for a, b, st in states if a <= tm < b), states[-1][2])
        comp = Image.alpha_composite(base, render_overlay_rgba(st, manifest, style=style)).convert("RGB")

        r, c = divmod(k, cols)
        x = 16 + c * (pw + 16)
        y = 66 + r * (ph + 62)
        sheet.paste(comp.resize((pw, ph), Image.Resampling.LANCZOS), (x, y))
        tr_tag = f" [dissolve {s.transition_duration_s:.2f}s]" if (k > 0 and s.transition_in == "dissolve") else ""
        d.text((x + 2, y + ph + 4), f"{s.sid}  {s.start_s:.1f}–{s.end_s:.1f}s{tr_tag}", font=fb, fill=(255, 224, 110))
        d.text((x + 2, y + ph + 26), f"{s.kind} • {s.src_file[:22]}", font=fm, fill=(195, 210, 230))

    out_sheet = out_dir / "pre_render_storyboard_contact_sheet.jpg"
    sheet.save(out_sheet, quality=92)
    return out_sheet


def _load_thumbnail_source_rgb(
    manifest: EpisodeManifest,
    timed_shots: list[ShotSpecModel],
    override_spec: Optional[ThumbnailSpecModel] = None,
) -> tuple[Image.Image, str]:
    tspec = override_spec or manifest.thumbnail_spec
    src_name = tspec.src_file if (tspec and tspec.src_file) else timed_shots[0].src_file
    src_path = _resolve_asset_path(src_name, manifest)
    crop_box = (
        tspec.crop_box
        if (tspec and tspec.crop_box)
        else (timed_shots[0].crop_box if src_name == timed_shots[0].src_file else None)
    )

    if src_path.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
        t_sec = tspec.src_time_s if (tspec and tspec.src_time_s is not None) else timed_shots[0].src_in
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{max(0.0, t_sec):.3f}",
                "-i",
                str(src_path),
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
            raise RuntimeError(f"Failed to grab thumbnail frame from {src_path} at {t_sec:.2f}s")
        im = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
        if crop_box is not None:
            im = im.crop(crop_box)
        return im, src_name

    return _open_upright_rgb(src_path, max_long_edge=3400, crop_box=crop_box), src_name


def render_thumbnail_concepts_for_episode(
    manifest: EpisodeManifest,
    timed_shots: Optional[list[ShotSpecModel]] = None,
) -> dict:
    """
    Standalone & integrated Thumbnail Studio workflow (`Part 7, Section 9`):
    Renders multiple distinct thumbnail concepts (from `manifest.thumbnail_concepts`, or derived
    from `thumbnail_spec` + `alt_headlines` + pure subject visual) and exports mobile-size
    comparison sheets without claiming visual scores predict real CTR.
    """
    style = manifest.resolve_style_profile()
    out_dir = Path(manifest.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t_shots = timed_shots or list(manifest.shots)

    specs: list[ThumbnailSpecModel] = list(manifest.thumbnail_concepts)
    if not specs:
        base_spec = manifest.thumbnail_spec or ThumbnailSpecModel(concept_id="A", headline_text="")
        specs.append(base_spec.model_copy(update={"concept_id": "A", "concept_rationale": base_spec.concept_rationale or "Primary opening-matched focal subject + concise curiosity hook"}))
        for idx, alt_h in enumerate((base_spec.alt_headlines or [])[:2]):
            specs.append(
                base_spec.model_copy(
                    update={
                        "concept_id": chr(ord("B") + idx),
                        "headline_text": alt_h,
                        "alt_headlines": [],
                        "concept_rationale": f"Alternative curiosity angle #{idx + 1}",
                    }
                )
            )
        # Ensure at least 2 concepts exist by adding a pure-visual / tighter focal framing concept
        if len(specs) < 2:
            specs.append(
                base_spec.model_copy(
                    update={
                        "concept_id": "B",
                        "headline_text": "",
                        "zoom": min(1.35, base_spec.zoom + 0.08),
                        "concept_rationale": "Pure authentic phenomenon close-up with zero text overlay",
                    }
                )
            )

    rendered_concepts: list[dict] = []
    for idx, cspec in enumerate(specs):
        src_rgb, src_name = _load_thumbnail_source_rgb(manifest, t_shots, override_spec=cspec)
        cscore = score_thumbnail_candidate(src_rgb, source_name=src_name)
        cx = cspec.cx if cspec.cx is not None else (t_shots[0].cx0 if src_name == t_shots[0].src_file else cscore.recommended_cx)
        cy = cspec.cy if cspec.cy is not None else (t_shots[0].cy0 if src_name == t_shots[0].src_file else cscore.recommended_cy)
        im = compose_subject_first_thumbnail(
            source_rgb=src_rgb,
            style=style,
            headline_text=cspec.headline_text,
            cx=cx,
            cy=cy,
            zoom=cspec.zoom,
            text_position=cspec.text_position,
            kicker_text=cspec.kicker_text,
            accent_line_index=cspec.accent_line_index,
            accent_rgb=cspec.accent_rgb,
            clarity_boost=cspec.clarity_boost,
            shadow_lift=cspec.shadow_lift,
        )
        rendered_concepts.append(
            {
                "concept_id": cspec.concept_id or chr(ord("A") + idx),
                "src_file": src_name,
                "headline_text": cspec.headline_text,
                "kicker_text": cspec.kicker_text,
                "concept_rationale": cspec.concept_rationale,
                "candidate_score": cscore,
                "image": im,
            }
        )

    return generate_thumbnail_concepts_package(
        concepts_rendered=rendered_concepts,
        out_dir=out_dir,
        slug=manifest.slug,
        primary_title=manifest.primary_title,
        style=style,
        opening_shot_src_file=t_shots[0].src_file if t_shots else "",
    )


def export_cover_variants_and_ab_sheet(
    f0_base_rgba: Image.Image,
    frame0_state: dict,
    manifest: EpisodeManifest,
    final_mp4: Path,
    scratch_dir: Path,
) -> list[dict]:
    out_dir = Path(manifest.output_dir)
    variant_records = []
    variant_images: list[tuple[CoverVariantSpec, Image.Image, Path]] = []

    for idx, var in enumerate(manifest.cover_variants):
        comp_rgb = Image.alpha_composite(
            f0_base_rgba, render_overlay_rgba(frame0_state, manifest, cover_variant=var)
        ).convert("RGB")
        if idx == 0:
            f0_master = scratch_dir / "frame0_master_rgb.png"
            comp_rgb.save(f0_master, format="PNG")
            export_first_frame_thumbnail(
                mp4_path=final_mp4,
                raw_frame0_rgb_path=f0_master,
                title_preview=manifest.primary_title,
                generate_preview_sheet=True,
                native_crop_box=(310, 620, 770, 1080),
            )
            shutil.copy2(out_dir / f"{manifest.slug}.jpg", out_dir / "thumbnail.jpg")

        v_jpg = out_dir / f"thumbnail_variant_{var.variant_id.lower()}.jpg"
        q = _save_youtube_444_jpeg(comp_rgb, v_jpg)
        variant_images.append((var, comp_rgb, v_jpg))
        variant_records.append(
            {
                "variant_id": var.variant_id,
                "cover_text": var.cover_text,
                "path": str(v_jpg),
                "size_kb": round(v_jpg.stat().st_size / 1024.0, 1),
                "jpeg_quality": q,
            }
        )

    n_var = len(variant_images)
    col_w = 740
    sheet_w = max(780, n_var * col_w + 40)
    sheet_h = 980
    ab = Image.new("RGB", (sheet_w, sheet_h), (14, 18, 26))
    d = ImageDraw.Draw(ab)
    f_hdr = get_font(FONT_BOLD, 28)
    f_sub = get_font(FONT_BOLD, 20)
    f_med = get_font(FONT_MED, 16)
    f_tiny = get_font(FONT_BOLD, 11)
    d.text((28, 22), f"MULTI-COVER A/B MOBILE SHELF & CROP EVALUATION — {manifest.primary_title}", font=f_hdr, fill=(255, 255, 255))

    for idx, (var, im_rgb, v_jpg) in enumerate(variant_images):
        ox = 28 + idx * col_w
        d.rounded_rectangle((ox, 74, ox + col_w - 24, sheet_h - 24), radius=18, fill=(20, 26, 38), outline=(72, 96, 128), width=2)
        tag = "PRIMARY FRAME-0 MASTER" if idx == 0 else "ALTERNATIVE CTR VARIANT"
        d.text((ox + 22, 92), f"Variant {var.variant_id}: \"{var.cover_text}\"  •  {tag}", font=f_sub, fill=(255, 226, 118))
        ab.paste(im_rgb.resize((360, 640), Image.Resampling.LANCZOS), (ox + 22, 136))
        d.text((ox + 22, 788), f"9:16 Master ({v_jpg.stat().st_size/1024:.0f} KB, 4:4:4 RGB)", font=f_med, fill=(205, 220, 238))
        mob = im_rgb.resize((160, 284), Image.Resampling.LANCZOS)
        ab.paste(mob, (ox + 404, 136))
        mob_ov = mob.copy().convert("RGBA")
        ov = Image.new("RGBA", (160, 284), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        od.rectangle((0, 224, 160, 284), fill=(0, 0, 0, 168))
        stitle = manifest.primary_title
        od.text((8, 232), stitle[:22] + ("..." if len(stitle) > 22 else ""), font=f_tiny, fill=(255, 255, 255, 245))
        ab.paste(Image.alpha_composite(mob_ov, ov).convert("RGB"), (ox + 572, 136))
        sq = im_rgb.crop((0, 420, 1080, 1500)).resize((310, 310), Image.Resampling.LANCZOS)
        ab.paste(sq, (ox + 404, 468))
        d.text((ox + 404, 788), "1:1 Feed Center Crop (y=420..1500)", font=f_med, fill=(205, 220, 238))

    ab.save(out_dir / "cover_ab_comparison_sheet.jpg", format="JPEG", quality=93, subsampling=0)
    return variant_records


def render_episode_master(
    manifest: EpisodeManifest,
    wt: dict,
    encode_mode: Literal["draft", "master"] = "master",
) -> Path:
    t_render_start = time.perf_counter()
    manifest.assert_output_dir_writable()
    style = manifest.resolve_style_profile()
    fps = style.output.fps
    sr = style.output.audio_sample_rate_hz

    out_dir = Path(manifest.output_dir)
    shots_dir = out_dir / "shots"
    scratch_dir = out_dir / ".scratch_build"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    mix_wav = out_dir / "work_audio" / "final_audio_mix.wav"
    final_mp4 = out_dir / f"{manifest.slug}.mp4"

    states, nframes, _, timed_shots, _ = compute_overlay_states(manifest, wt)
    handles = compute_transition_handles(timed_shots, style)
    t_shots_start = time.perf_counter()
    render_all_shots(manifest, wt, encode_mode=encode_mode, use_cache=True)
    shots_elapsed_s = round(time.perf_counter() - t_shots_start, 3)

    t_asm_start = time.perf_counter()
    base_mp4 = _assemble_base_timeline_mp4(timed_shots, handles, shots_dir, scratch_dir, encode_mode, style)
    ovl_mov = build_overlay_mov(states, nframes, manifest, scratch_dir)

    run_cmd(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(base_mp4),
            "-i",
            str(ovl_mov),
            "-i",
            str(mix_wav),
            "-filter_complex",
            "[1:v]format=rgba[o];[0:v][o]overlay=0:0:format=auto:shortest=1,format=yuv420p[v]",
            "-map",
            "[v]",
            "-map",
            "2:a",
            "-frames:v",
            str(nframes),
            "-r",
            str(fps),
            *_video_codec_args(encode_mode, style),
            "-c:a",
            style.output.audio_codec,
            "-b:a",
            style.output.audio_bitrate,
            "-ar",
            str(sr),
            "-movflags",
            "+faststart",
            str(final_mp4),
        ]
    )
    assembly_elapsed_s = round(time.perf_counter() - t_asm_start, 3)
    # Reclaim large lossless RGBA & intermediate concat files immediately after muxing
    ovl_mov.unlink(missing_ok=True)
    base_mp4.unlink(missing_ok=True)
    for xf in scratch_dir.glob("xfade_group_*.mp4"):
        xf.unlink(missing_ok=True)

    t_thumb_start = time.perf_counter()
    if style.opening_and_thumbnail.thumbnail_text_mode == "legacy_card" and manifest.cover_variants:
        f0_base = scratch_dir / "s01_frame0_base.png"
        run_cmd(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(shots_dir / f"{timed_shots[0].sid}.mp4"),
                "-vf",
                "select=eq(n\\,0)",
                "-frames:v",
                "1",
                str(f0_base),
            ]
        )
        f0_rgba = Image.open(f0_base).convert("RGBA")
        export_cover_variants_and_ab_sheet(f0_rgba, states[0][2], manifest, final_mp4, scratch_dir)
    else:
        render_thumbnail_concepts_for_episode(manifest, timed_shots=timed_shots)
    thumb_elapsed_s = round(time.perf_counter() - t_thumb_start, 3)

    pr = run_cmd(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(final_mp4)]).stdout
    (out_dir / "ffprobe_validation.json").write_text(pr)

    bench = {
        "slug": manifest.slug,
        "encode_mode": encode_mode,
        "shots_render_or_cache_s": shots_elapsed_s,
        "timeline_assembly_and_mux_s": assembly_elapsed_s,
        "thumbnail_concepts_s": thumb_elapsed_s,
        "total_render_master_s": round(time.perf_counter() - t_render_start, 3),
        "rendered_frames": nframes,
        "effective_render_fps": round(nframes / max(0.01, time.perf_counter() - t_render_start), 2),
    }
    (out_dir / "render_benchmarks.json").write_text(json.dumps(bench, indent=2), encoding="utf-8")
    return final_mp4
