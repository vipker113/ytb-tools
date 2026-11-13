export type ReupLanguageMode = "vi" | "en" | "vi_en" | "ko" | "zh" | "ja";

export type ReupVibeCategory =
  | "visual_smile"
  | "dance_trend"
  | "street_fashion"
  | "cosplay_trad"
  | "beach_travel"
  | "gym_sport";

export type ReupTitleLengthStyle = "short" | "detailed";

export interface VisualFrameProfile {
  shot_type?: "closeup_selfie" | "portrait" | "half_body" | "full_body";
  dominant_palette?: string;
  lighting_mood?: string;
  motion_level?: "calm_pose" | "dance_motion";
  suggested_vibe?: ReupVibeCategory;
  has_pillarbox?: boolean;
  summary_vi?: string;
}

export interface ReupSeoInput {
  language: ReupLanguageMode;
  vibe: ReupVibeCategory;
  titleStyle?: ReupTitleLengthStyle;
  visualProfile?: VisualFrameProfile | null;
  customNote?: string;
  isShort: boolean;
  channelHandle?: string;
  seed?: number;
}

export interface ReupSeoPackage {
  titles: string[];
  description: string;
  hashtags: string[];
  studioTags: string[];
  studioTagsCsv: string;
  studioTagsCharCount: number;
  detectedVisualSummary?: string;
}

interface VibeLexicon {
  defaultFocus: Record<ReupLanguageMode, string>;
  titleTemplates: Record<ReupLanguageMode, string[]>;
  descIntro: Record<ReupLanguageMode, string>;
  ctaLine: Record<ReupLanguageMode, string>;
  hashtags: Record<ReupLanguageMode, string[]>;
  tags: Record<ReupLanguageMode, string[]>;
}

