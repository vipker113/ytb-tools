# SubPulse Autopilot — Quy Chuẩn Tích Hợp Pipeline Video Gốc Trên Mac

Tài liệu này định nghĩa ranh giới rõ ràng khi chạy mã nguồn **SubPulse Autopilot** trên máy Mac cho kênh **`Proof of Wonder (@proofofwonderscience)`** (`UCtUnbMhnWa2O2RLTcXqC2yQ`).

> [!IMPORTANT]
> **NGUYÊN TẮC BẮT BUỘC DÀNH CHO AGENT TRÊN MAC:**
> 1. **TUYỆT ĐỐI KHÔNG** sử dụng logic dựng slideshow FFmpeg sơ sài (`zoompan`, `aevalsrc`, phụ đề `.ass` cơ bản) đang nằm tạm trong `src/lib/video-generator.ts`. Hãy **XÓA BỎ HOÀN TOÀN** phần logic render tạm đó và **THAY THẾ 100%** bằng kịch bản/pipeline dựng video gốc có sẵn trên máy Mac của người dùng!
> 2. **Giữ nguyên 100% chất lượng hình ảnh, chuyển động, nhịp dựng, âm thanh và phong cách sản xuất của kịch bản tạo video trên Mac.** Không tự ý cắt giảm hay thay đổi quy trình dựng video gốc của Mac.

---

## 1. Phân Vai Rõ Ràng Giữa Web App & Kịch Bản Video Trên Mac

### A. Vai trò của Web App (`ytb-tools`) — Bộ Não Dữ Liệu & Tự Động Đăng Kênh:
1. **Quét dữ liệu thật & Săn Outliers:** Theo dõi kênh `@proofofwonderscience` và 150 video từ 5 kênh đối thủ lớn (`@CleoAbram`, `@AstroKobi`, `@zackdfilms`, `@BeSmart`, `@MinuteEarth`).
2. **Lập kế hoạch Sprint 5 ngày & Cấp đề tài chuẩn SEO Mỹ:**
   - Endpoint lấy đề tài tự động cho Mac: `GET http://localhost:3000/api/pipeline` (trả về `nextEpisode`: `episodeId`, `title`, `hook3s`, `voiceoverScript`, `description`, `tags`, `pinnedComment`).
3. **Upload & Hẹn Giờ Thẳng Lên YouTube Studio (OAuth 2.0 đã kết nối sẵn trong `data/ytb-growth-db.json`):**
   - Endpoint nhận file `.mp4` thành phẩm từ Mac để đẩy thẳng lên kênh `@proofofwonderscience`:
     - Qua giao diện nút bấm trên Web (`DailyCockpitTab.tsx`): `POST /api/video/generate` (gọi hàm `generateCompleteShortMp4` trong `src/lib/video-generator.ts`) hoặc chọn file `.mp4` upload tại Bước 2 (`POST /api/youtube/upload`).
     - Qua script/CLI tự động trên Mac: gửi `FormData` (`file`, `publishMode="schedule_golden"`, `episodeId`, `title`, `description`, `tags`, `pinnedComment`) tới `POST http://localhost:3000/api/youtube/upload`.
   - Tự động hẹn đúng giờ vàng **`17:15 Giờ VN` (`10:15 UTC`)**, tự điền toàn bộ Metadata và tự động nhảy sang bài tiếp theo trong Sprint!

### B. Vai trò của Kịch Bản Tạo Video Trên Mac — Xưởng Sản Xuất `.MP4` Duy Nhất:
- Đảm nhận **100% khâu tạo video `.mp4`** theo đúng rule/workflow chất lượng cao mà người dùng đã xây dựng trên Mac.
- Có sẵn quyền truy cập gói **`$300` Google Cloud Vertex AI** tại `data/vertex-service-account.json` (`project_id: "starlit-cocoa-513211-p9"`, đã cấp quyền IAM chạy trực tiếp `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.8-flash-tts`, `gemini-2.5-flash-image`).
- **Đồng bộ Đồng hồ Token & Gói `$300` trên Header Web (`CreditMeterWidget`):** Mỗi khi pipeline tạo video trên Mac gọi Vertex AI / Gemini, hãy gọi hàm `recordAiUsageCall(...)` trong `src/lib/ai-usage.ts` (hoặc gửi `POST http://localhost:3000/api/usage` với `{ provider: "mac_pipeline", model, feature, usageMetadata, imageCount, isTts }`) để số Token và số tiền `$` trừ vào gói `$300` luôn hiển thị realtime trên thanh Header của Web!

---

## 2. Các Quy Tắc Chiến Lược Nội Dung & Đăng Bài Từ 160 Video Thật (Áp dụng cho phần Kịch bản chữ & Metadata)

Khi Web App cấp đề tài/metadata sang cho pipeline Mac (hoặc khi lên lịch đăng bài lên YouTube Studio), giữ các thông số dữ liệu đã kiểm chứng sau:
- **Thời lượng tối ưu trên Shorts Khoa học Mỹ:** Nhắm khoảng **`45s – 55s`** (nhóm `45–65s` có điểm Outlier cao hơn `+33%` so với video quá dài).
- **Tiêu đề (Title):** Tiếng Anh Mỹ sạch, khơi gợi nghịch lý/tò mò mạnh, **KHÔNG gắn `#hashtag` trên tiêu đề** (`0/25` top Outliers dùng hashtag ở tiêu đề).
- **Hook 0–3s & CTA & Loop trong lời dẫn:** Mở đầu trực diện vào nghịch lý vật lý (tránh chào hỏi rườm rà), lồng tự nhiên lời nhắc đăng ký kênh ở cao trào nội dung, và ưu tiên câu kết tạo vòng lặp mượt về đầu video.
- **Mô tả (Description) & Khung giờ đăng:** Kèm nguồn tham chiếu khoa học thật (`NASA`, `ESA`, `MIT`, `Nature`...) và hẹn giờ xuất bản tại khung giờ vàng của kênh **`17:15 Giờ VN`**.
