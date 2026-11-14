*** Variables ***
${GREETING}    hello


*** Keywords ***
Say Hello
    [Documentation]    Logs a greeting to the given name.
    ...    Second line is not shown on hover.
    [Arguments]    ${name}
    Log    ${GREETING} ${name}

Open Shop
    Say Hello    shop
