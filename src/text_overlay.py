"""Pillow renderer for the top hook with word-level highlighting."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

VIOLET = "#A855F7"


def resolve_font(preferred: Path | None, fallback_paths: list[Path] | None = None) -> Path:
    candidates = [preferred] if preferred else []
    candidates.extend(fallback_paths or [])
    candidates.extend([
        Path("fonts/Rubik-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
    ])
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate
    raise FileNotFoundError("No usable TrueType font found. Run setup.sh or upload a .ttf file.")


def _normalized(token: str) -> str:
    return re.sub(r"[^\w'-]", "", token, flags=re.UNICODE).casefold()


def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    box = draw.textbbox((0, 0), text, font=font, stroke_width=1)
    return float(box[2] - box[0])


def _wrap(draw: ImageDraw.ImageDraw, words: list[str], font: ImageFont.FreeTypeFont, max_width: int) -> list[list[str]]:
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        if current and _measure(draw, candidate, font) > max_width:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    return lines


def render_hook(
    text: str,
    highlighted_words: list[str],
    output_path: Path,
    font_path: Path | None = None,
    highlight_color: str = VIOLET,
) -> Path:
    """Create a transparent 1080x420 PNG for overlaying over the top region."""
    image = Image.new("RGBA", (1080, 420), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    words = text.strip().split()
    if not words:
        image.save(output_path)
        return output_path

    resolved = resolve_font(font_path)
    size = 72
    while True:
        font = ImageFont.truetype(str(resolved), size=size)
        lines = _wrap(draw, words, font, 960)
        line_height = int(size * 1.22)
        if len(lines) <= 3 and len(lines) * line_height <= 260:
            break
        size -= 4
        if size < 42:
            break

    targets = {_normalized(word) for word in highlighted_words if _normalized(word)}
    total_height = len(lines) * line_height
    y = max(92, (420 - total_height) // 2)
    for line in lines:
        widths = [_measure(draw, word, font) for word in line]
        space = _measure(draw, " ", font)
        x = (1080 - (sum(widths) + space * (len(line) - 1))) / 2
        for word, width in zip(line, widths):
            fill = highlight_color if _normalized(word) in targets else "#FFFFFF"
            draw.text((x, y), word, font=font, fill=fill, stroke_width=1, stroke_fill=(0, 0, 0, 180))
            x += width + space
        y += line_height

    image.save(output_path)
    return output_path
