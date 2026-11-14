"""Rules for keyword documentation."""

from robot.running import docstringparser

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker


class _WarningRecorder:
    def __init__(self):
        self.warnings = []

    def warn(self, message):
        self.warnings.append(message)


def has_tags_without_empty_row(doc: str) -> bool:
    """Ask Robot Framework's own docstring parser whether it warns about Tags:."""
    recorder = _WarningRecorder()
    original = docstringparser.LOGGER
    docstringparser.LOGGER = recorder
    try:
        docstringparser.parse_docstring(doc)
    finally:
        docstringparser.LOGGER = original
    return any("before 'Tags:'" in message for message in recorder.warnings)


class DocTagsWithoutEmptyRowRule(Rule):
    """
    Tags header in documentation without an empty row before it.

    The rf-7.5 release notes, section "Deprecated features", say:
    "When specifying tags as part of documentation, omitting an empty row
    before the `Tags:` header is deprecated (`#5707`_)." Detection uses
    Robot Framework's own ``parse_docstring``. Source:
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst

    Incorrect code example:

        [Documentation]    Does a thing.
        ...    Tags: smoke

    Correct code:

        [Documentation]    Does a thing.
        ...
        ...    Tags: smoke
    """

    name = "doc-tags-without-empty-row"
    rule_id = "RFL005"
    message = "No empty row before 'Tags:' is deprecated since RF 7.5"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"


class DocTagsChecker(VisitorChecker):
    doc_tags_without_empty_row: DocTagsWithoutEmptyRowRule

    def visit_Keyword(self, node):  # noqa: N802 - robot visitor naming
        for statement in node.body:
            if getattr(statement, "type", None) == "DOCUMENTATION":
                self.check_documentation(statement)

    def check_documentation(self, node):
        if not has_tags_without_empty_row(node.value):
            return
        tokens = node.get_tokens("ARGUMENT")
        target = next(
            (t for t in reversed(tokens) if t.value.strip().lower().startswith("tags:")),
            node.data_tokens[0],
        )
        self.report(
            self.doc_tags_without_empty_row,
            lineno=target.lineno,
            col=target.col_offset + 1,
            end_col=target.end_col_offset + 1,
        )
