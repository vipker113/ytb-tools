"use client";

import { ExternalLink, Smartphone } from "lucide-react";
import { useEffect } from "react";
import { YoutubeIcon } from "./YoutubeIcon";

export function SmartRedirectClient({ rawHandle }: { rawHandle: string }) {
  const decoded = decodeURIComponent(rawHandle).trim();
  const normalizedHandle = decoded.startsWith("@")
    ? decoded
    : decoded.startsWith("UC") && decoded.length >= 22
    ? `channel/${decoded}`
    : `@${decoded}`;

  const webSubUrl = `https://www.youtube.com/${normalizedHandle}?sub_confirmation=1`;

  useEffect(() => {
    fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "trackSmartClick",
        handle: decoded.startsWith("@") ? decoded : `@${decoded}`,
      }),
    }).catch(() => {});

    const ua = navigator.userAgent || "";
    const isAndroid = /Android/i.test(ua);
    const isIOS = /iPhone|iPad|iPod/i.test(ua);

    if (isAndroid) {
      const intentUrl = `intent://www.youtube.com/${normalizedHandle}?sub_confirmation=1#Intent;package=com.google.android.youtube;scheme=https;S.browser_fallback_url=${encodeURIComponent(
        webSubUrl
      )};end`;
      window.location.href = intentUrl;
    } else if (isIOS) {
      const iosAppUrl = `vnd.youtube://www.youtube.com/${normalizedHandle}?sub_confirmation=1`;
      window.location.href = iosAppUrl;
      const timer = setTimeout(() => {
        window.location.href = webSubUrl;
      }, 1400);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        window.location.href = webSubUrl;
      }, 900);
      return () => clearTimeout(timer);
    }
  }, [decoded, normalizedHandle, webSubUrl]);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-2xl border border-zinc-800 bg-zinc-900/90 p-8 text-center shadow-2xl">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-500/15 border border-red-500/30 text-red-400">
          <YoutubeIcon className="h-9 w-9" />
        </div>
        <h1 className="text-xl font-bold text-white mb-2">
          Đang chuyển sang Kênh YouTube {decoded}
        </h1>
        <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
          Đang tự động mở ứng dụng YouTube gốc kèm hộp thoại xác nhận Đăng ký (1-Click Subscribe) để bạn không cần đăng nhập lại!
        </p>

        <a
          href={webSubUrl}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-red-600 hover:bg-red-500 px-5 py-3.5 text-sm font-semibold text-white transition"
        >
          <ExternalLink className="h-4 w-4" />
          Bấm vào đây nếu chưa tự chuyển hướng
        </a>

        <div className="mt-5 flex items-center justify-center gap-2 text-xs text-zinc-500">
          <Smartphone className="h-3.5 w-3.5" />
          <span>Smart Deep Link bởi SubPulse YouTube Growth</span>
        </div>
      </div>
    </div>
  );
}
