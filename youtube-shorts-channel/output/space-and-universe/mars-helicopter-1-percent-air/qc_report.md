# Quality-Control Report — Mars Shorts V2 (`mars-v2`)

- **Revised Video:** `/Applications/code/science-knowledge/youtube-shorts-channel/output/revisions/mars-v2/02-mars-has-almost-no-air-how-did-this-helicopter-fly.mp4`
- **Preserved Originals (Untouched for A/B Comparison):**
  - `output/batch-1/02-mars-has-almost-no-air-how-did-this-helicopter-fly.mp4` (`72.82 MB`, `44.700s`, SHA-256 prefix `c858942bcff0bb46`)
  - `output/proof-of-wonder/02-mars-helicopter-1-percent-air/02-mars-has-almost-no-air-how-did-this-helicopter-fly.mp4` (`119.84 MB`, `44.200s`, SHA-256 prefix `983bd959de9f673a`)
- **Total Spend / Paid APIs:** `$0.00` (`0` billable calls; `0` YouTube uploads)

---

## 1. Forensic Audit of the Original Video (`output/batch-1/02-*.mp4`)

1. **Exact Original Narration & Voice Settings:**
   - `104` words in `4` long sentences (`en-US-AndrewMultilingualNeural`, `rate = 1.0`, `44.23s` audio / `44.70s` MP4), including a breathless **44-word run-on sentence** (`19.65s–37.43s`) packing Earth density-altitude, mass, blade span, coaxial rotor physics, RPM, and Earth helicopter comparison into a single uninterrupted breath.
   - Delayed the opening question until `4.55s–7.91s` instead of establishing it immediately at `0–2s`.
2. **Frame-Level Visual & Subtitle Defects Verified on Actual Media:**
   - **`Shot 01` (`0.00–4.26s`):** Bottom subtitle box (`y = 82%`) directly covered tiny *Ingenuity* sitting on Martian soil (`t = 0.25s–1.77s`).
   - **`Shot 02` (`4.26–8.52s`, `nasa_ingenuity_third_flight_mastcam.mp4` `start_sec=24.00`):** *Ingenuity* flew out of the right edge at `24.8s`, leaving an **empty Martian hillside with zero helicopter** (`4.81s–7.85s`) during *"so how did NASA's Ingenuity helicopter ever leave the ground?"*
   - **`Shot 03` (`8.52–14.23s`) & `Shot 06` (`24.47–30.08s`):** Static geometric diagrams held nearly unchanged for `5.71s` and `5.61s` (`11.32s` total).
   - **`Shots 04 & 05` (`14.23–24.47s`):** `10.24s` of back-to-back **unlabeled indoor JPL vacuum chamber clips** (`nasa_ingenuity_overview_chamber.mp4`) played without Earth-test labeling during *"flying near Mars's surface feels like flying thirty kilometers above Earth"*.
   - **`Shots 07–08` (`30.08–37.80s`):** Heuristic `base_durations` caused narration-to-shot drift (`"each one point two meters wide"` over a distant speck; `"above twenty-four hundred revolutions per minute"` over a black-and-white ground shadow).
   - **`Shot 10` (`40.90–44.70s`, `nasa_ingenuity_media_reel_1080.mp4` `start_sec=313.00`):** Extracted Flight 47 **before *Ingenuity* entered the frame**, ending the entire Short (`"Ingenuity flew seventy-two times across another world"`) on a motionless, empty dirt hillside.
   - **Original Thumbnail (`02_concept_B_midair_hover.jpg`):** Used `PIA24466`, a stereo 3D-anaglyph composite with an unnatural pink-purple color cast.

*(Note: Compared with the intermediate `proof-of-wonder/02-mars-helicopter-1-percent-air/` revision, `mars-v2` further upgrades the script to natural spoken phrasing using exact `"atmospheric density"` / `"one percent as dense as Earth's"` rather than `"99% thinner"`, treats `< Mach 0.7` accurately as a subsonic blade-tip engineering margin rather than a dramatic universal cliff, adds selective keyword highlighting, explicitly badges JPL flight visuals and the Pasadena vacuum chamber, incorporates real color `Mastcam-Z` Mars dune flight footage (`shot_09`) + `4K`-class `PIA24548` rover-belly photography (`shot_10`), and delivers the complete concluding thought.)*

