import { getEffectiveYoutubeKey, readStore } from "@/lib/store";
import { analyzeKeywordLiveOrDemo } from "@/lib/youtube";

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const keyword = String(body.keyword || "").trim();
    const store = await readStore();
    const apiKey = getEffectiveYoutubeKey(store);

    const hasViChars =
      /[ăâđêôơưĂÂĐÊÔƠƯáàảãạấầẩẫậắằẳẵặéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứứửữựýỳỷỹỵ]/.test(
        keyword
      );
    const regionCode = body.regionCode
      ? String(body.regionCode)
      : hasViChars
      ? "VN"
      : store.settings.defaultCountryCode || "US";

    const result = await analyzeKeywordLiveOrDemo({
      keyword,
      apiKey,
      regionCode,
    });

    return Response.json(result);
  } catch (err) {
    const message =
      err instanceof Error ? err.message : "Không thể phân tích từ khóa lúc này.";
    return Response.json({ error: message }, { status: 400 });
  }
}
