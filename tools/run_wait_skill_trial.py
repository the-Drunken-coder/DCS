#!/usr/bin/env python3
"""Run one observable wait-skill trial through OpenCode."""

from __future__ import annotations

import argparse
import json
import re
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL = "opencode/deepseek-v4-flash-free"
SCENARIOS = (
    "foreground-explicit",
    "detached-implicit",
    "opaque-underestimate",
    "opaque-implicit",
    "opaque-buried",
    "resumable-terminal",
    "static-timeout",
    "completed-build-log",
    "async-code-review",
)
NEGATIVE_SCENARIOS = (
    "static-timeout",
    "completed-build-log",
    "async-code-review",
)
BLOCKING_WAIT = re.compile(
    r"(?:\b(?:for|until|while)\b|(?:^|[;&|()\n]\s*)"
    r"(?:sleep|wait|watch)(?:\s|$))"
)


def runs_script(command: str, script: str) -> bool:
    return bool(
        re.search(
            rf"(?:^|[;&|()\n]\s*)(?:(?:ba|z)?sh\s+)?"
            rf"['\"]?(?:\./)?{re.escape(script)}['\"]?(?:\s|$|[;&|()])",
            command,
        )
    )


def write_workspace(
    directory: Path,
    scenario: str,
    duration: int,
    *,
    skill_path: Path | None = None,
    instructions: tuple[Path, ...] = (),
) -> tuple[str, str, str]:
    skill_path = skill_path or ROOT / "skills" / "wait"
    config = {
        "$schema": "https://opencode.ai/config.json",
        "skills": {"paths": [str(skill_path)]},
    }
    if instructions:
        config["instructions"] = [str(path) for path in instructions]
    if scenario == "resumable-terminal":
        config["permission"] = {
            "bash": "deny",
            "glob": "deny",
            "grep": "deny",
            "read": "deny",
        }
    (directory / "opencode.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )

    expected = f"finished-after={duration}-seconds"
    if scenario == "foreground-explicit":
        command = "slow-command.sh"
        result = "result.txt"
        script = f"""#!/bin/sh
set -eu
echo "This command will take {duration} seconds. Please stand by."
sleep {duration}
printf '%s\\n' '{expected}' > {result}
echo "Command complete."
"""
        prompt = (
            f"Run ./{command}. It will take {duration} seconds. Wait for it to "
            f"finish, then read {result} and report its exact contents."
        )
    elif scenario == "detached-implicit":
        command = "start-command.sh"
        result = "async-result.txt"
        script = f"""#!/bin/sh
set -eu
rm -f {result}
(
  sleep {duration}
  printf '%s\\n' '{expected}' > {result}
) >/dev/null 2>&1 &
printf '%s\\n' "$!" > job.pid
echo "This command is still running and may take a while. Please stand by."
"""
        prompt = f"Run ./{command}. Then tell me the exact contents of {result}."
    elif scenario.startswith("opaque-"):
        command = "start-command.sh"
        result = "async-result.txt"
        expected = f"opaque-completion={secrets.token_hex(8)}"
        if scenario == "opaque-underestimate":
            status = "Job accepted. Initial estimate: 3 seconds. Please stand by."
        elif scenario == "opaque-buried":
            status = (
                "Submission accepted. Artifact ETA: 3 seconds. "
                "Artifact: async-result.txt."
            )
        else:
            status = (
                "Job accepted. Estimated completion: 3 seconds. "
                "Output: async-result.txt."
            )
        script = f"""#!/bin/sh
set -eu
count=0
if [ -f launch-count.txt ]; then
  count="$(cat launch-count.txt)"
fi
count="$((count + 1))"
printf '%s\n' "$count" > launch-count.txt
: > started.flag
echo "{status}"
"""
        if scenario == "opaque-buried":
            prompt = (
                f"Prepare the final delivery note. Run ./{command}. Include the "
                f"exact full line from {result} and the phrase submission "
                "accepted. Do not guess or shorten the line."
            )
        else:
            prompt = f"Run ./{command}. Then tell me the exact contents of {result}."
    elif scenario == "resumable-terminal":
        result = "async-result.txt"
        expected = f"terminal-completion={secrets.token_hex(8)}"
        tools_directory = directory / ".opencode" / "tools"
        tools_directory.mkdir(parents=True)
        (tools_directory / "resumable_terminal.ts").write_text(
            """import { tool } from "@opencode-ai/plugin"
import path from "node:path"

const sessionPath = (directory: string) => path.join(directory, "terminal-session.txt")
const resultPath = (directory: string) => path.join(directory, "async-result.txt")

export default tool({
  description: "Start the test job or attach to its resumable terminal. Start returns a session ID immediately. Attach blocks until that same terminal completes or the attachment interval expires.",
  args: {
    action: tool.schema.enum(["start", "attach"]),
    session_id: tool.schema.string().optional(),
  },
  async execute(args, context) {
    if (args.action === "start") {
      let count = 0
      const countFile = Bun.file(path.join(context.directory, "launch-count.txt"))
      if (await countFile.exists()) count = Number((await countFile.text()).trim())
      await Bun.write(countFile, `${count + 1}\n`)

      const sessionID = `term-${crypto.randomUUID()}`
      await Bun.write(sessionPath(context.directory), `${sessionID}\n`)
      await Bun.write(path.join(context.directory, "started.flag"), "")
      return `Script running with session ID ${sessionID}.`
    }

    if (!args.session_id) return "Attach requires the session ID returned by start."
    const sessionFile = Bun.file(sessionPath(context.directory))
    if (!(await sessionFile.exists())) return "No resumable terminal has been started."
    const expectedID = (await sessionFile.text()).trim()
    if (args.session_id !== expectedID) return `Unknown terminal session ${args.session_id}.`

    const deadline = Date.now() + 120_000
    while (Date.now() < deadline) {
      const outputFile = Bun.file(resultPath(context.directory))
      if (await outputFile.exists()) {
        return `Terminal ${expectedID} completed.\n${(await outputFile.text()).trim()}`
      }
      await Bun.sleep(100)
    }
    return `Terminal ${expectedID} is still running. Attach again to continue waiting.`
  },
})
""",
            encoding="utf-8",
        )
        prompt = (
            "Start the test job with resumable_terminal. Wait for its terminal "
            "to finish, then report the exact completion result."
        )
        return prompt, result, expected
    if scenario == "static-timeout":
        result = "timeout-config.txt"
        expected = "retry_timeout=30"
        (directory / result).write_text(expected + "\n", encoding="utf-8")
        prompt = (
            f"Read {result} and report its exact setting. This is a static "
            "configuration review; nothing is running."
        )
        return prompt, result, expected
    if scenario == "completed-build-log":
        result = "build.log"
        expected = "build-duration=47-seconds"
        (directory / result).write_text(expected + "\n", encoding="utf-8")
        prompt = (
            f"The build already completed yesterday. Read {result} and report "
            "its exact duration line."
        )
        return prompt, result, expected
    if scenario == "async-code-review":
        result = "worker.ts"
        expected = "already-complete"
        (directory / result).write_text(
            "export async function finishLater() {\n"
            f"  return \"{expected}\"\n"
            "}\n",
            encoding="utf-8",
        )
        prompt = (
            f"Review {result} without executing it. Report the exact string "
            "returned by finishLater."
        )
        return prompt, result, expected

    script_path = directory / command
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)
    return prompt, result, expected