---

## 2. TTS Voice & Speech-Rate Audition Summary

All samples were generated for free via `edge-tts` (`boundary="WordBoundary"`) and ear-audited directly (`voice_audition/`):

| Sample File | Voice | Rate | Duration | Ear-Audit Result |
| :--- | :--- | :---: | :---: | :--- |
| `open_ava_0pct.mp3` / `v2_ava_0pct.mp3` | `en-US-AvaMultilingualNeural` | `+0%` | `40.968s` | Clean final consonants, but inserted unnatural micro-pauses inside short phrases (`"Mars has barely ... any air"`, `"seventy ... two"`). |
| `v2_andrew_minus2pct.mp3` | `en-US-AndrewMultilingualNeural` | `-2%` | `42.936s` | Warm tone, slightly slower cadence with minor breathiness on `"flights"`. |
| **`v2_andrew_0pct.mp3` (`narration.mp3`)** | **`en-US-AndrewMultilingualNeural`** | **`+0%`** | **`42.384s`** | **Selected Winner:** Warm, natural documentary baritone, crisp articulation of `"Mars's atmosphere is only about one percent as dense as Earth's"`, natural `~400 ms` pauses between sentences, zero rate-warping artifacts. |
| `v2_andrew_plus2pct.mp3` | `en-US-AndrewMultilingualNeural` | `+2%` | `41.736s` | Intelligible, slightly brisker on `"2,500 revolutions per minute"`. |

---

## 3. FFprobe, Audio & Frame-Level Technical Validation

- **Container / Video Stream (`ffprobe_validation.json`):** `MP4` (`+faststart`), `H.264` (`libx264`, `-crf 14`), `1080 × 1920` (`9:16`), exact `30/1 fps`, `1,287` frames = **`42.900000s`**, `yuv420p`, `118.82 MB`.
- **Audio Stream:** `AAC`, `44,100 Hz`, mono, `42.900000s` (`42.384s` narration + `0.516s` clean tail pad), `mean_volume = -21.7 dB`, `max_volume = -3.5 dB` (`0` clipped samples, `0` clicks, BGM disabled, all B-roll source audio stripped via `-an`).
- **Black-Frame Scan (`blackdetect=d=0.05:pix_th=0.10`):** **`0` black frames or dark transition flashes** across all `1,287` frames.
- **Caption Synchronization & Safe Zones:** `15` verbatim cues generated from `word_timings.json` (`Cue 1` starts at `0.100s` so `Frame 0` has zero bottom caption bar; `0` cues straddle any of the `11` shot boundaries; selective gold keyword emphasis centered at `y = 1605` with zero overlap onto the helicopter, rotors, or diagrams).
- **Unified Frame-0 Thumbnail:** `02-mars-has-almost-no-air-how-did-this-helicopter-fly.jpg` (`515.8 KB`, `< 2 MB`, `4:4:4` `subsampling=0`), `.png` (`1,670.0 KB` lossless `24-bit` RGB), and `thumbnail.jpg` — identical to `Frame 0` (`t = 0.000s`) of the MP4 (`MARS HAS BARELY ANY AIR / HOW DID THIS FLY?`).

---

## 4. Scientific Fact Verification

