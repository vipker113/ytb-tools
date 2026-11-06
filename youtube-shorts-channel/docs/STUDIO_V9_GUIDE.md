# Proof of Wonder — Studio v9.0 Production & Architecture Guide

Tài liệu kỹ thuật và vận hành chính thức cho **Proof of Wonder Documentary Studio v9.0** (`youtube-shorts-channel/pipeline/pow_studio/` + `ytb-tools/` Next.js 16 Dashboard). Mọi thành phần đều được thiết kế mới hoàn toàn (clean-room), chạy cục bộ với chi phí **`$0`**, không dùng API trả phí hay sinh video AI, và tương thích ngược `100%` với toàn bộ tập `v6–v8`.

---

## 1. Kiến Trúc Tổng Quan Studio v9 (6 Năng Lực Cốt Lõi)

| Mũi nhọn | Hạng mục | Module chính | Cờ / Lệnh kích hoạt |
|---|---|---|---|
| **Nền móng** | Sổ sự kiện sản xuất & Golden Render | `pow_studio/events.py`, `pipeline/v9_golden_render.py` | Tự động ghi `studio_state.json` + `studio_events.jsonl` |
| **1A — Tư liệu** | Harvester v2 (`8` nguồn `$0`) + `.provenance.json` | `pow_studio/footage_sources/*`, `rights_gate.py` | `footage-sources`, `discover-footage`, `download-footage` |
| **1B — Thị giác** | Local Visual Corpus (`CLIP`/`SigLIP` trên `mps`) | `pow_studio/visual_corpus/*` | `corpus-ingest`, `corpus-search`, `match-beats`, `visual_corpus_mode: on` |
| **2A — Điều phối** | Agent Guardrails & 6 Workspace Skills | `.agents/rules/pow-guardrails.md`, `.agents/skills/pow-*` | Tự động nạp trong Antigravity IDE |
| **2B — Cơ chế** | ManimCE Alpha Mechanism Overlays (`<= 35%` alpha) | `pow_studio/mechanism_overlay/*` | `render-overlays`, khối `mechanism_overlays:` trong YAML |
| **3A — Chiến lược** | Outlier Video Reference Analyst + UI Giải phẫu | `pow_studio/outlier_analyst.py`, `OutlierAnatomyModal.tsx` | `analyze-outlier`, `outlier-patterns`, nút **Giải phẫu nhịp dựng** |
| **3B — Bàn dựng** | Tab **Studio Backlot** (SSE) + Cổng duyệt Storyboard | `pow_studio/backlot.py`, `StudioBacklotTab.tsx` | `export-storyboard`, `require_storyboard_approval: true` |

---

## 2. Cài Đặt Môi Trường (`$0`, Tách Nhóm Thư Viện)

```bash
cd /Applications/code/science-knowledge

# Chỉ cài lõi Studio v6-v8 (nhẹ, chạy mọi lệnh dựng cơ bản):
./setup-studio-anywhere.sh

# Cài đầy đủ toàn bộ năng lực Studio v9 (CLIP mps + ManimCE + Outlier Analyst):
./setup-studio-anywhere.sh --with-all
```

Các nhóm phụ thuộc tách rời trong `youtube-shorts-channel/`:
- `requirements.txt` — Lõi dựng phim (`ffmpeg`, `faster-whisper`, `edge-tts`, `onnxruntime`, `pillow`, `pydantic`).
- `requirements-ml.txt` (`--with-ml`) — `torch` + `transformers` chạy `CLIP ViT-B/32` trên GPU Apple Silicon (`mps`, `~165 img/s`, `< 700 MB` RAM).
- `requirements-graphics.txt` (`--with-graphics`) — `manim==0.22.1`, `manimpango`, `pycairo` (render `.mov` `qtrle` kênh alpha trong suốt, dùng font `BeVietnamPro` / `Anton` đi kèm, **không cần cài MacTeX**).
- `requirements-analysis.txt` (`--with-analysis`) — `yt-dlp`, `scenedetect`, `youtube-transcript-api` cho phân tích nhịp dựng đối thủ.

*(Tuỳ chọn)* Nếu có khóa miễn phí của Cục Lưu trữ Quốc gia Mỹ (`NARA`), xuất biến môi trường `export NARA_API_KEY="..."` để nguồn thứ 8 (`nara`) tự động bật.

---

## 3. Quy Trình Sản Xuất Chuẩn Studio v9 (`10 Bước + 3 Cổng Duyệt Người Thật`)

Thiết lập biến môi trường nhanh:
```bash
cd /Applications/code/science-knowledge/youtube-shorts-channel
export PY=".venv/bin/python"
export STUDIO="pipeline/pow_studio/cli.py"
export EP="episodes/space_parker_solar_probe_v9_documentary.yaml"
```

