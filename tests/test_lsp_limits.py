"""Boundaries of the server's message, range, cap and size limits, and its document handlers."""

import asyncio
import importlib
from importlib import metadata
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from lsprotocol import types
from pygls.workspace import PositionCodec

import robotframework_lint
from robotframework_lint import lsp
from robotframework_lint.lsp import Settings, lint_text


def _finding(rule="ABC01", line=1, col=1, end=None, message="m", severity="W"):
    end_line, end_col = end or (line, col)
    return SimpleNamespace(
        rule=SimpleNamespace(rule_id=rule), severity=SimpleNamespace(value=severity), message=message,
        range=SimpleNamespace(start=SimpleNamespace(line=line, character=col),
                              end=SimpleNamespace(line=end_line, character=end_col)))


def _lint(monkeypatch, findings, settings=None):
    monkeypatch.setattr(lsp, "_run_robocop", lambda *args: findings)
    return lint_text("", settings or Settings())


def _range(diag):
    return (diag.range.start.line, diag.range.start.character, diag.range.end.line, diag.range.end.character)


def test_message_fitting_limit_stays_whole(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(message="x" * 114)])
    assert diag.message == "ABC01 " + "x" * 114


def test_long_message_cut_to_limit(monkeypatch):
    short, long = _lint(monkeypatch, [_finding(message="x" * 115), _finding(line=2, message="y" * 300)])
    assert short.message == "ABC01 " + "x" * 111 + "..."
    assert long.message == "ABC01 " + "y" * 111 + "..."


def test_fix_command_counts_toward_limit(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(rule="DEPR05", message="z" * 200)])
    suffix = "; fix all: robocop format --select ReplaceWithVAR <file>"
    assert len(diag.message) == 120 and diag.message.endswith("..." + suffix)


def test_ranges_become_zero_based(monkeypatch):
    found = [_finding(line=1, col=1, end=(1, 5)), _finding(line=3, col=2, end=(8, 6)),
             _finding(line=9, col=0, end=(0, 0))]
    assert [_range(d) for d in _lint(monkeypatch, found)] == [(0, 0, 0, 4), (2, 1, 7, 5), (8, 0, 8, 0)]


def test_duplicate_does_not_hide_next(monkeypatch):
    found = [_finding(), _finding(), _finding(rule="ABC02")]
    assert [d.code for d in _lint(monkeypatch, found)] == ["ABC01", "ABC02"]


def test_error_with_fix_command_stays_error(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(rule="DEPR05", severity="E")])
    assert diag.severity == types.DiagnosticSeverity.Error


def test_cap_exactly_full_has_no_overflow(monkeypatch):
    found = [_finding(line=n) for n in range(1, 21)]
    assert [d.code for d in _lint(monkeypatch, found)] == ["ABC01"] * 20


def test_cap_keeps_behavior_over_style(monkeypatch):
    kept, overflow = _lint(monkeypatch, [_finding(rule="LEN01", line=2), _finding(line=5)],
                           Settings(max_diagnostics=1))
    assert kept.code == "ABC01" and overflow.code == "overflow"


def test_cap_keeps_error_over_behavior(monkeypatch):
    kept, _ = _lint(monkeypatch, [_finding(line=1), _finding(rule="ABC02", line=5, severity="E")],
                    Settings(max_diagnostics=1))
    assert kept.code == "ABC02"


def test_overflow_sits_at_file_start(monkeypatch):
    found = [_finding(line=n) for n in range(3, 6)]
    overflow = _lint(monkeypatch, found, Settings(max_diagnostics=1))[-1]
    assert _range(overflow) == (0, 0, 0, 0)
    assert overflow.message == "overflow 2 more findings not shown (maxDiagnostics 1)"


def test_two_grouped_findings_show_count(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(line=3), _finding(line=4)], Settings(group=True))
    assert diag.message == "ABC01 x2 (lines 3,4) m"


def test_group_lists_six_lines_then_dots(monkeypatch):
    found = [_finding(line=n) for n in range(1, 8)]
    (diag,) = _lint(monkeypatch, found, Settings(group=True))
    assert diag.message == "ABC01 x7 (lines 1,2,3,4,5,6,...) m"


@pytest.mark.parametrize(("cap", "expected"), [(0, 20), (-1, 20), (1, 1), (True, 1), ("5", 20)])
def test_max_diagnostics_option(cap, expected):
    assert Settings.from_options({"maxDiagnostics": cap}).max_diagnostics == expected


def test_group_option_needs_true():
    assert Settings.from_options({"groupFindings": 1}).group is False
    assert Settings.from_options({"groupFindings": True}).group is True


def test_ignore_list_reaches_robocop():
    text = "*** Test Cases ***\nT\n    log  x    \n"
    codes = {d.code for d in lint_text(text, Settings(max_diagnostics=100))}
    ignored = sorted(codes)[0]
    assert ignored not in {d.code for d in lint_text(text, Settings(max_diagnostics=100, ignore=[ignored]))}


def test_lint_prints_nothing(capfd):
    lint_text("*** Test Cases ***\nT\n    log  x    \n", Settings())
    assert capfd.readouterr() == ("", "")


def _server(source, logs=None):
    sent = []
    doc = SimpleNamespace(source=source, version=1, lines=source.splitlines(keepends=True))
    ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=lambda u: doc, position_codec=PositionCodec()),
                         index=lsp.WorkspaceIndex(), scanned=set(), robotcode={}, settings_for=lambda uri: Settings(),
                         window_log_message=(logs if logs is not None else []).append,
                         text_document_publish_diagnostics=sent.append)
    return ls, sent


