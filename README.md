# Голосовой агент колл-центра

Локальный каркас русской речи: нарезка аудио под T-One, интерфейс Qwen3-TTS и список реальных классов Pipecat 1.13. Телефонии, Asterisk и CRM здесь нет. Веса моделей смоук не скачивает.

Пакеты сверены с исходниками, а не с черновыми примерами. В частности, `pip install tone` ставить нельзя: на PyPI это другой проект. T-One ставится из [voicekit-team/T-one](https://github.com/voicekit-team/T-one) (коммит `3c5b6c015038173840e62cea99e10cdb1c759116`).

## Окружение

Нужен Python 3.11 или новее.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app
pytest
```

Ожидание на машине без моделей: оба команды заканчиваются с кодом 0 и пишут, что T-One, Qwen3-TTS и локальный звук Pipecat отсутствуют. Это нормально.

## Что запускать позже, на Mac

Эта проверка писалась на Linux без микрофона. На MacBook шаги такие:

1. Поставить Python 3.11+ и создать venv, как выше.
2. Для микрофона Pipecat: `brew install portaudio`, затем `pip install "pipecat-ai[local]==1.13.0"`. Extra тянет PyAudio. Без portaudio импорт `LocalAudioTransport` падает.
3. ASR, когда понадобится реальный прогон:

```bash
pip install "tone @ git+https://github.com/voicekit-team/T-one.git@3c5b6c015038173840e62cea99e10cdb1c759116"
```

Сборка `kenlm` требует компилятор. Beam search дополнительно скачает `kenlm.bin` с Hugging Face (`t-tech/T-one`). Офлайн-декодер `greedy` языковой модели не качает, но зависимость пакета от KenLM остаётся.

4. TTS:

```bash
pip install "qwen-tts==0.1.1"
```

Официальный пример грузит `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` на CUDA (`device_map="cuda:0"`, `dtype=torch.bfloat16`, `attn_implementation="flash_attention_2"`). Прогона на MPS и на CPU в этом репозитории не было. Чекпоинт 0.6B большой: смотрите размер на карточке Hugging Face перед скачиванием. Флаг `CALL_CENTER_LOAD_WEIGHTS=1` разрешает коду вызвать загрузку; команда `python -m app` даже с этим флагом веса не качает.

5. Микрофонный диалог и замер задержки — после того как ASR и TTS один раз отработали на файле. Core Audio и MPS отсюда не проверялись.

## Полезные переменные

| Переменная | По умолчанию | Смысл |
| --- | --- | --- |
| `CALL_CENTER_LOAD_WEIGHTS` | `0` | `1` разрешает `load()`, который ходит в Hugging Face |
| `CALL_CENTER_ASR_DECODER` | `beam_search` | `greedy` или `beam_search` |
| `CALL_CENTER_TTS_MODEL` | `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice` | идентификатор HF |
| `CALL_CENTER_TTS_SPEAKER` | `Ryan` | один из 9 голосов CustomVoice |
| `CALL_CENTER_TTS_LANGUAGE` | `Russian` | имя языка как в Qwen3-TTS |
| `CALL_CENTER_TTS_DEVICE` | `cpu` | `cpu`, `cuda` или `mps` |
| `CALL_CENTER_TTS_FLASH_ATTN` | `0` | `1` добавляет `flash_attention_2`, только для CUDA |

Секретов нет. Облачный ключ DashScope не нужен и не читается.

## Где код

- `app/audio.py` — чанки 2400 сэмплов, 8 кГц, паддинг как у стримингового примера T-One.
- `app/asr.py` — `forward` / `forward_offline` / `finalize`, только после `load()`.
- `app/tts.py` — `generate_custom_voice`. Без модели метод бросает ошибку.
- `app/pipeline.py` — импорты Pipecat и короткий пайплайн из контекстных агрегаторов, если пакет установлен. Транспорт с микрофоном не создаётся.
