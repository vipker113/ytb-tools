# Kairo Spark — Locked 2D Flash Stickman Visual, Subtitle, Verification & Publishing Rulebook (Permanent Standard)

## 1. Locked Mascot & 2D Flash Visual DNA ("Sticky-Note Exec")
When generating or rendering any visual asset, scene, pose, prop, or thumbnail for the **Kairo Spark** stickman explainer channel, you MUST strictly follow the locked **2D Adobe Flash / Adobe Animate (Non-AI)** visual standard:

- **Locked Reference Files in Repo:**
  - Scene Benchmark (2x2 2D Flash Frames): `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack/reference_flash_scenes_locked.jpg`
  - Poses & Props Benchmark: `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack/reference_flash_poses_props_locked.jpg`
  - Extracted Transparent RGBA Sprites (12 core PNGs): `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/flash-pack/`
  - PyCairo Vector Hand-Drawn Pack: `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/handdrawn-pack/`

- **STRICT ANTI-AI VISUAL RULES (NEVER VIOLATE):**
  1. **NO warm sepia / yellow / vintage cream AI filter:** Heads and whiteboard cards MUST be pure crisp `#FFFFFF` white. Room walls, floors, and skies use flat 2D Flash bucket-fill colors (`#F6E2C6` beige wall, `#C49E72` wood floor planks, `#FDD5B1` peach sky, `#C29A6C` desert ground).
  2. **NO boxy white-shirt torso block:** Every stickman's torso MUST be a **SINGLE black ink stick line (`|`)** with single-line black stick arms and single-line black stick legs (`8–10px` uniform black marker stroke at 1080p), identical in construction to *Ink Explainer*.
  3. **ONLY two signature accessories on the pure stick figure (`Sticky-Note Exec`):**
     - A flat red necktie (`#E4442E`) hanging directly from the neck over the single black stick spine.
     - A small yellow sticky note (`#FFE600`) with a black ink symbol (`?`, `!`, `?!`, `zzz`, `X`) stuck on the forehead of the pure white round circle head.
  4. **NO 3D gradients, NO comic cross-hatching, NO photorealistic shading, NO internal character nickname labels (never write `"STICKY NOTE EXEC"` as text inside a scene).**
  5. **STRICT ZERO-HUD / ZERO-PIL-SLOP RULE:**
     - **NEVER** draw top-left Chapter HUD bars (`ACT I - ...`) or top-right Progress timers (`00:19`).
     - **NEVER** paste programmatic PIL rectangular text boxes (`make_stamp_card`, `make_split_card`), programmatic top-pill UI badges (`+badge:`), programmatic PIL comic speech bubbles (`+bubble`, `+bubble_right`), or programmatic PIL red `✕` / green `✓` stamps on top of artwork. All speech bubbles, signs, checkmarks, red X marks, and in-scene callouts MUST be drawn natively inside the 2D Adobe Flash artwork itself!
     - **ALWAYS** render sharp HD artwork (`1376×768` single full-bleed frames or `Real-ESRGAN x4v3` `dn=0.5` neural 4× upscaled → Lanczos `1920×1080`) so black ink lines are razor-sharp with zero upscaling blur.
     - **ALWAYS** burn in **`pow_studio` `cinema_boxless` subtitles** at `y = 918` (crisp white text + `5px` dark stroke + localized Gaussian optical shadow + warm gold `#FFDE76` keyword emphasis, with ZERO rectangular background box) AND export a companion `.srt` file.

---

## 2. The 16 Visual Storytelling, Quality Gate & Publishing Rules

### Rule 1: Ultra-Fast Clause-Level Cut Cadence (`1.0s – 2.5s` per cut, Max `3.5s`, `0.000` Camera Zoom/Pan)
- **NEVER** keep a single static frame on screen for a whole 8–12 second sentence, and **NEVER** fake motion by zooming or panning around a single image.
- Cut on **every spoken clause or comma (`,`)** at an average pace of **`1.5s – 2.3s` per frame** (`100%` locked static camera, hard cuts only).

### Rule 2: Authentic Multi-State Micro-Acting on the Same Background (`State A → State B → State C`)
- When a sentence splits into 2–3 clauses on the same setting, create genuine visual state changes (`State A → State B`) using:
  1. **Pose / Action Toggle (`State A → State B`):** Generate consecutive states in the 2x2 grid where the room stays identical and the character changes pose/expression (e.g., sipping coffee → putting mug down nervously → clutching chest; sleeping by `"CLOSED MONDAY"` loom → weaving furiously under `"TUESDAY"` sign).
  2. **Progressive Column Reveal (`+reveal_left` / `+reveal_col1` → `+reveal_col2` → Full Scene):** On 2-column or 3-column drawn comparison illustrations, reveal the left column on Clause 1 (masking the right column cleanly with the canvas background color), then pop in the right column on Clause 2.
  3. **In-World Comic Speech Bubble Pop-In (`+bubble:x,y,text`):** Frame A shows the clean drawing; Frame B pops in a white rounded comic speech bubble with a pointer tail aimed at the speaker's mouth.
  4. **Prop Red `✕` / Green `✓` Slam (`+x_on:cx,cy,r` / `+check_on:cx,cy`):** Frame A shows the clean prop (laptop spreadsheet, pocket watch, signpost); Frame B slams a bold red `✕` or green `✓` directly onto the prop.

