"""Minimal LSP server: robocop defaults plus our rules, token-cheap diagnostics.

Token controls: one short line per finding ("RULEID message", capped length),
a per-file cap, a severity floor, dedup of identical findings, and no related
information, code descriptions or data payloads.
"""

from __future__ import annotations

import asyncio
import tempfile

from . import __version__
from dataclasses import dataclass, field, replace
from pathlib import Path

from lsprotocol import types
from pygls import uris
from pygls.lsp.server import LanguageServer

from .hints import FIX_COMMANDS, FIX_HINTS, short_message
from .lsp_navigation import register as register_navigation
from .lsp_navigation import scan_project_of, scan_workspace
from .navigation import WorkspaceIndex
from .project_config import OUR_RULES, rule_filter
from .robotcode_tier import analyze as robotcode_analyze

RULES_DIR = Path(__file__).parent / "rules"
MAX_MESSAGE = 120
MAX_LINT_BYTES = 1_000_000
DEBOUNCE_SECONDS = 0.4
SEVERITY_ORDER = {"info": 0, "warning": 1, "error": 2}
LSP_SEVERITY = {
    "info": types.DiagnosticSeverity.Information,
    "warning": types.DiagnosticSeverity.Warning,
    "error": types.DiagnosticSeverity.Error,
}
MAX_GROUP_LINES = 6
# Rule groups about layout and naming; under the cap they yield to findings about behavior.
STYLE_GROUPS = {"LEN", "SPC", "NAME", "DOC", "COM", "ORD", "TAG"}


@dataclass
class Settings:
    max_diagnostics: int = 20
    min_severity: str = "warning"
    select: list[str] = field(default_factory=list)
    ignore: list[str] = field(default_factory=list)
    group: bool = False  # v4 A/B: grouped findings left more DEPR05/06 unfixed
    robotcode: list[str] = field(default_factory=list)  # empty: tier off

    @classmethod
    def from_options(cls, options: object) -> Settings:
        opts = options if isinstance(options, dict) else {}
        severity = str(opts.get("minSeverity", "warning")).lower()
        if severity not in SEVERITY_ORDER:
            severity = "warning"
        cap = opts.get("maxDiagnostics", 20)
        cap = cap if isinstance(cap, int) and cap > 0 else 20
        group = opts.get("groupFindings", False) is True
        return cls(cap, severity, _str_list(opts.get("select")), _str_list(opts.get("ignore")), group,
                   _str_list(opts.get("robotcodeCommand")))


def file_settings(settings: Settings, rules: tuple[list[str], list[str]]) -> Settings:
    """Client settings narrowed by the project's lists; a project select keeps our rules on."""
    select, ignore = rules
    return replace(settings, select=[*select, OUR_RULES] if select else settings.select,
                   ignore=[*settings.ignore, *ignore])


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
            threshold=RuleSeverity("I"),  # floor applied after promotion in lint_text
            custom_rules=[str(RULES_DIR)],
            return_result=True,
        )
        config = RawConfig(sources=[str(path)], linter=linter_config, silent=True)
        # A robocop or pyproject file above the temp dir must not pick rules or rule files.
        manager = ConfigManager(sources=[str(path)], root=Path(tmp), ignore_file_config=True,
                                overwrite_config=config)
        linter = RobocopLinter(manager)
        return list(linter.run_check(SourceFile(path=path, config=manager.default_config)))


def lint_text(text: str, settings: Settings, suffix: str = ".robot") -> list[types.Diagnostic]:
    """Lint a buffer and return capped, filtered, deduplicated LSP diagnostics."""
    groups = _collect(_run_robocop(text, suffix, settings), settings)
    return _cap([_group_to_lsp(members) for members in groups.values()], settings)


def _collect(found: list, settings: Settings) -> dict[str, list[tuple]]:
    floor = SEVERITY_ORDER[settings.min_severity]
    seen: set[tuple[int, str, str]] = set()
    groups: dict[str, list[tuple]] = {}
    for diag in sorted(found, key=lambda d: (d.range.start.line, d.range.start.character)):
        rule_id = diag.rule.rule_id
        severity = _severity_name(diag.severity)
        # Promote only Info rules one command fixes; each promoted finding costs agents an edit turn.
        if severity == "info" and rule_id in FIX_COMMANDS:
            severity = "warning"
        if SEVERITY_ORDER[severity] < floor:
            continue
        line = max(diag.range.start.line - 1, 0)
        key = (line, rule_id, diag.message)
        if key in seen:
            continue
        seen.add(key)
        group_key = rule_id if settings.group else f"{rule_id}:{len(seen)}"
        groups.setdefault(group_key, []).append((diag, rule_id, line, severity))
    return groups


def _cap(result: list[types.Diagnostic], settings: Settings) -> list[types.Diagnostic]:
    """Keep errors, then behavior warnings, then style, and show the kept ones in line order."""
    result.sort(key=lambda d: (d.range.start.line, d.range.start.character))
    if len(result) <= settings.max_diagnostics:
        return result
    kept = sorted(result, key=_tier)[: settings.max_diagnostics]
    kept.sort(key=lambda d: (d.range.start.line, d.range.start.character))
    return kept + [_overflow(len(result) - settings.max_diagnostics, settings)]


def _tier(diag: types.Diagnostic) -> int:
    if diag.severity == types.DiagnosticSeverity.Error:
        return 0
    return 2 if str(diag.code).rstrip("0123456789") in STYLE_GROUPS else 1


