from app.audio import (
    Pcm16ChunkBuffer,
    chunk_duration_seconds,
    float_samples_to_pcm16,
    iter_tone_chunks,
    pad_for_streaming,
    pcm16le_to_samples,
    require_tone_chunk,
    tail_pad_width,
)
from app.settings import TONE_CHUNK_SAMPLES, TONE_PADDING_SAMPLES


def test_tail_pad_matches_numpy_modulo() -> None:
    assert tail_pad_width(100) == (-100) % TONE_CHUNK_SAMPLES
    assert tail_pad_width(TONE_CHUNK_SAMPLES) == 0
    assert tail_pad_width(0) == 0


def test_streaming_chunks_are_padded_and_fixed_width() -> None:
    chunks = iter_tone_chunks((1, -2, 3))
    assert len(chunks) == 3
    assert all(len(chunk) == TONE_CHUNK_SAMPLES for chunk in chunks)
    padded = pad_for_streaming((1, -2, 3))
    assert padded[TONE_PADDING_SAMPLES : TONE_PADDING_SAMPLES + 3] == (1, -2, 3)
    assert chunks[1][0:3] == (1, -2, 3)


def test_offline_input_is_not_padded_by_the_helper() -> None:
    chunks = iter_tone_chunks((7,), pad_edges=False)
    assert len(chunks) == 1
    assert chunks[0][0] == 7
    assert chunks[0][1] == 0
    assert sum(1 for sample in chunks[0] if sample) == 1


def test_empty_streaming_audio_is_two_silent_chunks() -> None:
    chunks = iter_tone_chunks(())
    assert len(chunks) == 2
    assert set(chunks[0]) == {0}


def test_pcm16le_round_trip_edges() -> None:
    raw = (0).to_bytes(2, "little", signed=True) + (32767).to_bytes(2, "little", signed=True)
    raw += (-32768).to_bytes(2, "little", signed=True)
    assert pcm16le_to_samples(raw) == (0, 32767, -32768)


def test_require_chunk_rejects_short_buffer() -> None:
    try:
        require_tone_chunk((1, 2, 3))
    except ValueError as exc:
        assert "2400" in str(exc)
    else:
        raise AssertionError("короткий чанк должен отвергаться")


def test_chunk_is_300_milliseconds() -> None:
    assert chunk_duration_seconds() == 0.3


def test_buffer_keeps_a_short_tail_and_pads_it() -> None:
    buffer = Pcm16ChunkBuffer(chunk_samples=4)
    assert buffer.extend((1, 2)) == ()
    assert buffer.pending_count == 2
    ready = buffer.extend((3, 4, 5))
    assert ready == ((1, 2, 3, 4),)
    assert buffer.pending_count == 1
    tail = buffer.take_padded_remainder()
    assert tail == (5, 0, 0, 0)
    assert buffer.take_padded_remainder() is None


def test_float_wave_becomes_pcm16_and_empty_is_rejected() -> None:
    raw = float_samples_to_pcm16((0.0, 1.0, -1.0))
    assert pcm16le_to_samples(raw) == (0, 32767, -32767)
    try:
        float_samples_to_pcm16(())
    except ValueError as exc:
        assert "пустая" in str(exc)
    else:
        raise AssertionError("пустая волна не должна становиться тишиной")
