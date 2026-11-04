import { connection } from "next/server";
import {
  discoverSameNichePeers,
  resolvePartnerFromInput,
  verifyPartnersViaYoutubeOAuth,
} from "@/lib/cross-sub";
import { getEffectiveYoutubeKey, readStore, writeStore } from "@/lib/store";
import type {
  CrossSubPartner,
  CrossSubSourcePlatform,
  CrossSubStatus,
  DiscoveredNichePeer,
} from "@/lib/types";
import { getValidYoutubeAccessToken } from "@/lib/youtube-studio";

export async function GET() {
  await connection();
  const store = await readStore();
  return Response.json({
    partners: store.crossSubPartners || [],
    lastCrossSubAuditAt: store.lastCrossSubAuditAt || null,
    smartLinkClicks: store.smartLinkClicks || {},
  });
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const store = await readStore();
    const partners: CrossSubPartner[] = Array.isArray(store.crossSubPartners)
      ? [...store.crossSubPartners]
      : [];

    switch (body.action) {
      case "addPartner": {
        const apiKey = getEffectiveYoutubeKey(store);
        if (!apiKey) {
          return Response.json(
            {
              error:
                "Chưa có YouTube Data API v3 Key. Vui lòng kiểm tra mục Cài Đặt & API.",
            },
            { status: 400 }
          );
        }

        const rawInput = String(body.rawInput || "").trim();
        const initialStatus: CrossSubStatus =
          body.initialStatus === "need_my_sub" ||
          body.initialStatus === "completed" ||
          body.initialStatus === "unsubscribed"
            ? body.initialStatus
            : "waiting_their_sub";

        const sourcePlatform: CrossSubSourcePlatform =
          body.sourcePlatform === "niche_finder_us" ||
          body.sourcePlatform === "facebook_zalo" ||
          body.sourcePlatform === "reddit_discord" ||
          body.sourcePlatform === "youtube_comment"
            ? body.sourcePlatform
            : "facebook_zalo";

        const subAccountUsed =
          String(body.subAccountUsed || "").trim() || "Acc phụ / Clone";
        const notes = String(body.notes || "").trim();
        const markPublicSubConfirmed = Boolean(body.confirmedPublicSub);

        const resolved = await resolvePartnerFromInput({ rawInput, apiKey });
        const nowIso = new Date().toISOString();

        const existingIdx = partners.findIndex(
          (p) => p.channelId === resolved.channelId
        );

        let savedPartner: CrossSubPartner;
        if (existingIdx >= 0) {
          const prev = partners[existingIdx];
          savedPartner = {
            ...prev,
            ...resolved,
            latestVideoId: resolved.latestVideoId || prev.latestVideoId,
            latestVideoTitle: resolved.latestVideoTitle || prev.latestVideoTitle,
            status: initialStatus,
            subAccountUsed: subAccountUsed || prev.subAccountUsed,
            notes: notes || prev.notes,
            publicSubState: markPublicSubConfirmed
              ? "confirmed_public_sub"
              : prev.publicSubState,
            theySubscribedAt:
              markPublicSubConfirmed || initialStatus === "completed"
                ? prev.theySubscribedAt || nowIso
                : prev.theySubscribedAt,
            iSubscribedAt:
              initialStatus === "waiting_their_sub" ||
              initialStatus === "completed"
                ? prev.iSubscribedAt || nowIso
                : prev.iSubscribedAt,
            updatedAt: nowIso,
          };
          partners[existingIdx] = savedPartner;
        } else {
          savedPartner = {
            id: `csub-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            ...resolved,
            sourcePlatform,
            subAccountUsed,
            status: initialStatus,
            iSubscribedAt:
              initialStatus === "waiting_their_sub" ||
              initialStatus === "completed"
                ? nowIso
                : undefined,
            theySubscribedAt:
              markPublicSubConfirmed ||
              initialStatus === "need_my_sub" ||
              initialStatus === "completed"
                ? nowIso
                : undefined,
            publicSubState: markPublicSubConfirmed
              ? "confirmed_public_sub"
              : "unchecked",
            notes,
            createdAt: nowIso,
            updatedAt: nowIso,
          };
          partners.unshift(savedPartner);
        }

        store.crossSubPartners = partners;
        await writeStore(store);

        return Response.json({
          store,
          partner: savedPartner,
          message:
            existingIdx >= 0
              ? `Đã cập nhật kênh đối tác "${savedPartner.title}"!`
              : `Đã thêm "${savedPartner.title}" (Điểm an toàn CTR: ${savedPartner.nicheMatchScore}/100)!`,
        });
      }

      case "addDiscoveredPartner": {
        const peer = body.peer as DiscoveredNichePeer | undefined;
        if (!peer?.channelId) {
          return Response.json(
            { error: "Thiếu thông tin kênh đối tác." },
            { status: 400 }
          );
        }

        const subAccountUsed =
          String(body.subAccountUsed || "").trim() || "Acc phụ / Clone";
        const initialStatus: CrossSubStatus =
          body.initialStatus === "waiting_their_sub"
            ? "waiting_their_sub"
            : "need_my_sub";
        const nowIso = new Date().toISOString();

        const existingIdx = partners.findIndex(
          (p) => p.channelId === peer.channelId
        );

        let savedPartner: CrossSubPartner;
        if (existingIdx >= 0) {
          savedPartner = {
            ...partners[existingIdx],
            updatedAt: nowIso,
          };
        } else {
          savedPartner = {
            id: `csub-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
            channelId: peer.channelId,
            handle: peer.handle,
            title: peer.title,
            description: peer.description,
            thumbnailUrl: peer.thumbnailUrl,
            country: peer.country,
            subscribers: peer.subscribers,
            videoCount: peer.videoCount,
            totalViews: peer.totalViews,
            latestVideoId: peer.sampleVideoId,
            latestVideoTitle: peer.sampleVideoTitle,
            nicheMatchScore: peer.nicheMatchScore,
            nicheSafetyTier: peer.nicheSafetyTier,
            nicheReasonVi: peer.nicheReasonVi,
            sourcePlatform: "niche_finder_us",
            subAccountUsed,
            status: initialStatus,
            iSubscribedAt:
              initialStatus === "waiting_their_sub" ? nowIso : undefined,
            publicSubState: "unchecked",
            notes: `Tìm từ ngách Science US • Short mẫu: ${peer.sampleVideoTitle}`,
            createdAt: nowIso,
            updatedAt: nowIso,
          };
          partners.unshift(savedPartner);
        }

        store.crossSubPartners = partners;
        await writeStore(store);

        return Response.json({
          store,
          partner: savedPartner,
          message: `Đã lưu "${savedPartner.title}" vào Sổ Giao Lưu Cùng Ngách!`,
        });
      }

      case "updatePartner": {
        const partnerId = String(body.partnerId || "").trim();
        const idx = partners.findIndex((p) => p.id === partnerId);
        if (idx < 0) {
          return Response.json(
            { error: "Không tìm thấy kênh đối tác trong danh sách." },
            { status: 404 }
          );
        }

        const prev = partners[idx];
        const patch = (body.patch || {}) as Partial<CrossSubPartner>;
        const nowIso = new Date().toISOString();

        const nextStatus: CrossSubStatus = patch.status || prev.status;
        let iSubscribedAt =
          patch.iSubscribedAt !== undefined
            ? patch.iSubscribedAt
            : prev.iSubscribedAt;
        let theySubscribedAt =
          patch.theySubscribedAt !== undefined
            ? patch.theySubscribedAt
            : prev.theySubscribedAt;

        if (
          (nextStatus === "waiting_their_sub" || nextStatus === "completed") &&
          !iSubscribedAt
        ) {
          iSubscribedAt = nowIso;
        }
        if (nextStatus === "completed" && !theySubscribedAt) {
          theySubscribedAt = nowIso;
        }

        partners[idx] = {
          ...prev,
          ...patch,
          status: nextStatus,
          iSubscribedAt,
          theySubscribedAt,
          updatedAt: nowIso,
        };

        store.crossSubPartners = partners;
        await writeStore(store);

        return Response.json({
          store,
          partner: partners[idx],
          message: `Đã cập nhật trạng thái của "${partners[idx].title}".`,
        });
      }

      case "deletePartner": {
        const partnerId = String(body.partnerId || "").trim();
        store.crossSubPartners = partners.filter((p) => p.id !== partnerId);
        await writeStore(store);
        return Response.json({
          store,
          message: "Đã xóa kênh khỏi Sổ Sub Chéo.",
        });
      }

      case "discoverNichePeers": {
        const apiKey = getEffectiveYoutubeKey(store);
        if (!apiKey) {
          return Response.json(
            {
              error:
                "Chưa có YouTube Data API v3 Key. Vui lòng kiểm tra mục Cài Đặt & API.",
            },
            { status: 400 }
          );
        }

        const keyword =
          String(body.keyword || "").trim() ||
          "deep ocean science mystery #shorts";
        const minSubs = Math.max(0, Number(body.minSubs ?? 20));
        const maxSubs = Math.max(minSubs + 10, Number(body.maxSubs ?? 10000));
        const regionCode = String(body.regionCode || "US").trim() || "US";

        const activeChannel =
          store.myChannels.find((c) => c.id === store.activeChannelId) ||
          store.myChannels[0];

        const existingIds = new Set(partners.map((p) => p.channelId));
        const peers = await discoverSameNichePeers({
          keyword,
          minSubs,
          maxSubs,
          regionCode,
          apiKey,
          existingChannelIds: existingIds,
          myChannelId:
            store.youtubeOAuth?.connectedChannelId || activeChannel?.id,
        });

        return Response.json({
          peers,
          message: `Tìm thấy ${peers.length} kênh nhỏ cùng ngách phù hợp để giao lưu giảm hại CTR!`,
        });
      }

      case "verifyOAuthSubs": {
        if (!store.youtubeOAuth?.refreshToken) {
          return Response.json(
            {
              error:
                "Chưa kết nối OAuth YouTube Studio. Vui lòng kết nối OAuth ở mục Cài Đặt & API để đối soát người đăng ký.",
            },
            { status: 400 }
          );
        }

        const accessToken = await getValidYoutubeAccessToken(store);
        const audit = await verifyPartnersViaYoutubeOAuth({
          accessToken,
          partners,
        });

        const nowIso = new Date().toISOString();
        store.crossSubPartners = audit.updatedPartners;
        store.lastCrossSubAuditAt = nowIso;
        await writeStore(store);

        return Response.json({
          store,
          summary: {
            confirmedCount: audit.confirmedCount,
            unsubscribedCount: audit.unsubscribedCount,
            privateOrPendingCount: audit.privateOrPendingCount,
            publicSubscribersScanned: audit.publicSubscribersScanned,
            recentPublicSubscribers: audit.recentPublicSubscribers,
          },
          message: `Đã đối soát ${audit.publicSubscribersScanned} người đăng ký công khai: ${audit.confirmedCount} kênh xác nhận đã Sub${
            audit.unsubscribedCount > 0
              ? `, phát hiện ${audit.unsubscribedCount} kênh hủy Sub!`
              : "!"
          }`,
        });
      }

      default:
        return Response.json(
          { error: "Hành động không hợp lệ." },
          { status: 400 }
        );
    }
  } catch (err) {
    const msg =
      err instanceof Error ? err.message : "Lỗi xử lý yêu cầu Sub Chéo.";
    return Response.json({ error: msg }, { status: 500 });
  }
}
