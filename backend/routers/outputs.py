from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from models.schemas import CrossPaperData, EvaluationReport, FinalReport, PapersListResponse
from services.output_reader import (
    list_available_papers,
    read_cross_paper_data,
    read_evaluation_report,
    read_final_report,
)

router = APIRouter()


@router.get("/papers", response_model=PapersListResponse)
async def list_papers(request: Request) -> PapersListResponse:
    papers = list_available_papers(
        request.app.state.outputs_dir,
        inputs_dir=request.app.state.inputs_dir,
    )
    return PapersListResponse(papers=papers)


@router.get("/{paper_id}/final_report", response_model=FinalReport)
async def get_final_report(paper_id: str, request: Request) -> FinalReport:
    try:
        return read_final_report(paper_id, request.app.state.outputs_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Report not yet generated.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{paper_id}/evaluation_report", response_model=EvaluationReport)
async def get_evaluation_report(paper_id: str, request: Request) -> EvaluationReport:
    try:
        return read_evaluation_report(paper_id, request.app.state.outputs_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Evaluation report not yet generated.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{paper_id}/cross_paper", response_model=CrossPaperData)
async def get_cross_paper(paper_id: str, request: Request) -> CrossPaperData:
    try:
        return read_cross_paper_data(paper_id, request.app.state.outputs_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# Map friendly download names → actual output filenames
_DOWNLOAD_FILE_MAP: dict[str, str] = {
    "final_report": "final_report.json",
    "evaluation_report": "evaluation_metrics.json",
    "sections": "sections.json",
    "claims": "claims.json",
    "gaps": "gaps_actionable.json",
    "hypotheses": "hypotheses_scored.json",
    "reflection": "reflection_logs.json",
    "debate": "disagreement_log_all.json",
    "cross_paper": "cross_paper_claims.json",
    "evaluation": "evaluation_metrics.json",
}


@router.get("/{paper_id}/download/{file_type}")
async def download_file(paper_id: str, file_type: str, request: Request) -> FileResponse:
    if file_type not in _DOWNLOAD_FILE_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"file_type must be one of {set(_DOWNLOAD_FILE_MAP.keys())}",
        )

    target_name = _DOWNLOAD_FILE_MAP[file_type]
    outputs_dir: Path = request.app.state.outputs_dir

    # Also check alternative filenames (evaluation_metrics.json ↔ evaluation_report.json)
    alt_names = {target_name}
    _alt_map = {
        "evaluation_metrics.json": "evaluation_report.json",
        "evaluation_report.json": "evaluation_metrics.json",
    }
    if target_name in _alt_map:
        alt_names.add(_alt_map[target_name])

    candidates: list[Path] = []
    for name in alt_names:
        candidates.extend([
            outputs_dir / paper_id / name,
            outputs_dir / name,
            outputs_dir / paper_id / "evaluation" / name,
            outputs_dir / "evaluation" / name,
        ])

    for path in candidates:
        if path.exists():
            return FileResponse(
                path=str(path),
                media_type="application/json",
                filename=f"{paper_id}_{file_type}.json",
            )

    raise HTTPException(status_code=404, detail=f"{target_name} not found.")
