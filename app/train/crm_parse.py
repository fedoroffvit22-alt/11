"""Разбор выгрузки CRM: JSON или текст с ролями. Аудио и веса не читаются."""

from __future__ import annotations

import hashlib
import json
import re
from typing import cast

from app.train.model import OUTCOMES, SPEAKERS, CrmCall, Outcome, Speaker, Turn

_HEADER = re.compile(
    r"^#\s*(id|product|outcome|client|company|продукт|итог|клиент|компания)\s*:\s*(.*)$",
    re.IGNORECASE,
)
_ROLE = re.compile(
    r"^(оператор|менеджер|сотрудник|клиент|абонент|operator|client|agent)\s*:\s*(.*)$",
    re.IGNORECASE,
)
_HEADER_KEY = {
    "id": "id",
    "product": "product",
    "продукт": "product",
    "outcome": "outcome",
    "итог": "outcome",
    "client": "client",
    "клиент": "client",
    "company": "company",
    "компания": "company",
}
_SPEAKER_ALIASES = {
    "оператор": "operator",
    "менеджер": "operator",
    "сотрудник": "operator",
    "operator": "operator",
    "agent": "operator",
    "клиент": "client",
    "абонент": "client",
    "client": "client",
}
_OUTCOME_ALIASES = {
    "success": "success",
    "won": "success",
    "sale": "success",
    "успех": "success",
    "успешно": "success",
    "договор": "success",
    "договорённость": "success",
    "договоренность": "success",
    "refusal": "refusal",
    "refused": "refusal",
    "lost": "refusal",
    "отказ": "refusal",
    "неуспех": "refusal",
    "callback": "callback",
    "recall": "callback",
    "перезвон": "callback",
    "unknown": "unknown",
    "": "unknown",
    "none": "unknown",
    "без итога": "unknown",
}


class CrmImportError(ValueError):
    """Выгрузка не разобрана. Библиотека при этом не меняется."""


def parse_crm(raw: str) -> tuple[CrmCall, ...]:
    text = raw.lstrip("\ufeff").strip()
    if not text:
        raise CrmImportError("Пустая выгрузка. Нужен JSON со звонками или текст с ролями Оператор и Клиент.")
    if text[0] in "[{":
        return _parse_json(text)
    return _parse_text(text)


def _parse_json(text: str) -> tuple[CrmCall, ...]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CrmImportError(f"JSON не разобран: {exc.msg}, строка {exc.lineno}.") from exc
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and "calls" in payload:
        records = payload["calls"]
    elif isinstance(payload, dict):
        records = [payload]
    else:
        raise CrmImportError("JSON должен быть звонком, списком звонков или объектом с полем calls.")
    if not isinstance(records, list):
        raise CrmImportError("Поле calls должно быть списком звонков.")
    calls = parse_records(records)
    if not calls:
        raise CrmImportError("В выгрузке нет звонков.")
    return calls


def parse_records(records: list[object]) -> tuple[CrmCall, ...]:
    """Разобрать уже загруженный список. Пустой список допустим для файла библиотеки."""

    return tuple(_call_from_json(record, index) for index, record in enumerate(records, start=1))


def _call_from_json(record: object, index: int) -> CrmCall:
    if not isinstance(record, dict):
        raise CrmImportError(f"Звонок {index} должен быть объектом.")
    body = cast(dict[str, object], record)
    label = _text(body.get("id", body.get("call_id"))) or f"номер {index}"
    turns_raw = body.get("turns", body.get("dialogue", body.get("messages")))
    if not isinstance(turns_raw, list) or not turns_raw:
        raise CrmImportError(f"В звонке {label} нет реплик.")
    turns: list[Turn] = []
    for turn_index, item in enumerate(turns_raw, start=1):
        if not isinstance(item, dict):
            raise CrmImportError(f"Реплика {turn_index} в звонке {label} должна быть объектом.")
        turn_body = cast(dict[str, object], item)
        speaker = _speaker(_text(turn_body.get("speaker", turn_body.get("role", turn_body.get("from")))))
        if speaker is None:
            raise CrmImportError(f"В звонке {label} реплика {turn_index}: роль должна быть оператором или клиентом.")
        text = _text(turn_body.get("text", turn_body.get("content")))
        if not text:
            raise CrmImportError(f"В звонке {label} реплика {turn_index} пустая.")
        turns.append(Turn(speaker, text))
    return _finish(
        call_id=_text(body.get("id", body.get("call_id"))),
        product=_text(body.get("product", body.get("topic"))),
        outcome=_text(body.get("outcome", body.get("result", body.get("status")))),
        client_name=_text(body.get("client_name", body.get("client", body.get("name")))),
        company=_text(body.get("company", body.get("organization"))),
        turns=tuple(turns),
        label=label,
    )


