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
from app.settings import TONE_GIT_REVISION, TONE_SAMPLE_RATE, Settings
from app.tts import Qwen3Speech, SynthesisRequest, TtsPackageError, TtsRequestError, validate_request

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
    print(f"Неизвестная команда: {command}.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.file_run",
        description=(
            "Распознать файл T-One или синтезировать одну фразу. Команда скачивает веса. python -m app их не скачивает."
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
    request = SynthesisRequest(
        text=args.text,
        language=settings.tts_language,
        speaker=settings.tts_speaker,
        model_id=settings.tts_model_id,
    )
    try:
        validate_request(request)
    except TtsRequestError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print("Эта команда скачивает веса. python -m app их не скачивает.")
    print(f"from_pretrained скачает {settings.tts_model_id}. Устройство: {settings.tts_device}.")
    speech = Qwen3Speech()
    try:
        speech.load(settings)
        result = speech.synthesize(request)
        pcm = float_samples_to_pcm16(result.samples)
    except (TtsPackageError, TtsRequestError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    out = Path(args.out)
    with wave.open(str(out), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(result.sample_rate)
        handle.writeframes(pcm)
    print(f"Записано {out}: {len(result.samples)} сэмплов, {result.sample_rate} Гц.")
    return 0


def _asr_download_line(decoder: str) -> str:
    if decoder == "beam_search":
        return f"from_hugging_face скачает {_TONE_REPO}/model.onnx и {_TONE_REPO}/kenlm.bin."
    if decoder == "greedy":
        return f"from_hugging_face скачает только {_TONE_REPO}/model.onnx. kenlm.bin для greedy не качается."
    raise RuntimeError(f"Неизвестный декодер: {decoder}.")


if __name__ == "__main__":
    raise SystemExit(main())
