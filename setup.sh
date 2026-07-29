#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh — System setup for Linux / GitHub Codespaces.
#
#   * Verifies (or installs) system FFmpeg + fontconfig
#   * Installs all Python dependencies from requirements.txt
#   * Downloads the default fonts (Rubik Bold / Indivisible Black) into fonts/
#
# The Codespaces devcontainer runs this automatically via `postCreateCommand`.
# Safe to re-run at any time:   bash setup.sh
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

echo "==> [1/3] Checking system FFmpeg"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "    ffmpeg not found — installing via apt-get"
  sudo apt-get update
  sudo apt-get install -y ffmpeg fontconfig
else
  echo "    $(ffmpeg -version | head -n 1)"
fi

echo "==> [2/3] Installing Python dependencies"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> [3/3] Downloading default fonts into ./fonts"
mkdir -p fonts

fetch() {  # fetch <output-file> <url> [<url> ...]
  local out="$1"; shift
  if [ -s "$out" ]; then
    echo "    $out already present — skipping"
    return 0
  fi
  for url in "$@"; do
    echo "    trying $url"
    if curl -fsSL --retry 2 --connect-timeout 15 -o "$out" "$url"; then
      echo "    saved -> $out"
      return 0
    fi
  done
  echo "    WARNING: could not download $out — built-in system-font fallback will be used."
  return 0
}

# Hook font — Rubik Bold (Google Fonts, OFL)
fetch fonts/Rubik-Bold.ttf \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/static/Rubik-Bold.ttf" \
  "https://github.com/google/fonts/raw/main/ofl/rubik/static/Rubik-Bold.ttf"

# Caption font — Indivisible Black (Mozilla, OFL)
fetch fonts/Indivisible-Black.ttf \
  "https://cdn.jsdelivr.net/gh/mozilla/fonts@main/ttf/Indivisible-Black.ttf" \
  "https://raw.githubusercontent.com/mozilla/fonts/main/ttf/Indivisible-Black.ttf" \
  "https://github.com/mozilla/fonts/raw/main/ttf/Indivisible-Black.ttf"

echo ""
echo "Setup complete. Start the app with:"
echo "    streamlit run app.py --server.port 8501"
