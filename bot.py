"""
AI 反垃圾广告机器人 (AI Anti-Spam Bot)
官方项目：https://github.com/luoyanglang/AI-Anti-Spam-Bot
开发者：狼哥 (@luoyanglang)

功能：
1. 广告按钮管理 (/add_ad, /all_ad, /del_ad)
2. verification_times 验证机制
3. 灵活的检测策略配置
4. 配置验证和错误处理优化

如果本项目对您有帮助，请保留开发者信息，这是对开源作者最基本的尊重 🙏
"""
import asyncio
import base64
import hashlib
import html
import logging
import sys
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from telegram import Update, ChatMember, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ChatMemberHandler, ContextTypes, filters, CallbackQueryHandler
)
from config import config
from database import db, UserInfo
from developer_info import get_start_message
from i18n import t, set_locale
from message_utils import extract_message_text
from handler_logic import evaluate_photo_moderation
from moderation_logic import RuntimeStats, should_check_user
from command_logic import (
    CommandInputError,
    parse_add_ad_payload,
    parse_delete_ad_args,
    parse_unban_callback_data,
    resolve_unban_target,
)
from command_views import render_ad_list, render_stats_panel

# 确保日志目录存在
os.makedirs('data', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('data/bot.log', encoding='utf-8')
    ]
)
# httpx 的 INFO 日志会输出包含 Bot Token 的 Telegram API URL。
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

stats = RuntimeStats()

# 项目信息（请勿移除）
PROJECT_INFO = {
    'name': 'Telegram Ad Guard',
    'repo': 'https://github.com/luoyanglang/AI-Anti-Spam-Bot',
    'channel': 'https://t.me/langgefabu',
    'group': 'https://t.me/langgepython',
    'developer': '@luoyanglang',
    'demo_bot': '@xiaolangzaibot'
}

def detection_mode() -> str:
    return str(config.get("detection.mode", "ai")).strip().lower()


def create_configured_ai_client():
    from ai import create_ai_client

    return create_ai_client()


ai_client = create_configured_ai_client() if detection_mode() == "ai" else None

# ============ 工具函数 ============

def is_owner(user_id: int) -> bool:
    """检查是否为超级管理员（可管理广告）"""
    owners = {str(value) for value in config.get("telegram.owners", [])}
    return str(user_id) in owners


def is_whitelisted(user_id: int) -> bool:
    """超级管理员和显式白名单永不参与广告限额。"""
    whitelist = {str(value) for value in config.get("telegram.whitelist_user_ids", [])}
    return is_owner(user_id) or str(user_id) in whitelist


def is_allowed_group(chat_id: int) -> bool:
    if config.get("telegram.allow_any_group", False):
        return True
    groups = {str(value) for value in config.get("telegram.groups", [])}
    return str(chat_id) in groups

async def is_chat_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """检查是否为群管理员"""
    cache = getattr(context, "bot_data", None)
    cache_key = (chat_id, user_id)
    now = asyncio.get_running_loop().time()
    if isinstance(cache, dict):
        admin_cache = cache.setdefault("admin_status_cache", {})
        cached = admin_cache.get(cache_key)
        if cached and cached[1] > now:
            return cached[0]
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        result = member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
        if isinstance(cache, dict):
            admin_cache[cache_key] = (result, now + 300)
        return result
    except Exception:
        return False

def need_check(user: UserInfo) -> bool:
    """
    判断用户是否需要检测
    支持灵活的检测策略配置
    """
    if config.get("strategy.always_check", True):
        return True

    strategy = {
        "verification_times": config.get("strategy.verification_times", 0),
        "joined_days": config.get("strategy.joined_days", 3),
        "check_message_count": config.get("strategy.check_message_count", True),
        "min_messages": config.get("strategy.min_messages", 3),
    }
    return should_check_user(user, strategy)


def policy_settings() -> dict:
    """读取并规范化广告额度配置。"""
    return {
        "ad_interval": timedelta(minutes=int(config.get("policy.ad_interval_minutes", 60))),
        "violation_window": timedelta(days=int(config.get("policy.violation_window_days", 7))),
        "permanent_mute_after": int(config.get("policy.permanent_mute_after", 3)),
        "temporary_mute": timedelta(minutes=int(config.get("policy.temporary_mute_minutes", 60))),
        "duplicate_mute": timedelta(hours=int(config.get("policy.duplicate_ad_mute_hours", 12))),
    }


def no_send_permissions():
    from telegram import ChatPermissions
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


def normal_member_permissions():
    from telegram import ChatPermissions
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )


def current_message_body(message) -> str:
    """只返回当前消息的文本/说明，避免引用内容误伤发言者。"""
    return (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()


def ad_content_hash(message) -> str:
    """为广告当前正文生成群级去重指纹，不在数据库中保存广告明文。"""
    body = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    return hashlib.sha256(body.encode("utf-8")).hexdigest() if body else ""


def permanent_mute_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📨 本人发起申诉", callback_data=f"appeal_{user_id}")],
        [InlineKeyboardButton("🔓 管理员解除禁言", callback_data=f"unban_{user_id}")],
    ])


