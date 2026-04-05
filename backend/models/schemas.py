from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    paper_id: str
    filename: str


# ── Pipeline ──────────────────────────────────────────────────────────────────

class RunPipelineRequest(BaseModel):
    paper_id: str
    mode: str = Field("full", pattern="^(full|tier1|tier2|rag|qdrant_analysis|report|check|eval)$")
    tier: Optional[str] = Field(None, pattern="^(tier1|tier2)$")
    paper_ids: Optional[List[str]] = Field(None, description="2-3 paper IDs for cross-paper (tier2) mode")


# ── RAG Query ─────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)
    paper_id: Optional[str] = None


class QueryChunk(BaseModel):
    score: float
    paper_id: str
    section: str
    chunk_index: int
    text: str


class QueryResponse(BaseModel):
    query: str
    results: List[QueryChunk]


class PipelineStatusResponse(BaseModel):
    paper_id: str
    status: str = Field(..., pattern="^(idle|running|completed|error)$")
    mode: Optional[str] = None
    message: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class RunPipelineResponse(BaseModel):
    job_id: str
    status: str


# ── Domain objects (mirror TypeScript types) ──────────────────────────────────

class Claim(BaseModel):
    claim_id: str
    claim_text: str
    evidence_text: str
    confidence: float
    section: str


class Gap(BaseModel):
    gap_id: str
    gap_description: str
    gap_type: str
    actionable_direction: str
    priority: int


class AgentHypothesis(BaseModel):
    agent: str
    hypothesis: str
    rationale: str
    score: float
    decision: str


class HypothesisPair(BaseModel):
    gap_id: str
    agentA: AgentHypothesis
    agentB: AgentHypothesis
    preferred: str
    agreement: bool


class ReflectionEntry(BaseModel):
    gap_id: str
    original_hypothesis: str
    improvement_plan: str
    revised_hypothesis: str
    improvement_score: float


class FinalReport(BaseModel):
    paper_id: str
    paper_title: str
    sections: dict
    claims: List[Claim]
    gaps: List[Gap]
    hypothesis_pairs: List[HypothesisPair]
    reflections: List[ReflectionEntry]
    generated_at: str


class PerGapEvalResult(BaseModel):
    gap_id: str
    gap_description: str
    majority_winner: str
    system_wins: int
    baseline_wins: int
    ties: int
    keep_votes: int
    avg_system_score: float
    avg_baseline_score: float


class EvalMetrics(BaseModel):
    win_rate: float
    avg_hypothesis_score: float
    keep_rate: float
    agent_agreement_rate: float
    total_gaps_evaluated: int
    total_comparisons_run: int


class EvalSummary(BaseModel):
    strengths: List[str]
    weaknesses: List[str]
    conclusion: str


class EvaluationReport(BaseModel):
    paper_id: str
    metrics: EvalMetrics
    per_gap_results: List[PerGapEvalResult]
    summary: EvalSummary


class CrossPaperData(BaseModel):
    cross_claims: list
    contradictions: list


class PapersListResponse(BaseModel):
    papers: List[str]
