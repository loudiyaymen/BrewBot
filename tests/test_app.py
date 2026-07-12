"""Tests for app.py wiring: modal parsing, handlers, cycle flow, reward fallback.

Slack is fully mocked — no network. The Bolt App is constructed with token
verification disabled (see conftest).
"""

from unittest.mock import MagicMock

import pytest

import app
from conftest import make_employee


@pytest.fixture
def slack_client(monkeypatch):
    """Replace the shared app client with a mock and return it."""
    client = MagicMock()
    # app.client is a read-only property backed by _client.
    monkeypatch.setattr(app.app, "_client", client, raising=False)
    return client


@pytest.fixture(autouse=True)
def _db(fresh_db, monkeypatch):
    """Every app test runs against a fresh isolated DB (app imports db as a module)."""
    monkeypatch.setattr(app.db, "DB_PATH", fresh_db.DB_PATH)
    return fresh_db


# ── Modal state parsing helpers ──────────────────────────────────────────────

def test_selected_value_reads_option():
    block = {"input_x": {"selected_option": {"value": "chosen"}}}
    assert app._selected_value(block, "input_x") == "chosen"


def test_selected_value_default_when_empty():
    assert app._selected_value({"input_x": {}}, "input_x", "fallback") == "fallback"


def test_checkbox_values_extracts_list():
    block = {"input_g": {"selected_options": [{"value": "a"}, {"value": "b"}]}}
    assert app._checkbox_values(block, "input_g") == ["a", "b"]
    assert app._checkbox_values({"input_g": {}}, "input_g") == []


# ── Opt-in submit ────────────────────────────────────────────────────────────

def _opt_in_view(mode="matched", partner=None):
    def sel(v):
        return {"selected_option": {"value": v}}
    return {
        "state": {"values": {
            "block_mode": {"input_mode": {"selected_option": {"value": mode}}},
            "block_partner": {"input_partner": {"selected_user": partner}},
            "block_name": {"input_name": {"value": "Alice"}},
            "block_department": {"input_department": {"value": "engineering"}},
            "block_manager": {"input_manager": {"value": "Bob Boss"}},
            "block_region": {"input_region": sel("americas")},
            "block_level": {"input_level": sel("mid")},
            "block_tenure": {"input_tenure": sel("6to18")},
            "block_goals": {"input_goals": {"selected_options": [{"value": "find_mentor"}]}},
            "block_interests": {"input_interests": {"selected_options": [{"value": "career"}]}},
            "block_connection_type": {"input_connection_type": sel("mentee")},
            "block_frequency": {"input_frequency": sel("monthly")},
            "block_meeting_pref": {"input_meeting_pref": sel("virtual")},
            "block_location": {"input_location": {"value": "Austin"}},
            "block_program": {"input_program": sel("falcon_ignite")},
        }}
    }


def test_opt_in_persists_all_fields(slack_client, _db):
    ack = MagicMock()
    app.handle_opt_in_submit(ack, _opt_in_view(), slack_client, {"user": {"id": "U1"}})
    ack.assert_called_once()
    emp = _db.get_opted_in_employees()[0]
    assert emp["goals_list"] == ["find_mentor"]
    assert emp["connection_type"] == "mentee"
    assert emp["match_frequency"] == "monthly"
    assert emp["meeting_preference"] == "virtual"
    assert emp["location"] == "Austin"
    assert emp["program"] == "falcon_ignite"
    assert emp["tenure_months"] == 12


def test_opt_in_confirmation_dm_sent(slack_client, _db):
    app.handle_opt_in_submit(MagicMock(), _opt_in_view(), slack_client, {"user": {"id": "U1"}})
    slack_client.chat_postMessage.assert_called_once()
    assert slack_client.chat_postMessage.call_args.kwargs["channel"] == "U1"


def test_self_select_creates_match_immediately(slack_client, _db):
    slack_client.users_info.return_value = {
        "user": {"name": "u2", "profile": {"real_name": "Uma Two"}}
    }
    view = _opt_in_view(mode="self_select", partner="U2")
    app.handle_opt_in_submit(MagicMock(), view, slack_client, {"user": {"id": "U1"}})
    # A match row exists and both parties were DMed.
    with _db.get_db() as c:
        rows = c.execute("SELECT * FROM matches WHERE match_type='self_select'").fetchall()
    assert len(rows) == 1
    assert slack_client.chat_postMessage.call_count == 2
    # Self-selecting excludes the initiator from the automated pool this round.
    initiator = next(e for e in _db.get_opted_in_employees() if e["id"] == "U1")
    assert initiator["round_optin"] == 0
    # A stub row was created for the not-yet-opted-in partner (kept out of the pool).
    with _db.get_db() as c:
        partner = c.execute("SELECT * FROM employees WHERE id='U2'").fetchone()
    assert partner["opted_in"] == 0 and partner["name"] == "Uma Two"


