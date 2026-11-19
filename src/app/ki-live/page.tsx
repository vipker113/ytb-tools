import type { Metadata } from "next";
import { KiLivePublicBoard } from "@/components/KiLivePublicBoard";

export const metadata: Metadata = {
  title: "⚡ Realtime KI Power Meter | Live Evolution Dashboard",
  description:
    "Bảng theo dõi thanh năng lượng KI thời gian thật (đồng bộ YouTube mỗi 5 phút).",
};

export default function KiLivePage() {
  return <KiLivePublicBoard />;
}
