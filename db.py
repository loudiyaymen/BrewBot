"""SQLite adapter and query helpers for BrewBot."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Generator

DB_PATH = os.getenv("DB_PATH", "brewbot.db")


def _json_list(value) -> list:
    """Decode a JSON-array TEXT column into a list; tolerate NULL/blank/bad data."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def _row_to_employee(row: sqlite3.Row) -> dict:
    """Convert an employees row to a dict with goals_list/interests_list decoded."""
    data = dict(row)
    data["goals_list"] = _json_list(data.get("goals_list"))
    data["interests_list"] = _json_list(data.get("interests_list"))
    return data


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


# Columns added after the original four-table schema shipped. Applied idempotently
# to existing databases by _migrate(); also present in the CREATE TABLE bodies below
# so fresh databases get them directly.
_MIGRATIONS: list[tuple[str, str]] = [
    ("employees", "goals_list TEXT"),
    ("employees", "interests_list TEXT"),
    ("employees", "connection_type TEXT DEFAULT 'open'"),
    ("employees", "match_frequency TEXT DEFAULT 'biweekly'"),
    ("employees", "location TEXT"),
    ("employees", "meeting_preference TEXT DEFAULT 'either'"),
    ("employees", "round_optin INTEGER DEFAULT 1"),
    ("employees", "paused_until TEXT"),
    ("employees", "mode TEXT DEFAULT 'matched'"),
    ("matches", "match_type TEXT DEFAULT 'ai'"),
    ("matches", "match_score REAL"),
    ("matches", "match_reason TEXT"),
    ("matches", "group_id TEXT"),
    ("completions", "goals_met_a INTEGER"),
    ("completions", "goals_met_b INTEGER"),
    ("completions", "want_to_reconnect_a INTEGER"),
    ("completions", "want_to_reconnect_b INTEGER"),
    ("completions", "followup_sent INTEGER DEFAULT 0"),
    ("completions", "followup_response_a TEXT"),
    ("completions", "followup_response_b TEXT"),
]


def _migrate(conn: sqlite3.Connection) -> None:
    """Add newer columns to existing tables; no-op if they already exist."""
    for table, column_def in _MIGRATIONS:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
        except sqlite3.OperationalError:
            # "duplicate column name" — column already present, nothing to do.
            pass


