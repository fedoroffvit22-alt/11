"""Локальная языковая модель без облака и без весов в смоуке.

В Pipecat 1.13 нет LLM, которая работает в процессе без API-ключа и без демона.
`QwenLLMService` ходит в DashScope. `OLLamaLLMService` ждёт запущенный сервер Ollama.
Поэтому здесь свой интерфейс: русский системный промпт и потоковая выдача текста.
Бэкенд `off` ничего не генерирует. `stub` — тестовая заглушка, не Qwen ~4B.

Выбранный чекпоинт — `mlx-community/Qwen3-4B-Instruct-2507-4bit`.
`load_selected_model` — единственный вход, который может импортировать `mlx_lm`.
Смоук и pytest его не вызывают. `mlx-lm` нет в зависимостях по умолчанию:
на Mac он ломал `transformers`, нужные `qwen-tts`.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from app.settings import ABSENT_HF_LLM_ID, LOCAL_LLM_ID, Settings

RUSSIAN_SYSTEM_PROMPT = (
    "Отвечай по-русски, коротко, как оператор колл-центра. "
    "Не выдумывай факты о клиенте и не обещай того, чего нет в разговоре."
)

_INSTRUCTION_ROLES = frozenset({"system", "developer"})


class LlmBackendDisabled(RuntimeError):
    """Локальная модель не включена. Веса не скачивались."""


@dataclass(frozen=True)
class ChatTurn:
    role: str
    text: str


def turns_from_messages(messages: Sequence[object]) -> tuple[ChatTurn, ...]:
    """Текстовые реплики из `LLMContext`. Вложения и чужие объекты пропускаются."""

    turns: list[ChatTurn] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        turns.append(ChatTurn(role=role, text=text))
    return tuple(turns)


def with_russian_prompt(turns: Sequence[ChatTurn]) -> tuple[ChatTurn, ...]:
    """Добавить системный промпт, если в истории его ещё нет."""

    if any(turn.role in _INSTRUCTION_ROLES for turn in turns):
        return tuple(turns)
    return (ChatTurn(role="developer", text=RUSSIAN_SYSTEM_PROMPT),) + tuple(turns)


class DisabledLocalModel:
    """Бэкенд выключен. Поток не начинается и тишину не изображает."""

    def stream(self, turns: Sequence[ChatTurn]) -> Iterator[str]:
        raise LlmBackendDisabled("Локальная модель выключена (CALL_CENTER_LLM_BACKEND=off). Веса Qwen не скачивались.")


class StubLocalModel:
    """Короткие русские куски текста. Модель не загружает."""

    def stream(self, turns: Sequence[ChatTurn]) -> Iterator[str]:
        prepared = with_russian_prompt(turns)
        user_text = ""
        for turn in reversed(prepared):
            if turn.role == "user":
                user_text = turn.text
                break
        reply = f"Понял: {user_text}." if user_text else "Слушаю."
        words = reply.split(" ")
        for index, word in enumerate(words):
            if index == len(words) - 1:
                yield word
            else:
                yield word + " "


def build_local_model(backend: str) -> DisabledLocalModel | StubLocalModel:
    """`off` и `stub` не ходят в сеть и не вызывают `load_selected_model`."""

    if backend == "off":
        return DisabledLocalModel()
    if backend == "stub":
        return StubLocalModel()
    raise RuntimeError(
        f"Бэкенд {backend!r} не подключён. В Pipecat 1.13 нет локальной LLM без ключа и без демона. "
        "Ollama требует запущенный сервер, QwenLLMService — это DashScope."
    )


def load_selected_model(settings: Settings) -> object:
    """Явная загрузка выбранной Qwen. Смоук сюда не заходит и DashScope не вызывает.

    Импорт `mlx_lm` стоит внутри и выполняется только после флага весов.
    Пакет в `requirements.txt` не добавлен.
    """

    if not settings.load_weights:
        raise LlmBackendDisabled(
            "Загрузка локальной Qwen выключена. Нужны CALL_CENTER_LOAD_WEIGHTS=1 и явный вызов "
            "load_selected_model. Смоук веса не качает."
        )
    if settings.llm_model_id == ABSENT_HF_LLM_ID:
        raise LlmBackendDisabled(f"{ABSENT_HF_LLM_ID} на Hugging Face нет. Выбран {LOCAL_LLM_ID}.")
    module = importlib.import_module("mlx_lm")
    load = getattr(module, "load", None)
    if not callable(load):
        raise LlmBackendDisabled("В пакете mlx_lm нет функции load().")
    return load(settings.llm_model_id)
