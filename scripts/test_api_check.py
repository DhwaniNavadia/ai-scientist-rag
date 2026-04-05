#!/usr/bin/env python3
"""Quick API smoke test for Phase 1 Check 2."""
import httpx
import json
import sys

BASE = "http://localhost:8000"
PAPER_ID = "2410_08249v2"

tests = [
    ("GET",  f"{BASE}/api/papers",                     None,
     lambda r: isinstance(r.json().get("papers"), list) and len(r.json()["papers"]) > 0),
    ("POST", f"{BASE}/api/query",
     {"query": "attention mechanism", "top_k": 5},
     lambda r: len(r.json().get("results", r.json().get("chunks", []))) >= 1),
    ("POST", f"{BASE}/api/pipeline/run",
     {"paper_id": PAPER_ID, "mode": "tier1"},
     lambda r: "job_id" in r.json()),
    ("GET",  f"{BASE}/api/pipeline/status/{PAPER_ID}", None,
     lambda r: "status" in r.json()),
    ("GET",  f"{BASE}/api/outputs/{PAPER_ID}/final_report", None,
     lambda r: r.status_code in [200, 404]),
    ("GET",  f"{BASE}/api/outputs/{PAPER_ID}/download/claims", None,
     lambda r: r.status_code in [200, 404]),
]

all_pass = True
for method, url, body, check in tests:
    try:
        r = httpx.request(method, url, json=body, timeout=30)
        passed = check(r)
        tag = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        short_url = url.replace(BASE, "")
        print(f"{tag} | {method:4s} {short_url:50s} | {r.status_code} | {r.text[:160]}")
    except Exception as e:
        all_pass = False
        short_url = url.replace(BASE, "")
        print(f"FAIL | {method:4s} {short_url:50s} | ERR  | {e}")

sys.exit(0 if all_pass else 1)
