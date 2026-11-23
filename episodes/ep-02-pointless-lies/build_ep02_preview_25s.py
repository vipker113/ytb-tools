#!/usr/bin/env python3
"""
Kairo Spark — Episode #2: "Why We Lie When There's Nothing to Lose"
~25s Static 2D Adobe Flash Preview Builder (Obeys Rules 1–14 of kairo-stickman-style.md)
- Pure 2D Flash illustrations (zero PIL text boxes, zero top-pill badges, zero AI zoom/pan)
- Clause-level rapid cuts (13 cuts / 25.00s = 1.92s avg)
- pow_studio cinema_boxless subtitles at y=918 + companion .srt
- Editorial SFX foley mixed below Chatterbox TTS voiceover, mastered to -14.0 LUFS
"""

import os
import sys
import math
import json
import argparse
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/ep-02-pointless-lies"
SCENES_DIR = os.path.join(EP_DIR, "scenes")
FRAMES_DIR = os.path.join(EP_DIR, "frames_preview_25s")
FLASH_PACK_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack"
SFX_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/sfx"
FONT_BOLD = "/Applications/code/science-knowledge/youtube-shorts-channel/assets/fonts/BeVietnamPro-Bold.ttf"
VOICE_SRC = os.path.join(EP_DIR, "audio/ep02_hook_voice_chatterbox.mp3")
GRID1_SRC = "/Users/admin/.gemini/antigravity/brain/9c914627-c4fa-4486-ab2e-ea9740fd1166/ep02_preview_grid_01_1795432013075.jpg"

os.makedirs(SCENES_DIR, exist_ok=True)
os.makedirs(FRAMES_DIR, exist_ok=True)


def slice_grid_1():
    g1 = Image.open(GRID1_SRC).convert("RGB")
    W, H = g1.size
    hw, hh = W // 2, H // 2
    m = 10
    crops = [
        ((m, m, hw - m, hh - m), "s01_truth_zero_scale.png"),
        ((hw + m, m, W - m, hh - m), "s02_monday_breakroom_wide.png"),
        ((m, hh + m, hw - m, H - m), "s03_apartment_door_locked.png"),
        ((hw + m, hh + m, W - m, H - m), "s04_takeout_couch_dinner.png"),
    ]
    for box, name in crops:
        out_path = os.path.join(SCENES_DIR, name)
        g1.crop(box).resize((1920, 1080), Image.Resampling.LANCZOS).save(out_path)
    print("Sliced Grid 1 OK.")


def load_scene(name):
    p = os.path.join(SCENES_DIR, name)
    return Image.open(p).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)


