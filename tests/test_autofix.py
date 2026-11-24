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


def test_temp_parent_config_cannot_steer_fix(tmp_path, monkeypatch):
    import tempfile

    (tmp_path / "pyproject.toml").write_text('[tool.robocop.lint]\nignore = ["*"]\n')
    (tmp_path / "t").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "t"))
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    path = tmp_path / "repo" / "s.robot"
    path.write_text(LEGACY, encoding="utf-8")
    fix_file(path)
    assert "IF    $x    Log" in path.read_text(encoding="utf-8")


def test_fix_file_adds_zip_mode(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text("*** Test Cases ***\nT\n    FOR    ${a}    ${b}    IN ZIP    ${X}    ${Y}\n"
                    "        Log    ${a}\n    END\n", encoding="utf-8")
    fix_file(path)
    assert "IN ZIP    ${X}    ${Y}    mode=SHORTEST\n" in path.read_text(encoding="utf-8")


TWO_TESTS = ("*** Test Cases ***\nA\n    Set Test Variable    ${a}    1\n"
             "B\n    Set Test Variable    ${b}    2\n")


def test_edit_fixes_only_the_edited_lines(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(TWO_TESTS, encoding="utf-8")
    edit = "B\n    Set Test Variable    ${b}    2\n"
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": edit}})
    text = path.read_text(encoding="utf-8")
    assert "Set Test Variable    ${a}    1" in text
    assert "VAR    ${b}    2    scope=TEST" in text


def test_delete_only_edit_leaves_file_alone(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(TWO_TESTS, encoding="utf-8")
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": ""}})
    assert path.read_text(encoding="utf-8") == TWO_TESTS


def test_multiedit_fixes_each_edited_hunk(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(TWO_TESTS, encoding="utf-8")
    edits = [{"new_string": "A\n    Set Test Variable    ${a}    1\n"}]
    _run_hook({"tool_name": "MultiEdit", "tool_input": {"file_path": str(path), "edits": edits}})
    text = path.read_text(encoding="utf-8")
    assert "VAR    ${a}    1    scope=TEST" in text
    assert "Set Test Variable    ${b}    2" in text


def test_hook_survives_null_new_string(tmp_path):
    path = tmp_path / "t.robot"
    path.write_text(TWO_TESTS, encoding="utf-8")
    result = _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": None}})
    assert result.returncode == 0
    assert path.read_text(encoding="utf-8") == TWO_TESTS


def test_edit_text_seen_twice_fixes_the_written_copy(tmp_path):
    line = "    Set Test Variable    ${a}    1\n"
    path = tmp_path / "t.robot"
    path.write_text(f"*** Test Cases ***\nA\n{line}B\n{line}", encoding="utf-8")
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": line}})
    assert path.read_text(encoding="utf-8").endswith("B\n    VAR    ${a}    1    scope=TEST\n")


def test_edit_leaves_the_next_line_alone(tmp_path):
    first, second = "    Set Test Variable    ${a}    1\n", "    Set Test Variable    ${b}    2\n"
    path = tmp_path / "t.robot"
    path.write_text(f"*** Test Cases ***\nT\n{first}{second}", encoding="utf-8")
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": first}})
    text = path.read_text(encoding="utf-8")
    assert "VAR    ${a}    1    scope=TEST" in text and second in text


SET_A, SET_B = "    Set Test Variable    ${a}    1\n", "    Set Test Variable    ${b}    2\n"


def _edit(tmp_path, text: str, new_string: str) -> str:
    path = tmp_path / "t.robot"
    path.write_text(text, encoding="utf-8")
    _run_hook({"tool_name": "Edit", "tool_input": {"file_path": str(path), "new_string": new_string}})
    return path.read_text(encoding="utf-8")


def test_edit_at_file_start_is_fixed(tmp_path):
    head = f"*** Test Cases ***\nT\n{SET_A}"
    assert "VAR    ${a}    1    scope=TEST" in _edit(tmp_path, head + SET_B, head)


def test_leading_blank_line_keeps_line_numbers(tmp_path):
    text = _edit(tmp_path, f"\n*** Test Cases ***\nT\n{SET_A}{SET_B}", SET_B)
    assert SET_A in text and "VAR    ${b}    2    scope=TEST" in text


def test_edit_without_final_newline_is_fixed(tmp_path):
    text = _edit(tmp_path, f"*** Test Cases ***\nT\n{SET_A}{SET_B}", SET_B.rstrip("\n"))
    assert SET_A in text and "VAR    ${b}    2    scope=TEST" in text