async def send_permanent_mute_notice(context, chat_id: int, user, reason: str):
    safe_name = html.escape(getattr(user, "full_name", None) or str(user.id))
    notice = (
        f'🚫 <a href="tg://user?id={user.id}">{safe_name}</a> 已被<b>永久禁言</b>。\n'
        f"原因：{html.escape(reason)}\n"
        "如需申诉，由被禁言者本人点击下方按钮。"
    )
    sent_message = await context.bot.send_message(
        chat_id,
        notice,
        parse_mode="HTML",
        reply_markup=permanent_mute_keyboard(user.id),
    )
    delete_after = int(config.get("message.delete_permanent_mute_notice_after_seconds", 300))
    schedule_message_deletion(
        context,
        chat_id,
        sent_message.message_id,
        delete_after,
        "permanent mute notice",
    )


async def enforce_blocked_word(message, chat_id: int, user, context, matched: str) -> None:
    """屏蔽词优先级最高：删除原消息并永久禁言。"""
    try:
        await message.delete()
    except Exception as exc:
        logger.warning(
            "Failed to delete blocked-word message: chat=%s message=%s error=%s",
            chat_id,
            message.message_id,
            exc,
        )
    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user.id,
        permissions=no_send_permissions(),
        until_date=None,
    )
    await send_permanent_mute_notice(context, chat_id, user, f"命中本群屏蔽词：{matched}")
    logger.info(
        "Blocked-word permanent mute: chat=%s user=%s word=%r message=%s",
        chat_id,
        user.id,
        matched,
        message.message_id,
    )

def build_user_info(user, db_user: UserInfo) -> str:
    """构建用户信息字符串（不包含用户名称，避免因名称误判）"""
    from ai.prompts import USER_INFO_TEMPLATE

    return USER_INFO_TEMPLATE.format(
        msg_count=db_user.message_count + 1,
        join_time=db_user.join_time.strftime("%Y-%m-%d %H:%M")
    )

def schedule_message_deletion(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    delay_seconds: int,
    reason: str = "message"
):
    """后台延迟删除消息，避免群内长期堆积系统提示"""
    if delay_seconds <= 0:
        return

    async def delete_after_delay():
        await asyncio.sleep(delay_seconds)
        try:
            await context.bot.delete_message(chat_id, message_id)
            logger.info(f"Deleted {reason} in group {chat_id} after {delay_seconds}s")
        except Exception as e:
            logger.warning(f"Failed to delete {reason} in {chat_id}: {e}")

    asyncio.create_task(delete_after_delay())

def create_ban_keyboard() -> InlineKeyboardMarkup:
    """
    创建封禁通知的按钮
    包含：解封按钮 + 广告按钮
    """
    buttons = []
    
    # 第一行：解封按钮（占位，实际在 send_ban_notice 中动态生成）
    # buttons.append([InlineKeyboardButton("🔓 解除禁言", callback_data=f"unban_{user_id}")])
    
    # 后续行：广告按钮
    ads = db.get_valid_advertisements()
    for ad in ads:
        buttons.append([InlineKeyboardButton(ad.title, url=ad.url)])
    
    return InlineKeyboardMarkup(buttons) if buttons else None

