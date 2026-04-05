import type { EvaluationReport, FinalReport } from "./types";

export const DEMO_PAPER_IDS = ["demo_hsap", "demo_nlp"] as const;

export const demoFinalReports: Record<string, FinalReport> = {
  demo_hsap: {
    paper_id: "demo_hsap",
    paper_title: "Hierarchical Seating Allocation Problem (HSAP)",
    generated_at: "2025-07-21T00:00:00Z",
    sections: {
      Abstract:
        "The Hierarchical Seating Allocation Problem (HSAP) addresses the challenge of assigning employees to seats in a corporate office while respecting organizational structure, spatial constraints, and human preference. We formulate HSAP as a Mixed-Integer Quadratic Program (MIQP) and prove the problem is NP-hard. Three scalable solution approaches are presented: an exact branch-and-bound solver, a decomposition heuristic with warm-start, and a hybrid meta-controller.",
      Introduction:
        "Modern organizations face complex seating allocation challenges that must balance physical constraints (proximity, floor capacity) with hierarchical preferences (teams seated together, managers near their reports) and human factors (natural light, quiet zones). Prior work on seating allocation focuses on simpler variants without hierarchy or large-scale instances. PRM and RRT graph-based methods have been used to estimate pairwise seat distances on floor plans, but noisy or low-resolution floor plan images degrade distance estimates significantly.",
      Methods:
        "We model HSAP using a graph G = (V, E) where V represents seats and E encodes spatial proximity. The objective minimises total weighted distance subject to hierarchical grouping constraints. Probabilistic Roadmap Method (PRM) generates a roadmap from the floor plan image using δc (connection radius) and δs (step size) as hyper-parameters tuned to K = 2000 nodes. The MIQP formulation contains O(|S|²) decision variables, making direct optimisation intractable beyond 50 seats. We introduce a decomposition heuristic that partitions subproblems by team, solves each independently, and assembles a global solution with a conflict-resolution step.",
      Results:
        "Experiments on 50 synthetic instances (|S| ∈ {10, 50, 100, 200}) show the decomposition heuristic achieves 95.2% of exact-solver quality while reducing runtime by 10× on large instances. Human evaluators rated solutions produced by heuristic as 4.1/5 on average, compared to 3.8/5 for pure optimisation, suggesting the heuristic naturally surfaces group-adjacent seating patterns preferred by humans.",
      Conclusion:
        "This work presents the first formal treatment of HSAP and demonstrates that scalable, human-aligned seating allocation is achievable. Key limitations include manual hyper-parameter tuning (δc, δs), the limited ability of MIQP to incorporate subjective human preferences beyond hard constraints, and intractability for very large instances (> 50 seats in the monolithic formulation). Future work should investigate reinforcement learning for dynamic re-allocation and learned floor-plan representations.",
    },
    claims: [
      {
        claim_id: "C1",
        claim_text: "HSAP is NP-hard and reduces to graph coloring.",
        evidence_text:
          "We show via polynomial reduction from graph coloring that HSAP is NP-hard in the general case.",
        confidence: 0.95,
        section: "Introduction",
      },
      {
        claim_id: "C2",
        claim_text:
          "PRM-based distance estimation degrades significantly on low-quality floor plans.",
        evidence_text:
          "Similarly, finding an adequate representation is also made difficult if the quality of the provided floor plans is low.",
        confidence: 0.88,
        section: "Methods",
      },
      {
        claim_id: "C3",
        claim_text:
          "The decomposition heuristic achieves 95% of optimal quality at 10× speed.",
        evidence_text:
          "The heuristic achieves 95.2% of exact-solver quality while reducing runtime by 10× on large instances.",
        confidence: 0.91,
        section: "Results",
      },
      {
        claim_id: "C4",
        claim_text:
          "Human evaluators prefer heuristic solutions over exact optimisation output.",
        evidence_text:
          "Human evaluators rated solutions produced by heuristic as 4.1/5 on average, compared to 3.8/5 for pure optimisation.",
        confidence: 0.82,
        section: "Results",
      },
      {
        claim_id: "C5",
        claim_text:
          "MIQP formulation contains O(|S|²) variables, making it intractable beyond 50 seats.",
        evidence_text:
          "Solving the HSAP problem as a single monolithic instance is intractable for small, medium and large scale instances (i.e. over 50 seats).",
        confidence: 0.97,
        section: "Methods",
      },
      {
        claim_id: "C6",
        claim_text:
          "Hyper-parameters δc and δs were manually tuned until convergence at K = 2000.",
        evidence_text:
          "The hyper-parameters for δc and δs were manually tuned until the algorithm converged with a node limit of K = 2000.",
        confidence: 0.93,
        section: "Methods",
      },
    ],
    gaps: [
      {
        gap_id: "G1",
        gap_description:
          "Floor plan quality directly limits PRM/RRT distance estimation accuracy, but no automated robustness mechanism exists.",
        gap_type: "data_quality",
        actionable_direction:
          "A noise-robust preprocessing pipeline (denoising + wall-confidence filtering) could reduce PRM/RRT distance-estimation errors on low-quality floor plans.",
        priority: 1,
      },
      {
        gap_id: "G2",
        gap_description:
          "The optimisation objective does not model human adjacency preferences, leading to mathematically optimal but humanly unappealing solutions.",
        gap_type: "human_alignment",
        actionable_direction:
          "Adding an adjacency/contiguity penalty to the optimisation objective will improve human-rated seating quality without significantly increasing runtime.",
        priority: 2,
      },
      {
        gap_id: "G3",
        gap_description:
          "MIQP formulation is intractable for large instances (> 50 seats) due to O(|S|²) decision variables.",
        gap_type: "scalability",
        actionable_direction:
          "Decomposing the MIQP into smaller subproblems with a heuristic warm-start will reduce runtime while maintaining allocation quality on large instances.",
        priority: 3,
      },
    ],
    hypothesis_pairs: [
      {
        gap_id: "G1",
        agentA: {
          agent: "AgentA",
          hypothesis:
            "A noise-robust preprocessing pipeline (denoising + wall-confidence filtering) will reduce PRM/RRT distance-estimation errors on low-quality floor plans.",
          rationale:
            "Preprocessing floors plans to remove noise before feeding into PRM/RRT directly addresses the root cause of degraded distance estimates.",
          score: 9.3,
          decision: "KEEP",
        },
        agentB: {
          agent: "AgentB",
          hypothesis:
            "Ablating preprocessing steps will reveal that distance-estimation error is dominated by wall-detection failures on noisy plans.",
          rationale:
            "An ablation study pinpoints which preprocessing component contributes most to error, enabling targeted improvements.",
          score: 8.7,
          decision: "KEEP",
        },
        preferred: "AgentA",
        agreement: true,
      },
      {
        gap_id: "G2",
        agentA: {
          agent: "AgentA",
          hypothesis:
            "Adding an adjacency/contiguity penalty to the optimisation objective will improve human-rated seating quality without significantly increasing runtime.",
          rationale:
            "Encoding group adjacency as a soft penalty term directly aligns the mathematical objective with observed human preferences.",
          score: 8.7,
          decision: "KEEP",
        },
        agentB: {
          agent: "AgentB",
          hypothesis:
            "A two-stage approach (optimise constraints first, then apply a local human-preference refinement) will yield higher human satisfaction than a single-objective solver.",
          rationale:
            "Decoupling hard constraint satisfaction from preference optimisation avoids over-constraining the primary objective.",
          score: 8.0,
          decision: "KEEP",
        },
        preferred: "AgentA",
        agreement: true,
      },
      {
        gap_id: "G3",
        agentA: {
          agent: "AgentA",
          hypothesis:
            "Decomposing the MIQP into smaller subproblems with a heuristic warm-start will reduce runtime while maintaining allocation quality on large instances.",
          rationale:
            "Team-level decomposition reduces the number of variables per subproblem from O(|S|²) to O(t²) where t is team size, enabling tractable exact solving.",
          score: 9.3,
          decision: "KEEP",
        },
        agentB: {
          agent: "AgentB",
          hypothesis:
            "A hybrid approach that switches from exact optimisation to heuristic search beyond a size threshold will provide better runtime–quality tradeoffs than pure exact optimisation.",
          rationale:
            "Different instance sizes benefit from different algorithms; a dynamic selector avoids the worst-case behaviour of any single approach.",
          score: 8.7,
          decision: "KEEP",
        },
        preferred: "AgentA",
        agreement: true,
      },
    ],
    reflections: [
      {
        gap_id: "G1",
        original_hypothesis:
          "A noise-robust preprocessing pipeline (denoising + wall-confidence filtering) will reduce PRM/RRT distance-estimation errors on low-quality floor plans.",
        improvement_plan:
          "1. Add a benchmark of 50 synthetic noisy floor plans with ground-truth distances.\n2. Define the primary metric as mean absolute distance error (MADE).\n3. Compare denoising-only vs wall-confidence-only vs combined pipeline.\n4. Include a baseline of raw plan input with no preprocessing.",
        revised_hypothesis:
          "A combined denoising + wall-confidence-filtering preprocessing pipeline will reduce mean absolute distance error (MADE) by ≥ 20% compared to raw floor plan input, as validated on a benchmark of 50 synthetic floor plans with known ground-truth distances.",
        improvement_score: 0.72,
      },
      {
        gap_id: "G2",
        original_hypothesis:
          "Adding an adjacency/contiguity penalty to the optimisation objective will improve human-rated seating quality without significantly increasing runtime.",
        improvement_plan:
          "1. Define 'human-rated quality' via a structured 5-point Likert scale administered to 20 evaluators.\n2. Specify 'significant runtime increase' as > 15% overhead.\n3. Test on instances of sizes 20, 50, 100.\n4. Report both quality improvement and runtime overhead with confidence intervals.",
        revised_hypothesis:
          "Adding a tunable adjacency/contiguity penalty (λ ∈ {0.1, 0.5, 1.0}) will improve mean human-rated quality by ≥ 0.3 Likert points compared to the unpenalised MIQP, with < 15% runtime overhead, as evaluated on instances of sizes 20/50/100 with 20 human raters.",
        improvement_score: 0.68,
      },
      {
        gap_id: "G3",
        original_hypothesis:
          "Decomposing the MIQP into smaller subproblems with a heuristic warm-start will reduce runtime while maintaining allocation quality on large instances.",
        improvement_plan:
          "1. Define 'large instances' as |S| > 50 based on tractability analysis.\n2. Measure solution quality as deviation from exact solver (% optimality gap).\n3. Compare: no warm-start vs random warm-start vs heuristic warm-start.\n4. Target: maintain ≥ 90% of exact-solver quality at ≥ 5× speedup.",
        revised_hypothesis:
          "A team-level MIQP decomposition with heuristic warm-start will maintain ≥ 90% of exact-solver solution quality (measured by optimality gap) while achieving ≥ 5× runtime reduction on instances with |S| ∈ {50, 100, 200}, compared to the monolithic MIQP baseline.",
        improvement_score: 0.65,
      },
    ],
  },

  demo_nlp: {
    paper_id: "demo_nlp",
    paper_title: "Efficient Zero-Shot Cross-Lingual Transfer for NLP Tasks",
    generated_at: "2025-07-21T00:00:00Z",
    sections: {
      Abstract:
        "Zero-shot cross-lingual transfer leverages multilingual pre-trained models to perform NLP tasks in target languages without any target-language training data. This paper analyses the gap in transfer performance between high-resource and low-resource languages and proposes language-adaptive fine-tuning (LAFT) to narrow this gap.",
      Introduction:
        "Multilingual large language models (mLLMs) such as mBERT and XLM-R achieve strong performance on cross-lingual benchmarks, yet a significant performance gap persists for low-resource languages. We hypothesise that this gap is partly due to vocabulary imbalance and partly due to insufficient exposure during pre-training.",
      Methods:
        "We fine-tune XLM-R using language-specific adapter modules for 20 target languages. Each adapter adds < 2M parameters and is trained on unlabelled corpora. We evaluate on XNLI (NLI), TyDiQA (QA), and WikiANN (NER).",
      Results:
        "LAFT improves average zero-shot accuracy by 4.2% across all evaluated languages, with up to 9.1% improvement on Swahili. High-resource languages show minimal change (< 0.5%), confirming the targeted nature of the improvement.",
      Conclusion:
        "Language-adaptive fine-tuning is a lightweight and effective technique for improving zero-shot cross-lingual transfer for low-resource languages. Future work should explore adapter sharing across typologically similar languages.",
    },
    claims: [
      {
        claim_id: "C1",
        claim_text:
          "LAFT improves average zero-shot accuracy by 4.2% across evaluated languages.",
        evidence_text:
          "LAFT improves average zero-shot accuracy by 4.2% across all evaluated languages.",
        confidence: 0.93,
        section: "Results",
      },
      {
        claim_id: "C2",
        claim_text:
          "Performance gap for low-resource languages is partly due to vocabulary imbalance.",
        evidence_text:
          "We hypothesise that this gap is partly due to vocabulary imbalance during pre-training.",
        confidence: 0.71,
        section: "Introduction",
      },
      {
        claim_id: "C3",
        claim_text: "Each language adapter adds < 2M parameters.",
        evidence_text: "Each adapter adds < 2M parameters and is trained on unlabelled corpora.",
        confidence: 0.98,
        section: "Methods",
      },
    ],
    gaps: [
      {
        gap_id: "G1",
        gap_description:
          "Adapter sharing across typologically similar languages is unexplored.",
        gap_type: "scalability",
        actionable_direction:
          "Training a shared adapter for a language family (e.g., Romance, Bantu) and fine-tuning per-language heads could reduce parameter count while retaining accuracy.",
        priority: 1,
      },
      {
        gap_id: "G2",
        gap_description:
          "Vocabulary imbalance hypothesis is stated but not empirically validated.",
        gap_type: "data_quality",
        actionable_direction:
          "An ablation study that controls vocabulary coverage independently of pre-training hours would validate or refute the imbalance hypothesis.",
        priority: 2,
      },
    ],
    hypothesis_pairs: [
      {
        gap_id: "G1",
        agentA: {
          agent: "AgentA",
          hypothesis:
            "A shared-trunk adapter for a language family with per-language head layers will match per-language adapter accuracy with 60% fewer parameters.",
          rationale:
            "Typologically similar languages share morphosyntactic structure; a shared trunk can capture common patterns while heads retain language-specific features.",
          score: 8.7,
          decision: "KEEP",
        },
        agentB: {
          agent: "AgentB",
          hypothesis:
            "Cross-lingual adapter distillation from a high-resource source adapter to related low-resource target adapters will exceed per-language adapter performance.",
          rationale:
            "Knowledge distillation transfers structured representations rather than just parameters, potentially capturing richer cross-lingual alignment.",
          score: 8.0,
          decision: "KEEP",
        },
        preferred: "AgentA",
        agreement: true,
      },
      {
        gap_id: "G2",
        agentA: {
          agent: "AgentA",
          hypothesis:
            "Training XLM-R variants with controlled vocabulary coverage will show that vocabulary imbalance accounts for > 50% of the observed low-resource performance gap.",
          rationale:
            "Controlling vocabulary coverage as an independent variable allows causal attribution of the performance gap.",
          score: 8.0,
          decision: "KEEP",
        },
        agentB: {
          agent: "AgentB",
          hypothesis:
            "A vocabulary-aware fine-tuning strategy that up-weights low-resource language tokens will improve transfer accuracy independently of adapter modules.",
          rationale:
            "If vocabulary imbalance is causal, directly correcting it during fine-tuning (not just pre-training) should yield measurable gains.",
          score: 7.3,
          decision: "REVISE",
        },
        preferred: "AgentA",
        agreement: false,
      },
    ],
    reflections: [
      {
        gap_id: "G1",
        original_hypothesis:
          "A shared-trunk adapter for a language family with per-language head layers will match per-language adapter accuracy with 60% fewer parameters.",
        improvement_plan:
          "1. Define the language families to test (Romance, Bantu, Turkic).\n2. Specify 'match accuracy' as within 1% of per-language adapter baseline.\n3. Measure parameter reduction empirically across 5 language families.\n4. Add a baseline: single multilingual adapter (no family grouping).",
        revised_hypothesis:
          "For 3 language families (Romance, Bantu, Turkic), a shared-trunk + per-language-head adapter architecture will achieve accuracy within 1% of per-language adapter baselines using ≥ 50% fewer parameters, outperforming a single multilingual adapter baseline.",
        improvement_score: 0.61,
      },
    ],
  },
};

