"""evaluation/baseline.py — Single-agent baseline hypothesis generator.

Generates one hypothesis per research gap using the same LLM API as the main
pipeline.  Results are cached as JSON files under ``outputs/baseline/`` so
repeated runs do not incur redundant API calls.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from ai_scientist.config import OUTPUT_DIR, OPENAI_API_KEY

logger = logging.getLogger("evaluation.baseline")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BASELINE_DIR: Path = OUTPUT_DIR / "baseline"
MODEL: str = "gpt-4o-mini"

SYSTEM_PROMPT: str = (
    "You are a research scientist. Given a research gap, generate a single "
    "testable hypothesis that could address it.  "
    "Your response MUST be valid JSON matching this exact schema — return ONLY "
    "the JSON object, no preamble, no markdown:\n"
    '{"hypothesis": "<2-3 sentence hypothesis>", '
    '"rationale": "<why this is promising>", '
    '"confidence": <float 0.0-1.0>}'
)

USER_TEMPLATE: str = (
    "Research gap: {gap_description}\n\n"
    "Generate a hypothesis to address this gap."
)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_client():
    """Return an OpenAI client using the project API key."""
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


def _chat_complete(
    messages: List[Dict],
    temperature: float = 0.7,
    max_tokens: int = 350,
) -> str:
    """Call OpenAI chat completion with one automatic retry on transient errors.

    Args:
        messages:    Chat messages list in OpenAI format.
        temperature: Sampling temperature.
        max_tokens:  Maximum tokens in the response.

    Returns:
        Raw response content string.
    """
    from openai import RateLimitError, APIError

    client = _get_client()
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content or ""
        except RateLimitError as exc:
            logger.warning("Rate limit (attempt %d): %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(5)
            else:
                raise
        except APIError as exc:
            logger.error("APIError (attempt %d): %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(5)
            else:
                raise
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_baseline(gap_id: str, gap_description: str) -> Dict:
    """Generate a single baseline hypothesis for one research gap.

    Calls the LLM with a zero-shot prompt and parses the JSON response.  Falls
    back to a default placeholder when the LLM returns malformed output.

    Args:
        gap_id:          Identifier matching the pipeline gap (e.g. ``"G1"``).
        gap_description: Full text description of the research gap.

    Returns:
        Dict matching the baseline output schema::

            {
              "gap_id": str,
              "gap_description": str,
              "hypothesis": str,
              "rationale": str,
              "confidence": float,
              "generated_by": "baseline",
              "timestamp": ISO8601 str,
            }
    """
    logger.info("Generating baseline hypothesis for gap %s", gap_id)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": USER_TEMPLATE.format(gap_description=gap_description)},
    ]

    raw = ""
    parsed: Dict = {}
    try:
        raw = _chat_complete(messages)
        # Strip accidental markdown fences
        clean = raw.strip()
        if clean.startswith("```"):
            lines = clean.splitlines()
            clean = "\n".join(
                lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
            )
        parsed = json.loads(clean)
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning(
            "Failed to parse baseline response for %s (%s). Raw: %r",
            gap_id, exc, raw[:200],
        )

    return {
        "gap_id":          gap_id,
        "gap_description": gap_description,
        "hypothesis":      parsed.get(
            "hypothesis",
            f"Further investigation of the following gap is needed: {gap_description[:120]}",
        ),
        "rationale":       parsed.get("rationale", "No rationale generated."),
        "confidence":      float(max(0.0, min(1.0, parsed.get("confidence", 0.5)))),
        "generated_by":    "baseline",
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


def run_all_baselines(gaps: List[Dict]) -> List[Dict]:
    """Generate (or load cached) baseline hypotheses for every gap.

    Already-generated baselines are loaded from disk to avoid redundant API
    calls.  Results are written atomically to
    ``outputs/baseline/<gap_id>_baseline.json``.

    Args:
        gaps: List of gap dicts from ``gaps_actionable.json``.  Each entry must
              have ``"gap_id"`` and at least one of ``"gap_text"`` /
              ``"gap_statement"`` / ``"actionable_direction"``.

    Returns:
        List of baseline output dicts, one per gap.
    """
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    results: List[Dict] = []

    for gap in gaps:
        gap_id = gap.get("gap_id", "")
        gap_text = gap.get("gap_text") or gap.get("gap_statement", "")
        direction = gap.get("actionable_direction", "")
        description = f"{gap_text} {direction}".strip()

        cache_path = BASELINE_DIR / f"{gap_id}_baseline.json"

        # Try loading cached result.
        if cache_path.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                logger.info("Loaded cached baseline for gap %s", gap_id)
                results.append(cached)
                continue
            except json.JSONDecodeError:
                logger.warning("Corrupt cache for %s — regenerating.", gap_id)

        # Generate fresh baseline.
        result = generate_baseline(gap_id, description)

        # Atomic write.
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cache_path)
        logger.info("Saved baseline for gap %s → %s", gap_id, cache_path)

        results.append(result)

    return results
