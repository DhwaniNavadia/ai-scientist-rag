from __future__ import annotations

import re
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Request

from models.schemas import UploadResponse

router = APIRouter()

_SAFE_STEM = re.compile(r"[^a-zA-Z0-9_\-]")


def _sanitize(name: str) -> str:
    stem = Path(name).stem
    return _SAFE_STEM.sub("_", stem)[:64] or "paper"


@router.post("/upload", response_model=UploadResponse)
async def upload_paper(request: Request, file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    paper_id = _sanitize(file.filename)
    inputs_dir: Path = request.app.state.inputs_dir
    inputs_dir.mkdir(parents=True, exist_ok=True)

    dest = inputs_dir / f"{paper_id}.pdf"
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    dest.write_bytes(content)

    return UploadResponse(paper_id=paper_id, filename=file.filename)


@router.get("/uploaded")
async def list_uploaded(request: Request) -> dict:
    """Return list of all uploaded PDF paper IDs."""
    inputs_dir: Path = request.app.state.inputs_dir
    if not inputs_dir.is_dir():
        return {"uploaded": []}
    ids = sorted(
        p.stem for p in inputs_dir.iterdir() if p.suffix.lower() == ".pdf"
    )
    return {"uploaded": ids}


@router.delete("/uploaded/{paper_id}")
async def delete_uploaded(paper_id: str, request: Request) -> dict:
    """Remove an uploaded paper."""
    inputs_dir: Path = request.app.state.inputs_dir
    pdf = inputs_dir / f"{paper_id}.pdf"
    if pdf.exists():
        pdf.unlink()
        return {"deleted": paper_id}
    raise HTTPException(status_code=404, detail="Paper not found.")
