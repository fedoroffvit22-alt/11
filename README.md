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

## Прогон файла на Mac

Живой прогон на этой Linux VM не делался: пакеты ниже не ставились и веса не скачивались. Команды сверены с voicekit-team/T-one `3c5b6c015038173840e62cea99e10cdb1c759116` и с `qwen-tts` 0.1.1. Копия инструкции: её нет в git, текст для Виталия продублирован рядом с планом.

`pip install tone` запрещён. На PyPI это другой пакет. T-One ставится только из git.

KenLM — жёсткая зависимость T-One. На Mac перед сборкой обычно нужен `xcode-select --install`. Официальный путь репозитория — клон и `poetry install -E demo`. Ниже один venv рядом с этим приложением, поэтому команда — `pip install "tone @ git+..."`.

Шаг 1. Файл, без микрофона:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pip install "tone @ git+https://github.com/voicekit-team/T-one.git@3c5b6c015038173840e62cea99e10cdb1c759116"
pip install miniaudio
pip install "qwen-tts==0.1.1"
python -m app.file_run asr --example
CALL_CENTER_TTS_DEVICE=cpu python -m app.file_run tts --text "Алло, это колл-центр." --out фраза.wav
```

`miniaudio` нужен только для `--example`: `tone.read_example_audio()` читает `tone/demo/audio_examples/audio_short.flac` и приводит его к моно 8 кГц int32. Свой файл без miniaudio: `python -m app.file_run asr путь.wav` — только моно PCM16 8000 Гц, другая частота будет ошибкой, тихого ресемпла нет.

`python -m app` и `pytest` эту команду не вызывают и веса не качают, даже при `CALL_CENTER_LOAD_WEIGHTS=1`. Качает только явный `python -m app.file_run`.

Что скачивается:

- ASR, декодер по умолчанию `beam_search`: `StreamingCTCPipeline.from_hugging_face` тянет `t-tech/T-one` `model.onnx` и `kenlm.bin`.
- `CALL_CENTER_ASR_DECODER=greedy` качает только `model.onnx`. Зависимость пакета от KenLM при сборке остаётся.
- TTS: `Qwen3TTSModel.from_pretrained` качает `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`. Официальный quickstart — `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` на CUDA с flash-attn. Здесь пин 0.6B и устройство `cpu`. Прогона на MPS не было. Размер чекпоинта смотрите на карточке Hugging Face.

Шаг 2, после того как файл уже распознался и фраза записалась. На этой VM не запускалось: микрофон, `SileroVADAnalyzer`, `WorkerRunner`, `LocalAudioTransport`.

```bash
brew install portaudio
pip install "pipecat-ai[local]==1.13.0"
```

Extra ставит PyAudio. Без portaudio импорт `LocalAudioTransport` падает, а конструктор открывает устройство. `SileroVADAnalyzer()` сразу читает свой ONNX. `WorkerRunner` нужен, чтобы реально крутить пайплайн. Эти четыре вещи — следующий шаг, не часть команд файла.

Локальный LLM ~4B в этом срезе не ставится. `QwenLLMService` — DashScope, `OLLamaLLMService` ждёт запущенный сервер. Пока бэкенд `stub` или `off`.

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
- `app/file_run.py` — единственная команда, которая вызывает `load()`: `python -m app.file_run`. Смоук её не импортирует.
