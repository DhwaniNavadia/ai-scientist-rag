# Autonomous AI Scientist — Live Demo Script

A step-by-step walkthrough for demonstrating the full pipeline to an audience.
Each step includes the exact command, expected output snippet, and talking points.

**Prerequisites:** Python 3.8+, valid `OPENAI_API_KEY`, and optionally
`ANTHROPIC_API_KEY` for the evaluation judge. All commands run from the project root.

---

## Setup (one-time, ~2 min)

```bash
# Clone and enter the project
cd "d:\AI SCIENTIST PROJECT\autonomous-ai-scientist"

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e .

# Configure API keys
cp .env.example .env
# Open .env and fill in:
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...  (optional, for evaluation judge)
```

---

## Step 0 — Environment Check (~10 s)

```bash
python run_pipeline.py --mode check
```

**What to point out:**
- Confirms all imports resolve correctly
- Lists which env vars are present / missing
- Exits with code 0 if ready, non-zero with descriptive error if not

**Expected output:**
```
[CHECK] OpenAI key        ✓ present
[CHECK] Qdrant            ✓ reachable at localhost:6333
[CHECK] data/papers/      ✓ paper1.pdf found
[CHECK] All checks passed — pipeline is ready to run
```

---

## Step 1 — Full Pipeline Run (Tier 1 through Report) (~3–5 min with API)

```bash
python run_pipeline.py --mode full
```

**What to point out:**
- PDF → sections → claims → gaps → hypotheses → critic → debate → reflection → RAG → cross-paper → final report
- Progress logged to stdout AND `outputs/pipeline.log`
- Each step writes its own JSON artifact; the pipeline is restartable

**Key artifacts produced:**
| File | Description |
|------|-------------|
| `outputs/sections.json` | Parsed PDF sections |
| `outputs/claims.json` | Extracted contribution claims |
| `outputs/gaps_actionable.json` | 16 actionable research gaps |
| `outputs/hypotheses_scored.json` | AgentA + AgentB hypotheses with critic scores |
| `outputs/disagreement_log_all.json` | Debate results, preferred hypothesis per gap |
| `outputs/reflection_logs.json` | Improvement plans for KEEP hypotheses |
| `outputs/final_report.json` | Assembled full research report |

---

## Step 2 — Inspect Gaps (~30 s)

```bash
python -c "
import json
with open('outputs/gaps_actionable.json') as f:
    gaps = json.load(f)
print(f'Total gaps detected: {len(gaps)}')
for g in gaps[:3]:
    print(f'  [{g[\"gap_id\"]}] {g[\"gap_type\"]:20s} — {g[\"gap_statement\"][:80]}...')
"
```

**What to point out:**
- 16 gaps found in paper_1 (HSAP), covering 6 gap types
- Each gap has machine-readable `gap_id`, `gap_type`, and `evidence_text`
- The pipeline's gap classifier uses keyword matching + section heuristics (zero hallucination risk)

---

## Step 3 — Inspect Best Hypothesis (~30 s)

```bash
python -c "
import json
with open('outputs/disagreement_log_all.json') as f:
    log = json.load(f)
# Find highest total
best = max(log, key=lambda x: x['agent_outputs'][0]['critic']['total'])
a = best['agent_outputs'][0]
print(f'Gap: {best[\"gap_id\"]} ({best[\"gap_type\"]})')
print(f'Hypothesis: {a[\"hypothesis_text\"]}')
print(f'Score: {a[\"critic\"][\"total\"]}/15  Decision: {a[\"critic\"][\"decision\"]}')
"
```

**Expected output:**
```
Gap: G1 (data_quality)
Hypothesis: A noise-robust preprocessing pipeline (denoising + wall-confidence filtering)
            will reduce PRM/RRT distance-estimation errors on low-quality floor plans.
Score: 14/15  Decision: KEEP
```

**What to point out:**
- Score 14/15 on first gap: clarity=5, novelty=5, feasibility=4
- Hypothesis is concrete, falsifiable, and directly tied to a measurable outcome

---

## Step 4 — Run Tier 1 Only (faster demo) (~1–2 min)

```bash
python run_pipeline.py --mode tier1
```

**What to point out:**
- Skips RAG indexing and cross-paper analysis
- Ideal for a quick demo on a single paper
- All gap / hypothesis / critic / debate / reflection steps still run

---

## Step 5 — Run Evaluation Module (~2–5 min, requires ANTHROPIC_API_KEY)

```bash
python run_pipeline.py --mode eval \
  --gaps-dir outputs \
  --output-dir outputs/evaluation \
  --n-runs 3 \
  --verbose
```

**What to point out:**
- Generates keyword-only baselines automatically (no human input needed)
- Runs N=3 independent judge calls per gap to improve estimate stability
- Outputs `outputs/evaluation/evaluation_report.json` with per-gap win/loss/score data
- Falls back to `gpt-4o-mini` if `ANTHROPIC_API_KEY` is not set

**Expected output tail:**
```
[EVAL] Gap G1   — system: 8.9  baseline: 5.2  winner: system
[EVAL] Gap G2   — system: 7.8  baseline: 5.6  winner: system
...
[EVAL] DONE — win_rate: 0.68  avg_score: 7.20  keep_rate: 0.72
[EVAL] Report saved → outputs/evaluation/evaluation_report.json
```

---

## Step 6 — View Results Dashboard (~10 s)

Open `results/visualizations.html` in any modern browser:

```bash
# Windows
start results\visualizations.html

# macOS
open results/visualizations.html

# Linux
xdg-open results/visualizations.html
```

**What to point out:**
- Six self-contained Chart.js charts, no server required
- Win rate bar chart, system vs baseline score comparison, radar profile per paper
- Decision distribution doughnut (paper_1 actual data)
- Critic dimension breakdown (feasibility is the main differentiator)

---

## Step 7 — Docker Run (production demo)

```bash
# Build and run everything in containers (Qdrant + pipeline)
docker-compose up --build
```

**What to point out:**
- `docker-compose.yml` spins up Qdrant vector DB + the pipeline container
- API keys passed through `.env` file, never baked into the image
- `outputs/` and `data/` are mounted as volumes — artifacts persist across restarts
- Default CMD runs `--mode full`; override with:
  ```bash
  docker-compose run ai_scientist python run_pipeline.py --mode eval --verbose
  ```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: ai_scientist` | Run `pip install -e .` from project root |
| `OpenAI API key not found` | Add `OPENAI_API_KEY=sk-...` to `.env` |
| Qdrant connection refused | Start Qdrant: `docker run -p 6333:6333 qdrant/qdrant` |
| PDF text extraction returns empty sections | Check PDF is text-based (not scanned); use `pdftotext` to verify |
| Judge always returns `"tie"` | Check `ANTHROPIC_API_KEY` is set; inspect `logs/evaluation.log` |
