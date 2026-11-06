#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
STUDIO_DIR="$ROOT_DIR/youtube-shorts-channel"
WEB_DIR="$ROOT_DIR/ytb-tools"

echo "=================================================================="
echo " Proof of Wonder — Documentary Production Studio v6.0 Bootstrap"
echo " Workspace: $ROOT_DIR"
echo "=================================================================="

# 1. Check FFmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "⚠️  Chưa tìm thấy ffmpeg! Trên macOS hãy cài bằng: brew install ffmpeg"
  exit 1
fi
echo "✓ FFmpeg: $(ffmpeg -version | head -n 1)"

# 2. Setup Python virtual environment inside youtube-shorts-channel/.venv
echo "📦 Đang cài đặt môi trường Python cho Studio v6.0..."
if command -v uv >/dev/null 2>&1; then
  uv venv "$STUDIO_DIR/.venv" --python 3.11 || uv venv "$STUDIO_DIR/.venv"
  uv pip install --python "$STUDIO_DIR/.venv/bin/python" -r "$STUDIO_DIR/requirements.txt"
else
  python3 -m venv "$STUDIO_DIR/.venv"
  "$STUDIO_DIR/.venv/bin/pip" install --upgrade pip
  "$STUDIO_DIR/.venv/bin/pip" install -r "$STUDIO_DIR/requirements.txt"
fi
echo "✓ Studio v6.0 Python CLI sẵn sàng: $STUDIO_DIR/.venv/bin/python"

# 2b. Studio v9 optional dependency groups (flags: --with-ml --with-graphics --with-analysis --with-all)
WITH_ML=0; WITH_GRAPHICS=0; WITH_ANALYSIS=0
for arg in "$@"; do
  if [ "$arg" = "--with-ml" ] || [ "$arg" = "--with-all" ]; then WITH_ML=1; fi
  if [ "$arg" = "--with-graphics" ] || [ "$arg" = "--with-all" ]; then WITH_GRAPHICS=1; fi
  if [ "$arg" = "--with-analysis" ] || [ "$arg" = "--with-all" ]; then WITH_ANALYSIS=1; fi
done
install_group() {
  local req="$1"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$STUDIO_DIR/.venv/bin/python" -r "$req"
  else
    "$STUDIO_DIR/.venv/bin/pip" install -r "$req"
  fi
}
if [ "$WITH_ML" = "1" ]; then
  echo "🧠 Cài nhóm Visual Corpus (torch + transformers, chạy trên Apple Silicon mps)..."
  install_group "$STUDIO_DIR/requirements-ml.txt"
fi
if [ "$WITH_GRAPHICS" = "1" ]; then
  echo "📐 Cài nhóm Mechanism Overlay (ManimCE)..."
  if [ "$(uname)" = "Darwin" ] && command -v brew >/dev/null 2>&1; then
    brew list cairo >/dev/null 2>&1 || brew install cairo
    brew list pango >/dev/null 2>&1 || brew install pango
    brew list pkg-config >/dev/null 2>&1 || brew install pkg-config
  fi
  install_group "$STUDIO_DIR/requirements-graphics.txt"
fi
if [ "$WITH_ANALYSIS" = "1" ]; then
  echo "🔎 Cài nhóm Outlier Analyst (yt-dlp, scenedetect, transcript API)..."
  install_group "$STUDIO_DIR/requirements-analysis.txt"
fi

# 3. Verify Studio profiles & unit tests
"$STUDIO_DIR/.venv/bin/python" "$STUDIO_DIR/pipeline/pow_studio/cli.py" profiles

# 4. Setup ytb-tools Next.js Web UI if submodule is present
if [ -f "$WEB_DIR/package.json" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "🌐 Đang cài đặt thư viện cho Web UI (ytb-tools)..."
    (cd "$WEB_DIR" && npm install)
    echo "✓ Web UI sẵn sàng! Chạy: cd \"$WEB_DIR\" && npm run dev"
  else
    echo "ℹ️  Bỏ qua cài đặt ytb-tools vì máy chưa cài Node.js/npm."
  fi
fi

echo ""
echo "✅ HOÀN TẤT CÀI ĐẶT! Bạn có thể dựng video ngay trên máy này:"
echo "   export PY=\"$STUDIO_DIR/.venv/bin/python\""
echo "   export STUDIO=\"$STUDIO_DIR/pipeline/pow_studio/cli.py\""
echo "   \"\$PY\" \"\$STUDIO\" profiles"
