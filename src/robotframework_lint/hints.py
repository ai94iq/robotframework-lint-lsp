"""One-line fix hints for the findings agents most often left unfixed.

Robocop has no auto-fix for these, and agents without a hint spent extra
edit rounds guessing the modern form or left the finding in place.
"""

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
    "MISC09": "use inline IF: IF    cond    Keyword    ELSE    Keyword",
    "SPC03": "use exactly 2 empty lines between sections",
    "VAR02": "drop the assignment or use the variable",
    "VAR05": "pass the value as an argument or RETURN it",
    "VAR06": "pass the value as an argument or RETURN it",
    "VAR10": "spell the variable the same way everywhere",
    "MISC04": "use one assignment style in the file",
}
