from __future__ import annotations

import logging
import subprocess
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from models.schemas import PipelineStatusResponse

logger = logging.getLogger(__name__)

# In-memory store: paper_id → PipelineStatusResponse
_statuses: Dict[str, PipelineStatusResponse] = {}
_lock = threading.Lock()


def get_status(paper_id: str) -> PipelineStatusResponse:
    with _lock:
        return _statuses.get(
            paper_id,
            PipelineStatusResponse(
                paper_id=paper_id,
                status="idle",
                mode=None,
                message="No pipeline run started yet.",
                started_at=None,
                completed_at=None,
            ),
        )


def _set_status(status: PipelineStatusResponse) -> None:
    with _lock:
        _statuses[status.paper_id] = status


def _run_subprocess(
    paper_id: str,
    mode: str,
    pipeline_dir: Path,
    inputs_dir: Path,
    outputs_dir: Path,
    paper_ids: Optional[List[str]] = None,
) -> None:
    """Worker thread: invoke the pipeline CLI and update status on completion."""
    import sys
    python_exe = sys.executable  # use the same Python/venv as the backend

    # Build command using the actual CLI: run_pipeline.py --mode <mode>
    cmd = [python_exe, str(pipeline_dir / "run_pipeline.py"), "--mode", mode]

    # Copy uploaded PDFs into data/papers/ as paper1.pdf, paper2.pdf, paper3.pdf
    import shutil

    data_papers = pipeline_dir / "data" / "papers"
    data_papers.mkdir(parents=True, exist_ok=True)

    if paper_ids and len(paper_ids) >= 2:
        # Cross-paper mode: place the specifically selected papers in order
        for i, pid in enumerate(paper_ids[:3], start=1):
            src = inputs_dir / f"{pid}.pdf"
            dest = data_papers / f"paper{i}.pdf"
            if src.exists():
                try:
                    shutil.copy2(src, dest)
                except OSError:
                    pass
            else:
                logger.warning("PDF not found for paper_id=%r at %s", pid, src)
    else:
        # Single-paper / default: primary paper first, then fill remaining slots
        all_pdfs = sorted(
            (p for p in inputs_dir.iterdir() if p.suffix.lower() == ".pdf"),
            key=lambda p: (0 if p.stem == paper_id else 1, p.stem),
        )

        for i, pdf_src in enumerate(all_pdfs[:3], start=1):
            dest = data_papers / f"paper{i}.pdf"
            try:
                shutil.copy2(pdf_src, dest)
            except OSError:
                pass

    try:
        result = subprocess.run(
            cmd,
            cwd=str(pipeline_dir),
            capture_output=True,
            text=True,
            timeout=1800,  # 30-minute hard timeout
        )
        success = result.returncode == 0
        stderr_tail = (result.stderr or "")[-500:]

        # If per-paper output dir is distinct, copy outputs there
        paper_output_dir = outputs_dir / paper_id
        if paper_output_dir != outputs_dir and outputs_dir.is_dir():
            import shutil
            paper_output_dir.mkdir(parents=True, exist_ok=True)
            for f in outputs_dir.iterdir():
                if f.is_file() and f.suffix == ".json":
                    dest = paper_output_dir / f.name
                    shutil.copy2(f, dest)

        _set_status(
            PipelineStatusResponse(
                paper_id=paper_id,
                status="completed" if success else "error",
                mode=mode,
                message=(
                    "Pipeline completed successfully."
                    if success
                    else f"Pipeline failed: {stderr_tail}"
                ),
                started_at=_statuses.get(paper_id, PipelineStatusResponse(paper_id=paper_id, status="idle", message="")).started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    except subprocess.TimeoutExpired:
        _set_status(
            PipelineStatusResponse(
                paper_id=paper_id,
                status="error",
                mode=mode,
                message="Pipeline timed out after 30 minutes.",
                started_at=_statuses.get(paper_id, PipelineStatusResponse(paper_id=paper_id, status="idle", message="")).started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    except Exception as exc:
        _set_status(
            PipelineStatusResponse(
                paper_id=paper_id,
                status="error",
                mode=mode,
                message=f"Unexpected error: {exc}",
                started_at=_statuses.get(paper_id, PipelineStatusResponse(paper_id=paper_id, status="idle", message="")).started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        )


def start_pipeline(
    paper_id: str,
    mode: str,
    pipeline_dir: Path,
    inputs_dir: Path,
    outputs_dir: Path,
    paper_ids: Optional[List[str]] = None,
) -> str:
    """
    Launch the pipeline in a background thread.
    Returns a job_id (same as paper_id for simplicity).
    """
    job_id = paper_id

    if paper_ids and len(paper_ids) >= 2:
        msg = f"Comparing papers: {', '.join(paper_ids)} (mode={mode!r})"
    else:
        msg = f"Running pipeline in mode={mode!r}..."

    _set_status(
        PipelineStatusResponse(
            paper_id=paper_id,
            status="running",
            mode=mode,
            message=msg,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=None,
        )
    )

    t = threading.Thread(
        target=_run_subprocess,
        args=(paper_id, mode, pipeline_dir, inputs_dir, outputs_dir, paper_ids),
        daemon=True,
    )
    t.start()
    return job_id
