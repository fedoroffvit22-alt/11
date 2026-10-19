"""Обёртка T-One. Веса не качаются, пока `Settings.load_weights` выключен.

Реальный контракт (voicekit-team/T-one @ 3c5b6c0):
`StreamingCTCPipeline.from_hugging_face`, `forward`, `forward_offline`, `finalize`.
Пакет PyPI `tone` — другой проект; перед загрузкой проверяем наличие класса.
"""

from __future__ import annotations

import importlib
from collections.abc import Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Protocol

from app.audio import require_tone_chunk, validate_pcm16
from app.settings import Settings


class ModelNotLoaded(RuntimeError):
    """Веса не загружены или загрузка запрещена настройкой."""


class TonePackageError(RuntimeError):
    """Установлен не тот пакет `tone` или пакет не установлен."""


class SupportsTonePhrase(Protocol):
    text: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class TranscriptPhrase:
    text: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class ToneProbe:
    status: str
    detail: str


def classify_tone_module(module: object) -> str:
    """`ok`, если модуль похож на T-One, иначе `wrong_package`."""

    pipeline = getattr(module, "StreamingCTCPipeline", None)
    decoder = getattr(module, "DecoderType", None)
    if pipeline is None or decoder is None:
        return "wrong_package"
    needed = ("from_hugging_face", "forward", "forward_offline", "finalize")
    if not all(callable(getattr(pipeline, name, None)) for name in needed):
        return "wrong_package"
    if not hasattr(decoder, "BEAM_SEARCH") or not hasattr(decoder, "GREEDY"):
        return "wrong_package"
    return "ok"


def probe_tone() -> ToneProbe:
    try:
        module = importlib.import_module("tone")
    except ImportError as exc:
        return ToneProbe("missing", f"Пакет T-One не установлен: {exc}")
    status = classify_tone_module(module)
    if status == "wrong_package":
        return ToneProbe(
            "wrong_package",
            "Импортируется `tone` без StreamingCTCPipeline. На PyPI это другой пакет. Ставьте git voicekit-team/T-one.",
        )
    version = getattr(module, "__version__", "неизвестна")
    return ToneProbe("ok", f"T-One импортирован, версия {version}. Веса не загружались.")


def phrases_from_objects(items: Sequence[SupportsTonePhrase]) -> tuple[TranscriptPhrase, ...]:
    phrases: list[TranscriptPhrase] = []
    for item in items:
        start = float(item.start_time)
        end = float(item.end_time)
        if end < start:
            raise ValueError(f"Конец фразы {end} раньше начала {start}.")
        phrases.append(TranscriptPhrase(text=str(item.text).strip(), start_time=start, end_time=end))
    return tuple(phrases)


class ToneAsr:
    """Ленивый пайплайн. `load` ходит в Hugging Face только при флаге весов."""

    def __init__(self) -> None:
        self._pipeline: object | None = None

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def load(self, settings: Settings) -> None:
        if not settings.load_weights:
            raise ModelNotLoaded(
                "Загрузка T-One выключена. Включите CALL_CENTER_LOAD_WEIGHTS=1, "
                "когда готовы скачать model.onnx с Hugging Face."
            )
        module = _import_tone_or_raise()
        decoder = module.DecoderType.GREEDY if settings.asr_decoder == "greedy" else module.DecoderType.BEAM_SEARCH
        self._pipeline = module.StreamingCTCPipeline.from_hugging_face(decoder_type=decoder)

    def transcribe_offline(self, samples: Sequence[int]) -> tuple[TranscriptPhrase, ...]:
        pipeline = self._require()
        array = _as_int32_vector(samples)
        return phrases_from_objects(pipeline.forward_offline(array))

    def transcribe_stream(self, chunks: Sequence[Sequence[int]]) -> tuple[TranscriptPhrase, ...]:
        pipeline = self._require()
        state = None
        collected: list[TranscriptPhrase] = []
        for chunk in chunks:
            new_phrases, state = pipeline.forward(_as_int32_chunk(chunk), state)
            collected.extend(phrases_from_objects(new_phrases))
        final_phrases, _state = pipeline.finalize(state)
        collected.extend(phrases_from_objects(final_phrases))
        return tuple(collected)

    def _require(self) -> _Pipeline:
        if self._pipeline is None:
            raise ModelNotLoaded("T-One не загружен. Вызовите load() при CALL_CENTER_LOAD_WEIGHTS=1.")
        return self._pipeline  # type: ignore[return-value]


class _Pipeline(Protocol):
    def forward_offline(self, audio: object) -> Sequence[SupportsTonePhrase]: ...

    def forward(
        self, audio_chunk: object, state: object | None = None, *, is_last: bool = False
    ) -> tuple[Sequence[SupportsTonePhrase], object]: ...

    def finalize(self, state: object | None) -> tuple[Sequence[SupportsTonePhrase], object]: ...


def _import_tone_or_raise() -> ModuleType:
    try:
        module = importlib.import_module("tone")
    except ImportError as exc:
        raise TonePackageError(
            "T-One не установлен. Не используйте pip install tone: на PyPI другой пакет. "
            "Ставьте git+https://github.com/voicekit-team/T-one.git"
        ) from exc
    if classify_tone_module(module) != "ok":
        raise TonePackageError(
            "Найден чужой пакет tone без StreamingCTCPipeline. Удалите его и поставьте voicekit-team/T-one."
        )
    return module


def _as_int32_vector(samples: Sequence[int]) -> object:
    validate_pcm16(samples)
    numpy = importlib.import_module("numpy")
    return numpy.asarray(tuple(samples), dtype=numpy.int32)


def _as_int32_chunk(samples: Sequence[int]) -> object:
    chunk = require_tone_chunk(samples)
    numpy = importlib.import_module("numpy")
    return numpy.asarray(chunk, dtype=numpy.int32)
