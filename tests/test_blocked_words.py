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


def test_ad_words_have_independent_per_group_storage(tmp_path):
    path = tmp_path / "words.db"
    db = Database(path)

    assert db.add_ad_word(100, "源头", 1) is True
    assert db.add_ad_word(100, "源头", 1) is False
    assert db.find_ad_word(100, "AI 源头批发") == "源头"
    assert db.find_ad_word(200, "AI 源头批发") is None
    assert db.list_ad_words(100) == ["源头"]

    reopened = Database(path)
    assert reopened.find_ad_word(100, "源头低价") == "源头"
    assert reopened.remove_ad_word(100, "源头") is True
    assert reopened.find_ad_word(100, "源头低价") is None


def test_ad_word_matching_uses_nfkc_and_casefold(tmp_path):
    db = Database(tmp_path / "words.db")
    db.add_ad_word(100, "VCC１２３", 1)

    assert db.find_ad_word(100, "vcc123 批发") == "VCC１２３"


def test_invisible_format_characters_cannot_bypass_word_matching(tmp_path):
    db = Database(tmp_path / "words.db")
    db.add_blocked_word(100, "博彩", 1)
    db.add_ad_word(100, "源头", 1)

    assert db.find_blocked_word(100, "博\u200b彩推广") == "博彩"
    assert db.find_ad_word(100, "源\u200d头低价") == "源头"