### Rule 3: Multi-Camera Cinematic Coverage Within One Story Event (`Wide → Tight Static Close-Up`)
- Cover story events with distinct camera framings across consecutive clauses:
  - **Wide Establishing Shot** → **Medium Character Interaction** → **Instant Static Close-Up Cut (`+closeup:cx,cy,zoom`, `0.000` camera motion)** → **Macro Prop Close-Up** (e.g., open parchment scrolls, pocket watch in hand, 12-number wall clock).

### Rule 4: Synchronized Negative List Cuts (`1 Listed Item = 1 Visual Cut`)
- Whenever the script lists 3+ items (*"with no tractors, no electricity, and no labor laws"* or *"more clothes, more variety of food, more transportation"*), **cut to a new drawn illustration on every single listed item (`1.0s – 1.5s` each)**.

### Rule 5: The 1-Second White-Background Host Reaction Intercut
- At rhetorical turning points (*"and yet,"*, *"There is just one problem with it."*, *"Wait, stop right there."*, *"There was just one catch."*, *"Read that again."*), cut for **`0.8s – 1.6s`** to a **100% pure `#FFFFFF` white background with ONLY the host stickman (`Sticky-Note Exec`)** scaled to ~75% frame height (`y = 65..840`) doing a deadpan reaction pose — **with ZERO text on screen**.

### Rule 6: Visual Metaphor Illustrations (`Literal Object → Drawn Metaphor`)
- When the narrator uses a metaphor (*"human bodies that behaved like gears"*, *"forced into a 6-day cage"*, *"work expands like gas to fill 40 hours"*), draw the literal visual metaphor with stickman characters (workers walking inside giant interlocking steel gears; workers trapped inside a `"72 HRS"` iron birdcage; a `"5H WORK"` pink balloon inflating to fill a `"40H"` glass box).

### Rule 7: Drawn Split Comparisons (`A | B`) — Always With Characters & Props
- Every `A | B` comparison MUST feature **drawn stickman characters and props on both sides** (e.g., happy peasant on a balance scale with a green `"150"` weight vs crushed office worker under a `"260"` iron weight; `$0` wooden handloom vs brick furnace burning dollar bills; peasant resting under a tree `✕` vs Sticky-Note Exec pushing a shopping cart `✓`).

### Rule 8: Visualized Numbers, Dates & Equations (NEVER Plain Text Boxes)
- Whenever the script announces a key date, study, vote, or math paradox (`24 HOURS / DAY`, `1991 • HARVARD`, `1967 • E. P. THOMPSON`, `FATAL MATH PROBLEM`, `53 TO 30`), **draw a 2D Flash scene where characters interact with the number/object**:
  - `24 HOURS / 7 DAYS` → Planet Earth rotating between a `24H` Sun and `7D` Moon.
  - `1991 • HARVARD` → Red brick `"HARVARD 1991"` building with economist holding a green `"150"` chart.
  - `FATAL MATH PROBLEM` → Automaker pointing at a green chalkboard equation `[Car Icon] + [Crossed-Out Clock] = $0` and an `"UNSOLD"` Model T parking lot.
  - `53 TO 30` → U.S. Senate chamber scoreboard showing green `"YES 53"` vs red `"NO 30"` above cheering senators.

### Rule 9: Geographic Map Traces & Multi-Step Cycle Diagrams
- For geographic spread (*"Across England, France, and early America"*), show a flat 2D vector map with highlighted red regions and dotted arrows (`- - - ->`).
- For multi-step loops (*"One day for rest on Sunday, one day to spend on Saturday, five days to earn it back"*), show a 3-panel visual comic strip (`1. SUN` church → `2. SAT` shopping cart → `3. MON-FRI` office desk) revealed column-by-column.

### Rule 10: Era Costumes & Props
- Keep stickman anatomy consistent (`|`) across all historical eras while differentiating roles via clean 2D props/hats (gold crown for feudal lord, straw hat / pitchfork for peasant, tall black top hat for 1800s factory boss, bowler hat + binoculars for Ford spy, glasses + pointer stick for 1955 professor).

