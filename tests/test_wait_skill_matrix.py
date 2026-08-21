import unittest

from tools import run_wait_skill_matrix as matrix


class MatrixSummaryTests(unittest.TestCase):
    def test_summarizes_pass_rates_and_failed_checks(self) -> None:
        summary = matrix.summarize(
            [
                {
                    "model": "model-a",
                    "trial": 1,
                    "passed": True,
                    "checks": {"loaded_skill": True},
                },
                {
                    "model": "model-a",
                    "trial": 2,
                    "passed": False,
                    "checks": {"loaded_skill": False, "reported_result": True},
                },
                {
                    "model": "model-b",
                    "trial": 1,
                    "passed": True,
                    "checks": {"loaded_skill": True},
                },
            ]
        )

        self.assertFalse(summary["all_passed"])
        self.assertEqual(summary["total_passed"], 2)
        self.assertEqual(summary["total_trials"], 3)
        self.assertEqual(summary["models"]["model-a"]["pass_rate"], 0.5)
        self.assertEqual(
            summary["models"]["model-a"]["failures"][0]["failed_checks"],
            ["loaded_skill"],
        )

    def test_safe_name_removes_provider_separator(self) -> None:
        self.assertEqual(matrix.safe_name("opencode-go/hy3"), "opencode-go-hy3")


if __name__ == "__main__":
    unittest.main()
