"""ai_scientist/utils/llm_client.py — Backward-compatibility shim.

All LLM logic now lives in ``ai_scientist.llm.llm_client``.
This module re-exports the public API so any remaining callers keep working.
"""

from ai_scientist.llm.llm_client import (  # noqa: F401
    LLMClient,
    LLMParseError,
    LLMAllProvidersFailedError,
    generate,
    has_keys,
    strip_code_fences,
)
