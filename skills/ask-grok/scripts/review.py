#!/usr/bin/env python3
"""Run one grok review and preserve its complete response unchanged."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

END_MARKER = "REVIEW_COMPLETE"
PROVIDER = 'grok'
SETTINGS = {'model': 'grok-4.6', 'effort': 'xhigh'}


def save_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_hashes(source):
    hashes = {}
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Snapshot must contain actual files, not symlinks: {path}")
        if path.is_file():
            hashes[str(path.relative_to(source))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def extract_review(envelope):
    """Return the exact response string, a completion problem, and session ID."""
    if not isinstance(envelope, dict):
        return "", "CLI output is not a JSON object", None
    text = envelope.get("text", "")
    session = envelope.get("sessionId")
    good = envelope.get("stopReason") == "end_turn" and not envelope.get("error")
    reason = "Grok did not report end_turn"
    if not isinstance(text, str):
        return "", "CLI response field is not a string", session
    if not good:
        return text, reason, session
    if not text.strip():
        return text, "CLI returned an empty response", session
    # The common prompt requests this final line; never add it to a response.
    lines = text.rstrip().splitlines()
    if lines[-1] != END_MARKER or not "\n".join(lines[:-1]).strip():
        return text, "Full review completion marker is missing", session
    return text, None, session


def extract_grok_stream(raw, tool_errors=None):
    """Preserve text deltas only; thoughts and tool payloads stay in the raw log."""
    parts, endings = [], []
    problem, last_type = None, None
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError("event is not an object")
        except (ValueError, UnicodeError) as error:
            problem = f"Invalid Grok stream event: {error}"
            continue
        last_type = event.get("type")
        if last_type == "text":
            if isinstance(event.get("data"), str):
                parts.append(event["data"])
            else:
                problem = "Grok text event is not a string"
        elif last_type == "end":
            endings.append(event)
        elif last_type == "error":
            problem = "Grok stream reported an error"
        elif last_type == "tool_call_update" and event.get("status") == "failed":
            # A later successful read can recover a bad path. Preserve the warning
            # for coverage assessment without mislabeling a full final response.
            if tool_errors is not None:
                tool_errors.append(event)
    text = "".join(parts)
    terminal = endings[0] if len(endings) == 1 else {}
    if len(endings) != 1 or last_type != "end":
        problem = problem or "Grok stream has no single final end event"
    envelope = {**terminal, "text": text}
    _, completion_problem, session = extract_review(envelope)
    return text, problem or completion_problem, session


def command_for(source, prompt_path, directory, timeout):
    return (["grok", "--model", SETTINGS["model"], "--reasoning-effort", SETTINGS["effort"],
             "--permission-mode", "plan", "--no-subagents", "--tools", "Read,Grep,Glob",
             "--output-format", "streaming-json", "--prompt-file", str(prompt_path)], source)


def terminate_process(process):
    """Terminate only this invocation's process group, never a shared CLI service."""
    for sig, grace in [(signal.SIGTERM, 5), (signal.SIGKILL, None)]:
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=grace)
            return
        except subprocess.TimeoutExpired:
            pass


def run_process(command, cwd, stdin_path, stdout_path, stderr_path, timeout, cancelled=None):
    cancelled = cancelled or threading.Event()
    with stdin_path.open("rb") as stdin, stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        if cancelled.is_set():
            return None, "canceled"
        process = subprocess.Popen(command, cwd=cwd, stdin=stdin, stdout=stdout, stderr=stderr,
                                   start_new_session=True)
        deadline = time.monotonic() + timeout
        while not cancelled.is_set() and time.monotonic() < deadline:
            try:
                return process.wait(timeout=min(1, max(0.001, deadline - time.monotonic()))), None
            except subprocess.TimeoutExpired:
                pass
        terminate_process(process)
        return process.returncode, "canceled" if cancelled.is_set() else "timeout"


