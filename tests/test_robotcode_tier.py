"""Opt-in robotcode tier: unresolved keywords, variables and imports as LSP errors."""

import json
import sys
from pathlib import Path

from robotframework_lint.robotcode_tier import analyze

FINDING = {"range": {"start": {"line": 2, "character": 4}, "end": {"line": 2, "character": 14}},
           "message": "No keyword with name 'Missing Kw' found.", "severity": 1, "code": "KeywordNotFound"}
HINT = {**FINDING, "severity": 4, "code": "Hint"}


def fake_robotcode(tmp_path: Path, payload: object, exit_code: int = 0) -> list[str]:
    script = tmp_path / "fake_robotcode.py"
    script.write_text(f"import sys\nprint({json.dumps(json.dumps(payload))})\n"
                      f"sys.stderr.write(' '.join(sys.argv[1:]))\nsys.exit({exit_code})\n", encoding="utf-8")
    return [sys.executable, str(script)]


def robot_file(tmp_path: Path) -> Path:
    path = tmp_path / "t.robot"
    path.write_text("*** Test Cases ***\nT\n    Missing Kw\n", encoding="utf-8")
    return path


def test_reports_errors_only(tmp_path):
    command = fake_robotcode(tmp_path, {"diagnostics": {"t.robot": [FINDING, HINT]}}, exit_code=1)
    (diag,) = analyze(command, robot_file(tmp_path), tmp_path)
    assert diag.message == "KeywordNotFound No keyword with name 'Missing Kw' found."
    assert (diag.range.start.line, diag.range.start.character) == (2, 4)
    assert diag.code == "KeywordNotFound" and diag.source == "robotcode"


def test_caps_findings_and_message_length(tmp_path):
    long = {**FINDING, "message": "x" * 300}
    command = fake_robotcode(tmp_path, {"diagnostics": {"t.robot": [long] * 9}})
    found = analyze(command, robot_file(tmp_path), tmp_path)
    assert len(found) == 5
    assert all(len(d.message) <= 120 for d in found)


def test_bad_output_or_missing_command_gives_nothing(tmp_path):
    assert analyze(fake_robotcode(tmp_path, "not json"), robot_file(tmp_path), tmp_path) == []
    assert analyze([str(tmp_path / "no-such-robotcode")], robot_file(tmp_path), tmp_path) == []


def test_file_outside_root_is_skipped(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    command = fake_robotcode(tmp_path, {"diagnostics": {"t.robot": [FINDING]}})
    assert analyze(command, robot_file(tmp_path), root) == []


def test_save_publishes_robotcode_errors_first(tmp_path):
    import asyncio
    from types import SimpleNamespace

    from robotframework_lint import lsp

    path = robot_file(tmp_path)
    published: list[str] = []
    ls = SimpleNamespace(root=tmp_path, robotcode={}, publish=published.append,
                         workspace=SimpleNamespace(text_documents={path.as_uri(): object()}),
                         settings=lsp.Settings(robotcode=fake_robotcode(tmp_path, {"diagnostics": {"t.robot": [FINDING]}})))
    params = SimpleNamespace(text_document=SimpleNamespace(uri=path.as_uri()))
    asyncio.run(lsp.on_save(ls, params))
    assert published == [path.as_uri()]
    assert [d.code for d in ls.robotcode[path.as_uri()]] == ["KeywordNotFound"]
    assert lsp.Settings.from_options({"robotcodeCommand": ["rc"]}).robotcode == ["rc"]


def test_child_never_shares_server_stdin(tmp_path, monkeypatch):
    import subprocess

    from robotframework_lint import changed_lines, robotcode_tier

    seen = []

    def run(*args, **kwargs):
        seen.append(kwargs.get("stdin"))
        raise OSError("not started")

    monkeypatch.setattr(subprocess, "run", run)
    analyze(["robotcode"], robot_file(tmp_path), tmp_path)
    changed_lines.head_text(robot_file(tmp_path))
    assert seen == [subprocess.DEVNULL, subprocess.DEVNULL] and robotcode_tier.subprocess is subprocess
