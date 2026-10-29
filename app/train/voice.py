"""Ход репетиции через голос. Модуль не импортирует tone, qwen_tts, pipecat и mlx_lm."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.train.rehearsal import Rehearsal


@dataclass(frozen=True)
class Heard:
    text: str


@dataclass(frozen=True)
class Spoken:
    text: str
    wav: bytes


class VoicePort(Protocol):
    def hear(self, pcm16_8k: bytes) -> Heard: ...

    def speak(self, text: str) -> Spoken: ...


def play_operator_audio(rehearsal: Rehearsal, port: VoicePort, pcm16_8k: bytes) -> dict[str, object]:
    """Распознать реплику оператора и синтезировать новые реплики клиента.

    Пустое распознавание всё равно передаётся в репетицию, но синтез не вызывается.
    """

    before = len(rehearsal.transcript)
    heard = port.hear(pcm16_8k)
    if not heard.text.strip():
        rehearsal.say("")
        return rehearsal.snapshot()
    rehearsal.say(heard.text)
    for turn in rehearsal.transcript[before:]:
        if turn.speaker == "client":
            port.speak(turn.text)
    return rehearsal.snapshot()
