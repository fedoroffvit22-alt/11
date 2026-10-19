"""Закрытие сеанса не ждёт зависший PyAudio. Микрофон, сеть и веса не используются."""

from __future__ import annotations

import threading
import time
import types

from app.device_stop import limit_device_stop, wait_for_device_stop


def test_device_stop_does_not_wait_forever() -> None:
    release = threading.Event()

    def hang() -> None:
        release.wait(30)

    started = time.monotonic()
    finished = wait_for_device_stop(hang, timeout=0.2)
    elapsed = time.monotonic() - started
    release.set()
    assert finished is False
    assert elapsed < 1.0
    assert wait_for_device_stop(lambda: None, timeout=1.0) is True


def test_pipeline_close_skips_a_device_that_does_not_stop() -> None:
    release = threading.Event()

    class Stream:
        def __init__(self) -> None:
            self.closed = False

        def stop_stream(self) -> None:
            release.wait(30)

        def close(self) -> None:
            self.closed = True

    stream = Stream()
    part = types.SimpleNamespace(_in_stream=stream, _out_stream=None)
    limit_device_stop(part, timeout=0.2)
    started = time.monotonic()
    stream.stop_stream()
    elapsed = time.monotonic() - started
    release.set()
    stream.close()
    assert elapsed < 1.0
    assert stream.closed is False