async def send_policy_notice(context, chat_id: int, user, result, decision, temporary_minutes: int):
    """发送简洁、可申诉的额度违规通知。"""
    safe_name = html.escape(user.full_name or str(user.id))
    safe_reason = html.escape(getattr(result, "reason", "") or "命中广告词")
    if decision.is_permanent:
        action_text = "永久禁言"
    elif getattr(decision, "is_duplicate_content", False):
        action_text = f"禁言 {temporary_minutes // 60} 小时"
    else:
        action_text = f"禁言 {temporary_minutes} 分钟"

    is_duplicate = getattr(decision, "is_duplicate_content", False)
    violation_text = (
        "发送了本群 60 分钟内已经出现过的相同广告"
        if is_duplicate
        else "在广告额度内重复发广告"
    )
    count_text = (
        "此类重复不计入永久禁言次数。\n"
        if is_duplicate
        else f"最近统计周期内违规：<b>{decision.violation_count}</b> 次。\n"
    )
    notice = (
        f'⚠️ <a href="tg://user?id={user.id}">{safe_name}</a> {violation_text}。\n'
        f"本条已删除，处理：<b>{action_text}</b>。\n"
        f"{count_text}"
        f"识别原因：{safe_reason}"
    )
    if decision.is_permanent:
        buttons = permanent_mute_keyboard(user.id).inline_keyboard
    else:
        buttons = [[InlineKeyboardButton("管理员解除并清除记录", callback_data=f"unban_{user.id}")]]
    sent_message = await context.bot.send_message(
        chat_id,
        notice,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    delete_after = int(config.get(
        "message.delete_permanent_mute_notice_after_seconds"
        if decision.is_permanent
        else "message.delete_policy_notice_after_seconds",
        300 if decision.is_permanent else 60,
    ))
    schedule_message_deletion(context, chat_id, sent_message.message_id, delete_after, "policy notice")


async def apply_ad_policy(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user, message, result):
    """对已确认的广告执行一小时额度及滚动七天处罚。"""
    settings = policy_settings()
    decision = db.register_detected_ad(
        chat_id=chat_id,
        user_id=user.id,
        message_id=message.message_id,
        ad_interval=settings["ad_interval"],
        violation_window=settings["violation_window"],
        permanent_mute_after=settings["permanent_mute_after"],
        score=getattr(result, "score", 0),
        reason=getattr(result, "reason", ""),
        content_hash=ad_content_hash(message),
    )

    if decision.is_allowed:
        logger.info("Allowed first ad in quota: chat=%s user=%s", chat_id, user.id)
        return "allowed_ad"

    try:
        await message.delete()
    except Exception as exc:
        logger.warning("Failed to delete violating ad chat=%s message=%s: %s", chat_id, message.message_id, exc)

    mute_duration = (
        settings["duplicate_mute"]
        if getattr(decision, "is_duplicate_content", False)
        else settings["temporary_mute"]
    )
    until_date = None
    if not decision.is_permanent:
        until_date = datetime.now(timezone.utc) + mute_duration

    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user.id,
        permissions=no_send_permissions(),
        until_date=until_date,
    )
    temporary_minutes = int(mute_duration.total_seconds() // 60)
    await send_policy_notice(context, chat_id, user, result, decision, temporary_minutes)
    logger.info(
        "Ad violation enforced: chat=%s user=%s action=%s count=%s score=%s",
        chat_id, user.id, decision.action, decision.violation_count, getattr(result, "score", 0),
    )
    return decision.action


async def apply_word_rules(context, chat_id: int, user, message):
    """按屏蔽词 > 广告词的优先级处理当前消息。"""
    body = current_message_body(message)
    if not body:
        return None

    blocked_word = db.find_blocked_word(chat_id, body)
    if blocked_word:
        await enforce_blocked_word(message, chat_id, user, context, blocked_word)
        stats.record_check("banned")
        return "blocked_permanent_mute"

    ad_word = db.find_ad_word(chat_id, body)
    if ad_word:
        result = SimpleNamespace(
            is_spam=True,
            score=100,
            reason=f"命中本群广告词：{ad_word}",
            mock_text="",
        )
        action = await apply_ad_policy(context, chat_id, user, message, result)
        stats.record_check("passed" if action == "allowed_ad" else "banned")
        return action

    return None


# ============ 消息处理 ============

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理文本消息"""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if not message or not message.from_user:
        return
    user = message.from_user
    chat_id = message.chat_id

    if not is_allowed_group(chat_id) or is_whitelisted(user.id):
        return

    if await is_chat_admin(chat_id, user.id, context):
        return

    word_action = await apply_word_rules(context, chat_id, user, message)
    if word_action:
        return
    if detection_mode() != "ai":
        return

    db_user = db.get_user(user.id, chat_id)
    if not db_user:
        db_user = UserInfo(
            user_id=user.id,
            chat_id=chat_id,
            join_time=datetime.now(),
            message_count=0,
            check_count=0,
            verification_times=0
        )
        db.save_user(db_user)
    
    db.increment_message_count(user.id, chat_id)

    if not need_check(db_user):
        return

    try:
        user_info = build_user_info(user, db_user)
        message_text = extract_message_text(message) or message.text
        result = await ai_client.check_text(user_info, message_text)
        
        score_threshold = config.get("strategy.spam_score", 80)
        
        if result.is_spam and result.score >= score_threshold:
            action = await apply_ad_policy(context, chat_id, user, message, result)
            stats.record_check('passed' if action == 'allowed_ad' else 'banned')
        else:
            # 不是垃圾广告，增加验证通过次数
            db.increment_verification_times(user.id, chat_id)
            stats.record_check('passed')
            logger.info(f"User {user.id} passed check, verification_times increased")
    except Exception as e:
        logger.error(f"❌ AI 检测失败 (用户 {user.id}): {e}", exc_info=True)
        stats.record_check('failed')
        # 失败时不封禁，避免误伤

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理图片消息"""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if not message or not message.from_user:
        return
    user = message.from_user
    chat_id = message.chat_id

    if not is_allowed_group(chat_id) or is_whitelisted(user.id):
        return

    if await is_chat_admin(chat_id, user.id, context):
        return

    word_action = await apply_word_rules(context, chat_id, user, message)
    if word_action:
        return
    if detection_mode() != "ai":
        return

    db_user = db.get_user(user.id, chat_id)
    if not db_user:
        db_user = UserInfo(
            user_id=user.id,
            chat_id=chat_id,
            join_time=datetime.now(),
            message_count=0,
            check_count=0,
            verification_times=0
        )
        db.save_user(db_user)

    db.increment_message_count(user.id, chat_id)

    if not need_check(db_user):
        return

    try:
        photo = message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        image_bytes = await file.download_as_bytearray()
        image_base64 = f"data:image/jpeg;base64,{base64.b64encode(image_bytes).decode()}"

        user_info = build_user_info(user, db_user)
        score_threshold = config.get("strategy.spam_score", 80)
        message_text = extract_message_text(message)
        decision = await evaluate_photo_moderation(
            ai_client=ai_client,
            user_info=user_info,
            image_base64=image_base64,
            score_threshold=score_threshold,
            message_text=message_text,
            logger=logger,
            user_id=user.id,
        )

        if decision.should_ban:
            action = await apply_ad_policy(context, chat_id, user, message, decision.result)
            stats.record_check('passed' if action == 'allowed_ad' else 'banned')
        else:
            db.increment_verification_times(user.id, chat_id)
            stats.record_check('passed')
    except Exception as e:
        logger.error(f"❌ 图片检测失败 (用户 {user.id}): {e}", exc_info=True)
        stats.record_check('failed')
        # 失败时不封禁，避免误伤

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理贴纸消息"""
    message = getattr(update, "effective_message", None) or getattr(update, "message", None)
    if not message or not message.from_user:
        return
    user = message.from_user
    chat_id = message.chat_id

    if not is_allowed_group(chat_id) or is_whitelisted(user.id):
        return

    if await is_chat_admin(chat_id, user.id, context):
        return

    if detection_mode() != "ai":
        return

    db_user = db.get_user(user.id, chat_id)
    if not db_user:
        db_user = UserInfo(
            user_id=user.id,
            chat_id=chat_id,
            join_time=datetime.now(),
            message_count=0,
            check_count=0,
            verification_times=0
        )
        db.save_user(db_user)
    
    db.increment_message_count(user.id, chat_id)

    if not need_check(db_user):
        return

    try:
        file = await context.bot.get_file(message.sticker.file_id)
        image_bytes = await file.download_as_bytearray()
        image_base64 = f"data:image/webp;base64,{base64.b64encode(image_bytes).decode()}"

        user_info = build_user_info(user, db_user)
        result = await ai_client.check_image(user_info, image_base64)
        
        score_threshold = config.get("strategy.spam_score", 80)
        if result.is_spam and result.score >= score_threshold:
            action = await apply_ad_policy(context, chat_id, user, message, result)
            stats.record_check('passed' if action == 'allowed_ad' else 'banned')
        else:
            db.increment_verification_times(user.id, chat_id)
            stats.record_check('passed')
    except Exception as e:
        logger.error(f"❌ 贴纸检测失败 (用户 {user.id}): {e}", exc_info=True)
        stats.record_check('failed')
        # 失败时不封禁，避免误伤


# ============ 成员变动 ============

async def handle_bot_added_to_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 Bot 被添加到群组"""
    chat_member = update.my_chat_member
    new_status = chat_member.new_chat_member.status
    old_status = chat_member.old_chat_member.status
    chat = chat_member.chat
    
    # Bot 被添加到群组（从非成员变为成员）
    if old_status in [ChatMember.LEFT, ChatMember.BANNED] and new_status == ChatMember.MEMBER:
        welcome_msg = (
            "👋 广告限额机器人已加入。\n\n"
            "请将我提升为管理员，并授予：\n"
            "• 删除消息\n"
            "• 封禁/限制成员\n\n"
            "还需要在 @BotFather 中关闭 Privacy Mode，我才能读取普通群消息。"
        )
        
        try:
            sent_message = await context.bot.send_message(chat.id, welcome_msg)
            delete_after = config.get("message.delete_welcome_message_after_seconds", 30)
            schedule_message_deletion(context, chat.id, sent_message.message_id, delete_after, "welcome message")
            
        except Exception as e:
            logger.error(f"Failed to send welcome message to {chat.id}: {e}")
    
    # Bot 被提升为管理员
    elif new_status == ChatMember.ADMINISTRATOR and old_status != ChatMember.ADMINISTRATOR:
        admin_msg = (
            "✅ 管理权限已收到，广告限额开始生效。\n"
            "管理员可使用 /admin 查看当前规则。"
        )
        
        try:
            await context.bot.send_message(chat.id, admin_msg)
            logger.info(f"Bot promoted to admin in group {chat.id} ({chat.title})")
        except Exception as e:
            logger.error(f"Failed to send admin promotion message to {chat.id}: {e}")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理新成员加入"""
    chat_member = update.chat_member
    if chat_member.new_chat_member.status == ChatMember.MEMBER:
        user = chat_member.new_chat_member.user
        chat_id = chat_member.chat.id
        
        db_user = UserInfo(
            user_id=user.id,
            chat_id=chat_id,
            join_time=datetime.now(),
            message_count=0,
            check_count=0,
            verification_times=0
        )
        db.save_user(db_user)
        logger.info(f"New member {user.id} joined chat {chat_id}")

# ============ 广告管理命令 ============

async def cmd_add_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    添加广告按钮
    格式: /add_ad 标题|链接|过期时间|权重
    例如: /add_ad 官方频道|https://t.me/channel|2099-01-01 00:00:00|100
    """
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text(t('owner_only'))
        return
    
    if not context.args:
        await update.message.reply_text(t('ad_add_usage'))
        return
    
    try:
        payload = " ".join(context.args)
        ad = parse_add_ad_payload(payload)
        ad_id = db.add_advertisement(ad)
        await update.message.reply_text(t('ad_add_success', id=ad_id))
        
        # 显示所有广告
        await cmd_all_ad(update, context)
    except CommandInputError as e:
        if e.code == "format":
            await update.message.reply_text(t('ad_add_error_format'))
            return
        await update.message.reply_text(t('ad_add_failed', error=str(e)))
    except Exception as e:
        await update.message.reply_text(t('ad_add_failed', error=str(e)))

async def cmd_all_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看所有广告"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text(t('owner_only'))
        return
    
    ads = db.get_all_advertisements()
    await update.message.reply_text(render_ad_list(ads, t))

async def cmd_del_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    删除广告
    格式: /del_ad <ID>
    """
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text(t('owner_only'))
        return
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text(t('ad_delete_usage'))
        return
    
    try:
        ad_id = parse_delete_ad_args(context.args)
        db.delete_advertisement(ad_id)
        await update.message.reply_text(t('ad_delete_success', id=ad_id))
        await cmd_all_ad(update, context)
    except CommandInputError as e:
        if e.code == "usage":
            await update.message.reply_text(t('ad_delete_usage'))
            return
        await update.message.reply_text(t('ad_delete_failed', error=str(e)))
    except Exception as e:
        await update.message.reply_text(t('ad_delete_failed', error=str(e)))

# ============ 其他管理命令 ============

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    await update.message.reply_text(get_start_message())

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /admin 命令"""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == "private":
        if not is_owner(user_id):
            await update.message.reply_text(t('no_permission'))
            return
    else:
        if not await is_chat_admin(chat_id, user_id, context):
            await update.message.reply_text(t('admin_only'))
            return

    msg = (
        "⚙️ 广告限额管理\n\n"
        f"识别模式：{'AI' if detection_mode() == 'ai' else '关键词（不调用 AI）'}\n"
        f"本群广告词：{len(db.list_ad_words(chat_id))} 个\n"
        f"本群屏蔽词：{len(db.list_blocked_words(chat_id))} 个\n"
        f"每人每 {config.get('policy.ad_interval_minutes', 60)} 分钟允许 1 条广告\n"
        f"超额后禁言：{config.get('policy.temporary_mute_minutes', 60)} 分钟\n"
        f"相同广告重复：禁言 {config.get('policy.duplicate_ad_mute_hours', 12)} 小时，不计永久禁言次数\n"
        f"滚动 {config.get('policy.violation_window_days', 7)} 天内达到 "
        f"{config.get('policy.permanent_mute_after', 3)} 次：永久禁言\n\n"
        "管理员命令：\n"
        "• /ad_status — 回复成员消息查看状态\n"
        "• /reset_ad_history — 回复成员消息清除记录并解除禁言\n"
        "• /mute — 回复成员消息永久禁言\n"
        "• /unban — 回复成员消息解除禁言并清除记录\n"
        "• /add_adword <词或短语> — 添加本群广告词\n"
        "• /del_adword <词或短语> — 解除本群广告词\n"
        "• /adwords — 查看本群广告词\n"
        "• /add_blockword <词或短语> — 添加本群屏蔽词\n"
        "• /del_blockword <词或短语> — 解除本群屏蔽词\n"
        "• /blockwords — 查看本群屏蔽词"
    )
    
    await update.message.reply_text(msg)

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看运行统计（仅超级管理员）"""
    user_id = update.effective_user.id
    
    if not is_owner(user_id):
        await update.message.reply_text(t('owner_only'))
        return
    
    await update.message.reply_text(render_stats_panel(stats.get_stats(), t))


async def handle_appeal_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """被永久禁言者本人提交申诉，由群管理员决定是否解除。"""
    query = update.callback_query
    await query.answer()
    try:
        target_user_id = int(query.data.removeprefix("appeal_"))
    except (TypeError, ValueError):
        return

    if query.from_user.id != target_user_id:
        await query.answer("只有被禁言者本人可以发起申诉", show_alert=True)
        return

    chat_id = query.message.chat_id
    safe_name = html.escape(query.from_user.full_name or str(target_user_id))
    await context.bot.send_message(
        chat_id,
        (
            f'📨 <a href="tg://user?id={target_user_id}">{safe_name}</a> 已提交解除禁言申诉。\n'
            "请群管理员审核；同意时点击下方按钮。"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ 同意申诉并解除禁言", callback_data=f"unban_{target_user_id}")
        ]]),
    )
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ 申诉已提交", callback_data=f"appealed_{target_user_id}")
            ]])
        )
    except Exception as exc:
        logger.warning("Failed to mark appeal button submitted: %s", exc)


async def handle_appealed_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("申诉已经提交，请等待管理员处理", show_alert=True)

async def handle_unban_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理解除禁言按钮点击"""
    from telegram import ChatPermissions
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    
    if not await is_chat_admin(chat_id, user_id, context):
        await query.answer(t('admin_only'), show_alert=True)
        return
    
    target_user_id = parse_unban_callback_data(query.data)
    if target_user_id is None:
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        db.clear_ad_policy_history(target_user_id, chat_id)
        
        # 删除封禁消息（Go 版本的功能）
        try:
            await query.message.delete()
        except Exception as e:
            logger.warning(f"删除封禁消息失败: {e}")
        
        # 发送解禁通知（Go 版本的功能）
        admin_name = query.from_user.first_name or "Admin"
        notice = t('unban_notice', admin=admin_name, user_id=target_user_id)
        await context.bot.send_message(chat_id, notice, parse_mode="Markdown")
        
        await query.answer(t('unban_success'), show_alert=False)
        
        logger.info(f"Unmuted user {target_user_id} in chat {chat_id} by admin {user_id} via button")
    except Exception as e:
        await query.answer(t('unban_failed', error=str(e)), show_alert=True)
        logger.error(f"Failed to unmute user {target_user_id}: {e}")


async def cmd_mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """群管理员手动永久禁言：回复成员消息或使用 /mute <用户ID>。"""
    chat_id = update.effective_chat.id
    if not await _require_group_admin(update, context):
        return
    try:
        target_user_id, target_user_name = resolve_unban_target(
            update.message.reply_to_message,
            context.args or [],
        )
    except CommandInputError:
        await update.message.reply_text("用法：回复成员消息发送 /mute，或使用 /mute <用户ID>")
        return

    if await is_chat_admin(chat_id, target_user_id, context):
        await update.message.reply_text("❌ 不能禁言群管理员")
        return

    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=target_user_id,
        permissions=no_send_permissions(),
        until_date=None,
    )
    target_user = getattr(update.message.reply_to_message, "from_user", None)
    if target_user is None:
        target_user = type("MuteTarget", (), {
            "id": target_user_id,
            "full_name": target_user_name or str(target_user_id),
        })()
    await send_permanent_mute_notice(context, chat_id, target_user, "群管理员手动禁言")
    logger.info(
        "Manual permanent mute: chat=%s target=%s admin=%s",
        chat_id,
        target_user_id,
        update.effective_user.id,
    )