def _parse_text(text: str) -> tuple[CrmCall, ...]:
    blocks = re.split(r"\n\s*---\s*\n", text)
    calls: list[CrmCall] = []
    for block_index, block in enumerate(blocks, start=1):
        if not block.strip():
            continue
        calls.append(_parse_block(block, block_index))
    if not calls:
        raise CrmImportError("В тексте нет звонков. Разделяйте карточки строкой ---.")
    return tuple(calls)


def _parse_block(block: str, block_index: int) -> CrmCall:
    fields = {"id": "", "product": "", "outcome": "", "client": "", "company": ""}
    turns: list[Turn] = []
    speaker: Speaker | None = None
    for line_number, raw_line in enumerate(block.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        header = _HEADER.match(line)
        if header:
            key = _HEADER_KEY[header.group(1).casefold()]
            fields[key] = header.group(2).strip()
            speaker = None
            continue
        role = _ROLE.match(line)
        if role:
            speaker = _speaker(role.group(1))
            text = role.group(2).strip()
            if speaker is None:
                raise CrmImportError(f"Блок {block_index}, строка {line_number}: неизвестная роль.")
            if text:
                turns.append(Turn(speaker, text))
            else:
                turns.append(Turn(speaker, ""))
            continue
        if speaker is None or not turns:
            raise CrmImportError(
                f"Блок {block_index}, строка {line_number}: нужна роль «Оператор:» или «Клиент:». Получено: {line}"
            )
        previous = turns[-1]
        merged = f"{previous.text} {line}".strip()
        turns[-1] = Turn(previous.speaker, merged)
    filled = tuple(turn for turn in turns if turn.text)
    label = fields["id"] or f"блок {block_index}"
    return _finish(
        call_id=fields["id"],
        product=fields["product"],
        outcome=fields["outcome"],
        client_name=fields["client"],
        company=fields["company"],
        turns=filled,
        label=label,
    )


def _finish(
    *,
    call_id: str,
    product: str,
    outcome: str,
    client_name: str,
    company: str,
    turns: tuple[Turn, ...],
    label: str,
) -> CrmCall:
    if not product:
        raise CrmImportError(f"В звонке {label} не указан продукт.")
    if not turns or not any(turn.speaker == "client" for turn in turns):
        raise CrmImportError(f"В звонке {label} нет реплик клиента.")
    mapped = _outcome(outcome, label)
    identity = call_id or _digest(product, turns)
    return CrmCall(
        id=identity,
        product=product,
        outcome=mapped,
        client_name=client_name,
        company=company,
        turns=turns,
    )


def _outcome(raw: str, label: str) -> Outcome:
    mapped = _OUTCOME_ALIASES.get(raw.strip().casefold())
    if mapped is None:
        allowed = ", ".join(OUTCOMES)
        raise CrmImportError(
            f"В звонке {label} итог {raw!r} не разобран. Допустимо: {allowed}, плюс русские слова вроде «отказ»."
        )
    if mapped not in OUTCOMES:
        raise CrmImportError(f"В звонке {label} итог разобран в неизвестное значение.")
    return cast(Outcome, mapped)


def _speaker(raw: str) -> Speaker | None:
    mapped = _SPEAKER_ALIASES.get(raw.strip().casefold())
    if mapped in SPEAKERS:
        return cast(Speaker, mapped)
    return None


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, int | float) and not isinstance(value, bool):
        return str(value)
    return ""


def _digest(product: str, turns: tuple[Turn, ...]) -> str:
    body = product + "\n" + "\n".join(f"{turn.speaker}:{turn.text}" for turn in turns)
    return "call-" + hashlib.sha1(body.encode("utf-8")).hexdigest()[:8]
