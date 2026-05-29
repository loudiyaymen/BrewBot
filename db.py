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


def upsert_employee(data: dict) -> None:
    """Insert or update an employee record keyed on Slack user ID."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO employees
                (id, name, email, department, manager, region, timezone,
                 job_level, tenure_months, opted_in, opt_in_date, goals, interests, program)
            VALUES
                (:id, :name, :email, :department, :manager, :region, :timezone,
                 :job_level, :tenure_months, :opted_in, :opt_in_date, :goals, :interests, :program)
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                email         = COALESCE(excluded.email, email),
                department    = excluded.department,
                manager       = excluded.manager,
                region        = excluded.region,
                timezone      = COALESCE(excluded.timezone, timezone),
                job_level     = excluded.job_level,
                tenure_months = excluded.tenure_months,
                opted_in      = excluded.opted_in,
                opt_in_date   = excluded.opt_in_date,
                goals         = excluded.goals,
                interests     = excluded.interests,
                program       = excluded.program
            """,
            {
                "id": data["id"],
                "name": data["name"],
                "email": data.get("email"),
                "department": data["department"],
                "manager": data["manager"],
                "region": data["region"],
                "timezone": data.get("timezone"),
                "job_level": data.get("job_level"),
                "tenure_months": data.get("tenure_months"),
                "opted_in": data.get("opted_in", 1),
                "opt_in_date": data.get("opt_in_date"),
                "goals": data.get("goals", ""),
                "interests": data.get("interests", ""),
                "program": data.get("program", "open"),
            },
        )


def get_opted_in_employees(region: str | None = None) -> list[dict]:
    """Return all opted-in employees, optionally filtered by region."""
    with get_db() as conn:
        if region:
            rows = conn.execute(
                "SELECT * FROM employees WHERE opted_in = 1 AND region = ?", (region,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM employees WHERE opted_in = 1"
            ).fetchall()
        return [dict(r) for r in rows]


def get_match_history() -> set[frozenset]:
    """Return all historical matched pairs as a set of frozensets of employee IDs."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT employee_a_id, employee_b_id FROM matches"
        ).fetchall()
        return {frozenset((r["employee_a_id"], r["employee_b_id"])) for r in rows}


def create_cycle(program: str, start_date: str, end_date: str) -> str:
    """Insert a new cycle row and return its UUID."""
    cycle_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            "INSERT INTO cycles (id, program, start_date, end_date) VALUES (?, ?, ?, ?)",
            (cycle_id, program, start_date, end_date),
        )
    return cycle_id


def update_cycle_totals(cycle_id: str, total_opted_in: int, total_matched: int) -> None:
    """Patch opted_in and matched counts on a cycle row."""
    with get_db() as conn:
        conn.execute(
            "UPDATE cycles SET total_opted_in = ?, total_matched = ? WHERE id = ?",
            (total_opted_in, total_matched, cycle_id),
        )


def create_match(employee_a_id: str, employee_b_id: str, cycle_id: str) -> str:
    """Insert a new match row and return its UUID."""
    match_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO matches (id, employee_a_id, employee_b_id, cycle_id)
               VALUES (?, ?, ?, ?)""",
            (match_id, employee_a_id, employee_b_id, cycle_id),
        )
    return match_id


def update_match_status(match_id: str, status: str) -> None:
    """Set the status field on a match row."""
    with get_db() as conn:
        conn.execute(
            "UPDATE matches SET status = ? WHERE id = ?", (status, match_id)
        )


def get_pending_matches_older_than(hours: int) -> list[dict]:
    """Return pending matches whose matched_date is older than `hours` hours."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.employee_a_id, m.employee_b_id,
                   ea.name AS employee_a_name, eb.name AS employee_b_name
            FROM matches m
            JOIN employees ea ON m.employee_a_id = ea.id
            JOIN employees eb ON m.employee_b_id = eb.id
            WHERE m.status = 'pending' AND m.matched_date < ?
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_active_matches_near_cycle_end(days_threshold: int = 3) -> list[dict]:
    """Return non-completed matches in cycles ending within `days_threshold` days."""
    now = datetime.utcnow().isoformat()
    cutoff = (datetime.utcnow() + timedelta(days=days_threshold)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT m.id, m.employee_a_id, m.employee_b_id,
                   ea.name AS employee_a_name, eb.name AS employee_b_name,
                   CAST(julianday(c.end_date) - julianday(:now) AS INTEGER) AS days_left
            FROM matches m
            JOIN employees ea ON m.employee_a_id = ea.id
            JOIN employees eb ON m.employee_b_id = eb.id
            JOIN cycles c ON m.cycle_id = c.id
            WHERE m.status NOT IN ('completed', 'ghosted')
              AND c.end_date <= :cutoff
              AND c.end_date > :now
            """,
            {"now": now, "cutoff": cutoff},
        ).fetchall()
        return [dict(r) for r in rows]


