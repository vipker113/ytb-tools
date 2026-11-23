#!/usr/bin/env python3
"""
Kairo Spark — Pilot Episode #1: "Why Do We Work 5 Days a Week?"
100% Visual 2D Adobe Flash Multi-State Clause-Level Pipeline (Ink Explainer Style)
Obeys Rules 1–14 in .agents/rules/kairo-stickman-style.md:
- ZERO programmatic text-box cards (no make_stamp_card, no make_split_card)
- ZERO programmatic top-pill UI badges (no +badge:)
- 140 unique painted 2D Flash visual illustrations across all 5 Acts (01..56, 73..136, plus 20 opening frames)
- Authentic Ink Explainer State A -> State B progressions:
  * Progressive Split/Column Reveal (+reveal_left, +reveal_col1, +reveal_col2 -> Full Drawn Scene)
  * Multi-Camera Instant Static Close-Up Cut (+closeup:cx,cy,zoom)
  * In-World Comic Speech Bubble Pop-In (+bubble:x,y,text) & Prop Red X / Green Check Slams (+x_on, +check_on)
  * 1-Second Medium-Shot White-BG Host Reaction Cuts & 12-Number Clock Cutaways
- pow_studio cinema_boxless subtitles at y=918
"""

import os
import sys
import json
import math
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

BRAIN = "/Users/admin/.gemini/antigravity/brain/9c914627-c4fa-4486-ab2e-ea9740fd1166"
EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/pilot-01-why-5-days"
SCENES_DIR = os.path.join(EP_DIR, "scenes")
FLASH_PACK_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack"
TIMESTAMPS_JSON = os.path.join(EP_DIR, "audio/voice_master_timestamps.json")
AUDIO_MASTER = os.path.join(EP_DIR, "audio/pilot_01_full_mix_master.mp3")
FONT_BOLD = "/Applications/code/science-knowledge/youtube-shorts-channel/assets/fonts/BeVietnamPro-Bold.ttf"

FRAMES_DIR = os.path.join(EP_DIR, "frames_master_v3")
PREVIEW_FRAMES_DIR = os.path.join(EP_DIR, "preview_28s_frames")
os.makedirs(FRAMES_DIR, exist_ok=True)
os.makedirs(PREVIEW_FRAMES_DIR, exist_ok=True)

_SCENE_CACHE = {}
_ALL_SCENE_FILES = sorted(os.listdir(SCENES_DIR))

def load_scene(name):
    if name not in _SCENE_CACHE:
        p = os.path.join(SCENES_DIR, name)
        if not os.path.exists(p):
            prefix = name.split("_")[0] + "_"
            matches = [f for f in _ALL_SCENE_FILES if f.startswith(prefix) and f.endswith(".png")]
            if not matches:
                raise FileNotFoundError(f"No scene matching {name} (prefix {prefix})")
            p = os.path.join(SCENES_DIR, matches[0])
        _SCENE_CACHE[name] = Image.open(p).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
    return _SCENE_CACHE[name].copy()


# ==============================================================================
# 1. 2x-SUPERSAMPLED 12-NUMBER CLOCK GENERATOR (RULE 11 & RULE 12)
# ==============================================================================
def make_flash_12num_clock(hour_val, badge_text, sub_tag="SUNDAY EVENING", show_arc_from=None, minute_val=0, bg_wall=(236, 217, 178)):
    S = 2
    W, H = 1920 * S, 1080 * S
    img = Image.new("RGB", (W, H), bg_wall)
    d = ImageDraw.Draw(img)

    cx, cy = 960 * S, 445 * S
    r_outer = 320 * S  # bottom of clock is y=765 (153px above y=918 subtitle!)

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
        d.text((nx - tw / 2 - bbox[0], ny - th / 2 - bb_offset(bbox)), txt, font=f_use, fill=(205, 35, 35) if is_target else (15, 15, 15))

    if show_arc_from is not None:
        arc_r = r_inner - 135 * S
        for a_deg in range(show_arc_from * 30 - 85, hour_val * 30 - 92, 6):
            ar = math.radians(a_deg)
            px, py = cx + arc_r * math.cos(ar), cy + arc_r * math.sin(ar)
            d.ellipse([px - 5 * S, py - 5 * S, px + 5 * S, py + 5 * S], fill=(215, 50, 50))

    min_ang = math.radians(minute_val * 6 - 90)
    mx_end = cx + int((r_inner - 64 * S) * math.cos(min_ang))
    my_end = cy + int((r_inner - 64 * S) * math.sin(min_ang))
    d.line([(cx, cy), (mx_end, my_end)], fill=(15, 15, 15), width=14 * S)

    hr_ang = math.radians(hour_val * 30 + minute_val * 0.5 - 90)
    hr_len = r_inner - 122 * S
    hx_end = cx + hr_len * math.cos(hr_ang)
    hy_end = cy + hr_len * math.sin(hr_ang)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(15, 15, 15), width=24 * S)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(215, 65, 50), width=14 * S)

    cap_r = 20 * S
    d.ellipse([cx - cap_r, cy - cap_r, cx + cap_r, cy + cap_r], fill=(215, 65, 50), outline=(15, 15, 15), width=6 * S)

    bx1, by1, bx2, by2 = 160 * S, 360 * S, 540 * S, 490 * S
    d.rounded_rectangle([bx1 - 6 * S, by1 + 8 * S, bx2 - 6 * S, by2 + 8 * S], radius=22 * S, fill=(195, 175, 140))
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=22 * S, fill=(255, 226, 110), outline=(15, 15, 15), width=8 * S)
    font_badge = ImageFont.truetype(FONT_BOLD, 64 * S)
    bb = d.textbbox((0, 0), badge_text, font=font_badge)
    bw, bh = bb[2] - bb[0], bb[3] - bb[1]
    d.text(((bx1 + bx2 - bw) / 2 - bb[0], (by1 + by2 - bh) / 2 - bb[1]), badge_text, font=font_badge, fill=(15, 15, 15))

    if sub_tag:
        tx1, ty1, tx2, ty2 = 1380 * S, 380 * S, 1800 * S, 475 * S
        d.rounded_rectangle([tx1, ty1, tx2, ty2], radius=18 * S, fill=(255, 255, 255), outline=(15, 15, 15), width=7 * S)
        f_tag = ImageFont.truetype(FONT_BOLD, 34 * S)
        bbt = d.textbbox((0, 0), sub_tag, font=f_tag)
        d.text(((tx1 + tx2 - (bbt[2] - bbt[0])) / 2 - bbt[0], (ty1 + ty2 - (bbt[3] - bbt[1])) / 2 - bbt[1]), sub_tag, font=f_tag, fill=(15, 15, 15))

    return img.resize((1920, 1080), Image.Resampling.LANCZOS)

