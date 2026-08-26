from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from database import Database


BASE = datetime(2026, 8, 25, 0, 0, tzinfo=timezone.utc)
HOUR = timedelta(hours=1)
WEEK = timedelta(days=7)


def register(
    db,
    message_id,
    now,
    *,
    chat_id=100,
    user_id=200,
    content_hash="",
    force_duplicate=False,
):
    return db.register_detected_ad(
        chat_id=chat_id,
        user_id=user_id,
        message_id=message_id,
        ad_interval=HOUR,
        violation_window=WEEK,
        permanent_mute_after=3,
        score=95,
        reason="promotion",
        content_hash=content_hash,
        force_duplicate=force_duplicate,
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


def test_identical_ad_is_group_wide_violation_even_from_another_user(tmp_path):
    db = Database(tmp_path / "policy.db")

    first = register(db, 1, BASE, user_id=200, content_hash="same-ad")
    repeated = register(
        db,
        2,
        BASE + timedelta(minutes=10),
        user_id=201,
        content_hash="same-ad",
    )

    assert first.action == "allow"
    assert repeated.action == "duplicate_mute"
    assert repeated.violation_count == 0
    assert repeated.is_duplicate_content is True


def test_different_ad_text_does_not_consume_another_users_quota(tmp_path):
    db = Database(tmp_path / "policy.db")

    assert register(db, 1, BASE, user_id=200, content_hash="ad-a").is_allowed
    second_user = register(
        db,
        2,
        BASE + timedelta(minutes=10),
        user_id=201,
        content_hash="ad-b",
    )

    assert second_user.is_allowed


def test_identical_ad_is_allowed_again_after_rolling_hour(tmp_path):
    db = Database(tmp_path / "policy.db")

    assert register(db, 1, BASE, user_id=200, content_hash="same-ad").is_allowed
    later = register(
        db,
        2,
        BASE + timedelta(hours=1, seconds=1),
        user_id=201,
        content_hash="same-ad",
    )

    assert later.is_allowed


def test_duplicate_ads_never_count_toward_permanent_mute(tmp_path):
    db = Database(tmp_path / "policy.db")

    for offset, fingerprint in enumerate(("ad-a", "ad-b", "ad-c"), start=1):
        register(db, offset * 10, BASE, user_id=100 + offset, content_hash=fingerprint)
        duplicate = register(
            db,
            offset * 10 + 1,
            BASE + timedelta(minutes=offset),
            user_id=200,
            content_hash=fingerprint,
        )
        assert duplicate.action == "duplicate_mute"
        assert duplicate.violation_count == 0

    first_unique = register(
        db,
        50,
        BASE + timedelta(minutes=10),
        user_id=200,
        content_hash="unique-a",
    )
    normal_violation = register(
        db,
        51,
        BASE + timedelta(minutes=11),
        user_id=200,
        content_hash="unique-b",
    )

    assert first_unique.is_allowed
    assert normal_violation.action == "temporary_mute"
    assert normal_violation.violation_count == 1


def test_forced_duplicate_mutes_without_an_adword_history(tmp_path):
    db = Database(tmp_path / "policy.db")

    decision = register(
        db,
        1,
        BASE,
        user_id=200,
        content_hash="unclassified-copy",
        force_duplicate=True,
    )

    assert decision.action == "duplicate_mute"
    assert decision.is_duplicate_content is True
    assert decision.violation_count == 0


def test_long_message_fingerprints_detect_group_wide_copies(tmp_path):
    db = Database(tmp_path / "policy.db")

    first = db.register_message_fingerprint(
        chat_id=100,
        user_id=200,
        message_id=1,
        content_hash="same-long-message",
        duplicate_window=HOUR,
        now=BASE,
    )
    second = db.register_message_fingerprint(
        chat_id=100,
        user_id=201,
        message_id=2,
        content_hash="same-long-message",
        duplicate_window=HOUR,
        now=BASE + timedelta(minutes=20),
    )
    after_window = db.register_message_fingerprint(
        chat_id=100,
        user_id=202,
        message_id=3,
        content_hash="same-long-message",
        duplicate_window=HOUR,
        now=BASE + timedelta(hours=2),
    )

    assert first is False
    assert second is True
    assert after_window is False
