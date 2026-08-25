import logging

from message_utils import (
    DEFAULT_BAN_NOTICE_TEMPLATE,
    build_ban_notice,
    process_nickname,
)


def test_build_ban_notice_uses_default_template_when_missing():
    masked_name = process_nickname("Alice")

    notice = build_ban_notice(
        None,
        masked_name=masked_name,
        user_link="tg://user?id=1",
        score=88,
        reason="赌博广告",
        mock_text="别刷了",
    )

    expected = DEFAULT_BAN_NOTICE_TEMPLATE.format(
        masked_name=masked_name,
        user_link="tg://user?id=1",
        score=88,
        reason="赌博广告",
        mock="别刷了",
        user_id="",
        chat_id="",
        channel_url="",
        group_url="",
    )
    assert notice == expected


def test_build_ban_notice_renders_custom_template():
    notice = build_ban_notice(
        "用户 {user_id} 分数 {score} {channel_url}",
        masked_name=process_nickname("Alice"),
        user_link="tg://user?id=42",
        score=91,
        reason="spam",
        mock_text="mock",
        user_id=42,
        channel_url="https://t.me/example",
    )

    assert notice == "用户 42 分数 91 https://t.me/example"


def test_build_ban_notice_falls_back_on_unknown_placeholder(caplog):
    caplog.set_level(logging.WARNING)

    notice = build_ban_notice(
        "hello {unknown}",
        masked_name=process_nickname("Alice"),
        user_link="tg://user?id=7",
        score=50,
        reason="abc",
        mock_text="def",
        logger=logging.getLogger("test"),
    )

    assert "\\#封禁预警" in notice
    assert "Unknown placeholders in ban notice template" in caplog.text


def test_build_ban_notice_escapes_markdown_v2_content():
    notice = build_ban_notice(
        None,
        masked_name=process_nickname("A_[x]-!"),
        user_link="tg://user?id=99",
        score=77,
        reason="need_[escape]-!",
        mock_text="mock.(test)!",
    )

    assert "need\\_\\[escape\\]\\-\\!" in notice
    assert "mock\\.\\(test\\)\\!" in notice
    assert "A" in notice
    assert "\\_" in notice
