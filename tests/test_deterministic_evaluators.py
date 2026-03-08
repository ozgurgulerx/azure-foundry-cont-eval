"""Unit tests for custom deterministic evaluators.

Tests cover all four evaluators with representative inputs:
  - citation_present
  - response_length
  - refusal_on_out_of_scope
  - no_competitor_mention

Each test verifies the score, passed flag, and reason string.
"""

import unittest

from src.evaluators.deterministic import (
    evaluate_citation_present,
    evaluate_no_competitor_mention,
    evaluate_refusal_on_out_of_scope,
    evaluate_response_length,
)


class TestCitationPresent(unittest.TestCase):
    """Tests for evaluate_citation_present."""

    def test_pass_with_section_reference(self):
        response = (
            "The SunMax 400 is a residential solar panel with 400W output. "
            "See Section 2: Products for full details."
        )
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_pass_with_product_name_reference(self):
        response = "The PowerVault Home Battery has a capacity of 13.5 kWh."
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_pass_with_topic_reference(self):
        response = "Our Warranty and Support policy covers manufacturing defects."
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_pass_on_refusal(self):
        response = "I don't have that information in my knowledge base."
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])
        self.assertIn("refusal", result["reason"].lower())

    def test_fail_no_citation(self):
        response = "The price is $299 per panel before setup costs."
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])

    def test_fail_empty_response(self):
        result = evaluate_citation_present("")
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])

    def test_fail_whitespace_response(self):
        result = evaluate_citation_present("   ")
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])

    def test_case_insensitive(self):
        response = "According to section 5 on financing, we offer three options."
        result = evaluate_citation_present(response)
        self.assertEqual(result["score"], 1)


class TestResponseLength(unittest.TestCase):
    """Tests for evaluate_response_length."""

    def test_pass_within_bounds(self):
        response = " ".join(["word"] * 50)
        result = evaluate_response_length(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_pass_at_minimum(self):
        response = " ".join(["word"] * 10)
        result = evaluate_response_length(response)
        self.assertEqual(result["score"], 1)

    def test_pass_at_maximum(self):
        response = " ".join(["word"] * 200)
        result = evaluate_response_length(response)
        self.assertEqual(result["score"], 1)

    def test_fail_too_short(self):
        response = "Yes."
        result = evaluate_response_length(response)
        self.assertEqual(result["score"], 0)
        self.assertIn("too short", result["reason"].lower())

    def test_fail_too_long(self):
        response = " ".join(["word"] * 201)
        result = evaluate_response_length(response)
        self.assertEqual(result["score"], 0)
        self.assertIn("too long", result["reason"].lower())

    def test_fail_empty(self):
        result = evaluate_response_length("")
        self.assertEqual(result["score"], 0)

    def test_custom_bounds(self):
        response = " ".join(["word"] * 5)
        result = evaluate_response_length(response, min_words=3, max_words=10)
        self.assertEqual(result["score"], 1)

    def test_custom_bounds_fail(self):
        response = " ".join(["word"] * 15)
        result = evaluate_response_length(response, min_words=3, max_words=10)
        self.assertEqual(result["score"], 0)


class TestRefusalOnOutOfScope(unittest.TestCase):
    """Tests for evaluate_refusal_on_out_of_scope."""

    def test_pass_in_scope_question(self):
        response = "The SunMax 400 costs $299 per panel."
        result = evaluate_refusal_on_out_of_scope(response, is_out_of_scope=False)
        self.assertEqual(result["score"], 1)
        self.assertIn("not applicable", result["reason"].lower())

    def test_pass_correct_refusal(self):
        response = "I don't have that information in my knowledge base."
        result = evaluate_refusal_on_out_of_scope(response, is_out_of_scope=True)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_pass_alternative_refusal(self):
        response = "That question is outside the scope of what I can answer."
        result = evaluate_refusal_on_out_of_scope(response, is_out_of_scope=True)
        self.assertEqual(result["score"], 1)

    def test_fail_no_refusal_on_out_of_scope(self):
        response = "Solar panels typically last 25-30 years and are a great investment."
        result = evaluate_refusal_on_out_of_scope(response, is_out_of_scope=True)
        self.assertEqual(result["score"], 0)
        self.assertFalse(result["passed"])

    def test_fail_empty_response_out_of_scope(self):
        result = evaluate_refusal_on_out_of_scope("", is_out_of_scope=True)
        self.assertEqual(result["score"], 0)

    def test_pass_any_response_in_scope(self):
        # Even a weird response passes if the question is in-scope
        result = evaluate_refusal_on_out_of_scope("bananas", is_out_of_scope=False)
        self.assertEqual(result["score"], 1)


class TestNoCompetitorMention(unittest.TestCase):
    """Tests for evaluate_no_competitor_mention."""

    def test_pass_clean_response(self):
        response = "Contoso Solar's SunMax 400 panel produces 400W of power."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 1)
        self.assertTrue(result["passed"])

    def test_fail_mentions_tesla(self):
        response = "Unlike Tesla Solar, Contoso Solar offers a 25-year warranty."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 0)
        self.assertIn("Tesla Solar", result["reason"])

    def test_fail_mentions_sunrun(self):
        response = "Our prices are competitive with Sunrun and other providers."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 0)
        self.assertIn("Sunrun", result["reason"])

    def test_fail_multiple_competitors(self):
        response = "Compared to SunPower and First Solar, we offer better value."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 0)
        self.assertIn("SunPower", result["reason"])
        self.assertIn("First Solar", result["reason"])

    def test_pass_empty_response(self):
        result = evaluate_no_competitor_mention("")
        self.assertEqual(result["score"], 1)

    def test_case_insensitive(self):
        response = "Our panels are better than sunpower products."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 0)

    def test_pass_mentions_contoso_only(self):
        response = "Contoso Solar is the best choice for residential solar."
        result = evaluate_no_competitor_mention(response)
        self.assertEqual(result["score"], 1)


class TestResultStructure(unittest.TestCase):
    """Verify all evaluators return correctly structured results."""

    def _check_structure(self, result: dict):
        self.assertIn("name", result)
        self.assertIn("score", result)
        self.assertIn("passed", result)
        self.assertIn("reason", result)
        self.assertIsInstance(result["name"], str)
        self.assertIn(result["score"], (0, 1))
        self.assertIsInstance(result["passed"], bool)
        self.assertEqual(result["passed"], result["score"] == 1)
        self.assertIsInstance(result["reason"], str)
        self.assertGreater(len(result["reason"]), 0)

    def test_citation_present_structure(self):
        self._check_structure(evaluate_citation_present("Test response about Products."))
        self._check_structure(evaluate_citation_present(""))

    def test_response_length_structure(self):
        self._check_structure(evaluate_response_length("word " * 50))
        self._check_structure(evaluate_response_length(""))

    def test_refusal_structure(self):
        self._check_structure(
            evaluate_refusal_on_out_of_scope("I don't have that information.", True)
        )
        self._check_structure(
            evaluate_refusal_on_out_of_scope("Answer here.", False)
        )

    def test_competitor_structure(self):
        self._check_structure(evaluate_no_competitor_mention("Clean response."))
        self._check_structure(evaluate_no_competitor_mention("Tesla Solar is bad."))


if __name__ == "__main__":
    unittest.main()
