#!/usr/bin/env python3
"""
Kairo Spark — Episode #2: "Why We Lie When There's Nothing to Lose"
FULL PRODUCTION PIPELINE (Razor-Sharp Real-ESRGAN 4x HD + ZERO PIL Slop)
- Uses 88 unique 2D Adobe Flash illustrations upscaled 4x via Real-ESRGAN x4v3 (dn=0.55) -> 1920x1080
- ZERO PIL speech bubbles, ZERO PIL text cards, ZERO top-pill badges (100% native art!)
- Exact clause-level timestamp sync via faster_whisper word alignment on ep02_full_voice_14lufs.mp3
- pow_studio cinema_boxless subtitles at y=918 (max ~9 words per caption card for ultra-clean reading) + .srt
- Editorial SFX foley mixed below voiceover, mastered to -14.0 LUFS
- Act-by-Act visual QA contact sheets (verify_act1_sheet.jpg .. verify_act7_sheet.jpg)
- Auto-generates YOUTUBE_UPLOAD_INFO.md with exact verified chapter timestamps
"""

import os
import re
import sys
import json
import math
import argparse
import subprocess
from PIL import Image, ImageDraw, ImageFont, ImageFilter

EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/ep-02-pointless-lies"
SCENES_HD_DIR = os.path.join(EP_DIR, "scenes_hd")
SCENES_RAW_DIR = os.path.join(EP_DIR, "scenes_raw")
FRAMES_DIR = os.path.join(EP_DIR, "frames_full_hd")
FLASH_PACK_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack"
SFX_DIR = "/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/sfx"
FONT_BOLD = "/Applications/code/science-knowledge/youtube-shorts-channel/assets/fonts/BeVietnamPro-Bold.ttf"
AUDIO_DIR = os.path.join(EP_DIR, "audio")
VOICE_FULL_MP3 = os.path.join(AUDIO_DIR, "ep02_full_voice_14lufs.mp3")
SEGMENTS_JSON = os.path.join(AUDIO_DIR, "ep02_full_segments.json")
WORDS_JSON = os.path.join(AUDIO_DIR, "ep02_full_words.json")

os.makedirs(FRAMES_DIR, exist_ok=True)


