import asyncio
import importlib
import sys
from datetime import datetime
from types import ModuleType
from types import SimpleNamespace

import pytest


def fake_t(key: str, **kwargs) -> str:
    if not kwargs:
        return key
    rendered = ",".join(f"{name}={kwargs[name]}" for name in sorted(kwargs))
    return f"{key}|{rendered}"


class FakeMessage:
    def __init__(self, *, chat_id=100, reply_to_message=None):
        self.chat_id = chat_id
        self.message_id = 700
        self.reply_to_message = reply_to_message
        self.replies = []
        self.deleted = False

    async def reply_text(self, text, **kwargs):
        self.replies.append((text, kwargs))

    async def delete(self):
        self.deleted = True


class FakeBot:
    def __init__(self):
        self.restrict_calls = []
        self.send_calls = []
        self.files = {}
        self.sent_message_id = 900

    async def restrict_chat_member(self, **kwargs):
        self.restrict_calls.append(kwargs)

    async def send_message(self, chat_id, text, **kwargs):
        self.send_calls.append((chat_id, text, kwargs))
        self.sent_message_id += 1
        return SimpleNamespace(message_id=self.sent_message_id)

    async def get_file(self, file_id):
        return self.files[file_id]


class FakeDownloadedFile:
    def __init__(self, payload: bytes):
        self.payload = payload

    async def download_as_bytearray(self):
        return bytearray(self.payload)


class FakeDB:
    def __init__(self, user=None):
        self.user = user
        self.saved_users = []
        self.incremented_messages = []
        self.incremented_verifications = []
        self.cleared_history = []
        self.blocked_word_match = None
        self.ad_word_match = None
        self.blocked_words = {}
        self.ad_words = {}
        self.fingerprint_duplicate = False
        self.fingerprint_calls = []

    def get_user(self, user_id, chat_id):
        return self.user

    def save_user(self, user):
        self.user = user
        self.saved_users.append(user)

    def increment_message_count(self, user_id, chat_id):
        self.incremented_messages.append((user_id, chat_id))

    def increment_verification_times(self, user_id, chat_id):
        self.incremented_verifications.append((user_id, chat_id))

    def clear_ad_policy_history(self, user_id, chat_id):
        self.cleared_history.append((user_id, chat_id))
        return 1

    def find_blocked_word(self, chat_id, text):
        return self.blocked_word_match

    def find_ad_word(self, chat_id, text):
        return self.ad_word_match

    @staticmethod
    def normalize_blocked_text(text):
        return str(text or "").casefold().strip()

    def register_message_fingerprint(self, **kwargs):
        self.fingerprint_calls.append(kwargs)
        return self.fingerprint_duplicate

    def add_blocked_word(self, chat_id, word, created_by):
        words = self.blocked_words.setdefault(chat_id, [])
        if word in words:
            return False
        words.append(word)
        return True

    def remove_blocked_word(self, chat_id, word):
        words = self.blocked_words.setdefault(chat_id, [])
        if word not in words:
            return False
        words.remove(word)
        return True

    def list_blocked_words(self, chat_id):
        return list(self.blocked_words.get(chat_id, []))

    def add_ad_word(self, chat_id, word, created_by):
        words = self.ad_words.setdefault(chat_id, [])
        if word in words:
            return False
        words.append(word)
        return True

    def remove_ad_word(self, chat_id, word):
        words = self.ad_words.setdefault(chat_id, [])
        if word not in words:
            return False
        words.remove(word)
        return True

    def list_ad_words(self, chat_id):
        return list(self.ad_words.get(chat_id, []))


class FakeQuery:
    def __init__(self, *, data, from_user, message):
        self.data = data
        self.from_user = from_user
        self.message = message
        self.answers = []
        self.edited_reply_markup = None

    async def answer(self, text=None, show_alert=None):
        self.answers.append((text, show_alert))

    async def edit_message_reply_markup(self, reply_markup=None):
        self.edited_reply_markup = reply_markup


class FakeLogger:
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []

    def info(self, message, *args, **kwargs):
        self.infos.append(message % args if args else message)

    def warning(self, message, *args, **kwargs):
        self.warnings.append(message % args if args else message)

    def error(self, message, *args, **kwargs):
        self.errors.append(message % args if args else message)


