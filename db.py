"""SQLite adapter and query helpers for BrewBot."""

import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator

DB_PATH = os.getenv("DB_PATH", "brewbot.db")


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a SQLite connection with row_factory set and FK enforcement on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create all four tables if they don't already exist."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                email           TEXT,
                department      TEXT NOT NULL,
                manager         TEXT NOT NULL,
                region          TEXT NOT NULL,
                timezone        TEXT,
                job_level       TEXT,
                tenure_months   INTEGER,
                opted_in        INTEGER DEFAULT 1,
                opt_in_date     TEXT,
                goals           TEXT,
                interests       TEXT,
                program         TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cycles (
                id              TEXT PRIMARY KEY,
                program         TEXT DEFAULT 'open',
                start_date      TEXT NOT NULL,
                end_date        TEXT NOT NULL,
                total_opted_in  INTEGER DEFAULT 0,
                total_matched   INTEGER DEFAULT 0,
                total_completed INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS matches (
                id              TEXT PRIMARY KEY,
                employee_a_id   TEXT NOT NULL REFERENCES employees(id),
                employee_b_id   TEXT NOT NULL REFERENCES employees(id),
                cycle_id        TEXT NOT NULL REFERENCES cycles(id),
                matched_date    TEXT DEFAULT (datetime('now')),
                status          TEXT DEFAULT 'pending',
                awardco_code_a  TEXT,
                awardco_code_b  TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS completions (
                id              TEXT PRIMARY KEY,
                match_id        TEXT NOT NULL REFERENCES matches(id),
                completed_date  TEXT,
                confirmed_by_a  INTEGER DEFAULT 0,
                confirmed_by_b  INTEGER DEFAULT 0,
                feedback_a      TEXT,
                feedback_b      TEXT,
                rating_a        INTEGER,
                rating_b        INTEGER,
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
