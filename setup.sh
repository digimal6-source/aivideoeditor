#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if command -v sudo >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends ffmpeg fontconfig fonts-dejavu-core curl ca-certificates
else
  apt-get update
  apt-get install -y --no-install-recommends ffmpeg fontconfig fonts-dejavu-core curl ca-certificates
fi

python -m pip install --upgrade pip wheel setuptools
python -m pip install -r requirements.txt

mkdir -p fonts
fetch_font() {
  local url="$1"
  local destination="$2"
  if [[ ! -s "$destination" ]]; then
    echo "Downloading $(basename "$destination")..."
    curl --fail --location --retry 3 --output "$destination" "$url"
  fi
}

fetch_font "https://raw.githubusercontent.com/google/fonts/main/ofl/rubik/static/Rubik-Bold.ttf" "fonts/Rubik-Bold.ttf"
# Indivisible is proprietary; Montserrat Black is the open-source metric-safe fallback.
fetch_font "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/static/Montserrat-Black.ttf" "fonts/Indivisible-Black.ttf"

fc-cache -f >/dev/null 2>&1 || true
ffmpeg -version | head -n 1
python - <<'PY'
import streamlit, whisper
print("Streamlit:", streamlit.__version__)
print("Whisper import: OK")
PY

echo "Setup complete. Run: streamlit run app.py"
