from hypothesis import HealthCheck, assume, given, settings, strategies as st

from robotframework_lint.autofix import edited_ranges, keep_edited_hunks

LINE = st.text(alphabet="abc ", max_size=4) | st.sampled_from(["${x}", "a ${x}"])
CASE = settings(max_examples=200, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@st.composite
def edits(draw):
    lines = draw(st.lists(LINE, min_size=1, max_size=8))
    a = draw(st.integers(0, len(lines) - 1))
    b = draw(st.integers(a + 1, len(lines)))
    changed = draw(st.sets(st.integers(0, len(lines) - 1)))
    original = "".join(line + "\n" for line in lines)
    block = "\n".join(lines[a:b]) + draw(st.sampled_from(["", "\n"]))
    fixed = "".join(line + ("Z" if i in changed else "") + "\n" for i, line in enumerate(lines))
    return original, fixed, block, a, b, changed


def _starts(text, block):
    at, found = text.find(block), []
    while at >= 0:
        found.append(text.count("\n", 0, at))
        at = text.find(block, at + 1)
    return found


@CASE
@given(edits())
def test_lines_outside_every_occurrence_are_unchanged(case):
    original, fixed, block, a, b, changed = case
    assume(block)
    ranges = edited_ranges(original, {"new_string": block})
    result = keep_edited_hunks(original, fixed, ranges).splitlines()
    before, after = original.splitlines(), fixed.splitlines()
    assert len(result) == len(before)
    inside = {k for s in _starts(original, block) for k in range(s, s + block.count("\n") + (not block.endswith("\n")))}
    for i, line in enumerate(result):
        assert line == (after[i] if i in inside else before[i])


@CASE
@given(edits())
def test_first_block_lines_take_fixed(case):
    original, fixed, block, a, b, changed = case
    assume(block)
    ranges = edited_ranges(original, {"new_string": block})
    result = keep_edited_hunks(original, fixed, ranges).splitlines()
    first = _starts(original, block)[0]
    span = range(first, first + block.count(chr(10)) + (not block.endswith(chr(10))))
    assert all(result[i] == fixed.splitlines()[i] for i in span if i in changed)