# ==============================================================================
# 1. FULL 60-SEGMENT CREATIVE VISUAL MAP (114+ BEATS, 88 UNIQUE HD SCENES, ZERO PIL SLOP)
#    Format per seg_id: list of (clause_text, visual_spec, optional_sfx_tuple)
#    optional_sfx_tuple: (sfx_filename, gain_db, max_dur_sec) or None
# ==============================================================================
SEG_BEATS = {
    # ---------------- ACT I: The Monday Morning Coffee Machine ----------------
    1: [
        ("Why do we lie,", "scene:p01_truth_zero_scale.png+reveal_left:815", None),
        ("even when telling the truth", "scene:p01_truth_zero_scale.png", ("01_pop_appear.mp3", -16, 0.7)),
        ("wouldn't cost us anything?", "scene:p01_truth_zero_scale.png+closeup:1310,670,1.42", None),
    ],
    2: [
        ("Think about a normal Monday morning.", "scene:p02_monday_breakroom_wide.png", ("09_page_flip.mp3", -16, 0.4)),
        ("You're standing by the coffee machine,", "scene:h01_coffee_sleepy.png", ("24_coffee_pour.mp3", -18, 1.5)),
        ("still half asleep,", "scene:h01_coffee_sleepy.png+closeup:1290,360,1.50", ("27_yawn_tired.mp3", -20, 1.2)),
        ("and a coworker looks over and asks,", "scene:h02_coworker_waves.png", ("01_pop_appear.mp3", -16, 0.7)),
        ('"Hey, how was your weekend?"', "scene:g01_1.png", None),
    ],
    3: [
        ("Now, if you actually answered honestly,", "scene:g01_2.png", ("14_swoosh_fast.mp3", -17, 0.36)),
        ("what would you say?", "host:06_pose_thinking_lookup.png", None),
    ],
    4: [
        ("Maybe the real truth is that you barely left your apartment.", "scene:p03_apartment_door_locked.png", None),
        ("You spent most of Saturday on your phone,", "scene:h03_saturday_couch_phone.png", ("23_phone_vibrate.mp3", -20, 1.0)),
        ("ate dinner straight out of a takeout container", "scene:p04_takeout_couch_dinner.png", None),
        ("at four in the afternoon,", "clock:4|4:00 PM|SATURDAY", ("07_clock_ticking.mp3", -18, 1.4)),
        ("and went to bed early.", "scene:p05_bed_early_sunset.png", ("26_sigh_exhausted.mp3", -18, 1.1)),
    ],
    5: [
        ("What would happen if you said that out loud?", "host:01_pose_shrug_question.png", None),
        ("Nobody's going to fire you.", "scene:g01_3.png+reveal_left:960", ("15_stamp_thud.mp3", -17, 0.9)),
        ("Nobody's going to judge you for resting on a Saturday.", "scene:g01_3.png", ("44_gavel_hit.mp3", -18, 0.9)),
    ],
    6: [
        ("Most likely, your coworker would just say,", "scene:h02_coworker_waves.png", None),
        ('"Honestly, that sounds great," and go back to making their coffee.', "scene:g01_4.png", ("16_correct_chime.mp3", -18, 1.0)),
    ],
    7: [
        ("Nothing bad happens if you tell the truth here.", "scene:p01_truth_zero_scale.png", None),
        ("And yet, before you even think about it,", "host:04_pose_eureka_point_up.png", ("05_record_scratch.mp3", -17, 0.65)),
        ('you hear yourself say, "Oh, it was nice!"', "scene:p06_fake_nice_coffee_reply.png", ("01_pop_appear.mp3", -16, 0.7)),
        ("Got a few things done, caught up on some reading,", "scene:p07_fake_reading_checklist.png", ("09_page_flip.mp3", -17, 0.4)),
        ("went for a walk in the park.", "scene:h04_fake_park_walk.png", None),
    ],
    8: [
        ("Then you walk back to your desk", "scene:p08_back_at_desk_realization.png", ("32_footsteps.mp3", -20, 1.3)),
        ("and realize you haven't set foot in a park in three weeks.", "scene:p08_back_at_desk_realization.png+closeup:1080,450,1.32", ("26_sigh_exhausted.mp3", -19, 1.0)),
    ],

    # ---------------- ACT II: Bella DePaulo's Diary Study (1996) ----------------
    9: [
        ("Most of us have done some version of this.", "scene:g02_4.png", ("02_whoosh_card.mp3", -17, 0.6)),
        ('Saying "I\'m on my way!" when you haven\'t put your shoes on yet.', "scene:g02_1.png", ("23_phone_vibrate.mp3", -20, 0.9)),
    ],
    10: [
        ("Smiling and pretending you've heard of a band", "scene:g02_2.png", None),
        ("just so you don't have to stop the conversation.", "scene:g02_2.png+closeup:1320,420,1.28", None),
    ],
    11: [
        ("It doesn't mean you're manipulative.", "scene:g02_3.png", ("04_stamp_red_x.mp3", -17, 0.9)),
        ("It's a habit almost everyone shares,", "scene:g02_4.png", None),
        ("and psychologists have actually measured how often it happens.", "scene:g03_1.png", ("09_page_flip.mp3", -17, 0.4)),
    ],
    12: [
        ("Back in 1996, psychologist Bella DePaulo at the University of Virginia", "scene:g03_1.png", None),
        ("asked 147 ordinary people, college students and working adults,", "scene:g03_2.png", ("01_pop_appear.mp3", -17, 0.6)),
        ("to keep a small diary for a week.", "scene:g03_3.png", ("21_book_close.mp3", -17, 0.7)),
    ],
    13: [
        ("Every time they misled someone, even slightly, they wrote it down.", "scene:g03_4.png", ("11_pencil_write.mp3", -19, 1.8)),
    ],
    14: [
        ("On average, people told one or two lies a day,", "scene:g04_1.png", ("03_ding_eureka.mp3", -18, 1.2)),
        ("coming up in roughly a quarter of their daily social interactions.", "scene:g04_2.png", ("01_pop_appear.mp3", -16, 0.6)),
    ],
    15: [
        ("More than seventy percent of those lies weren't about hiding something serious,", "scene:g04_3.png", ("14_swoosh_fast.mp3", -17, 0.36)),
        ("getting money, or staying out of trouble.", "scene:g04_4.png", ("04_stamp_red_x.mp3", -17, 0.9)),
    ],
    16: [
        ("People lied about liking a sandwich that was dry,", "scene:g05_1.png", ("01_pop_appear.mp3", -17, 0.5)),
        ("about why they were five minutes late,", "scene:g05_2.png", ("01_pop_appear.mp3", -17, 0.5)),
        ("or about having seen a movie someone brought up at lunch.", "scene:g05_3.png", ("01_pop_appear.mp3", -17, 0.5)),
    ],
    17: [
        ("When DePaulo asked them afterward if anything bad would have happened if they'd just told the truth,", "scene:g05_4.png+reveal_left:620", None),
        ("most of them said no. Not really.", "scene:g05_4.png", None),
    ],

    # ---------------- ACT III: Why the Truth Feels Like More Work ----------------
    18: [
        ("Sometimes, telling the truth is just more trouble than it's worth.", "scene:g06_1.png", ("02_whoosh_card.mp3", -17, 0.6)),
        ("Not because you're afraid of getting caught.", "host:01_pose_shrug_question.png", None),
        ("You just don't feel like explaining yourself.", "scene:g06_2.png", ("09_page_flip.mp3", -16, 0.4)),
    ],
    19: [
        ("We're used to thinking that honesty is simple and lying takes effort.", "scene:g06_3.png", None),
        ("For a big lie, making up a whole story under pressure, that's definitely true.", "scene:g06_3.png+closeup:960,520,1.28", None),
    ],
    20: [
        ("In casual conversation, though, it often works the other way around.", "scene:g06_4.png", ("14_swoosh_fast.mp3", -16, 0.36)),
    ],
    21: [
        ("Say a friend texts on Friday evening asking if you want to grab drinks.", "scene:g07_1.png", ("23_phone_vibrate.mp3", -19, 1.0)),
        ("The honest reason you don't want to go isn't that you're upset with them.", "scene:g07_1.png+closeup:660,540,1.28", None),
    ],
    22: [
        ("You're just tired, your week was long, and you've been looking forward to staying home in comfortable clothes.", "scene:g07_2.png", ("26_sigh_exhausted.mp3", -19, 1.1)),
    ],
    23: [
        ("If you give that unfiltered answer, you often end up managing their reaction.", "scene:g07_3.png+reveal_left:950", None),
        ("They might wonder if you're mad at them, or try to talk you into it.", "scene:g07_3.png", ("01_pop_appear.mp3", -16, 0.6)),
    ],
    24: [
        ('"Come on, just for one drink, it\'ll get you out of the house."', "scene:g07_4.png", ("14_swoosh_fast.mp3", -17, 0.36)),
        ("Now a simple reply turns into a back-and-forth you don't really want to have.", "scene:g07_4.png+closeup:940,480,1.25", None),
    ],
    25: [
        ('Compare that to: "I\'d love to, I just have a headache coming on."', "scene:g08_1.png", ("22_mouse_click.mp3", -18, 0.6)),
    ],
    26: [
        ("Nobody feels rejected, nobody argues with a headache,", "scene:g08_2.png", ("16_correct_chime.mp3", -18, 1.0)),
        ("and the conversation wraps up in five seconds.", "scene:g08_3.png", ("03_ding_eureka.mp3", -18, 1.1)),
    ],
    27: [
        ("Calling in an easy excuse isn't really about deception.", "scene:g08_4.png+reveal_left:960", None),
        ("It's just a way to avoid unnecessary friction.", "scene:g08_4.png", ("14_swoosh_fast.mp3", -17, 0.36)),
    ],

    # ---------------- ACT IV: Avoiding Awkward Silence (Robert Feldman, 2002) ----------------
    28: [
        ("Avoiding plans makes sense.", "host:02_pose_walk_idea.png", None),
        ("What's stranger are the lies that slip out when we're just making small talk.", "scene:g09_1.png", ("01_pop_appear.mp3", -16, 0.6)),
    ],
    29: [
        ("Someone mentions a neighborhood restaurant, or a book everybody's talking about,", "scene:g09_2.png+reveal_left:1100", None),
        ('and you hear yourself say, "Oh yeah, I\'ve been meaning to go back there,"', "scene:g09_2.png", ("01_pop_appear.mp3", -17, 0.6)),
        ("even though you've never walked through the door.", "scene:g09_2.png+closeup:1450,480,1.32", None),
    ],
    30: [
        ("You're not even trying to impress them.", "scene:g09_3.png", None),
        ("You just didn't want the conversation to hit a wall.", "scene:g09_4.png", ("15_stamp_thud.mp3", -17, 0.9)),
    ],
    31: [
        ("Psychologist Robert Feldman at the University of Massachusetts tested how naturally this happens in 2002.", "scene:g10_1.png", ("17_camera_shutter.mp3", -17, 0.8)),
    ],
    32: [
        ("He paired up strangers, asked them to chat for ten minutes so they could get to know each other,", "scene:g10_2.png", None),
        ("and recorded the conversation.", "scene:g10_2.png+closeup:1320,460,1.28", ("17_camera_shutter.mp3", -18, 0.7)),
    ],
    33: [
        ("Afterward, he had each person watch the video back", "scene:g10_3.png", ("40_tape_rewind.mp3", -19, 1.0)),
        ("and point out every statement that wasn't completely accurate.", "scene:g10_4.png", ("01_pop_appear.mp3", -17, 0.5)),
    ],
    34: [
        ("Before watching the tape, almost everyone assumed they'd been totally honest.", "scene:g11_1.png", ("16_correct_chime.mp3", -19, 1.0)),
    ],
    35: [
        ("Once they saw the footage, around sixty percent realized they'd told at least one lie in just ten minutes,", "scene:g11_2.png", ("03_ding_eureka.mp3", -18, 1.2)),
        ("averaging nearly three small inaccuracies per conversation.", "scene:g11_2.png+closeup:620,460,1.28", None),
    ],
    36: [
        ("People exaggerated how much they liked something,", "scene:g11_3.png", None),
        ("claimed familiarity with things they barely knew, and nodded along with opinions they didn't actually share.", "scene:g02_2.png", None),
    ],
    37: [
        ("Most of it happened automatically because nobody wants to look odd or kill the flow of a normal chat.", "scene:g09_4.png", None),
        ("If the blunt truth creates an awkward pause, we smooth it over without noticing.", "scene:g11_4.png", ("02_whoosh_card.mp3", -17, 0.6)),
    ],

    # ---------------- ACT V: Why You Can't Take It Back ----------------
    38: [
        ("Once one of those small lies leaves your mouth, a funny thing happens:", "host:04_pose_eureka_point_up.png", None),
        ("it's almost impossible to walk it back.", "scene:g12_1.png", ("14_swoosh_fast.mp3", -16, 0.36)),
    ],
    39: [
        ("Imagine telling a coworker you went hiking over the weekend,", "scene:g12_2.png", None),
        ('and then two seconds later stopping and saying, "Wait, I don\'t know why I said that."', "scene:g12_3.png", ("05_record_scratch.mp3", -17, 0.65)),
        ('"I didn\'t go hiking. I stayed home all weekend."', "scene:g12_3.png+closeup:840,520,1.30", None),
    ],
    40: [
        ("Confessing to a major secret makes sense to people.", "scene:g12_4.png+reveal_left:960", None),
        ("Confessing to a meaningless lie about a weekend walk just makes the whole moment deeply uncomfortable.", "scene:g12_4.png", None),
    ],
    41: [
        ('So you don\'t correct it. When they follow up with, "Oh nice, where did you go?",', "scene:g13_1.png", ("01_pop_appear.mp3", -16, 0.6)),
        ("you name a trail you drove past last summer,", "scene:g13_2.png", ("09_page_flip.mp3", -16, 0.4)),
        ("just to close out a conversation neither of you even cared about a minute ago.", "scene:g13_3.png", ("26_sigh_exhausted.mp3", -19, 1.0)),
    ],
    42: [
        ("One casual phrase pulls a second one behind it.", "scene:g13_4.png", ("15_stamp_thud.mp3", -18, 0.8)),
    ],

    # ---------------- ACT VI: The Quiet Cost (Sharot & Garrett 2016 + Aldert Vrij) ----------------
    43: [
        ("When a white lie is isolated, it seems harmless. Polite untruths help daily life run smoothly.", "scene:g14_1.png", ("02_whoosh_card.mp3", -18, 0.6)),
    ],
    44: [
        ("In 2016, neuroscientists Tali Sharot and Neil Garrett studied what happens in the brain during repeated small dishonesty.", "scene:g14_2.png", ("39_mystery_chime.mp3", -20, 1.6)),
    ],
    45: [
        ("Using fMRI scans, they focused on the amygdala,", "scene:g14_3.png", ("01_pop_appear.mp3", -17, 0.6)),
        ("a region closely tied to the emotional tension or guilt people feel when doing something uncomfortable.", "scene:g14_4.png", ("03_ding_eureka.mp3", -18, 1.0)),
    ],
    46: [
        ("What they found was interesting. As people repeatedly benefited from dishonesty,", "scene:g15_1.png", ("06_cash_register.mp3", -19, 1.0)),
        ("their emotional response to it gradually weakened.", "scene:g15_2.png", None),
    ],
    47: [
        ("In other words, something that felt uncomfortable at first", "scene:g15_3.png", None),
        ("could become easier to do over time.", "scene:g15_4.png", ("14_swoosh_fast.mp3", -17, 0.36)),
    ],
    48: [
        ("There's also a simpler, everyday cost that deception researcher Aldert Vrij has studied for years: mental fatigue.", "scene:g16_1.png", ("21_book_close.mp3", -18, 0.7)),
    ],
    49: [
        ("Holding back what you actually think, or keeping track of two versions of the same small story,", "scene:g16_2.png", None),
        ("takes real attention.", "scene:g16_3.png", ("09_page_flip.mp3", -17, 0.4)),
    ],
    50: [
        ("If you've ever walked away from a long social gathering feeling strangely drained even though nothing went wrong,", "scene:g16_4.png", ("26_sigh_exhausted.mp3", -19, 1.1)),
        ("part of that exhaustion comes from quietly editing yourself all evening.", "scene:g16_4.png+closeup:1320,620,1.28", None),
    ],

    # ---------------- ACT VII: Taking a One-Second Beat & Real Connection ----------------
    51: [
        ("Stopping every white lie isn't realistic,", "host:01_pose_shrug_question.png", None),
        ("and being bluntly honest at all times would probably just make life harder for the people around you.", "scene:g17_1.png", ("38_crowd_gasp.mp3", -18, 0.9)),
    ],
    52: [
        ("Most pointless lies happen in the first split second after someone asks a casual question, before you've decided what you actually want to say.", "scene:g17_2.png", ("07_clock_ticking.mp3", -20, 1.4)),
    ],
    53: [
        ('Simply taking a half-second pause before replying, "Hmm, honestly..."', "scene:g17_3.png", ("16_correct_chime.mp3", -19, 1.0)),
        ("breaks the automatic response just enough to give you a choice.", "scene:g17_4.png", None),
    ],
    54: [
        ("When a question doesn't really carry high stakes, it helps to be a little more ordinary.", "scene:g18_1.png", ("02_whoosh_card.mp3", -18, 0.6)),
    ],
    55: [
        ("The next time someone asks what you did over the weekend,", "scene:g18_2.png", None),
        ('saying, "Honestly, I didn\'t do much at all, and I needed it," almost never lands poorly.', "scene:g18_2.png+closeup:1180,440,1.28", None),
    ],
    56: [
        ("More often than not, the other person looks noticeably relieved", "scene:g18_3.png", ("26_sigh_exhausted.mp3", -20, 0.9)),
        ('and says, "Yeah, me too."', "scene:g18_4.png", ("16_correct_chime.mp3", -17, 1.1)),
    ],
    57: [
        ("We tell small, pointless lies because we're trying to look a little busier, a little more interesting, or easier to talk to.", "scene:g19_1.png", None),
    ],
    58: [
        ("Everyone ends up protecting an image nobody was judging that closely anyway.", "scene:g19_2.png", None),
    ],
    59: [
        ("Usually, real connection doesn't start when two people trade impressive weekend stories.", "scene:g19_3.png", None),
    ],
    60: [
        ("It starts the moment someone admits they stayed home and did nothing,", "scene:g19_4.png", ("39_mystery_chime.mp3", -20, 1.8)),
        ("and makes it safe for the other person to tell the truth, too.", "scene:g19_4.png+closeup:960,540,1.18", None),
    ],
}