def bb_offset(bbox):
    return bbox[1]


# ==============================================================================
# 2. 1-SECOND WHITE-BG MEDIUM-SHOT HOST REACTION GENERATOR (RULE 5)
# ==============================================================================
_HOST_CACHE = {}
HOST_POSE_ALIASES = {
    "01_pose_explaining.png": "01_pose_shrug_question.png",
    "02_pose_shrug_question.png": "06_pose_thinking_lookup.png",
    "03_pose_shocked_hands_head.png": "03_pose_exhausted_burnout.png",
    "04_pose_facepalm_sigh.png": "03_pose_exhausted_burnout.png",
    "05_pose_pointing_aha.png": "04_pose_eureka_point_up.png",
    "09_pose_top_hat_factory_boss.png": "02_pose_walk_idea.png",
}

def make_host_reaction(pose_filename, flip=False):
    actual_name = HOST_POSE_ALIASES.get(pose_filename, pose_filename)
    key = (actual_name, flip)
    if key in _HOST_CACHE:
        return _HOST_CACHE[key].copy()
    p = os.path.join(FLASH_PACK_DIR, actual_name)
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
    _HOST_CACHE[key] = canvas
    return canvas.copy()


# ==============================================================================
# 3. AUTHENTIC INK EXPLAINER STATE-A -> STATE-B VISUAL OPERATORS (ZERO TOP-PILL BADGES!)
# ==============================================================================
def apply_state_overlay(img, overlay_spec):
    """
    Authentic Ink Explainer visual state operators:
    - 'reveal_left' or 'reveal_left:X_SPLIT' -> Masks the right half of a 2-column drawn scene with its background color (State A), so the full scene reveals the right half on State B!
    - 'reveal_col1' / 'reveal_col2' -> Progressive 3-column reveal on 3-part drawn scenes (114, 134)
    - 'closeup:CX,CY,ZOOM' -> Instant static multi-camera cut-in close-up on a character or key prop (0.000 motion)
    - 'bubble:X,Y,TEXT' -> In-world white oval comic speech bubble with black marker outline & pointer tail
    - 'x_on:CX,CY,R' -> Bold 2D Flash red X slammed directly onto a prop at (CX,CY)
    - 'check_on:CX,CY' -> Bold 2D Flash green checkmark circle popped in at (CX,CY)
    """
    out = img.copy()
    d = ImageDraw.Draw(out)

    if overlay_spec.startswith("reveal_left"):
        parts = overlay_spec.split(":")
        x_split = int(parts[1]) if len(parts) > 1 else 965
        bg_col = out.getpixel((1890, 40))
        d.rectangle([x_split, 0, 1920, 1080], fill=bg_col)

    elif overlay_spec == "reveal_col1":
        bg_col = out.getpixel((1890, 40))
        d.rectangle([655, 0, 1920, 1080], fill=bg_col)

    elif overlay_spec == "reveal_col2":
        bg_col = out.getpixel((1890, 40))
        d.rectangle([1285, 0, 1920, 1080], fill=bg_col)

    elif overlay_spec.startswith("closeup:"):
        payload = overlay_spec.split(":", 1)[1]
        cx_s, cy_s, z_s = payload.split(",")
        cx, cy, zoom = int(cx_s), int(cy_s), float(z_s)
        cw = int(1920 / zoom)
        ch = int(1080 / zoom)
        x1 = max(0, min(1920 - cw, cx - cw // 2))
        y1 = max(0, min(1080 - ch, cy - ch // 2))
        out = out.crop((x1, y1, x1 + cw, y1 + ch)).resize((1920, 1080), Image.Resampling.LANCZOS)

    elif overlay_spec.startswith("bubble:"):
        payload = overlay_spec.split(":", 1)[1]
        x_str, y_str, txt = payload.split(",", 2)
        cx, cy = int(x_str), min(700, int(y_str))
        f = ImageFont.truetype(FONT_BOLD, 40)
        bb = d.textbbox((0, 0), txt, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        bw, bh = tw + 72, th + 48
        bx1 = max(50, min(1870 - bw, cx - bw // 2))
        by1 = max(45, min(720 - bh, cy - bh // 2))
        bx2, by2 = bx1 + bw, by1 + bh
        tx = (bx1 + bx2) // 2
        d.polygon([(tx - 22, by2 - 4), (tx + 22, by2 - 4), (tx - 10, by2 + 38)], fill=(255, 255, 255), outline=(15, 15, 15), width=7)
        d.rounded_rectangle([bx1, by1, bx2, by2], radius=32, fill=(255, 255, 255), outline=(15, 15, 15), width=7)
        d.text((bx1 + 36 - bb[0], by1 + 24 - bb[1]), txt, font=f, fill=(15, 15, 15))

    elif overlay_spec.startswith("x_on:"):
        payload = overlay_spec.split(":", 1)[1]
        cx_s, cy_s, r_s = payload.split(",")
        cx, cy, r = int(cx_s), min(680, int(cy_s)), int(r_s)
        d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=(15, 15, 15), width=42)
        d.line([(cx + r, cy - r), (cx - r, cy + r)], fill=(15, 15, 15), width=42)
        d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=(228, 55, 50), width=28)
        d.line([(cx + r, cy - r), (cx - r, cy + r)], fill=(228, 55, 50), width=28)

    elif overlay_spec.startswith("check_on:"):
        payload = overlay_spec.split(":", 1)[1]
        cx_s, cy_s = payload.split(",")
        cx, cy = int(cx_s), min(680, int(cy_s))
        r = 68
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(104, 204, 118), outline=(15, 15, 15), width=8)
        d.line([(cx - 30, cy + 4), (cx - 6, cy + 28), (cx + 34, cy - 22)], fill=(15, 15, 15), width=14)

    return out


def render_visual_spec(spec):
    if spec.startswith("scene:"):
        rest = spec.split(":", 1)[1]
        if "+" in rest:
            s_name, ov = rest.split("+", 1)
            return apply_state_overlay(load_scene(s_name), ov)
        return load_scene(rest)
    elif spec.startswith("clock:"):
        parts = spec.split(":", 1)[1].split("|")
        hr = int(parts[0])
        b_txt = parts[1]
        s_tag = parts[2] if len(parts) > 2 else ""
        arc = int(parts[3]) if (len(parts) > 3 and parts[3] != "") else None
        min_v = int(parts[4]) if (len(parts) > 4 and parts[4] != "") else 0
        return make_flash_12num_clock(hr, b_txt, sub_tag=s_tag, show_arc_from=arc, minute_val=min_v)
    elif spec.startswith("host:") or spec.startswith("host_flip:"):
        flip = spec.startswith("host_flip:")
        p_name = spec.split(":", 1)[1]
        return make_host_reaction(p_name, flip=flip)
    elif spec.startswith("pre28:"):
        f_idx = int(spec.split(":", 1)[1])
        p = os.path.join(PREVIEW_FRAMES_DIR, f"frame_{f_idx:02d}.jpg")
        return Image.open(p).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
    else:
        raise ValueError(f"Unknown visual spec: {spec}")


# ==============================================================================
# 4. POW_STUDIO CINEMA_BOXLESS SUBTITLE RENDERER (RULE 12)
# ==============================================================================
_SUB_FONT = ImageFont.truetype(FONT_BOLD, 52)

HIGHLIGHT_WORDS = {
    "sunday", "seven", "eight", "monday", "five", "two", "1991", "harvard", "14th",
    "150", "260", "100", "half", "300-year", "clock", "task", "1700s", "saint",
    "tuesday", "steam", "penny", "furnace", "1967", "gears", "six", "watches",
    "30", "fines", "1850s", "12", "cage", "saturday", "ford", "1926", "six-dollar",
    "steel", "spied", "math", "model", "customer", "shopping", "1930s", "40-hour",
    "1930", "keynes", "15", "1933", "senate", "53", "kellogg's", "six-hour",
    "roosevelt", "buried", "1938", "40", "froze", "300", "percent", "1940",
    "four", "seconds", "501", "5:01", "friday", "1955", "parkinson", "warm",
    "17", "kalahari", "90", "broken", "human",
}

def burn_cinema_boxless_subtitle(img, text):
    if not text or not text.strip():
        return img
    text = text.strip().replace("501", "5:01")
    words = text.split()
    lines = []
    cur = []
    cur_len = 0
    for w in words:
        if cur and cur_len + 1 + len(w) > 42 and len(lines) == 0:
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


# ==============================================================================
# 5. FIRST 28.58s: EXACT 20 VERIFIED CLAUSE-LEVEL FRAMES (WITH 12-NUMBER CLOCKS)
# ==============================================================================
OPENING_20_FRAMES = [
    (0.00, 1.56, "", "pre28:1"),
    (1.56, 2.35, "around seven...", "clock:7|7:00 PM|SUNDAY EVENING||0"),
    (2.35, 3.46, "...or eight o'clock,", "clock:8|8:00 PM|TOMORROW IS MONDAY|7|0"),
    (3.46, 5.50, "", "pre28:4"),
    (5.50, 6.45, "", "pre28:5"),
    (6.45, 7.78, "", "pre28:6"),
    (7.78, 8.55, "", "pre28:7"),
    (8.55, 9.66, "", "pre28:8"),
    (9.66, 11.20, "", "pre28:9"),
    (11.20, 12.25, "", "pre28:10"),
    (12.25, 13.44, "", "pre28:11"),
    (13.44, 14.34, "", "pre28:12"),
    (14.34, 16.98, "", "pre28:13"),
    (16.98, 17.85, "", "pre28:14"),
    (17.85, 19.16, "", "pre28:15"),
    (19.16, 21.12, "", "pre28:16"),
    (21.12, 22.80, "", "pre28:17"),
    (22.80, 25.14, "", "pre28:18"),
    (25.14, 26.95, "", "pre28:19"),
    (26.95, 28.58, "", "pre28:20"),
]

# ==============================================================================
# 6. SEGMENTS 009..169 (28.58s - 541.48s): 100% DRAWN 2D FLASH VISUAL TIMELINE
#    ZERO PIL TEXT CARDS (stamp:/split:), ZERO TOP-PILL BADGES (+badge:)
# ==============================================================================
SEG_VISUAL_MAP = {
    # Act I: The Myth of the Brutal Grind vs. 14th-Century Peasant Reality
    9:  ["scene:11_ref_sunday_tv_calendar.png"],
    10: ["scene:73_earth_sun_moon_24h_cycle.png+reveal_left:1280",
         "scene:73_earth_sun_moon_24h_cycle.png"],
    11: ["scene:74_street_interview_mic_story.png+closeup:580,520,1.35"],
    12: ["scene:74_street_interview_mic_story.png"],
    13: ["scene:75_caveman_boulder_sunrise_sunset.png"],
    14: ["scene:14_ancient_sunrise_hill_stretch.png",
         "scene:75_caveman_boulder_sunrise_sunset.png+closeup:620,620,1.35"],
    15: ["scene:75_caveman_boulder_sunrise_sunset.png+bubble:580,260,JUST TO SURVIVE!"],
    16: ["scene:76_official_story_textbook_podium.png",
         "scene:76_official_story_textbook_podium.png+closeup:1320,560,1.38"],
    17: ["scene:76_official_story_textbook_podium.png+check_on:1680,220"],
    18: ["host:05_pose_pointing_aha.png"],
    19: ["scene:15_harvard_150_days_ledger.png"],
    20: ["scene:77_medieval_scrolls_parish_court.png"],
    21: ["scene:77_medieval_scrolls_parish_court.png+closeup:960,520,1.32"],
    22: ["host:03_pose_shocked_hands_head.png"],
    23: ["scene:78_harvard_1991_juliet_schor.png",
         "scene:78_harvard_1991_juliet_schor.png+closeup:1380,540,1.35"],
    24: ["scene:15_harvard_150_days_ledger.png+closeup:960,520,1.32",
         "scene:15_harvard_150_days_ledger.png+bubble:1320,210,WAIT... ONLY 150 DAYS?!"],
    25: ["scene:79_feudal_lord_castle_tax.png"],
    26: ["scene:33_no_tractor_x.png",
         "scene:34_no_lightbulb_x.png",
         "scene:79_feudal_lord_castle_tax.png+x_on:1320,540,180"],
    27: ["host:01_pose_explaining.png"],
    28: ["scene:02_medieval_150_days_picnic.png",
         "scene:80_scale_150_peasant_vs_260_office.png+reveal_left:960"],
    29: ["scene:80_scale_150_peasant_vs_260_office.png",
         "scene:12_ref_chart_150_vs_260_board.png"],
    30: ["scene:81_winter_snow_cottage_rest.png"],
    31: ["scene:16_medieval_parish_feast_table.png"],
    32: ["scene:82_half_year_pie_chart_feast.png"],
    33: ["scene:82_half_year_pie_chart_feast.png+bubble:1420,180,HALF THE YEAR FREE!"],
    34: ["scene:83_midday_dinner_bell_field.png+closeup:1580,340,1.45"],
    35: ["scene:83_midday_dinner_bell_field.png"],
    36: ["scene:35_medieval_feast_nap.png"],
    37: ["scene:84_power_grid_server_prison_bars.png+reveal_left:1100"],
    38: ["scene:68_open_calendar_monday_dread.png"],
    39: ["scene:84_power_grid_server_prison_bars.png+closeup:620,560,1.35"],
    40: ["scene:84_power_grid_server_prison_bars.png"],

    # Act II: The 300-Year War Over the Clock, Task Work & Saint Monday
    41: ["scene:85_300_year_clock_battlefield.png",
         "scene:85_300_year_clock_battlefield.png+closeup:960,460,1.35"],
    42: ["scene:36_pocket_watch_closeup.png"],
    43: ["clock:12|THE CLOCK|300-YEAR WAR||0"],
    44: ["scene:14_ancient_sunrise_hill_stretch.png+closeup:640,540,1.32"],
    45: ["scene:36b_pocket_watch_x.png"],
    46: ["scene:86_task_checklist_go_home.png+reveal_left:960",
         "scene:86_task_checklist_go_home.png"],
    47: ["scene:37_cobbler_workshop.png"],
    48: ["scene:39_tuesday_loom_work.png"],
    49: ["scene:87_burst_effort_vs_hammock_rest.png+reveal_left:780"],
    50: ["scene:87_burst_effort_vs_hammock_rest.png"],
    51: ["scene:88_customer_boot_order_rush.png"],
    52: ["scene:88_customer_boot_order_rush.png+closeup:1250,540,1.35"],
    53: ["scene:17_blacksmith_done_for_today.png",
         "scene:17_blacksmith_done_for_today.png+check_on:420,380"],
    54: ["scene:38_saint_monday_map.png"],
    55: ["scene:18_tavern_sunday_mugs.png"],
    56: ["scene:89_angry_1700s_merchant_empty_shop.png"],
    57: ["scene:38_saint_monday_map.png+closeup:960,460,1.28"],
    58: ["scene:24_sunday_morning_church_walk.png",
         "scene:18_tavern_sunday_mugs.png+bubble:960,165,CHEERS TO SUNDAY!"],
    59: ["scene:90_monday_morning_hangover_bed.png"],
    60: ["scene:89_angry_1700s_merchant_empty_shop.png+closeup:1280,460,1.35"],
    61: ["scene:03_saint_monday_closed_loom.png"],
    62: ["scene:39_tuesday_loom_work.png+closeup:1180,540,1.32"],
    63: ["scene:91_thursday_friday_candle_rush.png",
         "scene:91_thursday_friday_candle_rush.png+closeup:1280,560,1.32"],
    64: ["scene:92_hourglass_in_artisan_hands.png+reveal_left:960"],
    65: ["scene:92_hourglass_in_artisan_hands.png"],
    66: ["scene:03_saint_monday_closed_loom.png+closeup:640,480,1.32"],
    67: ["scene:40_loom_vs_furnace_cost.png+reveal_left:960"],
    68: ["scene:93_cold_iron_factory_rust_loss.png"],
    69: ["scene:93_cold_iron_factory_rust_loss.png+closeup:780,540,1.32"],
    70: ["scene:40_loom_vs_furnace_cost.png"],
    71: ["scene:94_ep_thompson_1967_history_book.png",
         "scene:94_ep_thompson_1967_history_book.png+closeup:960,480,1.32"],
    72: ["scene:04_factory_1850s_master_clock.png"],
    73: ["scene:95_drill_sergeant_factory_lineup.png"],
    74: ["scene:41_human_in_gears.png",
         "scene:41_human_in_gears.png+closeup:960,500,1.32"],
    75: ["scene:95_drill_sergeant_factory_lineup.png+closeup:960,520,1.32",
         "scene:04_factory_1850s_master_clock.png+closeup:1250,480,1.32"],
    76: ["scene:20_textile_mill_no_watches.png"],
    77: ["scene:20_textile_mill_no_watches.png+x_on:1180,680,170"],
    78: ["scene:96_padlocked_factory_master_clock.png"],
    79: ["scene:96_padlocked_factory_master_clock.png+closeup:1180,520,1.35"],
    80: ["scene:42_clock_tampering_30m.png"],
    81: ["scene:42_clock_tampering_30m.png+closeup:1080,460,1.30",
         "scene:97_exhausted_workers_night_shift.png"],
    82: ["scene:43_factory_fine_ticket.png"],
    83: ["scene:44_feast_days_trashed.png"],
    84: ["scene:19_steam_boiler_boss_clock.png",
         "scene:98_1850s_72_hour_iron_birdcage.png+closeup:960,480,1.35"],
    85: ["scene:98_1850s_72_hour_iron_birdcage.png"],
    86: ["scene:24_sunday_morning_church_walk.png+closeup:1160,520,1.32"],
    87: ["scene:99_evolution_march_into_cage.png+reveal_left:920"],
    88: ["scene:99_evolution_march_into_cage.png"],

    # Act III: Henry Ford (1926), The Customer Paradox & The Invention of Saturday Shopping
    89: ["scene:100_saturday_breaking_chains.png",
         "scene:100_saturday_breaking_chains.png+closeup:960,480,1.32"],
    90: ["scene:21_ford_1926_assembly_line.png"],
    91: ["scene:101_sept_25_1926_newspaper_flash.png+closeup:960,440,1.35"],
    92: ["scene:101_sept_25_1926_newspaper_flash.png"],
    93: ["scene:101_sept_25_1926_newspaper_flash.png+bubble:960,150,ONLY 5 DAYS A WEEK!"],
    94: ["scene:45_six_dollar_envelope.png",
         "scene:45_six_dollar_envelope.png+check_on:1620,220"],
    95: ["scene:102_ford_angel_halo_disguise.png"],
    96: ["scene:22_steel_boss_angry_5days.png",
         "scene:103_us_steel_moral_collapse_podium.png+reveal_left:1180"],
    97: ["scene:103_us_steel_moral_collapse_podium.png"],
    98: ["host:05_pose_pointing_aha.png"],
    99: ["scene:104_ford_stopwatch_whip_assembly.png",
         "scene:104_ford_stopwatch_whip_assembly.png+closeup:1240,560,1.35"],
    100: ["scene:46_sociological_spy.png"],
    101: ["scene:46_sociological_spy.png+closeup:680,460,1.35"],
    102: ["scene:102_ford_angel_halo_disguise.png+x_on:1180,380,220"],
    103: ["scene:105_ford_chalkboard_fatal_math.png",
          "scene:105_ford_chalkboard_fatal_math.png+closeup:1140,390,1.35"],
    104: ["scene:21_ford_1926_assembly_line.png+closeup:860,520,1.32"],
    105: ["scene:106_overflowing_model_t_parking_lot.png"],
    106: ["scene:107_worker_piggybank_car_price.png+reveal_left:780"],
    107: ["host:01_pose_explaining.png"],
    108: ["scene:107_worker_piggybank_car_price.png",
          "scene:23_exhausted_worker_bed_model_t.png"],
    109: ["scene:23_exhausted_worker_bed_model_t.png+closeup:640,620,1.35",
          "scene:24_sunday_morning_church_walk.png"],
    110: ["scene:108_closed_store_sleeping_worker.png",
          "scene:108_closed_store_sleeping_worker.png+closeup:1320,560,1.35"],
    111: ["scene:109_ford_interview_magazine_mic.png"],
    112: ["scene:47_worlds_work_magazine.png"],
    113: ["scene:110_wardrobe_clothes_rack_shopping.png"],
    114: ["scene:111_weekend_diner_feast_table.png"],
    115: ["scene:112_family_highway_roadtrip_model_t.png"],
    116: ["scene:106_overflowing_model_t_parking_lot.png+check_on:1620,200",
          "scene:05_ford_1926_model_t_shopping.png"],
    117: ["host:03_pose_shocked_hands_head.png"],
    118: ["scene:48_tree_vs_shopping_split.png+reveal_left:960",
          "scene:48_tree_vs_shopping_split.png"],
    119: ["scene:113_saturday_mall_cash_register.png",
          "scene:113_saturday_mall_cash_register.png+closeup:720,460,1.32"],
    120: ["scene:114_three_part_week_cycle_diagram.png+reveal_col1"],
    121: ["scene:114_three_part_week_cycle_diagram.png+reveal_col2"],
    122: ["scene:114_three_part_week_cycle_diagram.png"],

    # Act IV: Keynes's 15-Hour Prediction & The 1933 30-Hour Senate Bill
    123: ["scene:115_school_classroom_censored_history.png",
          "scene:115_school_classroom_censored_history.png+closeup:960,460,1.32"],
    124: ["scene:49_keynes_road_fork.png"],
    125: ["scene:116_downward_stairs_60_48_40_15.png"],
    126: ["scene:25_keynes_1930_15hrs_chalkboard.png",
          "scene:117_keynes_grandchildren_3hr_beach.png+reveal_left:820"],
    127: ["scene:117_keynes_grandchildren_3hr_beach.png",
          "scene:117_keynes_grandchildren_3hr_beach.png+closeup:1320,480,1.35"],
    128: ["scene:118_1933_depression_soup_line_capitol.png"],
    129: ["scene:50_hugo_black_30hr_bill.png",
          "scene:06_senate_1933_30hr_gavel.png"],
    130: ["scene:119_factory_30hr_speed_limit_sign.png"],
    131: ["scene:119_factory_30hr_speed_limit_sign.png+closeup:760,520,1.35",
          "scene:06_senate_1933_30hr_gavel.png+closeup:960,480,1.32"],
    132: ["scene:120_senate_scoreboard_53_to_30.png",
          "scene:120_senate_scoreboard_53_to_30.png+closeup:960,360,1.38"],
    133: ["scene:51_kellogg_6hr_shift.png",
          "scene:121_kellogg_cereal_box_safety_chart.png"],
    134: ["scene:121_kellogg_cereal_box_safety_chart.png+closeup:1180,340,1.35",
          "scene:26_kellogg_2pm_park_family.png"],
    135: ["scene:122_1933_6hr_law_finish_line_tape.png",
          "scene:122_1933_6hr_law_finish_line_tape.png+closeup:1120,480,1.32"],
    136: ["scene:27_lobby_hallway_top_hats.png"],
    137: ["scene:123_oval_office_lobbyists_roosevelt.png",
          "scene:123_oval_office_lobbyists_roosevelt.png+bubble:740,160,THEY WILL NEVER GO BACK TO 40H!"],
    138: ["scene:123_oval_office_lobbyists_roosevelt.png+closeup:680,480,1.35"],
    139: ["scene:52_buried_30hr_bill.png"],
    140: ["scene:124_1938_flsa_padlock_40_hours.png",
          "scene:124_1938_flsa_padlock_40_hours.png+closeup:960,520,1.32"],
    141: ["scene:28_frozen_40hrs_ice_clock.png"],
    142: ["scene:125_300_percent_rocket_vs_flat_40h.png",
          "scene:125_300_percent_rocket_vs_flat_40h.png+closeup:1080,420,1.32"],
    143: ["scene:29_1940_clerks_vs_today_laptop.png",
          "scene:126_4_second_stopwatch_spreadsheet.png"],
    144: ["scene:25_keynes_1930_15hrs_chalkboard.png+check_on:1580,220"],
    145: ["scene:127_tuesday_afternoon_office_exit.png"],
    146: ["clock:5|5:01 PM|FRIDAY • STILL AT YOUR DESK||1",
          "scene:128_friday_501pm_fluorescent_prison.png"],

    # Act V: Parkinson's Law, Graeber's 15-Hour Reality & The 90-Year Blip
    147: ["scene:129_parkinson_1955_economist_gas_balloon.png+reveal_left:830",
          "scene:129_parkinson_1955_economist_gas_balloon.png"],
    148: ["scene:129_parkinson_1955_economist_gas_balloon.png+closeup:1180,480,1.32",
          "scene:54_parkinson_5h_vs_35h_stacks.png"],
    149: ["scene:130_factory_shoes_vs_office_chair_clock.png+reveal_left:960"],
    150: ["scene:130_factory_shoes_vs_office_chair_clock.png",
          "scene:53_warm_chair_40hrs.png"],
    151: ["scene:54_parkinson_5h_vs_35h_stacks.png+closeup:960,640,1.38"],
    152: ["scene:30_bored_meeting_conference.png",
          "scene:07_office_501pm_email_meeting.png"],
    153: ["scene:131_david_graeber_15_20_hours_confession.png"],
    154: ["scene:131_david_graeber_15_20_hours_confession.png+closeup:960,480,1.32"],
    155: ["scene:10_ref_kalahari_campfire_17hrs.png",
          "scene:132_kalahari_17h_vs_office_17h_mirror.png"],
    156: ["scene:55_fake_busy_mask.png",
          "scene:55_fake_busy_mask.png+closeup:860,520,1.32"],
    157: ["host:02_pose_shrug_question.png"],
    158: ["scene:49_keynes_road_fork.png+x_on:1480,380,220"],
    159: ["scene:31_treadmill_house_phone_dollar.png"],
    160: ["scene:133_mansion_suv_giant_receipt_chain.png"],
    161: ["scene:133_mansion_suv_giant_receipt_chain.png+closeup:640,520,1.32"],
    162: ["scene:56_human_history_90yrs.png"],
    163: ["scene:56_human_history_90yrs.png+closeup:1460,520,1.38"],
    164: ["scene:134_three_fathers_of_5_day_week.png+reveal_col1"],
    165: ["scene:134_three_fathers_of_5_day_week.png+reveal_col2"],
    166: ["scene:134_three_fathers_of_5_day_week.png"],
    167: ["scene:13_sunday_night_moon_sofa.png",
          "scene:135_sunday_night_heartbeat_window.png"],
    168: ["scene:09_ref_office_clock_desk.png",
          "scene:135_sunday_night_heartbeat_window.png+closeup:960,520,1.32"],
    169: ["scene:08_sunset_hilltop_coffee_peace.png",
          "scene:136_human_nature_sun_tree_freedom.png"],
}


def split_segment_words(seg, n_parts):
    words = seg.get("words", [])
    st = seg["start"]
    en = seg["end"]
    if n_parts <= 1 or len(words) < n_parts * 2:
        return [(st, en, seg["text"].strip())]

    if n_parts == 2:
        mid = len(words) // 2
        best_idx = mid
        best_score = 999
        for i in range(max(2, len(words) // 4), min(len(words) - 2, (len(words) * 3) // 4 + 1)):
            w_txt = words[i - 1]["w"].strip()
            has_punct = w_txt.endswith((",", ";", ":", "—", "-"))
            dist = abs(i - mid) - (4 if has_punct else 0)
            if dist < best_score:
                best_score = dist
                best_idx = i
        t_split = round((words[best_idx - 1]["e"] + words[best_idx]["s"]) / 2.0, 2)
        if t_split <= st + 0.4 or t_split >= en - 0.4:
            t_split = round((st + en) / 2.0, 2)
        txt1 = " ".join(w["w"].strip() for w in words[:best_idx]).strip()
        txt2 = " ".join(w["w"].strip() for w in words[best_idx:]).strip()
        return [(st, t_split, txt1), (t_split, en, txt2)]

    elif n_parts == 3:
        comma_indices = [i + 1 for i, w in enumerate(words[:-1]) if w["w"].strip().endswith(",")]
        if len(comma_indices) >= 2:
            i1, i2 = comma_indices[0], comma_indices[1]
        else:
            i1, i2 = len(words) // 3, (len(words) * 2) // 3
        t1 = round((words[i1 - 1]["e"] + words[i1]["s"]) / 2.0, 2)
        t2 = round((words[i2 - 1]["e"] + words[i2]["s"]) / 2.0, 2)
        txt1 = " ".join(w["w"].strip() for w in words[:i1]).strip()
        txt2 = " ".join(w["w"].strip() for w in words[i1:i2]).strip()
        txt3 = " ".join(w["w"].strip() for w in words[i2:]).strip()
        return [(st, t1, txt1), (t1, t2, txt2), (t2, en, txt3)]


def build_full_timeline():
    with open(TIMESTAMPS_JSON) as f:
        data = json.load(f)
    total_dur = float(data["duration"])
    segs = data["segments"]

    raw_shots = []
    for st, en, sub_txt, v_spec in OPENING_20_FRAMES:
        raw_shots.append({"start": st, "end": en, "sub": sub_txt, "spec": v_spec})

    for idx in range(9, len(segs)):
        seg = segs[idx]
        specs = SEG_VISUAL_MAP.get(idx, ["scene:01_sunday_8pm_couch_monday.png"])
        parts = split_segment_words(seg, len(specs))
        for (p_st, p_en, p_txt), sp in zip(parts, specs):
            raw_shots.append({"start": p_st, "end": p_en, "sub": p_txt, "spec": sp})

    timeline = []
    for i, sh in enumerate(raw_shots):
        st = 0.0 if i == 0 else timeline[-1]["end"]
        en = total_dur if i == len(raw_shots) - 1 else round(raw_shots[i + 1]["start"], 3)
        if en <= st + 0.05:
            en = round(st + 0.25, 3)
        timeline.append({
            "index": i + 1,
            "start": st,
            "end": en,
            "dur": round(en - st, 3),
            "sub": sh["sub"],
            "spec": sh["spec"],
        })
    return timeline, total_dur


def render_all_frames_and_contact_sheets(timeline):
    print(f"Rendering {len(timeline)} 100%-visual 2D Flash frames (ZERO PIL text cards, ZERO top-pill badges)...")
    frame_paths = []
    for item in timeline:
        idx = item["index"]
        base_im = render_visual_spec(item["spec"])
        sub_im = burn_cinema_boxless_subtitle(base_im, item["sub"])
        fname = f"frame_{idx:03d}.jpg"
        fpath = os.path.join(FRAMES_DIR, fname)
        sub_im.save(fpath, quality=95)
        frame_paths.append((item, fpath))

        if idx in (2, 3):
            p28_jpg = os.path.join(PREVIEW_FRAMES_DIR, f"frame_{idx:02d}.jpg")
            sub_im.save(p28_jpg, quality=95)

    f_lbl = ImageFont.truetype(FONT_BOLD, 15)
    chunk_size = math.ceil(len(frame_paths) / 5)
    act_sheets = []
    for act_i in range(5):
        sub_list = frame_paths[act_i * chunk_size : (act_i + 1) * chunk_size]
        if not sub_list:
            continue
        cols = 5
        rows = math.ceil(len(sub_list) / cols)
        tw, th = 384, 216
        sh_im = Image.new("RGB", (cols * tw, rows * th), (18, 18, 18))
        sd = ImageDraw.Draw(sh_im)
        for j, (item, fp) in enumerate(sub_list):
            r, c = j // cols, j % cols
            im = Image.open(fp).resize((tw, th), Image.Resampling.LANCZOS)
            sh_im.paste(im, (c * tw, r * th))
            sd.rectangle([c * tw + 4, r * th + 4, c * tw + 195, r * th + 24], fill=(0, 0, 0))
            sd.text((c * tw + 8, r * th + 5), f"F{item['index']:03d} ({item['start']:.1f}-{item['end']:.1f}s)", font=f_lbl, fill=(255, 222, 118))
        act_path = f"{BRAIN}/verify_act{act_i+1}_frames_sheet.jpg"
        sh_im.save(act_path, quality=90)
        act_sheets.append(act_path)
        print(f"Saved Act {act_i+1} verification sheet ({len(sub_list)} frames):", act_path)

    return frame_paths, act_sheets


def encode_videos(frame_paths, total_dur):
    concat_full = os.path.join(EP_DIR, "concat_master_v3.txt")
    with open(concat_full, "w") as f:
        for item, fp in frame_paths:
            f.write(f"file '{fp}'\n")
            f.write(f"duration {item['dur']:.3f}\n")
        f.write(f"file '{frame_paths[-1][1]}'\n")
    out_full = os.path.join(EP_DIR, "pilot_01_why_5_days_master.mp4")
    cmd_full = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_full,
        "-i", AUDIO_MASTER, "-t", f"{total_dur:.2f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out_full
    ]
    subprocess.run(cmd_full, check=True)
    print("Encoded full 9-minute master video:", out_full)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "frames_only"
    timeline, total_dur = build_full_timeline()
    with open(os.path.join(EP_DIR, "timeline_master_v3.json"), "w") as f:
        json.dump({"duration": total_dur, "total_frames": len(timeline), "shots": timeline}, f, indent=2)
    print(f"Built timeline: {len(timeline)} clause-level shots across {total_dur:.2f}s (avg shot = {total_dur/len(timeline):.2f}s)")
    if mode == "encode_only":
        frame_paths = [(item, os.path.join(FRAMES_DIR, f"frame_{item['index']:03d}.jpg")) for item in timeline]
        encode_videos(frame_paths, total_dur)
    else:
        frame_paths, _ = render_all_frames_and_contact_sheets(timeline)
        if mode == "encode":
            encode_videos(frame_paths, total_dur)
