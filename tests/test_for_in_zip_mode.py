"""RFL001 for-in-zip-without-mode: runs the real robocop CLI on sample files."""

import subprocess
import sys
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"
RULES = Path(__file__).parents[1] / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", str(RULES),
         "--select", "RFL001", "--no-cache", str(SAMPLES / sample)],
        capture_output=True, text=True, check=False,
    )
    return result.stdout + result.stderr


def test_reports_zip_without_mode():
    output = run_robocop("for_in_zip_no_mode.robot")
    assert "RFL001" in output
    assert "for_in_zip_no_mode.robot:3" in output


def test_ignores_zip_with_mode_and_plain_for():
    output = run_robocop("for_in_zip_with_mode.robot")
    assert "RFL001" not in output
