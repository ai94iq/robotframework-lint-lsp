*** Variables ***
${CONTRACT}    C-1


*** Test Cases ***
Reads A Contract
    ${row}=    Set Variable    x
    VAR    ${CONTRACT}    y    scope=SUITE
    Log    ${row}
