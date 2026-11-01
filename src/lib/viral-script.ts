import type { VideoItem } from "./types";

export interface ViralScene {
  timestamp: string;
  visualDirection: string;
  voiceover: string;
}

export interface ViralShortBlueprint {
  topic: string;
  winningTitles: string[];
  first3sHook: {
    visualPrompt: string;
    voiceover: string;
  };
  scenes: ViralScene[];
  subTriggerLine: string;
  infiniteLoopBridge: string;
  pinnedDebateComment: string;
  readyDescription: string;
  tags: string[];
  whyItConvertsSubs: string;
}

export interface VideoRescueDiagnosis {
  videoId: string;
  originalTitle: string;
  cleanedTitle: string;
  views: number;
  durationSeconds: number;
  outlierScore: number;
  issues: string[];
  quickWins: string[];
  suggestedPinnedComment: string;
  appendDescriptionBlock: string;
}

export function diagnoseExistingVideosForSubRescue(
  videos: VideoItem[],
  channelHandle: string
): VideoRescueDiagnosis[] {
  const handle = channelHandle.startsWith("@")
    ? channelHandle
    : `@${channelHandle}`;

  return videos.map((v) => {
    const issues: string[] = [];
    const quickWins: string[] = [];

    // 1. Check hashtag clutter or mismatched hashtags in title
    const hasHashtagsInTitle = /#\w+/.test(v.title);
    const cleanedTitle = v.title
      .replace(/#\S+/g, "")
      .replace(/\s+\?/g, "?")
      .replace(/\s{2,}/g, " ")
      .trim();

    if (hasHashtagsInTitle) {
      const lowerTitle = cleanedTitle.toLowerCase();
      if (/#venus/i.test(v.title) && !lowerTitle.includes("venus")) {
        issues.push(
          "Tiêu đề chứa hashtag sai chủ đề (#venus trên video không nói về Sao Kim) làm lệch tệp khán giả đề xuất ban đầu."
        );
      } else {
        issues.push(
          "Tiêu đề dính cụm #hashtag ở cuối gây rối mắt trên Shorts Feed và giảm CTR."
        );
      }
      quickWins.push(`Đổi tiêu đề sạch gọn thành: "${cleanedTitle}"`);
    }

    // 2. Check hidden likes / 0 likes on high-view videos
    if (v.views >= 150 && v.likes === 0) {
      issues.push(
        `Video đạt ${v.views} views nhưng hiển thị 0 Likes (có thể đang tắt 'Show how many viewers like this video' trong YouTube Studio).`
      );
      quickWins.push(
        "Bật hiển thị số lượt Thích trong YouTube Studio để tạo hiệu ứng tin cậy (Social Proof) giúp người lạ dễ bấm Subscribe hơn."
      );
    }

    // 3. Check duration sweet spot for Shorts
    if (v.durationSeconds >= 70 && v.durationSeconds <= 180) {
      issues.push(
        `Thời lượng ${v.durationSeconds}s khá dài cho kênh mới — đòi hỏi tỷ lệ giữ chân rất cao mới vượt được ngưỡng 400–1.200 views.`
      );
      quickWins.push(
        "Với các tập mới, rút gọn kịch bản về khung vàng 38–48 giây (giống tập 39s đạt 1.268 views của bạn) kèm câu kết nối vòng lặp (Loop)."
      );
    }

    // 4. Check ?sub_confirmation=1 link in description
    if (!v.description.toLowerCase().includes("sub_confirmation=1")) {
      issues.push("Phần mô tả chưa gắn link Đăng ký 1-Click (?sub_confirmation=1).");
      quickWins.push(
        "Dán thêm khối Subscribe CTA + Pinned Comment bên dưới vào video này trên YouTube Studio."
      );
    }

    const coreSubject = cleanedTitle.replace(/[?!.]+$/, "");
    const suggestedPinnedComment = `Quick question for curious minds: What surprised you most about "${coreSubject}"—and what strange phenomenon should Proof of Wonder uncover next? 👇🔬`;

    const appendDescriptionBlock = [
      ``,
      `🔬 Subscribe to Proof of Wonder for daily strange science:`,
      `👉 https://www.youtube.com/${handle}?sub_confirmation=1`,
      ``,
      `#scienceshorts #science #curiosity`,
    ].join("\n");

    return {
      videoId: v.id,
      originalTitle: v.title,
      cleanedTitle,
      views: v.views,
      durationSeconds: v.durationSeconds,
      outlierScore: v.outlierScore,
      issues,
      quickWins,
      suggestedPinnedComment,
      appendDescriptionBlock,
    };
  });
}

export async function generateViralShortBlueprint(params: {
  topic: string;
  sourceOutlierTitle?: string;
  channelTitle: string;
  channelHandle: string;
  geminiApiKey: string;
  preferredModel?: string;
}): Promise<{
  blueprint: ViralShortBlueprint;
  usedAi: boolean;
  modelUsed: string;
}> {
  const handle = params.channelHandle.startsWith("@")
    ? params.channelHandle
    : `@${params.channelHandle}`;
  const topic = params.topic.trim();

  const fallback: ViralShortBlueprint = {
    topic,
    winningTitles: [
      `What Actually Happens If ${topic}?`,
      `Why ${topic} Defies Common Sense`,
      `Scientists Were Shocked by What's Inside ${topic}`,
      `The Strange Physics Behind ${topic}`,
    ],
    first3sHook: {
      visualPrompt:
        "Extreme close-up cinematic 3D/visual cutaway with dramatic contrast lighting and immediate motion in frame 1",
      voiceover: `...which means if you ever stepped into ${topic}, physics starts acting completely backwards.`,
    },
    scenes: [
      {
        timestamp: "00:00 - 00:08",
        visualDirection: "Fast visual zoom showing scale comparison next to a human silhouette",
        voiceover: `Most people assume ${topic} works just like everything on Earth's surface—but there's a hidden catch.`,
      },
      {
        timestamp: "00:08 - 00:22",
        visualDirection: "Cross-section diagram / animated mechanism revealing the core scientific force",
        voiceover:
          "Under extreme pressure and density differences, ordinary matter crosses a threshold where normal rules break down.",
      },
      {
        timestamp: "00:22 - 00:35",
        visualDirection: "Dramatic payoff visual showing the real-world consequence",
        voiceover:
          "Instead of dispersing, it traps energy in a razor-thin boundary layer that scientists can actually measure.",
      },
      {
        timestamp: "00:35 - 00:44 (Climax + Loop)",
        visualDirection:
          "Subtle text badge 'Subscribe to Proof of Wonder' for 2.5s while visual seamlessly morphs back to frame 1",
        voiceover:
          "Follow Proof of Wonder for daily strange science—because this tiny shift in density is the exact reason...",
      },
    ],
    subTriggerLine:
      "Follow Proof of Wonder for daily strange science (hiển thị text gọn ở giây 35 ngay sau khoảnh khắc giải mã bất ngờ nhất, KHÔNG làm màn hình đen cuối video!)",
    infiniteLoopBridge:
      "Câu cuối kết thúc lửng bằng '...is the exact reason' nối thẳng về câu mở đầu giây 00:00 '...which means if you ever stepped into...', khiến người xem nghe sang vòng thứ 2 mới nhận ra — đẩy Average Percentage Viewed vượt > 105%!",
    pinnedDebateComment: `Be honest: Did you think ${topic} worked like this before watching, or what's the weirdest science question we should test next? 👇🔬`,
    readyDescription: `Discover the hidden science behind ${topic}—and why reality is stranger than movies make it look.\n\n🔬 Subscribe to Proof of Wonder (1-Click): https://www.youtube.com/${handle}?sub_confirmation=1\n🎬 More strange science Shorts: https://www.youtube.com/${handle}/shorts\n\n#scienceshorts #science #space`,
    tags: [
      topic.toLowerCase(),
      "science shorts",
      "proof of wonder",
      "strange science",
      "physics explained",
      "space mysteries",
      "how the universe works",
      "scientific phenomena",
    ],
    whyItConvertsSubs:
      "Kết hợp khung thời lượng vàng 44 giây + Mở đầu nghịch lý trực quan + Kết thúc nối vòng lặp (Infinite Loop) giúp vượt ngưỡng test 1.200 views lên 10.000–100.000+ views trên US Shorts Feed.",
  };

  if (!params.geminiApiKey) {
    return { blueprint: fallback, usedAi: false, modelUsed: "template" };
  }

  const prompt = `You are an elite US YouTube Science Shorts Showrunner (behind channels like Cleo Abram, Zack D. Films, Veritasium Shorts, and AstroKobi).
Build a complete, high-retention 45-second Infinite-Loop YouTube Short blueprint for the channel "${params.channelTitle}" (${handle}).

Topic / Idea: "${topic}"
${params.sourceOutlierTitle ? `Inspired by proven viral Outlier title: "${params.sourceOutlierTitle}"` : ""}

CRITICAL RULES FOR MAXIMUM REAL SUBSCRIBERS ON YOUTUBE SHORTS:
1. All English scripts, titles, description, tags, and pinned comment MUST be in crisp, fascinating, 100% accurate US English (zero clickbait lies, real awe-inspiring science, zero hashtags in titles!).
2. Total voiceover length across scenes MUST be ~110-130 words (40-46 seconds at brisk narration pace).
3. Design a SEAMLESS INFINITE LOOP: the final words of the last scene must grammatically flow directly into the first words of first3sHook.voiceover!
4. Place a natural 5-word Subscribe micro-trigger right after the climax reveal (~second 34), NEVER at the start and NEVER as a dead outro screen.
5. Write "infiniteLoopBridge" and "whyItConvertsSubs" in VIETNAMESE so the Vietnamese channel owner understands how to edit and publish it.

Return pure JSON matching this exact schema:
{
  "topic": "${topic}",
  "winningTitles": ["4 punchy US English titles, 40-60 chars, NO hashtags, strong curiosity gap"],
  "first3sHook": {
    "visualPrompt": "Exact 0-3s visual/3D/footage prompt that stops scrolling immediately",
    "voiceover": "Opening spoken hook sentence (must connect smoothly from the final scene's last words!)"
  },
  "scenes": [
    { "timestamp": "00:03 - 00:13", "visualDirection": "...", "voiceover": "..." },
    { "timestamp": "00:13 - 00:25", "visualDirection": "...", "voiceover": "..." },
    { "timestamp": "00:25 - 00:36", "visualDirection": "...", "voiceover": "... (the mind-blowing scientific mechanism/reveal)" },
    { "timestamp": "00:36 - 00:45 (Sub Trigger + Loop)", "visualDirection": "...", "voiceover": "... (includes brief 'Subscribe to Proof of Wonder for daily strange science' + loop cliffhanger into 00:00)" }
  ],
  "subTriggerLine": "Exact micro-CTA sentence used at ~00:36",
  "infiniteLoopBridge": "Giải thích ngắn gọn bằng tiếng Việt cách câu cuối khớp mượt với câu đầu để tạo Loop >105% thời lượng xem",
  "pinnedDebateComment": "1 engaging US English question to pin in comments that sparks replies/debate",
  "readyDescription": "US English SEO description (250-450 chars) including https://www.youtube.com/${handle}?sub_confirmation=1 and 3 clean hashtags at the bottom",
  "tags": ["12 high-search US English science tags strictly relevant to this topic"],
  "whyItConvertsSubs": "Giải thích bằng tiếng Việt lý do tâm lý học khiến chủ đề & kịch bản này kéo Subscribers thật mạnh trên thị trường Mỹ"
}`;

  const cleanPreferred =
    params.preferredModel && !params.preferredModel.includes("argon")
      ? params.preferredModel
      : "gemini-3.8-flash";
  const models = Array.from(
    new Set([
      cleanPreferred,
      "gemini-3.8-flash",
      "gemini-3.6-flash",
      "gemini-3.5-flash",
    ])
  );
  for (const model of models) {
    try {
      const genConfig: Record<string, unknown> = {
        temperature: 0.75,
        responseMimeType: "application/json",
      };
      if (model.includes("3.8") || model.includes("3.7")) {
        genConfig.thinkingConfig = { thinkingBudget: 256 };
      }

      const res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
          params.geminiApiKey
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
      const cleaned = rawText.replace(/^```json\s*/i, "").replace(/```\s*$/, "");
      const parsed = JSON.parse(cleaned) as Partial<ViralShortBlueprint>;
      if (parsed.winningTitles && parsed.scenes && parsed.first3sHook) {
        return {
          usedAi: true,
          modelUsed: model,
          blueprint: {
            topic: parsed.topic || topic,
            winningTitles: parsed.winningTitles,
            first3sHook: parsed.first3sHook,
            scenes: parsed.scenes,
            subTriggerLine: parsed.subTriggerLine || fallback.subTriggerLine,
            infiniteLoopBridge:
              parsed.infiniteLoopBridge || fallback.infiniteLoopBridge,
            pinnedDebateComment:
              parsed.pinnedDebateComment || fallback.pinnedDebateComment,
            readyDescription:
              parsed.readyDescription || fallback.readyDescription,
            tags: Array.isArray(parsed.tags) ? parsed.tags : fallback.tags,
            whyItConvertsSubs:
              parsed.whyItConvertsSubs || fallback.whyItConvertsSubs,
          },
        };
      }
    } catch {
      // try next model
    }
  }

  return { blueprint: fallback, usedAi: false, modelUsed: "fallback" };
}
