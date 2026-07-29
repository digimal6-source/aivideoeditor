"""Local Whisper transcription and ASS caption generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

StatusCallback = Callable[[str], None]


@dataclass(frozen=True)
class Caption:
    start: float
    end: float
    text: str


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    whole = int(seconds % 60)
    centiseconds = int(round((seconds - int(seconds)) * 100))
    if centiseconds == 100:
        whole += 1
        centiseconds = 0
    return f"{hours}:{minutes:02d}:{whole:02d}.{centiseconds:02d}"


def _escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def _fallback_words(segment: dict) -> list[dict]:
    tokens = segment.get("text", "").strip().split()
    if not tokens:
        return []
    start, end = float(segment["start"]), float(segment["end"])
    step = max(0.05, (end - start) / len(tokens))
    return [{"word": token, "start": start + i * step, "end": min(end, start + (i + 1) * step)} for i, token in enumerate(tokens)]


def transcribe_to_captions(
    media_path: Path,
    model_name: str = "base",
    max_words: int = 3,
    status: StatusCallback | None = None,
) -> tuple[list[Caption], str | None]:
    """Transcribe media locally and return short, word-timed caption chunks."""
    if status:
        status(f"Loading Whisper {model_name} model...")
    import whisper

    model = whisper.load_model(model_name)
    if status:
        status("Transcribing audio locally...")
    result = model.transcribe(str(media_path), word_timestamps=True, fp16=False, verbose=False)

    words: list[dict] = []
    for segment in result.get("segments", []):
        words.extend(segment.get("words") or _fallback_words(segment))

    captions: list[Caption] = []
    for index in range(0, len(words), max_words):
        group = words[index:index + max_words]
        text = " ".join(str(item["word"]).strip() for item in group).strip()
        if text:
            captions.append(Caption(float(group[0]["start"]), float(group[-1]["end"]), text))
    return captions, result.get("language")


def write_ass(captions: list[Caption], output_path: Path, font_name: str = "Montserrat Black") -> Path:
    """Write captions positioned safely inside the lower 420px region."""
    safe_font = re.sub(r"[,\r\n]", "", font_name) or "DejaVu Sans"
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,{safe_font},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,4,2,50,50,180,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for caption in captions:
        text = _escape_ass(caption.text.upper())
        events.append(f"Dialogue: 0,{_ass_time(caption.start)},{_ass_time(caption.end)},Reel,,0,0,0,,{{\\an2\\pos(540,1705)}}{text}")
    output_path.write_text(header + "\n".join(events) + "\n", encoding="utf-8")
    return output_path