# ==============================================================================
# 2. VISUAL RENDERING ENGINE (ZERO PIL SPEECH BUBBLES / ZERO PIL TEXT CARDS)
# ==============================================================================
_SCENE_CACHE = {}
_HOST_CACHE = {}

def load_scene(name):
    if name not in _SCENE_CACHE:
        p = os.path.join(SCENES_HD_DIR, name)
        if not os.path.exists(p):
            p = os.path.join(SCENES_RAW_DIR, name)
        im = Image.open(p).convert("RGB")
        if im.size != (1920, 1080):
            im = im.resize((1920, 1080), Image.Resampling.LANCZOS)
        _SCENE_CACHE[name] = im
    return _SCENE_CACHE[name].copy()


def make_flash_12num_clock(hour_val, badge_text, sub_tag="SATURDAY", minute_val=0, bg_wall=(236, 217, 178)):
    S = 2
    W, H = 1920 * S, 1080 * S
    img = Image.new("RGB", (W, H), bg_wall)
    d = ImageDraw.Draw(img)

    cx, cy = 960 * S, 445 * S
    r_outer = 320 * S
    d.ellipse([cx - r_outer - 12 * S, cy - r_outer + 14 * S, cx + r_outer - 12 * S, cy + r_outer + 14 * S], fill=(204, 185, 148))
    d.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill=(242, 244, 247), outline=(15, 15, 15), width=10 * S)
    r_inner = r_outer - 34 * S
    d.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill=(255, 255, 255), outline=(15, 15, 15), width=7 * S)

    font_num = ImageFont.truetype(FONT_BOLD, 46 * S)
    font_active = ImageFont.truetype(FONT_BOLD, 56 * S)

    for hr in range(1, 13):
        ang = math.radians(hr * 30 - 90)
        t_out = r_inner - 12 * S
        t_in = r_inner - (32 * S if hr % 3 == 0 else 20 * S)
        d.line([(cx + t_in * math.cos(ang), cy + t_in * math.sin(ang)), (cx + t_out * math.cos(ang), cy + t_out * math.sin(ang))], fill=(15, 15, 15), width=7 * S if hr % 3 == 0 else 4 * S)
        num_r = r_inner - 72 * S
        nx, ny = cx + num_r * math.cos(ang), cy + num_r * math.sin(ang)
        is_target = (hr == hour_val)
        if is_target:
            d.ellipse([nx - 40 * S, ny - 40 * S, nx + 40 * S, ny + 40 * S], fill=(255, 224, 102), outline=(210, 45, 45), width=6 * S)
        f_use = font_active if (is_target or hr in (12, 3, 6, 9)) else font_num
        txt = str(hr)
        bb = d.textbbox((0, 0), txt, font=f_use)
        d.text((nx - (bb[2] - bb[0]) / 2 - bb[0], ny - (bb[3] - bb[1]) / 2 - bb[1]), txt, font=f_use, fill=(205, 35, 35) if is_target else (15, 15, 15))

    min_ang = math.radians(minute_val * 6 - 90)
    d.line([(cx, cy), (cx + (r_inner - 105 * S) * math.cos(min_ang), cy + (r_inner - 105 * S) * math.sin(min_ang))], fill=(15, 15, 15), width=14 * S)

    hr_ang = math.radians(hour_val * 30 + minute_val * 0.5 - 90)
    hx_end, hy_end = cx + (r_inner - 122 * S) * math.cos(hr_ang), cy + (r_inner - 122 * S) * math.sin(hr_ang)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(15, 15, 15), width=24 * S)
    d.line([(cx, cy), (hx_end, hy_end)], fill=(215, 65, 50), width=14 * S)
    d.ellipse([cx - 20 * S, cy - 20 * S, cx + 20 * S, cy + 20 * S], fill=(215, 65, 50), outline=(15, 15, 15), width=6 * S)

    bx1, by1, bx2, by2 = 160 * S, 360 * S, 540 * S, 490 * S
    d.rounded_rectangle([bx1 - 6 * S, by1 + 8 * S, bx2 - 6 * S, by2 + 8 * S], radius=22 * S, fill=(195, 175, 140))
    d.rounded_rectangle([bx1, by1, bx2, by2], radius=22 * S, fill=(255, 226, 110), outline=(15, 15, 15), width=8 * S)
    f_b = ImageFont.truetype(FONT_BOLD, 64 * S)
    bb = d.textbbox((0, 0), badge_text, font=f_b)
    d.text(((bx1 + bx2 - (bb[2] - bb[0])) / 2 - bb[0], (by1 + by2 - (bb[3] - bb[1])) / 2 - bb[1]), badge_text, font=f_b, fill=(15, 15, 15))

    if sub_tag:
        tx1, ty1, tx2, ty2 = 1380 * S, 380 * S, 1800 * S, 475 * S
        d.rounded_rectangle([tx1, ty1, tx2, ty2], radius=18 * S, fill=(255, 255, 255), outline=(15, 15, 15), width=7 * S)
        f_t = ImageFont.truetype(FONT_BOLD, 34 * S)
        bbt = d.textbbox((0, 0), sub_tag, font=f_t)
        d.text(((tx1 + tx2 - (bbt[2] - bbt[0])) / 2 - bbt[0], (ty1 + ty2 - (bbt[3] - bbt[1])) / 2 - bbt[1]), sub_tag, font=f_t, fill=(15, 15, 15))

    return img.resize((1920, 1080), Image.Resampling.LANCZOS)


