import type {
  GrowthPlanItem,
  GrowthSprintPlan,
  StoreData,
  VideoItem,
} from "./types";

interface TimingBucket {
  id: string;
  label: string;
  count: number;
  totalViews: number;
  avgViews: number;
}

export function analyzeChannelTimingVn(videos: VideoItem[]): {
  bestWindow: string;
  secondaryWindow: string;
  insight: string;
  buckets: TimingBucket[];
} {
  const bucketDefs = [
    {
      id: "morning",
      label: "07:00 – 12:00 Giờ VN (20h–01h đêm Mỹ)",
      match: (h: number) => h >= 7 && h < 12,
    },
    {
      id: "afternoon",
      label: "12:00 – 16:00 Giờ VN (01h–05h sáng Mỹ)",
      match: (h: number) => h >= 12 && h < 16,
    },
    {
      id: "golden_eu_us",
      label: "16:00 – 19:00 Giờ VN (Chiều Châu Âu + Bình minh Mỹ)",
      match: (h: number) => h >= 16 && h < 19,
    },
    {
      id: "us_prime",
      label: "20:00 – 23:30 Giờ VN (09h–12h30 trưa Mỹ)",
      match: (h: number) => h >= 19 || h < 7,
    },
  ];

  const buckets: TimingBucket[] = bucketDefs.map((b) => {
    const matched = videos.filter((v) => {
      const d = new Date(v.publishedAt);
      const vnHour = (d.getUTCHours() + 7) % 24;
      return b.match(vnHour);
    });
    const totalViews = matched.reduce((s, v) => s + v.views, 0);
    return {
      id: b.id,
      label: b.label,
      count: matched.length,
      totalViews,
      avgViews:
        matched.length > 0 ? Math.round(totalViews / matched.length) : 0,
    };
  });

  const nonEmpty = buckets
    .filter((b) => b.count > 0)
    .sort((a, b) => b.avgViews - a.avgViews);

  if (nonEmpty.length >= 2) {
    const best = nonEmpty[0];
    const worst = nonEmpty[nonEmpty.length - 1];
    const ratio =
      worst.avgViews > 0
        ? (best.avgViews / worst.avgViews).toFixed(1)
        : "3.5";
    return {
      bestWindow: best.label,
      secondaryWindow: "21:30 – 23:00 Giờ VN (Giờ nghỉ trưa Bờ Đông Mỹ)",
      insight: `Phân tích ${videos.length} video thực tế trên kênh: Đăng vào khung ${best.label} đạt trung bình ${best.avgViews.toLocaleString(
        "vi-VN"
      )} views/video — cao gấp ${ratio} lần so với khung ${worst.label} (${worst.avgViews.toLocaleString(
        "vi-VN"
      )} views/video)!`,
      buckets,
    };
  }

  return {
    bestWindow: "16:30 – 18:30 Giờ VN",
    secondaryWindow: "22:00 – 23:00 Giờ VN",
    insight:
      "Khung 16:30 – 18:30 Giờ VN đón trọn sóng chiều Châu Âu và sóng thức dậy buổi sáng tại Bờ Đông Hoa Kỳ (EDT).",
    buckets,
  };
}

function addDaysIso(baseDate: Date, offsetDays: number): string {
  const d = new Date(baseDate.getTime() + offsetDays * 86_400_000);
  return d.toISOString().slice(0, 10);
}

export function buildDefaultDescription(
  title: string,
  hook: string,
  handle: string
): string {
  const cleanHandle = handle.startsWith("@") ? handle : `@${handle}`;
  return [
    `${title} — ${hook.replace(/^\.\.\.\s*/, "")}`,
    ``,
    `🔬 Subscribe to Proof of Wonder for daily strange science:`,
    `👉 https://www.youtube.com/${cleanHandle}?sub_confirmation=1`,
    ``,
    `#ScienceShorts #Science #Space #ProofOfWonder`,
  ].join("\n");
}

