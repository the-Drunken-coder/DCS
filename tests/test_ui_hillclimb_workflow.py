"""Real browser capture and workflow gate, with explicitly synthetic review intake."""

from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/ui-hillclimb/scripts"


def browser_binary():
    configured = os.environ.get("UI_HILLCLIMB_BROWSER")
    candidates = [configured] if configured else [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser"),
    ]
    return next((path for path in candidates if path and Path(path).is_file()), None)


class WorkflowDOM(HTMLParser):
    passed = False

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.passed = dict(attrs).get("data-workflow") == "passed"


class RenderedWorkflowTests(unittest.TestCase):
    def test_capture_failed_control_review_intake_and_resumed_confirmation(self):
        browser = browser_binary()
        if browser is None:
            self.skipTest("Chrome/Chromium unavailable; set UI_HILLCLIMB_BROWSER for the rendered workflow test")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            page = project / "page.html"
            shutil.copyfile(ROOT / "tests/fixtures/ui-hillclimb.html", page)

            def invoke(script, *args, expected=0):
                process = subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                                         text=True, capture_output=True, timeout=30)
                self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
                return json.loads(process.stdout)

            def write(name, value):
                path = root / name
                path.write_text(json.dumps(value))
                return path

            def render(name, broken=False):
                image = root / f"{name}.png"
                url = page.as_uri() + "?verify=1" + ("&broken=1" if broken else "")
                process = subprocess.run([
                    browser, "--headless=new", "--no-first-run", "--no-default-browser-check",
                    "--disable-background-networking", "--disable-extensions", "--use-mock-keychain",
                    f"--user-data-dir={root / ('profile-' + name)}", "--window-size=980,740",
                    "--virtual-time-budget=1000", "--dump-dom", f"--screenshot={image}", url,
                ], capture_output=True, text=True, timeout=30)
                self.assertEqual(process.returncode, 0, process.stderr)
                dom = WorkflowDOM()
                dom.feed(process.stdout)
                log = root / f"{name}.log"
                log.write_text(process.stdout + "\n" + process.stderr)
                self.assertTrue(image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
                self.assertGreater(image.stat().st_size, 1000)
                return image, log, dom.passed

            baseline, baseline_log, baseline_passed = render("baseline")
            self.assertTrue(baseline_passed)
            contract = {
                "candidate": "V1", "variants": {"V1": ["desktop"], "V2": ["desktop"]},
                "categories": ["hierarchy"], "target_score": 9, "prefer_over": ["V2"],
                "reviewers": [{"id": f"fixture-{i}", "provider": "synthetic-fixture", "model": f"fixture-{i}"}
                              for i in range(3)],
                "checks": ["add-task"], "max_rounds": 3, "max_minutes": 5,
            }
            contract_path = write("contract.json", contract)

            def seal(name, image, log, passed):
                spec = {"revision": name, "images": {"V1": {"desktop": str(image)},
                                                     "V2": {"desktop": str(baseline)}},
                        "checks": {"add-task": {"passed": passed, "path": str(log)}}}
                spec_path = write(f"{name}-spec.json", spec)
                packet_path = root / f"{name}-packet.json"
                invoke("scorecard.py", "seal", spec_path, packet_path)
                return packet_path, json.loads(packet_path.read_text())

            initial_path, _ = seal("initial", baseline, baseline_log, baseline_passed)
            state = root / "state.json"
            invoke("scorecard.py", "start", contract_path, state, "--packet", initial_path)

            def review_pass(name, packet_path, packet, round_number, stage, expected):
                reviews, tasks = [], {}
                for reviewer in contract["reviewers"]:
                    reviewer_id = reviewer["id"]
                    public_dir = root / f"{name}-{reviewer_id}"
                    mapping_path = root / f"{name}-{reviewer_id}-private.json"
                    invoke("review_packet.py", "prepare", packet_path, public_dir,
                           "--map", mapping_path, "--reviewer", reviewer_id, "--workspace", project)
                    public = json.loads((public_dir / "packet.json").read_text())
                    private = json.loads(mapping_path.read_text())
                    labels = {canonical: blind for blind, canonical in private["labels"].items()}
                    # These synthetic ratings deliberately cannot certify the rendered control works.
                    result = {
                        "reviewer_id": reviewer_id, "provider": reviewer["provider"], "model": reviewer["model"],
                        "packet_id": packet["packet_id"], "blockers": [], "unverified": [],
                        "scores": {variant: {"desktop": {"hierarchy": {
                            "score": 9.4, "evidence": "Synthetic review intake fixture, not a model judgment."}}}
                                   for variant in public["images"]},
                        "comparisons": [{"left": labels["V1"], "right": labels["V2"],
                                         "preferred": labels["V1"], "evidence": "Synthetic preference fixture."}],
                    }
                    raw_path = write(f"{name}-{reviewer_id}-raw.json", result)
                    restored_path = root / f"{name}-{reviewer_id}-restored.json"
                    invoke("review_packet.py", "unblind", raw_path, mapping_path, restored_path)
                    reviews.append(json.loads(restored_path.read_text()))
                    tasks[reviewer_id] = f"synthetic-task-{name}-{reviewer_id}"
                record = {"round": round_number, "stage": stage, "revision": packet["revision"],
                          "packet_id": packet["packet_id"], "elapsed_minutes": 0,
                          "reviews": reviews, "delegate_tasks": tasks}
                record_path = write(f"{name}-pass.json", record)
                return invoke("scorecard.py", "gate", contract_path, packet_path, record_path,
                              "--state", state, expected=expected)

            broken, broken_log, broken_passed = render("broken", broken=True)
            self.assertFalse(broken_passed)
            broken_path, broken_packet = seal("broken", broken, broken_log, broken_passed)
            rejected = review_pass("broken", broken_path, broken_packet, 1, "full", expected=1)
            self.assertEqual(rejected["decision"], "needs_work")
            self.assertIn("required check not passed: add-task", rejected["reasons"])

            fixed, fixed_log, fixed_passed = render("fixed")
            self.assertTrue(fixed_passed)
            fixed_path, fixed_packet = seal("fixed", fixed, fixed_log, fixed_passed)
            accepted = review_pass("fixed", fixed_path, fixed_packet, 2, "full", expected=0)
            self.assertEqual(accepted["decision"], "panel_met")
            confirmed = review_pass("confirmation", fixed_path, fixed_packet, 2, "confirmation", expected=0)
            self.assertEqual(confirmed["decision"], "target_met")
            self.assertEqual([event["decision"] for event in json.loads(state.read_text())["history"]],
                             ["needs_work", "panel_met", "target_met"])
