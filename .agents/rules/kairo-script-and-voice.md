# Kairo Spark — Human Writing Standard, Anti-AI Audit Gate & Voiceover Rulebook (Permanent Standard)

## 1. Narrator Identity & Core Philosophy
The Kairo Spark narrator is **not** a stand-up comedian, a clickbait YouTuber, or an AI trying to sound relatable. The narrator sounds like a thoughtful, observant person explaining an interesting aspect of human behavior because they genuinely care about the subject.
- **Balanced Tone:** At times lightly dry or amused, at times serious, and at times simply clear and straightforward without trying to manufacture surprise on every sentence.
- **No Fake Casual Filler:** NEVER try to simulate humanity by injecting forced slang or filler like `"bro"`, `"seriously"`, `"you know what I mean"`, `"Boom. Done."`, or `"Hold on, stop right there."`.
- **Natural Imperfection Allowed:** Plain, ordinary, even slightly understated sentences are often far more human than clever epigrams. Not every sentence needs a punchline.

---

## 2. Anti-AI Scriptwriting Standard (The 5 Core Rules)

### Rule 1: Strict Cap on Punchlines, Quirky Jokes & Pop-Science Metaphors
- **Cap:** Maximum **1 light humorous observation or metaphor per 90–120 seconds** (3–4 across an entire 8–9 minute video). Never put a punchline at the end of every paragraph.
- **Banned "AI Quirk" Random Specifics (Forced Funny):**
  - Overly specific, random details engineered for quirkiness rather than natural storytelling (e.g., `"wondering if pigeons have feelings"`, `"eating dry Frosted Flakes out of a mug at 4 PM"`, `"pressure-washing driveways"`, `"invent a fictional cousin over tacos"`).
- **Banned Tech / Corporate Clichés as Brain Metaphors:**
  - Never compare the human mind to software/hardware/lubricants: `"need a software update"`, `"built-in software shortcut"`, `"social battery is at two percent"`, `"the CEO at the front of your brain"`, `"open a separate background tab"`, `"hits the autocomplete button"`, `"WD-40 of human civilization"`, `"choosing the paved highway over hacking through the jungle with a machete"`.
- **Replacement Standard (Plain Observation Over Clever Metaphor):**
  - *Avoid:* `"Your brain is aggressively, brilliantly lazy. It's an energy-saving shortcut. It's choosing the paved highway over hacking through the jungle with a machete."`
  - *Prefer:* `"Sometimes, telling the truth is just more trouble than it's worth. Not because you're afraid of getting caught. You just don't feel like explaining yourself."`

### Rule 2: Break the Formulaic 7-Step AI Beat Loop
- **Banned Formulaic Pattern:** Do NOT repeat the exact same rhythm in every section (`Curiosity Question -> Relatable Skit -> Quirky Joke -> Scientist Name-Drop -> Brain Mechanism -> Closing Punchline -> Hype Transition`).
- **Structural Variety:** Vary how acts open and close across an episode:
  - One section can open directly with an observation before asking any question.
  - One section can flow straight from a real-life example into a study without announcing a "secret mechanism."
  - One section can end on a quiet, reflective thought rather than a crisp joke or cliffhanger.

### Rule 3: Zero Predictable AI Transitions & Hype Phrasing
- **Strictly Banned Transitions:**
  - `"And here's the crazy part..."`
  - `"But here's the interesting thing..."`
  - `"Now, you might be thinking..."`
  - `"And what they discovered was wild..."`
  - `"revealed a hidden catch"` / `"there was just one catch"`
  - `"a stupidly simple trick"`
  - `"What if I told you..."` / `"Everything changed when..."`
- **Replacement Standard:** Transition by logic or observation rather than hype announcements. Let the idea itself carry the weight.

