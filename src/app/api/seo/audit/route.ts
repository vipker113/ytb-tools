import {
  generateAiSeoOptimization,
  generateAiSeoRewriteDiff,
  runSeoAndConversionAudit,
} from "@/lib/seo-analyzer";
import {
  getEffectiveGeminiKey,
  getEffectiveYoutubeKey,
  readStore,
} from "@/lib/store";
import { fetchSingleVideoLive } from "@/lib/youtube";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();

    if (body.action === "aiRewriteSeoDiff") {
      const geminiKey = getEffectiveGeminiKey(store);
      const tagsArray: string[] = Array.isArray(body.tags)
        ? body.tags.map(String)
        : String(body.tags || "")
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean);

      const proposal = await generateAiSeoRewriteDiff({
        currentTitle: String(body.title || ""),
        currentTargetKeyword: String(body.targetKeyword || ""),
        currentDescription: String(body.description || ""),
        currentTags: tagsArray,
        currentPinnedComment: String(body.pinnedComment || ""),
        narrationScript: body.narrationScript
          ? String(body.narrationScript)
          : undefined,
        channelHandle: String(body.channelHandle || "@proofofwonderscience"),
        niche: String(body.niche || "Science & Space Documentary Shorts"),
        isShort: body.isShort !== false,
        geminiApiKey: geminiKey,
        preferredModel: store.settings.geminiModel || "gemini-2.5-flash",
      });
      return Response.json({ ok: true, proposal });
    }

    if (body.action === "aiOptimize") {
      const geminiKey = getEffectiveGeminiKey(store);
      const result = await generateAiSeoOptimization({
        topicOrTitle: String(body.topicOrTitle || ""),
        targetKeyword: String(body.targetKeyword || ""),
        channelHandle: String(body.channelHandle || "@proofofwonderscience"),
        niche: String(body.niche || "Science & Space Documentary Shorts"),
        geminiApiKey: geminiKey,
        preferredModel: store.settings.geminiModel || "gemini-2.5-flash",
      });
      return Response.json(result);
    }

    if (body.videoUrl) {
      const ytKey = getEffectiveYoutubeKey(store);
      if (!ytKey) {
        return Response.json(
          {
            error:
              "Để quét trực tiếp từ URL YouTube, vui lòng nhập YouTube Data API v3 Key trong mục 'Cài đặt & Kết nối' (hoặc nhập Tiêu đề & Mô tả nháp ở chế độ Thủ công).",
          },
          { status: 400 }
        );
      }
      const video = await fetchSingleVideoLive(String(body.videoUrl), ytKey);
      const audit = runSeoAndConversionAudit({
        title: video.title,
        description: video.description,
        tags: video.tags,
        targetKeyword: body.targetKeyword
          ? String(body.targetKeyword)
          : undefined,
        channelHandle: video.channelHandle || body.channelHandle,
        isShort: video.isShort,
        views: video.views,
        likes: video.likes,
        comments: video.comments,
      });
      return Response.json({ audit, fetchedVideo: video });
    }

    const tagsArray = Array.isArray(body.tags)
      ? body.tags.map(String)
      : String(body.tags || "")
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);

    const audit = runSeoAndConversionAudit({
      title: String(body.title || ""),
      description: String(body.description || ""),
      tags: tagsArray,
      targetKeyword: String(body.targetKeyword || ""),
      channelHandle: String(body.channelHandle || "@proofofwonderscience"),
      isShort: Boolean(body.isShort),
      views: Number(body.views || 0),
      likes: Number(body.likes || 0),
      comments: Number(body.comments || 0),
    });

    return Response.json({ audit });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Không thể thực hiện chấm điểm SEO.";
    return Response.json({ error: message }, { status: 400 });
  }
}
