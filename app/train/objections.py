"""Типы возражений по русским формулировкам клиента. Модель для этого не нужна."""

from __future__ import annotations

import re
from typing import assert_never

from app.train.model import KINDS, Kind

_RULES: tuple[tuple[Kind, re.Pattern[str]], ...] = (
    ("send_info", re.compile(r"на почт|пришлите|пришли\b|киньте|коммерческ")),
    (
        "authority",
        re.compile(
            r"не я реша|не я принима|директор|руковод|собственник|согласован|бухгалтер|"
            r"(?<![а-яё])муж(?:а|у|ем)?(?![а-яё])|(?<![а-яё])жен[аы](?![а-яё])"
        ),
    ),
    (
        "competitor",
        re.compile(r"уже есть|уже работ|уже сид|уже польз|поставщик|yclients|конкурент|друг(?:ой|им) сервис"),
    ),
    ("trust", re.compile(r"мошен|не знаю вас|первый раз слыш|кто вы такие|отзыв")),
    ("price", re.compile(r"дорог|цен[аыу]\b|бюджет|дешевл|скидк|не по карман|много денег")),
    ("think", re.compile(r"подума|посовету|не готов реша|надо обсуд")),
    ("time", re.compile(r"нет времени|некогда|занят|не до этого|перезвон|позже|потом набер")),
    ("not_interested", re.compile(r"не интерес|не нужно|не надо|не хочу|не будем|не актуал")),
)


def detect_kind(text: str) -> Kind | None:
    """Первое совпадение по порядку правил. Пустая реплика — не возражение."""

    folded = text.casefold()
    for kind, pattern in _RULES:
        if pattern.search(folded):
            return kind
    return None


def kind_label(kind: Kind) -> str:
    if kind == "price":
        return "цена"
    if kind == "time":
        return "нет времени"
    if kind == "think":
        return "надо подумать"
    if kind == "competitor":
        return "уже есть решение"
    if kind == "not_interested":
        return "не интересно"
    if kind == "authority":
        return "решает другой человек"
    if kind == "send_info":
        return "пришлите информацию"
    if kind == "trust":
        return "нет доверия"
    assert_never(kind)


def has_signal(kind: Kind, text: str) -> bool:
    """Реплика касается сути этого возражения, а не продукта вообще."""

    folded = text.casefold()
    if kind == "price":
        tokens = ("дорого", "цена", "цену", "цены", "бюджет", "из чего", "за что", "окупа", "сравн", "абонент")
    elif kind == "time":
        tokens = ("минут", "когда удоб", "когда вам", "коротко", "во сколько", "сколько займ")
    elif kind == "think":
        tokens = ("что смуща", "какой вопрос", "с кем", "критер", "что решить", "что именно", "до какого")
    elif kind == "competitor":
        tokens = ("чем отлич", "сравн", "не хвата", "как сейчас", "что не устра", "текущ")
    elif kind == "not_interested":
        tokens = ("как сейчас", "что сейчас", "как реша", "какая задача", "что болит", "зачем звон")
    elif kind == "authority":
        tokens = (
            "кто принима",
            "как зовут",
            "его зовут",
            "её зовут",
            "ее зовут",
            "кого зовут",
            "когда будет",
            "созвон",
            "владел",
            "директор",
        )
    elif kind == "send_info":
        tokens = ("что именно", "на что смотреть", "куда отправ", "что прислать", "в письме")
    elif kind == "trust":
        tokens = ("договор", "кейс", "реквизит", "гарант", "инн", "юрлиц")
    else:
        assert_never(kind)
    return any(token in folded for token in tokens)


def known_kinds() -> tuple[Kind, ...]:
    return KINDS
