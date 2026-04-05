"""ai_scientist/llm/llm_client.py — Production-grade multi-provider LLM fallback.

Provider priority:  OpenAI  →  Grok (xAI)  →  deterministic fallback.

``generate()`` ALWAYS returns a ``dict``, NEVER raises in production, and
NEVER returns the string ``"[Generation failed]"``.

Environment variables (loaded via ``python-dotenv`` at import time):
    OPENAI_API_KEY   — required for OpenAI provider; skipped if missing
    GROK_API_KEY     — required for Grok provider; skipped if missing
    OPENAI_MODEL     — optional, default ``gpt-4.1-mini``
    GROK_MODEL       — optional, default ``grok-2-latest``
    LLM_LOG_LEVEL    — optional, default ``INFO``
"""

import json
import logging
import os
import re
import time
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log_level = os.getenv("LLM_LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("llm_client")
logger.setLevel(getattr(logging, _log_level, logging.INFO))

# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class LLMParseError(Exception):
    """Raised when an LLM response cannot be parsed as JSON."""

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__(f"Failed to parse LLM response as JSON: {raw_text[:200]!r}")


class LLMAllProvidersFailedError(Exception):
    """Raised only if the deterministic fallback itself somehow errors."""
    pass


# ---------------------------------------------------------------------------
# JSON safety helper
# ---------------------------------------------------------------------------


def _parse_json_safe(text: str) -> dict:
    """Parse *text* as JSON with progressive fallback.

    1. ``json.loads(text.strip())``
    2. Extract first ``{…}`` block via regex and parse that.
    3. Raise ``LLMParseError`` if both fail.
    """
    stripped = text.strip()

    # Attempt 1: direct parse
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
        # If it parsed but isn't a dict (e.g. a list), wrap it
        return {"data": result}
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: extract first {…} block
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
            return {"data": result}
        except (json.JSONDecodeError, ValueError):
            pass

    raise LLMParseError(text)


# ---------------------------------------------------------------------------
# strip_code_fences  (moved here so callers can import from one place)
# ---------------------------------------------------------------------------


def strip_code_fences(text: str) -> str:
    """Remove optional ```json … ``` wrappers from LLM output."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------


class LLMClient:
    """Multi-provider LLM client with automatic fallback.

    Provider chain:  OpenAI → Grok (xAI) → deterministic fallback.
    """

    def __init__(self) -> None:
        self._openai_key: str = os.getenv("OPENAI_API_KEY", "").strip()
        self._grok_key: str = os.getenv("GROK_API_KEY", "").strip()
        self._openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self._grok_model: str = os.getenv("GROK_MODEL", "grok-2-latest")

        if not self._openai_key:
            logger.warning("[LLM] OPENAI_API_KEY not set — OpenAI provider will be skipped")
        if not self._grok_key:
            logger.warning("[LLM] GROK_API_KEY not set — Grok provider will be skipped")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model: Optional[str] = None,
    ) -> dict:
        """Call LLM with automatic provider fallback.

        Returns a parsed ``dict``.  **Never raises.  Never returns
        ``"[Generation failed]"``.**

        Priority: OpenAI → Grok → deterministic fallback.
        """
        reasons: List[str] = []

        # --- Provider 1: OpenAI ---
        if self._openai_key:
            result = self._try_openai(prompt, system_prompt, temperature,
                                      max_tokens, model, reasons)
            if result is not None:
                return result
        else:
            reasons.append("OpenAI: API key not configured")

        # --- Provider 2: Grok (xAI) ---
        if self._grok_key:
            result = self._try_grok(prompt, system_prompt, temperature,
                                    max_tokens, model, reasons)
            if result is not None:
                return result
        else:
            reasons.append("Grok: API key not configured")

        # --- Provider 3: Deterministic fallback ---
        return self._deterministic_fallback(prompt, reasons)

    # ------------------------------------------------------------------
    # Provider 1 — OpenAI
    # ------------------------------------------------------------------

    def _try_openai(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
        reasons: List[str],
    ) -> Optional[dict]:
        """Attempt OpenAI. Returns parsed dict on success, None on failure."""
        try:
            import openai
        except ImportError:
            reason = "OpenAI: 'openai' package not installed"
            logger.info("[LLM] %s → trying Grok", reason)
            reasons.append(reason)
            return None

        chosen_model = model_override or self._openai_model
        logger.info("[LLM] Trying OpenAI (%s)", chosen_model)

        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        client = openai.OpenAI(api_key=self._openai_key, timeout=30.0)

        last_exc: Optional[Exception] = None
        for attempt in range(2):
            try:
                resp = client.chat.completions.create(
                    model=chosen_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content or ""
                content = strip_code_fences(content)
                return _parse_json_safe(content)

            except openai.RateLimitError as exc:
                last_exc = exc
                logger.warning("[LLM] OpenAI rate-limit (attempt %d/2): %s", attempt + 1, exc)
            except openai.APITimeoutError as exc:
                last_exc = exc
                logger.warning("[LLM] OpenAI timeout (attempt %d/2): %s", attempt + 1, exc)
            except openai.APIStatusError as exc:
                if exc.status_code == 429 or exc.status_code >= 500:
                    last_exc = exc
                    logger.warning("[LLM] OpenAI status %d (attempt %d/2): %s",
                                   exc.status_code, attempt + 1, exc)
                else:
                    # Non-retryable status (e.g. 401, 403)
                    reason = f"OpenAI: HTTP {exc.status_code} — {exc}"
                    logger.info("[LLM] %s → trying Grok", reason)
                    reasons.append(reason)
                    return None
            except LLMParseError as exc:
                last_exc = exc
                logger.warning("[LLM] OpenAI JSON parse failed (attempt %d/2): %s",
                               attempt + 1, str(exc)[:120])
            except Exception as exc:
                last_exc = exc
                logger.warning("[LLM] OpenAI unexpected error (attempt %d/2): %s",
                               attempt + 1, exc)

            if attempt < 1:
                time.sleep(2)

        reason = f"OpenAI: exhausted 2 attempts — {last_exc}"
        logger.info("[LLM] OpenAI failed: %s → trying Grok", reason)
        reasons.append(reason)
        return None

    # ------------------------------------------------------------------
    # Provider 2 — Grok (xAI)
    # ------------------------------------------------------------------

    def _try_grok(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
        reasons: List[str],
    ) -> Optional[dict]:
        """Attempt Grok via httpx. Returns parsed dict on success, None on failure."""
        try:
            import httpx
        except ImportError:
            reason = "Grok: 'httpx' package not installed"
            logger.info("[LLM] %s → using deterministic fallback", reason)
            reasons.append(reason)
            return None

        chosen_model = model_override or self._grok_model
        logger.info("[LLM] Trying Grok (%s)", chosen_model)

        messages: list = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._grok_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = httpx.post(
                "https://api.x.ai/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=30.0,
            )
            if resp.status_code < 200 or resp.status_code >= 300:
                reason = f"Grok: HTTP {resp.status_code} — {resp.text[:200]}"
                logger.info("[LLM] Grok failed: %s → using deterministic fallback", reason)
                reasons.append(reason)
                return None

            body = resp.json()
            content = body["choices"][0]["message"]["content"]
            content = strip_code_fences(content)
            return _parse_json_safe(content)

        except httpx.TimeoutException as exc:
            reason = f"Grok: timeout — {exc}"
            logger.info("[LLM] Grok failed: %s → using deterministic fallback", reason)
            reasons.append(reason)
            return None
        except LLMParseError as exc:
            reason = f"Grok: JSON parse failed — {str(exc)[:120]}"
            logger.info("[LLM] Grok failed: %s → using deterministic fallback", reason)
            reasons.append(reason)
            return None
        except (json.JSONDecodeError, KeyError, IndexError) as exc:
            reason = f"Grok: response structure error — {exc}"
            logger.info("[LLM] Grok failed: %s → using deterministic fallback", reason)
            reasons.append(reason)
            return None
        except Exception as exc:
            reason = f"Grok: unexpected error — {exc}"
            logger.info("[LLM] Grok failed: %s → using deterministic fallback", reason)
            reasons.append(reason)
            return None

    # ------------------------------------------------------------------
    # Provider 3 — Deterministic fallback
    # ------------------------------------------------------------------

    def _deterministic_fallback(self, prompt: str, reasons: List[str]) -> dict:
        """Return a well-formed dict that downstream code can consume.

        This method **never fails**.
        """
        combined_reasons = "; ".join(reasons) if reasons else "Unknown"
        logger.info(
            "[LLM] All providers failed. Returning deterministic fallback. Reasons: %s",
            combined_reasons,
        )

        try:
            return {
                "hypothesis": f"Hypothesis pending LLM availability. Gap: {prompt[:120]}",
                "reasoning": "Generated via deterministic fallback — LLM providers unavailable.",
                "confidence": 0.1,
                "novelty_score": 0.1,
                "testability": "Low",
                "_fallback": True,
                "_fallback_reason": combined_reasons,
            }
        except Exception as exc:
            # Should truly never happen, but satisfies the contract
            raise LLMAllProvidersFailedError(
                f"Deterministic fallback itself failed: {exc}"
            ) from exc


# ---------------------------------------------------------------------------
# Module-level convenience — backward compatibility
# ---------------------------------------------------------------------------

_default_client: Optional[LLMClient] = None


def _get_client() -> LLMClient:
    """Lazy singleton so env vars are read once."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


def generate(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    model: Optional[str] = None,
) -> str:
    """Backward-compatible wrapper that returns a **string**.

    Existing callers that do ``raw = llm_generate(…)`` followed by
    ``json.loads(raw)`` continue to work: we serialise the dict back to
    a JSON string so the caller's parse step succeeds unchanged.
    """
    result = _get_client().generate(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    return json.dumps(result)


def has_keys() -> bool:
    """Return True if at least one LLM provider has a configured key."""
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    grok_key = os.getenv("GROK_API_KEY", "").strip()
    # Also check the numbered keys for full backward compat
    for i in range(1, 5):
        if os.getenv(f"OPENAI_API_KEY_{i}", "").strip():
            return True
    return bool(openai_key) or bool(grok_key)
