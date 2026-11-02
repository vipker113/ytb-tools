# Hướng Dẫn Cài Đặt & Sản Xuất Video Trên Máy Ở Nhà (`Proof of Wonder — Studio v6.0`)

Tài liệu này hướng dẫn từ **A → Z** cách kéo toàn bộ hệ thống **`science-knowledge`** (`Documentary Studio v6.0` + `ytb-tools` Web Dashboard) về bất kỳ máy tính mới nào ở nhà (**macOS**, **Ubuntu/Linux**, hoặc **Windows WSL2**) để dựng video chuẩn kênh **Proof of Wonder** với chi phí `\$0`.

---

## 1. Chuẩn bị công cụ nền tảng trên máy ở nhà (Chỉ làm 1 lần đầu)

Mở Terminal trên máy ở nhà và đảm bảo có đủ 4 công cụ cơ bản: `git`, `ffmpeg`, `python3` (`3.11+`), và `node` (`18+`).

### Trên macOS (dùng Homebrew)
```bash
brew install git ffmpeg python@3.11 node uv
```

### Trên Ubuntu / Linux hoặc Windows (WSL2 Ubuntu)
```bash
sudo apt update
sudo apt install -y git ffmpeg python3 python3-venv python3-pip nodejs npm
```

> **Kiểm tra nhanh:**
> ```bash
> git --version && ffmpeg -version | head -n 1 && python3 --version && node -v
> ```

---

## 2. Tải toàn bộ Source Code & Cài đặt tự động (1 cụm lệnh)

Toàn bộ workspace `science-knowledge` (đã kèm submodule `ytb-tools`, bộ font `Anton` / `BebasNeue` / `BeVietnamPro`, kho âm thanh `CC0`, 4 Production Profiles, 7 Voice Presets và kịch bản mẫu) đã nằm trên GitHub.

Chạy đúng 3 dòng sau tại thư mục bạn muốn lưu code ở nhà:

```bash
git clone --recurse-submodules -b science-knowledge https://github.com/vipker113/ytb-tools.git science-knowledge
cd science-knowledge
./setup-studio-anywhere.sh
```

### Script `setup-studio-anywhere.sh` sẽ tự động làm gì?
1. Kiểm tra `ffmpeg` trên máy.
2. Tạo môi trường ảo `youtube-shorts-channel/.venv` và cài toàn bộ thư viện Python trong `youtube-shorts-channel/requirements.txt` (`edge-tts`, `faster-whisper`, `onnxruntime`, `opencv-python-headless`, `pillow`, `pydantic`, `scipy`, v.v.).
3. Chạy thử `cli.py profiles` để xác nhận **Studio v6.0** hoạt động hoàn hảo.
4. Vào thư mục `ytb-tools` chạy `npm install` để cài đặt Web Dashboard.

*(Lưu ý: Model tách lớp chiều sâu `Depth-Anything-V2-Small FP16 ONNX` nặng `~50 MB` không đẩy lên Git cho nhẹ kho code — hệ thống sẽ **tự động tải từ Hugging Face** ngay lần đầu bạn dựng cảnh có hiệu ứng chiều sâu 2.5D).*

---

## 3. Khởi động Web Dashboard (`ytb-tools`) & Kết nối lại API / Kênh YouTube

Vì lý do bảo mật, toàn bộ **API Key, OAuth Client Secret và Token đăng nhập kênh YouTube** (`ytb-tools/data/ytb-growth-db.json` & `.env*`) được chặn không đưa lên GitHub.

### Bước 3.1: Bật Web UI
```bash
cd science-knowledge/ytb-tools
npm run dev
```
Mở trình duyệt vào địa chỉ: **`http://localhost:3000`**

### Bước 3.2: Nhập lại Khóa API & Kết nối YouTube Studio trên máy ở nhà
1. Trên giao diện `http://localhost:3000`, bấm vào nút **Cài Đặt (Settings)** ở góc trên phải (hoặc tạo file `ytb-tools/.env.local` với `GEMINI_API_KEY=...` và `YOUTUBE_API_KEY=...`).
2. Nhập:
   - **Gemini API Key** (để dùng tính năng gợi ý chủ đề giữ chân & viết kịch bản AI).
   - **YouTube Data API v3 Key** (để quét kênh, đối thủ & từ khóa).
   - **Google OAuth Client ID & Client Secret** (để đồng bộ Analytics thật, chọn Playlist và bấm **Lưu Nháp / Đăng Video trực tiếp lên YouTube Studio**).
