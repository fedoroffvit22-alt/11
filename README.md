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

Живой прогон на этой Linux VM не делался: пакеты ниже не ставились и веса не скачивались. Команды сверены с voicekit-team/T-one `3c5b6c015038173840e62cea99e10cdb1c759116` и с `qwen-tts` 0.1.1.

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
CALL_CENTER_TTS_DEVICE=cpu CALL_CENTER_TTS_REF_AUDIO="/путь/на/mac/ref-ru.wav" \
  python -m app.file_run tts --text "Да, я вас слышу." --out фраза.wav
```

Принят клон `Qwen/Qwen3-TTS-12Hz-0.6B-Base`: `create_voice_clone_prompt` и `generate_voice_clone`, язык `Russian`. Запись голоса локальная, путь только в `CALL_CENTER_TTS_REF_AUDIO`, `ref-ru.wav` в git нет. Текст референса по умолчанию: «Алло, это колл центр, чем могу помочь.» Ответ сейчас синтезируется целиком на CPU после фразы. CustomVoice Aiden голосом по умолчанию не стал: скорость была лучше, акцент не принят.

`miniaudio` нужен только для `--example`: `tone.read_example_audio()` читает `tone/demo/audio_examples/audio_short.flac` и приводит его к моно 8 кГц int32. Свой файл без miniaudio: `python -m app.file_run asr путь.wav` — только моно PCM16 8000 Гц, другая частота будет ошибкой, тихого ресемпла нет.

`python -m app` и `pytest` эту команду не вызывают и веса не качают, даже при `CALL_CENTER_LOAD_WEIGHTS=1`. Качает только явный `python -m app.file_run`.

Что скачивается:

- ASR, декодер по умолчанию `beam_search`: `StreamingCTCPipeline.from_hugging_face` тянет `t-tech/T-one` `model.onnx` и `kenlm.bin`.
- `CALL_CENTER_ASR_DECODER=greedy` качает только `model.onnx`. Зависимость пакета от KenLM при сборке остаётся.
- TTS по умолчанию: `from_pretrained` качает `Qwen/Qwen3-TTS-12Hz-0.6B-Base` и клонирует локальную запись. Официальный quickstart Qwen — `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` на CUDA с flash-attn. CustomVoice 0.6B включается отдельно: `CALL_CENTER_TTS_MODE=custom`. Прогона на MPS не было. Размер чекпоинта смотрите на карточке Hugging Face.

Шаг 2, после того как файл уже распознался и фраза записалась. На этой VM не запускалось: микрофон, `SileroVADAnalyzer`, `WorkerRunner`, `LocalAudioTransport`.

```bash
brew install portaudio
pip install "pipecat-ai[local]==1.13.0"
```

Extra ставит PyAudio. Без portaudio импорт `LocalAudioTransport` падает, а конструктор открывает устройство. `SileroVADAnalyzer()` сразу читает свой ONNX. `WorkerRunner` нужен, чтобы реально крутить пайплайн. Эти четыре вещи — следующий шаг, не часть команд файла.

Локальная модель на Mac с 16 ГиБ: `mlx-community/Qwen3-4B-Instruct-2507-4bit`, 4-bit, 2.12 ГиБ. Идентификатора `Qwen/Qwen3-4B-Instruct` на Hugging Face нет. Пробный ответ: «Да, я здесь! Как я могу вам помочь?».

Два окружения, потому что `mlx-lm` в проектном venv ломал `transformers`, нужные `qwen-tts`. Проектный `.venv` пишет голос клоном Base. Отдельный `.venv-llm` (Python 3.11, `mlx-lm==0.32.2`, в git не входит) только считает текст скриптом `scripts/mlx_generate.py`. Проектный процесс `mlx_lm` не импортирует: скрипт запускается subprocess, stdin — JSON, у ребёнка `HF_HUB_OFFLINE=1`.

```bash
CALL_CENTER_TTS_REF_AUDIO="/путь/на/mac/ref-ru.wav" \
  python -m app.file_run reply --text "алло вы меня слышите" --out ответ.wav
