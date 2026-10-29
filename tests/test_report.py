"""Отчёт занятия: итог и закрытые возражения, без прослушивания."""

import json
from pathlib import Path

import pytest
from app.train.__main__ import main
from app.train.library import Library
from app.train.report import remember_closed, render_csv


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
