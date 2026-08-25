import pytest

from database import Database


def test_add_list_match_and_remove_blocked_word(tmp_path):
    db = Database(tmp_path / "blocked.db")

    assert db.add_blocked_word(100, "加我私聊", 1) is True
    assert db.list_blocked_words(100) == ["加我私聊"]
    assert db.find_blocked_word(100, "有事请加我私聊") == "加我私聊"
    assert db.remove_blocked_word(100, "加我私聊") is True
    assert db.find_blocked_word(100, "有事请加我私聊") is None


def test_matching_is_case_insensitive_and_nfkc_normalized(tmp_path):
    db = Database(tmp_path / "blocked.db")

    assert db.add_blocked_word(100, "ABC１２３", 1) is True
    assert db.find_blocked_word(100, "xxabc123yy") == "ABC１２３"
    assert db.add_blocked_word(100, "abc123", 2) is False
    assert db.remove_blocked_word(100, "ＡＢＣ１２３") is True


def test_words_are_isolated_per_group_and_persist(tmp_path):
    path = tmp_path / "blocked.db"
    db = Database(path)
    db.add_blocked_word(100, "博彩", 1)

    assert db.find_blocked_word(200, "博彩推广") is None

    reopened = Database(path)
    assert reopened.find_blocked_word(100, "博彩推广") == "博彩"


def test_longest_matching_word_is_returned_first(tmp_path):
    db = Database(tmp_path / "blocked.db")
    db.add_blocked_word(100, "广告", 1)
    db.add_blocked_word(100, "广告代理", 1)

    assert db.find_blocked_word(100, "招广告代理") == "广告代理"


def test_invalid_blocked_words_are_rejected(tmp_path):
    db = Database(tmp_path / "blocked.db")

    with pytest.raises(ValueError):
        db.add_blocked_word(100, "   ", 1)
    with pytest.raises(ValueError):
        db.add_blocked_word(100, "x" * 65, 1)
