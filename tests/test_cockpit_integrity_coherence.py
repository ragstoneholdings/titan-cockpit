"""Integrity consistency and Sentry state helpers."""

import os
from datetime import date, datetime, timedelta, timezone

import pytest

from api.services import cockpit_integrity_coherence as cic


def test_compute_integrity_consistency_percent_all_on():
    sidebar = {
        "labels": ["Mon"] * 28,
        "posture_days": [True] * 28,
        "neck_days": [True] * 28,
    }
    pct = cic.compute_integrity_consistency_percent(
        protocol_confirmed_today=True,
        sidebar_integrity=sidebar,
    )
    assert pct == 100.0


def test_compute_integrity_sentry_state_critical_on_alert():
    assert (
        cic.compute_integrity_sentry_state(identity_alert=True, consistency_percent=95.0) == "CRITICAL"
    )


def test_compute_integrity_sentry_state_warning_band():
    assert cic.compute_integrity_sentry_state(identity_alert=False, consistency_percent=70.0) == "WARNING"


def test_compute_integrity_sentry_state_low_consistency_warning_when_protocol_done():
    """Trailing consistency can be <50% while today's checkboxes are complete — not CRITICAL."""
    assert (
        cic.compute_integrity_sentry_state(
            identity_alert=False,
            consistency_percent=31.4,
            protocol_confirmed_today=True,
        )
        == "WARNING"
    )


def test_compute_integrity_sentry_state_low_consistency_critical_when_protocol_not_done():
    assert (
        cic.compute_integrity_sentry_state(
            identity_alert=False,
            consistency_percent=31.4,
            protocol_confirmed_today=False,
        )
        == "CRITICAL"
    )


def test_sacred_overdue_requires_env(monkeypatch):
    monkeypatch.delenv("JANITOR_SACRED_SUBSTRINGS", raising=False)
    by_id = {"1": {"content": "Call Jason", "description": "", "due_date": "2020-01-01"}}
    assert cic.count_sacred_overdue_tasks(by_id, date(2026, 1, 15)) == 0


def test_sacred_overdue_counts(monkeypatch):
    monkeypatch.setenv("JANITOR_SACRED_SUBSTRINGS", "jason")
    by_id = {"1": {"content": "Call Jason re QBR", "description": "", "due_date": "2026-01-01"}}
    assert cic.count_sacred_overdue_tasks(by_id, date(2026, 4, 1)) == 1


@pytest.mark.parametrize(
    "hour,expect",
    [
        (7, False),
        (9, True),
        (11, False),
    ],
)
def test_focus_shell_window(hour, expect, monkeypatch):
    monkeypatch.setenv("FOCUS_SHELL_START_HOUR", "8")
    monkeypatch.setenv("FOCUS_SHELL_END_HOUR", "11")
    d = date.today()
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    now = datetime(d.year, d.month, d.day, hour, 0, tzinfo=tz)
    assert cic.focus_shell_window_active(recon_day=d, now=now) is expect


def test_ops_posture_nudge_google_block(monkeypatch):
    monkeypatch.setenv("COCKPIT_OPS_POSTURE_NUDGE_SUBSTRINGS", "sync")
    d = date.today()
    tz = datetime.now().astimezone().tzinfo or timezone.utc
    start = datetime(d.year, d.month, d.day, 10, 0, tzinfo=tz)
    end = start + timedelta(hours=1)
    now = start + timedelta(minutes=15)
    landscape = [
        {
            "start_iso": start.isoformat(),
            "end_iso": end.isoformat(),
            "title": "Team sync",
            "source": "google",
            "source_kind": "personal_google",
        }
    ]
    vis, msg = cic.compute_ops_posture_nudge(recon_day=d, landscape=landscape, now=now)
    assert vis is True
    assert "posture" in msg.lower()
