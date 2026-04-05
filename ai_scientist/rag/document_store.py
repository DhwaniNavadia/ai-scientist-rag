"""ai_scientist/rag/document_store.py — Chunk, embed, and store paper sections in Qdrant Cloud."""

import hashlib
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import COLLECTION_NAME, QDRANT_URL, QDRANT_API_KEY, validate_qdrant_config

VECTOR_SIZE = 384   # all-MiniLM-L6-v2 output dimension
MODEL_NAME  = "all-MiniLM-L6-v2"


class DocumentStore:
    """
    Thin wrapper around Qdrant Cloud + SentenceTransformer that handles:
      chunk_sections → embed → upsert
    """

    def __init__(self, collection_name: str = COLLECTION_NAME) -> None:
        self.collection_name = collection_name
        self._model           = None   # lazy-loaded on first use
        self._client          = None   # lazy-loaded on first use

    # ------------------------------------------------------------------
    # Lazy initialisation
    # ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            from qdrant_client import QdrantClient
            from qdrant_client.models import Distance, VectorParams

            if not validate_qdrant_config():
                raise ConnectionError(
                    "Qdrant Cloud credentials not configured. "
                    "Set QDRANT_URL and QDRANT_API_KEY in .env"
                )

            self._client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

            existing = {c.name for c in self._client.get_collections().collections}
            if self.collection_name not in existing:
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
                )
                logger.info("Created Qdrant collection '%s'", self.collection_name)
            else:
                logger.debug("Using existing Qdrant collection '%s'", self.collection_name)
        return self._client

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading SentenceTransformer model '%s'", MODEL_NAME)
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk_sections(
        self,
        sections: Dict[str, str],
        paper_id: str,
        chunk_size: int = 256,
        overlap: int = 32,
    ) -> List[Dict]:
        """
        Split each section's text into overlapping token windows.

        Args:
            sections:   {section_name: full_text}
            paper_id:   identifier for the paper (e.g. "paper1")
            chunk_size: target tokens per chunk
            overlap:    tokens shared between consecutive chunks

        Returns:
            List of {paper_id, section, chunk_index, text}
        """
        chunks: List[Dict] = []
        for section, text in sections.items():
            if not text.strip():
                continue
            tokens      = text.split()
            chunk_index = 0
            start       = 0

            while start < len(tokens):
                end        = start + chunk_size
                chunk_text = " ".join(tokens[start:end])
                chunks.append({
                    "paper_id":    paper_id,
                    "section":     section,
                    "chunk_index": chunk_index,
                    "text":        chunk_text,
                })
                if end >= len(tokens):
                    break
                start       += chunk_size - overlap
                chunk_index += 1

        logger.debug("Chunked %d sections into %d chunks (paper=%s)", len(sections), len(chunks), paper_id)
        return chunks

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Embed *texts* using all-MiniLM-L6-v2. Returns list of 384-dim float vectors."""
        vectors = self.model.encode(texts, show_progress_bar=False, convert_to_numpy=True)
        return [v.tolist() for v in vectors]

    def upsert(self, chunks: List[Dict], embeddings: List[List[float]]) -> None:
        """
        Upsert *chunks* + *embeddings* into Qdrant.
        Point ID = hash(paper_id + "_" + chunk_index) truncated to int63.
        """
        from qdrant_client.models import PointStruct

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings"
            )

        points: List[PointStruct] = []
        for chunk, vec in zip(chunks, embeddings):
            key = f"{chunk['paper_id']}_{chunk['section']}_{chunk['chunk_index']}"
            uid = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2 ** 63)
            points.append(PointStruct(id=uid, vector=vec, payload=chunk))

        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[i: i + batch_size],
            )

        logger.debug("Upserted %d points into '%s'", len(points), self.collection_name)

    def index_paper(self, paper_id: str, sections: Dict[str, str]) -> int:
        """
        Full pipeline: chunk → embed → upsert.

        Returns:
            Number of chunks indexed.
        """
        chunks = self.chunk_sections(sections, paper_id)
        if not chunks:
            logger.warning("No chunks produced for paper_id='%s'", paper_id)
            return 0

        logger.info("Embedding %d chunks for paper '%s'", len(chunks), paper_id)
        embeddings = self.embed([c["text"] for c in chunks])
        self.upsert(chunks, embeddings)

        logger.info("Indexed %d chunks for paper '%s'", len(chunks), paper_id)
        return len(chunks)

    def index_paper_full(
        self,
        paper_id: str,
        sections: Dict[str, str],
        title: str = "",
        categories: List[str] = None,
        source: str = "arxiv",
    ) -> int:
        """
        Full pipeline with rich metadata: chunk → enrich payload → embed → upsert.

        Payload per chunk includes: paper_id, section, chunk_index, text,
        title, category (primary), source.

        Returns:
            Number of chunks indexed.
        """
        chunks = self.chunk_sections(sections, paper_id)
        if not chunks:
            logger.warning("No chunks produced for paper_id='%s'", paper_id)
            return 0

        primary_category = categories[0] if categories else ""
        for chunk in chunks:
            chunk["title"]    = title
            chunk["category"] = primary_category
            chunk["source"]   = source

        logger.info("Embedding %d chunks for paper '%s' (%s)", len(chunks), paper_id, title[:60])
        embeddings = self.embed([c["text"] for c in chunks])
        self.upsert(chunks, embeddings)

        logger.info("Stored %d vectors in Qdrant for paper '%s'", len(chunks), paper_id)
        return len(chunks)
