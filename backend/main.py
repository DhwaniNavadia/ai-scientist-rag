from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import outputs, pipeline, query, upload

load_dotenv()

# ── Config from environment ───────────────────────────────────────────────────

_here = Path(__file__).parent

PIPELINE_DIR = Path(os.getenv("PIPELINE_DIR", str(_here.parent))).resolve()
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", str(PIPELINE_DIR / "outputs"))).resolve()
INPUTS_DIR = Path(os.getenv("INPUTS_DIR", str(PIPELINE_DIR / "inputs"))).resolve()
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = (
    ["*"] if CORS_ORIGINS_RAW.strip() == "*" else [o.strip() for o in CORS_ORIGINS_RAW.split(",")]
)

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous AI Scientist API",
    version="1.0.0",
    description="Backend API for the Autonomous AI Scientist research pipeline.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach path config to app state so routers can read it
app.state.pipeline_dir = PIPELINE_DIR
app.state.outputs_dir = OUTPUTS_DIR
app.state.inputs_dir = INPUTS_DIR

# ── Routers ────────────────────────────────────────────────────────────────────

app.include_router(upload.router, prefix="/api")
app.include_router(pipeline.router, prefix="/api/pipeline")
app.include_router(outputs.router, prefix="/api/outputs")
app.include_router(query.router, prefix="/api")


# ── Convenience aliases ───────────────────────────────────────────────────────

@app.get("/api/papers")
async def list_papers() -> dict:
    """Alias for /api/outputs/papers — returns {papers: [str]}."""
    from services.output_reader import list_available_papers
    papers = list_available_papers(
        app.state.outputs_dir,
        inputs_dir=app.state.inputs_dir,
    )
    return {"papers": papers}


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
