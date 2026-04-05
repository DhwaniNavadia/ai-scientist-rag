"""backend/routers/query.py — RAG semantic search endpoint."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from models.schemas import QueryChunk, QueryRequest, QueryResponse

router = APIRouter()

# Ensure the project root is on sys.path so ai_scientist imports work
_backend_dir = Path(__file__).resolve().parent.parent
_project_root = _backend_dir.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))


def _get_retriever():
    """Lazy-init RAGRetriever (returns None if Qdrant is not configured)."""
    try:
        from ai_scientist.rag.document_store import DocumentStore
        from ai_scientist.rag.retriever import RAGRetriever
        from ai_scientist.config import validate_qdrant_config

        if not validate_qdrant_config():
            return None
        return RAGRetriever(DocumentStore())
    except Exception:
        return None


@router.post("/query", response_model=QueryResponse)
async def rag_query(body: QueryRequest, request: Request) -> QueryResponse:
    """Semantic search over all indexed papers in Qdrant."""
    retriever = _get_retriever()
    if retriever is None:
        raise HTTPException(
            status_code=503,
            detail="RAG retriever unavailable — Qdrant credentials not configured.",
        )

    try:
        results = retriever.retrieve(
            query=body.query,
            top_k=body.top_k,
            paper_id=body.paper_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {exc}")

    chunks = [
        QueryChunk(
            score=r.get("score", 0.0),
            paper_id=r.get("paper_id", ""),
            section=r.get("section", ""),
            chunk_index=r.get("chunk_index", 0),
            text=r.get("text", ""),
        )
        for r in results
    ]
    return QueryResponse(query=body.query, results=chunks)
