"""Rules for FOR loops."""

from robot.api import Token

from robocop.linter.fix import Fix, FixApplicability, FixAvailability, TextEdit
from robocop.linter.rules import FixableRule, RuleSeverity, VisitorChecker

RF_70_NOTES = (
    "https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.0.rst"
)


class ForInZipWithoutModeRule(FixableRule):
    """
    FOR IN ZIP without an explicit ``mode``.

    Robot Framework 7.0 added ``mode=STRICT``, ``mode=SHORTEST`` and
    ``mode=LONGEST`` to FOR IN ZIP. Lists of different lengths are planned to
    fail in a later release, so the release notes advise setting ``mode``
    explicitly. Source: rf-7.0 release notes,
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.0.rst

    Incorrect code example:

        FOR    ${a}    ${b}    IN ZIP    ${LIST_A}    ${LIST_B}
            Log    ${a} ${b}
        END

    Correct code:

        FOR    ${a}    ${b}    IN ZIP    ${LIST_A}    ${LIST_B}    mode=STRICT
            Log    ${a} ${b}
        END

    The fix adds ``mode=SHORTEST``, the mode RF 7.x uses when none is set,
    so behaviour does not change. Headers with a comment or ``...`` are left
    for a manual edit.
    """

    name = "for-in-zip-without-mode"
    rule_id = "RFL001"
    message = "FOR IN ZIP without mode=; set STRICT, SHORTEST or LONGEST"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"
    fix_availability = FixAvailability.SOMETIMES

    def fix(self, diag, source_lines: list[str]) -> Fix | None:
        line_no = diag.range.start.line
        line = source_lines[line_no - 1].rstrip()
        next_line = source_lines[line_no] if line_no < len(source_lines) else ""
        if "#" in line or next_line.lstrip().startswith("..."):
            return None
        end_col = len(line) + 1
        edit = TextEdit(self.rule_id, self.name, line_no, end_col, line_no, end_col,
                        "    mode=SHORTEST")
        return Fix(edits=[edit], message="Add mode=SHORTEST, the current default",
                   applicability=FixApplicability.SAFE)


class ForLoopChecker(VisitorChecker):
    for_in_zip_without_mode: ForInZipWithoutModeRule

    def visit_For(self, node):  # noqa: N802 - robot visitor naming
        if node.flavor == "IN ZIP" and not node.mode:
            header = node.header
            separator = header.get_token(Token.FOR_SEPARATOR)
            self.report(
                self.for_in_zip_without_mode,
                node=header,
                col=separator.col_offset + 1,
                end_col=separator.end_col_offset + 1,
            )
        self.generic_visit(node)
