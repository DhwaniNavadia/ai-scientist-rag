from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from models.schemas import (
    PipelineStatusResponse,
    RunPipelineRequest,
    RunPipelineResponse,
)
from services import pipeline_runner

router = APIRouter()


@router.post("/run", response_model=RunPipelineResponse)
async def run_pipeline(body: RunPipelineRequest, request: Request) -> RunPipelineResponse:
    current = pipeline_runner.get_status(body.paper_id)
    if current.status == "running":
        raise HTTPException(
            status_code=409,
            detail=f"Pipeline is already running for paper_id={body.paper_id!r}.",
        )

    mode = body.tier if body.mode in ("run", "tier1", "tier2") and body.tier else body.mode
    # Map frontend "run" to "full"
    if mode == "run":
        mode = "full"

    job_id = pipeline_runner.start_pipeline(
        paper_id=body.paper_id,
        mode=mode,
        pipeline_dir=request.app.state.pipeline_dir,
        inputs_dir=request.app.state.inputs_dir,
        outputs_dir=request.app.state.outputs_dir,
        paper_ids=body.paper_ids,
    )
    return RunPipelineResponse(job_id=job_id, status="running")


@router.get("/status/{paper_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(paper_id: str) -> PipelineStatusResponse:
    return pipeline_runner.get_status(paper_id)