@pytest.fixture
def bot_module(monkeypatch, tmp_path):
    values = {
        "ai_model": "openai",
        "detection.mode": "ai",
        "openai.api_key": "test-key",
        "openai.base_url": "https://example.com/v1",
        "openai.model": "gpt-test",
        "strategy.spam_score": 80,
        "strategy.joined_days": 3,
        "strategy.min_messages": 3,
        "strategy.verification_times": 0,
        "telegram.owners": ["1"],
        "telegram.allow_any_group": True,
        "message.delete_ban_notice_after_seconds": 30,
        "message.delete_welcome_message_after_seconds": 30,
    }

    monkeypatch.chdir(tmp_path)
    fake_config_module = ModuleType("config")
    fake_config_module.config = SimpleNamespace(get=lambda key, default=None: values.get(key, default))
    fake_ai_module = ModuleType("ai")
    fake_ai_module.create_ai_client = lambda: SimpleNamespace()
    fake_ai_module.SpamResult = lambda **kwargs: SimpleNamespace(**kwargs)
    fake_prompts_module = ModuleType("ai.prompts")
    fake_prompts_module.USER_INFO_TEMPLATE = "count={msg_count} joined={join_time}"
    fake_i18n_module = ModuleType("i18n")
    fake_i18n_module.t = fake_t
    fake_i18n_module.set_locale = lambda locale: None

    class FakeChatMember:
        ADMINISTRATOR = "administrator"
        OWNER = "creator"
        MEMBER = "member"
        LEFT = "left"
        BANNED = "kicked"

    class FakeInlineKeyboardButton:
        def __init__(self, text, url=None, callback_data=None):
            self.text = text
            self.url = url
            self.callback_data = callback_data

    class FakeInlineKeyboardMarkup:
        def __init__(self, inline_keyboard):
            self.inline_keyboard = inline_keyboard

    class FakeChatPermissions:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    fake_telegram_module = ModuleType("telegram")
    fake_telegram_module.Update = object
    fake_telegram_module.ChatMember = FakeChatMember
    fake_telegram_module.InlineKeyboardButton = FakeInlineKeyboardButton
    fake_telegram_module.InlineKeyboardMarkup = FakeInlineKeyboardMarkup
    fake_telegram_module.ChatPermissions = FakeChatPermissions

    class FakeApplication:
        @staticmethod
        def builder():
            return SimpleNamespace(token=lambda value: SimpleNamespace())

    class FakeChatMemberHandler:
        MY_CHAT_MEMBER = "my_chat_member"
        CHAT_MEMBER = "chat_member"

    fake_ext_module = ModuleType("telegram.ext")
    fake_ext_module.Application = FakeApplication
    fake_ext_module.CommandHandler = object
    fake_ext_module.MessageHandler = object
    fake_ext_module.ChatMemberHandler = FakeChatMemberHandler
    fake_ext_module.ContextTypes = SimpleNamespace(DEFAULT_TYPE=object)
    fake_ext_module.filters = SimpleNamespace(TEXT=1, COMMAND=2, PHOTO=3, Sticker=SimpleNamespace(ALL=4))
    fake_ext_module.CallbackQueryHandler = object

    monkeypatch.setitem(sys.modules, "config", fake_config_module)
    monkeypatch.setitem(sys.modules, "ai", fake_ai_module)
    monkeypatch.setitem(sys.modules, "ai.prompts", fake_prompts_module)
    monkeypatch.setitem(sys.modules, "i18n", fake_i18n_module)
    monkeypatch.setitem(sys.modules, "telegram", fake_telegram_module)
    monkeypatch.setitem(sys.modules, "telegram.ext", fake_ext_module)
    sys.modules.pop("bot", None)
    module = importlib.import_module("bot")
    monkeypatch.setattr(module, "t", fake_t)
    return module


async def _return_true(*args, **kwargs):
    return True


async def _return_false(*args, **kwargs):
    return False


def test_cmd_stats_requires_owner(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_owner", lambda user_id: False)
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=99),
        message=message,
    )

    asyncio.run(bot_module.cmd_stats(update, SimpleNamespace()))

    assert message.replies == [("owner_only", {})]


def test_cmd_stats_renders_panel_for_owner(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_owner", lambda user_id: True)
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(get_stats=lambda: {"checks_total": 5}))
    monkeypatch.setattr(bot_module, "render_stats_panel", lambda snapshot, translator: f"stats:{snapshot['checks_total']}")
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=message,
    )

    asyncio.run(bot_module.cmd_stats(update, SimpleNamespace()))

    assert message.replies == [("stats:5", {})]