def make_flash_12num_clock(hour_val, badge_text, sub_tag="SATURDAY", minute_val=0, bg_wall=(236, 217, 178)):
    S = 2
    W, H = 1920 * S, 1080 * S
    img = Image.new("RGB", (W, H), bg_wall)
    d = ImageDraw.Draw(img)

    cx, cy = 960 * S, 445 * S
    r_outer = 320 * S  # bottom at y=765, safely 153px above y=918 subtitle

    d.ellipse([cx - r_outer - 12 * S, cy - r_outer + 14 * S, cx + r_outer - 12 * S, cy + r_outer + 14 * S], fill=(204, 185, 148))
    d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(242, 244, 247), outline=(15, 15, 15), width=10 * S)
    r_inner = r_outer - 34 * S
    d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(255, 255, 255), outline=(15, 15, 15), width=7 * S)

    font_num = ImageFont.truetype(FONT_BOLD, 46 * S)
    font_active = ImageFont.truetype(FONT_BOLD, 56 * S)

    for hr in range(1, 13):
        ang_deg = hr * 30 - 90
        ang = math.radians(ang_deg)
        t_out = r_inner - 12 * S
        t_in = r_inner - (32 * S if hr % 3 == 0 else 20 * S)
        t_w = 7 * S if hr % 3 == 0 else 4 * S
        d.line(
            [(cx + t_in * math.cos(ang), cy + t_in * math.sin(ang)),
             (cx + t_out * math.cos(ang), cy + t_out * math.sin(ang))],
            fill=(15, 15, 15), width=t_w
        )
        num_r = r_inner - 72 * S
        nx = cx + num_r * math.cos(ang)
        ny = cy + num_r * math.sin(ang)
        is_target = (hr == hour_val)
        if is_target:
            hl_r = 40 * S
            d.ellipse([nx - hl_r, ny - hl_r, nx + hl_r, ny + hl_r], fill=(255, 224, 102), outline=(210, 45, 45), width=6 * S)
        f_use = font_active if (is_target or hr in (12, 3, 6, 9)) else font_num
        txt = str(hr)
        bbox = d.textbbox((0, 0), txt, font=f_use)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text((nx - tw / 2 - bbox[0], ny - th / 2 - bbox[1]), txt, font=f_use, fill=(205, 35, 35) if is_target else (15, 15, 15))

    min_ang = math.radians(minute_val * 6 - 90)
    d.line([(cx, cy), (cx + (r_inner - 105 * S) * math.cos(min_ang), cy + (r_inner - 105 * S) * math.sin(min_ang))], fill=(15, 15, 15), width=14 * S)

    hr_ang = math.radians(hour_val * 30 + minute_val * 0.5 - 90)
    hr_len = r_inner - 122 * S
    hx_end = cx + hr_len * math.cos(hr_ang)
    hy_end = cy + hr_len * math.sin(hr_ang)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(15, 15, 15), width=24 * S)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(215, 65, 50), width=14 * S)

    cap_r = 20 * S
    d.ellipse([cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r], fill=(215, 65, 50), outline=(15, 15, 15), width=6 * S)

    # Left digital time badge
    bx1, by1, bx2, by2 = 160 * S, 360 * S, 540 * S, 490 * S
    d.rounded_rectangle([bx1 - 6 * S, by1 + 8 * S, bx2 - 6 * S, by2 + 8 * S], radius=22 * S, fill=(195, 175, 140))
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=22 * S, fill=(255, 226, 110), outline=(15, 15, 15), width=8 * S)
    font_badge = ImageFont.truetype(FONT_BOLD, 64 * S)
    bb = d.textbbox((0, 0), badge_text, font=font_badge)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((bx1 + bx2 - bw) / 2 - bb[0], (by1 + by2 - bh) / 2 - bb[1]), badge_text, font=font_badge, fill=(15, 15, 15))

    # Right day tag
    if sub_tag:
        tx1, ty1, tx2, ty2 = 1380 * S, 380 * S, 1800 * S, 475 * S
        d.rounded_rectangle([tx1, ty1, tx2, ty2], radius=18 * S, fill=(255, 255, 255), outline=(15, 15, 15), width=7 * S)
        f_tag = ImageFont.truetype(FONT_BOLD, 34 * S)
        bbt = d.textbbox((0, 0), sub_tag, font=f_tag)
        d.text(((tx1 + tx2 - (bbt[2] - bbt[0])) / 2 - bbt[0], (ty1 + ty2 - (bbt[3] - bbt[1])) / 2 - bbt[1]), sub_tag, font=f_tag, fill=(15, 15, 15))

    return img.resize((1920, 1080), Image.Resampling.LANCZOS)


def make_host_reaction(pose_filename, flip=False):
    p = os.path.join(FLASH_PACK_DIR, pose_filename)
    pose = Image.open(p).convert("RGBA")
    white_bg = Image.new("RGBA", pose.size, (255, 255, 255, 255))
    rgb = Image.alpha_composite(white_bg, pose).convert("RGB")
    w, h = rgb.size
    px = rgb.load()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    for y in range(10, h - 10):
        for x in range(10, w - 10):
            r, g, b = px[x, y]
            if r < 240 or g < 240 or b < 240:
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y
    pad = 20
    crop = rgb.crop((max(0, min_x - pad), max(0, min_y - pad), min(w, max_x + pad), min(h, max_y + pad)))
    if flip:
        crop = crop.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    cw, ch = crop.size
    target_h = 775
    target_w = int(cw * (target_h / ch))
    if target_w > 1400:
        target_w = 1400
        target_h = int(ch * (target_w / cw))
    resized = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1920, 1080), (255, 255, 255))
    paste_x = (1920 - target_w) // 2
    paste_y = 65 + (775 - target_h) // 2
    rpx = resized.load()
    for yy in range(target_h):
        for xx in range(target_w):
            r, g, b = rpx[xx, yy]
            if r > 242 and g > 242 and b > 238:
                rpx[xx, yy] = (255, 255, 255)
    canvas.paste(resized, (paste_x, paste_y))
    return canvas


