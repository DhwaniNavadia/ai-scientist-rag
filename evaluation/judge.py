"""evaluation/judge.py — LLM-as-Judge for pairwise hypothesis evaluation.

Compares a system hypothesis against a baseline hypothesis for the same
research gap.  Supports both Anthropic (Claude) and OpenAI backends:

  * If ``ANTHROPIC_API_KEY`` is set → uses ``claude-opus-4-5``.
  * Otherwise             → falls back to ``gpt-4o-mini`` (same model as the
                             main pipeline).

Retry logic: up to ``max_retries`` additional attempts with exponential
back-off (1s → 2s → 4s …) on any API or parsing error.  Raises
:class:`ValueError` if a valid result cannot be obtained within the budget.
"""

import json
import logging
import os
import time
from typing import Dict

logger = logging.getLogger("evaluation.judge")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (from environment — no hard-coded keys)
# ─────────────────────────────────────────────────────────────────────────────

_ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
_JUDGE_MODEL_ANTHROPIC: str = os.getenv("JUDGE_MODEL", "claude-opus-4-5")
_JUDGE_MODEL_OPENAI: str    = os.getenv("JUDGE_MODEL", "gpt-4o-mini")

# ─────────────────────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT: str = """You are an expert scientific evaluator.

Your task: compare two research hypotheses generated for the same research gap
and determine which is better.

Evaluate each hypothesis on these four dimensions (equally weighted):
  1. Novelty        — How original and creative is the hypothesis?
  2. Specificity    — How precise and unambiguous are the claims?
  3. Scientific rigor — How testable and grounded in existing knowledge?
  4. Actionability  — How practical is it to design an experiment to test it?

Return ONLY valid JSON — no preamble, no markdown fences, no explanation
outside the JSON. Use exactly this schema:
{
  "winner": "system",
  "system_score": 7.5,
  "baseline_score": 5.0,
  "reasoning": "brief explanation of the decision",
  "keep_system": true
}

Rules:
  - "winner" must be one of: "system", "baseline", "tie"
  - scores must be floats in [0, 10]
  - "keep_system" is true when the system hypothesis is worth keeping for
    further research (score >= 6.0 or winner == "system")
"""

_USER_TEMPLATE: str = """Research gap: {gap_description}

--- System hypothesis ---
{system_text}

--- Baseline hypothesis ---
{baseline_text}

