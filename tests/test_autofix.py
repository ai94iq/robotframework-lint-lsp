"""PostToolUse hook: applies safe robocop fixes to the edited Robot file."""

import json
import subprocess
import sys

from robotframework_lint.autofix import fix_file

LEGACY = ("*** Test Cases ***\nT\n    Set Test Variable    ${x}    1\n"
          "    ${a}=    Set Variable    1\n    ${b}    Set Variable    2\n"
          "    IF    $x\n        Log    ${a}${b}\n    END\n")


def test_fix_file_rewrites_fixable_rules(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    fix_file(path)
    text = path.read_text(encoding="utf-8")
    assert "Set Test Variable" not in text
    assert "VAR    ${x}    1    scope=TEST" in text
    assert "IF    $x    Log" in text  # MISC09 inline IF
    assert ("${a}=" in text) == ("${b}=" in text)  # MISC04 one assignment style


def test_hook_ignores_non_robot_files(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("Set Test Variable", encoding="utf-8")
    result = _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
    assert result.returncode == 0 and result.stdout == ""
    assert path.read_text(encoding="utf-8") == "Set Test Variable"


def test_hook_fixes_robot_file_silently(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    result = _run_hook({"tool_name": "Write", "tool_input": {"file_path": str(path)}})
    assert result.returncode == 0 and result.stdout == ""
    assert "Set Test Variable" not in path.read_text(encoding="utf-8")


def test_hook_ignores_repo_robocop_module(tmp_path):
    marker = tmp_path / "MARKER"
    (tmp_path / "robocop.py").write_text(f"open(r'{marker}', 'w').write('ran')\n", encoding="utf-8")
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path)}}, cwd=tmp_path)
    assert not marker.exists()
    assert "Set Test Variable" not in path.read_text(encoding="utf-8")


def test_hook_survives_bad_input():
    result = subprocess.run([sys.executable, "-m", "robotframework_lint.autofix"],
                            input="not json", capture_output=True, text=True, timeout=60)
    assert result.returncode == 0


def _run_hook(payload: dict, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "robotframework_lint.autofix"], cwd=cwd,
                          input=json.dumps(payload), capture_output=True, text=True, timeout=120)


def test_fix_file_keeps_lf_line_endings(tmp_path):
    path = tmp_path / "t.robot"
    path.write_bytes(LEGACY.encode("utf-8"))
    fix_file(path)
    assert b"\r\n" not in path.read_bytes()


def test_two_robocop_runs_fit_hook_timeout():
    from pathlib import Path

    from robotframework_lint.autofix import TIMEOUT_S
    hook = json.loads((Path(__file__).parents[1] / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    budget = hook["hooks"]["PostToolUse"][0]["hooks"][0]["timeout"]
    assert 2 * TIMEOUT_S < budget


def test_fix_skips_file_changed_meanwhile(tmp_path, monkeypatch):
    from robotframework_lint import autofix

    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    real = autofix.subprocess.run

    def edit_during_run(*args, **kwargs):
        path.write_text("NEWER", encoding="utf-8")
        return real(*args, **kwargs)

    monkeypatch.setattr(autofix.subprocess, "run", edit_during_run)
    fix_file(path)
    assert path.read_text(encoding="utf-8") == "NEWER"
