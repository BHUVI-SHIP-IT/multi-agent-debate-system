import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from agents import run_verdict_agent


class _DummyResponse:
    def __init__(self, content: str):
        self.content = content


class _DummyLLM:
    def __init__(self, content: str):
        self._content = content

    def invoke(self, _messages):
        return _DummyResponse(self._content)


class VerdictAgentTests(unittest.TestCase):
    def test_tie_rule_when_margin_below_threshold(self):
        llm_payload = {
            "scores": {
                "pro": {
                    "argument_quality": 20,
                    "evidence_use": 21,
                    "rebuttal_effectiveness": 16,
                    "factual_accuracy": 14,
                    "clarity": 9,
                    "total": 80,
                },
                "opponent": {
                    "argument_quality": 21,
                    "evidence_use": 21,
                    "rebuttal_effectiveness": 16,
                    "factual_accuracy": 14,
                    "clarity": 9,
                    "total": 81,
                },
            },
            "winner": "opponent",
            "rationale": "Opponent was slightly stronger.",
            "confidence": 88,
            "key_errors": {"pro": [], "opponent": []},
            "summary": "Very close debate.",
        }

        state = {
            "topic": "AI in education",
            "conversation": [
                {"role": "pro", "content": "AI enables adaptive learning."},
                {"role": "opponent", "content": "AI can reduce human mentorship."},
            ],
        }

        with patch("agents.strict_llm", _DummyLLM(json.dumps(llm_payload))):
            result = run_verdict_agent(state)

        verdict_data = result["verdict_data"]
        self.assertEqual(verdict_data["winner"], "tie")
        self.assertAlmostEqual(verdict_data["scores"]["pro"]["total"], 80)
        self.assertAlmostEqual(verdict_data["scores"]["opponent"]["total"], 81)
        self.assertGreaterEqual(verdict_data["confidence"], 0)
        self.assertLessEqual(verdict_data["confidence"], 100)

    def test_false_and_repeated_partial_penalties_are_applied(self):
        llm_payload = {
            "scores": {
                "pro": {
                    "argument_quality": 18,
                    "evidence_use": 18,
                    "rebuttal_effectiveness": 15,
                    "factual_accuracy": 15,
                    "clarity": 8,
                    "total": 74,
                },
                "opponent": {
                    "argument_quality": 19,
                    "evidence_use": 20,
                    "rebuttal_effectiveness": 16,
                    "factual_accuracy": 16,
                    "clarity": 8,
                    "total": 79,
                },
            },
            "winner": "opponent",
            "rationale": "Opponent had stronger detail.",
            "confidence": 70,
            "key_errors": {"pro": [], "opponent": []},
            "summary": "Opponent initially leads.",
        }

        state = {
            "topic": "Should remote work be default?",
            "conversation": [
                {"role": "pro", "content": "Remote work improves retention."},
                {"role": "opponent", "content": "Productivity always drops remotely."},
                {"role": "fact_checker", "content": "False: several studies show mixed outcomes."},
                {"role": "opponent", "content": "At best, remote work is partially effective."},
                {"role": "fact_checker", "content": "Partially True: depends on job type."},
                {"role": "opponent", "content": "Remote work is partially useful only for senior roles."},
                {"role": "fact_checker", "content": "Partially True: overgeneralized claim."},
            ],
        }

        with patch("agents.strict_llm", _DummyLLM(json.dumps(llm_payload))):
            result = run_verdict_agent(state)

        verdict_data = result["verdict_data"]
        opponent_penalty = verdict_data["penalties"]["opponent"]["points_deducted"]

        # 1 False (8 points) + 1 repeated Partially True (3 points)
        self.assertEqual(opponent_penalty, 11)
        self.assertAlmostEqual(verdict_data["scores"]["opponent"]["total"], 68)
        self.assertEqual(verdict_data["winner"], "pro")
        self.assertTrue(any("False" in err for err in verdict_data["key_errors"]["opponent"]))

    def test_json_wrapped_in_prose_still_parses(self):
        wrapped = "Here is the final verdict:\n```json\n{\"scores\": {\"pro\": {\"argument_quality\": 10, \"evidence_use\": 10, \"rebuttal_effectiveness\": 10, \"factual_accuracy\": 10, \"clarity\": 5, \"total\": 45}, \"opponent\": {\"argument_quality\": 11, \"evidence_use\": 11, \"rebuttal_effectiveness\": 11, \"factual_accuracy\": 11, \"clarity\": 5, \"total\": 49}}, \"winner\": \"opponent\", \"rationale\": \"Opponent was clearer.\", \"confidence\": 60, \"key_errors\": {\"pro\": [], \"opponent\": []}, \"summary\": \"Opponent wins narrowly.\"}\n```"

        state = {
            "topic": "Electric vehicles",
            "conversation": [
                {"role": "pro", "content": "EV adoption lowers emissions."},
                {"role": "opponent", "content": "Battery supply chains remain problematic."},
            ],
        }

        with patch("agents.strict_llm", _DummyLLM(wrapped)):
            result = run_verdict_agent(state)

        verdict_data = result["verdict_data"]
        self.assertIn("scores", verdict_data)
        self.assertEqual(verdict_data["winner"], "opponent")
        self.assertIn("Winner:", result["verdict"])


if __name__ == "__main__":
    unittest.main()
