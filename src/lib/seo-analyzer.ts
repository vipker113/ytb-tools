import type {
  AiOptimizationResult,
  AiSeoRewriteProposal,
  ScriptContentAuditResult,
  SeoAuditResult,
  SeoCheckItem,
} from "./types";
import { buildGeminiModelChain } from "./viral-script";

export interface AuditInput {
  title: string;
  description: string;
  tags: string[];
  targetKeyword?: string;
  channelHandle?: string;
  isShort?: boolean;
  views?: number;
  likes?: number;
  comments?: number;
}

const POWER_WORDS_REGEX =
  /(\d+|bí quyết|bí mật|sai lầm|cách|hướng dẫn|thực tế|thực chiến|miễn phí|con số 0|đừng|tuyệt đối|nhanh nhất|hiệu quả|mới nhất|chi tiết|từ a-z|how|why|what|actually|inside|hidden|deadly|never|strange|impossible|mistake|secret|free|guide|\?|\(|\)|\[|\])/i;

function isLikelyEnglish(text: string): boolean {
  const sample = text.trim();
  if (!sample) return false;
  // Vietnamese specific accented characters
  const hasViDiacritics =
    /[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ]/.test(
      sample
    );
  return !hasViDiacritics;
}

export function runSeoAndConversionAudit(input: AuditInput): SeoAuditResult {
  const title = input.title.trim();
  const description = input.description.trim();
  const tags = input.tags.map((t) => t.trim()).filter(Boolean);
  const channelHandle = (input.channelHandle || "@TenKenhCuaBan").startsWith("@")
    ? input.channelHandle || "@TenKenhCuaBan"
    : `@${input.channelHandle}`;

  // Infer keyword if user didn't specify one
  const inferredKw =
    (input.targetKeyword || "").trim() ||
    tags[0] ||
    title
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .split(/\s+/)
      .filter((w) => w.length > 2)
      .slice(0, 4)
      .join(" ");

  const kwLower = inferredKw.toLowerCase();
  const titleLower = title.toLowerCase();
  const descLower = description.toLowerCase();

  const checks: SeoCheckItem[] = [];

  // 1. Title Length (8 pts)
  const tLen = title.length;
  const lenOptimal = tLen >= 42 && tLen <= 72;
  const lenAcceptable = tLen >= 28 && tLen <= 85;
  checks.push({
    id: "title-length",
    category: "title",
    label: "Độ dài tiêu đề chuẩn hiển thị (42–72 ký tự)",
    passed: lenOptimal,
    score: lenOptimal ? 8 : lenAcceptable ? 5 : tLen > 0 ? 2 : 0,
    maxScore: 8,
    feedback: `Hiện tại: ${tLen} ký tự. ${
      lenOptimal
        ? "Độ dài lý tưởng cho cả điện thoại và máy tính!"
        : tLen < 42
        ? "Tiêu đề hơi ngắn, chưa tận dụng hết không gian từ khóa & kích thích tò mò."
        : "Tiêu đề dài dễ bị cắt dấu '...' trên màn hình điện thoại."
    }`,
    actionTip: lenOptimal
      ? undefined
      : "Đưa lợi ích chính lên 55 ký tự đầu tiên và giữ tổng độ dài trong khoảng 45–70 ký tự.",
  });

  // 2. Keyword in Title (10 pts)
  const kwWords = kwLower.split(/\s+/).filter((w) => w.length > 2);
  const exactKwInTitle = kwLower.length > 0 && titleLower.includes(kwLower);
  const matchedWords = kwWords.filter((w) => titleLower.includes(w));
  const partialMatch =
    kwWords.length > 0 && matchedWords.length >= Math.ceil(kwWords.length * 0.6);
  const kwInFirstHalf =
    exactKwInTitle && titleLower.indexOf(kwLower) <= Math.max(25, title.length * 0.5);

  checks.push({
    id: "title-keyword",
    category: "title",
    label: `Từ khóa mục tiêu ("${inferredKw || "..."}") xuất hiện trong tiêu đề`,
    passed: exactKwInTitle || partialMatch,
    score: kwInFirstHalf ? 10 : exactKwInTitle ? 8 : partialMatch ? 5 : 0,
    maxScore: 10,
    feedback: kwInFirstHalf
      ? "Tuyệt vời! Từ khóa nằm ngay nửa đầu tiêu đề giúp tăng mạnh SEO tìm kiếm."
      : exactKwInTitle
      ? "Đã có chính xác từ khóa trong tiêu đề."
      : partialMatch
      ? "Có chứa một phần từ khóa, nhưng nên ghép cụm từ tự nhiên sát nghĩa hơn."
      : "Chưa thấy từ khóa chính trong tiêu đề.",
    actionTip:
      exactKwInTitle || partialMatch
        ? undefined
        : `Chèn cụm từ "${inferredKw}" vào nửa đầu tiêu đề.`,
  });

  // 3. Hook / Power Words in Title (7 pts)
  const hasPowerHook = POWER_WORDS_REGEX.test(title);
  const hasNumber = /\d+/.test(title);
  checks.push({
    id: "title-hook",
    category: "title",
    label: "Yếu tố kích thích Click (Con số cụ thể, ngoặc đơn, từ khóa cảm xúc)",
    passed: hasPowerHook,
    score: hasPowerHook && hasNumber ? 7 : hasPowerHook ? 5 : 1,
    maxScore: 7,
    feedback:
      hasPowerHook && hasNumber
        ? "Tiêu đề có cả con số cụ thể lẫn từ ngữ kích thích CTR cao!"
        : hasPowerHook
        ? "Đã có từ gợi mở, thêm con số định lượng (VD: 5 bước, 10 phút, 2026) sẽ tăng thêm CTR."
        : "Tiêu đề đang mang tính trần thuật chung chung, khó cạnh tranh lượt click.",
    actionTip: hasPowerHook
      ? undefined
      : "Thêm kết quả cụ thể hoặc ngoặc bổ trợ như (Hướng dẫn thực tế), (Cho người mới).",
  });

  // 4. Title Readability / No Spam Caps (5 pts)
  const upperChars = (title.match(/\p{Lu}/gu) || []).length;
  const letterChars = Math.max((title.match(/\p{L}/gu) || []).length, 1);
  const capsRatio = upperChars / letterChars;
  const cleanCaps = title.length > 0 && capsRatio < 0.45;
  checks.push({
    id: "title-clarity",
    category: "title",
    label: "Trình bày tự nhiên, không lạm dụng VIẾT HOA toàn bộ",
    passed: cleanCaps,
    score: cleanCaps ? 5 : title.length > 0 ? 2 : 0,
    maxScore: 5,
    feedback: cleanCaps
      ? "Định dạng chữ hoa/thường chuyên nghiệp, tạo thiện cảm đáng tin cậy."
      : "Viết hoa quá nhiều từ dễ gây cảm giác giật tít rẻ tiền (clickbait).",
  });

  // 5. Keyword in first 160 chars of Description (8 pts)
  const first160 = descLower.slice(0, 180);
  const kwInSnippet =
    kwLower.length > 0 &&
    (first160.includes(kwLower) ||
      (kwWords.length > 0 &&
        kwWords.filter((w) => first160.includes(w)).length >=
          Math.ceil(kwWords.length * 0.6)));
  checks.push({
    id: "desc-snippet",
    category: "description",
    label: "Từ khóa xuất hiện trong 2 dòng đầu Mô tả (Đoạn trích tìm kiếm)",
    passed: kwInSnippet,
    score: kwInSnippet ? 8 : description.length > 20 ? 2 : 0,
    maxScore: 8,
    feedback: kwInSnippet
      ? "2 dòng đầu mô tả đã chứa từ khóa, hiển thị nổi bật trên trang tìm kiếm YouTube & Google!"
      : "2 dòng đầu mô tả chưa có từ khóa chính.",
    actionTip: kwInSnippet
      ? undefined
      : `Viết câu mở đầu mô tả tóm tắt giá trị video kèm từ khóa "${inferredKw}".`,
  });

  // 6. Description Depth (7 pts)
  const dLen = description.length;
  const descGood = dLen >= 250 || (Boolean(input.isShort) && dLen >= 80);
  checks.push({
    id: "desc-depth",
    category: "description",
    label: "Độ sâu nội dung phần Mô tả (>= 250 ký tự)",
    passed: descGood,
    score: descGood ? 7 : dLen >= 100 ? 4 : dLen > 0 ? 1 : 0,
    maxScore: 7,
    feedback: `Hiện tại: ${dLen} ký tự. ${
      descGood
        ? "Đủ ngữ cảnh để thuật toán YouTube phân loại đúng tệp khán giả!"
        : "Mô tả quá ngắn khiến YouTube thiếu dữ liệu hiểu sâu chủ đề video."
    }`,
  });

  // 7. Chapters / Timestamps (7 pts)
  const hasChapters = /00:00|0:00/.test(description) && /\d{1,2}:\d{2}/.test(description);
  const chaptersPass = Boolean(input.isShort) || hasChapters;
  checks.push({
    id: "desc-chapters",
    category: "description",
    label: input.isShort
      ? "Định dạng Shorts gọn gàng (#shorts)"
      : "Chia phân đoạn Thời gian (Chapters 00:00) tăng giữ chân người xem",
    passed: chaptersPass,
    score: chaptersPass ? 7 : /\d{1,2}:\d{2}/.test(description) ? 4 : 0,
    maxScore: 7,
    feedback: input.isShort
      ? "Video Shorts không bắt buộc chia Chapters."
      : hasChapters
      ? "Đã có mốc 00:00 Chapters giúp lên top Google Video Key Moments!"
      : "Chưa có phân đoạn 00:00 trong mô tả.",
    actionTip: chaptersPass
      ? undefined
      : "Thêm danh sách mốc thời gian bắt đầu từ `00:00 Mở đầu` trong phần mô tả.",
  });

  // 8. Smart Subscribe Confirmation Link (8 pts)
  const hasSubConfirm = descLower.includes("sub_confirmation=1");
  checks.push({
    id: "desc-sub-link",
    category: "description",
    label: "Chèn Link Đăng Ký 1-Click (?sub_confirmation=1) trong Mô tả",
    passed: hasSubConfirm,
    score: hasSubConfirm ? 8 : descLower.includes("youtube.com/") ? 3 : 0,
    maxScore: 8,
    feedback: hasSubConfirm
      ? "Đã gắn link xác nhận đăng ký trực tiếp giúp tăng tỷ lệ chuyển đổi Sub gấp 2–3 lần!"
      : "Chưa có link `?sub_confirmation=1` trong mô tả — đang bỏ lỡ lượng Sub tự nhiên rất lớn!",
    actionTip: hasSubConfirm
      ? undefined
      : `Copy khối CTA bên dưới có sẵn link https://www.youtube.com/${channelHandle}?sub_confirmation=1 dán vào mô tả.`,
  });

  // 9. Tags Count (7 pts)
  const tCount = tags.length;
  const countPass = tCount >= 6 && tCount <= 22;
  checks.push({
    id: "tags-count",
    category: "tags",
    label: "Số lượng thẻ Tags hợp lý (6–20 thẻ chuyên sâu)",
    passed: countPass,
    score: countPass ? 7 : tCount >= 3 ? 4 : tCount > 0 ? 2 : 0,
    maxScore: 7,
    feedback: `Hiện có ${tCount} thẻ tag. ${
      countPass
        ? "Số lượng thẻ chuẩn, bao phủ tốt từ khóa ngách và lỗi chính tả."
        : "Cần bổ sung thêm thẻ tag đồng nghĩa và từ khóa dài (long-tail)."
    }`,
  });

  // 10. Tags Character Utilization (7 pts)
  const tagChars = tags.join(",").length;
  const charsPass = tagChars >= 140 && tagChars <= 495;
  checks.push({
    id: "tags-chars",
    category: "tags",
    label: "Tận dụng dung lượng Tags (140–495 / 500 ký tự tối đa)",
    passed: charsPass,
    score: charsPass ? 7 : tagChars >= 60 && tagChars <= 500 ? 4 : 0,
    maxScore: 7,
    feedback: `Đang dùng ${tagChars}/500 ký tự. ${
      tagChars > 500
        ? "Vượt quá giới hạn 500 ký tự của YouTube Studio!"
        : charsPass
        ? "Tối ưu tốt dung lượng thẻ từ khóa."
        : "Còn nhiều khoảng trống ký tự để thêm các cụm từ tìm kiếm ngách."
    }`,
  });

  // 11. Target Keyword in Tags (6 pts)
  const kwInTags =
    kwLower.length > 0 &&
    tags.some((t) => t.toLowerCase().includes(kwLower) || kwLower.includes(t.toLowerCase()));
  checks.push({
    id: "tags-keyword",
    category: "tags",
    label: "Từ khóa chính nằm trong danh sách thẻ Tags",
    passed: kwInTags,
    score: kwInTags ? 6 : 0,
    maxScore: 6,
    feedback: kwInTags
      ? "Đồng bộ hoàn hảo giữa Tiêu đề – Mô tả – Thẻ Tags!"
      : `Hãy thêm chính xác thẻ "${inferredKw}" lên vị trí đầu tiên của ô Tags.`,
  });

  // 12. Subscriber Value Hook / Community Question CTA (8 pts)
  const hasCtaWords =
    /(đăng ký|subscribe|bình luận|comment|chia sẻ ý kiến|tài liệu|template|quà tặng|link tải|stay curious|what do you think|let us know|drop it below|share your|which one|follow)/i.test(
      description
    );
  checks.push({
    id: "conv-cta-text",
    category: "conversion",
    label: "Lời kêu gọi hành động (CTA trao giá trị / đặt câu hỏi thảo luận)",
    passed: hasCtaWords,
    score: hasCtaWords ? 8 : 2,
    maxScore: 8,
    feedback: hasCtaWords
      ? "Mô tả có lời mời tương tác/nhận giá trị giúp kích thích bình luận và bấm Đăng ký."
      : "Thiếu lời kêu gọi bình luận hoặc lý do cụ thể để người xem bấm Subscribe.",
    actionTip: hasCtaWords
      ? undefined
      : "Đặt 1 câu hỏi mở cho khán giả bình luận (tăng đề xuất thuật toán) kèm lời hứa nội dung tuần tới.",
  });

  // 13. Session Chaining / Related Video Link (6 pts)
  const descWithoutSub = descLower.replace(/[^\s]*sub_confirmation=1[^\s]*/g, "");
  const hasRelatedVideo =
    /(youtu\.be\/|youtube\.com\/watch|youtube\.com\/playlist|youtube\.com\/shorts|youtube\.com\/@[^/\s]+\/(shorts|videos|playlists))/i.test(
      descWithoutSub
    );
  checks.push({
    id: "conv-bridge",
    category: "conversion",
    label: "Điều hướng xem tiếp Video/Playlist liên quan (Kéo dài phiên xem)",
    passed: hasRelatedVideo,
    score: hasRelatedVideo ? 6 : 1,
    maxScore: 6,
    feedback: hasRelatedVideo
      ? "Có link giữ chân khán giả xem tiếp video thứ 2 (người xem >= 2 video có tỷ lệ Sub cao gấp 5 lần!)."
      : "Chưa gắn link dẫn sang video/playlist liên quan của kênh trong phần mô tả.",
  });

  // 14. Engagement Benchmark or Opening Value Promise (6 pts)
  const views = input.views || 0;
  if (views > 0) {
    const eng = (((input.likes || 0) + (input.comments || 0)) / views) * 100;
    const goodEng = eng >= 3.8;
    checks.push({
      id: "conv-engagement",
      category: "conversion",
      label: "Tỷ lệ tương tác thực tế (Likes + Comments / Views >= 3.8%)",
      passed: goodEng,
      score: goodEng ? 6 : eng >= 2.2 ? 4 : 2,
      maxScore: 6,
      feedback: `Tỷ lệ tương tác hiện tại: ${eng.toFixed(2)}%. ${
        goodEng
          ? "Tương tác rất khỏe — tín hiệu cực tốt để YouTube đẩy thêm đề xuất trang chủ!"
          : "Tương tác còn thấp; hãy ghim 1 bình luận đặt câu hỏi thú vị ngay dưới video."
      }`,
    });
  } else {
    const strongOpening = description.split("\n")[0]?.length >= 45;
    checks.push({
      id: "conv-engagement",
      category: "conversion",
      label: "Cam kết lợi ích rõ ràng ngay dòng đầu tiên (Hook giữ chân)",
      passed: strongOpening,
      score: strongOpening ? 6 : 2,
      maxScore: 6,
      feedback: strongOpening
        ? "Dòng đầu tiên mô tả rõ lợi ích người xem nhận được."
        : "Viết câu đầu tiên thật cụ thể về kết quả người xem đạt được sau khi xem hết video.",
    });
  }

  const catScores = {
    title: checks
      .filter((c) => c.category === "title")
      .reduce((s, c) => s + c.score, 0),
    description: checks
      .filter((c) => c.category === "description")
      .reduce((s, c) => s + c.score, 0),
    tags: checks
      .filter((c) => c.category === "tags")
      .reduce((s, c) => s + c.score, 0),
    conversion: checks
      .filter((c) => c.category === "conversion")
      .reduce((s, c) => s + c.score, 0),
  };

  const totalScore =
    catScores.title + catScores.description + catScores.tags + catScores.conversion;

  let grade: SeoAuditResult["grade"] = "C";
  if (totalScore >= 88) grade = "S";
  else if (totalScore >= 75) grade = "A";
  else if (totalScore >= 60) grade = "B";
  else if (totalScore >= 45) grade = "C";
  else grade = "D";

  const isEn = isLikelyEnglish(`${title} ${inferredKw} ${description.slice(0, 120)}`);
  const cleanTopic = inferredKw || (isEn ? "this phenomenon" : "chủ đề này");

  const suggestedTitles = isEn
    ? [
        `Why ${cleanTopic} Defies What You Learned in School`,
        `What Actually Happens Inside ${cleanTopic}?`,
        `Scientists Found Something Impossible Inside ${cleanTopic}`,
      ]
    : [
        `Cách ${cleanTopic} hiệu quả từ con số 0 (Hướng dẫn thực chiến 2026)`,
        `5 Sai lầm khiến 90% người mới thất bại khi ${cleanTopic} (Và cách sửa)`,
        `Tôi đã áp dụng ${cleanTopic} trong 30 ngày: Kết quả & Quy trình chi tiết`,
      ];

  const suggestedCtaBlock = isEn
    ? [
        `🔬 STAY CURIOUS — SUBSCRIBE FOR DAILY SCIENCE:`,
        `👉 Subscribe in 1-Click: https://www.youtube.com/${channelHandle}?sub_confirmation=1`,
        ``,
        `🎬 WATCH NEXT ON PROOF OF WONDER:`,
        `▶️ More Strange Science Shorts: https://www.youtube.com/${channelHandle}/shorts`,
        ``,
        `💬 QUESTION FOR YOU: Would you dare get close to ${cleanTopic}, or which science mystery should we uncover next? Drop your thought in the comments!`,
      ].join("\n")
    : [
        `🔥 ĐĂNG KÝ KÊNH ĐỂ KHÔNG BỎ LỠ VIDEO MỖI TUẦN:`,
        `👉 Bấm đăng ký ngay (1-Click): https://www.youtube.com/${channelHandle}?sub_confirmation=1`,
        ``,
        `🎬 XEM TIẾP CHUỖI VIDEO HỮU ÍCH NHẤT TRÊN KÊNH:`,
        `▶️ Danh sách phát trọn bộ: https://www.youtube.com/${channelHandle}/playlists`,
        ``,
        `💬 CÂU HỎI DÀNH CHO BẠN: Bạn đang gặp khó khăn lớn nhất ở bước nào khi ${cleanTopic}? Hãy để lại bình luận bên dưới, mình sẽ đọc và giải đáp chi tiết nhé!`,
      ].join("\n");

  const suggestedTags = isEn
    ? Array.from(
        new Set([
          cleanTopic.toLowerCase(),
          `${cleanTopic.toLowerCase()} explained`,
          "science shorts",
          "strange science",
          "earth mysteries",
          "space science",
          "documentary shorts",
          channelHandle.replace(/^@/, "").toLowerCase(),
        ])
      )
    : Array.from(
        new Set([
          cleanTopic.toLowerCase(),
          `hướng dẫn ${cleanTopic.toLowerCase()}`,
          `cách ${cleanTopic.toLowerCase()}`,
          `${cleanTopic.toLowerCase()} cho người mới`,
          `${cleanTopic.toLowerCase()} 2026`,
          `kinh nghiệm ${cleanTopic.toLowerCase()}`,
          `mẹo ${cleanTopic.toLowerCase()}`,
          channelHandle.replace(/^@/, "").toLowerCase(),
        ])
      );

  return {
    totalScore,
    grade,
    categoryScores: catScores,
    checks,
    suggestedTitles,
    suggestedCtaBlock,
    suggestedTags,
  };
}

