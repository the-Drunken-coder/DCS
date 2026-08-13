#!/usr/bin/env python3
"""Check or synchronize third-party skills listed in upstreams.json."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "upstreams.json"
PLUGIN_MANIFEST = ROOT / ".codex-plugin" / "plugin.json"
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PLAIN_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Upstream:
    name: str
    repository: str
    ref: str
    path: PurePosixPath
    destination: PurePosixPath

    @property
    def source(self) -> str:
        return f"{self.repository}@{self.ref}:{self.path}"


@dataclass(frozen=True)
class Result:
    upstream: Upstream
    commit: str
    changes: tuple[str, ...]


def relative_path(value: object, field: str) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise SyncError(f"{field} must be a non-empty string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path == PurePosixPath(".")
        or ".." in path.parts
        or path.parts[0].startswith("-")
    ):
        raise SyncError(f"{field} must be a safe relative path")
    return path


def load_registry(path: Path) -> list[Upstream]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read {path}: {error}") from error
    if not isinstance(data, dict) or data.get("schemaVersion") != 1:
        raise SyncError("upstreams.json must use schemaVersion 1")
    if not isinstance(data.get("skills"), list):
        raise SyncError("upstreams.json skills must be an array")

    upstreams: list[Upstream] = []
    names: set[str] = set()
    for index, raw in enumerate(data["skills"]):
        label = f"skills[{index}]"
        fields = {"name", "repository", "ref", "path", "destination"}
        if not isinstance(raw, dict) or set(raw) != fields:
            raise SyncError(f"{label} must contain exactly: {', '.join(sorted(fields))}")

        name = raw["name"]
        repository = raw["repository"]
        ref = raw["ref"]
        if not isinstance(name, str) or not SKILL_NAME.fullmatch(name):
            raise SyncError(f"{label}.name must be lower-case hyphen-case")
        if not isinstance(repository, str) or not GITHUB_REPOSITORY.fullmatch(repository):
            raise SyncError(f"{label}.repository must be a GitHub owner/repo")
        if not isinstance(ref, str) or not ref.strip() or ref.startswith("-") or "\n" in ref:
            raise SyncError(f"{label}.ref must be a safe Git ref")

        source_path = relative_path(raw["path"], f"{label}.path")
        destination = relative_path(raw["destination"], f"{label}.destination")
        if destination != PurePosixPath("skills") / name:
            raise SyncError(f"{label}.destination must be skills/{name}")
        if name in names:
            raise SyncError(f"{label}.name is duplicated")

        names.add(name)
        upstreams.append(Upstream(name, repository, ref, source_path, destination))
    return upstreams


def git(*arguments: str, cwd: Path | None = None) -> str:
    process = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise SyncError(f"git {' '.join(arguments)} failed: {detail}")
    return process.stdout.strip()


def reject_symlinks(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_symlink():
            raise SyncError(f"{root} contains a symlink: {path.relative_to(root)}")


def validate_skill(directory: Path, expected_name: str) -> None:
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        raise SyncError(f"{directory} must contain SKILL.md")
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError(f"cannot read {skill_file}: {error}") from error
    if not lines or lines[0] != "---":
        raise SyncError(f"{skill_file} must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise SyncError(f"{skill_file} has unterminated YAML frontmatter") from error

    fields: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip().strip("\"'")
    if fields.get("name") != expected_name:
        raise SyncError(f"{skill_file} name must be {expected_name!r}")
    if not fields.get("description"):
        raise SyncError(f"{skill_file} must have a description")


def checkout(upstream: Upstream, parent: Path) -> tuple[Path, str]:
    checkout_root = parent / upstream.name
    url = f"https://github.com/{upstream.repository}.git"
    git(
        "clone",
        "--quiet",
        "--depth=1",
        "--filter=blob:none",
        "--sparse",
        "--branch",
        upstream.ref,
        url,
        str(checkout_root),
    )
    git("sparse-checkout", "set", str(upstream.path), cwd=checkout_root)
    source = checkout_root.joinpath(*upstream.path.parts)
    if not source.is_dir() or not source.resolve().is_relative_to(checkout_root.resolve()):
        raise SyncError(f"{upstream.source} is not a safe directory")
    reject_symlinks(source)
    validate_skill(source, upstream.name)
    return source, git("rev-parse", "HEAD", cwd=checkout_root)


def snapshot(root: Path) -> dict[str, tuple[str, bool]]:
    if not root.exists():
        return {}
    if not root.is_dir():
        raise SyncError(f"{root} is not a directory")
    reject_symlinks(root)

    files: dict[str, tuple[str, bool]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            executable = bool(path.stat().st_mode & stat.S_IXUSR)
            files[relative] = (digest, executable)
    return files


def describe_changes(current: dict[str, tuple[str, bool]], incoming: dict[str, tuple[str, bool]]) -> tuple[str, ...]:
    changes: list[str] = []
    for path in sorted(set(current) | set(incoming)):
        if path not in current:
            changes.append(f"added {path}")
        elif path not in incoming:
            changes.append(f"removed {path}")
        elif current[path] != incoming[path]:
            changes.append(f"changed {path}")
    return tuple(changes)


def replace_directory(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f".{destination.name}-", dir=destination.parent) as temp:
        replacement = Path(temp) / destination.name
        backup = Path(temp) / "previous"
        shutil.copytree(source, replacement)
        if destination.exists():
            destination.rename(backup)
        try:
            replacement.rename(destination)
        except Exception:
            if backup.exists() and not destination.exists():
                backup.rename(destination)
            raise


def validate_plugin() -> None:
    try:
        manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read plugin manifest: {error}") from error
    if manifest.get("name") != "dcs" or manifest.get("skills") != "./skills/":
        raise SyncError("plugin manifest must describe the root DCS skill plugin")
    if not isinstance(manifest.get("version"), str):
        raise SyncError("plugin manifest must have a version")
    for directory in sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir()):
        validate_skill(directory, directory.name)


def plugin_version(bump: bool = False) -> str:
    manifest = json.loads(PLUGIN_MANIFEST.read_text(encoding="utf-8"))
    version = manifest.get("version")
    if not bump:
        return version
    match = PLAIN_SEMVER.fullmatch(version) if isinstance(version, str) else None
    if not match:
        raise SyncError("automatic patch bumps require a plain x.y.z plugin version")
    major, minor, patch = (int(value) for value in match.groups())
    version = f"{major}.{minor}.{patch + 1}"
    manifest["version"] = version
    PLUGIN_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return version


def synchronize(registry: Path, write: bool) -> tuple[list[Result], bool]:
    results: list[Result] = []
    staged: list[tuple[Path, Path]] = []
    with tempfile.TemporaryDirectory(prefix="dcs-upstreams-") as temp:
        for upstream in load_registry(registry):
            source, commit = checkout(upstream, Path(temp))
            destination = ROOT.joinpath(*upstream.destination.parts)
            changes = describe_changes(snapshot(destination), snapshot(source))
            if changes:
                staged.append((source, destination))
            results.append(Result(upstream, commit, changes))
        if write:
            for source, destination in staged:
                replace_directory(source, destination)
    return results, bool(staged)


def report(results: list[Result], changed: bool, version: str) -> str:
    lines = [
        "## Upstream skill sync",
        "",
        f"DCS upstream skills are **{'changed' if changed else 'up to date'}**.",
        "",
        "| Skill | Source | Commit | State |",
        "| --- | --- | --- | --- |",
    ]
    for result in results:
        state = "changed" if result.changes else "current"
        lines.append(f"| `{result.upstream.name}` | `{result.upstream.source}` | `{result.commit}` | {state} |")
    lines.extend(
        [
            "",
            f"Plugin version: `{version}`",
            "",
            "Review all imported instruction changes before opening and merging a pull request. This automation never changes main.",
            "",
        ]
    )
    return "\n".join(lines)


def write_automation_output(results: list[Result], changed: bool, version: str, markdown: str) -> None:
    if output := os.environ.get("GITHUB_OUTPUT"):
        commits = ", ".join(f"{result.upstream.name}:{result.commit}" for result in results)
        with Path(output).open("a", encoding="utf-8") as file:
            file.write(f"changed={'true' if changed else 'false'}\n")
            file.write(f"version={version}\n")
            file.write(f"commits={commits}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as file:
            file.write(markdown)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--sync", action="store_true")
    mode.add_argument("--validate", action="store_true")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--bump-plugin-version", action="store_true")
    args = parser.parse_args()
    if args.bump_plugin_version and not args.sync:
        parser.error("--bump-plugin-version requires --sync")
    return args


def main() -> int:
    args = parse_args()
    registry = args.registry.resolve()
    if args.validate:
        load_registry(registry)
        validate_plugin()
        print("DCS plugin and upstream registry are valid.")
        return 0

    results, changed = synchronize(registry, write=args.sync)
    version = plugin_version(changed and args.bump_plugin_version)
    if args.sync:
        validate_plugin()

    for result in results:
        print(f"{result.upstream.name}: {'changed' if result.changes else 'current'} at {result.commit}")
        for change in result.changes:
            print(f"  {change}")

    markdown = report(results, changed, version)
    write_automation_output(results, changed, version, markdown)
    if args.check and changed:
        print("Upstream drift detected. Run the manual sync workflow to open an update PR.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SyncError as error:
        prefix = "::error::" if os.environ.get("GITHUB_ACTIONS") else "error: "
        print(f"{prefix}{error}", file=sys.stderr)
        raise SystemExit(2)
