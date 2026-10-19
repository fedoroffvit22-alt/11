"""Локальная модель без Pipecat, весов и сети."""

import pytest
from app.llm import (
    RUSSIAN_SYSTEM_PROMPT,
    ChatTurn,
    LlmBackendDisabled,
    StubLocalModel,
    build_local_model,
    turns_from_messages,
    with_russian_prompt,
)


def test_turns_keep_text_and_drop_attachments() -> None:
    turns = turns_from_messages(
        [
            {"role": "developer", "content": "  системный  "},
            {"role": "user", "content": [{"type": "image"}]},
            {"role": "user", "content": "Алло"},
            "не словарь",
        ]
    )
    assert turns == (
        ChatTurn("developer", "системный"),
        ChatTurn("user", "Алло"),
    )


def test_russian_prompt_is_added_once() -> None:
    bare = with_russian_prompt((ChatTurn("user", "Алло"),))
    assert bare[0].role == "developer"
    assert "по-русски" in bare[0].text
    assert bare[0].text == RUSSIAN_SYSTEM_PROMPT
    again = with_russian_prompt(bare)
    assert len(again) == len(bare)


def test_stub_streams_words_without_weights() -> None:
    pieces = list(StubLocalModel().stream((ChatTurn("user", "нужен оператор"),)))
    assert len(pieces) > 1
    assert "".join(pieces) == "Понял: нужен оператор."


def test_disabled_backend_does_not_invent_a_reply() -> None:
    model = build_local_model("off")
    with pytest.raises(LlmBackendDisabled, match="не скачивались"):
        model.stream(())


def test_unknown_backend_is_refused() -> None:
    with pytest.raises(RuntimeError, match="DashScope"):
        build_local_model("ollama")
