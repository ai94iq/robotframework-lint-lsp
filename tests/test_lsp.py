"""LSP server: raw stdio JSON-RPC roundtrip plus token controls."""

import json
import subprocess
import sys
from pathlib import Path

from robotframework_lint.lsp import Settings, lint_text

SAMPLES = Path(__file__).parent / "samples"
NOISY = "*** Test Cases ***\n" + "".join(
    f"test {i}\n    log  x    \n    Sleep    1s\n" for i in range(40)
)


def _frame(payload: dict) -> bytes:
    body = json.dumps(payload).encode()
    return f"Content-Length: {len(body)}\r\n\r\n".encode() + body


def _read_messages(stream, until_method: str) -> dict:
    while True:
        length = 0
        while (line := stream.readline().strip()):
            if line.lower().startswith(b"content-length"):
                length = int(line.split(b":")[1])
        message = json.loads(stream.read(length))
        if message.get("method") == until_method:
            return message


def test_stdio_roundtrip_publishes_capped_diagnostics():
    uri = (SAMPLES / "arg_names_deprecated.robot").resolve().as_uri()
    text = (SAMPLES / "arg_names_deprecated.robot").read_text(encoding="utf-8")
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "processId": None, "rootUri": None, "capabilities": {},
            "initializationOptions": {"maxDiagnostics": 2, "minSeverity": "info"}}}))
        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": uri, "languageId": "robotframework", "version": 1, "text": text}}}))
        proc.stdin.flush()
        published = _read_messages(proc.stdout, "textDocument/publishDiagnostics")
    finally:
        proc.kill()
    diagnostics = published["params"]["diagnostics"]
    assert len(diagnostics) == 3, diagnostics  # two findings plus the overflow marker
    for diag in diagnostics:
        assert set(diag) <= {"range", "message", "severity", "code", "source"}
        assert diag["message"].startswith(diag["code"] + " ")


def test_our_rule_reported_with_line():
    text = (SAMPLES / "arg_names_deprecated.robot").read_text(encoding="utf-8")
    found = lint_text(text, Settings(max_diagnostics=100, min_severity="info", select=["RFL006"], group=False))
    assert {d.range.start.line for d in found} == {6, 7, 8, 9}
    assert all(d.code == "RFL006" and len(d.message) <= 120 for d in found)


def test_cap_default_twenty_plus_overflow_marker():
    found = lint_text(NOISY, Settings(min_severity="info", group=False))
    total = len(lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info", group=False)))
    assert len(found) == 21
    assert found[-1].code == "overflow"
    assert found[-1].message == f"overflow {total - 20} more findings not shown (maxDiagnostics 20)"


def test_no_marker_under_cap():
    found = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info", group=False))
    assert all(d.code != "overflow" for d in found)


def test_severity_floor_filters():
    info = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info", group=False))
    errors = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="error"))
    assert len(errors) < len(info)
    assert all(d.severity == 1 for d in errors)


def test_dedup_identical_findings():
    found = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info", group=False))
    keys = [(d.range.start.line, d.code, d.message) for d in found]
    assert len(keys) == len(set(keys))


def test_settings_from_options_defaults_and_overrides():
    assert Settings.from_options(None) == Settings()
    s = Settings.from_options({"maxDiagnostics": 5, "minSeverity": "ERROR", "ignore": ["DOC01"]})
    assert (s.max_diagnostics, s.min_severity, s.ignore) == (5, "error", ["DOC01"])
    assert Settings.from_options({"maxDiagnostics": -1, "minSeverity": "bogus"}) == Settings()


