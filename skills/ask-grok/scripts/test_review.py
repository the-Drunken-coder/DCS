import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("review", Path(__file__).with_name("review.py"))
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)

def envelope(text):
    return {"text": text, "stopReason": "end_turn", "sessionId": "test"}


def stream(text):
    return "\n".join(json.dumps(event) for event in [
        {"type": "text", "data": text},
        {"type": "end", "stopReason": "end_turn", "sessionId": "test"},
    ])

class CompletionTests(unittest.TestCase):
    def test_preserves_entire_response(self):
        text = "  Progress\n\n# Finding\nUnicode: café → 2\r\nREVIEW_COMPLETE\n\n"
        actual, problem, session = collector.extract_review(envelope(text))
        self.assertEqual(actual.encode(), text.encode())
        self.assertIsNone(problem)
        self.assertEqual(session, "test")

    def test_rejects_empty_progress_truncated_and_marker_only(self):
        for text in ["", " \n", "I'll inspect the source.", "# Finding\nEnds mid-", "REVIEW_COMPLETE"]:
            actual, problem, _ = collector.extract_review(envelope(text))
            self.assertEqual(actual, text)
            self.assertIsNotNone(problem)

    def test_rejects_wrong_output_types(self):
        self.assertIsNotNone(collector.extract_review(["unexpected"])[1])
        self.assertIsNotNone(collector.extract_review(envelope(None))[1])

    def test_rejects_nonterminal_or_failed_envelopes(self):
        for key, value in [("stopReason", "max_tokens"), ("error", "stream failed")]:
            data = envelope("No findings.\nREVIEW_COMPLETE")
            data[key] = value
            self.assertIsNotNone(collector.extract_review(data)[1])

class StreamTests(unittest.TestCase):
    def test_preserves_text_deltas_without_thoughts_or_tool_payloads(self):
        events = [
            {"type": "thought", "data": "Private reasoning"},
            {"type": "text", "data": "  Finding: café → 2\r\n"},
            {"type": "tool_call_update", "status": "completed", "rawOutput": "source"},
            {"type": "text", "data": "REVIEW_"},
            {"type": "text", "data": "COMPLETE\n\n"},
            {"type": "end", "stopReason": "end_turn", "sessionId": "test"},
        ]
        raw = "\n".join(json.dumps(event) for event in events).encode()
        text, problem, session = collector.extract_grok_stream(raw)
        self.assertEqual(text, "  Finding: café → 2\r\nREVIEW_COMPLETE\n\n")
        self.assertIsNone(problem)
        self.assertEqual(session, "test")

    def test_rejects_missing_end_bad_tail_errors_and_duplicate_end(self):
        text = "Full text.\nREVIEW_COMPLETE"
        valid = stream(text)
        variants = [
            valid.splitlines()[0],
            valid + '\n{"type": "te',
            valid.replace('"end_turn"', '"max_tokens"'),
            '{"type":"error","message":"failed"}\n' + valid,
            valid + '\n' + valid.splitlines()[-1],
        ]
        for raw in variants:
            with self.subTest(raw=raw):
                actual, problem, _ = collector.extract_grok_stream(raw.encode())
                self.assertEqual(actual, text)
                self.assertIsNotNone(problem)

    def test_full_response_keeps_tool_errors_as_coverage_diagnostics(self):
        failed = {"type": "tool_call_update", "status": "failed", "toolCallId": "bad-path"}
        raw = json.dumps(failed) + '\n' + stream("Full review.\nREVIEW_COMPLETE")
        errors = []
        text, problem, _ = collector.extract_grok_stream(raw.encode(), errors)
        self.assertIsNone(problem)
        self.assertEqual(errors, [failed])
        self.assertEqual(text, "Full review.\nREVIEW_COMPLETE")

class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.prompt = self.root / "request.txt"
        self.prompt.write_text("Review the provided files.")

    def collect(self, python, timeout=2):
        with patch.object(collector, "command_for", return_value=([sys.executable, "-c", python], self.source)):
            return collector.collect_review( self.source, self.prompt, self.root, timeout)

    def test_success_writes_verbatim_review_and_valid_manifest(self):
        text = "No findings.\r\nREVIEW_COMPLETE\n"
        raw = stream(text)
        result = self.collect("print(" + repr(raw) + ")")
        self.assertEqual(result["status"], "completed")
        self.assertEqual(Path(result["review"]).read_bytes(), text.encode())
        self.assertEqual(json.loads((self.root / "status.json").read_text()), result)

    def test_partial_stays_partial_even_with_exit_zero(self):
        text = "Review cut off instead of"
        result = self.collect("print(" + repr(stream(text)) + ")")
        self.assertEqual(result["status"], "incomplete")
        self.assertNotIn("review", result)
        self.assertEqual(Path(result["partial"]).read_bytes(), text.encode())

    def test_nonzero_exit_never_counts_as_success(self):
        raw = stream("No findings.\nREVIEW_COMPLETE")
        result = self.collect("import sys; print(" + repr(raw) + "); sys.exit(7)")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["exit_code"], 7)
        self.assertNotIn("review", result)

    def test_malformed_json_keeps_raw_output(self):
        result = self.collect("print('{truncated')")
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(Path(result["stdout"]).read_text(), "{truncated\n")

    def test_deadline_terminates_process_and_records_incomplete(self):
        partial = json.dumps({"type": "text", "data": "An unfinished review"})
        result = self.collect("import time; print(" + repr(partial) + ", flush=True); time.sleep(60)", timeout=0.2)
        self.assertTrue(result["timed_out"])
        self.assertEqual(result["status"], "incomplete")
        self.assertLess(result["seconds"], 7)
        self.assertEqual(Path(result["partial"]).read_text(), "An unfinished review")


    def test_cancellation_stops_running_process(self):
        cancelled = threading.Event()
        timer = threading.Timer(0.2, cancelled.set)
        timer.start()
        self.addCleanup(timer.join)
        command = [sys.executable, "-c", "import time; time.sleep(60)"]
        with patch.object(collector, "command_for", return_value=(command, self.source)):
            result = collector.collect_review( self.source, self.prompt, self.root, 60, cancelled)
        self.assertTrue(result["canceled"])
        self.assertEqual(result["status"], "incomplete")
        self.assertLess(result["seconds"], 7)


    def test_snapshot_checks_contents_and_rejects_symlink_escapes(self):
        source = self.source / "file.txt"
        source.write_text("first")
        before = collector.source_hashes(self.source)
        source.write_text("second")
        self.assertNotEqual(before, collector.source_hashes(self.source))
        (self.source / "outside").symlink_to(self.prompt)
        with self.assertRaises(ValueError):
            collector.source_hashes(self.source)
    def test_setup_error_is_a_failed_result(self):
        with patch.object(collector, "command_for", side_effect=OSError("setup failed")):
            result = collector.collect_review(self.source, self.prompt, self.root, 2)
        self.assertEqual(result["status"], "failed")
        self.assertIn("setup failed", result["reason"])


if __name__ == "__main__":
    unittest.main()
