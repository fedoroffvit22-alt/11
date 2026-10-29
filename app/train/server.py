"""Локальная страница репетиции. Наружу по умолчанию не слушаем, веса не грузим."""

from __future__ import annotations

import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import unquote, urlsplit

from app.train.crm_parse import CrmImportError
from app.train.library import Library, outcome_label, practice_case
from app.train.objections import kind_label
from app.train.paths import sample_calls_path
from app.train.rehearsal import LEVELS, Rehearsal, start_rehearsal
from app.train.report import journal_rows, remember_closed

_MAX_BODY = 2_000_000
_STATIC = Path(__file__).resolve().parent / "static"
_FILES = {
    "/static/app.css": ("app.css", "text/css; charset=utf-8"),
    "/static/app.js": ("app.js", "text/javascript; charset=utf-8"),
}
_CASE = re.compile(r"^/api/cases/([^/]+)$")
_SESSION = re.compile(r"^/api/sessions/([^/]+)$")
_TURN = re.compile(r"^/api/sessions/([^/]+)/turn$")
_HANGUP = re.compile(r"^/api/sessions/([^/]+)/hangup$")


class HttpError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status = status


def make_handler(library: Library) -> type[BaseHTTPRequestHandler]:
    sessions: dict[str, Rehearsal] = {}
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self._route("GET")

        def do_POST(self) -> None:
            self._route("POST")

        def do_DELETE(self) -> None:
            self._route("DELETE")

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _route(self, method: str) -> None:
            path = urlsplit(self.path).path
            try:
                if method == "GET" and path == "/favicon.ico":
                    self.send_response(204)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if method == "GET" and path in {"/", "/index.html"}:
                    self._file(_STATIC / "index.html", "text/html; charset=utf-8")
                    return
                if method == "GET" and path in _FILES:
                    name, content_type = _FILES[path]
                    self._file(_STATIC / name, content_type)
                    return
                if method == "GET" and path == "/api/library":
                    with lock:
                        self._json(200, library_payload(library))
                    return
                if method == "GET" and path == "/api/journal":
                    self._journal()
                    return
                if method == "POST" and path == "/api/import":
                    self._import()
                    return
                if method == "POST" and path == "/api/examples":
                    self._examples()
                    return
                if method == "DELETE":
                    matched = _CASE.fullmatch(path)
                    if matched:
                        self._delete_case(unquote(matched.group(1)))
                        return
                if method == "POST" and path == "/api/sessions":
                    self._open_session()
                    return
                if method == "GET":
                    matched = _SESSION.fullmatch(path)
                    if matched:
                        self._read_session(unquote(matched.group(1)))
                        return
                if method == "POST":
                    turn = _TURN.fullmatch(path)
                    if turn:
                        self._turn(unquote(turn.group(1)))
                        return
                    hangup = _HANGUP.fullmatch(path)
                    if hangup:
                        self._hangup(unquote(hangup.group(1)))
                        return
            except HttpError as exc:
                self._json(exc.status, {"error": str(exc)})
                return
            except CrmImportError as exc:
                self._json(400, {"error": str(exc)})
                return
            self._json(404, {"error": "Такого адреса нет."})

        def _journal(self) -> None:
            try:
                rows = journal_rows(library)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise HttpError(f"Журнал не читается: {exc}", 500) from exc
            self._json(200, {"rows": rows})

        def _import(self) -> None:
            body = self._body()
            raw = body.get("text")
            if not isinstance(raw, str) or not raw.strip():
                raise HttpError("В поле text нужна выгрузка CRM.", 400)
            with lock:
                calls = library.add_text(raw)
                payload = library_payload(library)
            payload["imported"] = len(calls)
            self._json(200, payload)

        def _examples(self) -> None:
            path = sample_calls_path()
            if not path.is_file():
                raise HttpError(f"Нет учебного файла {path}.", 500)
            with lock:
                calls = library.add_text(path.read_text(encoding="utf-8"))
                payload = library_payload(library)
            payload["imported"] = len(calls)
            self._json(200, payload)

        def _delete_case(self, call_id: str) -> None:
            with lock:
                if call_id not in library.calls:
                    raise HttpError("Такого звонка в библиотеке нет.", 404)
                library.remove(call_id)
                payload = library_payload(library)
            self._json(200, payload)

        def _open_session(self) -> None:
            body = self._body()
            case_id = body.get("case_id")
            if not isinstance(case_id, str) or not case_id.strip():
                raise HttpError("Нужен case_id карточки.", 400)
            level = body.get("level", "medium")
            if not isinstance(level, str) or level not in LEVELS:
                names = ", ".join(LEVELS)
                raise HttpError(f"Уровень должен быть одним из: {names}.", 400)
            with lock:
                if case_id not in library.calls:
                    raise HttpError("Такого звонка в библиотеке нет.", 404)
                rehearsal = start_rehearsal(library.case(case_id), library.ordered(), level=level)
                sessions[rehearsal.id] = rehearsal
                payload = rehearsal.snapshot()
            self._json(200, payload)

        def _read_session(self, session_id: str) -> None:
            with lock:
                rehearsal = sessions.get(session_id)
                payload = None if rehearsal is None else rehearsal.snapshot()
            if payload is None:
                raise HttpError("Такого звонка нет. Начните его заново.", 404)
            self._json(200, payload)

        def _turn(self, session_id: str) -> None:
            body = self._body()
            text = body.get("text")
            if not isinstance(text, str):
                raise HttpError("В поле text нужна реплика оператора.", 400)
            with lock:
                rehearsal = sessions.get(session_id)
                if rehearsal is None:
                    raise HttpError("Такого звонка нет. Начните его заново.", 404)
                before = rehearsal.phase
                rehearsal.say(text)
                payload = _closed_snapshot(library, rehearsal, before)
            self._json(200, payload)

        def _hangup(self, session_id: str) -> None:
            with lock:
                rehearsal = sessions.get(session_id)
                if rehearsal is None:
                    raise HttpError("Такого звонка нет. Начните его заново.", 404)
                before = rehearsal.phase
                rehearsal.hangup()
                payload = _closed_snapshot(library, rehearsal, before)
            self._json(200, payload)

        def _body(self) -> dict[str, object]:
            length_raw = self.headers.get("Content-Length", "0")
            try:
                length = int(length_raw)
            except ValueError as exc:
                raise HttpError("Некорректный Content-Length.", 400) from exc
            if length < 0 or length > _MAX_BODY:
                raise HttpError("Слишком большая выгрузка. Лимит 2 МБ.", 413)
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise HttpError("Нужен JSON в кодировке UTF-8.", 400) from exc
            if not isinstance(payload, dict):
                raise HttpError("Нужен JSON-объект.", 400)
            return cast(dict[str, object], payload)

        def _file(self, path: Path, content_type: str) -> None:
            if not path.is_file():
                self._json(500, {"error": f"Нет файла страницы {path.name}."})
                return
            body = path.read_bytes()
            self._bytes(200, body, content_type)

        def _json(self, status: int, payload: dict[str, object]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._bytes(status, body, "application/json; charset=utf-8")

        def _bytes(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def _closed_snapshot(library: Library, rehearsal: Rehearsal, before: str) -> dict[str, object]:
    payload = rehearsal.snapshot()
    if before != "closed" and rehearsal.phase == "closed":
        remember_closed(library, payload)
    return payload


def library_payload(library: Library) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for call in library.ordered():
        case = practice_case(call)
        cases.append(
            {
                "id": call.id,
                "client_name": call.client_name,
                "company": call.company,
                "product": call.product,
                "outcome": call.outcome,
                "outcome_label": outcome_label(call.outcome),
                "objection_count": len(case.objections),
            }
        )
    learned: list[dict[str, object]] = []
    for item in library.learned():
        learned.append(
            {
                "product": item.product,
                "kind": item.kind,
                "label": kind_label(item.kind),
                "seen": item.seen,
                "client_examples": list(item.client_examples),
                "helpful": list(item.helpful),
                "unhelpful": list(item.unhelpful),
            }
        )
    return {"cases": cases, "learned": learned}


def bind(library: Library, host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), make_handler(library))


def serve(library: Library, host: str = "127.0.0.1", port: int = 8765) -> None:
    server = bind(library, host, port)
    bound = cast(tuple[str, int], server.server_address)
    print(f"Репетиция: http://{bound[0]}:{bound[1]}/")
    print("Микрофон не открывается. Клиент говорит фразами из загруженных звонков.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nРепетиция остановлена.")
    finally:
        server.server_close()