async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /unban 命令"""
    from telegram import ChatPermissions
    
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if update.effective_chat.type == "private":
        await update.message.reply_text(t('group_only'))
        return
    
    if not await is_chat_admin(chat_id, user_id, context):
        await update.message.reply_text(t('admin_only'))
        return
    
    try:
        target_user_id, target_user_name = resolve_unban_target(
            update.message.reply_to_message,
            context.args or [],
        )
    except CommandInputError as e:
        if e.code == "invalid_id":
            await update.message.reply_text(t('unban_invalid_id'))
            return
        await update.message.reply_text(t('unban_usage'))
        return
    
    try:
        await context.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=target_user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False
            )
        )
        db.clear_ad_policy_history(target_user_id, chat_id)
        
        if target_user_name:
            await update.message.reply_text(t('unban_success_detail', name=target_user_name, user_id=target_user_id))
        else:
            await update.message.reply_text(t('unban_success_id', user_id=target_user_id))
        
        logger.info(f"Unmuted user {target_user_id} in chat {chat_id} by admin {user_id}")
    except Exception as e:
        await update.message.reply_text(t('unban_failed', error=str(e)))
        logger.error(f"Failed to unmute user {target_user_id}: {e}")


def _resolve_policy_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return resolve_unban_target(update.message.reply_to_message, context.args or [])


async def cmd_ad_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员查看某成员当前一小时额度和七天违规次数。"""
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text(t('group_only'))
        return
    if not await is_chat_admin(chat_id, update.effective_user.id, context):
        await update.message.reply_text(t('admin_only'))
        return
    try:
        target_user_id, target_name = _resolve_policy_target(update, context)
    except CommandInputError:
        await update.message.reply_text("请回复该成员的消息，或使用 /ad_status <用户ID>")
        return

    settings = policy_settings()
    status = db.get_ad_policy_status(
        target_user_id,
        chat_id,
        ad_interval=settings["ad_interval"],
        violation_window=settings["violation_window"],
    )
    last_allowed = status["last_allowed_at"]
    quota_text = "当前可发一条广告" if last_allowed is None else (
        "本时段额度已使用，上次允许时间：" + last_allowed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    )
    await update.message.reply_text(
        f"用户：{target_name or target_user_id}\n"
        f"{quota_text}\n"
        f"滚动窗口违规：{status['violation_count']} 次"
    )


