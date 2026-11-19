# ⚡ Tài Liệu Toàn Diện: Hệ Thống Video Tiến Hóa Sức Mạnh Theo Tương Tác Thời Gian Thật (Interactive KI Evolution Studio)

Tài liệu này tổng hợp đầy đủ **ý tưởng cốt lõi, tâm lý học tăng trưởng YouTube, công thức tính điểm KI, kiến trúc kỹ thuật 2.5D Character Idle, cơ chế cập nhật Tiêu đề Realtime qua YouTube Data API v3, bộ Prompt tạo nhân vật mới (Luffy, Naruto, Vegeta...)** và **quy trình vận hành chuẩn (SOP)** để sản xuất chuỗi video tự động kéo View, Like, Comment và Subscribe.

---

## 1. Tổng Quan Ý Tưởng & Cơ Chế Viral ("Gamified VOD Series")

Thay vì đăng một video thụ động thông thường hoặc phải treo máy Livestream 24/7 tốn tài nguyên, mô hình **Interactive KI Power Evolution** biến mỗi video ngang `16:9` (`1920×1080`) thành một **"Trò chơi cộng đồng tích lũy năng lượng"**:

1. **Trạng thái nhân vật sống động (`2.5D Character Idle`):** Video dài `12–45 giây` hiển thị nhân vật ở tư thế đứng gồng năng lượng sống động (ngực và vai hít thở nhịp nhàng, tóc/đai áo bay nhẹ theo gió, hào quang Ki bốc lửa gợn sóng, hạt tinh thể năng lượng bay lên và tia sét điện xẹt quanh người) — tuyệt đối không đứng đơ như ảnh tĩnh.
2. **Bố cục trực quan trong 0.5 giây đầu tiên (trên cả Thumbnail lẫn Video):**
   - **Khung Trái:** Hình dạng **Hiện Tại** của nhân vật (VD: *Goku — Base Form*).
   - **Khung Giữa:** Mũi tên tiến hóa chỉ rõ **Mốc KI Mục Tiêu** (VD: `10,000 KI ➡️`) kèm **Bảng Quy Đổi Tương Tác** (`View`, `Like`, `Comment`, `Subscribe`).
   - **Khung Phải:** Hình dạng **Cấp Tiếp Theo** sẽ mở khóa khi chạm mốc (hiển thị lộ diện rực rỡ hoặc ẩn dưới dạng **Bóng Đen Bí Ẩn `?`**).
   - **Thanh Lộ Trình Đáy:** Hiển thị toàn bộ 6 bậc tiến hóa từ cấp 1 đến cấp tối thượng.
3. **Phản hồi thời gian thật trên Tiêu Đề YouTube (`Realtime Dynamic Title`):**
   - Hệ thống ngầm liên tục quét chỉ số thật của video và cập nhật tổng điểm `KI` thẳng lên **Tiêu đề video YouTube** (VD: `⚡ CURRENT KI: 6,420 / 10,000 | Help Goku Unlock Kaioken x20! 🔥`).
   - Bất kỳ khán giả nào F5 trang hoặc quay lại kiểm tra sau vài phút đều thấy con số `KI` tăng lên thật nhờ đóng góp của mình.
4. **Chuỗi Tập Tiến Hóa Liên Hoàn (`Episodic Flywheel`):**
   - Không cần đổi lại nội dung video cũ; ngay khi video Tập 1 chạm đủ mốc `KI`, bạn bấm 1 nút để xuất **Tập 2** với nhân vật đã biến hình sang cấp mới + đặt cột mốc `KI` cao hơn gấp 3–4 lần.

---

## 2. Công Thức Tính Điểm `KI` & Thiết Kế Cột Mốc Chuẩn

### 2.1. Công thức toán học
`KI = (Views × w_view) + (Likes × w_like) + (Comments × w_comment) + (GainedSubs × w_sub)`

Trọng số mặc định (có thể tùy chỉnh tự do trên giao diện):
- **👁️ 1 View:** `+1 KI`
- **👍 1 Like:** `+20 KI`
- **💬 1 Comment:** `+50 KI`
- **🔔 1 Subscribe:** `+200 KI` (tính từ độ chênh lệch `currentChannelSubs - baselineSubscribers` tại thời điểm bắt đầu theo dõi tập đó).

### 2.2. Bảng gợi ý đặt Cột Mốc KI

