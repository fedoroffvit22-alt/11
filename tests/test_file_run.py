"""Команда файла не качает веса, пока её явно не запустили. Здесь load подменён."""

from __future__ import annotations

import subprocess
import sys
import wave
from pathlib import Path

import pytest
from app.asr import TranscriptPhrase
from app.file_run import build_parser, main, read_pcm16_wav
from app.tts import SynthesisResult


def test_import_and_parse_do_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("load вызван при разборе аргументов")

    monkeypatch.setattr("app.file_run.ToneAsr.load", refuse)
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", refuse)
    build_parser().parse_args(["asr", "--example"])
    build_parser().parse_args(["tts", "--text", "Алло", "--out", "фраза.wav"])


def test_smoke_does_not_import_file_run() -> None:
    code = "import sys\nfrom app.smoke import main\nassert main() == 0\nassert 'app.file_run' not in sys.modules\n"
    result = subprocess.run([sys.executable, "-c", code], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_asr_wav_loads_only_inside_main(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav = tmp_path / "in.wav"
    _write_wav(wav, rate=8000, samples=(1, -1, 0))
    seen: dict[str, object] = {}

    class FakeAsr:
        def load(self, settings: object) -> None:
            seen["load_weights"] = settings.load_weights  # type: ignore[attr-defined]

        def transcribe_offline(self, samples: tuple[int, ...]) -> tuple[TranscriptPhrase, ...]:
            seen["samples"] = samples
            return (TranscriptPhrase(text="алло", start_time=0.0, end_time=0.3),)

    monkeypatch.setenv("CALL_CENTER_LOAD_WEIGHTS", "0")
    monkeypatch.setattr("app.file_run.ToneAsr", FakeAsr)
    assert main(["asr", str(wav)]) == 0
    assert seen["load_weights"] is True
    assert seen["samples"] == (1, -1, 0)
    output = capsys.readouterr().out
    assert "model.onnx" in output
    assert "kenlm.bin" in output
    assert "алло" in output


def test_greedy_mentions_only_onnx(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav = tmp_path / "in.wav"
    _write_wav(wav, rate=8000, samples=(0,))

    class FakeAsr:
        def load(self, settings: object) -> None:
            return None

        def transcribe_offline(self, samples: tuple[int, ...]) -> tuple[TranscriptPhrase, ...]:
            return ()

    monkeypatch.setenv("CALL_CENTER_ASR_DECODER", "greedy")
    monkeypatch.setattr("app.file_run.ToneAsr", FakeAsr)
    assert main(["asr", str(wav)]) == 0
    output = capsys.readouterr().out
    assert "только t-tech/T-one/model.onnx" in output
    assert "kenlm.bin для greedy не качается" in output


def test_example_reads_then_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_example() -> tuple[int, ...]:
        return (4, 5)

    class FakeAsr:
        def load(self, settings: object) -> None:
            seen["load_weights"] = settings.load_weights  # type: ignore[attr-defined]

        def transcribe_offline(self, samples: tuple[int, ...]) -> tuple[TranscriptPhrase, ...]:
            seen["samples"] = samples
            return ()

    monkeypatch.setattr("app.file_run.read_tone_example", fake_example)
    monkeypatch.setattr("app.file_run.ToneAsr", FakeAsr)
    assert main(["asr", "--example"]) == 0
    assert seen["load_weights"] is True
    assert seen["samples"] == (4, 5)


def test_wrong_rate_does_not_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "wide.wav"
    _write_wav(wav, rate=16000, samples=(0, 1))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("load не должен вызываться на чужой частоте")

    monkeypatch.setattr("app.file_run.ToneAsr.load", refuse)
    assert main(["asr", str(wav)]) == 2
    with pytest.raises(ValueError, match="16000"):
        read_pcm16_wav(wav)


def test_asr_needs_exactly_one_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "in.wav"
    _write_wav(wav, rate=8000, samples=(0,))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("load не должен вызываться без одного источника")

    monkeypatch.setattr("app.file_run.ToneAsr.load", refuse)
    assert main(["asr"]) == 2
    assert main(["asr", str(wav), "--example"]) == 2


def test_tts_writes_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, object] = {}
    ref = tmp_path / "local-ref.wav"
    ref.write_bytes(b"")

    class FakeSpeech:
        def load(self, settings: object) -> None:
            seen["load_weights"] = settings.load_weights  # type: ignore[attr-defined]
            seen["model"] = settings.tts_model_id  # type: ignore[attr-defined]

        def synthesize(self, request: object) -> SynthesisResult:
            seen["text"] = request.text  # type: ignore[attr-defined]
            seen["mode"] = request.mode  # type: ignore[attr-defined]
            seen["ref_audio"] = request.ref_audio  # type: ignore[attr-defined]
            return SynthesisResult(sample_rate=24000, samples=(0.0, 0.5, -0.5))

    monkeypatch.setenv("CALL_CENTER_TTS_REF_AUDIO", str(ref))
    monkeypatch.setattr("app.file_run.Qwen3Speech", FakeSpeech)
    out = tmp_path / "фраза.wav"
    assert main(["tts", "--text", "Да, я вас слышу.", "--out", str(out)]) == 0
    assert seen["load_weights"] is True
    assert seen["model"] == "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
    assert seen["mode"] == "clone"
    assert seen["ref_audio"] == str(ref)
    assert seen["text"] == "Да, я вас слышу."
    output = capsys.readouterr().out
    assert "Qwen/Qwen3-TTS-12Hz-0.6B-Base" in output
    assert "Aiden" not in output
    with wave.open(str(out), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 3


def test_clone_without_ref_file_does_not_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("load не должен вызываться без записи голоса")

    monkeypatch.delenv("CALL_CENTER_TTS_REF_AUDIO", raising=False)
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", refuse)
    assert main(["tts", "--text", "Да, я вас слышу.", "--out", str(tmp_path / "фраза.wav")]) == 2


def test_tts_empty_text_does_not_load(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("load не должен вызываться на пустом тексте")

    monkeypatch.setattr("app.file_run.Qwen3Speech.load", refuse)
    assert main(["tts", "--text", "   ", "--out", "фраза.wav"]) == 2


def test_missing_tts_args_return_2() -> None:
    assert main(["tts"]) == 2


def _write_wav(path: Path, *, rate: int, samples: tuple[int, ...]) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))
