"""Стриминговый движок T-One на поддельном пайплайне. Веса и сеть не нужны."""

from types import SimpleNamespace

import pytest
from app.asr import ModelNotLoaded, ToneAsr, ToneStreamEngine
from app.settings import TONE_CHUNK_SAMPLES, TONE_PADDING_SAMPLES


class _ScriptedPipeline:
    def __init__(self) -> None:
        self.forward_chunks: list[tuple[int, ...]] = []
        self.finalized = False

    def forward(self, audio_chunk: object, state: object | None = None, *, is_last: bool = False):
        chunk = tuple(int(sample) for sample in audio_chunk)  # type: ignore[arg-type]
        self.forward_chunks.append(chunk)
        phrase = SimpleNamespace(text="алло", start_time=0.0, end_time=0.3)
        return ([phrase], {"n": len(self.forward_chunks)})

    def finalize(self, state: object | None):
        self.finalized = True
        phrase = SimpleNamespace(text="конец", start_time=0.3, end_time=0.6)
        return ([phrase], None)


def _pcm16(samples: tuple[int, ...]) -> bytes:
    return b"".join(sample.to_bytes(2, "little", signed=True) for sample in samples)


def test_missing_pipeline_errors_once_then_skips() -> None:
    engine = ToneStreamEngine()
    with pytest.raises(ModelNotLoaded, match="не загружен"):
        engine.push_pcm16(_pcm16((1, 2)))
    assert engine.push_pcm16(_pcm16((1, 2))) == ()
    assert engine.finish() == ()


def test_finish_without_audio_does_not_invent_a_phrase() -> None:
    engine = ToneStreamEngine()
    assert engine.finish() == ()
    loaded = ToneStreamEngine(_ScriptedPipeline())
    assert loaded.finish() == ()
    assert loaded.loaded is True


def test_stream_left_pads_then_finalizes() -> None:
    pipeline = _ScriptedPipeline()
    engine = ToneStreamEngine(pipeline)
    spoken = (7,) * 10
    first = engine.push_pcm16(_pcm16(spoken))
    assert [phrase.text for phrase in first] == ["алло"]
    assert pipeline.forward_chunks[0] == (0,) * TONE_PADDING_SAMPLES
    assert all(len(chunk) == TONE_CHUNK_SAMPLES for chunk in pipeline.forward_chunks)
    done = engine.finish()
    assert [phrase.text for phrase in done] == ["алло", "конец"]
    assert pipeline.finalized is True
    tail = pipeline.forward_chunks[-1]
    assert tail[:10] == spoken
    assert set(tail[10:]) == {0}
    assert engine.finish() == ()


def test_open_stream_does_not_load_weights() -> None:
    asr = ToneAsr()

    def refuse(_settings: object) -> None:
        raise AssertionError("from_hugging_face не должен вызываться")

    asr.load = refuse  # type: ignore[method-assign]
    engine = asr.open_stream()
    assert engine.loaded is False
    with pytest.raises(ModelNotLoaded):
        engine.push_pcm16(_pcm16((1,)))
