"""Include the provider-owned runner tests in DCS's normal test command."""

import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    skills = Path(__file__).resolve().parents[1] / "skills"
    for name in ("ask-antigravity", "ask-grok"):
        path = skills / name / "scripts" / "test_review.py"
        spec = importlib.util.spec_from_file_location(name.replace("-", "_") + "_tests", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        tests.addTests(loader.loadTestsFromModule(module))
    return tests