async def cmd_reset_ad_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """清除成员广告额度/违规记录，并同步解除禁言。"""
    chat_id = update.effective_chat.id
    if update.effective_chat.type == "private":
        await update.message.reply_text(t('group_only'))
        return
    if not await is_chat_admin(chat_id, update.effective_user.id, context):
        await update.message.reply_text(t('admin_only'))
        return
    try:
        target_user_id, target_name = _resolve_policy_target(update, context)
    except CommandInputError:
        await update.message.reply_text("请回复该成员的消息，或使用 /reset_ad_history <用户ID>")
        return

    db.clear_ad_policy_history(target_user_id, chat_id)
    await context.bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=target_user_id,
        permissions=normal_member_permissions(),
    )
    await update.message.reply_text(f"✅ 已清除 {target_name or target_user_id} 的广告记录并解除禁言")


async def _require_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_chat.type == "private":
        await update.message.reply_text(t('group_only'))
        return False
    if not await is_chat_admin(update.effective_chat.id, update.effective_user.id, context):
        await update.message.reply_text(t('admin_only'))
        return False
    return True


async def cmd_add_blockword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加本群屏蔽词或短语。"""
    if not await _require_group_admin(update, context):
        return
    word = " ".join(context.args or []).strip()
    if not word:
        await update.message.reply_text("用法：/add_blockword <词或短语>")
        return
    try:
        inserted = db.add_blocked_word(
            update.effective_chat.id,
            word,
            update.effective_user.id,
        )
    except ValueError as exc:
        await update.message.reply_text(f"❌ 添加失败：{exc}")
        return
    if inserted:
        await update.message.reply_text(f"✅ 已添加本群屏蔽词：{word}")
    else:
        await update.message.reply_text(f"ℹ️ 本群已存在该屏蔽词：{word}")


async def cmd_del_blockword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解除本群屏蔽词。"""
    if not await _require_group_admin(update, context):
        return
    word = " ".join(context.args or []).strip()
    if not word:
        await update.message.reply_text("用法：/del_blockword <词或短语>")
        return
    if db.remove_blocked_word(update.effective_chat.id, word):
        await update.message.reply_text(f"✅ 已解除本群屏蔽词：{word}")
    else:
        await update.message.reply_text(f"ℹ️ 没有找到该屏蔽词：{word}")


