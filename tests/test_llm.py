"""Локальная модель без Pipecat, весов и сети."""

import sys
from pathlib import Path

import pytest
from app.llm import (
    RUSSIAN_SYSTEM_PROMPT,
    ChatTurn,
    LlmBackendDisabled,
    StubLocalModel,
    build_local_model,
    load_selected_model,
    turns_from_messages,
    with_russian_prompt,
)
from app.settings import ABSENT_HF_LLM_ID, LOCAL_LLM_ID, Settings
from app.smoke import main as smoke_main


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


def test_selected_llm_id_is_the_mlx_4bit() -> None:
    assert LOCAL_LLM_ID == "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    assert ABSENT_HF_LLM_ID == "Qwen/Qwen3-4B-Instruct"
    settings = Settings.from_env({})
    assert settings.llm_model_id == LOCAL_LLM_ID
    assert settings.llm_backend == "off"
    for name in ("requirements.txt", "requirements-dev.txt"):
        for line in Path(name).read_text().splitlines():
            if line.strip().startswith("#"):
                continue
            assert "mlx" not in line.lower()


def test_explicit_llm_load_refuses_without_flag() -> None:
    with pytest.raises(LlmBackendDisabled, match="load_selected_model"):
        load_selected_model(Settings())
    assert "mlx_lm" not in sys.modules
    with pytest.raises(LlmBackendDisabled, match="Hugging Face нет"):
        load_selected_model(Settings(load_weights=True, llm_model_id=ABSENT_HF_LLM_ID))
    assert "mlx_lm" not in sys.modules


def test_smoke_does_not_load_selected_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("локальная Qwen загружена из смоука")

    monkeypatch.setenv("CALL_CENTER_LOAD_WEIGHTS", "1")
    monkeypatch.setattr("app.llm.load_selected_model", refuse)
    assert smoke_main() == 0
