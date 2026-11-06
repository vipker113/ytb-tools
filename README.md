# Proof of Wonder (`science-knowledge`) — Documentary Video Studio v9.0 & Channel Suite

Hệ thống sản xuất phim tài liệu khoa học tự động `$0` (**Studio v9.0**, tương thích ngược `100%` với `v6–v8`) + Web Dashboard quản lý kênh YouTube (**ytb-tools**) cho thương hiệu **Proof of Wonder**.

> 📖 **Hướng dẫn cài đặt cho máy ở nhà:** [HOME_SETUP_GUIDE.md](./HOME_SETUP_GUIDE.md)
> 📐 **Hướng dẫn kiến trúc & quy trình Studio v9 chi tiết:** [youtube-shorts-channel/docs/STUDIO_V9_GUIDE.md](./youtube-shorts-channel/docs/STUDIO_V9_GUIDE.md)

## 1. Cài đặt nhanh trên bất kỳ máy mới nào (Mac / Linux)

### Yêu cầu hệ thống
- `git`, `ffmpeg` (`brew install ffmpeg` trên macOS), `python3` (`3.11+` hoặc `uv`), và `node` (`18+` cho Web UI).

### Lệnh tải toàn bộ workspace (`science-knowledge` + `ytb-tools`) & cài đặt tự động
```bash
git clone --recurse-submodules -b science-knowledge https://github.com/vipker113/ytb-tools.git science-knowledge
cd science-knowledge
chmod +x setup-studio-anywhere.sh

# Cài đầy đủ Studio v9 (CLIP Visual Corpus trên mps + ManimCE Alpha Overlays + Outlier Analyst):
./setup-studio-anywhere.sh --with-all
```
*(Nếu chỉ cần lõi dựng `v6–v8` gọn nhẹ, chạy `./setup-studio-anywhere.sh` không kèm cờ; hoặc chọn từng nhóm `--with-ml`, `--with-graphics`, `--with-analysis`).*

---

## 2. Cấu trúc thư mục

- `.agents/` — **Hệ thống điều phối Agent (Studio v9)**:
  - `rules/pow-guardrails.md` — Luật bảo vệ bắt buộc (`$0`, không tự upload, khóa thư mục đã hoàn thành, kiểm tra giấy phép bằng code).
  - `skills/pow-*/SKILL.md` — 6 kỹ năng chuyên biệt (`pow-executive-producer`, `pow-footage-research`, `pow-script-and-voice`, `pow-mechanism-overlay`, `pow-qa-and-release`, `pow-outlier-analysis`).
- `youtube-shorts-channel/` — **Proof of Wonder Documentary Production Studio v9.0**:
  - `pipeline/pow_studio/` — Động cơ sản xuất phim tài liệu (`footage_sources/`, `visual_corpus/`, `mechanism_overlay/`, `backlot.py`, `outlier_analyst.py`, `events.py`, `story_engine.py`, `voice_studio.py`, `audio_engine.py`, `visual_intelligence.py`, `compositor.py`, `qc_suite.py`, `creative_qa.py`, `cli.py`).
  - `config/profiles/` & `config/voice_profiles/` — Production Profiles tái sử dụng & 7 Voice Direction Presets.
  - `episodes/` — File cấu hình tập phim (`.yaml`) & kịch bản điều hướng giọng đọc (`.txt`).
  - `docs/` — Tài liệu vận hành `STUDIO_V9_GUIDE.md` và các báo cáo benchmark thực nghiệm (`v9_*_benchmark.md`, `v9_corpus_eval.md`).
- `ytb-tools/` — Giao diện Web Next.js 16 (`http://localhost:3000`):
  - **Studio Backlot** (`SSE` trực tiếp): duyệt filmstrip `IN/MID/OUT`, lớp phủ cơ chế ManimCE, điểm `CLIP`, 3 Thumbnail di động và mở khóa cổng render Master (`storyboard_approval.json`).
  - **Outlier Hunter (`Giải phẫu nhịp dựng`)**: phân tích nhịp cắt cảnh, lớp chuyển động và cấu trúc Hook của đối thủ ngay tại máy.
  - **Mac Studio Review**: kiểm duyệt bản Master cuối cùng và đồng bộ YouTube Studio.

---

## 3. Lệnh dựng video chuẩn Studio v9.0

```bash
export PY="$(pwd)/youtube-shorts-channel/.venv/bin/python"
export STUDIO="$(pwd)/youtube-shorts-channel/pipeline/pow_studio/cli.py"
export EP="$(pwd)/youtube-shorts-channel/episodes/space_parker_solar_probe_v9_documentary.yaml"

# Bước 1: Săn tư liệu thật ($0), tải kèm sidecar .provenance.json & nạp Visual Corpus (CLIP mps)
"$PY" "$STUDIO" discover-footage -t "Parker Solar Probe" -m "$EP"
"$PY" "$STUDIO" corpus-ingest --path youtube-shorts-channel/assets/raw_footage
"$PY" "$STUDIO" match-beats -m "$EP"
"$PY" "$STUDIO" feasibility -m "$EP" --out-dir youtube-shorts-channel/output/space-and-universe/parker-solar-probe-corona-v9/planning
"$PY" "$STUDIO" stage1-research -m "$EP"

# Bước 2: Chấm điểm Hook mở đầu, kiểm tra nhịp giữ chân & xuất bản đồ Retention
"$PY" "$STUDIO" stage2-story -m "$EP"

# Bước 3: Sinh giọng đọc có ngữ điệu + trộn âm thanh 5 lớp (-16 LUFS) -> nghe thử rồi khóa giọng
"$PY" "$STUDIO" stage3-voice -m "$EP"
"$PY" "$STUDIO" voice-approve -m "$EP" --note "Approved"

# Bước 4: Render lớp phủ cơ chế ManimCE (kênh alpha), lập khung hình & xuất Storyboard lên Studio Backlot
"$PY" "$STUDIO" render-overlays -m "$EP"
"$PY" "$STUDIO" stage4-visual -m "$EP" --mode draft
"$PY" "$STUDIO" optimize-scenes -m "$EP"
"$PY" "$STUDIO" plan-soundscape -m "$EP"
"$PY" "$STUDIO" export-storyboard -m "$EP"

# -> Mở http://localhost:3000 (tab Studio Backlot) bấm "Duyệt Master", sau đó chạy:

# Bước 5: Dựng video Master 1080x1920 @ 30fps (hỗ trợ cache SHA-256 từng cảnh & từng overlay)
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode master

# Bước 6: Kiểm định 14 cổng kỹ thuật + QA 6 trụ + Creative QC
"$PY" "$STUDIO" stage6-quality -m "$EP"
"$PY" "$STUDIO" qa-6pillar -m "$EP" --out-dir youtube-shorts-channel/output/space-and-universe/parker-solar-probe-corona-v9/qa
"$PY" "$STUDIO" creative-qc -m "$EP"
```

### Khởi động giao diện Web Quản lý, Backlot & Upload (`ytb-tools`)
```bash
cd ytb-tools
npm run dev
# Mở http://localhost:3000 (Studio Backlot / Outlier Hunter / Mac Studio Review)
```
