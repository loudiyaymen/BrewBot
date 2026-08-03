"""Tests for the SQLite data layer, migrations, and query helpers."""

import csv
import io
import sqlite3

from conftest import make_employee


def _columns(db, table):
    with db.get_db() as c:
        return {r[1] for r in c.execute(f"PRAGMA table_info({table})")}


def test_init_creates_new_columns(fresh_db):
    emp_cols = _columns(fresh_db, "employees")
    assert {"goals_list", "interests_list", "connection_type", "match_frequency",
            "location", "meeting_preference", "round_optin", "paused_until",
            "mode"} <= emp_cols
    assert {"match_type", "match_score", "match_reason", "group_id"} <= _columns(fresh_db, "matches")
    assert {"followup_sent", "goals_met_a", "want_to_reconnect_a"} <= _columns(fresh_db, "completions")


def test_init_is_idempotent(fresh_db):
    fresh_db.init_db()  # second run must not raise
    fresh_db.init_db()


def test_migrate_upgrades_legacy_schema(tmp_path, monkeypatch):
    import db

    legacy = tmp_path / "legacy.db"
    conn = sqlite3.connect(legacy)
    conn.executescript(
        """
        CREATE TABLE employees (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            department TEXT NOT NULL, manager TEXT NOT NULL, region TEXT NOT NULL);
        CREATE TABLE cycles (id TEXT PRIMARY KEY, start_date TEXT NOT NULL, end_date TEXT NOT NULL);
        CREATE TABLE matches (id TEXT PRIMARY KEY, employee_a_id TEXT, employee_b_id TEXT, cycle_id TEXT);
        CREATE TABLE completions (id TEXT PRIMARY KEY, match_id TEXT);
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(db, "DB_PATH", str(legacy))
    db.init_db()
    assert "round_optin" in _columns(db, "employees")
    assert "match_reason" in _columns(db, "matches")


def test_upsert_and_roundtrip_json_lists(fresh_db):
    fresh_db.upsert_employee(make_employee(
        id="U1", goals_list=["find_mentor", "networking"], interests_list=["career"],
        connection_type="mentee",
    ))
    emp = fresh_db.get_opted_in_employees()[0]
    assert emp["goals_list"] == ["find_mentor", "networking"]
    assert emp["interests_list"] == ["career"]
    assert emp["connection_type"] == "mentee"


def test_upsert_populates_legacy_free_text(fresh_db):
    fresh_db.upsert_employee(make_employee(id="U1", goals_list=["a", "b"]))
    with fresh_db.get_db() as c:
        row = c.execute("SELECT goals FROM employees WHERE id='U1'").fetchone()
    assert row["goals"] == "a, b"


def test_upsert_updates_existing(fresh_db):
    fresh_db.upsert_employee(make_employee(id="U1", name="Alice"))
    fresh_db.upsert_employee(make_employee(id="U1", name="Alicia", connection_type="mentor"))
    emp = fresh_db.get_opted_in_employees()[0]
    assert emp["name"] == "Alicia" and emp["connection_type"] == "mentor"


def test_for_cycle_respects_frequency(fresh_db):
    fresh_db.upsert_employee(make_employee(id="B", match_frequency="biweekly"))
    fresh_db.upsert_employee(make_employee(id="M", match_frequency="monthly"))
    fresh_db.upsert_employee(make_employee(id="R", match_frequency="random"))
    ids = {e["id"] for e in fresh_db.get_opted_in_employees_for_cycle("biweekly")}
    assert ids == {"B", "R"}  # monthly excluded, random always included


def test_for_cycle_respects_round_optin_and_pause(fresh_db):
    fresh_db.upsert_employee(make_employee(id="IN"))
    fresh_db.upsert_employee(make_employee(id="SKIP", round_optin=0))
    fresh_db.upsert_employee(make_employee(id="PAUSED"))
    with fresh_db.get_db() as c:
        c.execute("UPDATE employees SET paused_until = '2099-01-01' WHERE id='PAUSED'")
    ids = {e["id"] for e in fresh_db.get_opted_in_employees_for_cycle("biweekly")}
    assert ids == {"IN"}


def test_for_cycle_program_filter(fresh_db):
    fresh_db.upsert_employee(make_employee(id="FI", program="falcon_ignite"))
    fresh_db.upsert_employee(make_employee(id="OPEN", program="open"))
    fresh_db.upsert_employee(make_employee(id="XLR8", program="xlr8"))
    ids = {e["id"] for e in fresh_db.get_opted_in_employees_for_cycle("biweekly", program="falcon_ignite")}
    assert ids == {"FI", "OPEN"}


def test_set_round_optin_transitions(fresh_db):
    fresh_db.upsert_employee(make_employee(id="U1"))
    fresh_db.set_round_optin("U1", "skip")
    assert not fresh_db.get_opted_in_employees_for_cycle("biweekly")
    fresh_db.set_round_optin("U1", "yes")
    assert len(fresh_db.get_opted_in_employees_for_cycle("biweekly")) == 1
    fresh_db.set_round_optin("U1", "out")
    assert not fresh_db.get_opted_in_employees()  # opted out entirely


def test_create_match_with_metadata(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = fresh_db.create_match("A", "B", cid, match_type="matched", match_score=6.7,
                                match_reason="because", group_id=None)
    with fresh_db.get_db() as c:
        row = c.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    assert row["match_score"] == 6.7 and row["match_reason"] == "because"


def test_unique_match_count(fresh_db):
    for eid in ("A", "B", "C"):
        fresh_db.upsert_employee(make_employee(id=eid, manager=f"M{eid}", department=f"d{eid}"))
    cid = fresh_db.create_cycle("open", "2026-01-01", "2026-01-15")
    fresh_db.create_match("A", "B", cid)
    fresh_db.create_match("C", "A", cid)  # A appears on either side
    assert fresh_db.get_unique_match_count("A") == 2
    assert fresh_db.get_unique_match_count("B") == 1


def test_followup_lifecycle(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = fresh_db.create_match("A", "B", cid)
    fresh_db.update_match_status(mid, "completed")
    fresh_db.upsert_completion(mid, confirmed_by="A", rating=5, feedback="great")
    with fresh_db.get_db() as c:
        c.execute("UPDATE completions SET completed_date='2020-01-01' WHERE match_id=?", (mid,))

    needing = fresh_db.get_completions_needing_followup(days=7)
    assert len(needing) == 1
    comp_id = needing[0]["completion_id"]

    fresh_db.record_followup(comp_id, "A", "yes", reconnect=True)
    fresh_db.mark_followup_sent(comp_id)
    assert fresh_db.get_completions_needing_followup(days=7) == []

    with fresh_db.get_db() as c:
        row = c.execute("SELECT * FROM completions WHERE id=?", (comp_id,)).fetchone()
    assert row["followup_response_a"] == "yes" and row["want_to_reconnect_a"] == 1


def test_get_match_for_reward(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = fresh_db.create_match("A", "B", cid)
    reward = fresh_db.get_match_for_reward(mid)
    assert reward["employee_a_id"] == "A" and reward["employee_b_id"] == "B"
    assert fresh_db.get_match_for_reward("nope") is None


def _seed_pair(db):
    db.upsert_employee(make_employee(id="A", name="Alice", manager="M1", department="eng"))
    db.upsert_employee(make_employee(id="B", name="Bob", manager="M2", department="product"))


# ── CSV export ───────────────────────────────────────────────────────────────

def test_export_matches_current_cycle(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    mid = fresh_db.create_match("A", "B", cid, "matched", 6.7, "shared goals")
    fresh_db.update_match_status(mid, "completed")
    fresh_db.upsert_completion(mid, confirmed_by="A", rating=5, feedback="great chat")

    rows = fresh_db.export_matches(cid)
    assert len(rows) == 1
    row = rows[0]
    assert row["partner_a"] == "Alice" and row["partner_b"] == "Bob"
    assert row["took_place"] == "yes"
    assert row["completed_date"] and row["rating_a"] == 5 and row["feedback_a"] == "great chat"
    assert row["match_reason"] == "shared goals"


def test_export_matches_includes_pending(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    fresh_db.create_match("A", "B", cid)  # never completed
    row = fresh_db.export_matches(cid)[0]
    assert row["took_place"] == "no" and row["completed_date"] is None


def test_export_matches_all_scope(fresh_db):
    _seed_pair(fresh_db)
    c1 = fresh_db.create_cycle("open", "2026-07-01", "2026-07-15")
    c2 = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    fresh_db.create_match("A", "B", c1)
    fresh_db.create_match("A", "B", c2)
    assert len(fresh_db.export_matches()) == 2
    assert len(fresh_db.export_matches(c2)) == 1


def test_matches_to_csv_roundtrip(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    fresh_db.create_match("A", "B", cid, "matched", 6.7, "shared goals")
    text = fresh_db.matches_to_csv(fresh_db.export_matches(cid))
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert list(parsed[0].keys()) == fresh_db.EXPORT_COLUMNS
    assert parsed[0]["partner_a"] == "Alice"


def test_matches_to_csv_empty_has_header_only(fresh_db):
    text = fresh_db.matches_to_csv([])
    lines = text.strip().splitlines()
    assert len(lines) == 1 and lines[0].split(",") == fresh_db.EXPORT_COLUMNS


def test_export_matches_includes_followup(fresh_db):
    _seed_pair(fresh_db)
    cid = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    mid = fresh_db.create_match("A", "B", cid)
    fresh_db.update_match_status(mid, "completed")
    fresh_db.upsert_completion(mid, confirmed_by="A", rating=4, feedback="")
    with fresh_db.get_db() as c:
        comp_id = c.execute("SELECT id FROM completions WHERE match_id=?", (mid,)).fetchone()["id"]
    fresh_db.record_followup(comp_id, "A", "partial", reconnect=True)

    row = fresh_db.export_matches(cid)[0]
    assert row["followup_response_a"] == "partial"
    assert row["want_to_reconnect_a"] == 1
    assert row["dept_a"] == "eng" and row["employee_a_id"] == "A"


def test_export_employees_includes_profile_and_counts(fresh_db):
    fresh_db.upsert_employee(make_employee(
        id="A", name="Alice", manager="M1", department="eng",
        goals_list=["find_mentor", "networking"], connection_type="mentee",
    ))
    fresh_db.upsert_employee(make_employee(id="B", name="Bob", manager="M2", department="product"))
    cid = fresh_db.create_cycle("open", "2026-08-01", "2026-08-15")
    fresh_db.create_match("A", "B", cid)

    rows = {r["id"]: r for r in fresh_db.export_employees()}
    assert rows["A"]["goals"] == "find_mentor; networking"
    assert rows["A"]["connection_type"] == "mentee"
    assert rows["A"]["unique_matches"] == 1


def test_employees_to_csv_roundtrip(fresh_db):
    fresh_db.upsert_employee(make_employee(id="A", name="Alice", manager="M1", department="eng"))
    text = fresh_db.employees_to_csv(fresh_db.export_employees())
    parsed = list(csv.DictReader(io.StringIO(text)))
    assert list(parsed[0].keys()) == fresh_db.EMPLOYEE_EXPORT_COLUMNS
    assert parsed[0]["name"] == "Alice"