def init_db() -> None:
    """Create all four tables if they don't already exist, then apply migrations."""
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id                 TEXT PRIMARY KEY,
                name               TEXT NOT NULL,
                email              TEXT,
                department         TEXT NOT NULL,
                manager            TEXT NOT NULL,
                region             TEXT NOT NULL,
                timezone           TEXT,
                job_level          TEXT,
                tenure_months      INTEGER,
                opted_in           INTEGER DEFAULT 1,
                opt_in_date        TEXT,
                goals              TEXT,
                interests          TEXT,
                goals_list         TEXT,
                interests_list     TEXT,
                connection_type    TEXT DEFAULT 'open',
                match_frequency    TEXT DEFAULT 'biweekly',
                location           TEXT,
                meeting_preference TEXT DEFAULT 'either',
                round_optin        INTEGER DEFAULT 1,
                paused_until       TEXT,
                mode               TEXT DEFAULT 'matched',
                program            TEXT,
                created_at         TEXT DEFAULT (datetime('now'))
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
                match_type      TEXT DEFAULT 'ai',
                match_score     REAL,
                match_reason    TEXT,
                group_id        TEXT,
                awardco_code_a  TEXT,
                awardco_code_b  TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS completions (
                id                  TEXT PRIMARY KEY,
                match_id            TEXT NOT NULL REFERENCES matches(id),
                completed_date      TEXT,
                confirmed_by_a      INTEGER DEFAULT 0,
                confirmed_by_b      INTEGER DEFAULT 0,
                feedback_a          TEXT,
                feedback_b          TEXT,
                rating_a            INTEGER,
                rating_b            INTEGER,
                goals_met_a         INTEGER,
                goals_met_b         INTEGER,
                want_to_reconnect_a INTEGER,
                want_to_reconnect_b INTEGER,
                followup_sent       INTEGER DEFAULT 0,
                followup_response_a TEXT,
                followup_response_b TEXT,
                created_at          TEXT DEFAULT (datetime('now'))
            );
        """)
        _migrate(conn)


def upsert_employee(data: dict) -> None:
    """Insert or update an employee record keyed on Slack user ID."""
    with get_db() as conn:
        goals_list = data.get("goals_list") or []
        interests_list = data.get("interests_list") or []
        conn.execute(
            """
            INSERT INTO employees
                (id, name, email, department, manager, region, timezone,
                 job_level, tenure_months, opted_in, opt_in_date, goals, interests,
                 goals_list, interests_list, connection_type, match_frequency,
                 location, meeting_preference, round_optin, mode, program)
            VALUES
                (:id, :name, :email, :department, :manager, :region, :timezone,
                 :job_level, :tenure_months, :opted_in, :opt_in_date, :goals, :interests,
                 :goals_list, :interests_list, :connection_type, :match_frequency,
                 :location, :meeting_preference, :round_optin, :mode, :program)
            ON CONFLICT(id) DO UPDATE SET
                name               = excluded.name,
                email              = COALESCE(excluded.email, email),
                department         = excluded.department,
                manager            = excluded.manager,
                region             = excluded.region,
                timezone           = COALESCE(excluded.timezone, timezone),
                job_level          = excluded.job_level,
                tenure_months      = excluded.tenure_months,
                opted_in           = excluded.opted_in,
                opt_in_date        = excluded.opt_in_date,
                goals              = excluded.goals,
                interests          = excluded.interests,
                goals_list         = excluded.goals_list,
                interests_list     = excluded.interests_list,
                connection_type    = excluded.connection_type,
                match_frequency    = excluded.match_frequency,
                location           = excluded.location,
                meeting_preference = excluded.meeting_preference,
                round_optin        = excluded.round_optin,
                mode               = excluded.mode,
                program            = excluded.program
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
                # Keep legacy free-text columns populated for back-compat / readability.
                "goals": data.get("goals") or ", ".join(goals_list),
                "interests": data.get("interests") or ", ".join(interests_list),
                "goals_list": json.dumps(goals_list),
                "interests_list": json.dumps(interests_list),
                "connection_type": data.get("connection_type", "open"),
                "match_frequency": data.get("match_frequency", "biweekly"),
                "location": data.get("location"),
                "meeting_preference": data.get("meeting_preference", "either"),
                "round_optin": data.get("round_optin", 1),
                "mode": data.get("mode", "matched"),
                "program": data.get("program", "open"),
            },
        )


def ensure_employee_stub(user_id: str, name: str = "A CrowdStriker") -> None:
    """Insert a minimal placeholder for a self-selected partner who hasn't opted in.

    Required fields get placeholders and the row is left out of the automated pool
    (opted_in=0). If the person later runs /crowdbrew, upsert_employee overwrites it
    with their real data.
    """
    with get_db() as conn:
        exists = conn.execute(
            "SELECT 1 FROM employees WHERE id = ?", (user_id,)
        ).fetchone()
        if exists:
            return
        conn.execute(
            """INSERT INTO employees
                   (id, name, department, manager, region, opted_in, round_optin, mode)
               VALUES (?, ?, 'unknown', 'unknown', 'unknown', 0, 0, 'self_select')""",
            (user_id, name),
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
        return [_row_to_employee(r) for r in rows]


def get_opted_in_employees_for_cycle(
    cycle_type: str = "biweekly", program: str | None = None
) -> list[dict]:
    """Return participants eligible for this round.

    Honors per-round opt-in, matching-frequency preference, an optional program
    filter, and the pause/snooze window. `cycle_type` is the cadence of the cycle
    being run ('biweekly' or 'monthly'); 'random' and 'once' always participate.
    """
    clauses = [
        "opted_in = 1",
        "round_optin = 1",
        "(match_frequency = ? OR match_frequency = 'random' OR match_frequency = 'once')",
        "(paused_until IS NULL OR paused_until < datetime('now'))",
    ]
    params: list = [cycle_type]
    if program:
        clauses.append("(program = ? OR program = 'open')")
        params.append(program)

    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM employees WHERE {' AND '.join(clauses)}", params
        ).fetchall()
        return [_row_to_employee(r) for r in rows]


