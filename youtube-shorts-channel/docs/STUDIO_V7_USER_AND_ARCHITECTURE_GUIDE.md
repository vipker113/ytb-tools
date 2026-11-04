# Proof of Wonder — Studio v7.0 User & Architecture Guide

> **Advanced Voice, Sound Design & Intelligent Story Editing Engine (`$0` Budget)**  
> Workspace: `youtube-shorts-channel` | Fallback flag: `legacy_v6_fallback: true`

---

## 1. Core Philosophy: Make Every Element Matter

Studio v7.0 replaces fixed-duration templates, identical background drones, transition whooshes, and rigid shot counts with an adaptive, narration-governed documentary workflow:

1. **Final Narration Governs the Timeline:** A 35-second focused briefing, an 80-second multi-beat mystery, and a 2.5-minute deep documentary naturally produce different scene counts, pacing rhythms, and audio structures.
2. **Restraint Over Decoration:** Silence, a single strong continuous shot, and natural conversational contrast are first-class creative decisions.
3. **Strict `$0` Budget & Non-Destructive Safety:** Local `edge-tts`, `faster-whisper`, `Depth-Anything-V2`, and `FFmpeg` run at `$0.00`. When `ELEVENLABS_API_KEY` is present in the environment, `elevenlabs_provider.py` unlocks model-capability-aware ElevenLabs generation without code changes. Existing completed episodes in `PROTECTED_COMPLETED_OUTPUT_DIRS` can never be overwritten.

---

## 2. Reusable Modular Architecture (`pipeline/pow_studio/`)

| Module | Responsibility | Output Artifacts |
|---|---|---|
| `elevenlabs_provider.py` | Capability matrix for `eleven_multilingual_v2`, `eleven_v3`, `eleven_turbo_v2_5`, `eleven_flash_v2_5`; model-safe `voice_settings`; strips unsupported/theatrical `[tags]`; request stitching (`previous_text`/`next_text`) | Used by `voice_studio.py` |
| `voice_studio.py` | 11-parameter segment voice direction parser, anti-overdrama contrast rebalancer, raised-cosine boundary fades, continuity auditor, SHA-256 lock, dependent cache invalidator | `word_timings.json`, `voice_continuity_report.json`, `voice_approval_lock.json` |
| `audio_registry.py` | Persistent commercial-safe audio registry (11 metadata fields), 8 distinct vocal-pocket-safe CC0 acoustic beds, `$0` Wikimedia Commons field-audio harvester | `assets/audio_library/audio_asset_registry.json`, `AUDIO_ASSET_REGISTRY.md` |
| `music_planner.py` | Resolves Adaptive Audio Profile (`minimal_documentary`, `immersive_exploration`, `mystery_and_discovery`, `scientific_explanation`); plans `0..3` sections + pre-reveal hush | `music_plan.json` |
| `ambience_planner.py` | Merges connected location shots into continuous environmental beds with `1.2s` crossfades; enforces `space_vacuum_silent` in outer space | `ambience_plan.json` |
| `sfx_planner.py` | Evaluates every proposed cue against 6 documentary questions; blocks transition whooshes/booms, space SFX, and unshown off-screen sounds | `sfx_plan.json` |
| `scene_editor.py` | Evaluates every candidate shot (`Keep` / `Replace` / `Merge` / `Remove`) against finalized narration & source clip durations; snaps cuts to speech pauses (`0.000ms` drift) | `scene_optimization_report.json`, `scene_optimization_report.md` |
| `timeline_builder.py` | Builds the 11-column unified storyboard + soundscape plan and verifies audio-visual synchronization | `unified_av_timeline.json`, `unified_av_timeline.md` |
| `audio_engine.py` | Voice-first relative mixer (ceiling-only bed protection — never boosts quiet/music-free mixes upward), speech + important-phrase ducking, True-Peak limiting | `audio_engineering_report.json`, `audio_engineering_report.md` |
| `creative_qa.py` + `qc_suite.py` | Voice QA, Music & Effect QA, and Visual & Audio Creative QA (`CRITICAL`/`MAJOR`/`MINOR`/`INFO`); fails Gate 15 on poor creative edits even if technical metrics pass | `creative_qa_report.json`, `creative_qa_report.md`, `qc_measurements.json` |

---

## 3. Production & Voice Profiles (`config/`)

### 3.1 Production Profiles (`config/profiles/*.yaml`)
- `mysterious_earth_exploration` — Restrained atmospheric tension, natural ambience, gradual reveals.
- `cinematic_science_documentary` — Subtle acoustic/orchestral textures, deliberate documentary cuts.
- `deep_ocean_exploration` (and `deep_ocean_documentary`) — Immersive underwater pressure floor, longer uninterrupted shots.
- `space_discovery` — Spacious minimal design, strict vacuum silence in outer space, zero fake radio chatter.
- `ancient_mystery` — Historical open-fifth modal atmosphere, evidence-led narrative progression.
- `scientific_investigation` — Narration-first clarity, minimal/zero background music, information-first editing.

### 3.2 Voice Direction Profiles (`config/voice_profiles/*.yaml`)
- `cinematic_documentary`, `mysterious_discovery`, `scientific_authority`, `dramatic_reveal`, `calm_exploration`, `urgent_discovery`, `emotional_reflection`.

---

## 4. How Future Episodes Use Studio v7 Capabilities

### 4.1 YAML Manifest Controls
```yaml
style_profile: scientific_investigation   # Or any profile in config/profiles/
adaptive_audio_profile: auto              # 'auto' | 'minimal_documentary' | 'immersive_exploration' | 'mystery_and_discovery' | 'scientific_explanation'
adaptive_duration_mode: true              # Final narration determines runtime (no artificial padding/cutting)
enable_intelligent_scene_editing: true    # Runs Keep / Replace / Merge / Remove pass automatically
legacy_v6_fallback: false                 # Set true to revert to legacy v6 behavior if ever needed

tts_provider: auto                        # Uses ElevenLabs when ELEVENLABS_API_KEY is set, else $0 edge-tts
elevenlabs_model_id: eleven_multilingual_v2
voice_direction_profile: scientific_authority
```

### 4.2 Annotated Voice Script Tags (Sentence-Level Direction)
```text
[SEG: N01]
"Deep beneath Taylor Glacier, trapped seawater sat in darkness for over a million years."
[DELIVERY: MYSTERIOUS]
[TONE: curious_restraint]
[PACE: SLOW]
[ENERGY: 2/5]
[INTENSITY: 0.35]
[PITCH DIRECTION: falling]
[RHYTHM: measured]
[PAUSE BEFORE: 120ms]
[EMPHASIS: "million years"]
[PRONOUNCE: "Mikucki"="Mih-koo-kee"]
[PAUSE AFTER: 460ms]
```

### 4.3 CLI Commands
```powershell
# Run complete end-to-end Studio v7 workflow (Rights -> Voice & Stems -> Scene Optimization -> Shots -> Render -> 15-Gate Technical + Creative QA)
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py all -m episodes/your_episode.yaml

# Run individual Studio v7 inspection / planning stages
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py audio-registry --harvest "ocean hydrophone"
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py optimize-scenes -m episodes/your_episode.yaml
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py plan-soundscape -m episodes/your_episode.yaml
.\.venv\Scripts\python.exe pipeline/pow_studio/cli.py creative-qc -m episodes/your_episode.yaml
```
