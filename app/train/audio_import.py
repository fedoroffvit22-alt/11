"""Файл звонка из CRM. Расшифровка обязательна: эта команда веса не качает."""

from __future__ import annotations

import wave
from pathlib import Path

from app.settings import TONE_SAMPLE_RATE, Settings
from app.train.crm_parse import CrmImportError, parse_crm
from app.train.library import Library
from app.train.model import CrmCall


class AudioImportError(ValueError):
    """WAV в библиотеку не попал."""


def import_recorded_call(
    library: Library,
    wav: Path,
    transcript: Path | None,
    settings: Settings,
) -> CrmCall:
    _require_wav(wav)
    if transcript is None or not transcript.is_file():
        if settings.load_weights:
            raise AudioImportError(
                "Рядом с WAV нет расшифровки. Распознавание файла здесь не вызывает from_hugging_face."
            )
        raise AudioImportError(
            "Рядом с WAV нет расшифровки. Положите JSON или текст. Веса этой командой не скачиваются."
        )
    try:
        raw = transcript.read_text(encoding="utf-8")
        calls = parse_crm(raw)
    except (OSError, UnicodeError, CrmImportError) as exc:
        raise AudioImportError(str(exc)) from exc
    if len(calls) != 1:
        raise AudioImportError("Рядом с одним WAV должна быть одна карточка.")
    call = calls[0]
    _require_safe_id(call.id)
    library.add_text(raw)
    _keep_audio(library, wav, call.id)
    return library.calls[call.id]


def _require_wav(path: Path) -> None:
    if not path.is_file():
        raise AudioImportError(f"Файл не найден: {path}")
    try:
        handle = wave.open(str(path), "rb")
    except wave.Error as exc:
        raise AudioImportError(f"{path} не читается как WAV: {exc}") from exc
    with handle:
        channels = handle.getnchannels()
        width = handle.getsampwidth()
        rate = handle.getframerate()
    if channels not in (1, 2) or width != 2 or rate != TONE_SAMPLE_RATE:
        raise AudioImportError(
            f"Нужен PCM16 WAV {TONE_SAMPLE_RATE} Гц, моно или стерео "
            f"(левый канал — оператор, правый — клиент). "
            f"В {path.name}: каналов {channels}, байт на сэмпл {width}, {rate} Гц. Тихого ресемпла нет."
        )


def _require_safe_id(call_id: str) -> None:
    if not call_id or call_id in {".", ".."} or "/" in call_id or "\\" in call_id:
        raise AudioImportError(f"Идентификатор карточки не годится для имени файла: {call_id!r}.")


def _keep_audio(library: Library, wav: Path, call_id: str) -> None:
    if library.path is None:
        return
    folder = library.path.parent / "audio"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{call_id}.wav").write_bytes(wav.read_bytes())
