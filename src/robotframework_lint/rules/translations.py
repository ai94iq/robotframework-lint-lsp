"""Rules for localized section headers and settings."""

from robot.api import Token
from robot.conf.languages import Language

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker

MARKER_TYPES = frozenset(Token.HEADER_TOKENS) | frozenset(Token.SETTING_TOKENS)


def normalize(marker: str) -> str:
    return " ".join(marker.strip("*[] ").split()).title()


def deprecated_markers() -> dict[str, tuple[str, str]]:
    """Map old term to (new term, version) from Robot Framework's own languages."""
    found = {}
    for language in Language.__subclasses__():
        for old, (new, version) in language.deprecations.items():
            found[normalize(old)] = (new, version or "")
    return found


DEPRECATED = deprecated_markers()


class DeprecatedTranslationRule(Rule):
    """
    Translation deprecated in Robot Framework 7.5.

    The rf-7.5 release notes, section "Deprecated features", say:
    "French "Test Cases" translation "Unites de test" has been deprecated in
    favor of "Cas de test" (`#5510`_)." and "Finnish "Tags" translation
    "Tagit" has been deprecated and "Tunnisteet" should be used instead
    (`#5726`_)." (the French term carries an accented e). Terms come from
    Robot Framework's own ``Language.deprecations``. A term is only reported
    when Robot Framework parsed it as a header or setting, so only files
    whose language is set to French or Finnish. Source:
    https://github.com/robotframework/robotframework/blob/master/doc/releasenotes/rf-7.5.rst

    Incorrect code example (``language: fi``):

        [Tagit]    smoke

    Correct code:

        [Tunnisteet]    smoke
    """

    name = "deprecated-translation"
    rule_id = "RFL004"
    message = "'{old}' is deprecated since RF {version}; use '{new}'"
    severity = RuleSeverity.WARNING
    added_in_version = "0.1.0"


class TranslationChecker(VisitorChecker):
    deprecated_translation: DeprecatedTranslationRule

    def visit_Statement(self, node):  # noqa: N802 - robot visitor naming
        token = node.data_tokens[0] if node.data_tokens else None
        if token is None or token.type not in MARKER_TYPES:
            return
        old = normalize(token.value)
        if old in DEPRECATED:
            new, version = DEPRECATED[old]
            self.report(
                self.deprecated_translation,
                old=" ".join(token.value.strip("*[] ").split()),
                new=new,
                version=version,
                lineno=token.lineno,
                col=token.col_offset + 1,
                end_col=token.end_col_offset + 1,
            )