def test_two_quick_changes_publish_once(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from robotframework_lint import lsp

    monkeypatch.setattr(lsp, "DEBOUNCE_SECONDS", 0.05)
    calls: list[str] = []
    ls = SimpleNamespace(pending={}, publish=calls.append)
    params = SimpleNamespace(text_document=SimpleNamespace(uri="file:///x.robot"))

    async def scenario() -> None:
        await lsp.on_change(ls, params)
        await lsp.on_change(ls, params)
        await asyncio.sleep(0.2)

    asyncio.run(scenario())
    assert calls == ["file:///x.robot"]


def test_rules_load_once_with_pyproject_and_entry_point(monkeypatch):
    from importlib.metadata import entry_points

    from robotframework_lint.lsp import _run_robocop

    assert any(ep.name == "robotframework_lint" for ep in entry_points(group="robocop.plugins"))
    monkeypatch.chdir(Path(__file__).parent.parent)  # pyproject custom_rules applies here
    text = (SAMPLES / "arg_names_deprecated.robot").read_text(encoding="utf-8")
    raw = _run_robocop(text, ".robot", Settings(min_severity="info", select=["RFL006"]))
    on_line = [d for d in raw if d.range.start.line - 1 == 6]
    assert len(on_line) == 1, [(d.rule.rule_id, d.message) for d in on_line]


NON_ASCII = "*** Test Cases ***\nT\n    Log    ä😀    \n"


def _trailing_space_start(encoding: str) -> int:
    """Open NON_ASCII under one position encoding; return SPC01's start column."""
    proc = subprocess.Popen([sys.executable, "-m", "robotframework_lint.lsp"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        proc.stdin.write(_frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "processId": None, "rootUri": None, "capabilities": {"general": {"positionEncodings": [encoding]}},
            "initializationOptions": {"minSeverity": "info"}}}))
        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "initialized", "params": {}}))
        proc.stdin.write(_frame({"jsonrpc": "2.0", "method": "textDocument/didOpen", "params": {
            "textDocument": {"uri": "file:///x.robot", "languageId": "robotframework", "version": 1,
                             "text": NON_ASCII}}}))
        proc.stdin.flush()
        published = _read_messages(proc.stdout, "textDocument/publishDiagnostics")
    finally:
        proc.kill()
    (spc,) = [d for d in published["params"]["diagnostics"] if d["code"] == "SPC01"]
    return spc["range"]["start"]["character"]


def test_diagnostic_columns_utf16():
    # "    Log    ä😀" is 13 code points; the emoji is 2 utf-16 units
    assert _trailing_space_start("utf-16") == 14


def test_diagnostic_columns_utf8():
    # same prefix is 17 utf-8 bytes (ä 2, emoji 4)
    assert _trailing_space_start("utf-8") == 17


def test_deprecations_pass_warning_floor():
    # DEPR rules are Info in robocop, but agents left them unfixed when hidden
    text = ("*** Settings ***\nLibrary    String\nLibrary    Collections\n\n\n*** Test Cases ***\nT\n"
            "    Set Test Variable    ${x}    1\n    ${items}    Create List    a\n")
    found = {d.code: d.severity for d in lint_text(text, Settings())}
    assert found.get("DEPR05") == 2 and found.get("DEPR06") == 2, found
    assert "IMP02" not in found  # Info import order stays hidden
    assert "IMP02" in {d.code for d in lint_text(text, Settings(min_severity="info"))}


def test_deprecation_message_has_fix_command():
    text = "*** Test Cases ***\nT\n    Set Test Variable    ${x}    1\n"
    (depr,) = [d for d in lint_text(text, Settings()) if d.code == "DEPR05"]
    assert depr.message == ("DEPR05 Set Test Variable used instead of VAR; "
                            "fix all: robocop format --select ReplaceWithVAR <file>")


def test_same_rule_grouped_into_one_diagnostic():
    text = ("*** Test Cases ***\nT\n    Set Test Variable    ${x}    1\n    Log    x\n"
            "    Set Test Variable    ${y}    2\n    Set Suite Variable    ${z}    3\n")
    depr = [d for d in lint_text(text, Settings(group=True)) if d.code == "DEPR05"]
    assert len(depr) == 1, depr
    assert depr[0].range.start.line == 2
    assert depr[0].message.startswith("DEPR05 x3 (lines 3,5,6) ")
    assert depr[0].message.endswith("fix all: robocop format --select ReplaceWithVAR <file>")
    assert len(depr[0].message) <= 120


