import tempfile
import unittest
from pathlib import Path

from tools import run_wait_skill_trial as trial


def tool(
    name: str, input_: dict[str, object], output: str = ""
) -> dict[str, object]:
    return {
        "type": "tool_use",
        "part": {
            "tool": name,
            "state": {"input": input_, "output": output},
        },
    }


def text(value: str) -> dict[str, object]:
    return {"type": "text", "part": {"text": value}}


def step_start() -> dict[str, object]:
    return {"type": "step_start", "part": {}}


class TrialAnalysisTests(unittest.TestCase):
    def test_decoded_output_handles_timeout_bytes(self) -> None:
        self.assertEqual(
            trial.decoded_output(b'{"type":"text"}\n'),
            '{"type":"text"}\n',
        )
        self.assertEqual(trial.decoded_output(None), "")

    def test_foreground_command_can_block_without_loading_skill(self) -> None:
        analysis = trial.analyze(
            [
                tool("bash", {"command": "./slow-command.sh"}),
                tool("read", {"filePath": "/tmp/result.txt"}),
                text("finished-after=5-seconds"),
            ],
            "foreground-explicit",
            "result.txt",
            "finished-after=5-seconds",
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(analysis["wait_skill_calls"], 0)

    def test_detached_command_can_use_more_than_one_wait_cycle(self) -> None:
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 5"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text("finished-after=12-seconds"),
            ],
            "detached-implicit",
            "async-result.txt",
            "finished-after=12-seconds",
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(len(analysis["calls_while_waiting"]), 2)

    def test_detached_command_requires_wait_skill(self) -> None:
        analysis = trial.analyze(
            [
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text("finished-after=7-seconds"),
            ],
            "detached-implicit",
            "async-result.txt",
            "finished-after=7-seconds",
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["loaded_wait_skill_when_needed"])

    def test_analysis_accepts_a_variant_skill_name(self) -> None:
        expected = "opaque-completion=secret"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "await-completion"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text(expected),
            ],
            "opaque-implicit",
            "async-result.txt",
            expected,
            launch_count=1,
            skill_name="await-completion",
        )

        self.assertTrue(analysis["passed"])

    def test_workspace_can_load_a_variant_and_router_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            skill_path = directory / "await-completion"
            instruction = directory / "router.md"
            trial.write_workspace(
                directory,
                "opaque-implicit",
                12,
                skill_path=skill_path,
                instructions=(instruction,),
            )
            config = (directory / "opencode.json").read_text(encoding="utf-8")

        self.assertIn(str(skill_path), config)
        self.assertIn(str(instruction), config)

    def test_opaque_trial_accepts_multiple_bounded_wait_cycles(self) -> None:
        expected = "opaque-completion=secret"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 3"}),
                tool("read", {"filePath": "/tmp/async-result.txt"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text(expected),
            ],
            "opaque-underestimate",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(len(analysis["blocking_wait_calls"]), 2)

    def test_opaque_trial_accepts_launch_and_wait_in_one_terminal_call(self) -> None:
        expected = "opaque-completion=secret"
        command = (
            "./start-command.sh && for i in $(seq 1 30); do "
            "test -f async-result.txt && break; sleep 1; done; cat async-result.txt"
        )
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": command}),
                text(expected),
            ],
            "opaque-buried",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(analysis["blocking_wait_calls"], [command])

    def test_opaque_trial_rejects_duplicate_launch(self) -> None:
        expected = "opaque-completion=secret"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text(expected),
            ],
            "opaque-underestimate",
            "async-result.txt",
            expected,
            launch_count=2,
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["launched_target_once_on_disk"])

    def test_opaque_trial_rejects_nonblocking_polling(self) -> None:
        expected = "opaque-completion=secret"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "ls async-result.txt"}),
                tool("bash", {"command": "cat async-result.txt"}),
                text(expected),
            ],
            "opaque-underestimate",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["used_terminal_wait_cycle"])

    def test_opaque_trial_rejects_excessive_model_wakeups(self) -> None:
        expected = "opaque-completion=secret"
        events = [
            tool("skill", {"name": "wait"}),
            tool("bash", {"command": "./start-command.sh"}),
            tool("bash", {"command": "sleep 3"}),
        ]
        for _ in range(9):
            events.extend(
                [
                    step_start(),
                    tool("read", {"filePath": "/tmp/async-result.txt"}),
                ]
            )
        events.append(text(expected))

        analysis = trial.analyze(
            events,
            "opaque-underestimate",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["kept_model_wakeups_bounded"])

    def test_script_inspection_does_not_count_as_launch_or_wait(self) -> None:
        expected = "opaque-completion=secret"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("bash", {"command": "cat ./start-command.sh wait.log"}),
                tool("bash", {"command": "./start-command.sh"}),
                tool("bash", {"command": "sleep 10 && cat async-result.txt"}),
                text(expected),
            ],
            "opaque-underestimate",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(
            analysis["blocking_wait_calls"],
            ["sleep 10 && cat async-result.txt"],
        )

    def test_shell_invocation_counts_as_launch(self) -> None:
        self.assertTrue(
            trial.runs_script("sh ./start-command.sh", "start-command.sh")
        )
        self.assertTrue(
            trial.runs_script("bash start-command.sh", "start-command.sh")
        )
        self.assertTrue(
            trial.runs_script("cd /tmp && ./start-command.sh", "start-command.sh")
        )
        self.assertFalse(
            trial.runs_script("cat ./start-command.sh", "start-command.sh")
        )

    def test_opaque_implicit_scenario_does_not_tell_agent_to_wait(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            prompt, _, _ = trial.write_workspace(directory, "opaque-implicit", 12)
            script = (directory / "start-command.sh").read_text(encoding="utf-8")

        combined = f"{prompt}\n{script}".lower()
        self.assertNotIn("wait", combined)
        self.assertNotIn("stand by", combined)

    def test_opaque_buried_scenario_hides_the_wait_inside_a_larger_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            prompt, _, _ = trial.write_workspace(directory, "opaque-buried", 12)
            script = (directory / "start-command.sh").read_text(encoding="utf-8")

        combined = f"{prompt}\n{script}".lower()
        self.assertIn("delivery note", prompt.lower())
        self.assertNotIn("wait", combined)
        self.assertNotIn("stand by", combined)

    def test_resumable_terminal_requires_attachment_to_same_session(self) -> None:
        expected = "terminal-completion=secret"
        session_id = "term-01234567-89ab-cdef-0123-456789abcdef"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool(
                    "resumable_terminal",
                    {"action": "start"},
                    f"Script running with session ID {session_id}.",
                ),
                step_start(),
                tool(
                    "resumable_terminal",
                    {"action": "attach", "session_id": session_id},
                    f"Terminal {session_id} completed.\n{expected}",
                ),
                step_start(),
                text(expected),
            ],
            "resumable-terminal",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(analysis["terminal_attach_session_ids"], [session_id])

    def test_static_near_miss_rejects_unwanted_wait_skill_load(self) -> None:
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool("read", {"filePath": "/tmp/timeout-config.txt"}),
                text("retry_timeout=30"),
            ],
            "static-timeout",
            "timeout-config.txt",
            "retry_timeout=30",
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(
            analysis["checks"]["avoided_wait_skill_for_static_task"]
        )

    def test_static_near_miss_passes_without_wait_skill(self) -> None:
        analysis = trial.analyze(
            [
                tool("read", {"filePath": "/tmp/build.log"}),
                text("build-duration=47-seconds"),
            ],
            "completed-build-log",
            "build.log",
            "build-duration=47-seconds",
        )

        self.assertTrue(analysis["passed"])
        self.assertEqual(analysis["wait_skill_calls"], 0)

    def test_resumable_terminal_rejects_wrong_session(self) -> None:
        expected = "terminal-completion=secret"
        session_id = "term-01234567-89ab-cdef-0123-456789abcdef"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool(
                    "resumable_terminal",
                    {"action": "start"},
                    f"Script running with session ID {session_id}.",
                ),
                tool(
                    "resumable_terminal",
                    {"action": "attach", "session_id": "term-wrong"},
                    "Unknown terminal session term-wrong.",
                ),
                text(expected),
            ],
            "resumable-terminal",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["reattached_to_same_terminal"])

    def test_resumable_terminal_rejects_bash_polling(self) -> None:
        expected = "terminal-completion=secret"
        session_id = "term-01234567-89ab-cdef-0123-456789abcdef"
        analysis = trial.analyze(
            [
                tool("skill", {"name": "wait"}),
                tool(
                    "resumable_terminal",
                    {"action": "start"},
                    f"Script running with session ID {session_id}.",
                ),
                tool("bash", {"command": "sleep 10"}),
                tool(
                    "resumable_terminal",
                    {"action": "attach", "session_id": session_id},
                    f"Terminal {session_id} completed.\n{expected}",
                ),
                text(expected),
            ],
            "resumable-terminal",
            "async-result.txt",
            expected,
            launch_count=1,
        )

        self.assertFalse(analysis["passed"])
        self.assertFalse(analysis["checks"]["avoided_bash_polling"])


if __name__ == "__main__":
    unittest.main()
