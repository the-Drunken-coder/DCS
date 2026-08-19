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

import yaml
from yaml.nodes import MappingNode, ScalarNode
from yaml.tokens import ScalarToken


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "upstreams.json"
UPSTREAM_LOCK = ROOT / "upstreams.lock.json"
PLUGIN_MANIFEST = ROOT / "plugin.json"
PLUGIN_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
PLUGIN_FIELDS = {
    "$schema",
    "name",
    "version",
    "description",
    "author",
    "homepage",
    "repository",
    "license",
    "keywords",
    "extensions",
}
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PLAIN_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
EXTENSION_NAMESPACE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$"
)
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
SKILL_FIELDS = {"name", "description", "license", "allowed-tools", "metadata"}
MAX_SKILL_NAME_LENGTH = 64
DCS_DISPLAY_PREFIX = "DCS: "
PSTACK_ADAPTER = "pstack-single-skill"
SUPPORTED_ADAPTERS = {"cursor-manual-only", PSTACK_ADAPTER}


class SyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class Upstream:
    name: str
    repository: str
    ref: str
    path: PurePosixPath
    destination: PurePosixPath
    adapter: str | None
    overlay: PurePosixPath | None
    patch: PurePosixPath | None

    @property
    def source(self) -> str:
        return f"{self.repository}@{self.ref}:{self.path}"


@dataclass(frozen=True)
class Result:
    upstream: Upstream
    commit: str
    tree: str
    changes: tuple[str, ...]


def tracks_source_tree(upstream: Upstream) -> bool:
    return bool(upstream.adapter or upstream.overlay or upstream.patch)


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
        required = {"name", "repository", "ref", "path", "destination"}
        optional = {"adapter", "overlay", "patch"}
        if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - required - optional:
            raise SyncError(f"{label} must contain required fields and only supported adapter fields")

        name = raw["name"]
        repository = raw["repository"]
        ref = raw["ref"]
        if (
            not isinstance(name, str)
            or not SKILL_NAME.fullmatch(name)
            or len(name) > MAX_SKILL_NAME_LENGTH
        ):
            raise SyncError(f"{label}.name must be lower-case hyphen-case")
        if not isinstance(repository, str) or not GITHUB_REPOSITORY.fullmatch(repository):
            raise SyncError(f"{label}.repository must be a GitHub owner/repo")
        if not isinstance(ref, str) or not ref.strip() or ref.startswith("-") or "\n" in ref:
            raise SyncError(f"{label}.ref must be a safe Git ref")

        source_path = relative_path(raw["path"], f"{label}.path")
        destination = relative_path(raw["destination"], f"{label}.destination")
        adapter = raw.get("adapter")
        if adapter is not None and (
            not isinstance(adapter, str) or adapter not in SUPPORTED_ADAPTERS
        ):
            raise SyncError(f"{label}.adapter is not supported")
        overlay = relative_path(raw["overlay"], f"{label}.overlay") if "overlay" in raw else None
        patch = relative_path(raw["patch"], f"{label}.patch") if "patch" in raw else None
        if overlay and overlay.parts[0] != "ports":
            raise SyncError(f"{label}.overlay must live under ports/")
        if patch and (patch.parts[0] != "ports" or patch.suffix != ".patch"):
            raise SyncError(f"{label}.patch must be a .patch file under ports/")
        if destination != PurePosixPath("skills") / name:
            raise SyncError(f"{label}.destination must be skills/{name}")
        if adapter == PSTACK_ADAPTER and (
            name != "pstack"
            or repository != "cursor/plugins"
            or ref != "main"
            or source_path != PurePosixPath("pstack")
            or overlay != PurePosixPath("ports/pstack")
            or patch is not None
        ):
            raise SyncError(
                f"{label} pstack adapter must use cursor/plugins@main:pstack -> "
                "skills/pstack with ports/pstack"
            )
        if name in names:
            raise SyncError(f"{label}.name is duplicated")

        names.add(name)
        upstreams.append(Upstream(name, repository, ref, source_path, destination, adapter, overlay, patch))
    return upstreams


