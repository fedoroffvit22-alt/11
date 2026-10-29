"""Звонок клиенту. Клиент говорит фразами из карточки, человек отвечает как оператор."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Literal, assert_never

from app.train.coach import review_objection
from app.train.library import learn, outcome_label
from app.train.model import CrmCall, LearnedKind, PracticeCase, Turn
from app.train.objections import kind_label

Phase = Literal["pitch", "objection", "closed"]
Result = Literal["open", "next_step", "refused", "hungup"]
StudyStatus = Literal["handled", "missed", "unanswered"]
_AGREEMENT = "Хорошо. Пришлите коротко условия сегодня, я посмотрю до вечера."
_REFUSAL = "Тогда мне это не подходит. До свидания."
_PITCH_RETRY = "Не расслышал. Представьтесь и скажите, зачем звоните."
_PITCH_EXIT = "Перезвоните, когда сможете представиться. До свидания."
_CONNECTORS = ("Хорошо.", "Допустим.", "Это ясно.")


@dataclass
class _Study:
    index: int
    status: StudyStatus


@dataclass
class Rehearsal:
    """Один разговор. Будущие возражения наружу не отдаются, пока клиент их не сказал."""

    case: PracticeCase
    learned: tuple[LearnedKind, ...]
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    phase: Phase = "pitch"
    result: Result = "open"
    started_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    ended_ms: int | None = None
    transcript: list[Turn] = field(default_factory=list)
    coach: str = "Клиент снял трубку. Представьтесь и скажите, зачем звоните. Возражения заранее не показаны."
    objection_index: int = 0
    misses: int = 0
    delivered: int = 0
    studies: list[_Study] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.transcript.append(Turn("client", self.case.opening))

    def say(self, text: str) -> None:
        if self.phase == "closed":
            self.coach = "Звонок уже закончен. Начните новый, если хотите пройти карточку ещё раз."
            return
        spoken = " ".join(text.split())
        if self.phase == "pitch":
            self._pitch(spoken)
            return
        if self.phase == "objection":
            self._objection(spoken)
            return
        assert_never(self.phase)

    def hangup(self) -> None:
        if self.phase == "closed":
            return
        self._close(
            "hungup",
            "Вы положили трубку. Разбор ниже — только по тем возражениям, которые клиент успел сказать.",
        )

    def snapshot(self) -> dict[str, object]:
        call = self.case.call
        return {
            "id": self.id,
            "case_id": call.id,
            "phase": self.phase,
            "result": self.result,
            "result_label": _result_label(self.result),
            "started_ms": self.started_ms,
            "ended_ms": self.ended_ms,
            "client": {"name": call.client_name, "company": call.company, "product": call.product},
            "transcript": [{"speaker": turn.speaker, "text": turn.text} for turn in self.transcript],
            "coach": self.coach,
            "can_speak": self.phase != "closed",
            "debrief": None if self.phase != "closed" else self._debrief(),
        }

    def _pitch(self, spoken: str) -> None:
        self.transcript.append(Turn("operator", spoken))
        if _is_pitch(spoken, self.case.call.product):
            self.misses = 0
            self._raise_objection()
            return
        self.misses += 1
        if self.misses >= 2:
            self.transcript.append(Turn("client", _PITCH_EXIT))
            self._close("refused", "Клиент не дождался, кто звонит и зачем. До возражений разговор не дошёл.")
            return
        self.transcript.append(Turn("client", _PITCH_RETRY))
        self.coach = "Клиент не понял, кто вы. Назовите себя и повод звонка, без прайса на полминуты."

    def _objection(self, spoken: str) -> None:
        hit = self.case.objections[self.objection_index]
        review = review_objection(spoken, hit, self.case.facts)
        self.transcript.append(Turn("operator", spoken))
        self.coach = review.coach
        if review.handled:
            self._resolve(self.objection_index, "handled")
            self.misses = 0
            self.objection_index += 1
            self._raise_objection(review.coach)
            return
        self.misses += 1
        if self.misses >= 2:
            self._resolve(self.objection_index, "missed")
            self.transcript.append(Turn("client", _REFUSAL))
            self._close("refused", review.coach)
            return
        self.transcript.append(Turn("client", f"Я уже сказал: {hit.client_text}"))

    def _raise_objection(self, prior: str = "") -> None:
        objections = self.case.objections
        if self.objection_index >= len(objections):
            self.transcript.append(Turn("client", _AGREEMENT))
            closed = "Клиент согласился на конкретный шаг."
            if not objections:
                closed = "В исходном звонке не было возражений. Клиент просит короткие условия."
            self._close("next_step", closed)
            return
        hit = objections[self.objection_index]
        if self.objection_index == 0:
            line = hit.client_text
        else:
            bridge = _CONNECTORS[(self.objection_index - 1) % len(_CONNECTORS)]
            line = f"{bridge} {hit.client_text}"
        self.transcript.append(Turn("client", line))
        self.delivered += 1
        self.phase = "objection"
        label = kind_label(hit.kind)
        if prior:
            self.coach = f"{prior} Дальше другое: {label}."
        else:
            self.coach = f"Клиент сказал возражение: {label}. Ответьте на него, не пересказывая презентацию."

    def _resolve(self, index: int, status: StudyStatus) -> None:
        self.studies = [item for item in self.studies if item.index != index]
        self.studies.append(_Study(index, status))

    def _close(self, result: Result, coach: str) -> None:
        self.phase = "closed"
        self.result = result
        self.ended_ms = int(time.time() * 1000)
        self.coach = coach
        for index in range(self.delivered):
            if not any(item.index == index for item in self.studies):
                self.studies.append(_Study(index, "unanswered"))

    def _debrief(self) -> dict[str, object]:
        handled = sum(1 for item in self.studies if item.status == "handled")
        remaining = len(self.case.objections) - self.delivered
        studies = []
        for item in sorted(self.studies, key=lambda study: study.index):
            hit = self.case.objections[item.index]
            pattern = _pattern(self.learned, self.case.call.product, hit.kind)
            studies.append(
                {
                    "label": kind_label(hit.kind),
                    "status": item.status,
                    "status_label": _study_label(item.status),
                    "client_text": hit.client_text,
                    "helpful": list(pattern.helpful) if pattern is not None else [],
                    "unhelpful": list(pattern.unhelpful) if pattern is not None else [],
                }
            )
        tail = ""
        if remaining > 0:
            tail = f" В карточке ещё {remaining} возражений, до них разговор не дошёл."
        summary = f"Закрыто {handled} из {self.delivered} сказанных.{tail}"
        return {
            "summary": summary,
            "result_label": _result_label(self.result),
            "handled": handled,
            "spoken": self.delivered,
            "remaining": remaining,
            "source_outcome": outcome_label(self.case.call.outcome),
            "studies": studies,
        }


def start_rehearsal(case: PracticeCase, calls: tuple[CrmCall, ...]) -> Rehearsal:
    return Rehearsal(case=case, learned=learn(calls))


def _is_pitch(text: str, product: str) -> bool:
    spoken = " ".join(text.split())
    if len(spoken) < 20 or len(spoken) > 600:
        return False
    folded = spoken.casefold()
    if any(marker in folded for marker in ("здравств", "добрый", "звоню", "меня зовут", "компани")):
        return True
    for word in product.casefold().replace("ё", "е").split():
        if len(word) >= 5 and word in folded:
            return True
    return False


def _pattern(learned: tuple[LearnedKind, ...], product: str, kind: str) -> LearnedKind | None:
    for item in learned:
        if item.product == product and item.kind == kind:
            return item
    return None


def _result_label(result: Result) -> str:
    if result == "open":
        return "разговор"
    if result == "next_step":
        return "следующий шаг"
    if result == "refused":
        return "клиент завершил разговор"
    if result == "hungup":
        return "вы положили трубку"
    assert_never(result)


def _study_label(status: StudyStatus) -> str:
    if status == "handled":
        return "закрыто"
    if status == "missed":
        return "не закрыто"
    if status == "unanswered":
        return "без ответа"
    assert_never(status)
