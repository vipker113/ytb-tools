#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
echo "🚀 Đang cài đặt thư viện cho SubPulse Autopilot (0₫ Free Mode) trên Mac..."
npm install
echo "✅ Đã sẵn sàng! Đang mở http://localhost:3000 ..."
(sleep 3 && open http://localhost:3000) &
npm run dev
