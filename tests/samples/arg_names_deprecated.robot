*** Settings ***
Library    Collections

*** Test Cases ***
Example
    ${items}    Create List    b    a
    Sort List    list_=${items}
    Collections.Reverse List    list_=${items}
    Sleep    time_=1 second
    BuiltIn.Sleep    time_=1s    reason=wait