def test_size_limit_is_inclusive(monkeypatch):
    linted = []
    monkeypatch.setattr(lsp, "lint_text", lambda text, settings, suffix, changed: linted.append(len(text)) or [])
    ls, sent = _server("x" * 1_000_000)
    lsp.RflintServer.publish(ls, "untitled:x.robot")
    assert linted == [1_000_000] and sent[0].diagnostics == []


def test_oversized_file_reports_lint_error():
    ls, sent = _server("x" * 1_000_001)
    lsp.RflintServer.publish(ls, "untitled:x.robot")
    (diag,) = sent[0].diagnostics
    assert diag.message == "lint-error file over 1 MB not linted, findings unknown"
    assert _range(diag) == (0, 0, 0, 0)


@pytest.mark.parametrize(("uri", "suffix"), [("untitled:x.resource", ".resource"), ("untitled:x.robot", ".robot")])
def test_suffix_follows_uri(monkeypatch, uri, suffix):
    seen = []
    monkeypatch.setattr(lsp, "lint_text", lambda text, settings, sfx, changed: seen.append(sfx) or [])
    ls, _ = _server("x")
    lsp.RflintServer.publish(ls, uri)
    assert seen == [suffix]


def test_crash_log_cut_to_200(monkeypatch):
    def crash(*args, **kwargs):
        raise RuntimeError("e" * 1000)

    monkeypatch.setattr(lsp, "lint_text", crash)
    logs = []
    ls, _ = _server("x", logs)
    lsp.RflintServer.publish(ls, "untitled:x.robot")
    assert logs[0].message == ("rflint: " + "e" * 1000)[:200]


def test_debounce_waits_before_publish(monkeypatch):
    waits = []

    async def sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr(lsp.asyncio, "sleep", sleep)
    ls = SimpleNamespace(pending={}, publish=lambda uri: None)
    params = SimpleNamespace(text_document=SimpleNamespace(uri="file:///x.robot"))

    async def scenario():
        await lsp.on_change(ls, params)
        await ls.pending["file:///x.robot"]

    asyncio.run(scenario())
    assert waits == [0.4]


def test_initialize_sets_root(tmp_path):
    ls = SimpleNamespace(index=lsp.WorkspaceIndex(), scanned=set(), root=None)
    params = types.InitializeParams(capabilities=types.ClientCapabilities(), root_uri=tmp_path.as_uri())
    lsp.on_initialize(ls, params)
    assert ls.root == tmp_path


@pytest.mark.parametrize(("command", "root"), [(["robotcode"], None), ([], Path("."))])
def test_robotcode_needs_command_and_root(monkeypatch, command, root):
    calls, published = [], []
    monkeypatch.setattr(lsp, "robotcode_analyze", lambda *args: calls.append(args) or [])
    ls = SimpleNamespace(settings=SimpleNamespace(robotcode=command), root=root, robotcode={},
                         workspace=SimpleNamespace(text_documents={}), publish=published.append)
    params = types.DidSaveTextDocumentParams(text_document=types.TextDocumentIdentifier(uri="file:///D:/x.robot"))
    asyncio.run(lsp.on_save(ls, params))
    assert calls == [] and published == ["file:///D:/x.robot"]


def test_version_falls_back_outside_install(monkeypatch):
    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(metadata, "version", missing)
    try:
        assert importlib.reload(robotframework_lint).__version__ == "0+unknown"
    finally:
        monkeypatch.undo()
        importlib.reload(robotframework_lint)


def _send(proc, method, params):
    body = json.dumps({"jsonrpc": "2.0", "method": method, "params": params}).encode()
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    proc.stdin.flush()


def _next_publish(stream):
    while True:
        length = 0
        while (line := stream.readline().strip()):
            if line.lower().startswith(b"content-length"):
                length = int(line.split(b":")[1])
        message = json.loads(stream.read(length))
        if message.get("method") == "textDocument/publishDiagnostics":
            return message["params"]


def _open_server(uri, text):
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                       "params": {"processId": None, "rootUri": None, "capabilities": {}}}).encode()
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
    _send(proc, "initialized", {})
    _send(proc, "textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "robotframework",
                                                           "version": 1, "text": text}})
    _next_publish(proc.stdout)
    return proc


def test_change_save_close_each_publish(tmp_path):
    uri, text = (tmp_path / "s.robot").as_uri(), "*** Test Cases ***\nT\n    log  x    \n"
    proc = _open_server(uri, text)
    try:
        _send(proc, "textDocument/didChange", {"textDocument": {"uri": uri, "version": 2},
                                                "contentChanges": [{"text": text + "\n"}]})
        changed = _next_publish(proc.stdout)
        _send(proc, "textDocument/didSave", {"textDocument": {"uri": uri}})
        saved = _next_publish(proc.stdout)
        _send(proc, "textDocument/didClose", {"textDocument": {"uri": uri}})
        closed = _next_publish(proc.stdout)
    finally:
        proc.kill()
    assert changed["version"] == 2 and saved["diagnostics"] and closed["diagnostics"] == []


def test_hint_room_is_limit_minus_hint(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(rule="VAR02", message="v" * 200)])
    assert len(diag.message) == 120 and diag.message.endswith("...; drop the assignment or use the variable")


def test_wide_columns_shift_by_one(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(line=0, col=5, end=(0, 9))])
    assert _range(diag) == (0, 4, 0, 8)


def test_six_grouped_findings_have_no_dots(monkeypatch):
    (diag,) = _lint(monkeypatch, [_finding(line=n) for n in range(1, 7)], Settings(group=True))
    assert diag.message == "ABC01 x6 (lines 1,2,3,4,5,6) m"


def test_grouping_off_when_unset():
    assert Settings.from_options({}).group is False