async def cmd_blockwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看本群所有屏蔽词。"""
    if not await _require_group_admin(update, context):
        return
    words = db.list_blocked_words(update.effective_chat.id)
    if not words:
        await update.message.reply_text("本群暂未设置屏蔽词。")
        return
    lines = ["本群屏蔽词："] + [f"{index}. {word}" for index, word in enumerate(words, 1)]
    await update.message.reply_text("\n".join(lines))


async def cmd_add_adword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """添加本群广告词或短语。"""
    if not await _require_group_admin(update, context):
        return
    word = " ".join(context.args or []).strip()
    if not word:
        await update.message.reply_text("用法：/add_adword <词或短语>")
        return
    try:
        inserted = db.add_ad_word(
            update.effective_chat.id,
            word,
            update.effective_user.id,
        )
    except ValueError as exc:
        await update.message.reply_text(f"❌ 添加失败：{exc}")
        return
    if inserted:
        await update.message.reply_text(f"✅ 已添加本群广告词：{word}")
    else:
        await update.message.reply_text(f"ℹ️ 本群已存在该广告词：{word}")


async def cmd_del_adword(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """解除本群广告词。"""
    if not await _require_group_admin(update, context):
        return
    word = " ".join(context.args or []).strip()
    if not word:
        await update.message.reply_text("用法：/del_adword <词或短语>")
        return
    if db.remove_ad_word(update.effective_chat.id, word):
        await update.message.reply_text(f"✅ 已解除本群广告词：{word}")
    else:
        await update.message.reply_text(f"ℹ️ 没有找到该广告词：{word}")


async def cmd_adwords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看本群全部广告词。"""
    if not await _require_group_admin(update, context):
        return
    words = db.list_ad_words(update.effective_chat.id)
    if not words:
        await update.message.reply_text("本群暂未设置广告词。")
        return
    lines = ["本群广告词："] + [f"{index}. {word}" for index, word in enumerate(words, 1)]
    await update.message.reply_text("\n".join(lines))

