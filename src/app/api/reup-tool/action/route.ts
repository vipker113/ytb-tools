import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  generateLocalReupSeoPackage,
  type ReupLanguageMode,
  type ReupVibeCategory,
} from "@/lib/reup-seo-generator";
import {
  ensureSessionDir,
  expandHomePath,
  isAllowedVideoFile,
  runBeautyAnalyzer,
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

      if (body.revealInFinder && process.platform === "darwin") {
        execFile("open", [targetDir], () => {});
      }

      return Response.json({
        ok: true,
        targetDir,
        savedThumbPath,
        savedSeoPath,
      });
    }

    if (action === "aiPolishSeo") {
      const language = (body.language || "vi") as ReupLanguageMode;
      const vibe = (body.vibe || "visual_smile") as ReupVibeCategory;
      const customNote = String(body.customNote || "");
      const isShort = body.isShort !== false;
      const channelHandle = String(body.channelHandle || "");
      const seed = Number(body.seed || 0);

      const fallbackPkg = generateLocalReupSeoPackage({
        language,
        vibe,
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
          seo: fallbackPkg,
        });
      }

      const langNameMap: Record<ReupLanguageMode, string> = {
        vi: "Vietnamese (Tiếng Việt tự nhiên, bắt trend giới trẻ Việt Nam)",
        en: "English (Natural viral YouTube/Reels global style)",
        vi_en: "Bilingual Vietnamese + English (Song ngữ Việt - Anh ngắn gọn, thu hút)",
        ko: "Korean (한국어 유튜브 쇼츠/릴스 인기 스타일)",
        zh: "Simplified Chinese (中文热门短视频/纯欲街拍高点击风格)",
        ja: "Japanese (日本語のバズるショート動画・透明感美少女スタイル)",
      };

      const prompt = `You are a YouTube SEO & High-CTR Packaging Specialist for an aesthetic beauty / dance / fashion / lifestyle channel.
Generate 6 click-worthy, platform-safe video titles, 1 concise SEO description, 8 trending hashtags, and 14 search tags.
- Language: ${langNameMap[language] || langNameMap.vi}
- Format: ${isShort ? "YouTube Shorts (vertical short video, append #Shorts on top 3 titles)" : "Standard HD horizontal/full video"}
- Vibe category: ${vibe}
- Specific video note/detail: ${customNote || "(general captivating beauty/visuals/charm)"}

Return ONLY valid JSON with exact keys:
{
  "titles": ["...", "...", "...", "...", "...", "..."],
  "description": "...",
  "hashtags": ["#...", "#..."],
  "studioTags": ["tag1", "tag2", "..."]
}`;

      try {
        const model = "gemini-2.5-flash";
        const resp = await fetch(
          `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${encodeURIComponent(
            geminiKey
          )}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              contents: [{ parts: [{ text: prompt }] }],
              generationConfig: {
                temperature: 0.85,
                responseMimeType: "application/json",
              },
            }),
          }
        );
        if (resp.ok) {
          const json = await resp.json();
          const rawText =
            json?.candidates?.[0]?.content?.parts?.[0]?.text || "";
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
            return Response.json({
              ok: true,
              usedAi: true,
              seo: {
                titles: parsed.titles.slice(0, 6).map(String),
                description: String(parsed.description || fallbackPkg.description),
                hashtags: Array.isArray(parsed.hashtags)
                  ? parsed.hashtags.map((h: string) =>
                      String(h).startsWith("#") ? String(h) : `#${h}`
                    )
                  : fallbackPkg.hashtags,
                studioTags: fitted,
                studioTagsCsv: csv,
                studioTagsCharCount: csv.length,
              },
            });
          }
        }
      } catch {
        // Fallback cleanly to instant local engine
      }

      return Response.json({
        ok: true,
        usedAi: false,
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
