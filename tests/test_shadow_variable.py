"""RFL007 local-shadows-suite-variable: runs the real robocop CLI on sample files."""

import subprocess
import sys
from pathlib import Path

SAMPLES = Path(__file__).parent / "samples"
RULES = Path(__file__).parents[1] / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", str(RULES),
         "--select", "RFL007", "--no-cache", str(SAMPLES / sample)],
        capture_output=True, text=True, check=False,
    )
    return result.stdout + result.stderr


def test_reports_assignment_and_var_that_shadow():
    output = run_robocop("shadow_suite_variable.robot")
    assert "shadow_suite_variable.robot:7:5 RFL007 ${contract} hides suite variable ${CONTRACT} (line 2)" in output
    assert "shadow_suite_variable.robot:8:12 RFL007 ${con_tract} hides" in output


def test_ignores_other_names_and_suite_scope():
    output = run_robocop("shadow_none.robot")
    assert "RFL007" not in output
    assert "did not match" not in output


def test_reports_when_variables_section_comes_last():
    output = run_robocop("shadow_variables_last.robot")
    assert "shadow_variables_last.robot:3:5 RFL007 ${contract} hides suite variable ${CONTRACT} (line 8)" in output


def test_item_assignment_changes_suite_variable_not_hides_it():
    output = run_robocop("shadow_item_assignment.robot")
    assert "RFL007" not in output
