"""Rules for variable names and scopes."""

from robocop.linter.rules import Rule, RuleSeverity, VisitorChecker
from robot.api import Token
from robot.utils import normalize
from robot.variables import search_variable


def _variable_key(name: str) -> str:
    return normalize(search_variable(name.rstrip("= ")).base or "", ignore="_")


class LocalShadowsSuiteVariableRule(Rule):
    """
    A local assignment in a test or keyword whose name equals a suite variable.

    The Robot Framework User Guide, section "Using variables", says: "Robot
    Framework variables, similarly as keywords, are case-insensitive, and also
    spaces and underscores are ignored." Section "Variables set during test
    execution" says such variables "always override possible existing
    variables in the scope where they are set." So ``${contract}=`` in a test
    hides ``${CONTRACT}`` from the Variables section for the rest of the test,
    and every later ``${CONTRACT}`` reads the local value.
    Source: User Guide, Variables,
    https://github.com/robotframework/robotframework/blob/master/doc/userguide/src/CreatingTestData/Variables.rst

    Incorrect code example:

        *** Variables ***
        ${CONTRACT}    C-1

        *** Test Cases ***
        Reads A Contract
            ${contract}=    Get Contract Row
            Send Contract    ${CONTRACT}

    Correct code:

        *** Test Cases ***
        Reads A Contract
            ${contract_row}=    Get Contract Row
            Send Contract    ${CONTRACT}
    """

    name = "local-shadows-suite-variable"
    rule_id = "RFL007"
    message = "{local} hides suite variable {suite} (line {line}); RF names ignore case, _ and spaces"
    severity = RuleSeverity.ERROR
    added_in_version = "1.2.0"


class ShadowChecker(VisitorChecker):
    local_shadows_suite_variable: LocalShadowsSuiteVariableRule

    def visit_File(self, node):  # noqa: N802 - robot visitor naming
        self.suite_variables = {}
        super().generic_visit(node)

    def visit_Variable(self, node):  # noqa: N802 - robot visitor naming
        if node.name:
            self.suite_variables.setdefault(_variable_key(node.name), (node.name, node.lineno))

    def visit_KeywordCall(self, node):  # noqa: N802 - robot visitor naming
        for token in node.get_tokens(Token.ASSIGN):
            self._check(token)

    def visit_Var(self, node):  # noqa: N802 - robot visitor naming
        if (node.scope or "LOCAL").upper() == "LOCAL":
            self._check(node.get_token(Token.VARIABLE))

    def _check(self, token):
        suite = self.suite_variables.get(_variable_key(token.value))
        if suite is None:
            return
        local = token.value.rstrip("= ")
        self.report(self.local_shadows_suite_variable, local=local, suite=suite[0], line=suite[1],
                    lineno=token.lineno, col=token.col_offset + 1, end_col=token.col_offset + 1 + len(local))