def test_cmd_add_ad_success_calls_list_refresh(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_owner", lambda user_id: True)
    fake_db = SimpleNamespace(add_advertisement=lambda ad: 7)
    monkeypatch.setattr(bot_module, "db", fake_db)
    refreshed = []

    async def fake_cmd_all_ad(update, context):
        refreshed.append((update, context))

    monkeypatch.setattr(bot_module, "cmd_all_ad", fake_cmd_all_ad)
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=message,
    )
    context = SimpleNamespace(args=["Title|https://t.me/test|2099-01-01", "00:00:00|100"])

    asyncio.run(bot_module.cmd_add_ad(update, context))

    assert message.replies == [("ad_add_success|id=7", {})]
    assert len(refreshed) == 1


def test_cmd_del_ad_invalid_id_reports_error(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_owner", lambda user_id: True)
    monkeypatch.setattr(bot_module, "db", SimpleNamespace(delete_advertisement=lambda ad_id: None))
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        message=message,
    )
    context = SimpleNamespace(args=["abc"])

    asyncio.run(bot_module.cmd_del_ad(update, context))

    assert message.replies == [("ad_delete_failed|error=invalid_id", {})]


def test_cmd_unban_requires_group_chat(bot_module):
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="private"),
        message=message,
    )

    asyncio.run(bot_module.cmd_unban(update, SimpleNamespace(args=[])))

    assert message.replies == [("group_only", {})]


def test_cmd_unban_requires_admin(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    message = FakeMessage()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="supergroup"),
        message=message,
    )

    asyncio.run(bot_module.cmd_unban(update, SimpleNamespace(args=["123"])))

    assert message.replies == [("admin_only", {})]


def test_cmd_unban_unbans_reply_target(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_bot = FakeBot()
    reply_to_message = SimpleNamespace(from_user=SimpleNamespace(id=123, first_name="Alice"))
    message = FakeMessage(reply_to_message=reply_to_message)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="supergroup"),
        message=message,
    )
    context = SimpleNamespace(args=[], bot=fake_bot)
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)

    asyncio.run(bot_module.cmd_unban(update, context))

    assert len(fake_bot.restrict_calls) == 1
    assert fake_bot.restrict_calls[0]["user_id"] == 123
    assert fake_db.cleared_history == [(123, 100)]
    assert message.replies == [("unban_success_detail|name=Alice,user_id=123", {})]


def test_handle_unban_button_requires_admin(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    query_message = FakeMessage(chat_id=100)
    query = FakeQuery(
        data="unban_123",
        from_user=SimpleNamespace(id=2, first_name="Boss"),
        message=query_message,
    )
    update = SimpleNamespace(callback_query=query)

    asyncio.run(bot_module.handle_unban_button(update, SimpleNamespace(bot=FakeBot())))

    assert query.answers == [(None, None), ("admin_only", True)]


def test_handle_unban_button_unbans_target_and_notifies(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_bot = FakeBot()
    query_message = FakeMessage(chat_id=100)
    query = FakeQuery(
        data="unban_123",
        from_user=SimpleNamespace(id=2, first_name="Boss"),
        message=query_message,
    )
    update = SimpleNamespace(callback_query=query)
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)

    asyncio.run(bot_module.handle_unban_button(update, SimpleNamespace(bot=fake_bot)))

    assert len(fake_bot.restrict_calls) == 1
    assert fake_bot.restrict_calls[0]["user_id"] == 123
    assert query_message.deleted is True
    assert fake_db.cleared_history == [(123, 100)]
    assert fake_bot.send_calls == [
        (100, "unban_notice|admin=Boss,user_id=123", {"parse_mode": "Markdown"})
    ]
    assert query.answers == [(None, None), ("unban_success", False)]


def test_handle_text_skips_admin_messages(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=9)
    message.text = "hello"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert fake_db.incremented_messages == []


def test_handle_text_deletes_blocked_word_without_calling_ai(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    fake_db = FakeDB()
    fake_db.blocked_word_match = "博彩"
    monkeypatch.setattr(bot_module, "db", fake_db)
    called = []
    monkeypatch.setattr(
        bot_module,
        "ai_client",
        SimpleNamespace(check_text=lambda *args, **kwargs: called.append(True)),
    )
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=9)
    message.text = "博彩推广"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert message.deleted is True
    assert fake_db.incremented_messages == []
    assert called == []


def test_blockword_commands_are_scoped_to_current_group(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)
    message = FakeMessage(chat_id=100)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="supergroup"),
        message=message,
    )

    asyncio.run(bot_module.cmd_add_blockword(update, SimpleNamespace(args=["加我", "私聊"])))
    asyncio.run(bot_module.cmd_blockwords(update, SimpleNamespace(args=[])))
    asyncio.run(bot_module.cmd_del_blockword(update, SimpleNamespace(args=["加我", "私聊"])))

    assert fake_db.blocked_words[100] == []
    assert message.replies[0][0] == "✅ 已添加本群屏蔽词：加我 私聊"
    assert "1. 加我 私聊" in message.replies[1][0]
    assert message.replies[2][0] == "✅ 已解除本群屏蔽词：加我 私聊"


