import { connection } from "next/server";
import { readStore } from "@/lib/store";
import { buildYoutubeOAuthUrl } from "@/lib/youtube-studio";

export async function GET(request: Request) {
  await connection();
  const store = await readStore();
  const clientId = (store.settings.googleClientId || "").trim();

  const origin = new URL(request.url).origin;
  if (!clientId) {
    return Response.redirect(
      `${origin}/?oauth=error&reason=${encodeURIComponent(
        "Chưa cấu hình Google OAuth Client ID."
      )}`
    );
  }

  const authUrl = buildYoutubeOAuthUrl(clientId);
  return Response.redirect(authUrl);
}
