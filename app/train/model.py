"""Карточки звонка. Разбор CRM и репетиция говорят этими типами, не сырым JSON."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Outcome = Literal["success", "refusal", "callback", "unknown"]
Speaker = Literal["operator", "client"]
Kind = Literal[
    "price",
    "time",
    "think",
    "competitor",
    "not_interested",
    "authority",
    "send_info",
    "trust",
]
OUTCOMES: tuple[Outcome, ...] = ("success", "refusal", "callback", "unknown")
SPEAKERS: tuple[Speaker, ...] = ("operator", "client")
KINDS: tuple[Kind, ...] = (
    "price",
    "time",
    "think",
    "competitor",
    "not_interested",
    "authority",
    "send_info",
    "trust",
)


@dataclass(frozen=True)
class Turn:
    speaker: Speaker
    text: str


@dataclass(frozen=True)
class CrmCall:
    id: str
    product: str
    outcome: Outcome
    client_name: str
    company: str
    turns: tuple[Turn, ...]

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "product": self.product,
            "outcome": self.outcome,
            "client_name": self.client_name,
            "company": self.company,
            "turns": [{"speaker": turn.speaker, "text": turn.text} for turn in self.turns],
        }


@dataclass(frozen=True)
class ObjectionHit:
    kind: Kind
    client_text: str
    operator_text: str
    outcome: Outcome
    call_id: str


@dataclass(frozen=True)
class CaseFacts:
    prices: tuple[str, ...]
    discount_allowed: bool


@dataclass(frozen=True)
class PracticeCase:
    call: CrmCall
    opening: str
    objections: tuple[ObjectionHit, ...]
    facts: CaseFacts


@dataclass(frozen=True)
class LearnedKind:
    product: str
    kind: Kind
    seen: int
    client_examples: tuple[str, ...]
    helpful: tuple[str, ...]
    unhelpful: tuple[str, ...]
