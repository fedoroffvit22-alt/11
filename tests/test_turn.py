"""Команда turn читает файл. Модели подменены, mlx_lm и from_pretrained не вызываются."""

from __future__ import annotations

import json
import sys
import wave
from pathlib import Path

import pytest
from app.asr import TranscriptPhrase
from app.file_run import main
from app.settings import LOCAL_LLM_ID
from app.tts import SynthesisResult


def test_turn_wrong_rate_does_not_load(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "wide.wav"
    _write_wav(wav, rate=16000, samples=(0, 1))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("модель вызвана на чужой частоте")

    monkeypatch.setattr("app.file_run.ToneAsr.load", refuse)
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", refuse)
    monkeypatch.setattr("app.reply.subprocess.run", refuse)
    monkeypatch.setattr("app.llm.load_selected_model", refuse)
    code = main(["turn", "--wav", str(wav), "--out", str(tmp_path / "ответ.wav")])
    assert code == 2
    assert "mlx_lm" not in sys.modules


def test_turn_without_phrases_does_not_call_tts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    wav = tmp_path / "in.wav"
    _write_wav(wav, rate=8000, samples=(1, -1, 0))
    seen: dict[str, object] = {}

    class FakeAsr:
        def load(self, settings: object) -> None:
            seen["asr"] = settings.load_weights  # type: ignore[attr-defined]

        def transcribe_offline(self, samples: tuple[int, ...]) -> tuple[TranscriptPhrase, ...]:
            seen["samples"] = samples
            return ()

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("TTS или mlx вызваны без фраз")

    monkeypatch.setattr("app.file_run.ToneAsr", FakeAsr)
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", refuse)
    monkeypatch.setattr("app.reply.subprocess.run", refuse)
    monkeypatch.setattr("app.llm.load_selected_model", refuse)
    monkeypatch.setattr("app.tts.Qwen3Speech.load", refuse)
    code = main(["turn", "--wav", str(wav), "--out", str(tmp_path / "ответ.wav")])
    assert code == 1
    assert seen["asr"] is True
    assert seen["samples"] == (1, -1, 0)
    assert "mlx_lm" not in sys.modules


def test_turn_joins_phrases_and_replies_without_pretrained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    wav = tmp_path / "in.wav"
    _write_wav(wav, rate=8000, samples=(1, 2))
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"")
    fake_python = tmp_path / "python"
    _write_fake_python(fake_python)
    seen: dict[str, object] = {}

    class FakeAsr:
        def load(self, _settings: object) -> None:
            seen["asr"] = True

        def transcribe_offline(self, _samples: tuple[int, ...]) -> tuple[TranscriptPhrase, ...]:
            return (
                TranscriptPhrase(text="алло", start_time=0.0, end_time=0.3),
                TranscriptPhrase(text="вы меня слышите", start_time=0.3, end_time=0.8),
            )

    class FakeSpeech:
        def load(self, _settings: object) -> None:
            seen["tts"] = True

        def synthesize(self, request: object) -> SynthesisResult:
            seen["spoken"] = request.text  # type: ignore[attr-defined]
            seen["mode"] = request.mode  # type: ignore[attr-defined]
            return SynthesisResult(sample_rate=24000, samples=(0.0, 0.5))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("from_pretrained или mlx_lm в проектном процессе")

    monkeypatch.setenv("CALL_CENTER_TTS_REF_AUDIO", str(ref))
    monkeypatch.setattr("app.file_run.ToneAsr", FakeAsr)
    monkeypatch.setattr("app.file_run.Qwen3Speech", FakeSpeech)
    monkeypatch.setattr("app.asr.ToneAsr.load", refuse)
    monkeypatch.setattr("app.tts.Qwen3Speech.load", refuse)
    monkeypatch.setattr("app.llm.load_selected_model", refuse)
    monkeypatch.setattr("app.reply.llm_python_path", lambda: fake_python)
    out = tmp_path / "ответ.wav"
    assert main(["turn", "--wav", str(wav), "--out", str(out)]) == 0
    output = capsys.readouterr().out
    heard_at = output.index("Распознано: алло вы меня слышите")
    model_at = output.index("Модель: Да, я здесь!")
    saved_at = output.index("Записано ")
    assert heard_at < model_at < saved_at
    assert seen["asr"] is True
    assert seen["tts"] is True
    assert seen["spoken"] == "Да, я здесь!"
    assert seen["mode"] == "clone"
    payload = json.loads(Path(str(fake_python) + ".in").read_text())
    assert payload["user"] == "алло вы меня слышите"
    assert payload["model"] == LOCAL_LLM_ID
    with wave.open(str(out), "rb") as handle:
        assert handle.getframerate() == 24000
        assert handle.getnframes() == 2
    assert "mlx_lm" not in sys.modules


def _write_wav(path: Path, *, rate: int, samples: tuple[int, ...]) -> None:
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples))


def _write_fake_python(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, os, sys",
                "from pathlib import Path",
                "if os.environ.get('HF_HUB_OFFLINE') != '1':",
                "    raise SystemExit(1)",
                "raw = sys.stdin.read()",
                "Path(sys.argv[0] + '.in').write_text(raw)",
                "sys.stdout.write('<think>скрыто</think>Да, я здесь! 😊')",
                "",
            ]
        )
    )
    path.chmod(0o755)
