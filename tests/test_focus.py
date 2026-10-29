"""Одно возражение: после представления клиент говорит только выбранный вид."""

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest
from app.train.library import Library
from app.train.paths import sample_calls_path
from app.train.rehearsal import start_rehearsal
from app.train.server import bind

PITCH = "Добрый день, это Алексей, звоню по онлайн-записи для салона."


def _library() -> Library:
    library = Library(None)
    library.add_text(sample_calls_path().read_text(encoding="utf-8"))
    return library


def test_focus_stops_after_the_chosen_objection() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-igor"), library.ordered(), focus="think")
    session.say(PITCH)
    assert "подумаю" in session.transcript[-1].text.casefold()
    session.say("Что именно хотите решить до того, как перезвоните?")
    assert session.result == "next_step"
    spoken = " ".join(turn.text for turn in session.transcript)
    assert "не интерес" not in spoken.casefold()
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["spoken"] == 1
    assert debrief["studies"][0]["label"] == "надо подумать"
    assert session.snapshot()["focus"] == "think"


def test_focus_skips_objections_that_come_earlier_in_the_card() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-igor"), library.ordered(), focus="not_interested")
    assert "подумаю" not in json.dumps(session.snapshot(), ensure_ascii=False).casefold()
    session.say(PITCH)
    assert "не интерес" in session.transcript[-1].text.casefold()
    assert "подумаю" not in session.transcript[-1].text.casefold()
    session.say("Понимаю. Как сейчас записываете клиентов?")
    assert session.result == "next_step"
    spoken = " ".join(turn.text for turn in session.transcript)
    assert "подумаю" not in spoken.casefold()


def test_focus_rejects_a_card_without_that_kind() -> None:
    library = _library()
    with pytest.raises(ValueError, match="надо подумать"):
        start_rehearsal(library.case("salon-marina"), library.ordered(), focus="think")


def test_unknown_focus_names_the_real_kinds() -> None:
    library = _library()
    with pytest.raises(ValueError, match="цена"):
        start_rehearsal(library.case("salon-marina"), library.ordered(), focus="budget")


def test_page_filters_cases_and_starts_the_chosen_objection(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.json")
    server = bind(library)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = int(server.server_address[1])
    try:
        status, page = _request(port, "GET", "/")
        assert status == 200
        assert isinstance(page, str)
        assert "Вся карточка" in page

        status, imported = _request(port, "POST", "/api/examples", {})
        assert status == 200
        assert isinstance(imported, dict)
        igor = next(item for item in imported["cases"] if isinstance(item, dict) and item["id"] == "salon-igor")
        assert [entry["kind"] for entry in igor["kinds"] if isinstance(entry, dict)] == ["think", "not_interested"]

        status, missing = _request(
            port,
            "POST",
            "/api/sessions",
            {"case_id": "salon-marina", "focus": "think"},
        )
        assert status == 400
        assert isinstance(missing, dict)
        assert "надо подумать" in str(missing["error"])

        status, bad = _request(port, "POST", "/api/sessions", {"case_id": "salon-igor", "focus": "budget"})
        assert status == 400

        status, session = _request(
            port,
            "POST",
            "/api/sessions",
            {"case_id": "salon-igor", "level": "hard", "focus": "not_interested"},
        )
        assert status == 200
        assert isinstance(session, dict)
        assert session["focus"] == "not_interested"
        assert "подумаю" not in json.dumps(session, ensure_ascii=False).casefold()
        session_id = session["id"]
        assert isinstance(session_id, str)

        status, turned = _request(port, "POST", f"/api/sessions/{session_id}/turn", {"text": PITCH})
        assert status == 200
        assert isinstance(turned, dict)
        blob = json.dumps(turned, ensure_ascii=False).casefold()
        assert "не интерес" in blob
        assert "подумаю" not in blob
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


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
