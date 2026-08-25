from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from database import Database


BASE = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
WEEK = timedelta(days=7)


def register(db, message_id, now, *, chat_id=100, user_id=200):
    return db.register_detected_ad(
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        ad_interval=HOUR,
        violation_window=WEEK,
        permanent_mute_after=3,
        score=95,
        reason="promotion",
        now=now,
    )


def test_first_ad_allowed_second_ad_is_violation(tmp_path):
    db = Database(tmp_path / "policy.db")

    first = register(db, 1, BASE)
    second = register(db, 2, BASE + timedelta(minutes=10))

    assert first.action == "allow"
    assert second.action == "temporary_mute"
    assert second.violation_count == 1


def test_quota_resets_after_rolling_hour(tmp_path):
    db = Database(tmp_path / "policy.db")

    assert register(db, 1, BASE).is_allowed
    assert register(db, 2, BASE + timedelta(hours=1, seconds=1)).is_allowed


def test_third_violation_in_rolling_week_is_permanent(tmp_path):
    db = Database(tmp_path / "policy.db")

    assert register(db, 1, BASE).is_allowed
    assert register(db, 2, BASE + timedelta(minutes=10)).action == "temporary_mute"
    assert register(db, 3, BASE + timedelta(minutes=20)).action == "temporary_mute"
    third = register(db, 4, BASE + timedelta(minutes=30))

    assert third.action == "permanent_mute"
    assert third.violation_count == 3


def test_old_violations_fall_out_of_seven_day_window(tmp_path):
    db = Database(tmp_path / "policy.db")
    register(db, 1, BASE)
    register(db, 2, BASE + timedelta(minutes=10))
    register(db, 3, BASE + timedelta(minutes=20))

    fresh = BASE + timedelta(days=8)
    assert register(db, 4, fresh).is_allowed
    violation = register(db, 5, fresh + timedelta(minutes=1))

    assert violation.action == "temporary_mute"
    assert violation.violation_count == 1


def test_same_message_is_idempotent(tmp_path):
    db = Database(tmp_path / "policy.db")

    first = register(db, 1, BASE)
    duplicate = register(db, 1, BASE + timedelta(minutes=1))

    assert first.action == duplicate.action == "allow"
    status = db.get_ad_policy_status(200, 100, ad_interval=HOUR, violation_window=WEEK, now=BASE)
    assert status["violation_count"] == 0


def test_clear_history_resets_quota_and_violations(tmp_path):
    db = Database(tmp_path / "policy.db")
    register(db, 1, BASE)
    register(db, 2, BASE + timedelta(minutes=1))

    assert db.clear_ad_policy_history(200, 100) == 2
    assert register(db, 3, BASE + timedelta(minutes=2)).is_allowed


def test_concurrent_ads_only_consume_one_quota(tmp_path):
    db = Database(tmp_path / "policy.db")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda mid: register(db, mid, BASE), [1, 2]))

    assert sorted(result.action for result in results) == ["allow", "temporary_mute"]

