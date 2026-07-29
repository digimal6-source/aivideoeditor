# Fonts

`setup.sh` downloads the runtime fonts into this directory:

- `Rubik-Bold.ttf` — SIL Open Font License, from Google Fonts.
- `Indivisible-Black.ttf` — Montserrat Black stored under the requested runtime filename because Indivisible is not redistributable as an open-source asset.

The binary font files are intentionally downloaded during setup rather than committed. Users may upload licensed custom `.ttf` files from the Streamlit sidebar. If downloads are unavailable, the app falls back to DejaVu Sans Bold installed by the devcontainer.
