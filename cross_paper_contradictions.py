from pathlib import Path
import json
import re
from collections import defaultdict

CLAIMS_JSON = "outputs/cross_paper_claims.json"

CANDIDATE_TEXT_FILES = {
    "paper2": ["outputs/paper2.txt", "outputs/paper2_text.txt", "outputs/paper2_raw.txt", "outputs/gcn.txt"],
    "paper3": ["outputs/paper3.txt", "outputs/paper3_text.txt", "outputs/paper3_raw.txt", "outputs/gat.txt"],
}

BENCH_DATASETS = ["cora", "citeseer", "pubmed", "ppi"]
DEFAULT_TABLE_METRIC = "accuracy"

DATASET_ALIASES = {
    "cite seer": "citeseer",
    "cite-seer": "citeseer",
    "p p i": "ppi",
    "protein-protein interaction": "ppi",
    "protein protein interaction": "ppi",
}

# Strongly exclude training/setup/architecture lines from being treated as result rows
ROW_BLOCKLIST = [
    "epoch", "epochs", "early stopping", "optimizer", "adam", "sgd",
    "learning rate", "lr", "weight decay", "regularization", "l2", "lambda", "λ",
    "hidden", "features", "heads", "attention heads", "units", "layers",
    "glorot", "relu", "elu", "dropout", "batch", "minibatch", "mini-batch",
    "cross entropy", "cross-entropy", "training", "validation", "test set size",
    "table", "figure", "experimental setup", "we train", "we test", "we evaluate",
]

# ------------------------ Utils ------------------------
def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def squeeze_letters(text: str) -> str:
    t = normalize(text)
    # "c i t e s e e r" -> "citeseer"
    t = re.sub(r"\b([a-z])\s+(?=[a-z]\b)", r"\1", t)
    return t


def apply_aliases(text: str) -> str:
    t = squeeze_letters(text)
    for k, v in DATASET_ALIASES.items():
        t = t.replace(k, v)
    return t


def load_claims():
    p = Path(CLAIMS_JSON)
    if not p.exists():
        print(f"❌ Missing {CLAIMS_JSON}")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def load_best_text(paper_key: str, claims_fallback: list[str]) -> str:
    for fp in CANDIDATE_TEXT_FILES.get(paper_key, []):
        f = Path(fp)
        if f.exists() and f.stat().st_size > 1000:
            return f.read_text(encoding="utf-8", errors="ignore")
    return "\n".join(claims_fallback)


def split_lines(text: str):
    raw = text.replace("\r", "\n").split("\n")
    lines = []
    for x in raw:
        x = x.strip()
        if len(x) < 5:
            continue
        lines.append(x)
    return lines


def detect_datasets_in_line(line: str):
    t = apply_aliases(line)
    hits = []
    for d in BENCH_DATASETS:
        if d in t:
            hits.append(d)
    return hits


def is_table_like_line(line: str) -> bool:
    """
    Accept only lines that look like table rows:
      - contain | separators, OR
      - have multiple “column gaps” (>=2 occurrences of 2+ spaces)
    Reject normal sentences.
    """
    if "|" in line:
        return True
    if len(re.findall(r"\s{2,}", line)) >= 2:
        return True
    return False


def looks_like_table_header(line: str) -> bool:
    """
    A true header usually contains:
      - at least 2 dataset names
      - and a column label like "method" / "model"
      - and is table-like
    """
    t = apply_aliases(line)
    ds = set(detect_datasets_in_line(t))
    if len(ds) < 2:
        return False
    if not is_table_like_line(line):
        return False
    if ("method" not in t) and ("model" not in t):
        return False
    return True


def header_dataset_order(line: str) -> list[str]:
    """
    Determine dataset order by position in header.
    """
    t = apply_aliases(line)
    pos = []
    for d in BENCH_DATASETS:
        idx = t.find(d)
        if idx != -1:
            pos.append((idx, d))
    pos.sort()
    return [d for _, d in pos]


def row_has_blocklisted_context(row: str) -> bool:
    t = normalize(row)
    return any(w in t for w in ROW_BLOCKLIST)


def extract_numeric_cells(row: str):
    """
    Extract candidate result cells.
    Handles:
      81.5
      81.5±0.7
      81.5 +/- 0.7
      81.5%
    We keep only the primary numbers (ignore ± secondaries).
    """
    # Remove section-like prefixes "6.1 " at the start
    s = row.strip()
    s = re.sub(r"^\s*\d+(?:\.\d+)?\s+", "", s)

    # Capture percent numbers first
    pct = re.findall(r"\b\d{1,3}(?:\.\d+)?\s*%", s)
    pct_vals = []
    for p in pct:
        try:
            v = float(p.replace("%", "").strip())
            if 0.0 <= v <= 100.0:
                pct_vals.append(v)
        except:
            pass

    # Capture plain numbers (for tables without %)
    nums = re.findall(r"\b\d+(?:\.\d+)?\b", s)
    vals = []
    for n in nums:
        try:
            v = float(n)
        except:
            continue
        # skip years
        if 1900 <= v <= 2099 and float(v).is_integer():
            continue
        vals.append(v)

    # If percent values exist, prefer them (tables often show percents)
    if pct_vals:
        return pct_vals, "percent"

    # Otherwise keep only plausible accuracy-like numbers (30..100)
    # This kills 0.01, 1.0, 6.1, 14, 64(features), 400(epochs)
    acc_like = [v for v in vals if 30.0 <= v <= 100.0]
    return acc_like, "number"


