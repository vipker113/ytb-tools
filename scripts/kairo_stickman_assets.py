#!/usr/bin/env python3
"""
Kairo Spark — Phase 1 Reusable Visual Asset & Beat Template Engine
Mascot: STICKY-NOTE EXEC (Forehead Sticky Note + Striped Coral Tie + Asymmetrical Office Eyes)
Generates 20 modular PNG assets (poses, props, and code-driven beat cards) + a 20-asset contact sheet.
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

INK = (28, 27, 24, 255)
CREAM = (247, 243, 233, 255)
WHITE = (255, 255, 255, 255)
CORAL = (224, 90, 71, 255)
CORAL_DARK = (176, 54, 38, 255)
STICKY_AMBER = (245, 158, 66, 255)
TEAL = (46, 111, 126, 255)
AMBER = (233, 180, 76, 255)
RED_X = (220, 38, 38, 255)
GREEN_OK = (22, 163, 74, 255)
GRAY_MUTED = (110, 105, 95, 255)


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for p in [
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf",
        "/System/Library/Fonts/Supplemental/ChalkboardSE.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_sticky_note_exec(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    scale: float = 1.0,
    pose: str = "neutral",
    note_text: str = "?",
    mood: str = "curious",
) -> None:
    """
    Renders the locked Kairo Spark mascot: STICKY-NOTE EXEC.
    - Oval white head, asymmetrical eyes, tired office under-eye arcs
    - Forehead coral-amber sticky note with dynamic symbol (?, !, ?!, zzz, X, ⚡)
    - White collar + striped coral-orange necktie + black stick torso/limbs
    """
    rx = int(64 * scale)
    ry = int(58 * scale)
    hx, hy = cx, cy - int(115 * scale)
    lw = max(3, int(6 * scale))

    neck_y = hy + ry
    hip_y = neck_y + int(118 * scale)
    shoulder_y = neck_y + int(22 * scale)

    # White shirt torso trapezoid (subtle office silhouette) or pure stick torso
    shirt_w_top = int(34 * scale)
    shirt_w_bot = int(30 * scale)
    shirt_poly = [
        (cx - shirt_w_top, neck_y + int(4 * scale)),
        (cx + shirt_w_top, neck_y + int(4 * scale)),
        (cx + shirt_w_bot, hip_y),
        (cx - shirt_w_bot, hip_y),
    ]
    draw.polygon(shirt_poly, fill=WHITE, outline=INK)
    draw.line(shirt_poly + [shirt_poly[0]], fill=INK, width=lw)

    # Shirt collar wings
    draw.polygon(
        [
            (cx - int(22 * scale), neck_y + int(2 * scale)),
            (cx, neck_y + int(18 * scale)),
            (cx - int(10 * scale), neck_y + int(26 * scale)),
        ],
        fill=WHITE,
        outline=INK,
    )
    draw.polygon(
        [
            (cx + int(22 * scale), neck_y + int(2 * scale)),
            (cx, neck_y + int(18 * scale)),
            (cx + int(10 * scale), neck_y + int(26 * scale)),
        ],
        fill=WHITE,
        outline=INK,
    )

    # Striped Coral Necktie
    tie_top = neck_y + int(16 * scale)
    tie_bot = hip_y - int(12 * scale)
    tw = int(13 * scale)
    tie_poly = [
        (cx - int(6 * scale), tie_top),
        (cx + int(6 * scale), tie_top),
        (cx + tw, tie_bot - int(16 * scale)),
        (cx, tie_bot),
        (cx - tw, tie_bot - int(16 * scale)),
    ]
    draw.polygon(tie_poly, fill=CORAL, outline=INK)
    # Diagonal stripes on tie
    for sy in range(tie_top + int(14 * scale), tie_bot - int(14 * scale), max(6, int(16 * scale))):
        draw.line(
            [(cx - int(8 * scale), sy), (cx + int(8 * scale), sy - int(7 * scale))],
            fill=CORAL_DARK,
            width=max(2, int(3 * scale)),
        )
    draw.line(tie_poly + [tie_poly[0]], fill=INK, width=max(2, lw - 2))

    # Legs
    if pose == "sofa_guilt":
        draw.line([(cx - int(10 * scale), hip_y), (cx + int(75 * scale), hip_y + int(25 * scale))], fill=INK, width=lw)
        draw.line([(cx + int(10 * scale), hip_y), (cx + int(85 * scale), hip_y + int(45 * scale))], fill=INK, width=lw)
    else:
        draw.line([(cx - int(14 * scale), hip_y), (cx - int(36 * scale), hip_y + int(108 * scale))], fill=INK, width=lw)
        draw.line([(cx + int(14 * scale), hip_y), (cx + int(36 * scale), hip_y + int(108 * scale))], fill=INK, width=lw)
        # Feet
        draw.line([(cx - int(36 * scale), hip_y + int(108 * scale)), (cx - int(58 * scale), hip_y + int(112 * scale))], fill=INK, width=lw)
        draw.line([(cx + int(36 * scale), hip_y + int(108 * scale)), (cx + int(58 * scale), hip_y + int(112 * scale))], fill=INK, width=lw)

    # Arms by pose
    l_sh = (cx - shirt_w_top, shoulder_y)
    r_sh = (cx + shirt_w_top, shoulder_y)

    if pose == "briefcase":
        draw.line([l_sh, (cx - int(56 * scale), shoulder_y + int(68 * scale))], fill=INK, width=lw)
        hand_r = (cx + int(56 * scale), shoulder_y + int(68 * scale))
        draw.line([r_sh, hand_r], fill=INK, width=lw)
        # Briefcase prop
        bx0, by0 = hand_r[0] - int(22 * scale), hand_r[1] + int(4 * scale)
        bx1, by1 = hand_r[0] + int(26 * scale), hand_r[1] + int(40 * scale)
        draw.rounded_rectangle([bx0, by0, bx1, by1], radius=4, fill=(238, 232, 218, 255), outline=INK, width=max(2, lw - 1))
        draw.arc([hand_r[0] - int(10 * scale), by0 - int(10 * scale), hand_r[0] + int(14 * scale), by0 + int(6 * scale)], 180, 360, fill=INK, width=max(2, lw - 2))
    elif pose == "coffee":
        draw.line([l_sh, (cx - int(54 * scale), shoulder_y + int(40 * scale)), (cx - shirt_w_bot, hip_y - int(8 * scale))], fill=INK, width=lw)
        mug_pos = (cx + int(72 * scale), shoulder_y + int(18 * scale))
        draw.line([r_sh, (cx + int(50 * scale), shoulder_y + int(38 * scale)), mug_pos], fill=INK, width=lw)
        # Coffee mug
        mw, mh = int(24 * scale), int(28 * scale)
        draw.rounded_rectangle([mug_pos[0], mug_pos[1] - mh // 2, mug_pos[0] + mw, mug_pos[1] + mh // 2], radius=4, fill=WHITE, outline=INK, width=max(2, lw - 1))
        f_q = load_font(max(14, int(24 * scale)))
        draw.text((mug_pos[0] + int(4 * scale), mug_pos[1] - mh - int(22 * scale)), "?", fill=GRAY_MUTED, font=f_q)
    elif pose == "eureka":
        draw.line([l_sh, (cx - int(52 * scale), shoulder_y + int(56 * scale))], fill=INK, width=lw)
        draw.line([r_sh, (cx + int(62 * scale), shoulder_y - int(16 * scale)), (cx + int(74 * scale), shoulder_y - int(66 * scale))], fill=INK, width=lw)
    elif pose == "shock":
        draw.line([l_sh, (cx - int(66 * scale), hy), (hx - rx + int(4 * scale), hy - int(14 * scale))], fill=INK, width=lw)
        draw.line([r_sh, (cx + int(66 * scale), hy), (hx + rx - int(4 * scale), hy - int(14 * scale))], fill=INK, width=lw)
    elif pose == "point_chart":
        draw.line([l_sh, (cx - int(48 * scale), shoulder_y + int(58 * scale))], fill=INK, width=lw)
        hand_p = (cx + int(72 * scale), shoulder_y - int(12 * scale))
        draw.line([r_sh, hand_p], fill=INK, width=lw)
        draw.line([hand_p, (hand_p[0] + int(45 * scale), hand_p[1] - int(32 * scale))], fill=CORAL, width=max(2, lw - 1))
    else:
        draw.line([l_sh, (cx - int(54 * scale), shoulder_y + int(62 * scale))], fill=INK, width=lw)
        draw.line([r_sh, (cx + int(54 * scale), shoulder_y + int(62 * scale))], fill=INK, width=lw)

    # Head oval
    draw.ellipse([hx - rx, hy - ry, hx + rx, hy + ry], fill=WHITE, outline=INK, width=lw)

    # Signature Forehead Sticky Note (tilted square on upper forehead)
    nw = int(38 * scale)
    nh = int(36 * scale)
    nx, ny = hx - int(4 * scale), hy - ry + int(22 * scale)
    note_poly = [
        (nx - nw // 2, ny - nh // 2 + int(3 * scale)),
        (nx + nw // 2, ny - nh // 2 - int(3 * scale)),
        (nx + nw // 2 + int(4 * scale), ny + nh // 2 - int(2 * scale)),
        (nx - nw // 2 + int(2 * scale), ny + nh // 2 + int(4 * scale)),
    ]
    draw.polygon(note_poly, fill=STICKY_AMBER, outline=INK)
    draw.line(note_poly + [note_poly[0]], fill=INK, width=max(2, lw - 2))
    f_note = load_font(max(12, int(22 * scale if len(note_text) <= 2 else 14 * scale)))
    tb = draw.textbbox((0, 0), note_text, font=f_note)
    tw_n, th_n = tb[2] - tb[0], tb[3] - tb[1]
    draw.text((nx - tw_n // 2, ny - th_n // 2 - int(2 * scale)), note_text, fill=INK, font=f_note)

    # Asymmetrical Expressive Eyes
    ey = hy + int(8 * scale)
    ex1 = hx - int(22 * scale)
    ex2 = hx + int(22 * scale)
    r_eye_left = int(13 * scale)
    r_eye_right = int(10 * scale)

    if mood == "tired":
        draw.arc([ex1 - r_eye_left, ey - int(4 * scale), ex1 + r_eye_left, ey + int(10 * scale)], 0, 180, fill=INK, width=max(2, lw - 2))
        draw.arc([ex2 - r_eye_right, ey - int(4 * scale), ex2 + r_eye_right, ey + int(10 * scale)], 0, 180, fill=INK, width=max(2, lw - 2))
    else:
        # Left eye: wide ringed eye
        draw.ellipse([ex1 - r_eye_left, ey - r_eye_left, ex1 + r_eye_left, ey + r_eye_left], fill=WHITE, outline=INK, width=max(2, lw - 2))
        pr = max(2, int(3.5 * scale))
        draw.ellipse([ex1 - pr, ey - pr, ex1 + pr, ey + pr], fill=INK)
        # Right eye: slightly narrower / sceptical half-lidded eye
        draw.ellipse([ex2 - r_eye_right, ey - int(7 * scale), ex2 + r_eye_right, ey + int(7 * scale)], fill=WHITE, outline=INK, width=max(2, lw - 2))
        draw.ellipse([ex2 - pr, ey - pr, ex2 + pr, ey + pr], fill=INK)
        if mood in ("curious", "sceptical"):
            draw.line([(ex2 - r_eye_right - 2, ey - int(5 * scale)), (ex2 + r_eye_right + 2, ey - int(5 * scale))], fill=INK, width=max(2, lw - 2))

    # Subtle tired office under-eye lines
    draw.arc([ex1 - int(10 * scale), ey + int(8 * scale), ex1 + int(10 * scale), ey + int(18 * scale)], 20, 160, fill=GRAY_MUTED, width=max(1, int(2 * scale)))
    draw.arc([ex2 - int(9 * scale), ey + int(6 * scale), ex2 + int(9 * scale), ey + int(15 * scale)], 20, 160, fill=GRAY_MUTED, width=max(1, int(2 * scale)))

    # Mouth
    my = hy + int(33 * scale)
    if mood == "shock":
        draw.ellipse([hx - int(10 * scale), my - int(7 * scale), hx + int(10 * scale), my + int(9 * scale)], fill=INK)
    elif mood == "eureka":
        draw.arc([hx - int(16 * scale), my - int(10 * scale), hx + int(16 * scale), my + int(10 * scale)], 10, 170, fill=INK, width=max(2, lw - 2))
    elif mood == "tired":
        draw.arc([hx - int(14 * scale), my - int(2 * scale), hx + int(14 * scale), my + int(14 * scale)], 195, 345, fill=INK, width=max(2, lw - 2))
    else:
        draw.line([(hx - int(12 * scale), my), (hx + int(10 * scale), my - int(2 * scale))], fill=INK, width=max(2, lw - 2))


def generate_all_assets(out_dir: str, sheet_path: str) -> None:
    os.makedirs(out_dir, exist_ok=True)

    # 1-10: 10 Modular Transparent PNG Mascot Poses
    mascot_specs = [
        ("01_pose_presenter_briefcase.png", "briefcase", "?", "curious", "01. Presenter (?)"),
        ("02_pose_coffee_question.png", "coffee", "?", "sceptical", "02. Coffee Skeptic (?)"),
        ("03_pose_eureka_spark.png", "eureka", "!", "eureka", "03. Eureka Spark (!)"),
        ("04_pose_paradox_shock.png", "shock", "?!", "shock", "04. Paradox Shock (?!)"),
        ("05_pose_burnout_501pm.png", "neutral", "zzz", "tired", "05. 5:01 PM Burnout (zzz)"),
        ("06_pose_chart_pointer.png", "point_chart", "!", "curious", "06. Data Pointer (!)"),
        ("07_pose_myth_buster_x.png", "point_chart", "X", "sceptical", "07. Myth Buster (X)"),
        ("08_pose_guilty_rest.png", "sofa_guilt", "404", "tired", "08. Guilty Rest (404)"),
        ("09_pose_time_observer.png", "coffee", "?!", "curious", "09. Time Observer (?!)"),
        ("10_pose_calm_takeaway.png", "neutral", "OK", "eureka", "10. Calm Takeaway (OK)"),
    ]

    rendered_thumbs = []

    for fname, pose, note, mood, label in mascot_specs:
        im = Image.new("RGBA", (500, 560), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        draw_sticky_note_exec(dr, 250, 295, scale=1.15, pose=pose, note_text=note, mood=mood)
        im.save(os.path.join(out_dir, fname))
        rendered_thumbs.append((label, im))

    # 11-16: 6 Reusable Props (Transparent PNGs)
    props = [
        ("11_prop_clock_501.png", "11. Clock 5:01 PM"),
        ("12_prop_calendar_5day.png", "12. 5-Day Calendar"),
        ("13_prop_campfire.png", "13. Ancient Campfire"),
        ("14_prop_stamp_red_x.png", "14. Red [X] Stamp"),
        ("15_prop_stamp_green_ok.png", "15. Green [OK] Stamp"),
        ("16_prop_battery_12pct.png", "16. 12% Brain Battery"),
    ]

    f_prop = load_font(34)
    f_prop_sm = load_font(24)

    for fname, label in props:
        im = Image.new("RGBA", (500, 560), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        if "clock" in fname:
            dr.ellipse([130, 140, 370, 380], fill=WHITE, outline=INK, width=7)
            dr.line([(250, 260), (250, 175)], fill=INK, width=7)
            dr.line([(250, 260), (315, 305)], fill=CORAL, width=7)
            dr.text((185, 405), "5:01 PM", fill=CORAL, font=f_prop)
        elif "calendar" in fname:
            dr.rounded_rectangle([100, 140, 400, 410], radius=18, fill=WHITE, outline=INK, width=6)
            dr.rounded_rectangle([100, 140, 400, 205], radius=18, fill=CORAL, outline=INK, width=6)
            dr.text((130, 156), "M   T   W   Th   F", fill=WHITE, font=f_prop)
            for gx in range(160, 360, 60):
                dr.line([(gx, 205), (gx, 410)], fill=INK, width=3)
            for gy in range(270, 390, 65):
                dr.line([(100, gy), (400, gy)], fill=INK, width=3)
        elif "campfire" in fname:
            dr.polygon([(250, 140), (325, 340), (175, 340)], fill=CORAL, outline=INK)
            dr.polygon([(250, 195), (295, 340), (205, 340)], fill=AMBER, outline=INK)
            for sx in range(155, 355, 45):
                dr.ellipse([sx, 330, sx + 48, 368], fill=(160, 155, 145, 255), outline=INK, width=5)
        elif "red_x" in fname:
            dr.rounded_rectangle([110, 180, 390, 370], radius=24, fill=(254, 226, 226, 255), outline=RED_X, width=8)
            dr.line([(170, 220), (330, 330)], fill=RED_X, width=16)
            dr.line([(330, 220), (170, 330)], fill=RED_X, width=16)
        elif "green_ok" in fname:
            dr.rounded_rectangle([110, 180, 390, 370], radius=24, fill=(220, 252, 231, 255), outline=GREEN_OK, width=8)
            dr.line([(165, 280), (225, 335), (340, 215)], fill=GREEN_OK, width=16)
        elif "battery" in fname:
            dr.rounded_rectangle([105, 210, 375, 340], radius=16, fill=WHITE, outline=INK, width=7)
            dr.rectangle([375, 248, 398, 302], fill=INK)
            dr.rounded_rectangle([120, 225, 175, 325], radius=8, fill=RED_X)
            dr.text((195, 255), "12% LEFT", fill=RED_X, font=f_prop)
        im.save(os.path.join(out_dir, fname))
        rendered_thumbs.append((label, im))

    # 17-20: 4 Code-Driven Beat Cards (Whiteboard, Split Comparison, Research Stamp, Chapter Card)
    cards = [
        ("17_card_whiteboard_hook.png", "17. Whiteboard Beat", "WHY 5 DAYS?"),
        ("18_card_research_stamp.png", "18. Evidence Stamp", "FORD • 1926"),
        ("19_card_myth_vs_truth.png", "19. Myth vs Reality", "LAZY = LIE"),
        ("20_card_chapter_break.png", "20. Chapter Break", "ACT II: THE TRAP"),
    ]
    for fname, label, headline in cards:
        im = Image.new("RGBA", (500, 560), (0, 0, 0, 0))
        dr = ImageDraw.Draw(im)
        dr.rounded_rectangle([35, 120, 465, 430], radius=22, fill=CREAM, outline=INK, width=6)
        dr.rounded_rectangle([65, 150, 330, 192], radius=8, fill=CORAL)
        dr.text((80, 158), "KAIRO SPARK BEAT", fill=WHITE, font=f_prop_sm)
        dr.text((70, 255), headline, fill=INK, font=f_prop)
        im.save(os.path.join(out_dir, fname))
        rendered_thumbs.append((label, im))

    # Build 20-Asset Contact Sheet (5 columns x 4 rows, 1920x1080)
    sheet = Image.new("RGB", (1920, 1080), (236, 231, 220))
    sd = ImageDraw.Draw(sheet)
    f_head = load_font(34)
    f_lbl = load_font(17)
    sd.text(
        (45, 22),
        "KAIRO SPARK — PHASE 1: 20 REUSABLE CODE-GENERATED VISUAL ASSETS (STICKY-NOTE EXEC)",
        fill=(28, 27, 24),
        font=f_head,
    )

    cols, rows = 5, 4
    cell_w, cell_h = 360, 232
    for idx, (label, asset_im) in enumerate(rendered_thumbs[:20]):
        c = idx % cols
        r = idx // cols
        x0 = 40 + c * 372
        y0 = 82 + r * 244
        sd.rounded_rectangle([x0, y0, x0 + cell_w, y0 + cell_h], radius=16, fill=(247, 243, 233), outline=(28, 27, 24), width=3)
        thumb = asset_im.copy()
        thumb.thumbnail((185, 185))
        sheet.paste(thumb, (x0 + (cell_w - thumb.width) // 2, y0 + 6), thumb)
        sd.rounded_rectangle([x0 + 12, y0 + cell_h - 38, x0 + cell_w - 12, y0 + cell_h - 8], radius=8, fill=(28, 27, 24))
        sd.text((x0 + 22, y0 + cell_h - 33), label, fill=(255, 255, 255), font=f_lbl)

    sheet.save(sheet_path, quality=93)


if __name__ == "__main__":
    OUT = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/assets"
    SHEET = "/Users/admin/.gemini/antigravity/brain/9c914627-c4fa-4486-ab2e-ea9740fd1166/kairo_sticky_exec_code_assets_20.jpg"
    generate_all_assets(OUT, SHEET)
    print("Generated 20 modular PNG assets + contact sheet!")
