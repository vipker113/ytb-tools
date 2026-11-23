#!/usr/bin/env python3
"""
Kairo Spark — Grok Imagine Video (Image-to-Video) Batch 2D Flash Scene Animator
Transforms the 32 static 2D Flash scenes in `episodes/pilot-01-why-5-days/scenes/`
into 4-second 1080p animated 2D Flash video clips (`animated_clips/*.mp4`)
using xAI's `grok-imagine-video-1.5-lite` ($0.02/s) or `grok-imagine-video-1.5` ($0.08/s).

Usage:
  1. Via xAI API (Automated Batch):
     export XAI_API_KEY="xai-..."
     python scripts/grok_animate_scenes.py --model grok-imagine-video-1.5-lite --duration 4

  2. Export Prompts Table for Manual Generation on grok.com Web UI:
     python scripts/grok_animate_scenes.py --export-prompts
"""

import argparse
import base64
import json
import os
import time
import urllib.error
import urllib.request

EP_DIR = "/Applications/code/science-knowledge/ytb-tools/episodes/pilot-01-why-5-days"
SCENES_DIR = os.path.join(EP_DIR, "scenes")
CLIPS_DIR = os.path.join(EP_DIR, "animated_clips")
FLOW_GRIDS_DIR = os.path.join(EP_DIR, "flow_grids")
PROMPTS_MD = os.path.join(EP_DIR, "grok_32_scene_motion_prompts.md")
FLOW_PROMPTS_MD = os.path.join(FLOW_GRIDS_DIR, "GOOGLE_FLOW_8_GRIDS_PROMPTS.md")

