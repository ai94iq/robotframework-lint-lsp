"""RFL005 doc-tags-without-empty-row: real robocop CLI."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SAMPLES = Path(__file__).parent / "samples"
RULES = ROOT / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str) -> str:
    cmd = [sys.executable, "-m", "robocop", "check", "--select", "RFL005", "--no-cache",
           "--custom-rules", str(RULES), str(SAMPLES / sample)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return result.stdout + result.stderr


def test_reports_tags_header_without_empty_row():
    output = run_robocop("doc_tags_no_empty_row.robot")
    assert "doc_tags_no_empty_row.robot:8:" in output
    assert "RFL005" in output


def test_silent_with_empty_row_or_tags_first():
    output = run_robocop("doc_tags_ok.robot")
    assert "RFL005" not in output, output
