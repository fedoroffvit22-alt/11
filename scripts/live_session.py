"""Незакоммиченный живой сеанс. Смоук и pytest его не запускают.

Микрофон открывает только `WorkerRunner.run()`: конструктор транспорта поток не стартует.
Сигнал человеку — сразу перед `run()`.

Пока агент говорит и коротким хвостом после тишины динамика, кадры микрофона не идут в
распознавание и не начинают ход. Перебивание выключено. Сеанс закрывается только когда
текущая фраза уже доиграна: после двух настоящих реплик либо когда окно второй реплики
истекло. Эхо только что сказанного текста ходом не считается.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from dataclasses import dataclass, field, replace

from app.llm import RUSSIAN_SYSTEM_PROMPT
from app.pipecat_services import LocalLlmService, Qwen3TtsService, ToneSttService
from app.settings import PIPELINE_AUDIO_OUT_SAMPLE_RATE, TONE_SAMPLE_RATE, Settings
from app.tts import Qwen3Speech
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    ErrorFrame,
    InputAudioRawFrame,
    InterruptionFrame,
    LLMTextFrame,
    TranscriptionFrame,
    UserStartedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.transports.local.audio import LocalAudioTransport, LocalAudioTransportParams
from pipecat.turns.user_mute.base_user_mute_strategy import BaseUserMuteStrategy
from pipecat.turns.user_start.vad_user_turn_start_strategy import VADUserTurnStartStrategy
from pipecat.turns.user_stop.speech_timeout_user_turn_stop_strategy import (
    SpeechTimeoutUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

INPUT_DEVICE_INDEX = 2
OUTPUT_DEVICE_INDEX = 3
ECHO_TAIL_SECS = 0.8
SECOND_TURN_WINDOW_SECS = 32.0
TRANSCRIPT_GRACE_SECS = 2.0
HARD_CAP_SECS = 150.0


def normalize_words(text: str) -> list[str]:
    lowered = text.lower().replace("ё", "е")
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered)
    return [word for word in cleaned.split() if word]


def is_echo(heard: str, spoken_texts: list[str]) -> bool:
    """Эхо — фраза из двух и более слов, которая по порядку входит в последний ответ."""

    heard_words = normalize_words(heard)
    if len(heard_words) < 2 or not spoken_texts:
        return False
    spoken_words = normalize_words(spoken_texts[-1])
    index = 0
    for word in spoken_words:
        if index < len(heard_words) and word == heard_words[index]:
            index += 1
    return index == len(heard_words)


@dataclass
class PhrasePlay:
    text: str
    started: bool = False
    finished: bool = False
    cut: bool = False


@dataclass
class SessionLog:
    started: float = 0.0
    user_turns: list[str] = field(default_factory=list)
    echo_turns: list[str] = field(default_factory=list)
    suppressed: list[str] = field(default_factory=list)
    model_texts: list[str] = field(default_factory=list)
    phrases: list[PhrasePlay] = field(default_factory=list)
    mute_armed: bool = False
    playback: bool = False
    awaiting_playback: bool = False
    tail_until: float = 0.0
    listen_until: float = 0.0
    accept_until: float = 0.0
    drain_until: float = 0.0
    user_speaking: bool = False
    speaker_played: bool = False
    tts_cut_off: bool = False
    replies_finished: int = 0
    raw_model_texts: list[str] = field(default_factory=list)
    first_error: str = ""

    def muted(self, now: float) -> bool:
        if self.replies_finished >= 2:
            return True
        return self.mute_armed or self.playback or now < self.tail_until


def transcript_fate(text: str, session: SessionLog, now: float) -> str:
    if session.muted(now):
        return "echo" if is_echo(text, session.model_texts) else "suppressed"
    if is_echo(text, session.model_texts):
        return "echo"
    return "keep"


def decide_stop(session: SessionLog, now: float) -> str | None:
    """Пока динамик играет или в нём ещё доигрывается буфер, сеанс не закрывается."""

    if session.playback or now < session.drain_until:
        return None
    if (
        len(session.user_turns) >= 2
        and session.replies_finished >= 2
        and not session.awaiting_playback
    ):
        return "две настоящие реплики, оба ответа доиграны"
    if session.user_speaking or now < session.accept_until:
        return None
    if session.started and now - session.started >= HARD_CAP_SECS:
        return "предел времени"
    reply_still_due = session.awaiting_playback or (
        len(session.user_turns) >= 2 and session.replies_finished < len(session.user_turns)
    )
    if reply_still_due:
        return None
    if (
        session.replies_finished >= 1
        and len(session.user_turns) < 2
        and session.listen_until
        and now >= session.listen_until
    ):
        return "окно второй реплики закрыто"
    return None


def observe(session: SessionLog, frame: object) -> None:
    now = time.monotonic()
    if isinstance(frame, LLMTextFrame) and frame.text.strip():
        text = frame.text.strip()
        session.model_texts.append(text)
        session.phrases.append(PhrasePlay(text=text))
        session.mute_armed = True
        session.awaiting_playback = True
        return
    if isinstance(frame, BotStartedSpeakingFrame):
        if session.playback:
            return
        session.playback = True
        session.speaker_played = True
        if session.phrases and not session.phrases[-1].started:
            session.phrases[-1].started = True
        print("ДИНАМИК: речь агента началась", flush=True)
        return
    if isinstance(frame, BotStoppedSpeakingFrame):
        if not session.playback:
            return
        session.playback = False
        session.mute_armed = False
        session.tail_until = now + ECHO_TAIL_SECS
        session.drain_until = now + 1.2
        session.awaiting_playback = False
        if session.phrases and session.phrases[-1].started and not session.phrases[-1].finished:
            session.phrases[-1].finished = True
            session.replies_finished += 1
        if session.replies_finished == 1 and session.listen_until == 0.0 and session.user_turns:
            session.listen_until = now + SECOND_TURN_WINDOW_SECS
            print("ОКНО: динамик замолчал, жду вторую реплику", flush=True)
        print("ДИНАМИК: речь агента закончилась", flush=True)
        return
    if isinstance(frame, (UserStartedSpeakingFrame, VADUserStartedSpeakingFrame)):
        if session.muted(now):
            return
        session.user_speaking = True
        return
    if isinstance(frame, VADUserStoppedSpeakingFrame):
        if session.user_speaking:
            session.user_speaking = False
            session.accept_until = now + TRANSCRIPT_GRACE_SECS
        return
    if isinstance(frame, InterruptionFrame) and session.playback:
        session.tts_cut_off = True
        if session.phrases and session.phrases[-1].started and not session.phrases[-1].finished:
            session.phrases[-1].cut = True
        print("ПЕРЕБИВАНИЕ: TTS оборван", flush=True)
        return
    if isinstance(frame, ErrorFrame) and not session.first_error:
        session.first_error = frame.error
        if session.awaiting_playback and not session.playback:
            session.awaiting_playback = False
            session.mute_armed = False
        print(f"ОШИБКА: {frame.error}", flush=True)


class MuteWhileBotSpeaks(BaseUserMuteStrategy):
    def __init__(self, session: SessionLog, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._session = session

    async def process_frame(self, frame: object) -> bool:
        observe(self._session, frame)
        return self._session.muted(time.monotonic())


class MicGate(FrameProcessor):
    """Не пускает микрофон в распознавание, пока динамик говорит или звенит хвост."""

    def __init__(self, session: SessionLog, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._session = session

    async def process_frame(self, frame: object, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        observe(self._session, frame)
        if (
            direction == FrameDirection.DOWNSTREAM
            and isinstance(frame, InputAudioRawFrame)
            and self._session.muted(time.monotonic())
        ):
            return
        await self.push_frame(frame, direction)


class TurnLog(FrameProcessor):
    def __init__(self, session: SessionLog, *, count_user: bool, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._session = session
        self._count_user = count_user

    async def process_frame(self, frame: object, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if self._count_user and isinstance(frame, TranscriptionFrame) and frame.text.strip():
            fate = transcript_fate(frame.text, self._session, time.monotonic())
            mark = "финал" if frame.finalized else "частично"
            if fate == "keep":
                print(f"РАСПОЗНАНО ({mark}): {frame.text}", flush=True)
                if frame.finalized:
                    self._session.user_turns.append(frame.text.strip())
                await self.push_frame(frame, direction)
                return
            bucket = self._session.echo_turns if fate == "echo" else self._session.suppressed
            bucket.append(frame.text.strip())
            print(f"ЭХО не ход ({mark}): {frame.text}", flush=True)
            return
        observe(self._session, frame)
        await self.push_frame(frame, direction)


def log_spoken_reply(session: SessionLog) -> None:
    """Печатает текст модели до shape_spoken_reply и фразу, которая уйдёт в TTS."""

    import app.reply as reply_module

    original = reply_module.shape_spoken_reply

    def logged(user_text: str, model_text: str) -> str:
        spoken = original(user_text, model_text)
        session.raw_model_texts.append(model_text)
        print(f"МОДЕЛЬ_ДО_ПРАВКИ: {model_text}", flush=True)
        print(f"В_TTS: {spoken}", flush=True)
        return spoken

    reply_module.shape_spoken_reply = logged


def cue(start: bool) -> None:
    title = "Колл-центр"
    text = "Говорите сейчас" if start else "Сеанс закрыт"
    subprocess.run(
        ["osascript", "-e", f'display notification "{text}" with title "{title}"'],
        check=False,
    )
    subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], check=False)


def self_check() -> None:
    spoken = ["Да, слышу вас. Как я могу помочь?"]
    if not is_echo("да слышу вас", spoken):
        raise SystemExit("эхо «да слышу вас» не распознано")
    if is_echo("алло", spoken):
        raise SystemExit("короткое «алло» ошибочно признано эхом")
    if is_echo("это проверка связи", spoken):
        raise SystemExit("чужая фраза признана эхом")

    session = SessionLog(started=time.monotonic())
    session.user_turns.append("алло")
    session.awaiting_playback = True
    if decide_stop(session, time.monotonic()) is not None:
        raise SystemExit("сеанс закрылся, пока ответ ещё не доигран")
    session.awaiting_playback = False
    session.playback = True
    if decide_stop(session, time.monotonic()) is not None:
        raise SystemExit("сеанс закрылся во время речи динамика")
    session.playback = False
    session.replies_finished = 1
    session.listen_until = time.monotonic() + 5
    if decide_stop(session, time.monotonic()) is not None:
        raise SystemExit("окно второй реплики закрылось сразу")
    if decide_stop(session, session.listen_until + 0.1) != "окно второй реплики закрыто":
        raise SystemExit("окно второй реплики не закрылось")
    session.user_turns.append("вторая")
    session.replies_finished = 1
    session.awaiting_playback = True
    if decide_stop(session, time.monotonic()) is not None:
        raise SystemExit("вторая реплика оборвала ещё не начатый ответ")
    session.awaiting_playback = False
    session.replies_finished = 2
    if decide_stop(session, time.monotonic()) != "две настоящие реплики, оба ответа доиграны":
        raise SystemExit("две доигранные реплики не завершили сеанс")
    print("ПРОВЕРКА логики без микрофона: ок", flush=True)


async def main() -> int:
    self_check()
    settings = replace(Settings.from_env(), load_weights=True)
    print("Гружу Silero, T-One и клон. Микрофон ещё закрыт.", flush=True)
    vad = SileroVADAnalyzer(sample_rate=TONE_SAMPLE_RATE, params=VADParams(stop_secs=0.2))
    tone = ToneSttService(settings=settings)
    tone._asr.load(settings)
    speech = Qwen3Speech()
    speech.load(settings)
    qwen = Qwen3TtsService(
        settings=settings,
        speech=speech,
        output_sample_rate=PIPELINE_AUDIO_OUT_SAMPLE_RATE,
    )
    strategies = UserTurnStrategies(
        start=[VADUserTurnStartStrategy(enable_interruptions=False)],
        stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.2)],
    )
    context = LLMContext(messages=[{"role": "developer", "content": RUSSIAN_SYSTEM_PROMPT}])
    session = SessionLog()
    user, assistant = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            user_turn_strategies=strategies,
            vad_analyzer=vad,
            user_mute_strategies=[MuteWhileBotSpeaks(session)],
        ),
    )
    log_spoken_reply(session)
    local_llm = LocalLlmService(settings=settings)
    gate = MicGate(session, name="mic-gate")
    heard = TurnLog(session, count_user=True, name="heard")
    spoken = TurnLog(session, count_user=False, name="spoken")
    runner: WorkerRunner | None = None
    try:
        transport = LocalAudioTransport(
            LocalAudioTransportParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                audio_in_sample_rate=TONE_SAMPLE_RATE,
                audio_out_sample_rate=PIPELINE_AUDIO_OUT_SAMPLE_RATE,
                audio_in_channels=1,
                audio_out_channels=1,
                input_device_index=INPUT_DEVICE_INDEX,
                output_device_index=OUTPUT_DEVICE_INDEX,
            )
        )
        pipeline = Pipeline(
            [
                transport.input(),
                gate,
                tone,
                heard,
                user,
                local_llm,
                spoken,
                qwen,
                transport.output(),
                assistant,
            ]
        )
        worker = PipelineWorker(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=TONE_SAMPLE_RATE,
                audio_out_sample_rate=PIPELINE_AUDIO_OUT_SAMPLE_RATE,
            ),
            idle_timeout_secs=HARD_CAP_SECS + 30,
        )

        runner = WorkerRunner()
        await runner.add_workers(worker)
        print("СИГНАЛ: говорите сейчас", flush=True)
        cue(start=True)
        session.started = time.monotonic()
        print(
            f"МИКРОФОН: открываю индекс {INPUT_DEVICE_INDEX} «Микрофон MacBook Air», "
            f"динамик индекс {OUTPUT_DEVICE_INDEX}.",
            flush=True,
        )

        async def stop_later() -> None:
            assert runner is not None
            while True:
                await asyncio.sleep(0.25)
                reason = decide_stop(session, time.monotonic())
                if reason is None:
                    continue
                if session.playback or session.awaiting_playback:
                    continue
                print(f"СТОП: {reason}", flush=True)
                await runner.cancel()
                return

        stopper = asyncio.create_task(stop_later())
        try:
            await runner.run()
        finally:
            stopper.cancel()
        return 0 if not session.first_error else 1
    finally:
        elapsed = time.monotonic() - session.started if session.started else 0.0
        print(f"ДЛИТЕЛЬНОСТЬ: {elapsed:.1f} с", flush=True)
        print(f"РЕПЛИКИ: {session.user_turns}", flush=True)
        print(f"ЭХО: {session.echo_turns}", flush=True)
        print(f"ПОДАВЛЕНО: {session.suppressed}", flush=True)
        print(f"МОДЕЛЬ_ДО_ПРАВКИ_ВСЕ: {session.raw_model_texts}", flush=True)
        print(f"В_TTS_ВСЕ: {session.model_texts}", flush=True)
        for index, phrase in enumerate(session.phrases, start=1):
            print(
                f"ФРАЗА {index}: доиграна={phrase.finished} оборвана={phrase.cut} текст={phrase.text}",
                flush=True,
            )
        print(f"TTS_ОБОРВАН: {session.tts_cut_off}", flush=True)
        print(f"ДИНАМИК_ИГРАЛ: {session.speaker_played}", flush=True)
        if session.first_error:
            print(f"ПЕРВАЯ_ОШИБКА: {session.first_error}", flush=True)
        print("СИГНАЛ: сеанс закрыт", flush=True)
        cue(start=False)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        self_check()
        raise SystemExit(0)
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
