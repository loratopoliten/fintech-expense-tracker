"""
Database layer — SQLite locally, PostgreSQL (Supabase) in production.
Supports both postgres:// and postgresql:// connection strings.
Railway/Supabase sometimes returns postgres:// — both are handled.
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Any

_raw_url = os.getenv("DATABASE_URL", "")

# Normalise: Railway/Supabase may give postgres:// but psycopg2 wants postgresql://
if _raw_url.startswith("postgres://"):
    DATABASE_URL = _raw_url.replace("postgres://", "postgresql://", 1)
elif _raw_url.startswith("postgresql://"):
    DATABASE_URL = _raw_url
else:
    DATABASE_URL = "db/fintrack.db"

USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        raise RuntimeError(
            "psycopg2 not installed. Run: pip install psycopg2-binary\n"
            "Or use requirements-postgres.txt for Railway."
        )


class DatabaseCursor:
    """Allow route code to use SQLite-style ? placeholders with either database."""

    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query: str, params: tuple[Any, ...] | list[Any] | None = None):
        if USE_POSTGRES:
            query = query.replace("?", "%s")
        if params is None:
            return self.cursor.execute(query)
        return self.cursor.execute(query, params)

    def executemany(self, query: str, seq_of_params):
        if USE_POSTGRES:
            query = query.replace("?", "%s")
        return self.cursor.executemany(query, seq_of_params)

    def executescript(self, script: str):
        return self.cursor.executescript(script)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def __iter__(self):
        return iter(self.cursor)


def get_db_connection():
    if USE_POSTGRES:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    else:
        os.makedirs("db", exist_ok=True)
        conn = sqlite3.connect(DATABASE_URL)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


@contextmanager
def db_cursor():
    conn = get_db_connection()
    try:
        cur = DatabaseCursor(conn.cursor())
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sqlite_init(cur):
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            username   TEXT    NOT NULL UNIQUE,
            email      TEXT    NOT NULL UNIQUE,
            password   TEXT    NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            type        TEXT    NOT NULL CHECK(type IN ('income','expense')),
            amount      REAL    NOT NULL CHECK(amount > 0),
            category    TEXT    NOT NULL,
            description TEXT,
            date        DATE    NOT NULL DEFAULT (DATE('now')),
            created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL REFERENCES users(id),
            category   TEXT    NOT NULL,
            limit_amt  REAL    NOT NULL,
            month      TEXT    NOT NULL,
            UNIQUE(user_id, category, month)
        );
        CREATE TABLE IF NOT EXISTS financial_scores (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL REFERENCES users(id),
            score        REAL    NOT NULL,
            breakdown    TEXT    NOT NULL,
            band         TEXT    NOT NULL,
            tips         TEXT    NOT NULL,
            computed_at  DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)


def _postgres_init(cur):
    statements = [
        """CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
            type TEXT NOT NULL CHECK(type IN ('income','expense')),
            amount NUMERIC NOT NULL CHECK(amount > 0),
            category TEXT NOT NULL, description TEXT,
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            created_at TIMESTAMPTZ DEFAULT NOW())""",
        """CREATE TABLE IF NOT EXISTS budgets (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
            category TEXT NOT NULL, limit_amt NUMERIC NOT NULL,
            month TEXT NOT NULL, UNIQUE(user_id, category, month))""",
        """CREATE TABLE IF NOT EXISTS financial_scores (
            id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id),
            score NUMERIC NOT NULL, breakdown TEXT NOT NULL,
            band TEXT NOT NULL, tips TEXT NOT NULL,
            computed_at TIMESTAMPTZ DEFAULT NOW())""",
    ]
    for stmt in statements:
        cur.execute(stmt)


def init_db():
    """Create all tables on startup — works for both SQLite and PostgreSQL."""
    with db_cursor() as cur:
        if USE_POSTGRES:
            _postgres_init(cur)
        else:
            _sqlite_init(cur)