| Tập | Chuyển đổi hình dạng | Kênh Mới (< 1K Subs) | Kênh Đang Lên (1K – 20K Subs) |
| :---: | :--- | :---: | :---: |
| **Tập 1** | `Base Form` ➔ `Kaioken x20` | `2,500` – `5,000 KI` | `10,000` – `25,000 KI` |
| **Tập 2** | `Kaioken x20` ➔ `Super Saiyan 1` | `10,000` – `15,000 KI` | `50,000` – `75,000 KI` |
| **Tập 3** | `Super Saiyan 1` ➔ `Super Saiyan 3` | `30,000` – `50,000 KI` | `150,000` – `250,000 KI` |
| **Tập 4** | `Super Saiyan 3` ➔ `Super Saiyan Blue` | `100,000 KI` | `500,000 KI` |
| **Tập 5** | `Super Saiyan Blue` ➔ `Ultra Instinct` | `250,000 KI` | `1,000,000 KI` |

---

## 3. Kiến Trúc Kỹ Thuật & Toán Học Quota YouTube API

1. **Engine `2.5D Character Idle` (`scripts/render_ki_idle_video.py`):**
   - Tách 5 lớp mặt nạ giải phẫu học (`face_protect`, `chest_mask`, `wind_mask`, `aura_ring_mask`, `particles` + `lightning`) bằng `cv2.remap`.
   - Dựng vòng lặp liền mạch `90 frames` (`3.0s @ 30fps`) bằng `h264_videotoolbox` và ghép âm thanh `0%` bản quyền.
2. **Kiến Trúc 3 Tầng Tối Ưu Quota (`src/lib/ki-challenge-server.ts` & `/ki-live`):**
   - **Đồng bộ số liệu mỗi 5 phút (`288 lần/ngày`):** `videos.list` (`1 unit`) + `channels.list` (`1 unit`) = **`576 units/ngày/video`**.
   - **Thanh KI Realtime trên Website riêng (`/ki-live` & `/ki-live?v=<videoId>`):** Hiển thị thanh năng lượng KI chi tiết từng điểm tự làm mới mỗi 15 giây, tốn **`0` YouTube Quota**.
   - **Tiêu đề YouTube chỉ đổi ở 4 mốc `25%`, `50%`, `75%`, `100%`:** Cả vòng đời video chỉ gọi `PUT videos.update` tối đa **4 lần = `200 units` tổng cộng**, loại bỏ hoàn toàn nguy cơ vượt trần `10,000 units/ngày`.

---

## 4. Quy Trình Vận Hành Từng Bước (SOP)

1. Mở `http://localhost:3000/?tab=ki` (**Thử Thách KI Tiến Hóa**).
2. Chọn ngôn ngữ (`English Global` hoặc `Tiếng Việt`), chọn cấp **Hiện tại** (Trái) & **Mốc tiếp theo** (Phải), đặt `Target KI` và hệ số quy đổi.
3. Bấm **"1. Dựng Video Idle 1080p (.MP4) + Thumbnail (.JPG)"**.
4. Bấm **"Đăng Lên YouTube & Tự Động Cập Nhật KI Ở Tiêu Đề Ngay!"** (hoặc tải file tự đăng rồi dán Link vào ô **Gắn Auto-KI**).
5. Khi đạt `100%` mốc KI, bấm nút **"Chuyển Lên Dựng Tập Tiếp Theo"** để xuất video nhân vật ở hình dạng mới kèm cột mốc mới!

---

## 5. Mẫu Prompt Tạo Thêm Bộ Nhân Vật Mới (Luffy, Naruto, Vegeta...)

```text
Stylized 3D-cel-shaded anime portrait, 3:4 vertical framing, waist-up heroic front-facing stance, centered character, clean dark starry cosmic arena background, no text, no watermark:
[Mô tả nhân vật + trang phục cố định + màu tóc/mắt/hào quang của từng cấp độ]
```

---

## 6. Danh Mục File Mã Nguồn

- `scripts/render_ki_idle_video.py` — Engine 2.5D Character Idle & xuất MP4 1080p
- `src/lib/ki-challenge-server.ts` — Quản lý bộ đếm KI, Daemon ngầm & YouTube API sync
- `src/app/api/ki-challenge/route.ts` — REST API cho Studio & Tracker
- `src/components/KiChallengeStudioTab.tsx` — Giao diện Canvas 1920×1080 & Dashboard theo dõi KI
- `public/ki-challenge/goku/stage_1_base.jpg` .. `stage_6_ultra_instinct.jpg` — Bộ 6 cấp Goku AI có sẵn
