# Голосовой агент колл-центра

Локальный каркас русской речи: T-One, клон Qwen3-TTS и локальная Qwen через отдельный `.venv-llm`. Телефонии и Asterisk здесь нет. Веса моделей смоук не скачивает. Живой ход уже был одной командой `turn` после записи. Живой сеанс лежит в `scripts/live_session.py`, перебивание выключено, смоук его не запускает.

Репетиция звонка — отдельный режим: человек говорит как оператор, клиент отвечает фразами из выгрузки CRM. Запуск: `python -m app.train`, страница `http://127.0.0.1:8765/`. Микрофон не открывается, веса не читаются. Формат выгрузки — в конце файла.

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

Ожидание на машине без моделей и без `pipecat-ai`: обе команды заканчиваются с кодом 0 и пишут, что T-One, Qwen3-TTS и Pipecat отсутствуют. Смоук не запускает `.venv-llm` и не открывает референс. Если Pipecat установлен, смоук собирает пайплайн с T-One, `LocalLlmService` и клоном Qwen3-TTS, но не стартует его: `from_hugging_face` и `from_pretrained` не вызываются.

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

Перед синтезом из ответа убираются блок `<think>` и эмодзи, текст режется до одного-двух предложений. Если в реплике есть продажа и нет покупки, ответ говорит о продаже и не спрашивает, что купить; покупка без продажи — наоборот. Нет файла референса — код 2, модель не вызывается. Нет `.venv-llm/bin/python` — код 1, TTS не грузится. Смоук и pytest веса не грузят. DashScope по-прежнему запрещён. Бэкенд смоука остаётся `off`.

`turn` читает уже лежащий на диске файл, не микрофон:

```bash
CALL_CENTER_TTS_REF_AUDIO="/путь/на/mac/ref-ru.wav" \
  python -m app.file_run turn --wav путь.wav --out ответ.wav
```

Файл должен быть моно PCM16, 8000 Гц. Другая частота — ошибка и код 2, без тихого ресемпла. Если фраз нет, код 1 и TTS не вызывается. Иначе текст фраз склеивается и идёт тем же путём, что `reply`: `.venv-llm` и клон. Живой ход на Mac уже был этой командой после записи.

`LocalLlmService` в каркасе Pipecat зовёт тот же `generate_reply`: отдельный `.venv-llm` и `scripts/mlx_generate.py`, без импорта `mlx_lm` в проектном процессе. `Qwen3TtsService` синтезирует клон Base, путь к записи только из настроек. Нет интерпретатора или файла референса — `ErrorFrame`, не тишина. Сборка каркаса и `python -m app` эти вызовы не делают, поэтому смоук без `.venv-llm` и без записи не падает. `WorkerRunner` и `LocalAudioTransport` в репозитории не стартуют.

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
| `CALL_CENTER_LLM_BACKEND` | `off` | `off` и `stub` в `app/llm.py` не качают веса. Сервис Pipecat зовёт `generate_reply`, не эту заглушку |
| `CALL_CENTER_LLM_MODEL` | `mlx-community/Qwen3-4B-Instruct-2507-4bit` | выбранный id; само чтение модель не грузит |

Частота выхода пайплайна — 24 кГц. Если синтез вернёт другую частоту, `Qwen3TtsService` пересчитывает PCM16 ресемплером Pipecat (`SOXRAudioResampler`) до этой частоты. Динамик при этом не открывается.

Секретов нет. Облачный ключ DashScope не нужен и не читается.

## Где код

- `app/audio.py` — чанки 2400 сэмплов, 8 кГц, паддинг как у стримингового примера T-One, перевод волны TTS в PCM16.
- `app/asr.py` — `forward` / `forward_offline` / `finalize` и стриминговый движок. `from_hugging_face` только внутри `load()`.
- `app/tts.py` — клон Base (`create_voice_clone_prompt`, `generate_voice_clone`) и режим CustomVoice. Без модели метод бросает ошибку, тишину не подставляет. `from_pretrained` только внутри `load()`.
- `app/llm.py` — русский системный промпт. `off` и `stub` не качают Qwen. Смоук `mlx_lm` не импортирует.
- `app/reply.py` — команда `reply` и путь, которым пользуется `LocalLlmService`: subprocess в `.venv-llm`, затем очистка и правка текста до TTS.
- `scripts/mlx_generate.py` — генерация в отдельном окружении, `mlx-lm==0.32.2`.
- `app/pipecat_services.py` — `ToneSttService`, `Qwen3TtsService` (клон Base, референс из настроек) и `LocalLlmService` (тот же `generate_reply`). Импорт модуля требует `pipecat-ai`. Нет референса или `.venv-llm` — ошибка, не тишина.
- `app/pipeline.py` — если пакет установлен, пайплайн из T-One, агрегатора пользователя со стратегией перебивания, локальной LLM и клона Qwen3-TTS. Объекты собираются, микрофон и раннер не запускаются. Без пакета смоук остаётся зелёным.
- `app/file_run.py` — `asr`, `tts`, `reply` и `turn`. `turn` читает файл, не микрофон. Смоук этот модуль не импортирует.
- `app/train/` — репетиция звонка. `python -m app.train` поднимает страницу, `import` разбирает выгрузку, `audio` кладёт WAV рядом с расшифровкой, `report` пишет CSV занятия. T-One и Qwen этот пакет импортирует только команда `speak`.

