# Documentary Audio Engineering & Mastering Report — `test-a-before-v6-fallback`

- **Engine Mode:** `legacy_v6_fallback`
- **Adaptive Audio Profile:** `legacy_v6`
- **Master Integrated Loudness:** `-16.0 LUFS` | **LRA:** `1.4 LU` | **True Peak:** `-1.5 dBTP`
- **Voice-to-Bed Margin:** `10.6 LU` (`clipped_samples=0`, `excessive_silences=0`)

## Per-Layer Stem Loudness

| Stem | Active | Integrated Loudness | Notes |
|---|---|---:|---|
| `layer_1_narration` | `True` | `-15.9 LUFS` | Authoritative timing & intelligibility master |
| `layer_2_music` | `False` | `-70.0 LUFS` | `1` section(s); speech & important-phrase ducked |
| `layer_3_ambience` | `True` | `-44.4 LUFS` | `1` continuous environment section(s) |
| `layer_4_natural_sounds` | `True` | `-43.4 LUFS` | Verified expedition/diegetic field audio |
| `layer_5_cinematic_sfx` | `True` | `-36.1 LUFS` | `3` approved / `0` rejected for silence |
