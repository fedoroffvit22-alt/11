"""Страница репетиции на локальном порту. Веса не читаются."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest
from app.train.__main__ import main
from app.train.library import Library
from app.train.paths import sample_calls_path
from app.train.server import bind

SAMPLE = sample_calls_path()


def _request(
    port: int,
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, dict[str, object] | str]:
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    raw = response.read()
    status = response.status
    content_type = response.getheader("Content-Type", "")
    connection.close()
    if "json" in content_type:
        parsed = json.loads(raw.decode("utf-8"))
        assert isinstance(parsed, dict)
        return status, parsed
    return status, raw.decode("utf-8")


def test_page_import_call_and_delete(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.json")
    server = bind(library)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        status, page = _request(port, "GET", "/")
        assert status == 200
        assert isinstance(page, str)
        assert "Репетиция" in page

        status, imported = _request(port, "POST", "/api/import", {"text": SAMPLE.read_text(encoding="utf-8")})
        assert status == 200
        assert isinstance(imported, dict)
        assert imported["imported"] == 4
        cases = imported["cases"]
        assert isinstance(cases, list)
        assert len(cases) == 4
        assert "Дорого" not in json.dumps(cases, ensure_ascii=False)

        status, missing = _request(port, "POST", "/api/sessions", {"case_id": "нет"})
        assert status == 404
        assert isinstance(missing, dict)

        status, session = _request(port, "POST", "/api/sessions", {"case_id": "salon-marina"})
        assert status == 200
        assert isinstance(session, dict)
        assert "Дорого" not in json.dumps(session, ensure_ascii=False)
        session_id = session["id"]
        assert isinstance(session_id, str)

        status, turned = _request(
            port,
            "POST",
            f"/api/sessions/{session_id}/turn",
            {"text": "Добрый день, это Алексей, звоню по онлайн-записи для салона."},
        )
        assert status == 200
        assert isinstance(turned, dict)
        assert "Дорого" in json.dumps(turned, ensure_ascii=False)

        status, ended = _request(port, "POST", f"/api/sessions/{session_id}/hangup", {})
        assert status == 200
        assert isinstance(ended, dict)
        assert ended["result"] == "hungup"

        status, library_body = _request(port, "DELETE", "/api/cases/salon-marina")
        assert status == 200
        assert isinstance(library_body, dict)
        ids = [item["id"] for item in library_body["cases"] if isinstance(item, dict)]
        assert "salon-marina" not in ids

        status, bad = _request(port, "POST", "/api/import", {"text": ""})
        assert status == 400
        assert isinstance(bad, dict)
        assert "text" in str(bad["error"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


def test_cli_import_writes_the_library(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--data", str(tmp_path / "library.json"), "import", str(SAMPLE)])
    assert code == 0
    assert "Разобрано звонков: 4" in capsys.readouterr().out
    assert "salon-marina" in Library(tmp_path / "library.json").calls
    missing = main(["--data", str(tmp_path / "library.json"), "import", str(tmp_path / "нет.json")])
    assert missing == 1
