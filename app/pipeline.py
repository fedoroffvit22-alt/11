"""Каркас Pipecat 1.13.0. Символы сверены с тегом v1.13.0.

Смоук импортирует их только если пакет установлен, и не открывает микрофон:
`LocalAudioTransport` при импорте требует PyAudio, а конструктор открывает устройство.
`SileroVADAnalyzer()` сразу грузит bundled ONNX — в каркасе создаём только `VADParams`.
`WorkerRunner()` без запущенного event loop зовёт `get_running_loop()`, поэтому
раннер здесь не создаётся.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass

from app.settings import TONE_SAMPLE_RATE

# Пути сверены по исходникам тега v1.13.0, не по DSL из спецификации.
CORE_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("Pipeline", "pipecat.pipeline.pipeline"),
    ("PipelineWorker", "pipecat.pipeline.worker"),
    ("PipelineParams", "pipecat.pipeline.worker"),
    ("WorkerRunner", "pipecat.workers.runner"),
    ("SileroVADAnalyzer", "pipecat.audio.vad.silero"),
    ("VADParams", "pipecat.audio.vad.vad_analyzer"),
    ("LLMContext", "pipecat.processors.aggregators.llm_context"),
    ("LLMContextAggregatorPair", "pipecat.processors.aggregators.llm_response_universal"),
    ("LLMUserAggregatorParams", "pipecat.processors.aggregators.llm_response_universal"),
)

LOCAL_AUDIO_SYMBOLS: tuple[tuple[str, str], ...] = (
    ("LocalAudioTransport", "pipecat.transports.local.audio"),
    ("LocalAudioTransportParams", "pipecat.transports.local.audio"),
)

# Порядок процессоров будущего полного дуплекса. Это план, не исполняемый бот:
# своих STT/TTS-сервисов Pipecat для T-One и Qwen3-TTS в пакете нет.
FULL_DUPLEX_SLOTS: tuple[str, ...] = (
    "transport.input",
    "tone_asr",
    "user_aggregator",
    "local_qwen_llm",
    "qwen3_tts",
    "transport.output",
    "assistant_aggregator",
)


@dataclass(frozen=True)
class SymbolProbe:
    status: str
    detail: str
    found: tuple[str, ...] = ()


@dataclass(frozen=True)
class PipelineSkeleton:
    """Собранные объекты конфигурации. Пайплайн не запускается."""

    audio_in_sample_rate: int
    audio_out_sample_rate: int
    vad_stop_secs: float
    processor_count: int
    context_messages: int


def probe_symbols(symbols: tuple[tuple[str, str], ...]) -> SymbolProbe:
    found: list[str] = []
    missing: list[str] = []
    loaded: dict[str, object] = {}
    failed: dict[str, str] = {}
    for name, module_name in symbols:
        if module_name not in loaded and module_name not in failed:
            try:
                loaded[module_name] = importlib.import_module(module_name)
            except ImportError as exc:
                failed[module_name] = str(exc)
        if module_name in failed:
            missing.append(f"{module_name}.{name}: {failed[module_name]}")
            continue
        obj = getattr(loaded[module_name], name, None)
        if obj is None:
            missing.append(f"{module_name} не содержит {name}")
            continue
        found.append(name)
    if missing and not found:
        return SymbolProbe("missing", missing[0], ())
    if missing:
        return SymbolProbe("partial", "; ".join(missing), tuple(found))
    return SymbolProbe("ok", "символы импортированы", tuple(found))


def build_skeleton() -> PipelineSkeleton | SymbolProbe:
    """Собрать реальные PipelineParams, VADParams, LLMContext и короткий Pipeline.

    Возвращает `SymbolProbe`, если pipecat-ai не установлен. Микрофон не открывается.
    """

    probe = probe_symbols(CORE_SYMBOLS)
    if probe.status != "ok":
        return probe

    pipeline_mod = importlib.import_module("pipecat.pipeline.pipeline")
    worker_mod = importlib.import_module("pipecat.pipeline.worker")
    vad_mod = importlib.import_module("pipecat.audio.vad.vad_analyzer")
    context_mod = importlib.import_module("pipecat.processors.aggregators.llm_context")
    pair_mod = importlib.import_module("pipecat.processors.aggregators.llm_response_universal")

    params = worker_mod.PipelineParams(
        audio_in_sample_rate=TONE_SAMPLE_RATE,
        audio_out_sample_rate=24000,
    )
    vad_params = vad_mod.VADParams(stop_secs=0.2)
    context = context_mod.LLMContext(
        messages=[{"role": "developer", "content": "Отвечай по-русски, коротко, как оператор."}]
    )
    user, assistant = pair_mod.LLMContextAggregatorPair(
        context,
        user_params=pair_mod.LLMUserAggregatorParams(),
    )
    pipeline = pipeline_mod.Pipeline([user, assistant])
    _worker = worker_mod.PipelineWorker(pipeline, params=params)
    return PipelineSkeleton(
        audio_in_sample_rate=params.audio_in_sample_rate,
        audio_out_sample_rate=params.audio_out_sample_rate,
        vad_stop_secs=vad_params.stop_secs,
        processor_count=len(pipeline.processors),
        context_messages=len(context.messages) if hasattr(context, "messages") else 1,
    )