const VIBE_DATA: Record<ReupVibeCategory, VibeLexicon> = {
  visual_smile: {
    defaultFocus: {
      vi: "Visual trong trẻo & nụ cười tỏa nắng",
      en: "Effortless natural beauty & radiant smile",
      vi_en: "Visual cực phẩm • Radiant Smile",
      ko: "심쿵하는 청순 미모와 눈웃음",
      zh: "治愈系甜美笑容与神仙颜值",
      ja: "透明感あふれる笑顔と美少女ビジュアル",
    },
    titleTemplates: {
      vi: [
        "{focus} khiến người xem không thể rời mắt ✨",
        "Chỉ 3 giây đầu thôi đã đủ hiểu vì sao clip này triệu view 💖 | {focus}",
        "Nụ cười gây thương nhớ nhất hôm nay 🥰 | {focus}",
        "Góc nghiêng thần thánh & visual cực phẩm không góc chết ✨ ({focus})",
        "Xem đi xem lại vẫn thấy cuốn 💕 | {focus}",
        "Vibe nhẹ nhàng trong trẻo đúng chuẩn nàng thơ 🌸 | {focus}",
        "Ánh mắt biết cười đốn tim mọi ánh nhìn 💫 | {focus}",
        "Visual mộc mạc nhưng sức hút không đùa được đâu ✨ | {focus}",
      ],
      en: [
        "{focus} That Instantly Brightens Your Day ✨",
        "Wait For Her Smile At The End 💖 | {focus}",
        "Unmatched Natural Visuals & Effortless Charm ✨ ({focus})",
        "3 Seconds Is All It Takes To Fall For This Vibe 🥰 | {focus}",
        "Pure Aesthetic Glow & Sweetest Eye Smile 🌸 | {focus}",
        "Why Everyone Keeps Rewatching This Clip 💫 | {focus}",
        "Camera Loves Her Every Single Angle ✨ | {focus}",
        "Soft Visuals & Golden Hour Perfection 💖 | {focus}",
      ],
      vi_en: [
        "{focus} khiến ai xem cũng đứng hình ✨ | Pure Visuals",
        "Nụ cười đốn tim ngay giây đầu tiên 💖 | Sweetest Smile Ever",
        "Góc nghiêng cực phẩm không góc chết ✨ | Stunning Natural Beauty",
        "Xem lại lần thứ 10 vẫn cuốn 🥰 | Aesthetic Girl Vibe",
        "Visual nàng thơ trong trẻo ✨ | {focus}",
        "Ánh mắt biết cười cực cuốn hút 💫 | Unforgettable Charm",
      ],
      ko: [
        "3초 만에 심쿵하게 만드는 역대급 비주얼 ✨ | {focus}",
        "끝까지 보면 무조건 반하는 눈웃음 여신 💖 | {focus}",
        "분위기 자체가 화보 그 자체인 청순 미녀 🌸 | {focus}",
        "무한 반복 재생 부르는 레전드 직캠 모먼트 ✨ | {focus}",
        "카메라가 다 못 담는 실물 느낌 여신 비주얼 💫",
        "보는 순간 기분 좋아지는 상큼 미소 🥰 | {focus}",
      ],
      zh: [
        "只看三秒就沦陷的神仙颜值 ✨ | {focus}",
        "回眸一笑百媚生！这氛围感真的绝了 💖 | {focus}",
        "纯欲天花板级别的甜美笑容 🥰 | {focus}",
        "越看越上头的治愈系美女，建议反复观看 ✨",
        "生图直出都这么美！360度无死角颜值 🌸 | {focus}",
        "心动瞬间！这个眼神谁顶得住啊 💫 | {focus}",
      ],
      ja: [
        "たった3秒で恋に落ちる圧倒的透明感 ✨ | {focus}",
        "最後の笑顔が可愛すぎて無限ループ確定 💖 | {focus}",
        "どこを切り取っても絵になる天使ビジュアル 🌸 | {focus}",
        "癒やし効果抜群のナチュラル美少女 ✨ | {focus}",
        "目が合った瞬間にドキッとする可愛さ 💫",
        "清楚系ビジュアルの最高峰 🥰 | {focus}",
      ],
    },
    descIntro: {
      vi: "Khoảnh khắc visual trong trẻo, thần thái tự nhiên và nụ cười cuốn hút sắc nét chuẩn HD.",
      en: "High-definition aesthetic moments featuring effortless natural beauty, radiant smiles, and captivating charm.",
      vi_en: "Khoảnh khắc visual cực phẩm chuẩn HD — Captivating natural beauty & sweetest aesthetic vibes.",
      ko: "보는 것만으로도 힐링되는 고화질 청순 비주얼 & 심쿵 미소 모음입니다.",
      zh: "高清治愈系美女合集，记录最动人的甜美笑容与绝美氛围感瞬间。",
      ja: "見ているだけで癒やされる高画質ナチュラル美少女＆最高の笑顔クリップ。",
    },
    ctaLine: {
      vi: "👉 Đừng quên bấm Like 👍 và Đăng ký kênh để đón xem những video gái xinh chất lượng HD mới nhất mỗi ngày nhé!",
      en: "👉 Hit Like 👍 & Subscribe for daily HD aesthetic visuals and trending clips!",
      vi_en: "👉 Bấm Like & Subscribe để xem thêm nhiều clip HD cuốn hút mỗi ngày! / Subscribe for daily HD visuals!",
      ko: "👉 좋아요와 구독을 눌러주시면 매일 새로운 고화질 비주얼 영상을 만나보실 수 있어요!",
      zh: "👉 喜欢的话记得点赞👍并订阅频道，每天更新高清高颜值精选视频！",
      ja: "👉 高評価＆チャンネル登録で毎日の高画質トレンド動画をチェックしてくださいね！",
    },
    hashtags: {
      vi: ["#gaixinh", "#visual", "#xuhuong", "#girlxinh", "#tiktokvn", "#nangtho"],
      en: ["#prettygirl", "#aesthetic", "#visuals", "#naturalbeauty", "#viralclip", "#trending"],
      vi_en: ["#gaixinh", "#prettygirl", "#visuals", "#xuhuong", "#aesthetic", "#girlxinh"],
      ko: ["#미녀", "#비주얼", "#여신", "#청순", "#심쿵", "#인기급상승"],
      zh: ["#美女", "#神仙颜值", "#氛围感", "#纯欲", "#甜美", "#热门"],
      ja: ["#美少女", "#可愛い", "#透明感", "#癒やし", "#天使", "#トレンド"],
    },
    tags: {
      vi: [
        "gái xinh",
        "gai xinh",
        "gái xinh tiktok",
        "girl xinh",
        "gái đẹp",
        "visual cực phẩm",
        "nụ cười tỏa nắng",
        "góc nghiêng thần thánh",
        "nàng thơ",
        "gái xinh việt nam",
        "gái xinh châu á",
        "video gái xinh hd",
        "xu hướng",
        "clip ngắn triệu view",
      ],
      en: [
        "pretty girl",
        "natural beauty",
        "stunning visuals",
        "cute smile",
        "aesthetic girl",
        "asian beauty",
        "ulzzang girl",
        "viral beauty clip",
        "effortless charm",
        "golden hour aesthetic",
        "trending girls",
        "hd portrait video",
      ],
      vi_en: [
        "gái xinh",
        "girl xinh",
        "pretty girl",
        "stunning visuals",
        "gái xinh tiktok",
        "asian beauty",
        "natural beauty",
        "cute girl smile",
        "nàng thơ",
        "aesthetic vibe",
        "trending reels",
        "gái đẹp hd",
      ],
      ko: [
        "미녀",
        "여신 비주얼",
        "청순 미녀",
        "눈웃음",
        "심쿵 영상",
        "얼짱",
        "분위기 여신",
        "직캠",
        "인기 쇼츠",
        "예쁜 여자",
      ],
      zh: [
        "美女",
        "神仙颜值",
        "甜美笑容",
        "纯欲美女",
        "氛围感美女",
        "抖音美女",
        "治愈系美女",
        "高颜值",
        "心动女孩",
        "高清美女",
      ],
      ja: [
        "美少女",
        "可愛い女の子",
        "透明感美女",
        "天使の笑顔",
        "美人",
        "清楚系",
        "癒やし動画",
        "アジアンビューティー",
        "バズり動画",
      ],
    },
  },

  dance_trend: {
    defaultFocus: {
      vi: "Vũ đạo bắt nhịp cực dính & thần thái cuốn hút",
      en: "Smooth viral dance & unmatched stage presence",
      vi_en: "Nhảy bắt trend cực cuốn • Viral Dance",
      ko: "박자감 미친 댄스 챌린지 & 춤선 여신",
      zh: "卡点丝滑的热门舞蹈与绝美身材比例",
      ja: "キレキレで可愛すぎる話題のダンスチャレンジ",
    },
    titleTemplates: {
      vi: [
        "{focus} khiến dân tình tua lại liên tục 🔥💃",
        "Nhịp nhạc vừa lên là thần thái cuốn không lối thoát ✨ | {focus}",
        "Vừa xinh vừa nhảy dẻo thế này bảo sao triệu view 💖 | {focus}",
        "Bắt trend nhảy cực mượt không thừa một động tác nào 🔥 ({focus})",
        "Đôi chân cực phẩm & chuyển động siêu cuốn 💃 | {focus}",
        "Xem 1 lần là dính luôn giai điệu lẫn người nhảy 🥰 | {focus}",
      ],
      en: [
        "{focus} — Impossible To Watch Just Once 🔥💃",
        "Her Rhythm & Expression Hit Every Single Beat ✨ | {focus}",
        "When Beauty Meets Effortless Dance Flow 💖 | {focus}",
        "Cleanest Viral Dance Trend You'll See Today 🔥 ({focus})",
        "Hypnotic Footwork & Unmatched Charisma 💃 | {focus}",
        "She Owns The Frame From Second One ✨ | {focus}",
      ],
      vi_en: [
        "{focus} xem cuốn không rời mắt 🔥 | Viral Dance Trend",
        "Nhảy bắt nhịp cực mượt & thần thái đỉnh cao 💃 | Smooth Dance",
        "Vừa xinh vừa nhảy đẹp bảo sao triệu view ✨ | Trending Dance Clip",
        "Chuyển động mượt từng khung hình 💖 | {focus}",
        "Bắt trend nhạc hot cực dính 🔥 | Addictive Rhythm",
        "Thần thái sân khấu 10/10 💃 | Stage Presence",
      ],
      ko: [
        "춤선 하나로 알고리즘 장악한 레전드 댄스 챌린지 🔥💃 | {focus}",
        "박자 쪼개는 실력과 비주얼 모두 완벽 ✨ | {focus}",
        "한 번 보면 못 빠져나오는 중독성 갑 댄스 직캠 💖",
        "표정 연기부터 춤선까지 갓벽한 트렌드 댄스 🔥 | {focus}",
        "비율과 리듬감 미쳤다는 반응 폭발 중인 영상 💃",
        "도입부부터 시선 강탈하는 댄스 여신 ✨ | {focus}",
      ],
      zh: [
        "卡点极度舒适！这舞姿和身材比例太绝了 🔥💃 | {focus}",
        "又美又飒的热门舞蹈挑战，看一遍根本不够 ✨ | {focus}",
        "节奏感拉满！每一个动作都踩在审美点上 💖 | {focus}",
        "百万播放热门热舞！表情管理满分 🔥",
        "这腿长和律动感简直绝绝子 💃 | {focus}",
        "丝滑卡点舞蹈，越看越上头 ✨ | {focus}",
      ],
      ja: [
        "リズム感と可愛さが完璧すぎる話題のダンス動画 🔥💃 | {focus}",
        "1秒目から惹き込まれるキレキレダンス ✨ | {focus}",
        "スタイル抜群＆表情まで完璧なトレンドダンス 💖 | {focus}",
        "何回見ても飽きない中毒性ダンスクリップ 🔥",
        "しなやかな動きに釘付けになる美少女ダンス 💃",
        "音楽とのシンクロ率100% ✨ | {focus}",
      ],
    },
    descIntro: {
      vi: "Màn bắt trend vũ đạo cực mượt, khớp từng nhịp nhạc kết hợp visual sắc nét chuẩn HD.",
      en: "Crisp HD dance performance hitting every beat with effortless grace, style, and captivating energy.",
      vi_en: "Vũ đạo bắt trend cực cuốn chuẩn HD — Addictive dance rhythm & stunning charisma.",
      ko: "깔끔한 춤선과 완벽한 박자감이 돋보이는 고화질 인기 댄스 영상입니다.",
      zh: "丝滑卡点热门舞蹈精选，高清画质展现满分律动与绝佳气质。",
      ja: "抜群のリズム感と魅力的な表現力が光る高画質トレンドダンス動画。",
    },
    ctaLine: {
      vi: "👉 Thả Like 👍 & Đăng ký kênh ngay để không bỏ lỡ các bản dance trend cuốn nhất mỗi ngày!",
      en: "👉 Drop a Like 👍 & Subscribe for daily viral dance trends in crisp HD!",
      vi_en: "👉 Like & Subscribe để cập nhật các clip nhảy bắt trend HD mới nhất mỗi ngày!",
      ko: "👉 좋아요와 구독으로 매일 업데이트되는 핫한 댄스 영상을 받아보세요!",
      zh: "👉 记得点赞👍并订阅频道，每天为您精选高清热门舞蹈视频！",
      ja: "👉 高評価＆チャンネル登録で最新トレンドダンスを毎日お楽しみください！",
    },
    hashtags: {
      vi: ["#nhaydep", "#dancetrend", "#gaixinh", "#xuhuong", "#tiktokdance", "#nhaytiktok"],
      en: ["#dance", "#dancetrend", "#viraldance", "#dancechallenge", "#kpopdance", "#prettygirl"],
      vi_en: ["#dancetrend", "#nhaydep", "#gaixinh", "#viraldance", "#tiktokdance", "#xuhuong"],
      ko: ["#댄스", "#댄스챌린지", "#춤선", "#직캠", "#인기댄스", "#미녀"],
      zh: ["#热门舞蹈", "#热舞", "#卡点舞", "#美女跳舞", "#抖音热舞", "#身材"],
      ja: ["#ダンス", "#ダンス動画", "#踊ってみた", "#トレンドダンス", "#美少女", "#可愛い"],
    },
    tags: {
      vi: [
        "gái xinh nhảy đẹp",
        "nhảy tiktok",
        "dance trend",
        "nhảy bắt trend",
        "gái xinh nhảy nhạc remix",
        "vũ đạo cuốn hút",
        "tiktok dance vn",
        "girl xinh nhảy",
        "clip nhảy triệu view",
        "gái đẹp dáng chuẩn",
      ],
      en: [
        "viral dance",
        "dance challenge",
        "tiktok dance trend",
        "girl dancing",
        "smooth dance moves",
        "kpop dance cover",
        "aesthetic dance",
        "fancam hd",
        "trending dance video",
        "charismatic dancer",
      ],
      vi_en: [
        "gái xinh nhảy đẹp",
        "viral dance",
        "tiktok dance trend",
        "nhảy bắt trend",
        "dance challenge",
        "girl xinh nhảy",
        "smooth dance",
        "fancam hd",
        "nhạc remix nhảy cuốn",
        "gái xinh dáng đẹp",
      ],
      ko: [
        "댄스 챌린지",
        "춤선 레전드",
        "직캠 고화질",
        "인기 댄스",
        "여자 댄스",
        "틱톡 댄스",
        "릴스 댄스",
        "비주얼 댄서",
      ],
      zh: [
        "美女跳舞",
        "抖音热舞",
        "热门舞蹈挑战",
        "丝滑卡点舞",
        "大长腿热舞",
        "颜值热舞",
        "韩舞翻跳",
        "高清舞蹈",
      ],
      ja: [
        "ダンス動画",
        "踊ってみた",
        "可愛いダンス",
        "TikTokダンス",
        "ダンスチャレンジ",
        "スタイル抜群",
        "高画質ダンス",
      ],
    },
  },

  street_fashion: {
    defaultFocus: {
      vi: "Street style tôn dáng cực phẩm & thần thái sang chảnh",
      en: "Effortless street fashion & model-tier proportions",
      vi_en: "Street style tôn dáng đỉnh cao • Chic OOTD",
      ko: "모델 비율 자랑하는 세련된 스트릿 패션 & 데일리룩",
      zh: "回头率200%的街拍穿搭与超模身材比例",
      ja: "抜群のスタイルが際立つ洗練ストリートファッション",
    },
    titleTemplates: {
      vi: [
        "{focus} bước đi tới đâu chiếm trọn spotlight tới đó ✨👗",
        "Cách phối đồ đơn giản mà tôn dáng 10 điểm không có nhưng 💖 | {focus}",
        "Tỷ lệ cơ thể siêu thực ngoài đời thật 🔥 | {focus}",
        "Street style cuốn hút như bước ra từ tạp chí thời trang ✨ ({focus})",
        "Khí chất sang chảnh khó rời mắt ngay từ giây đầu 💫 | {focus}",
        "Outfit dạo phố chuẩn gu vừa thanh lịch vừa quyến rũ 🌸 | {focus}",
      ],
      en: [
        "{focus} Turning The Sidewalk Into A Runway ✨👗",
        "10/10 Outfit & Unreal Proportions In Real Life 🔥 | {focus}",
        "Effortless Chic Streetwear Vibe You Need To See 💖 | {focus}",
        "Minimalist Styling With Maximum Visual Impact ✨ ({focus})",
        "Main Character Energy On The City Streets 💫 | {focus}",
        "Timeless Lookbook Inspiration & Pure Elegance 🌸 | {focus}",
      ],
      vi_en: [
        "{focus} biến đường phố thành sàn diễn ✨ | Street Fashion",
        "Phối đồ tôn dáng 10/10 cực cuốn 💖 | Chic OOTD Lookbook",
        "Khí chất sang chảnh & tỷ lệ dáng siêu thực 🔥 | Runway Vibe",
        "Outfit dạo phố đơn giản mà cực sang ✨ | {focus}",
        "Thần thái chuẩn người mẫu ngoài đời 💫 | Model Proportions",
        "Gu thời trang tinh tế không thể rời mắt 🌸 | Street Style",
      ],
      ko: [
        "길거리를 런웨이로 만드는 넘사벽 모델 비율 ✨👗 | {focus}",
        "심플한데 고급미 넘치는 여신 데일리룩 코디 💖 | {focus}",
        "지나가다 무조건 뒤돌아보게 되는 스트릿 패션 🔥",
        "실물 비율 실화?! 분위기 압도하는 룩북 모먼트 ✨ | {focus}",
        "세련미 가득한 도심 속 워킹 직캠 💫",
        "꾸안꾸 정석 보여주는 패션 센스 🌸 | {focus}",
      ],
      zh: [
        "把马路走出T台既视感！这身材比例绝了 ✨👗 | {focus}",
        "回头率爆表的女神级街拍穿搭示范 💖 | {focus}",
        "简约却高级感拉满的日常OOTD 🔥 | {focus}",
        "生图镜头下的超模腿长与优雅气质 ✨",
        "甜酷与优雅并存的街头时尚瞬间 💫 | {focus}",
        "一眼惊艳的穿搭模板，气质拿捏死死的 🌸",
      ],
      ja: [
        "街角が一瞬でランウェイに変わる圧倒的スタイル ✨👗 | {focus}",
        "シンプルなのに上品で目を惹く大人可愛いコーデ 💖 | {focus}",
        "リアル8頭身？！憧れのストリートスナップ 🔥 | {focus}",
        "真似したくなる洗練OOTD＆モデルウォーキング ✨",
        "歩くだけで絵になる都会派ビューティー 💫",
        "全方位どこから見ても完璧なシルエット 🌸 | {focus}",
      ],
    },
    descIntro: {
      vi: "Khoảnh khắc street style dạo phố cực tôn dáng, gu phối đồ tinh tế và thần thái cuốn hút chuẩn HD.",
      en: "Curated HD street fashion and OOTD lookbook moments showcasing effortless styling and model proportions.",
      vi_en: "Street style dạo phố tôn dáng chuẩn HD — Effortless OOTD fashion & runway charisma.",
      ko: "감각적인 스타일링과 완벽한 비율이 돋보이는 고화질 스트릿 패션 룩북입니다.",
      zh: "高清街拍时尚穿搭精选，展现高级感满满的日常搭配与绝佳身材管理。",
      ja: "洗練された着こなしと美しいシルエットが際立つ高画質ストリートファッション。",
    },
    ctaLine: {
      vi: "👉 Bấm Like 👍 & Đăng ký kênh để cập nhật xu hướng street style và visual đẹp mỗi ngày!",
      en: "👉 Like 👍 & Subscribe for daily street style inspiration and HD lookbooks!",
      vi_en: "👉 Like & Subscribe để xem thêm nhiều clip street style & OOTD HD mỗi ngày!",
      ko: "👉 좋아요와 구독으로 매일 감각적인 패션 & 비주얼 쇼츠를 만나보세요!",
      zh: "👉 点赞👍并订阅频道，每日解锁更多高清街拍美女与时尚穿搭灵感！",
      ja: "👉 高評価＆チャンネル登録で毎日のトレンドコーデ＆美少女スナップをチェック！",
    },
    hashtags: {
      vi: ["#streetstyle", "#ootd", "#thoitrang", "#gaixinh", "#dangdep", "#xuhuong"],
      en: ["#streetfashion", "#ootd", "#lookbook", "#modelwalk", "#fashionstyle", "#chic"],
      vi_en: ["#streetstyle", "#ootd", "#gaixinh", "#streetfashion", "#lookbook", "#dangdep"],
      ko: ["#스트릿패션", "#데일리룩", "#코디", "#모델비율", "#룩북", "#패션"],
      zh: ["#街拍", "#穿搭", "#街拍美女", "#OOTD", "#高级感穿搭", "#好身材"],
      ja: ["#ストリートスナップ", "#コーデ", "#ファッション", "#OOTD", "#スタイル抜群", "#美人"],
    },
    tags: {
      vi: [
        "street style gái xinh",
        "phối đồ tôn dáng",
        "gái xinh dáng đẹp",
        "thời trang dạo phố",
        "ootd vietnam",
        "gái xinh chân dài",
        "khí chất sang chảnh",
        "lookbook thời trang",
        "gái đẹp mặc đẹp",
      ],
      en: [
        "street fashion",
        "ootd lookbook",
        "korean street style",
        "asian street fashion",
        "model proportions",
        "chic outfit ideas",
        "runway walk street",
        "aesthetic fashion video",
      ],
      vi_en: [
        "street style gái xinh",
        "street fashion",
        "ootd lookbook",
        "gái xinh dáng đẹp",
        "korean street style",
        "phối đồ nữ đẹp",
        "model proportions",
        "asian fashion",
      ],
      ko: [
        "스트릿 패션",
        "여자 데일리룩",
        "모델 워킹",
        "꾸안꾸 코디",
        "강남 스트릿",
        "홍대 패션",
        "여신 룩북",
      ],
      zh: [
        "街拍美女",
        "时尚穿搭",
        "夏日穿搭",
        "女神街拍",
        "超模身材",
        "气质穿搭",
        "抖音街拍",
      ],
      ja: [
        "ストリートファッション",
        "韓国ファッション",
        "大人可愛いコーデ",
        "モデル体型",
        "街角スナップ",
        "着回しコーデ",
      ],
    },
  },

  cosplay_trad: {
    defaultFocus: {
      vi: "Tạo hình áo dài / cosplay bước ra từ tranh vẽ",
      en: "Breathtaking cosplay & traditional elegance brought to life",
      vi_en: "Tạo hình bước ra từ tranh vẽ • Ethereal Cosplay & Traditional Look",
      ko: "만찢녀 비주얼 자랑하는 레전드 코스프레 & 전통미",
      zh: "仿佛从画中走出来的绝美古风汉服与神级Cosplay",
      ja: "二次元から飛び出してきたような神クオリティ美少女コスプレ",
    },
    titleTemplates: {
      vi: [
        "{focus} đẹp như bước ra từ trang sách ✨🌸",
        "Visual cổ điển pha nét hiện đại khiến ai nhìn cũng mê 💖 | {focus}",
        "Từng cử chỉ đều dịu dàng chuẩn tuyệt sắc giai nhân ✨ ({focus})",
        "Màn biến hình trang phục đỉnh nhất tuần này 🔥 | {focus}",
        "Độ hoàn thiện nhan sắc lẫn thần thái 100/10 💫 | {focus}",
        "Nét đẹp Á Đông trong trẻo khó cưỡng 🥰 | {focus}",
      ],
      en: [
        "{focus} — Straight Out Of A Painting ✨🌸",
        "Unreal Attention To Detail & Ethereal Grace 💖 | {focus}",
        "When Real Life Looks Even Better Than Anime/Art 🔥 ({focus})",
        "Most Mesmerizing Costume Transformation Today ✨ | {focus}",
        "Timeless Eastern Elegance & Flawless Visuals 💫 | {focus}",
        "Every Frame Looks Like A Movie Poster 🥰 | {focus}",
      ],
      vi_en: [
        "{focus} đẹp tựa tranh vẽ ✨ | Straight Out Of A Painting",
        "Màn biến hình trang phục cực phẩm 🔥 | Stunning Transformation",
        "Nét đẹp dịu dàng đốn tim người xem 💖 | Ethereal Beauty",
        "Mỗi khung hình đều đẹp như điện ảnh ✨ | {focus}",
        "Thần thái nhân vật 10/10 💫 | Flawless Cosplay & Elegance",
        "Visual Á Đông trong trẻo 🌸 | Timeless Charm",
      ],
      ko: [
        "만화 찢고 나온 듯한 싱크로율 200% 여신 비주얼 ✨🌸 | {focus}",
        "고전미와 청순함이 공존하는 레전드 한복/코스프레 💖",
        "한 장면 한 장면이 영화 포스터 같은 분위기 🔥 | {focus}",
        "변신 전후 모두 완벽한 비주얼 장인 ✨ | {focus}",
        "우아한 선과 눈빛에 홀리게 되는 영상 💫",
        "실사판 여주인공 그 자체인 순간 🥰 | {focus}",
      ],
      zh: [
        "仿佛从画卷里走出来的仙女！这古风韵味绝了 ✨🌸 | {focus}",
        "打破次元壁的神级颜值！每一帧都能当壁纸 💖 | {focus}",
        "一眼万年的东方古典美，气质温婉如玉 🔥 | {focus}",
        "变装前后都惊艳！这妆造还原度满分 ✨",
        "仙气飘飘的氛围感大片，美到失语 💫 | {focus}",
        "回眸那一刻真的惊艳了时光 🥰 | {focus}",
      ],
      ja: [
        "二次元を超えた神ビジュアル！完成度が高すぎる ✨🌸 | {focus}",
        "まるで絵画のような美しさと儚げな透明感 💖 | {focus}",
        "一瞬で世界観に引き込まれる変身クリップ 🔥 | {focus}",
        "どの角度から見ても完璧な再現度＆美貌 ✨",
        "映画のワンシーンみたいな幻想的ビジュアル 💫",
        "大和撫子×トレンド感の最高峰 🥰 | {focus}",
      ],
    },
    descIntro: {
      vi: "Tạo hình truyền thống & cosplay chỉn chu từng chi tiết với thần thái dịu dàng, sắc nét chuẩn HD.",
      en: "Mesmerizing HD cosplay and traditional attire visuals with cinematic lighting and graceful expression.",
      vi_en: "Tạo hình truyền thống & cosplay tuyệt đẹp chuẩn HD — Cinematic elegance & flawless character visuals.",
      ko: "섬세한 의상 디테일과 독보적인 분위기가 어우러진 고화질 비주얼 영상입니다.",
      zh: "唯美古风汉服与高还原度Cosplay高清精选，帧帧皆可做壁纸。",
      ja: "圧倒的な完成度と幻想的な雰囲気が魅力の高画質コスプレ＆伝統美クリップ。",
    },
    ctaLine: {
      vi: "👉 Nhấn Like 👍 & Đăng ký kênh để thưởng thức thêm nhiều màn biến hình & tạo hình đẹp mê hồn!",
      en: "👉 Like 👍 & Subscribe for more breathtaking HD transformations and aesthetic visuals!",
      vi_en: "👉 Like & Subscribe để đón xem thêm các màn biến hình & tạo hình HD ấn tượng nhất!",
      ko: "👉 좋아요와 구독으로 매일 새로운 레전드 변신 & 비주얼 영상을 감상하세요!",
      zh: "👉 喜欢请点赞👍并订阅，每天更新绝美古风与次元壁女神高清视频！",
      ja: "👉 高評価＆チャンネル登録で神クオリティな変身＆美少女動画を毎日チェック！",
    },
    hashtags: {
      vi: ["#aodai", "#cosplay", "#cotrang", "#gaixinh", "#bienhinh", "#nangtho"],
      en: ["#cosplay", "#cosplayer", "#hanfu", "#aodai", "#animegirl", "#ethereal"],
      vi_en: ["#cosplay", "#aodai", "#gaixinh", "#ethereal", "#transformation", "#visuals"],
      ko: ["#코스프레", "#만찢녀", "#전통미", "#여신", "#변신영상", "#비주얼"],
      zh: ["#汉服", "#古风美女", "#Cosplay", "#变装", "#国风", "#神仙颜值"],
      ja: ["#コスプレ", "#美少女コスプレ", "#二次元", "#変身動画", "#着物女子", "#透明感"],
    },
    tags: {
      vi: [
        "gái xinh mặc áo dài",
        "cosplay gái xinh",
        "mỹ nhân cổ trang",
        "biến hình tiktok",
        "áo dài trắng nữ sinh",
        "vẻ đẹp á đông",
        "cosplay anime đời thực",
        "gái đẹp dịu dàng",
      ],
      en: [
        "cosplay girl",
        "realistic anime cosplay",
        "traditional asian dress",
        "ao dai vietnam beauty",
        "hanfu fairy",
        "costume transformation",
        "ethereal aesthetic",
      ],
      vi_en: [
        "gái xinh áo dài",
        "cosplay girl",
        "costume transformation",
        "biến hình trang phục",
        "traditional beauty",
        "ethereal visuals",
        "anime cosplay real life",
      ],
      ko: ["코스프레 레전드", "만찢녀 비주얼", "한복 미녀", "변신 챌린지", "실사판 캐릭터"],
      zh: ["汉服美女", "古风变装", "神级Cosplay", "国风美少女", "仙气美女"],
      ja: ["コスプレイヤー", "美少女コスプレ", "変身メイク", "アニメ実写", "和装美人"],
    },
  },

  beach_travel: {
    defaultFocus: {
      vi: "Vibe biển nắng vàng & năng lượng mùa hè rực rỡ",
      en: "Sun-kissed golden hour beach & carefree travel vibe",
      vi_en: "Nắng vàng biển xanh & visual rực rỡ • Golden Hour Travel Vibe",
      ko: "청량미 터지는 여름 바다 & 노을빛 여행 여신",
      zh: "海风落日与元气满满的度假风氛围感美女",
      ja: "青い海と夕日に映える爽やかサマーガール＆旅ムービー",
    },
    titleTemplates: {
      vi: [
        "{focus} xem xong chỉ muốn xách vali đi ngay 🌊☀️",
        "Hoàng hôn trên biển cũng không rực rỡ bằng nụ cười này ✨ | {focus}",
        "Gió biển nhẹ bay & khung hình trong trẻo chữa lành tâm hồn 💙 ({focus})",
        "Năng lượng mùa hè tươi mát tràn ngập khung hình 🌴 | {focus}",
        "Ánh nắng chiều tà tôn lên visual cực phẩm 🌅 | {focus}",
        "Vừa thơ mộng vừa cuốn hút khó rời mắt 💖 | {focus}",
      ],
      en: [
        "{focus} — Pure Golden Hour Magic 🌊☀️",
        "Ocean Breeze, Sunset Glow & Unmatched Summer Vibes ✨ | {focus}",
        "This Clip Feels Like A Dream Vacation 💙 ({focus})",
        "Sun-Kissed Visuals That Instantly Lift Your Mood 🌴 | {focus}",
        "Golden Hour Lighting Was Made For Her 🌅 | {focus}",
        "Carefree Travel Aesthetic At Its Finest 💖 | {focus}",
      ],
      vi_en: [
        "{focus} đẹp như thước phim điện ảnh 🌊☀️ | Sunset Beach Vibe",
        "Gió biển hoàng hôn & nụ cười rạng rỡ ✨ | Golden Hour Beauty",
        "Vibe du lịch chữa lành cực cuốn 💙 | Dreamy Travel Aesthetic",
        "Nắng chiều tôn trọn nét đẹp trong trẻo 🌅 | {focus}",
        "Năng lượng mùa hè tươi mới 🌴 | Summer Breeze",
        "Khung hình HD sắc nét từng làn sóng 💖 | Ocean Glow",
      ],
      ko: [
        "청량함 한도 초과! 바다 바람 맞으며 빛나는 여신 비주얼 🌊☀️ | {focus}",
        "노을빛 윤슬보다 더 눈부신 여행 브이로그 모먼트 ✨",
        "보기만 해도 시원해지는 여름 휴양지 감성 💙 | {focus}",
        "바람에 흩날리는 머릿결까지 영화 같은 순간 🌅",
        "힐링 그 자체인 황금빛 선셋 & 미소 🌴 | {focus}",
        "여행 뽐뿌 제대로 오는 청순 화보 느낌 💖",
      ],
      zh: [
        "海风、落日与心动女孩！这度假氛围感拉满了 🌊☀️ | {focus}",
        "夕阳余晖下的绝美侧颜，每一秒都好治愈 ✨ | {focus}",
        "清爽感扑面而来的海边大片，美得像电影画面 💙",
        "夏日海边最亮眼的风景线 🌴 | {focus}",
        "阳光洒在身上的那一刻简直封神 🌅 | {focus}",
        "元气满满的旅行随拍，看心情都变好了 💖",
      ],
      ja: [
        "海風と夕日に照らされた透明感がエモすぎる 🌊☀️ | {focus}",
        "見ているだけで 여름気分になれる爽やか美少女クリップ ✨",
        "映画のワンシーンのようなサンセットビーチ 💙 | {focus}",
        "太陽よりも眩しいナチュラルな笑顔 🌴 | {focus}",
        "旅に出たくなる癒やしのリゾートVibe 🌅",
        "風になびく髪とキラキラした瞳が最高 💖 | {focus}",
      ],
    },
    descIntro: {
      vi: "Khung hình du lịch biển rực rỡ ánh hoàng hôn kết hợp visual tươi tắn, tràn đầy sức sống chuẩn HD.",
      en: "Sun-drenched HD travel and coastal golden hour moments filled with warmth, ocean breeze, and natural charm.",
      vi_en: "Vibe biển hoàng hôn trong trẻo chuẩn HD — Sun-kissed travel visuals & refreshing summer energy.",
      ko: "탁 트인 바다와 따스한 노을빛이 어우러진 청량한 고화질 여행 비주얼 영상입니다.",
      zh: "高清海边度假与落日氛围感随拍，记录最清爽治愈的夏日美好瞬间。",
      ja: "美しい海辺のサンセットと爽やかな笑顔に癒やされる高画質トラベルクリップ。",
    },
    ctaLine: {
      vi: "👉 Bấm Like 👍 & Đăng ký kênh để tận hưởng những thước phim du lịch & gái xinh chữa lành mỗi ngày!",
      en: "👉 Like 👍 & Subscribe for daily sun-kissed travel aesthetics and HD visuals!",
      vi_en: "👉 Like & Subscribe để đón xem thêm nhiều thước phim du lịch & visual HD mới nhất!",
      ko: "👉 좋아요와 구독으로 매일 기분 좋아지는 청량 힐링 영상을 만나보세요!",
      zh: "👉 欢迎点赞👍并订阅，每天带你看遍高清治愈系旅行与高颜值风景！",
      ja: "👉 高評価＆チャンネル登録で癒やしのトラベル＆美少女動画を毎日お届け！",
    },
    hashtags: {
      vi: ["#dibien", "#dulich", "#hoanghon", "#gaixinh", "#chualanh", "#muahe"],
      en: ["#beachvibes", "#goldenhour", "#summervibes", "#travelgirl", "#sunsetglow", "#aesthetic"],
      vi_en: ["#beachvibes", "#dibien", "#gaixinh", "#goldenhour", "#summervibes", "#dulich"],
      ko: ["#바다여행", "#청량", "#노을", "#여름감성", "#힐링영상", "#여신"],
      zh: ["#海边拍照", "#落日氛围感", "#旅行随拍", "#度假穿搭", "#治愈系", "#美女"],
      ja: ["#海", "#サンセット", "#夏休み", "#リゾート", "#エモい", "#美少女"],
    },
    tags: {
      vi: [
        "gái xinh đi biển",
        "du lịch biển",
        "hoàng hôn trên biển",
        "vibe chữa lành",
        "gái xinh mùa hè",
        "nắng vàng biển xanh",
        "girl xinh du lịch",
        "clip biển đẹp hd",
      ],
      en: [
        "beach aesthetic",
        "golden hour girl",
        "summer beach vibes",
        "sunset ocean aesthetic",
        "travel vlog girl",
        "sun kissed beauty",
        "vacation lookbook",
      ],
      vi_en: [
        "gái xinh đi biển",
        "beach vibes",
        "golden hour aesthetic",
        "summer girl",
        "hoàng hôn biển",
        "travel lookbook",
        "vibe chữa lành",
      ],
      ko: ["여름 바다", "청량 여신", "휴양지 룩", "선셋 비주얼", "여행 브이로그"],
      zh: ["海边美女", "海岛度假", "落日氛围感", "夏日清爽美女", "旅行大片"],
      ja: ["ビーチガール", "海辺の美少女", "夕日エモい", "リゾートコーデ", "夏旅"],
    },
  },

  gym_sport: {
    defaultFocus: {
      vi: "Năng lượng thể thao khỏe khoắn & vóc dáng săn chắc",
      en: "Athletic fitness glow & inspiring healthy physique",
      vi_en: "Vóc dáng khỏe khoắn cuốn hút • Fit & Active Glow",
      ko: "건강미 넘치는 탄탄한 바디라인 & 운동 자극 모먼트",
      zh: "自律又迷人的运动系女孩与绝佳健身线条",
      ja: "ヘルシーな美ボディ＆ポジティブな輝きを放つスポーツ女子",
    },
    titleTemplates: {
      vi: [
        "{focus} truyền động lực tập luyện ngay lập tức 💪✨",
        "Vẻ đẹp khỏe khoắn tràn đầy năng lượng tích cực 🔥 | {focus}",
        "Thành quả của sự kỷ luật: vóc dáng chuẩn từng centimet 💖 ({focus})",
        "Sporty style năng động mà vẫn cực kỳ cuốn hút ✨ | {focus}",
        "Tập luyện chăm chỉ tạo nên thần thái tự tin rạng ngời 🌟 | {focus}",
        "Động lực đến phòng tập mỗi ngày là đây chứ đâu 🏋️‍♀️ | {focus}",
      ],
      en: [
        "{focus} — Instant Workout Motivation 💪✨",
        "Discipline & Confidence Look Incredible On Her 🔥 | {focus}",
        "Healthy Athletic Glow & Effortless Sporty Style 💖 ({focus})",
        "Proof That Consistency Pays Off Every Time 🌟 | {focus}",
        "Active Lifestyle Energy That Inspires You To Move 🏋️‍♀️ | {focus}",
        "Strong, Graceful & Full Of Positive Vibes ✨ | {focus}",
      ],
      vi_en: [
        "{focus} truyền cảm hứng tập luyện cực mạnh 💪✨ | Fitness Motivation",
        "Vẻ đẹp khỏe khoắn & kỷ luật đáng ngưỡng mộ 🔥 | Healthy Glow",
        "Sporty outfit tôn trọn vóc dáng săn chắc 💖 | Active Lifestyle",
        "Năng lượng tích cực ngập tràn khung hình 🌟 | {focus}",
        "Động lực đi tập mỗi ngày 🏋️‍♀️ | Gym Inspiration",
        "Tự tin & rạng rỡ chuẩn HD ✨ | Fit & Fabulous",
      ],
      ko: [
        "운동 욕구 수직 상승하게 만드는 워너비 건강미 💪✨ | {focus}",
        "꾸준한 자기관리로 완성된 탄탄한 핏 & 에너지 🔥 | {focus}",
        "스포티한 애슬레저룩이 찰떡인 운동 여신 💖",
        "보는 사람까지 활기차지는 긍정 에너지 뿜뿜 🌟 | {focus}",
        "자신감 넘치는 미소와 완벽한 밸런스 🏋️‍♀️",
        "오늘 당장 헬스장 가게 만드는 자극 영상 ✨ | {focus}",
      ],
      zh: [
        "自律的女生到底有多美！这运动线条太励志了 💪✨ | {focus}",
        "阳光活力感拉满的健身女孩，满满正能量 🔥 | {focus}",
        "健康匀称的好身材才是最顶级的穿搭 💖 | {focus}",
        "运动风穿搭清爽又吸睛，看完立马想锻炼 🌟",
        "流汗后的自信笑容最有感染力 🏋️‍♀️ | {focus}",
        "力量感与柔美兼具的运动系女神 ✨",
      ],
      ja: [
        "努力の結晶！ヘルシーで美しすぎる理想のボディライン 💪✨ | {focus}",
        "見ているだけでモチベ爆上がりするワークアウト女子 🔥 | {focus}",
        "スポーティーコーデが爽やかに映える健康美 💖",
        "ポジティブなオーラ全開のアクティブ美少女 🌟 | {focus}",
        "引き締まったシルエットと弾ける笑顔が最高 🏋️‍♀️",
        "自分磨きを頑張りたくなる憧れスタイル ✨ | {focus}",
      ],
    },
    descIntro: {
      vi: "Năng lượng thể thao khỏe khoắn, phong cách năng động và vóc dáng cân đối truyền cảm hứng tập luyện mỗi ngày.",
      en: "Inspiring HD fitness and active lifestyle highlights celebrating healthy energy, confidence, and athletic grace.",
      vi_en: "Năng lượng thể thao khỏe khoắn chuẩn HD — Inspiring fitness glow & confident active style.",
      ko: "건강한 에너지와 탄탄한 자기관리 매력이 돋보이는 고화질 스포티 비주얼 영상입니다.",
      zh: "充满阳光活力的运动健身女孩高清精选，传递自律与健康的审美力量。",
      ja: "健康的で引き締まったスタイルと前向きなエネルギーが輝く高画質スポーツクリップ。",
    },
    ctaLine: {
      vi: "👉 Nhấn Like 👍 & Đăng ký kênh để nạp thêm năng lượng tích cực & động lực tập luyện mỗi ngày!",
      en: "👉 Like 👍 & Subscribe for daily fitness motivation and vibrant HD lifestyle clips!",
      vi_en: "👉 Like & Subscribe để nhận thêm động lực tập luyện & năng lượng tích cực mỗi ngày!",
      ko: "👉 좋아요와 구독으로 매일 건강한 운동 자극 & 활기찬 영상을 받아보세요!",
      zh: "👉 点赞👍并订阅频道，每天一起感受阳光运动与自律之美！",
      ja: "👉 高評価＆チャンネル登録で毎日のモチベーションアップ動画をチェック！",
    },
    hashtags: {
      vi: ["#gymnu", "#fitness", "#dangdep", "#gaixinh", "#thethao", "#dongluctapluyen"],
      en: ["#fitnessmotivation", "#gymgirl", "#athleisure", "#healthylifestyle", "#fitgirl", "#workout"],
      vi_en: ["#gymgirl", "#dangdep", "#fitnessmotivation", "#gaixinh", "#sportystyle", "#workout"],
      ko: ["#운동자극", "#건강미", "#애슬레저룩", "#헬스녀", "#바디라인", "#자기관리"],
      zh: ["#健身女孩", "#运动美女", "#好身材", "#自律打卡", "#瑜伽裤穿搭", "#活力"],
      ja: ["#筋トレ女子", "#フィットネス", "#美ボディ", "#スポーツ女子", "#ダイエット刺激", "#健康美"],
    },
    tags: {
      vi: [
        "gái xinh tập gym",
        "vóc dáng săn chắc",
        "động lực tập luyện",
        "sporty style nữ",
        "gái đẹp dáng chuẩn",
        "yoga pilates nữ",
        "vẻ đẹp khỏe khoắn",
      ],
      en: [
        "fitness girl motivation",
        "gym outfit lookbook",
        "athleisure fashion",
        "healthy athletic glow",
        "pilates workout aesthetic",
        "fit lifestyle",
      ],
      vi_en: [
        "gái xinh tập gym",
        "fitness motivation",
        "athleisure style",
        "vóc dáng khỏe khoắn",
        "gym girl",
        "healthy glow",
      ],
      ko: ["운동하는 여자", "필라테스 여신", "애슬레저 코디", "운동 자극 쇼츠", "건강미 비주얼"],
      zh: ["健身美女", "运动系女孩", "普拉提身材", "自律女生", "运动穿搭"],
      ja: ["ワークアウト女子", "ピラティス美少女", "ジムコーデ", "美脚トレーニング", "ヘルシー美人"],
    },
  },
};

