# Kairo Spark — Full Project Context & New-Machine Handoff Guide

> **Mục đích file này:** Khi chuyển sang máy mới (hoặc mở một phiên AI mới), chỉ cần đưa file này + 2 file rule trong `.agents/rules/` là AI hiểu **100% ngữ cảnh, phong cách hình ảnh, chuẩn kịch bản, quy trình giọng đọc miễn phí, bộ upscale Real-ESRGAN 4× HD, cấu trúc repo và lịch sử các tập đã làm** mà không cần giải thích lại từ đầu.

---

## 1. Nhận diện kênh & Định hướng nội dung

- **Tên kênh:** **Kairo Spark** (YouTube US English, ngách 2D Stickman Explainer dài `8–10 phút`).
- **Kênh chuẩn tham chiếu (Benchmark):** *Ink Explainer* (`@inkexplainer96`) — category `People & Blogs`, phong cách vẽ 2D Adobe Flash / Adobe Animate phẳng, nhịp cắt nhanh theo từng mệnh đề, không hiệu ứng zoom/pan giả, không màu mè AI.
- **Linh vật độc quyền (`Sticky-Note Exec` — KHÔNG BAO GIỜ viết tên nội bộ này lên trong tranh):**
  - Đầu tròn màu trắng tinh `#FFFFFF` (tuyệt đối không phủ màu kem/sepia cổ điển lên đầu).
  - Thân người que **1 nét đen liền (`|`)**, tay chân 1 nét đen đậm đều (tuyệt đối KHÔNG vẽ áo trắng dạng hình hộp hay bầu dục).
  - **Đúng 2 phụ kiện nhận diện:**
    1. Cà vạt đỏ phẳng (`#E4442E`) treo từ cổ dọc theo nét thân đen.
    2. Mẩu giấy nhớ vuông màu vàng (`#FFE600`) dán trên trán, mang ký hiệu mực đen (`?`, `!`, `?!`, `zzz`, `X`).
- **Giọng văn & Tư duy kịch bản:** Đời thường, điềm tĩnh, có quan điểm rõ ràng như một người thật đang kể điều họ thực sự quan tâm — **chống 100% văn phong AI** (cấm câu đùa gượng, cấm ẩn dụ phần mềm/tech sáo rỗng, cấm cấu trúc 7 bước lặp đều, cấm câu dẫn lố `"And here's the crazy part..."`).

---

## 2. Cấu trúc Repository & 2 File Luật Vĩnh Viễn (BẮT BUỘC ĐỌC TRƯỚC KHI LÀM TẬP MỚI)

Dự án gồm repo cha `science-knowledge` (`git@github.com:vipker113/science-knowledge.git`) chứa submodule `ytb-tools` (`git@github.com:vipker113/ytb-tools.git`):

