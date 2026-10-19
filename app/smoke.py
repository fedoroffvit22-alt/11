"""Смоук без скачивания весов и без открытия аудиоустройства."""

from __future__ import annotations

from app.asr import probe_tone
from app.pipeline import (
    FULL_DUPLEX_SLOTS,
    LOCAL_AUDIO_SYMBOLS,
    PipelineSkeleton,
    build_skeleton,
    probe_symbols,
)
from app.settings import Settings
from app.tts import probe_tts


def main() -> int:
    settings = Settings.from_env()
    tone = probe_tone()
    tts = probe_tts()
    local_audio = probe_symbols(LOCAL_AUDIO_SYMBOLS)
    skeleton = build_skeleton()

    print("Голосовой агент: смоук каркаса.")
    print(f"Загрузка весов: {'включена настройкой' if settings.load_weights else 'выключена'}.")
    print("Смоук веса не скачивает и микрофон не открывает.")
    print(f"ASR T-One: {tone.status}. {tone.detail}")
    print(f"TTS Qwen3: {tts.status}. {tts.detail}")
    print(f"Pipecat local audio: {local_audio.status}. {local_audio.detail}")
    if isinstance(skeleton, PipelineSkeleton):
        print(
            "Каркас Pipecat собран: "
            f"вход {skeleton.audio_in_sample_rate} Гц, "
            f"выход {skeleton.audio_out_sample_rate} Гц, "
            f"процессоров в коротком пайплайне {skeleton.processor_count}."
        )
    else:
        print(f"Каркас Pipecat: {skeleton.status}. {skeleton.detail}")
    print("Слоты полного дуплекса (ещё не процессоры): " + ", ".join(FULL_DUPLEX_SLOTS) + ".")
    if settings.load_weights:
        print("CALL_CENTER_LOAD_WEIGHTS=1. Этот смоук всё равно не вызывает from_hugging_face и from_pretrained.")
    return 0
