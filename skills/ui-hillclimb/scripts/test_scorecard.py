#!/usr/bin/env python3
"""Exercise the scorecard CLI against real temporary artifacts."""

import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


SCRIPT = Path(__file__).with_name("scorecard.py")
REVIEW_PACKET = SCRIPT.with_name("review_packet.py")
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")


class ScorecardCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ("candidate.png", "baseline.png"):
            (self.root / name).write_bytes(PNG)
        (self.root / "workflow.log").write_text("Opened item, edited field, saved and reloaded successfully.\n")
        self.contract = {
            "candidate": "V1", "variants": {"V1": ["wide", "narrow"], "V2": ["wide", "narrow"]},
            "categories": ["hierarchy", "typography"], "target_score": 9,
            "reviewers": [{"id": f"judge-{i}", "provider": f"provider-{i}", "model": f"model-{i}"}
                          for i in range(3)],
            "checks": ["workflow"], "max_rounds": 6, "max_minutes": 90, "max_spend_usd": None,
        }
        spec = {"revision": "fixture-sha+fixture-source-digest", "images": {
            "V1": {"wide": "candidate.png", "narrow": "candidate.png"},
            "V2": {"wide": "baseline.png", "narrow": "baseline.png"}},
            "checks": {"workflow": {"passed": True, "path": "workflow.log"}}}
        self.write("spec.json", spec)
        self.invoke("seal", self.root / "spec.json", self.root / "packet.json", expected=0)
        self.packet = json.loads((self.root / "packet.json").read_text())
        self.review_pass = {"round": 1, "stage": "full", "revision": spec["revision"],
                            "packet_id": self.packet["packet_id"], "elapsed_minutes": 15,
                            "spend_usd": None, "reviews": [],
                            "delegate_tasks": {f"judge-{i}": f"task-{i}-pass-1" for i in range(3)}}
        for reviewer in self.contract["reviewers"]:
            self.review_pass["reviews"].append({
                "reviewer_id": reviewer["id"], "provider": reviewer["provider"], "model": reviewer["model"],
                "packet_id": self.packet["packet_id"], "blockers": [], "unverified": [],
                "scores": {variant: {scenario: {category: {"score": score, "evidence": "Visible title is legible."}
                                                    for category in self.contract["categories"]}
                                      for scenario in self.contract["variants"][variant]}
                           for variant, score in [("V1", 9.4), ("V2", 7.2)]}})

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def invoke(self, *args, expected):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def packet_command(self, *args, expected=0):
        result = subprocess.run([sys.executable, str(REVIEW_PACKET), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def gate(self, expected=0):
        self.write("contract.json", self.contract)
        self.write("pass.json", self.review_pass)
        if not (self.root / "state.json").exists():
            self.invoke("start", self.root / "contract.json", self.root / "state.json",
                        "--packet", self.root / "packet.json", expected=0)
        return self.invoke("gate", self.root / "contract.json", self.root / "packet.json",
                           self.root / "pass.json", "--state", self.root / "state.json", expected=expected)

    def cell(self):
        return self.review_pass["reviews"][0]["scores"]["V1"]["narrow"]["typography"]

    def test_complete_panel(self):
        self.assertEqual(self.gate()["decision"], "panel_met")

    def test_low_single_cell_is_not_hidden_by_averages(self):
        self.cell()["score"] = 3
        self.assertEqual(self.gate(1)["candidate_minimums"]["judge-0"], 3)

    def test_missing_evidence(self):
        self.cell()["evidence"] = ""
        self.assertEqual(self.gate(1)["decision"], "needs_work")

    def test_unviewed_image(self):
        self.cell()["score"] = None
        self.review_pass["reviews"][0]["unverified"].append("narrow image unavailable")
        self.gate(1)

    def test_missing_reviewer(self):
        self.review_pass["reviews"].pop()
        self.review_pass["delegate_tasks"].pop("judge-2")
        self.gate(1)

    def test_stale_review(self):
        self.review_pass["reviews"][0]["packet_id"] = "old-packet"
        self.gate(2)

    def test_changed_baseline(self):
        self.gate()
        (self.root / "baseline.png").write_bytes(PNG + b"changed")
        self.gate(2)

    def test_failed_workflow(self):
        spec = json.loads((self.root / "spec.json").read_text())
        spec["checks"]["workflow"]["passed"] = False
        self.write("failed-spec.json", spec)
        self.invoke("seal", self.root / "failed-spec.json", self.root / "failed-packet.json", expected=0)
        failed = json.loads((self.root / "failed-packet.json").read_text())
        self.packet = failed
        self.write("packet.json", failed)
        self.review_pass["packet_id"] = failed["packet_id"]
        for review in self.review_pass["reviews"]:
            review["packet_id"] = failed["packet_id"]
        self.gate(1)

    def test_baseline_defect_does_not_veto_candidate(self):
        self.review_pass["reviews"][0]["blockers"].append(
            {"variant": "V2", "scenario": "wide", "evidence": "Original primary action is hidden."})
        self.gate()

    def test_candidate_defect_blocks(self):
        self.review_pass["reviews"][0]["blockers"].append(
            {"variant": "V1", "scenario": "wide", "evidence": "Primary action is hidden."})
        self.gate(1)

    def test_pilot_cannot_complete(self):
        self.review_pass["stage"] = "pilot"
        self.gate(1)

    def test_budget_stop(self):
        self.contract["max_rounds"] = 1
        self.cell()["score"] = 8
        self.assertEqual(self.gate(1)["decision"], "budget_stop")

    def test_unknown_spend_under_explicit_cap(self):
        self.contract["max_spend_usd"] = 10
        self.assertEqual(self.gate(1)["decision"], "budget_stop")

    def test_required_reference_win(self):
        self.contract["must_beat"] = ["V2"]
        self.review_pass["reviews"][0]["scores"]["V2"]["wide"]["typography"]["score"] = 10
        self.gate(1)

    def test_changed_source_revision(self):
        self.review_pass["revision"] = "new-source"
        self.gate(2)

    def test_invalid_numeric_score(self):
        self.cell()["score"] = float("nan")
        self.gate(2)

    def test_model_substitution(self):
        self.review_pass["reviews"][0]["model"] = "different-model"
        self.gate(2)

    def test_refuses_packet_overwrite(self):
        self.invoke("seal", self.root / "spec.json", self.root / "packet.json", expected=2)

    def fresh_tasks(self):
        self.review_pass["delegate_tasks"] = {f"judge-{i}": f"task-{i}-pass-2" for i in range(3)}

    def test_confirmation_requires_passing_full_panel(self):
        self.review_pass["stage"] = "confirmation"
        self.gate(2)

    def test_full_then_fresh_confirmation(self):
        self.gate()
        self.fresh_tasks()
        self.review_pass["stage"] = "confirmation"
        self.assertEqual(self.gate()["decision"], "target_met")

    def test_confirmation_rejects_reused_reviews(self):
        self.gate()
        self.review_pass["stage"] = "confirmation"
        self.gate(2)

    def test_resumed_round_reset(self):
        self.gate()
        self.fresh_tasks()
        self.review_pass["round"] = 0
        self.gate(2)

    def test_resumed_elapsed_reset(self):
        self.gate()
        self.fresh_tasks()
        self.review_pass["elapsed_minutes"] = 1
        self.gate(2)

    def test_resumed_spend_reset(self):
        self.review_pass["spend_usd"] = 9
        self.gate()
        self.fresh_tasks()
        self.review_pass["spend_usd"] = 1
        self.gate(2)

    def test_actual_elapsed_clock_counts_on_resume(self):
        self.gate()
        state = json.loads((self.root / "state.json").read_text())
        state["started_at"] = time.time() - 91 * 60
        self.write("state.json", state)
        self.fresh_tasks()
        self.review_pass["stage"] = "confirmation"
        self.assertEqual(self.gate(1)["decision"], "budget_stop")

    def test_contract_frozen(self):
        self.gate()
        self.fresh_tasks()
        self.contract["target_score"] = 5
        self.gate(2)

    def test_cannot_resume_after_budget_stop(self):
        self.contract["max_rounds"] = 1
        self.cell()["score"] = 8
        self.gate(1)
        self.fresh_tasks()
        self.cell()["score"] = 10
        self.gate(2)

    def next_capture(self):
        self.write("next-spec.json", json.loads((self.root / "spec.json").read_text()))
        self.invoke("seal", self.root / "next-spec.json", self.root / "next-packet.json", expected=0)
        self.packet = json.loads((self.root / "next-packet.json").read_text())
        self.write("packet.json", self.packet)
        self.review_pass["round"] += 1
        self.review_pass["packet_id"] = self.packet["packet_id"]
        for review in self.review_pass["reviews"]:
            review["packet_id"] = self.packet["packet_id"]
        self.fresh_tasks()

    def test_resealed_changed_baseline_is_rejected_across_rounds(self):
        self.cell()["score"] = 8
        self.gate(1)
        (self.root / "baseline.png").write_bytes(PNG + b"different anchor")
        self.next_capture()
        self.cell()["score"] = 10
        result = self.gate(2)
        self.assertIn("fixed comparison", result["error"])

    def test_resealed_candidate_can_change_with_fixed_baseline(self):
        self.cell()["score"] = 8
        self.gate(1)
        (self.root / "candidate.png").write_bytes(PNG + b"new candidate")
        self.next_capture()
        self.cell()["score"] = 9.4
        self.assertEqual(self.gate()["decision"], "panel_met")

    def add_preferences(self, preferences):
        self.contract["prefer_over"] = ["V2"]
        for review, preference in zip(self.review_pass["reviews"], preferences):
            review["comparisons"] = [{"left": "V1", "right": "V2", "preferred": preference,
                                      "evidence": "The primary action is easier to locate."}]

    def test_pairwise_majority_can_pass_with_one_tie(self):
        self.add_preferences(["V1", "V1", "tie"])
        self.assertEqual(self.gate()["preference_votes"], {"V2": 2})

    def test_pairwise_tie_cannot_be_hidden_by_high_scores(self):
        self.add_preferences(["V1", "V2", "tie"])
        self.gate(1)

    def test_pairwise_missing_judgment_is_incomplete(self):
        self.add_preferences(["V1", "V1", "V1"])
        self.review_pass["reviews"][2]["comparisons"] = []
        self.gate(1)

    def prepare_review(self):
        return self.packet_command("prepare", self.root / "packet.json", self.root / "reviewer",
                                   "--map", self.root / "private-map.json", "--reviewer", "judge-0",
                                   "--workspace", self.root / "project")

    def blind_result(self):
        mapping = json.loads((self.root / "private-map.json").read_text())
        reverse = {canonical: public for public, canonical in mapping["labels"].items()}
        result = json.loads(json.dumps(self.review_pass["reviews"][0]))
        result["scores"] = {reverse[key]: value for key, value in result["scores"].items()}
        result["blockers"] = [{"variant": reverse["V2"], "scenario": "wide", "evidence": "Old action is unclear."}]
        result["comparisons"] = [{"left": reverse["V1"], "right": reverse["V2"], "preferred": reverse["V1"],
                                  "evidence": "The primary action is easier to locate."}]
        self.write("blind-result.json", result)

    def test_anonymous_packet_round_trip_preserves_scores_and_evidence(self):
        self.prepare_review()
        public = json.loads((self.root / "reviewer/packet.json").read_text())
        for scenarios in public["images"].values():
            for image_path in scenarios.values():
                path = Path(image_path)
                self.assertTrue(path.name.startswith("sample-"))
                self.assertEqual(path.read_bytes(), PNG)
                self.assertEqual(path.stat().st_mtime, 946684800)
        self.assertNotIn("checks", public)
        self.assertNotIn("revision", public)
        self.blind_result()
        self.packet_command("unblind", self.root / "blind-result.json", self.root / "private-map.json",
                            self.root / "restored.json")
        restored = json.loads((self.root / "restored.json").read_text())
        self.assertEqual(restored["scores"], self.review_pass["reviews"][0]["scores"])
        self.assertEqual(restored["blockers"][0]["variant"], "V2")
        self.assertEqual(restored["comparisons"][0]["preferred"], "V1")

    def test_private_mapping_cannot_be_in_reviewer_directory(self):
        self.packet_command("prepare", self.root / "packet.json", self.root / "reviewer",
                            "--map", self.root / "reviewer/map.json", "--reviewer", "judge-0",
                            "--workspace", self.root / "project", expected=2)
        self.assertFalse((self.root / "reviewer").exists())

    def test_reviewer_copies_must_be_outside_project(self):
        self.packet_command("prepare", self.root / "packet.json", self.root / "project/reviewer",
                            "--map", self.root / "private-map.json", "--reviewer", "judge-0",
                            "--workspace", self.root / "project", expected=2)

    def test_edited_reviewer_image_invalidates_result(self):
        self.prepare_review()
        self.blind_result()
        image = next((self.root / "reviewer").glob("*.png"))
        image.write_bytes(PNG + b"edited")
        self.packet_command("unblind", self.root / "blind-result.json", self.root / "private-map.json",
                            self.root / "restored.json", expected=2)

    def test_edited_reviewer_manifest_invalidates_result(self):
        self.prepare_review()
        self.blind_result()
        (self.root / "reviewer/packet.json").write_text("{}")
        self.packet_command("unblind", self.root / "blind-result.json", self.root / "private-map.json",
                            self.root / "restored.json", expected=2)

    def test_same_round_cannot_resample_failed_full_panel(self):
        self.cell()["score"] = 8
        self.gate(1)
        self.cell()["score"] = 10
        self.fresh_tasks()
        result = self.gate(2)
        self.assertIn("full review already recorded", result["error"])

    def test_next_round_requires_changed_capture(self):
        self.cell()["score"] = 8
        self.gate(1)
        self.review_pass["round"] = 2
        self.cell()["score"] = 10
        self.fresh_tasks()
        self.assertIn("new capture evidence", self.gate(2)["error"])

    def test_resealed_identical_candidate_cannot_resample_failed_panel(self):
        self.cell()["score"] = 8
        self.gate(1)
        (self.root / "renamed-candidate.png").write_bytes(PNG)
        spec = json.loads((self.root / "spec.json").read_text())
        spec["images"]["V1"] = {scenario: "renamed-candidate.png" for scenario in spec["images"]["V1"]}
        self.write("spec.json", spec)
        self.next_capture()
        self.cell()["score"] = 10
        self.assertIn("full review already recorded", self.gate(2)["error"])

    def test_swapped_private_label_map_is_rejected(self):
        self.prepare_review()
        self.blind_result()
        mapping = json.loads((self.root / "private-map.json").read_text())
        keys = list(mapping["labels"])
        mapping["labels"][keys[0]], mapping["labels"][keys[1]] = mapping["labels"][keys[1]], mapping["labels"][keys[0]]
        self.write("private-map.json", mapping)
        result = self.packet_command("unblind", self.root / "blind-result.json", self.root / "private-map.json",
                                     self.root / "restored.json", expected=2)
        self.assertIn("private label mapping changed", result["error"])

    def test_mapping_requires_unique_canonical_variants(self):
        self.prepare_review()
        self.blind_result()
        mapping = json.loads((self.root / "private-map.json").read_text())
        keys = list(mapping["labels"])
        mapping["labels"][keys[1]] = mapping["labels"][keys[0]]
        self.write("private-map.json", mapping)
        result = self.packet_command("unblind", self.root / "blind-result.json", self.root / "private-map.json",
                                     self.root / "restored.json", expected=2)
        self.assertIn("bijection", result["error"])

    def test_private_mapping_cannot_be_in_project_workspace(self):
        self.packet_command("prepare", self.root / "packet.json", self.root / "reviewer",
                            "--map", self.root / "project/private.json", "--reviewer", "judge-0",
                            "--workspace", self.root / "project", expected=2)
        self.assertFalse((self.root / "reviewer").exists())


if __name__ == "__main__":
    unittest.main()
