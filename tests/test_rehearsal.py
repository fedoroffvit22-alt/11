"""Репетиция: клиент из карточки, человек отвечает как оператор."""

import json

from app.train.coach import offers_discount, review_objection
from app.train.crm_parse import parse_crm
from app.train.library import Library, practice_case
from app.train.model import CaseFacts, ObjectionHit
from app.train.paths import sample_calls_path
from app.train.rehearsal import start_rehearsal

SAMPLE = sample_calls_path().read_text(encoding="utf-8")
PITCH = "Добрый день, это Алексей, звоню по онлайн-записи для салона."


def _library() -> Library:
    library = Library(None)
    library.add_text(SAMPLE)
    return library


def test_opening_hides_the_objection() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-marina"), library.ordered())
    blob = json.dumps(session.snapshot(), ensure_ascii=False)
    assert "Дорого" not in blob
    assert session.snapshot()["debrief"] is None
    assert session.transcript[0].text == "Алло, слушаю."


def test_short_opening_asks_for_a_name_then_a_second_miss_ends_the_call() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-marina"), library.ordered())
    session.say("алло")
    assert session.phase == "pitch"
    assert "Представьтесь" in session.transcript[-1].text
    session.say("я по делу")
    assert session.result == "refused"
    assert session.phase == "closed"
    assert "представиться" in session.transcript[-1].text
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["spoken"] == 0


def test_price_answer_earns_the_next_step_without_a_discount() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-marina"), library.ordered())
    session.say(PITCH)
    assert "Дорого" in session.transcript[-1].text
    session.say("Понимаю. Из чего для вас складывается дорого?")
    assert session.result == "next_step"
    assert session.transcript[-1].text.startswith("Хорошо. Пришлите коротко условия")
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["handled"] == 1
    assert debrief["studies"][0]["status"] == "handled"
    assert debrief["studies"][0]["helpful"]


def test_invented_discount_and_price_do_not_close_the_objection() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-marina"), library.ordered())
    session.say(PITCH)
    session.say("Могу сделать скидку пятьдесят процентов.")
    assert session.phase == "objection"
    assert "Скидку обещать нельзя" in session.coach
    assert session.transcript[-1].text.startswith("Я уже сказал")
    session.say("Тогда отдам за 1000 рублей сегодня.")
    assert session.result == "refused"

    denied = review_objection(
        "Понимаю. Скидку не обещаю. Из чего для вас складывается дорого?",
        practice_case(parse_crm(SAMPLE)[0]).objections[0],
        CaseFacts(prices=("3900",), discount_allowed=False),
    )
    assert denied.handled is True
    assert offers_discount("Скидку не обещаю.") is False


def test_refusal_phrase_from_crm_does_not_count_as_handling() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-igor"), library.ordered())
    session.say(PITCH)
    assert "подумаю" in session.transcript[-1].text.casefold()
    session.say("Хорошо, я перезвоню через месяц.")
    assert "отказом" in session.coach
    session.say("Ну подумайте тогда.")
    assert session.result == "refused"
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["studies"][0]["status"] == "missed"
    assert debrief["studies"][0]["unhelpful"] == ["Хорошо, я перезвоню через месяц."]


def test_authority_question_moves_the_call_forward() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-olga"), library.ordered())
    session.say("Добрый день, меня зовут Алексей, звоню по записи клиентов.")
    assert "муж" in session.transcript[-1].text
    session.say("Понимаю. Как его зовут и когда с ним можно говорить?")
    assert session.result == "next_step"


def test_hangup_marks_the_spoken_objection_unanswered() -> None:
    library = _library()
    session = start_rehearsal(library.case("salon-marina"), library.ordered())
    session.say(PITCH)
    session.hangup()
    assert session.result == "hungup"
    debrief = session.snapshot()["debrief"]
    assert isinstance(debrief, dict)
    assert debrief["studies"][0]["status"] == "unanswered"
    session.say("ещё одна реплика")
    assert session.transcript[-1].speaker == "client"


def test_repeat_of_a_working_crm_line_counts_even_without_the_lexicon() -> None:
    hit = ObjectionHit(
        kind="price",
        client_text="Дорого.",
        operator_text="Давайте оставим тетрадь и посчитаем сорванные субботы.",
        outcome="success",
        call_id="c1",
    )
    review = review_objection(hit.operator_text, hit, CaseFacts(prices=(), discount_allowed=False))
    assert review.handled is True
    refused = ObjectionHit(
        kind="price",
        client_text="Дорого.",
        operator_text=hit.operator_text,
        outcome="refusal",
        call_id="c1",
    )
    again = review_objection(hit.operator_text, refused, CaseFacts(prices=(), discount_allowed=False))
    assert again.handled is False
