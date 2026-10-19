from types import SimpleNamespace

import pytest
from app.asr import ModelNotLoaded as AsrNotLoaded
from app.asr import ToneAsr, classify_tone_module, phrases_from_objects, probe_tone
from app.pipeline import CORE_SYMBOLS, LOCAL_AUDIO_SYMBOLS, SymbolProbe, build_skeleton
from app.settings import Settings
from app.smoke import main
from app.tts import ModelNotLoaded as TtsNotLoaded
from app.tts import Qwen3Speech, SynthesisRequest, TtsRequestError, probe_tts, validate_request


class _FakePipeline:
    from_hugging_face = staticmethod(lambda **kwargs: None)
    forward = staticmethod(lambda *args, **kwargs: None)
    forward_offline = staticmethod(lambda *args, **kwargs: None)
    finalize = staticmethod(lambda *args, **kwargs: None)


class _Decoder:
    BEAM_SEARCH = "beam_search"
    GREEDY = "greedy"


def test_tone_classifier_accepts_real_shape() -> None:
    module = SimpleNamespace(StreamingCTCPipeline=_FakePipeline, DecoderType=_Decoder)
    assert classify_tone_module(module) == "ok"


def test_tone_classifier_rejects_unrelated_package() -> None:
    assert classify_tone_module(SimpleNamespace()) == "wrong_package"


def test_phrase_mapping_strips_text() -> None:
    raw = SimpleNamespace(text="  привет  ", start_time=1.5, end_time=2.0)
    phrase = phrases_from_objects([raw])[0]
    assert phrase.text == "привет"
    assert phrase.start_time == 1.5


def test_asr_and_tts_refuse_to_load_without_flag() -> None:
    settings = Settings.from_env({})
    with pytest.raises(AsrNotLoaded):
        ToneAsr().load(settings)
    with pytest.raises(TtsNotLoaded):
        Qwen3Speech().load(settings)


def test_transcribe_without_load_is_an_error() -> None:
    with pytest.raises(AsrNotLoaded):
        ToneAsr().transcribe_offline((0, 1, 2))


def test_tts_validation_and_no_fake_audio() -> None:
    with pytest.raises(TtsRequestError):
        validate_request(SynthesisRequest(text="   "))
    with pytest.raises(TtsRequestError):
        validate_request(SynthesisRequest(text="Алло", speaker="Robot"))
    with pytest.raises(TtsRequestError, match="instruction"):
        validate_request(SynthesisRequest(text="Алло", instruct="говори спокойно"))
    request = SynthesisRequest(text="Алло, это колл-центр.")
    validate_request(request)
    with pytest.raises(TtsNotLoaded):
        Qwen3Speech().synthesize(request)


def test_probes_skip_when_packages_absent() -> None:
    tone = probe_tone()
    tts = probe_tts()
    assert tone.status in {"missing", "wrong_package", "ok"}
    assert tts.status in {"missing", "wrong_package", "ok"}
    if tone.status == "missing":
        assert "не установлен" in tone.detail
    skeleton = build_skeleton()
    if isinstance(skeleton, SymbolProbe):
        assert skeleton.status in {"missing", "partial"}


def test_symbol_table_matches_verified_modules() -> None:
    modules = {name: module for name, module in CORE_SYMBOLS}
    assert modules["Pipeline"] == "pipecat.pipeline.pipeline"
    assert modules["PipelineWorker"] == "pipecat.pipeline.worker"
    assert modules["WorkerRunner"] == "pipecat.workers.runner"
    assert modules["SileroVADAnalyzer"] == "pipecat.audio.vad.silero"
    assert modules["LLMContextAggregatorPair"].endswith("llm_response_universal")
    assert LOCAL_AUDIO_SYMBOLS[0] == ("LocalAudioTransport", "pipecat.transports.local.audio")


def test_smoke_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CALL_CENTER_LOAD_WEIGHTS", "1")
    assert main() == 0
