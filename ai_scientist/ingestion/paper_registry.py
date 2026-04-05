"""ai_scientist/ingestion/paper_registry.py — Dynamic paper registry replacing hardcoded 3-paper limit."""

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

from ai_scientist.config import DATA_DIR, OUTPUT_DIR

# ---------------------------------------------------------------------------
# Registry file location
# ---------------------------------------------------------------------------

REGISTRY_PATH = OUTPUT_DIR / "paper_registry.json"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PaperEntry:
    paper_id: str
    title: str = ""
    pdf_path: str = ""
    arxiv_id: str = ""
    categories: List[str] = field(default_factory=list)
    status: str = "registered"  # registered | parsed | indexed | failed
    output_dir: str = ""


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class PaperRegistry:
    """In-memory registry backed by a JSON file.

    Replaces the hardcoded PAPER1_PATH / PAPER2_PATH / PAPER3_PATH model
    with a dynamic, N-paper registry.
    """

    def __init__(self, path: Path = REGISTRY_PATH) -> None:
        self._path = path
        self._papers: Dict[str, PaperEntry] = {}
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for item in data:
                    entry = PaperEntry(**{k: v for k, v in item.items() if k in PaperEntry.__dataclass_fields__})
                    self._papers[entry.paper_id] = entry
                logger.debug("Loaded %d papers from registry", len(self._papers))
            except Exception as exc:
                logger.warning("Failed to load paper registry: %s", exc)

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        data = [asdict(e) for e in self._papers.values()]
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        import os
        os.replace(str(tmp), str(self._path))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def register(
        self,
        paper_id: str,
        pdf_path: str = "",
        title: str = "",
        arxiv_id: str = "",
        categories: List[str] = None,
    ) -> PaperEntry:
        """Register a new paper or update an existing one."""
        if paper_id in self._papers:
            entry = self._papers[paper_id]
            if pdf_path:
                entry.pdf_path = pdf_path
            if title:
                entry.title = title
            if arxiv_id:
                entry.arxiv_id = arxiv_id
            if categories:
                entry.categories = categories
        else:
            entry = PaperEntry(
                paper_id=paper_id,
                pdf_path=pdf_path,
                title=title,
                arxiv_id=arxiv_id,
                categories=categories or [],
                output_dir=str(OUTPUT_DIR / paper_id),
            )
            self._papers[paper_id] = entry
            logger.info("Registered paper: %s", paper_id)

        self._save()
        return entry

    def get(self, paper_id: str) -> Optional[PaperEntry]:
        """Get a paper by ID."""
        return self._papers.get(paper_id)

    def list_all(self) -> List[PaperEntry]:
        """Return all registered papers."""
        return list(self._papers.values())

    def list_by_status(self, status: str) -> List[PaperEntry]:
        """Return papers with a given status."""
        return [p for p in self._papers.values() if p.status == status]

    def update_status(self, paper_id: str, status: str) -> None:
        """Update the status of a paper."""
        if paper_id in self._papers:
            self._papers[paper_id].status = status
            self._save()
        else:
            logger.warning("Paper %s not in registry — cannot update status", paper_id)

    def remove(self, paper_id: str) -> bool:
        """Remove a paper from the registry."""
        if paper_id in self._papers:
            del self._papers[paper_id]
            self._save()
            logger.info("Removed paper: %s", paper_id)
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._papers)

    def __contains__(self, paper_id: str) -> bool:
        return paper_id in self._papers

    def __len__(self) -> int:
        return len(self._papers)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    reg = PaperRegistry()
    print(f"Registry has {reg.count} papers")
    for p in reg.list_all():
        print(f"  {p.paper_id}: status={p.status}, path={p.pdf_path}")
