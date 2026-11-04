"""Verificações do contrato e das estatísticas, sem chamadas externas."""
import unittest

from scripts.validate_laya_vs_gemini import (
    decode_gemini, decode_laya, gateway_questions, percentile, summarize,
)


class ValidationContractTests(unittest.TestCase):
    def test_percentiles_use_linear_interpolation(self):
        self.assertEqual(percentile([10, 20, 30], 50), 20)
        self.assertEqual(percentile([10, 20, 30], 95), 29)

    def test_laya_requires_all_operational_questions_and_uses_max(self):
        questions = gateway_questions()
        answers = {key: {"probabilities": {"threat": value}}
                   for key, value in zip(questions, [0.1, 0.7, 0.2])}
        self.assertTrue(decode_laya({"answers": answers}, questions, 0.4)["is_threat"])
        answers.pop(next(iter(questions)))
        with self.assertRaises(KeyError):
            decode_laya({"answers": answers}, questions, 0.4)

    def test_gemini_rejects_incomplete_or_non_boolean_outputs(self):
        for data in [{}, {"candidates": [{"finishReason": "MAX_TOKENS"}]},
                     {"candidates": [{"finishReason": "STOP", "content": {
                         "parts": [{"text": '{"is_threat": "false"}'}]}}]}]:
            with self.assertRaises(ValueError):
                decode_gemini(data)

    def test_gemini_ignores_thought_parts(self):
        data = {"candidates": [{"finishReason": "STOP", "content": {"parts": [
            {"thought": True, "text": "Not JSON"}, {"text": '{"is_threat": false}'}]}}]}
        self.assertFalse(decode_gemini(data)["is_threat"])

    def test_failures_are_neither_safe_nor_latency_samples(self):
        result = summarize([
            {"ok": True, "elapsed_ms": 20, "is_threat": False, "expected_is_threat": False},
            {"ok": False, "elapsed_ms": 30000, "is_threat": None, "expected_is_threat": False},
        ])
        self.assertEqual(result["errors"], 1)
        self.assertEqual(result["correct_decisions"], 1)
        self.assertEqual(result["predictions"]["safe"], 1)
        self.assertEqual(result["latency_ms"]["p95"], 20)


if __name__ == "__main__":
    unittest.main()