def set_round_optin(user_id: str, response: str) -> None:
    """Apply a per-round opt-in button press.

    'yes'  → participate this round; 'skip' → sit this round out (stay opted in);
    'out'  → opt out of the program entirely.
    """
    with get_db() as conn:
        if response == "yes":
            conn.execute(
                "UPDATE employees SET round_optin = 1, opted_in = 1 WHERE id = ?",
                (user_id,),
            )
        elif response == "skip":
            conn.execute(
                "UPDATE employees SET round_optin = 0 WHERE id = ?", (user_id,)
            )
        elif response == "out":
            conn.execute(
                "UPDATE employees SET opted_in = 0, round_optin = 0 WHERE id = ?",
                (user_id,),
            )


def get_unique_match_count(user_id: str) -> int:
    """Count distinct people this employee has ever been matched with."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT COUNT(DISTINCT partner) AS n FROM (
                SELECT employee_b_id AS partner FROM matches WHERE employee_a_id = ?
                UNION
                SELECT employee_a_id AS partner FROM matches WHERE employee_b_id = ?
            )
            """,
            (user_id, user_id),
        ).fetchone()
        return row["n"] or 0


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


def create_match(
    employee_a_id: str,
    employee_b_id: str,
    cycle_id: str,
    match_type: str = "matched",
    match_score: float | None = None,
    match_reason: str | None = None,
    group_id: str | None = None,
) -> str:
    """Insert a new match row and return its UUID."""
    match_id = str(uuid.uuid4())
    with get_db() as conn:
        conn.execute(
            """INSERT INTO matches
                   (id, employee_a_id, employee_b_id, cycle_id,
                    match_type, match_score, match_reason, group_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                match_id, employee_a_id, employee_b_id, cycle_id,
                match_type, match_score, match_reason, group_id,
            ),
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


def get_completions_needing_followup(days: int = 7) -> list[dict]:
    """Return completed matches confirmed >= `days` ago that haven't been followed up.

    Joins in both employees' IDs and names so the caller can DM each party.
    """
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id AS completion_id, m.employee_a_id, m.employee_b_id,
                   ea.name AS employee_a_name, eb.name AS employee_b_name
            FROM completions c
            JOIN matches m ON c.match_id = m.id
            JOIN employees ea ON m.employee_a_id = ea.id
            JOIN employees eb ON m.employee_b_id = eb.id
            WHERE m.status = 'completed'
              AND COALESCE(c.followup_sent, 0) = 0
              AND c.completed_date IS NOT NULL
              AND c.completed_date < ?
            """,
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def record_followup(completion_id: str, user_id: str, response: str, reconnect: bool) -> None:
    """Store a follow-up check-in response for the confirming employee's side."""
    with get_db() as conn:
        match = conn.execute(
            """SELECT m.employee_a_id
               FROM completions c JOIN matches m ON c.match_id = m.id
               WHERE c.id = ?""",
            (completion_id,),
        ).fetchone()
        if not match:
            return
        is_a = match["employee_a_id"] == user_id
        response_col = "followup_response_a" if is_a else "followup_response_b"
        reconnect_col = "want_to_reconnect_a" if is_a else "want_to_reconnect_b"
        conn.execute(
            f"UPDATE completions SET {response_col} = ?, {reconnect_col} = ? WHERE id = ?",
            (response, 1 if reconnect else 0, completion_id),
        )


def mark_followup_sent(completion_id: str) -> None:
    """Flag a completion so its follow-up DM isn't sent again."""
    with get_db() as conn:
        conn.execute(
            "UPDATE completions SET followup_sent = 1 WHERE id = ?", (completion_id,)
        )


def get_match_for_reward(match_id: str) -> dict | None:
    """Return the two employee IDs and program for building an AwardCo reward row."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT m.id, m.employee_a_id, m.employee_b_id,
                   COALESCE(ea.program, 'open') AS program
            FROM matches m
            JOIN employees ea ON m.employee_a_id = ea.id
            WHERE m.id = ?
            """,
            (match_id,),
        ).fetchone()
        return dict(row) if row else None


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
