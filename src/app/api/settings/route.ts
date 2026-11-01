import { readStore, writeStore } from "@/lib/store";
import { testYoutubeApiKey } from "@/lib/youtube";

export async function POST(request: Request) {
  try {
    const body = await request.json();

    if (body.action === "testYoutubeKey") {
      const keyToTest = String(body.youtubeApiKey || "").trim();
      const result = await testYoutubeApiKey(keyToTest);
      return Response.json(result);
    }

    const store = await readStore();
    if (body.action === "disconnectYoutubeOAuth") {
      store.youtubeOAuth = null;
      await writeStore(store);
      return Response.json({
        ok: true,
        store,
        message: "Đã ngắt kết nối tài khoản YouTube Studio.",
      });
    }

    if (typeof body.youtubeApiKey === "string") {
      store.settings.youtubeApiKey = body.youtubeApiKey.trim();
    }
    if (typeof body.geminiApiKey === "string") {
      store.settings.geminiApiKey = body.geminiApiKey.trim();
    }
    if (typeof body.geminiModel === "string" && body.geminiModel.trim()) {
      store.settings.geminiModel = body.geminiModel.trim();
    }
    if (typeof body.googleClientId === "string") {
      store.settings.googleClientId = body.googleClientId.trim();
    }
    if (typeof body.googleClientSecret === "string") {
      store.settings.googleClientSecret = body.googleClientSecret.trim();
    }
    if (typeof body.defaultCountryCode === "string") {
      store.settings.defaultCountryCode = body.defaultCountryCode.trim() || "VN";
    }

    await writeStore(store);
    return Response.json({
      ok: true,
      store,
      message: "Đã lưu cấu hình thành công!",
    });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Lỗi khi lưu cài đặt.";
    return Response.json({ ok: false, error: message }, { status: 400 });
  }
}
