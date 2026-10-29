"""WAV из CRM становится той же карточкой. Веса не качаются."""

import sys
import wave
from pathlib import Path

import pytest
from app.settings import Settings
from app.train.__main__ import main
from app.train.audio_import import AudioImportError, import_recorded_call
from app.train.library import Library

_TRANSCRIPT = """
{
  "id": "wav-1",
  "product": "Доставка",
  "outcome": "callback",
  "client_name": "Анна",
  "company": "Кафе",
  "turns": [
    {"speaker": "operator", "text": "Анна, добрый день, это доставка."},
    {"speaker": "client", "text": "Пришлите на почту, я посмотрю."}
  ]
}
"""


def _wav(path: Path, *, rate: int = 8000, channels: int = 1) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"\x00\x00" * channels * 8)


def test_transcript_beside_wav_adds_one_case(tmp_path: Path) -> None:
    wav = tmp_path / "call.wav"
    transcript = tmp_path / "call.json"
    _wav(wav)
    transcript.write_text(_TRANSCRIPT, encoding="utf-8")
    library = Library(tmp_path / "library.json")
    call = import_recorded_call(library, wav, transcript, Settings())
    assert call.id == "wav-1"
    assert library.calls["wav-1"].client_name == "Анна"
    stored = tmp_path / "audio" / "wav-1.wav"
    assert stored.is_file()
    assert stored.read_bytes() == wav.read_bytes()


def test_stereo_8k_is_accepted_with_a_transcript(tmp_path: Path) -> None:
    wav = tmp_path / "stereo.wav"
    transcript = tmp_path / "call.json"
    _wav(wav, channels=2)
    transcript.write_text(_TRANSCRIPT, encoding="utf-8")
    call = import_recorded_call(Library(None), wav, transcript, Settings())
    assert call.id == "wav-1"


def test_missing_transcript_does_not_touch_the_library_or_models(tmp_path: Path) -> None:
    wav = tmp_path / "call.wav"
    _wav(wav)
    library = Library(tmp_path / "library.json")
    with pytest.raises(AudioImportError, match="расшифровк"):
        import_recorded_call(library, wav, None, Settings())
    assert library.calls == {}
    assert not library.path.is_file()
    assert "tone" not in sys.modules


def test_cli_reports_a_missing_transcript(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    wav = tmp_path / "call.wav"
    _wav(wav)
    code = main(["--data", str(tmp_path / "library.json"), "audio", "--wav", str(wav)])
    assert code == 1
    assert "расшифровк" in capsys.readouterr().out
    assert "tone" not in sys.modules


def test_wrong_rate_is_rejected(tmp_path: Path) -> None:
    wav = tmp_path / "wide.wav"
    _wav(wav, rate=16000)
    with pytest.raises(AudioImportError, match="8000"):
        import_recorded_call(Library(None), wav, None, Settings())