# ============ 启动 ============

def validate_config():
    """验证必要的配置项"""
    errors = []
    
    # 检查 Telegram Token
    token = config.get("telegram.token")
    if not token or "replace-with" in str(token):
        errors.append("❌ telegram.token 未配置")
    
    mode = detection_mode()
    if mode not in {"keywords", "ai"}:
        errors.append("❌ detection.mode 只能是 keywords 或 ai")
    if mode == "ai":
        ai_model = config.get("ai_model", "openai")
        if ai_model == "openai":
            if not config.get("openai.api_key") or "replace-with" in str(config.get("openai.api_key")):
                errors.append("❌ openai.api_key 未配置")
        elif ai_model == "qwen":
            if not config.get("qwen.api_key") or "replace-with" in str(config.get("qwen.api_key")):
                errors.append("❌ qwen.api_key 未配置")
        elif ai_model == "deepseek":
            if not config.get("deepseek.api_key") or "replace-with" in str(config.get("deepseek.api_key")):
                errors.append("❌ deepseek.api_key 未配置")
        elif ai_model == "kimi":
            if not config.get("kimi.api_key") or "replace-with" in str(config.get("kimi.api_key")):
                errors.append("❌ kimi.api_key 未配置")
        else:
            errors.append(f"❌ 不支持的 AI 模型: {ai_model}")
    
    # 检查超级管理员
    owners = config.get("telegram.owners", [])
    if not owners:
        logger.warning("⚠️ telegram.owners 未配置；群管理命令正常，仅 /stats 等超级管理命令不可用")

    numeric_policy = {
        "policy.ad_interval_minutes": config.get("policy.ad_interval_minutes", 60),
        "policy.temporary_mute_minutes": config.get("policy.temporary_mute_minutes", 60),
        "policy.duplicate_ad_mute_hours": config.get("policy.duplicate_ad_mute_hours", 12),
        "policy.violation_window_days": config.get("policy.violation_window_days", 7),
        "policy.permanent_mute_after": config.get("policy.permanent_mute_after", 3),
    }
    for key, value in numeric_policy.items():
        try:
            if int(value) <= 0:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"❌ {key} 必须是正整数")

    if not config.get("telegram.allow_any_group", False) and not config.get("telegram.groups", []):
        errors.append("❌ telegram.groups 为空；请填写目标群组 ID，或显式启用 allow_any_group")
    if (
        not config.get("telegram.allow_any_group", False)
        and "-1001234567890" in {str(value) for value in config.get("telegram.groups", [])}
    ):
        errors.append("❌ telegram.groups 仍是示例 ID，请替换为真实群组 ID")
    
    if errors:
        logger.error("配置验证失败：")
        for error in errors:
            logger.error(error)
        logger.error("\n请检查 config.yml 配置文件")
        sys.exit(1)
    
    logger.info("✅ 配置验证通过")

