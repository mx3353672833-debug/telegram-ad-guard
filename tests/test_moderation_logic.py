from datetime import datetime, timedelta
from types import SimpleNamespace

from moderation_logic import RuntimeStats, should_check_user


def test_should_check_user_stops_after_verification_limit():
    user = SimpleNamespace(
        join_time=datetime(2026, 1, 1, 12, 0, 0),
        message_count=0,
        verification_times=2,
    )
    strategy = {
        "verification_times": 2,
        "joined_days": 3,
        "check_message_count": True,
        "min_messages": 3,
    }

    assert not should_check_user(user, strategy, now=datetime(2026, 1, 2, 12, 0, 0))


def test_should_check_user_stops_after_joined_days_threshold():
    user = SimpleNamespace(
        join_time=datetime(2026, 1, 1, 12, 0, 0),
        message_count=0,
        verification_times=0,
    )
    strategy = {
        "verification_times": 0,
        "joined_days": 3,
        "check_message_count": True,
        "min_messages": 3,
    }

    assert not should_check_user(user, strategy, now=datetime(2026, 1, 5, 12, 0, 1))


def test_should_check_user_stops_after_message_threshold_when_enabled():
    user = SimpleNamespace(
        join_time=datetime(2026, 1, 1, 12, 0, 0),
        message_count=4,
        verification_times=0,
    )
    strategy = {
        "verification_times": 0,
        "joined_days": 999,
        "check_message_count": True,
        "min_messages": 3,
    }

    assert not should_check_user(user, strategy, now=datetime(2026, 1, 2, 12, 0, 0))


def test_should_check_user_ignores_message_threshold_when_disabled():
    user = SimpleNamespace(
        join_time=datetime(2026, 1, 1, 12, 0, 0),
        message_count=999,
        verification_times=0,
    )
    strategy = {
        "verification_times": 0,
        "joined_days": 999,
        "check_message_count": False,
        "min_messages": 3,
    }

    assert should_check_user(user, strategy, now=datetime(2026, 1, 2, 12, 0, 0))


def test_runtime_stats_tracks_counts_and_uptime():
    start = datetime(2026, 1, 1, 0, 0, 0)
    stats = RuntimeStats(start_time=start)

    stats.record_check("passed")
    stats.record_check("banned")
    stats.record_check("failed")

    snapshot = stats.get_stats(now=start + timedelta(hours=2, minutes=30))

    assert snapshot == {
        "uptime_seconds": 9000,
        "checks_total": 3,
        "checks_passed": 1,
        "checks_banned": 1,
        "checks_failed": 1,
    }
