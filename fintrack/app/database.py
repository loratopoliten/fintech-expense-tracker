"""
Database layer — SQLite locally, PostgreSQL on Supabase (CapitalPyre deploy pattern).
Switch DATABASE_URL env var to use Postgres:
  postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
"""

import sqlite3
import os
from contextlib import contextmanager
from typing import Any

DATABASE_URL = os.getenv("DATABASE_URL") or "db/fintrack.db"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]
USE_POSTGRES = DATABASE_URL.startswith("postgresql://")

if USE_POSTGRES:
    import psycopg2
    from psycopg2.extras import RealDictCursor


class DatabaseCursor:
    """Small adapter so app queries can use SQLite-style ? parameters everywhere."""

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

def init_db():
    """Create all tables on startup."""
    os.makedirs("db", exist_ok=True)
    with db_cursor() as cur:
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
        """) if not USE_POSTGRES else None

        if USE_POSTGRES:
            # Postgres-compatible schema (same structure)
            for stmt in [
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
            ]:
                cur.execute(stmt)