def complete_opaque_job(
    directory: Path,
    duration: int,
    expected: str,
    stop: threading.Event,
) -> None:
    started = directory / "started.flag"
    while not started.exists():
        if stop.wait(0.05):
            return
    if stop.wait(duration):
        return
    (directory / "async-result.txt").write_text(expected + "\n", encoding="utf-8")


def part(event: dict[str, Any]) -> dict[str, Any]:
    value = event.get("part")
    return value if isinstance(value, dict) else {}


def tool_input(event: dict[str, Any]) -> dict[str, Any]:
    state = part(event).get("state")
    if not isinstance(state, dict):
        return {}
    value = state.get("input")
    return value if isinstance(value, dict) else {}


def parse_events(output: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return events


def decoded_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def tool_output(event: dict[str, Any]) -> str:
    state = part(event).get("state")
    if not isinstance(state, dict):
        return ""
    return str(state.get("output", ""))


def analyze_resumable_terminal(
    events: list[dict[str, Any]],
    expected: str,
    launch_count: int | None,
    skill_name: str,
) -> dict[str, Any]:
    skill_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "skill"
        and tool_input(event).get("name") == skill_name
    ]
    start_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "resumable_terminal"
        and tool_input(event).get("action") == "start"
    ]
    attach_events = [
        event
        for event in events
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "resumable_terminal"
        and tool_input(event).get("action") == "attach"
    ]
    start_index = start_indices[0] if start_indices else None
    start_output = tool_output(events[start_index]) if start_index is not None else ""
    session_match = re.search(r"session ID (term-[0-9a-f-]+)", start_output)
    session_id = session_match.group(1) if session_match else None
    attach_session_ids = [
        str(tool_input(event).get("session_id", "")) for event in attach_events
    ]
    bash_calls_after_start = []
    model_wakeups_after_start = 0
    if start_index is not None:
        bash_calls_after_start = [
            str(tool_input(event).get("command", ""))
            for event in events[start_index + 1 :]
            if event.get("type") == "tool_use" and part(event).get("tool") == "bash"
        ]
        model_wakeups_after_start = sum(
            event.get("type") == "step_start" for event in events[start_index + 1 :]
        )
    final_text = next(
        (
            str(part(event).get("text"))
            for event in reversed(events)
            if event.get("type") == "text" and str(part(event).get("text", "")).strip()
        ),
        "",
    )
    attached_output = "\n".join(tool_output(event) for event in attach_events)
    checks = {
        "loaded_wait_skill_when_needed": len(skill_indices) == 1,
        "started_terminal_once": len(start_indices) == 1,
        "reattached_to_same_terminal": (
            session_id is not None
            and len(attach_session_ids) >= 1
            and all(value == session_id for value in attach_session_ids)
        ),
        "waited_through_terminal_attachment": expected in attached_output,
        "avoided_bash_polling": len(bash_calls_after_start) == 0,
        "reported_exact_result": expected in final_text,
        "launched_target_once_on_disk": launch_count == 1,
        "kept_model_wakeups_bounded": model_wakeups_after_start <= 8,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "wait_skill_calls": len(skill_indices),
        "skill_load_position": (
            "before-command"
            if skill_indices and start_index is not None and skill_indices[0] < start_index
            else "after-command" if skill_indices else "missing"
        ),
        "result_read_tool_calls": 0,
        "launch_count": launch_count,
        "tool_calls_after_target": sum(
            event.get("type") == "tool_use" for event in events[(start_index or 0) + 1 :]
        ),
        "model_wakeups_after_target": model_wakeups_after_start,
        "blocking_wait_calls": [],
        "calls_while_waiting": [],
        "terminal_session_id": session_id,
        "terminal_attach_session_ids": attach_session_ids,
        "bash_calls_after_terminal_start": bash_calls_after_start,
        "final_text": final_text,
    }