def upsert_completion(match_id: str, confirmed_by: str, rating: int, feedback: str) -> None:
    """Insert or update a completion row; fills the confirming employee's columns."""
    with get_db() as conn:
        match = conn.execute(
            "SELECT employee_a_id FROM matches WHERE id = ?", (match_id,)
        ).fetchone()
        if not match:
            return

        is_a = match["employee_a_id"] == confirmed_by
        rating_col = "rating_a" if is_a else "rating_b"
        feedback_col = "feedback_a" if is_a else "feedback_b"
        confirmed_col = "confirmed_by_a" if is_a else "confirmed_by_b"

        existing = conn.execute(
            "SELECT id FROM completions WHERE match_id = ?", (match_id,)
        ).fetchone()

        if existing:
            conn.execute(
                f"UPDATE completions SET {rating_col}=?, {feedback_col}=?, {confirmed_col}=1 WHERE match_id=?",
                (rating, feedback, match_id),
            )
        else:
            conn.execute(
                f"""INSERT INTO completions
                    (id, match_id, completed_date, {confirmed_col}, {rating_col}, {feedback_col})
                    VALUES (?, ?, ?, 1, ?, ?)""",
                (str(uuid.uuid4()), match_id, datetime.utcnow().isoformat(), rating, feedback),
            )


def get_partner_name(match_id: str, user_id: str) -> str:
    """Return the name of the other employee in a match."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT ea.name AS employee_a_name, eb.name AS employee_b_name, m.employee_a_id
            FROM matches m
            JOIN employees ea ON m.employee_a_id = ea.id
            JOIN employees eb ON m.employee_b_id = eb.id
            WHERE m.id = ?
            """,
            (match_id,),
        ).fetchone()
        if not row:
            return "your match"
        return row["employee_b_name"] if row["employee_a_id"] == user_id else row["employee_a_name"]


def get_current_cycle() -> dict | None:
    """Return the most recently created cycle row, or None."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM cycles ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None


def ghost_unresolved_matches(cycle_id: str) -> None:
    """Mark all non-completed matches in a cycle as ghosted."""
    with get_db() as conn:
        conn.execute(
            """UPDATE matches SET status = 'ghosted'
               WHERE cycle_id = ? AND status NOT IN ('completed', 'ghosted')""",
            (cycle_id,),
        )


def get_cycle_stats(cycle_id: str) -> dict:
    """Return a stats dict for the given cycle, including match status counts and avg rating."""
    with get_db() as conn:
        cycle = conn.execute(
            "SELECT * FROM cycles WHERE id = ?", (cycle_id,)
        ).fetchone()
        if not cycle:
            return {}

        counts = conn.execute(
            """
            SELECT
                COUNT(*) * 2                                                      AS total_matched,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END)            AS total_completed,
                SUM(CASE WHEN status = 'ghosted'   THEN 1 ELSE 0 END)            AS total_ghosted,
                SUM(CASE WHEN status IN ('pending','nudged') THEN 1 ELSE 0 END)  AS total_pending,
                SUM(CASE WHEN status = 'nudged'    THEN 1 ELSE 0 END)            AS total_nudged
            FROM matches WHERE cycle_id = ?
            """,
            (cycle_id,),
        ).fetchone()

        avg_row = conn.execute(
            """
            SELECT AVG(
                CASE WHEN c.rating_a IS NOT NULL AND c.rating_b IS NOT NULL
                     THEN (c.rating_a + c.rating_b) / 2.0
                     ELSE COALESCE(c.rating_a, c.rating_b) END
            ) AS avg_rating
            FROM completions c
            JOIN matches m ON c.match_id = m.id
            WHERE m.cycle_id = ?
            """,
            (cycle_id,),
        ).fetchone()

        avg_rating = avg_row["avg_rating"]
        return {
            **dict(cycle),
            "total_matched": counts["total_matched"] or 0,
            "total_completed": counts["total_completed"] or 0,
            "total_ghosted": counts["total_ghosted"] or 0,
            "total_pending": counts["total_pending"] or 0,
            "total_nudged": counts["total_nudged"] or 0,
            "avg_rating": round(avg_rating, 1) if avg_rating else None,
        }