### Rule 4: Understated Scientific Authority (No Tabloid Drama Over Studies)
- Present academic studies calmly and accurately: who ran the study, what people actually did, and what the researchers observed.
- **Banned Academic Hype:** `"landmark study"`, `"nailed this down"`, `"crunched the numbers"`, `"shocked everyone"`, `"blew their minds"`, `"jumped right off the page"`, `"was wild"`.
- **Replacement Standard:**
  - *Avoid:* `"And what Sharot and Garrett saw on the scans was wild. By the fifth or sixth time? The alarm barely registered at all."`
  - *Prefer:* `"What they found was interesting. As people repeatedly benefited from dishonesty, their emotional response to it gradually weakened. In other words, something that felt uncomfortable at first could become easier to do over time."`

### Rule 5: Natural Conversational Flow & Punctuation (Write for the Ear)
- Always use standard spoken contractions (`you're`, `it's`, `don't`, `didn't`, `wasn't`, `that's`, `wouldn't`) unless intentionally emphasizing `"NOT"` for contrast.
- Mix medium explanatory sentences with occasional short reflections, letting ordinary sentences breathe without forcing drama at the end of every beat.
- Vary opening words and sentence shapes across paragraphs.

---

## 3. Pre-Production 5-Gate Script Audit (Mandatory Before Voice or Storyboard)
Every new script MUST pass these 5 verification gates before moving to audio generation or visual storyboarding:
1. **Punchline & Metaphor Density Gate:** Count humorous quips and colorful metaphors across the full script. Verify they sit around **3–4 total** (<= 1 per 2 minutes), with zero stacked joke-after-joke clusters.
2. **Banned Transition & Cliché Scan:** Scan the full script to confirm **0 occurrences** of AI hype transitions (`crazy part`, `interesting thing`, `might be thinking`, `was wild`, `hidden catch`, `stupidly simple trick`, `Boom. Done.`) and **0 tech/software clichés** (`software update`, `background tab`, `autocomplete button`, `social battery`).
3. **Structural Rhythm Gate:** Confirm consecutive sections do NOT follow the same rigid 7-step loop (`Question -> Skit -> Joke -> Study -> Mechanism -> Punchline -> Transition`).
4. **Scientific Calmness Gate:** Confirm every study citation states what happened plainly without tabloid exaggeration or invented absolute numbers that exceed the paper's actual claim.
5. **TTS Cleanliness Gate:** Confirm the final Voiceover Copy Block uses natural punctuation (`,`, `.`, `...`, `—`, `?`), light occasional stress caps (max 1–2 per minute), and zero robotic micro-direction spam (`[pause 0.35s]`, `[beat 0.25s]`, `[flip the tone — lively]`).

---

## 4. Voiceover Production Standard (Chatterbox Local MPS / ElevenLabs v3)

### Option A: Local Chatterbox TTS (Free, Apple Silicon MPS)
- **Script:** `/Applications/code/science-knowledge/ytb-tools/scripts/kairo_chatterbox_tts.py`
- **Settings:** Use moderate natural expression (`exaggeration = 0.50–0.65`, `cfg_weight = 0.38–0.45`) for reflective explanatory sections — avoid pushing `exaggeration > 0.75` for long 9-minute scripts unless hitting a rare emotional peak, otherwise delivery sounds theatrical rather than sincere.
- **Input Cleanliness:** Pass plain punctuation prose without bracketed stage directions (or let `clean_text_for_chatterbox` strip rare brackets), chunked by coherent 2–4 sentence beats so pacing breathes naturally.

### Option B: ElevenLabs v3 (If Used)
- **Model & Stability:** `Eleven v3` with `Stability` at `Creative` (`35% – 45%`) or `Natural` (`45% – 55%`). Never `Robust`.
- **Stage-Direction Hygiene:** NEVER add `[pause 0.35s]`, `[beat 0.25s]`, or long inline actor directives inside every sentence — over-directing breaks ElevenLabs v3 rhythm and creates artificial stops. Use natural prose punctuation for 95% of phrasing and at most 1–2 simple physical tags per Act (e.g., `[sighs]`, `[softly]`, `[chuckles]`).
- **Master Audio Standard:** Normalize final assembled voice track to `-14.0 LUFS` (`TP = -1.5 dB`) and verify clause-level word timestamps via `faster_whisper` before visual cutting.
