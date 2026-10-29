"""Явная команда голосовой репетиции. До проверки референса модели не вызываются."""

from __future__ import annotations

import sys
import wave
from dataclasses import replace
from pathlib import Path

from app.asr import ToneAsr, TonePackageError
from app.audio import float_samples_to_pcm16, pcm16le_to_samples
from app.file_run import read_pcm16_wav
from app.settings import Settings
from app.train.library import Library
from app.train.rehearsal import start_rehearsal
from app.train.voice import Heard, Spoken, play_operator_audio
from app.tts import Qwen3Speech, TtsPackageError, TtsRequestError, request_from_settings, validate_request


def speak_case(
    *,
    case_id: str,
    wav: Path,
    out: Path,
    settings: Settings,
    library: Library,
) -> int:
    if not Path(settings.tts_ref_audio).is_file():
        shown = settings.tts_ref_audio or "(путь пустой)"
        print(
            f"Запись голоса не найдена: {shown}. Задайте CALL_CENTER_TTS_REF_AUDIO. Модель не вызывалась.",
            file=sys.stderr,
        )
        return 2
    try:
        samples = read_pcm16_wav(wav)
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        case = library.case(case_id)
    except KeyError:
        print(f"Нет карточки {case_id}.", file=sys.stderr)
        return 1
    armed = replace(settings, load_weights=True)
    port = _LoadedVoice(armed, out)
    try:
        play_operator_audio(start_rehearsal(case, library.ordered()), port, _samples_to_pcm(samples))
    except (TonePackageError, TtsPackageError, TtsRequestError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not out.is_file():
        print("Фраз клиента нет. TTS не вызывался.", file=sys.stderr)
        return 1
    return 0


class _LoadedVoice:
    def __init__(self, settings: Settings, out: Path) -> None:
        self._settings = settings
        self._out = out

    def hear(self, pcm16_8k: bytes) -> Heard:
        asr = ToneAsr()
        asr.load(self._settings)
        phrases = asr.transcribe_offline(pcm16le_to_samples(pcm16_8k))
        text = " ".join(phrase.text.strip() for phrase in phrases if phrase.text.strip())
        return Heard(text)

    def speak(self, text: str) -> Spoken:
        request = request_from_settings(text, self._settings)
        validate_request(request)
        speech = Qwen3Speech()
        speech.load(self._settings)
        result = speech.synthesize(request)
        pcm = float_samples_to_pcm16(result.samples)
        with wave.open(str(self._out), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(result.sample_rate)
            handle.writeframes(pcm)
        return Spoken(text=text, wav=pcm)


def _samples_to_pcm(samples: tuple[int, ...]) -> bytes:
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)
