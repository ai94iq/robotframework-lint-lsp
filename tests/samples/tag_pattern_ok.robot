*** Settings ***
Test Tags    smoke    -wip AND slow

*** Test Cases ***
Example
    [Tags]    COLOR    ORANGE    -xORy
    Remove Tags    foo OR bar
    Log    a&b