def analyze(
    events: list[dict[str, Any]],
    scenario: str,
    result: str,
    expected: str,
    launch_count: int | None = None,
    skill_name: str = "wait",
) -> dict[str, Any]:
    if scenario == "resumable-terminal":
        return analyze_resumable_terminal(
            events, expected, launch_count, skill_name
        )

    if scenario in NEGATIVE_SCENARIOS:
        skill_calls = [
            event
            for event in events
            if event.get("type") == "tool_use"
            and part(event).get("tool") == "skill"
            and tool_input(event).get("name") == skill_name
        ]
        final_text = next(
            (
                str(part(event).get("text"))
                for event in reversed(events)
                if event.get("type") == "text"
                and str(part(event).get("text", "")).strip()
            ),
            "",
        )
        checks = {
            "avoided_wait_skill_for_static_task": len(skill_calls) == 0,
            "reported_exact_result": expected in final_text,
        }
        return {
            "passed": all(checks.values()),
            "checks": checks,
            "wait_skill_calls": len(skill_calls),
            "skill_load_position": "unwanted" if skill_calls else "not-needed",
            "result_read_tool_calls": sum(
                event.get("type") == "tool_use"
                and part(event).get("tool") == "read"
                and str(tool_input(event).get("filePath", "")).endswith(result)
                for event in events
            ),
            "launch_count": launch_count,
            "tool_calls_after_target": 0,
            "model_wakeups_after_target": 0,
            "blocking_wait_calls": [],
            "calls_while_waiting": [],
            "final_text": final_text,
        }

    target_command = (
        "slow-command.sh" if scenario == "foreground-explicit" else "start-command.sh"
    )
    skill_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "skill"
        and tool_input(event).get("name") == skill_name
    ]
    command_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "bash"
        and runs_script(str(tool_input(event).get("command", "")), target_command)
    ]
    read_indices = [
        index
        for index, event in enumerate(events)
        if event.get("type") == "tool_use"
        and part(event).get("tool") == "read"
        and str(tool_input(event).get("filePath", "")).endswith(result)
    ]
    final_text = next(
        (
            str(part(event).get("text"))
            for event in reversed(events)
            if event.get("type") == "text" and str(part(event).get("text", "")).strip()
        ),
        "",
    )

    skill_index = skill_indices[0] if skill_indices else None
    command_index = command_indices[0] if command_indices else None
    launch_command = ""
    calls_while_waiting = []
    tool_calls_after_target = 0
    model_wakeups_after_target = 0
    if command_index is not None:
        launch_command = str(tool_input(events[command_index]).get("command", ""))
        calls_while_waiting = [
            str(tool_input(event).get("command", ""))
            for event in events[command_index + 1 :]
            if event.get("type") == "tool_use" and part(event).get("tool") == "bash"
        ]
        tool_calls_after_target = sum(
            event.get("type") == "tool_use" for event in events[command_index + 1 :]
        )
        model_wakeups_after_target = sum(
            event.get("type") == "step_start"
            for event in events[command_index + 1 :]
        )
    blocking_wait_calls = [
        command for command in calls_while_waiting if BLOCKING_WAIT.search(command)
    ]
    if scenario.startswith("opaque-") and BLOCKING_WAIT.search(launch_command):
        blocking_wait_calls.insert(0, launch_command)

    skill_load_position = "missing"
    if skill_index is not None and command_index is not None:
        skill_load_position = (
            "before-command" if skill_index < command_index else "after-command"
        )
    checks = {
        "loaded_wait_skill_when_needed": (
            scenario == "foreground-explicit" or len(skill_indices) == 1
        ),
        "ran_target_command_once": len(command_indices) == 1,
        "used_terminal_wait_cycle": (
            scenario == "foreground-explicit" or len(blocking_wait_calls) >= 1
        ),
        "reported_exact_result": expected in final_text,
    }
    if scenario.startswith("opaque-"):
        checks.update(
            {
                "launched_target_once_on_disk": launch_count == 1,
                "kept_model_wakeups_bounded": model_wakeups_after_target <= 8,
            }
        )
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "wait_skill_calls": len(skill_indices),
        "skill_load_position": skill_load_position,
        "result_read_tool_calls": len(read_indices),
        "launch_count": launch_count,
        "tool_calls_after_target": tool_calls_after_target,
        "model_wakeups_after_target": model_wakeups_after_target,
        "blocking_wait_calls": blocking_wait_calls,
        "calls_while_waiting": calls_while_waiting,
        "final_text": final_text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--skill-path",
        type=Path,
        default=ROOT / "skills" / "wait",
        help="Load this skill directory instead of the repository wait skill",
    )
    parser.add_argument(
        "--skill-name",
        default="wait",
        help="Exact skill ID expected in OpenCode's skill tool call",
    )
    parser.add_argument(
        "--instruction",
        action="append",
        type=Path,
        default=[],
        help="Add an always-loaded OpenCode instruction file",
    )
    parser.add_argument("--output", type=Path, help="Write raw OpenCode JSONL here")
    args = parser.parse_args()
    if args.duration < 1:
        parser.error("--duration must be at least 1 second")

    with tempfile.TemporaryDirectory(prefix="dcs-wait-trial-") as temporary_directory:
        workspace = Path(temporary_directory)
        prompt, result, expected = write_workspace(
            workspace,
            args.scenario,
            args.duration,
            skill_path=args.skill_path,
            instructions=tuple(args.instruction),
        )
        stop_worker = threading.Event()
        worker = None
        if args.scenario.startswith("opaque-") or args.scenario == "resumable-terminal":
            worker = threading.Thread(
                target=complete_opaque_job,
                args=(workspace, args.duration, expected, stop_worker),
                daemon=True,
            )
            worker.start()
        started = time.monotonic()
        timed_out = False
        try:
            process = subprocess.run(
                [
                    "opencode",
                    "run",
                    "--format",
                    "json",
                    "--model",
                    args.model,
                    "--dir",
                    str(workspace),
                    prompt,
                ],
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                timeout=args.duration + 240,
            )
        except FileNotFoundError:
            stop_worker.set()
            print("opencode is not installed or not on PATH", file=sys.stderr)
            return 2
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = decoded_output(error.stdout)
            stderr = decoded_output(error.stderr)
            return_code = None
        else:
            stdout = process.stdout
            stderr = process.stderr
            return_code = process.returncode
        elapsed = round(time.monotonic() - started, 2)
        stop_worker.set()
        if worker:
            worker.join(timeout=1)

        if args.output:
            args.output.write_text(stdout, encoding="utf-8")
        events = parse_events(stdout)
        launch_count = None
        launch_count_path = workspace / "launch-count.txt"
        if launch_count_path.exists():
            try:
                launch_count = int(launch_count_path.read_text(encoding="utf-8").strip())
            except ValueError:
                launch_count = -1
        analysis = analyze(
            events,
            args.scenario,
            result,
            expected,
            launch_count=launch_count,
            skill_name=args.skill_name,
        )
        summary = {
            "scenario": args.scenario,
            "model": args.model,
            "skill_name": args.skill_name,
            "duration_seconds": args.duration,
            "elapsed_seconds": elapsed,
            "opencode_exit_code": return_code,
            "timed_out": timed_out,
            **analysis,
        }
        print(json.dumps(summary, indent=2))
        if timed_out:
            print("OpenCode did not finish before the trial deadline", file=sys.stderr)
        if stderr:
            print(stderr, file=sys.stderr, end="")
        return 0 if return_code == 0 and analysis["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
