"""Rules for library imports."""

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker

RF_75_NOTES = (
    "https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst"
)

# Standard libraries deprecated in RF 7.5, mapped to the replacement named there.
DEPRECATED_LIBRARIES = {"Telnet": "TelnetLibrary"}


class DeprecatedStandardLibraryRule(Rule):
    """
    Import of a standard library deprecated in Robot Framework 7.5.

    The rf-7.5 release notes, section "Deprecated features", say: "The Telnet
    library has been deprecated (#5786). The new external TelnetLibrary
    should be used instead." Telnet is the only standard library that section
    deprecates. Source: rf-7.5 release notes,
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst

    Incorrect code example:

        *** Settings ***
        Library    Telnet

    Correct code:

        *** Settings ***
        Library    TelnetLibrary
    """

    name = "deprecated-standard-library"
    rule_id = "RFL002"
    message = "{name} is deprecated since RF 7.5; use {replacement}"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"


class ImportChecker(VisitorChecker):
    deprecated_standard_library: DeprecatedStandardLibraryRule

    def visit_LibraryImport(self, node):  # noqa: N802 - robot visitor naming
        replacement = DEPRECATED_LIBRARIES.get(node.name)
        if replacement:
            token = node.get_token("NAME")
            self.report(
                self.deprecated_standard_library,
                name=node.name,
                replacement=replacement,
                node=node,
                col=token.col_offset + 1,
                end_col=token.end_col_offset + 1,
            )