def test_blocked_word_has_priority_and_permanently_mutes(bot_module, monkeypatch):
    fake_db = FakeDB()
    fake_db.blocked_word_match = "无限开卡"
    fake_db.ad_word_match = "开卡"
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=stats_calls.append))
    scheduled = []
    monkeypatch.setattr(
        bot_module,
        "schedule_message_deletion",
        lambda context, chat_id, message_id, delay_seconds, reason: scheduled.append(
            (chat_id, message_id, delay_seconds, reason)
        ),
    )
    fake_bot = FakeBot()
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=9, full_name="Blocked User")
    message.text = "无限开卡"

    action = asyncio.run(
        bot_module.apply_word_rules(SimpleNamespace(bot=fake_bot), 100, message.from_user, message)
    )

    assert action == "blocked_permanent_mute"
    assert message.deleted is True
    assert fake_bot.restrict_calls[0]["until_date"] is None
    assert len(fake_bot.send_calls) == 1
    assert stats_calls == ["banned"]
    assert scheduled == [(100, 901, 300, "permanent mute notice")]


def test_ad_word_uses_hourly_ad_policy_without_ai(bot_module, monkeypatch):
    fake_db = FakeDB()
    fake_db.ad_word_match = "源头"
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=stats_calls.append))
    captured = []

    async def fake_policy(context, chat_id, user, message, result):
        captured.append(result)
        return "allowed_ad"

    monkeypatch.setattr(bot_module, "apply_ad_policy", fake_policy)
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=10, full_name="Advertiser")
    message.text = "AI 源头低价"

    action = asyncio.run(
        bot_module.apply_word_rules(SimpleNamespace(bot=FakeBot()), 100, message.from_user, message)
    )

    assert action == "allowed_ad"
    assert captured[0].score == 100
    assert "源头" in captured[0].reason
    assert stats_calls == ["passed"]


def test_repeated_long_text_is_moderated_without_matching_adword(bot_module, monkeypatch):
    fake_db = FakeDB()
    fake_db.fingerprint_duplicate = True
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=stats_calls.append))
    captured = []

    async def fake_policy(context, chat_id, user, message, result, *, force_duplicate=False):
        captured.append((result, force_duplicate))
        return "duplicate_mute"

    monkeypatch.setattr(bot_module, "apply_ad_policy", fake_policy)
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=10, full_name="Repeater")
    message.text = "自动加群，自动群发，一个人管理多个TG号，免费试用"

    action = asyncio.run(
        bot_module.apply_word_rules(
            SimpleNamespace(bot=FakeBot()),
            100,
            message.from_user,
            message,
        )
    )

    assert action == "duplicate_mute"
    assert captured[0][1] is True
    assert "完全相同" in captured[0][0].reason
    assert stats_calls == ["banned"]


def test_short_repeated_text_is_not_fingerprinted(bot_module, monkeypatch):
    fake_db = FakeDB()
    fake_db.fingerprint_duplicate = True
    monkeypatch.setattr(bot_module, "db", fake_db)
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=10, full_name="Member")
    message.text = "谢谢老板"

    action = asyncio.run(
        bot_module.apply_word_rules(
            SimpleNamespace(bot=FakeBot()),
            100,
            message.from_user,
            message,
        )
    )

    assert action is None
    assert fake_db.fingerprint_calls == []


def test_adword_commands_are_scoped_to_current_group(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)
    message = FakeMessage(chat_id=100)
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="supergroup"),
        message=message,
    )

    asyncio.run(bot_module.cmd_add_adword(update, SimpleNamespace(args=["AI", "源头"])))
    asyncio.run(bot_module.cmd_adwords(update, SimpleNamespace(args=[])))
    asyncio.run(bot_module.cmd_del_adword(update, SimpleNamespace(args=["AI", "源头"])))

    assert fake_db.ad_words[100] == []
    assert message.replies[0][0] == "✅ 已添加本群广告词：AI 源头"
    assert "1. AI 源头" in message.replies[1][0]
    assert message.replies[2][0] == "✅ 已解除本群广告词：AI 源头"


