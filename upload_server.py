"""Chunked upload sidecar used to bypass forwarded-port request size limits."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

UPLOAD_ROOT = Path("uploads").resolve()
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
CHUNK_SIZE = 5 * 1024 * 1024
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov"}

app = FastAPI(title="AI Video Editor Upload Service", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware,
    # Streamlit renders components in a sandboxed srcdoc iframe. Some browsers
    # report that iframe's Origin as "null", while others use the parent URL.
    allow_origins=["null", "http://localhost:8501", "http://127.0.0.1:8501"],
    allow_origin_regex=r"https://.*\.app\.github\.dev",
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


class StartUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    size: int = Field(gt=0, le=MAX_FILE_SIZE)


def _directory(upload_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", upload_id):
        raise HTTPException(status_code=400, detail="Invalid upload identifier")
    return UPLOAD_ROOT / upload_id


def _metadata(upload_id: str) -> dict:
    path = _directory(upload_id) / "metadata.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Upload not found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "chunk_size": CHUNK_SIZE}


@app.post("/uploads/start")
def start_upload(payload: StartUpload) -> dict:
    safe_name = Path(payload.filename).name
    if Path(safe_name).suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only MP4 and MOV files are accepted")
    upload_id = uuid.uuid4().hex
    directory = _directory(upload_id)
    directory.mkdir(parents=True, exist_ok=False)
    metadata = {"filename": safe_name, "size": payload.size, "chunk_size": CHUNK_SIZE}
    (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (directory / "video.part").touch()
    return {"upload_id": upload_id, "chunk_size": CHUNK_SIZE}


@app.post("/uploads/{upload_id}/chunks/{index}")
async def upload_chunk(upload_id: str, index: int, request: Request) -> dict:
    metadata = _metadata(upload_id)
    if index < 0:
        raise HTTPException(status_code=400, detail="Invalid chunk index")
    data = await request.body()
    if not data or len(data) > metadata["chunk_size"]:
        raise HTTPException(status_code=400, detail="Invalid chunk size")
    offset = index * metadata["chunk_size"]
    if offset + len(data) > metadata["size"]:
        raise HTTPException(status_code=400, detail="Chunk exceeds declared file size")
    part_path = _directory(upload_id) / "video.part"
    with part_path.open("r+b") as handle:
        handle.seek(offset)
        handle.write(data)
    return {"received": len(data), "index": index}


@app.post("/uploads/{upload_id}/complete")
def complete_upload(upload_id: str) -> dict:
    metadata = _metadata(upload_id)
    directory = _directory(upload_id)
    part_path = directory / "video.part"
    actual_size = part_path.stat().st_size
    if actual_size != metadata["size"]:
        raise HTTPException(
            status_code=409,
            detail=f"Upload incomplete: received {actual_size} of {metadata['size']} bytes",
        )
    final_path = directory / metadata["filename"]
    part_path.replace(final_path)
    return {"filename": metadata["filename"], "path": str(final_path), "size": actual_size}