# 8 2x2 Grid Definitions for Google Flow (1 generation = 4 animated scenes simultaneously!)
FLOW_2X2_GRIDS: list[tuple[str, list[str], str]] = [
    (
        "grid_01_act1_act2_hero.jpg",
        [
            "01_sunday_8pm_couch_monday.mp4",
            "02_medieval_150_days_picnic.mp4",
            "03_saint_monday_closed_loom.mp4",
            "04_factory_1850s_master_clock.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left stickman on blue sofa clutches his chest and sighs at the MONDAY calendar; Top-right two medieval stickmen under oak tree laugh and raise ale mugs; Bottom-left stickman sleeps peacefully on bench beside CLOSED MONDAY loom; Bottom-right three stickman workers march in step as factory gears spin and furnace fire flickers.",
    ),
    (
        "grid_02_act3_act5_hero.jpg",
        [
            "05_ford_1926_model_t_shopping.mp4",
            "06_senate_1933_30hr_gavel.mp4",
            "07_office_501pm_email_meeting.mp4",
            "08_sunset_hilltop_coffee_peace.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left stickman walks happily swinging shopping bags past the black 1920s Model T car; Top-right stickman taps the 30 HRS / WK sign beside the wooden gavel; Bottom-left exhausted stickman types frantically between wobbling EMAIL and MEETING paper stacks at 5:01; Bottom-right stickman on green sunset hill sips a steaming coffee mug peacefully.",
    ),
    (
        "grid_03_act1_extra.jpg",
        [
            "13_sunday_night_moon_sofa.mp4",
            "14_ancient_sunrise_hill_stretch.mp4",
            "15_harvard_150_days_ledger.mp4",
            "16_medieval_parish_feast_table.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left worried stickman on sofa glances at the yellow crescent moon window and sighs; Top-right stickman on green hill stretches both arms wide as the morning sun rises; Bottom-left stickman moves magnifying glass over the 150 DAYS ledger book; Bottom-right four medieval stickmen clink ale mugs and cheer at feast table outside church.",
    ),
    (
        "grid_04_act2_extra.jpg",
        [
            "17_blacksmith_done_for_today.mp4",
            "18_tavern_sunday_mugs.mp4",
            "19_steam_boiler_boss_clock.mp4",
            "20_textile_mill_no_watches.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left stickman blacksmith lowers hammer by anvil and nods at DONE FOR TODAY sign; Top-right three stickmen clink foamy mugs around wooden tavern barrel; Bottom-left top-hat boss shakes finger at clock as orange fire flickers in steam boiler; Bottom-right top-hat boss drops pocket watches into NO WATCHES wooden crate.",
    ),
    (
        "grid_05_act3_extra.jpg",
        [
            "21_ford_1926_assembly_line.mp4",
            "22_steel_boss_angry_5days.mp4",
            "23_exhausted_worker_bed_model_t.mp4",
            "24_sunday_morning_church_walk.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left factory stickmen turn wrenches on black Model T cars on conveyor belt; Top-right angry top-hat boss slams fist on desk beside 5 DAYS?! newspaper; Bottom-left exhausted stickman sleeps face-down on bed while Model T sits outside window; Bottom-right stickman family walks hand-in-hand toward white church under sunny sky.",
    ),
    (
        "grid_06_act4_extra.jpg",
        [
            "25_keynes_1930_15hrs_chalkboard.mp4",
            "26_kellogg_2pm_park_family.mp4",
            "27_lobby_hallway_top_hats.mp4",
            "28_frozen_40hrs_ice_clock.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left economist stickman points at 15 HRS / WK green chalkboard while talking; Top-right stickman parents and kids toss red ball back and forth in sunny green park; Bottom-left three top-hat bosses march down hallway swinging LOBBY briefcases; Bottom-right stickman looks up in shock at giant 40 HRS clock frozen in blue ice spikes.",
    ),
    (
        "grid_07_act5_extra.jpg",
        [
            "29_1940_clerks_vs_today_laptop.mp4",
            "30_bored_meeting_conference.mp4",
            "31_treadmill_house_phone_dollar.mp4",
            "32_twilight_sofa_peaceful_smile.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left 1940 clerks scribble furiously in paper piles while TODAY stickman taps one laptop key; Top-right five bored stickmen slump and yawn around MEETING conference table; Bottom-left stickman runs in place on red treadmill chasing floating house, phone, and dollar icons; Bottom-right stickman on sofa smiles calmly at twilight window.",
    ),
    (
        "grid_08_ref_base.jpg",
        [
            "09_ref_office_clock_desk.mp4",
            "10_ref_kalahari_campfire_17hrs.mp4",
            "11_ref_sunday_tv_calendar.mp4",
            "12_ref_chart_150_vs_260_board.mp4",
        ],
        "2D Adobe Flash flat stickman animation across all 4 split-screen panels simultaneously, locked steady camera, no zoom: Top-left tired stickman at office desk sighs as 5:01 wall clock ticks; Top-right ancient hunter-gatherer relaxes on straw mat as orange campfire flames flicker; Bottom-left WHY 5 DAYS? board sun icon rotates gently; Bottom-right stickman presenter gestures at living room sofa icons.",
    ),
]

# Guardrail prefix/suffix to prevent 3D morphing or jerky camera zooms in Grok Imagine Video
FLASH_2D_MOTION_GUARD = (
    "2D Adobe Flash flat vector stickman animation, locked steady camera, no camera zoom, "
    "keep flat 2D colors and clean black ink outlines without 3D shading: "
)

SCENE_MOTION_PROMPTS: list[tuple[str, str]] = [
    (
        "01_sunday_8pm_couch_monday.png",
        "The stickman with the red tie and yellow forehead sticky note sits on the blue sofa, sighs deeply, clutches his chest with one hand, blinks his tired eyes, and glances nervously at the MONDAY calendar while the wall clock hands tick.",
    ),
    (
        "02_medieval_150_days_picnic.png",
        "Two cheerful 2D stickman peasants sitting under the green oak tree laugh, raise their wooden ale mugs in a toast, and sway gently while leaves rustle in the breeze.",
    ),
    (
        "03_saint_monday_closed_loom.png",
        "The sleeping stickman weaver on the wooden bench breathes peacefully with his chest rising and falling as small hand-drawn Zzz letters float up beside the idle CLOSED MONDAY wooden handloom.",
    ),
    (
        "04_factory_1850s_master_clock.png",
        "The three stickman factory workers march forward in a synchronized mechanical rhythm while the black iron gears on the brick wall rotate, the orange furnace fire flickers, and the giant master clock ticks.",
    ),
    (
        "05_ford_1926_model_t_shopping.png",
        "The stickman with the red tie and yellow sticky note walks happily along the sidewalk swinging his colorful shopping bags while the black 1920s Model T car's wheels gently idle.",
    ),
    (
        "06_senate_1933_30hr_gavel.png",
        "The stickman with the red tie and '!' yellow forehead sticky note taps the 30 HRS / WK sign excitedly with his finger while the wooden gavel on the desk bounces slightly.",
    ),
    (
        "07_office_501pm_email_meeting.png",
        "The exhausted stickman at the office desk types frantically on the laptop, blinks his tired eyes, and slumps his shoulders as the tall EMAIL and MEETING paper stacks wobble slightly and the 5:01 clock ticks.",
    ),
    (
        "08_sunset_hilltop_coffee_peace.png",
        "The stickman stands calmly on the green hilltop under the warm sunset sky, raises the warm coffee mug to take a peaceful sip, and smiles as gentle steam rises from the cup.",
    ),
    (
        "09_ref_office_clock_desk.png",
        "The tired stickman sitting at the office desk rubs his forehead, looks down at the laptop screen, and sighs while the 5:01 wall clock hands tick steadily.",
    ),
    (
        "10_ref_kalahari_campfire_17hrs.png",
        "The ancient hunter-gatherer stickman reclines comfortably on the straw mat warming his hands as the orange campfire flames flicker and dance happily.",
    ),
    (
        "11_ref_sunday_tv_calendar.png",
        "The hand-drawn sun icon in the top-left rotates gently and the green leaf in the bottom-right sways while the bold WHY 5 DAYS? text pulses slightly on the white board.",
    ),
    (
        "12_ref_chart_150_vs_260_board.png",
        "The stickman presenter points his hand up and down at the green 150 DAYS bar and the tall red 260 DAYS bar on the whiteboard while nodding his head.",
    ),
    (
        "13_sunday_night_moon_sofa.png",
        "The worried stickman on the blue sofa turns his head slowly from the dark window with the glowing yellow crescent moon toward the viewer and sighs.",
    ),
    (
        "14_ancient_sunrise_hill_stretch.png",
        "The stickman on the green hill stretches both arms wide toward the sky and smiles warmly as the yellow morning sun rises slightly over the horizon.",
    ),
    (
        "15_harvard_150_days_ledger.png",
        "The stickman with the red tie moves the magnifying glass slowly across the open 150 DAYS ledger book, blinks in surprise, and leans closer to inspect the page.",
    ),
    (
        "16_medieval_parish_feast_table.png",
        "Four happy medieval stickman peasants around the wooden feast table clink their ale mugs together, cheer, and wave their arms in celebration outside the stone church.",
    ),
    (
        "17_blacksmith_done_for_today.png",
        "The stickman blacksmith lowers his hammer beside the iron anvil, wipes his brow with relief, and gestures proudly toward the DONE FOR TODAY sign.",
    ),
    (
        "18_tavern_sunday_mugs.png",
        "Three cheerful stickmen sitting on barstools around the wooden tavern barrel clink their foamy mugs together and laugh warmly.",
    ),
    (
        "19_steam_boiler_boss_clock.png",
        "The angry stickman boss in the black top hat shakes his pointing finger at the wall clock while bright orange flames flicker inside the iron boiler and dark smoke billows from the chimney.",
    ),
    (
        "20_textile_mill_no_watches.png",
        "The stern stickman boss in the black top hat drops shiny pocket watches from his hand into the wooden NO WATCHES crate one by one.",
    ),
    (
        "21_ford_1926_assembly_line.png",
        "Two stickman factory workers turn their metal wrenches on the black 1920s Model T cars as the conveyor belt rollers turn beneath the wheels.",
    ),
    (
        "22_steel_boss_angry_5days.png",
        "The furious stickman tycoon in the black top hat slams his fist down onto the brown desk repeatedly, making the 5 DAYS?! newspaper vibrate.",
    ),
    (
        "23_exhausted_worker_bed_model_t.png",
        "The exhausted stickman worker sleeps face-down on the bed with his back rising and falling slowly while the black Model T car sits still outside the dark window.",
    ),
    (
        "24_sunday_morning_church_walk.png",
        "The stickman parents holding their child's hand walk gently along the green grass toward the white church door as the yellow sun shines above.",
    ),
    (
        "25_keynes_1930_15hrs_chalkboard.png",
        "The stickman economist taps his finger on the green chalkboard reading 15 HRS / WK and turns his head to explain while talking.",
    ),
    (
        "26_kellogg_2pm_park_family.png",
        "The stickman parents and two small stickman children in the sunny green park toss the red ball back and forth happily while the children jump with joy.",
    ),
    (
        "27_lobby_hallway_top_hats.png",
        "Three stickman corporate lobbyists in black top hats march briskly down the hallway swinging their LOBBY briefcases toward the wooden door.",
    ),
    (
        "28_frozen_40hrs_ice_clock.png",
        "The stickman with the red tie and yellow forehead sticky note shivers slightly and looks up in disbelief at the giant 40 HRS clock covered in glistening blue ice spikes.",
    ),
    (
        "29_1940_clerks_vs_today_laptop.png",
        "On the left the three 1940 stickman clerks scribble furiously on paper stacks, while on the right the modern stickman casually taps a single key on his laptop with one finger.",
    ),
    (
        "30_bored_meeting_conference.png",
        "The five bored stickmen around the conference table slump in their chairs, blink slowly, and prop their heads on their hands in front of the MEETING board.",
    ),
    (
        "31_treadmill_house_phone_dollar.png",
        "The stickman with the red tie runs tirelessly in place on the moving red treadmill belt while the house, smartphone, and dollar bill icons bob up and down ahead of him.",
    ),
    (
        "32_twilight_sofa_peaceful_smile.png",
        "The stickman sitting on the blue sofa takes a calm, deep breath, relaxes his shoulders, and smiles gently while looking out the window at the warm twilight sky.",
    ),
]


def export_prompts_markdown() -> None:
    os.makedirs(CLIPS_DIR, exist_ok=True)
    lines = [
        "# Pilot #1 — 32 Grok Imagine Video (Image-to-Video) 2D Flash Motion Prompts",
        "",
        "> **Hướng dẫn dùng trên Web `grok.com` hoặc qua API `grok-imagine-video-1.5`:**",
        "> - **Cách 1 (Tự động 100% qua API):** Đặt `export XAI_API_KEY=\"xai-...\"` rồi chạy:",
        ">   ```bash",
        ">   /Applications/code/science-knowledge/youtube-shorts-channel/.venv/bin/python /Applications/code/science-knowledge/ytb-tools/scripts/grok_animate_scenes.py --animate-all",
        ">   ```",
        "> - **Cách 2 (Tạo trực tiếp trên Web `grok.com`):** Tải từng ảnh trong `episodes/pilot-01-why-5-days/scenes/` lên `grok.com` (chế độ **Make Video / Animate**), dán đúng câu Prompt bên dưới, tải file `.mp4` về và lưu cùng tên vào thư mục `episodes/pilot-01-why-5-days/animated_clips/` (ví dụ `01_sunday_8pm_couch_monday.mp4`).",
        "",
        "| # | File Ảnh Tĩnh (`scenes/`) | File Video Đích (`animated_clips/`) | Prompt Chuyển Động 2D Flash Chuẩn Cho Grok |",
        "| :---: | :--- | :--- | :--- |",
    ]
    for idx, (fname, prompt) in enumerate(SCENE_MOTION_PROMPTS, start=1):
        mp4_name = fname.replace(".png", ".mp4")
        full_prompt = FLASH_2D_MOTION_GUARD + prompt
        lines.append(f"| {idx:02d} | `{fname}` | `{mp4_name}` | `{full_prompt}` |")

    with open(PROMPTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"Exported 32 Grok 2D Flash Motion Prompts to: {PROMPTS_MD}")

    os.makedirs(FLOW_GRIDS_DIR, exist_ok=True)
    flow_lines = [
        "# Google Flow (`50 Credits/Day` Trick) — Animate 4 Scenes Per Generation (`8 2x2 Grids = 32 Scenes`)",
        "",
        "> **Mẹo Nhân 4 Trên Google Flow (`labs.google/fx/tools/flow` — Chế độ `Frames to Video`):**",
        "> - Với **50 credits/ngày**:",
        ">   - Nếu chọn **`Veo 3.1 Lite` (`10 credits/video`)**: Bạn tạo được **5 video/ngày**. Vì mỗi ảnh dưới đây là một **Bảng Ghép `2x2` (chứa 4 cảnh 2D Flash trong 1 khung 16:9)**, chỉ với **5 lần tạo (`50 credits`)**, bạn biến được **`5 × 4 = 20 cảnh` thành video chuyển động 8 giây trong đúng 1 ngày**!",
        ">   - Nếu chọn **`Veo 3.1 Fast` (`20 credits/video`)**: 2 lần Fast (`40 credits`) + 1 lần Lite (`10 credits`) = **3 video `2x2` (`12 cảnh chuyển động` / ngày)**.",
        "> - **Quy trình 3 bước:**",
        ">   1. Mở thư mục `episodes/pilot-01-why-5-days/flow_grids/`, kéo ảnh `grid_01_act1_act2_hero.jpg` .. `grid_08_ref_base.jpg` lên **Google Flow (`Frames to Video`)**.",
        ">   2. Copy câu **Prompt 4-in-1** tương ứng trong bảng dưới đây dán vào Google Flow.",
        ">   3. Tải video `.mp4` từ Google Flow về và lưu vào `episodes/pilot-01-why-5-days/flow_grids/` với tên `grid_01.mp4` .. `grid_08.mp4` (hoặc trùng tên ảnh `.mp4`), sau đó chạy:",
        ">      ```bash",
        ">      /Applications/code/science-knowledge/youtube-shorts-channel/.venv/bin/python /Applications/code/science-knowledge/ytb-tools/scripts/grok_animate_scenes.py --slice-flow-grids",
        ">      ```",
        ">      Script sẽ tự động cắt mỗi video `2x2` thành **4 video Full HD `1920x1080` riêng biệt** vào `animated_clips/` và lắp thẳng vào `pilot_01_why_5_days_master.mp4`!",
        "",
        "| # | Ảnh Ghép `2x2` (`flow_grids/`) | Tên File MP4 Khi Tải Về (`flow_grids/`) | 4 Cảnh Được Tách Tự Động (`animated_clips/`) | Prompt 4-Trong-1 Dán Vào Google Flow (`Frames to Video`) |",
        "| :---: | :--- | :--- | :--- | :--- |",
    ]
    for idx, (g_img, out_mp4s, g_prompt) in enumerate(FLOW_2X2_GRIDS, start=1):
        short_mp4 = f"grid_{idx:02d}.mp4"
        outs_str = "<br>".join(f"`{m}`" for m in out_mp4s)
        flow_lines.append(f"| {idx:02d} | `{g_img}` | `{short_mp4}` (hoặc `{g_img.replace('.jpg', '.mp4')}`) | {outs_str} | `{g_prompt}` |")

    with open(FLOW_PROMPTS_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(flow_lines) + "\n")
    print(f"Exported 8 Google Flow 2x2 Grid Prompts to: {FLOW_PROMPTS_MD}")


def slice_flow_grid_videos() -> list[str]:
    """
    Scans `episodes/pilot-01-why-5-days/flow_grids/` for downloaded Google Flow 2x2 grid `.mp4` videos
    (`grid_01.mp4` .. `grid_08.mp4` or `grid_01_act1_act2_hero.mp4`, etc.) and slices each 2x2 video
    into 4 individual 1920x1080 `.mp4` clips inside `animated_clips/` (trimming out the center black dividers).
    """
    import subprocess

    os.makedirs(CLIPS_DIR, exist_ok=True)
    sliced = []
    for idx, (g_img, out_mp4s, _) in enumerate(FLOW_2X2_GRIDS, start=1):
        candidates = [
            os.path.join(FLOW_GRIDS_DIR, f"grid_{idx:02d}.mp4"),
            os.path.join(FLOW_GRIDS_DIR, g_img.replace(".jpg", ".mp4")),
        ]
        src_mp4 = next((p for p in candidates if os.path.exists(p) and os.path.getsize(p) > 50_000), None)
        if not src_mp4:
            continue

        print(f"[SLICE 2x2] Splitting {os.path.basename(src_mp4)} into 4 1080p animated scene clips...")
        # Quadrant crop filters trimming 10px margin from outer edges and center black divider
        crop_filters = [
            "crop=iw/2-16:ih/2-16:8:8,scale=1920:1080:flags=lanczos",
            "crop=iw/2-16:ih/2-16:iw/2+8:8,scale=1920:1080:flags=lanczos",
            "crop=iw/2-16:ih/2-16:8:ih/2+8,scale=1920:1080:flags=lanczos",
            "crop=iw/2-16:ih/2-16:iw/2+8:ih/2+8,scale=1920:1080:flags=lanczos",
        ]
        for vf, dst_name in zip(crop_filters, out_mp4s):
            dst_path = os.path.join(CLIPS_DIR, dst_name)
            subprocess.check_call(
                [
                    "/opt/homebrew/bin/ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    src_mp4,
                    "-vf",
                    vf,
                    "-an",
                    "-c:v",
                    "h264_videotoolbox",
                    "-b:v",
                    "5000k",
                    "-pix_fmt",
                    "yuv420p",
                    dst_path,
                ]
            )
            sliced.append(dst_path)
            print(f"  -> Saved 1080p clip: {dst_path}")
    return sliced


def animate_scene_via_xai_api(
    fname: str,
    prompt: str,
    api_key: str,
    model: str = "grok-imagine-video-1.5-lite",
    duration: int = 4,
    resolution: str = "1080p",
) -> str | None:
    os.makedirs(CLIPS_DIR, exist_ok=True)
    in_path = os.path.join(SCENES_DIR, fname)
    out_path = os.path.join(CLIPS_DIR, fname.replace(".png", ".mp4"))
    if os.path.exists(out_path) and os.path.getsize(out_path) > 50_000:
        print(f"[SKIP] Already animated: {out_path}")
        return out_path

    with open(in_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "model": model,
        "prompt": FLASH_2D_MOTION_GUARD + prompt,
        "image": {"url": f"data:image/png;base64,{b64_img}"},
        "duration": duration,
        "resolution": resolution,
        "aspect_ratio": "16:9",
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "KairoSparkStudio/1.0",
    }
    req = urllib.request.Request(
        "https://api.x.ai/v1/videos/generations",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    print(f"[SUBMIT] {fname} -> {model} ({duration}s, {resolution})...")
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    req_id = resp.get("request_id") or resp.get("id")
    if not req_id:
        raise RuntimeError(f"Unexpected response from xAI API: {resp}")

    status_url = f"https://api.x.ai/v1/videos/{req_id}"
    for attempt in range(45):
        time.sleep(5)
        st_req = urllib.request.Request(status_url, headers=headers, method="GET")
        st_data = json.loads(urllib.request.urlopen(st_req, timeout=20).read().decode("utf-8"))
        status = st_data.get("status", "").lower()
        video_url = (
            st_data.get("video_url")
            or st_data.get("url")
            or (st_data.get("video") or {}).get("url")
        )
        if status in ("completed", "succeeded", "done") or video_url:
            if not video_url:
                raise RuntimeError(f"Completed without video_url: {st_data}")
            vid_bytes = urllib.request.urlopen(video_url, timeout=60).read()
            with open(out_path, "wb") as f:
                f.write(vid_bytes)
            print(f"[DONE] Saved animated clip: {out_path} ({len(vid_bytes) // 1024} KB)")
            return out_path
        if status in ("failed", "error", "cancelled"):
            raise RuntimeError(f"Grok video generation failed for {fname}: {st_data}")
        print(f"  [{fname}] status={status or 'processing'} (poll {attempt + 1}/45)...")

    raise TimeoutError(f"Timed out waiting for Grok video generation: {fname}")


def animate_scene_via_kling_fal(
    fname: str,
    prompt: str,
    fal_key: str,
    endpoint: str = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video",
    duration: str = "5",
) -> str | None:
    """
    Animates a static 2D Flash PNG scene using Kling AI (v2.5 Turbo Pro or v2.6 Pro) via fal.ai REST queue API.
    """
    os.makedirs(CLIPS_DIR, exist_ok=True)
    in_path = os.path.join(SCENES_DIR, fname)
    out_path = os.path.join(CLIPS_DIR, fname.replace(".png", ".mp4"))
    if os.path.exists(out_path) and os.path.getsize(out_path) > 50_000:
        print(f"[SKIP] Already animated: {out_path}")
        return out_path

    with open(in_path, "rb") as f:
        b64_img = base64.b64encode(f.read()).decode("ascii")

    payload = {
        "prompt": FLASH_2D_MOTION_GUARD + prompt,
        "image_url": f"data:image/png;base64,{b64_img}",
        "duration": str(duration),
        "aspect_ratio": "16:9",
        "negative_prompt": "3d render, realistic skin, gradient shading, camera zoom, blurry, extra limbs, morphing",
        "cfg_scale": 0.65,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Key {fal_key}",
        "User-Agent": "KairoSparkStudio/1.0",
    }
    submit_url = f"https://queue.fal.run/{endpoint}"
    req = urllib.request.Request(submit_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    print(f"[KLING SUBMIT] {fname} -> {endpoint} ({duration}s)...")
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    status_url = resp.get("status_url")
    response_url = resp.get("response_url")
    if not (status_url and response_url):
        raise RuntimeError(f"Unexpected Kling/Fal queue response: {resp}")

    for attempt in range(60):
        time.sleep(5)
        st_req = urllib.request.Request(status_url, headers=headers, method="GET")
        st_data = json.loads(urllib.request.urlopen(st_req, timeout=20).read().decode("utf-8"))
        status = st_data.get("status", "").upper()
        if status == "COMPLETED":
            res_req = urllib.request.Request(response_url, headers=headers, method="GET")
            res_data = json.loads(urllib.request.urlopen(res_req, timeout=20).read().decode("utf-8"))
            video_url = (res_data.get("video") or {}).get("url") or res_data.get("video_url")
            if not video_url:
                raise RuntimeError(f"Kling completed without video URL: {res_data}")
            vid_bytes = urllib.request.urlopen(video_url, timeout=60).read()
            with open(out_path, "wb") as f:
                f.write(vid_bytes)
            print(f"[KLING DONE] Saved animated clip: {out_path} ({len(vid_bytes) // 1024} KB)")
            return out_path
        if status in ("FAILED", "ERROR", "CANCELLED"):
            raise RuntimeError(f"Kling generation failed for {fname}: {st_data}")
        print(f"  [{fname}] Kling status={status} (poll {attempt + 1}/60)...")

    raise TimeoutError(f"Timed out waiting for Kling video generation: {fname}")


KLING_MCP_TOKEN_FILE = "/Users/admin/.mcp-auth/mcp-remote-v1/dd23ae12bf6bf6472a0e70ceb0f7bdf5_tokens.json"
KLING_MCP_CLIENT_FILE = "/Users/admin/.mcp-auth/mcp-remote-v1/dd23ae12bf6bf6472a0e70ceb0f7bdf5_client_info.json"


def get_kling_mcp_access_token() -> str:
    if not os.path.exists(KLING_MCP_TOKEN_FILE):
        raise FileNotFoundError(f"Kling MCP OAuth token not found at {KLING_MCP_TOKEN_FILE}. Run `npx -y mcp-remote https://kling.ai/mcp` to authorize.")
    with open(KLING_MCP_TOKEN_FILE, "r", encoding="utf-8") as f:
        tok_data = json.load(f)
    return tok_data["access_token"]


def kling_mcp_rpc(tool_name: str, arguments: dict, access_token: str) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    req = urllib.request.Request(
        "https://kling.ai/mcp",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "KairoSparkStudio/1.0",
        },
        method="POST",
    )
    return json.loads(urllib.request.urlopen(req, timeout=45).read().decode("utf-8"))


def animate_scene_via_kling_mcp(
    fname: str,
    prompt: str,
    model: str = "kling-video-v4_0_flash",
    duration: int = 4,
    resolution: str = "720p",
) -> str | None:
    """
    Animates a static 2D Flash PNG scene directly through the authorized `https://kling.ai/mcp` server:
    1. Calls `file_upload` to get a single-use upload ticket (`https://kling.ai/api/mcp/files`).
    2. Uploads the local PNG via multipart/form-data to get a `https://s15-kling.klingai.com/...` URL.
    3. Calls `image_to_video` with `kling-video-v4_0_flash` (4s) or `kling-video-v2_5` (5s).
    4. Polls `query_tasks` until complete and downloads `urlWithoutWatermark` (or `url`) to `animated_clips/`.
    """
    import uuid

    os.makedirs(CLIPS_DIR, exist_ok=True)
    in_path = os.path.join(SCENES_DIR, fname)
    out_path = os.path.join(CLIPS_DIR, fname.replace(".png", ".mp4"))
    if os.path.exists(out_path) and os.path.getsize(out_path) > 50_000:
        print(f"[SKIP] Already animated: {out_path}")
        return out_path

    tok = get_kling_mcp_access_token()
    trace_id = str(uuid.uuid4())
    fsize = os.path.getsize(in_path)

    # Step 1: Request upload ticket
    up_res = kling_mcp_rpc(
        "file_upload",
        {"filename": fname, "contentType": "image/png", "size": fsize, "taskTraceId": trace_id},
        tok,
    )
    ticket_info = json.loads(up_res["result"]["content"][0]["text"])
    ticket = ticket_info["ticket"]
    upload_url = ticket_info.get("upload_url") or ticket_info["uploadUrl"]

    # Step 2: Upload PNG bytes via multipart/form-data
    boundary = "----KairoSparkBoundary" + uuid.uuid4().hex
    with open(in_path, "rb") as f:
        file_bytes = f.read()
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="ticket"\r\n\r\n'
        f"{ticket}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    up_req = urllib.request.Request(
        upload_url,
        data=body,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "KairoSparkStudio/1.0",
        },
        method="POST",
    )
    up_out = json.loads(urllib.request.urlopen(up_req, timeout=60).read().decode("utf-8"))
    file_url = up_out.get("url") or (up_out.get("data") or {}).get("url")
    if not file_url:
        raise RuntimeError(f"Kling MCP file upload did not return url: {up_out}")
    print(f"[KLING MCP UPLOADED] {fname} -> {file_url[:72]}...")

    # Step 3: Submit image_to_video
    dur_str = str(duration if "v4_0" in model else (5 if duration <= 5 else 10))
    args_list = [
        {"name": "prompt", "value": FLASH_2D_MOTION_GUARD + prompt},
        {"name": "duration", "value": dur_str},
        {"name": "resolution", "value": resolution},
    ]
    if "v2_5" in model or "v2_6" in model or "v3_0" in model:
        args_list.append({"name": "enable_audio", "value": "false"})

    gen_res = kling_mcp_rpc(
        "image_to_video",
        {
            "model": model,
            "arguments": args_list,
            "inputs": [{"name": "first_image", "inputType": "URL", "url": file_url}],
            "rationale": f"Animate Pilot #1 2D Flash scene {fname} into a {dur_str}s motion clip per user request",
            "taskTraceId": trace_id,
        },
        tok,
    )
    res_block = gen_res.get("result", {})
    txt_content = (res_block.get("content") or [{}])[0].get("text", "")
    if res_block.get("isError"):
        raise RuntimeError(f"Kling MCP image_to_video error: {txt_content}")

    gen_data = json.loads(txt_content)
    gen_id = str(gen_data.get("generationId") or gen_data.get("generation_id") or gen_data.get("id"))
    print(f"[KLING MCP SUBMITTED] {fname} -> generationId={gen_id}")

    # Step 4: Poll query_tasks
    for attempt in range(60):
        time.sleep(5)
        q_res = kling_mcp_rpc("query_tasks", {"generationId": gen_id, "taskTraceId": trace_id}, tok)
        q_txt = (q_res.get("result", {}).get("content") or [{}])[0].get("text", "{}")
        q_data = json.loads(q_txt)
        status = str(q_data.get("status", "")).upper()
        # Look for video URL in result
        video_url = (
            q_data.get("urlWithoutWatermark")
            or q_data.get("url")
            or ((q_data.get("works") or [{}])[0] if q_data.get("works") else {}).get("urlWithoutWatermark")
            or ((q_data.get("works") or [{}])[0] if q_data.get("works") else {}).get("url")
        )
        if video_url:
            vid_bytes = urllib.request.urlopen(video_url, timeout=60).read()
            with open(out_path, "wb") as f:
                f.write(vid_bytes)
            print(f"[KLING MCP DONE] Saved animated clip: {out_path} ({len(vid_bytes) // 1024} KB)")
            return out_path
        if status in ("FAILED", "ERROR", "CANCELLED"):
            raise RuntimeError(f"Kling MCP task failed for {fname}: {q_data}")
        print(f"  [{fname}] Kling MCP status={status or 'RUNNING'} (poll {attempt + 1}/60)...")

    raise TimeoutError(f"Timed out waiting for Kling MCP task {gen_id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kairo Spark — Grok, Kling & Google Flow 2D Flash Scene Animator")
    parser.add_argument("--export-prompts", action="store_true", help="Export 32 scene motion prompts + 8 Google Flow 2x2 Grid prompts")
    parser.add_argument("--slice-flow-grids", action="store_true", help="Slice downloaded Google Flow 2x2 grid MP4s into 4 individual 1080p scene clips")
    parser.add_argument("--animate-all", action="store_true", help="Animate all 32 scenes via selected provider API")
    parser.add_argument("--scene", help="Animate a single scene filename (e.g. 01_sunday_8pm_couch_monday.png)")
    parser.add_argument("--provider", choices=["kling-mcp", "grok", "kling-fal"], default="kling-mcp", help="Provider: 'kling-mcp' (official https://kling.ai/mcp), 'grok' (xAI API), or 'kling-fal'")
    parser.add_argument("--api-key", default="", help="API Key (only needed for grok or kling-fal)")
    parser.add_argument("--model", default="kling-video-v4_0_flash", help="Model name (e.g. kling-video-v4_0_flash, kling-video-v2_5, grok-imagine-video-1.5-lite)")
    parser.add_argument("--duration", type=int, default=4, help="Clip duration in seconds (default: 4)")
    parser.add_argument("--resolution", default="720p", help="Output resolution: 720p or 1080p")
    args = parser.parse_args()

    export_prompts_markdown()

    if args.slice_flow_grids:
        out_clips = slice_flow_grid_videos()
        print(f"Sliced {len(out_clips)} individual 1080p scene clips into {CLIPS_DIR}")

    if args.animate_all or args.scene:
        targets = [item for item in SCENE_MOTION_PROMPTS if not args.scene or item[0] == args.scene]
        if args.provider == "kling-mcp":
            for fname, prompt in targets:
                animate_scene_via_kling_mcp(fname, prompt, model=args.model, duration=args.duration, resolution=args.resolution)
        elif args.provider == "grok":
            key = args.api_key or os.environ.get("XAI_API_KEY", "")
            if not key:
                raise SystemExit("ERROR: Missing XAI_API_KEY. Pass --api-key xai-... or set export XAI_API_KEY='xai-...'")
            for fname, prompt in targets:
                animate_scene_via_xai_api(fname, prompt, api_key=key, model=args.model, duration=args.duration, resolution=args.resolution)
        else:
            key = args.api_key or os.environ.get("FAL_KEY", "")
            if not key:
                raise SystemExit("ERROR: Missing FAL_KEY for Kling. Pass --api-key ... or set export FAL_KEY='...'")
            ep = args.model if "kling" in args.model else "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
            for fname, prompt in targets:
                animate_scene_via_kling_fal(fname, prompt, fal_key=key, endpoint=ep, duration=str(max(5, args.duration)))
