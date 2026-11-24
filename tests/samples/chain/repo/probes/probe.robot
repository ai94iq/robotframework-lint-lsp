*** Settings ***
Resource    ../resources/resources.resource


*** Variables ***
${CONTRACT}    C-100


*** Test Cases ***
Reads A Contract
    ${row}=    Get Contract    ${CONTRACT}
    Make Row
    Make Row
    Make Row


*** Keywords ***
Make Row
    No Operation
