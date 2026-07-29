"""AI Short-Form Video Editor — core processing package.

Modules
-------
silence_remover : ffprobe helpers + FFmpeg silencedetect + segment stitching
transcription   : Whisper word-level transcription + ASS subtitle generation
text_overlay    : Pillow hook rendering, font resolution, caption chunking
video_engine    : FFmpeg composite pipeline (1:1 viewport, zooms, burn-in)
"""

__version__ = "1.0.0"