def test_fixable_info_rule_promoted_with_command():
    text = "*** Keywords ***\nK\n    [Return]    1\n"
    (depr,) = [d for d in lint_text(text, Settings()) if d.code == "DEPR11"]
    assert depr.severity == 2
    assert depr.message.endswith("; fix all: robocop check --fix --select DEPR11 <file>")


def test_grouping_off_by_default():
    # v4 A/B: grouped DEPR05/06 left more findings than one diagnostic per line
    text = ("*** Test Cases ***\nT\n    Set Test Variable    ${x}    1\n"
            "    Set Test Variable    ${y}    2\n")
    assert [d.range.start.line for d in lint_text(text, Settings()) if d.code == "DEPR05"] == [2, 3]
    assert Settings.from_options({}).group is False
    assert Settings.from_options({"groupFindings": True}).group is True


def test_mixed_assignment_style_names_fix_command():
    # MISC04 was the largest leftover in A/B runs; agents saw it but did not fix it by hand
    text = "*** Test Cases ***\nT\n    ${a}=    Set Variable    1\n    ${b}    Set Variable    2\n    Log    ${a}${b}\n"
    (misc,) = [d for d in lint_text(text, Settings()) if d.code == "MISC04"]
    assert misc.message.endswith("; fix all: robocop check --fix --select MISC04 <file>")


def test_inline_if_info_promoted_with_command():
    text = "*** Test Cases ***\nT\n    IF    $x\n        Log    a\n    END\n"
    (misc,) = [d for d in lint_text(text, Settings()) if d.code == "MISC09"]
    assert misc.severity == 2
    assert misc.message.endswith("; fix all: robocop check --fix --select MISC09 <file>")


def test_info_rule_without_command_not_promoted():
    text = "*** Settings ***\nLibrary    String\nLibrary    Collections\n"
    assert "IMP02" not in {d.code for d in lint_text(text, Settings())}


def test_close_cancels_pending_publish(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from robotframework_lint import lsp

    monkeypatch.setattr(lsp, "DEBOUNCE_SECONDS", 0.05)
    calls: list[str] = []
    ls = SimpleNamespace(pending={}, robotcode={}, publish=calls.append,
                         text_document_publish_diagnostics=lambda p: None)
    params = SimpleNamespace(text_document=SimpleNamespace(uri="file:///x.robot"))

    async def scenario() -> None:
        await lsp.on_change(ls, params)
        lsp.on_close(ls, params)
        await asyncio.sleep(0.2)

    asyncio.run(scenario())
    assert calls == []


def test_parent_config_cannot_steer_lint(tmp_path, monkeypatch):
    import tempfile

    (tmp_path / "pyproject.toml").write_text('[tool.robocop.lint]\nignore = ["*"]\n')
    (tmp_path / "t").mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "t"))
    assert lint_text(NOISY, Settings())


def test_huge_buffer_skips_lint(monkeypatch):
    from types import SimpleNamespace

    from robotframework_lint import lsp

    monkeypatch.setattr(lsp, "MAX_LINT_BYTES", 10)
    sent = []
    doc = SimpleNamespace(source=NOISY, version=1, lines=NOISY.splitlines(True))
    ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=lambda u: doc), settings=Settings(),
                         index=SimpleNamespace(update=lambda *a: None), window_log_message=lambda p: None,
                         text_document_publish_diagnostics=sent.append)
    lsp.RflintServer.publish(ls, "file:///x.robot")
    assert sent[0].diagnostics == []


def test_server_info_version_matches_package():
    from importlib.metadata import version
    from robotframework_lint.lsp import RflintServer
    assert RflintServer().version == version("robotframework-lint-lsp")