```

Перед синтезом из ответа убираются блок `<think>` и эмодзи. Нет файла референса — код 2, модель не вызывается. Нет `.venv-llm/bin/python` — код 1, TTS не грузится. Смоук и pytest веса не грузят. DashScope по-прежнему запрещён. Бэкенд смоука остаётся `off`.

`turn` читает уже лежащий на диске файл, не микрофон:

```bash
CALL_CENTER_TTS_REF_AUDIO="/путь/на/mac/ref-ru.wav" \
  python -m app.file_run turn --wav путь.wav --out ответ.wav
```

Файл должен быть моно PCM16, 8000 Гц. Другая частота — ошибка и код 2, без тихого ресемпла. Если фраз нет, код 1 и TTS не вызывается. Иначе текст фраз склеивается и идёт тем же путём, что `reply`: `.venv-llm` и клон.

## Полезные переменные

| Переменная | По умолчанию | Смысл |
| --- | --- | --- |
| `CALL_CENTER_LOAD_WEIGHTS` | `0` | `1` разрешает `load()`, который ходит в Hugging Face |
| `CALL_CENTER_ASR_DECODER` | `beam_search` | `greedy` или `beam_search` |
| `CALL_CENTER_TTS_MODE` | `clone` | `clone` — принятый клон Base; `custom` — CustomVoice |
| `CALL_CENTER_TTS_MODEL` | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | для `custom` по умолчанию чекпоинт CustomVoice |
| `CALL_CENTER_TTS_REF_AUDIO` | пусто | путь к записи голоса на машине, не файл репозитория |
| `CALL_CENTER_TTS_REF_TEXT` | `Алло, это колл центр, чем могу помочь.` | расшифровка этой записи |
| `CALL_CENTER_TTS_SPEAKER` | `Ryan` | только режим `custom`; Aiden не по умолчанию |
| `CALL_CENTER_TTS_LANGUAGE` | `Russian` | имя языка как в Qwen3-TTS |
| `CALL_CENTER_TTS_DEVICE` | `cpu` | `cpu`, `cuda` или `mps` |
| `CALL_CENTER_TTS_FLASH_ATTN` | `0` | `1` добавляет `flash_attention_2`, только для CUDA |
| `CALL_CENTER_LLM_BACKEND` | `off` | `off` — модель молчит с ошибкой; `stub` — тестовые русские фразы без весов |
| `CALL_CENTER_LLM_MODEL` | `mlx-community/Qwen3-4B-Instruct-2507-4bit` | выбранный id; само чтение модель не грузит |

Частота выхода пайплайна — 24 кГц. Если синтез вернёт другую частоту, `Qwen3TtsService` пересчитывает PCM16 ресемплером Pipecat (`SOXRAudioResampler`) до этой частоты. Динамик при этом не открывается.

Секретов нет. Облачный ключ DashScope не нужен и не читается.

## Где код

- `app/audio.py` — чанки 2400 сэмплов, 8 кГц, паддинг как у стримингового примера T-One, перевод волны TTS в PCM16.
- `app/asr.py` — `forward` / `forward_offline` / `finalize` и стриминговый движок. `from_hugging_face` только внутри `load()`.
- `app/tts.py` — клон Base (`create_voice_clone_prompt`, `generate_voice_clone`) и режим CustomVoice. Без модели метод бросает ошибку, тишину не подставляет. `from_pretrained` только внутри `load()`.
- `app/llm.py` — русский системный промпт. `off` и `stub` не качают Qwen. Смоук `mlx_lm` не импортирует.
- `app/reply.py` — команда `reply`: subprocess в `.venv-llm`, затем очистка текста.
- `scripts/mlx_generate.py` — генерация в отдельном окружении, `mlx-lm==0.32.2`.
- `app/pipecat_services.py` — `ToneSttService`, `Qwen3TtsService` (с согласованием частоты) и `LocalLlmService`. Импорт модуля требует `pipecat-ai`.
- `app/pipeline.py` — если пакет установлен, пайплайн из T-One, агрегатора пользователя со стратегией перебивания, локальной LLM, Qwen3-TTS и агрегатора ассистента. Микрофон и раннер не запускаются. Без пакета смоук остаётся зелёным.
- `app/file_run.py` — `asr`, `tts`, `reply` и `turn`. `turn` читает файл, не микрофон. Смоук этот модуль не импортирует.
