from types import SimpleNamespace

from hypothesis import given, settings, strategies as st
from pygls.workspace import PositionCodec

from robotframework_lint import lsp
from robotframework_lint.lsp import Settings

PIECES = st.sampled_from(["*** Test Cases ***", "*** Variables ***", "*** Keywords ***", "*** Settings ***",
                          "Log    ${x}", "\tKeyword", "My Test", "${x}=    Set Variable    1", "    ", "\r\n", "\n", "\t"])
ROBOT_TEXT = st.lists(PIECES | st.text(max_size=12), max_size=12).map("\n".join) | st.text(max_size=80)


def _publish_one(source):
    sent = []
    doc = SimpleNamespace(source=source, version=1, lines=source.splitlines(keepends=True))
    ls = SimpleNamespace(workspace=SimpleNamespace(get_text_document=lambda u: doc, position_codec=PositionCodec()),
                         settings=Settings(), index=lsp.WorkspaceIndex(), scanned=set(), robotcode={},
                         settings_for=lambda uri: Settings(), window_log_message=lambda p: None,
                         text_document_publish_diagnostics=sent.append)
    lsp.RflintServer.publish(ls, "untitled:x.robot")
    return sent[0].diagnostics


@settings(max_examples=100, deadline=None)
@given(ROBOT_TEXT)
def test_publish_never_raises_and_messages_are_short(source):
    diagnostics = _publish_one(source)
    assert isinstance(diagnostics, list)
    assert all(len(d.message) <= 120 for d in diagnostics)
