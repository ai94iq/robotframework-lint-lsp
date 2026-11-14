"""Rules for keyword call arguments."""

import inspect

from robot.libraries.BuiltIn import BuiltIn
from robot.libraries.Collections import Collections
from robot.utils import normalize

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker

DEPRECATED_NAMES = ("list_", "time_")


def keywords_with_deprecated_args() -> dict[str, frozenset[str]]:
    """Map normalized keyword name to its deprecated argument names, read from RF."""
    found = {}
    for library in (BuiltIn, Collections):
        for attr, method in inspect.getmembers(library, inspect.isfunction):
            if attr.startswith("_"):
                continue
            params = set(inspect.signature(method).parameters) & set(DEPRECATED_NAMES)
            if not params:
                continue
            frozen = frozenset(params)
            found[normalize(attr, ignore="_")] = frozen
            found[normalize(f"{library.__name__}.{attr}", ignore="_")] = frozen
    return found


KEYWORDS = keywords_with_deprecated_args()


class DeprecatedArgumentNameRule(Rule):
    """
    Deprecated argument name in a Collections or BuiltIn keyword call.

    The rf-7.5 release notes, section "Deprecated features", say:
    "`list_` argument used in Collections and `time_` argument used in Builtin
    have been deprecated (`#5763`_). They will be renamed to `list` and `time`,
    respectively, in Robot Framework 8.0. This only affects usages like
    `time_=1 second`, not usages where values are passed positionally like
    `1 second`." Keyword signatures come from Robot Framework's own library
    classes. Source:
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst

    Incorrect code example:

        Sleep    time_=1 second

    Correct code:

        Sleep    1 second
    """

    name = "deprecated-argument-name"
    rule_id = "RFL006"
    message = "'{arg}' is deprecated since RF 7.5; pass it positionally"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"


class ArgumentNameChecker(VisitorChecker):
    deprecated_argument_name: DeprecatedArgumentNameRule

    def visit_KeywordCall(self, node):  # noqa: N802 - robot visitor naming
        names = KEYWORDS.get(normalize(node.keyword or "", ignore="_"))
        if not names:
            return
        for token in node.get_tokens("ARGUMENT"):
            arg = token.value.split("=", 1)[0]
            if "=" in token.value and arg in names:
                self.report(
                    self.deprecated_argument_name,
                    arg=arg,
                    lineno=token.lineno,
                    col=token.col_offset + 1,
                    end_col=token.end_col_offset + 1,
                )
