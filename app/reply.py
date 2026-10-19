"""Ответ: текст считает `.venv-llm`, этот процесс `mlx_lm` не импортирует.

Скрипт `scripts/mlx_generate.py` запускается через subprocess.
stdin — JSON, в окружении ребёнка `HF_HUB_OFFLINE=1`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from app.llm import RUSSIAN_SYSTEM_PROMPT
from app.settings import LOCAL_LLM_ID, Settings

MLX_LM_VERSION = "0.32.2"
LLM_PYTHON_RELATIVE = Path(".venv-llm") / "bin" / "python"
_THINK_CLOSED = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_THINK_OPEN = re.compile(r"<think>.*", re.IGNORECASE | re.DOTALL)
_EMOJI = re.compile(
    "["
    "\U0001f600-\U0001f64f"
    "\U0001f300-\U0001f5ff"
    "\U0001f680-\U0001f6ff"
    "\U0001f700-\U0001f77f"
    "\U0001f780-\U0001f7ff"
    "\U0001f800-\U0001f8ff"
    "\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001faff"
    "\U00002702-\U000027b0"
    "\U000024c2-\U0001f251"
    "\U0001f1e6-\U0001f1ff"
    "\u2600-\u26ff"
    "\u2700-\u27bf"
    "\ufe0f"
    "\u200d"
    "]+",
    flags=re.UNICODE,
)


class ReplyFailed(RuntimeError):
    """Текст ответа не получен. TTS при этом запускать нельзя."""

    def __init__(self, message: str, code: int = 1) -> None:
        super().__init__(message)
        self.code = code


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def llm_python_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / LLM_PYTHON_RELATIVE


def script_path(root: Path | None = None) -> Path:
    return (root or repo_root()) / "scripts" / "mlx_generate.py"


_SALE = re.compile(r"прода")
_BUY = re.compile(r"покуп|купи|куплю")
_SENTENCE = re.compile(r"[^.!?]+(?:[.!?]+|$)")
_HEARING_TURNS = frozenset(
    {
        "как меня слышно",
        "меня слышно",
        "как слышно",
        "слышно меня",
        "вы меня слышно",
        "как вы меня слышно",
        "слышно",
    }
)
_SALE_REPLY = "Понял, вы хотите продать. Уточните, что именно продаёте."
_BUY_REPLY = "Понял, вы хотите купить. Уточните, что именно покупаете."
_HEARING_REPLY = "Да, я вас слышу."


def clean_reply_text(raw: str) -> str:
    """Убрать блок `<think>` и эмодзи перед синтезом."""

    text = _THINK_CLOSED.sub(" ", raw)
    text = _THINK_OPEN.sub(" ", text)
    text = _EMOJI.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def shape_spoken_reply(user_text: str, model_text: str) -> str:
    """Короткий ответ до TTS. Продажа и покупка не подменяются надеждой на промпт."""

    user = clean_reply_text(user_text).casefold()
    model = clean_reply_text(model_text)
    sale = _mentions(_SALE, user)
    buy = _mentions(_BUY, user)
    if sale and not buy:
        if _mentions(_SALE, model) and not _mentions(_BUY, model):
            return _two_sentences(model)
        return _SALE_REPLY
    if buy and not sale:
        if _mentions(_BUY, model) and not _mentions(_SALE, model):
            return _two_sentences(model)
        return _BUY_REPLY
    if _is_hearing_turn(user):
        return _HEARING_REPLY
    return _two_sentences(model)


def _is_hearing_turn(user: str) -> bool:
    """Ход про слышимость целиком, а не обрывок «слышно» внутри другой реплики."""

    text = re.sub(r"[^0-9a-zа-яё\s]+", " ", user.casefold())
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(?:алло|здравствуйте)\s+", "", text)
    return text in _HEARING_TURNS


def _mentions(pattern: re.Pattern[str], text: str) -> bool:
    return pattern.search(text.casefold()) is not None


def _two_sentences(text: str) -> str:
    parts = [part.strip() for part in _SENTENCE.findall(text) if part.strip()]
    spoken = " ".join(parts[:2]).strip()
    if spoken and spoken[-1] not in ".!?":
        spoken += "."
    return spoken


def generate_reply(user_text: str, settings: Settings, *, python_path: Path | None = None) -> str:
    """Спросить выбранную Qwen в соседнем интерпретаторе. Веса здесь не грузятся."""

    python = python_path or llm_python_path()
    script = script_path()
    if not python.is_file():
        raise ReplyFailed(
            f"Нет интерпретатора {python}. Текст считает отдельное окружение .venv-llm "
            f"(Python 3.11, mlx-lm=={MLX_LM_VERSION}). TTS не запускался.",
            code=1,
        )
    if not script.is_file():
        raise ReplyFailed(f"Нет скрипта {script}.", code=1)
    payload = json.dumps(
        {
            "model": settings.llm_model_id or LOCAL_LLM_ID,
            "system": RUSSIAN_SYSTEM_PROMPT,
            "user": user_text.strip(),
            "max_tokens": 256,
        },
        ensure_ascii=False,
    )
    env = os.environ.copy()
    env["HF_HUB_OFFLINE"] = "1"
    completed = subprocess.run(
        [str(python), str(script)],
        input=payload,
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "scripts/mlx_generate.py завершился с ошибкой."
        raise ReplyFailed(detail, code=1)
    cleaned = clean_reply_text(completed.stdout)
    if not cleaned:
        raise ReplyFailed("Модель вернула пустой ответ после очистки. TTS не запускался.", code=1)
    spoken = shape_spoken_reply(user_text, cleaned)
    if not spoken:
        raise ReplyFailed("Модель вернула пустой ответ после очистки. TTS не запускался.", code=1)
    return spoken
