#!/usr/bin/env python3
"""Compare isolated wait-skill discovery variants through OpenCode."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from .run_wait_skill_matrix import failed_checks, safe_name, summarize
    from .run_wait_skill_trial import SCENARIOS
except ImportError:
    from run_wait_skill_matrix import failed_checks, safe_name, summarize
    from run_wait_skill_trial import SCENARIOS


ROOT = Path(__file__).resolve().parents[1]
TRIAL_RUNNER = ROOT / "tools" / "run_wait_skill_trial.py"
SOURCE_SKILL = ROOT / "skills" / "wait" / "SKILL.md"
SCREEN_MODELS = (
    "opencode-go/hy3",
    "opencode-go/mimo-v2.5",
    "opencode-go/qwen3.7-plus",
    "opencode-go/kimi-k2.6",
)


@dataclass(frozen=True)
class Variant:
    key: str
    skill_name: str
    description: str
    router_instruction: str | None = None


def source_parts() -> tuple[str, str]:
    source = SOURCE_SKILL.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(?P<frontmatter>.*?)\n---\n(?P<body>.*)\Z", source, re.S)
    if not match:
        raise ValueError(f"invalid skill frontmatter in {SOURCE_SKILL}")
    description_match = re.search(
        r"^description:\s*(?P<description>.+)$",
        match.group("frontmatter"),
        re.M,
    )
    if not description_match:
        raise ValueError(f"missing description in {SOURCE_SKILL}")
    return description_match.group("description").strip(), match.group("body")


def variants() -> dict[str, Variant]:
    baseline_description, _ = source_parts()
    values = (
        Variant("baseline", "wait", baseline_description),
        Variant(
            "imperative-intent",
            "wait",
            "Use this skill when a task depends on a command, job, process, file, "
            "service, or external state becoming ready later. Invoke it before "
            "monitoring or checking for completion, including background work, "
            "uncertain durations, and prompts that only ask for the eventual result.",
        ),
        Variant(
            "concrete-capability",
            "wait",
            "Block efficiently until asynchronous work becomes ready while keeping "
            "the model inactive. Use this skill whenever a task cannot continue "
            "until a command, job, process, file, service, or external state changes, "
            "including unknown durations and prompts that only ask for the eventual "
            "result.",
        ),
        Variant(
            "await-completion",
            "await-completion",
            "Use this skill whenever completing the task requires awaiting a command, "
            "job, process, file, service, or external state. Invoke it for background "
            "work and delayed results even when no wait is requested and no duration "
            "is known.",
        ),
        Variant(
            "eventual-result",
            "wait",
            "Use this skill whenever the requested result will appear only after a "
            "command, job, process, file, service, or external state finishes or "
            "changes. This includes background work, delayed output, unknown timing, "
            "and requests that never explicitly mention waiting.",
        ),
        Variant(
            "result-dependency",
            "wait",
            "Use this skill whenever the requested result depends on a command, "
            "job, process, file, service, or external state becoming ready later. "
            "Load it before monitoring or checking for completion, including "
            "background work, unknown timing, and requests that never explicitly "
            "mention waiting.",
        ),
        Variant(
            "router-control",
            "wait",
            baseline_description,
            "When the requested result depends on a command, job, process, file, "
            "service, or external state becoming ready later, load the wait skill "
            "before continuing.",
        ),
    )
    return {variant.key: variant for variant in values}


def write_variant(directory: Path, variant: Variant, body: str) -> tuple[Path, Path | None]:
    skill_path = directory / variant.key / variant.skill_name
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text(
        "---\n"
        f"name: {variant.skill_name}\n"
        f"description: {variant.description}\n"
        "---\n"
        f"{body}",
        encoding="utf-8",
    )
    instruction_path = None
    if variant.router_instruction:
        instruction_path = directory / variant.key / "router.md"
        instruction_path.write_text(
            variant.router_instruction + "\n", encoding="utf-8"
        )
    return skill_path, instruction_path


def triggered(result: dict[str, Any]) -> bool:
    checks = result.get("checks")
    return isinstance(checks, dict) and checks.get(
        "loaded_wait_skill_when_needed"
    ) is True


def unwanted_trigger(result: dict[str, Any]) -> bool:
    checks = result.get("checks")
    return isinstance(checks, dict) and checks.get(
        "avoided_wait_skill_for_static_task"
    ) is False


def summarize_variants(
    results: list[dict[str, Any]], selected: list[Variant]
) -> dict[str, Any]:
    summaries: dict[str, Any] = {}
    for variant in selected:
        variant_results = [
            result for result in results if result.get("variant") == variant.key
        ]
        outcome = summarize(variant_results)
        trigger_count = sum(triggered(result) for result in variant_results)
        unwanted_trigger_count = sum(
            unwanted_trigger(result) for result in variant_results
        )
        summaries[variant.key] = {
            "skill_name": variant.skill_name,
            "description": variant.description,
            "router_instruction": variant.router_instruction,
            "triggered": trigger_count,
            "trigger_rate": trigger_count / len(variant_results),
            "unwanted_triggers": unwanted_trigger_count,
            "unwanted_trigger_rate": unwanted_trigger_count / len(variant_results),
            **outcome,
        }
    return summaries


def main() -> int:
    available = variants()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", nargs="+", choices=available, default=list(available))
    parser.add_argument("--scenario", choices=SCENARIOS, default="opaque-implicit")
    parser.add_argument("--models", nargs="+", default=SCREEN_MODELS)
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--duration", type=int, default=12)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    if args.duration < 1:
        parser.error("--duration must be at least 1 second")
    if args.output_dir:
        args.output_dir.mkdir(parents=True, exist_ok=True)

    selected = [available[key] for key in args.variants]
    _, body = source_parts()
    results: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="dcs-wait-variants-") as temporary_directory:
        variant_root = Path(temporary_directory)
        for variant in selected:
            skill_path, instruction_path = write_variant(variant_root, variant, body)
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
                        "--skill-path",
                        str(skill_path),
                        "--skill-name",
                        variant.skill_name,
                    ]
                    if instruction_path:
                        command.extend(["--instruction", str(instruction_path)])
                    if args.output_dir:
                        output_path = args.output_dir / (
                            f"{variant.key}-{safe_name(model)}-{trial_number}.jsonl"
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
                    result.update(
                        {
                            "variant": variant.key,
                            "trial": trial_number,
                            "runner_exit_code": process.returncode,
                        }
                    )
                    if process.stderr:
                        result["runner_stderr"] = process.stderr
                    results.append(result)
                    print(
                        json.dumps(
                            {
                                "event": "trial",
                                "variant": variant.key,
                                "model": model,
                                "trial": trial_number,
                                "triggered": triggered(result),
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
        "models": args.models,
        "variants": summarize_variants(results, selected),
    }
    if args.summary:
        args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"event": "summary", **summary}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
