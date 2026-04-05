#!/usr/bin/env python3
"""
run_pipeline.py — Autonomous AI Scientist top-level orchestrator.

Usage:
  python run_pipeline.py --mode full         # Run everything end-to-end
  python run_pipeline.py --mode tier1        # Single-paper pipeline only
  python run_pipeline.py --mode tier2        # Cross-paper pipeline only
  python run_pipeline.py --mode rag          # Index papers into Qdrant only
  python run_pipeline.py --mode report       # Final report assembly only
  python run_pipeline.py --mode check        # Validate all outputs exist
  python run_pipeline.py --mode eval         # Pairwise evaluation vs baseline
"""

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path

# ------------------------------------------------------------------
# Set up logging BEFORE importing ai_scientist modules so all module
# loggers inherit the root configuration.
# ------------------------------------------------------------------

from ai_scientist.config import OUTPUT_DIR  # ensures outputs/ dir exists

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.FileHandler(str(OUTPUT_DIR / "pipeline.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("run_pipeline")

from ai_scientist.config import (
    PAPER1_PATH, PAPER2_PATH, PAPER3_PATH, OPENAI_API_KEY,
)


# ---------------------------------------------------------------------------
# Guard helpers
# ---------------------------------------------------------------------------

def _require_file(path: Path, hint: str = "") -> bool:
    if not path.exists():
        msg = f"[✗] Missing: {path}"
        if hint:
            msg += f" — run --mode {hint} first"
        logger.error(msg)
        return False
    return True


def _require_api_key(step: str) -> bool:
    if not OPENAI_API_KEY:
        logger.error("[✗] OPENAI_API_KEY not set — add it to .env (required for %s)", step)
        return False
    return True


def _step(name: str, fn, *args, no_abort: bool = False, **kwargs):
    """Execute *fn* with args/kwargs, log result, honour no_abort flag."""
    logger.info("[→] %s", name)
    try:
        result = fn(*args, **kwargs)
        logger.info("[✓] %s", name)
        return result
    except Exception as exc:
        logger.error("[✗] %s failed: %s", name, exc)
        if not no_abort:
            raise
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Tier 1 — single-paper pipeline
# ---------------------------------------------------------------------------

def run_tier1(no_abort: bool = False) -> bool:
    logger.info("══════════ TIER 1: Single-Paper Pipeline ══════════")

    if not _require_file(PAPER1_PATH):
        return False
    if not _require_api_key("hypothesis generation"):
        return False

    # 1. PDF → sections.json
    from ai_scientist.ingestion.pdf_parser import run as parse_pdf
    sections = _step("PDF parsing", parse_pdf, PAPER1_PATH, no_abort=no_abort)
    if sections is None and not no_abort:
        return False

    # 2. sections.json → claims.json
    if not _require_file(OUTPUT_DIR / "sections.json", "tier1"):
        return False
    from ai_scientist.extraction.claim_extractor import run as extract_claims
    claims = _step("Claim extraction", extract_claims, no_abort=no_abort)
    if claims is not None:
        logger.info("    → %d claims written to outputs/claims.json", len(claims))

    # 3. sections.json → gaps_rulebased.json + gaps_actionable.json
    from ai_scientist.extraction.gap_detector import run as detect_gaps
    result = _step("Gap detection", detect_gaps, no_abort=no_abort)
    if result is not None:
        raw, actionable = result
        logger.info(
            "    → %d raw / %d actionable gaps written", len(raw), len(actionable)
        )

    # 4. gaps_actionable.json → hypotheses.json
    if not _require_file(OUTPUT_DIR / "gaps_actionable.json", "tier1"):
        return False
    from ai_scientist.reasoning.hypothesis_generator import run as gen_hypotheses
    hyps = _step("Hypothesis generation", gen_hypotheses, no_abort=no_abort)
    if hyps is not None:
        logger.info("    → %d raw hypotheses written to outputs/hypotheses.json", len(hyps))

    # 5. hypotheses.json → hypotheses_scored.json
    if not _require_file(OUTPUT_DIR / "hypotheses.json", "tier1"):
        return False
    from ai_scientist.reasoning.critic import run as score_hypotheses
    scored = _step("Hypothesis scoring (critic)", score_hypotheses, no_abort=no_abort)
    if scored is not None:
        logger.info("    → %d scored hypotheses written", len(scored))

    # 6. hypotheses_scored.json → disagreement_log_all.json
    if not _require_file(OUTPUT_DIR / "hypotheses_scored.json", "tier1"):
        return False
    from ai_scientist.reasoning.debate_orchestrator import run as build_debate
    dlog = _step("Debate orchestration", build_debate, no_abort=no_abort)
    if dlog is not None:
        logger.info("    → %d disagreement entries written", len(dlog))

    # 7. hypotheses_scored.json → reflection_logs.json
    from ai_scientist.reasoning.reflection_engine import run as gen_reflections
    refs = _step("Reflection generation", gen_reflections, no_abort=no_abort)
    if refs is not None:
        logger.info("    → %d reflections written", len(refs))

    return True


# ---------------------------------------------------------------------------
# Tier 2 — cross-paper pipeline
# ---------------------------------------------------------------------------

def run_tier2(no_abort: bool = False) -> bool:
    logger.info("══════════ TIER 2: Cross-Paper Pipeline ══════════")

    missing = [p for p in [PAPER2_PATH, PAPER3_PATH] if not p.exists()]
    if missing:
        for p in missing:
            logger.error("[✗] Missing paper: %s", p)
        return False

    from ai_scientist.cross_paper.claims_sectioned import main as extract_cross_claims
    _step("Cross-paper claim extraction", extract_cross_claims, no_abort=no_abort)

    if not _require_file(OUTPUT_DIR / "cross_paper_claims.json", "tier2"):
        return False
    from ai_scientist.cross_paper.contradictions import main as detect_contradictions
    _step("Contradiction detection", detect_contradictions, no_abort=no_abort)

    return True


# ---------------------------------------------------------------------------
# RAG — index into Qdrant
# ---------------------------------------------------------------------------

def run_rag(no_abort: bool = False) -> bool:
    logger.info("══════════ RAG: Indexing Papers into Qdrant ══════════")

    if not _require_file(OUTPUT_DIR / "sections.json", "tier1"):
        return False

    sections = json.loads((OUTPUT_DIR / "sections.json").read_text(encoding="utf-8"))

    from ai_scientist.rag.document_store import DocumentStore
    store = DocumentStore()
    count = _step("Indexing paper1 into Qdrant", store.index_paper, "paper1", sections, no_abort=no_abort)
    if count is not None:
        logger.info("    → %d chunks indexed", count)

    return True


# ---------------------------------------------------------------------------
# Report — final assembly
# ---------------------------------------------------------------------------

def run_report(no_abort: bool = False) -> bool:
    logger.info("══════════ REPORT: Assembling Final Report ══════════")

    required = [
        OUTPUT_DIR / "sections.json",
        OUTPUT_DIR / "claims.json",
        OUTPUT_DIR / "gaps_actionable.json",
        OUTPUT_DIR / "hypotheses_scored.json",
        OUTPUT_DIR / "reflection_logs.json",
        OUTPUT_DIR / "disagreement_log_all.json",
    ]
    for f in required:
        if not _require_file(f, "tier1"):
            return False

    from ai_scientist.reporting.assembler import run as assemble_report
    report = _step("Final report assembly", assemble_report, no_abort=no_abort)
    if report is not None:
        lineage_count = len(report.get("hypothesis_lineage", []))
        logger.info(
            "    → final_report.json written — lineage: %d entries", lineage_count
        )

    return True


# ---------------------------------------------------------------------------
# Evaluation — Phase 9 pairwise assessment
# ---------------------------------------------------------------------------

def run_eval(
    gaps_dir:     Path = None,
    baseline_dir: Path = None,
    output_dir:   Path = None,
    n_runs:       int  = 3,
    verbose:      bool = False,
    no_abort:     bool = False,
) -> bool:
    """Run pairwise evaluation of the multi-agent system vs the single-agent baseline."""
    logger.info("══════════ EVAL: Pairwise Evaluation vs Baseline ══════════")

    if not _require_api_key("evaluation"):
        return False

    required_outputs = [
        OUTPUT_DIR / "gaps_actionable.json",
        OUTPUT_DIR / "disagreement_log_all.json",
    ]
    for f in required_outputs:
        if not _require_file(f, "tier1"):
            return False

    from evaluation.report import run as run_eval_report
    from evaluation.logger import get_eval_logger
    get_eval_logger(verbose=verbose)

    try:
        report = run_eval_report(
            gaps_path=gaps_dir,
            baseline_dir=baseline_dir,
            output_dir=output_dir,
            n_runs=n_runs,
            verbose=verbose,
        )
        metrics = report.get("metrics", {})
        logger.info(
            "Evaluation complete — win_rate=%.3f  keep_rate=%.3f  "
            "avg_score=%.3f  agreement=%.3f",
            metrics.get("win_rate", 0),
            metrics.get("keep_rate", 0),
            metrics.get("avg_hypothesis_score", 0),
            metrics.get("agent_agreement_rate", 0),
        )
        return True
    except Exception as exc:
        logger.error("Evaluation failed: %s", exc)
        if not no_abort:
            raise
        return False


# ---------------------------------------------------------------------------
# Qdrant Cross-Paper Analysis — contradictions across indexed papers
# ---------------------------------------------------------------------------

def run_qdrant_analysis(no_abort: bool = False) -> bool:
    logger.info("══════════ QDRANT: Cross-Paper Analysis ══════════")

    from ai_scientist.cross_paper.contradictions import detect_qdrant_contradictions
    contradictions = _step(
        "Qdrant cross-paper contradiction detection",
        detect_qdrant_contradictions,
        no_abort=no_abort,
    )
    if contradictions is not None:
        logger.info("    → %d Qdrant-based contradictions found", len(contradictions))
        # Merge with existing contradictions file if it exists
        out_path = OUTPUT_DIR / "cross_paper_contradictions.json"
        existing = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        # Append new Qdrant contradictions (avoid duplicates by type)
        existing_types = {(c.get("type"), c.get("explanation", "")[:60]) for c in existing}
        for c in contradictions:
            key = (c.get("type"), c.get("explanation", "")[:60])
            if key not in existing_types:
                existing.append(c)
        out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        logger.info("    → Saved %d total contradictions to %s", len(existing), out_path)

    return True


# ---------------------------------------------------------------------------
# Metrics — automated quality evaluation
# ---------------------------------------------------------------------------

def run_metrics(no_abort: bool = False) -> bool:
    """Run automated quality metrics on pipeline outputs."""
    logger.info("══════════ METRICS: Automated Quality Evaluation ══════════")

    from ai_scientist.evaluation.metrics import run_evaluation
    metrics = _step("Evaluation metrics", run_evaluation, no_abort=no_abort)
    if metrics is not None:
        hyp_q = metrics.get("hypothesis_quality", {})
        logger.info(
            "    → avg_total=%.2f  keep_rate=%.2f  claims=%d  gaps=%d",
            hyp_q.get("avg_total", 0),
            hyp_q.get("keep_rate", 0),
            metrics.get("claim_count", 0),
            metrics.get("gap_count", 0),
        )
    return True


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_full(no_abort: bool = False) -> bool:
    ok = True
    ok = run_tier1(no_abort=no_abort) and ok
    ok = run_rag(no_abort=True) and ok       # RAG is best-effort; don't block pipeline
    ok = run_tier2(no_abort=no_abort) and ok
    ok = run_qdrant_analysis(no_abort=True) and ok  # Qdrant cross-paper analysis
    ok = run_report(no_abort=no_abort) and ok
    ok = run_metrics(no_abort=True) and ok   # Automated quality metrics (best-effort)
    return ok


# ---------------------------------------------------------------------------
# Check — validation
# ---------------------------------------------------------------------------

def run_check() -> bool:
    logger.info("══════════ CHECK: Validating Outputs ══════════")

    expected = [
        "sections.json",
        "claims.json",
        "gaps_rulebased.json",
        "gaps_actionable.json",
        "hypotheses.json",
        "hypotheses_scored.json",
        "disagreement_log_all.json",
        "reflection_logs.json",
        "cross_paper_claims.json",
        "cross_paper_contradictions.json",
        "final_report.json",
        "evaluation_metrics.json",
    ]

    all_ok = True
    for name in expected:
        path = OUTPUT_DIR / name
        if path.exists():
            size = path.stat().st_size
            logger.info("[✓] %-40s  (%d bytes)", name, size)
        else:
            logger.error("[✗] Missing: %s", name)
            all_ok = False

    # Extra: validate hypothesis_lineage count in final_report.json
    fr_path = OUTPUT_DIR / "final_report.json"
    if fr_path.exists():
        try:
            report = json.loads(fr_path.read_text(encoding="utf-8"))
            lineage = report.get("hypothesis_lineage", [])
            n_disagree = report.get("paper_context", {}).get("num_disagreement_entries", 0)
            if lineage and len(lineage) == n_disagree:
                logger.info("[✓] hypothesis_lineage has %d entries (matches disagreement log)", len(lineage))
            else:
                logger.warning(
                    "[!] hypothesis_lineage=%d but disagreement_entries=%d",
                    len(lineage), n_disagree,
                )
        except Exception as exc:
            logger.error("[✗] Could not validate final_report.json: %s", exc)

    return all_ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="run_pipeline",
        description="Autonomous AI Scientist — pipeline orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  full    Run everything end-to-end
  tier1   Single-paper pipeline only
  tier2   Cross-paper pipeline only
  rag     Index papers into Qdrant only
  report  Final report assembly only
  check   Validate all outputs exist + schema check
  eval    Pairwise evaluation of system vs single-agent baseline
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "tier1", "tier2", "rag", "qdrant_analysis", "report", "check", "eval"],
        default="full",
        help="Pipeline mode to run (default: full)",
    )
    parser.add_argument(
        "--no-abort",
        action="store_true",
        help="Continue to the next step on failure instead of aborting",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable DEBUG-level logging",
    )

    # ── Evaluation-mode arguments ────────────────────────────────────────────
    parser.add_argument(
        "--gaps-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Path to gaps JSON file or directory (default: outputs/gaps_actionable.json)",
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Directory for baseline cache files (default: outputs/baseline/)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Directory for evaluation report output (default: outputs/evaluation/)",
    )
    parser.add_argument(
        "--n-runs",
        type=int,
        default=3,
        metavar="N",
        help="Number of judge runs per gap pair (default: 3)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging for the evaluation module",
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    mode_map = {
        "full":             lambda: run_full(no_abort=args.no_abort),
        "tier1":            lambda: run_tier1(no_abort=args.no_abort),
        "tier2":            lambda: run_tier2(no_abort=args.no_abort),
        "rag":              lambda: run_rag(no_abort=args.no_abort),
        "qdrant_analysis":  lambda: run_qdrant_analysis(no_abort=args.no_abort),
        "report":           lambda: run_report(no_abort=args.no_abort),
        "check":            run_check,
        "eval":             lambda: run_eval(
                      gaps_dir=args.gaps_dir,
                      baseline_dir=args.baseline_dir,
                      output_dir=args.output_dir,
                      n_runs=args.n_runs,
                      verbose=args.verbose,
                      no_abort=args.no_abort,
                  ),
    }

    success = mode_map[args.mode]()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
