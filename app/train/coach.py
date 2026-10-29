"""Оценка реплики оператора по фактам звонка и по фразам, которые уже были в CRM."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import assert_never

from app.train.model import CaseFacts, Kind, ObjectionHit, Outcome
from app.train.objections import has_signal, kind_label

_MONEY = re.compile(r"\d[\d\s]{0,12}\s*(?:руб(?:лей|ля|\.)?|₽|тыс\.?)", re.IGNORECASE)
_ACK = ("понял", "понима", "слышу", "логично", "справедлив", "соглас", "бывает", "вижу", "принял")
_QUESTION = (
    " как ",
    " чего ",
    " что ",
    " когда ",
    " кто ",
    " сколько ",
    " почему ",
    " зачем ",
    " где ",
    " какой ",
    " какая ",
    " какие ",
)
_STOP = frozenset(
    {
        "это",
        "как",
        "что",
        "для",
        "вас",
        "вам",
        "меня",
        "тебе",
        "просто",
        "очень",
        "только",
        "когда",
        "если",
        "или",
        "уже",
        "ещё",
        "еще",
        "надо",
        "будет",
        "можно",
        "сейчас",
        "сегодня",
        "завтра",
        "потом",
        "вообще",
        "давайте",
        "хорошо",
        "ладно",
    }
)
_HELPFUL: frozenset[Outcome] = frozenset({"success", "callback"})


@dataclass(frozen=True)
class Review:
    handled: bool
    coach: str
    invented: bool


def money_amounts(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in _MONEY.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if digits and digits not in found:
            found.append(digits)
    return tuple(found)


def offers_discount(text: str) -> bool:
    folded = text.casefold()
    if re.search(r"скидк\w*\s+не|не\s+.{0,24}скидк|без\s+скидк", folded):
        return False
    if "не бесплатно" in folded:
        folded = folded.replace("не бесплатно", " ")
    return re.search(r"скидк|бесплатно|в подарок", folded) is not None


def review_objection(text: str, hit: ObjectionHit, facts: CaseFacts) -> Review:
    """Закрыто ли текущее возражение. Выдуманная скидка или сумма закрытием не считается."""

    spoken = " ".join(text.split())
    if not spoken:
        return Review(False, "Пустая реплика. Клиент всё ещё ждёт ответа на возражение.", False)
    label = kind_label(hit.kind)
    if offers_discount(spoken) and not facts.discount_allowed:
        return Review(
            False,
            "Скидку обещать нельзя: в этом звонке её не давали. Ответьте на суть возражения.",
            True,
        )
    foreign = [amount for amount in money_amounts(spoken) if amount not in facts.prices]
    if foreign:
        known = ", ".join(f"{amount} ₽" for amount in facts.prices) or "сумм в звонке не было"
        bad = ", ".join(f"{amount} ₽" for amount in foreign)
        return Review(
            False,
            f"Суммы {bad} в этом звонке нет. Называйте только то, что уже звучало: {known}.",
            True,
        )
    if len(spoken) > 600:
        return Review(False, "Слишком длинно для звонка. Скажите то же самое в одном-двух предложениях.", False)
    if len(spoken) < 12:
        return Review(False, f"Слишком коротко: возражение «{label}» так и осталось без ответа.", False)
    helpful = _quote_overlap(spoken, hit.operator_text) if hit.outcome in _HELPFUL else 0.0
    if helpful >= 0.34 and hit.operator_text.strip():
        return Review(
            True,
            ("Формулировка близка к реплике из этой карточки, после которой был рабочий итог. Клиент слушает дальше."),
            False,
        )
    if (_has_ack(spoken) or _has_question(spoken)) and has_signal(hit.kind, spoken):
        return Review(True, _hit_text(hit.kind), False)
    unhelpful = _quote_overlap(spoken, hit.operator_text) if hit.outcome == "refusal" else 0.0
    if unhelpful >= 0.45 and hit.operator_text.strip():
        return Review(
            False,
            f"Похожая фраза в этой карточке закончилась отказом. Нужен вопрос по сути: {label}.",
            False,
        )
    return Review(False, _miss_text(hit.kind), False)


def _has_ack(text: str) -> bool:
    folded = text.casefold()
    return any(token in folded for token in _ACK)


def _has_question(text: str) -> bool:
    if "?" in text:
        return True
    padded = f" {text.casefold()} "
    return any(token in padded for token in _QUESTION)


def _quote_overlap(left: str, right: str) -> float:
    a = _tokens(left)
    b = _tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[а-яё]+", text.casefold()) if len(word) >= 4 and word not in _STOP}


def miss_hint(kind: Kind) -> str:
    """Подсказка до ответа на базовом уровне. Не оценивает реплику."""

    return _miss_text(kind)


def _hit_text(kind: Kind) -> str:
    if kind == "price":
        return "Цена принята: вы ответили на слова клиента и не ушли в общий рассказ о продукте."
    if kind == "time":
        return "Время принято: у разговора есть короткая длина или понятный следующий момент."
    if kind == "think":
        return "«Подумаю» разобрано: есть вопрос, что именно решить."
    if kind == "competitor":
        return "Текущее решение не атаковано в лоб: вы спросили, чего в нём не хватает."
    if kind == "not_interested":
        return "Отказ не проигнорирован: вы уточнили, как вопрос закрыт сейчас."
    if kind == "authority":
        return "Найден следующий человек: есть имя или момент, когда с ним можно говорить."
    if kind == "send_info":
        return "Письмо не стало побегом: понятно, что в нём смотреть."
    if kind == "trust":
        return "Доверие опирается на проверяемый факт, не на слова «мы надёжные»."
    assert_never(kind)


def _miss_text(kind: Kind) -> str:
    if kind == "price":
        return "Возражение про цену не закрыто. Спросите, из чего она складывается или с чем клиент её сравнивает."
    if kind == "time":
        return "Возражение про время не закрыто. Назовите, сколько минут займёт разговор, и спросите, когда удобно."
    if kind == "think":
        return "«Подумаю» не закрыто. Спросите, что именно решить и до какого момента."
    if kind == "competitor":
        return (
            "Возражение «уже есть решение» не закрыто. "
            "Спросите, чего не хватает сейчас, и не предлагайте менять всё сразу."
        )
    if kind == "not_interested":
        return "Отказ не разобран. Уточните, как клиент закрывает этот вопрос сейчас, без нового монолога."
    if kind == "authority":
        return "Не найден человек, который решает. Спросите, как его зовут и когда с ним можно говорить."
    if kind == "send_info":
        return "Уход в почту не закрыт. Скажите, что именно смотреть в письме и зачем это делать сейчас."
    if kind == "trust":
        return "Доверие не поддержано. Назовите договор, реквизиты или кейс, без общих слов «мы надёжные»."
    assert_never(kind)