### Rule 11: Instant-Readability Standard for Clocks (`12 Numbers Mandatory`, `< 0.5s` Glance Test)
- **NEVER** draw an analog clock with only 4 numbers (`12, 3, 6, 9`).
- Every clock frame MUST display **all 12 numbers (`1` through `12`) + 12 hour tick marks**, highlight the active spoken hour (`7`, `8`, `5`) with a yellow/red ring, point the red hour hand directly at that hour, AND show a clear digital time badge (`7:00 PM`, `8:00 PM`, `5:01 PM`) beside the clock.

### Rule 12: Bottom Subtitle Safe-Zone (`y <= 850` for Artwork; `y = 918` for `pow_studio` `cinema_boxless` Subtitles)
- Every frame in the video MUST have **`pow_studio` `cinema_boxless` subtitles** burned in at `y = 918` (`BeVietnamPro-Bold`, `52px`, crisp white `(252, 253, 255)` with `5px` dark stroke `(6, 10, 16)`, localized Gaussian blur `radius=12` shadow, and warm gold `(255, 222, 118)` keyword emphasis).
- All clock rims, chart labels, and important visual details MUST stay at **`y <= 850`** (`130px+` clear margin above the bottom edge) so they never collide with the subtitle.

### Rule 13: Mandatory Pre-Video Visual Verification Gate
- **NEVER** run final FFmpeg video encoding before generating Act-by-Act verification contact sheets (`verify_act1_frames_sheet.jpg` .. `verify_act5_frames_sheet.jpg`) and inspecting every single sheet with `read_file`.
- Any spelling typo in an AI-drawn header, clipped progressive reveal (`reveal_left`), hollow double-line stickman torso, 4-number clock, or subtitle overlap discovered on the contact sheets MUST be fixed and re-verified before encoding the MP4.

### Rule 14: Strict Ban on Programmatic Text-Box Cards ("AI Slop" Boards), Top-Pill Badges & Scene Repetition
- **ZERO Programmatic Text-Box Cards (`make_stamp_card` / `make_split_card`):** Plain rectangular PIL text cards are strictly forbidden.
- **ZERO Programmatic Top-Pill Badges (`+badge:`):** Slapping a rounded yellow/red/green pill box at the top of an existing image is strictly forbidden.
- **High Visual Density (120–140+ Unique Painted 2D Flash Panels per 9-Minute Episode):** Generate enough 2x2 grids (via parallel `image-generator` subagents) so that almost every sentence segment in the episode has its own dedicated painted 2D Flash illustration, and no static painting is recycled across multiple paragraphs.

### Rule 15: High-CTR 2D Flash YouTube Thumbnail Standard
- **Composition:** Single full-bleed 16:9 2D Adobe Flash illustration with Sticky-Note Exec on the left reacting in shock (`?!` on yellow forehead sticky note) and pointing at the core visual metaphor on the right (e.g., red `MON–FRI` calendar prison cage wrapped in iron chains with a ringing alarm clock). Keep bottom-right (`x > 1600, y > 900`) clear of text for the YouTube timestamp.
- **Typography (Locked Variant 1 Standard):** State the full curiosity question clearly in chunky 3D cartoon block lettering (`Arial Black` with thick black outline and 3D offset drop shadow):
  - Line 1 (Crisp White `#FFFFFF`): e.g., **`WHY DO WE HAVE TO WORK`**
  - Line 2 (Multi-Color Impact — Bright Yellow `#FFE819` + Warm Red-Orange `#FF5C48`): e.g., **`5 DAYS`** (Yellow) + **`A WEEK?!`** (Red-Orange).

### Rule 16: Short *Ink Explainer*-Style YouTube Metadata & Stickman-Focused Tags Standard
- **Category:** `People & Blogs` (matches all reference *Ink Explainer* hit videos).
- **Description Format (Keep Short & Clean):**
  1. Line 1: Repeat the core hook question (`Why Do We Work 5 Days a Week?`).
  2. Paragraph 1: 2 short sentences summarizing the counter-intuitive twist.
  3. `Time stamps👇🏾` with 6–7 concise chapter markers (`0:00 - ...`).
  4. Credit line: `🎨 Animation by Kairo Spark`
  5. Stickman-focused hashtags: `#stickman #stickmananimation #stickmanexplainer #animation #explainer #history`
- **Tags (Short & Laser-Focused on the Stickman Explainer Niche):**
  - `stickman, stickman explainer, stickman animation, stickman history, paint explainer, 2d stickman, <topic question>`

---

## 3. Sound Effects (MyInstants Editorial Foley Standard & Auto-Download Rule)
- **Master SFX Library (44+ Core MP3s + JSON Index):** `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/sfx/` and `/Applications/code/science-knowledge/ytb-tools/public/kairo-stickman/sfx/sfx_catalog.json`.
- **Audio Mixing Standard:** Mix short punctuation SFX at `-14 dB` below voiceover and continuous ambience SFX at `-22 dB` to `-26 dB` with `0.3s` fade-in/out, mastering final output to `-14.0 LUFS`.