3. Đảm bảo trong Google Cloud Console của bạn đã khai báo **Authorized redirect URI**:
   ```text
   http://localhost:3000/api/youtube/oauth/callback
   ```
4. Bấm **Kết nối OAuth YouTube** → chọn kênh **Proof of Wonder** → bấm **Đồng bộ Kênh**.

> **Mẹo mang nguyên Kho Backlog & Cấu hình sang máy ở nhà:**
> Nếu bạn muốn giữ nguyên 100% cấu hình + danh sách Backlog cá nhân mà không cần nhập lại, chỉ cần chép riêng file `ytb-tools/data/ytb-growth-db.json` qua USB/AirDrop/Google Drive cá nhân vào đúng đường dẫn `science-knowledge/ytb-tools/data/ytb-growth-db.json` trên máy ở nhà (tuyệt đối không đưa file này lên Git công khai).

---

## 4. Hai Cách Dựng Video Trên Máy Ở Nhà

### Cách A — Nhanh & Tự Động Nhất (Dùng cùng Antigravity IDE ở nhà)

1. Mở ứng dụng **Antigravity** trên máy ở nhà → **Open Folder** chọn thư mục `science-knowledge` vừa clone.
2. Nếu bạn muốn dựng ngay **tập Tam Giác Quỷ (Bermuda Triangle)** đã được chuẩn bị sẵn kịch bản trên GitHub (`youtube-shorts-channel/episodes/bermuda_abyss_v6_voice_script.txt`), chỉ cần nhắn cho Antigravity câu lệnh sau:

```text
Hãy dựng hoàn chỉnh tập phim tài liệu Tam Giác Quỷ từ kịch bản có sẵn tại youtube-shorts-channel/episodes/bermuda_abyss_v6_voice_script.txt bằng quy trình 6 bước của Studio v6.0 (profile deep_ocean_documentary, voice mysterious_discovery). Thumbnail dùng Concept C chèn chữ lớn ("8,300M UNDER / BERMUDA" trên ảnh chụp xác tàu đắm dưới đèn xanh biển sâu của NOAA). Tải tư liệu thật từ NOAA / USGS / USCG, chạy đủ 14 cổng kiểm định QA và xuất ra youtube-shorts-channel/output để tôi duyệt trên ytb-tools.
```

3. Hoặc với bất kỳ chủ đề mới nào từ tab **Ý Tưởng & Đối Thủ (`Backlog`)** trên `http://localhost:3000`, bấm nút **Copy Lệnh Dựng** và dán thẳng vào Antigravity!

---

### Cách B — Chạy Trực Tiếp Bằng Dòng Lệnh (`Studio v6.0 CLI` — 6 Bước Chuẩn)

Mở Terminal tại thư mục gốc `science-knowledge`:

```bash
export PY="$(pwd)/youtube-shorts-channel/.venv/bin/python"
export STUDIO="$(pwd)/youtube-shorts-channel/pipeline/pow_studio/cli.py"

# Xem danh sách 4 Production Profiles & 7 Voice Presets có sẵn
"$PY" "$STUDIO" profiles
```

#### Bước 0 (Tuỳ chọn): Dựng thử lại tập mẫu `Blood Falls v6 Pilot` để kiểm tra máy mới
*(Lưu ý: Trên máy mới thư mục `assets/raw_footage/` đang trống để nhẹ Git; khi tạo tập mới hệ thống sẽ tải cảnh quay thật từ Wikimedia Commons / NASA / NOAA lưu vào `assets/raw_footage/<ten_tap>/`).*

