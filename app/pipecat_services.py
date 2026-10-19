"""Процессоры Pipecat 1.13 для T-One и Qwen3-TTS.

Импорт этого модуля требует `pipecat-ai`. `STTService` и `TTSService` — наследники
`FrameProcessor`. Контракт подкласса: `run_stt(audio: bytes)` и `run_tts(text, context_id)`.
Конструкторы не вызывают `from_hugging_face` и `from_pretrained`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from pipecat.frames.frames import (
    EndFrame,
    ErrorFrame,
    Frame,
    InputAudioRawFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.settings import STTSettings, TTSSettings
from pipecat.services.stt_service import STTService
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601

from app.asr import ModelNotLoaded as AsrNotLoaded
from app.asr import ToneAsr, TonePackageError, ToneStreamEngine
from app.audio import float_samples_to_pcm16
from app.settings import TONE_SAMPLE_RATE, TTS_MODEL_0_6B_CUSTOM, Settings
from app.tts import ModelNotLoaded as TtsNotLoaded
from app.tts import Qwen3Speech, SynthesisRequest, TtsRequestError, validate_request

TONE_MODEL_ID = "t-tech/T-one"


class ToneSttService(STTService):
    """Потоковый ASR: PCM16 8 кГц режется на 300 мс и уходит в `forward`."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        asr: ToneAsr | None = None,
        engine: ToneStreamEngine | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(
            sample_rate=TONE_SAMPLE_RATE,
            settings=STTSettings(model=TONE_MODEL_ID, language=Language.RU),
            **kwargs,
        )
        self._app_settings = settings or Settings()
        self._asr = asr or ToneAsr()
        self._engine = engine

    @property
    def weights_loaded(self) -> bool:
        if self._engine is not None:
            return self._engine.loaded
        return self._asr.loaded

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame | None, None]:
        if self.sample_rate not in (0, TONE_SAMPLE_RATE):
            yield ErrorFrame(
                error=f"T-One ждёт {TONE_SAMPLE_RATE} Гц, в сервисе {self.sample_rate} Гц. Ресемплинг не делается."
            )
            return
        try:
            engine = self._engine_for_audio()
            phrases = engine.push_pcm16(audio)
        except (AsrNotLoaded, TonePackageError, ValueError) as exc:
            yield ErrorFrame(error=str(exc))
            return
        for phrase in phrases:
            if not phrase.text:
                continue
            yield TranscriptionFrame(
                text=phrase.text,
                user_id=self._user_id,
                timestamp=time_now_iso8601(),
                language=Language.RU,
            )

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        if isinstance(frame, InputAudioRawFrame) and frame.sample_rate not in (0, TONE_SAMPLE_RATE):
            await self.push_error(f"Кадр аудио {frame.sample_rate} Гц, T-One принимает только {TONE_SAMPLE_RATE} Гц.")
            return
        if isinstance(frame, EndFrame):
            await self._flush_stream()
        await super().process_frame(frame, direction)
        if isinstance(frame, VADUserStoppedSpeakingFrame):
            await self._flush_stream()

    def _engine_for_audio(self) -> ToneStreamEngine:
        if self._engine is not None:
            return self._engine
        if not self._asr.loaded and self._app_settings.load_weights:
            self._asr.load(self._app_settings)
        self._engine = self._asr.open_stream()
        return self._engine

    async def _flush_stream(self) -> None:
        engine = self._engine
        if engine is None:
            return
        try:
            phrases = engine.finish()
        except (AsrNotLoaded, TonePackageError, ValueError) as exc:
            await self.push_error(str(exc), exception=exc)
            return
        for phrase in phrases:
            if not phrase.text:
                continue
            await self.push_frame(
                TranscriptionFrame(
                    text=phrase.text,
                    user_id=self._user_id,
                    timestamp=time_now_iso8601(),
                    language=Language.RU,
                    finalized=True,
                )
            )


class Qwen3TtsService(TTSService):
    """Синтез через `Qwen3TTSModel.generate_custom_voice`. Без весов — ErrorFrame.

    Частота кадра — та, что вернула модель. К 24 кГц выхода пайплайна волна не приводится:
    ресемплер здесь не подключён.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        speech: Qwen3Speech | None = None,
        **kwargs: object,
    ) -> None:
        app_settings = settings or Settings()
        super().__init__(
            sample_rate=None,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(
                model=app_settings.tts_model_id or TTS_MODEL_0_6B_CUSTOM,
                voice=app_settings.tts_speaker,
                language=Language.RU,
            ),
            **kwargs,
        )
        self._app_settings = app_settings
        self._speech = speech or Qwen3Speech()

    @property
    def weights_loaded(self) -> bool:
        return self._speech.loaded

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame | None, None]:
        request = SynthesisRequest(
            text=text,
            language=self._app_settings.tts_language,
            speaker=self._app_settings.tts_speaker,
            model_id=self._app_settings.tts_model_id,
        )
        try:
            validate_request(request)
            if not self._speech.loaded:
                if not self._app_settings.load_weights:
                    yield ErrorFrame(error="Qwen3-TTS не загружен. Веса не скачивались, тишина не подставляется.")
                    return
                self._speech.load(self._app_settings)
            result = self._speech.synthesize(request)
            audio = float_samples_to_pcm16(result.samples)
        except (TtsNotLoaded, TtsRequestError, ValueError) as exc:
            yield ErrorFrame(error=str(exc))
            return
        yield TTSAudioRawFrame(
            audio=audio,
            sample_rate=result.sample_rate,
            num_channels=1,
            context_id=context_id,
        )
