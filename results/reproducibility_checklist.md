# Reproducibility Checklist — Autonomous AI Scientist

Use this checklist to reproduce the full pipeline and evaluation results from scratch.
All experiments were run on Python 3.11 with the package versions pinned in `requirements.txt`.

> **Note:** Evaluation results in the `results/` directory are currently based on mock data.
> Complete Steps 1–6 below to generate real evaluation figures.

---

## Environment

- [ ] Python 3.8 or higher installed (`python --version`)
- [ ] Git installed and repo cloned
- [ ] Virtual environment created and activated
  ```bash
  python -m venv .venv
  # Windows: .venv\Scripts\activate
  # macOS/Linux: source .venv/bin/activate
  ```
- [ ] Dependencies installed
  ```bash
  pip install -r requirements.txt
  pip install -e .
  ```
- [ ] `.env` file created from `.env.example`
  ```bash
  cp .env.example .env
  ```
- [ ] `OPENAI_API_KEY` set in `.env` (required for all reasoning steps)
- [ ] `ANTHROPIC_API_KEY` set in `.env` (optional; enables `claude-opus-4-5` judge)

---

## Step 1 — Validate Environment

```bash
python run_pipeline.py --mode check
```

**Expected result:** All checks pass; console prints `[CHECK] All checks passed`.

- [ ] Check passes without errors

---

## Step 2 — Provide Input PDFs

- [ ] `data/papers/paper1.pdf` exists (required)
- [ ] `data/papers/paper2.pdf` exists (optional, for cross-paper analysis)
- [ ] `data/papers/paper3.pdf` exists (optional, for cross-paper analysis)

In the pre-computed experiments:
- `paper1.pdf` = HSAP paper (arXiv 2602.05875 or equivalent)
- `paper2.pdf` and `paper3.pdf` = placeholder papers for cross-paper module

---

## Step 3 — Run Full Pipeline

```bash
python run_pipeline.py --mode full
```

**Expected outputs** (all in `outputs/`):

- [ ] `sections.json` — non-empty, keys include at least one section heading
- [ ] `claims.json` — list with at least 1 claim entry
- [ ] `gaps_actionable.json` — list with at least 1 gap; expected ~16 for HSAP paper
- [ ] `hypotheses.json` — one entry per gap
- [ ] `hypotheses_scored.json` — each entry has `critic.total` and `critic.decision`
- [ ] `disagreement_log_all.json` — each entry has `agent_outputs` array and `disagreement_summary`
- [ ] `reflection_logs.json` — entries for all KEEP hypotheses
- [ ] `cross_paper_claims.json` — exists (may be empty if only paper1.pdf provided)
- [ ] `cross_paper_contradictions.json` — exists
- [ ] `final_report.json` — exists and has `lineage` field
- [ ] `pipeline.log` — non-empty; no CRITICAL errors

**Timing:** ~3–5 minutes with OpenAI API calls (depends on number of gaps detected).

---

## Step 4 — Run Evaluation Module

```bash
python run_pipeline.py --mode eval \
  --gaps-dir outputs \
  --output-dir outputs/evaluation \
  --n-runs 3 \
  --verbose
```

**Expected outputs:**

- [ ] `outputs/baseline/` directory created with one `<gap_id>_baseline.json` per gap
- [ ] `outputs/evaluation/evaluation_report.json` created
- [ ] `evaluation_report.json` contains:
  - `metrics.win_rate` (float 0–1)
  - `metrics.avg_hypothesis_score` (float 0–10)
  - `metrics.keep_rate` (float 0–1)
  - `metrics.agent_agreement_rate` (float 0–1)
  - `per_gap_results` list with one entry per gap

**Timing:** ~2–5 minutes for 16 gaps × 3 runs = 48 judge calls.

---

## Step 5 — Verify Against Reported Results

After running Steps 3–4, compare your `evaluation_report.json` metrics against
the mock values in `results/aggregated_results.json`.

| Metric | Mock (paper_1) | Real (your run) |
|--------|:--------------:|:---------------:|
| `win_rate` | 0.68 | |
| `avg_hypothesis_score` | 7.2 | |
| `keep_rate` | 0.72 | |
| `agent_agreement_rate` | 0.81 | |

> Fill in the "Real" column and update `results/aggregated_results.json` if real
> values differ substantially from mock values.

- [ ] `win_rate` is within expected range (0.5–0.8 for a well-formed paper)
- [ ] `avg_hypothesis_score` is > 5.0 (system should beat baseline)
- [ ] `keep_rate` is within 0.5–0.9

---

## Step 6 — Update Results Files (if running real evaluation)

If you have generated real evaluation data, update the mock values:

```bash
# Update results/aggregated_results.json with real metrics
# Update results/comparison_analysis.json with real per-paper scores
# Update results/key_findings.json with real measurements
# Regenerate result_tables.md   (edit manually or re-run evaluation script)
```

- [ ] `results/aggregated_results.json` updated with real data
- [ ] `results/comparison_analysis.json` updated
- [ ] `data_source` field in each JSON changed from `"mock"` to `"real"`
- [ ] `results/visualizations.html` `DATA` object updated with real values

---

## Step 7 — Docker Reproduction

```bash
# Build image and run full pipeline in containers
docker-compose up --build

# Run evaluation inside containers
docker-compose run ai_scientist \
  python run_pipeline.py --mode eval --n-runs 3 --verbose
```

- [ ] `docker-compose up --build` completes without build errors
- [ ] `outputs/final_report.json` is created inside the mounted volume
- [ ] `outputs/evaluation/evaluation_report.json` is created

---

## Step 8 — Test Suite

```bash
# All 131 tests must pass
python -m pytest tests/ evaluation/tests/ -v
```

- [ ] 131 tests pass with no failures

---

## Software Versions

| Software | Version used |
|----------|:------------:|
| Python | 3.11 |
| openai | see requirements.txt |
| anthropic | see requirements.txt |
| qdrant-client | see requirements.txt |
| pytest | see requirements.txt |
| Docker | 24+ |
| docker-compose | 2.x |

---

## Known Reproducibility Issues

1. **LLM non-determinism:** Hypothesis text and critic scores vary across runs
   because `temperature > 0` is used. The critic scores in `disagreement_log_all.json`
   are from a single original run and will not exactly reproduce.

2. **API rate limits:** Large numbers of gaps (> 20) may trigger OpenAI rate
   limits. Use `--no-abort` to continue after individual failures, or reduce the
   PDF to the key sections.

3. **Qdrant instance required for RAG:** If Qdrant is not running, the `rag`
   and `full` modes will fail at the indexing step. Use `--mode tier1` to skip
   RAG, or start Qdrant first:
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

4. **Mock vs. real evaluation:** The `results/` metrics are mock. Until
   `--mode eval` is run, do not cite the quantitative figures as experimental
   results.
