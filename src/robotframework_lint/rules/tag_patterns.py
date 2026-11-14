"""Rules for tag patterns."""

import re

from robot.api import Token

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker

# Operator glued to non-lowercase text on both sides, as in XORY.
GLUED_OPERATOR = re.compile(r"(?<=[^\sa-z])(AND|OR|NOT)(?=[^\sa-z])")
# Keywords whose arguments are tag patterns.
PATTERN_KEYWORDS = {"removetags"}


def deprecated_form(pattern: str) -> str | None:
    if "&" in pattern:
        return "&"
    match = GLUED_OPERATOR.search(pattern)
    return match.group(1) if match else None


class DeprecatedTagPatternRule(Rule):
    """
    Tag pattern form deprecated in Robot Framework 7.5.

    The rf-7.5 release notes, section "Deprecated features", say:
    "Boolean operators used with tag patterns need to be separated from tags
    more clearly and usages like `XORY` are deprecated (`#5657`_). Operators
    can be surrounded with spaces like `X OR Y` or tags can be specified in
    lower case like `xORy`." and "Using `&` as a Boolean operator with tag
    patterns is deprecated and `AND` should be used instead (`#5661`_)."
    Checked: ``-tag`` removals in Test Tags, Keyword Tags, Force Tags,
    Default Tags and [Tags], and Remove Tags arguments. Source:
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst

    Incorrect code example:

        [Tags]    -smoke&slow
        Remove Tags    SMOKEORSLOW

    Correct code:

        [Tags]    -smoke AND slow
        Remove Tags    SMOKE OR SLOW
    """

    name = "deprecated-tag-pattern"
    rule_id = "RFL003"
    message = "'{operator}' tag pattern is deprecated since RF 7.5; use spaced AND/OR/NOT"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"


class TagPatternChecker(VisitorChecker):
    deprecated_tag_pattern: DeprecatedTagPatternRule

    def check_token(self, token, pattern):
        operator = deprecated_form(pattern)
        if operator:
            self.report(
                self.deprecated_tag_pattern,
                operator=operator,
                lineno=token.lineno,
                col=token.col_offset + 1,
                end_col=token.end_col_offset + 1,
            )

    def check_tag_removals(self, node):
        for token in node.get_tokens(Token.ARGUMENT):
            if token.value.startswith("-"):
                self.check_token(token, token.value[1:])

    visit_TestTags = visit_KeywordTags = visit_ForceTags = check_tag_removals  # noqa: N815
    visit_DefaultTags = visit_Tags = check_tag_removals  # noqa: N815

    def visit_KeywordCall(self, node):  # noqa: N802 - robot visitor naming
        name = (node.keyword or "").split(".")[-1].replace(" ", "").replace("_", "").lower()
        if name in PATTERN_KEYWORDS:
            for token in node.get_tokens(Token.ARGUMENT):
                self.check_token(token, token.value)