```text
science-knowledge/
├── KAIRO_SPARK_PROJECT_CONTEXT.md          # File ngữ cảnh tổng hợp này (cũng mirror trong ytb-tools/)
├── .agents/rules/
│   ├── kairo-stickman-style.md             # 16 luật hình ảnh, phụ đề, SFX, QA, thumbnail & YouTube metadata
│   └── kairo-script-and-voice.md           # Bộ Human Writing Standard & 5 cổng kiểm duyệt kịch bản chống AI
├── youtube-shorts-channel/
│   └── assets/fonts/BeVietnamPro-Bold.ttf  # Font phụ đề pow_studio cinema_boxless
└── ytb-tools/                              # Submodule chính chứa toàn bộ production pipeline Kairo Spark
    ├── public/kairo-stickman/
    │   ├── flash-pack/                     # 12 sprite PNG trong suốt + 2 ảnh benchmark khóa phong cách 2D Flash
    │   ├── handdrawn-pack/                 # Bộ vector PyCairo
    │   └── sfx/                            # 44 file MP3 hiệu ứng âm thanh chuẩn + sfx_catalog.json
    ├── scripts/
    │   ├── kairo_chatterbox_tts.py         # TTS local miễn phí (Chatterbox TTS trên Apple Silicon MPS / CUDA)
    │   ├── kairo_realesrgan_hd.py          # Upscale neural Real-ESRGAN x4v3 (dn=0.55) -> 1080p siêu nét như vector
    │   ├── kairo_flash_sprite_extractor.py # Tách sprite RGBA trong suốt từ sheet nhân vật
    │   ├── start_flow_profile5.sh          # Khởi động Chrome CDP port 9222 cho Google Flow MCP (tùy chọn)
    │   └── models/
    │       ├── realesr-general-x4v3.pth    # Weights Real-ESRGAN 4× sắc nét (đã commit sẵn)
    │       └── realesr-general-wdn-x4v3.pth# Weights Real-ESRGAN 4× khử nhiễu JPEG (đã commit sẵn)
    └── episodes/
        ├── pilot-01-why-5-days/            # Tập #1 (HOÀN TẤT 100%)
        │   ├── audio/ref_kairo_voice_12s.wav  # File giọng mẫu 12s chuẩn Kairo Spark để Chatterbox clone (đã commit!)
        │   ├── script_elevenlabs_v2_human.md
        │   ├── build_pilot_01_video.py
        │   ├── pilot_01_subtitles.srt
        │   ├── pilot_01_thumbnail_5days_final.jpg
        │   └── YOUTUBE_UPLOAD_INFO.md
        └── ep-02-pointless-lies/           # Tập #2 (HOÀN TẤT 100%)
            ├── script_verified_human.md    # Kịch bản 1,279 từ đã qua 5 cổng Human Writing Audit
            ├── gen_ep02_full_voice.py      # Script tạo giọng full 60 đoạn Chatterbox TTS
            ├── build_ep02_full_video.py    # Pipeline chuẩn mới nhất (Real-ESRGAN 4× HD, 0 PIL slop!)
            ├── ep02_pointless_lies_subtitles.srt
            ├── ep02_thumbnail_final.jpg
            └── YOUTUBE_UPLOAD_INFO.md
```

> **Lưu ý git:** Các file nặng dẫn xuất (`.mp4`, `.wav` từng đoạn, `.mp3` full mix, `frames*/`, `scenes*/`, `.venv-chatterbox/`, `mcp-servers/`) được `.gitignore` để repo nhẹ và sạch. Toàn bộ tài sản cốt lõi (rules, scripts, 44 SFX, sprites, weights Real-ESRGAN, `ref_kairo_voice_12s.wav`, kịch bản, `.srt`, thumbnails, `YOUTUBE_UPLOAD_INFO.md`) đều đã được commit đầy đủ.

---

## 3. Các Tập Đã Sản Xuất (Episode Tracker)

| Tập | Chủ đề / Tiêu đề đề xuất | Thời lượng | Trạng thái | Ghi chú kỹ thuật |
| :--- | :--- | :--- | :--- | :--- |
| **Ep #1** | *Why Do We Work 5 Days a Week?* | `9m 01.5s` (`541.48s`) | **100% Ready to Publish** | 140 cảnh vẽ 2D Flash, 234 khung hình, 57 SFX, Thumbnail Variant 1 (`WHY DO WE HAVE TO WORK / 5 DAYS A WEEK?!`). |
| **Ep #2** | *Why Do We Lie For No Reason?* (`ep-02-pointless-lies`) | `7m 56.8s` (`476.80s`) | **100% Ready to Publish** | Kịch bản chuẩn Human Writing Standard (4 nghiên cứu: DePaulo 1996, Feldman 2002, Sharot & Garrett 2016, Aldert Vrij); giọng **Chatterbox TTS local miễn phí** clone từ `ref_kairo_voice_12s.wav`; **88 cảnh sáng tạo độc lập upscale Real-ESRGAN 4× HD (`dn=0.55`)**; **0% PIL AI slop** (bong bóng thoại vẽ tay trong tranh); `165` khung hình + `74` SFX; Thumbnail Variant 1 (`WHY DO WE LIE / FOR NO REASON?!`). |

---

## 4. Pipeline Sản Xuất Chuẩn Mới Nhất (Áp dụng từ Tập #2 trở đi)

1. **Bước 1 — Kiểm duyệt kịch bản (`kairo-script-and-voice.md`):**
   - Chạy qua 5 cổng Anti-AI: không punchline cưỡng ép, không ẩn dụ tech/software, không lặp nhịp 7 bước, không câu transition lố, không spam thẻ `[pause 0.3s]`.
   - Độ dài lý tưởng: `1,250 – 1,450` từ (`~8 – 9.5 phút`).
