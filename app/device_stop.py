"""Остановка звукового устройства не должна держать процесс бесконечно."""

from __future__ import annotations

import threading
from collections.abc import Callable


def wait_for_device_stop(stop: Callable[[], None], *, timeout: float) -> bool:
    """Дождаться stop(). False значит, что вызов не вернулся и дальше его не ждут.

    Сам stop() идёт в демоническом потоке. Зависший PyAudio_StopStream не держит процесс.
    """

    finished = threading.Event()

    def run() -> None:
        try:
            stop()
        except Exception as exc:
            print(f"СТОП: устройство не закрылось: {exc}", flush=True)
        finally:
            finished.set()

    threading.Thread(target=run, daemon=True).start()
    return finished.wait(timeout)


def limit_device_stop(part: object, *, timeout: float) -> None:
    """Подменить stop_stream и close: закрытие пайплайна не ждёт устройство вечно."""

    stream = getattr(part, "_in_stream", None)
    if stream is None:
        stream = getattr(part, "_out_stream", None)
    if stream is None:
        return
    original_stop = stream.stop_stream
    original_close = stream.close
    state = {"stopped": False}

    def stop_stream() -> None:
        state["stopped"] = wait_for_device_stop(original_stop, timeout=timeout)

    def close() -> None:
        if not state["stopped"]:
            return
        wait_for_device_stop(original_close, timeout=timeout)

    stream.stop_stream = stop_stream
    stream.close = close
