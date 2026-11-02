#!/usr/bin/env python3
"""
Generate exact word-boundary subtitles.srt directly from word_timings.json
for the Proof of Wonder Venus pilot.

Every cue:
- Matches the spoken narration word-for-word.
- Uses exact start/end timestamps from Edge TTS WordBoundary events.
- Never crosses a shot cut boundary.
- Keeps each cue concise (4–8 words) so captions wrap cleanly on 1–2 lines at font_size=48.
"""

import json
import os

OUT_DIR = "/Applications/code/science-knowledge/youtube-shorts-channel/output/proof-of-wonder/01-venus-hotter-than-mercury"
WT_PATH = f"{OUT_DIR}/word_timings.json"
SRT_PATH = f"{OUT_DIR}/subtitles.srt"

# Exact word-index groupings [w_start, w_end_inclusive, display_text_with_punctuation]
# Verified word-for-word against script.md and narration.mp3!
CUE_GROUPS = [
    # Shot 01: [0.000 -> 4.067s]
    (0, 5, "Why is Venus hotter than Mercury,"),
    (6, 12, "even though it's farther from the Sun?"),
    # Shot 02: [4.067 -> 7.633s]
    (13, 18, "Closer Mercury hits four hundred thirty"),
    (19, 22, "degrees Celsius by day,"),
    # Shot 03: [7.633 -> 9.900s]
    (23, 27, "but with almost no atmosphere,"),
    # Shot 04: [9.900 -> 15.367s]
    (28, 34, "that heat escapes into space at night,"),
    (35, 41, "plunging to minus one hundred eighty degrees."),
    # Shot 05: [15.367 -> 17.300s]
    (42, 48, "Venus looks like it should be cooler,"),
    # Shot 06: [17.300 -> 23.067s]
    (49, 55, "because thick pale clouds of sulfuric acid"),
    (56, 61, "reflect about seventy-five percent of sunlight."),
    # Shot 07: [23.067 -> 26.833s]
    (62, 66, "Yet the sunlight that gets"),
    (67, 71, "through warms the rocky surface,"),
    # Shot 08: [26.833 -> 34.167s]
    (72, 77, "and its dense carbon dioxide atmosphere,"),
    (78, 82, "ninety-six point five percent pure,"),
    (83, 86, "blocks outgoing infrared heat."),
    # Shot 09: [34.167 -> 36.700s]
    (87, 91, "While Mercury cools every night,"),
    # Shot 10: [36.700 -> 42.900s]
    (92, 95, "Venus stays locked near"),
    (96, 100, "four hundred sixty-four degrees Celsius,"),
    (101, 103, "day and night."),
]


def fmt_srt_time(sec: float) -> str:
    ms_total = int(round(sec * 1000))
    h = ms_total // 3600000
    rem = ms_total % 3600000
    m = rem // 60000
    rem %= 60000
    s = rem // 1000
    ms = rem % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main() -> None:
    wt = json.load(open(WT_PATH))
    assert len(wt) == 104, f"Expected 104 word events, got {len(wt)}"

    lines = []
    for idx, (i0, i1, display) in enumerate(CUE_GROUPS, start=1):
        # Verify word-for-word match (ignoring punctuation)
        raw_words = [wt[k].get("text", wt[k].get("word", "")) for k in range(i0, i1 + 1)]
        clean_disp = display.replace(",", "").replace(".", "").replace("?", "")
        assert " ".join(raw_words) == clean_disp, f"Mismatch at cue {idx}: {raw_words} vs {clean_disp}"

        t0 = float(wt[i0]["start"])
        t1 = float(wt[i1]["end"]) + 0.08  # tiny 80ms readable tail hold without overlapping next word
        if idx < len(CUE_GROUPS):
            next_t0 = float(wt[CUE_GROUPS[idx][0]]["start"])
            t1 = min(t1, next_t0 - 0.02)

        lines.append(f"{idx}")
        lines.append(f"{fmt_srt_time(t0)} --> {fmt_srt_time(t1)}")
        lines.append(display)
        lines.append("")

    with open(SRT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(CUE_GROUPS)} verbatim cues to {SRT_PATH}")


if __name__ == "__main__":
    main()
