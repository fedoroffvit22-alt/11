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


def clean_reply_text(raw: str) -> str:
    """Убрать блок `<think>` и эмодзи перед синтезом."""

    text = _THINK_CLOSED.sub(" ", raw)
    text = _THINK_OPEN.sub(" ", text)
    text = _EMOJI.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


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
    spoken = clean_reply_text(completed.stdout)
    if not spoken:
        raise ReplyFailed("Модель вернула пустой ответ после очистки. TTS не запускался.", code=1)
    return spoken
