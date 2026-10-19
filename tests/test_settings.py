import pytest
from app.settings import ASR_DECODERS, TTS_MODEL_0_6B_CUSTOM, Settings


def test_defaults_do_not_load_weights() -> None:
    settings = Settings.from_env({})
    assert settings.load_weights is False
    assert settings.tts_flash_attention is False
    assert settings.asr_decoder == "beam_search"
    assert settings.tts_model_id == TTS_MODEL_0_6B_CUSTOM
    assert settings.tts_language == "Russian"
    assert settings.tts_device == "cpu"
    assert settings.llm_backend == "off"
    assert settings.audio_out_sample_rate == 24000


def test_flags_and_decoder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALL_CENTER_LOAD_WEIGHTS", "1")
    monkeypatch.setenv("CALL_CENTER_ASR_DECODER", "greedy")
    monkeypatch.setenv("CALL_CENTER_TTS_DEVICE", "cuda")
    settings = Settings.from_env()
    assert settings.load_weights is True
    assert settings.asr_decoder == "greedy"
    assert settings.tts_device == "cuda"
    assert "greedy" in ASR_DECODERS


def test_rejects_unknown_decoder() -> None:
    with pytest.raises(ValueError, match="CALL_CENTER_ASR_DECODER"):
        Settings.from_env({"CALL_CENTER_ASR_DECODER": "whisper"})


def test_llm_backend_rejects_ollama_and_dashscope() -> None:
    with pytest.raises(ValueError, match="CALL_CENTER_LLM_BACKEND"):
        Settings.from_env({"CALL_CENTER_LLM_BACKEND": "ollama"})
    with pytest.raises(ValueError, match="CALL_CENTER_LLM_BACKEND"):
        Settings.from_env({"CALL_CENTER_LLM_BACKEND": "qwen"})
