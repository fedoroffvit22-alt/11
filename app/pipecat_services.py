"""Процессоры Pipecat 1.13 для T-One и Qwen3-TTS.

Импорт этого модуля требует `pipecat-ai`. `STTService` и `TTSService` — наследники
`FrameProcessor`. Контракт подкласса: `run_stt(audio: bytes)` и `run_tts(text, context_id)`.
Конструкторы не вызывают `from_hugging_face` и `from_pretrained`.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from pathlib import Path

from pipecat.audio.utils import create_file_resampler
from pipecat.frames.frames import (
    EndFrame,
    ErrorFrame,
    Frame,
    InputAudioRawFrame,
    LLMContextFrame,
    LLMFullResponseEndFrame,
    LLMFullResponseStartFrame,
    TranscriptionFrame,
    TTSAudioRawFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.llm_service import LLMService
from pipecat.services.settings import LLMSettings, STTSettings, TTSSettings
from pipecat.services.stt_service import STTService
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601

from app.asr import ModelNotLoaded as AsrNotLoaded
from app.asr import ToneAsr, TonePackageError, ToneStreamEngine
from app.audio import float_samples_to_pcm16
from app.llm import RUSSIAN_SYSTEM_PROMPT, turns_from_messages
from app.reply import ReplyFailed, generate_reply
from app.settings import TONE_SAMPLE_RATE, Settings
from app.tts import ModelNotLoaded as TtsNotLoaded
from app.tts import Qwen3Speech, TtsRequestError, request_from_settings, validate_request

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
    """Синтез принятым клоном Base. Референс только из настроек.

    CustomVoice остаётся режимом `custom`. Нет файла референса или нет весов —
    ErrorFrame, не тишина и не загрузка. Если частота волны не совпадает с
    `audio_out_sample_rate` пайплайна, PCM16 пересчитывается ресемплером Pipecat
    (`SOXRAudioResampler`). Устройство не открывается. `from_pretrained` конструктор не вызывает.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        speech: Qwen3Speech | None = None,
        output_sample_rate: int | None = None,
        **kwargs: object,
    ) -> None:
        app_settings = settings or Settings()
        rate = output_sample_rate if output_sample_rate is not None else app_settings.audio_out_sample_rate
        self._output_sample_rate = rate
        super().__init__(
            sample_rate=rate,
            push_start_frame=True,
            push_stop_frames=True,
            settings=TTSSettings(
                model=app_settings.tts_model_id,
                voice="clone" if app_settings.tts_mode == "clone" else app_settings.tts_speaker,
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
        request = request_from_settings(text, self._app_settings)
        try:
            validate_request(request)
            if request.mode == "clone" and not Path(request.ref_audio).is_file():
                yield ErrorFrame(
                    error=(
                        f"Запись голоса не найдена: {request.ref_audio}. "
                        "Задайте CALL_CENTER_TTS_REF_AUDIO. Модель не вызывалась."
                    )
                )
                return
            if not self._speech.loaded:
                if not self._app_settings.load_weights:
                    yield ErrorFrame(error="Qwen3-TTS не загружен. Веса не скачивались, тишина не подставляется.")
                    return
                self._speech.load(self._app_settings)
            result = self._speech.synthesize(request)
            audio = float_samples_to_pcm16(result.samples)
            audio = await _match_pipeline_rate(audio, result.sample_rate, self._output_sample_rate)
        except (TtsNotLoaded, TtsRequestError, ValueError) as exc:
            yield ErrorFrame(error=str(exc))
            return
        yield TTSAudioRawFrame(
            audio=audio,
            sample_rate=self._output_sample_rate,
            num_channels=1,
            context_id=context_id,
        )


class LocalLlmService(LLMService):
    """Текст считает тот же путь, что `file_run reply`.

    Это `generate_reply`: отдельный `.venv-llm` и `scripts/mlx_generate.py`.
    Проектный процесс `mlx_lm` не импортирует. Конструктор скрипт не запускает,
    поэтому смоук без интерпретатора не падает. Нет `.venv-llm` — ошибка, не тишина.
    Не `QwenLLMService` и не Ollama. Пайплайн отсюда не стартует.
    """

    def __init__(self, *, settings: Settings | None = None, **kwargs: object) -> None:
        app_settings = settings or Settings()
        super().__init__(
            settings=LLMSettings(
                model=app_settings.llm_model_id,
                system_instruction=RUSSIAN_SYSTEM_PROMPT,
            ),
            **kwargs,
        )
        self._app_settings = app_settings

    @property
    def weights_loaded(self) -> bool:
        return False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextFrame):
            await self._reply(frame.context.get_messages())
            return
        await self.push_frame(frame, direction)

    async def _reply(self, messages: object) -> None:
        user_text = _latest_user_text(messages)
        await self.push_frame(LLMFullResponseStartFrame())
        try:
            if not user_text:
                await self.push_error("В контексте нет реплики пользователя. Модель не вызывалась.")
                return
            spoken = generate_reply(user_text, self._app_settings)
            if spoken:
                await self._push_llm_text(spoken)
        except ReplyFailed as exc:
            await self.push_error(str(exc), exception=exc)
        finally:
            await self.push_frame(LLMFullResponseEndFrame())


def _latest_user_text(messages: object) -> str:
    if isinstance(messages, (str, bytes)) or not isinstance(messages, Sequence):
        return ""
    for turn in reversed(turns_from_messages(messages)):
        if turn.role == "user" and turn.text:
            return turn.text
    return ""


async def _match_pipeline_rate(audio: bytes, source_rate: int, target_rate: int) -> bytes:
    """Привести PCM16 к частоте выхода пайплайна. Совпадающие частоты не трогаем."""

    if source_rate == target_rate:
        return audio
    if source_rate <= 0 or target_rate <= 0:
        raise ValueError(f"Частота TTS {source_rate} Гц или пайплайна {target_rate} Гц не положительная.")
    resampled = await create_file_resampler().resample(audio, source_rate, target_rate)
    if not resampled:
        raise ValueError("Ресемплер Pipecat вернул пустую волну.")
    return resampled
