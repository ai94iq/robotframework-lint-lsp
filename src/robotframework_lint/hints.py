"""Fix commands, one-line fix hints and short messages for the findings agents most often left unfixed.

FIX_COMMANDS fixes a rule in one command. FIX_HINTS covers rules robocop cannot fix: agents
without a hint spent extra edit rounds guessing the modern form or left the finding in place.
"""

import re

# One shell command fixes every finding of the rule in the file (checked on robocop 9.4.0).
FIX_COMMANDS = {
    "DEPR05": "robocop format --select ReplaceWithVAR <file>",
    "DEPR06": "robocop format --select ReplaceWithVAR <file>",
    **{rule: f"robocop check --fix --select {rule} <file>"
       for rule in ("DEPR03", "DEPR04", "DEPR07", "DEPR08", "DEPR09", "DEPR10", "DEPR11",
                    "MISC04", "MISC09", "VAR01")},
    "RFL001": "robocop check --fix --custom-rules robotframework_lint --select RFL001 <file>",
}

FIX_HINTS = {
    "SPC03": "use exactly 2 empty lines between sections",
    "VAR02": "drop the assignment or use the variable",
    "VAR05": "pass the value as an argument or RETURN it",
    "VAR06": "pass the value as an argument or RETURN it",
}

# Robocop messages that lose the part the agent needs when cut at the line cap.
SHORT_MESSAGES = {
    "VAR10": (re.compile(r"Variable '(.+)' has inconsistent naming\. First used as '(.+)'"),
              r"\1 = \2 (first use): one variable, spell it one way"),
}


def short_message(rule_id: str, message: str) -> str:
    pattern, template = SHORT_MESSAGES.get(rule_id, (None, ""))
    return pattern.sub(template, message) if pattern else message
