"""Команда reply не импортирует mlx_lm и не грузит TTS без референса и интерпретатора."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import wave
from pathlib import Path
from types import ModuleType

import pytest
from app.file_run import main
from app.reply import clean_reply_text
from app.settings import LOCAL_LLM_ID
from app.smoke import main as smoke_main
from app.tts import SynthesisResult


def test_clean_reply_drops_think_block_and_emoji() -> None:
    raw = "<think>секрет\nне говорить</think>\nДа, я здесь! 😊"
    assert clean_reply_text(raw) == "Да, я здесь!"
    assert clean_reply_text("Привет 👋 мир") == "Привет мир"
    assert "<think>" not in clean_reply_text("до <think>ещё")


def test_reply_without_reference_does_not_call_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("модель или TTS вызваны без референса")

    monkeypatch.delenv("CALL_CENTER_TTS_REF_AUDIO", raising=False)
    monkeypatch.setattr("app.reply.subprocess.run", boom)
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", boom)
    monkeypatch.setattr("app.llm.load_selected_model", boom)
    code = main(["reply", "--text", "алло", "--out", str(tmp_path / "ответ.wav")])
    assert code == 2
    assert "mlx_lm" not in sys.modules


def test_reply_without_llm_python_does_not_load_tts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"")

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("TTS загружен без интерпретатора .venv-llm")

    monkeypatch.setenv("CALL_CENTER_TTS_REF_AUDIO", str(ref))
    monkeypatch.setattr("app.reply.llm_python_path", lambda: tmp_path / "missing-python")
    monkeypatch.setattr("app.file_run.Qwen3Speech.load", boom)
    monkeypatch.setattr("app.llm.load_selected_model", boom)
    code = main(["reply", "--text", "алло", "--out", str(tmp_path / "ответ.wav")])
    assert code == 1
    assert "mlx_lm" not in sys.modules


def test_reply_strips_text_then_synthesizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ref = tmp_path / "ref.wav"
    ref.write_bytes(b"")
    fake_python = tmp_path / "python"
    _write_fake_python(fake_python)
    seen: dict[str, object] = {}

    class FakeSpeech:
        def load(self, settings: object) -> None:
            seen["loaded"] = settings.llm_model_id  # type: ignore[attr-defined]

        def synthesize(self, request: object) -> SynthesisResult:
            seen["text"] = request.text  # type: ignore[attr-defined]
            seen["ref_text"] = request.ref_text  # type: ignore[attr-defined]
            seen["ref_audio"] = request.ref_audio  # type: ignore[attr-defined]
            return SynthesisResult(sample_rate=24000, samples=(0.0, 0.25))

    monkeypatch.setenv("CALL_CENTER_TTS_REF_AUDIO", str(ref))
    monkeypatch.setattr("app.reply.llm_python_path", lambda: fake_python)
    monkeypatch.setattr("app.file_run.Qwen3Speech", FakeSpeech)
    monkeypatch.setattr("app.llm.load_selected_model", _refuse_inprocess_mlx)
    out = tmp_path / "ответ.wav"
    assert main(["reply", "--text", "алло вы меня слышите", "--out", str(out)]) == 0
    assert seen["text"] == "Да, я здесь!"
    assert seen["ref_audio"] == str(ref)
    assert seen["ref_text"] == "Алло, это колл центр, чем могу помочь."
    payload = json.loads(Path(str(fake_python) + ".in").read_text())
    assert payload["model"] == LOCAL_LLM_ID
    assert payload["user"] == "алло вы меня слышите"
    assert "по-русски" in payload["system"]
    with wave.open(str(out), "rb") as handle:
        assert handle.getnframes() == 2
    assert "mlx_lm" not in sys.modules


def test_smoke_does_not_import_mlx(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.llm.load_selected_model", _refuse_inprocess_mlx)
    monkeypatch.setattr("app.tts.Qwen3Speech.load", _refuse_inprocess_mlx)
    assert smoke_main() == 0
    assert "mlx_lm" not in sys.modules


def test_generate_script_calls_mlx_api(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    seen: dict[str, object] = {}

    class Tokenizer:
        has_chat_template = True

        def apply_chat_template(self, messages: list[dict[str, str]], tokenize: bool = False, **_kwargs: object) -> str:
            seen["messages"] = messages
            seen["tokenize"] = tokenize
            return "PROMPT"

    def load(path: str) -> tuple[object, Tokenizer]:
        seen["path"] = path
        return object(), Tokenizer()

    def generate(model: object, tokenizer: object, prompt: str, verbose: bool = False, max_tokens: int = 256) -> str:
        seen["prompt"] = prompt
        seen["verbose"] = verbose
        seen["max_tokens"] = max_tokens
        return "сырой"

    fake = ModuleType("mlx_lm")
    fake.load = load  # type: ignore[attr-defined]
    fake.generate = generate  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mlx_lm", fake)
    script = _load_script()
    payload = json.dumps(
        {"model": LOCAL_LLM_ID, "system": "системный", "user": "алло", "max_tokens": 256},
        ensure_ascii=False,
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert script.main() == 0
    assert capsys.readouterr().out == "сырой"
    assert seen["path"] == LOCAL_LLM_ID
    assert seen["verbose"] is False
    assert seen["prompt"] == "PROMPT"
    messages = seen["messages"]
    assert isinstance(messages, list)
    assert messages[1]["content"] == "алло"


def _refuse_inprocess_mlx(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("mlx_lm импортирован в проектном процессе")


def _write_fake_python(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json, os, sys",
                "from pathlib import Path",
                "if os.environ.get('HF_HUB_OFFLINE') != '1':",
                "    sys.stderr.write('no offline')",
                "    raise SystemExit(1)",
                "raw = sys.stdin.read()",
                "Path(sys.argv[0] + '.in').write_text(raw)",
                "data = json.loads(raw)",
                "if data['model'] != 'mlx-community/Qwen3-4B-Instruct-2507-4bit':",
                "    raise SystemExit(1)",
                "sys.stdout.write('<think>секрет</think>Да, я здесь! 😊')",
                "",
            ]
        )
    )
    path.chmod(0o755)


def _load_script() -> object:
    path = Path(__file__).resolve().parents[1] / "scripts" / "mlx_generate.py"
    spec = importlib.util.spec_from_file_location("mlx_generate_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Не удалось загрузить {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
