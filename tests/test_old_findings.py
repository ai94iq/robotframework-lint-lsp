"""Findings on lines unchanged since git HEAD rank last and carry an (old) tag."""

import subprocess
from types import SimpleNamespace

from robotframework_lint import lsp
from robotframework_lint.changed_lines import changed_lines
from robotframework_lint.lsp import Settings, lint_text

COMMITTED = "a\nb\nc\n"


def _repo(tmp_path, text=COMMITTED):
    path = tmp_path / "s.robot"
    path.write_text(text, encoding="utf-8")
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-C", str(tmp_path)]
    for args in (["init", "-q"], ["add", "s.robot"], ["commit", "-q", "-m", "c"]):
        subprocess.run([*git, *args], check=True, capture_output=True)
    return path


def test_appended_line_is_the_only_change(tmp_path):
    assert changed_lines(_repo(tmp_path), COMMITTED + "d\n") == {3}


def test_edited_line_marked(tmp_path):
    assert changed_lines(_repo(tmp_path), "a\nB\nc\n") == {1}


def test_deletion_marks_next_line(tmp_path):
    assert changed_lines(_repo(tmp_path), "a\nc\n") == {1}


def test_crlf_buffer_matches_lf_commit(tmp_path):
    assert changed_lines(_repo(tmp_path), "a\r\nb\r\nc\r\n") == set()


def test_file_outside_git_is_unknown(tmp_path):
    path = tmp_path / "s.robot"
    path.write_text(COMMITTED, encoding="utf-8")
    assert changed_lines(path, COMMITTED) is None


def test_untracked_file_is_unknown(tmp_path):
    _repo(tmp_path)
    assert changed_lines(tmp_path / "new.robot", COMMITTED) is None


def _finding(rule, line):
    return SimpleNamespace(rule=SimpleNamespace(rule_id=rule), severity=SimpleNamespace(value="W"), message="m",
                           range=SimpleNamespace(start=SimpleNamespace(line=line, character=1),
                                                 end=SimpleNamespace(line=line, character=1)))


def test_old_finding_tagged(monkeypatch):
    monkeypatch.setattr(lsp, "_run_robocop", lambda *args: [_finding("ABC01", 1), _finding("ABC02", 2)])
    old, new = lint_text("", Settings(), changed={1})
    assert (old.message, new.message) == ("ABC01 (old) m", "ABC02 m")


def test_unknown_changes_add_no_tag(monkeypatch):
    monkeypatch.setattr(lsp, "_run_robocop", lambda *args: [_finding("ABC01", 1)])
    assert lint_text("", Settings(), changed=None)[0].message == "ABC01 m"


def test_cap_keeps_changed_lines_first(monkeypatch):
    found = [_finding("ERR01", 1), _finding("LEN01", 5)]
    monkeypatch.setattr(lsp, "_run_robocop", lambda *args: found)
    kept, overflow = lint_text("", Settings(max_diagnostics=1), changed={4})
    assert kept.code == "LEN01" and overflow.code == "overflow"


def test_publish_tags_findings_from_git(tmp_path, monkeypatch):
    path = _repo(tmp_path)
    seen = []
    monkeypatch.setattr(lsp, "lint_text", lambda text, settings, suffix, changed: seen.append(changed) or [])
    sent = []
    doc = SimpleNamespace(source=COMMITTED + "d\n", version=1, lines=[])
    ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=lambda u: doc), index=lsp.WorkspaceIndex(),
                         scanned=set(), robotcode={}, settings_for=lambda uri: Settings(),
                         text_document_publish_diagnostics=sent.append)
    lsp.RflintServer.publish(ls, path.as_uri())
    assert seen == [{3}]


def test_git_failure_means_unknown(tmp_path, monkeypatch):
    from robotframework_lint import changed_lines as module

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 5)

    path = _repo(tmp_path)
    monkeypatch.setattr(module.subprocess, "run", fail)
    assert changed_lines(path, COMMITTED) is None


def test_group_tag_follows_first_finding(monkeypatch):
    monkeypatch.setattr(lsp, "_run_robocop", lambda *args: [_finding("ABC01", 1), _finding("ABC01", 5)])
    (diag,) = lint_text("", Settings(group=True), changed={4})
    assert diag.message == "ABC01 (old) x2 (lines 1,5) m" and diag.range.start.line == 0
