"""RFL006 deprecated-argument-name: real robocop CLI."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SAMPLES = Path(__file__).parent / "samples"
RULES = ROOT / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str) -> str:
    cmd = [sys.executable, "-m", "robocop", "check", "--select", "RFL006", "--no-cache",
           "--custom-rules", str(RULES), str(SAMPLES / sample)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return result.stdout + result.stderr


def test_reports_list_and_time_named_args():
    output = run_robocop("arg_names_deprecated.robot")
    for line in (7, 8, 9, 10):
        assert f"arg_names_deprecated.robot:{line}:" in output, output
    assert "'list_'" in output
    assert "'time_'" in output


def test_silent_on_positional_and_other_keywords():
    output = run_robocop("arg_names_ok.robot")
    assert "RFL006" not in output, output
