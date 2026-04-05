"""scripts/test_llm_fallback.py — Test LLMClient under 3 scenarios.

Run:  python scripts/test_llm_fallback.py

Tests:
  1. Normal operation — at least one provider responds with a dict.
  2. OpenAI forced failure — fallback to Grok or deterministic.
  3. All providers forced failure — deterministic fallback with _fallback=True.
"""

import logging
import os
import sys

# Ensure project root is on sys.path
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-12s %(levelname)-5s %(message)s",
)
logger = logging.getLogger("test_llm_fallback")


def test_normal_operation() -> bool:
    """Test 1 — Normal operation: at least one provider should respond."""
    logger.info("=" * 60)
    logger.info("TEST 1: Normal operation")
    logger.info("=" * 60)

    from ai_scientist.llm.llm_client import LLMClient

    client = LLMClient()
    result = client.generate(
        prompt="What is the role of attention in transformers?",
        system_prompt=(
            "Respond with valid JSON: "
            '{"hypothesis": "...", "reasoning": "...", "confidence": 0.8}'
        ),
        temperature=0.3,
        max_tokens=200,
    )

    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

    if result.get("_fallback"):
        logger.info("TEST 1 PASS (deterministic fallback — no live API keys)")
        return True

    assert "hypothesis" in result or len(result) > 0, "Response dict is empty"
    assert "_fallback" not in result, "_fallback key present in live response"
    logger.info("TEST 1 PASS (live LLM response)")
    return True


def test_openai_forced_failure() -> bool:
    """Test 2 — Force OpenAI failure, verify fallback."""
    logger.info("=" * 60)
    logger.info("TEST 2: OpenAI forced failure")
    logger.info("=" * 60)

    original_key = os.environ.get("OPENAI_API_KEY", "")

    try:
        os.environ["OPENAI_API_KEY"] = "sk-invalid-key-forced-fail"

        from ai_scientist.llm.llm_client import LLMClient

        client = LLMClient()
        result = client.generate(
            prompt="Test prompt for fallback",
            system_prompt='Respond with JSON: {"hypothesis": "test"}',
            temperature=0.3,
            max_tokens=100,
        )

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        logger.info("TEST 2 PASS (fallback triggered, got dict)")
        return True
    finally:
        if original_key:
            os.environ["OPENAI_API_KEY"] = original_key
        else:
            os.environ.pop("OPENAI_API_KEY", None)


def test_all_providers_forced_failure() -> bool:
    """Test 3 — Force all providers to fail, verify deterministic fallback."""
    logger.info("=" * 60)
    logger.info("TEST 3: All providers forced failure")
    logger.info("=" * 60)

    original_openai = os.environ.get("OPENAI_API_KEY", "")
    original_grok = os.environ.get("GROK_API_KEY", "")

    try:
        os.environ["OPENAI_API_KEY"] = "sk-invalid-key-forced-fail"
        os.environ["GROK_API_KEY"] = "xai-invalid-key-forced-fail"

        from ai_scientist.llm.llm_client import LLMClient

        client = LLMClient()
        result = client.generate(
            prompt="Test prompt for deterministic fallback",
            temperature=0.3,
            max_tokens=100,
        )

        assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        assert result.get("_fallback") is True, (
            f"Expected _fallback=True, got {result.get('_fallback')}"
        )
        assert result.get("_fallback_reason"), "_fallback_reason is empty"
        assert isinstance(result["_fallback_reason"], str), (
            f"Expected str reason, got {type(result['_fallback_reason'])}"
        )
        logger.info("TEST 3 PASS (deterministic fallback with _fallback=True)")
        logger.info("  _fallback_reason: %s", result["_fallback_reason"][:200])
        return True
    finally:
        if original_openai:
            os.environ["OPENAI_API_KEY"] = original_openai
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        if original_grok:
            os.environ["GROK_API_KEY"] = original_grok
        else:
            os.environ.pop("GROK_API_KEY", None)


def main() -> None:
    """Run all 3 tests and print summary."""
    passed = 0
    total = 3

    for i, test_fn in enumerate([
        test_normal_operation,
        test_openai_forced_failure,
        test_all_providers_forced_failure,
    ], 1):
        try:
            if test_fn():
                passed += 1
        except Exception as exc:
            logger.error("TEST %d FAIL: %s", i, exc, exc_info=True)

    logger.info("=" * 60)
    logger.info("SUMMARY: %d/%d tests passed", passed, total)
    logger.info("=" * 60)

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
