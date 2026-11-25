"""Hook edges: hunks that change the line count, overlapping edit text, robocop failures, main guards."""

import io
import json
import subprocess
import sys

import pytest

from robotframework_lint import autofix
from robotframework_lint.autofix import edited_ranges, fix_file, keep_edited_hunks

LEGACY = "*** Test Cases ***\nT\n    ${a}=    Set Variable    1\n    Log    ${a}\n"


@pytest.mark.parametrize(("ranges", "expected"), [([(2, 3)], "a\nb\nNEW\nc\n"), ([(0, 1)], "a\nb\nc\n")])
def test_insert_kept_only_at_edit(ranges, expected):
    assert keep_edited_hunks("a\nb\nc\n", "a\nb\nNEW\nc\n", ranges) == expected


@pytest.mark.parametrize(("ranges", "expected"), [([(1, 2)], "a\nc\n"), ([(0, 1)], "a\nb\nc\n")])
def test_delete_kept_only_at_edit(ranges, expected):
    assert keep_edited_hunks("a\nb\nc\n", "a\nc\n", ranges) == expected


@pytest.mark.parametrize(("ranges", "expected"), [([(1, 2)], "a\nX\nY\nc\n"), ([(0, 1)], "a\nb\nc\n")])
def test_split_line_kept_only_at_edit(ranges, expected):
    assert keep_edited_hunks("a\nb\nc\n", "a\nX\nY\nc\n", ranges) == expected


@pytest.mark.parametrize(("ranges", "expected"), [
    ([(1, 2)], "a\nB\nc\nd\n"), ([(0, 1)], "A\nb\nc\nd\n"), ([(4, 5)], "a\nb\nc\nd\nE\n")])
def test_same_size_replace_maps_line_by_line(ranges, expected):
    assert keep_edited_hunks("a\nb\nc\nd\n", "A\nB\nc\nd\nE\n", ranges) == expected


def test_overlapping_edit_text_marks_each_copy():
    assert edited_ranges("x\n\n\ny\n", {"new_string": "\n\n"}) == [(0, 2), (1, 3)]


def test_robocop_failure_leaves_file_alone(tmp_path, monkeypatch):
    real = subprocess.run
    monkeypatch.setattr(autofix.subprocess, "run", lambda cmd, **kw: real(
        [sys.executable, "-c", "import sys; sys.exit(1)"], **kw))
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    fix_file(path)
    assert path.read_text(encoding="utf-8") == LEGACY


@pytest.mark.parametrize("newer", ["!newer", "~newer"])
def test_newer_text_never_overwritten(tmp_path, monkeypatch, newer):
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    real = subprocess.run
    monkeypatch.setattr(autofix.subprocess, "run",
                        lambda *args, **kw: path.write_text(newer, encoding="utf-8") and real(*args, **kw))
    fix_file(path)
    assert path.read_text(encoding="utf-8") == newer


def _main(monkeypatch, tool_input, fix=None):
    calls = []
    monkeypatch.setattr(autofix, "fix_file", fix or (lambda path, ranges: calls.append(ranges)))
    monkeypatch.setattr(autofix.sys, "stdin", io.StringIO(json.dumps({"tool_input": tool_input})))
    return autofix.main(), calls


def test_hook_skips_other_file_types(tmp_path, monkeypatch):
    path = tmp_path / "t.py"
    path.write_text("x = 1\n", encoding="utf-8")
    assert _main(monkeypatch, {"file_path": str(path), "new_string": "x = 1\n"}) == (0, [])


def test_hook_skips_delete_only_edit(tmp_path, monkeypatch):
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    assert _main(monkeypatch, {"file_path": str(path), "new_string": ""}) == (0, [])


def test_hook_swallows_robocop_timeout(tmp_path, monkeypatch):
    def slow(path, ranges):
        raise subprocess.TimeoutExpired("robocop", 50)

    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    assert _main(monkeypatch, {"file_path": str(path)}, slow)[0] == 0


def test_edit_text_at_file_start_overlaps():
    assert edited_ranges("\n\n\n", {"new_string": "\n\n"}) == [(0, 2), (1, 3)]


def test_late_replace_keeps_unedited_neighbor():
    original, fixed = "a\nb\nc\nd\ne\nf\n", "a\nb\nc\nD\nE\nf\nG\n"
    assert keep_edited_hunks(original, fixed, [(4, 5)]) == "a\nb\nc\nd\nE\nf\n"


def test_fix_prints_nothing(tmp_path, capfd):
    path = tmp_path / "t.robot"
    path.write_text(LEGACY, encoding="utf-8")
    fix_file(path)
    assert capfd.readouterr() == ("", "")


def test_replace_second_line_stays_original():
    original, fixed = "a\nb\nc\nd\ne\nf\n", "a\nb\nc\nD\nE\nf\nG\n"
    assert keep_edited_hunks(original, fixed, [(3, 4)]) == "a\nb\nc\nD\ne\nf\n"


def test_two_lines_merged_at_edit():
    assert keep_edited_hunks("a\nb\nc\nd\n", "a\nX\nd\n", [(1, 2)]) == "a\nX\nd\n"


def test_insert_at_odd_line_kept():
    assert keep_edited_hunks("a\nb\nc\n", "a\nNEW\nb\nc\n", [(1, 2)]) == "a\nNEW\nb\nc\n"


def test_long_replace_fixes_only_edited_line():
    original = "a\nb\nc\nd\ne\nf\ng\nh\n"
    fixed = "a\nb\nc\nD\nE\nF\nG\nh\nI\n"
    assert keep_edited_hunks(original, fixed, [(6, 7)]) == "a\nb\nc\nd\ne\nf\nG\nh\n"
