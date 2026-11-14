"""RFL004 deprecated-translation: real robocop CLI."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SAMPLES = Path(__file__).parent / "samples"
RULES = ROOT / "src" / "robotframework_lint" / "rules"


def run_robocop(sample: str, custom: bool = True) -> str:
    cmd = [sys.executable, "-m", "robocop", "check", "--select", "RFL004", "--no-cache"]
    if custom:
        cmd += ["--custom-rules", str(RULES)]
    cmd.append(str(SAMPLES / sample))
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, cwd=ROOT)
    return result.stdout + result.stderr



def test_reports_deprecated_french_header():
    output = run_robocop("translation_fr_deprecated.robot")
    assert "translation_fr_deprecated.robot:3:" in output
    assert "Cas de test" in output


def test_reports_deprecated_finnish_tags():
    output = run_robocop("translation_fi_deprecated.robot")
    for line in (4, 8):
        assert f"translation_fi_deprecated.robot:{line}:" in output
    assert "Tunnisteet" in output


def test_silent_on_current_or_other_language():
    for sample in ("translation_fi_ok.robot", "translation_fr_ok.robot", "translation_en_ok.robot"):
        output = run_robocop(sample)
        assert "RFL004" not in output, output
        assert "did not match" not in output