def apply_overlay(img, spec):
    out = img.copy()
    d = ImageDraw.Draw(out)
    if spec.startswith("reveal_left:"):
        x_split = int(spec.split(":", 1)[1])
        bg_col = out.getpixel((1890, 40))
        d.rectangle([x_split, 0, 1920, 1080], fill=bg_col)
    elif spec.startswith("closeup:"):
        cx, cy, z = spec.split(":", 1)[1].split(",")
        cx, cy, zoom = int(cx), int(cy), float(z)
        cw = int(1920 / zoom)
        ch = int(1080 / zoom)
        x1 = max(0, min(1920 - cw, cx - cw // 2))
        y1 = max(0, min(1080 - ch, cy - ch // 2))
        out = out.crop((x1, y1, x1 + cw, y1 + ch)).resize((1920, 1080), Image.Resampling.LANCZOS)
    elif spec.startswith("bubble_right:"):
        # Comic speech bubble positioned cleanly over coworker without touching protagonist
        payload = spec.split(":", 1)[1]
        x_s, y_s, txt = payload.split(",", 2)
        cx, cy = int(x_s), int(y_s)
        f = ImageFont.truetype(FONT_BOLD, 33)
        bb = d.textbbox((0, 0), txt, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        bw, bh = tw + 60, th + 40
        bx1 = max(40, min(1885 - bw, cx - bw // 2))
        by1 = max(28, min(680 - bh, cy - bh // 2))
        bx2, by2 = bx1 + bw, by1 + bh
        tail_pts = [(bx2 - 140, by2 - 4), (bx2 - 92, by2 - 4), (bx2 - 58, by2 + 52)]
        d.polygon(tail_pts, fill=(255, 255, 255), outline=(15, 15, 15), width=7)
        d.rounded_rectangle([bx1, by1, bx2, by2], radius=28, fill=(255, 255, 255), outline=(15, 15, 15), width=7)
        d.line([(bx2 - 134, by2 - 4), (bx2 - 96, by2 - 4)], fill=(255, 255, 255), width=9)
        d.text((bx1 + 30 - bb[0], by1 + 20 - bb[1]), txt, font=f, fill=(15, 15, 15))
    return out


def render_visual(spec):
    if spec.startswith("scene:"):
        rest = spec.split(":", 1)[1]
        if "+" in rest:
            s_name, ov = rest.split("+", 1)
            return apply_overlay(load_scene(s_name), ov)
        return load_scene(rest)
    elif spec.startswith("clock:"):
        hr, badge, tag = spec.split(":", 1)[1].split("|")
        return make_flash_12num_clock(int(hr), badge, sub_tag=tag)
    elif spec.startswith("host:"):
        return make_host_reaction(spec.split(":", 1)[1])
    raise ValueError(f"Unknown spec: {spec}")


_SUB_FONT = ImageFont.truetype(FONT_BOLD, 52)
HIGHLIGHT_WORDS = {
    "lie", "truth", "anything", "monday", "coffee", "asleep",
    "weekend", "apartment", "saturday", "phone", "takeout", "four", "early",
}


def burn_cinema_boxless_subtitle(img, text):
    if not text or not text.strip():
        return img
    words = text.strip().split()
    lines = []
    cur = []
    cur_len = 0
    for w in words:
        if cur and cur_len + 1 + len(w) > 40 and len(lines) == 0:
            lines.append(cur)
            cur = [w]
            cur_len = len(w)
        else:
            cur.append(w)
            cur_len += (1 + len(w)) if cur_len else len(w)
    if cur:
        lines.append(cur)

    base = img.convert("RGBA")
    shadow_layer = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    text_layer = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    ds = ImageDraw.Draw(shadow_layer)
    dt = ImageDraw.Draw(text_layer)

    line_h = 64
    total_h = len(lines) * line_h
    start_y = 918 - (total_h // 2) + 22

    for li, lwords in enumerate(lines):
        line_str = " ".join(lwords)
        bb = dt.textbbox((0, 0), line_str, font=_SUB_FONT)
        lw = bb[2] - bb[0]
        x_cursor = (1920 - lw) // 2
        y_pos = start_y + li * line_h

        ds.text((x_cursor, y_pos + 3), line_str, font=_SUB_FONT, fill=(0, 0, 0, 210), stroke_width=10, stroke_fill=(0, 0, 0, 210))

        space_w = dt.textlength(" ", font=_SUB_FONT)
        for w_tok in lwords:
            clean_w = w_tok.lower().strip(".,?!:;\"'—()-")
            is_hl = clean_w in HIGHLIGHT_WORDS
            fill_col = (255, 222, 118, 255) if is_hl else (252, 253, 255, 255)
            dt.text((x_cursor, y_pos), w_tok, font=_SUB_FONT, fill=fill_col, stroke_width=5, stroke_fill=(6, 10, 16, 255))
            x_cursor += dt.textlength(w_tok, font=_SUB_FONT) + space_w

    shadow_blurred = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    out = Image.alpha_composite(base, shadow_blurred)
    out = Image.alpha_composite(out, text_layer)
    return out.convert("RGB")


# 14 clause-level beats synchronized precisely to ep02_hook_words.json (0.00s -> 25.00s)
TIMELINE_25S = [
    (0.00, 1.32, "Why do we lie,", "scene:s01_truth_zero_scale.png+reveal_left:815"),
    (1.32, 2.12, "even when telling the truth", "scene:s01_truth_zero_scale.png"),
    (2.12, 3.65, "wouldn't cost us anything?", "scene:s01_truth_zero_scale.png+closeup:1310,670,1.48"),
    (3.65, 6.20, "Think about a normal Monday morning.", "scene:s02_monday_breakroom_wide.png"),
    (6.20, 8.20, "You're standing by the coffee machine,", "scene:s05_coffee_sleepy.png"),
    (8.20, 9.55, "still half asleep,", "scene:s05_coffee_sleepy.png+closeup:1235,360,1.65"),
    (9.55, 11.75, "and a coworker looks over and asks,", "scene:s06_coworker_waves.png"),
    (11.75, 13.70, '"Hey, how was your weekend?"', "scene:s06_coworker_waves.png+bubble_right:1575,92,HOW WAS YOUR WEEKEND?"),
    (13.70, 15.35, "Maybe the real truth is", "host:06_pose_thinking_lookup.png"),
    (15.35, 17.20, "that you barely left your apartment.", "scene:s03_apartment_door_locked.png"),
    (17.20, 19.65, "You spent most of Saturday on your phone,", "scene:s08_saturday_couch_phone.png"),
    (19.65, 21.92, "ate dinner straight out of a takeout container", "scene:s04_takeout_couch_dinner.png"),
    (21.92, 23.45, "at four in the afternoon,", "clock:4|4:00 PM|SATURDAY"),
    (23.45, 25.00, "and went to bed early.", "scene:s10_bed_early_sunset.png"),
]

# Subtle editorial SFX foley cues: (start_sec, filename, gain_db, max_dur_sec)
SFX_CUES = [
    (1.32, "01_pop_appear.mp3", -15, 0.7),
    (3.70, "09_page_flip.mp3", -16, 0.4),
    (6.40, "24_coffee_pour.mp3", -18, 1.5),
    (8.25, "27_yawn_tired.mp3", -20, 1.2),
    (9.60, "01_pop_appear.mp3", -15, 0.7),
    (17.60, "23_phone_vibrate.mp3", -20, 1.0),
    (21.92, "07_clock_ticking.mp3", -18, 1.45),
    (23.55, "26_sigh_exhausted.mp3", -18, 1.1),
]


def fmt_srt_time(sec):
    ms = int(round(sec * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_frames_and_qa():
    slice_grid_1()
    frame_paths = []
    srt_lines = []
    concat_lines = []

    for idx, (t0, t1, sub, spec) in enumerate(TIMELINE_25S, start=1):
        img = render_visual(spec)
        img = burn_cinema_boxless_subtitle(img, sub)
        fp = os.path.join(FRAMES_DIR, f"frame_{idx:02d}.jpg")
        img.save(fp, quality=95)
        frame_paths.append(fp)

        dur = round(t1 - t0, 3)
        concat_lines.append(f"file '{fp}'")
        concat_lines.append(f"duration {dur:.3f}")

        srt_lines.append(f"{idx}\n{fmt_srt_time(t0)} --> {fmt_srt_time(t1)}\n{sub}\n")

    # FFmpeg concat demuxer requires repeating the final file without duration
    concat_lines.append(f"file '{frame_paths[-1]}'")

    concat_path = os.path.join(EP_DIR, "concat_preview_25s.txt")
    with open(concat_path, "w") as f:
        f.write("\n".join(concat_lines) + "\n")

    srt_path = os.path.join(EP_DIR, "ep02_preview_25s.srt")
    with open(srt_path, "w") as f:
        f.write("\n".join(srt_lines))

    # Build 4x4 visual QA contact sheet (Rule 13)
    cols, rows = 4, 4
    tw, th = 480, 270
    sheet = Image.new("RGB", (cols * tw, rows * th), (24, 24, 28))
    ds = ImageDraw.Draw(sheet)
    f_lbl = ImageFont.truetype(FONT_BOLD, 20)
    for i, fp in enumerate(frame_paths):
        im = Image.open(fp).resize((tw, th), Image.Resampling.LANCZOS)
        r, c = divmod(i, cols)
        sheet.paste(im, (c * tw, r * th))
        t0, t1, _, _ = TIMELINE_25S[i]
        lbl = f"#{i+1:02d} {t0:.2f}-{t1:.2f}s"
        ds.rectangle([c * tw + 6, r * th + 6, c * tw + 185, r * th + 34], fill=(0, 0, 0))
        ds.text((c * tw + 12, r * th + 9), lbl, font=f_lbl, fill=(255, 224, 102))

    sheet_path = os.path.join(EP_DIR, "verify_ep02_25s_sheet.jpg")
    sheet.save(sheet_path, quality=92)
    print(f"Rendered {len(frame_paths)} frames + QA contact sheet: {sheet_path}")
    return concat_path, srt_path, sheet_path


def mix_audio_25s():
    out_audio = os.path.join(EP_DIR, "audio/ep02_preview_25s_mix.mp3")
    cmd = ["ffmpeg", "-y", "-i", VOICE_SRC]
    valid_cues = []
    for t0, fname, gain_db, max_dur in SFX_CUES:
        p = os.path.join(SFX_DIR, fname)
        if os.path.exists(p):
            cmd.extend(["-i", p])
            valid_cues.append((t0, fname, gain_db, max_dur))

    filters = []
    # Trim voice cleanly to 25.00s with gentle 0.15s tail fade
    filters.append("[0:a]atrim=0:25.00,asetpts=PTS-STARTPTS,afade=t=out:st=24.85:d=0.15[v]")
    mix_inputs = ["[v]"]

    for idx, (t0, fname, gain_db, max_dur) in enumerate(valid_cues, start=1):
        delay_ms = int(round(t0 * 1000))
        fade_out_st = max(0.05, max_dur - 0.20)
        filters.append(
            f"[{idx}:a]atrim=0:{max_dur:.2f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.05,afade=t=out:st={fade_out_st:.2f}:d=0.20,"
            f"volume={gain_db}dB,adelay={delay_ms}|{delay_ms}[s{idx}]"
        )
        mix_inputs.append(f"[s{idx}]")

    filters.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:duration=first:dropout_transition=0:normalize=0,"
        f"loudnorm=I=-14.0:TP=-1.0:LRA=11[aout]"
    )
    cmd.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[aout]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        out_audio,
    ])
    subprocess.run(cmd, check=True)
    print(f"Mixed 25s audio master: {out_audio}")
    return out_audio


def encode_video_25s():
    concat_path = os.path.join(EP_DIR, "concat_preview_25s.txt")
    audio_path = mix_audio_25s()
    out_mp4 = os.path.join(EP_DIR, "ep02_pointless_lies_25s_preview.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", audio_path,
        "-vf", "fps=30,scale=1920:1080,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-t", "25.00",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"Encoded 25s preview MP4: {out_mp4}")
    return out_mp4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--encode", action="store_true")
    args = ap.parse_args()
    if args.frames_only:
        build_frames_and_qa()
    elif args.encode:
        encode_video_25s()
    else:
        build_frames_and_qa()
        encode_video_25s()
