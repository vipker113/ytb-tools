#!/usr/bin/env python3
"""
Generate exact word-boundary subtitles.srt directly from word_timings.json
for Proof of Wonder #02 (Mars Ingenuity Helicopter in 1% Air).

Every cue:
- Matches the spoken narration word-for-word.
- Starts at t >= 0.100s so Frame 0 (t = 0.000s) has zero bottom subtitle bar (clean unified thumbnail).
- Uses exact start/end timestamps from Edge TTS WordBoundary events.
- Never crosses any of the 10 shot cut boundaries.
"""

import json

OUT_DIR = "/Applications/code/science-knowledge/youtube-shorts-channel/output/proof-of-wonder/02-mars-helicopter-1-percent-air"
WT_PATH = f"{OUT_DIR}/word_timings.json"
SRT_PATH = f"{OUT_DIR}/subtitles.srt"

SHOT_CUTS = [0.000, 6.133, 11.100, 15.000, 17.133, 20.633, 24.900, 31.067, 37.067, 38.967, 44.200]

# Exact word-index groupings [w_start, w_end_inclusive, display_text_with_punctuation, shot_idx]
CUE_GROUPS = [
    # Shot 01: [0.000 -> 6.133s]
    (0, 7, "How did NASA fly a helicopter on Mars", 0),
    (8, 14, "in air ninety-nine percent thinner than Earth's?", 0),
    # Shot 02: [6.133 -> 11.100s]
    (15, 17, "In twenty twenty-one,", 1),
    (18, 24, "Ingenuity lifted off from red Martian dust.", 1),
    # Shot 03: [11.100 -> 15.000s]
    (25, 30, "Mars's air is just one percent", 2),
    (31, 34, "as dense as Earth's,", 2),
    # Shot 04: [15.000 -> 17.133s]
    (35, 39, "like hovering thirty kilometers up.", 3),
    # Shot 05: [17.133 -> 20.633s]
    (40, 42, "Engineers tested it", 4),
    (43, 48, "in a giant Mars vacuum chamber.", 4),
    # Shot 06: [20.633 -> 24.900s]
    (49, 51, "They trimmed Ingenuity", 5),
    (52, 56, "to one point eight kilograms,", 5),
    # Shot 07: [24.900 -> 31.067s]
    (57, 63, "spinning carbon-fiber rotors past twenty-five hundred RPM,", 6),
    (64, 69, "five times faster than Earth helicopters.", 6),
    # Shot 08: [31.067 -> 37.067s]
    (70, 74, "Any faster, and blade tips", 7),
    (75, 79, "hit Mach zero point seven,", 7),
    (80, 83, "where shockwaves kill lift.", 7),
    # Shot 09: [37.067 -> 38.967s]
    (84, 87, "Built for five flights,", 8),
    # Shot 10: [38.967 -> 44.200s]
    (88, 91, "Ingenuity flew seventy-two times", 9),
    (92, 94, "across another world.", 9),
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
    assert len(wt) == 95, f"Expected 95 word events, got {len(wt)}"

    lines = []
    for idx, (i0, i1, display, s_idx) in enumerate(CUE_GROUPS, start=1):
        raw_words = [wt[k]["text"] for k in range(i0, i1 + 1)]
        clean_disp = display.replace(",", "").replace(".", "").replace("?", "")
        assert " ".join(raw_words) == clean_disp, f"Mismatch at cue {idx}: {raw_words} vs {clean_disp}"

        t0 = float(wt[i0]["start"])
        t1 = float(wt[i1]["end"]) + 0.08
        if idx < len(CUE_GROUPS):
            next_t0 = float(wt[CUE_GROUPS[idx][0]]["start"])
            t1 = min(t1, next_t0 - 0.02)

        shot_start = SHOT_CUTS[s_idx]
        shot_end = SHOT_CUTS[s_idx + 1]
        t1 = min(t1, shot_end - 0.04)
        assert t0 >= shot_start + 0.02 and t1 <= shot_end - 0.03, (
            f"Cue {idx} [{t0:.3f}..{t1:.3f}] crosses shot {s_idx+1} [{shot_start:.3f}..{shot_end:.3f}]"
        )

        lines.append(f"{idx}")
        lines.append(f"{fmt_srt_time(t0)} --> {fmt_srt_time(t1)}")
        lines.append(display)
        lines.append("")

    assert float(wt[0]["start"]) >= 0.08, "Cue 1 must start after t=0.000s so Frame 0 thumbnail has no bottom caption!"

    with open(SRT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {len(CUE_GROUPS)} verified cues to {SRT_PATH}")


if __name__ == "__main__":
    main()
