"""What one Robot Framework file defines, calls and imports, read from its parsed model.

Positions are 0-based lines and columns, as LSP sends them.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from robot.api import Token, get_model, get_resource_model
from robot.parsing.model.blocks import Keyword, TestCase
from robot.parsing.model.statements import Arguments, Documentation, ResourceImport, Variable
from robot.utils import normalize

MAX_RESULTS = 50
# Fixture settings name a keyword in a NAME token instead of a KEYWORD token.
FIXTURES = {Token.SETUP, Token.TEARDOWN, Token.SUITE_SETUP, Token.SUITE_TEARDOWN,
            Token.TEST_SETUP, Token.TEST_TEARDOWN}
VARIABLE_USE = re.compile(r"[$@&%]\{([^{}]+)\}")
VARIABLE_PREFIX = "var:"


@dataclass(frozen=True)
class Symbol:
    name: str
    kind: str
    line: int
    end_line: int


@dataclass(frozen=True)
class Location:
    uri: str
    line: int
    start: int
    end: int


@dataclass
class Definition:
    name: str
    location: Location
    signature: str
    doc: str


@dataclass
class FileIndex:
    calls: list[Location] = field(default_factory=list)
    names: list[str] = field(default_factory=list)
    definitions: dict[str, Definition] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def key(name: str) -> str:
    return normalize(name, ignore="_")


def variable_key(name: str) -> str:
    """${CONTRACT}, @{Contract} and ${con_tract} are one variable."""
    return VARIABLE_PREFIX + key(name.strip("$@&%{}= "))


def variable_at(line: str, character: int) -> str | None:
    match = next((m for m in VARIABLE_USE.finditer(line) if m.start() <= character <= m.end()), None)
    return variable_key(match.group(1)) if match else None


def parse(text: str, suffix: str):
    parser = get_resource_model if suffix == ".resource" else get_model
    return parser(io.StringIO(text))


def walk(node):
    yield node
    for child in getattr(node, "body", []) + getattr(node, "sections", []):
        yield from walk(child)


def document_symbols(text: str, suffix: str) -> list[Symbol]:
    """Tests, keywords and variables in file order."""
    symbols = []
    for node in walk(parse(text, suffix)):
        if isinstance(node, (TestCase, Keyword)):
            kind = "test" if isinstance(node, TestCase) else "keyword"
            symbols.append(Symbol(node.name, kind, node.lineno - 1, node.end_lineno - 1))
        elif isinstance(node, Variable) and node.name:
            symbols.append(Symbol(node.name, "variable", node.lineno - 1, node.lineno - 1))
    return symbols[:MAX_RESULTS]


def index_file(uri: str, text: str) -> FileIndex:
    model = parse(text, ".resource" if uri.endswith(".resource") else ".robot")
    tokens = _calls(model)
    return FileIndex(
        [Location(uri, t.lineno - 1, t.col_offset, t.end_col_offset) for t in tokens],
        [key(t.value) for t in tokens],
        _definitions(uri, model),
        text.splitlines(keepends=True),
        _imports(uri, model),
    )


def _calls(model) -> list[Token]:
    """Every token that names a called keyword."""
    calls = []
    for node in walk(model):
        if getattr(node, "type", None) in FIXTURES:
            calls.extend(t for t in node.tokens if t.type == Token.NAME and t.value.upper() != "NONE")
        elif hasattr(node, "tokens"):
            calls.extend(t for t in node.tokens if t.type == Token.KEYWORD)
    return calls


def _definitions(uri: str, model) -> dict[str, Definition]:
    found = {}
    for node in walk(model):
        if isinstance(node, Keyword):
            name = node.header.get_token(Token.KEYWORD_NAME)
            loc = Location(uri, name.lineno - 1, name.col_offset, name.end_col_offset)
            found[key(node.name)] = Definition(node.name, loc, _signature(node), _first_doc_line(node))
        elif isinstance(node, Variable) and node.name:
            name = node.get_token(Token.VARIABLE)
            loc = Location(uri, name.lineno - 1, name.col_offset, name.end_col_offset)
            signature = "    ".join([node.name, *node.value])
            found[variable_key(node.name)] = Definition(node.name, loc, signature, "")
    return found


def _signature(node: Keyword) -> str:
    args = next((s.values for s in node.body if isinstance(s, Arguments)), ())
    return f"{node.name}({', '.join(args)})"


def _first_doc_line(node: Keyword) -> str:
    doc = next((s.value for s in node.body if isinstance(s, Documentation)), "")
    return doc.split("\n", 1)[0]


def _imports(uri: str, model) -> list[str]:
    """Resource files this file imports, as file URIs; ${CURDIR} is the file's folder."""
    if not uri.startswith("file:"):
        return []
    folder = Path(url2pathname(urlparse(uri).path)).parent
    found = []
    for node in walk(model):
        if isinstance(node, ResourceImport) and node.name:
            target = node.name.replace("${CURDIR}", str(folder))
            found.append((folder / target).resolve().as_uri())
    return found
