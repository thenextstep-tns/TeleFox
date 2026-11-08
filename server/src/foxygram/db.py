"""SQLite store. One file, so a backup is a file copy."""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  color TEXT NOT NULL DEFAULT '#a371f7'
);

CREATE TABLE IF NOT EXISTS categories(
  id INTEGER PRIMARY KEY,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS chats(
  chat_id INTEGER PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  kind TEXT NOT NULL DEFAULT 'private',
  ai_enabled INTEGER NOT NULL DEFAULT 0,
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
  needs_reply INTEGER NOT NULL DEFAULT 0,
  urgency TEXT NOT NULL DEFAULT 'normal',
  last_activity INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS bursts(
  id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  created_at INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  error TEXT
);
CREATE INDEX IF NOT EXISTS bursts_status ON bursts(status, id);

-- Only chats you selected are ever written here.
CREATE TABLE IF NOT EXISTS messages(
  id INTEGER PRIMARY KEY,
  chat_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  date INTEGER NOT NULL,
  received_at INTEGER NOT NULL,
  sender_id INTEGER NOT NULL DEFAULT 0,
  sender_name TEXT NOT NULL DEFAULT '',
  outgoing INTEGER NOT NULL DEFAULT 0,
  kind TEXT NOT NULL DEFAULT 'text',
  text TEXT NOT NULL DEFAULT '',
  reply_to INTEGER NOT NULL DEFAULT 0,
  burst_id INTEGER REFERENCES bursts(id) ON DELETE SET NULL,
  context_only INTEGER NOT NULL DEFAULT 0,
  UNIQUE(chat_id, message_id)
);
CREATE INDEX IF NOT EXISTS messages_open ON messages(chat_id) WHERE burst_id IS NULL AND context_only = 0;
CREATE INDEX IF NOT EXISTS messages_burst ON messages(burst_id);

CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
  text, content='messages', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
  INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF text ON messages BEGIN
  INSERT INTO messages_fts(messages_fts, rowid, text) VALUES ('delete', old.id, old.text);
  INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS message_entities(
  chat_id INTEGER NOT NULL,
  message_id INTEGER NOT NULL,
  type TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY(chat_id, message_id, type, value)
);

CREATE TABLE IF NOT EXISTS analyses(
  burst_id INTEGER PRIMARY KEY REFERENCES bursts(id) ON DELETE CASCADE,
  intent TEXT NOT NULL,
  needs_reply INTEGER NOT NULL,
  urgency TEXT NOT NULL,
  summary TEXT NOT NULL,
  model TEXT NOT NULL,
  created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cases(
  id INTEGER PRIMARY KEY,
  title TEXT NOT NULL,
  summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open',
  project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS cases_updated ON cases(status, updated_at DESC);

CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
  title, summary, content='cases', content_rowid='id', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS cases_ai AFTER INSERT ON cases BEGIN
  INSERT INTO cases_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;
CREATE TRIGGER IF NOT EXISTS cases_ad AFTER DELETE ON cases BEGIN
  INSERT INTO cases_fts(cases_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
END;
CREATE TRIGGER IF NOT EXISTS cases_au AFTER UPDATE OF title, summary ON cases BEGIN
  INSERT INTO cases_fts(cases_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
  INSERT INTO cases_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TABLE IF NOT EXISTS case_links(
  burst_id INTEGER PRIMARY KEY REFERENCES bursts(id) ON DELETE CASCADE,
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  source TEXT NOT NULL,
  confidence REAL NOT NULL DEFAULT 1.0,
  needs_review INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS case_links_case ON case_links(case_id);

CREATE TABLE IF NOT EXISTS case_entities(
  case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  value TEXT NOT NULL,
  PRIMARY KEY(case_id, type, value)
);
CREATE INDEX IF NOT EXISTS case_entities_lookup ON case_entities(type, value);

-- Your manual fixes, fed back to Claude as examples.
CREATE TABLE IF NOT EXISTS corrections(
  id INTEGER PRIMARY KEY,
  created_at INTEGER NOT NULL,
  burst_summary TEXT NOT NULL,
  from_case TEXT,
  to_case TEXT
);

CREATE TABLE IF NOT EXISTS devices(
  token TEXT PRIMARY KEY,
  name TEXT NOT NULL DEFAULT '',
  updated_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS claude_calls(
  id INTEGER PRIMARY KEY,
  at INTEGER NOT NULL,
  ok INTEGER NOT NULL,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  duration_ms INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS claude_calls_at ON claude_calls(at);

CREATE TABLE IF NOT EXISTS kv(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now() -> int:
    return int(time.time())


class Database:
    def __init__(self, path: Path | str):
        self._conn = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(SCHEMA)

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._conn.execute(sql, tuple(params))

    def all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, tuple(params)).fetchall()]

    def one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
            return dict(row) if row else None

    def scalar(self, sql: str, params: Iterable[Any] = ()) -> Any:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
            return row[0] if row else None

    def transaction(self):
        return _Transaction(self)

    def get_kv(self, key: str, default: str = "") -> str:
        value = self.scalar("SELECT value FROM kv WHERE key = ?", (key,))
        return default if value is None else value

    def set_kv(self, key: str, value: str) -> None:
        self.execute(
            "INSERT INTO kv(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class _Transaction:
    def __init__(self, db: Database):
        self.db = db

    def __enter__(self) -> Database:
        self.db._lock.acquire()
        self.db._conn.execute("BEGIN IMMEDIATE")
        return self.db

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            self.db._conn.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.db._lock.release()
