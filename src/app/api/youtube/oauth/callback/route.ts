import { connection } from "next/server";
import { readStore, writeStore } from "@/lib/store";
import { exchangeYoutubeAuthCode } from "@/lib/youtube-studio";

export async function GET(request: Request) {
  await connection();
  const reqUrl = new URL(request.url);
  const origin = reqUrl.origin;
  const code = reqUrl.searchParams.get("code");
  const oauthError = reqUrl.searchParams.get("error");

  if (oauthError || !code) {
    return Response.redirect(
      `${origin}/?oauth=error&reason=${encodeURIComponent(
        oauthError || "Bạn đã hủy cấp quyền OAuth."
      )}`
    );
  }

  try {
    const store = await readStore();
    const clientId = (store.settings.googleClientId || "").trim();
    const clientSecret = (store.settings.googleClientSecret || "").trim();

    if (!clientId || !clientSecret) {
      throw new Error("Thiếu Google Client ID hoặc Client Secret trong hệ thống.");
    }

    const oauthState = await exchangeYoutubeAuthCode({
      code,
      clientId,
      clientSecret,
    });

    store.youtubeOAuth = oauthState;
    store.autopilotLogs = [
      {
        id: `log-${Date.now()}`,
        timestamp: new Date().toISOString(),
        type: "system" as const,
        message: `🔐 Đã kết nối trực tiếp quyền quản trị YouTube Studio cho kênh: ${
          oauthState.connectedChannelTitle || "YouTube Channel"
        } (${oauthState.connectedChannelHandle || oauthState.connectedChannelId || "OK"}).`,
      },
      ...(store.autopilotLogs || []),
    ].slice(0, 25);

    await writeStore(store);
    return Response.redirect(`${origin}/?oauth=connected`);
  } catch (err) {
    const reason =
      err instanceof Error ? err.message : "Lỗi xác thực OAuth với Google.";
    return Response.redirect(
      `${origin}/?oauth=error&reason=${encodeURIComponent(reason)}`
    );
  }
}
