# fonts/ — default typefaces

These two files are **downloaded automatically** — they are intentionally not
committed to git (`fonts/*.ttf` is in `.gitignore`):

| File | Purpose | Source | License |
|---|---|---|---|
| `Rubik-Bold.ttf` | Top text hook | `google/fonts` GitHub (static weights) | SIL OFL 1.1 |
| `Indivisible-Black.ttf` | Bottom captions | `mozilla/fonts` CDN / GitHub | SIL OFL 1.1 |

They are fetched by:

1. `bash setup.sh` — runs automatically when the Codespace is created
   (`postCreateCommand` in `.devcontainer/devcontainer.json`), or
2. the app itself — on render, `src/text_overlay.py:resolve_font()` tries the
   local file first, re-downloads it if missing, and finally falls back to
   the system **DejaVu Sans Bold** so rendering never hard-fails.

You can also upload any `.ttf` in the Streamlit sidebar to override a default
for a single render.
