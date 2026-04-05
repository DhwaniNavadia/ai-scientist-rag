#!/usr/bin/env python3
"""Check 3: Multi-paper retrieval test."""
import httpx

r = httpx.post("http://localhost:8000/api/query",
               json={"query": "neural network training", "top_k": 8},
               timeout=30)
chunks = r.json()["results"]
paper_ids = [c["paper_id"] for c in chunks]
unique = set(paper_ids)
print(f"Unique papers in results: {len(unique)} -- {unique}")
for c in chunks:
    print(f"  {c['paper_id']:20s} | {c['section']:20s} | score={c['score']:.3f} | {c['text'][:80]}")
assert len(unique) >= 2, "FAIL: retrieval is single-paper dominated"
print("CHECK 3: PASS")
