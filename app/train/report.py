"""Сводка занятия: закрытые звонки в CSV, без прослушивания записи."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import cast

from app.train.library import Library


def render_csv(snapshots: list[dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["case_id", "result", "handled", "spoken", "objections"])
    for item in snapshots:
        debrief = item.get("debrief")
        studies: list[object] = []
        handled = 0
        spoken = 0
        if isinstance(debrief, dict):
            raw_studies = debrief.get("studies")
            if isinstance(raw_studies, list):
                studies = raw_studies
            handled = _count(debrief.get("handled"))
            spoken = _count(debrief.get("spoken"))
        labels = [_label(study) for study in studies]
        writer.writerow(
            [
                _text(item.get("case_id")),
                _text(item.get("result")),
                handled,
                spoken,
                "; ".join(label for label in labels if label),
            ]
        )
    return buffer.getvalue()


def remember_closed(library: Library, snapshot: dict[str, object]) -> None:
    if snapshot.get("phase") != "closed" or library.path is None:
        return
    target = library.path.parent / "sessions.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def read_sessions(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(cast(dict[str, object], item))
    return rows


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _label(study: object) -> str:
    if not isinstance(study, dict):
        return ""
    label = study.get("label")
    return label if isinstance(label, str) else ""