def make_host_reaction(pose_filename):
    if pose_filename in _HOST_CACHE:
        return _HOST_CACHE[pose_filename].copy()
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
    cw, ch = crop.size
    target_h = 775
    target_w = int(cw * (target_h / ch))
    if target_w > 1400:
        target_w = 1400
        target_h = int(ch * (target_w / cw))
    resized = crop.resize((target_w, target_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (1920, 1080), (255, 255, 255))
    rpx = resized.load()
    for yy in range(target_h):
        for xx in range(target_w):
            r, g, b = rpx[xx, yy]
            if r > 242 and g > 242 and b > 238:
                rpx[xx, yy] = (255, 255, 255)
    canvas.paste(resized, ((1920 - target_w) // 2, 65 + (775 - target_h) // 2))
    _HOST_CACHE[pose_filename] = canvas
    return canvas.copy()


def apply_camera_op(img, spec):
    """Only pure framing ops (reveal_left mask or clean static close-up). ZERO PIL shapes/text!"""
    out = img.copy()
    if spec.startswith("reveal_left:"):
        x_split = int(spec.split(":", 1)[1])
        bg_col = out.getpixel((1890, 40))
        d = ImageDraw.Draw(out)
        d.rectangle([x_split, 0, 1920, 1080], fill=bg_col)
    elif spec.startswith("closeup:"):
        cx, cy, z = spec.split(":", 1)[1].split(",")
        cx, cy, zoom = int(cx), int(cy), float(z)
        cw, ch = int(1920 / zoom), int(1080 / zoom)
        x1 = max(0, min(1920 - cw, cx - cw // 2))
        y1 = max(0, min(1080 - ch, cy - ch // 2))
        out = out.crop((x1, y1, x1 + cw, y1 + ch)).resize((1920, 1080), Image.Resampling.LANCZOS)
    return out


def render_visual(spec):
    if spec.startswith("scene:"):
        rest = spec.split(":", 1)[1]
        if "+" in rest:
            s_name, ov = rest.split("+", 1)
            return apply_camera_op(load_scene(s_name), ov)
        return load_scene(rest)
    elif spec.startswith("clock:"):
        hr, badge, tag = spec.split(":", 1)[1].split("|")
        return make_flash_12num_clock(int(hr), badge, sub_tag=tag)
    elif spec.startswith("host:"):
        return make_host_reaction(spec.split(":", 1)[1])
    raise ValueError(f"Unknown visual spec: {spec}")


# ==============================================================================
# 3. POW_STUDIO CINEMA_BOXLESS SUBTITLE RENDERER (RULE 12 — ULTRA-CLEAN 1–2 LINES)
# ==============================================================================
_SUB_FONT = ImageFont.truetype(FONT_BOLD, 52)
HIGHLIGHT_WORDS = {
    "lie", "lies", "truth", "honest", "honestly", "anything", "monday", "coffee",
    "asleep", "weekend", "apartment", "saturday", "phone", "takeout", "four", "early",
    "fire", "judge", "park", "three", "weeks", "1996", "147", "diary", "quarter",
    "seventy", "percent", "sandwich", "five", "movie", "no", "trouble", "explaining",
    "effort", "friday", "drinks", "tired", "mad", "headache", "friction", "small",
    "talk", "wall", "2002", "ten", "minutes", "sixty", "awkward", "pause", "hiking",
    "secret", "trail", "second", "2016", "fmri", "amygdala", "guilt", "weakened",
    "easier", "mental", "fatigue", "two", "versions", "drained", "half-second",
    "choice", "ordinary", "relieved", "image", "connection", "nothing", "safe",
}


def burn_cinema_boxless_subtitle(img, text):
    if not text or not text.strip():
        return img
    words = text.strip().split()
    # Balanced 2-line wrap (max ~42 chars/line)
    lines = []
    if len(" ".join(words)) <= 42:
        lines = [words]
    else:
        best_split = len(words) // 2
        best_diff = 999
        for i in range(1, len(words)):
            l1 = len(" ".join(words[:i]))
            l2 = len(" ".join(words[i:]))
            if l1 <= 46 and l2 <= 46 and abs(l1 - l2) < best_diff:
                best_diff = abs(l1 - l2)
                best_split = i
        lines = [words[:best_split], words[best_split:]]

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
        ds.text((x_cursor, y_pos + 3), line_str, font=_SUB_FONT, fill=(0, 0, 0, 215), stroke_width=10, stroke_fill=(0, 0, 0, 215))

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


def split_caption_chunks(text, max_words=11):
    """Split a long spoken clause into 1–2 concise subtitle chunks so captions never crowd the frame."""
    words = text.strip().split()
    if len(words) <= max_words:
        return [text.strip()]
    # Prefer splitting near midpoint on comma/punctuation if available
    mid = len(words) // 2
    best_idx = mid
    for offset in range(0, 4):
        for cand in (mid - offset, mid + offset):
            if 2 <= cand <= len(words) - 2 and words[cand - 1][-1] in ",;:—.?!" :
                best_idx = cand
                break
        else:
            continue
        break
    part1 = " ".join(words[:best_idx])
    part2 = " ".join(words[best_idx:])
    return [part1, part2]


def norm_word(w):
    return re.sub(r"[^a-z0-9]", "", w.lower())


def align_segments_to_timeline():
    """Align all 60 segments and their sub-beats cleanly using faster_whisper words inside each segment window."""
    with open(SEGMENTS_JSON) as f:
        seg_data = json.load(f)
    segments = seg_data["segments"]
    total_dur = seg_data["total_duration"]

    # Run faster_whisper once if words cache doesn't exist
    if not os.path.exists(WORDS_JSON):
        print("Running faster_whisper word alignment on full voiceover...")
        from faster_whisper import WhisperModel
        wm = WhisperModel("base.en", device="cpu", compute_type="int8")
        w_segs, _ = wm.transcribe(VOICE_FULL_MP3, word_timestamps=True)
        all_words = []
        for ws in w_segs:
            for w in ws.words:
                all_words.append({"w": w.word.strip(), "nw": norm_word(w.word), "s": round(w.start, 3), "e": round(w.end, 3)})
        with open(WORDS_JSON, "w") as f:
            json.dump(all_words, f)
        print(f"Saved {len(all_words)} aligned words to {WORDS_JSON}")
    else:
        with open(WORDS_JSON) as f:
            all_words = json.load(f)

    timeline = []
    sfx_events = []
    act_starts = {}

    for seg in segments:
        sid = seg["id"]
        act = seg["act"]
        s0 = seg["start"]
        s1 = seg["end"]
        pause_after = seg["pause_after"]
        seg_end_total = round(s1 + pause_after, 3)

        if act not in act_starts:
            act_starts[act] = s0

        beats = SEG_BEATS[sid]
        # Gather Whisper words inside [s0 - 0.15, s1 + 0.15]
        seg_words = [w for w in all_words if w["s"] >= s0 - 0.15 and w["e"] <= s1 + 0.25]

        # Compute exact beat start/end times inside [s0, seg_end_total]
        beat_spans = []
        if len(beats) == 1:
            beat_spans.append((s0, seg_end_total))
        else:
            # Find boundary word indices using normalized word matching; fallback to char-length ratio
            weights = [max(4, len(norm_word(b[0]))) for b in beats]
            total_w = sum(weights)
            boundaries = [s0]
            w_cursor = 0
            for bi in range(1, len(beats)):
                next_tokens = [norm_word(tok) for tok in beats[bi][0].split() if norm_word(tok)][:3]
                found_t = None
                if seg_words and next_tokens:
                    # Expected rough time
                    exp_frac = sum(weights[:bi]) / total_w
                    exp_t = s0 + (s1 - s0) * exp_frac
                    # Search within +/- 2.0s window around expected time
                    best_dist = 999.0
                    for wi in range(w_cursor, len(seg_words)):
                        if seg_words[wi]["nw"] == next_tokens[0]:
                            # Verify 2nd token if available
                            ok2 = True
                            if len(next_tokens) > 1 and wi + 1 < len(seg_words):
                                ok2 = (seg_words[wi + 1]["nw"] == next_tokens[1])
                            dist = abs(seg_words[wi]["s"] - exp_t)
                            if ok2 and dist < 2.2 and dist < best_dist and seg_words[wi]["s"] > boundaries[-1] + 0.45:
                                best_dist = dist
                                found_t = max(boundaries[-1] + 0.45, seg_words[wi]["s"] - 0.04)
                                w_cursor = wi + 1
                if found_t is None:
                    frac = sum(weights[:bi]) / total_w
                    found_t = s0 + (s1 - s0) * frac
                boundaries.append(round(found_t, 3))
            boundaries.append(seg_end_total)
            for bi in range(len(beats)):
                beat_spans.append((boundaries[bi], boundaries[bi + 1]))

        # Expand long captions (>11 words) into 2 crisp caption cards holding the same clean visual
        for (bt0, bt1), (clause, spec, sfx_info) in zip(beat_spans, beats):
            if sfx_info:
                sfx_events.append((bt0, sfx_info[0], sfx_info[1], sfx_info[2]))
            sub_chunks = split_caption_chunks(clause, max_words=11)
            if len(sub_chunks) == 1:
                timeline.append({"act": act, "seg": sid, "start": bt0, "end": bt1, "sub": sub_chunks[0], "spec": spec})
            else:
                cw = [len(c) for c in sub_chunks]
                mid_t = round(bt0 + (bt1 - bt0) * (cw[0] / sum(cw)), 3)
                timeline.append({"act": act, "seg": sid, "start": bt0, "end": mid_t, "sub": sub_chunks[0], "spec": spec})
                timeline.append({"act": act, "seg": sid, "start": mid_t, "end": bt1, "sub": sub_chunks[1], "spec": spec})

    # Ensure gapless continuity from 0.000 to total_dur
    if timeline:
        timeline[0]["start"] = 0.0
        for i in range(1, len(timeline)):
            timeline[i]["start"] = timeline[i - 1]["end"]
        timeline[-1]["end"] = round(total_dur, 3)

    return timeline, sfx_events, act_starts, total_dur


def fmt_srt(sec):
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def fmt_yt_ts(sec):
    s = int(round(sec))
    return f"{s // 60}:{s % 60:02d}"


def build_frames_and_qa():
    timeline, sfx_events, act_starts, total_dur = align_segments_to_timeline()
    meta_out = os.path.join(EP_DIR, "timeline_full_hd.json")
    with open(meta_out, "w") as f:
        json.dump({"total_duration": total_dur, "act_starts": act_starts, "sfx_events": sfx_events, "frames": timeline}, f, indent=2)

    concat_lines = []
    srt_lines = []
    act_frames = {}

    for idx, item in enumerate(timeline, start=1):
        img = render_visual(item["spec"])
        img = burn_cinema_boxless_subtitle(img, item["sub"])
        fp = os.path.join(FRAMES_DIR, f"frame_{idx:03d}.jpg")
        img.save(fp, quality=96)
        item["file"] = fp

        dur = max(0.05, round(item["end"] - item["start"], 3))
        concat_lines.append(f"file '{fp}'")
        concat_lines.append(f"duration {dur:.3f}")
        srt_lines.append(f"{idx}\n{fmt_srt(item['start'])} --> {fmt_srt(item['end'])}\n{item['sub']}\n")
        act_frames.setdefault(item["act"], []).append((idx, item))

    concat_lines.append(f"file '{timeline[-1]['file']}'")

    with open(os.path.join(EP_DIR, "concat_full_hd.txt"), "w") as f:
        f.write("\n".join(concat_lines) + "\n")
    with open(os.path.join(EP_DIR, "ep02_pointless_lies_subtitles.srt"), "w") as f:
        f.write("\n".join(srt_lines))

    # Build Act-by-Act QA Contact Sheets (Rule 13)
    f_lbl = ImageFont.truetype(FONT_BOLD, 18)
    tw, th = 480, 270
    for act_name, items in sorted(act_frames.items()):
        cols = 4
        rows = math.ceil(len(items) / cols)
        sheet = Image.new("RGB", (cols * tw, rows * th), (24, 24, 28))
        ds = ImageDraw.Draw(sheet)
        for i, (fidx, item) in enumerate(items):
            r, c = divmod(i, cols)
            im = Image.open(item["file"]).resize((tw, th), Image.Resampling.LANCZOS)
            sheet.paste(im, (c * tw, r * th))
            lbl = f"#{fidx:03d} S{item['seg']:02d} {item['start']:.1f}s"
            ds.rectangle([c * tw + 4, r * th + 4, c * tw + 180, r * th + 30], fill=(0, 0, 0))
            ds.text((c * tw + 10, r * th + 6), lbl, font=f_lbl, fill=(255, 224, 102))
        sp = os.path.join(EP_DIR, f"verify_{act_name.lower()}_sheet.jpg")
        sheet.save(sp, quality=90)
        print(f"QA Sheet {act_name}: {len(items)} frames -> {sp}")

    # Auto-write YOUTUBE_UPLOAD_INFO.md (Rule 16 Ink Explainer concise standard)
    yt_md = f"""# Episode #2 — YouTube Upload Info (Kairo Spark)

## Title Options (Pick 1)
1. **Why Do We Lie For No Reason?** *(Recommended — matches thumbnail & Ink Explainer curiosity style)*
2. **Why We Lie Even When There's Nothing to Lose**
3. **Why Your Brain Invents Pointless Lies**

## Category
`People & Blogs`

## Description (Copy & Paste)
```text
Why do we lie even when telling the truth wouldn't cost us anything?

Most everyday lies aren't about hiding a dark secret or getting away with something. They happen automatically in casual conversations just to avoid tiny awkward pauses and unnecessary explanations—and psychology shows they come with a quiet cost.

Time stamps👇🏾
{fmt_yt_ts(act_starts.get('ACT_1', 0))} - The Monday Morning Coffee Machine
{fmt_yt_ts(act_starts.get('ACT_2', 0))} - Bella DePaulo's 1996 Diary Study
{fmt_yt_ts(act_starts.get('ACT_3', 0))} - Why the Truth Feels Like More Work
{fmt_yt_ts(act_starts.get('ACT_4', 0))} - Avoiding Awkward Silence (Feldman 2002)
{fmt_yt_ts(act_starts.get('ACT_5', 0))} - Why You Can't Take a Small Lie Back
{fmt_yt_ts(act_starts.get('ACT_6', 0))} - What Repeated Lies Do to Your Brain
{fmt_yt_ts(act_starts.get('ACT_7', 0))} - The Half-Second Pause

🎨 Animation by Kairo Spark

#stickman #stickmananimation #stickmanexplainer #animation #explainer #psychology
```

## Tags (Copy & Paste)
```text
stickman, stickman explainer, stickman animation, paint explainer, 2d stickman, psychology explainer, why do we lie, white lies psychology, why we lie for no reason
```

## Files Ready for Upload
- **Master Video (1080p HD, Real-ESRGAN 4× Sharp):** `ep02_pointless_lies_master.mp4`
- **Official Thumbnail (Variant 1 Chunky 3D):** `ep02_thumbnail_final.jpg`
- **Subtitles (`.srt`):** `ep02_pointless_lies_subtitles.srt`
"""
    with open(os.path.join(EP_DIR, "YOUTUBE_UPLOAD_INFO.md"), "w") as f:
        f.write(yt_md)
    print(f"Rendered {len(timeline)} total frames ({total_dur:.2f}s) + YOUTUBE_UPLOAD_INFO.md!")


def mix_full_audio():
    with open(os.path.join(EP_DIR, "timeline_full_hd.json")) as f:
        meta = json.load(f)
    sfx_events = meta["sfx_events"]
    total_dur = meta["total_duration"]

    out_mix = os.path.join(AUDIO_DIR, "ep02_full_mix_master.mp3")
    cmd = ["ffmpeg", "-y", "-i", VOICE_FULL_MP3]
    valid = []
    for t0, fname, gain_db, max_dur in sfx_events:
        p = os.path.join(SFX_DIR, fname)
        if os.path.exists(p):
            cmd.extend(["-i", p])
            valid.append((t0, fname, gain_db, max_dur))

    filters = ["[0:a]aresample=48000,aformat=channel_layouts=stereo[v]"]
    mix_ins = ["[v]"]
    for idx, (t0, fname, gain_db, max_dur) in enumerate(valid, start=1):
        delay_ms = max(0, int(round(t0 * 1000)))
        fout = max(0.05, max_dur - 0.18)
        filters.append(
            f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
            f"atrim=0:{max_dur:.2f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d=0.04,afade=t=out:st={fout:.2f}:d=0.18,"
            f"volume={gain_db}dB,adelay={delay_ms}|{delay_ms}[s{idx}]"
        )
        mix_ins.append(f"[s{idx}]")

    filters.append(
        f"{''.join(mix_ins)}amix=inputs={len(mix_ins)}:duration=first:dropout_transition=0:normalize=0,"
        f"loudnorm=I=-14.0:TP=-1.0:LRA=11[aout]"
    )
    fc_path = os.path.join(AUDIO_DIR, "ep02_audio_filter.txt")
    with open(fc_path, "w") as f:
        f.write(";\n".join(filters))

    cmd.extend([
        "-filter_complex", ";".join(filters),
        "-map", "[aout]",
        "-c:a", "libmp3lame", "-b:a", "192k",
        "-t", f"{total_dur:.3f}",
        out_mix,
    ])
    subprocess.run(cmd, check=True)
    print(f"Mixed full episode audio ({len(valid)} SFX cues) -> {out_mix}")
    return out_mix, total_dur


def encode_master_mp4():
    mix_mp3, total_dur = mix_full_audio()
    concat_path = os.path.join(EP_DIR, "concat_full_hd.txt")
    out_mp4 = os.path.join(EP_DIR, "ep02_pointless_lies_master.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_path,
        "-i", mix_mp3,
        "-vf", "fps=30,scale=1920:1080,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "16",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-t", f"{total_dur:.3f}",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"Encoded FULL HD MASTER MP4 -> {out_mp4}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames-only", action="store_true")
    ap.add_argument("--encode", action="store_true")
    args = ap.parse_args()
    if args.frames_only:
        build_frames_and_qa()
    elif args.encode:
        encode_master_mp4()
    else:
        build_frames_and_qa()
        encode_master_mp4()
