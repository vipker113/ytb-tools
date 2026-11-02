import { connection } from "next/server";
import { readStore } from "@/lib/store";
import type { YoutubePlaylistSummary } from "@/lib/types";
import {
  createChannelPlaylist,
  getValidYoutubeAccessToken,
  listChannelPlaylists,
} from "@/lib/youtube-studio";

let playlistCache: {
  channelKey: string;
  fetchedAt: number;
  playlists: YoutubePlaylistSummary[];
} | null = null;

export async function GET(request: Request) {
  await connection();
  try {
    const url = new URL(request.url);
    const force = url.searchParams.get("force") === "1";

    const store = await readStore();
    if (!store.youtubeOAuth?.refreshToken) {
      return Response.json({
        ok: true,
        connected: false,
        playlists: [],
      });
    }

    const channelKey = store.youtubeOAuth.connectedChannelId || "default";
    if (
      !force &&
      playlistCache &&
      playlistCache.channelKey === channelKey &&
      Date.now() - playlistCache.fetchedAt < 30_000
    ) {
      return Response.json({
        ok: true,
        connected: true,
        cached: true,
        playlists: playlistCache.playlists,
      });
    }

    const accessToken = await getValidYoutubeAccessToken(store);
    const playlists = await listChannelPlaylists(accessToken);

    playlistCache = {
      channelKey,
      fetchedAt: Date.now(),
      playlists,
    };

    return Response.json({
      ok: true,
      connected: true,
      playlists,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        connected: false,
        playlists: [],
        error:
          err instanceof Error
            ? err.message
            : "Không thể tải danh sách Playlist từ YouTube Studio.",
      },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const title = String(body.title || "").trim();
    const description = String(body.description || "").trim();
    const privacyRaw = String(body.privacyStatus || "public");
    const privacyStatus: "public" | "unlisted" | "private" =
      privacyRaw === "private" || privacyRaw === "unlisted"
        ? privacyRaw
        : "public";

    if (!title) {
      return Response.json(
        { ok: false, error: "Vui lòng nhập tên Playlist mới." },
        { status: 400 }
      );
    }

    const store = await readStore();
    const accessToken = await getValidYoutubeAccessToken(store);
    const created = await createChannelPlaylist({
      accessToken,
      title,
      description,
      privacyStatus,
    });

    const refreshed = await listChannelPlaylists(accessToken).catch(() => [
      created,
      ...(playlistCache?.playlists || []),
    ]);

    playlistCache = {
      channelKey: store.youtubeOAuth?.connectedChannelId || "default",
      fetchedAt: Date.now(),
      playlists: refreshed,
    };

    return Response.json({
      ok: true,
      created,
      playlists: refreshed,
      message: `📂 Đã tạo Playlist mới "${created.title}" trên YouTube Studio!`,
    });
  } catch (err) {
    return Response.json(
      {
        ok: false,
        error:
          err instanceof Error
            ? err.message
            : "Không thể tạo Playlist mới trên YouTube Studio.",
      },
      { status: 500 }
    );
  }
}