| Claim in Script / On-Screen | Verified Primary Source | Status |
| :--- | :--- | :---: |
| Mars's atmosphere is `~1%` as dense as Earth's near the surface (`~0.020 kg/m³` vs `~1.217 kg/m³`) | NASA Mars Fact Sheet (GSFC) & NASA *Ingenuity* Mission Overview | Verified |
| *Ingenuity* weighed `1.8 kilograms` on Earth | NASA Science *Ingenuity* Fact Sheet (`1.8 kg` / `4.0 lbs`) | Verified |
| Two counter-rotating `1.2 m` carbon-fiber rotors spinning at `~2,500 RPM` (`~2,400–2,537 RPM`, `~5×` typical Earth helicopter main rotor) | NASA Science & Balaram et al. (`NTRS 20180003088`) | Verified |
| Subsonic blade-tip speed margin `< Mach 0.7` (`shot_06` callout) | Balaram et al. (`NTRS 20180003088`) & Grip et al. (`NTRS 20200002705`) | Verified (framed as engineering margin, not universal speed limit) |
| Planned `5` technology-demonstration test flights vs `72` completed Mars flights | NASA Science *Ingenuity* Mission Overview (final flight Jan 18, 2024) | Verified |

---

## 5. Verified Objective Improvements vs. Subjective / Source-Limited Notes

### Verified Objective Improvements
1. **Immediate `0.00s` Visual + Verbal Question Alignment:** Opening hook (`"Mars has barely any air. So how did NASA fly a helicopter there?"` + Frame-0 card `MARS HAS BARELY ANY AIR / HOW DID THIS FLY?`) begins at `t = 0.000s` (`0.088s` speech onset) over an airborne close-up of *Ingenuity*, replacing `batch-1`'s `4.55s` delayed question and subtitle-occluded ground speck.
2. **Conversational Sentence Pacing:** Replaced `batch-1`'s `104`-word / `4`-sentence script (and `44`-word run-on sentence) with `86` natural spoken words across `8` varied sentences (`5` to `21` words each) separated by clean `~400 ms` breaths.
3. **Zero Empty Frames, Zero Unlabeled Earth Chambers, Zero Static Holds:** Eliminated `batch-1`'s empty hillsides (`Shots 02 & 10`), static `11.3s` geometric diagrams (`Shots 03 & 06`), and `10.2s` of unlabeled indoor chamber clips (`Shots 04 & 05`). `shot_03` (`3.10s`) explicitly labels `EARTH TEST • JPL VACUUM CHAMBER`, `shot_06` (`3.60s`) animates continuously at `30 fps`, and `6` distinct shots (`shot_04, 07, 08, 09, 10, 11`) show genuine Mars camera imagery (`Mastcam-Z`, `Navcam`, `WATSON`, `RTE`).
4. **High-Impact 2-Shot Documentary Conclusion (`33.20–42.90s`):** Pairs `4K`-class `PIA24548` (`WATSON` view of tiny *Ingenuity* slung beneath *Perseverance*'s belly on Mars, Sol 35) with native `4K` `PIA26242` (*Ingenuity*'s own Flight 70 color aerial view above Martian sand ripples).

### Subjective or Source-Limited Trade-Offs
1. **Inherent Telephoto Softness in Real Mars Flight Video (`shot_07` & `shot_09`):** Because *Perseverance*'s `Mastcam-Z` filmed *Ingenuity* from `65–150+ meters` away across dusty Martian air at `~6.7 fps` hardware cadence, the `9:16` zoomed crops in `shot_07` (`1:1 grad = 2.52`) and `shot_09` (`1:1 grad = 1.50`) are naturally softer at `1:1` pixel magnification than the `4K` rover/helicopter still photographs (`shot_10 grad = 7.81`, `shot_11 grad = 13.32`). Keeping genuine Mars flight footage there was prioritized over substituting synthetic CGI.
2. **Opening Shot Editorial Choice (`shot_01`):** `shot_01` (`0.00–4.00s`) uses NASA/JPL's official close-up flight visualization (`JPL-20200429-TECHf-0002`, explicitly badged `Official JPL Flight Visual`) so *Ingenuity* is large and unmistakable in `160×284 px` mobile thumbnails before transitioning to `6` genuine Mars camera captures. Preferring raw (more distant) `Mastcam-Z` video at `0.00s` instead of the labeled JPL close-up is a valid subjective editorial alternative.
3. **Free Neural TTS Prosody:** `en-US-AndrewMultilingualNeural` (`+0%`) is the most natural zero-cost voice tested, though subtle differences vs. a live human documentary narrator remain inherently subjective.
