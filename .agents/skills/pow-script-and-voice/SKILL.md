---
name: pow-script-and-voice
description: Writes and directs Proof of Wonder narration — hook, 4-part documentary structure, episode YAML narration_segments, and the bracket-annotated voice script — then generates and locks the voice. Use when drafting or revising a script, hook, title, narration, voice direction, or when running stage2-story / stage3-voice.
---

# Script & Voice (Proof of Wonder)

## Editorial formula (locked by the channel owner)

`Thumbnail → Question → Proof → Explanation`, as 4 beats:
1. **Hook (0.00s):** a direct spoken question or physical contradiction tied to the thumbnail/title.
   Within the first 1–2 s the viewer must see the real subject, hear the question, read a short
   on-screen hook (top safe zone), and see motion. No greetings, logos, slow establishing shots.
2. **Evidence:** show the actual object/event/phenomenon.
3. **Mechanism:** explain the cause with relevant footage; restrained explanatory graphics
   (mechanism overlays) ≤ 30% of runtime.
4. **Payoff:** answer the opening question; one memorable conclusion; ideally loops into frame 0.

Thumbnail, title, opening line and first shot promise the same story. If footage cannot honestly
support that promise (feasibility gate), re-scope the topic — do not write around missing evidence.

## Length & language

- Target 45–55 s (ytb-tools outlier data: 45–65 s performs best for US science Shorts). Older channel
  brief says 35–45 s; prefer the data-driven range unless the user says otherwise.
- Natural spoken US/UK English, no article prose, no AI clichés, ≤ 18 words in the first sentence,
  ≤ 24 words per sentence (`viral_retention` limits). No hashtags in titles.
- Every number, label and claim must match ≥ 2 primary sources (NASA, ESA, NOAA, peer-reviewed) listed
  in `factual_references`. State scientific caveats honestly (`scientific_caveat_seg_id`).
- Mid-video pivot (`layer2_pivot_seg_id`) around 35–45% of runtime.

## Manifest fields to fill (per `narration_segments[]`)

`seg_id, text, delivery, pace, energy, pause_after_ms, emphasis_words, narrative_beat,
viewer_question, new_information, visual_reveal, emotional_direction, retention_purpose`.
Use `episodes/deep_ocean_black_smokers_v8_documentary.yaml` as the reference template; set
`manifest_version: "9.0"`, `require_storyboard_approval: true`, `visual_corpus_mode: shadow` (or `on`
once the corpus eval passes).

## Voice script (`episodes/<slug>_voice_script.txt`)

Per segment:

```text
[SEG: N01]
"Exact spoken sentence."

[DELIVERY: HOOK]            # HOOK | CALM EXPLANATION | MEASURED EVIDENCE | MYSTERIOUS | SURPRISED BUT CONTROLLED | CINEMATIC REVEAL | EMOTIONAL REFLECTION
[TONE: quiet_tension]
[INTENSITY: 0.72]
[PITCH DIRECTION: falling]  # falling | steady | gentle_rise | low_intimate
[RHYTHM: crisp]
[EMPHASIS: "phrase one", "phrase two"]
[PRONOUNCE: "Rimicaris"="Rih-mih-KAR-iss"]
[PAUSE AFTER: 380ms]
```

Contrast matters: do not mark everything as a reveal. Explanation lines stay calm; one or two lines
get real emphasis. Voice profiles: `cinematic_documentary, mysterious_discovery,
scientific_authority, dramatic_reveal, calm_exploration, urgent_discovery, emotional_reflection`
(`$PY $STUDIO profiles`).

## Commands

```bash
$PY $STUDIO stage2-story -m $EP          # hook scoring, momentum audit, retention plan
$PY $STUDIO voice-preview -t "..." -p mysterious_discovery --compare-variants
$PY $STUDIO stage3-voice -m $EP          # narration + 5-layer stems + word_timings.json
```

Then **stop**: give the user the narration file (`<out>/work_audio/narration_norm.wav`) and wait.
Only after the user approves: `$PY $STUDIO voice-approve -m $EP --note "<user note>"`.
Regenerating narration invalidates timing-dependent artifacts automatically; re-run downstream stages.