#### Quy trình 6 Bước cho một file cấu hình tập phim (`$EP`)
```bash
export EP="$(pwd)/youtube-shorts-channel/episodes/<ten_file_tap_phim>.yaml"

# BƯỚC 1: Kiểm tra bản quyền tư liệu & chấm điểm cơ hội chủ đề (Topic Opportunity)
"$PY" "$STUDIO" stage1-research -m "$EP"

# BƯỚC 2: Chấm điểm 3 phương án mở đầu (0-3s Hook), kiểm tra nhịp giữ chân & chống văn phong AI
"$PY" "$STUDIO" stage2-story -m "$EP"

# BƯỚC 3A: Sinh giọng đọc TTS có đạo diễn ngữ điệu (nhấn chữ, ngắt nhịp tự nhiên) + trộn âm thanh 5 lớp (-16 LUFS)
"$PY" "$STUDIO" stage3-voice -m "$EP" --approve

# (HOẶC BƯỚC 3B — Nếu bạn tự thu âm giọng thật bằng mic riêng):
# "$PY" "$STUDIO" stage3-voice -m "$EP" --upload-voice "/duong/dan/giong_thu_am.wav" --approve

# BƯỚC 4: Đánh giá độ khớp Lời thoại ↔ Hình ảnh, góc máy & xuất 3 phương án Thumbnail trên khung điện thoại
"$PY" "$STUDIO" stage4-visual -m "$EP" --mode master

# BƯỚC 5: Dựng video
# - Chạy bản nháp 540x960 siêu nhanh để xem thử nhịp cắt cảnh:
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode draft
# - Khi ưng ý, xuất bản Master 1080x1920 @ 30fps (tự động cache SHA-256 từng cảnh):
"$PY" "$STUDIO" stage5-edit -m "$EP" --mode master

# BƯỚC 6: Chạy 14 cổng kiểm định chất lượng tự động (14-Gate QA) & xuất hồ sơ cho Web UI
"$PY" "$STUDIO" stage6-quality -m "$EP"
```

Sau khi **Bước 6** báo `14/14 PASS`:
- Mở tab **Duyệt & Đăng Video (Mac Studio Review)** trên `http://localhost:3000` → bấm **Quét lại Output**.
- Xem trực tiếp video, nghe âm thanh, chọn Thumbnail (`Primary` / `Variant B` / `Variant C`), chọn Playlist (ví dụ: *Hidden Earth* hoặc *Deep-Sea Mysteries*) và bấm **Lưu Bản Nháp (Draft)** hoặc **Đăng Công Khai** lên YouTube Studio!

---

## 5. Cách Cập Nhật & Đồng Bộ Code Giữa Máy Công Ty ↔ Máy Ở Nhà

### Khi ngồi vào máy ở nhà (kéo thay đổi mới nhất từ GitHub về)
```bash
cd science-knowledge
git pull github-ytb science-knowledge || git pull origin science-knowledge
git submodule update --init --recursive --remote
```

### Khi làm xong việc ở nhà muốn đẩy code/kịch bản mới lên lại GitHub
1. Nếu có sửa code trong `ytb-tools`:
   ```bash
   cd science-knowledge/ytb-tools
   git add .
   git commit -m "update: cap nhat ytb-tools tu may o nha"
   git push origin main
   ```
2. Đẩy kịch bản `.yaml` / `.txt` hoặc code `Studio v6.0` từ thư mục gốc `science-knowledge`:
   ```bash
   cd science-knowledge
   git add .
   git commit -m "feat: them kich ban va cap nhat studio tu may o nha"
   git push origin HEAD:science-knowledge
   ```

---

## 6. Kiểm Tra Hệ Thống & Xử Lý Lỗi Thường Gặp (Troubleshooting)

1. **Chạy bộ kiểm thử tự động (20 Unit Tests) để chắc chắn máy ở nhà cài đúng 100%:**
   ```bash
   cd science-knowledge
   ./youtube-shorts-channel/.venv/bin/python -m pytest youtube-shorts-channel/pipeline/tests/test_pow_studio_v6.py -q
   ```
   *(Kết quả hiện `20 passed` là toàn bộ hệ thống hoạt động chuẩn xác).*

2. **Lỗi cổng `3000` đang bận khi chạy `npm run dev`:**
   - Tắt tiến trình cũ đang chiếm cổng `3000`: `lsof -ti:3000 | xargs kill -9` rồi chạy lại `npm run dev` (nên giữ đúng cổng `3000` để khớp với Google OAuth Redirect URI).

3. **Lỗi `Permission denied (publickey)` khi `git push` trên máy ở nhà:**
   - Vì khi clone bằng link `https://github.com/vipker113/ytb-tools.git`, bạn có thể đăng nhập bằng GitHub Personal Access Token (PAT) hoặc cài GitHub CLI (`gh auth login`) trên máy ở nhà để push cực nhanh mà không cần cấu hình SSH key thủ công.

4. ** Web UI báo không thấy tập video nào trong tab Duyệt Video:**
   - Đó là bình thường khi mới clone về (vì các file `.mp4` nặng hàng GB không lưu trên Git). Ngay sau khi bạn dựng xong tập đầu tiên vào `youtube-shorts-channel/output/...`, bấm nút **Làm mới / Quét lại** trên Web UI là tập phim sẽ hiện lên đầy đủ kèm bảng điểm 14 cổng QA.