def _overflow(hidden: int, settings: Settings) -> types.Diagnostic:
    # Without it an agent can't tell a clean tail from a truncated one.
    return types.Diagnostic(
        range=types.Range(types.Position(0, 0), types.Position(0, 0)),
        message=f"overflow {hidden} more findings not shown (maxDiagnostics {settings.max_diagnostics})",
        severity=types.DiagnosticSeverity.Information,
        code="overflow",
        source="rflint",
    )


def _lint_error(exc: Exception) -> types.Diagnostic:
    """One finding for a failed lint: an empty list would read as a clean file."""
    return types.Diagnostic(
        range=types.Range(types.Position(0, 0), types.Position(0, 0)),
        message=f"lint-error linting failed, findings unknown: {exc}"[:MAX_MESSAGE],
        severity=types.DiagnosticSeverity.Warning,
        code="lint-error",
        source="rflint",
    )


def _group_to_lsp(members: list[tuple]) -> types.Diagnostic:
    """One diagnostic per rule, anchored at its first finding, with the worst severity."""
    diag, rule_id, line, _ = members[0]
    severity = max((m[3] for m in members), key=SEVERITY_ORDER.__getitem__)
    count = ""
    if len(members) > 1:
        lines = [str(m[2] + 1) for m in members[:MAX_GROUP_LINES]]
        more = ",..." if len(members) > MAX_GROUP_LINES else ""
        count = f"x{len(members)} (lines {','.join(lines)}{more}) "
    return _to_lsp(diag, rule_id, line, severity, count)


def _to_lsp(diag, rule_id: str, line: int, severity: str, count: str = "") -> types.Diagnostic:
    start_col = max(diag.range.start.character - 1, 0)
    end_line = max(diag.range.end.line - 1, line)
    end_col = max(diag.range.end.character - 1, 0)
    command = FIX_COMMANDS.get(rule_id)
    hint = f"fix all: {command}" if command else FIX_HINTS.get(rule_id)
    suffix = f"; {hint}" if hint else ""
    base = f"{rule_id} {count}{short_message(rule_id, diag.message)}"
    room = MAX_MESSAGE - len(suffix)
    if len(base) > room:
        base = base[: room - 3] + "..."
    message = base + suffix
    return types.Diagnostic(
        range=types.Range(types.Position(line, start_col), types.Position(end_line, end_col)),
        message=message,
        severity=LSP_SEVERITY[severity],
        code=rule_id,
        source="rflint",
    )


class RflintServer(LanguageServer):
    def __init__(self) -> None:
        super().__init__("robotframework-lint-lsp", __version__)
        self.settings = Settings()
        self.pending: dict[str, asyncio.Task] = {}
        self.index = WorkspaceIndex()
        self.root: Path | None = None
        self.scanned: set[Path] = set()
        self.robotcode: dict[str, list[types.Diagnostic]] = {}  # last on-save result per uri

    def settings_for(self, uri: str) -> Settings:
        if not uri.startswith("file:"):
            return self.settings
        return file_settings(self.settings, rule_filter(Path(uris.to_fs_path(uri))))

    def publish(self, uri: str) -> None:
        doc = self.workspace.get_text_document(uri)
        suffix = ".resource" if uri.endswith(".resource") else ".robot"
        if len(doc.source) > MAX_LINT_BYTES:  # a generated blob would hold the event loop
            self.text_document_publish_diagnostics(
                types.PublishDiagnosticsParams(uri=uri, version=doc.version, diagnostics=[]))
            return
        try:
            scan_project_of(self.index, self.scanned, uri)
            self.index.update(uri, doc.source)
            diagnostics = self.robotcode.get(uri, []) + lint_text(doc.source, self.settings_for(uri), suffix)
            for diag in diagnostics:  # robocop columns are code points
                diag.range = self.workspace.position_codec.range_to_client_units(doc.lines, diag.range)
        except Exception as exc:  # parse errors must not kill the server
            self.window_log_message(types.LogMessageParams(types.MessageType.Warning, f"rflint: {exc}"[:200]))
            diagnostics = [_lint_error(exc)]
        self.text_document_publish_diagnostics(
            types.PublishDiagnosticsParams(uri=uri, version=doc.version, diagnostics=diagnostics)
        )


server = RflintServer()
register_navigation(server)


@server.feature(types.INITIALIZE)
def on_initialize(ls: RflintServer, params: types.InitializeParams) -> None:
    ls.settings = Settings.from_options(params.initialization_options)
    scan_workspace(ls.index, ls.scanned, params.root_uri)
    if params.root_uri:
        ls.root = Path(uris.to_fs_path(params.root_uri))


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def on_open(ls: RflintServer, params: types.DidOpenTextDocumentParams) -> None:
    ls.publish(params.text_document.uri)


@server.feature(types.TEXT_DOCUMENT_DID_SAVE)
async def on_save(ls: RflintServer, params: types.DidSaveTextDocumentParams) -> None:
    uri = params.text_document.uri
    if ls.settings.robotcode and ls.root:
        # robotcode reads the saved file in place; a cold run takes seconds, so off the event loop.
        path = Path(uris.to_fs_path(uri))
        ls.robotcode[uri] = await asyncio.to_thread(robotcode_analyze, ls.settings.robotcode, path, ls.root)
    ls.publish(uri)


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
    pending = ls.pending.pop(params.text_document.uri, None)
    if pending:
        pending.cancel()  # a late publish would bring back diagnostics for a closed file
    ls.robotcode.pop(params.text_document.uri, None)
    ls.text_document_publish_diagnostics(types.PublishDiagnosticsParams(uri=params.text_document.uri, diagnostics=[]))


def main() -> None:
    server.start_io()


if __name__ == "__main__":
    main()
