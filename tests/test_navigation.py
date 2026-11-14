"""Symbols, definition, references and hover over the nav samples."""

from pathlib import Path

from robotframework_lint.navigation import WorkspaceIndex, document_symbols

NAV = Path(__file__).parent / "samples" / "nav"
RESOURCE = (NAV / "common.resource").resolve().as_uri()
SUITE = (NAV / "suite.robot").resolve().as_uri()


def _index() -> WorkspaceIndex:
    index = WorkspaceIndex()
    for path in NAV.iterdir():
        index.update(path.resolve().as_uri(), path.read_text(encoding="utf-8"))
    return index


def test_symbols_list_keywords_and_variables():
    found = [(s.name, s.kind, s.line) for s in document_symbols((NAV / "common.resource").read_text(), ".resource")]
    assert found == [("${GREETING}", "variable", 1), ("Say Hello", "keyword", 5), ("Open Shop", "keyword", 11)]


def test_symbols_list_test_cases():
    found = [(s.name, s.kind) for s in document_symbols((NAV / "suite.robot").read_text(), ".robot")]
    assert found == [("Greets A User", "test", )]


def test_definition_matches_normalized_name():
    # "say_hello" in the suite resolves to "Say Hello" in the resource
    location = _index().definition(SUITE, line=7, character=6)
    assert (location.uri, location.line) == (RESOURCE, 5)


def test_definition_from_setup_fixture():
    location = _index().definition(SUITE, line=2, character=16)
    assert (location.uri, location.line) == (RESOURCE, 11)


def test_definition_off_a_keyword_is_none():
    assert _index().definition(SUITE, line=5, character=0) is None


def test_references_cover_every_call_site():
    refs = sorted((r.uri, r.line) for r in _index().references(RESOURCE, line=5, character=2))
    assert refs == sorted([(RESOURCE, 12), (SUITE, 7)])


def test_references_capped_at_fifty():
    calls = "".join(f"T{i}\n    Say Hello    x\n" for i in range(60))
    index = _index()
    index.update("file:///many.robot", "*** Test Cases ***\n" + calls)
    assert len(index.references(RESOURCE, line=5, character=2)) == 50


def test_symbols_capped_at_fifty():
    tests = "".join(f"T{i}\n    No Operation\n" for i in range(60))
    assert len(document_symbols("*** Test Cases ***\n" + tests, ".robot")) == 50


def test_hover_shows_args_and_first_doc_line():
    text = _index().hover(SUITE, line=7, character=6)
    assert text == "Say Hello(${name})\nLogs a greeting to the given name."
