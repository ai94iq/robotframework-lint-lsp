"""Minimal LSP server: robocop defaults plus our rules, token-cheap diagnostics.

Token controls: one short line per finding ("RULEID message", capped length),
a per-file cap, a severity floor, dedup of identical findings, and no related
information, code descriptions or data payloads.
"""

from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from lsprotocol import types
from pygls.lsp.server import LanguageServer

RULES_DIR = Path(__file__).parent / "rules"
MAX_MESSAGE = 120
DEBOUNCE_SECONDS = 0.4
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
LSP_SEVERITY = {
    "info": types.DiagnosticSeverity.Information,
    "warning": types.DiagnosticSeverity.Warning,
    "error": types.DiagnosticSeverity.Error,
}
THRESHOLD = {"info": "I", "warning": "W", "error": "E"}


@dataclass
class Settings:
    max_diagnostics: int = 20
    min_severity: str = "warning"
    select: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)

    @classmethod
    def from_options(cls, options: object) -> Settings:
        opts = options if isinstance(options, dict) else {}
        severity = str(opts.get("minSeverity", "warning")).lower()
        if severity not in SEVERITY_ORDER:
            severity = "warning"
        cap = opts.get("maxDiagnostics", 20)
        cap = cap if isinstance(cap, int) and cap > 0 else 20
        return cls(cap, severity, _str_list(opts.get("select")), _str_list(opts.get("ignore")))


def _str_list(value: object) -> list[str]:
    return [str(v) for v in value] if isinstance(value, list) else []


def _severity_name(robocop_severity: object) -> str:
    letter = getattr(robocop_severity, "value", "W")
    return {"I": "info", "W": "warning", "E": "error"}.get(letter, "warning")


def _run_robocop(text: str, suffix: str, settings: Settings) -> list:
    from robocop.config.manager import ConfigManager
    from robocop.config.schema import RawConfig, RawLinterConfig
    from robocop.linter.rules import RuleSeverity
    from robocop.linter.runner import RobocopLinter
    from robocop.source_file import SourceFile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"buffer{suffix}"
        path.write_text(text, encoding="utf-8")
        linter_config = RawLinterConfig(
            select=settings.select or None,
            ignore=settings.ignore or None,
            threshold=RuleSeverity(THRESHOLD[settings.min_severity]),
            custom_rules=[str(RULES_DIR)],
            return_result=True,
        )
        config = RawConfig(sources=[str(path)], linter=linter_config, silent=True)
        manager = ConfigManager(sources=[str(path)], overwrite_config=config)
        linter = RobocopLinter(manager)
        return list(linter.run_check(SourceFile(path=path, config=manager.default_config)))


def lint_text(text: str, settings: Settings, suffix: str = ".robot") -> list[types.Diagnostic]:
    """Lint a buffer and return capped, filtered, deduplicated LSP diagnostics."""
    floor = SEVERITY_ORDER[settings.min_severity]
    seen: set[tuple[int, str, str]] = set()
    result: list[types.Diagnostic] = []
    found = sorted(_run_robocop(text, suffix, settings), key=lambda d: (d.range.start.line, d.range.start.character))
    for diag in found:
        severity = _severity_name(diag.severity)
        if SEVERITY_ORDER[severity] < floor:
            continue
        rule_id = diag.rule.rule_id
        line = max(diag.range.start.line - 1, 0)
        key = (line, rule_id, diag.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(_to_lsp(diag, rule_id, line, severity))
        if len(result) >= settings.max_diagnostics:
            break
    return result


def _to_lsp(diag, rule_id: str, line: int, severity: str) -> types.Diagnostic:
    start_col = max(diag.range.start.character - 1, 0)
    end_line = max(diag.range.end.line - 1, line)
    end_col = max(diag.range.end.character - 1, 0)
    message = f"{rule_id} {diag.message}"
    if len(message) > MAX_MESSAGE:
        message = message[: MAX_MESSAGE - 3] + "..."
    return types.Diagnostic(
        range=types.Range(types.Position(line, start_col), types.Position(end_line, end_col)),
        message=message,
        severity=LSP_SEVERITY[severity],
        code=rule_id,
        source="rflint",
    )


class RflintServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("robotframework-lint-lsp", "0.1.0")
        self.settings = Settings()
        self.pending: dict[str, asyncio.Task] = {}

    def publish(self, uri: str) -> None:
        doc = self.workspace.get_text_document(uri)
        suffix = ".resource" if uri.endswith(".resource") else ".robot"
        try:
            diagnostics = lint_text(doc.source, self.settings, suffix)
        except Exception as exc:  # parse errors must not kill the server
            self.window_log_message(types.LogMessageParams(types.MessageType.Warning, f"rflint: {exc}"[:200]))
            diagnostics = []
        self.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, version=doc.version, diagnostics=diagnostics)
        )


server = RflintServer()


@server.feature(types.INITIALIZE)
def on_initialize(ls: RflintServer, params: types.InitializeParams) -> None:
    ls.settings = Settings.from_options(params.initialization_options)


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def on_open(ls: RflintServer, params: types.DidOpenTextDocumentParams) -> None:
    ls.publish(params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
def on_save(ls: RflintServer, params: types.DidSaveTextDocumentParams) -> None:
    ls.publish(params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
async def on_change(ls: RflintServer, params: types.DidChangeTextDocumentParams) -> None:
    uri = params.text_document.uri
    previous = ls.pending.pop(uri, None)
    if previous:
        previous.cancel()

    async def later() -> None:
        await asyncio.sleep(DEBOUNCE_SECONDS)
        ls.pending.pop(uri, None)
        ls.publish(uri)

    ls.pending[uri] = asyncio.ensure_future(later())


@server.feature(types.TEXT_DOCUMENT_DID_CLOSE)
def on_close(ls: RflintServer, params: types.DidCloseTextDocumentParams) -> None:
    ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[]))


def main() -> None:
    server.start_io()


if __name__ == "__main__":
    main()
