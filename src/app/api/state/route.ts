import { connection } from "next/server";
import { INITIAL_DEMO_STORE } from "@/lib/demo-data";
import { readStore, writeStore } from "@/lib/store";
import type { SavedIdea } from "@/lib/types";

export async function GET() {
  await connection();
  const store = await readStore();
  return Response.json(store);
}

export async function POST(request: Request) {
  const body = await request.json();
  const store = await readStore();

  switch (body.action) {
    case "setActiveChannel": {
      if (typeof body.channelId === "string") {
        store.activeChannelId = body.channelId;
      }
      break;
    }

    case "updateMilestone": {
      const ch = store.myChannels.find((c) => c.id === body.channelId);
      if (ch && Number(body.targetMilestone) > 0) {
        ch.targetMilestone = Number(body.targetMilestone);
      }
      break;
    }

    case "removeChannel": {
      store.myChannels = store.myChannels.filter((c) => c.id !== body.channelId);
      if (store.activeChannelId === body.channelId) {
        store.activeChannelId = store.myChannels[0]?.id || "";
      }
      break;
    }

    case "removeCompetitor": {
      store.competitors = store.competitors.filter(
        (c) => c.id !== body.competitorId
      );
      break;
    }

    case "addIdea": {
      const incoming = body.idea as Partial<SavedIdea>;
      const newIdea: SavedIdea = {
        id: `idea-${Date.now()}`,
        title: incoming.title || "Ý tưởng video mới",
        remakeTitle: incoming.remakeTitle || incoming.title || "",
        targetKeyword: incoming.targetKeyword || "",
        sourceVideoId: incoming.sourceVideoId,
        sourceVideoTitle: incoming.sourceVideoTitle,
        sourceChannelTitle: incoming.sourceChannelTitle,
        sourceThumbnailUrl: incoming.sourceThumbnailUrl,
        sourceOutlierScore: incoming.sourceOutlierScore,
        format: incoming.format === "short" ? "short" : "long",
        status: incoming.status || "backlog",
        notes: incoming.notes || "",
        tags: Array.isArray(incoming.tags) ? incoming.tags : [],
        checklist: incoming.checklist || {
          hook5s: false,
          peakValueCta: false,
          subConfirmationLink: false,
          pinnedCommentCta: false,
          endScreenSub: false,
        },
        createdAt: new Date().toISOString(),
      };
      store.ideas = [newIdea, ...store.ideas];
      break;
    }

    case "updateIdea": {
      const idx = store.ideas.findIndex((i) => i.id === body.ideaId);
      if (idx >= 0 && body.patch) {
        store.ideas[idx] = {
          ...store.ideas[idx],
          ...body.patch,
          checklist: body.patch.checklist
            ? { ...store.ideas[idx].checklist, ...body.patch.checklist }
            : store.ideas[idx].checklist,
        };
      }
      break;
    }

    case "deleteIdea": {
      store.ideas = store.ideas.filter((i) => i.id !== body.ideaId);
      break;
    }

    case "trackSmartClick": {
      const handle = String(body.handle || "").trim();
      if (handle) {
        store.smartLinkClicks[handle] = (store.smartLinkClicks[handle] || 0) + 1;
      }
      break;
    }

    case "toggleResolvedVideo": {
      const vid = String(body.videoId || "").trim();
      if (vid) {
        const current = new Set(store.resolvedVideoIds || []);
        if (current.has(vid)) {
          current.delete(vid);
        } else {
          current.add(vid);
        }
        store.resolvedVideoIds = Array.from(current);
      }
      break;
    }

    case "toggleAutoSync": {
      store.autoSyncOnOpen = Boolean(body.enabled);
      break;
    }

    case "skipPlanItem": {
      const itemId = String(body.itemId || "").trim();
      if (store.activePlan && itemId) {
        const idx = store.activePlan.items.findIndex((i) => i.id === itemId);
        if (idx >= 0) {
          const [picked] = store.activePlan.items.splice(idx, 1);
          store.activePlan.items.push(picked);
        }
      }
      break;
    }

    case "clearDemoData": {
      store.myChannels = store.myChannels.filter((c) => !c.isDemo);
      store.competitors = store.competitors.filter((c) => !c.isDemo);
      store.activeChannelId = store.myChannels[0]?.id || "";
      break;
    }

    case "resetDemoData": {
      const demo = structuredClone(INITIAL_DEMO_STORE);
      store.myChannels = [
        ...store.myChannels.filter((c) => !c.isDemo),
        ...demo.myChannels,
      ];
      store.competitors = [
        ...store.competitors.filter((c) => !c.isDemo),
        ...demo.competitors,
      ];
      if (!store.activeChannelId) {
        store.activeChannelId = store.myChannels[0]?.id || "";
      }
      break;
    }

    default:
      return Response.json(
        { error: "Hành động không hợp lệ." },
        { status: 400 }
      );
  }

  await writeStore(store);
  return Response.json(store);
}
