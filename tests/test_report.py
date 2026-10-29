"""Отчёт занятия: итог и закрытые возражения, без прослушивания."""

import json
from pathlib import Path

import pytest
from app.train.__main__ import main
from app.train.library import Library
from app.train.report import journal_rows, remember_closed, render_csv


def test_csv_row_names_the_case_and_the_objections() -> None:
    text = render_csv(
        [
            {
                "case_id": "salon-marina",
                "result": "next_step",
                "debrief": {
                    "handled": 1,
                    "spoken": 1,
                    "studies": [{"label": "цена", "status": "handled"}],
                },
            }
        ]
    )
    lines = text.strip().splitlines()
    assert lines[0] == "case_id,result,handled,spoken,objections"
    assert lines[1] == "salon-marina,next_step,1,1,цена"


def test_closed_session_is_appended_and_exported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    library = Library(tmp_path / "library.json")
    library.save()
    remember_closed(
        library,
        {
            "phase": "closed",
            "case_id": "wav-1",
            "result": "refused",
            "debrief": {"handled": 0, "spoken": 1, "studies": [{"label": "надо подумать"}]},
        },
    )
    out = tmp_path / "занятие.csv"
    code = main(["--data", str(library.path), "report", "--out", str(out)])
    assert code == 0
    assert "wav-1,refused,0,1,надо подумать" in out.read_text(encoding="utf-8")
    stored = json.loads((tmp_path / "sessions.jsonl").read_text(encoding="utf-8"))
    assert stored["case_id"] == "wav-1"
    assert capsys.readouterr().out == ""


def test_journal_lists_the_newest_closed_call_first(tmp_path: Path) -> None:
    library = Library(tmp_path / "library.json")
    library.save()
    log = tmp_path / "sessions.jsonl"
    log.write_text(json.dumps({"phase": "pitch", "case_id": "skip"}) + "\n", encoding="utf-8")
    remember_closed(
        library,
        {
            "phase": "closed",
            "case_id": "older",
            "result": "hungup",
            "debrief": {"handled": 0, "spoken": 0, "studies": []},
        },
    )
    remember_closed(
        library,
        {
            "phase": "closed",
            "id": "s2",
            "case_id": "salon-marina",
            "level": "hard",
            "result": "refused",
            "result_label": "клиент завершил разговор",
            "client": {"name": "Марина", "product": "Онлайн-запись"},
            "debrief": {"handled": 0, "spoken": 1, "studies": [{"label": "цена"}]},
        },
    )
    rows = journal_rows(library)
    assert [row["case_id"] for row in rows] == ["salon-marina", "older"]
    assert rows[0]["client_name"] == "Марина"
    assert rows[0]["level"] == "hard"
    assert rows[0]["objections"] == "цена"
    assert rows[0]["result_label"] == "клиент завершил разговор"
    assert journal_rows(Library(None)) == []