2. **Bước 2 — Giọng đọc 100% miễn phí bằng Chatterbox TTS (`gen_ep02_full_voice.py`):**
   - Dùng file giọng mẫu khóa chuẩn: `ytb-tools/episodes/pilot-01-why-5-days/audio/ref_kairo_voice_12s.wav`.
   - Tham số khóa chất giọng đã được duyệt: `exaggeration = 0.52 – 0.64`, `cfg_weight = 0.40`, `sr = 24000`, chuẩn hóa `-14.0 LUFS` (`loudnorm=I=-14.0:TP=-1.2:LRA=11`).
   - Chia thành ~55–65 câu/đoạn ngắn, cache từng `seg_XX.wav` để có thể resume nếu ngắt giữa chừng.
   - Chạy `faster_whisper` (`base.en`, `int8`) xuất word-level timestamps (`*_words.json`).
3. **Bước 3 — Vẽ hình ảnh 2D Adobe Flash sáng tạo & ZERO PIL Slop (`kairo-stickman-style.md`):**
   - Tham chiếu phong cách khóa: `ytb-tools/public/kairo-stickman/flash-pack/reference_flash_scenes_locked.jpg`.
   - **CẤM TUYỆT ĐỐI:** thẻ chữ PIL (`make_stamp_card`, `make_split_card`), badge PIL (`+badge:`), bong bóng thoại PIL (`+bubble`, `+bubble_right`), dấu `X`/`✓` dán bằng PIL. Mọi bong bóng thoại, biển hiệu, ký hiệu đều vẽ tự nhiên ngay trong tranh 2D Flash!
   - Khuyến khích sáng tạo mạnh về ẩn dụ thị giác (bập bênh, tường gạch, sân tennis tin nhắn, não fMRI phát sáng, tung hứng 2 quyển sách, bảng điều tra dây đỏ, bìa các-tông...).
   - Vẽ ~18–22 bảng 2×2 (72–88 cảnh độc lập) song song nhiều luồng + 1 Thumbnail 16:9 full-bleed (để trống 32% phía trên cho chữ 3D Variant 1).
4. **Bước 4 — Làm nét chuẩn vector 1080p HD bằng Real-ESRGAN 4× (`kairo_realesrgan_hd.py`):**
   - Cắt các ô nguyên bản vào `scenes_raw/`, chạy `kairo_realesrgan_hd.py --dn 0.55` (pha 45% `realesr-general-x4v3.pth` + 55% `realesr-general-wdn-x4v3.pth` → phóng 4× khử sạch nhiễu JPEG và làm sắc nét đường viền đen rồi Lanczos về `1920×1080`). Chạy trên Apple Silicon MPS chỉ mất `~0.38s/ảnh`!
5. **Bước 5 — Kiểm duyệt trực quan bắt buộc (Rule 13) → Trộn SFX → Xuất Master MP4:**
   - Chạy `--frames-only` để xuất phụ đề `pow_studio` `cinema_boxless` (`y = 918`, `BeVietnamPro-Bold 52px`, highlight vàng kim `#FFDE76`, bóng Gaussian, không hộp nền) + file `.srt` + bảng contact sheet từng Act (`verify_act_1_sheet.jpg` ...).
   - **BẮT BUỘC mở mắt kiểm tra 100% contact sheet** trước khi chạy `--encode` (`libx264`, `CRF 16`, `30fps`, `yuv420p`, `+faststart`, AAC `48kHz 192k`, trộn SFX từ `public/kairo-stickman/sfx/` ở `-16dB` đến `-20dB`, master `-14.0 LUFS`).
6. **Bước 6 — Thumbnail Variant 1 & Metadata chuẩn Ink Explainer (Rule 15 & 16):**
   - Chữ 3D `Arial Black` dày viền đen đổ bóng: Dòng 1 Trắng `#FFFFFF`, Dòng 2 Vàng `#FFE819` + Đỏ cam `#FF5C48`.
   - Danh mục YouTube: `People & Blogs`, mô tả ngắn gọn kèm `Time stamps👇🏾`, credit `🎨 Animation by Kairo Spark`, tags tập trung ngách `stickman explainer`.

