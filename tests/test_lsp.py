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
    found = lint_text(text, Settings(max_diagnostics=100, min_severity="info", select=["RFL006"]))
    assert {d.range.start.line for d in found} == {6, 7, 8, 9}
    assert all(d.code == "RFL006" and len(d.message) <= 120 for d in found)


def test_cap_default_twenty_plus_overflow_marker():
    found = lint_text(NOISY, Settings(min_severity="info"))
    total = len(lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info")))
    assert len(found) == 21
    assert found[-1].code == "overflow"
    assert found[-1].message == f"overflow {total - 20} more findings not shown (maxDiagnostics 20)"


def test_no_marker_under_cap():
    found = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info"))
    assert all(d.code != "overflow" for d in found)


def test_severity_floor_filters():
    info = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info"))
    errors = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="error"))
    assert len(errors) < len(info)
    assert all(d.severity == 1 for d in errors)


def test_dedup_identical_findings():
    found = lint_text(NOISY, Settings(max_diagnostics=1000, min_severity="info"))
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
