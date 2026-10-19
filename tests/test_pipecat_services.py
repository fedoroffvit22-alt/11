"""Контракт процессоров Pipecat. Модели не создаются, from_pretrained не зовётся."""

import asyncio
import sys
from collections.abc import AsyncIterator

import pytest
from app.asr import ModelNotLoaded, TranscriptPhrase
from app.llm import RUSSIAN_SYSTEM_PROMPT, ChatTurn, LlmBackendDisabled
from app.pipeline import PipelineSkeleton, SymbolProbe, build_skeleton
from app.settings import DEFAULT_TTS_REF_TEXT, TTS_MODEL_0_6B_BASE, Settings
from app.smoke import main
from app.tts import SynthesisRequest, SynthesisResult

pytest.importorskip("pipecat")

from app.pipecat_services import LocalLlmService, Qwen3TtsService, ToneSttService  # noqa: E402
from pipecat.clocks.system_clock import SystemClock  # noqa: E402
from pipecat.frames.frames import (  # noqa: E402
    EndFrame,
    ErrorFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    LLMTextFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext  # noqa: E402
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor, FrameProcessorSetup  # noqa: E402
from pipecat.services.llm_service import LLMService  # noqa: E402
from pipecat.services.stt_service import STTService  # noqa: E402
from pipecat.services.tts_service import TTSService  # noqa: E402
from pipecat.transcriptions.language import Language  # noqa: E402
from pipecat.turns.types import ProcessFrameResult  # noqa: E402
from pipecat.turns.user_start.vad_user_turn_start_strategy import VADUserTurnStartStrategy  # noqa: E402
from pipecat.utils.asyncio.task_manager import TaskManager  # noqa: E402


class _Engine:
    def __init__(self, *, loaded: bool, phrases: tuple[TranscriptPhrase, ...] = ()) -> None:
        self.loaded = loaded
        self._phrases = phrases
        self.audio: list[bytes] = []
        self.finished = 0

    def push_pcm16(self, audio: bytes) -> tuple[TranscriptPhrase, ...]:
        self.audio.append(audio)
        if not self.loaded:
            raise ModelNotLoaded("T-One не загружен. Веса не скачивались.")
        return self._phrases

    def finish(self) -> tuple[TranscriptPhrase, ...]:
        self.finished += 1
        if not self.loaded:
            raise ModelNotLoaded("T-One не загружен. Веса не скачивались.")
        return (TranscriptPhrase(text="финал", start_time=0.3, end_time=0.6),)


class _Speech:
    def __init__(self, *, loaded: bool) -> None:
        self.loaded = loaded
        self.requests: list[SynthesisRequest] = []
        self.load_calls = 0

    def load(self, _settings: Settings) -> None:
        self.load_calls += 1
        raise AssertionError("from_pretrained не должен вызываться")

    def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        self.requests.append(request)
        return SynthesisResult(sample_rate=12345, samples=(0.5, -0.5))


def _frames(generator: AsyncIterator[object]) -> list[object]:
    async def collect() -> list[object]:
        return [frame async for frame in generator]

    return asyncio.run(collect())


def test_services_are_pipecat_frame_processors() -> None:
    tone = ToneSttService(settings=Settings(), engine=_Engine(loaded=False))
    qwen = Qwen3TtsService(settings=Settings(), speech=_Speech(loaded=False))
    assert isinstance(tone, STTService)
    assert isinstance(tone, FrameProcessor)
    assert isinstance(qwen, TTSService)
    assert isinstance(qwen, FrameProcessor)
    assert tone.weights_loaded is False
    assert qwen.weights_loaded is False


def test_run_stt_yields_russian_transcript_from_the_engine() -> None:
    phrase = TranscriptPhrase(text="привет", start_time=0.0, end_time=0.3)
    engine = _Engine(loaded=True, phrases=(phrase,))
    service = ToneSttService(settings=Settings(), engine=engine)
    frames = _frames(service.run_stt((1).to_bytes(2, "little", signed=True)))
    assert len(frames) == 1
    frame = frames[0]
    assert isinstance(frame, TranscriptionFrame)
    assert frame.text == "привет"
    assert frame.language == Language.RU
    assert frame.finalized is False
    assert engine.audio


def test_run_stt_without_weights_is_an_error_not_silence() -> None:
    engine = _Engine(loaded=False)
    service = ToneSttService(settings=Settings(), engine=engine)
    frames = _frames(service.run_stt(b"\x01\x00"))
    assert len(frames) == 1
    assert isinstance(frames[0], ErrorFrame)
    assert "не загружен" in frames[0].error
    assert not any(isinstance(frame, TranscriptionFrame) for frame in frames)


def test_run_stt_rejects_a_foreign_sample_rate_before_the_engine() -> None:
    engine = _Engine(loaded=True, phrases=(TranscriptPhrase("x", 0.0, 0.1),))
    service = ToneSttService(settings=Settings(), engine=engine)
    service._sample_rate = 16000
    frames = _frames(service.run_stt(b"\x01\x00"))
    assert isinstance(frames[0], ErrorFrame)
    assert "16000" in frames[0].error
    assert engine.audio == []


def test_vad_stop_flushes_a_final_transcript() -> None:
    engine = _Engine(loaded=True, phrases=())
    service = ToneSttService(settings=Settings(), engine=engine)
    pushed: list[object] = []

    async def capture(frame: object, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    service.push_frame = capture  # type: ignore[method-assign]
    asyncio.run(service.process_frame(VADUserStoppedSpeakingFrame(), FrameDirection.DOWNSTREAM))
    transcripts = [frame for frame in pushed if isinstance(frame, TranscriptionFrame)]
    assert engine.finished == 1
    assert [frame.text for frame in transcripts] == ["финал"]
    assert transcripts[0].finalized is True


def test_end_frame_without_audio_does_not_load_or_error() -> None:
    service = ToneSttService(settings=Settings(load_weights=True))

    def refuse(_settings: object) -> None:
        raise AssertionError("load() вызван без звука")

    service._asr.load = refuse  # type: ignore[method-assign]
    errors: list[str] = []

    async def capture_error(error_msg: str, exception: Exception | None = None, **_kwargs: object) -> None:
        errors.append(error_msg)

    async def capture(frame: object, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        return None

    service.push_error = capture_error  # type: ignore[method-assign]
    service.push_frame = capture  # type: ignore[method-assign]
    asyncio.run(service.process_frame(EndFrame(), FrameDirection.DOWNSTREAM))
    assert errors == []
    assert service._engine is None


def test_wrong_frame_rate_is_rejected() -> None:
    engine = _Engine(loaded=True)
    service = ToneSttService(settings=Settings(), engine=engine)
    errors: list[str] = []

    async def capture_error(error_msg: str, exception: Exception | None = None, **_kwargs: object) -> None:
        errors.append(error_msg)

    service.push_error = capture_error  # type: ignore[method-assign]
    frame = InputAudioRawFrame(audio=b"\x00\x00", sample_rate=16000, num_channels=1)
    asyncio.run(service.process_frame(frame, FrameDirection.DOWNSTREAM))
    assert errors
    assert "16000" in errors[0]
    assert engine.audio == []


def test_tts_without_weights_yields_error_and_does_not_load() -> None:
    speech = _Speech(loaded=False)
    service = Qwen3TtsService(
        settings=Settings(load_weights=False, tts_ref_audio="/mac/ref-ru.wav"),
        speech=speech,
    )
    frames = _frames(service.run_tts("Алло", "ctx-1"))
    assert speech.load_calls == 0
    assert speech.requests == []
    assert len(frames) == 1
    assert isinstance(frames[0], ErrorFrame)
    assert "не загружен" in frames[0].error
    assert not any(isinstance(frame, TTSAudioRawFrame) for frame in frames)


def test_tts_uses_voice_clone_contract() -> None:
    speech = _Speech(loaded=True)
    service = Qwen3TtsService(
        settings=Settings(tts_ref_audio="/mac/ref-ru.wav"),
        speech=speech,
        output_sample_rate=12345,
    )
    frames = _frames(service.run_tts("Да, я вас слышу.", "ctx-7"))
    assert speech.load_calls == 0
    request = speech.requests[0]
    assert request.text == "Да, я вас слышу."
    assert request.language == "Russian"
    assert request.mode == "clone"
    assert request.model_id == TTS_MODEL_0_6B_BASE
    assert request.ref_audio == "/mac/ref-ru.wav"
    assert request.ref_text == DEFAULT_TTS_REF_TEXT
    assert request.speaker != "Aiden"
    audio = frames[0]
    assert isinstance(audio, TTSAudioRawFrame)
    assert audio.sample_rate == 12345
    assert audio.context_id == "ctx-7"
    assert audio.num_channels == 1
    assert len(audio.audio) == 4


def test_tts_bad_request_is_an_error_frame() -> None:
    speech = _Speech(loaded=True)
    service = Qwen3TtsService(settings=Settings(), speech=speech)
    frames = _frames(service.run_tts("   ", "ctx"))
    assert isinstance(frames[0], ErrorFrame)
    assert speech.requests == []


def test_skeleton_wires_processors_without_weights() -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("загрузчик весов вызван при сборке каркаса")

    asr_load = pytest.MonkeyPatch()
    asr_load.setattr("app.asr.ToneAsr.load", refuse)
    asr_load.setattr("app.tts.Qwen3Speech.load", refuse)
    try:
        skeleton = build_skeleton(Settings(load_weights=True))
    finally:
        asr_load.undo()
    assert isinstance(skeleton, PipelineSkeleton)
    assert skeleton.has_tone_stt is True
    assert skeleton.has_qwen_tts is True
    assert skeleton.weights_loaded is False
    assert skeleton.audio_in_sample_rate == 8000
    assert skeleton.processor_count == 7
    assert skeleton.has_local_llm is True
    assert skeleton.llm_backend == "off"
    assert skeleton.interrupt_on_user_speech is True


def test_tts_resamples_when_model_rate_differs() -> None:
    class _EightK:
        loaded = True

        def synthesize(self, _request: SynthesisRequest) -> SynthesisResult:
            return SynthesisResult(sample_rate=8000, samples=(0.5, -0.5, 0.25, -0.25))

    service = Qwen3TtsService(
        settings=Settings(tts_ref_audio="/mac/ref-ru.wav"),
        speech=_EightK(),  # type: ignore[arg-type]
        output_sample_rate=16000,
    )
    frames = _frames(service.run_tts("Алло", "ctx"))
    audio = frames[0]
    assert isinstance(audio, TTSAudioRawFrame)
    assert audio.sample_rate == 16000
    assert len(audio.audio) > 8
    assert len(audio.audio) % 2 == 0


class _RecordingModel:
    def __init__(self) -> None:
        self.turns: tuple[ChatTurn, ...] = ()

    def stream(self, turns: tuple[ChatTurn, ...]):
        self.turns = tuple(turns)
        yield "Алло"
        yield " мир"


def test_local_llm_streams_text_and_is_not_dashscope() -> None:
    qwen_llm = pytest.importorskip("pipecat.services.qwen.llm")
    model = _RecordingModel()
    service = LocalLlmService(settings=Settings(llm_backend="off"), model=model)
    assert isinstance(service, LLMService)
    assert not isinstance(service, qwen_llm.QwenLLMService)
    assert service.weights_loaded is False
    pushed: list[object] = []

    async def capture(frame: object, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    service.push_frame = capture  # type: ignore[method-assign]
    context = LLMContext([{"role": "user", "content": "нужен оператор"}])
    asyncio.run(service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM))
    texts = [frame.text for frame in pushed if isinstance(frame, LLMTextFrame)]
    assert texts == ["Алло", " мир"]
    assert isinstance(pushed[0], LLMFullResponseStartFrame)
    assert isinstance(pushed[-1], LLMFullResponseEndFrame)
    assert model.turns[0].role == "developer"
    assert model.turns[0].text == RUSSIAN_SYSTEM_PROMPT
    assert model.turns[1] == ChatTurn("user", "нужен оператор")


def test_local_llm_without_backend_is_an_error() -> None:
    service = LocalLlmService(settings=Settings(llm_backend="off"))
    errors: list[str] = []
    pushed: list[object] = []

    async def capture(frame: object, direction: FrameDirection = FrameDirection.DOWNSTREAM) -> None:
        pushed.append(frame)

    async def capture_error(error_msg: str, exception: Exception | None = None, **_kwargs: object) -> None:
        errors.append(error_msg)
        assert isinstance(exception, LlmBackendDisabled)

    service.push_frame = capture  # type: ignore[method-assign]
    service.push_error = capture_error  # type: ignore[method-assign]
    context = LLMContext([{"role": "user", "content": "Алло"}])
    asyncio.run(service.process_frame(LLMContextFrame(context), FrameDirection.DOWNSTREAM))
    assert errors
    assert "выключена" in errors[0]
    assert not any(isinstance(frame, LLMTextFrame) for frame in pushed)


def test_vad_turn_start_stops_tts() -> None:
    async def scenario() -> None:
        speech = Qwen3TtsService(settings=Settings(), speech=_Speech(loaded=False))
        await speech.setup(
            FrameProcessorSetup(
                clock=SystemClock(),
                task_manager=TaskManager(),
                pipeline_worker=None,  # type: ignore[arg-type]
            )
        )
        try:
            await speech.create_audio_context("reply")
            assert speech.audio_context_available("reply")
            strategy = VADUserTurnStartStrategy(enable_interruptions=True)
            seen: dict[str, object] = {}

            @strategy.event_handler("on_user_turn_started")
            async def _on_started(_strategy: object, params: object) -> None:
                try:
                    seen["interrupt"] = getattr(params, "enable_interruptions")
                    if seen["interrupt"]:
                        await speech.process_frame(InterruptionFrame(), FrameDirection.DOWNSTREAM)
                except Exception as exc:  # noqa: BLE001
                    seen["error"] = exc

            result = await strategy.process_frame(VADUserStartedSpeakingFrame())
            assert result is ProcessFrameResult.STOP
            assert seen.get("error") is None
            assert seen.get("interrupt") is True
            assert speech.audio_context_available("reply") is False
        finally:
            await speech.cleanup()

    asyncio.run(scenario())


def test_skeleton_skips_when_pipecat_import_is_blocked() -> None:
    class _Blocker:
        def find_spec(self, fullname: str, path: object = None, target: object = None) -> None:
            if fullname == "pipecat" or fullname.startswith("pipecat."):
                raise ImportError("pipecat заблокирован в тесте")
            return None

    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    removed: dict[str, object] = {}
    try:
        for name in list(sys.modules):
            if name == "pipecat" or name.startswith("pipecat."):
                removed[name] = sys.modules.pop(name)
        skeleton = build_skeleton()
        assert main() == 0
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(removed)
    assert isinstance(skeleton, SymbolProbe)
    assert skeleton.status in {"missing", "partial"}
