*** Test Cases ***
Zip With Mode
    FOR    ${a}    ${b}    IN ZIP    ${LIST_A}    ${LIST_B}    mode=STRICT
        Log    ${a} ${b}
    END

Plain For
    FOR    ${a}    IN    @{LIST_A}
        Log    ${a}
    END
