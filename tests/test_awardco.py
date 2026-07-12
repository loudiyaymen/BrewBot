"""Tests for the AwardCo SFTP reward module."""

import awardco


def test_build_reward_rows_format():
    csv = awardco._build_reward_rows(["U012AB3CD", "U034"], "2026-07-06")
    lines = csv.strip().splitlines()
    assert lines[0] == "employee_id,program_id,points,date"
    assert lines[1] == f"U012AB3CD,{awardco.PROGRAM_ID},10,2026-07-06"
    assert lines[2].startswith("U034,")


def test_is_configured_false_without_env(monkeypatch):
    monkeypatch.setattr(awardco, "SFTP_HOST", None)
    monkeypatch.setattr(awardco, "SFTP_USER", None)
    monkeypatch.setattr(awardco, "SFTP_KEY", None)
    assert awardco.is_configured() is False


def test_is_configured_true_with_env(monkeypatch):
    monkeypatch.setattr(awardco, "SFTP_HOST", "sftp.example.com")
    monkeypatch.setattr(awardco, "SFTP_USER", "user")
    monkeypatch.setattr(awardco, "SFTP_KEY", "/tmp/key")
    assert awardco.is_configured() is True


def test_issue_points_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(awardco, "SFTP_HOST", None)
    assert awardco.issue_points("match-1", ["U1", "U2"]) is False


def test_issue_points_returns_false_on_sftp_error(monkeypatch):
    # Configured, but the key file doesn't exist -> paramiko raises -> False.
    monkeypatch.setattr(awardco, "SFTP_HOST", "sftp.example.com")
    monkeypatch.setattr(awardco, "SFTP_USER", "user")
    monkeypatch.setattr(awardco, "SFTP_KEY", "/nonexistent/key")
    assert awardco.issue_points("match-1", ["U1", "U2"]) is False
