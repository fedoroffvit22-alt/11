"""Уровни репетиции: подсказка до ответа, после ответа или молчание до конца."""

import pytest
from app.train.library import Library
from app.train.paths import sample_calls_path
from app.train.rehearsal import start_rehearsal

PITCH = "Добрый день, это Алексей, звоню по онлайн-записи для салона."


def _session(level: str):
    library = Library(None)
    library.add_text(sample_calls_path().read_text(encoding="utf-8"))
    return start_rehearsal(library.case("salon-marina"), library.ordered(), level=level)


def test_basic_shows_the_hint_before_the_answer() -> None:
    session = _session("basic")
    session.say(PITCH)
    assert "из чего" in session.coach
    assert session.phase == "objection"


def test_medium_keeps_the_hint_until_after_the_answer() -> None:
    session = _session("medium")
    session.say(PITCH)
    assert "из чего" not in session.coach
    session.say("ну ладно, расскажу про сервис ещё раз")
    assert session.result == "open"
    assert "цен" in session.coach.casefold()


def test_hard_ends_on_the_first_miss_without_a_hint() -> None:
    session = _session("hard")
    session.say(PITCH)
    assert "из чего" not in session.coach
    assert "скидк" not in session.coach.casefold()
    session.say("ну ладно, расскажу про сервис ещё раз")
    assert session.result == "refused"
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["studies"][0]["status"] == "missed"


def test_unknown_level_is_refused() -> None:
    library = Library(None)
    library.add_text(sample_calls_path().read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="basic"):
        start_rehearsal(library.case("salon-marina"), library.ordered(), level="easy")
