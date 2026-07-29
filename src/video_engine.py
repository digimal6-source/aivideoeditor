"""Orchestrates trimming, silence removal, transcription, and final FFmpeg render."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .silence_remover import remove_silence
from .text_overlay import render_hook, resolve_font
from .transcription import transcribe_to_captions, write_ass

StatusCallback = Callable[[str, float], None]


@dataclass(frozen=True)
class RenderOptions:
    start_seconds: float
    end_seconds: float
    hook_text: str
    highlight_words: list[str]
    remove_silence: bool = True
    silence_threshold_db: int = -30
    fps: int = 30
    whisper_model: str = "base"
    hook_font: Path | None = None
    subtitle_font: Path | None = None


def parse_timestamp(value: str) -> float:
    """Parse MM:SS or HH:MM:SS input."""
    value = value.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", value):
        raise ValueError("Use MM:SS or HH:MM:SS timestamp format.")
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        if seconds >= 60:
            raise ValueError("Seconds must be between 00 and 59.")
        return minutes * 60 + seconds
    hours, minutes, seconds = parts
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Minutes and seconds must be between 00 and 59.")
    return hours * 3600 + minutes * 60 + seconds


def probe_duration(path: Path) -> float:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ], check=True, capture_output=True, text=True)
    return float(json.loads(result.stdout)["format"]["duration"])


def _run(command: list[str]) -> None:
    process = subprocess.run(command, text=True, capture_output=True)
    if process.returncode:
        tail = "\n".join(process.stderr.splitlines()[-30:])
        raise RuntimeError(f"FFmpeg failed:\n{tail}")


def _escape_filter_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def _font_family(path: Path) -> str:
    name = path.stem.replace("-", " ")
    return "Montserrat Black" if "Indivisible" in name else name


def render_reel(input_path: Path, output_path: Path, workdir: Path, options: RenderOptions, status: StatusCallback) -> Path:
    if options.fps not in (30, 60):
        raise ValueError("FPS must be 30 or 60.")
    duration = probe_duration(input_path)
    if options.start_seconds < 0 or options.end_seconds <= options.start_seconds:
        raise ValueError("End time must be later than start time.")
    if options.end_seconds > duration + 0.25:
        raise ValueError(f"End time exceeds the video duration ({duration:.1f}s).")

    trimmed = workdir / "01_trimmed.mp4"
    status("Trimming video...", 0.08)
    _run([
        "ffmpeg", "-y", "-hide_banner", "-ss", f"{options.start_seconds:.3f}",
        "-to", f"{options.end_seconds:.3f}", "-i", str(input_path),
        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(trimmed),
    ])

    cleaned = workdir / "02_cleaned.mp4"
    if options.remove_silence:
        status("Removing silence...", 0.20)
        remove_silence(trimmed, cleaned, options.silence_threshold_db, status=lambda message: status(message, 0.26))
    else:
        shutil.copy2(trimmed, cleaned)

    status("Transcribing audio...", 0.43)
    captions, _language = transcribe_to_captions(
        cleaned, options.whisper_model, status=lambda message: status(message, 0.50)
    )
    subtitle_font = resolve_font(options.subtitle_font, [Path("fonts/Indivisible-Black.ttf")])
    ass_path = write_ass(captions, workdir / "captions.ass", _font_family(subtitle_font))

    status("Rendering hook artwork...", 0.66)
    hook_path = render_hook(
        options.hook_text, options.highlight_words, workdir / "hook.png", options.hook_font
    )

    fps = options.fps
    # zoompan is applied to the square stream before it is overlaid on the static portrait canvas.
    zoom = f"1+0.09*(1-cos(2*PI*mod(on\,{4 * fps})/{4 * fps}))"
    video_filter = (
        f"[0:v]fps={fps},scale=1080:1080:force_original_aspect_ratio=increase,"
        f"crop=1080:1080,zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':"
        f"y='ih/2-(ih/zoom/2)':d=1:s=1080x1080:fps={fps}[square];"
        f"color=c=black:s=1080x1920:r={fps}[canvas];"
        f"[canvas][square]overlay=x=0:y=420:shortest=1[framed];"
        f"[framed][1:v]overlay=x=0:y=0:format=auto[hooked];"
        f"[hooked]ass='{_escape_filter_path(ass_path)}':fontsdir='{_escape_filter_path(subtitle_font.parent)}'[video]"
    )

    status("Rendering final MP4...", 0.74)
    _run([
        "ffmpeg", "-y", "-hide_banner", "-i", str(cleaned), "-loop", "1", "-i", str(hook_path),
        "-filter_complex", video_filter, "-map", "[video]", "-map", "0:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart", str(output_path),
    ])
    status("Reel ready.", 1.0)
    return output_path
