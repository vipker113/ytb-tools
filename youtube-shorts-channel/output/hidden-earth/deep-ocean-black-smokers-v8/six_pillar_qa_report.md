# 6-Pillar Future-Video QA Report — `deep-ocean-black-smokers-v8`

- **Technical Approval:** `PASS`
- **Creative Approval:** `FAIL`
- **Overall Release Approval:** `BLOCKED_FOR_REVISION`

## 5-Part Source-Honest Visual Coverage Metrics
- **A. Genuine Moving Footage Ratio:** `88.32%` (Time-lapse subset: `0.0%`)
- **B. Meaningful Action Footage Ratio:** `88.32%`
- **C. Establishing Footage Ratio:** `0.0%`
- **D. Static Image Ratio:** `11.68%` (Animated stills: `11.68%`)
- **E. Scientific Visualization Ratio:** `0.0%`

## 6-Pillar Gate Summary
| Pillar | Verdict | Critical | Major | Minor |
|---|---|---|---|---|
| `media_qa` | **FAIL** | 0 | 1 | 0 |
| `semantic_qa` | **PASS** | 0 | 0 | 0 |
| `repetition_qa` | **PASS** | 0 | 0 | 0 |
| `timeline_qa` | **PASS** | 0 | 0 | 0 |
| `technical_qa` | **PASS** | 0 | 0 | 0 |
| `creative_qa` | **PASS** | 0 | 0 | 0 |

## Detailed QA Findings
| Severity | Pillar | Shot | Code | Message |
|---|---|---|---|---|
| **MAJOR** | `media_qa` | `S08` | `animated_still_disguised_as_video` | Shot S08 ('ifremer_biobaz_sampling_81111.webm') is a static image with artificial pan/zoom baked into MP4 (Artificial pan/zoom over static image detected (raw_diff=7.62, compensated_diff=2.76, ratio=0.36, p90_flow_res=0.43px).). |
