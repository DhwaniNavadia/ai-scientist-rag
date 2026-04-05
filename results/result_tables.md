# Autonomous AI Scientist — Result Tables

> **Data source:** Mock evaluation results (evaluation_report.json not yet generated).
> Run `python run_pipeline.py --mode eval` to replace mock values with real LLM judge decisions.

---

## Table 1 — Per-Paper Evaluation Metrics

| Paper | Gaps Evaluated | Win Rate ↑ | Avg Score (0–10) ↑ | Keep Rate ↑ | Agent Agreement ↑ |
|-------|:--------------:|:----------:|:-------------------:|:-----------:|:-----------------:|
| paper_1 (HSAP) | 12 | **0.68** | 7.2 | 0.72 | 0.81 |
| paper_2        |  9 | 0.54 | 6.4 | 0.58 | 0.67 |
| paper_3        | 11 | **0.71** | **7.6** | **0.75** | **0.88** |
| **Weighted avg** | **32** | **0.651** | **7.113** | **0.691** | **0.795** |

**Key:** Win Rate = fraction of gaps where system hypothesis was preferred over baseline by LLM judge.
Agent Agreement = fraction of gaps where AgentA and AgentB critic scores agree on ranking direction.

---

## Table 2 — System vs. Baseline Score Comparison

| Paper | System Avg Score | Baseline Avg Score | Delta (pts) | Delta (%) |
|-------|:----------------:|:------------------:|:-----------:|:---------:|
| paper_1 | 7.2 | 5.8 | +1.4 | +24.1% |
| paper_2 | 6.4 | 5.6 | +0.8 | +14.3% |
| paper_3 | 7.6 | 5.8 | +1.8 | +31.0% |
| **Overall** | **7.113** | **5.720** | **+1.393** | **+24.4%** |

Baseline = keyword-only gap framing submitted to the LLM without critic scoring, debate, or reflection.

---

## Table 3 — Win / Loss / Tie Breakdown

| Paper | Gaps | System Wins | Baseline Wins | Ties | System Win% |
|-------|:----:|:-----------:|:-------------:|:----:|:-----------:|
| paper_1 | 12 | 8  | 4 | 0 | 66.7% |
| paper_2 |  9 | 5  | 4 | 0 | 55.6% |
| paper_3 | 11 | 8  | 3 | 0 | 72.7% |
| **Total** | **32** | **21** | **11** | **0** | **65.6%** |

Note: Resolved win rate (65.6%) differs slightly from weighted win rate (65.1%) due to rounding.

---

## Table 4 — Gap Type Distribution (paper_1 actual data)

| Gap Type | Count | Avg AgentA Score | Avg AgentB Score | Preferred Agent |
|----------|:-----:|:----------------:|:----------------:|:---------------:|
| data_quality | 3 | 14.0 | 13.0 | AgentA (3/3) |
| scalability | 3 | 14.0 | 13.0 | AgentA (3/3) |
| human_alignment | 4 | 12.5 | 12.0 | AgentA (4/4) |
| manual_effort | 3 | 11.0 | 11.0 | AgentA (3/3, tie) |
| robustness | 1 | 12.0 | 13.0 | **AgentB (1/1)** |
| problem_formulation | 1 | 10.0 | 10.0 | AgentA (1/1, tie) |
| future_work | 1 | 12.0 | 11.0 | AgentA (1/1) |

AgentB wins on G12 (robustness) — the only gap where ablation reasoning outscored direct repair proposals.

---

## Table 5 — Hypothesis Decision Distribution (paper_1, preferred agent)

| Decision | Count | Percentage |
|----------|:-----:|:----------:|
| KEEP     | 14    | 87.5%      |
| REVISE   |  1    |  6.3%      |
| REJECT   |  1    |  6.3%      |
| **Total** | **16** | **100%** |

---

## Table 6 — Critic Score Breakdown (paper_1, preferred hypotheses)

| Score Category | Min | Max | Mean |
|----------------|:---:|:---:|:----:|
| Clarity (1–5)  | 3   | 5   | 4.4  |
| Novelty (1–5)  | 4   | 5   | 4.9  |
| Feasibility (1–5) | 2 | 4  | 3.3  |
| Total (3–15)   | 10  | 14  | 12.5 |

Novelty is consistently the strongest dimension (near ceiling at 4.9/5); feasibility is the main differentiator between KEEP vs. REVISE/REJECT decisions.

---

## Table 7 — Evaluation Configuration

| Parameter | Value |
|-----------|-------|
| Judge model | `claude-opus-4-5` (Anthropic) / `gpt-4o-mini` (fallback) |
| N runs per gap (n_runs) | 3 |
| Exponential backoff retries | 3 |
| Total comparisons (3 papers) | 96 |
| Baseline type | Keyword-only gap framing |
| Critic rubric dimensions | clarity, novelty, feasibility |
| Score threshold (KEEP) | total ≥ 12 |
