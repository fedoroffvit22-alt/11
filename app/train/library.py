"""Библиотека звонков и то, чему по ним можно учить: возражения и реплики с итогом."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import assert_never, cast

from app.train.coach import money_amounts, offers_discount
from app.train.crm_parse import CrmImportError, parse_crm, parse_records
from app.train.model import (
    KINDS,
    CaseFacts,
    CrmCall,
    LearnedKind,
    ObjectionHit,
    Outcome,
    PracticeCase,
    Speaker,
    Turn,
)
from app.train.objections import detect_kind

_HELPFUL: frozenset[Outcome] = frozenset({"success", "callback"})
_QUOTE_LIMIT = 3


class LibraryError(RuntimeError):
    """Файл библиотеки не прочитан. Звонки в нём не затираются."""


class Library:
    def __init__(self, path: Path | None) -> None:
        self.path = path
        self.calls: dict[str, CrmCall] = {}
        if path is not None and path.is_file():
            self.calls = {call.id: call for call in _read(path)}

    def add_text(self, raw: str) -> tuple[CrmCall, ...]:
        calls = parse_crm(raw)
        for call in calls:
            self.calls[call.id] = call
        self.save()
        return calls

    def remove(self, call_id: str) -> None:
        if call_id not in self.calls:
            raise KeyError(call_id)
        del self.calls[call_id]
        self.save()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"calls": [call.to_json() for call in self.calls.values()]}
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def ordered(self) -> tuple[CrmCall, ...]:
        return tuple(self.calls.values())

    def case(self, call_id: str) -> PracticeCase:
        try:
            call = self.calls[call_id]
        except KeyError as exc:
            raise KeyError(call_id) from exc
        return practice_case(call)

    def learned(self) -> tuple[LearnedKind, ...]:
        return learn(self.ordered())


def practice_case(call: CrmCall) -> PracticeCase:
    return PracticeCase(
        call=call,
        opening=_opening(call),
        objections=extract_objections(call),
        facts=_facts(call),
    )


def extract_objections(call: CrmCall) -> tuple[ObjectionHit, ...]:
    hits: list[ObjectionHit] = []
    seen: set[str] = set()
    for index, turn in enumerate(call.turns):
        if turn.speaker != "client":
            continue
        kind = detect_kind(turn.text)
        if kind is None or kind in seen:
            continue
        seen.add(kind)
        hits.append(
            ObjectionHit(
                kind=kind,
                client_text=turn.text,
                operator_text=_next_text(call.turns, index, "operator"),
                outcome=call.outcome,
                call_id=call.id,
            )
        )
    return tuple(hits)


def learn(calls: tuple[CrmCall, ...]) -> tuple[LearnedKind, ...]:
    """Сводка по продукту и типу возражения. Реплика учит вместе со своим итогом."""

    grouped: dict[tuple[str, str], list[ObjectionHit]] = {}
    for call in calls:
        for hit in extract_objections(call):
            grouped.setdefault((call.product, hit.kind), []).append(hit)
    learned: list[LearnedKind] = []
    for kind in KINDS:
        products = sorted(product for product, hit_kind in grouped if hit_kind == kind)
        for product in products:
            hits = grouped[(product, kind)]
            learned.append(
                LearnedKind(
                    product=product,
                    kind=kind,
                    seen=len(hits),
                    client_examples=_unique(hit.client_text for hit in hits),
                    helpful=_unique(hit.operator_text for hit in hits if hit.outcome in _HELPFUL and hit.operator_text),
                    unhelpful=_unique(
                        hit.operator_text for hit in hits if hit.outcome == "refusal" and hit.operator_text
                    ),
                )
            )
    return tuple(learned)


def outcome_label(outcome: Outcome) -> str:
    if outcome == "success":
        return "договорённость"
    if outcome == "refusal":
        return "отказ"
    if outcome == "callback":
        return "перезвон"
    if outcome == "unknown":
        return "без итога"
    assert_never(outcome)


def _opening(call: CrmCall) -> str:
    for turn in call.turns:
        if turn.speaker != "client":
            continue
        if detect_kind(turn.text) is None and len(turn.text) <= 80:
            return turn.text
        return "Алло."
    return "Алло."


def _facts(call: CrmCall) -> CaseFacts:
    prices: list[str] = []
    for turn in call.turns:
        for amount in money_amounts(turn.text):
            if amount not in prices:
                prices.append(amount)
    discount = any(turn.speaker == "operator" and offers_discount(turn.text) for turn in call.turns)
    return CaseFacts(prices=tuple(prices), discount_allowed=discount)


def _next_text(turns: tuple[Turn, ...], start: int, speaker: Speaker) -> str:
    for turn in turns[start + 1 :]:
        if turn.speaker == speaker and turn.text:
            return turn.text
    return ""


def _unique(items: Iterable[str]) -> tuple[str, ...]:
    found: list[str] = []
    for item in items:
        text = " ".join(item.split())
        if text and text not in found:
            found.append(text)
        if len(found) == _QUOTE_LIMIT:
            break
    return tuple(found)


def _read(path: Path) -> tuple[CrmCall, ...]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise LibraryError(f"Файл библиотеки не прочитан: {path}. {exc}") from exc
    if not isinstance(payload, dict):
        raise LibraryError(f"Файл библиотеки не прочитан: {path}. Ожидался объект с полем calls.")
    records = payload.get("calls")
    if not isinstance(records, list):
        raise LibraryError(f"Файл библиотеки не прочитан: {path}. Поле calls должно быть списком.")
    try:
        return parse_records(cast(list[object], records))
    except CrmImportError as exc:
        raise LibraryError(f"Файл библиотеки не прочитан: {path}. {exc}") from exc