def test_muted_user_can_submit_appeal(bot_module):
    fake_bot = FakeBot()
    query = FakeQuery(
        data="appeal_123",
        from_user=SimpleNamespace(id=123, full_name="Alice"),
        message=FakeMessage(chat_id=100),
    )

    asyncio.run(
        bot_module.handle_appeal_button(
            SimpleNamespace(callback_query=query),
            SimpleNamespace(bot=fake_bot),
        )
    )

    assert len(fake_bot.send_calls) == 1
    assert "已提交解除禁言申诉" in fake_bot.send_calls[0][1]
    assert query.edited_reply_markup is not None


def test_other_user_cannot_submit_someone_elses_appeal(bot_module):
    fake_bot = FakeBot()
    query = FakeQuery(
        data="appeal_123",
        from_user=SimpleNamespace(id=999, full_name="Other"),
        message=FakeMessage(chat_id=100),
    )

    asyncio.run(
        bot_module.handle_appeal_button(
            SimpleNamespace(callback_query=query),
            SimpleNamespace(bot=fake_bot),
        )
    )

    assert fake_bot.send_calls == []
    assert query.answers[-1] == ("只有被禁言者本人可以发起申诉", True)


def test_admin_can_manually_permanently_mute_reply_target(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "_require_group_admin", _return_true)
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    fake_bot = FakeBot()
    target = SimpleNamespace(id=123, full_name="Alice", first_name="Alice")
    message = FakeMessage(chat_id=100, reply_to_message=SimpleNamespace(from_user=target))
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=2),
        effective_chat=SimpleNamespace(id=100, type="supergroup"),
        message=message,
    )

    asyncio.run(bot_module.cmd_mute(update, SimpleNamespace(args=[], bot=fake_bot)))

    assert fake_bot.restrict_calls[0]["user_id"] == 123
    assert fake_bot.restrict_calls[0]["until_date"] is None
    assert len(fake_bot.send_calls) == 1


def test_handle_text_creates_user_and_bans_spam(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    monkeypatch.setattr(bot_module, "extract_message_text", lambda message: "visible spam")
    fake_db = FakeDB()
    monkeypatch.setattr(bot_module, "db", fake_db)
    fake_ai = SimpleNamespace(check_text=lambda user_info, text: _async_result(SimpleNamespace(is_spam=True, score=95)))
    monkeypatch.setattr(bot_module, "ai_client", fake_ai)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    banned = []

    async def fake_ban(context, chat_id, user, message, result):
        banned.append((chat_id, user.id, result.score))
        return "temporary_mute"

    monkeypatch.setattr(bot_module, "apply_ad_policy", fake_ban)
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=10)
    message.text = "spam"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert len(fake_db.saved_users) == 1
    assert fake_db.incremented_messages == [(10, 100)]
    assert banned == [(100, 10, 95)]
    assert stats_calls == ["banned"]


