"""Одна реплика Qwen в окружении `.venv-llm`, не в проектном процессе.

Интерпретатор: Python 3.11, пакет `mlx-lm==0.32.2`.
Модель: `mlx-community/Qwen3-4B-Instruct-2507-4bit`.
stdin — JSON `{"model", "system", "user", "max_tokens"}`, stdout — сырой текст.
Родитель ставит `HF_HUB_OFFLINE=1`. Проектный `python -m app` этот файл не импортирует.

`mlx_lm` импортируется внутри `main`, а не при загрузке файла: пакета нет
в проектном окружении, и смоук не должен его трогать.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        print(f"stdin не JSON: {exc}", file=sys.stderr)
        return 1
    model_id = payload.get("model")
    system = payload.get("system")
    user = payload.get("user")
    max_tokens = payload.get("max_tokens", 256)
    if not isinstance(model_id, str) or not isinstance(system, str) or not isinstance(user, str):
        print("JSON должен содержать строки model, system и user.", file=sys.stderr)
        return 1
    if not isinstance(max_tokens, int) or max_tokens == 0:
        print("max_tokens должен быть ненулевым целым.", file=sys.stderr)
        return 1

    from mlx_lm import generate, load

    model, tokenizer = load(model_id)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if getattr(tokenizer, "has_chat_template", False):
        prompt = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    else:
        prompt = f"{system}\n{user}"
    text = generate(model, tokenizer, prompt, verbose=False, max_tokens=max_tokens)
    if not isinstance(text, str):
        print("mlx_lm.generate вернул не строку.", file=sys.stderr)
        return 1
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
