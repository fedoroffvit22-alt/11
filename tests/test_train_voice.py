"""Голосовой ход репетиции без весов, без tone и без qwen_tts."""

import sys
from pathlib import Path

import pytest
from app.settings import Settings
from app.train.library import Library
from app.train.paths import sample_calls_path
from app.train.rehearsal import start_rehearsal
from app.train.speak_turn import speak_case
from app.train.voice import Heard, Spoken, play_operator_audio


class ScriptedVoice:
    def __init__(self, heard: str) -> None:
        self._heard = heard
        self.spoken: list[Spoken] = []
        self.speak_calls = 0

    def hear(self, pcm16_8k: bytes) -> Heard:
        assert pcm16_8k == b"\x00\x00"
        return Heard(self._heard)

    def speak(self, text: str) -> Spoken:
        self.speak_calls += 1
        spoken = Spoken(text=text, wav=b"")
        self.spoken.append(spoken)
        return spoken


def test_operator_audio_becomes_a_client_line_without_loading_models() -> None:
    library = Library(None)
    library.add_text(sample_calls_path().read_text(encoding="utf-8"))
    rehearsal = start_rehearsal(library.case("salon-marina"), library.ordered())
    port = ScriptedVoice(heard="Добрый день, это Алексей, звоню по онлайн-записи для салона.")
    view = play_operator_audio(rehearsal, port, b"\x00\x00")
    assert any("Дорого" in turn["text"] for turn in view["transcript"])
    assert port.spoken[-1].text.startswith("Дорого")
    assert "tone" not in sys.modules
    assert "qwen_tts" not in sys.modules


def test_speak_without_voice_reference_exits_before_models(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = speak_case(
        case_id="salon-marina",
        wav=tmp_path / "in.wav",
        out=tmp_path / "out.wav",
        settings=Settings.from_env({}),
        library=Library(None),
    )
    assert code == 2
    assert "CALL_CENTER_TTS_REF_AUDIO" in capsys.readouterr().err
    assert "tone" not in sys.modules
    assert "qwen_tts" not in sys.modules
    assert not (tmp_path / "out.wav").exists()


def test_empty_recognition_does_not_synthesize() -> None:
    library = Library(None)
    library.add_text(sample_calls_path().read_text(encoding="utf-8"))
    rehearsal = start_rehearsal(library.case("salon-marina"), library.ordered())
    port = ScriptedVoice(heard="   ")
    play_operator_audio(rehearsal, port, b"\x00\x00")
    assert port.speak_calls == 0
