# QC Report — Proof of Wonder #03: How High Could You Jump on Other Planets?

- **Video:** `03-how-high-could-you-jump-on-other-planets.mp4` — H.264 `1080×1920`, `30/1 fps`, `1,140` frames = `38.000 s`; AAC `44.1 kHz` mono; `34.2 MB`.
- **Audio levels:** mean `-21.5 dB`, max `-3.4 dB` (no clipping). BGM disabled; all source audio stripped (`-an`).
- **Black-frame scan** (`blackdetect d=0.05 pix_th=0.10`): `0` black segments.
- **Thumbnail:** Frame 0 exported as `03-how-high-could-you-jump-on-other-planets.jpg` (`310 KB`, `4:4:4`), `.png` (lossless), and `thumbnail.jpg`. Identical to the first frame of the video.
- **Cost:** `$0` (free edge-tts, free NASA / CC BY assets, local rendering). Nothing uploaded.

## Voice selection
| Sample | Span | Rate | Objective notes |
| :--- | :---: | :---: | :--- |
| `andrew_0pct` | `35.16 s` | `2.59 words/s` | All pauses at punctuation; a little fast for a script with many numbers. |
| **`andrew_minus3pct` (selected)** | `36.48 s` | `2.49 words/s` | All pauses at punctuation (~0.4 s between sentences); more room for each number. |
| `ava_0pct` | `36.79 s` | `2.47 words/s` | Unnatural `312 ms` gap inside "Gravity … decides". |

> Unresolved: this session could not play audio, so the voice was chosen from objective timing data only (no listening check). Andrew is the channel's previously approved voice, but someone still needs to listen to `narration.mp3` before publishing.

## Sync and captions
- Every cut falls inside a natural pause in the narration (`11` shots; shortest `2.00 s`, longest `5.63 s`).
- `17` captions taken word-for-word from `word_timings.json`. No caption crosses a cut. Frame 0 has no caption. Captions are centred at `y = 1605`, below every figure, ruler and planet label.

## Science check
| On-screen / spoken value | Calculation | Source |
| :--- | :--- | :--- |
| Earth 0.50 m (premise) | v0 = 3.13 m/s | Stated as an assumption ("Say you manage…"); untrained adults typically jump 0.30–0.45 m |
| Mars 1.33 m / Mercury 1.32 m | 0.50 ÷ 0.377 / 0.378 | NASA GSFC ratio fact sheet |
| Moon 3.01 m, airtime 3.85 s | 0.50 ÷ 0.166; 2v0/g | NASA GSFC |
| Jupiter 0.21 m (cloud level) | 0.50 ÷ 2.36 | NASA GSFC (1-bar level) |
| Saturn 0.55 m; mass 95× Earth | 0.50 ÷ 0.916 | NASA GSFC; NASA Saturn facts |
| Pluto 7.90 m, airtime 10.1 s | g = 0.62 m/s² | NASA GSFC Pluto fact sheet |

## Honesty safeguards
- Every jumping figure is a labelled explanatory animation that follows the exact parabola for that world. All motion is real-time except Pluto, which carries a `2× SPEED` badge.
- Jupiter and Saturn are shown with an explicitly labelled **hypothetical platform**, because neither has a solid surface.
- The Moon scene notes "no spacesuit". Real Apollo jumps in suits were much lower, so no Apollo footage was used to illustrate the 3 m figure.

## Subjective / open items
1. At `160×284 px`, the thumbnail's seven figures are small. The hook text carries the message; a bolder alternative would be a two-world close-up (Earth vs Pluto).
2. Planet surfaces are stylised horizons, with exaggerated curvature and black space instead of each world's real sky colour. Pluto's map is built from one NASA hemisphere photo, so it is softer than the other surfaces.
3. **Required for publishing:** the video description must credit Solar System Scope (CC BY 4.0).
