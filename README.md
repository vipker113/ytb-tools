# Proof of Wonder (`science-knowledge`) — Documentary Video Studio v6.0 & Channel Suite

Hệ thống sản xuất phim tài liệu khoa học tự động `\$0` (**Studio v6.0**) + Web Dashboard quản lý kênh YouTube (**ytb-tools**) cho thương hiệu **Proof of Wonder**.

## 1. Cài đặt nhanh trên bất kỳ máy mới nào (Mac / Linux)

### Yêu cầu hệ thống
- `git`, `ffmpeg` (`brew install ffmpeg` trên macOS), `python3` (`3.11+` hoặc `uv`), và `node` (`18+` cho Web UI).

### Lệnh tải toàn bộ workspace (`science-knowledge` + `ytb-tools`) & cài đặt tự động
```bash
git clone --recurse-submodules -b science-knowledge https://github.com/vipker113/ytb-tools.git science-knowledge
cd science-knowledge
chmod +x setup-studio-anywhere.sh
./setup-studio-anywhere.sh
```
*(Nếu bạn đã tách thêm repo riêng `vipker113/science-knowledge`, dùng: `git clone --recurse-submodules https://github.com/vipker113/science-knowledge.git`)*

---

## 2. Cấu trúc thư mục

- `youtube-shorts-channel/` — **Proof of Wonder Documentary Production Studio v6.0**:
  - `pipeline/pow_studio/` — Toàn bộ 6 tầng sản xuất (`story_engine.py`, `voice_studio.py`, `audio_engine.py`, `visual_intelligence.py`, `shot_planner.py`, `thumbnail_engine.py`, `compositor.py`, `qc_suite.py`, `manifest_v6.py`, `analytics_learning.py`, `cli.py`).
  - `config/profiles/` — 4 Production Profiles tái sử dụng (`cinematic_science_documentary`, `mysterious_earth_exploration`, `space_discovery`, `deep_ocean_documentary`).
  - `config/voice_profiles/` — 7 Voice Direction Presets (`mysterious_discovery`, `cinematic_documentary`, `scientific_authority`, v.v.).
  - `episodes/` — Các file cấu hình tập phim (`.yaml`) & kịch bản điều hướng giọng đọc (`.txt`).
  - `assets/fonts/` & `assets/sfx_cc0/` — Bộ font chữ chuẩn (`Anton`, `BebasNeue`, `BeVietnamPro`) và âm thanh CC0 đi kèm sẵn trong Git.
- `ytb-tools/` — Giao diện Web quản lý kênh, Backlog chủ đề, duyệt video & đồng bộ YouTube Studio (`http://localhost:3000`).

---

## 3. Lệnh dựng video trên máy mới (Quy trình 6 bước Studio v6.0)

```bash
export PY="$(pwd)/youtube-shorts-channel/.venv/bin/python"
export STUDIO="$(pwd)/youtube-shorts-channel/pipeline/pow_studio/cli.py"
export EP="$(pwd)/youtube-shorts-channel/episodes/<ten_tap_phim>.yaml"

# Bước 1: Kiểm chứng nguồn khoa học & săn cảnh quay Public Domain (NASA / NOAA / Wikimedia)
"$PY" "$STUDIO" stage1-research -m "$EP"

# Bước 2: Chấm điểm Hook mở đầu, kiểm tra nhịp giữ chân & xuất bản đồ Retention
"$PY" "$STUDIO" stage2-story -m "$EP"

# Bước 3: Sinh giọng đọc có ngữ điệu (hoặc nạp file thu âm giọng thật --upload-voice) + khóa master âm thanh 5 lớp
"$PY" "$STUDIO" stage3-voice -m "$EP" --reuse-tts --approve

# Bước 4: Đánh giá độ khớp hình ảnh, góc máy & xuất 3 phương án Thumbnail trên giao diện di động
"$PY" "$STUDIO" stage4-visual -m "$EP" --mode master

# Bước 5: Dựng video Master 1080x1920 @ 30fps (hỗ trợ cache từng cảnh SHA-256 siêu tốc)
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode master

# Bước 6: Kiểm định tự động 14 cổng chất lượng (14-Gate QA) & xuất production_manifest_v6.json
"$PY" "$STUDIO" stage6-quality -m "$EP"
```

### Khởi động giao diện Web Quản lý & Upload (`ytb-tools`)
```bash
cd ytb-tools
npm run dev
# Mở http://localhost:3000 (vào Cài Đặt để nhập lại API Key / kết nối OAuth trên máy mới)
```
