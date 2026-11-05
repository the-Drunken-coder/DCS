"""Include the skill's portable executable checks in repository test discovery."""

import importlib.util
from pathlib import Path


def load_tests(loader, tests, pattern):
    path = Path(__file__).resolve().parents[1] / "skills/ui-hillclimb/scripts/test_scorecard.py"
    spec = importlib.util.spec_from_file_location("ui_scorecard_tests", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return loader.loadTestsFromModule(module)
