from datetime import datetime
from types import SimpleNamespace

import pytest

from command_logic import (
    CommandInputError,
    parse_add_ad_payload,
    parse_delete_ad_args,
    parse_unban_callback_data,
    resolve_unban_target,
)


def test_parse_add_ad_payload_builds_advertisement():
    ad = parse_add_ad_payload("官方频道|https://t.me/test|2099-01-01 00:00:00|100")

    assert ad.title == "官方频道"
    assert ad.url == "https://t.me/test"
    assert ad.sort == 100
    assert ad.validity_period == datetime(2099, 1, 1, 0, 0, 0)


def test_parse_add_ad_payload_rejects_wrong_part_count():
    with pytest.raises(CommandInputError) as exc:
        parse_add_ad_payload("标题|https://t.me/test|2099-01-01 00:00:00")

    assert exc.value.code == "format"


def test_parse_delete_ad_args_returns_ad_id():
    assert parse_delete_ad_args(["42"]) == 42


def test_parse_delete_ad_args_rejects_invalid_id():
    with pytest.raises(CommandInputError) as exc:
        parse_delete_ad_args(["abc"])

    assert exc.value.code == "invalid_id"


def test_parse_unban_callback_data_returns_target_user_id():
    assert parse_unban_callback_data("unban_12345") == 12345
    assert parse_unban_callback_data("noop") is None
    assert parse_unban_callback_data("unban_x") is None


def test_resolve_unban_target_prefers_reply_user():
    reply = SimpleNamespace(from_user=SimpleNamespace(id=123, first_name="Alice"))

    target_user_id, target_user_name = resolve_unban_target(reply, ["999"])

    assert target_user_id == 123
    assert target_user_name == "Alice"


def test_resolve_unban_target_rejects_invalid_arg():
    with pytest.raises(CommandInputError) as exc:
        resolve_unban_target(None, ["abc"])

    assert exc.value.code == "invalid_id"


def test_resolve_unban_target_requires_reply_or_args():
    with pytest.raises(CommandInputError) as exc:
        resolve_unban_target(None, [])

    assert exc.value.code == "usage"
