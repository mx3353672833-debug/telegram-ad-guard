from datetime import datetime, timedelta
import sqlite3

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


def test_existing_database_is_migrated_for_duplicate_ad_detection(tmp_path):
    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE detected_ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL,
            detected_at INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            score INTEGER DEFAULT 0,
            reason TEXT DEFAULT '',
            UNIQUE(chat_id, message_id)
        )
        """
    )
    conn.commit()
    conn.close()

    Database(db_path)

    conn = sqlite3.connect(db_path)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(detected_ads)")}
    indexes = {row[1] for row in conn.execute("PRAGMA index_list(detected_ads)")}
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()

    assert {"content_hash", "duplicate_content"} <= columns
    assert "idx_detected_ads_content_time" in indexes
    assert "message_fingerprints" in tables