## Репетиция звонка

Оператор — человек. Клиент снимает трубку и дальше говорит репликами из загруженной карточки: сначала повод звонка, потом возражения в том порядке, в каком они прозвучали в CRM. Пока возражение не сказано, страница его не показывает. Почему облачный голос, живой OAuth CRM и дообучение весов сюда не входят — в `docs/superpowers/plans/2026-10-29-negotiation-trainer.md`.

Голосовой ход — `play_operator_audio` в `app/train/voice.py`: распознанный текст идёт в ту же репетицию, новые реплики клиента уходят в синтез. Тест подменяет порт. `pytest` и `python -m app` этот ход не связывают с T-One и Qwen3-TTS. На Mac явная команда `python -m app.train speak --case ИД --wav путь.wav --out ответ.wav` читает моно PCM16 8000 Гц и требует `CALL_CENTER_TTS_REF_AUDIO`. Нет файла референса — код 2, `from_pretrained` не вызывается.

Запись из CRM кладётся той же карточкой: `python -m app.train audio --wav путь.wav --transcript расшифровка.json`. WAV — моно PCM16 8000 Гц либо стерео, левый канал оператор, правый клиент. Без расшифровки команда отвечает ошибкой и библиотеку не меняет. Этот файл она не распознаёт, даже при `CALL_CENTER_LOAD_WEIGHTS=1`. Другая частота — ошибка, тихого ресемпла нет. Копия лежит рядом с библиотекой в `audio/` и в git не входит.

Уровень на странице и в `POST /api/sessions` (`level`): `basic` — подсказка до ответа, два промаха; `medium` — подсказка после ответа, два промаха; `hard` — подсказки нет, один промах завершает звонок.

Закрытый звонок дописывается одной строкой в `sessions.jsonl` рядом с библиотекой. Повтор того же закрытия строку не дублирует. Сводка: `python -m app.train report --out занятие.csv`. Колонки: `case_id`, `result`, `handled`, `spoken`, `objections`. Несколько возражений в одной ячейке разделены точкой с запятой.

Разбор реплики идёт по двум источникам. Первый — сама карточка: скидку и сумму можно называть только если они уже были у оператора в этом звонке. Второй — корпус: реплика, после которой звонок закончился договорённостью или перезвоном, считается рабочей; похожая реплика из отказа — нет. Это не дообучение Qwen. Веса не скачиваются и не меняются.

Два слабых ответа подряд на одно возражение — клиент кладёт трубку. Закрытые возражения кончаются конкретным шагом: прислать условия сегодня.

```bash
python -m app.train
python -m app.train import examples/crm/sample-calls.json
python -m app.train audio --wav звонок.wav --transcript звонок.json
python -m app.train report --out занятие.csv
```

Библиотека пишется в `data/train/library.json` и в git не входит. Учебные звонки лежат в `examples/crm/sample-calls.json`. На странице их подставляет кнопка «Учебные».

JSON:

```json
{
  "calls": [
    {
      "id": "1042",
      "product": "Онлайн-запись",
      "outcome": "refusal",
      "client_name": "Игорь",
      "company": "Барбершоп Ус",
      "turns": [
        {"speaker": "operator", "text": "Добрый день, Игорь."},
        {"speaker": "client", "text": "Я подумаю."}
      ]
    }
  ]
}
```

Итог: `success`, `refusal`, `callback`, `unknown` или русские «договорённость», «отказ», «перезвон». Роль: оператор или клиент. Тот же звонок можно отдать текстом, несколько карточек разделяет строка `---`:

```text
# id: 1042
# product: Онлайн-запись
# outcome: отказ
# client: Игорь
# company: Барбершоп Ус

Оператор: Добрый день, Игорь.
Клиент: Я подумаю.
```
