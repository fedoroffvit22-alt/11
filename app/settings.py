"""Настройки из окружения. Секретов здесь нет: платные API не используем."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

TONE_GIT_REVISION = "3c5b6c015038173840e62cea99e10cdb1c759116"
TONE_SAMPLE_RATE = 8000
TONE_CHUNK_SAMPLES = 2400
TONE_PADDING_SAMPLES = 2400

TTS_MODEL_0_6B_CUSTOM = "Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice"
TTS_LANGUAGE_RUSSIAN = "Russian"
DEFAULT_TTS_SPEAKER = "Ryan"

ASR_DECODERS = ("greedy", "beam_search")
TTS_DEVICES = ("cpu", "cuda", "mps")

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


@dataclass(frozen=True)
class Settings:
    """Срез конфигурации, который умеет прочитать смоук без весов."""

    load_weights: bool = False
    asr_decoder: str = "beam_search"
    tts_model_id: str = TTS_MODEL_0_6B_CUSTOM
    tts_speaker: str = DEFAULT_TTS_SPEAKER
    tts_language: str = TTS_LANGUAGE_RUSSIAN
    tts_device: str = "cpu"
    tts_flash_attention: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        source = os.environ if env is None else env
        return cls(
            load_weights=_flag(source.get("CALL_CENTER_LOAD_WEIGHTS", "0"), "CALL_CENTER_LOAD_WEIGHTS"),
            asr_decoder=_choice(
                source.get("CALL_CENTER_ASR_DECODER", "beam_search"),
                ASR_DECODERS,
                "CALL_CENTER_ASR_DECODER",
            ),
            tts_model_id=source.get("CALL_CENTER_TTS_MODEL", TTS_MODEL_0_6B_CUSTOM).strip() or TTS_MODEL_0_6B_CUSTOM,
            tts_speaker=source.get("CALL_CENTER_TTS_SPEAKER", DEFAULT_TTS_SPEAKER).strip() or DEFAULT_TTS_SPEAKER,
            tts_language=source.get("CALL_CENTER_TTS_LANGUAGE", TTS_LANGUAGE_RUSSIAN).strip() or TTS_LANGUAGE_RUSSIAN,
            tts_device=_choice(
                source.get("CALL_CENTER_TTS_DEVICE", "cpu"),
                TTS_DEVICES,
                "CALL_CENTER_TTS_DEVICE",
            ),
            tts_flash_attention=_flag(
                source.get("CALL_CENTER_TTS_FLASH_ATTN", "0"),
                "CALL_CENTER_TTS_FLASH_ATTN",
            ),
        )


def _flag(raw: str, name: str) -> bool:
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ValueError(f"{name} должно быть 0 или 1, получено {raw!r}.")


def _choice(raw: str, allowed: tuple[str, ...], name: str) -> str:
    value = raw.strip().lower()
    if value not in allowed:
        options = ", ".join(allowed)
        raise ValueError(f"{name} должно быть одним из: {options}. Получено {raw!r}.")
    return value
