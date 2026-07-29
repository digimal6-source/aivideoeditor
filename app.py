"""Streamlit interface for the local AI short-form video editor."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import streamlit as st

from src.video_engine import RenderOptions, parse_timestamp, render_reel

st.set_page_config(page_title="AI Video Editor", page_icon="✦", layout="wide")

st.markdown("""
<style>
.block-container {max-width: 1180px; padding-top: 2rem;}
.hero {border: 1px solid rgba(168,85,247,.35); background: linear-gradient(135deg, rgba(168,85,247,.15), rgba(39,131,222,.08)); border-radius: 12px; padding: 28px 32px; margin-bottom: 24px;}
.hero h1 {margin: 0 0 8px 0; font-size: 2.25rem; letter-spacing: -.03em;}
.hero p {margin: 0; color: rgba(255,255,255,.70); max-width: 720px;}
.violet {color: #A855F7; font-weight: 700;}
div[data-testid="stSidebar"] {border-right: 1px solid rgba(255,255,255,.10);}
.stButton > button, .stDownloadButton > button {min-height: 44px; border-radius: 8px; font-weight: 700;}
.preview-note {padding: 14px 16px; border: 1px solid rgba(255,255,255,.12); border-radius: 8px; color: rgba(255,255,255,.68);}
</style>
<div class="hero">
  <h1>AI Short-Form Video Editor <span class="violet">✦</span></h1>
  <p>Turn long-form footage into polished 9:16 reels with local Whisper captions, silence removal, engagement zooms, and highlighted hooks.</p>
</div>
""", unsafe_allow_html=True)


def save_upload(upload, destination: Path) -> Path:
    destination.write_bytes(upload.getbuffer())
    return destination


def resolve_local_video(value: str) -> Path:
    path = Path(value.strip()).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Video file was not found: {path}")
    if path.suffix.lower() not in {".mp4", ".mov"}:
        raise ValueError("The local source must be an MP4 or MOV file.")
    return path


with st.sidebar:
    st.header("Reel settings")
    source_mode = st.radio(
        "Video source",
        ["Browser upload", "Codespace file"],
        help="Use Codespace file for large videos that exceed the forwarded-port upload limit.",
    )
    if source_mode == "Browser upload":
        video = st.file_uploader(
            "Source video", type=["mp4", "mov"],
            help="MP4 or MOV. Large uploads may be rejected by the Codespaces proxy.",
        )
        local_video_path = ""
    else:
        video = None
        local_video_path = st.text_input("Codespace file path", "input.mp4")
        st.caption("Place the video in the repository using the Codespaces Explorer, then enter its path here.")

    left, right = st.columns(2)
    start_text = left.text_input("Start", "00:00", help="MM:SS")
    end_text = right.text_input("End", "00:30", help="MM:SS")
    hook_text = st.text_area("Hook text", "STOP SCROLLING — THIS CHANGES EVERYTHING", height=92)
    highlights = st.text_input("Highlight word(s)", "CHANGES", help="Comma-separated words")
    st.caption("Highlight color: 🟣 `#A855F7`")
    hook_font_upload = st.file_uploader("Hook font (.ttf)", type=["ttf"], key="hook_font")
    subtitle_font_upload = st.file_uploader("Subtitle font (.ttf)", type=["ttf"], key="subtitle_font")
    remove_silence_enabled = st.toggle("Remove silent pauses", value=True)
    threshold = st.slider("Silence threshold", min_value=-50, max_value=-15, value=-30, step=1, format="%d dB", disabled=not remove_silence_enabled)
    fps = st.radio("Export frame rate", [30, 60], horizontal=True, format_func=lambda value: f"{value} FPS")
    whisper_model = st.selectbox("Whisper model", ["base", "small"], help="Small is more accurate but slower on CPU.")
    generate = st.button("🚀 Generate Short-Form Reel", type="primary", use_container_width=True)

main_left, main_right = st.columns([1.2, 0.8], gap="large")
with main_left:
    st.subheader("Output")
    progress = st.progress(0.0)
    status_box = st.empty()
    if "reel_bytes" in st.session_state:
        st.video(st.session_state.reel_bytes, format="video/mp4")
        st.download_button(
            "Download final_reel.mp4", st.session_state.reel_bytes,
            file_name="final_reel.mp4", mime="video/mp4", use_container_width=True,
        )
    else:
        st.markdown('<div class="preview-note">Your completed 1080 × 1920 reel will appear here.</div>', unsafe_allow_html=True)

with main_right:
    st.subheader("Render pipeline")
    st.markdown("""
1. **Slice** the selected timestamp range
2. **Tighten** silent pauses
3. **Transcribe** locally with Whisper
4. **Compose** the static 9:16 canvas
5. **Burn in** hook and captions
6. **Export** H.264 + AAC

All media stays inside your Codespace. No API key is required.
""")

if generate:
    if source_mode == "Browser upload" and video is None:
        st.error("Upload an MP4 or MOV video first.")
        st.stop()
    if source_mode == "Codespace file" and not local_video_path.strip():
        st.error("Enter the path to an MP4 or MOV file in the Codespace.")
        st.stop()
    try:
        start_seconds = parse_timestamp(start_text)
        end_seconds = parse_timestamp(end_text)
        if end_seconds <= start_seconds:
            raise ValueError("End time must be later than start time.")
        if not hook_text.strip():
            raise ValueError("Hook text cannot be empty.")

        def update_status(message: str, fraction: float) -> None:
            progress.progress(min(max(fraction, 0.0), 1.0))
            status_box.info(message)

        workdir = Path(tempfile.mkdtemp(prefix="aivideoeditor_"))
        if source_mode == "Browser upload":
            suffix = Path(video.name).suffix.lower()
            input_path = save_upload(video, workdir / f"source{suffix}")
        else:
            input_path = resolve_local_video(local_video_path)

        hook_font = save_upload(hook_font_upload, workdir / "custom_hook.ttf") if hook_font_upload else None
        subtitle_font = save_upload(subtitle_font_upload, workdir / "custom_subtitle.ttf") if subtitle_font_upload else None
        output_path = workdir / "final_reel.mp4"
        options = RenderOptions(
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            hook_text=hook_text.strip(),
            highlight_words=[item.strip() for item in highlights.split(",") if item.strip()],
            remove_silence=remove_silence_enabled,
            silence_threshold_db=threshold,
            fps=fps,
            whisper_model=whisper_model,
            hook_font=hook_font,
            subtitle_font=subtitle_font,
        )
        render_reel(input_path, output_path, workdir, options, update_status)
        st.session_state.reel_bytes = output_path.read_bytes()
        st.session_state.reel_hash = hashlib.sha256(st.session_state.reel_bytes).hexdigest()
        st.success("Your reel is ready to preview and download.")
        st.rerun()
    except Exception as exc:
        progress.empty()
        status_box.empty()
        st.error(str(exc))
