"""RFL002 deprecated-standard-library: runs the real robocop CLI on sample files."""

import subprocess
import sys
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"
RULES = Path(__file__).parents[1] / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", str(RULES),
         "--select", "RFL002", "--no-cache", str(SAMPLES / sample)],
        capture_output=True, text=True, check=False,
    )
    return result.stdout + result.stderr


def test_reports_telnet_import():
    output = run_robocop("deprecated_library_telnet.robot")
    assert "deprecated_library_telnet.robot:2" in output
    assert "RFL002" in output
    assert output.count("RFL002 Telnet is deprecated") == 1


def test_ignores_other_libraries():
    output = run_robocop("deprecated_library_none.robot")
    assert "did not match" not in output
    assert "RFL002" not in output
