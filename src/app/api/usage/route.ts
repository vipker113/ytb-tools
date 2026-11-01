import { connection } from "next/server";
import {
  calibrateAiUsageUsd,
  readAiUsageSummary,
  recordAiUsageCall,
} from "@/lib/ai-usage";

export async function GET() {
  await connection();
  const aiUsage = await readAiUsageSummary();
  return Response.json({ ok: true, aiUsage });
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const action = String(body.action || "record");

    if (action === "calibrate") {
      const actualTotalUsedUsd = Number(body.actualTotalUsedUsd ?? 0);
      if (Number.isNaN(actualTotalUsedUsd) || actualTotalUsedUsd < 0) {
        return Response.json(
          { error: "Số tiền đã dùng không hợp lệ." },
          { status: 400 }
        );
      }
      const creditLimitUsd =
        body.creditLimitUsd !== undefined
          ? Number(body.creditLimitUsd)
          : undefined;

      const aiUsage = await calibrateAiUsageUsd({
        actualTotalUsedUsd,
        creditLimitUsd,
      });
      return Response.json({
        ok: true,
        aiUsage,
        message: `Đã đồng bộ số tiền sử dụng gói $${aiUsage.creditLimitUsd}: Đã dùng $${aiUsage.totalUsedUsd.toFixed(
          2
        )} • Còn lại $${aiUsage.remainingUsd.toFixed(2)}!`,
      });
    }

    // Default action === "record": used by Mac external video scripts or services to log exact Vertex AI tokens & spend
    const providerRaw = String(body.provider || "mac_pipeline");
    const provider =
      providerRaw === "vertex" || providerRaw === "gemini_free"
        ? providerRaw
        : "mac_pipeline";

    const aiUsage = await recordAiUsageCall({
      provider,
      model: String(body.model || "vertex/gemini-4-argon"),
      feature: String(body.feature || "Pipeline Tạo Video Trên Mac"),
      usageMetadata: body.usageMetadata
        ? {
            promptTokenCount:
              body.usageMetadata.promptTokenCount !== undefined
                ? Number(body.usageMetadata.promptTokenCount)
                : undefined,
            candidatesTokenCount:
              body.usageMetadata.candidatesTokenCount !== undefined
                ? Number(body.usageMetadata.candidatesTokenCount)
                : undefined,
            thoughtsTokenCount:
              body.usageMetadata.thoughtsTokenCount !== undefined
                ? Number(body.usageMetadata.thoughtsTokenCount)
                : undefined,
            totalTokenCount:
              body.usageMetadata.totalTokenCount !== undefined
                ? Number(body.usageMetadata.totalTokenCount)
                : undefined,
          }
        : undefined,
      imageCount:
        body.imageCount !== undefined ? Number(body.imageCount) : undefined,
      isTts: Boolean(body.isTts),
      explicitCostUsd:
        body.costUsd !== undefined ? Number(body.costUsd) : undefined,
    });

    return Response.json({ ok: true, aiUsage });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Lỗi cập nhật bộ đếm Token & Chi phí.";
    return Response.json({ ok: false, error: message }, { status: 400 });
  }
}