function rotateArray<T>(arr: T[], offset: number): T[] {
  if (arr.length === 0) return [];
  const k = ((offset % arr.length) + arr.length) % arr.length;
  return [...arr.slice(k), ...arr.slice(0, k)];
}

function buildShortSignatureTitles(input: ReupSeoInput): string[] {
  const lang = input.language || "en";
  const vibe = input.vibe || "visual_smile";
  const vp = input.visualProfile || {};
  const shot = vp.shot_type || "portrait";
  const palette = vp.dominant_palette || "soft_neutral";
  const note = (input.customNote || "").trim();
  const seed = Math.max(0, Math.floor(input.seed || 0));

  // If user typed "ASA | BABYMONSTER" or "Yuqi" or "Douyin", parse optional left/right parts cleanly
  let customSubject = "";
  let customTag = "";
  if (note) {
    if (note.includes("|")) {
      const [l, r] = note.split("|", 2).map((s) => s.trim());
      customSubject = l;
      customTag = r;
    } else if (note.length <= 18) {
      customSubject = note;
    } else {
      customSubject = note.split(/\s+/).slice(0, 4).join(" ");
    }
  }

  const colorHookEn: Record<string, string> = {
    pink_pastel: "Sweet Pink Vibe",
    purple_fairy: "Dreamy Fairy Girl",
    pure_white: "Pure White Angel",
    classic_black: "Chic In Black",
    sky_blue: "Soft Blue Aesthetic",
    red_charm: "Stunning In Red",
    green_outdoor: "Sunny Outdoor Girl",
    warm_beige: "Soft Golden Glow",
    soft_neutral: "Natural Doll Visuals",
  };

  const colorHookVi: Record<string, string> = {
    pink_pastel: "Tone Hồng Ngọt Ngào",
    purple_fairy: "Nàng Thơ Tím Mộng Mơ",
    pure_white: "Áo Trắng Tinh Khôi",
    classic_black: "Outfit Đen Cuốn Hút",
    sky_blue: "Tone Xanh Trong Trẻo",
    red_charm: "Sắc Đỏ Nổi Bật",
    green_outdoor: "Nắng Ngoại Cảnh Xinh",
    warm_beige: "Visual Ấm Áp",
    soft_neutral: "Visual Xinh Tự Nhiên",
  };

  const shotHookEn =
    shot === "closeup_selfie"
      ? "Pretty Close-Up Gaze"
      : shot === "portrait"
      ? "Sweetest Eye Smile"
      : shot === "half_body"
      ? "Effortless Cute Vibe"
      : "Lovely Full Vibe";

  const shotHookVi =
    shot === "closeup_selfie"
      ? "Cận Mặt Xinh Xỉu"
      : shot === "portrait"
      ? "Ánh Mắt Biết Cười"
      : shot === "half_body"
      ? "Thần Thái Cuốn Hút"
      : "Dáng Xinh Hết Nước Chấm";

  const vibeTagEn: Record<ReupVibeCategory, string> = {
    visual_smile: "Douyin",
    dance_trend: "Dance Vibe",
    street_fashion: "OOTD",
    cosplay_trad: "Cosplay",
    beach_travel: "Summer Vibe",
    gym_sport: "Fit Girl",
  };

  const tagEn = customTag || vibeTagEn[vibe] || "Douyin";
  const subjEn = customSubject || "";

  const pools: Record<ReupLanguageMode, string[]> = {
    en: subjEn
      ? [
          `${subjEn} Is So Adorable! ✨ | ${tagEn}`,
          `${subjEn} Visuals 💖 | ${customTag || "Cute Vibes"}`,
          `Cute ${subjEn} Moment ✨ | ${tagEn}`,
          `${shotHookEn} 🌸 | ${subjEn}`,
          `${colorHookEn[palette] || "Sweet Visuals"} ✨ | ${subjEn}`,
          `Can't Stop Watching! 💖 | ${subjEn}`,
        ]
      : vibe === "dance_trend"
      ? [
          `Smooth Dance Moves ✨ | ${tagEn}`,
          `She Nailed The Beat! 🔥 | Dance`,
          `Cute Girl Dancing 💖 | Douyin`,
          `${colorHookEn[palette] || "Sweet Vibe"} ✨ | Dance`,
          `Addictive Rhythm 💫 | Cute Vibes`,
          `So Effortlessly Cute! ✨ | Dance`,
        ]
      : vibe === "street_fashion"
      ? [
          `${colorHookEn[palette] || "Chic Street Style"} ✨ | OOTD`,
          `Cute Street Girl 💖 | Fashion`,
          `Effortless Outfit Vibe ✨ | Douyin`,
          `She Looks Stunning! 🖤 | OOTD`,
          `${shotHookEn} ✨ | Street Style`,
          `Pure Model Vibes 💫 | Asian Girl`,
        ]
      : vibe === "cosplay_trad"
      ? [
          `${colorHookEn[palette] || "Fairy Girl"} 🌸 | ${customTag || "Douyin"}`,
          `Real-Life Anime Girl ✨ | Cosplay`,
          `She Is So Dreamy! 💖 | Fairy Vibe`,
          `Cute Traditional Look ✨ | Douyin`,
          `Pure Fairy Visuals 🌸 | Cute Girl`,
          `Adorable Cosplay Girl ✨ | Kawaii`,
        ]
      : vibe === "beach_travel"
      ? [
          `Sunny Summer Girl ☀️ | Beach Vibe`,
          `Golden Hour Smile ✨ | Travel`,
          `Fresh Ocean Breeze 💖 | Cute Girl`,
          `${colorHookEn[palette] || "Summer Glow"} ✨ | Vacation`,
          `Radiant Holiday Vibe 🌸 | Douyin`,
          `Sweetest Beach Smile ✨ | Cute Vibes`,
        ]
      : vibe === "gym_sport"
      ? [
          `Healthy & Glowing ✨ | Fit Girl`,
          `Sporty Cute Vibe 💪 | Gym`,
          `${colorHookEn[palette] || "Active Chic"} ✨ | Fitness`,
          `Stunning Workout Glow 💖 | Fit Vibe`,
          `Pure Energy & Charm ✨ | Sporty`,
          `Fit & Adorable! 🔥 | Asian Girl`,
        ]
      : [
          `She Is So Adorable! ✨ | ${tagEn}`,
          `${shotHookEn} 💖 | Cute Vibes`,
          `Cute Asian Girl ✨ | ${tagEn}`,
          `${colorHookEn[palette] || "Doll-Like Visuals"} 🌸 | Ulzzang`,
          `Wait For Her Smile 💖 | ${tagEn}`,
          `Unreal Doll Visuals ✨ | Pretty Girl`,
        ],

    vi: subjEn
      ? [
          `${subjEn} Xinh Xỉu Luôn ✨ | ${customTag || "Gái Xinh"}`,
          `${shotHookVi} 💖 | ${subjEn}`,
          `${colorHookVi[palette] || "Visual Trong Trẻo"} ✨ | ${subjEn}`,
          `Nụ Cười Đốn Tim 🥰 | ${subjEn}`,
          `Ngắm Mãi Không Chán ✨ | ${subjEn}`,
          `Vibe Nàng Thơ 🌸 | ${subjEn}`,
        ]
      : [
          `${shotHookVi} ✨ | Gái Xinh`,
          `${colorHookVi[palette] || "Visual Trong Trẻo"} 💖 | Douyin`,
          `Xinh Xắn Đáng Yêu Quá 🥰 | Cute`,
          `Nụ Cười Gây Thương Nhớ 🌸 | Visual`,
          `Ngắm Thôi Cũng Thấy Cuốn ✨ | Trend`,
          `Vibe Nhẹ Nhàng Dịu Mắt 💖 | Nàng Thơ`,
        ],

    vi_en: [
          `${shotHookVi} ✨ | ${tagEn}`,
          `${colorHookVi[palette] || "Visual Cực Phẩm"} 💖 | Cute Vibes`,
          `Xinh Xỉu Luôn! ✨ | Pretty Girl`,
          `Nụ Cười Đốn Tim 🌸 | Sweet Smile`,
          `Thần Thái Cuốn Hút ✨ | Ulzzang`,
          `Ngắm Mãi Không Chán 💖 | ${tagEn}`,
        ],

    ko: [
          `너무 귀여운 비주얼 ✨ | ${customTag || "여신"}`,
          `심쿵 눈맞춤 모먼트 💖 | 청순미녀`,
          `인형 같은 분위기 🌸 | Ulzzang`,
          `미소가 너무 예뻐요 ✨ | Cute Vibe`,
          `무한 반복 비주얼 💫 | 데일리`,
          `청순 열매 먹은 미모 🥰 | Shorts`,
        ],

    zh: [
          `甜妹颜值暴击 ✨ | 抖音美女`,
          `一眼心动的神仙颜值 💖 | 纯欲风`,
          `这眼神太绝了 🌸 | 氛围感`,
          `笑容超治愈的小姐姐 ✨ | 甜美`,
          `精致娃娃脸美少女 💫 | 高颜值`,
          `越看越可爱的心动瞬间 🥰 | 美女`,
        ],

    ja: [
          `お人形さんみたいな可愛さ ✨ | 美少女`,
          `天使すぎる透明感 💖 | 可愛い`,
          `目が合う瞬間ドキッ 🌸 | ナチュラル`,
          `笑顔が癒やしすぎる ✨ | トレンド`,
          `圧倒的ヒロイン感 💫 | Kawaii`,
          `ずっと見てられる可愛さ 🥰 | 美女`,
        ],
  };

  return rotateArray(pools[lang] || pools.en, seed).slice(0, 6);
}