Evaluate both and return your verdict as JSON."""


# ─────────────────────────────────────────────────────────────────────────────
# Backend helpers
# ─────────────────────────────────────────────────────────────────────────────

def _call_anthropic(user_message: str) -> str:
    """Call Anthropic Claude and return raw text response.

    Args:
        user_message: The user-turn content for the judge.

    Returns:
        Raw text from the model.

    Raises:
        ImportError:  If ``anthropic`` package is not installed.
        Exception:    Any Anthropic SDK error.
    """
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError(
            "anthropic package is required when ANTHROPIC_API_KEY is set. "
            "Run: pip install anthropic>=0.40.0"
        ) from exc

    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=_JUDGE_MODEL_ANTHROPIC,
        max_tokens=512,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _call_openai(user_message: str) -> str:
    """Call OpenAI and return raw text response.

    Args:
        user_message: The user-turn content for the judge.

    Returns:
        Raw text from the model.
    """
    from openai import OpenAI
    from ai_scientist.config import OPENAI_API_KEY

    client = OpenAI(api_key=OPENAI_API_KEY)
    resp = client.chat.completions.create(
        model=_JUDGE_MODEL_OPENAI,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        max_tokens=512,
        temperature=0.2,
    )
    return resp.choices[0].message.content or ""


def _call_judge_api(user_message: str) -> str:
    """Dispatch to the appropriate LLM backend.

    Uses Anthropic when ``ANTHROPIC_API_KEY`` is present; falls back to OpenAI.

    Args:
        user_message: Formatted user prompt for the judge.

    Returns:
        Raw text response from the model.
    """
    if _ANTHROPIC_API_KEY:
        logger.debug("Using Anthropic (%s) as judge.", _JUDGE_MODEL_ANTHROPIC)
        return _call_anthropic(user_message)
    logger.debug("Using OpenAI (%s) as judge.", _JUDGE_MODEL_OPENAI)
    return _call_openai(user_message)


# ─────────────────────────────────────────────────────────────────────────────
# Response parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_judge_response(raw: str) -> Dict:
    """Parse and strictly validate a judge JSON response.

    Args:
        raw: Raw text returned by the LLM.

    Returns:
        Validated dict with keys: ``winner``, ``system_score``,
        ``baseline_score``, ``reasoning``, ``keep_system``.

    Raises:
        ValueError: If the text is not valid JSON, is missing required fields,
                    or contains an invalid ``winner`` value.
    """
    # Strip any accidental markdown code fences.
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence line and optional closing fence.
        inner = lines[1:-1] if lines and lines[-1].strip().startswith("```") else lines[1:]
        text = "\n".join(inner)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Judge returned invalid JSON: {exc!r}. Raw text: {raw[:200]!r}"
        ) from exc

    # Required field presence.
    required = {"winner", "system_score", "baseline_score", "reasoning", "keep_system"}
    missing = required - set(data.keys())
    if missing:
        raise ValueError(
            f"Judge response missing required fields: {missing}. Got: {list(data.keys())}"
        )

    # Validate winner value.
    if data["winner"] not in {"system", "baseline", "tie"}:
        raise ValueError(
            f"Invalid winner value {data['winner']!r}. "
            "Must be one of: 'system', 'baseline', 'tie'."
        )

    return {
        "winner":         str(data["winner"]),
        "system_score":   float(data["system_score"]),
        "baseline_score": float(data["baseline_score"]),
        "reasoning":      str(data["reasoning"]),
        "keep_system":    bool(data["keep_system"]),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def judge(
    system_hyp:      Dict,
    baseline_hyp:    Dict,
    gap_description: str,
    max_retries:     int = 3,
) -> Dict:
    """Run the LLM judge to compare one system hypothesis against a baseline.

    Args:
        system_hyp:      System hypothesis dict.  Must contain
                         ``"hypothesis_text"`` (pipeline schema).
        baseline_hyp:    Baseline hypothesis dict.  Must contain
                         ``"hypothesis"`` (baseline schema).
        gap_description: Plain-text description of the research gap.
        max_retries:     Maximum additional retries after the first attempt
                         (default: 3, meaning up to 4 total attempts).

    Returns:
        Dict with keys::

            {
              "winner":         "system" | "baseline" | "tie",
              "system_score":   float,   # 0–10
              "baseline_score": float,   # 0–10
              "reasoning":      str,
              "keep_system":    bool,
            }

    Raises:
        ValueError: If a valid verdict cannot be obtained after all attempts.
    """
    system_text   = system_hyp.get("hypothesis_text") or system_hyp.get("hypothesis", "")
    baseline_text = baseline_hyp.get("hypothesis")    or baseline_hyp.get("hypothesis_text", "")

    user_message = _USER_TEMPLATE.format(
        gap_description=gap_description,
        system_text=system_text,
        baseline_text=baseline_text,
    )

    last_error: Exception = ValueError("No attempts made")

    total_attempts = max_retries + 1
    for attempt in range(total_attempts):
        if attempt > 0:
            wait_secs = 2 ** (attempt - 1)   # 1, 2, 4 … seconds
            logger.warning(
                "Retrying judge (attempt %d/%d) after %ds back-off.",
                attempt + 1, total_attempts, wait_secs,
            )
            time.sleep(wait_secs)

        try:
            logger.debug(
                "Judge attempt %d — gap: %.60s…", attempt + 1, gap_description
            )
            raw    = _call_judge_api(user_message)
            result = _parse_judge_response(raw)
            logger.debug(
                "Judge verdict: winner=%s  system=%.1f  baseline=%.1f",
                result["winner"], result["system_score"], result["baseline_score"],
            )
            return result

        except ValueError as exc:
            last_error = exc
            logger.warning("Invalid judge response (attempt %d): %s", attempt + 1, exc)
        except Exception as exc:
            last_error = exc
            logger.warning("API error (attempt %d): %s", attempt + 1, exc)

    raise ValueError(
        f"Judge failed after {total_attempts} attempt(s). Last error: {last_error}"
    ) from last_error