export function buildDefaultTags(title: string): string[] {
  const words = title
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, "")
    .split(/\s+/)
    .filter((w) => w.length > 3)
    .slice(0, 4);
  return Array.from(
    new Set([
      words.join(" "),
      ...words,
      "science shorts",
      "proof of wonder",
      "strange science",
      "physics explained",
      "space mysteries",
    ])
  ).filter(Boolean);
}

export async function generateNextGrowthSprint(
  store: StoreData,
  options?: {
    fastMode?: boolean;
  }
): Promise<GrowthSprintPlan> {
  const channel =
    store.myChannels.find((c) => c.id === store.activeChannelId) ||
    store.myChannels[0];

  const subs = channel?.subscribers || 0;
  const videoCount = channel?.videoCount || 0;
  const handle = channel?.handle || "@proofofwonderscience";
  const channelTitle = channel?.title || "Proof of Wonder";
  const sprintNumber = (store.completedSprintsCount || 0) + 1;

  const timing = analyzeChannelTimingVn(channel?.recentVideos || []);

  // Gather channel's own top winners
  const ownWinners = [...(channel?.recentVideos || [])]
    .sort((a, b) => b.views - a.views)
    .slice(0, 3);

  // Gather unused top competitor outliers
  const usedTitles = new Set<string>([
    ...(store.ideas || []).map((i) => i.title.toLowerCase()),
    ...(store.activePlan?.items || []).map((i) => i.title.toLowerCase()),
  ]);

  const compOutliers: VideoItem[] = [];
  for (const c of store.competitors) {
    for (const v of c.videos) {
      if (!usedTitles.has(v.title.toLowerCase())) {
        compOutliers.push(v);
      }
    }
  }
  compOutliers.sort((a, b) => b.outlierScore - a.outlierScore);
  const topOutliers = compOutliers.slice(0, 5);

  const targetSubsGoal =
    subs < 50
      ? Math.max(subs + 35, 50)
      : subs < 100
      ? 100
      : subs < 500
      ? subs + 150
      : subs + Math.round(subs * 0.25);

  const now = new Date();
  const geminiKey = (store.settings.geminiApiKey || "").trim();

  const fallbackItems: GrowthPlanItem[] = [
    {
      id: `plan-${sprintNumber}-1`,
      dayLabel: "Bước 1 (Hôm nay)",
      scheduledDate: addDaysIso(now, 0),
      vnPublishWindow: "17:00 – 18:15 Giờ VN",
      strategyType: "competitor_outlier",
      title: "Why the Sun Should Actually Be Silent—Yet NASA Recorded Its Roar",
      hook3s:
        "...which means if space had air for just one second, the Sun would sound like a chainsaw roaring right next to your ear.",
      voiceoverScript:
        "Space is a vacuum, so sound waves shouldn't travel at all. Yet solar physicists at Stanford and NASA tracked massive pressure waves churning across the Sun's surface—vibrations ten thousand miles wide. Even from 93 million miles away, if air filled the gap between Earth and the Sun, it would blast your eardrums at 100 decibels nonstop, day and night. Follow Proof of Wonder for daily strange science—because that hidden solar vibration...",
      description: buildDefaultDescription(
        "Why the Sun Should Actually Be Silent—Yet NASA Recorded Its Roar",
        "If space had air for just one second, the Sun would blast Earth at 100 decibels nonstop.",
        handle
      ),
      tags: [
        "sound of the sun",
        "nasa sun audio",
        "space sound",
        "solar physics",
        "science shorts",
        "space mysteries",
        "proof of wonder",
      ],
      pinnedComment:
        "Imagine hearing a 100dB roar in the sky 24/7—how long could humans stay sane if space transmitted sound? 👇☀️",
      whySelected:
        "Lấy cảm hứng từ Outlier 6.36x của Cleo Abram ('The Sun Is Weirder Than You Think').",
      expectedGoal: "Mở khóa 1.500+ views & kéo +6–12 Subscribers",
      status: "pending",
    },
    {
      id: `plan-${sprintNumber}-2`,
      dayLabel: "Bước 2 (Ngày mai)",
      scheduledDate: addDaysIso(now, 1),
      vnPublishWindow: "17:00 – 18:15 Giờ VN",
      strategyType: "sequel_winner",
      title: "What Happens If a Submarine Hits an Underwater Lake?",
      hook3s:
        "...and that extreme salt barrier is so dense that a multi-ton research submarine literally bounces off it like solid concrete.",
      voiceoverScript:
        "When deep-sea pilots steer a submersible down onto an ocean-floor brine pool, they can't just dive straight in. The water inside is up to five times saltier than the surrounding sea, creating an invisible liquid floor with actual waves lapping against a toxic shoreline. Pushing the thrusters down sends ripples across the lake while deadly hydrogen sulfide paralyzes anything that swims across. Subscribe to Proof of Wonder for daily strange science...",
      pinnedComment:
        "Does seeing ripples on a lake AT THE BOTTOM of the ocean break your brain too, or did SpongeBob's Goo Lagoon actually get science right? 👇🌊",
      whySelected:
        "Phần 2 trực tiếp ăn theo video 'The Deadly Lakes Hidden Beneath the Ocean' (1.246 views) — thuật toán YouTube tự động đẩy cho chính 1.246 người vừa xem Phần 1!",
      expectedGoal: "Tỷ lệ bấm Sub gấp 4–5 lần từ tệp khán giả quay lại",
      status: "pending",
    },
    {
      id: `plan-${sprintNumber}-3`,
      dayLabel: "Bước 3 (Ngày +2)",
      scheduledDate: addDaysIso(now, 2),
      vnPublishWindow: "17:00 – 18:15 Giờ VN",
      strategyType: "sequel_winner",
      title: "What Happens If You Try Jumping on a Neutron Star?",
      hook3s:
        "...because before your boots even bent to jump, gravity two hundred billion times stronger than Earth's would flatten you into a layer of atoms.",
      voiceoverScript:
        "On the Moon you can leap ten feet high, and on an asteroid you could accidentally launch yourself into orbit. But step onto a neutron star—a collapsed giant sun crushed to the size of a city—and dropping from just one millimeter high slams you down at four million miles per hour. A single teaspoon of the ground beneath your feet weighs as much as Mount Everest. Follow Proof of Wonder for daily strange science...",
      pinnedComment:
        "Which world would you rather test in a superhero suit: an asteroid where 1 jump puts you in orbit, or surviving 1 second near a neutron star? 👇🚀",
      whySelected:
        "Phần 2 nối tiếp video số 1 của kênh 'How High Could You Jump on Other Worlds?' (1.268 views — 39s).",
      expectedGoal: "Đánh trúng tệp Space/Physics cốt lõi, mục tiêu 2.000+ views",
      status: "pending",
    },
    {
      id: `plan-${sprintNumber}-4`,
      dayLabel: "Bước 4 (Ngày +3)",
      scheduledDate: addDaysIso(now, 3),
      vnPublishWindow: "17:15 – 18:30 Giờ VN",
      strategyType: "competitor_outlier",
      title: "The Runaway Star Flying Fast Enough to Escape Our Galaxy",
      hook3s:
        "...tearing through space at nearly four million miles per hour—so fast it could cross from Earth to the Moon in just six minutes.",
      voiceoverScript:
        "Most stars orbit our galaxy calmly, including our Sun. But astronomers spotted a hypervelocity star known as S5-HVS1rocketing out of the Milky Way forever. Four million years ago, it wandered too close to our galaxy's supermassive black hole, which violently slingshotted it into intergalactic darkness like a cosmic cannonball. Subscribe to Proof of Wonder for daily strange science—because right now that lone star is still...",
      pinnedComment:
        "Imagine living on a planet orbiting that star—watching the entire Milky Way shrink behind you forever. Terrifying or peaceful? 👇✨",
      whySelected:
        "Nhân bản từ Outlier 6.06x của AstroKobi ('The Fastest Star Ever Discovered') kết hợp đúng sở trường Space của kênh bạn.",
      expectedGoal: "Mở rộng tệp khán giả yêu thiên văn học Mỹ",
      status: "pending",
    },
    {
      id: `plan-${sprintNumber}-5`,
      dayLabel: "Bước 5 (Ngày +4)",
      scheduledDate: addDaysIso(now, 4),
      vnPublishWindow: "17:00 – 18:15 Giờ VN",
      strategyType: "competitor_outlier",
      title: "Why Mosquitoes Lock Onto One Person and Ignore Everyone Else",
      hook3s:
        "...which is why two people can sit side by side all evening while one gets eaten alive and the other gets zero bites.",
      voiceoverScript:
        "It's not 'sweet blood'—it's an invisible chemical plume rising off your skin. Scientists at Rockefeller University found that mosquito magnets produce drastically higher levels of carboxylic acids in their natural skin oils. Worse, mosquitoes have backup sensors, so even when researchers disabled one smell receptor, the insects still tracked those exact same people from fifty feet away. Follow Proof of Wonder for daily strange science...",
      pinnedComment:
        "Are you the 'human shield' who gets 15 mosquito bites while your friend gets 0, or are you the lucky immune one? 👇🦟",
      whySelected:
        "Chuyển thể từ Siêu Outlier 23.0x của MinuteEarth — chủ đề đời sống khoa học chạm tới 100% người xem phổ thông!",
      expectedGoal: "Bùng nổ bình luận chia sẻ cá nhân (đẩy mạnh đề xuất Shorts Feed)",
      status: "pending",
    },
  ];

  for (const item of fallbackItems) {
    if (!item.description) {
      item.description = buildDefaultDescription(
        item.title,
        item.hook3s,
        handle
      );
    }
    if (!item.tags || item.tags.length === 0) {
      item.tags = buildDefaultTags(item.title);
    }
  }

  let aiSummary = `Sprint #${sprintNumber}: Tập trung nhân bản 2 chủ đề thắng lớn nhất kênh (>1.200 views) thành chuỗi Phần 2 để gom khán giả cũ bấm Subscribe, kết hợp 3 chủ đề Outlier 6x–23x từ đối thủ và cố định giờ đăng vàng 17:00–18:30 Giờ VN.`;
  let finalItems = fallbackItems;

  if (geminiKey) {
    const prompt = `You are an autonomous YouTube Growth Autopilot planning Sprint #${sprintNumber} for the US English Science Shorts channel "${channelTitle}" (${handle}).
Current stats: ${subs} subscribers, ${videoCount} videos. Target milestone for this 5-day sprint: ${targetSubsGoal} subscribers.
Proven best upload window in Vietnam time: "${timing.bestWindow}".

Channel's own top winning videos:
${ownWinners.map((v) => `- "${v.title}" (${v.views} views, ${v.durationSeconds}s)`).join("\n")}

Competitors' top live viral Outlier videos not yet covered:
${topOutliers
  .map(
    (v) =>
      `- [${v.outlierScore}x Outlier on ${v.channelTitle}] "${v.title}" (${v.views} views)`
  )
  .join("\n")}

Create a 5-Day Autonomous Growth Sprint Plan (Sprint #${sprintNumber}):
- Step 1 & Step 2: Sequels / adjacent spin-offs to the channel's own winning videos (to re-capture returning viewers, who subscribe at 5x higher rate!).
- Step 3, 4, 5: High-retention 42-46s Infinite-Loop Science Shorts adapted from the top competitor Outliers above.
- ALL "title", "hook3s", "voiceoverScript" (~95-115 words, ending with a seamless loop phrase + subtle "Subscribe to Proof of Wonder for daily strange science"), "description" (with https://www.youtube.com/${handle}?sub_confirmation=1 and 3 clean hashtags), "tags" (8 relevant English science tags), and "pinnedComment" MUST be in crisp, captivating US English (NO hashtags in title!).
- "strategicSummary", "dayLabel", "whySelected", and "expectedGoal" MUST be in clear VIETNAMESE.

Return pure JSON matching:
{
  "strategicSummary": "2-3 câu tóm tắt chiến lược Sprint #${sprintNumber} bằng tiếng Việt",
  "items": [
    {
      "dayLabel": "Ngày 1",
      "vnPublishWindow": "17:00 – 18:15 Giờ VN",
      "strategyType": "sequel_winner",
      "title": "...",
      "hook3s": "...",
      "voiceoverScript": "...",
      "description": "...",
      "tags": ["..."],
      "pinnedComment": "...",
      "whySelected": "...",
      "expectedGoal": "..."
    }
  ]
}`;

    const preferred =
      store.settings.geminiModel &&
      !store.settings.geminiModel.includes("argon")
        ? store.settings.geminiModel
        : "gemini-3.8-flash";
    const models = options?.fastMode
      ? ["gemini-3.6-flash", "gemini-3.5-flash"]
      : Array.from(
          new Set([preferred, "gemini-3.6-flash", "gemini-3.5-flash"])
        );
    for (const model of models) {
      try {
        const genConfig: Record<string, unknown> = {
          temperature: 0.72,
          responseMimeType: "application/json",
        };
        if (model.includes("3.8") || model.includes("3.7")) {
          genConfig.thinkingConfig = { thinkingBudget: 256 };
        }

        const res = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
            geminiKey
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

        const cleaned = rawText
          .replace(/^```json\s*/i, "")
          .replace(/```\s*$/, "");
        const parsed = JSON.parse(cleaned) as {
          strategicSummary?: string;
          items?: Array<Partial<GrowthPlanItem>>;
        };

        if (Array.isArray(parsed.items) && parsed.items.length >= 3) {
          aiSummary = parsed.strategicSummary || aiSummary;
          finalItems = parsed.items.map((it, idx) => {
            const cleanTitle = (
              it.title ||
              fallbackItems[idx]?.title ||
              "Science Short"
            )
              .replace(/#\S+/g, "")
              .trim();
            const cleanHook = it.hook3s || fallbackItems[idx]?.hook3s || "";
            return {
              id: `plan-${sprintNumber}-${idx + 1}-${Date.now()}`,
              dayLabel: it.dayLabel || `Ngày ${idx + 1}`,
              scheduledDate: addDaysIso(now, idx),
              vnPublishWindow: it.vnPublishWindow || "17:00 – 18:15 Giờ VN",
              strategyType:
                it.strategyType === "competitor_outlier" ||
                it.strategyType === "channel_optimization"
                  ? it.strategyType
                  : "sequel_winner",
              title: cleanTitle,
              hook3s: cleanHook,
              voiceoverScript:
                it.voiceoverScript || fallbackItems[idx]?.voiceoverScript || "",
              description:
                it.description ||
                buildDefaultDescription(cleanTitle, cleanHook, handle),
              tags:
                Array.isArray(it.tags) && it.tags.length > 0
                  ? it.tags
                  : buildDefaultTags(cleanTitle),
              pinnedComment:
                it.pinnedComment || fallbackItems[idx]?.pinnedComment || "",
              whySelected:
                it.whySelected || fallbackItems[idx]?.whySelected || "",
              expectedGoal: it.expectedGoal || "+10–20 Subscribers thật",
              status: "pending",
            };
          });
          break;
        }
      } catch {
        // fallback if AI fails
      }
    }
  }

  return {
    id: `sprint-${sprintNumber}-${Date.now()}`,
    sprintNumber,
    createdAt: now.toISOString(),
    basedOnSubscribers: subs,
    basedOnVideoCount: videoCount,
    targetSubscribersGoal: targetSubsGoal,
    bestPublishWindowVn: timing.bestWindow,
    publishTimingInsight: timing.insight,
    strategicSummary: aiSummary,
    autoContinueEnabled: true,
    items: finalItems,
  };
}
