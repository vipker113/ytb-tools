export function formatNumber(n: number): string {
  return new Intl.NumberFormat("vi-VN").format(Math.round(n || 0));
}

export function formatCompact(n: number): string {
  if (!n) return "0";
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1)} Tr`;
  }
  if (n >= 10_000) {
    return `${(n / 1_000).toFixed(n >= 100_000 ? 0 : 1)} N`;
  }
  return formatNumber(n);
}

export function formatDuration(seconds: number): string {
  if (!seconds || seconds <= 0) return "0:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function formatDateShort(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function getOutlierBadgeStyle(score: number): {
  label: string;
  className: string;
} {
  if (score >= 10) {
    return {
      label: `${score.toFixed(1)}x Siêu Viral 🔥`,
      className:
        "bg-gradient-to-r from-red-500/25 to-amber-500/25 text-amber-300 border-amber-500/40",
    };
  }
  if (score >= 4) {
    return {
      label: `${score.toFixed(1)}x Outlier 🔥`,
      className: "bg-orange-500/20 text-orange-300 border-orange-500/35",
    };
  }
  if (score >= 2) {
    return {
      label: `${score.toFixed(1)}x Vượt chuẩn`,
      className: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    };
  }
  return {
    label: `${score.toFixed(1)}x Trung bình`,
    className: "bg-zinc-800 text-zinc-400 border-zinc-700",
  };
}