export async function generateAiSeoOptimization(params: {
  topicOrTitle: string;
  targetKeyword: string;
  channelHandle: string;
  niche: string;
  geminiApiKey: string;
  preferredModel?: string;
}): Promise<{
  data: AiOptimizationResult;
  usedAi: boolean;
  modelUsed: string;
}> {
  const handle = (params.channelHandle || "@KenhCuaBan").startsWith("@")
    ? params.channelHandle
    : `@${params.channelHandle}`;
  const kw = params.targetKeyword.trim() || params.topicOrTitle.trim();
  const isEn = isLikelyEnglish(`${params.topicOrTitle} ${params.targetKeyword}`);

  const fallback: AiOptimizationResult = isEn
    ? {
        titles: [
          `What Actually Happens Inside ${kw}?`,
          `Why ${kw} Shouldn't Be Possible—Yet It Exists`,
          `The Hidden Science Behind ${kw} Explained in 60 Seconds`,
          `Nobody Tells You What's Really Inside ${kw}`,
          `${kw}—So Why Does Physics Allow This?`,
        ],
        hookScript5s: `"Everyone pictures ${kw} one way—but if you actually went down there, what you'd find is completely different, and almost nobody talks about why."`,
        seoDescription: `${kw} hides one of the strangest mechanisms in nature. Here is the real science behind how it works.\n\n👉 Subscribe for more strange science: https://www.youtube.com/${handle}?sub_confirmation=1\n\n🎬 Watch more mysteries: https://www.youtube.com/${handle}/shorts\n\n💬 What's the strangest phenomenon you want explained next? Tell us in the comments!`,
        tags: [
          kw.toLowerCase(),
          `${kw.toLowerCase()} explained`,
          "science shorts",
          "strange science",
          "how it works",
          "everyday mysteries",
          "physics explained",
          "nature phenomena",
          handle.replace(/^@/, "").toLowerCase(),
        ],
        subTriggerTip:
          "Với kênh Science Shorts tiếng Anh: Đừng chèn màn hình Outro dài 5 giây ở cuối (người xem sẽ vuốt đi làm tụt % xem hết!). Hãy đặt 1 câu kết bất ngờ ở giây cuối nối mượt lại câu mở đầu (Looping Short) và gắn lời nhắc ngắn trên phụ đề giây thứ 32: 'Follow Proof of Wonder for daily strange science'.",
      }
    : {
        titles: [
          `Cách ${kw} từ A–Z cho người mới (Làm được ngay trong 15 phút)`,
          `Đừng ${kw} theo cách cũ! Đây là quy trình mới gấp 3 hiệu quả (2026)`,
          `7 Bí quyết ${kw} thực chiến ít ai chia sẻ thật lòng với bạn`,
          `Tôi đã thử ${kw} suốt 30 ngày và rút ra bài học đắt giá này`,
          `[${params.niche || "Hướng Dẫn"}] Lộ trình ${kw} tinh gọn & dễ áp dụng nhất`,
        ],
        hookScript5s: `"Nếu bạn đang tốn hàng giờ cho ${kw} mà chưa ra kết quả, thì trong đúng 8 phút tới mình sẽ chỉ cho bạn quy trình từng bước giúp rút ngắn một nửa thời gian — đặc biệt bước thứ 3 ở giữa video là thứ tạo ra 80% sự khác biệt!"`,
        seoDescription: `${kw} — Hướng dẫn thực chiến chi tiết từng bước dành cho người mới bắt đầu lẫn người muốn tối ưu hiệu suất trong lĩnh vực ${params.niche || "sáng tạo"}.\n\n👉 Đăng ký kênh ủng hộ mình nhé: https://www.youtube.com/${handle}?sub_confirmation=1\n\n⏱️ NỘI DUNG CHÍNH TRONG VIDEO:\n00:00 Vấn đề phổ biến nhất khi ${kw}\n01:30 Bước 1: Chuẩn bị nền tảng chuẩn\n04:15 Bước 2: Quy trình thực hiện chi tiết\n07:40 Bước 3: Mẹo tối ưu nhân đôi kết quả\n10:10 Tổng kết & Tài liệu tặng kèm\n\n💬 Bạn muốn mình làm sâu hơn về phần nào tiếp theo? Bình luận ngay bên dưới nhé!`,
        tags: [
          kw.toLowerCase(),
          `hướng dẫn ${kw.toLowerCase()}`,
          `cách ${kw.toLowerCase()} hiệu quả`,
          `${kw.toLowerCase()} cho người mới`,
          `${kw.toLowerCase()} 2026`,
          `tự học ${kw.toLowerCase()}`,
          `sai lầm khi ${kw.toLowerCase()}`,
          `mẹo ${kw.toLowerCase()}`,
          (params.niche || "kiến thức thực chiến").toLowerCase(),
          handle.replace(/^@/, "").toLowerCase(),
        ],
        subTriggerTip:
          "Đừng xin Subscribe ở 15 giây đầu tiên! Hãy trao ngay 1 mẹo cực đắt giá ở phút thứ 2–3, ngay sau câu kết luận mẹo đó hãy nói: 'Nếu mẹo nhỏ vừa rồi giúp bạn tiết kiệm thời gian, hãy bấm Đăng ký kênh vì mỗi tuần mình đều chia sẻ 1 quy trình thực chiến như vậy.' — Tỷ lệ bấm Sub thực tế tăng 2.4 lần!",
      };

  if (!params.geminiApiKey) {
    return { data: fallback, usedAi: false, modelUsed: "template" };
  }

  const contentLangLabel = isEn
    ? "TIẾNG ANH chuẩn tự nhiên cho khán giả Mỹ/Quốc tế (US English, phong cách Veritasium / Cleo Abram / Zack D. Films, KHÔNG gắn hashtag rác cuối tiêu đề)"
    : "TIẾNG VIỆT tự nhiên, thu hút cao";

  const prompt = `Bạn là chuyên gia tăng trưởng kênh YouTube (YouTube Growth Strategist).
Hãy tối ưu gói SEO & Chuyển đổi người xem thành Subscribers thật cho video sau:
- Chủ đề / Tiêu đề nháp: "${params.topicOrTitle}"
- Từ khóa chính: "${params.targetKeyword || params.topicOrTitle}"
- Ngách kênh: "${params.niche}"
- Handle kênh: "${handle}"
- Ngôn ngữ nội dung đầu ra cho titles, hookScript5s, seoDescription, tags: ${contentLangLabel}. (Riêng trường subTriggerTip viết bằng tiếng Việt để hướng dẫn chủ kênh).

Trả về ĐÚNG định dạng JSON thuần (không bọc markdown) theo cấu trúc:
{
  "titles": ["5 tiêu đề CTR cực cao, độ dài 42-65 ký tự, kích thích tò mò khoa học/thực tế, không giật tít rẻ tiền"],
  "hookScript5s": "Lời thoại 5-8 giây mở đầu video cực cuốn hút để giữ chân người xem không vuốt qua",
  "seoDescription": "Đoạn mô tả chuẩn SEO YouTube >= 280 ký tự, có từ khóa ở 2 dòng đầu, có link https://www.youtube.com/${handle}?sub_confirmation=1, có link xem tiếp https://www.youtube.com/${handle}/shorts và 1 câu hỏi kích thích bình luận",
  "tags": ["12 thẻ tags tìm kiếm cao liên quan trực tiếp đúng ngôn ngữ kênh, KHÔNG chèn thẻ sai chủ đề"],
  "subTriggerTip": "1 lời khuyên cụ thể bằng tiếng Việt cho video này để tăng tỷ lệ người xem bấm Subscribe thật"
}`;

  const models = buildGeminiModelChain(params.preferredModel);
  for (const model of models) {
    try {
      const genConfig: Record<string, unknown> = {
        temperature: 0.7,
        responseMimeType: "application/json",
      };

      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
          params.geminiApiKey
        )}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: genConfig,
          }),
          cache: "no-store",
        }
      );
      if (!res.ok) continue;
      const json = await res.json();
      const parts: Array<{ text?: string; thought?: boolean }> =
        json?.candidates?.[0]?.content?.parts || [];
      const answerPart =
        parts.find((p) => !p.thought && p.text) || parts[parts.length - 1];
      const rawText = answerPart?.text;
      if (!rawText) continue;
      const cleaned = rawText.replace(/^```json\s*/i, "").replace(/```\s*$/, "");
      const parsed = JSON.parse(cleaned) as Partial<AiOptimizationResult>;
      return {
        usedAi: true,
        modelUsed: model,
        data: {
          titles:
            Array.isArray(parsed.titles) && parsed.titles.length > 0
              ? parsed.titles
              : fallback.titles,
          hookScript5s: parsed.hookScript5s || fallback.hookScript5s,
          seoDescription: parsed.seoDescription || fallback.seoDescription,
          tags:
            Array.isArray(parsed.tags) && parsed.tags.length > 0
              ? parsed.tags
              : fallback.tags,
          subTriggerTip: parsed.subTriggerTip || fallback.subTriggerTip,
        },
      };
    } catch {
      // try next model or fallback
    }
  }

  return { data: fallback, usedAi: false, modelUsed: "fallback" };
}

