from pathlib import Path
import json
import re
import PyPDF2


# -----------------------------
# Config
# -----------------------------
PAPER2_PATH = "data/papers/paper2.pdf"
PAPER3_PATH = "data/papers/paper3.pdf"

OUT_PATH = "outputs/cross_paper_claims.json"

# claim-style verbs / phrases
CLAIM_CUES = [
    "we propose", "we present", "we introduce", "we develop", "we show",
    "we demonstrate", "we find", "we achieve", "we outperform", "we improve",
    "our model", "our method", "our approach", "we validate", "we evaluate",
    "we compare", "we report"
]

# remove obvious junk
JUNK_PATTERNS = [
    "university", "department", "email", "@", "published as",
    "conference paper", "iclr", "proceedings", "table", "figure",
    "keywords", "index terms", "copyright",
    "cora", "citeseer", "pubmed", "ppi",  # dataset tables often contain these alone
    "nodes", "edges", "#", "task", "transductive", "inductive"
]


# -----------------------------
# Helpers
# -----------------------------
def read_pdf_text(pdf_path: str) -> str:
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(f"Missing file: {pdf_path}")

    reader = PyPDF2.PdfReader(str(p))
    pages = []
    for page in reader.pages:
        txt = page.extract_text() or ""
        pages.append(txt)

    return "\n".join(pages)


def clean_text(t: str) -> str:
    # remove hyphenation breaks like "classi-\nﬁcation" -> "classification"
    t = re.sub(r"-\s*\n", "", t)
    t = re.sub(r"\n+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def split_sentences(text: str):
    # simple sentence splitting (MVP)
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def looks_like_junk(s: str) -> bool:
    s2 = s.lower()
    if len(s2) < 40:
        return True
    if sum(ch.isdigit() for ch in s2) > 8:   # heavy numeric lines = tables
        return True
    if any(p in s2 for p in JUNK_PATTERNS):
        # BUT allow if it's still a real claim sentence (contains a cue)
        if any(cue in s2 for cue in CLAIM_CUES):
            return False
        return True
    return False


def is_claim(s: str) -> bool:
    s2 = s.lower()
    if looks_like_junk(s):
        return False
    return any(cue in s2 for cue in CLAIM_CUES)


def extract_claims(pdf_path: str):
    raw = read_pdf_text(pdf_path)
    text = clean_text(raw)
    sents = split_sentences(text)

    claims = []
    for s in sents:
        if is_claim(s):
            claims.append(s)

    # dedupe
    seen = set()
    uniq = []
    for c in claims:
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)

    return uniq


# -----------------------------
# Main
# -----------------------------
def main():
    Path("outputs").mkdir(exist_ok=True)

    paper2_claims = extract_claims(PAPER2_PATH)
    paper3_claims = extract_claims(PAPER3_PATH)

    print(f"✅ paper2: extracted {len(paper2_claims)} claims")
    print(f"✅ paper3: extracted {len(paper3_claims)} claims")

    data = {
        "paper2": paper2_claims,
        "paper3": paper3_claims
    }

    Path(OUT_PATH).write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"✅ Saved {OUT_PATH}")


if __name__ == "__main__":
    main()