def test_self_select_falls_back_when_name_unresolved(slack_client, _db):
    slack_client.users_info.side_effect = Exception("no such user")
    view = _opt_in_view(mode="self_select", partner="U2")
    app.handle_opt_in_submit(MagicMock(), view, slack_client, {"user": {"id": "U1"}})
    with _db.get_db() as c:
        partner = c.execute("SELECT name FROM employees WHERE id='U2'").fetchone()
    assert partner["name"] == "your chosen partner"


# ── Reward issuance / fallback ───────────────────────────────────────────────

def test_issue_reward_falls_back_to_admin(slack_client, _db, monkeypatch):
    _db.upsert_employee(make_employee(id="A", manager="M1", department="eng"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product"))
    cid = _db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = _db.create_match("A", "B", cid)

    monkeypatch.setattr(app.awardco, "issue_points", lambda *a, **k: False)
    app.issue_reward(mid)
    # Falls back to the admin channel.
    assert slack_client.chat_postMessage.call_args.kwargs["channel"] == app.ADMIN_CHANNEL_ID


def test_issue_reward_skips_admin_on_success(slack_client, _db, monkeypatch):
    _db.upsert_employee(make_employee(id="A", manager="M1", department="eng"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product"))
    cid = _db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = _db.create_match("A", "B", cid)

    monkeypatch.setattr(app.awardco, "issue_points", lambda *a, **k: True)
    app.issue_reward(mid)
    slack_client.chat_postMessage.assert_not_called()


# ── Per-round opt-in & follow-up buttons ─────────────────────────────────────

def test_round_optin_handler_updates_db(slack_client, _db):
    _db.upsert_employee(make_employee(id="U1"))
    app.handle_round_optin(MagicMock(), {"value": "skip"}, slack_client, {"user": {"id": "U1"}})
    assert not _db.get_opted_in_employees_for_cycle("biweekly")


def test_followup_response_recorded(slack_client, _db):
    _db.upsert_employee(make_employee(id="A", manager="M1", department="eng"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product"))
    cid = _db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = _db.create_match("A", "B", cid)
    _db.upsert_completion(mid, confirmed_by="A", rating=5, feedback="")
    with _db.get_db() as c:
        comp_id = c.execute("SELECT id FROM completions WHERE match_id=?", (mid,)).fetchone()["id"]

    action = {"value": comp_id, "action_id": "followup_partial"}
    app.handle_followup_response(MagicMock(), action, slack_client, {"user": {"id": "A"}})
    with _db.get_db() as c:
        row = c.execute("SELECT followup_response_a FROM completions WHERE id=?", (comp_id,)).fetchone()
    assert row["followup_response_a"] == "partial"


# ── Cycle flow ───────────────────────────────────────────────────────────────

def test_run_cycle_start_matches_and_dms(slack_client, _db):
    _db.upsert_employee(make_employee(id="A", manager="M1", department="eng", connection_type="mentee"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product", connection_type="mentor"))
    app.run_cycle_start()
    with _db.get_db() as c:
        matches = c.execute("SELECT * FROM matches").fetchall()
    assert len(matches) == 1
    assert matches[0]["match_score"] and matches[0]["match_reason"]
    # Both employees DMed their intro.
    assert slack_client.chat_postMessage.call_count == 2


def test_run_cycle_start_bails_when_too_few(slack_client, _db):
    _db.upsert_employee(make_employee(id="A"))
    app.run_cycle_start()
    with _db.get_db() as c:
        assert c.execute("SELECT COUNT(*) n FROM matches").fetchone()["n"] == 0


def test_run_cycle_start_forms_groups(slack_client, _db):
    for i in range(3):
        _db.upsert_employee(make_employee(id=f"G{i}", manager=f"M{i}", department=f"d{i}", mode="group"))
    app.run_cycle_start()
    with _db.get_db() as c:
        gid = c.execute("SELECT DISTINCT group_id FROM matches WHERE group_id IS NOT NULL").fetchall()
    assert len(gid) == 1  # one group, recorded as pairwise rows sharing a group_id


def test_send_followup_checkins_dms_and_marks(slack_client, _db):
    _db.upsert_employee(make_employee(id="A", manager="M1", department="eng"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product"))
    cid = _db.create_cycle("open", "2026-01-01", "2026-01-15")
    mid = _db.create_match("A", "B", cid)
    _db.update_match_status(mid, "completed")
    _db.upsert_completion(mid, confirmed_by="A", rating=5, feedback="")
    with _db.get_db() as c:
        c.execute("UPDATE completions SET completed_date='2020-01-01' WHERE match_id=?", (mid,))

    app.send_followup_checkins()
    assert slack_client.chat_postMessage.call_count == 2  # both parties
    assert _db.get_completions_needing_followup(7) == []  # marked sent


def test_broadcast_round_optin_dms_everyone(slack_client, _db):
    _db.upsert_employee(make_employee(id="A"))
    _db.upsert_employee(make_employee(id="B", manager="M2", department="product"))
    app.broadcast_round_optin()
    assert slack_client.chat_postMessage.call_count == 2
