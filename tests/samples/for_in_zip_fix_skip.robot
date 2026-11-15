*** Test Cases ***
Zip With Continuation
    FOR    ${a}    ${b}    IN ZIP    ${LIST_A}
    ...    ${LIST_B}
        Log    ${a} ${b}
    END

Zip With Comment
    FOR    ${a}    ${b}    IN ZIP    ${LIST_A}    ${LIST_B}    # pairs
        Log    ${a} ${b}
    END
