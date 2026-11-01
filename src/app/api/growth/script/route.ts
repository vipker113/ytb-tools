import {
  getVertexAuthServer,
  readAiUsageSummary,
  recordAiUsageCall,
} from "@/lib/ai-usage";
import { getEffectiveGeminiKey, readStore } from "@/lib/store";
import {
  diagnoseExistingVideosForSubRescue,
  generateViralShortBlueprint,
} from "@/lib/viral-script";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();
    const activeChannel =
      store.myChannels.find((c) => c.id === store.activeChannelId) ||
      store.myChannels[0];

    if (body.action === "diagnoseChannel") {
      if (!activeChannel) {
        return Response.json({ diagnoses: [] });
      }
      const diagnoses = diagnoseExistingVideosForSubRescue(
        activeChannel.recentVideos,
        activeChannel.handle
      );
      return Response.json({ diagnoses });
    }

    const topic = String(body.topic || "").trim();
    if (!topic) {
      return Response.json(
        { error: "Vui lòng nhập chủ đề khoa học / ý tưởng video." },
        { status: 400 }
      );
    }

    const geminiKey = getEffectiveGeminiKey(store);
    const preferredModel =
      typeof body.model === "string" && body.model.trim()
        ? body.model.trim()
        : store.settings.geminiModel || "gemini-3.8-flash";

    const vertexAuth = await getVertexAuthServer();
    const result = await generateViralShortBlueprint({
      topic,
      sourceOutlierTitle: body.sourceOutlierTitle
        ? String(body.sourceOutlierTitle)
        : undefined,
      channelTitle: activeChannel?.title || "Proof of Wonder",
      channelHandle: activeChannel?.handle || "@proofofwonderscience",
      geminiApiKey: geminiKey,
      preferredModel,
      vertexAuth,
    });

    const aiUsage = result.usageReport
      ? await recordAiUsageCall({
          provider: result.usageReport.provider,
          model: result.usageReport.model,
          feature: "Xưởng Chia Cảnh 45s",
          usageMetadata: result.usageReport.usageMetadata,
          fallbackPromptChars: result.usageReport.promptChars,
        })
      : await readAiUsageSummary();

    return Response.json({ ...result, aiUsage });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Không thể tạo kịch bản AI lúc này.";
    return Response.json({ error: message }, { status: 400 });
  }
}
