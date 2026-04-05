#!/usr/bin/env python3
"""scripts/test_api.py — Smoke-test all API endpoints."""

import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0


def _req(method: str, path: str, body=None, expect_status=200):
    global PASS, FAIL
    url = BASE + path
    label = f"{method} {path}"
    try:
        headers = {"Content-Type": "application/json"} if body else {}
        data = json.dumps(body).encode() if body else None
        req = Request(url, data=data, headers=headers, method=method)
        resp = urlopen(req, timeout=15)
        status = resp.status
        payload = json.loads(resp.read().decode())
        if status == expect_status:
            PASS += 1
            print(f"  [PASS] {label} -> {status}")
            return payload
        else:
            FAIL += 1
            print(f"  [FAIL] {label} -> {status} (expected {expect_status})")
            return payload
    except HTTPError as e:
        # 4xx/5xx might be expected (e.g. 503 for unconfigured RAG)
        if e.code == expect_status:
            PASS += 1
            print(f"  [PASS] {label} -> {e.code} (expected)")
        else:
            FAIL += 1
            print(f"  [FAIL] {label} -> HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except (URLError, Exception) as e:
        FAIL += 1
        print(f"  [FAIL] {label} -> {e}")
        return None


print("=" * 60)
print("  Autonomous AI Scientist — API Smoke Tests")
print("=" * 60)

# 1. Health
print("\n[1] Health Check")
_req("GET", "/health")

# 2. Upload (skip actual file — just test endpoint exists)
print("\n[2] Paper Management")
_req("GET", "/api/uploaded")

# 3. Papers list
print("\n[3] Papers List")
_req("GET", "/api/papers")

# 4. Pipeline status (use a dummy paper_id)
print("\n[4] Pipeline Status")
_req("GET", "/api/pipeline/status/test_paper")

# 5. RAG Query (may return 503 if Qdrant not configured)
print("\n[5] RAG Query")
_req("POST", "/api/query", body={"query": "graph neural network", "top_k": 3},
     expect_status=503)  # Will be 503 if Qdrant not configured, 200 if it is

# 6. Outputs — list papers
print("\n[6] Outputs")
_req("GET", "/api/outputs/papers")

# Summary
print("\n" + "=" * 60)
print(f"  Results: {PASS} passed, {FAIL} failed")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
