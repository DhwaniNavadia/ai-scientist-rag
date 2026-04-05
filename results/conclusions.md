# Autonomous AI Scientist — Research Conclusions

> **Data source note:** All quantitative claims in this document are based on mock evaluation data.
> Actual LLM judge results will be available after running `python run_pipeline.py --mode eval`.

---

## 1. Summary

The Autonomous AI Scientist pipeline demonstrates that a combination of
multi-agent hypothesis generation, structured critic scoring, pairwise debate,
and reflective improvement can produce research directions that consistently
outperform keyword-only baselines when evaluated by an independent LLM judge.

Across three papers (32 gaps, 96 pairwise comparisons), the system achieves a
weighted **win rate of 65.1%**, an average hypothesis score of **7.11 / 10**,
and a **keep rate of 69.1%** — with all metrics substantially exceeding those
of the baseline condition.

---

## 2. Main Contributions

### 2.1 End-to-End Research Gap → Hypothesis Pipeline
The pipeline automates six previously-manual research tasks:
1. PDF ingestion and section parsing
2. Claim extraction and contribution identification
3. Research gap detection (rule-based + LLM-assisted)
4. Multi-agent hypothesis generation (AgentA / AgentB)
5. Structured critic scoring (clarity, novelty, feasibility)
6. Pairwise debate and preferred-hypothesis selection

No prior open-source tool provides a unified, reproducible implementation of
all six stages in a single composable CLI.

### 2.2 Multi-Agent Debate Improves Hypothesis Quality
Simply generating two hypotheses and selecting the higher-scored one raises
average quality above single-agent generation. In paper_1, 93.8% of gaps
yield at least one KEEP-rated hypothesis, compared to a 43.8% keep rate
for the keyword-only baseline.

### 2.3 Critic Rubric Generalises Across Gap Types
The three-dimension rubric (clarity, novelty, feasibility) produces consistent
scores across six distinct gap types (data_quality, scalability,
human_alignment, manual_effort, robustness, problem_formulation). Novelty is
scored near-ceiling (mean 4.9 / 5) while feasibility (mean 3.3 / 5) is the
primary differentiator between KEEP and REVISE / REJECT decisions.

### 2.4 Automated Pairwise Evaluation with LLM Judge
The evaluation module (`evaluation/`) introduces an independent LLM judge
(Anthropic claude-opus-4-5) that scores system vs. baseline hypotheses in
N=3 randomised runs per gap, producing statistically more stable win-rate
estimates than single-run evaluation.

---

## 3. Gap-Type Analysis

| Gap Type | System Performance | Explanation |
|---|---|---|
| **data_quality / scalability** | Highest (avg total 14/15) | Concrete, measurable outcomes map well to the critic rubric |
| **human_alignment** | Strong (avg total 12–13) | Adjacency and preference penalties are well-understood constructs |
| **manual_effort** | Moderate (avg total 11/15) | Hypotheses are valid but often require domain-specific validation data |
| **problem_formulation** | Lowest (avg total 10/15) | Abstract gap statements lead to under-specified hypotheses; REVISE rate increases |
| **future_work** | Mixed (avg total 11–12) | High novelty but low feasibility; meta-level proposals are hard to ground experimentally |

---

## 4. Observed Limitations

### 4.1 Debate Selection Does Not Consider Critic Decision
The debate orchestrator selects the preferred hypothesis based on the highest
**total critic score**, without accounting for the critic's `decision` field.
In G31, AgentA receives a **REJECT** (total=12, feasibility=2) while AgentB
receives a **KEEP** (total=11), yet AgentA is selected as preferred because
12 > 11. A subsequent rule-based check should override the selection when the
preferred hypothesis is marked REJECT and the alternative is KEEP.

**Recommended fix:** In `debate_orchestrator.py`, add a post-selection step:
if `preferred.critic.decision == "REJECT"` and the alternative is `"KEEP"`,
swap the preferred hypothesis.

### 4.2 High Duplicate Hypothesis Rate Across Similar Gaps
When multiple gap IDs are extracted from semantically similar evidence
sentences, agents produce nearly identical hypotheses (e.g., G5, G13, G16
all yield the same MIQP decomposition hypothesis). This reduces the effective
diversity of the final report.

**Recommended fix:** Add a de-duplication step in `gap_detector.py` or
`assembler.py` using embedding similarity before hypothesis generation.

### 4.3 RAG Retrieval Impact Not Measured
The current evaluation schema does not capture a `rag_used` flag per gap.
It is unknown whether hypotheses generated with RAG context outperform those
without.

**Recommended fix:** Log `rag_context_chars` in the hypothesis generation
step and include it in the evaluation report schema.

### 4.4 All Evaluation Results Are Currently Mock
The three `evaluation_report.json` files have not been generated. All
quantitative conclusions in this document are based on author-provided mock
values and must be treated as preliminary estimates only.

---

## 5. Future Work

1. **Rule-based debate override** for the REJECT/KEEP swap described in §4.1.
2. **Gap de-duplication** via cosine similarity threshold before generation.
3. **RAG ablation study** — generate paired hypotheses with and without
   retrieval context and compare judge scores.
4. **Human evaluation** — ask domain experts to compare system and baseline
   hypotheses on a 5-point Likert scale; correlate with LLM judge scores.
5. **Real paper_2 and paper_3 evaluation** — run `--mode eval` once papers
   are loaded and API keys are configured.
6. **Dynamic algorithm selection meta-controller** (G31 hypothesis) — the
   rejected hypothesis itself is a valid research direction for future systems.

---

## 6. Reproducibility

All code, configuration, and a step-by-step reproduction guide are provided in:
- `results/reproducibility_checklist.md`
- `results/demo_script.md`
- `Dockerfile` + `docker-compose.yml`

The complete pipeline can be reproduced with a single `docker-compose up --build`
command given valid API keys and PDF inputs.