def load_lock_state(
    path: Path | None = None, required: bool = True
) -> tuple[dict[str, str], set[str]]:
    path = path or UPSTREAM_LOCK
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if required:
            raise SyncError(f"missing upstream lock: {path}") from None
        return {}, set()
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read {path}: {error}") from error
    skills = data.get("skills") if isinstance(data, dict) and data.get("schemaVersion") == 1 else None
    if not isinstance(skills, dict) or any(
        not isinstance(name, str)
        or not SKILL_NAME.fullmatch(name)
        or not isinstance(tree, str)
        or not re.fullmatch(r"[0-9a-f]{40}", tree)
        for name, tree in skills.items()
    ):
        raise SyncError("upstreams.lock.json must contain skill names mapped to Git tree hashes")
    managed_value = data.get("managedSkills", list(skills))
    if (
        not isinstance(managed_value, list)
        or any(not isinstance(name, str) or not SKILL_NAME.fullmatch(name) for name in managed_value)
        or len(managed_value) != len(set(managed_value))
    ):
        raise SyncError("upstreams.lock.json managedSkills must contain unique skill names")
    managed = set(managed_value)
    if not set(skills) <= managed:
        raise SyncError("upstreams.lock.json managedSkills must include every source-tree lock")
    return skills, managed


def load_lock(path: Path | None = None, required: bool = True) -> dict[str, str]:
    return load_lock_state(path, required)[0]


def write_lock(
    trees: dict[str, str], path: Path | None = None, *, managed: set[str] | None = None
) -> None:
    path = path or UPSTREAM_LOCK
    managed = set(trees) if managed is None else managed
    content = json.dumps(
        {
            "schemaVersion": 1,
            "skills": dict(sorted(trees.items())),
            "managedSkills": sorted(managed),
        },
        indent=2,
    ) + "\n"
    write_bytes_atomic(path, content.encode())