def collect_review(source, prompt_path, output, timeout, cancelled=None):
    directory = output
    result = {"provider": PROVIDER, "requested": SETTINGS, "status": "running",
              "stdout": str(directory / 'stdout.jsonl'),
              "stderr": str(directory / "stderr.txt")}
    started = time.monotonic()
    text = ""
    try:
        save_json(directory / "status.json", result)
        command, cwd = command_for(source, prompt_path, directory, timeout)
        input_path = Path(os.devnull)
        code, termination = run_process(command, cwd, input_path, Path(result["stdout"]),
                                        Path(result["stderr"]), timeout, cancelled)
        result.update(exit_code=code, timed_out=termination == "timeout", canceled=termination == "canceled")
        try:
            raw = Path(result["stdout"]).read_bytes()
            tool_errors = []
            text, problem, session = extract_grok_stream(raw, tool_errors)
            if tool_errors:
                result["tool_errors"] = tool_errors
            result["session_id"] = session
        except (ValueError, UnicodeError) as error:
            problem = f"No valid final JSON envelope: {error}"
        if termination:
            reason = "Collection canceled" if termination == "canceled" else f"Review exceeded {timeout} seconds"
            result.update(status="incomplete", reason=reason)
        elif code != 0:
            result.update(status="failed", reason=f"CLI exited {code}; see stderr")
        elif problem:
            result.update(status="incomplete", reason=problem)
        else:
            result["status"] = "completed"
        if text:
            path = directory / ("review.txt" if result["status"] == "completed" else "partial.txt")
            path.write_bytes(text.encode("utf-8"))
            result["review" if result["status"] == "completed" else "partial"] = str(path)
    except (OSError, ValueError) as error:
        result.update(status="failed", reason=str(error))
    result["seconds"] = round(time.monotonic() - started, 2)
    try:
        save_json(directory / "status.json", result)
    except OSError as error:
        result["status_write_error"] = str(error)
    print(json.dumps({"provider": PROVIDER, "status": result["status"], "seconds": result["seconds"]}), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Prepared source snapshot")
    parser.add_argument("--prompt", type=Path, required=True, help="Review request")
    parser.add_argument("--out", type=Path, required=True, help="New artifact directory outside source")
    parser.add_argument("--timeout", type=int, default=1800, help="Review deadline in seconds (default: 1800)")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.out.resolve()
    if not source.is_dir() or output.is_relative_to(source) or args.timeout <= 0:
        parser.error("Source must be a directory, output outside it, and timeout positive")
    prompt = args.prompt.read_text(encoding="utf-8")
    if not prompt.strip():
        parser.error("The review request must not be empty")
    prompt += (f"\n\nReview transport instructions:\nSource snapshot: {source}\n"
               "Use file-reading/search tools to inspect that source; shell commands, edits, "
               "other agents, and other reviewers' artifacts are outside this review. "
               "Return the complete review in your final answer. Identify coverage gaps. "
               "Do not truncate or summarize an existing review. "
               f"Finish your complete review with the exact final line {END_MARKER}.\n")
    if len(prompt.encode("utf-8")) > 60000:
        parser.error("Keep the prompt under 60000 bytes; put source/context in the snapshot")
    before = source_hashes(source)
    if not before:
        parser.error("The source snapshot must not be empty")
    output.mkdir(parents=True, exist_ok=False)
    prompt_path = output / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    save_json(output / "source-files.json", before)
    cancelled = threading.Event()
    handlers = {sig: signal.signal(sig, lambda *_: cancelled.set())
                for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        result = collect_review(source, prompt_path, output, args.timeout, cancelled)
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    result.update(source=str(source), prompt=str(prompt_path), timeout_seconds=args.timeout,
                  prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest())
    try:
        after = source_hashes(source)
        result["source_unchanged"] = before == after
        if before != after:
            result["changed_files"] = sorted(k for k in before.keys() | after.keys()
                                             if before.get(k) != after.get(k))
    except (OSError, ValueError) as error:
        result.update(source_unchanged=False, source_check_error=str(error))
    save_json(output / "status.json", result)
    print(json.dumps({"status_file": str(output / "status.json"),
                      "status": result["status"], "source_unchanged": result["source_unchanged"]}), flush=True)
    return 0 if result["source_unchanged"] and result["status"] == "completed" else 1



if __name__ == "__main__":
    raise SystemExit(main())
