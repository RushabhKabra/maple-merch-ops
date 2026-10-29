from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "merchops.sqlite3"

def connect(path=DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn

def initialize(path=DEFAULT_DB):
    with connect(path) as conn:
        conn.executescript((ROOT / "sql" / "schema.sql").read_text())

@contextmanager
def transaction(path=DEFAULT_DB):
    conn = connect(path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def rows(conn, sql, params=()):
    return [dict(row) for row in conn.execute(sql, params).fetchall()]

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def log(conn, action, reference, before=None, after=None, actor="Local operator"):
    conn.execute("INSERT INTO audit_log(at,actor,action,reference,before_json,after_json) VALUES(?,?,?,?,?,?)",
                 (now(), actor, action, reference, json.dumps(before or {}), json.dumps(after or {})))

def as_of(conn):
    return conn.execute("SELECT value FROM settings WHERE key='as_of'").fetchone()[0]