export function generateLocalReupSeoPackage(input: ReupSeoInput): ReupSeoPackage {
  const lex = VIBE_DATA[input.vibe] || VIBE_DATA.visual_smile;
  const lang = input.language || "en";
  const titleStyle: ReupTitleLengthStyle = input.titleStyle || "short";
  const note = (input.customNote || "").trim();
  const focus = note || lex.defaultFocus[lang];
  const seed = Math.max(0, Math.floor(input.seed || 0));

  let titles: string[];
  if (titleStyle === "short") {
    titles = buildShortSignatureTitles(input);
  } else {
    const shortSuffix = input.isShort ? " #Shorts" : "";
    const rawTemplates = rotateArray(lex.titleTemplates[lang], seed);
    titles = rawTemplates.slice(0, 6).map((tpl, idx) => {
      const filled = tpl.replace("{focus}", focus);
      if (input.isShort && idx < 4 && filled.length <= 90 && !filled.toLowerCase().includes("#shorts")) {
        return `${filled}${shortSuffix}`;
      }
      return filled;
    });
  }

  // Build hashtags
  const baseHashtags = [...lex.hashtags[lang]];
  if (input.isShort && !baseHashtags.some((h) => h.toLowerCase() === "#shorts")) {
    baseHashtags.unshift("#Shorts");
  }
  if (note) {
    const slugTag =
      "#" +
      note
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/đ/g, "d")
        .replace(/[^a-z0-9\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+/g, "");
    if (slugTag.length >= 3 && slugTag.length <= 26 && !baseHashtags.includes(slugTag)) {
      baseHashtags.splice(1, 0, slugTag);
    }
  }
  const hashtags = baseHashtags.slice(0, 10);

  // Build YouTube Studio comma-separated tags (strictly <= 485 chars for YouTube Studio 500-char limit)
  const candidateTags: string[] = [];
  if (note) {
    candidateTags.push(note);
  }
  for (const t of rotateArray(lex.tags[lang], seed)) {
    if (!candidateTags.some((x) => x.toLowerCase() === t.toLowerCase())) {
      candidateTags.push(t);
    }
  }
  if (input.isShort) {
    for (const st of ["shorts", "youtube shorts", "viral shorts"]) {
      if (!candidateTags.some((x) => x.toLowerCase() === st)) {
        candidateTags.push(st);
      }
    }
  } else {
    for (const lt of ["hd 1080p", "4k visual", "aesthetic compilation"]) {
      if (!candidateTags.some((x) => x.toLowerCase() === lt)) {
        candidateTags.push(lt);
      }
    }
  }

  const studioTags: string[] = [];
  let runningLen = 0;
  for (const tag of candidateTags) {
    const clean = tag.replace(/,/g, " ").trim();
    if (!clean) continue;
    const nextLen = runningLen === 0 ? clean.length : runningLen + 2 + clean.length;
    if (nextLen > 480) break;
    studioTags.push(clean);
    runningLen = nextLen;
  }
  const studioTagsCsv = studioTags.join(", ");

  // Build Description
  const cleanHandle = input.channelHandle
    ? input.channelHandle.startsWith("@")
      ? input.channelHandle
      : `@${input.channelHandle}`
    : "";

  const shortDescOpener: Record<ReupLanguageMode, string> = {
    en: note
      ? `A lovely moment featuring ${note}! 💖`
      : "Wait For Her Smile At The End 💖",
    vi: note
      ? `Khoảnh khắc cực xinh của ${note} 💖`
      : "Chờ xem nụ cười ở giây cuối nhé 💖",
    vi_en: note
      ? `Khoảnh khắc cực cuốn của ${note} ✨ | Lovely moment!`
      : "Chờ xem nụ cười cuối clip nhé 💖 | Wait For Her Smile!",
    ko: "끝까지 보면 심쿵하는 모먼트 💖",
    zh: "看到最后有心动笑容哦 💖",
    ja: "最後の笑顔まで見逃せない可愛さ 💖",
  };

  const shortCta: Record<ReupLanguageMode, string> = {
    en: `👉 Hit Like 👍 & Subscribe${cleanHandle ? ` (${cleanHandle})` : ""}`,
    vi: `👉 Bấm Like 👍 & Đăng ký kênh${cleanHandle ? ` (${cleanHandle})` : ""} nhé!`,
    vi_en: `👉 Hit Like 👍 & Subscribe${cleanHandle ? ` ${cleanHandle}` : ""}`,
    ko: `👉 좋아요 👍 & 구독 부탁드려요!`,
    zh: `👉 点赞 👍 并订阅频道看更多高颜值视频！`,
    ja: `👉 高評価 👍 & チャンネル登録お願いします！`,
  };

  const description =
    titleStyle === "short"
      ? [shortDescOpener[lang], "", shortCta[lang], "", hashtags.join(" ")].join("\n")
      : [
          titles[0],
          "",
          lex.descIntro[lang] + (note ? ` (${note})` : ""),
          "",
          lex.ctaLine[lang] + (cleanHandle ? `\n🔔 Channel: ${cleanHandle}` : ""),
          "",
          hashtags.join(" "),
        ].join("\n");

  return {
    titles,
    description,
    hashtags,
    studioTags,
    studioTagsCsv,
    studioTagsCharCount: studioTagsCsv.length,
    detectedVisualSummary: input.visualProfile?.summary_vi,
  };
}