def write_bytes_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(content)
        temporary.chmod(path.stat().st_mode if path.exists() else 0o644)
        temporary.replace(path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


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


def validate_skill(
    directory: Path, expected_name: str, strict: bool = True
) -> dict[str, object]:
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        raise SyncError(f"{directory} must contain SKILL.md")
    try:
        contents = skill_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError(f"cannot read {skill_file}: {error}") from error
    lines = contents.splitlines()
    if not lines or lines[0] != "---":
        raise SyncError(f"{skill_file} must start with YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as error:
        raise SyncError(f"{skill_file} has unterminated YAML frontmatter") from error
    try:
        fields = yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as error:
        raise SyncError(f"{skill_file} has malformed YAML frontmatter") from error
    if not isinstance(fields, dict):
        raise SyncError(f"{skill_file} frontmatter must be an object")
    if strict and set(fields) - SKILL_FIELDS:
        raise SyncError(f"{skill_file} frontmatter must contain only supported Agent Skills fields")
    if not SKILL_NAME.fullmatch(expected_name) or len(expected_name) > MAX_SKILL_NAME_LENGTH:
        raise SyncError(f"{skill_file} has an invalid skill name")
    if fields.get("name") != expected_name:
        raise SyncError(f"{skill_file} name must be {expected_name!r}")
    description = fields.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SyncError(f"{skill_file} must have a description")
    if "<" in description or ">" in description or len(description) > 1024:
        raise SyncError(f"{skill_file} has an invalid description")
    return fields


def validate_agent_manifest(directory: Path, *, require_dcs_prefix: bool = True) -> None:
    path = directory / "agents" / "openai.yaml"
    if not path.exists():
        raise SyncError(f"{directory} must contain agents/openai.yaml")
    if not path.is_file():
        raise SyncError(f"{path} must be a file")
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError(f"cannot read {path}: {error}") from error
    except yaml.YAMLError as error:
        raise SyncError(f"{path} has malformed agent YAML") from error
    if not isinstance(payload, dict):
        raise SyncError(f"{path} must contain an object")
    if set(payload) - {"interface", "policy", "dependencies"}:
        raise SyncError(f"{path} contains unsupported top-level fields")

    interface = payload.get("interface")
    interface_fields = {
        "display_name",
        "short_description",
        "icon_small",
        "icon_large",
        "brand_color",
        "default_prompt",
    }
    if not isinstance(interface, dict) or set(interface) - interface_fields:
        raise SyncError(f"{path} must contain a supported interface object")
    for field in ("display_name", "short_description"):
        if not isinstance(interface.get(field), str) or not interface[field].strip():
            raise SyncError(f"{path} interface.{field} must be a non-empty string")
    display_name = interface["display_name"]
    if require_dcs_prefix and (
        not display_name.startswith(DCS_DISPLAY_PREFIX)
        or not display_name[len(DCS_DISPLAY_PREFIX) :].strip()
    ):
        raise SyncError(
            f"{path} interface.display_name must start with {DCS_DISPLAY_PREFIX!r} "
            "and include a display name"
        )
    default_prompt = interface.get("default_prompt")
    if default_prompt is not None and (
        not isinstance(default_prompt, str) or not default_prompt.strip()
    ):
        raise SyncError(f"{path} interface.default_prompt must be a non-empty string")
    brand_color = interface.get("brand_color")
    if brand_color is not None and (
        not isinstance(brand_color, str) or not HEX_COLOR.fullmatch(brand_color)
    ):
        raise SyncError(f"{path} interface.brand_color must use #RRGGBB")
    for field in ("icon_small", "icon_large"):
        value = interface.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise SyncError(f"{path} interface.{field} must be a relative file path")
        try:
            relative = relative_path(value, f"{path} interface.{field}")
        except SyncError as error:
            raise SyncError(f"{path} interface.{field} must be a relative file path") from error
        icon = directory.joinpath(*relative.parts).resolve()
        if not icon.is_relative_to(directory.resolve()) or not icon.is_file():
            raise SyncError(f"{path} interface.{field} must point inside the skill")

    policy = payload.get("policy")
    if policy is not None:
        if not isinstance(policy, dict):
            raise SyncError(f"{path} policy must be an object")
        if set(policy) - {"allow_implicit_invocation"}:
            raise SyncError(f"{path} contains unsupported policy fields")
        value = policy.get("allow_implicit_invocation")
        if value is not None and not isinstance(value, bool):
            raise SyncError(f"{path} policy.allow_implicit_invocation must be a boolean")

    dependencies = payload.get("dependencies")
    if dependencies is not None:
        if not isinstance(dependencies, dict):
            raise SyncError(f"{path} dependencies must be an object")
        if set(dependencies) - {"tools"}:
            raise SyncError(f"{path} contains unsupported dependency fields")


def apply_dcs_display_name(directory: Path, skill_name: str) -> None:
    path = directory / "agents" / "openai.yaml"
    if not path.exists():
        fields = validate_skill(directory, skill_name)
        description = fields["description"]
        assert isinstance(description, str)
        display_name = skill_name.replace("-", " ").title()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "interface:\n"
            f"  display_name: {json.dumps(DCS_DISPLAY_PREFIX + display_name, ensure_ascii=False)}\n"
            f"  short_description: {json.dumps(description.strip(), ensure_ascii=False)}\n",
            encoding="utf-8",
        )
        return

    validate_agent_manifest(directory, require_dcs_prefix=False)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    display_name = payload["interface"]["display_name"]
    if display_name.startswith(DCS_DISPLAY_PREFIX):
        return

    contents = path.read_bytes().decode("utf-8")
    document = yaml.compose(contents)
    if not isinstance(document, MappingNode):
        raise SyncError(f"{path} must contain an object")
    interface_nodes = [
        value
        for key, value in document.value
        if isinstance(key, ScalarNode) and key.value == "interface"
    ]
    if len(interface_nodes) != 1 or not isinstance(interface_nodes[0], MappingNode):
        raise SyncError(f"{path} must contain one interface object")
    display_name_nodes = [
        value
        for key, value in interface_nodes[0].value
        if isinstance(key, ScalarNode) and key.value == "display_name"
    ]
    if len(display_name_nodes) != 1 or not isinstance(display_name_nodes[0], ScalarNode):
        raise SyncError(f"{path} must contain one interface.display_name field")

    node = display_name_nodes[0]
    scalar_tokens = [
        token
        for token in yaml.scan(contents)
        if isinstance(token, ScalarToken)
        and node.start_mark.index <= token.start_mark.index
        and token.end_mark.index <= node.end_mark.index
        and token.value == display_name
    ]
    if len(scalar_tokens) != 1:
        raise SyncError(f"{path} must contain one interface.display_name scalar")
    token = scalar_tokens[0]
    original = contents[token.start_mark.index : token.end_mark.index]
    replacement = json.dumps(DCS_DISPLAY_PREFIX + display_name, ensure_ascii=False)
    if original.endswith("\r\n"):
        replacement += "\r\n"
    elif original.endswith("\n"):
        replacement += "\n"
    contents = (
        contents[: token.start_mark.index]
        + replacement
        + contents[token.end_mark.index :]
    )
    path.write_bytes(contents.encode("utf-8"))


def validate_pstack_source(directory: Path) -> None:
    manifest_path = directory / ".cursor-plugin" / "plugin.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read pstack manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise SyncError("pstack manifest must contain an object")
    if manifest.get("name") != "pstack" or manifest.get("license") != "MIT":
        raise SyncError("pstack source must retain its named MIT plugin manifest")

    mode = directory / "skills" / "poteto-mode" / "SKILL.md"
    try:
        mode_contents = mode.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise SyncError(f"cannot read pstack poteto-mode: {error}") from error
    if not all(
        marker in mode_contents
        for marker in ("disable-model-invocation: true", "## Principles", "## Playbooks")
    ):
        raise SyncError("pstack poteto-mode entry point changed; review the single-skill port")


def checkout(
    upstream: Upstream,
    parent: Path,
    cache: dict[tuple[str, str], tuple[Path, str]] | None = None,
) -> tuple[Path, str, str]:
    cache = cache if cache is not None else {}
    key = (upstream.repository, upstream.ref)
    if key in cache:
        checkout_root, commit = cache[key]
        git("sparse-checkout", "add", str(upstream.path), cwd=checkout_root)
    else:
        checkout_root = parent / f"source-{len(cache)}"
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
        commit = git("rev-parse", "HEAD", cwd=checkout_root)
        cache[key] = (checkout_root, commit)
    source = checkout_root.joinpath(*upstream.path.parts)
    if (
        source.is_symlink()
        or not source.is_dir()
        or not source.resolve().is_relative_to(checkout_root.resolve())
    ):
        raise SyncError(f"{upstream.source} is not a safe directory")
    reject_symlinks(source)
    if upstream.adapter == PSTACK_ADAPTER:
        validate_pstack_source(source)
    else:
        validate_skill(source, upstream.name, strict=False)
    tree = git("rev-parse", f"HEAD:{upstream.path}", cwd=checkout_root)
    return source, commit, tree


def apply_port_patch(candidate: Path, patch: Path) -> None:
    process = subprocess.run(
        ["patch", "--posix", "-s", "-f", "-p1", "-d", str(candidate), "-i", str(patch)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise SyncError(f"cannot apply {patch.relative_to(ROOT)}: {detail}")


def adapt_candidate(upstream: Upstream, source: Path, candidate: Path) -> None:
    if upstream.adapter == PSTACK_ADAPTER:
        validate_pstack_source(source)
        candidate.mkdir()
    else:
        shutil.copytree(source, candidate)
    if upstream.adapter == "cursor-manual-only":
        skill_file = candidate / "SKILL.md"
        lines = skill_file.read_text(encoding="utf-8").splitlines(keepends=True)
        try:
            frontmatter_end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
        except StopIteration as error:
            raise SyncError(f"{upstream.source} has unterminated YAML frontmatter") from error
        marker = [
            index
            for index, line in enumerate(lines[1:frontmatter_end], 1)
            if line.strip() == "disable-model-invocation: true"
        ]
        if len(marker) != 1:
            raise SyncError(f"{upstream.source} must contain one disable-model-invocation: true marker")
        del lines[marker[0]]
        skill_file.write_text("".join(lines), encoding="utf-8")
    if upstream.patch:
        patch = ROOT.joinpath(*upstream.patch.parts).resolve()
        if not patch.is_file() or not patch.is_relative_to(ROOT.resolve()):
            raise SyncError(f"missing or unsafe port patch: {upstream.patch}")
        apply_port_patch(candidate, patch)
    if upstream.overlay:
        overlay = ROOT.joinpath(*upstream.overlay.parts).resolve()
        if not overlay.is_dir() or not overlay.is_relative_to(ROOT.resolve()):
            raise SyncError(f"missing or unsafe port overlay: {upstream.overlay}")
        reject_symlinks(overlay)
        collisions = sorted(
            path.relative_to(overlay)
            for path in overlay.rglob("*")
            if path.is_file() and (candidate / path.relative_to(overlay)).exists()
        )
        if collisions:
            paths = ", ".join(path.as_posix() for path in collisions)
            raise SyncError(f"{upstream.source} port overlay collides with upstream files: {paths}")
        shutil.copytree(overlay, candidate, dirs_exist_ok=True)
    apply_dcs_display_name(candidate, upstream.name)
    reject_symlinks(candidate)
    validate_skill(candidate, upstream.name)
    validate_agent_manifest(candidate)


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


def install_synchronization(
    staged: list[tuple[Path, Path]], trees: dict[str, str], managed: set[str], removed: set[str]
) -> None:
    skills = ROOT / "skills"
    previous_lock = UPSTREAM_LOCK.read_bytes() if UPSTREAM_LOCK.exists() else None
    with tempfile.TemporaryDirectory(prefix=".skills-sync-", dir=ROOT) as temp:
        transaction = Path(temp)
        incoming_skills = transaction / "incoming"
        previous_skills = transaction / "previous"
        shutil.copytree(skills, incoming_skills)
        shutil.copytree(skills, previous_skills)
        for source, destination in staged:
            relative = destination.relative_to(skills)
            incoming = incoming_skills / relative
            if incoming.exists():
                shutil.rmtree(incoming)
            shutil.copytree(source, incoming)
        for name in removed:
            incoming = incoming_skills / name
            if incoming.exists():
                shutil.rmtree(incoming)

        try:
            if staged or removed:
                replace_directory(incoming_skills, skills)
            write_lock(trees, managed=managed)
        except Exception as error:
            try:
                if staged or removed:
                    replace_directory(previous_skills, skills)
                if previous_lock is None:
                    UPSTREAM_LOCK.unlink(missing_ok=True)
                else:
                    write_bytes_atomic(UPSTREAM_LOCK, previous_lock)
            except Exception as rollback_error:
                raise SyncError(f"synchronization failed and rollback also failed: {rollback_error}") from error
            raise


def validate_plugin_manifest(path: Path) -> dict[str, object]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SyncError(f"cannot read plugin manifest: {error}") from error
    if not isinstance(manifest, dict):
        raise SyncError("plugin manifest must contain an object")
    unknown_fields = set(manifest) - PLUGIN_FIELDS
    if unknown_fields:
        raise SyncError(
            "plugin manifest contains unsupported Agent Plugins fields: "
            + ", ".join(sorted(unknown_fields))
        )
    if manifest.get("$schema") != PLUGIN_SCHEMA:
        raise SyncError("plugin manifest must declare the Agent Plugins 1.0 schema")
    if manifest.get("name") != "dcs":
        raise SyncError("plugin manifest name must be 'dcs'")
    version = manifest.get("version")
    if not isinstance(version, str) or not PLAIN_SEMVER.fullmatch(version):
        raise SyncError("plugin manifest version must use plain x.y.z semver")
    description = manifest.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SyncError("plugin manifest must have a description")
    author = manifest.get("author")
    if (
        not isinstance(author, dict)
        or set(author) - {"name", "email", "url"}
        or any(not isinstance(value, str) for value in author.values())
        or not isinstance(author.get("name"), str)
        or not author["name"].strip()
    ):
        raise SyncError("plugin manifest must have a supported author")
    for field in ("homepage", "repository", "license"):
        if field in manifest and not isinstance(manifest[field], str):
            raise SyncError(f"plugin manifest {field} must be a string")
    keywords = manifest.get("keywords")
    if keywords is not None and (
        not isinstance(keywords, list) or any(not isinstance(value, str) for value in keywords)
    ):
        raise SyncError("plugin manifest keywords must be an array of strings")
    extensions = manifest.get("extensions")
    if extensions is not None and (
        not isinstance(extensions, dict)
        or any(not isinstance(value, dict) for value in extensions.values())
    ):
        raise SyncError("plugin manifest extensions must contain namespace objects")
    if isinstance(extensions, dict) and any(
        not EXTENSION_NAMESPACE.fullmatch(namespace) for namespace in extensions
    ):
        raise SyncError("plugin manifest extension keys must use reverse-domain namespaces")
    return manifest


def validate_plugin() -> None:
    validate_plugin_manifest(PLUGIN_MANIFEST)
    if (ROOT / ".codex-plugin" / "plugin.json").exists():
        raise SyncError("legacy .codex-plugin/plugin.json must be absent")
    upstreams = load_registry(DEFAULT_REGISTRY)
    registry_names = {upstream.name for upstream in upstreams}
    adapted_names = {upstream.name for upstream in upstreams if tracks_source_tree(upstream)}
    lock, managed = load_lock_state()
    if adapted_names != set(lock):
        raise SyncError("upstreams.lock.json must contain exactly the registered adapted skills")
    if registry_names != managed:
        raise SyncError("upstreams.lock.json managedSkills must contain exactly the registered skills")
    missing = sorted(
        upstream.name
        for upstream in upstreams
        if not ROOT.joinpath(*upstream.destination.parts).is_dir()
    )
    if missing:
        raise SyncError(f"missing registered skill directories: {', '.join(missing)}")
    for directory in sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir()):
        validate_skill(directory, directory.name)
        validate_agent_manifest(directory)


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
    if registry.resolve() != DEFAULT_REGISTRY.resolve():
        operation = "writes" if write else "checks"
        raise SyncError(f"synchronization {operation} require the canonical upstreams.json registry")
    results: list[Result] = []
    staged: list[tuple[Path, Path]] = []
    locked, managed = load_lock_state(required=False)
    trees: dict[str, str] = {}
    upstreams = load_registry(registry)
    registered_names = {upstream.name for upstream in upstreams}
    removed = managed - registered_names
    with tempfile.TemporaryDirectory(prefix="dcs-upstreams-") as temp:
        temp_root = Path(temp)
        checkout_root = temp_root / "checkouts"
        checkout_root.mkdir()
        candidate_root = temp_root / "candidates"
        candidate_root.mkdir()
        checkout_cache: dict[tuple[str, str], tuple[Path, str]] = {}
        for upstream in upstreams:
            source, commit, tree = checkout(upstream, checkout_root, checkout_cache)
            candidate = candidate_root / upstream.name
            adapt_candidate(upstream, source, candidate)
            destination = ROOT.joinpath(*upstream.destination.parts)
            content_changes = describe_changes(snapshot(destination), snapshot(candidate))
            changes = list(content_changes)
            if tracks_source_tree(upstream) and locked.get(upstream.name) != tree:
                previous = locked.get(upstream.name, "untracked")
                changes.insert(0, f"upstream tree {previous[:12]} -> {tree[:12]}")
            if content_changes:
                staged.append((candidate, destination))
            if tracks_source_tree(upstream):
                trees[upstream.name] = tree
            results.append(Result(upstream, commit, tree, tuple(changes)))
        lock_changed = locked != trees or managed != registered_names
        if write and (staged or lock_changed or removed):
            install_synchronization(staged, trees, registered_names, removed)
    return results, lock_changed or any(result.changes for result in results)


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
