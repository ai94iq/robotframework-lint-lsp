*** Settings ***
Library    Collections

*** Test Cases ***
Example
    ${items}    Create List    b    a
    Sort List    ${items}
    Sleep    1 second
    Log    time_=1 second
    My Sort    list_=${items}

*** Keywords ***
My Sort
    [Arguments]    ${list_}
    Log    ${list_}
