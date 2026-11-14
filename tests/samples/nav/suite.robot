*** Settings ***
Resource    common.resource
Test Setup    Open Shop


*** Test Cases ***
Greets A User
    say_hello    user
