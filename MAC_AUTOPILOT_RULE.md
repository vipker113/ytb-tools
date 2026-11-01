# SubPulse Autopilot — Quy Chuẩn Tích Hợp Pipeline Video Gốc Trên Mac (100% Miễn Phí 0₫)

Tài liệu này định nghĩa ranh giới rõ ràng khi chạy mã nguồn **SubPulse Autopilot** trên máy Mac cho kênh **`Proof of Wonder (@proofofwonderscience)`** (`UCtUnbMhnWa2O2RLTcXqC2yQ`).

> [!IMPORTANT]
> **NGUYÊN TẮC BẮT BUỘC DÀNH CHO AGENT TRÊN MAC:**
> 1. **TUYỆT ĐỐI KHÔNG** gọi Google Cloud Vertex AI hay bất kỳ dịch vụ trả phí nào có thể phát sinh cước thẻ tín dụng. Toàn bộ Web App chỉ dùng **YouTube Data API v3, OAuth 2.0 và Gemini Free API (0₫)**.
> 2. **Giữ nguyên 100% chất lượng hình ảnh, chuyển động, nhịp dựng, âm thanh và phong cách sản xuất của kịch bản tạo video gốc có sẵn trên máy Mac của người dùng.** Không tự dựng slideshow FFmpeg sơ sài để thay thế.

---

## 1. Phân Vai Rõ Ràng Giữa Web App & Kịch Bản Video Trên Mac

### A. Vai trò của Web App (`ytb-tools`) — Bộ Não Dữ Liệu & Tự Động Đăng Kênh (0₫):
1. **Quét dữ liệu thật & Săn Outliers:** Theo dõi kênh `@proofofwonderscience` và 150 video từ 5 kênh đối thủ lớn (`@CleoAbram`, `@AstroKobi`, `@zackdfilms`, `@BeSmart`, `@MinuteEarth`).
2. **Lập kế hoạch Sprint 5 ngày & Cấp đề tài chuẩn SEO Mỹ:**
   - Endpoint lấy đề tài tự động cho Mac: `GET http://localhost:3000/api/pipeline` (trả về `nextEpisode`: `episodeId`, `title`, `hook3s`, `voiceoverScript`, `fullNarration`, `description`, `tags`, `pinnedComment`).
3. **Upload & Hẹn Giờ Thẳng Lên YouTube Studio (OAuth 2.0 đã kết nối sẵn trong `data/ytb-growth-db.json` — Miễn phí 0₫):**
   - Qua giao diện Web (`DailyCockpitTab.tsx`): Chọn file `.mp4` thành phẩm ở **Bước 2** để đẩy thẳng lên YouTube Studio.
   - Hoặc qua script/CLI tự động trên Mac: gửi `FormData` (`file`, `publishMode="schedule_golden"`, `episodeId`, `title`, `description`, `tags`, `pinnedComment`) tới `POST http://localhost:3000/api/youtube/upload` (hoặc tạo nút bấm trên Web gọi trực tiếp sang script tạo video trên Mac của người dùng).
   - Tự động hẹn đúng giờ vàng **`17:15 Giờ VN` (`10:15 UTC`)**, tự điền toàn bộ Metadata và tự động nhảy sang bài tiếp theo trong Sprint!

### B. Vai trò của Kịch Bản Tạo Video Trên Mac — Xưởng Sản Xuất `.MP4` Duy Nhất:
- Đảm nhận **100% khâu tạo video `.mp4`** theo đúng rule/workflow chất lượng cao mà người dùng đã xây dựng trên Mac.
- Không kích hoạt hay sử dụng bất kỳ tài khoản thanh toán Vertex AI trả phí nào.

---

## 2. Các Quy Tắc Chiến Lược Nội Dung & Đăng Bài Từ 160 Video Thật

Khi Web App cấp đề tài/metadata sang cho pipeline Mac (hoặc khi lên lịch đăng bài lên YouTube Studio), giữ các thông số dữ liệu đã kiểm chứng sau:
- **Thời lượng tối ưu trên Shorts Khoa học Mỹ:** Nhắm khoảng **`45s – 55s`** (nhóm `45–65s` có điểm Outlier cao hơn `+33%` so với video quá dài).
- **Tiêu đề (Title):** Tiếng Anh Mỹ sạch, khơi gợi nghịch lý/tò mò mạnh, **KHÔNG gắn `#hashtag` trên tiêu đề** (`0/25` top Outliers dùng hashtag ở tiêu đề).
- **Hook 0–3s & CTA & Loop trong lời dẫn:** Mở đầu trực diện vào nghịch lý vật lý (tránh chào hỏi rườm rà), lồng tự nhiên lời nhắc đăng ký kênh ở cao trào nội dung, và ưu tiên câu kết tạo vòng lặp mượt về đầu video.
- **Mô tả (Description) & Khung giờ đăng:** Kèm nguồn tham chiếu khoa học thật (`NASA`, `ESA`, `MIT`, `Nature`...) và hẹn giờ xuất bản tại khung giờ vàng của kênh **`17:15 Giờ VN`**.
