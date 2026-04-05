from pathlib import Path
import json
import re

# --------- CONFIG ---------
CANDIDATE_PAPER2_PATHS = [r"data\papers\paper2.pdf"]
CANDIDATE_PAPER3_PATHS = [r"data\papers\paper3.pdf"]

OUT_PATH = Path("outputs/cross_paper_claims.json")

KEEP_SECTIONS = [
    "experiment", "experiments", "experimental",
    "evaluation", "results", "discussion", "conclusion", "conclusions",
    "analysis", "ablation", "limitations"
]

DROP_SECTIONS = [
    "related work", "background", "preliminaries", "references",
    "appendix", "supplementary", "acknowledgments", "acknowledgements"
]

CLAIM_CUES = [
    "outperform", "outperforms", "improve", "improves", "improved",
    "achieve", "achieves", "achieved", "state-of-the-art", "sota",
    "we show", "we demonstrate", "we find", "results show", "results indicate",
    "significant", "consistent", "robust", "scalable", "efficient", "linear",
    "accuracy", "f1", "auc", "error", "loss", "runtime", "time", "memory",
    "attention", "convolution", "graph", "node classification"
]

# --------- PDF TEXT EXTRACTION ---------
def extract_pdf_text(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        print("❌ Missing dependency: pypdf")
        print("Run: pip install pypdf")
        return ""

    try:
        reader = PdfReader(str(pdf_path))
        chunks = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            if txt.strip():
                chunks.append(txt)
        return "\n".join(chunks)
    except Exception as e:
        print(f"❌ Failed to read PDF {pdf_path}: {e}")
        return ""


def read_first_existing(paths):
    for p in paths:
        pp = Path(p)
        if pp.exists():
            if pp.suffix.lower() == ".pdf":
                return extract_pdf_text(pp)
            return pp.read_text(encoding="utf-8", errors="ignore")
    return None


# --------- TEXT UTILS ---------
def normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_heading(line: str) -> bool:
    l = line.strip()
    if len(l) < 3:
        return False

    if re.match(r"^\d+(\.\d+)*\s+[A-Za-z][A-Za-z \-]{2,}$", l):
        return True

    if l.isupper() and len(l) <= 60 and any(c.isalpha() for c in l):
        return True

    if len(l) <= 40 and re.match(r"^[A-Z][A-Za-z \-]{2,}$", l) and "." not in l:
        return True

    return False


def heading_name(line: str) -> str:
    l = line.strip()
    l = re.sub(r"^\d+(\.\d+)*\s+", "", l)
    return l.strip().lower()


def looks_like_table_or_figure(line: str) -> bool:
    """
    Filter table rows, figure captions, and diagram text blocks.
    """
    s = line.strip()
    s2 = normalize(s)

    # obvious junk cues
    if "published as a conference paper" in s2:
        return True
    if "iclr" in s2 and "published as" in s2:
        return True
    if s2.startswith("figure") or "figure " in s2 or "table " in s2:
        return True

    # dataset header-ish
    if any(h in s2 for h in ["nodes edges classes", "dataset type nodes", "label rate", "# nodes", "# edges"]):
        return True

    # many numbers/percentages -> likely table
    nums = re.findall(r"\d+(?:\.\d+)?%?", s2)
    if len(nums) >= 8:
        return True

    # lots of short tokens (table-like columns)
    tokens = re.split(r"\s+", s)
    if len(tokens) >= 12:
        short = sum(1 for t in tokens if len(t) <= 3)
        if short / max(1, len(tokens)) > 0.45:
            return True

    # diagram-like: many single-letter tokens X1 Y2 Z3 etc.
    if re.search(r"\b[xyz]\d+\b", s2) and ("layer" in s2 or "input" in s2 or "output" in s2):
        return True

    return False


def sentence_split(text: str):
    text = re.sub(r"\s+", " ", text).strip()
    # split on sentence boundaries; also break on " . " artifacts
    parts = re.split(r"(?<=[\.\?\!])\s+", text)
    out = []
    for p in parts:
        p = p.strip()
        if len(p) < 25:
            continue
        out.append(p)
    return out


def has_claim_signal(s: str) -> bool:
    s2 = normalize(s)

    # ignore metadata blobs
    if "university" in s2 and "abstract" in s2:
        return False

    # drop references-like stuff
    if "proceedings" in s2 or "arxiv" in s2:
        return False

    # must look like a sentence (has verb-ish cues or punctuation)
    if "." not in s and "we " not in s2 and "shows" not in s2 and "demonstrate" not in s2:
        return False

    # keep if cue words
    if any(c in s2 for c in CLAIM_CUES):
        return True

    # keep if percentage present
    if re.search(r"\d+(?:\.\d+)?\s*%", s2):
        return True

    # keep if non-year numeric metric present (and not table-like)
    nums = re.findall(r"\d+(?:\.\d+)?", s2)
    for n in nums:
        try:
            v = float(n)
        except:
            continue
        if 1900 <= v <= 2099 and float(v).is_integer():
            continue
        if v < 1900:
            return True

    return False


def extract_sectioned_claims(full_text: str, max_claims: int = 60):
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]

    # remove obvious table/figure lines early
    lines = [ln for ln in lines if not looks_like_table_or_figure(ln)]

    current = "unknown"
    buckets = {}

    for ln in lines:
        if is_heading(ln):
            current = heading_name(ln)
            continue
        buckets.setdefault(current, []).append(ln)

    kept_text_chunks = []
    for sec, sec_lines in buckets.items():
        sec_norm = normalize(sec)
        if any(d in sec_norm for d in DROP_SECTIONS):
            continue
        if any(k in sec_norm for k in KEEP_SECTIONS):
            kept_text_chunks.append(" ".join(sec_lines))

    if not kept_text_chunks:
        kept_text_chunks = [" ".join(lines)]

    claims = []
    for chunk in kept_text_chunks:
        for sent in sentence_split(chunk):
            if looks_like_table_or_figure(sent):
                continue
            if has_claim_signal(sent):
                claims.append(sent)

    # de-dup
    seen = set()
    uniq = []
    for c in claims:
        key = normalize(c)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    # sort by "claiminess": prefer sentences with key cues and decent length
    def score_sentence(s: str) -> float:
        s2 = normalize(s)
        score = 0.0
        if "we " in s2:
            score += 1.0
        if any(k in s2 for k in ["outperform", "improv", "achiev", "result", "accuracy", "runtime", "scalable"]):
            score += 1.0
        if re.search(r"\d+(?:\.\d+)?\s*%", s2):
            score += 1.0
        score += min(len(s2) / 200.0, 1.0)  # length bonus capped
        return score

    uniq.sort(key=score_sentence, reverse=True)
    return uniq[:max_claims]


def main():
    text2 = read_first_existing(CANDIDATE_PAPER2_PATHS)
    text3 = read_first_existing(CANDIDATE_PAPER3_PATHS)

    if not text2:
        print("❌ Could not extract paper2 text. Tried:")
        for p in CANDIDATE_PAPER2_PATHS:
            print("  -", p)
        return

    if not text3:
        print("❌ Could not extract paper3 text. Tried:")
        for p in CANDIDATE_PAPER3_PATHS:
            print("  -", p)
        return

    claims2 = extract_sectioned_claims(text2, max_claims=60)
    claims3 = extract_sectioned_claims(text3, max_claims=60)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"paper2": claims2, "paper3": claims3}, indent=2),
        encoding="utf-8"
    )

    print(f"✅ Wrote {len(claims2)} paper2 claims + {len(claims3)} paper3 claims to {OUT_PATH}")

    print("\n--- Preview paper2 (top 5) ---")
    for s in claims2[:5]:
        print("-", s[:140], "...")
    print("\n--- Preview paper3 (top 5) ---")
    for s in claims3[:5]:
        print("-", s[:140], "...")


if __name__ == "__main__":
    main()
