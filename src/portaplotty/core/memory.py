from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_DEFAULT_DB_PATH = Path.home() / ".portaplotty" / "cache.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS apps (
    fingerprint  TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT,
    kind         TEXT NOT NULL,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL
);
"""


@dataclass
class AppRecord:
    fingerprint: str
    name: str
    description: str | None
    kind: str
    first_seen: str
    last_seen: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@contextmanager
def _connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


class Memory:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or _DEFAULT_DB_PATH

    def lookup(self, fingerprint: str) -> AppRecord | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM apps WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if row is None:
                return None
            return AppRecord(**dict(row))

    def remember(
        self,
        fingerprint: str,
        name: str,
        kind: str,
        description: str | None = None,
    ) -> AppRecord:
        """Upsert a record. Updates name/description/kind, bumps last_seen."""
        now = _now()
        with _connect(self.db_path) as conn:
            existing = conn.execute(
                "SELECT first_seen FROM apps WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO apps (fingerprint, name, description, kind, first_seen, last_seen) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (fingerprint, name, description, kind, now, now),
                )
                first_seen = now
            else:
                conn.execute(
                    "UPDATE apps SET name = ?, description = ?, kind = ?, last_seen = ? "
                    "WHERE fingerprint = ?",
                    (name, description, kind, now, fingerprint),
                )
                first_seen = existing["first_seen"]
        return AppRecord(fingerprint, name, description, kind, first_seen, now)

    def touch(self, fingerprint: str) -> None:
        """Bump last_seen only. No-op if fingerprint unknown."""
        with _connect(self.db_path) as conn:
            conn.execute(
                "UPDATE apps SET last_seen = ? WHERE fingerprint = ?",
                (_now(), fingerprint),
            )

    def update_user_fields(
        self,
        fingerprint: str,
        name: str | None = None,
        description: str | None = None,
    ) -> AppRecord | None:
        """Used by the web FE for user renames. Returns updated record or None if not found."""
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM apps WHERE fingerprint = ?", (fingerprint,)
            ).fetchone()
            if row is None:
                return None
            new_name = name if name is not None else row["name"]
            new_desc = description if description is not None else row["description"]
            now = _now()
            conn.execute(
                "UPDATE apps SET name = ?, description = ?, last_seen = ? WHERE fingerprint = ?",
                (new_name, new_desc, now, fingerprint),
            )
            return AppRecord(
                fingerprint=fingerprint,
                name=new_name,
                description=new_desc,
                kind=row["kind"],
                first_seen=row["first_seen"],
                last_seen=now,
            )
