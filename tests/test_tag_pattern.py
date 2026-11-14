"""RFL003 deprecated-tag-pattern and pyproject plugin loading: real robocop CLI."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SAMPLES = Path(__file__).parent / "samples"
RULES = ROOT / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str, custom: bool = True) -> str:
    cmd = [sys.executable, "-m", "robocop", "check", "--select", "RFL003", "--no-cache"]
    if custom:
        cmd += ["--custom-rules", str(RULES)]
    cmd.append(str(SAMPLES / sample))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return result.stdout + result.stderr


def test_reports_deprecated_patterns():
    output = run_robocop("tag_pattern_deprecated.robot")
    for line in (2, 6, 8):
        assert f"tag_pattern_deprecated.robot:{line}:" in output
    assert "tag_pattern_deprecated.robot:7:" not in output
    assert "did not match" not in output


def test_silent_on_valid_patterns():
    output = run_robocop("tag_pattern_ok.robot")
    assert "RFL003" not in output
    assert "did not match" not in output


def test_pyproject_loads_plugin_without_flag():
    output = run_robocop("tag_pattern_deprecated.robot", custom=False)
    assert "tag_pattern_deprecated.robot:2:" in output
    assert "did not match" not in output


def test_all_caps_operator_words_follow_rf():
    # RF 7.5.1 TagPatterns warns on DONOTX and ORANGE; lower case is fine.
    output = run_robocop("tag_pattern_all_caps.robot")
    assert output.count("tag_pattern_all_caps.robot:3:") == 2
    assert "'NOT'" in output and "'OR'" in output
