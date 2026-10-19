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

from app.llm import RUSSIAN_SYSTEM_PROMPT
from app.settings import PIPELINE_AUDIO_OUT_SAMPLE_RATE, TONE_SAMPLE_RATE

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

# Порядок будущего полного дуплекса. Свои процессоры T-One и Qwen3-TTS живут в
# `app.pipecat_services` и подключаются, только если pipecat-ai импортируется.
# В пакете Pipecat готовых классов для T-One и Qwen3-TTS нет.
# Локальная LLM — свой `LocalLlmService`, не DashScope и не Ollama.
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
    """Собранные объекты конфигурации. Пайплайн не запускается и веса не грузит."""

    audio_in_sample_rate: int
    audio_out_sample_rate: int
    vad_stop_secs: float
    processor_count: int
    context_messages: int
    has_tone_stt: bool
    has_qwen_tts: bool
    has_local_llm: bool
    llm_backend: str
    interrupt_on_user_speech: bool
    weights_loaded: bool


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


def build_skeleton(settings: object | None = None) -> PipelineSkeleton | SymbolProbe:
    """Собрать PipelineParams, контекст и процессоры T-One / Qwen3-TTS.

    Возвращает `SymbolProbe`, если pipecat-ai не установлен. Микрофон не открывается.
    `settings` — `app.settings.Settings`. По умолчанию веса выключены, загрузчики не зовутся.
    """

    probe = probe_symbols(CORE_SYMBOLS)
    if probe.status != "ok":
        return probe

    # Отложенный импорт: модуль процессоров тянет pipecat на уровне файла.
    # Пока пакета нет, `import app.pipeline` и смоук должны оставаться рабочими.
    services = importlib.import_module("app.pipecat_services")
    settings_mod = importlib.import_module("app.settings")

    app_settings = settings if isinstance(settings, settings_mod.Settings) else settings_mod.Settings()
    pipeline_mod = importlib.import_module("pipecat.pipeline.pipeline")
    worker_mod = importlib.import_module("pipecat.pipeline.worker")
    vad_mod = importlib.import_module("pipecat.audio.vad.vad_analyzer")
    context_mod = importlib.import_module("pipecat.processors.aggregators.llm_context")
    pair_mod = importlib.import_module("pipecat.processors.aggregators.llm_response_universal")

    params = worker_mod.PipelineParams(
        audio_in_sample_rate=TONE_SAMPLE_RATE,
        audio_out_sample_rate=app_settings.audio_out_sample_rate or PIPELINE_AUDIO_OUT_SAMPLE_RATE,
    )
    vad_params = vad_mod.VADParams(stop_secs=0.2)
    # Явные стратегии: старт хода по VAD с перебиванием. Стоп — таймаут речи,
    # без LocalSmartTurnAnalyzerV3, который читает bundled ONNX.
    # SileroVADAnalyzer не создаём: его конструктор тоже грузит ONNX.
    turn_mod = importlib.import_module("pipecat.turns.user_turn_strategies")
    vad_start = importlib.import_module("pipecat.turns.user_start.vad_user_turn_start_strategy")
    speech_stop = importlib.import_module("pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy")
    strategies = turn_mod.UserTurnStrategies(
        start=[vad_start.VADUserTurnStartStrategy(enable_interruptions=True)],
        stop=[speech_stop.SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=vad_params.stop_secs)],
    )
    context = context_mod.LLMContext(messages=[{"role": "developer", "content": RUSSIAN_SYSTEM_PROMPT}])
    user, assistant = pair_mod.LLMContextAggregatorPair(
        context,
        user_params=pair_mod.LLMUserAggregatorParams(user_turn_strategies=strategies),
    )
    tone = services.ToneSttService(settings=app_settings)
    local_llm = services.LocalLlmService(settings=app_settings)
    qwen = services.Qwen3TtsService(settings=app_settings, output_sample_rate=params.audio_out_sample_rate)
    # Микрофон не открываем, DashScope и Ollama не подключаем, раннер не запускаем.
    pipeline = pipeline_mod.Pipeline([tone, user, local_llm, qwen, assistant])
    _worker = worker_mod.PipelineWorker(pipeline, params=params)
    return PipelineSkeleton(
        audio_in_sample_rate=params.audio_in_sample_rate,
        audio_out_sample_rate=params.audio_out_sample_rate,
        vad_stop_secs=vad_params.stop_secs,
        processor_count=len(pipeline.processors),
        context_messages=len(context.messages) if hasattr(context, "messages") else 1,
        has_tone_stt=True,
        has_qwen_tts=True,
        has_local_llm=True,
        llm_backend=app_settings.llm_backend,
        interrupt_on_user_speech=True,
        weights_loaded=tone.weights_loaded or qwen.weights_loaded or local_llm.weights_loaded,
    )