export function splitDescriptionEditorialAndCredits(description: string): {
  editorialPart: string;
  lockedCreditsPart: string;
} {
  const markers = [
    "\nScientific Sources:",
    "\nMedia & Attribution Credits:",
    "\nMedia Credits:",
  ];
  let splitIdx = -1;
  for (const m of markers) {
    const idx = description.indexOf(m);
    if (idx >= 0 && (splitIdx === -1 || idx < splitIdx)) {
      splitIdx = idx;
    }
  }

  if (splitIdx === -1) {
    return { editorialPart: description.trim(), lockedCreditsPart: "" };
  }
  return {
    editorialPart: description.slice(0, splitIdx).trim(),
    lockedCreditsPart: description.slice(splitIdx).trim(),
  };
}

export function auditShortsScriptAndCompliance(params: {
  narrationText: string;
  durationSec?: number | null;
  description: string;
}): ScriptContentAuditResult {
  const text = (params.narrationText || "").trim();
  const desc = (params.description || "").trim();
  const sentences = text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
  const words = text.split(/\s+/).filter(Boolean);
  const wordCount = words.length;
  const dur = params.durationSec && params.durationSec > 0 ? params.durationSec : 0;
  const wps = dur > 0 ? wordCount / dur : 2.5;

  const firstHook = sentences.slice(0, 2).join(" ");
  const hookStrong =
    firstHook.length >= 35 &&
    !/(welcome back|in this video|today we will|hey guys|let's delve)/i.test(
      firstHook
    );

  const pacingGood = wordCount === 0 || (wps >= 1.95 && wps <= 3.15);

  const aiClicheMatch =
    /(testament to|tapestry of|delve into|it's important to note|in conclusion|realm of)/i.test(
      text
    );

  const hasDoiOrCitations =
    /(doi\.org|scientific sources|et al\.|nasa|nature|science|plos|journal)/i.test(
      desc
    );
  const descUnderLimit =
    desc.length <= 4950 && !desc.includes("<") && !desc.includes(">");

  const checks = [
    {
      id: "hook-3s",
      label: "Mở đầu trực diện 0–3s (Không câu chào thừa)",
      passed: wordCount === 0 ? true : hookStrong,
      detail:
        wordCount === 0
          ? "Chưa có file script đính kèm"
          : hookStrong
          ? "Vào thẳng nghịch lý / hành động ngay câu đầu tiên"
          : "Câu đầu hơi chậm, tránh mở bài chung chung",
    },
    {
      id: "pacing-wps",
      label: "Nhịp đọc Documentary chuẩn (2.0 – 3.1 từ/giây)",
      passed: pacingGood,
      detail:
        dur > 0 && wordCount > 0
          ? `${wps.toFixed(2)} từ/giây (${wordCount} từ / ${dur.toFixed(1)}s)`
          : `${wordCount} từ`,
    },
    {
      id: "zero-ai-smell",
      label: "Ngôn từ tự nhiên (0% văn mẫu sáo rỗng AI)",
      passed: !aiClicheMatch,
      detail: !aiClicheMatch
        ? "Không chứa cụm từ AI sáo rỗng (delve, tapestry, realm...)"
        : "Phát hiện cụm từ văn mẫu AI cần làm sạch",
    },
    {
      id: "doi-credits",
      label: "Đầy đủ Nguồn Khoa Học (DOI) & Ghi công CC-BY",
      passed: hasDoiOrCitations,
      detail: hasDoiOrCitations
        ? "Đã đính kèm trích dẫn khoa học & bản quyền an toàn"
        : "Chưa thấy khối Scientific Sources trong phần mô tả",
    },
    {
      id: "yt-limits",
      label: "An toàn ký tự YouTube Studio (< 5.000 chars, không dấu <>)",
      passed: descUnderLimit,
      detail: `${desc.length}/4950 ký tự hợp lệ`,
    },
  ];

  const passedCount = checks.filter((c) => c.passed).length;
  return {
    score: Math.round((passedCount / checks.length) * 100),
    checks,
  };
}

