"""Файл ASR и одна фраза TTS. Веса качаются только из `main()`.

`python -m app` этот модуль не импортирует. Импорт и разбор аргументов
`load()` не вызывают.
"""

from __future__ import annotations

import argparse
import importlib
import sys
import wave
from dataclasses import replace
from pathlib import Path

from app.asr import ToneAsr, TonePackageError
from app.audio import float_samples_to_pcm16, pcm16le_to_samples
from app.reply import ReplyFailed, generate_reply
from app.settings import TONE_GIT_REVISION, TONE_SAMPLE_RATE, Settings
from app.tts import Qwen3Speech, TtsPackageError, TtsRequestError, request_from_settings, validate_request

_TONE_REPO = "t-tech/T-one"


def main(argv: list[str] | None = None) -> int:
    """Единственный путь, который ставит `load_weights=True` и вызывает `load()`."""

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        if code is None or code == 0:
            return 0
        if isinstance(code, int):
            return code
        return 2

    settings = replace(Settings.from_env(), load_weights=True)
    command = args.command
    if command == "asr":
        return _run_asr(args, settings)
    if command == "tts":
        return _run_tts(args, settings)
    if command == "reply":
        return _run_reply(args, settings)
    if command == "turn":
        return _run_turn(args, settings)
    print(f"Неизвестная команда: {command}.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.file_run",
        description=(
            "Распознать файл, ответить на него или синтезировать фразу. "
            "python -m app веса не скачивает и микрофон не открывает."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    asr = commands.add_parser("asr", help="Офлайн-распознавание файла 8 кГц.")
    asr.add_argument("wav", nargs="?", help="Моно PCM16 WAV, 8000 Гц.")
    asr.add_argument(
        "--example",
        action="store_true",
        help="Короткий пример T-One (tone.read_example_audio, нужен miniaudio).",
    )
    tts = commands.add_parser("tts", help="Одна фраза Qwen3-TTS в WAV.")
    tts.add_argument("--text", required=True, help="Русская фраза.")
    tts.add_argument("--out", required=True, help="Куда записать WAV.")
    reply = commands.add_parser("reply", help="Ответ .venv-llm и WAV клоном Base.")
    reply.add_argument("--text", required=True, help="Реплика пользователя.")
    reply.add_argument("--out", required=True, help="Куда записать WAV ответа.")
    turn = commands.add_parser("turn", help="Готовый WAV 8 кГц → ответ. Микрофон не открывается.")
    turn.add_argument("--wav", required=True, help="Моно PCM16 WAV, 8000 Гц, уже на диске.")
    turn.add_argument("--out", required=True, help="Куда записать WAV ответа.")
    return parser


def read_pcm16_wav(path: Path) -> tuple[int, ...]:
    """Моно PCM16 8 кГц. Другую частоту не ресемплит."""

    try:
        handle = wave.open(str(path), "rb")
    except FileNotFoundError:
        raise FileNotFoundError(f"Файл не найден: {path}") from None
    except wave.Error as exc:
        raise ValueError(f"{path} не читается как WAV: {exc}") from exc
    with handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if channels != 1 or width != 2 or rate != TONE_SAMPLE_RATE:
        raise ValueError(
            f"Нужен моно PCM16 WAV {TONE_SAMPLE_RATE} Гц. "
            f"В {path.name}: каналов {channels}, байт на сэмпл {width}, {rate} Гц. "
            "Тихого ресемпла нет. Для примера T-One запустите asr --example."
        )
    return pcm16le_to_samples(frames)


def read_tone_example() -> tuple[int, ...]:
    """`tone.read_example_audio()`: audio_short.flac, моно 8 кГц int32. Веса не качает."""

    try:
        module = importlib.import_module("tone")
    except ImportError as exc:
        raise TonePackageError(
            "T-One не установлен. Не используйте pip install tone. "
            f"Ставьте git+https://github.com/voicekit-team/T-one.git@{TONE_GIT_REVISION}"
        ) from exc
    reader = getattr(module, "read_example_audio", None)
    if not callable(reader):
        raise TonePackageError("В пакете tone нет read_example_audio. Нужен voicekit-team/T-one.")
    try:
        audio = reader()
    except ModuleNotFoundError as exc:
        raise TonePackageError(
            "Для --example нужен miniaudio: pip install miniaudio. "
            "В самом T-One это extra demo: poetry install -E demo."
        ) from exc
    return tuple(int(sample) for sample in audio)


def _run_asr(args: argparse.Namespace, settings: Settings) -> int:
    if bool(args.example) == bool(args.wav):
        print("Укажите либо путь к WAV, либо --example, но не оба сразу.", file=sys.stderr)
        return 2
    try:
        samples = read_tone_example() if args.example else read_pcm16_wav(Path(args.wav))
    except (FileNotFoundError, ValueError, TonePackageError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Эта команда скачивает веса. python -m app их не скачивает.")
    print(_asr_download_line(settings.asr_decoder))
    asr = ToneAsr()
    try:
        asr.load(settings)
        phrases = asr.transcribe_offline(samples)
    except (TonePackageError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if not phrases:
        print("Фраз нет.")
        return 0
    for phrase in phrases:
        print(f"{phrase.start_time:.2f}-{phrase.end_time:.2f} {phrase.text}")
    return 0


def _run_tts(args: argparse.Namespace, settings: Settings) -> int:
    return _synthesize_to_wav(args.text, Path(args.out), settings)


def _run_reply(args: argparse.Namespace, settings: Settings) -> int:
    return _reply_from_text(args.text, Path(args.out), settings)


def _run_turn(args: argparse.Namespace, settings: Settings) -> int:
    try:
        samples = read_pcm16_wav(Path(args.wav))
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("turn читает файл. Микрофон не открывается.")
    print(_asr_download_line(settings.asr_decoder))
    asr = ToneAsr()
    try:
        asr.load(settings)
        phrases = asr.transcribe_offline(samples)
    except (TonePackageError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    heard = _join_phrases(phrases)
    if not heard:
        print("Фраз нет. TTS не вызывался.", file=sys.stderr)
        return 1
    print(f"Распознано: {heard}")
    return _reply_from_text(heard, Path(args.out), settings)


def _reply_from_text(text: str, out: Path, settings: Settings) -> int:
    cleaned = text.strip()
    if not cleaned:
        print("Текст пустой.", file=sys.stderr)
        return 2
    if not Path(settings.tts_ref_audio).is_file():
        print(
            f"Запись голоса не найдена: {settings.tts_ref_audio or '(путь пустой)'}. "
            "Задайте CALL_CENTER_TTS_REF_AUDIO. Модель не вызывалась.",
            file=sys.stderr,
        )
        return 2
    try:
        spoken = generate_reply(cleaned, settings)
    except ReplyFailed as exc:
        print(str(exc), file=sys.stderr)
        return exc.code
    print(f"Модель: {spoken}")
    return _synthesize_to_wav(spoken, out, settings)


def _join_phrases(phrases: tuple[object, ...]) -> str:
    parts: list[str] = []
    for phrase in phrases:
        text = getattr(phrase, "text", "")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return " ".join(parts)


def _synthesize_to_wav(text: str, out: Path, settings: Settings) -> int:
    request = request_from_settings(text, settings)
    try:
        validate_request(request)
        if settings.tts_mode == "clone" and not Path(settings.tts_ref_audio).is_file():
            raise TtsRequestError(
                f"Запись голоса не найдена: {settings.tts_ref_audio or '(путь пустой)'}. "
                "Задайте CALL_CENTER_TTS_REF_AUDIO. ref-ru.wav в репозиторий не кладётся."
            )
    except TtsRequestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Эта команда скачивает веса. python -m app их не скачивает.")
    print(_tts_download_line(settings))
    speech = Qwen3Speech()
    try:
        speech.load(settings)
        result = speech.synthesize(request)
        pcm = float_samples_to_pcm16(result.samples)
    except (TtsPackageError, TtsRequestError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(result.sample_rate)
        handle.writeframes(pcm)
    print(f"Записано {out}: {len(result.samples)} сэмплов, {result.sample_rate} Гц.")
    return 0


def _tts_download_line(settings: Settings) -> str:
    if settings.tts_mode == "clone":
        return (
            f"from_pretrained скачает {settings.tts_model_id}. Устройство: {settings.tts_device}. "
            "Режим клона: запись голоса только с диска, синтез целиком после фразы."
        )
    if settings.tts_mode == "custom":
        return (
            f"from_pretrained скачает {settings.tts_model_id}. Устройство: {settings.tts_device}. "
            f"Режим CustomVoice, диктор {settings.tts_speaker}."
        )
    raise RuntimeError(f"Неизвестный режим TTS: {settings.tts_mode}.")


def _asr_download_line(decoder: str) -> str:
    if decoder == "beam_search":
        return f"from_hugging_face скачает {_TONE_REPO}/model.onnx и {_TONE_REPO}/kenlm.bin."
    if decoder == "greedy":
        return f"from_hugging_face скачает только {_TONE_REPO}/model.onnx. kenlm.bin для greedy не качается."
    raise RuntimeError(f"Неизвестный декодер: {decoder}.")


if __name__ == "__main__":
    raise SystemExit(main())