def test_handle_text_skips_ai_when_need_check_is_false(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: False)
    fake_db = FakeDB(user=SimpleNamespace(user_id=10, chat_id=100, join_time=datetime(2026, 1, 1), message_count=0, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    called = []
    monkeypatch.setattr(bot_module, "ai_client", SimpleNamespace(check_text=lambda *args, **kwargs: called.append(True)))
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=10)
    message.text = "hello"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert fake_db.incremented_messages == [(10, 100)]
    assert called == []


def test_handle_text_marks_passed_and_increments_verification(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    monkeypatch.setattr(bot_module, "extract_message_text", lambda message: "clean text")
    fake_db = FakeDB(user=SimpleNamespace(user_id=11, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    monkeypatch.setattr(
        bot_module,
        "ai_client",
        SimpleNamespace(check_text=lambda user_info, text: _async_result(SimpleNamespace(is_spam=False, score=20))),
    )
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=11)
    message.text = "hello"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert fake_db.incremented_verifications == [(11, 100)]
    assert stats_calls == ["passed"]


def test_handle_text_records_failed_when_ai_errors(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=12, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)

    async def broken_check_text(user_info, text):
        raise RuntimeError("boom")

    monkeypatch.setattr(bot_module, "ai_client", SimpleNamespace(check_text=broken_check_text))
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=12)
    message.text = "hello"
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_text(update, SimpleNamespace(bot=FakeBot())))

    assert stats_calls == ["failed"]
    assert fake_db.incremented_verifications == []


def test_handle_photo_downloads_image_and_marks_passed(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    monkeypatch.setattr(bot_module, "extract_message_text", lambda message: "caption text")
    fake_db = FakeDB(user=SimpleNamespace(user_id=20, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    captured = {}

    async def fake_evaluate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(should_ban=False, result=SimpleNamespace(score=0))

    monkeypatch.setattr(bot_module, "evaluate_photo_moderation", fake_evaluate)
    fake_bot = FakeBot()
    fake_bot.files["photo-1"] = FakeDownloadedFile(b"img")
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=20)
    message.photo = [SimpleNamespace(file_id="photo-1")]
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_photo(update, SimpleNamespace(bot=fake_bot)))

    assert captured["message_text"] == "caption text"
    assert captured["image_base64"].startswith("data:image/jpeg;base64,")
    assert fake_db.incremented_verifications == [(20, 100)]
    assert stats_calls == ["passed"]


def test_handle_photo_bans_when_decision_is_spam(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=21, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    monkeypatch.setattr(
        bot_module,
        "evaluate_photo_moderation",
        lambda **kwargs: _async_result(SimpleNamespace(should_ban=True, result=SimpleNamespace(score=99))),
    )
    banned = []

    async def fake_ban(context, chat_id, user, message, result):
        banned.append((chat_id, user.id, result.score))
        return "temporary_mute"

    monkeypatch.setattr(bot_module, "apply_ad_policy", fake_ban)
    fake_bot = FakeBot()
    fake_bot.files["photo-2"] = FakeDownloadedFile(b"img")
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=21)
    message.photo = [SimpleNamespace(file_id="photo-2")]
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_photo(update, SimpleNamespace(bot=fake_bot)))

    assert banned == [(100, 21, 99)]
    assert stats_calls == ["banned"]


def test_handle_photo_records_failed_when_download_errors(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=22, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    fake_bot = FakeBot()
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=22)
    message.photo = [SimpleNamespace(file_id="missing")]
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_photo(update, SimpleNamespace(bot=fake_bot)))

    assert stats_calls == ["failed"]


def test_handle_sticker_marks_passed(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=30, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    monkeypatch.setattr(
        bot_module,
        "ai_client",
        SimpleNamespace(check_image=lambda user_info, image: _async_result(SimpleNamespace(is_spam=False, score=20))),
    )
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    fake_bot = FakeBot()
    fake_bot.files["sticker-1"] = FakeDownloadedFile(b"webp")
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=30)
    message.sticker = SimpleNamespace(file_id="sticker-1")
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_sticker(update, SimpleNamespace(bot=fake_bot)))

    assert fake_db.incremented_verifications == [(30, 100)]
    assert stats_calls == ["passed"]


def test_handle_sticker_bans_spam(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=31, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    monkeypatch.setattr(
        bot_module,
        "ai_client",
        SimpleNamespace(check_image=lambda user_info, image: _async_result(SimpleNamespace(is_spam=True, score=96))),
    )
    stats_calls = []
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    banned = []

    async def fake_ban(context, chat_id, user, message, result):
        banned.append((chat_id, user.id, result.score))
        return "temporary_mute"

    monkeypatch.setattr(bot_module, "apply_ad_policy", fake_ban)
    fake_bot = FakeBot()
    fake_bot.files["sticker-2"] = FakeDownloadedFile(b"webp")
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=31)
    message.sticker = SimpleNamespace(file_id="sticker-2")
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_sticker(update, SimpleNamespace(bot=fake_bot)))

    assert banned == [(100, 31, 96)]
    assert stats_calls == ["banned"]


def test_handle_sticker_logs_error_when_detection_fails(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_false)
    monkeypatch.setattr(bot_module, "need_check", lambda user: True)
    fake_db = FakeDB(user=SimpleNamespace(user_id=32, chat_id=100, join_time=datetime(2026, 1, 1), message_count=1, verification_times=0))
    monkeypatch.setattr(bot_module, "db", fake_db)
    stats_calls = []
    fake_logger = FakeLogger()
    monkeypatch.setattr(bot_module, "logger", fake_logger)
    monkeypatch.setattr(bot_module, "stats", SimpleNamespace(record_check=lambda outcome: stats_calls.append(outcome)))
    fake_bot = FakeBot()
    message = FakeMessage(chat_id=100)
    message.from_user = SimpleNamespace(id=32)
    message.sticker = SimpleNamespace(file_id="missing")
    update = SimpleNamespace(message=message)

    asyncio.run(bot_module.handle_sticker(update, SimpleNamespace(bot=fake_bot)))

    assert stats_calls == ["failed"]
    assert fake_logger.errors


