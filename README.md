# Голосовой агент колл-центра

Локальный каркас русской речи: T-One, Qwen3-TTS, локальная LLM-заглушка и перебивание по стратегии хода Pipecat 1.13. Телефонии, Asterisk и CRM здесь нет. Веса моделей смоук не скачивает. Живой микрофон по-прежнему только на Mac.

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

Ожидание на машине без моделей и без `pipecat-ai`: обе команды заканчиваются с кодом 0 и пишут, что T-One, Qwen3-TTS и Pipecat отсутствуют. Локальная LLM по умолчанию выключена (`off`) и ничего не генерирует. Если Pipecat установлен, смоук собирает пайплайн с T-One, заглушкой LLM и Qwen3-TTS, но `from_hugging_face` и `from_pretrained` не вызывает.

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

5. Локальный LLM ~4B в этом срезе не ставится. В Pipecat 1.13 нет модели в процессе без ключа и без демона: `QwenLLMService` — DashScope, `OLLamaLLMService` ждёт запущенный сервер. Пока бэкенд `stub` или `off`. Живой ответ модели — позже, отдельно от этого смоука.
6. Микрофонный диалог — после файла на Mac. `LocalAudioTransport` отсюда не создаётся: Core Audio, MPS и микрофон не проверялись. Перебивание в каркасе уже включено стратегией `VADUserTurnStartStrategy`: кадр VAD «пользователь заговорил» шлёт `InterruptionFrame`, и TTS сбрасывает текущий звук. `SileroVADAnalyzer` смоук не создаёт, он сразу читает ONNX.

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
| `CALL_CENTER_LLM_BACKEND` | `off` | `off` — модель молчит с ошибкой; `stub` — тестовые русские фразы без весов |

Частота выхода пайплайна — 24 кГц. Если `generate_custom_voice` вернёт другую частоту, `Qwen3TtsService` пересчитывает PCM16 ресемплером Pipecat (`SOXRAudioResampler`) до этой частоты. Динамик при этом не открывается.

Секретов нет. Облачный ключ DashScope не нужен и не читается.

## Где код

- `app/audio.py` — чанки 2400 сэмплов, 8 кГц, паддинг как у стримингового примера T-One, перевод волны TTS в PCM16.
- `app/asr.py` — `forward` / `forward_offline` / `finalize` и стриминговый движок. `from_hugging_face` только внутри `load()`.
- `app/tts.py` — `generate_custom_voice`. Без модели метод бросает ошибку, тишину не подставляет.
- `app/llm.py` — русский системный промпт и потоковый интерфейс. `off` и `stub` не качают Qwen.
- `app/pipecat_services.py` — `ToneSttService`, `Qwen3TtsService` (с согласованием частоты) и `LocalLlmService`. Импорт модуля требует `pipecat-ai`.
- `app/pipeline.py` — если пакет установлен, пайплайн из T-One, агрегатора пользователя со стратегией перебивания, локальной LLM, Qwen3-TTS и агрегатора ассистента. Микрофон и раннер не запускаются. Без пакета смоук остаётся зелёным.
