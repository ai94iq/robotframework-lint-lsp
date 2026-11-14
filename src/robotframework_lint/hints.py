"""One-line fix hints for the findings agents most often left unfixed.

Robocop has no auto-fix for these, and agents without a hint spent extra
edit rounds guessing the modern form or left the finding in place.
"""

FIX_HINTS = {
    "DEPR05": "use VAR    ${name}    value    scope=TEST|SUITE|GLOBAL",
    "DEPR06": "use VAR    @{list}    a    b  or  VAR    &{dict}    k=v",
    "MISC09": "use inline IF: IF    cond    Keyword    ELSE    Keyword",
    "SPC03": "use exactly 2 empty lines between sections",
    "VAR02": "drop the assignment or use the variable",
    "VAR05": "pass the value as an argument or RETURN it",
    "VAR06": "pass the value as an argument or RETURN it",
    "VAR10": "spell the variable the same way everywhere",
    "MISC04": "use one assignment style in the file",
}
