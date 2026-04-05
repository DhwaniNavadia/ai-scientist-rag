# Autonomous AI Scientist

An end-to-end autonomous research pipeline that ingests academic PDFs, extracts
research gaps, generates and debates hypotheses via multiple LLM agents, critiques
every hypothesis, and evaluates the results against a keyword-only baseline — all
from a single CLI command.

> **Status:** Phase 10 complete · 131 tests passing · Docker-ready

---

## Table of Contents

1. [What It Does](#what-it-does)
2. [Architecture Overview](#architecture-overview)
3. [Quickstart (Docker)](#quickstart-docker)
4. [Manual Setup](#manual-setup)
5. [CLI Reference](#cli-reference)
6. [Output Files](#output-files)
7. [Results Summary](#results-summary)
8. [Project Structure](#project-structure)
9. [Running Tests](#running-tests)
10. [Extending the Pipeline](#extending-the-pipeline)
11. [Known Limitations](#known-limitations)
12. [Environment Variables](#environment-variables)

---

## What It Does

The pipeline automates six research assistance tasks that are normally performed
manually:

| Stage | Module | Description |
|-------|--------|-------------|
| 1 · Ingest | `pdf_parser` | Parse PDF into labelled sections (Abstract, Introduction, Evaluation, Conclusion) |
| 2 · Extract | `claim_extractor` | Identify contribution claims with confidence scores |
| 3 · Gap detect | `gap_detector` | Detect under-explored research directions via rule-based signals + LLM |
| 4 · Hypothesise | `hypothesis_generator` | Two independent LLM agents (AgentA / AgentB) propose solutions per gap |
| 5 · Critique | `critic` | Score every hypothesis on clarity, novelty, and feasibility (1–5 each) |
| 6 · Debate | `debate_orchestrator` | Compare scores; select preferred hypothesis per gap |
| 7 · Reflect | `reflection_engine` | KEEP-rated hypotheses receive LLM-generated improvement plans |
| 8 · Index | `document_store` / `retriever` | Embed sections into Qdrant for semantic retrieval (RAG) |
| 9 · Cross-paper | `cross_paper_claims` | Extract claims and detect numeric contradictions across multiple papers |
| 10 · Report | `assembler` | Merge all artifacts into a single structured `final_report.json` |
| 11 · Evaluate | `evaluation/` | Pairwise LLM judge scores system vs. keyword-only baseline |

---

## Architecture Overview

```
data/papers/
  paper1.pdf
  paper2.pdf   (optional)
  paper3.pdf   (optional)
       │
       ▼
  ai_scientist/
    ingestion/
      pdf_parser.py         → outputs/sections.json
    extraction/
      claim_extractor.py    → outputs/claims.json
      gap_detector.py       → outputs/gaps_rulebased.json
                               outputs/gaps_actionable.json
    reasoning/
      hypothesis_generator  → outputs/hypotheses.json
      critic.py             → outputs/hypotheses_scored.json
      debate_orchestrator   → outputs/disagreement_log_all.json
      reflection_engine     → outputs/reflection_logs.json
    rag/
      document_store.py     → Qdrant collection
      retriever.py          ← semantic search
    cross_paper/
      cross_paper_claims    → outputs/cross_paper_claims.json
      cross_paper_contradictions → outputs/cross_paper_contradictions.json
    reporting/
      assembler.py          → outputs/final_report.json
  evaluation/
    baseline.py             → outputs/baseline/<gap_id>_baseline.json
    judge.py                → per-gap win/loss/score
    pairwise.py             → N-run aggregation per gap
    metrics.py              → MetricsSummary
    report.py               → outputs/evaluation/evaluation_report.json
```

---

## Quickstart (Docker)

```bash
# 1. Clone the repo
git clone <repo-url>
cd autonomous-ai-scientist

# 2. Configure API keys
cp .env.example .env
# Edit .env — required: OPENAI_API_KEY
# Optional:    ANTHROPIC_API_KEY  (enables claude-opus-4-5 as evaluation judge)

# 3. Place your PDFs
#    paper1.pdf is required. paper2.pdf and paper3.pdf are optional.
cp /path/to/your/paper.pdf data/papers/paper1.pdf

# 4. Run the full pipeline
docker-compose up --build
```

Outputs will be written to `outputs/`. Logs go to `outputs/pipeline.log`.

To run evaluation after the pipeline completes:

```bash
docker-compose run ai_scientist \
  python run_pipeline.py --mode eval --n-runs 3 --verbose
```

---

## Manual Setup

```bash
# Python 3.8+ required
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -e .

# Copy and populate environment variables
cp .env.example .env

# Verify everything is ready
python run_pipeline.py --mode check
```

---

## CLI Reference

```
python run_pipeline.py --mode <mode> [options]
```

### Modes

| Mode | Description |
|------|-------------|
| `full` | Run the complete pipeline end-to-end (default) |
| `tier1` | Single-paper only: parse → extract → hypothesise → debate → reflect |
| `tier2` | Cross-paper analysis only (requires existing `sections.json`) |
| `rag` | Index papers into Qdrant only |
| `report` | Assemble `final_report.json` from existing artifacts |
| `check` | Validate environment and all expected outputs |
| `eval` | Pairwise evaluation of system vs. keyword-only baseline |

### Global Options

| Flag | Default | Description |
|------|---------|-------------|
| `--no-abort` | off | Continue on step failures instead of stopping |
| `--debug` | off | Enable DEBUG logging to stdout |

### Evaluation-Specific Options (`--mode eval`)

| Flag | Default | Description |
|------|---------|-------------|
| `--gaps-dir PATH` | `outputs` | Directory containing `gaps_actionable.json` |
| `--baseline-dir PATH` | `outputs/baseline` | Directory to cache baseline hypothesis files |
| `--output-dir PATH` | `outputs/evaluation` | Where to write `evaluation_report.json` |
| `--n-runs N` | `3` | Number of independent judge calls per gap |
| `--verbose` | off | Print per-gap judge results to stdout |

---

## Output Files

### Pipeline Outputs (`outputs/`)

| File | Description |
|------|-------------|
| `sections.json` | Parsed PDF sections keyed by heading name |
| `claims.json` | Extracted contribution claims with confidence scores |
| `gaps_rulebased.json` | Raw detected gaps (pre-filter) |
| `gaps_actionable.json` | Actionable gaps with `gap_id`, `gap_type`, `evidence_text` |
| `hypotheses.json` | Raw hypotheses from AgentA and AgentB |
| `hypotheses_scored.json` | Hypotheses with critic scores and KEEP/REVISE/REJECT |
| `disagreement_log_all.json` | Per-gap AgentA vs AgentB debate with preferred hypothesis |
| `reflection_logs.json` | Improvement plans for KEEP hypotheses |
| `cross_paper_claims.json` | Claims extracted from paper2 / paper3 |
| `cross_paper_contradictions.json` | Numeric contradictions detected across papers |
| `final_report.json` | Assembled complete research report with lineage |
| `pipeline.log` | Full run log with timestamps |

### Evaluation Outputs (`outputs/evaluation/`)

| File | Description |
|------|-------------|
| `evaluation_report.json` | Per-gap win/loss/score + aggregate metrics |

### Baseline Cache (`outputs/baseline/`)

| File | Description |
|------|-------------|
| `<gap_id>_baseline.json` | Keyword-only baseline hypothesis for each gap |

---

## Results Summary

> Mock evaluation results (3 papers, 32 gaps, 96 comparisons). Run
> `--mode eval` to generate real figures.

| Metric | System | Baseline | Delta |
|--------|:------:|:--------:|:-----:|
| Win Rate | **65.1%** | 28.4% | +36.7 pts |
| Avg Score (0–10) | **7.11** | 5.72 | +1.39 (+24.4%) |
| Keep Rate | **69.1%** | 43.8% | +25.3 pts |
| Agent Agreement | **79.5%** | N/A | — |

Open `results/visualizations.html` in any browser for interactive charts.
See `results/result_tables.md` for detailed per-paper breakdowns and
`results/conclusions.md` for full research analysis.

---

## Project Structure

```
autonomous-ai-scientist/
├── ai_scientist/
│   ├── config.py
│   ├── ingestion/
│   │   └── pdf_parser.py
│   ├── extraction/
│   │   ├── claim_extractor.py
│   │   └── gap_detector.py
│   ├── reasoning/
│   │   ├── hypothesis_generator.py
│   │   ├── critic.py
│   │   ├── debate_orchestrator.py
│   │   └── reflection_engine.py
│   ├── rag/
│   │   ├── document_store.py
│   │   └── retriever.py
│   ├── cross_paper/
│   │   ├── cross_paper_claims_sectioned.py
│   │   └── cross_paper_contradictions.py
│   └── reporting/
│       └── assembler.py
├── evaluation/
│   ├── baseline.py
│   ├── judge.py
│   ├── pairwise.py
│   ├── metrics.py
│   ├── report.py
│   └── tests/
│       ├── test_baseline.py
│       ├── test_judge.py
│       ├── test_pairwise.py
│       └── test_metrics_report.py
├── tests/
│   ├── test_ingestion.py
│   ├── test_extraction.py
│   ├── test_reasoning.py
│   └── test_rag.py
├── results/
│   ├── aggregated_results.json
│   ├── comparison_analysis.json
│   ├── key_findings.json
│   ├── result_tables.md
│   ├── visualizations.html
│   ├── qualitative_examples.json
│   ├── conclusions.md
│   ├── demo_script.md
│   └── reproducibility_checklist.md
├── data/papers/
│   └── paper1.pdf
├── outputs/           (generated at runtime)
├── run_pipeline.py
├── requirements.txt
├── setup.py
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Running Tests

```bash
# All 131 tests
python -m pytest tests/ evaluation/tests/ -v

# Pipeline tests only (73 tests)
python -m pytest tests/ -v

# Evaluation tests only (58 tests)
python -m pytest evaluation/tests/ -v

# Single module
python -m pytest tests/test_reasoning.py -v
```

---

## Extending the Pipeline

**Add a new paper:** Place it under `data/papers/` as `paper2.pdf` or `paper3.pdf`.
The cross-paper module picks it up automatically.

**Add a new gap type:** Edit the `GAP_TYPE_KEYWORDS` dict in
`ai_scientist/extraction/gap_detector.py`.

**Change the hypothesis model:** Update `MODEL` in
`ai_scientist/reasoning/hypothesis_generator.py`.

**Use a remote Qdrant cluster:** Set `QDRANT_HOST` and `QDRANT_PORT` in `.env`.

**Add a new evaluation judge:** Implement the `judge()` interface in
`evaluation/judge.py` and register it in `evaluation/report.py`.

---

## Known Limitations

- Requires an active OpenAI API key; all reasoning steps incur API costs.
- PDF parsing relies on embedded text extraction — scanned PDFs without OCR
  will not parse correctly.
- RAG indexing requires a running Qdrant instance (local Docker or remote).
- Cross-paper contradiction detection uses regex-based numeric extraction;
  semantic contradiction detection is not yet implemented.
- The debate orchestrator selects by highest critic total score without
  accounting for the KEEP/REVISE/REJECT decision (see `results/conclusions.md §4.1`).
- Hypotheses for semantically similar gaps are sometimes identical; a
  de-duplication step before generation is planned.

---

## Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `OPENAI_API_KEY` | ✓ | OpenAI API key (hypothesis generation, critic, reflection) |
| `ANTHROPIC_API_KEY` | optional | Anthropic key for `claude-opus-4-5` evaluation judge; falls back to `gpt-4o-mini` |
| `QDRANT_HOST` | optional | Qdrant hostname (default: `localhost`) |
| `QDRANT_PORT` | optional | Qdrant port (default: `6333`) |
| `COLLECTION_NAME` | optional | Qdrant collection name (default: `ai_scientist`) |
