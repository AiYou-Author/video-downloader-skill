#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHECK_ONLY=false
HAS_ERROR=false

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { echo -e "${GREEN}✓${NC} $1"; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; HAS_ERROR=true; }
err()  { echo -e "${RED}✗${NC} $1"; HAS_ERROR=true; }

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --check-only) CHECK_ONLY=true; shift ;;
    *) shift ;;
  esac
done

echo "=== Video Downloader Skill Setup ==="
echo ""

# Check Python
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 --version 2>&1)
  ok "Python3: $PY_VER"
else
  err "Python3 not found. Install with: apt install python3"
fi

# Check yt-dlp
if python3 -c "import yt_dlp" 2>/dev/null; then
  YT_VER=$(python3 -m yt_dlp --version 2>/dev/null || echo "unknown")
  ok "yt-dlp: $YT_VER"
else
  warn "yt-dlp not installed. Run: pip install yt-dlp"
fi

# Check ffmpeg
if command -v ffmpeg &>/dev/null; then
  FF_VER=$(ffmpeg -version 2>&1 | head -1)
  ok "ffmpeg: $FF_VER"
else
  warn "ffmpeg not installed. Format merging and audio extraction won't work."
  echo "       Install: apt install ffmpeg"
fi

# Check optional env vars
if [ -n "${VIDEO_DL_OUTPUT_DIR:-}" ]; then
  ok "VIDEO_DL_OUTPUT_DIR = $VIDEO_DL_OUTPUT_DIR"
else
  echo "  VIDEO_DL_OUTPUT_DIR not set (default: ./downloads)"
fi

if [ -n "${VIDEO_DL_PROXY:-}" ]; then
  ok "VIDEO_DL_PROXY = $VIDEO_DL_PROXY"
fi

if [ -n "${VIDEO_DL_COOKIES_FILE:-}" ]; then
  if [ -f "$VIDEO_DL_COOKIES_FILE" ]; then
    ok "Cookies file: $VIDEO_DL_COOKIES_FILE"
  else
    warn "Cookies file not found: $VIDEO_DL_COOKIES_FILE"
  fi
fi

echo ""

if $CHECK_ONLY; then
  if $HAS_ERROR; then
    echo "Some checks failed. Fix the issues above before using the skill."
    exit 1
  else
    echo "All checks passed."
  fi
else
  # Install yt-dlp if needed
  if ! python3 -c "import yt_dlp" 2>/dev/null; then
    echo "Installing yt-dlp..."
    pip install yt-dlp
    ok "yt-dlp installed"
  fi
  echo ""
  echo "Setup complete. Run: python3 ${BASE_DIR}/scripts/downloader.py --help"
fi