def main():
    # 初始化语言设置
    language = config.get("language", "zh")
    set_locale(language)
    
    # 显示项目信息
    logger.info("=" * 60)
    logger.info(f"🤖 {PROJECT_INFO['name']} - 官方版本")
    logger.info(f"📦 项目地址: {PROJECT_INFO['repo']}")
    logger.info(f"👨‍💻 开发者: {PROJECT_INFO['developer']}")
    logger.info(f"📢 官方频道: {PROJECT_INFO['channel']}")
    logger.info(f"💬 交流群组: {PROJECT_INFO['group']}")
    logger.info(f"🎯 演示 Bot: {PROJECT_INFO['demo_bot']}")
    logger.info("=" * 60)
    
    # 验证配置
    validate_config()
    
    token = config.get("telegram.token")
    
    global ai_client
    if detection_mode() == "ai":
        try:
            ai_client = create_configured_ai_client()
            logger.info(f"✅ AI 客户端初始化成功: {config.get('ai_model')}")
        except Exception as e:
            logger.error(f"❌ AI 客户端初始化失败: {e}")
            sys.exit(1)
    else:
        ai_client = None
        logger.info("✅ 关键词模式已启用，不调用 AI API")

    import os
    api_url = os.getenv("TELEGRAM_API_URL")
    
    builder = Application.builder().token(token)
    if api_url:
        builder = builder.base_url(f"{api_url}/bot")
        builder = builder.base_file_url(f"{api_url}/file/bot")
        logger.info(f"Using custom Telegram API: {api_url}")
    
    app = builder.build()

    # 注册处理器
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("mute", cmd_mute))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("ad_status", cmd_ad_status))
    app.add_handler(CommandHandler("reset_ad_history", cmd_reset_ad_history))
    app.add_handler(CommandHandler("add_blockword", cmd_add_blockword))
    app.add_handler(CommandHandler("del_blockword", cmd_del_blockword))
    app.add_handler(CommandHandler("blockwords", cmd_blockwords))
    app.add_handler(CommandHandler("add_adword", cmd_add_adword))
    app.add_handler(CommandHandler("del_adword", cmd_del_adword))
    app.add_handler(CommandHandler("adwords", cmd_adwords))
    app.add_handler(CommandHandler("stats", cmd_stats))

    # 未知命令也要进入审核，避免用 /x 前缀绕过词库。
    app.add_handler(MessageHandler(filters.COMMAND, handle_text))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & ~filters.COMMAND & ~filters.PHOTO, handle_text))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    app.add_handler(ChatMemberHandler(handle_bot_added_to_group, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(ChatMemberHandler(handle_new_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CallbackQueryHandler(handle_unban_button, pattern="^unban_"))
    app.add_handler(CallbackQueryHandler(handle_appeal_button, pattern="^appeal_"))
    app.add_handler(CallbackQueryHandler(handle_appealed_button, pattern="^appealed_"))

    logger.info("🚀 Bot 启动中...")
    logger.info(
        "📊 广告策略: 模式=%s | 每%s分钟1条 | 超额禁言%s分钟 | 相同广告禁言%s小时 | %s天内%s次永久禁言",
        detection_mode(),
        config.get('policy.ad_interval_minutes', 60),
        config.get('policy.temporary_mute_minutes', 60),
        config.get('policy.duplicate_ad_mute_hours', 12),
        config.get('policy.violation_window_days', 7),
        config.get('policy.permanent_mute_after', 3),
    )
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