# ------------------------ Table Extraction ------------------------
def extract_eval_records_from_tables(text: str, paper_key: str):
    lines = split_lines(text)
    records = []
    headers_found = 0

    i = 0
    while i < len(lines):
        header = lines[i]
        if not looks_like_table_header(header):
            i += 1
            continue

        headers_found += 1
        order = header_dataset_order(header)
        if len(order) < 2:
            i += 1
            continue

        # Read subsequent lines as potential rows
        for j in range(i + 1, min(i + 35, len(lines))):
            row = lines[j]

            # Stop at next header
            if looks_like_table_header(row):
                break

            # Must look like a table row (not a sentence)
            if not is_table_like_line(row):
                continue

            # Block training/setup lines
            if row_has_blocklisted_context(row):
                continue

            vals, vtype = extract_numeric_cells(row)

            # Must have enough values to map at least 2 datasets (strict)
            # (some tables have extra columns, that’s fine)
            if len(vals) < len(order):
                continue

            vals = vals[:len(order)]

            for d, v in zip(order, vals):
                records.append({
                    "paper": paper_key,
                    "dataset": d,
                    "metric": DEFAULT_TABLE_METRIC,
                    "value": float(v),
                    "value_type": vtype,
                    "row": row.strip(),
                    "header": header.strip(),
                })

        i += 1

    # De-dupe
    seen = set()
    uniq = []
    for r in records:
        key = (r["paper"], r["dataset"], r["metric"], r["value"], normalize(r["row"]))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    return uniq, headers_found


def extract_eval_records(doc_text: str, paper_key: str):
    recs, headers_found = extract_eval_records_from_tables(doc_text, paper_key)
    return recs, headers_found


# ------------------------ Matching ------------------------
def match_by_dataset_metric(rec2, rec3):
    by2 = defaultdict(list)
    by3 = defaultdict(list)
    for r in rec2:
        by2[(r["dataset"], r["metric"])].append(r)
    for r in rec3:
        by3[(r["dataset"], r["metric"])].append(r)

    pairs = []
    for key, L2 in by2.items():
        if key not in by3:
            continue
        for a in L2:
            for b in by3[key]:
                pairs.append((a, b))

    # De-dupe by row text pair
    seen = set()
    uniq = []
    for a, b in pairs:
        k = (normalize(a["row"]), normalize(b["row"]), a["dataset"], a["metric"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append((a, b))
    return uniq


# ------------------------ Main ------------------------
def main():
    claims = load_claims()
    if claims is None:
        return

    raw2 = claims.get("paper2", [])
    raw3 = claims.get("paper3", [])

    text2 = load_best_text("paper2", raw2)
    text3 = load_best_text("paper3", raw3)

    rec2, h2 = extract_eval_records(text2, "paper2")
    rec3, h3 = extract_eval_records(text3, "paper3")

    print(f"📌 Raw claims -> paper2: {len(raw2)} | paper3: {len(raw3)}")
    print(f"🧾 Table headers found -> paper2: {h2} | paper3: {h3}")
    print(f"🧾 Eval records extracted (STRICT table) -> paper2: {len(rec2)} | paper3: {len(rec3)}")

    if len(rec2) == 0 or len(rec3) == 0:
        print("❌ 0 strict table eval records on one side.")
        print("   This means the result tables are not appearing as clean text lines in your inputs.")
        Path("outputs/cross_paper_contradictions.json").write_text("[]", encoding="utf-8")
        return

    pairs = match_by_dataset_metric(rec2, rec3)

    out = []
    for a, b in pairs:
        d = float(a["value"]) - float(b["value"])
        flag = abs(d) >= 1.0  # accuracy-point difference

        out.append({
            "dataset": a["dataset"],
            "metric": a["metric"],
            "paper2_value": a["value"],
            "paper3_value": b["value"],
            "delta_p2_minus_p3": round(d, 4),
            "potential_contradiction": flag,
            "reason": f"Δ={d:.4f} (threshold=1.0)",
            "paper2_header": a["header"],
            "paper2_row": a["row"],
            "paper3_header": b["header"],
            "paper3_row": b["row"],
        })

    out.sort(key=lambda r: (not r["potential_contradiction"], -abs(r["delta_p2_minus_p3"])))

    Path("outputs/cross_paper_contradictions.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"✅ Saved {len(out)} matched pairs to outputs/cross_paper_contradictions.json")

    print("\n--- Top 5 matches ---")
    for r in out[:5]:
        tag = "⚠️ FLAG" if r["potential_contradiction"] else "OK"
        print(f"{tag} | {r['dataset']} | {r['metric']} | p2={r['paper2_value']} | p3={r['paper3_value']} | {r['reason']}")
        print("P2 row:", r["paper2_row"][:140], "...")
        print("P3 row:", r["paper3_row"][:140], "...")
        print("---")


if __name__ == "__main__":
    main()