export const demoEvalReports: Record<string, EvaluationReport> = {
  demo_hsap: {
    paper_id: "demo_hsap",
    metrics: {
      win_rate: 0.68,
      avg_hypothesis_score: 7.2,
      keep_rate: 0.72,
      agent_agreement_rate: 0.81,
      total_gaps_evaluated: 3,
      total_comparisons_run: 9,
    },
    per_gap_results: [
      {
        gap_id: "G1",
        gap_description:
          "Floor plan quality limits PRM/RRT distance estimation accuracy.",
        majority_winner: "system",
        system_wins: 2,
        baseline_wins: 1,
        ties: 0,
        keep_votes: 3,
        avg_system_score: 8.9,
        avg_baseline_score: 5.2,
      },
      {
        gap_id: "G2",
        gap_description:
          "Optimisation objective does not model human adjacency preferences.",
        majority_winner: "system",
        system_wins: 2,
        baseline_wins: 1,
        ties: 0,
        keep_votes: 3,
        avg_system_score: 7.8,
        avg_baseline_score: 5.6,
      },
      {
        gap_id: "G3",
        gap_description: "MIQP intractable for large instances.",
        majority_winner: "baseline",
        system_wins: 1,
        baseline_wins: 2,
        ties: 0,
        keep_votes: 2,
        avg_system_score: 7.1,
        avg_baseline_score: 7.4,
      },
    ],
    summary: {
      strengths: [
        "System hypotheses for data_quality gaps score significantly higher than baseline (+3.7 pts on G1).",
        "High agent agreement rate (81%) indicates stable critique rubric across diverse gap types.",
        "All system hypotheses for G1 and G2 earned KEEP decisions — none required revision.",
      ],
      weaknesses: [
        "System underperforms baseline on G3 (scalability) — decomposition proposals are less specific than keyword-framed baselines.",
        "Feasibility scores are consistently lower than novelty/clarity, suggesting hypotheses need more grounding in preliminary experiments.",
      ],
      conclusion:
        "The pipeline generates higher-quality hypotheses than keyword-only baselines for data quality and human alignment gaps. Scalability gaps remain a challenge where more domain-specific prompting may help.",
    },
  },

  demo_nlp: {
    paper_id: "demo_nlp",
    metrics: {
      win_rate: 0.54,
      avg_hypothesis_score: 6.8,
      keep_rate: 0.62,
      agent_agreement_rate: 0.72,
      total_gaps_evaluated: 2,
      total_comparisons_run: 6,
    },
    per_gap_results: [
      {
        gap_id: "G1",
        gap_description: "Adapter sharing across typologically similar languages is unexplored.",
        majority_winner: "system",
        system_wins: 2,
        baseline_wins: 1,
        ties: 0,
        keep_votes: 3,
        avg_system_score: 7.8,
        avg_baseline_score: 5.9,
      },
      {
        gap_id: "G2",
        gap_description: "Vocabulary imbalance hypothesis is not empirically validated.",
        majority_winner: "baseline",
        system_wins: 1,
        baseline_wins: 2,
        ties: 0,
        keep_votes: 1,
        avg_system_score: 5.8,
        avg_baseline_score: 6.3,
      },
    ],
    summary: {
      strengths: [
        "Strong hypothesis quality for scalability gap G1 (system +1.9 pts over baseline).",
        "Agent agreement reasonable at 72% for a complex NLP domain.",
      ],
      weaknesses: [
        "G2 hypothesis scored below baseline — the statistical validation framing needs a clearer experimental design.",
      ],
      conclusion:
        "Mixed results on the NLP paper. Domain-specific knowledge gaps (vocabulary imbalance) are harder to hypothesise about without domain context. Including relevant literature in the RAG context would likely improve G2 performance.",
    },
  },
};
