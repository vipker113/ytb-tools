---
name: pow-mechanism-overlay
description: Plans and adds alpha mechanism overlays (ManimCE templates such as pressure ripples, gauges, flow arrows, scale bars, trajectories, leader labels) on top of real footage in a Proof of Wonder episode. Use when an episode needs to explain a physical mechanism, number, scale, or process visually, or when replacing hand-written Pillow diagram scripts.
---

# Mechanism Overlays (Studio v9)

Overlays explain the mechanism **on top of real footage**; they never replace it. They are composited
above the video and below captions, at the final mux step (shot caches are untouched).

## When to use

- Only in the Mechanism beat (and occasionally Payoff). One signature overlay per episode, at most
  `max_overlays_per_video` (4) total. Never in the hook (first 1.5 s).
- Use when narration states a number, scale, flow, wave, or trajectory that the footage alone cannot
  make obvious. If removing the overlay loses nothing, do not add it.
- Never repeat the caption text in the overlay; overlays show values/shapes, captions carry words.

## Templates

| Template | Use | Key params |
|---|---|---|
| `pressure_ripple` | waves spreading from a source | `center`, `rings`, `period_s`, `label`, `sublabel`, `color` |
| `wave_frequency_scale` | log scale of frequency/energy | `title` / `label`, `ticks` (`[{label, sub}]`), `marker_label` / `marker_value`, `color` |
| `value_callout_gauge` | number counting up + leader line to a point | `value_from`, `value_to`, `decimals`, `unit`, `label`, `point` |
| `flow_arrows` | curved arrows along a flow path | `path` (normalized `[x, y]` points), `count`, `label`, `color` |
| `scale_bar_compare` | size comparison bar | `length_label`, `reference_label`, `ratio` |
| `trajectory_trace` | orbit / flight path drawing | `path`, `label`, `color` |
| `label_leader` | thin label + leader line, optional tracking | `point`, `text`, `subtext`, `track_keyframes` (`[[u, x, y], ...]`) |

## Manifest (`mechanism_overlays[]`)

```yaml
mechanism_overlays:
  - overlay_id: OV1
    template: value_callout_gauge
    anchor: { seg_id: N02, phrase: "three hundred sixty atmospheres" }
    hold_s: 2.4
    region: { x: 0.08, y: 0.14, w: 0.84, h: 0.30 }
    params: { value_to: 360, unit: "°C", label: "VENT FLUID", point: [0.52, 0.46] }
    claim_ref: 2                       # index into factual_references (required)
    honesty_label: measured_value      # measured_value | illustrative_model | scale_comparison
```

## Honesty & layout rules (enforced by QA)

- Graphics stay inside `y ∈ [215, 1380]` px (caption and UI zones are forbidden) → CRITICAL if violated.
- Alpha-covered area ≤ 35% of the frame; above that for > 1 s, the interval is counted as
  `INFOGRAPHIC`, not real footage.
- Total overlay time ≤ 30% of runtime; each overlay ≥ 1.2 s; must not cross a hard cut unless
  `span_cut: true`.
- Every overlay cites a `claim_ref`; illustrative models must be labeled `illustrative_model`.

## Commands (Studio v9 M4)

```bash
$PY $STUDIO render-overlays -m $EP     # renders/caches overlays/<id>_<hash>.mov + mechanism_overlay_qa.json
$PY $STUDIO preview -m $EP --mode draft
```

Review `mechanism_overlay_qa.json` and the preview sheet visually before asking for storyboard approval.
