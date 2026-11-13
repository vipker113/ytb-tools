import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  generateLocalReupSeoPackage,
  type ReupLanguageMode,
  type ReupTitleLengthStyle,
  type ReupVibeCategory,
  type VisualFrameProfile,
} from "@/lib/reup-seo-generator";
import {
  ensureSessionDir,
  expandHomePath,
  isAllowedAudioFile,
  isAllowedVideoFile,
  resolveBuiltinBgmPath,
  runBeautyAnalyzer,
  runVideoRemaster,
} from "@/lib/reup-studio-server";
import { getEffectiveGeminiKey, readStore } from "@/lib/store";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const action = String(body.action || "");

    if (action === "listFolder") {
      const folderRaw = String(body.folderPath || "~/Downloads");
      const folderAbs = expandHomePath(folderRaw);
      if (!fs.existsSync(folderAbs)) {
        return Response.json(
          { ok: false, error: `Không tìm thấy thư mục: ${folderAbs}` },
          { status: 404 }
        );
      }
      const stat = fs.statSync(folderAbs);
      if (stat.isFile()) {
        if (!isAllowedVideoFile(folderAbs)) {
          return Response.json(
            { ok: false, error: "File được chọn không phải định dạng video (.mp4, .mov, .webm, .mkv)." },
            { status: 400 }
          );
        }
        return Response.json({
          ok: true,
          folderPath: path.dirname(folderAbs),
          files: [
            {
              name: path.basename(folderAbs),
              fullPath: folderAbs,
              sizeMb: Number((stat.size / (1024 * 1024)).toFixed(1)),
              mtimeMs: stat.mtimeMs,
            },
          ],
        });
      }

      const entries = fs.readdirSync(folderAbs, { withFileTypes: true });
      const files = entries
        .filter((e) => e.isFile() && isAllowedVideoFile(e.name) && !e.name.startsWith("._"))
        .map((e) => {
          const fullPath = path.join(folderAbs, e.name);
          const st = fs.statSync(fullPath);
          return {
            name: e.name,
            fullPath,
            sizeMb: Number((st.size / (1024 * 1024)).toFixed(1)),
            mtimeMs: st.mtimeMs,
          };
        })
        .sort((a, b) => b.mtimeMs - a.mtimeMs)
        .slice(0, 80);

      return Response.json({
        ok: true,
        folderPath: folderAbs,
        files,
      });
    }

    if (action === "scanLocalPath") {
      const videoAbs = expandHomePath(String(body.videoPath || ""));
      if (!fs.existsSync(videoAbs) || !isAllowedVideoFile(videoAbs)) {
        return Response.json(
          { ok: false, error: `Không tìm thấy file video hợp lệ tại: ${videoAbs}` },
          { status: 404 }
        );
      }
      const enhanceMode = ["beauty_glow", "crisp_hd", "raw_hd"].includes(String(body.enhanceMode))
        ? String(body.enhanceMode)
        : "beauty_glow";
      const sessionId =
        String(body.sessionId || "") ||
        `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
      const sessionDir = ensureSessionDir(sessionId);

      const result = await runBeautyAnalyzer([
        "scan",
        "--video",
        videoAbs,
        "--out-dir",
        sessionDir,
        "--top-k",
        "6",
        "--enhance",
        enhanceMode,
      ]);

      return Response.json({
        ...result,
        ok: true,
        sessionId: path.basename(sessionDir),
        videoPath: videoAbs,
        originalName: path.basename(videoAbs),
      });
    }

    if (action === "extractCustomTime") {
      const videoAbs = expandHomePath(String(body.videoPath || ""));
      if (!fs.existsSync(videoAbs)) {
        return Response.json(
          { ok: false, error: "Phiên làm việc video đã hết hạn, vui lòng chọn lại video." },
          { status: 404 }
        );
      }
      const timeSec = Math.max(0, Number(body.timeSec || 0));
      const enhanceMode = ["beauty_glow", "crisp_hd", "raw_hd"].includes(String(body.enhanceMode))
        ? String(body.enhanceMode)
        : "beauty_glow";
      const sessionDir = ensureSessionDir(String(body.sessionId || "sess_custom"));

      const result = await runBeautyAnalyzer([
        "extract",
        "--video",
        videoAbs,
        "--out-dir",
        sessionDir,
        "--time",
        timeSec.toFixed(3),
        "--enhance",
        enhanceMode,
      ]);

      return Response.json({
        ...result,
        ok: true,
        sessionId: path.basename(sessionDir),
      });
    }

    if (action === "exportBundleToDisk") {
      const defaultOutDir = path.join(os.homedir(), "Downloads", "Reup-Thumbnails-HD");
      const targetDir = body.targetDir
        ? expandHomePath(String(body.targetDir))
        : defaultOutDir;
      fs.mkdirSync(targetDir, { recursive: true });

      const rawBase = String(body.baseName || "video_reup")
        .replace(/\.[^.]+$/, "")
        .replace(/[^a-zA-Z0-9_\u00C0-\u024F\u1E00-\u1EFF -]/g, "_")
        .trim()
        .slice(0, 70) || "video_reup";

      let savedThumbPath = "";
      if (body.dataUrl && String(body.dataUrl).startsWith("data:image/")) {
        const str = String(body.dataUrl);
        const isPng = str.startsWith("data:image/png");
        const base64 = str.split(",")[1] || "";
        savedThumbPath = path.join(targetDir, `${rawBase}_thumbnail_hd.${isPng ? "png" : "jpg"}`);
        fs.writeFileSync(savedThumbPath, Buffer.from(base64, "base64"));
      } else if (body.sessionId && body.imageFile) {
        const sessionDir = ensureSessionDir(String(body.sessionId));
        const srcImg = path.join(sessionDir, path.basename(String(body.imageFile)));
        if (fs.existsSync(srcImg)) {
          const ext = path.extname(srcImg) || ".jpg";
          savedThumbPath = path.join(targetDir, `${rawBase}_thumbnail_hd${ext}`);
          fs.copyFileSync(srcImg, savedThumbPath);
        }
      }

      const seoText = String(body.seoTextContent || "");
      const savedSeoPath = path.join(targetDir, `${rawBase}_titles_tags.txt`);
      fs.writeFileSync(savedSeoPath, seoText, "utf-8");

      let savedVideoPath = "";
      if (body.sessionId && body.remasteredVideoFile) {
        const sessionDir = ensureSessionDir(String(body.sessionId));
        const srcVid = path.join(
          sessionDir,
          path.basename(String(body.remasteredVideoFile))
        );
        if (fs.existsSync(srcVid)) {
          savedVideoPath = path.join(targetDir, `${rawBase}_FullHD_SafeAudio.mp4`);
          fs.copyFileSync(srcVid, savedVideoPath);
        }
      }

      if (body.revealInFinder && process.platform === "darwin") {
        execFile("open", [targetDir], () => {});
      }

      return Response.json({
        ok: true,
        targetDir,
        savedThumbPath,
        savedSeoPath,
        savedVideoPath,
      });
    }

    if (action === "remasterVideo") {
      const videoRaw = String(body.videoPath || "");
      const videoAbs = expandHomePath(videoRaw);
      if (!videoRaw || !fs.existsSync(videoAbs) || !isAllowedVideoFile(videoAbs)) {
        return Response.json(
          { ok: false, error: "Không tìm thấy file video gốc để nâng cấp." },
          { status: 400 }
        );
      }

      const sessionId = String(body.sessionId || `sess_${Date.now()}`);
      const sessionDir = ensureSessionDir(sessionId);
      const outFileName = `remastered_hd_${Date.now()}.mp4`;
      const outAbs = path.join(sessionDir, outFileName);

      const qualityPreset = ["beauty_hd", "crisp_hd", "clean_upscale"].includes(
        String(body.qualityPreset || "")
      )
        ? String(body.qualityPreset)
        : "beauty_hd";

      const cropMode = ["auto_remove_bars", "force_9_16", "keep_original"].includes(
        String(body.cropMode || "")
      )
        ? String(body.cropMode)
        : "auto_remove_bars";

      const audioMode = ["replace_bgm", "anti_id_shift", "mute", "keep_original"].includes(
        String(body.audioMode || "")
      )
        ? String(body.audioMode)
        : "replace_bgm";

      const mirror = Boolean(body.mirror);
      const bgmStart = Number(body.bgmStart || 0);
      const bgmVolume = Number(body.bgmVolume ?? 1.0);
      const origMix = Number(body.origMix ?? 0.0);

      let resolvedBgm = "";
      if (audioMode === "replace_bgm") {
        const bgmSourceType = String(body.bgmSourceType || "builtin");
        if (bgmSourceType === "custom_path" && body.customAudioPath) {
          const customAbs = expandHomePath(String(body.customAudioPath));
          if (!fs.existsSync(customAbs) || !isAllowedAudioFile(customAbs)) {
            return Response.json(
              { ok: false, error: "Không tìm thấy file nhạc riêng bạn đã chọn." },
              { status: 400 }
            );
          }
          resolvedBgm = customAbs;
        } else {
          const builtinFile = String(body.builtinTrack || "sweet_douyin_bell.m4a");
          const builtinAbs = resolveBuiltinBgmPath(builtinFile);
          if (!fs.existsSync(builtinAbs)) {
            return Response.json(
              { ok: false, error: `Không tìm thấy nhạc nền có sẵn: ${builtinFile}` },
              { status: 404 }
            );
          }
          resolvedBgm = builtinAbs;
        }
      }

      const cliArgs: string[] = [
        "--video",
        videoAbs,
        "--out",
        outAbs,
        "--quality-preset",
        qualityPreset,
        "--crop-mode",
        cropMode,
        "--audio-mode",
        audioMode,
        "--bgm-start",
        String(Math.max(0, bgmStart)),
        "--bgm-volume",
        String(bgmVolume),
        "--orig-mix",
        String(origMix),
      ];
      if (mirror) {
        cliArgs.push("--mirror");
      }
      if (resolvedBgm) {
        cliArgs.push("--bgm-path", resolvedBgm);
      }

      const result = await runVideoRemaster(cliArgs);

      return Response.json({
        ...result,
        ok: true,
        sessionId: path.basename(sessionDir),
        remasteredFile: outFileName,
      });
    }

    if (action === "aiPolishSeo" || action === "analyzeFramesSeo") {
      const language = (body.language || "en") as ReupLanguageMode;
      const vibe = (body.vibe || "visual_smile") as ReupVibeCategory;
      const titleStyle: ReupTitleLengthStyle =
        body.titleStyle === "detailed" ? "detailed" : "short";
      const visualProfile = (body.visualProfile || null) as VisualFrameProfile | null;
      const customNote = String(body.customNote || "").trim();
      const videoName = String(body.videoName || "").trim();
      const isShort = body.isShort !== false;
      const channelHandle = String(body.channelHandle || "");
      const seed = Number(body.seed || 0);
      const sessionId = String(body.sessionId || "").trim();
      const selectedFile = path.basename(String(body.selectedFile || ""));

      const fallbackPkg = generateLocalReupSeoPackage({
        language,
        vibe,
        titleStyle,
        visualProfile,
        customNote,
        isShort,
        channelHandle,
        seed,
      });

      const store = await readStore();
      const geminiKey = getEffectiveGeminiKey(store);
      if (!geminiKey) {
        return Response.json({
          ok: true,
          usedAi: false,
          usedVision: false,
          seo: fallbackPkg,
        });
      }

      // Collect creator's real posted naming examples from synced channel(s), anchored by @asiangirlvibescute
      const postedExamples: string[] = [
        "Cute Chinese Girl ✨ | Douyin",
        "ASA Is So Adorable! ✨ | BABYMONSTER",
      ];
      for (const ch of store.myChannels || []) {
        const h = (ch.handle || "").toLowerCase();
        const isTargetChannel =
          h.includes("asiangirl") ||
          (channelHandle && h === channelHandle.toLowerCase());
        if (!isTargetChannel) continue;
        for (const v of (ch.recentVideos || []).slice(0, 12)) {
          const t = (v.title || "").trim();
          if (t && t.length <= 58 && !postedExamples.includes(t)) {
            postedExamples.push(t);
          }
        }
      }

      // Attach actual extracted video frames (`vision_strip.jpg` 3-frame contact sheet, or selected frame)
      const imageParts: Array<{ inlineData: { mimeType: string; data: string } }> = [];
      if (sessionId) {
        try {
          const sessionDir = ensureSessionDir(sessionId);
          const stripPath = path.join(sessionDir, "vision_strip.jpg");
          if (fs.existsSync(stripPath)) {
            const b64 = fs.readFileSync(stripPath).toString("base64");
            imageParts.push({
              inlineData: { mimeType: "image/jpeg", data: b64 },
            });
          } else if (selectedFile) {
            const candPath = path.join(sessionDir, selectedFile);
            if (fs.existsSync(candPath) && fs.statSync(candPath).size <= 2_500_000) {
              const b64 = fs.readFileSync(candPath).toString("base64");
              imageParts.push({
                inlineData: { mimeType: "image/jpeg", data: b64 },
              });
            }
          }
        } catch {
          // Proceed with text-only if session files unavailable
        }
      }

      const langNameMap: Record<ReupLanguageMode, string> = {
        en: "English (Natural, clean global YouTube style)",
        vi: "Vietnamese (Tiếng Việt tự nhiên, ngắn gọn, bắt trend)",
        vi_en: "Bilingual Vietnamese + English (Ngắn gọn 3-5 chữ Việt | Tag tiếng Anh)",
        ko: "Korean (한국어 짧고 센스있는 비주얼 제목)",
        zh: "Simplified Chinese (中文简短高点击颜值标题)",
        ja: "Japanese (日本語の短くて可愛いタイトル)",
      };

      const cleanHandle = channelHandle
        ? channelHandle.startsWith("@")
          ? channelHandle
          : `@${channelHandle}`
        : "@asiangirlvibescute";

      const styleRules =
        titleStyle === "short"
          ? `CRITICAL NAMING STYLE — MATCH THE CREATOR'S EXACT POSTED VIDEOS:
Here are real video titles already posted on the creator's channel (${cleanHandle}):
${postedExamples.slice(0, 8).map((ex) => `- "${ex}"`).join("\n")}

STRICT RULES FOR ALL 6 TITLES:
1. ULTRA-SHORT & PUNCHY: Every title MUST be 22 to 42 characters total (3 to 6 words maximum!). NEVER write long sentences.
2. EXACT SIGNATURE FORMAT: "<Short Visual Trait or Cute Reaction> <1 Emoji> | <1-2 Word Vibe / Origin / Outfit / Group>"
   - Good examples:
     • "Cute Chinese Girl ✨ | Douyin"
     • "ASA Is So Adorable! ✨ | BABYMONSTER"
     • "Doll-Like Blue Eyes ✨ | Douyin"
     • "Sweet Bangs & Smile 💖 | Ulzzang"
     • "Purple Fairy Dress 🌸 | Douyin"
     • "Chic Street Outfit 🖤 | OOTD"
3. GROUNDED IN THE ATTACHED VIDEO FRAMES: Look directly at the attached frame(s) and base the titles on REAL visible details (hairstyle/bangs/ponytail, eye color/glasses/wink/smile, outfit type & color like Hanfu/uniform/white top/black dress/streetwear/gym wear, setting like bridge/selfie/dance studio/beach, and cultural vibe like Douyin / Ulzzang / K-Pop / Kawaii / Cosplay).
4. DO NOT put "#Shorts" or any hashtags inside the titles! Keep "#Shorts" in the description and hashtags array.`
          : `TITLE STYLE: Hook-driven titles (45 to 72 characters) grounded directly in the visible details of the attached video frames${
              isShort ? " (append #Shorts on top 3 titles)" : ""
            }.`;

      const prompt = `You are the packaging specialist for the YouTube channel ${cleanHandle}.
${
  imageParts.length > 0
    ? "Carefully inspect the attached contact-sheet frame(s) extracted from the video (showing key moments from start to end)."
    : "Generate titles and metadata for this beauty/lifestyle video."
}

Context:
- Target Language: ${langNameMap[language] || langNameMap.en}
- Video filename hint (ignore if random numbers/hash): "${videoName}"
- Creator's optional note / idol / source name: "${customNote || "(none — infer purely from the visual frames)"}"
- Video format: ${isShort ? "Vertical Short" : "Horizontal Video"}

${styleRules}

DESCRIPTION RULES:
- Keep the description clean, short, and matching the creator's posted style:
  Line 1: A warm 1-sentence visual hook matching the clip (e.g. "Wait For Her Smile At The End 💖" or "A lovely moment featuring ...! ✨")
  Blank line
  Line 2: Short CTA (e.g. "👉 Hit Like 👍 & Subscribe")
  Blank line
  Line 3: Hashtags starting with ${isShort ? "#Shorts " : ""}followed by 6 specific hashtags matching the visual frame.

Return ONLY valid JSON with exact keys:
{
  "detectedVisualSummary": "Tóm tắt ngắn gọn bằng Tiếng Việt (8-16 từ) những đặc điểm nổi bật nhìn thấy trong khung hình: kiểu tóc, mắt/biểu cảm, trang phục/màu sắc, bối cảnh & vibe",
  "suggestedVibe": "one of: visual_smile | dance_trend | street_fashion | cosplay_trad | beach_travel | gym_sport",
  "titles": ["title 1", "title 2", "title 3", "title 4", "title 5", "title 6"],
  "description": "...",
  "hashtags": ["#Shorts", "#...", "..."],
  "studioTags": ["14 specific search tags matching what is visible in the frame"]
}`;

      const visionModels = [
        "gemini-3-flash-preview",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
      ];

      for (const model of visionModels) {
        try {
          const resp = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
              geminiKey
            )}`,
            {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                contents: [
                  {
                    parts: [...imageParts, { text: prompt }],
                  },
                ],
                generationConfig: {
                  temperature: 0.7,
                  responseMimeType: "application/json",
                },
              }),
              signal: AbortSignal.timeout(9500),
            }
          );
          if (!resp.ok) continue;
          const json = await resp.json();
          const parts: Array<{ text?: string; thought?: boolean }> =
            json?.candidates?.[0]?.content?.parts || [];
          const answerPart =
            parts.find((p) => !p.thought && p.text) || parts[parts.length - 1];
          const rawText = (answerPart?.text || "")
            .replace(/^```json\s*/i, "")
            .replace(/```\s*$/, "")
            .trim();
          if (!rawText) continue;
          const parsed = JSON.parse(rawText);
          if (Array.isArray(parsed.titles) && parsed.titles.length >= 3) {
            const rawTags: string[] = Array.isArray(parsed.studioTags)
              ? parsed.studioTags.map(String)
              : fallbackPkg.studioTags;
            const fitted: string[] = [];
            let len = 0;
            for (const t of rawTags) {
              const c = t.replace(/,/g, " ").trim();
              if (!c) continue;
              const nl = len === 0 ? c.length : len + 2 + c.length;
              if (nl > 480) break;
              fitted.push(c);
              len = nl;
            }
            const csv = fitted.join(", ");
            const cleanedTitles = parsed.titles.slice(0, 6).map((t: unknown) => {
              const s = String(t || "").trim();
              return titleStyle === "short"
                ? s.replace(/\s*#shorts\b/gi, "").trim()
                : s;
            });
            const hashtagsOut = Array.isArray(parsed.hashtags)
              ? parsed.hashtags.map((h: string) =>
                  String(h).startsWith("#") ? String(h) : `#${h}`
                )
              : fallbackPkg.hashtags;
            if (
              isShort &&
              !hashtagsOut.some((h: string) => h.toLowerCase() === "#shorts")
            ) {
              hashtagsOut.unshift("#Shorts");
            }
            const validVibes: ReupVibeCategory[] = [
              "visual_smile",
              "dance_trend",
              "street_fashion",
              "cosplay_trad",
              "beach_travel",
              "gym_sport",
            ];
            const suggestedVibe = validVibes.includes(parsed.suggestedVibe)
              ? (parsed.suggestedVibe as ReupVibeCategory)
              : undefined;

            return Response.json({
              ok: true,
              usedAi: true,
              usedVision: imageParts.length > 0,
              modelUsed: model,
              suggestedVibe,
              seo: {
                titles: cleanedTitles,
                description: String(parsed.description || fallbackPkg.description),
                hashtags: hashtagsOut,
                studioTags: fitted,
                studioTagsCsv: csv,
                studioTagsCharCount: csv.length,
                detectedVisualSummary:
                  String(parsed.detectedVisualSummary || "").trim() ||
                  fallbackPkg.detectedVisualSummary,
              },
            });
          }
        } catch {
          // Try next model in chain or fallback cleanly
        }
      }

      return Response.json({
        ok: true,
        usedAi: false,
        usedVision: false,
        seo: fallbackPkg,
      });
    }

    return Response.json({ ok: false, error: "Action không hợp lệ" }, { status: 400 });
  } catch (err) {
    return Response.json(
      { ok: false, error: err instanceof Error ? err.message : "Lỗi máy chủ" },
      { status: 500 }
    );
  }
}
