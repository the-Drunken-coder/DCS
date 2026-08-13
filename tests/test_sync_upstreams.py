from pathlib import Path, PurePosixPath
import tempfile
import unittest
from unittest import mock

from tools import sync_upstreams as sync


class PortAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.original_root = sync.ROOT
        sync.ROOT = self.root

    def tearDown(self) -> None:
        sync.ROOT = self.original_root
        self.temporary_directory.cleanup()

    def upstream(self) -> sync.Upstream:
        return sync.Upstream(
            name="example",
            repository="owner/repository",
            ref="main",
            path=PurePosixPath("skills/example"),
            destination=PurePosixPath("skills/example"),
            adapter="cursor-manual-only",
            overlay=PurePosixPath("ports/example"),
            patch=PurePosixPath("ports/example.patch"),
        )

    def write_source(self, marker: bool = True) -> Path:
        source = self.root / "source"
        source.mkdir()
        invocation = "disable-model-invocation: true\n" if marker else ""
        (source / "SKILL.md").write_text(
            "---\n"
            "name: example\n"
            "description: Example skill.\n"
            f"{invocation}"
            "---\n\n"
            "# Example\n\n"
            "Original instructions.\n",
            encoding="utf-8",
        )
        return source

    def write_port(self) -> None:
        overlay = self.root / "ports" / "example" / "agents"
        overlay.mkdir(parents=True)
        (overlay / "openai.yaml").write_text(
            "policy:\n  allow_implicit_invocation: false\n",
            encoding="utf-8",
        )
        (self.root / "ports" / "example.patch").write_text(
            "--- a/SKILL.md\n"
            "+++ b/SKILL.md\n"
            "@@ -5,4 +5,4 @@\n"
            " \n"
            " # Example\n"
            " \n"
            "-Original instructions.\n"
            "+Codex instructions.\n",
            encoding="utf-8",
        )

    def test_adapter_removes_cursor_metadata_and_applies_port(self) -> None:
        source = self.write_source()
        self.write_port()
        candidate = self.root / "candidate"

        sync.adapt_candidate(self.upstream(), source, candidate)

        skill = (candidate / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("disable-model-invocation", skill)
        self.assertIn("Codex instructions.", skill)
        self.assertFalse((candidate / "SKILL.md.orig").exists())
        self.assertTrue((candidate / "agents" / "openai.yaml").is_file())

    def test_adapter_fails_when_cursor_metadata_changes(self) -> None:
        source = self.write_source(marker=False)
        self.write_port()

        with self.assertRaisesRegex(sync.SyncError, "must contain one"):
            sync.adapt_candidate(self.upstream(), source, self.root / "candidate")

    def test_overlay_fails_when_upstream_adds_the_same_file(self) -> None:
        source = self.write_source()
        self.write_port()
        upstream_agents = source / "agents"
        upstream_agents.mkdir()
        (upstream_agents / "openai.yaml").write_text("upstream: true\n", encoding="utf-8")

        with self.assertRaisesRegex(sync.SyncError, "overlay collides"):
            sync.adapt_candidate(self.upstream(), source, self.root / "candidate")


class RegistryTests(unittest.TestCase):
    def test_invalid_adapter_collection_raises_sync_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            registry = Path(temporary_directory) / "upstreams.json"
            registry.write_text(
                '{"schemaVersion":1,"skills":[{"name":"example",'
                '"repository":"owner/repository","ref":"main",'
                '"path":"skills/example","destination":"skills/example",'
                '"adapter":[]}]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(sync.SyncError, "adapter is not supported"):
                sync.load_registry(registry)


class SkillValidationTests(unittest.TestCase):
    def test_rejects_unsupported_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            skill = Path(temporary_directory)
            (skill / "SKILL.md").write_text(
                "---\nname: example\ndescription: Example skill.\n"
                "disable_model_invocation: true\n---\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(sync.SyncError, "only name and description"):
                sync.validate_skill(skill, "example")

    def test_rejects_malformed_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            skill = Path(temporary_directory)
            (skill / "SKILL.md").write_text(
                "---\nname: example\ndescription Example skill.\n---\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(sync.SyncError, "malformed YAML frontmatter"):
                sync.validate_skill(skill, "example")

    def test_rejects_invalid_yaml_scalars(self) -> None:
        for description in ('"unterminated', "bad: value", "[not, closed", "# comment", "- item"):
            with self.subTest(description=description), tempfile.TemporaryDirectory() as temporary_directory:
                skill = Path(temporary_directory)
                (skill / "SKILL.md").write_text(
                    f"---\nname: example\ndescription: {description}\n---\n",
                    encoding="utf-8",
                )

                with self.assertRaisesRegex(sync.SyncError, "malformed YAML frontmatter"):
                    sync.validate_skill(skill, "example")


class CheckoutTests(unittest.TestCase):
    def test_shared_repository_ref_uses_one_clone(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            parent = Path(temporary_directory)
            checkout = parent / "source-0"
            for name in ("alpha", "beta"):
                skill = checkout / "skills" / name
                skill.mkdir(parents=True)
                (skill / "SKILL.md").write_text(
                    f"---\nname: {name}\ndescription: Example skill.\n---\n",
                    encoding="utf-8",
                )
            cache: dict[tuple[str, str], tuple[Path, str]] = {}

            def fake_git(*arguments: str, cwd: Path | None = None) -> str:
                if arguments[:2] == ("rev-parse", "HEAD"):
                    return "c" * 40
                if arguments[0] == "rev-parse":
                    return "d" * 40
                return ""

            def upstream(name: str) -> sync.Upstream:
                return sync.Upstream(
                    name, "owner/repository", "main", PurePosixPath(f"skills/{name}"),
                    PurePosixPath(f"skills/{name}"), None, None, None
                )

            with mock.patch.object(sync, "git", side_effect=fake_git) as git:
                sync.checkout(upstream("alpha"), parent, cache)
                sync.checkout(upstream("beta"), parent, cache)

            clones = [call for call in git.call_args_list if call.args and call.args[0] == "clone"]
            self.assertEqual(len(clones), 1)
            git.assert_any_call("sparse-checkout", "add", "skills/beta", cwd=checkout)


class PortPolicyTests(unittest.TestCase):
    def test_all_thermos_ports_are_explicit_only(self) -> None:
        root = Path(__file__).resolve().parents[1]
        for name in ("thermo-nuclear-code-quality-review", "thermo-nuclear-review", "thermos"):
            with self.subTest(name=name):
                contents = (root / "ports" / name / "agents" / "openai.yaml").read_text(encoding="utf-8")
                self.assertEqual(contents.split("policy:\n", 1)[1], "  allow_implicit_invocation: false\n")


class LockTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "upstreams.lock.json"
            expected = {"example": "a" * 40}

            sync.write_lock(expected, path)

            self.assertEqual(sync.load_lock(path), expected)

    def test_rejects_unsafe_lock_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "upstreams.lock.json"
            path.write_text(
                '{"schemaVersion":1,"skills":{"../outside":"' + "a" * 40 + '"}}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(sync.SyncError, "skill names"):
                sync.load_lock(path)

    def test_source_tree_change_is_drift_when_packaged_files_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "skills" / "example"
            source.mkdir()
            destination.mkdir(parents=True)
            source_skill = (
                "---\nname: example\ndescription: Example skill.\n"
                "disable-model-invocation: true\n---\n"
            )
            packaged_skill = "---\nname: example\ndescription: Example skill.\n---\n"
            (source / "SKILL.md").write_text(source_skill, encoding="utf-8")
            (destination / "SKILL.md").write_text(packaged_skill, encoding="utf-8")
            registry = root / "upstreams.json"
            registry.write_text(
                '{"schemaVersion":1,"skills":[{"name":"example",'
                '"repository":"owner/repository","ref":"main",'
                '"path":"skills/example","destination":"skills/example",'
                '"adapter":"cursor-manual-only"}]}',
                encoding="utf-8",
            )
            lock = root / "upstreams.lock.json"
            sync.write_lock({"example": "a" * 40}, lock)

            with (
                mock.patch.object(sync, "ROOT", root),
                mock.patch.object(sync, "UPSTREAM_LOCK", lock),
                mock.patch.object(sync, "checkout", return_value=(source, "c" * 40, "b" * 40)),
            ):
                results, changed = sync.synchronize(registry, write=False)

            self.assertTrue(changed)
            self.assertEqual(results[0].changes, (f"upstream tree {'a' * 12} -> {'b' * 12}",))

    def test_custom_registry_cannot_overwrite_canonical_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            canonical = root / "upstreams.json"
            custom = root / "custom.json"

            with (
                mock.patch.object(sync, "ROOT", root),
                mock.patch.object(sync, "DEFAULT_REGISTRY", canonical),
                self.assertRaisesRegex(sync.SyncError, "canonical upstreams.json"),
            ):
                sync.synchronize(custom, write=True)

    def test_lock_only_cleanup_is_reported_and_written(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "skills" / "example"
            source.mkdir()
            destination.mkdir(parents=True)
            skill = "---\nname: example\ndescription: Example skill.\n---\n"
            (source / "SKILL.md").write_text(skill, encoding="utf-8")
            (destination / "SKILL.md").write_text(skill, encoding="utf-8")
            registry = root / "upstreams.json"
            registry.write_text(
                '{"schemaVersion":1,"skills":[{"name":"example",'
                '"repository":"owner/repository","ref":"main",'
                '"path":"skills/example","destination":"skills/example"}]}',
                encoding="utf-8",
            )
            lock = root / "upstreams.lock.json"
            sync.write_lock({"example": "a" * 40}, lock)

            with (
                mock.patch.object(sync, "ROOT", root),
                mock.patch.object(sync, "DEFAULT_REGISTRY", registry),
                mock.patch.object(sync, "UPSTREAM_LOCK", lock),
                mock.patch.object(sync, "checkout", return_value=(source, "c" * 40, "b" * 40)),
            ):
                results, changed = sync.synchronize(registry, write=True)

            self.assertTrue(changed)
            self.assertEqual(results[0].changes, ())
            self.assertEqual(sync.load_lock(lock), {})

    def test_deregistered_adapted_skill_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "skills" / "retired"
            destination.mkdir(parents=True)
            (destination / "SKILL.md").write_text(
                "---\nname: retired\ndescription: Retired skill.\n---\n",
                encoding="utf-8",
            )
            registry = root / "upstreams.json"
            registry.write_text('{"schemaVersion":1,"skills":[]}', encoding="utf-8")
            lock = root / "upstreams.lock.json"
            sync.write_lock({"retired": "a" * 40}, lock)

            with (
                mock.patch.object(sync, "ROOT", root),
                mock.patch.object(sync, "DEFAULT_REGISTRY", registry),
                mock.patch.object(sync, "UPSTREAM_LOCK", lock),
            ):
                results, changed = sync.synchronize(registry, write=True)

            self.assertTrue(changed)
            self.assertEqual(results, [])
            self.assertFalse(destination.exists())
            self.assertEqual(sync.load_lock(lock), {})

    def test_failed_lock_write_rolls_back_all_skill_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            destination = root / "skills" / "example"
            source.mkdir()
            destination.mkdir(parents=True)
            old_skill = "---\nname: example\ndescription: Old skill.\n---\n"
            new_skill = "---\nname: example\ndescription: New skill.\n---\n"
            upstream_skill = (
                "---\nname: example\ndescription: New skill.\n"
                "disable-model-invocation: true\n---\n"
            )
            (source / "SKILL.md").write_text(upstream_skill, encoding="utf-8")
            (destination / "SKILL.md").write_text(old_skill, encoding="utf-8")
            registry = root / "upstreams.json"
            registry.write_text(
                '{"schemaVersion":1,"skills":[{"name":"example",'
                '"repository":"owner/repository","ref":"main",'
                '"path":"skills/example","destination":"skills/example",'
                '"adapter":"cursor-manual-only"}]}',
                encoding="utf-8",
            )
            lock = root / "upstreams.lock.json"
            sync.write_lock({"example": "a" * 40}, lock)
            previous_lock = lock.read_bytes()

            with (
                mock.patch.object(sync, "ROOT", root),
                mock.patch.object(sync, "DEFAULT_REGISTRY", registry),
                mock.patch.object(sync, "UPSTREAM_LOCK", lock),
                mock.patch.object(sync, "checkout", return_value=(source, "c" * 40, "b" * 40)),
                mock.patch.object(sync, "write_lock", side_effect=OSError("injected lock failure")),
                self.assertRaisesRegex(OSError, "injected lock failure"),
            ):
                sync.synchronize(registry, write=True)

            self.assertEqual((destination / "SKILL.md").read_text(encoding="utf-8"), old_skill)
            self.assertEqual(lock.read_bytes(), previous_lock)


if __name__ == "__main__":
    unittest.main()
