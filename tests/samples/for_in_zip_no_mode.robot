*** Test Cases ***
Zip Without Mode
    FOR    ${a}    ${b}    IN ZIP    ${LIST_A}    ${LIST_B}
        Log    ${a} ${b}
    END
