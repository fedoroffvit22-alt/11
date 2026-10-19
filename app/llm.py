"""Локальная языковая модель без облака и без весов.

В Pipecat 1.13 нет LLM, которая работает в процессе без API-ключа и без демона.
`QwenLLMService` ходит в DashScope. `OLLamaLLMService` ждёт запущенный сервер Ollama.
Поэтому здесь свой интерфейс: русский системный промпт и потоковая выдача текста.
Бэкенд `off` ничего не генерирует. `stub` — тестовая заглушка, не Qwen ~4B.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

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
    """`off` и `stub` не ходят в сеть и не вызывают `from_pretrained`."""

    if backend == "off":
        return DisabledLocalModel()
    if backend == "stub":
        return StubLocalModel()
    raise RuntimeError(
        f"Бэкенд {backend!r} не подключён. В Pipecat 1.13 нет локальной LLM без ключа и без демона. "
        "Ollama требует запущенный сервер, QwenLLMService — это DashScope."
    )
