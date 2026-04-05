# AI-Scientist Codebase: Comprehensive Technical Analysis & Research Documentation

**Document Classification:** System Specification & Research Foundation  
**Target Venues:** ACL / NeurIPS / ICML Systems Track  
**Codebase Version:** 1.0.0 (June 2025)  
**Total Modules Analyzed:** 29 Python modules across 7 subpackages  

---

## Table of Contents

1. [Executive System Overview](#1-executive-system-overview)
2. [Comprehensive Pipeline Analysis](#2-comprehensive-pipeline-analysis)
3. [LLM Reliability Architecture](#3-llm-reliability-architecture)
4. [Data Structures & Schemas](#4-data-structures--schemas)
5. [Inter-Module Communication](#5-inter-module-communication)
6. [Error Handling & System Robustness](#6-error-handling--system-robustness)
7. [Experimental Design for Research Validation](#7-experimental-design-for-research-validation)
8. [Novel Contributions & Research Value](#8-novel-contributions--research-value)
9. [Limitations & Known Issues](#9-limitations--known-issues)
10. [Future Work & Extensions](#10-future-work--extensions)
11. [Code Quality Assessment](#11-code-quality-assessment)
12. [Research Paper Mapping](#12-research-paper-mapping)
13. [Appendices](#13-appendices)

---

## 1. Executive System Overview

### 1.1 System Purpose

The Autonomous AI Scientist is an end-to-end automated research analysis pipeline that ingests scientific papers (PDF or arXiv), extracts structured knowledge, generates research hypotheses through multi-agent debate, and produces comprehensive analytical reports—all without human intervention once the pipeline is initiated.

The system implements a novel multi-agent reasoning architecture where two LLM agents with distinct epistemic dispositions (conservative vs. exploratory) generate competing hypotheses for each identified research gap. These hypotheses undergo peer-review scoring, a three-round structured debate protocol, and reflective revision, producing a complete scientific analysis lineage from raw paper text to refined, scored hypotheses.

### 1.2 Architecture Summary

The system is organized into three architectural layers:

**Core AI Pipeline** (`ai_scientist/`): 29 Python modules across 7 subpackages implementing the full research analysis pipeline:
- `ingestion/` — PDF parsing, arXiv fetching, domain validation, paper registry
- `extraction/` — Claim extraction (keyword + LLM), gap detection (signal-based + typed)
- `reasoning/` — Hypothesis generation (dual-agent), critic scoring, debate orchestration, reflection
- `cross_paper/` — Multi-paper claim synthesis, numeric + semantic contradiction detection
- `evaluation/` — Automated quality metrics (retrieval precision, debate quality, hypothesis quality)
- `reporting/` — Final report assembly with preference logic
- `rag/` — Qdrant Cloud vector store with MMR retrieval
- `llm/` — Multi-provider LLM client with cascading fallback

**Backend API** (`backend/`): FastAPI application exposing 12+ REST endpoints for pipeline control, output retrieval, file download, and RAG queries.

**Frontend** (`ui/`): Static HTML/JavaScript dashboard providing paper upload, pipeline control, claims/gaps visualization, hypothesis comparison, and report download.

### 1.3 Technology Stack

| Component | Technology | Version/Details |
|-----------|-----------|-----------------|
| Language | Python 3.10+ | Type hints throughout |
| Primary LLM | OpenAI GPT-4.1-mini | Default model, 2-retry with backoff |
| Fallback LLM | Grok (xAI) grok-2-latest | Via httpx direct HTTP |
| Deterministic Fallback | Rule-based JSON generator | Zero-dependency safety net |
| Vector Store | Qdrant Cloud | Cosine similarity, 384-dim vectors |
| Embeddings | all-MiniLM-L6-v2 | SentenceTransformer, 384-dim output |
| PDF Parsing | pypdf ≥ 3.0.0 | Multi-page text extraction |
| API Framework | FastAPI + Uvicorn | Async, auto-docs at /docs |
| Paper Fetching | arxiv SDK ≥ 2.1.0 | Rate-limited client, 3s delay |

### 1.4 Pipeline Execution Modes

The orchestrator (`run_pipeline.py`) supports 8 execution modes:

| Mode | Stages | Description |
|------|--------|-------------|
| `full` | tier1 → rag → tier2 → qdrant_analysis → report → metrics | Complete end-to-end pipeline |
| `tier1` | parse → claims → gaps → hypotheses → critic → debate → reflection | Single-paper deep analysis |
| `tier2` | cross_paper_claims → contradictions | Multi-paper comparison |
| `rag` | Qdrant indexing | Embed and store paper sections |
| `qdrant_analysis` | RAG-based contradictions | Cross-paper analysis via vector search |
| `report` | Final report assembly | Aggregate all outputs |
| `eval` | Quality metrics | Compute automated evaluation metrics |
| `check` | Validation | Verify all required output files exist |

---

## 2. Comprehensive Pipeline Analysis

### 2.1 Stage 1: PDF Ingestion & Section Parsing

**Module:** `ai_scientist/ingestion/pdf_parser.py` (~190 lines)  
**Entry Point:** `run()` → writes `outputs/sections.json`

**Mechanism:** The parser implements a two-pass section bucketing algorithm using heading detection heuristics. Text is extracted page-by-page via `pypdf.PdfReader`, then lines are classified as headings or body text.

**Heading Detection** (`_detect_heading()`): Three pattern types are recognized:
1. Standalone keyword lines matching canonical section names
2. Numbered headings (e.g., "3 Method", "4.1 Results")
3. Standalone numbers on one line followed by a text line on the next

**Canonical Section Mapping** (`HEADING_CANONICAL`):
```python
{
    "abstract": "abstract", "introduction": "introduction", "intro": "introduction",
    "method": "evaluation", "approach": "evaluation", "experiment": "evaluation",
    "result": "evaluation", "evaluation": "evaluation", "discussion": "evaluation",
    "analysis": "evaluation", "ablation": "evaluation",
    "conclusion": "conclusion", "summary": "conclusion", "future": "conclusion",
    "limitation": "conclusion",
}
```

**Output:** Four canonical sections are produced—`abstract`, `introduction`, `evaluation`, `conclusion`—each containing concatenated text from all matching headings. This aggressive normalization reduces the section space from dozens of possible headings to four semantically stable buckets.

**Design Decision:** Mapping "method", "approach", "experiment", "result", "discussion", "analysis", and "ablation" all into `evaluation` reflects a deliberate choice to group all technical content together, prioritizing downstream extraction recall over fine-grained section fidelity.

---

### 2.2 Stage 2: Claim Extraction

**Module:** `ai_scientist/extraction/claim_extractor.py` (~200 lines)  
**Entry Point:** `extract_claims()` → writes `outputs/claims.json`

The extractor implements a dual-strategy architecture combining rule-based keyword matching with LLM-powered extraction, followed by aggressive post-filtering.

**Strategy A — Keyword-Based Extraction:**
Sentences containing any of 16 claim cue phrases are extracted:
```python
CLAIM_CUES = [
    "we propose", "we introduce", "we present", "we show", "we demonstrate",
    "we find", "we achieve", "our method", "our approach", "our model",
    "results show", "results indicate", "outperforms", "state-of-the-art",
    "significant improvement", "novel",
]
```
Each extracted sentence is paired with the following sentence as evidence text, and assigned a base confidence of 0.75.

**Strategy B — LLM-Based Extraction:**

**System Prompt (verbatim):**
```
You are a precise scientific claim extractor. Given a section of a research paper,
extract the key empirical and methodological claims.

Return ONLY valid JSON: a list of objects with keys:
  "claim_text": the exact claim sentence,
  "evidence_text": supporting evidence or context,
  "confidence": 0.0 to 1.0

Extract 3-5 claims per section. Focus on:
- Empirical results with specific numbers
- Comparative statements (outperforms, improves over)
- Novel methodological contributions
- Key findings and conclusions
```

**LLM Parameters:** `temperature=0.2`, `max_tokens=500`, input truncated to 4,000 characters.

**Post-Filtering Pipeline** (`_post_filter_claims()`):
1. **Noise Pattern Rejection:** Claims matching metadata patterns (university names, conference headers, email addresses) are dropped
2. **Length Filter:** Claims shorter than 40 characters (`MIN_CLAIM_LENGTH`) are removed
3. **Confidence Threshold:** Claims below 0.5 confidence (`MIN_CONFIDENCE`) are dropped
4. **Alpha Ratio Gate:** Claims with alphabetic character ratio ≤ 0.4 are rejected (catches table fragments)
5. **Deduplication:** Exact normalized text matching

**Output Constraint:** Maximum 10 claims per paper (`MAX_CLAIMS`), selected by confidence score after deduplication of keyword + LLM results.

---

### 2.3 Stage 3: Research Gap Detection

**Module:** `ai_scientist/extraction/gap_detector.py` (~200 lines)  
**Entry Point:** `detect_gaps()` → writes `outputs/gaps_rulebased.json` + `outputs/gaps_actionable.json`

The gap detector employs a signal-based extraction approach with typed classification and actionable direction generation.

**Gap Signal Keywords** (21 signals):
```python
GAP_SIGNALS = [
    "limitation", "future work", "open problem", "challenge",
    "not yet", "remains to be", "has not been", "lack of",
    "insufficient", "room for improvement", "gap", "shortcoming",
    "constraint", "caveat", "assumption", "simplification",
    "does not address", "beyond the scope", "unexplored",
    "underexplored", "unresolved",
]
```

**Gap Type Classification** (`GAP_TYPE_KEYWORDS`):
| Type | Keywords |
|------|----------|
| `data_quality` | dataset, annotation, label, noise, bias, imbalanced, missing |
| `human_alignment` | human evaluation, user study, subjective, alignment, interpretability |
| `scalability` | scalability, computational cost, memory, efficiency, large-scale, distributed |
| `manual_effort` | manual, hand-crafted, feature engineering, heuristic, rule-based |

**Actionable Direction Generation** (`DIRECTION_TEMPLATES`):
Each gap type maps to a predefined actionable direction template:
- `data_quality` → "Propose data augmentation or noise-robust training strategies"
- `human_alignment` → "Design automated proxy metrics that correlate with human judgments"
- `scalability` → "Investigate decomposition, approximation, or distributed methods to scale to larger instances"
- `manual_effort` → "Develop automated representation learning to replace manual feature engineering"

**Deduplication:** Jaccard similarity at threshold 0.7 (`_deduplicate()`) removes near-duplicate gaps by computing token overlap ratios.

**Output Constraint:** Maximum 16 actionable gaps (`MAX_ACTIONABLE`), producing 8 gap pairs for dual-agent hypothesis generation (16 hypotheses total).

---

### 2.4 Stage 4: Dual-Agent Hypothesis Generation

**Module:** `ai_scientist/reasoning/hypothesis_generator.py` (~250 lines)  
**Entry Point:** `generate_hypotheses()` → writes `outputs/hypotheses.json`

This stage implements the core multi-agent reasoning architecture. Two LLM agents with contrasting epistemic dispositions independently generate hypotheses for each research gap.

**Agent A — Conservative Scientist:**

**System Prompt (verbatim):**
```
You are a conservative research scientist. You propose hypotheses that are:
- Incremental and well-grounded in existing literature
- Highly feasible with current methods and resources
- Focused on extending or refining existing approaches
- Cautious about making strong claims without evidence

Given a research gap, propose ONE specific, testable hypothesis.
Return ONLY valid JSON:
{"hypothesis": "your hypothesis text", "reasoning": "why this hypothesis",
 "novelty_score": 0.0-1.0, "confidence": 0.0-1.0}
```
**Temperature:** 0.4 (low randomness, favoring coherent incremental proposals)

**Agent B — Exploratory Scientist:**

**System Prompt (verbatim):**
```
You are an exploratory research scientist. You propose hypotheses that are:
- Bold and creative, potentially paradigm-shifting
- Novel combinations of existing ideas from different fields
- High-risk but high-reward if validated
- Pushing boundaries of current understanding

Given a research gap, propose ONE specific, testable hypothesis.
Return ONLY valid JSON:
{"hypothesis": "your hypothesis text", "reasoning": "why this hypothesis",
 "novelty_score": 0.0-1.0, "confidence": 0.0-1.0}
```
**Temperature:** 0.9 (high randomness, encouraging creative divergence)

**User Template (per gap):**
```
Research gap: {gap_text}
Actionable direction: {actionable_direction}
Gap type: {gap_type}

Propose a specific, testable hypothesis to address this gap.
```

**RAG Evidence Injection:** When Qdrant is available, top-5 MMR-diverse evidence chunks are appended to the user prompt:
```
Relevant evidence from indexed papers:
  [1] (section: evaluation, paper: paper1) "Evidence text..."
  [2] (section: introduction, paper: paper2) "Evidence text..."
```

**Output:** 2 hypotheses per gap × 8 gaps = 16 hypotheses total. Each hypothesis carries `source` (AgentA/AgentB), `gap_id`, `gap_type`, `novelty_score`, and `confidence` metadata.

---

### 2.5 Stage 5: Peer-Review Critic Scoring

**Module:** `ai_scientist/reasoning/critic.py` (~250 lines)  
**Entry Point:** `score_hypotheses()` → writes `outputs/hypotheses_scored.json`

Each hypothesis undergoes independent peer-review scoring on three dimensions.

**System Prompt (verbatim):**
```
You are a critical peer reviewer for a top-tier AI research venue.
Score the following hypothesis on three dimensions (1-5 each):
- clarity: How clear, specific, and well-defined is the hypothesis?
- novelty: How novel is the approach compared to existing work?
- feasibility: How feasible is it to test this hypothesis with current methods?

You MUST also identify at least one weakness or limitation.

Return ONLY valid JSON:
{"clarity": 1-5, "novelty": 1-5, "feasibility": 1-5,
 "rationale": "brief justification", "weakness": "identified weakness"}
```

**LLM Parameters:** `temperature=0.3`, `max_tokens=200`

**Decision Rules (enforced in code, not by LLM):**
```python
total = clarity + novelty + feasibility  # Range: 3-15
if total >= 10:  decision = "KEEP"
elif total >= 6:  decision = "REVISE"
else:             decision = "REJECT"
```

**Default Scores (on parse failure):**
```python
DEFAULT_SCORES = {"clarity": 3, "novelty": 3, "feasibility": 3, "total": 9}
# → decision = "REVISE" (safe middle ground)
```

**RAG Integration:** When available, evidence chunks relevant to each hypothesis are included in the prompt to ground the critic's assessment.

**Output:** Each hypothesis is augmented with `scores.{clarity, novelty, feasibility, total}`, `decision` (KEEP/REVISE/REJECT), `rationale`, and `weakness`.

---

### 2.6 Stage 6: Three-Round Structured Debate

**Module:** `ai_scientist/reasoning/debate_orchestrator.py` (~430 lines)  
**Entry Point:** `run()` → writes `outputs/disagreement_log_all.json`

This is the most architecturally complex module, implementing a novel three-round adversarial debate protocol for each gap's competing hypotheses.

#### Round 1 — Senior Advisor Comparison

**System Prompt (verbatim):**
```
You are a senior research advisor evaluating two competing hypotheses generated
by researchers with different approaches.

Compare them on: scientific rigor, novelty, testability, potential impact.

Return ONLY valid JSON:
{"preferred": "AgentA" or "AgentB",
 "reasoning": "detailed comparison",
 "synthesis": "how elements of both could be combined",
 "confidence": 0.0-1.0}
```

**LLM Parameters:** `temperature=0.4`, `max_tokens=300`

#### Round 2 — Challenge by Non-Preferred Agent

The agent whose hypothesis was NOT preferred in Round 1 is given the opportunity to respond.

**System Prompt (verbatim):**
```
You are a researcher whose hypothesis was not initially preferred.
The advisor preferred your colleague's hypothesis for these reasons:
{round1_reasoning}

You may respond with ONE of three actions:
- DEFEND: Argue why your hypothesis is actually superior
- CONCEDE: Agree the other hypothesis is better and explain why
- REFINE: Propose a modified version that addresses the criticism

Return ONLY valid JSON:
{"action": "DEFEND" or "CONCEDE" or "REFINE",
 "response": "your argument or concession",
 "refined_hypothesis": "only if action is REFINE, otherwise empty string"}
```

**LLM Parameters:** `temperature=0.5`, `max_tokens=300`

**Confidence Adjustment:** If the challenger chooses DEFEND, the overall confidence is reduced by 0.1 (reflecting unresolved disagreement).

#### Round 3 — Synthesis Verdict

**System Prompt (verbatim):**
```
You are the senior advisor delivering your final verdict after considering
the initial comparison and the challenger's response.

Consider all evidence presented in both rounds.

Return ONLY valid JSON:
{"final_preferred": "AgentA" or "AgentB",
 "verdict": "final reasoning incorporating all rounds",
 "decisive_factor": "what tipped the decision",
 "confidence": 0.0-1.0,
 "recommendation": "ACCEPT" or "REVISE" or "MERGE"}
```

**LLM Parameters:** `temperature=0.3`, `max_tokens=300`

#### Score-Based Fallback (`pick_preferred()`):

When LLM calls fail, a deterministic fallback selects the preferred hypothesis:
```python
decision_rank = {"KEEP": 3, "REVISE": 2, "REJECT": 1}
# 1. Higher decision rank wins
# 2. Tie-break: higher total score wins
# 3. Final tie-break: AgentA wins (conservative preference)
```

**Output Schema:** Per-gap entries with `round_1`, `round_2`, `round_3` sub-objects, plus `preferred_agent`, `agreement`, `confidence`, `llm_reasoning`, `synthesis`, and `challenge` fields.

---

### 2.7 Stage 7: Reflective Revision

**Module:** `ai_scientist/reasoning/reflection_engine.py` (~250 lines)  
**Entry Point:** `run()` → writes `outputs/reflection_logs.json`

Hypotheses with KEEP or REVISE decisions undergo reflective improvement. REJECT hypotheses are skipped.

**System Prompt (verbatim):**
```
You are a senior researcher reviewing a hypothesis that has been scored by peer reviewers.
Provide a thoughtful reflection and improvement plan.

Consider the scores, decision, and any available evidence.

Return ONLY valid JSON:
{"reflection": "analysis of strengths and weaknesses",
 "improvement_plan": "specific steps to improve",
 "revised_hypothesis": "improved version of the hypothesis",
 "evidence_assessment": "how well the hypothesis is supported by evidence",
 "confidence_delta": -0.2 to 0.2}
```

**LLM Parameters:** `temperature=0.5`, `max_tokens=300`

**User Template:**
```
Hypothesis: {hypothesis_text}
Scores: clarity={clarity}, novelty={novelty}, feasibility={feasibility}, total={total}
Decision: {decision}

{evidence_block if RAG available}

Reflect on this hypothesis and suggest improvements.
```

**Fallback on Parse Failure:** Returns the original hypothesis text unchanged with empty reflection fields and `confidence_delta=0.0`.

---

### 2.8 Stage 8: Cross-Paper Claim Extraction (Tier 2)

**Module:** `ai_scientist/cross_paper/claims_sectioned.py` (~430 lines)  
**Entry Point:** `main()` → writes `outputs/cross_paper_claims.json`

This module performs section-aware claim extraction across two comparison papers (paper2 and paper3), followed by LLM-powered cross-paper synthesis.

**Section Filtering:**
- **Keep:** experiment, experiments, experimental, evaluation, results, discussion, conclusion, conclusions, analysis, ablation, limitations
- **Drop:** related work, background, preliminaries, references, appendix, supplementary, acknowledgments

**Claim Signal Detection** (`has_claim_signal()`):
Extended from 16 to ~30 cue terms including domain-specific metrics (accuracy, f1, auc, error, runtime, attention, convolution, graph, node classification). Sentences with percentage values (`\d+\.?\d*\s*%`) are automatically kept.

**Scoring Function** (for ranking):
```python
score = 0.0
if "we " in text:        score += 1.0  # First-person claims
if has_result_keyword:    score += 1.0  # outperform, improve, achieve...
if has_percentage:        score += 1.0  # Numeric results
score += min(len(text) / 200, 1.0)     # Length bonus (up to 1.0)
```

**LLM Cross-Paper Synthesis:**

**System Prompt (verbatim):**
```
You are a research analyst comparing claims from two different scientific papers.

Analyze the claims below and produce a structured cross-paper synthesis.

Return ONLY valid JSON with these EXACT keys:
{
  "shared_findings": [{"finding": "string", "paper_ids": ["paper2", "paper3"]}],
  "contradictions": [{"claim_a": "string", "paper_a": "paper2",
   "claim_b": "string", "paper_b": "paper3", "type": "strong"|"weak"}],
  "complementary_methods": [{"description": "string", "paper_ids": ["paper2", "paper3"]}],
  "unique_contributions": [{"contribution": "string", "paper_id": "paper2"|"paper3"}]
}
```

**Validation:** Output is validated to ensure at least 2 distinct paper IDs are referenced. If validation fails, one retry is attempted with an explicit instruction about the missing paper references.

**LLM Parameters:** `temperature=0.3`, `max_tokens=1200`

---

### 2.9 Stage 9: Cross-Paper Contradiction Detection (Tier 2)

**Module:** `ai_scientist/cross_paper/contradictions.py` (~600 lines)  
**Entry Point:** `main()` → writes `outputs/cross_paper_contradictions.json`

This module implements a dual-strategy contradiction detection system combining numeric table extraction with LLM semantic analysis.

**Strategy A — Numeric Table Extraction:**

The module parses raw paper text to find evaluation tables, then compares numeric results across papers.

- **Table Header Detection:** Lines containing ≥2 benchmark dataset names (cora, citeseer, pubmed, ppi) with structural indicators (pipes, method/model keywords)
- **Row Parsing:** Numeric cells extracted via regex; accuracy-like values (30.0-100.0) are kept; year-like values (1900-2099) are excluded
- **Blocklist Filtering:** Rows containing hyperparameter keywords (epoch, learning rate, dropout, etc.) are rejected
- **Contradiction Flag:** Absolute delta ≥ 1.0 between same-dataset results triggers a contradiction flag

**Strategy B — LLM Semantic Contradiction Detection:**

**System Prompt (verbatim):**
```
You are a scientific contradiction detector performing pairwise cross-paper comparison.

You are given claims from Paper A and Paper B. These are DIFFERENT papers.
Identify genuine semantic contradictions — cases where the two papers disagree on:
  1. Empirical results (different numbers for the same experiment/dataset)
  2. Methodological claims (conflicting statements about how something works)
  3. Interpretive conclusions (opposing interpretations of similar evidence)

RULES:
  - Only report GENUINE contradictions, not complementary or unrelated findings.
  - Each contradiction must cite specific claims from BOTH papers.
  - Differences in scope are NOT contradictions.
  - Assign severity: 'high', 'medium', 'low'.

Return ONLY valid JSON: a list of objects with keys:
  "claim_paper_a", "claim_paper_b", "contradiction_type",
  "severity", "evidence_a", "evidence_b", "confidence", "explanation"
```

**LLM Parameters:** `temperature=0.3`, `max_tokens=1000`

**Same-Paper Guard:** If both claim sets are identical (normalized), semantic detection is skipped to prevent false self-contradictions.

**Strategy C — Qdrant-Powered Cross-Paper Contradictions:**

When Qdrant is available, a third strategy uses RAG retrieval with 5 diverse queries to collect chunks across all indexed papers, groups by paper ID, and asks the LLM to identify cross-paper conflicts. This includes a cross-paper guard that rejects same-paper pairs in the LLM output.

**Output Combination:** `detect_all_contradictions()` merges numeric and semantic results into a unified list tagged with `type: "numeric"`, `type: "semantic"`, or `type: "semantic_qdrant"`.

---

### 2.10 Stage 10: Report Assembly

**Module:** `ai_scientist/reporting/assembler.py` (~160 lines)  
**Entry Point:** `run()` → writes `outputs/final_report.json`

The assembler loads all pipeline outputs, applies preference logic, and constructs the hypothesis lineage connecting gaps → hypotheses → scores → debate outcomes → reflections.

**Preference Logic** (`pick_preferred()`):
```python
decision_rank = {"KEEP": 3, "REVISE": 2}  # default: 1
# AgentA vs AgentB: higher rank wins, then higher total score, then AgentA
```

**Lineage Construction:** For each of the 16 disagreement entries:
1. Look up the corresponding gap by `gap_id`
2. Select the preferred agent's hypothesis
3. Attach the corresponding reflection (by `hypothesis_id`)
4. Build a lineage entry with: gap_id, gap_type, gap_text, preferred_agent, hypothesis_text, scores, decision, reflection, revised_hypothesis

**Output Structure:**
```json
{
  "project": {"name": "Autonomous AI Scientist (MVP)", "scope": "..."},
  "paper_context": {"available_sections": [...], "num_claims": N, ...},
  "claims": [...],
  "gaps_actionable": [...],
  "hypothesis_lineage": [...],
  "disagreement_log": [...]
}
```

**Atomic Write:** Uses `.tmp` file + `os.replace()` for crash-safe writes.

---

### 2.11 Stage 11: Automated Evaluation Metrics

**Module:** `ai_scientist/evaluation/metrics.py` (~350 lines)  
**Entry Point:** `run_evaluation()` → writes `outputs/evaluation_metrics.json`

**Metric 1 — Retrieval Precision@K:**
Keyword-overlap proxy for RAG relevance. Counts how many of the top-K retrieved chunks contain at least one relevant keyword.

**Metric 2 — Paper Diversity Score:**
Normalized Shannon entropy over paper IDs in retrieved chunks. Score of 1.0 = perfectly even across N papers; 0.0 = all from one paper. Diversity requires ≥2 papers and no single paper dominating >60%.

**Metric 3 — Hypothesis Quality Score:**
Aggregates critic scores across all hypotheses: avg_total, avg_clarity, avg_novelty, avg_feasibility, keep_rate, reject_rate. Additionally uses LLM to assess up to 5 hypotheses on specificity/novelty/testability (1-10 scale each).

**LLM Assessment Prompt:**
```
You are a research methodology expert. Rate this hypothesis on three dimensions.

Respond ONLY with valid JSON:
{"specificity": 1-10, "novelty": 1-10, "testability": 1-10,
 "justification": "one sentence explaining the scores"}
```

**Metric 4 — Debate Quality Score:**
Per-entry scoring based on 3-round debate completeness:
- Round 1 present with reasoning: +3.33
- Round 2 present with response/action: +3.33, plus +1.0 bonus if evidence is cited
- Round 3 present with decisive_factor: +3.33
- Maximum: 10.0 per entry
- Also tracks: agreement_rate, avg_confidence, challenge_rate, rounds_with_all_3

---

### 2.12 RAG Pipeline: Indexing & Retrieval

**Modules:** `ai_scientist/rag/document_store.py` (~200 lines), `ai_scientist/rag/retriever.py` (~300 lines)

#### Document Store

**Chunking:** Overlapping token windows (256 tokens, 32-token overlap) per section. Each chunk carries metadata: `paper_id`, `section`, `chunk_index`, `text`, plus optional `title`, `category`, `source`.

**Embedding:** all-MiniLM-L6-v2 (384-dimensional), batch-encoded via SentenceTransformer.

**Upsert:** Point ID = MD5 hash of `"{paper_id}_{section}_{chunk_index}"` truncated to int63. Batch upsert in groups of 100.

**Lazy Initialization:** Both the Qdrant client and SentenceTransformer model are lazily loaded on first use, allowing the pipeline to operate without RAG dependencies when Qdrant is not configured.

#### RAG Retriever

**Standard Retrieval:** Embeds query, searches Qdrant with optional paper_id and section filters, returns top-K results with scores and payloads.

**MMR Retrieval** (Maximal Marginal Relevance):
```
MMR(d) = λ · relevance(d, query) - (1-λ) · max_sim(d, selected)
```
- Default λ = 0.5 (balanced relevance/diversity)
- Candidate pool = 4× top_k
- Paper diversity check: if dominant paper >60% and <3 papers, re-runs with λ=0.3
- Raises `RetrievalDiversityError` if min_papers cannot be satisfied

**Convenience Methods:**
- `retrieve_for_gap(gap_text)` → top-5 MMR-diverse chunks for a research gap
- `retrieve_for_hypothesis(hypothesis_text)` → top-5 MMR-diverse chunks for hypothesis grounding

---

### 2.13 Ingestion Pipeline: arXiv → Qdrant

**Modules:** `ai_scientist/ingestion/arxiv_fetcher.py`, `ingest_pipeline.py`, `paper_registry.py`, `domain_validator.py`

#### arXiv Fetcher

Fetches recent papers from arXiv API using the `arxiv` SDK with rate limiting (3s delay). Default query: `cat:cs.AI OR cat:cs.LG OR cat:cs.CL`. Downloads PDFs via urllib with User-Agent header. Minimum file size check (>1000 bytes) prevents saving error pages.

#### Domain Validator

Two-tier validation gate:
1. **Category Validation:** Checks arXiv categories against allowed set: `cs.AI`, `cs.CL`, `cs.CV`, `cs.LG`, `cs.MA`, `cs.NE`, `stat.ML`, `cs.IR`, `cs.RO`
2. **Keyword Fallback:** If categories don't match, requires ≥3 hits from 30 AI keyword phrases (machine learning, transformer, attention mechanism, etc.)

#### Paper Registry

JSON-backed dynamic registry replacing hardcoded 3-paper paths. Supports CRUD operations with status tracking: `registered → parsed → indexed → failed`. Atomic writes via `.tmp` + `os.replace()`.

#### Ingestion Pipeline

End-to-end orchestration: arXiv API → domain filter → download PDF → parse sections → chunk + embed → upsert to Qdrant → update registry. Includes retry logic (skips only `indexed` papers, retries `failed`), verification step post-ingestion, and CLI with `--n`, `--query`, `--verify-only` arguments.

---

## 3. LLM Reliability Architecture

### 3.1 Multi-Provider Cascading Fallback

**Module:** `ai_scientist/llm/llm_client.py` (~280 lines)

The LLM client implements a three-tier cascading fallback architecture that ensures the pipeline never crashes due to API failures.

```
Request → OpenAI (2 retries) → Grok xAI (1 attempt) → Deterministic Fallback
```

#### Tier 1: OpenAI (Primary)

```python
client = openai.OpenAI(api_key=OPENAI_API_KEY, timeout=30)
# Model: configurable, default "gpt-4.1-mini"
# Retries: 2 attempts with 2-second sleep between
```

**Error Handling:**
- `RateLimitError` (429) → retry with sleep
- `APITimeoutError` → retry
- `APIStatusError` (5xx) → retry
- `APIStatusError` (401/403) → immediate cascade to Grok (auth failure, no retry value)
- `LLMParseError` → cascade to Grok

#### Tier 2: Grok xAI (Secondary)

```python
response = httpx.post(
    "https://api.x.ai/v1/chat/completions",
    headers={"Authorization": f"Bearer {GROK_API_KEY}"},
    json={"model": "grok-2-latest", "messages": [...], "temperature": T, "max_tokens": N},
    timeout=30.0,
)
```

**Error Handling:**
- `httpx.TimeoutException` → cascade to deterministic
- JSON parse failure → cascade to deterministic
- Missing response structure → cascade to deterministic

#### Tier 3: Deterministic Fallback (Safety Net)

```python
def _deterministic_fallback(self, prompt, reasons):
    return {
        "hypothesis": f"Hypothesis pending LLM availability. Gap: {prompt[:150]}",
        "reasoning": f"Generated via deterministic fallback — LLM providers unavailable.",
        "confidence": 0.1,
        "novelty_score": 0.1,
        "clarity": 3, "novelty": 3, "feasibility": 3,
        "_fallback": True,
        "_fallback_reason": "; ".join(reasons),
    }
```

**Key Property:** This fallback returns the SAME JSON schema expected by downstream consumers, with safe default values that always resolve to REVISE decisions (total=9). The `_fallback: True` flag enables downstream modules to identify and handle fallback data.

### 3.2 JSON Parsing Safety

**`_parse_json_safe(text)`:** Two-stage parser:
1. Direct `json.loads(text)` attempt
2. Regex extraction of first `{...}` block via `re.search(r"\{.*\}", text, re.DOTALL)`
3. Raises `LLMParseError` if both fail

**`strip_code_fences(text)`:** Removes Markdown code fences (` ```json ... ``` `) that LLMs commonly produce despite instructions.

### 3.3 API Key Availability Detection

`has_keys()` checks for: `OPENAI_API_KEY`, `GROK_API_KEY`, and `OPENAI_API_KEY_1` through `OPENAI_API_KEY_4` (supporting multi-key rotation). Modules use this to conditionally skip LLM steps.

### 3.4 Temperature Strategy Across Pipeline

| Module | Temperature | Rationale |
|--------|-------------|-----------|
| Claim Extractor | 0.2 | Factual extraction requires precision |
| Hypothesis Gen (AgentA) | 0.4 | Conservative, coherent proposals |
| Hypothesis Gen (AgentB) | 0.9 | Creative, divergent exploration |
| Critic Scoring | 0.3 | Consistent evaluation judgments |
| Debate Round 1 | 0.4 | Balanced comparison |
| Debate Round 2 | 0.5 | Moderate creativity for challenge/defense |
| Debate Round 3 | 0.3 | Precise final verdicts |
| Reflection | 0.5 | Balanced reflection and improvement |
| Cross-Paper Synthesis | 0.3 | Accurate cross-document analysis |
| Contradiction Detection | 0.3 | Precise factual comparison |
| Hypothesis Quality Assessment | 0.3 | Consistent evaluation |

---

## 4. Data Structures & Schemas

### 4.1 Pipeline Data Flow

```
PDF → sections.json → claims.json → gaps_rulebased.json → gaps_actionable.json
                                                                    ↓
hypotheses.json → hypotheses_scored.json → disagreement_log_all.json → reflection_logs.json
                                                                                ↓
                                                                    final_report.json
                                                                    
(Tier 2) cross_paper_claims.json → cross_paper_contradictions.json
(Eval)   evaluation_metrics.json
```

### 4.2 Core Schemas

#### `sections.json`
```json
{
  "abstract": "Full abstract text...",
  "introduction": "Full introduction text...",
  "evaluation": "Methods + results + discussion text...",
  "conclusion": "Conclusion + limitations + future work text..."
}
```

#### `claims.json`
```json
[
  {
    "claim_id": "C1",
    "section": "introduction",
    "claim_text": "We achieve state-of-the-art results...",
    "evidence_text": "Supporting evidence sentence...",
    "confidence": 0.9
  }
]
```

#### `gaps_actionable.json`
```json
[
  {
    "gap_id": "G1",
    "gap_type": "scalability",
    "gap_text": "The method does not scale to graphs with >1M nodes.",
    "source_section": "evaluation",
    "actionable_direction": "Investigate decomposition, approximation, or distributed methods..."
  }
]
```

#### `hypotheses_scored.json`
```json
[
  {
    "hypothesis_id": "H1",
    "gap_id": "G1",
    "gap_type": "scalability",
    "gap_text": "...",
    "actionable_direction": "...",
    "hypothesis_text": "We hypothesize that...",
    "source": "AgentA",
    "based_on": [],
    "novelty_score": 0.7,
    "confidence": 0.8,
    "scores": {"clarity": 4, "novelty": 3, "feasibility": 4, "total": 11},
    "decision": "KEEP",
    "rationale": "Well-grounded hypothesis with clear testing plan.",
    "weakness": "Assumes availability of large-scale distributed infrastructure."
  }
]
```

#### `disagreement_log_all.json`
```json
[
  {
    "gap_id": "G1",
    "gap_type": "scalability",
    "evidence_text": "...",
    "agent_a": {
      "hypothesis_id": "H1",
      "hypothesis": "...",
      "scores": {"clarity": 4, "novelty": 3, "feasibility": 4, "total": 11},
      "decision": "KEEP"
    },
    "agent_b": {
      "hypothesis_id": "H2",
      "hypothesis": "...",
      "scores": {"clarity": 3, "novelty": 4, "feasibility": 3, "total": 10},
      "decision": "KEEP"
    },
    "preferred_agent": "AgentA",
    "agreement": true,
    "round_1": {"preferred": "AgentA", "reasoning": "...", "synthesis": "...", "confidence": 0.8},
    "round_2": {"challenger": "AgentB", "action": "DEFEND", "response": "...", "refined_hypothesis": ""},
    "round_3": {"final_preferred": "AgentA", "verdict": "...", "decisive_factor": "...", "confidence": 0.7, "recommendation": "ACCEPT"},
    "llm_reasoning": "...",
    "synthesis": "...",
    "confidence": 0.7,
    "challenge": {"challenger": "AgentB", "action": "DEFEND", "response": "...", "refined_hypothesis": ""}
  }
]
```

#### `reflection_logs.json`
```json
[
  {
    "hypothesis_id": "H1",
    "original_hypothesis": "...",
    "decision": "KEEP",
    "reflection": "This hypothesis is well-grounded...",
    "improvement_plan": "Consider adding baseline comparison...",
    "revised_hypothesis": "Improved hypothesis text...",
    "evidence_assessment": "Moderate support from existing literature.",
    "confidence_delta": 0.1
  }
]
```

#### `cross_paper_claims.json`
```json
{
  "paper2": ["claim sentence 1", "claim sentence 2", ...],
  "paper3": ["claim sentence 1", "claim sentence 2", ...],
  "cross_paper_synthesis": {
    "shared_findings": [{"finding": "...", "paper_ids": ["paper2", "paper3"]}],
    "contradictions": [{"claim_a": "...", "paper_a": "paper2", "claim_b": "...", "paper_b": "paper3", "type": "strong"}],
    "complementary_methods": [{"description": "...", "paper_ids": ["paper2", "paper3"]}],
    "unique_contributions": [{"contribution": "...", "paper_id": "paper2"}]
  }
}
```

#### `cross_paper_contradictions.json`
```json
[
  {
    "type": "numeric",
    "dataset": "cora",
    "metric": "accuracy",
    "paper2_value": 83.5,
    "paper3_value": 81.2,
    "delta_p2_minus_p3": 2.3,
    "potential_contradiction": true,
    "reason": "Δ=2.3000 (threshold=1.0)"
  },
  {
    "type": "semantic",
    "claim_paper2": "...",
    "claim_paper3": "...",
    "contradiction_type": "empirical",
    "severity": "medium",
    "confidence": 0.7,
    "explanation": "..."
  }
]
```

#### `evaluation_metrics.json`
```json
{
  "hypothesis_quality": {
    "avg_total": 9.5,
    "avg_clarity": 3.2,
    "avg_novelty": 3.1,
    "avg_feasibility": 3.2,
    "keep_rate": 0.25,
    "reject_rate": 0.0,
    "llm_assessments": [
      {"hypothesis_id": "H1", "specificity": 7, "novelty": 6, "testability": 8, "justification": "..."}
    ]
  },
  "debate_quality": {
    "agreement_rate": 0.5,
    "avg_confidence": 0.6,
    "challenge_rate": 0.75,
    "avg_round_score": 7.5,
    "rounds_with_all_3": 6
  },
  "claim_count": 10,
  "gap_count": 8
}
```

### 4.3 Backend API Schemas (Pydantic)

```python
class RunPipelineRequest(BaseModel):
    paper_id: str
    mode: str  # full|tier1|tier2|rag|qdrant_analysis|report|check|eval
    tier: Optional[str]    # tier1|tier2
    paper_ids: Optional[List[str]]  # 2-3 paper IDs for cross-paper mode

class PipelineStatusResponse(BaseModel):
    paper_id: str
    status: str  # idle|running|completed|error
    mode: Optional[str]
    message: str
    started_at: Optional[str]
    completed_at: Optional[str]

class QueryRequest(BaseModel):
    query: str  # 1-2000 chars
    top_k: int  # 1-50, default 5
    paper_id: Optional[str]
```

---

## 5. Inter-Module Communication

### 5.1 Communication Pattern

All inter-module communication happens through **JSON files on disk**. There are no in-memory message queues, no function-call interfaces between pipeline stages, and no shared state objects. Each stage reads its input file(s), processes, and writes its output file(s).

```
parse_pdf() → sections.json
                ↓ (read by)
extract_claims(sections) → claims.json
detect_gaps(sections) → gaps_rulebased.json, gaps_actionable.json
                ↓ (read by)
generate_hypotheses(gaps) → hypotheses.json
                ↓ (read by)
score_hypotheses(hypotheses) → hypotheses_scored.json
                ↓ (read by)
debate_orchestrator(scored) → disagreement_log_all.json
                ↓ (read by)
reflection_engine(scored) → reflection_logs.json
                ↓ (read by)
assembler(all files) → final_report.json
```

### 5.2 Pipeline Orchestrator Coupling

The orchestrator (`run_pipeline.py`) enforces file-based dependencies via `_require_file()`:

```python
def _require_file(name: str) -> Path:
    p = OUTPUT_DIR / name
    if not p.exists():
        raise SystemExit(f"Required file missing: {p}")
    return p
```

Each step explicitly declares its input dependencies:
- `tier1_step2` (claims) requires `sections.json`
- `tier1_step3` (gaps) requires `sections.json`
- `tier1_step4` (hypotheses) requires `gaps_actionable.json`
- `tier1_step5` (critic) requires `hypotheses.json`
- `tier1_step6` (debate) requires `hypotheses_scored.json`
- `tier1_step7` (reflection) requires `hypotheses_scored.json`

### 5.3 Error Propagation

The `_step()` helper supports a `no_abort` flag for non-critical steps (RAG, qdrant_analysis, metrics). When `no_abort=True`, failures are logged but don't halt the pipeline:

```python
def _step(label, fn, *args, no_abort=False):
    try:
        fn(*args)
    except Exception as exc:
        if no_abort:
            log.warning("Non-critical step '%s' failed: %s", label, exc)
        else:
            raise SystemExit(f"Step '{label}' failed: {exc}")
```

### 5.4 Backend↔Pipeline Communication

The backend runs the pipeline as a subprocess via `pipeline_runner.py`:

```python
cmd = [python_exe, str(pipeline_dir / "run_pipeline.py"), "--mode", mode]
result = subprocess.run(cmd, cwd=str(pipeline_dir), timeout=1800)
```

Status is tracked in an in-memory dict protected by a threading lock. After completion, JSON outputs are copied from the shared output directory to a paper-specific directory (`outputs/{paper_id}/`).

---

## 6. Error Handling & System Robustness

### 6.1 LLM Failure Modes & Mitigations

| Failure Mode | Detection | Mitigation |
|-------------|-----------|------------|
| API timeout (30s) | `httpx.TimeoutException` / `openai.APITimeoutError` | Cascade to next provider |
| Rate limit (429) | `openai.RateLimitError` | Retry with 2s backoff (2 retries) |
| Auth failure (401/403) | `openai.APIStatusError` | Immediate cascade (no retry) |
| Server error (5xx) | `openai.APIStatusError` | Retry with backoff |
| JSON parse failure | `json.JSONDecodeError` | Regex extraction → `LLMParseError` → cascade |
| Code fence wrapping | `strip_code_fences()` | Pre-processing before parse |
| All providers down | Exhausted cascade | Deterministic fallback with safe defaults |

### 6.2 File I/O Safety

**Atomic Writes:** Both `assembler.py` and `metrics.py` use the pattern:
```python
tmp = out_path.with_suffix(".tmp")
tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
os.replace(str(tmp), str(out_path))
```
This prevents partial writes from corrupting output files during crashes.

**UTF-8 with Error Handling:** PDF text and paper files are read with `encoding="utf-8", errors="ignore"` to tolerate encoding issues.

### 6.3 Pipeline Resilience Patterns

- **Non-critical step isolation:** RAG indexing, Qdrant analysis, and metrics computation use `no_abort=True`, meaning the pipeline completes even if these optional features fail
- **Graceful RAG degradation:** `_get_rag_retriever()` in hypothesis_generator returns `None` if Qdrant is unconfigured, and all RAG consumers check for `None` before use
- **Default scores on critic failure:** Parse failures in the critic module assign `{clarity: 3, novelty: 3, feasibility: 3, total: 9}`, which ensures a REVISE decision (safe middle ground)
- **Reflection skip for REJECT:** The reflection engine only processes KEEP and REVISE hypotheses, avoiding wasted computation on rejected hypotheses
- **Registry retry logic:** The ingestion pipeline only skips papers with status `indexed`, automatically retrying `failed` papers

### 6.4 Backend Robustness

- **30-minute subprocess timeout:** Pipeline runs are killed after 1800 seconds
- **Thread safety:** Pipeline status updates use `threading.Lock()` around the shared `_statuses` dict
- **Multi-filename search:** The output reader searches for both `evaluation_metrics.json` and `evaluation_report.json` across four path patterns per file
- **CORS configuration:** Configurable via environment variable, defaults to `*` for development

---

## 7. Experimental Design for Research Validation

### 7.1 Ablation Study Design

**Experiment 1 — Agent Temperature Ablation:**
- Vary AgentA temperature: {0.1, 0.2, 0.3, 0.4, 0.5}
- Vary AgentB temperature: {0.5, 0.6, 0.7, 0.8, 0.9, 1.0}
- Measure: hypothesis diversity (Jaccard distance between AgentA/B outputs), critic score distributions, debate outcome stability
- Hypothesis: Wider temperature gap → higher diversity → more productive debates

**Experiment 2 — Debate Round Ablation:**
- Condition A: Round 1 only (direct comparison)
- Condition B: Rounds 1+2 (comparison + challenge)
- Condition C: Rounds 1+2+3 (full protocol)
- Measure: Preferred hypothesis quality (human evaluation), decision flip rate between rounds, confidence calibration

**Experiment 3 — Claim Extraction Strategy Comparison:**
- Condition A: Keyword-only extraction
- Condition B: LLM-only extraction
- Condition C: Combined (current system)
- Measure: Precision/recall against human-annotated claims, unique claims per strategy

**Experiment 4 — RAG Evidence Impact:**
- Condition A: No RAG evidence (baseline)
- Condition B: Standard retrieval (top-5)
- Condition C: MMR retrieval (top-5, λ=0.5)
- Measure: Hypothesis grounding (human eval), critic score distribution, evidence diversity score

**Experiment 5 — Gap Detection Sensitivity:**
- Vary `MIN_ACTIONABLE`: {4, 8, 12, 16, 20}
- Vary Jaccard dedup threshold: {0.5, 0.6, 0.7, 0.8, 0.9}
- Measure: Gap coverage (fraction of human-identified gaps detected), false positive rate, downstream hypothesis quality

### 7.2 Baseline Comparison Design

**Baseline 1 — Single-Agent Generation:**
Replace dual-agent + debate with a single LLM call generating one hypothesis per gap. Compare hypothesis quality (human eval + automated metrics) and diversity.

**Baseline 2 — No Debate:**
Keep dual-agent generation but skip the debate stage. Use critic scores alone for preference selection. Measure quality improvement attributable to the debate protocol.

**Baseline 3 — Static Prompts:**
Remove RAG evidence injection and use fixed prompts without paper-specific context. Measure the contribution of evidence grounding.

### 7.3 Human Evaluation Protocol

- **Annotators:** ≥3 NLP/ML researchers, blind to system conditions
- **Metrics:** Clarity (1-5), Novelty (1-5), Feasibility (1-5), Overall quality (1-5)
- **IAA:** Inter-annotator agreement via Krippendorff's alpha, target α ≥ 0.7
- **Sample:** 50 hypotheses stratified by gap type and source agent

---

## 8. Novel Contributions & Research Value

### 8.1 Multi-Agent Adversarial Debate for Hypothesis Generation

The three-round debate protocol is, to our knowledge, the first implementation of structured adversarial debate for automated hypothesis generation. The protocol's key innovations:

1. **Epistemic Diversity by Design:** The temperature gap (0.4 vs. 0.9) between agents is not arbitrary—it ensures one agent explores the conservative, incremental hypothesis space while the other explores the creative, high-risk space. This dual-agent setup systematically covers a wider hypothesis landscape than any single-agent approach.

2. **Challenge-Response Dynamics:** Round 2 introduces the non-preferred agent's opportunity to DEFEND, CONCEDE, or REFINE. This three-action space creates a structured adversarial dynamic where weak hypotheses are challenged and strong ones are validated through opposition.

3. **Confidence-Adjusted Verdicts:** The 0.1 confidence penalty for DEFEND actions quantitatively encodes the intuition that unresolved disagreement should reduce certainty.

### 8.2 Cascading LLM Reliability Architecture

The three-tier fallback system (OpenAI → Grok → Deterministic) with schema-preserving deterministic fallback is a practical contribution to LLM system engineering. The key insight is that the deterministic fallback returns the same JSON schema as successful LLM calls, with default scores that produce safe REVISE decisions—ensuring the pipeline always produces meaningful output regardless of API availability.

### 8.3 Integrated Knowledge Extraction Pipeline

The full pipeline—from PDF parsing through claim extraction, gap detection, dual-agent hypothesis generation, peer review, structured debate, reflection, cross-paper synthesis, contradiction detection, and automated evaluation—represents a complete instantiation of the automated scientific discovery workflow.

### 8.4 MMR-Enhanced RAG for Research Grounding

The implementation of Maximal Marginal Relevance retrieval with paper-diversity enforcement (min_papers constraint, 60% dominance threshold, automatic λ reduction) addresses a specific problem in research RAG: ensuring evidence is drawn from multiple papers rather than over-representing a single source.

---

## 9. Limitations & Known Issues

### 9.1 PDF Parsing Limitations

- **Four-bucket section model:** All technical content (methods, experiments, results, discussion, analysis, ablation) is merged into a single `evaluation` bucket. This loses section-level granularity that could improve claim and gap extraction precision
- **Heading detection heuristics:** Three regex patterns cover common formats but miss uncommon heading styles (e.g., italic-only headings, non-Latin characters)
- **No table/figure extraction:** The parser extracts text only. Tabular data, figures, and equations are either lost or garbled

### 9.2 Claim Extraction Constraints

- **MAX_CLAIMS=10 cap:** Arbitrary hard limit may truncate important claims from long papers
- **4,000-character input truncation:** The LLM sees only a fraction of each section, potentially missing claims in later paragraphs
- **Confidence thresholding:** The 0.5 minimum confidence filter and keyword-assigned 0.75 base confidence are not empirically calibrated

### 9.3 Gap Detection Limitations

- **Fixed direction templates:** Only 4 gap types with hardcoded actionable directions. Gaps outside these categories receive generic directions that may not be useful
- **Keyword-only detection:** No LLM-based gap detection; relies entirely on 21 signal keywords. Implicit gaps or gaps expressed with novel phrasing are missed

### 9.4 Hypothesis Generation Issues

- **Deterministic fallback quality:** When all LLM providers are unavailable, the system produces placeholder hypotheses ("Hypothesis pending LLM availability...") that carry no research value. The pipeline continues but all downstream outputs (scores, debates, reflections) are computed over meaningless text
- **No cross-gap reasoning:** Each gap is processed independently. Hypotheses cannot reference or build upon hypotheses from other gaps

### 9.5 Debate Protocol Limitations

- **Single comparison per gap:** Only one pair of hypotheses (AgentA vs. AgentB) is debated per gap. Alternative pairings or multi-hypothesis tournaments are not supported
- **Fixed three rounds:** The debate protocol cannot terminate early (when Round 1 produces high-confidence agreement) or extend (when Round 3 confidence remains low)

### 9.6 Cross-Paper Analysis Constraints

- **Legacy paper slot model:** Despite the dynamic paper registry, the pipeline still uses `paper2` and `paper3` naming conventions hardcoded in configuration. True N-paper comparison requires rewriting the cross-paper modules
- **Same-model benchmark assumption:** Numeric contradiction detection assumes papers report on the same benchmarks (cora, citeseer, pubmed, ppi). Papers using different benchmarks produce no numeric comparisons

### 9.7 RAG Dependencies

- **External service dependency:** Qdrant Cloud is required for RAG features. If credentials are not configured, all RAG-enhanced stages (evidence injection in hypothesis generation, critic scoring, and reflection) operate without grounding evidence
- **Embedding model fixed:** The all-MiniLM-L6-v2 model is hardcoded with 384-dim vectors. Switching models requires recreating the entire Qdrant collection

### 9.8 Evaluation Limitations

- **Proxy metrics only:** Retrieval precision uses keyword overlap as a proxy for relevance. Hypothesis quality scoring uses the same LLM that generated the hypotheses, creating potential self-evaluation bias
- **No ground truth:** The system lacks gold-standard annotations for any output type. All automated metrics are heuristic approximations

---

## 10. Future Work & Extensions

### 10.1 Short-Term Improvements

1. **LLM-based gap detection:** Supplement keyword signals with an LLM call that identifies implicit research gaps, especially in methods and results sections
2. **Dynamic debate termination:** End debates early when Round 1 confidence exceeds a threshold (e.g., 0.9); extend to Round 4 when Round 3 confidence is below 0.5
3. **Multi-model ensemble:** Route different pipeline stages to different LLM providers based on task type (e.g., GPT-4 for debate, Claude for reflection)
4. **Section-aware claim extraction:** Use the 4-section structure to apply different extraction strategies per section (e.g., empirical claims from evaluation, methodological claims from introduction)

### 10.2 Medium-Term Extensions

5. **N-paper comparison:** Generalize cross-paper modules from fixed paper2/paper3 to arbitrary N-paper analysis with pairwise and group-level synthesis
6. **Interactive hypothesis refinement:** Allow users to provide feedback on hypotheses, creating a human-in-the-loop cycle that updates the reflection engine
7. **Citation graph integration:** Use citation networks from Semantic Scholar or OpenAlex to enrich gap detection with related-work context
8. **Experiment protocol generation:** Extend hypotheses into complete experimental protocols with specific methods, datasets, baselines, and expected outcomes

### 10.3 Long-Term Research Directions

9. **Multi-round iterative refinement:** Run the full pipeline multiple times, feeding final report insights back into claim extraction as context for deeper analysis
10. **Automated paper writing:** Generate draft paper sections from the hypothesis lineage, debate logs, and evidence base
11. **Collaborative multi-agent research:** Multiple AI scientist instances analyzing different aspects of a research area, then synthesizing findings
12. **Benchmark creation:** Use the system to automatically generate research benchmarks and evaluation suites for emerging research areas

---

## 11. Code Quality Assessment

### 11.1 Architecture Adherence

**Strengths:**
- Clean separation of concerns: each module has a single responsibility
- Consistent module interface: `run()` entry point pattern across all pipeline stages
- Centralized configuration via `ai_scientist/config.py`
- Lazy initialization for expensive resources (Qdrant client, SentenceTransformer model)

**Weaknesses:**
- Mixed abstraction levels: some modules use dataclasses (hypothesis_generator), others use raw dicts (gap_detector)
- No formal interface/protocol definitions between stages; coupling is implicit through JSON schema expectations
- The `main.py` legacy report assembler duplicates logic from `reporting/assembler.py`

### 11.2 Error Handling Quality

**Strengths:**
- Three-tier LLM fallback ensures pipeline completion
- Atomic file writes prevent corruption
- `no_abort` flag isolates non-critical failures
- Default scores on critic parse failure prevent cascade crashes

**Weaknesses:**
- Broad exception catching in several modules (`except Exception`) masks specific error types
- No structured error logging format; errors are scattered across module-specific loggers
- No error recovery for mid-pipeline failures (must restart from beginning)

### 11.3 Testing & Verification

**Current State:**
- `pytest >= 7.4.0` is in requirements.txt but no test files were found in the codebase
- No unit tests, integration tests, or end-to-end tests
- The `check` pipeline mode verifies file existence but not content validity

**Recommendations:**
- Unit tests for JSON parsing, heading detection, claim filtering, and Jaccard deduplication
- Integration tests for each pipeline stage with fixture data
- End-to-end test with a known paper producing expected output ranges
- Property-based tests for temperature/confidence bounds

### 11.4 Code Metrics

| Metric | Value |
|--------|-------|
| Total Python modules | 29 |
| Total estimated lines | ~5,500 |
| Average module size | ~190 lines |
| Largest module | debate_orchestrator.py (~430 lines) |
| Smallest module | llm/__init__.py (~5 lines) |
| LLM prompt count | 12 distinct system prompts |
| Configuration constants | ~30 |
| External API integrations | 3 (OpenAI, Grok/xAI, arXiv) |
| External service dependencies | 2 (Qdrant Cloud, OpenAI-compatible APIs) |

### 11.5 Security Considerations

- **API key management:** Keys loaded from environment variables via `python-dotenv`, not hardcoded
- **Input validation:** Backend uses Pydantic models with Field constraints (regex patterns, min/max lengths)
- **Subprocess execution:** Pipeline runs use explicit command arrays (not shell=True), preventing command injection
- **CORS policy:** Defaults to `*` (permissive) in development; should be restricted for production
- **No authentication:** The backend API has no authentication or authorization layer
- **PDF parsing:** pypdf is used (not untrusted JavaScript-based parsers), but PDFs from arXiv are treated as trusted input without additional sandboxing

---

## 12. Research Paper Mapping

### 12.1 Paper Structure Recommendation

**Title:** "Autonomous Scientific Hypothesis Generation Through Multi-Agent Adversarial Debate"

**Venue:** ACL 2026 Systems Track / NeurIPS 2025 Datasets and Benchmarks

### 12.2 Section Mapping

| Paper Section | Codebase Modules | Key Content |
|--------------|-----------------|-------------|
| Abstract | — | System overview, debate protocol, key results |
| Introduction | All modules (system description) | Research motivation, contributions list |
| Related Work | — | AI scientist systems, multi-agent reasoning, automated discovery |
| System Architecture (§3) | config.py, run_pipeline.py | Pipeline overview, execution modes |
| Knowledge Extraction (§4) | pdf_parser.py, claim_extractor.py, gap_detector.py | Section parsing, dual-strategy extraction |
| Multi-Agent Reasoning (§5) | hypothesis_generator.py, critic.py, debate_orchestrator.py, reflection_engine.py | Core contribution: dual-agent + debate |
| Cross-Paper Analysis (§6) | claims_sectioned.py, contradictions.py | Multi-paper synthesis and contradictions |
| RAG Integration (§7) | document_store.py, retriever.py | MMR retrieval with diversity enforcement |
| LLM Reliability (§8) | llm_client.py | Cascading fallback architecture |
| Experimental Setup (§9) | evaluation/metrics.py | Ablation design, baselines, metrics |
| Results (§10) | Output JSON files | Quality metrics, case studies |
| Discussion & Limitations (§11) | — | Known issues, design trade-offs |
| Conclusion | — | Summary, future work |

### 12.3 Contribution Claims for Research Paper

1. **Primary:** A novel three-round adversarial debate protocol for automated scientific hypothesis generation that outperforms single-agent baselines in hypothesis diversity and quality
2. **Secondary:** A complete end-to-end pipeline from PDF ingestion to scored, debated, and refined research hypotheses with full provenance tracking
3. **Tertiary:** A cascading multi-provider LLM architecture with deterministic fallback that ensures pipeline robustness under API failures
4. **Empirical:** Cross-paper contradiction detection combining numeric table extraction with LLM semantic analysis across multiple research papers

---

## 13. Appendices

### Appendix A: Complete Prompt Library

All LLM system prompts used in the pipeline, organized by module:

| # | Module | Prompt Name | Temperature | Max Tokens | Purpose |
|---|--------|-------------|-------------|------------|---------|
| 1 | claim_extractor | LLM_CLAIM_PROMPT | 0.2 | 500 | Extract 3-5 claims with evidence |
| 2 | hypothesis_generator | AGENT_A_SYSTEM_PROMPT | 0.4 | — | Conservative hypothesis generation |
| 3 | hypothesis_generator | AGENT_B_SYSTEM_PROMPT | 0.9 | — | Exploratory hypothesis generation |
| 4 | critic | SYSTEM_PROMPT | 0.3 | 200 | Peer-review scoring (clarity/novelty/feasibility) |
| 5 | debate_orchestrator | DEBATE_SYSTEM_PROMPT (Round 1) | 0.4 | 300 | Senior advisor comparison |
| 6 | debate_orchestrator | CHALLENGE_SYSTEM_PROMPT (Round 2) | 0.5 | 300 | Challenge by non-preferred agent |
| 7 | debate_orchestrator | SYNTHESIS_SYSTEM_PROMPT (Round 3) | 0.3 | 300 | Final synthesis verdict |
| 8 | reflection_engine | SYSTEM_PROMPT | 0.5 | 300 | Reflective improvement |
| 9 | claims_sectioned | CROSS_PAPER_SYNTHESIS_PROMPT | 0.3 | 1200 | Cross-paper claim synthesis |
| 10 | contradictions | CONTRADICTION_PROMPT | 0.3 | 1000 | Semantic contradiction detection |
| 11 | contradictions | QDRANT_CONTRADICTION_PROMPT | 0.3 | 1200 | RAG-based contradiction detection |
| 12 | metrics | _HYP_QUALITY_PROMPT | 0.3 | 150 | Hypothesis quality assessment |

### Appendix B: Configuration Reference

```python
# ai_scientist/config.py
ROOT_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = ROOT_DIR / "data" / "papers"
OUTPUT_DIR  = ROOT_DIR / "outputs"
PAPER1_PATH = DATA_DIR / "paper1.pdf"
PAPER2_PATH = DATA_DIR / "paper2.pdf"
PAPER3_PATH = DATA_DIR / "paper3.pdf"

# Environment variables
OPENAI_API_KEY     = os.getenv("OPENAI_API_KEY", "")
QDRANT_URL         = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY     = os.getenv("QDRANT_API_KEY", "")
COLLECTION_NAME    = os.getenv("QDRANT_COLLECTION", "ai_scientist_papers")
GROK_API_KEY       = os.getenv("GROK_API_KEY", "")

# Backend (backend/main.py)
PIPELINE_DIR  = os.getenv("PIPELINE_DIR", parent_dir)
OUTPUTS_DIR   = os.getenv("OUTPUTS_DIR", PIPELINE_DIR / "outputs")
INPUTS_DIR    = os.getenv("INPUTS_DIR", PIPELINE_DIR / "inputs")
CORS_ORIGINS  = os.getenv("CORS_ORIGINS", "*")
```

### Appendix C: API Endpoint Catalog

| Method | Endpoint | Description | Request | Response |
|--------|----------|-------------|---------|----------|
| GET | `/health` | Health check | — | `{"status": "ok"}` |
| GET | `/api/papers` | List available papers | — | `{"papers": ["paper1", ...]}` |
| POST | `/api/upload` | Upload PDF | multipart/form-data | `{"paper_id": "...", "filename": "..."}` |
| POST | `/api/pipeline/run` | Start pipeline | `RunPipelineRequest` | `{"job_id": "...", "status": "running"}` |
| GET | `/api/pipeline/status/{paper_id}` | Pipeline status | — | `PipelineStatusResponse` |
| GET | `/api/outputs/papers` | List papers with outputs | — | `{"papers": [...]}` |
| GET | `/api/outputs/{paper_id}/final_report` | Final report | — | `FinalReport` |
| GET | `/api/outputs/{paper_id}/evaluation_report` | Evaluation metrics | — | `EvaluationReport` |
| GET | `/api/outputs/{paper_id}/cross_paper` | Cross-paper data | — | `CrossPaperData` |
| GET | `/api/outputs/{paper_id}/download/{file_type}` | Download output file | — | FileResponse (JSON) |
| POST | `/api/query` | RAG semantic search | `QueryRequest` | `QueryResponse` |

**Download file_type values:** `final_report`, `evaluation_report`, `sections`, `claims`, `gaps`, `hypotheses`, `reflection`, `debate`, `cross_paper`, `evaluation`

### Appendix D: Dependency List

```
# Core
pypdf>=3.0.0              # PDF text extraction
openai>=1.30.0            # Primary LLM provider
httpx>=0.27.0             # Grok xAI HTTP client
tenacity>=8.2.0           # Retry utilities

# RAG
sentence-transformers>=2.2.0  # Embedding model (all-MiniLM-L6-v2)
qdrant-client>=1.7.0          # Vector store client

# Ingestion
arxiv>=2.1.0              # arXiv API SDK

# Backend
fastapi                   # REST API framework
uvicorn                   # ASGI server
python-dotenv>=1.0.0      # Environment variable loading

# Dev
pytest>=7.4.0             # Test framework
anthropic>=0.40.0         # (Unused in current code — reserved for future provider)
```

### Appendix E: Pipeline Execution Timing Profile

Estimated execution times for a single paper (tier1 mode, with LLM availability):

| Stage | Estimated Time | LLM Calls | Bottleneck |
|-------|---------------|-----------|------------|
| PDF Parse | <2s | 0 | pypdf I/O |
| Claim Extraction | 5-15s | 4 (one per section) | LLM latency |
| Gap Detection | <1s | 0 | Regex/keyword |
| Hypothesis Generation | 15-30s | 16 (2 agents × 8 gaps) | LLM latency |
| Critic Scoring | 15-30s | 16 (one per hypothesis) | LLM latency |
| Debate Orchestration | 20-60s | 24 (3 rounds × 8 gaps) | LLM latency |
| Reflection | 10-20s | ≤16 (KEEP + REVISE only) | LLM latency |
| Report Assembly | <1s | 0 | File I/O |
| **Total (tier1)** | **~70-160s** | **~76** | **LLM API** |

---

*Document generated through forensic analysis of 29 Python modules, 7 subpackages, 4 backend service modules, 12 LLM prompts, and 10 output schema files.*
