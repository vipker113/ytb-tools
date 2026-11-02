#!/usr/bin/env python3
"""
Export the Venus Pilot unified Frame-0 (`t = 0.000s`) thumbnail (`<video-slug>.jpg` & `.png`)
and mobile preview sheet in the exact same directory as the final MP4.
Delegates to the standardized channel utility `first_frame_thumbnail.py`.
"""

from first_frame_thumbnail import export_first_frame_thumbnail

ROOT = "/Applications/code/science-knowledge/youtube-shorts-channel"
OUT_DIR = f"{ROOT}/output/proof-of-wonder/01-venus-hotter-than-mercury"
FINAL_MP4 = f"{OUT_DIR}/01-venus-reflects-most-sunlight-why-is-it-hotter-than-mercury.mp4"
RAW_FRAME0 = f"{OUT_DIR}/shots/shot_01_frame0_master.png"

if __name__ == "__main__":
    export_first_frame_thumbnail(
        mp4_path=FINAL_MP4,
        raw_frame0_rgb_path=RAW_FRAME0,
        title_preview="Venus Reflects Most Sunlight—Why Is It Hotter Than Mercury?",
        generate_preview_sheet=True,
    )
