from datetime import datetime, timedelta

from database import Advertisement, Database, UserInfo


def test_database_user_counters_round_trip(tmp_path):
    db = Database(tmp_path / "test.db")
    user = UserInfo(
        user_id=1,
        chat_id=2,
        join_time=datetime(2026, 1, 1, 12, 0, 0),
    )

    db.save_user(user)
    db.increment_message_count(1, 2)
    db.increment_check_count(1, 2)
    db.increment_verification_times(1, 2)

    stored = db.get_user(1, 2)
    assert stored is not None
    assert stored.message_count == 1
    assert stored.check_count == 1
    assert stored.verification_times == 1


def test_database_only_returns_unexpired_ads(tmp_path):
    db = Database(tmp_path / "test.db")
    now = datetime.now()

    valid_id = db.add_advertisement(
        Advertisement(
            title="Valid",
            url="https://example.com/valid",
            sort=10,
            validity_period=now + timedelta(days=1),
        )
    )
    db.add_advertisement(
        Advertisement(
            title="Expired",
            url="https://example.com/expired",
            sort=100,
            validity_period=now - timedelta(days=1),
        )
    )

    ads = db.get_valid_advertisements()

    assert [ad.id for ad in ads] == [valid_id]
    assert ads[0].title == "Valid"
