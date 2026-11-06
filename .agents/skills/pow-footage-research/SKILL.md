---
name: pow-footage-research
description: Finds, licenses, downloads and verifies real commercial-safe documentary footage for a Proof of Wonder episode, then runs the visual feasibility gate. Use when searching for footage/B-roll/clips, checking licenses, adding assets_register entries, using the visual corpus, or when the feasibility gate fails.
---

# Footage Research & Feasibility (Studio v9)

Goal: every narrated physical event is shown by real moving footage (`REAL_VIDEO_ACTION` preferred),
with verifiable commercial-safe rights. Footage availability decides the story, not the reverse.

## Sources and license rules

| Source | License to record | Notes |
|---|---|---|
| NASA Images | `Public Domain (NASA)` | skip items credited "copyright", "used with permission" |
| Wikimedia Commons | exact `LicenseShortName` | only PD / CC0 / CC BY; check uploader credit (e.g. Ifremer CC BY 4.0) |
| Internet Archive | PD / CC0 / CC BY from `licenseurl` | pick the real mp4 file, not the item folder |
| NASA SVS | `Public Domain (NASA SVS)` | strip audio (music is often licensed) |
| ESA/Webb, ESA/Hubble | `CC BY 4.0` + credit line | no logos, no endorsement, no identifiable people; note "cropped to 9:16" |
| NOAA Ocean Exploration | `Public Domain (NOAA)` | credit "NOAA Ocean Exploration"; OneStop direct links are 640x360 (`low_res_lead`) → use to locate dives, then find HD copies (Commons/Archive) or order HD from NCEI |
| NARA | `Public Domain (NARA)` | only if `NARA_API_KEY` set and `useRestriction=Unrestricted` |
| ESA main site, JAXA, Pexels/Pixabay, Library of Congress | **excluded** | BY-SA / non-commercial / not documentary evidence / LoC blocks scripted access (do not bypass) |

## Workflow

```bash
$PY $STUDIO footage-sources                       # which sources are on, and why
# 1) discover (persisted to <out>/planning/footage_discovery.{json,md}); -m derives beats + default --out
$PY $STUDIO discover-footage -t "<short topic>" -m $EP [-q "extra literal query"] [--sources nasa_images,wikimedia]
# 2) download chosen candidates with provenance sidecars (+ pixel motion audit, audio strip for SVS/ESA)
$PY $STUDIO download-footage --discovery <out>/planning/footage_discovery.json --select <ids> --dest assets/raw_footage/<dir>
# 3) index + retrieve by what the frames show   (Studio v9 M3 — CLIP B/32 on mps, 165 img/s)
$PY $STUDIO corpus-ingest --path assets/raw_footage
$PY $STUDIO corpus-search --text "ROV manipulator arm black smoker plume" -k 10 --genuine-only
$PY $STUDIO match-beats -m $EP                  # writes <out>/planning/beat_matches.{json,md} + beat_matches_strip.jpg
# 4) gate
$PY $STUDIO feasibility -m $EP --out-dir <out>/planning
```

Topics/queries: keep them SHORT (2–5 content words). Archive engines return nothing for long
planner phrases like "… aerial documentary footage". The tool already adds 2-word sub-phrases.
For `corpus-search --text`, always describe **visible frame content** (nouns, colors, actions), never
abstract narration prose (`clip-b32:hybrid-70-30` reaches `64.0%` Window R@5 / `90.5%` File R@5 on
concrete visual descriptions vs `28.8%` on abstract prose; see `docs/v9_corpus_eval.md`). Watch out
for expedition intro slates containing topic words — CLIP has OCR neurons that can score text slates
highly if you do not check the window start time (`src_in`).

`download-footage` prints ready-to-paste `assets_register` YAML. Its `source_media_class` comes from
pixels and may downgrade the metadata hint (action → establishing, video → animated still) — keep it.
Fill `depicted_subject/action/location` yourself after looking at the frames.

## Verify with your own eyes

Never trust titles. For each candidate you intend to use, look at the contact strip
(`beat_matches` strips or extract 3 frames with ffmpeg) and check: internal cuts, talking heads,
burned-in titles, watermarks, letterboxing, wrong location. Items flagged
`possible_mislabeled_asset` must be visually confirmed or dropped.

## assets_register entry (every file)

`local_file, title, creator_agency, source_page_url, direct_media_url, license, license_url,
required_attribution, media_type, source_media_class, depicted_subject, depicted_action,
depicted_location, intended_use` (the `.provenance.json` sidecar has these prefilled).

## When the feasibility gate fails

Options, in order: find better footage → change the narrated angle to what footage can prove →
frame it honestly as a rare-photo mystery (`allow_extended_still_for_essential_evidence`) → ask the
user before `--accept-limited`. Never use proxy locations without narration disclosing it
(`explicit_analog_comparison`).