---

## 5. Hướng Dẫn Cài Đặt Nhanh Trên Máy Mới (macOS Apple Silicon / Linux)

```bash
# 1. Clone repo kèm submodule ytb-tools
git clone --recurse-submodules git@github.com:vipker113/science-knowledge.git
cd science-knowledge

# Nếu đã clone rồi thì cập nhật cả repo cha + submodule:
git pull origin main && git submodule update --init --recursive

# 2. Cài FFmpeg (macOS)
brew install ffmpeg

# 3. Tạo venv cho Chatterbox TTS + Real-ESRGAN 4x (yêu cầu Python 3.11)
cd ytb-tools
uv venv .venv-chatterbox --python 3.11   # hoặc python3.11 -m venv .venv-chatterbox
uv pip install --python .venv-chatterbox/bin/python chatterbox-tts==0.1.7 torch==2.6.0 torchaudio==2.6.0 soundfile pillow numpy faster-whisper
```

> **Mẹo fix lỗi đã biết cho Chatterbox trên macOS MPS** (đã được code sẵn trong `ytb-tools/scripts/kairo_chatterbox_tts.py`):
> - Patch `torch.load` với `map_location=torch.device("mps")`.
> - Nếu `perth.PerthImplicitWatermarker is None`, gán fallback `perth.PerthImplicitWatermarker = perth.DummyWatermarker`.

---

## 6. Nâng Cấp Tương Lai Đã Kiểm Chứng (Tùy chọn: Google Flow MCP — 70/30 Hybrid Animation)

Chủ kênh có tài khoản **Google AI ULTRA (25,000 credits/tháng)** và đã test thành công tích hợp **Google Flow MCP** (`Mitanshp5/Google-Flow_MCP` v1.1.0) tạo clip hoạt hình 2D Flash `Omni 1.2 Flash` (`720p`, `8s`, `24 credits/clip`, giữ nguyên 100% nét stickman không bị méo hình!):

- **Cài trên máy mới (khi cần dùng cảnh động):**
  ```bash
  mkdir -p ytb-tools/mcp-servers && cd ytb-tools/mcp-servers
  git clone https://github.com/Mitanshp5/Google-Flow_MCP.git
  cd Google-Flow_MCP && npm install && npm run build
  ```
- **Lưu ý vận hành đã test thực chiến:**
  1. Chrome 136+ trên macOS chặn `--remote-debugging-port=9222` trên thư mục profile gốc → dùng script `ytb-tools/scripts/start_flow_profile5.sh` (tự copy profile sang `/tmp/chrome-flow-profile5-cdp`).
  2. Luôn mở URL kèm `/u/<account_index>/?hl=en` để giao diện tiếng Anh cho Playwright selector chạy 100%.
  3. Tài khoản ULTRA mặc định mở panel `Flow Agent` bên phải → cần tắt `Flow Agent` để lộ thanh tạo video trực tiếp (`Video · 720p · 8s · 16:9 · x1`).
  4. Dùng `reference_images` (chế độ Ingredients) với model `Omni 1.2 Flash` + prompt khóa: `"Flat 2D Adobe Flash stickman animation starting exactly from the reference frame, locked tripod camera, zero camera zoom or pan, crisp black outlines and solid flat colors, zero 3D shading..."`.

---

## 7. Prompt Khởi Động Nhanh Khi Chuyển Sang Máy Mới (Copy & Paste)

> *"Hãy đọc [KAIRO_SPARK_PROJECT_CONTEXT.md](KAIRO_SPARK_PROJECT_CONTEXT.md), [.agents/rules/kairo-stickman-style.md](.agents/rules/kairo-stickman-style.md), và [.agents/rules/kairo-script-and-voice.md](.agents/rules/kairo-script-and-voice.md) để nắm toàn bộ ngữ cảnh kênh YouTube stickman **Kairo Spark** (đã hoàn thành Tập #1 & Tập #2). Giờ hãy giúp tôi sản xuất **Tập #3** về chủ đề: `[nhập chủ đề]` theo đúng chuẩn Human Writing Standard + Chatterbox TTS local + 2D Flash sáng tạo + Real-ESRGAN 4× HD (0% PIL slop)."*
