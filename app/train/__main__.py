"""Страница репетиции и импорт выгрузки CRM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.settings import Settings
from app.train.audio_import import AudioImportError, import_recorded_call
from app.train.crm_parse import CrmImportError
from app.train.library import Library, LibraryError, outcome_label, practice_case
from app.train.objections import kind_label
from app.train.paths import default_library_path
from app.train.report import read_sessions, render_csv
from app.train.server import serve
from app.train.speak_turn import speak_case


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Репетиция звонка клиенту по выгрузке CRM")
    parser.add_argument("--data", type=Path, default=None, help="Файл библиотеки. По умолчанию data/train/library.json")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="Открыть страницу репетиции")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)

    import_parser = sub.add_parser("import", help="Разобрать файл выгрузки и добавить его в библиотеку")
    import_parser.add_argument("path", type=Path)

    audio_parser = sub.add_parser("audio", help="Положить WAV из CRM в библиотеку. Нужна расшифровка рядом")
    audio_parser.add_argument("--wav", type=Path, required=True)
    audio_parser.add_argument("--transcript", type=Path, default=None)

    speak_parser = sub.add_parser("speak", help="Один голосовой ход репетиции. Веса качает только эта команда")
    speak_parser.add_argument("--case", required=True)
    speak_parser.add_argument("--wav", type=Path, required=True)
    speak_parser.add_argument("--out", type=Path, required=True)

    report_parser = sub.add_parser("report", help="Сводка закрытых звонков: карточка, итог, возражения")
    report_parser.add_argument("--out", type=Path, required=True)
    report_parser.add_argument(
        "--sessions",
        type=Path,
        default=None,
        help="sessions.jsonl рядом с библиотекой, если путь не задан",
    )

    args = parser.parse_args(argv)
    path = args.data if args.data is not None else default_library_path()
    try:
        library = Library(path)
    except LibraryError as exc:
        print(exc)
        return 1
    if args.command == "import":
        return _import(library, args.path)
    if args.command == "audio":
        return _audio(library, args.wav, args.transcript)
    if args.command == "speak":
        return speak_case(
            case_id=args.case,
            wav=args.wav,
            out=args.out,
            settings=Settings.from_env(),
            library=library,
        )
    if args.command == "report":
        return _report(library, args.out, args.sessions)
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8765)
    serve(library, host, port)
    return 0


def _audio(library: Library, wav: Path, transcript: Path | None) -> int:
    try:
        call = import_recorded_call(library, wav, transcript, Settings.from_env())
    except AudioImportError as exc:
        print(exc)
        return 1
    print(f"В библиотеке {call.id} · {call.client_name or 'без имени'} · {call.product}.")
    return 0


def _report(library: Library, out: Path, sessions: Path | None) -> int:
    path = sessions
    if path is None and library.path is not None:
        path = library.path.parent / "sessions.jsonl"
    if path is None or not path.is_file():
        print(f"Нет файла сессий {path}.")
        return 1
    try:
        rows = read_sessions(path)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(exc)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_csv(rows), encoding="utf-8")
    return 0


def _import(library: Library, path: Path) -> int:
    if not path.is_file():
        print(f"Нет файла {path}.")
        return 1
    try:
        calls = library.add_text(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, CrmImportError) as exc:
        print(exc)
        return 1
    print(f"Разобрано звонков: {len(calls)}.")
    for call in calls:
        case = practice_case(call)
        kinds = ", ".join(kind_label(hit.kind) for hit in case.objections) or "нет"
        who = call.client_name or "без имени"
        print(f"{call.id} · {who} · {call.product} · {outcome_label(call.outcome)} · возражения: {kinds}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
