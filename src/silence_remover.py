"""FFmpeg-based silence detection and removal."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

StatusCallback = Callable[[str], None]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def probe_duration(path: Path) -> float:
    result = _run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "json", str(path),
    ])
    return float(json.loads(result.stdout)["format"]["duration"])


def detect_silences(path: Path, threshold_db: int = -30, min_duration: float = 0.45) -> list[tuple[float, float]]:
    command = [
        "ffmpeg", "-hide_banner", "-i", str(path), "-af",
        f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    process = subprocess.run(command, text=True, capture_output=True)
    log = process.stderr
    starts = [float(value) for value in re.findall(r"silence_start:\s*([0-9.]+)", log)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([0-9.]+)", log)]
    duration = probe_duration(path)
    if len(starts) > len(ends):
        ends.append(duration)
    return [(max(0.0, start), min(duration, end)) for start, end in zip(starts, ends) if end > start]


def _keep_intervals(duration: float, silences: list[tuple[float, float]], padding: float) -> list[tuple[float, float]]:
    keep: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in silences:
        cut_start = max(cursor, start + padding)
        if cut_start - cursor >= 0.08:
            keep.append((cursor, cut_start))
        cursor = max(cursor, end - padding)
    if duration - cursor >= 0.08:
        keep.append((cursor, duration))
    return keep


def remove_silence(
    input_path: Path,
    output_path: Path,
    threshold_db: int = -30,
    min_silence: float = 0.45,
    padding: float = 0.10,
    status: StatusCallback | None = None,
) -> Path:
    """Remove detected silent ranges while retaining a small natural edge padding."""
    if status:
        status("Analyzing silent pauses...")
    silences = detect_silences(input_path, threshold_db, min_silence)
    if not silences:
        shutil.copy2(input_path, output_path)
        return output_path

    duration = probe_duration(input_path)
    keep = _keep_intervals(duration, silences, padding)
    if not keep:
        raise ValueError("The selected range contains no audible content at this threshold.")

    filters: list[str] = []
    labels: list[str] = []
    for index, (start, end) in enumerate(keep):
        filters.extend([
            f"[0:v]trim=start={start:.4f}:end={end:.4f},setpts=PTS-STARTPTS[v{index}]",
            f"[0:a]atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS[a{index}]",
        ])
        labels.append(f"[v{index}][a{index}]")
    filters.append(f"{''.join(labels)}concat=n={len(keep)}:v=1:a=1[outv][outa]")

    if status:
        status(f"Stitching {len(keep)} speaking segments...")
    command = [
        "ffmpeg", "-y", "-hide_banner", "-i", str(input_path),
        "-filter_complex", ";".join(filters),
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(output_path),
    ]
    _run(command)
    return output_path