def test_handle_bot_added_to_group_sends_welcome_and_schedules_cleanup(bot_module, monkeypatch):
    scheduled = []
    monkeypatch.setattr(
        bot_module,
        "schedule_message_deletion",
        lambda context, chat_id, message_id, delay_seconds, reason: scheduled.append((chat_id, message_id, delay_seconds, reason)),
    )
    fake_bot = FakeBot()
    update = SimpleNamespace(
        my_chat_member=SimpleNamespace(
            old_chat_member=SimpleNamespace(status=bot_module.ChatMember.LEFT),
            new_chat_member=SimpleNamespace(status=bot_module.ChatMember.MEMBER),
            chat=SimpleNamespace(id=555, title="Group A"),
        )
    )

    asyncio.run(bot_module.handle_bot_added_to_group(update, SimpleNamespace(bot=fake_bot)))

    assert len(fake_bot.send_calls) == 1
    assert fake_bot.send_calls[0][0] == 555
    assert "广告限额机器人已加入" in fake_bot.send_calls[0][1]
    assert scheduled == [(555, 901, 30, "welcome message")]


def test_handle_bot_added_to_group_logs_welcome_send_failure(bot_module, monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr(bot_module, "logger", fake_logger)

    class FailingBot(FakeBot):
        async def send_message(self, chat_id, text, **kwargs):
            raise RuntimeError("send failed")

    update = SimpleNamespace(
        my_chat_member=SimpleNamespace(
            old_chat_member=SimpleNamespace(status=bot_module.ChatMember.LEFT),
            new_chat_member=SimpleNamespace(status=bot_module.ChatMember.MEMBER),
            chat=SimpleNamespace(id=556, title="Group B"),
        )
    )

    asyncio.run(bot_module.handle_bot_added_to_group(update, SimpleNamespace(bot=FailingBot())))

    assert fake_logger.errors


def test_handle_bot_added_to_group_logs_admin_promotion(bot_module, monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr(bot_module, "logger", fake_logger)
    fake_bot = FakeBot()
    update = SimpleNamespace(
        my_chat_member=SimpleNamespace(
            old_chat_member=SimpleNamespace(status=bot_module.ChatMember.MEMBER),
            new_chat_member=SimpleNamespace(status=bot_module.ChatMember.ADMINISTRATOR),
            chat=SimpleNamespace(id=557, title="Group C"),
        )
    )

    asyncio.run(bot_module.handle_bot_added_to_group(update, SimpleNamespace(bot=fake_bot)))

    assert len(fake_bot.send_calls) == 1
    assert "广告限额开始生效" in fake_bot.send_calls[0][1]
    assert fake_logger.infos


def test_handle_bot_added_to_group_logs_admin_promotion_failure(bot_module, monkeypatch):
    fake_logger = FakeLogger()
    monkeypatch.setattr(bot_module, "logger", fake_logger)

    class FailingBot(FakeBot):
        async def send_message(self, chat_id, text, **kwargs):
            raise RuntimeError("send failed")

    update = SimpleNamespace(
        my_chat_member=SimpleNamespace(
            old_chat_member=SimpleNamespace(status=bot_module.ChatMember.MEMBER),
            new_chat_member=SimpleNamespace(status=bot_module.ChatMember.ADMINISTRATOR),
            chat=SimpleNamespace(id=558, title="Group D"),
        )
    )

    asyncio.run(bot_module.handle_bot_added_to_group(update, SimpleNamespace(bot=FailingBot())))

    assert fake_logger.errors


def test_handle_unban_button_logs_warning_when_notice_delete_fails(bot_module, monkeypatch):
    monkeypatch.setattr(bot_module, "is_chat_admin", _return_true)
    fake_logger = FakeLogger()
    monkeypatch.setattr(bot_module, "logger", fake_logger)
    fake_bot = FakeBot()
    query_message = FakeMessage(chat_id=100)

    async def broken_delete():
        raise RuntimeError("cannot delete")

    query_message.delete = broken_delete
    query = FakeQuery(
        data="unban_123",
        from_user=SimpleNamespace(id=2, first_name="Boss"),
        message=query_message,
    )
    update = SimpleNamespace(callback_query=query)
    monkeypatch.setattr(bot_module, "db", FakeDB())

    asyncio.run(bot_module.handle_unban_button(update, SimpleNamespace(bot=fake_bot)))

    assert fake_logger.warnings
    assert fake_bot.send_calls == [
        (100, "unban_notice|admin=Boss,user_id=123", {"parse_mode": "Markdown"})
    ]


async def _async_result(value):
    return value


def test_apply_ad_policy_keeps_first_ad(bot_module, monkeypatch):
    decision = SimpleNamespace(is_allowed=True, is_permanent=False, action="allow", violation_count=0)
    monkeypatch.setattr(
        bot_module,
        "db",
        SimpleNamespace(register_detected_ad=lambda **kwargs: decision),
    )
    message = FakeMessage(chat_id=100)
    user = SimpleNamespace(id=88, full_name="Alice")
    fake_bot = FakeBot()

    action = asyncio.run(
        bot_module.apply_ad_policy(
            SimpleNamespace(bot=fake_bot),
            100,
            user,
            message,
            SimpleNamespace(score=95, reason="推广"),
        )
    )

    assert action == "allowed_ad"
    assert message.deleted is False
    assert fake_bot.restrict_calls == []


def test_apply_ad_policy_deletes_and_temporarily_mutes_violation(bot_module, monkeypatch):
    decision = SimpleNamespace(
        is_allowed=False,
        is_permanent=False,
        action="temporary_mute",
        violation_count=1,
    )
    monkeypatch.setattr(
        bot_module,
        "db",
        SimpleNamespace(register_detected_ad=lambda **kwargs: decision),
    )

    async def fake_notice(*args, **kwargs):
        return None

    monkeypatch.setattr(bot_module, "send_policy_notice", fake_notice)
    message = FakeMessage(chat_id=100)
    user = SimpleNamespace(id=88, full_name="Alice")
    fake_bot = FakeBot()

    action = asyncio.run(
        bot_module.apply_ad_policy(
            SimpleNamespace(bot=fake_bot),
            100,
            user,
            message,
            SimpleNamespace(score=95, reason="推广"),
        )
    )

    assert action == "temporary_mute"
    assert message.deleted is True
    assert len(fake_bot.restrict_calls) == 1
    assert fake_bot.restrict_calls[0]["until_date"] is not None


def test_apply_ad_policy_mutes_duplicate_for_twelve_hours(bot_module, monkeypatch):
    decision = SimpleNamespace(
        is_allowed=False,
        is_permanent=False,
        is_duplicate_content=True,
        action="duplicate_mute",
        violation_count=0,
    )
    monkeypatch.setattr(
        bot_module,
        "db",
        SimpleNamespace(register_detected_ad=lambda **kwargs: decision),
    )
    monkeypatch.setattr(
        bot_module,
        "policy_settings",
        lambda: {
            "ad_interval": bot_module.timedelta(hours=1),
            "violation_window": bot_module.timedelta(days=7),
            "permanent_mute_after": 3,
            "temporary_mute": bot_module.timedelta(hours=1),
            "duplicate_mute": bot_module.timedelta(hours=12),
        },
    )

    captured_minutes = []

    async def fake_notice(context, chat_id, user, result, actual_decision, minutes):
        captured_minutes.append(minutes)

    monkeypatch.setattr(bot_module, "send_policy_notice", fake_notice)
    message = FakeMessage(chat_id=100)
    user = SimpleNamespace(id=88, full_name="Alice")
    fake_bot = FakeBot()
    before = datetime.now(bot_module.timezone.utc)

    action = asyncio.run(
        bot_module.apply_ad_policy(
            SimpleNamespace(bot=fake_bot),
            100,
            user,
            message,
            SimpleNamespace(score=100, reason="相同广告"),
        )
    )

    until_date = fake_bot.restrict_calls[0]["until_date"]
    assert action == "duplicate_mute"
    assert captured_minutes == [720]
    assert bot_module.timedelta(hours=11, minutes=59) < until_date - before
    assert until_date - before < bot_module.timedelta(hours=12, minutes=1)


def test_permanent_policy_notice_is_deleted_after_five_minutes(bot_module, monkeypatch):
    scheduled = []
    monkeypatch.setattr(
        bot_module,
        "schedule_message_deletion",
        lambda context, chat_id, message_id, delay_seconds, reason: scheduled.append(
            (chat_id, message_id, delay_seconds, reason)
        ),
    )
    monkeypatch.setattr(
        bot_module,
        "config",
        SimpleNamespace(get=lambda key, default=None: default),
    )
    decision = SimpleNamespace(
        is_permanent=True,
        is_duplicate_content=False,
        violation_count=3,
    )
    fake_bot = FakeBot()

    asyncio.run(
        bot_module.send_policy_notice(
            SimpleNamespace(bot=fake_bot),
            100,
            SimpleNamespace(id=88, full_name="Alice"),
            SimpleNamespace(reason="普通额度违规"),
            decision,
            60,
        )
    )

    assert scheduled == [(100, 901, 300, "policy notice")]
