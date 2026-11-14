"""The robocop.plugins entry point loads the rules by plugin name, no rules path."""

import subprocess
import sys
from importlib.metadata import entry_points
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"


def test_entry_point_is_registered():
    names = {ep.name: ep.value for ep in entry_points(group="robocop.plugins")}
    assert names.get("robotframework_lint") == "robotframework_lint.rules"


def test_rules_load_through_entry_point():
    result = subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", "robotframework_lint",
         "--select", "RFL001",
         "--no-cache", str(SAMPLES / "for_in_zip_no_mode.robot")],
        capture_output=True, text=True, check=False,
    )
    assert "for_in_zip_no_mode.robot:3:" in result.stdout + result.stderr
