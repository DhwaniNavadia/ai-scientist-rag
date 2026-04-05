export type PaperID = string;

export interface Claim {
  claim_id: string;
  claim_text: string;
  evidence_text: string;
  confidence: number;
  section: string;
}

export interface Gap {
  gap_id: string;
  gap_description: string;
  gap_type: string;
  actionable_direction: string;
  priority: number;
}

export interface AgentHypothesis {
  agent: "AgentA" | "AgentB";
  hypothesis: string;
  rationale: string;
  score: number;
  decision: "KEEP" | "REVISE" | "REJECT";
}

export interface HypothesisPair {
  gap_id: string;
  agentA: AgentHypothesis;
  agentB: AgentHypothesis;
  preferred: "AgentA" | "AgentB" | "tie";
  agreement: boolean;
}

export interface ReflectionEntry {
  gap_id: string;
  original_hypothesis: string;
  improvement_plan: string;
  revised_hypothesis: string;
  improvement_score: number;
}

export interface FinalReport {
  paper_id: string;
  paper_title: string;
  sections: Record<string, string>;
  claims: Claim[];
  gaps: Gap[];
  hypothesis_pairs: HypothesisPair[];
  reflections: ReflectionEntry[];
  generated_at: string;
}

export interface PerGapEvalResult {
  gap_id: string;
  gap_description: string;
  majority_winner: "system" | "baseline" | "tie";
  system_wins: number;
  baseline_wins: number;
  ties: number;
  keep_votes: number;
  avg_system_score: number;
  avg_baseline_score: number;
}

export interface EvalMetrics {
  win_rate: number;
  avg_hypothesis_score: number;
  keep_rate: number;
  agent_agreement_rate: number;
  total_gaps_evaluated: number;
  total_comparisons_run: number;
}

export interface EvaluationReport {
  paper_id: string;
  metrics: EvalMetrics;
  per_gap_results: PerGapEvalResult[];
  summary: {
    strengths: string[];
    weaknesses: string[];
    conclusion: string;
  };
}

export interface PipelineStatus {
  paper_id: string;
  status: "idle" | "running" | "completed" | "error";
  mode: "run" | "eval" | "full" | "tier1" | "tier2" | null;
  message: string;
  started_at: string | null;
  completed_at: string | null;
}
