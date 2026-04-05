#!/usr/bin/env python3
"""Check 4: Hypothesis generation test."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_scientist.reasoning.hypothesis_generator import _generate_for_agent, Hypothesis
from ai_scientist.utils.llm_client import has_keys

print(f"has_keys(): {has_keys()}")

if not has_keys():
    print("SKIP: No OpenAI API keys configured — cannot test hypothesis generation")
    print("Checking structural correctness only...")
    # Test that the Hypothesis dataclass works
    hyp = Hypothesis(
        hypothesis_id="test",
        gap_id="G1",
        gap_type="method",
        gap_text="test gap",
        actionable_direction="test direction",
        hypothesis_text="test hypothesis",
        source="AgentA",
        based_on=["ref1"],
        novelty_score=0.8,
        confidence=0.7,
    )
    d = hyp.to_dict()
    assert d["hypothesis_text"] == "test hypothesis"
    assert d["based_on"] == ["ref1"]
    assert d["novelty_score"] == 0.8
    print("Hypothesis dataclass: OK")
    print("CHECK 4: PARTIAL PASS (no LLM key, dataclass OK)")
    sys.exit(0)

# Full test with LLM
gap = {
    "gap_id": "G_test",
    "gap_type": "scalability",
    "gap_text": "The role of positional encoding in long-context transformers is underexplored.",
    "actionable_direction": "Investigate improved positional encoding for long sequences",
}

retrieved = [
    {"text": "Rotary embeddings improve length generalisation...", "paper_id": "paper_1", "score": 0.91}
]

try:
    result = _generate_for_agent(gap, "AgentA", 0.4, rag_evidence=retrieved)
    print(f"Result keys: {list(result.keys())}")
    print(f"hypothesis_text: {result['hypothesis_text'][:200]}")
    print(f"based_on: {result['based_on']}")
    print(f"novelty_score: {result['novelty_score']}")
    print(f"confidence: {result['confidence']}")
    
    assert result["hypothesis_text"] != "", "FAIL: empty hypothesis"
    assert not result["hypothesis_text"].startswith("[Generation"), "FAIL: generation failed marker"
    assert "based_on" in result, "FAIL: missing based_on"
    print("CHECK 4: PASS")
except Exception as e:
    print(f"CHECK 4: FAIL — {e}")
    sys.exit(1)
