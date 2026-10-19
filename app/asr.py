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

from app.audio import Pcm16ChunkBuffer, pcm16le_to_samples, require_tone_chunk, validate_pcm16
from app.settings import TONE_PADDING_SAMPLES, Settings


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


class ToneStreamEngine:
    """Стриминг в `StreamingCTCPipeline.forward` чанками по 2400 сэмплов.

    Левый паддинг 2400 нулей добавляется один раз, как в `read_stream_audio`.
    Без пайплайна первый вызов бросает `ModelNotLoaded`, следующие ничего не делают.
    `from_hugging_face` этот класс не вызывает.
    """

    def __init__(self, pipeline: object | None = None) -> None:
        self._pipeline = pipeline
        self._state: object | None = None
        self._buffer = Pcm16ChunkBuffer()
        self._primed = False
        self._saw_audio = False
        self._missing_reported = False

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def push_pcm16(self, audio: bytes) -> tuple[TranscriptPhrase, ...]:
        if not self._require_pipeline():
            return ()
        if not audio:
            return ()
        samples = pcm16le_to_samples(audio)
        self._saw_audio = True
        primed: tuple[tuple[int, ...], ...] = ()
        if not self._primed:
            primed = self._buffer.extend((0,) * TONE_PADDING_SAMPLES)
            self._primed = True
        return self._consume(primed + self._buffer.extend(samples), is_last=False)

    def finish(self) -> tuple[TranscriptPhrase, ...]:
        """Добить хвост и вызвать `finalize`. Без звука — пусто, даже если весов нет."""

        if not self._saw_audio:
            return ()
        if not self._require_pipeline():
            return ()
        remainder = self._buffer.take_padded_remainder()
        phrases = list(self._consume((remainder,) if remainder else (), is_last=False))
        pipeline = self._pipeline
        final, _state = pipeline.finalize(self._state)  # type: ignore[attr-defined]
        phrases.extend(phrases_from_objects(final))
        self._state = None
        self._saw_audio = False
        self._primed = False
        return tuple(phrases)

    def _require_pipeline(self) -> bool:
        if self._pipeline is not None:
            return True
        if self._missing_reported:
            return False
        self._missing_reported = True
        raise ModelNotLoaded(
            "T-One не загружен. Веса не скачивались: CALL_CENTER_LOAD_WEIGHTS выключен "
            "или пакет voicekit-team/T-one не установлен."
        )

    def _consume(self, chunks: Sequence[Sequence[int]], *, is_last: bool) -> tuple[TranscriptPhrase, ...]:
        pipeline = self._pipeline
        if pipeline is None:
            return ()
        phrases: list[TranscriptPhrase] = []
        for chunk in chunks:
            new_phrases, self._state = pipeline.forward(  # type: ignore[attr-defined]
                chunk,
                self._state,
                is_last=is_last,
            )
            phrases.extend(phrases_from_objects(new_phrases))
        return tuple(phrases)


class NumpyChunkPipeline:
    """Переводит чанк-кортеж в int32 ndarray, которого ждёт настоящий T-One."""

    def __init__(self, pipeline: object) -> None:
        self._pipeline = pipeline

    def forward(self, audio_chunk: Sequence[int], state: object | None = None, *, is_last: bool = False):
        array = _as_int32_chunk(audio_chunk)
        return self._pipeline.forward(array, state, is_last=is_last)  # type: ignore[attr-defined]

    def finalize(self, state: object | None):
        return self._pipeline.finalize(state)  # type: ignore[attr-defined]


class ToneAsr:
    """Ленивый пайплайн. `load` ходит в Hugging Face только при флаге весов."""

    def __init__(self) -> None:
        self._pipeline: object | None = None

    @property
    def loaded(self) -> bool:
        return self._pipeline is not None

    def open_stream(self) -> ToneStreamEngine:
        """Движок стриминга. Без `load()` пайплайн внутри пустой, веса не качаются."""

        pipeline = NumpyChunkPipeline(self._pipeline) if self._pipeline is not None else None
        return ToneStreamEngine(pipeline)

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
