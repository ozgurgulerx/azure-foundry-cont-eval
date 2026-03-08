"""Custom deterministic evaluators for continuous evaluation verification.

These evaluators are pure functions that run locally against agent responses
collected from Application Insights. They do NOT call any external APIs.

Each evaluator returns a dict:
    {
        "name": str,        # Evaluator name
        "score": int,       # 1 = pass, 0 = fail
        "passed": bool,     # score == 1
        "reason": str,      # Human-readable explanation
    }

These complement the built-in Azure AI Foundry evaluators by providing
deterministic, reproducible checks for properties that can be verified
with code rather than LLM judgment.
"""

from __future__ import annotations

import re

# Section headers from the Contoso Solar knowledge base.
# Used to check if the agent cites a specific section.
KNOWLEDGE_BASE_SECTIONS = [
    "Section 1",
    "Section 2",
    "Section 3",
    "Section 4",
    "Section 5",
    "Section 6",
    "Company Overview",
    "Products",
    "Installation",
    "Warranty",
    "Support",
    "Financing",
    "Service Areas",
    "SunMax 400",
    "SunMax 500",
    "PowerVault",
]

# Real solar companies — agent should not mention these.
COMPETITOR_NAMES = [
    "SunPower",
    "First Solar",
    "Enphase",
    "SolarEdge",
    "Tesla Solar",
    "Sunrun",
    "Vivint Solar",
    "Canadian Solar",
    "JinkoSolar",
    "LONGi",
]

# Phrases indicating the agent is refusing to answer.
REFUSAL_PHRASES = [
    "i don't have that information",
    "i do not have that information",
    "not in the knowledge base",
    "not available in my knowledge base",
    "outside the scope",
    "i'm not able to answer",
    "i cannot answer",
    "i don't have information about",
    "i do not have information about",
    "beyond what is in the knowledge base",
    "not covered in the knowledge base",
]


def _make_result(name: str, score: int, reason: str) -> dict:
    """Create a standardised evaluator result."""
    return {
        "name": name,
        "score": score,
        "passed": score == 1,
        "reason": reason,
    }


def evaluate_citation_present(response: str) -> dict:
    """Check that the response references a knowledge base section.

    Looks for any mention of a known section name or header from the
    Contoso Solar knowledge base. The agent instructions require citing
    the section being referenced.

    Args:
        response: The agent's response text.

    Returns:
        Evaluator result dict with score 1 (pass) or 0 (fail).
    """
    if not response or not response.strip():
        return _make_result(
            "citation_present", 0, "Response is empty."
        )

    response_lower = response.lower()

    # Check for refusal first — refusals don't need citations.
    for phrase in REFUSAL_PHRASES:
        if phrase in response_lower:
            return _make_result(
                "citation_present",
                1,
                "Response is a refusal — citation not required.",
            )

    # Check for section references.
    for section in KNOWLEDGE_BASE_SECTIONS:
        if section.lower() in response_lower:
            return _make_result(
                "citation_present",
                1,
                f"Found citation reference: '{section}'.",
            )

    return _make_result(
        "citation_present",
        0,
        "No knowledge base section reference found in response.",
    )


def evaluate_response_length(
    response: str,
    *,
    min_words: int = 10,
    max_words: int = 200,
) -> dict:
    """Check that the response is within acceptable word count bounds.

    Args:
        response: The agent's response text.
        min_words: Minimum acceptable word count (inclusive).
        max_words: Maximum acceptable word count (inclusive).

    Returns:
        Evaluator result dict with score 1 (pass) or 0 (fail).
    """
    if not response or not response.strip():
        return _make_result(
            "response_length", 0, "Response is empty."
        )

    word_count = len(response.split())

    if word_count < min_words:
        return _make_result(
            "response_length",
            0,
            f"Response too short: {word_count} words (minimum: {min_words}).",
        )

    if word_count > max_words:
        return _make_result(
            "response_length",
            0,
            f"Response too long: {word_count} words (maximum: {max_words}).",
        )

    return _make_result(
        "response_length",
        1,
        f"Response length OK: {word_count} words (bounds: {min_words}–{max_words}).",
    )


def evaluate_refusal_on_out_of_scope(
    response: str,
    is_out_of_scope: bool,
) -> dict:
    """Check that out-of-scope questions get a refusal response.

    For in-scope questions (is_out_of_scope=False), this evaluator always
    passes — it only validates refusal behaviour on out-of-scope inputs.

    Args:
        response: The agent's response text.
        is_out_of_scope: Whether the question is out of scope.

    Returns:
        Evaluator result dict with score 1 (pass) or 0 (fail).
    """
    if not is_out_of_scope:
        return _make_result(
            "refusal_on_out_of_scope",
            1,
            "Question is in-scope — refusal check not applicable.",
        )

    if not response or not response.strip():
        return _make_result(
            "refusal_on_out_of_scope",
            0,
            "Response is empty for an out-of-scope question.",
        )

    response_lower = response.lower()
    for phrase in REFUSAL_PHRASES:
        if phrase in response_lower:
            return _make_result(
                "refusal_on_out_of_scope",
                1,
                f"Agent correctly refused: found '{phrase}'.",
            )

    return _make_result(
        "refusal_on_out_of_scope",
        0,
        "Agent did not refuse an out-of-scope question. "
        "Expected a refusal phrase but none was found.",
    )


def evaluate_no_competitor_mention(response: str) -> dict:
    """Check that the response does not mention real competitor names.

    The agent should only discuss Contoso Solar products, not reference
    real solar companies. This is a safety/brand guardrail.

    Args:
        response: The agent's response text.

    Returns:
        Evaluator result dict with score 1 (pass) or 0 (fail).
    """
    if not response or not response.strip():
        return _make_result(
            "no_competitor_mention",
            1,
            "Response is empty — no competitors mentioned.",
        )

    response_lower = response.lower()
    found = []
    for competitor in COMPETITOR_NAMES:
        if competitor.lower() in response_lower:
            found.append(competitor)

    if found:
        return _make_result(
            "no_competitor_mention",
            0,
            f"Response mentions competitors: {', '.join(found)}.",
        )

    return _make_result(
        "no_competitor_mention",
        1,
        "No competitor names found in response.",
    )
