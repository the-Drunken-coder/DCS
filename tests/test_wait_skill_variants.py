import tempfile
import unittest
from pathlib import Path

from tools import run_wait_skill_variants as variants


class VariantTests(unittest.TestCase):
    def test_variants_have_valid_matching_names(self) -> None:
        for variant in variants.variants().values():
            self.assertRegex(variant.skill_name, r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
            self.assertLessEqual(len(variant.description), 1024)

    def test_writes_isolated_skill_and_router(self) -> None:
        variant = variants.variants()["router-control"]
        with tempfile.TemporaryDirectory() as temporary_directory:
            skill_path, instruction_path = variants.write_variant(
                Path(temporary_directory), variant, "# Wait\n"
            )
            content = (skill_path / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn(f"name: {variant.skill_name}", content)
        self.assertIn(variant.description, content)
        self.assertIsNotNone(instruction_path)

    def test_summary_separates_trigger_rate_from_full_pass_rate(self) -> None:
        selected = [variants.variants()["baseline"]]
        summary = variants.summarize_variants(
            [
                {
                    "variant": "baseline",
                    "model": "model-a",
                    "trial": 1,
                    "passed": False,
                    "checks": {
                        "loaded_wait_skill_when_needed": True,
                        "reported_exact_result": False,
                    },
                },
                {
                    "variant": "baseline",
                    "model": "model-a",
                    "trial": 2,
                    "passed": True,
                    "checks": {
                        "loaded_wait_skill_when_needed": True,
                        "reported_exact_result": True,
                    },
                },
            ],
            selected,
        )["baseline"]

        self.assertEqual(summary["trigger_rate"], 1.0)
        self.assertEqual(summary["total_passed"], 1)

    def test_summary_counts_unwanted_static_triggers(self) -> None:
        selected = [variants.variants()["baseline"]]
        summary = variants.summarize_variants(
            [
                {
                    "variant": "baseline",
                    "model": "model-a",
                    "trial": 1,
                    "passed": False,
                    "checks": {
                        "avoided_wait_skill_for_static_task": False,
                        "reported_exact_result": True,
                    },
                }
            ],
            selected,
        )["baseline"]

        self.assertEqual(summary["unwanted_triggers"], 1)
        self.assertEqual(summary["unwanted_trigger_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
