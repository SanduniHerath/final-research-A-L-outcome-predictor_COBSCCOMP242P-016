"""Database of everything students do in the app (SQLite, one file, no server needed).

Each browser gets a random visit code (``X-Alora-Session`` header, made by the interface). No name,
e-mail, IP address or device details are stored. A student can delete everything stored for their
visit code from the About page (``DELETE /api/my-data``).

Tables:

| Table | One row per |
|---|---|
| sessions | browser (visit code), with first and last time seen and the language |
| profiles | different set of answers a browser sent |
| results | answer from a system part (predict, gap, recommend, explain, chat) |
| chat_messages | chatbot question and its reply |

Export to CSV for analysis::

    python -m backend.storage export            # -> data/app/export/<table>.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from src.utils.config import load_config, resolve_path

log = logging.getLogger(__name__)

TABLES = ("sessions", "profiles", "results", "chat_messages")
_SESSION = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_LANGS = {"en", "si", "ta"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    language    TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    answers_hash TEXT NOT NULL,
    answers_json TEXT NOT NULL,
    is_example   INTEGER NOT NULL,
    created_at   TEXT NOT NULL,
    UNIQUE (session_id, answers_hash)
);
CREATE TABLE IF NOT EXISTS results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    profile_id   INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    part         TEXT NOT NULL,
    options_json TEXT,
    result_json  TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chat_messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT REFERENCES sessions(session_id) ON DELETE CASCADE,
    profile_id  INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    question    TEXT NOT NULL,
    reply       TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
-- Visit codes whose data was deleted. A request still running at the moment of deletion must not
-- store its result afterwards; the interface makes a new code after deleting, so the old one is
-- never used again. Holds only the random code and the time.
CREATE TABLE IF NOT EXISTS deleted_sessions (
    session_id  TEXT PRIMARY KEY,
    deleted_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profiles_session ON profiles(session_id);
CREATE INDEX IF NOT EXISTS idx_results_session ON results(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_session ON chat_messages(session_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _json(value: object) -> str:
    return json.dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True)


def clean_session(value: str | None) -> str | None:
    """The visit code if it looks like one the interface makes, otherwise None (stored as unknown)."""
    value = (value or "").strip().lower()
    return value if _SESSION.match(value) else None


class AppStore:
    """Writes app usage to SQLite. A failed write is logged and never breaks the app."""

    def __init__(self, path: str | Path) -> None:
        """Open (and if needed create) the database file at ``path``."""
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._examples = list(load_config("example_profiles").values())
        with self._connect() as db:
            db.executescript(SCHEMA)

    @classmethod
    def from_config(cls) -> AppStore | None:
        """The store set in ``configs/app.yaml`` (``storage``), or None if storage is switched off.

        The ``ALORA_DB`` environment variable replaces the path (the tests use a temporary file).
        """
        settings = load_config("app").get("storage", {})
        if not settings.get("enabled"):
            return None
        return cls(resolve_path(os.environ.get("ALORA_DB") or settings["path"]))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            db = sqlite3.connect(self.path)
            try:
                db.execute("PRAGMA foreign_keys = ON")
                db.execute("PRAGMA journal_mode = WAL")
                yield db
                db.commit()
            finally:
                db.close()

    def _is_example(self, answers: dict[str, Any]) -> bool:
        return any(all(answers.get(k) == v for k, v in ex.items()) for ex in self._examples)

    def _profile_id(
        self, db: sqlite3.Connection, session: str | None, lang: str | None, answers: dict[str, Any]
    ) -> int:
        now = _now()
        if session:
            db.execute(
                "INSERT INTO sessions (session_id, first_seen, last_seen, language) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(session_id) DO UPDATE SET last_seen = excluded.last_seen,"
                " language = COALESCE(excluded.language, sessions.language)",
                (session, now, now, lang if lang in _LANGS else None),
            )
        text = _json(answers)
        digest = hashlib.sha256(text.encode()).hexdigest()
        row = db.execute(
            "SELECT id FROM profiles WHERE session_id IS ? AND answers_hash = ?", (session, digest)
        ).fetchone()
        if row:
            return int(row[0])
        cursor = db.execute(
            "INSERT INTO profiles (session_id, answers_hash, answers_json, is_example, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (session, digest, text, int(self._is_example(answers)), now),
        )
        return int(cursor.lastrowid)

    def record(
        self,
        part: str,
        answers: dict[str, Any],
        result: dict[str, Any],
        *,
        session: str | None = None,
        lang: str | None = None,
        options: dict[str, Any] | None = None,
        question: str | None = None,
    ) -> None:
        """Store one answer of a system part (and, for the chatbot, the question and reply)."""
        try:
            with self._connect() as db:
                if session and db.execute(
                    "SELECT 1 FROM deleted_sessions WHERE session_id = ?", (session,)
                ).fetchone():
                    return  # the student deleted this visit's data; never store it again
                profile_id = self._profile_id(db, session, lang, answers)
                now = _now()
                db.execute(
                    "INSERT INTO results (session_id, profile_id, part, options_json, result_json,"
                    " created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        session,
                        profile_id,
                        part,
                        _json(options) if options else None,
                        _json(result),
                        now,
                    ),
                )
                if question is not None:
                    db.execute(
                        "INSERT INTO chat_messages (session_id, profile_id, question, reply, created_at)"
                        " VALUES (?, ?, ?, ?, ?)",
                        (session, profile_id, question, str(result.get("reply", "")), now),
                    )
        except sqlite3.Error:
            log.exception("Could not store the %s result", part)

    def delete_session(self, session: str) -> int:
        """Delete everything stored for one visit code; returns the number of rows removed."""
        with self._connect() as db:
            removed = sum(
                db.execute(f"DELETE FROM {table} WHERE session_id = ?", (session,)).rowcount
                for table in ("chat_messages", "results", "profiles", "sessions")
            )
            db.execute(
                "INSERT OR IGNORE INTO deleted_sessions (session_id, deleted_at) VALUES (?, ?)",
                (session, _now()),
            )
        return removed

    def counts(self) -> dict[str, int]:
        """Number of rows in each table."""
        with self._connect() as db:
            return {t: int(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]) for t in TABLES}

    def export_csv(self, out_dir: str | Path) -> list[Path]:
        """Write every table to ``<out_dir>/<table>.csv`` (UTF-8 with BOM so Excel shows Sinhala/Tamil)."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        written = []
        with self._connect() as db:
            for table in TABLES:
                cursor = db.execute(f"SELECT * FROM {table} ORDER BY 1")
                path = out / f"{table}.csv"
                with path.open("w", newline="", encoding="utf-8-sig") as handle:
                    writer = csv.writer(handle)
                    writer.writerow([c[0] for c in cursor.description])
                    writer.writerows(cursor)
                written.append(path)
        return written


def main() -> None:
    """Command line: ``counts`` or ``export``."""
    parser = argparse.ArgumentParser(description="Alora app database tools")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="write every table to CSV")
    export.add_argument("--out", default="data/app/export")
    sub.add_parser("counts", help="number of rows in each table")
    args = parser.parse_args()

    store = AppStore(resolve_path(load_config("app")["storage"]["path"]))
    if args.command == "counts":
        for table, n in store.counts().items():
            print(f"{table:14} {n}")
    else:
        for path in store.export_csv(resolve_path(args.out)):
            print(path)


if __name__ == "__main__":
    main()
