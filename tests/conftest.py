"""Shared pytest fixtures for BrewBot tests."""

import functools
import os

import pytest

# Dummy env so importing app.py (which constructs a Slack App and reads config) works
# offline. Must be set before any test imports app.
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test")
os.environ.setdefault("ADMIN_CHANNEL_ID", "C_ADMIN")
os.environ.setdefault("CALENDLY_LINK", "https://calendly.com/test")

# Slack Bolt's App() runs a live auth.test at construction; disable it for tests.
import slack_bolt  # noqa: E402

if not getattr(slack_bolt.App, "_brewbot_patched", False):
    _orig_init = slack_bolt.App.__init__
    slack_bolt.App.__init__ = functools.partialmethod(
        _orig_init, token_verification_enabled=False
    )
    slack_bolt.App._brewbot_patched = True


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    """Point db at an isolated, freshly-initialized SQLite file."""
    import db

    db_file = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", str(db_file))
    db.init_db()
    return db


def make_employee(**overrides) -> dict:
    """Build an employee dict with sensible defaults, overridable per test."""
    base = dict(
        id="U1",
        name="Alice",
        department="engineering",
        manager="M1",
        region="americas",
        job_level="mid",
        tenure_months=12,
        goals_list=[],
        interests_list=[],
        connection_type="open",
        match_frequency="biweekly",
        meeting_preference="either",
        location=None,
        program="open",
        mode="matched",
    )
    base.update(overrides)
    return base