export async function generateAiSeoRewriteDiff(params: {
  currentTitle: string;
  currentTargetKeyword: string;
  currentDescription: string;
  currentTags: string[];
  currentPinnedComment: string;
  narrationScript?: string;
  channelHandle: string;
  niche: string;
  isShort: boolean;
  geminiApiKey: string;
  preferredModel?: string;
}): Promise<AiSeoRewriteProposal> {
  const handle = (params.channelHandle || "@proofofwonderscience").startsWith("@")
    ? params.channelHandle
    : `@${params.channelHandle}`;

  const beforeAudit = runSeoAndConversionAudit({
    title: params.currentTitle,
    description: params.currentDescription,
    tags: params.currentTags,
    targetKeyword: params.currentTargetKeyword,
    channelHandle: handle,
    isShort: params.isShort,
  });

  const { editorialPart, lockedCreditsPart } =
    splitDescriptionEditorialAndCredits(params.currentDescription);

  const failedChecksText = beforeAudit.checks
    .filter((c) => !c.passed)
    .map((c) => `- ${c.label}: ${c.feedback}`)
    .join("\n");

  const isEn = isLikelyEnglish(
    `${params.currentTitle} ${params.narrationScript || editorialPart}`
  );

  const scriptSnippet = (params.narrationScript || "").slice(0, 1800);

  const prompt = `You are a top 0.5% YouTube Science Shorts Growth & SEO Strategist (Veritasium / Cleo Abram / Fern level).
Analyze this rendered video's spoken script and current metadata, then rewrite its SEO package so it achieves maximum CTR on the US Shorts Shelf AND 92-100/100 SEO + Subscriber Conversion score.

CHANNEL: ${handle} (${params.niche})
CURRENT SEO SCORE: ${beforeAudit.totalScore}/100 (Grade ${beforeAudit.grade})
FAILED / WEAK SEO CHECKS TO FIX:
${failedChecksText || "- Already high score, make Title hookier (curiosity gap, 46-66 chars), tighten opening 2-line keyword snippet, and upgrade Tags + Pinned Comment."}

CURRENT TITLE: "${params.currentTitle}"
CURRENT TARGET KEYWORD: "${params.currentTargetKeyword}"
CURRENT EDITORIAL DESCRIPTION (excluding locked citations):
"""
${editorialPart.slice(0, 1200)}
"""
CURRENT TAGS: ${JSON.stringify(params.currentTags)}
CURRENT PINNED COMMENT: "${params.currentPinnedComment}"

ACTUAL SPOKEN VIDEO SCRIPT:
"""
${scriptSnippet || editorialPart.slice(0, 900)}
"""

STRICT RULES:
1. Choose ONE crisp, high-search 2-to-4 word ${isEn ? "US English" : "Vietnamese"} "targetKeyword" matching the core topic.
2. "bestTitle" MUST be ${isEn ? "natural US English" : "Vietnamese"}, 46–68 characters, ZERO #hashtags, NOT ALL-CAPS, includes a number or strong curiosity/paradox word (Why, What, Inside, Hidden, Locked, Silent, Deadly, etc.), AND naturally contains "targetKeyword" (prefer in the first half of the title!).
3. Provide "alternativeTitles": 3 distinct high-CTR title options (each 46–68 chars, containing or closely matching targetKeyword, zero #hashtags).
4. "editorialDescription" (ONLY the editorial summary + CTA — DO NOT include Scientific Sources or Media Credits because the system will automatically re-attach the locked DOI/CC-BY block below your text!):
   - First sentence (first 140 chars) MUST naturally include "targetKeyword" and hook curiosity.
   - 2 concise paragraphs summarizing the scientific twist (260–550 chars).
   - Include exact 1-click subscribe line: 🔔 Subscribe for daily strange science: https://www.youtube.com/${handle}?sub_confirmation=1
   - Include exact watch-next bridge line: ▶️ Watch more Proof of Wonder Shorts: https://www.youtube.com/${handle}/shorts
   - End with a short discussion question inviting comments.
5. "tags": 12–15 high-intent search tags (total 220–430 chars, comma-joined <= 450 chars). Tag #1 MUST be the exact "targetKeyword" in lowercase.
6. "pinnedComment": 1 irresistible curiosity/debate question matching the video's twist that makes viewers reply in comments.
7. "reasoningVi": Write 1–2 concise sentences IN VIETNAMESE explaining clearly to the creator what was weak before and why this rewrite improves CTR + SEO.

Return STRICT RAW JSON ONLY:
{
  "targetKeyword": "...",
  "bestTitle": "...",
  "alternativeTitles": ["...", "...", "..."],
  "editorialDescription": "...",
  "tags": ["..."],
  "pinnedComment": "...",
  "reasoningVi": "..."
}`;

  const models = buildGeminiModelChain(params.preferredModel);

  let parsedAi: {
    targetKeyword?: string;
    bestTitle?: string;
    alternativeTitles?: string[];
    editorialDescription?: string;
    tags?: string[];
    pinnedComment?: string;
    reasoningVi?: string;
  } | null = null;
  let usedModel = "fallback";
  let usedAi = false;

  if (params.geminiApiKey) {
    for (const model of models) {
      try {
        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
            params.geminiApiKey
          )}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: {
                temperature: 0.65,
                responseMimeType: "application/json",
              },
            }),
            cache: "no-store",
          }
        );
        if (!res.ok) continue;
        const json = await res.json();
        const parts: Array<{ text?: string; thought?: boolean }> =
          json?.candidates?.[0]?.content?.parts || [];
        const answerPart =
          parts.find((p) => !p.thought && p.text) || parts[parts.length - 1];
        const rawText = answerPart?.text;
        if (!rawText) continue;
        const cleaned = rawText
          .replace(/^```json\s*/i, "")
          .replace(/```\s*$/, "")
          .trim();
        parsedAi = JSON.parse(cleaned);
        usedModel = model;
        usedAi = true;
        break;
      } catch {
        // try next model
      }
    }
  }

  const finalKw = (
    parsedAi?.targetKeyword ||
    params.currentTargetKeyword ||
    params.currentTags[0] ||
    "strange science"
  )
    .replace(/[#<>"]/g, "")
    .trim();

  const cleanTitle = (
    parsedAi?.bestTitle ||
    params.currentTitle.replace(/#\S+/g, "").trim()
  )
    .replace(/#\S+/g, "")
    .replace(/\s{2,}/g, " ")
    .trim()
    .slice(0, 95);

  let editorialOut = (
    parsedAi?.editorialDescription || editorialPart
  ).trim();

  if (!editorialOut.toLowerCase().includes("sub_confirmation=1")) {
    editorialOut += `\n\n🔔 Subscribe for daily strange science: https://www.youtube.com/${handle}?sub_confirmation=1`;
  }
  const withoutSub = editorialOut
    .toLowerCase()
    .replace(/[^\s]*sub_confirmation=1[^\s]*/g, "");
  if (
    !/(youtu\.be\/|youtube\.com\/watch|youtube\.com\/playlist|youtube\.com\/shorts|youtube\.com\/@[^/\s]+\/shorts)/i.test(
      withoutSub
    )
  ) {
    editorialOut += `\n▶️ Watch more Proof of Wonder Shorts: https://www.youtube.com/${handle}/shorts`;
  }

  // Re-attach 100% of locked Scientific Sources & CC-BY Media Credits safely under 4950 chars
  let fullDescription = editorialOut;
  if (lockedCreditsPart) {
    const maxEditorialBudget = Math.max(
      320,
      4940 - lockedCreditsPart.length - 2
    );
    const safeEditorial =
      editorialOut.length > maxEditorialBudget
        ? editorialOut.slice(0, maxEditorialBudget).trimEnd()
        : editorialOut;
    fullDescription = `${safeEditorial}\n\n${lockedCreditsPart}`;
  } else {
    fullDescription = editorialOut.slice(0, 4940);
  }

  // Normalize tags: ensure targetKeyword is #1 and total length fits 160-445 chars
  const rawTags = [
    finalKw.toLowerCase(),
    ...(Array.isArray(parsedAi?.tags) ? parsedAi!.tags : params.currentTags),
    "proof of wonder",
    "science shorts",
  ];
  const dedupTags: string[] = [];
  const seenTag = new Set<string>();
  let charBudget = 0;
  for (const t of rawTags) {
    const c = String(t).replace(/[#<>"]/g, "").trim();
    if (!c || c.length > 55) continue;
    const low = c.toLowerCase();
    if (seenTag.has(low)) continue;
    if (charBudget + c.length + 2 > 445) break;
    seenTag.add(low);
    dedupTags.push(c);
    charBudget += c.length + 2;
    if (dedupTags.length >= 16) break;
  }

  const finalPinned = (
    parsedAi?.pinnedComment || params.currentPinnedComment
  ).trim();

  const altTitles = Array.from(
    new Set(
      [
        cleanTitle,
        ...(Array.isArray(parsedAi?.alternativeTitles)
          ? parsedAi!.alternativeTitles
          : []),
      ]
        .map((t) => String(t).replace(/#\S+/g, "").trim())
        .filter((t) => t.length >= 25)
    )
  ).slice(0, 4);

  const afterAudit = runSeoAndConversionAudit({
    title: cleanTitle,
    description: fullDescription,
    tags: dedupTags,
    targetKeyword: finalKw,
    channelHandle: handle,
    isShort: params.isShort,
  });

  return {
    usedAi,
    modelUsed: usedModel,
    reasoningVi:
      parsedAi?.reasoningVi ||
      "Đã đồng bộ từ khóa mục tiêu vào Tiêu đề + 2 dòng đầu Mô tả + Thẻ Tags và khóa an toàn phần Nguồn Khoa Học / Bản quyền CC-BY.",
    protectedCreditsKept: Boolean(lockedCreditsPart),
    protectedBlockPreview: lockedCreditsPart
      ? lockedCreditsPart.split("\n").slice(0, 3).join(" • ").slice(0, 160)
      : "",
    beforeScore: beforeAudit.totalScore,
    beforeGrade: beforeAudit.grade,
    afterScore: afterAudit.totalScore,
    afterGrade: afterAudit.grade,
    alternativeTitles: altTitles,
    proposed: {
      title: cleanTitle,
      targetKeyword: finalKw,
      editorialDescription: editorialOut,
      fullDescription,
      tags: dedupTags,
      pinnedComment: finalPinned,
    },
  };
}
