"""Streamlit interface for the local AI short-form video editor."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.video_engine import RenderOptions, parse_timestamp, render_reel

st.set_page_config(page_title="AI Video Editor", page_icon="✦", layout="wide")
UPLOAD_ROOT = Path("uploads").resolve()

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


@st.cache_resource
def ensure_upload_server() -> subprocess.Popen | None:
    """Start the local chunk receiver once per Streamlit server process."""
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
        return None
    except Exception:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "upload_server:app", "--host", "0.0.0.0", "--port", "8000"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            try:
                urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
                return process
            except Exception:
                time.sleep(0.2)
        process.terminate()
        raise RuntimeError("The chunked upload service could not start on port 8000.")


def save_upload(upload, destination: Path) -> Path:
    destination.write_bytes(upload.getbuffer())
    return destination


def uploaded_videos() -> list[Path]:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    return sorted(
        [path for path in UPLOAD_ROOT.glob("*/*") if path.is_file() and path.suffix.lower() in {".mp4", ".mov"}],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def uploader_html() -> str:
    return r"""
<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:transparent;color:#f7f7fa;font:14px system-ui,-apple-system,sans-serif}
.card{border:1px dashed rgba(168,85,247,.7);background:rgba(168,85,247,.07);border-radius:10px;padding:14px}
input{width:100%;padding:11px;border:1px solid rgba(255,255,255,.18);border-radius:7px;background:#111118;color:#fff}
button{width:100%;min-height:42px;margin-top:10px;border:0;border-radius:7px;background:#A855F7;color:white;font-weight:700;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}
.track{height:8px;background:#292934;border-radius:4px;margin-top:12px;overflow:hidden}.bar{height:100%;width:0;background:#A855F7;transition:width .15s}
#status{margin-top:9px;color:rgba(255,255,255,.72);line-height:1.4}.error{color:#ff8b82!important}.success{color:#72BC8F!important}
</style></head><body><div class="card">
<input id="file" type="file" accept="video/mp4,video/quicktime,.mp4,.mov">
<button id="upload">Upload video</button><div class="track"><div class="bar" id="bar"></div></div>
<div id="status">Files are split into 5 MB requests, avoiding the Codespaces request-size limit.</div></div>
<script>
const fileInput=document.getElementById('file'),button=document.getElementById('upload'),bar=document.getElementById('bar'),status=document.getElementById('status');
function apiBase(){let base;try{base=new URL(document.referrer)}catch(e){base=new URL('http://localhost:8501')};if(base.hostname.endsWith('.app.github.dev'))base.hostname=base.hostname.replace(/-8501(?=\.app\.github\.dev$)/,'-8000');else{base.hostname='localhost';base.port='8000'}return base.origin}
async function jsonRequest(url,options){const response=await fetch(url,options);if(!response.ok){let detail=response.statusText;try{detail=(await response.json()).detail||detail}catch(e){}throw new Error(detail)}return response.json()}
button.onclick=async()=>{const file=fileInput.files[0];if(!file){status.textContent='Choose an MP4 or MOV file first.';status.className='error';return}button.disabled=true;bar.style.width='0%';status.className='';try{const api=apiBase();status.textContent='Starting upload...';const start=await jsonRequest(api+'/uploads/start',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename:file.name,size:file.size})});const chunks=Math.ceil(file.size/start.chunk_size);for(let i=0;i<chunks;i++){const chunk=file.slice(i*start.chunk_size,Math.min(file.size,(i+1)*start.chunk_size));await jsonRequest(api+'/uploads/'+start.upload_id+'/chunks/'+i,{method:'POST',credentials:'include',headers:{'Content-Type':'application/octet-stream'},body:chunk});const percent=Math.round(((i+1)/chunks)*100);bar.style.width=percent+'%';status.textContent='Uploading... '+percent+'%'}await jsonRequest(api+'/uploads/'+start.upload_id+'/complete',{method:'POST',credentials:'include'});status.textContent='Upload complete. Click “Use uploaded video” below.';status.className='success'}catch(error){status.textContent='Upload failed: '+error.message;status.className='error'}finally{button.disabled=false}};
</script></body></html>
"""


try:
    ensure_upload_server()
except Exception as exc:
    st.error(str(exc))
    st.stop()

with st.sidebar:
    st.header("Reel settings")
    st.subheader("Source video")
    components.html(uploader_html(), height=180)
    refresh_uploads = st.button("Use uploaded video", use_container_width=True)
    videos = uploaded_videos()
    if videos:
        selected_video = st.selectbox(
            "Uploaded file",
            videos,
            format_func=lambda path: f"{path.name} · {path.stat().st_size / (1024**2):.0f} MB",
        )
    else:
        selected_video = None
        st.caption("Upload an MP4 or MOV above, then click **Use uploaded video**.")

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
1. **Upload** in resumable 5 MB chunks
2. **Slice** the selected timestamp range
3. **Tighten** silent pauses
4. **Transcribe** locally with Whisper
5. **Compose** the static 9:16 canvas
6. **Burn in** hook and captions
7. **Export** H.264 + AAC

All media stays inside your Codespace. No API key is required.
""")

if generate:
    if selected_video is None:
        st.error("Upload a video and click Use uploaded video first.")
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
        render_reel(selected_video, output_path, workdir, options, update_status)
        st.session_state.reel_bytes = output_path.read_bytes()
        st.session_state.reel_hash = hashlib.sha256(st.session_state.reel_bytes).hexdigest()
        st.success("Your reel is ready to preview and download.")
        st.rerun()
    except Exception as exc:
        progress.empty()
        status_box.empty()
        st.error(str(exc))
