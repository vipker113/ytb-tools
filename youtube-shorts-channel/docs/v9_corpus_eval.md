# Studio v9 Visual Corpus Benchmark (`docs/v9_corpus_eval.md`)

## 1. Evaluation Setup & Bias Disclosure
- **Licensed Corpus Windows Evaluated:** `1982` across `188` licensed files (`license_status in {verified, declared}`).
- **Gold Shot Queries:** `253` deduplicated `(episode, src_file, src_in)` shots from production manifests.
- **Query Suites:**
  1. **`visual_desc`** — shot visual description from YAML. *Bias note:* authored after an editor/agent inspected the footage, so absolute scores carry mild optimism bias.
  2. **`narration_concept`** — spoken narration concept (`associated_narration_concept` / segment text). Tests blind **narration-to-pixels** retrieval before clip selection.
- **Recommended Configuration:** `clip-l14:hybrid-70-30` (`exceeds_token_baseline=True`).

## 2. Suite A — `visual_desc` Queries (Window & File Recall)

| Method | Win R@1 | Win R@5 | Win R@10 | Win MRR | File R@1 | File R@5 | File R@10 | File MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `token-baseline-v8` | 0.364 | **0.526** | 0.628 | 0.441 | 0.692 | **0.846** | 0.893 | 0.764 |
| `clip-b32:visual-only` | 0.158 | **0.439** | 0.581 | 0.287 | 0.360 | **0.739** | 0.909 | 0.537 |
| `clip-b32:hybrid-70-30` | 0.300 | **0.640** | 0.755 | 0.444 | 0.644 | **0.905** | 0.968 | 0.762 |
| `siglip-b16:visual-only` | 0.174 | **0.407** | 0.557 | 0.295 | 0.387 | **0.747** | 0.877 | 0.546 |
| `siglip-b16:hybrid-70-30` | 0.348 | **0.549** | 0.680 | 0.448 | 0.652 | **0.885** | 0.945 | 0.751 |
| `clip-l14:visual-only` | 0.217 | **0.423** | 0.561 | 0.327 | 0.419 | **0.775** | 0.913 | 0.575 |
| `clip-l14:hybrid-70-30` | 0.360 | **0.597** | 0.739 | 0.473 | 0.696 | **0.925** | 0.968 | 0.803 |

## 3. Suite B — Blind `narration_concept` Queries (Window & File Recall)

| Method | Win R@1 | Win R@5 | Win R@10 | Win MRR | File R@1 | File R@5 | File R@10 | File MRR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `token-baseline-v8` | 0.127 | **0.205** | 0.257 | 0.170 | 0.237 | **0.443** | 0.494 | 0.328 |
| `clip-b32:visual-only` | 0.032 | **0.107** | 0.205 | 0.079 | 0.115 | **0.285** | 0.466 | 0.214 |
| `clip-b32:hybrid-70-30` | 0.043 | **0.115** | 0.170 | 0.083 | 0.115 | **0.288** | 0.411 | 0.216 |
| `siglip-b16:visual-only` | 0.043 | **0.130** | 0.166 | 0.086 | 0.103 | **0.316** | 0.459 | 0.210 |
| `siglip-b16:hybrid-70-30` | 0.059 | **0.138** | 0.198 | 0.105 | 0.138 | **0.340** | 0.439 | 0.244 |
| `clip-l14:visual-only` | 0.067 | **0.150** | 0.194 | 0.111 | 0.115 | **0.332** | 0.486 | 0.225 |
| `clip-l14:hybrid-70-30` | 0.075 | **0.182** | 0.217 | 0.124 | 0.178 | **0.352** | 0.470 | 0.271 |

## 4. Apple M2 Pro (`mps`, 16 GB RAM) Throughput & Memory

| Method | Device | Throughput (img/s) | Peak RSS (MB) | Query Eval Time (s) |
|---|---|---:|---:|---:|
| `token-baseline-v8` | `cpu` | — | — | 0.357 |
| `clip-b32:visual-only` | `mps` | 164.9 | 692.0 | 1.342 |
| `clip-b32:hybrid-70-30` | `mps` | 164.9 | 692.0 | 1.342 |
| `siglip-b16:visual-only` | `mps` | 77.5 | 1448.6 | 3.471 |
| `siglip-b16:hybrid-70-30` | `mps` | 77.5 | 1448.6 | 3.471 |
| `clip-l14:visual-only` | `mps` | 21.9 | 1448.6 | 2.332 |
| `clip-l14:hybrid-70-30` | `mps` | 21.9 | 1448.6 | 2.332 |
## 5. Shadow-Mode Disagreement Audit (`3` Episodes) & Production Recommendation

After stripping abstract beat-planner placeholders (`_beat_visual_query`) and applying a `-0.22` infographic-slate penalty, we ran `match-beats` in `shadow` mode across 3 episodes (`35` beats total) and visually inspected every `beat_matches_strip.jpg`:

| Episode | Beats | Disagreements | Classification of Disagreements |
|---|---:|---:|---|
| `perseus-black-hole-sound-v6` | 11 | 2 | **2/2 Visual wins:** `B05` picked moving 4K `perseus_cluster_wave_4k.webm` over static B&W still; `B10` picked `ngc1275_hst_chandra_4k.jpg` instead of repeating the same B&W still. |
| `bermuda-triangle-abyss-v6` | 12 | 2 | **1 Visual win, 1 CLIP OCR trap:** `B03` picked actual ROV shipwreck (`noaa_ex2502_shipwreck_nevada_1080p.mp4`) instead of a NOAA logo slate; `B02` matched text on an expedition opening slate (`"Puerto Rico's Seamounts"`). |
| `blood-falls-v6-studio-pilot` | 12 | 3 | **2 Visual wins, 1 tie:** `B01` picked real Antarctic flyover video over a cross-section diagram; `B04` picked the rust-stained Blood Falls cliff (`bf_2010_12_14.jpg`) over a helicopter on snow; `B10` swapped two equivalent field-team clips. |

### Production Configuration Decision for Studio v9
1. **Default Model:** Keep `clip-b32` (`hybrid-70-30`) as the default (`+11.4` pts Window R@5 and `+5.9` pts File R@5 over v8 lexical baseline on visual queries, `164.9 img/s`, `692 MB` peak RSS on Apple M2 Pro `mps` — `7.5x` faster and `52%` lower RAM than `clip-l14`, which remains selectable via `--model clip-l14`).
2. **Mode Readiness:** Approved to enable `visual_corpus_mode: on` (`0.20` visual weight) on Studio v9 episodes, with mandatory agent inspection of `planning/beat_matches_strip.jpg` to reject any clip-opening title slates attracted by CLIP's OCR neurons.
