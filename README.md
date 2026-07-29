# AI Video Editor

A production-oriented, open-source Streamlit app that turns long-form MP4/MOV footage into captioned 9:16 short-form reels. Processing is local: FFmpeg handles media composition and OpenAI Whisper handles transcription without an API key.

## Features

- Resumable-style in-app chunked uploads for large MP4/MOV files in Codespaces
- Timestamp slicing with `MM:SS` or `HH:MM:SS` input
- Configurable FFmpeg silence detection and seamless segment stitching
- Fixed 1080 × 1920 black canvas with a clipped 1080 × 1080 center viewport at `y=420`
- Subtle 1.0×–1.18× engagement zooms isolated to the square viewport
- Multi-line top hook with Electric Violet word highlighting (`#A855F7`)
- Local Whisper `base`/`small` transcription and maximum-three-word ASS caption chunks
- Burned-in lower captions with bold white type, black outline, and hard shadow
- H.264/AAC export at 30 or 60 FPS with a browser preview and download
- Custom hook and subtitle `.ttf` uploads

## Run in GitHub Codespaces

1. Open this repository on GitHub.
2. Select **Code → Codespaces → Create codespace on main**.
3. Wait for setup to install FFmpeg, Python packages, and fonts.
4. Run:

```bash
python -m streamlit run app.py
```

The app starts its chunk receiver automatically on port `8000`; Codespaces forwards ports `8501` and `8000`. The upload widget divides each video into 5 MB requests, so a large file does not trigger the proxy's per-request HTTP 413 limit.

After updating an existing Codespace, run:

```bash
git pull origin main
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Run on Debian/Ubuntu

```bash
git clone https://github.com/digimal6-source/aivideoeditor.git
cd aivideoeditor
bash setup.sh
python -m streamlit run app.py
```

## How to use

1. Choose an MP4 or MOV in the in-app upload card.
2. Click **Upload video** and wait for 100%.
3. Click **Use uploaded video** so Streamlit refreshes the available-file list.
4. Set timestamps, hook, highlighting, silence settings, model, and FPS.
5. Click **🚀 Generate Short-Form Reel**.
6. Preview and download `final_reel.mp4`.

The first render downloads the selected Whisper model. CPU rendering is intensive; begin with a 15–30 second range and the `base` model.

## Upload architecture

The Codespaces proxy rejects a single very large request before Streamlit can process it. The app avoids that platform limit without requiring terminal file management:

1. The embedded uploader splits the selected file into 5 MB browser blobs.
2. A private FastAPI sidecar accepts and writes each chunk at the correct byte offset.
3. Completion verifies the assembled file size before exposing it to the editor.
4. Only MP4/MOV files are accepted, filenames are sanitized, upload IDs are random, and maximum declared size is 4 GB.

## Video pipeline

1. Re-encode the selected timestamp range for frame-accurate trimming.
2. Detect silence with FFmpeg `silencedetect`; retain small edge padding and concatenate audible intervals.
3. Transcribe cleaned audio with local Whisper word timestamps.
4. Scale/crop source video to a square and apply a periodic zoom with `zoompan`.
5. Overlay that square at `(0, 420)` on a static 1080 × 1920 black canvas.
6. Overlay the Pillow hook and burn ASS captions into the lower region.
7. Encode H.264 (`libx264`, CRF 18, `yuv420p`) and AAC 192 kbps.

## Fonts

`setup.sh` downloads Rubik Bold and the open-source Montserrat Black alternative for Indivisible. The app also falls back to DejaVu Sans Bold.

## Troubleshooting

- **Upload service unavailable:** ensure port `8000` is forwarded and run `python -m pip install -r requirements.txt` before restarting Streamlit.
- **Upload completes but is not listed:** click **Use uploaded video**.
- **End time exceeds duration:** choose an end timestamp inside the source duration.
- **No audible content:** lower the silence threshold or disable silence removal.
- **Whisper is slow:** use `base`, shorten the range, or select a larger Codespace.
- **Out of memory:** use 30 FPS and a shorter source range.

## Security and privacy

Media remains inside the Codespace. The upload sidecar uses Codespaces' private forwarded-port access, sanitized filenames, file-type allowlisting, randomized upload directories, and a 4 GB size ceiling. Do not make the forwarded ports public for sensitive media.

## License

MIT
