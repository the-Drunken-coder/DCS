#!/usr/bin/env python3
"""Run repeated wait-skill trials sequentially and summarize reliability."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .run_wait_skill_trial import SCENARIOS
except ImportError:
    from run_wait_skill_trial import SCENARIOS


ROOT = Path(__file__).resolve().parents[1]
TRIAL_RUNNER = ROOT / "tools" / "run_wait_skill_trial.py"
CHEAP_GO_MODELS = (
    "opencode-go/hy3",
    "opencode-go/mimo-v2.5",
    "opencode-go/gpt-5.6-luna",
    "opencode-go/minimax-m3",
    "opencode-go/qwen3.7-plus",
    "opencode-go/kimi-k2.6",
)


def safe_name(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", model).strip("-")


def failed_checks(result: dict[str, Any]) -> list[str]:
    checks = result.get("checks")
    if not isinstance(checks, dict):
        return ["missing_checks"]
    return [name for name, passed in checks.items() if passed is not True]


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    models: dict[str, dict[str, Any]] = {}
    for result in results:
        model = str(result.get("model", "unknown"))
        summary = models.setdefault(
            model,
            {"passed": 0, "trials": 0, "failures": []},
        )
        summary["trials"] += 1
        if result.get("passed") is True:
            summary["passed"] += 1
        else:
            summary["failures"].append(
                {
                    "trial": result.get("trial"),
                    "failed_checks": failed_checks(result),
                    "timed_out": result.get("timed_out"),
                    "opencode_exit_code": result.get("opencode_exit_code"),
                }
            )
    for summary in models.values():
        summary["pass_rate"] = summary["passed"] / summary["trials"]
    return {
        "all_passed": all(result.get("passed") is True for result in results),
        "total_passed": sum(result.get("passed") is True for result in results),
        "total_trials": len(results),
        "models": models,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="opaque-implicit")
    parser.add_argument("--duration", type=int, default=12)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--models", nargs="+", default=CHEAP_GO_MODELS)
    parser.add_argument("--skill-path", type=Path)
    parser.add_argument("--skill-name", default="wait")
    parser.add_argument("--instruction", action="append", type=Path, default=[])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if args.duration < 1:
        parser.error("--duration must be at least 1 second")
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for model in args.models:
        for trial_number in range(1, args.repeat + 1):
            command = [
                sys.executable,
                "-B",
                str(TRIAL_RUNNER),
                args.scenario,
                "--duration",
                str(args.duration),
                "--model",
                model,
                "--skill-name",
                args.skill_name,
            ]
            if args.skill_path:
                command.extend(["--skill-path", str(args.skill_path)])
            for instruction in args.instruction:
                command.extend(["--instruction", str(instruction)])
            if args.output_dir:
                output_path = (
                    args.output_dir / f"{safe_name(model)}-{trial_number}.jsonl"
                )
                command.extend(["--output", str(output_path)])
            process = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            try:
                result = json.loads(process.stdout)
            except json.JSONDecodeError:
                result = {
                    "model": model,
                    "passed": False,
                    "checks": {"returned_valid_summary": False},
                    "opencode_exit_code": process.returncode,
                    "timed_out": False,
                    "stdout": process.stdout,
                }
            result["trial"] = trial_number
            result["runner_exit_code"] = process.returncode
            if process.stderr:
                result["runner_stderr"] = process.stderr
            results.append(result)
            print(
                json.dumps(
                    {
                        "event": "trial",
                        "model": model,
                        "trial": trial_number,
                        "passed": result.get("passed"),
                        "elapsed_seconds": result.get("elapsed_seconds"),
                        "failed_checks": failed_checks(result),
                    }
                ),
                flush=True,
            )

    summary = {
        "scenario": args.scenario,
        "duration_seconds": args.duration,
        "repeat": args.repeat,
        "skill_name": args.skill_name,
        **summarize(results),
    }
    if args.summary:
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "summary", **summary}, indent=2), flush=True)
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
