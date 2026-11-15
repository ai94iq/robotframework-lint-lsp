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


def fix_copy(sample: str, tmp_path: Path) -> str:
    target = tmp_path / sample
    target.write_bytes((SAMPLES / sample).read_bytes())
    subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", str(RULES),
         "--select", "RFL001", "--no-cache", "--fix", str(target)],
        capture_output=True, text=True, check=False, cwd=tmp_path,
    )
    return target.read_text()


def test_fix_keeps_shortest_behaviour(tmp_path):
    fixed = fix_copy("for_in_zip_no_mode.robot", tmp_path)
    assert "IN ZIP    ${LIST_A}    ${LIST_B}    mode=SHORTEST\n" in fixed
    assert "RFL001" not in run_robocop_path(tmp_path / "for_in_zip_no_mode.robot")


def test_fix_skips_continuation_and_comment(tmp_path):
    sample = "for_in_zip_fix_skip.robot"
    assert fix_copy(sample, tmp_path) == (SAMPLES / sample).read_text()


def run_robocop_path(path: Path) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "robocop", "check", "--custom-rules", str(RULES),
         "--select", "RFL001", "--no-cache", str(path)],
        capture_output=True, text=True, check=False,
    )
    return result.stdout + result.stderr