### Giai đoạn A — Săn Tư Liệu Thật & Cổng Khả Thi (`Footage-First`)
```bash
# 1. Kiểm tra các kho tư liệu $0 đang bật
"$PY" "$STUDIO" footage-sources

# 2. Tìm ứng viên tư liệu (dùng cụm từ khóa ngắn 2-4 từ)
"$PY" "$STUDIO" discover-footage -t "Parker Solar Probe" -q "WISPR corona" --out output/space-and-universe/parker-solar-probe-corona-v9/planning

# 3. Tải tư liệu kèm sidecar .provenance.json, kiểm tra chuyển động từ pixel & tự gỡ track nhạc SVS/ESA
"$PY" "$STUDIO" download-footage \
  --discovery output/space-and-universe/parker-solar-probe-corona-v9/planning/footage_discovery.json \
  --select ae3d1666a3,e403f6685e,538b0cfb5e,150a388c13 \
  --dest assets/raw_footage/space_parker_solar_probe_v9

# 4. Nạp vào Visual Corpus cục bộ (tăng dần, bỏ qua file không đổi) & tìm theo nội dung khung hình
"$PY" "$STUDIO" corpus-ingest --path assets/raw_footage
"$PY" "$STUDIO" corpus-search --text "cleanroom engineers installing octagonal heat shield" -k 8 --genuine-only

# 5. Khớp các nhịp kịch bản với Visual Corpus & chạy cổng Feasibility + Rights Gate
"$PY" "$STUDIO" match-beats -m "$EP"
"$PY" "$STUDIO" feasibility -m "$EP" --out-dir output/space-and-universe/parker-solar-probe-corona-v9/planning
"$PY" "$STUDIO" stage1-research -m "$EP"
```
> **Lưu ý thị giác:** Luôn mở `planning/beat_matches_strip.jpg` kiểm tra bằng mắt để loại trừ các khung tiêu đề đầu/cuối video có chữ trùng tên chủ đề (hiện tượng neuron OCR của `CLIP`).

### Giai đoạn B — Kịch Bản, Giọng Đọc & Cổng Duyệt 1 (`Voice Lock`)
```bash
# 6. Chấm điểm Hook (0-3s), nhịp giữ chân & kiểm tra chống văn phong AI
"$PY" "$STUDIO" stage2-story -m "$EP"

# 7. Sinh giọng đọc đạo diễn ngữ điệu + tách word_timings.json + trộn 5 lớp âm thanh (-16 LUFS)
"$PY" "$STUDIO" stage3-voice -m "$EP"
```
- **CỔNG DUYỆT 1:** Nghe thử `<output_dir>/work_audio/narration_norm.wav`. Khi ưng ý mới khóa giọng:
  ```bash
  "$PY" "$STUDIO" voice-approve -m "$EP" --note "Approved natural documentary pacing"
  ```

### Giai đoạn C — Overlay Cơ Chế, Bàn Dựng `Studio Backlot` & Cổng Duyệt 2 (`Storyboard Gate`)
```bash
# 8. Render ManimCE alpha overlays (cache SHA-256) & kiểm tra mechanism_overlay_qa.json
"$PY" "$STUDIO" render-overlays -m "$EP"

# 9. Lập kế hoạch khung hình, tối ưu cắt cảnh, soundscape & xuất Storyboard lên Backlot
"$PY" "$STUDIO" stage4-visual -m "$EP" --mode draft
"$PY" "$STUDIO" optimize-scenes -m "$EP"
"$PY" "$STUDIO" plan-soundscape -m "$EP"
"$PY" "$STUDIO" export-storyboard -m "$EP"

# (Tuỳ chọn) Render bản nháp 540x960 để xem trước chuyển động mà không bị chặn bởi cổng Master
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode draft
```
- **CỔNG DUYỆT 2:** Mở `http://localhost:3000` → tab **Studio Backlot**:
  - Xem filmstrip `IN / MID / OUT` của từng cảnh (đã ghép sẵn lớp alpha overlay ManimCE), huy hiệu bản quyền, điểm `CLIP`, 3 phương án Thumbnail di động `160x284` và nhật ký sự kiện trực tiếp qua `SSE`.
  - Bấm **Duyệt Master** (ghi `storyboard_approval.json` khóa theo mã băm `storyboard_sha256`) hoặc ghi chú từng shot rồi bấm **Yêu cầu sửa**. Nếu bất kỳ shot hay overlay nào thay đổi sau đó, `storyboard_sha256` tự động đổi và chặn render Master cho đến khi duyệt lại.

