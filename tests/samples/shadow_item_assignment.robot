*** Variables ***
&{CONFIG}    a=1
@{ITEMS}    x    y

*** Test Cases ***
Item Assignment
    ${CONFIG}[a]=    Set Variable    2
    ${ITEMS}[0]=    Set Variable    z
    ${config.a}=    Set Variable    3
    Log    ${CONFIG}
