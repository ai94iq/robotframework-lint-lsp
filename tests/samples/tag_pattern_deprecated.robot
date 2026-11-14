*** Settings ***
Test Tags    smoke    -WIPANDSLOW

*** Test Cases ***
Example
    [Tags]    -smoke&slow
    Remove Tags    fooORbar
    Remove Tags    FOOORBAR
