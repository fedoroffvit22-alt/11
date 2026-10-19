"""Нарезка PCM под контракт T-One. Без numpy и без весов.

Повторяет `tone.demo.read_audio.read_stream_audio` и `StreamingCTCPipeline`:
8 кГц, моно, чанк 2400 сэмплов (300 мс), паддинг 2400 с обеих сторон перед
стримингом. `forward_offline` паддит сам, поэтому офлайн-вход не паддим здесь.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.settings import TONE_CHUNK_SAMPLES, TONE_PADDING_SAMPLES, TONE_SAMPLE_RATE

PCM16_MIN = -32768
PCM16_MAX = 32767


def tail_pad_width(length: int, chunk_size: int = TONE_CHUNK_SAMPLES) -> int:
    """Сколько нулей дописать, чтобы длина делилась на чанк. Как `-n % chunk` в NumPy."""

    if chunk_size <= 0:
        raise ValueError("Размер чанка должен быть положительным.")
    if length < 0:
        raise ValueError("Длина аудио не может быть отрицательной.")
    return (-length) % chunk_size


def validate_pcm16(samples: Sequence[int]) -> None:
    for index, sample in enumerate(samples):
        if not isinstance(sample, int) or isinstance(sample, bool):
            raise TypeError(f"Сэмпл {index} должен быть int, получен {type(sample).__name__}.")
        if sample < PCM16_MIN or sample > PCM16_MAX:
            raise ValueError(f"Сэмпл {index}={sample} вне диапазона int16 [{PCM16_MIN}; {PCM16_MAX}].")


def pcm16le_to_samples(data: bytes) -> tuple[int, ...]:
    if len(data) % 2:
        raise ValueError("PCM16LE должен содержать чётное число байт.")
    return tuple(int.from_bytes(data[i : i + 2], "little", signed=True) for i in range(0, len(data), 2))


def pad_for_streaming(
    samples: Sequence[int],
    *,
    padding: int = TONE_PADDING_SAMPLES,
) -> tuple[int, ...]:
    validate_pcm16(samples)
    if padding < 0:
        raise ValueError("Паддинг не может быть отрицательным.")
    return (0,) * padding + tuple(samples) + (0,) * padding


def iter_tone_chunks(
    samples: Sequence[int],
    *,
    chunk_size: int = TONE_CHUNK_SAMPLES,
    pad_edges: bool = True,
) -> tuple[tuple[int, ...], ...]:
    """Нарезать аудио так же, как стриминговый пример T-One.

    `pad_edges=True` — путь `read_stream_audio`: паддинг, затем чанки ровно
    `chunk_size`, хвост дополняется нулями. Для `forward_offline` паддинг
    выключен: метод пайплайна добавляет его сам.
    """

    prepared = pad_for_streaming(samples) if pad_edges else tuple(samples)
    if not pad_edges:
        validate_pcm16(prepared)
    if chunk_size <= 0:
        raise ValueError("Размер чанка должен быть положительным.")

    chunks: list[tuple[int, ...]] = []
    for start in range(0, len(prepared), chunk_size):
        piece = prepared[start : start + chunk_size]
        missing = chunk_size - len(piece)
        if missing:
            piece = piece + (0,) * missing
        chunks.append(piece)
    return tuple(chunks)


def require_tone_chunk(samples: Sequence[int], *, chunk_size: int = TONE_CHUNK_SAMPLES) -> tuple[int, ...]:
    validate_pcm16(samples)
    if len(samples) != chunk_size:
        raise ValueError(f"Чанк T-One должен быть длины {chunk_size}, получено {len(samples)}.")
    return tuple(samples)


def chunk_duration_seconds(chunk_size: int = TONE_CHUNK_SAMPLES, sample_rate: int = TONE_SAMPLE_RATE) -> float:
    if sample_rate <= 0:
        raise ValueError("Частота дискретизации должна быть положительной.")
    return chunk_size / sample_rate


class Pcm16ChunkBuffer:
    """Копит PCM16 и отдаёт куски ровно `chunk_samples`. Хвост остаётся в буфере."""

    def __init__(self, chunk_samples: int = TONE_CHUNK_SAMPLES) -> None:
        if chunk_samples <= 0:
            raise ValueError("Размер чанка должен быть положительным.")
        self._chunk_samples = chunk_samples
        self._pending: list[int] = []

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    def extend(self, samples: Sequence[int]) -> tuple[tuple[int, ...], ...]:
        validate_pcm16(samples)
        self._pending.extend(samples)
        ready: list[tuple[int, ...]] = []
        size = self._chunk_samples
        while len(self._pending) >= size:
            ready.append(tuple(self._pending[:size]))
            del self._pending[:size]
        return tuple(ready)

    def take_padded_remainder(self) -> tuple[int, ...] | None:
        if not self._pending:
            return None
        missing = (-len(self._pending)) % self._chunk_samples
        chunk = tuple(self._pending) + (0,) * missing
        self._pending.clear()
        return chunk


def float_samples_to_pcm16(samples: Sequence[float]) -> bytes:
    """Волна в диапазоне [-1, 1] → PCM16LE. Пустой вход — ошибка, не тишина."""

    if not samples:
        raise ValueError("Волна пустая.")
    pieces: list[bytes] = []
    for sample in samples:
        value = float(sample)
        if value > 1.0:
            value = 1.0
        elif value < -1.0:
            value = -1.0
        integer = int(round(value * 32767))
        if integer > PCM16_MAX:
            integer = PCM16_MAX
        elif integer < PCM16_MIN:
            integer = PCM16_MIN
        pieces.append(integer.to_bytes(2, "little", signed=True))
    return b"".join(pieces)