### Giai đoạn D — Render Master, QA 6 Trụ & Cổng Duyệt 3 (`Release Handoff`)
```bash
# 10. Render bản Master 1080x1920 @ 30fps (chỉ mở khóa sau khi duyệt Storyboard trên Backlot)
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode master

# 11. Kiểm định 14 cổng kỹ thuật + QA 6 trụ + Creative QC
"$PY" "$STUDIO" stage6-quality -m "$EP"
"$PY" "$STUDIO" qa-6pillar -m "$EP" --out-dir output/space-and-universe/parker-solar-probe-corona-v9/qa
"$PY" "$STUDIO" creative-qc -m "$EP"
```
- **CỔNG DUYỆT 3:** Mở `http://localhost:3000` → tab **Mac Studio Review** → bấm **Quét lại Output** để xem bản Master cuối cùng, chọn Thumbnail và quyết định lưu nháp / lên lịch đăng. Agent **tuyệt đối không tự chạy lệnh upload/publish** nếu không có lệnh rõ ràng cho tập đó.

---

## 4. Khai Báo Manifest v9 (`episodes/*.yaml`)

Ba trường mới của Studio v9 (mặc định tắt trên các YAML `v6–v8` để giữ nguyên đầu ra bit-for-bit):

```yaml
manifest_version: "9.0"
visual_corpus_mode: "on"             # off | shadow | on
require_storyboard_approval: true    # Bắt buộc duyệt trên Studio Backlot trước khi render master

mechanism_overlays:
  - overlay_id: "OV2_SHIELD_GAUGE"
    template: "value_callout_gauge"  # pressure_ripple | wave_frequency_scale | value_callout_gauge | flow_arrows | scale_bar_compare | trajectory_trace | label_leader
    anchor:
      seg_id: "N04"
      phrase: "thirteen hundred seventy degrees"
      lead_in_s: 0.0
    hold_s: 2.3
    span_cut: true
    region: { x: 0.12, y: 0.16, w: 0.76, h: 0.26 }
    params:
      value_from: 30
      value_to: 1370
      decimals: 0
      unit: "°C"
      label: "SHIELD FRONT (30°C BEHIND)"
      point: [0.50, 0.54]
      color: "#78D6FF"
    claim_ref: 1                     # Chỉ số 0-based trỏ tới factual_references[]
    honesty_label: "measured_value"  # measured_value | illustrative_model | scale_comparison
```

**Luật trung thực lớp phủ (`Honesty QA`):**
- Nằm gọn trong vùng an toàn dọc `y ∈ [215, 1380]` px (tránh đè phụ đề dưới và giao diện YouTube Shorts).
- Diện tích alpha `<= 35%` khung hình → cảnh nền vẫn được tính là tư liệu thật (`REAL_VIDEO_*`); vượt `35%` liên tục quá `1.0s` sẽ bị hạ xuống `INFOGRAPHIC`.
- Tổng thời lượng overlay `<= 30%` thời lượng tập, tối đa `4` overlay/tập, cấm xuất hiện trong `1.5s` mở đầu.

---

## 5. Phân Tích Video Outlier Đối Thủ (`Outlier Reference Analyst`)

```bash
# Phân tích 1 video YouTube Short (tải tạm <=480p vào thư mục tạm rồi tự xóa ngay sau khi trích chỉ số):
"$PY" "$STUDIO" analyze-outlier --video-id TZd3xs5A3mE --mode download

# Chế độ chỉ đọc phụ đề (không tải video):
"$PY" "$STUDIO" analyze-outlier --video-id TZd3xs5A3mE --mode transcript_only

# Tổng hợp báo cáo chênh lệch nhịp dựng so với các tập Proof of Wonder:
"$PY" "$STUDIO" outlier-patterns
```
Hoặc dùng trực tiếp trên Web UI (`http://localhost:3000` → **Ý Tưởng & Đối Thủ** → **Outlier Hunter** → bấm **Giải phẫu nhịp dựng** → **Lưu ý tưởng kèm giải phẫu**).

---

## 6. Kiểm Chứng Hồi Quy & Báo Cáo Benchmark

- Chạy toàn bộ kiểm thử tự động:
  ```bash
  ./youtube-shorts-channel/.venv/bin/pytest youtube-shorts-channel/pipeline/tests -q
  ```
- Kiểm tra bất biến `framemd5` trên tập chuẩn `v6`:
  ```bash
  ./youtube-shorts-channel/.venv/bin/python youtube-shorts-channel/pipeline/v9_golden_render.py \
    --manifest youtube-shorts-channel/episodes/space_perseus_black_hole_v6_documentary.yaml \
    --mode master --compare
  ```
- Hồ sơ đo kiểm chi tiết của từng mũi nhọn:
  - Harvester v2: `youtube-shorts-channel/docs/v9_harvester_benchmark.md`
  - Local Visual Corpus (`mps`): `youtube-shorts-channel/docs/v9_corpus_eval.md`
  - ManimCE Alpha Overlays: `youtube-shorts-channel/docs/v9_mechanism_overlay_benchmark.md`
  - Outlier Analyst (`10` video / `5` kênh): `youtube-shorts-channel/docs/v9_outlier_benchmark.md`
