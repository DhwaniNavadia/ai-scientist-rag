"""Final validation of all upgrades."""
import json
import sys
sys.path.insert(0, ".")

# === Test claim noise filter ===
from ai_scientist.extraction.claim_extractor import _is_valid_claim

tests = [
    ("Figure 3 shows the results", False),
    ("Table 2 demonstrates performance", False),
    ("[1] proposed a method", False),
    ("http://example.com has the data", False),
    ("Short", False),
    ("The proposed GNN architecture achieves state-of-the-art results on node classification.", True),
    ("x" * 301, False),
]
print("=== CLAIM NOISE FILTER ===")
for text, expected in tests:
    result = _is_valid_claim(text)
    status = "PASS" if result == expected else "FAIL"
    print(f"  {status}: _is_valid_claim({text[:50]!r}) = {result} (expected {expected})")

# === Test contradiction severity values ===
from ai_scientist.cross_paper.contradictions import CONTRADICTION_PROMPT, QDRANT_CONTRADICTION_PROMPT

checks = {
    '"high"' in CONTRADICTION_PROMPT: "high severity in prompt",
    '"medium"' in CONTRADICTION_PROMPT: "medium severity in prompt",
    '"low"' in CONTRADICTION_PROMPT: "low severity in prompt",
    "evidence_a" in CONTRADICTION_PROMPT: "evidence_a in prompt",
    "confidence" in CONTRADICTION_PROMPT: "confidence in prompt",
    "MUST differ from paper_a" in QDRANT_CONTRADICTION_PROMPT: "cross-paper guard in qdrant prompt",
}
print("\n=== CONTRADICTION SEVERITY + GUARD ===")
for cond, label in checks.items():
    print(f"  {'PASS' if cond else 'FAIL'}: {label}")

# === Test 3-round debate structure ===
from ai_scientist.reasoning.debate_orchestrator import build_disagreement_log

scored = json.loads(open("outputs/hypotheses_scored.json").read())
log = build_disagreement_log(scored)
print(f"\n=== DEBATE 3-ROUND STRUCTURE ({len(log)} entries) ===")
all_have_r3 = True
for e in log:
    r1 = e.get("round_1")
    r2 = e.get("round_2")
    r3 = e.get("round_3")
    df = r3.get("decisive_factor", "") if r3 else ""
    if not r3 or not df:
        all_have_r3 = False
    print(f"  gap={e['gap_id']}: r1={bool(r1)}, r2={r2 is not None}, r3={bool(r3)}, decisive_factor={df!r}")
print(f"  ALL have round_3 with decisive_factor: {'PASS' if all_have_r3 else 'FAIL'}")

# === Test eval metrics output ===
eval_path = "outputs/2410_08249v2/eval_metrics.json"
import os
print(f"\n=== EVAL METRICS FILE ===")
print(f"  {eval_path} exists: {'PASS' if os.path.exists(eval_path) else 'FAIL'}")
if os.path.exists(eval_path):
    m = json.loads(open(eval_path).read())
    print(f"  Keys: {list(m.keys())}")
