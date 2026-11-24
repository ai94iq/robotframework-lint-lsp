"""The project's own robocop.toml picks rules per folder, for the server and the hook."""

from robotframework_lint.autofix import fix_file
from robotframework_lint.lsp import Settings, file_settings, lint_text
from robotframework_lint.project_config import rule_filter

LONG_AND_SHADOW = ("*** Variables ***\n${CONTRACT}    C-1\n\n\n*** Test Cases ***\nT\n"
                   f"    Log    {'x' * 130}\n    ${{contract}}=    Set Variable    1\n")


def _project(tmp_path):
    (tmp_path / "robot.toml").write_text("")
    (tmp_path / "robocop.toml").write_text('[tool.robocop.lint]\nselect = ["DEPR*", "VAR*"]\n')
    (tmp_path / "probes").mkdir()
    (tmp_path / "probes" / "robocop.toml").write_text('[tool.robocop.lint]\nignore = ["LEN*", "DEPR*"]\n')
    return tmp_path


def test_nearest_robocop_toml_wins(tmp_path):
    root = _project(tmp_path)
    assert rule_filter(root / "suite.robot") == (["DEPR*", "VAR*"], [])
    assert rule_filter(root / "probes" / "p.robot") == ([], ["LEN*", "DEPR*"])


def test_no_config_above_project_root(tmp_path):
    (tmp_path / "robocop.toml").write_text('[tool.robocop.lint]\nselect = ["LEN*"]\n')
    (tmp_path / "repo").mkdir()
    (tmp_path / "repo" / ".git").mkdir()
    assert rule_filter(tmp_path / "repo" / "a.robot") == ([], [])


def test_server_keeps_our_rules_when_project_selects():
    settings = file_settings(Settings(ignore=["NAME01"]), (["DEPR*"], ["TAG01"]))
    assert (settings.select, settings.ignore) == (["DEPR*", "RFL*"], ["NAME01", "TAG01"])


def test_project_select_drops_length_findings(tmp_path):
    settings = file_settings(Settings(), rule_filter(_project(tmp_path) / "suite.robot"))
    codes = {d.code for d in lint_text(LONG_AND_SHADOW, settings)}
    assert "RFL007" in codes and not any(c.startswith("LEN") for c in codes)


def test_cap_keeps_errors_before_style():
    found = lint_text(LONG_AND_SHADOW, Settings(max_diagnostics=1))
    assert found[0].code == "RFL007"


def test_hook_skips_fixes_the_folder_ignores(tmp_path):
    path = _project(tmp_path) / "probes" / "p.robot"
    text = "*** Test Cases ***\nT\n    ${a}=    Set Variable    1\n    Log    ${a}\n"
    path.write_text(text, encoding="utf-8")
    fix_file(path)
    assert path.read_text(encoding="utf-8") == text
