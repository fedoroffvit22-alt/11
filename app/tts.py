"""Обёртка Qwen3-TTS. `synthesize` не подставляет тишину, если модели нет.

Сверено с qwen-tts 0.1.1 / QwenLM/Qwen3-TTS:
`Qwen3TTSModel.from_pretrained` и `generate_custom_voice`.
Класса `TTSModel` и идентификатора `qwen_tts:base_0.6b` в пакете нет.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from app.settings import TTS_MODEL_0_6B_CUSTOM, Settings

CUSTOM_VOICE_SPEAKERS = (
    "Vivian",
    "Serena",
    "Uncle_Fu",
    "Dylan",
    "Eric",
    "Ryan",
    "Aiden",
    "Ono_Anna",
    "Sohee",
)

CUSTOM_VOICE_LANGUAGES = (
    "Chinese",
    "English",
    "Japanese",
    "Korean",
    "German",
    "French",
    "Russian",
    "Portuguese",
    "Spanish",
    "Italian",
    "Auto",
)


class ModelNotLoaded(RuntimeError):
    """Веса Qwen3-TTS не загружены или загрузка запрещена."""


class TtsPackageError(RuntimeError):
    """Пакет qwen-tts не установлен или в нём нет Qwen3TTSModel."""


class TtsRequestError(ValueError):
    """Текст, диктор или язык не подходят под контракт 0.6B CustomVoice."""


@dataclass(frozen=True)
class SynthesisRequest:
    text: str
    language: str = "Russian"
    speaker: str = "Ryan"
    model_id: str = TTS_MODEL_0_6B_CUSTOM
    instruct: str | None = None


@dataclass(frozen=True)
class SynthesisResult:
    sample_rate: int
    samples: tuple[float, ...]


@dataclass(frozen=True)
class TtsProbe:
    status: str
    detail: str


def validate_request(request: SynthesisRequest) -> None:
    text = request.text.strip()
    if not text:
        raise TtsRequestError("Текст для синтеза пустой.")
    if request.speaker not in CUSTOM_VOICE_SPEAKERS:
        names = ", ".join(CUSTOM_VOICE_SPEAKERS)
        raise TtsRequestError(f"Диктор {request.speaker!r} не из списка CustomVoice: {names}.")
    if request.language not in CUSTOM_VOICE_LANGUAGES:
        names = ", ".join(CUSTOM_VOICE_LANGUAGES)
        raise TtsRequestError(f"Язык {request.language!r} не из списка Qwen3-TTS: {names}.")
    if request.instruct and request.model_id == TTS_MODEL_0_6B_CUSTOM:
        raise TtsRequestError(
            "Qwen3-TTS-12Hz-0.6B-CustomVoice не поддерживает instruction control. "
            "Уберите instruct или смените модель на 1.7B CustomVoice."
        )


def probe_tts() -> TtsProbe:
    try:
        module = importlib.import_module("qwen_tts")
    except ImportError as exc:
        return TtsProbe("missing", f"qwen-tts не установлен: {exc}")
    model_cls = getattr(module, "Qwen3TTSModel", None)
    if model_cls is None or not callable(getattr(model_cls, "from_pretrained", None)):
        return TtsProbe("wrong_package", "В qwen_tts нет Qwen3TTSModel.from_pretrained.")
    if not callable(getattr(model_cls, "generate_custom_voice", None)):
        return TtsProbe("wrong_package", "У Qwen3TTSModel нет generate_custom_voice.")
    return TtsProbe("ok", "qwen-tts импортирован. Веса не загружались.")


class Qwen3Speech:
    def __init__(self) -> None:
        self._model: object | None = None
        self._model_id: str | None = None

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def load(self, settings: Settings) -> None:
        if not settings.load_weights:
            raise ModelNotLoaded(
                "Загрузка Qwen3-TTS выключена. Включите CALL_CENTER_LOAD_WEIGHTS=1, "
                "когда готовы скачать чекпоинт с Hugging Face."
            )
        module = _import_qwen_or_raise()
        torch = importlib.import_module("torch")
        kwargs = _pretrained_kwargs(torch, settings.tts_device, settings.tts_flash_attention)
        self._model = module.Qwen3TTSModel.from_pretrained(settings.tts_model_id, **kwargs)
        self._model_id = settings.tts_model_id

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        validate_request(request)
        if self._model is None:
            raise ModelNotLoaded("Qwen3-TTS не загружен. synthesize() не возвращает поддельную волну.")
        if self._model_id is not None and request.model_id != self._model_id:
            raise TtsRequestError(f"Загружена модель {self._model_id}, а запрос указывает {request.model_id}.")
        wavs, sample_rate = self._model.generate_custom_voice(  # type: ignore[attr-defined]
            text=request.text.strip(),
            language=request.language,
            speaker=request.speaker,
        )
        if not wavs:
            raise RuntimeError("Qwen3-TTS вернул пустой список волн.")
        first = wavs[0]
        samples = tuple(float(sample) for sample in first)
        if not samples:
            raise RuntimeError("Qwen3-TTS вернул волну нулевой длины.")
        return SynthesisResult(sample_rate=int(sample_rate), samples=samples)


def _import_qwen_or_raise() -> object:
    try:
        module = importlib.import_module("qwen_tts")
    except ImportError as exc:
        raise TtsPackageError("Пакет qwen-tts не установлен.") from exc
    if getattr(module, "Qwen3TTSModel", None) is None:
        raise TtsPackageError("В пакете qwen_tts нет класса Qwen3TTSModel.")
    return module


def _pretrained_kwargs(torch: object, device: str, flash_attention: bool) -> dict[str, object]:
    """kwargs для from_pretrained. Официальный пример — CUDA; CPU/MPS здесь не гонялись."""

    if device == "cpu":
        dtype = torch.float32  # type: ignore[attr-defined]
    elif device.startswith("cuda"):
        dtype = torch.bfloat16  # type: ignore[attr-defined]
    elif device == "mps":
        dtype = torch.float32  # type: ignore[attr-defined]
    else:
        raise TtsRequestError(f"Неизвестное устройство TTS: {device}.")
    kwargs: dict[str, object] = {"device_map": device, "dtype": dtype}
    if flash_attention:
        if not device.startswith("cuda"):
            raise TtsRequestError("flash_attention_2 в официальном примере задаётся только для CUDA.")
        kwargs["attn_implementation"] = "flash_attention_2"
    return kwargs
