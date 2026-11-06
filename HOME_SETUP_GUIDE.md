# Hướng Dẫn Cài Đặt & Sản Xuất Video Trên Máy Ở Nhà (`Proof of Wonder — Studio v9.0`)

Tài liệu này hướng dẫn từ **A → Z** cách kéo toàn bộ hệ thống **`science-knowledge`** (`Documentary Studio v9.0` + `ytb-tools` Web Dashboard) về bất kỳ máy tính mới nào ở nhà (**macOS Apple Silicon / Intel**, **Ubuntu/Linux**, hoặc **Windows WSL2**) để dựng video chuẩn kênh **Proof of Wonder** với chi phí `$0`.

> 📐 **Tài liệu kỹ thuật chuyên sâu cho Studio v9:** [youtube-shorts-channel/docs/STUDIO_V9_GUIDE.md](./youtube-shorts-channel/docs/STUDIO_V9_GUIDE.md)

---

## 1. Chuẩn bị công cụ nền tảng trên máy ở nhà (Chỉ làm 1 lần đầu)

Mở Terminal trên máy ở nhà và đảm bảo có đủ 4 công cụ cơ bản: `git`, `ffmpeg`, `python3` (`3.11+`), và `node` (`18+`).

### Trên macOS (dùng Homebrew — tự cài thêm `cairo` / `pango` khi dùng `--with-graphics`)
```bash
brew install git ffmpeg python@3.11 node uv cairo pango pkg-config
```

### Trên Ubuntu / Linux hoặc Windows (WSL2 Ubuntu)
```bash
sudo apt update
sudo apt install -y git ffmpeg python3 python3-venv python3-pip nodejs npm libcairo2-dev libpango1.0-dev pkg-config
```

> **Kiểm tra nhanh:**
> ```bash
> git --version && ffmpeg -version | head -n 1 && python3 --version && node -v
> ```

---

## 2. Tải toàn bộ Source Code & Cài đặt tự động (1 cụm lệnh)

Toàn bộ workspace `science-knowledge` (đã kèm submodule `ytb-tools`, bộ font `Anton` / `BebasNeue` / `BeVietnamPro`, kho âm thanh `CC0`, Production Profiles, 7 Voice Presets, 6 Agent Skills và kịch bản mẫu) đã nằm trên GitHub.

Chạy 3 dòng sau tại thư mục bạn muốn lưu code ở nhà:

```bash
git clone --recurse-submodules -b science-knowledge https://github.com/vipker113/ytb-tools.git science-knowledge
cd science-knowledge
./setup-studio-anywhere.sh --with-all
```

### Script `setup-studio-anywhere.sh --with-all` sẽ tự động làm gì?
1. Kiểm tra `ffmpeg` trên máy.
2. Tạo môi trường ảo `youtube-shorts-channel/.venv` (ưu tiên `Python 3.11` qua `uv`) và cài lõi `requirements.txt`.
3. Cài 3 nhóm năng lực mở rộng của **Studio v9** (có thể bật lẻ bằng `--with-ml`, `--with-graphics`, `--with-analysis`):
   - **Visual Corpus (`--with-ml`):** `torch` + `transformers` chạy `CLIP ViT-B/32` trực tiếp trên GPU Apple Silicon (`mps`, không tốn tiền API).
   - **Mechanism Overlays (`--with-graphics`):** `ManimCE` xuất đồ họa cơ chế vật lý trong suốt `.mov` (`qtrle` RGBA) dùng trực tiếp font đi kèm, **không cần cài MacTeX**.
   - **Outlier Analyst (`--with-analysis`):** `yt-dlp`, `scenedetect`, `youtube-transcript-api` để phân tích nhịp cắt cảnh đối thủ và tự xóa file video tạm sau khi trích chỉ số.
4. Chạy thử `cli.py profiles` và cài `npm install` cho `ytb-tools`.

*(Tuỳ chọn: Nếu bạn có khóa miễn phí của Cục Lưu trữ Quốc gia Hoa Kỳ `NARA`, thêm `export NARA_API_KEY="..."` vào `~/.zshrc` để tự động mở nguồn tư liệu thứ 8).*

---

## 3. Khởi động Web Dashboard (`ytb-tools`) & Kết nối Kênh YouTube

Vì lý do bảo mật, toàn bộ **API Key, OAuth Client Secret và Token đăng nhập kênh YouTube** (`ytb-tools/data/ytb-growth-db.json` & `.env*`) không đưa lên GitHub.

### Bước 3.1: Bật Web UI
```bash
cd science-knowledge/ytb-tools
npm run dev
```
Mở trình duyệt vào địa chỉ: **`http://localhost:3000`**

