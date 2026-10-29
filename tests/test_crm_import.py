"""Разбор выгрузки CRM без весов и без сети."""

from pathlib import Path

import pytest
from app.train.crm_parse import CrmImportError, parse_crm
from app.train.library import Library, LibraryError, learn, practice_case
from app.train.objections import detect_kind
from app.train.paths import sample_calls_path

SAMPLE = sample_calls_path()


def test_sample_calls_become_practice_cases() -> None:
    calls = parse_crm(SAMPLE.read_text(encoding="utf-8"))
    by_id = {call.id: practice_case(call) for call in calls}
    assert [call.id for call in calls] == ["salon-marina", "salon-igor", "salon-olga", "salon-pavel"]
    marina = by_id["salon-marina"]
    assert [hit.kind for hit in marina.objections] == ["price"]
    assert marina.opening == "Алло, слушаю."
    assert marina.facts.prices == ("3900",)
    assert marina.facts.discount_allowed is False
    igor = by_id["salon-igor"]
    assert [hit.kind for hit in igor.objections] == ["think", "not_interested"]
    assert igor.objections[0].operator_text == "Хорошо, я перезвоню через месяц."
    assert igor.objections[1].operator_text == ""
    assert [hit.kind for hit in by_id["salon-olga"].objections] == ["authority"]
    assert [hit.kind for hit in by_id["salon-pavel"].objections] == ["competitor"]


def test_learned_quotes_keep_their_outcome() -> None:
    learned = {item.kind: item for item in learn(parse_crm(SAMPLE.read_text(encoding="utf-8")))}
    assert learned["price"].helpful
    assert not learned["price"].unhelpful
    assert learned["think"].unhelpful == ("Хорошо, я перезвоню через месяц.",)
    assert learned["think"].helpful == ()
    assert "Дорого" in learned["price"].client_examples[0]


def test_text_export_and_russian_outcome() -> None:
    raw = """
# product: Доставка
# outcome: перезвон
# client: Анна
# company: Кафе

Оператор: Анна, добрый день, это служба доставки.
Клиент: Алло.
Оператор: Звоню по утренним слотам.
Клиент: Пришлите на почту,
я посмотрю вечером.
---
# id: second
# product: Доставка
# outcome: отказ
# client: Пётр

Клиент: Дорого.
Оператор: Понимаю.
"""
    first, second = parse_crm(raw)
    assert first.outcome == "callback"
    assert first.client_name == "Анна"
    assert first.turns[-1].text == "Пришлите на почту, я посмотрю вечером."
    assert [hit.kind for hit in practice_case(first).objections] == ["send_info"]
    assert second.id == "second"
    assert second.outcome == "refusal"
    assert practice_case(second).opening == "Алло."


def test_broken_export_names_the_problem() -> None:
    with pytest.raises(CrmImportError, match="итог"):
        parse_crm('{"id":"1","product":"Касса","outcome":"победа","turns":[{"speaker":"client","text":"Алло"}]}')
    with pytest.raises(CrmImportError, match="продукт"):
        parse_crm("Клиент: Алло.\n")
    with pytest.raises(CrmImportError, match="роль"):
        parse_crm("# product: Касса\nпросто текст\n")


def test_kind_order_and_false_friends() -> None:
    assert detect_kind("Я подумаю и перезвоню сам.") == "think"
    assert detect_kind("женщина записалась сама") is None
    assert detect_kind("мужчина на ресепшене") is None
    assert detect_kind("Это решает мой муж.") == "authority"


def test_library_roundtrip_replaces_same_id_and_keeps_old_on_error(tmp_path: Path) -> None:
    path = tmp_path / "library.json"
    library = Library(path)
    library.add_text(SAMPLE.read_text(encoding="utf-8"))
    library.add_text(
        '{"id":"salon-marina","product":"Онлайн-запись","outcome":"unknown","client_name":"Мария",'
        '"turns":[{"speaker":"client","text":"Алло"}]}'
    )
    assert library.calls["salon-marina"].client_name == "Мария"
    with pytest.raises(CrmImportError):
        library.add_text("{")
    assert library.calls["salon-marina"].client_name == "Мария"
    again = Library(path)
    assert again.calls["salon-marina"].client_name == "Мария"
    assert len(again.calls) == 4


def test_empty_library_file_is_readable(tmp_path: Path) -> None:
    path = tmp_path / "library.json"
    Library(path).save()
    assert Library(path).calls == {}
    path.write_text("{", encoding="utf-8")
    with pytest.raises(LibraryError, match="не прочитан"):
        Library(path)