### Bước 3.2: Ba khu vực làm việc chính trên `ytb-tools` (Studio v9)
1. **Ý Tưởng & Đối Thủ (`Outlier Hunter`):** Bấm nút **Giải phẫu nhịp dựng** trên bất kỳ video đối thủ nào để xem thanh timeline cắt cảnh theo lớp chuyển động, bảng chỉ số 4 pha (`0–3s / 3–15s / 15–35s / 35s+`), so sánh với trung vị kênh mình và bấm **Lưu ý tưởng kèm giải phẫu**.
2. **Bàn Dựng (`Studio Backlot`):** Theo dõi trực tiếp tiến độ dựng tập phim qua `SSE` (`< 2s` không cần tải lại trang), xem filmstrip `IN/MID/OUT` của từng cảnh kèm lớp phủ ManimCE, kiểm tra giấy phép + điểm `CLIP`, ghi chú sửa từng shot hoặc bấm **Duyệt Master** để mở khóa cổng render `1080x1920`.
3. **Duyệt & Đăng Video (`Mac Studio Review`):** Xem video Master đã qua 14 cổng kỹ thuật + 6 trụ QA, chọn Thumbnail (`A / B / C`) và bấm **Lưu Bản Nháp** hoặc **Đăng Video** lên YouTube Studio.

### Bước 3.3: Nhập lại Khóa API & Kết nối YouTube Studio trên máy mới
1. Bấm **Cài Đặt (Settings)** ở góc trên phải `http://localhost:3000`.
2. Nhập `GEMINI_API_KEY` (tuỳ chọn cho gợi ý chủ đề trên web), `YOUTUBE_API_KEY`, và Google OAuth (`Authorized redirect URI`: `http://localhost:3000/api/youtube/oauth/callback`).

---

## 4. Hai Cách Dựng Video Trên Máy Ở Nhà

### Cách A — Dùng cùng Antigravity IDE (Tự động nạp `.agents/skills/pow-*`)
1. Mở **Antigravity** → **Open Folder** chọn thư mục `science-knowledge`.
2. Hệ thống tự động nạp luật bảo vệ `.agents/rules/pow-guardrails.md` và 6 kỹ năng `pow-*`. Bạn chỉ cần nhắn chủ đề (ví dụ: *"Sản xuất tập mới về NASA Parker Solar Probe bay xuyên vành nhật hoa 1,000,000°C theo quy trình Studio v9"*): Agent sẽ tự tìm tư liệu `$0`, nạp Visual Corpus, kiểm tra `feasibility`, sinh giọng đọc rồi dừng đúng tại cổng nghe giọng & cổng duyệt **Studio Backlot** cho bạn quyết định.

### Cách B — Chạy Trực Tiếp Bằng Dòng Lệnh (`Studio v9.0 CLI`)
```bash
cd science-knowledge/youtube-shorts-channel
export PY=".venv/bin/python"
export STUDIO="pipeline/pow_studio/cli.py"
export EP="episodes/space_parker_solar_probe_v9_documentary.yaml"

# 1. Khớp nhịp Visual Corpus & kiểm tra cổng khả thi + bản quyền
"$PY" "$STUDIO" match-beats -m "$EP"
"$PY" "$STUDIO" feasibility -m "$EP" --out-dir output/space-and-universe/parker-solar-probe-corona-v9/planning
"$PY" "$STUDIO" stage1-research -m "$EP"

# 2. Chấm điểm kịch bản & sinh giọng đọc 5 lớp âm thanh
"$PY" "$STUDIO" stage2-story -m "$EP"
"$PY" "$STUDIO" stage3-voice -m "$EP"
# Nghe thử work_audio/narration_norm.wav rồi khóa giọng:
"$PY" "$STUDIO" voice-approve -m "$EP" --note "Approved"

# 3. Render ManimCE overlays, lập khung hình & đẩy bảng phân cảnh lên Studio Backlot
"$PY" "$STUDIO" render-overlays -m "$EP"
"$PY" "$STUDIO" stage4-visual -m "$EP" --mode draft
"$PY" "$STUDIO" optimize-scenes -m "$EP"
"$PY" "$STUDIO" plan-soundscape -m "$EP"
"$PY" "$STUDIO" export-storyboard -m "$EP"

# 4. Vào http://localhost:3000 -> tab "Studio Backlot" bấm "Duyệt Master", sau đó render Master + QA 6 trụ:
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode master
"$PY" "$STUDIO" stage6-quality -m "$EP"
"$PY" "$STUDIO" qa-6pillar -m "$EP" --out-dir output/space-and-universe/parker-solar-probe-corona-v9/qa
"$PY" "$STUDIO" creative-qc -m "$EP"
```

---

## 5. Kiểm Tra Hệ Thống & Xử Lý Lỗi Thường Gặp

1. **Chạy toàn bộ bộ kiểm thử tự động Studio v6–v9 (`79+` tests):**
   ```bash
   cd science-knowledge/youtube-shorts-channel
   .venv/bin/pytest pipeline/tests -q
   ```
2. **Lỗi cổng `3000` đang bận khi chạy `npm run dev`:**
   - Giải phóng cổng `3000`: `lsof -ti:3000 | xargs kill -9` rồi chạy lại `npm run dev`.
3. **`stage5-edit --mode master` báo bị chặn bởi cổng Storyboard:**
   - Đây là cơ chế bảo vệ chuẩn của `manifest_version: "9.0"` (`require_storyboard_approval: true`). Mở `http://localhost:3000` → tab **Studio Backlot** → chọn tập phim → bấm **Duyệt Master** (hoặc chạy bản nháp `--mode draft` để xem trước mà không cần mở khóa).
