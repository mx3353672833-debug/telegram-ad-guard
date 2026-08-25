"""
数据库模块 - 支持广告管理功能
优化：使用线程安全的连接管理
"""
import sqlite3
import threading
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from contextlib import contextmanager

@dataclass
class UserInfo:
    user_id: int
    chat_id: int
    join_time: datetime
    message_count: int = 0
    check_count: int = 0
    verification_times: int = 0  # 新增：验证通过次数

@dataclass
class Advertisement:
    """广告按钮数据"""
    id: Optional[int] = None
    title: str = ""
    url: str = ""
    sort: int = 0
    validity_period: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass(frozen=True)
class AdPolicyDecision:
    """一次已确认广告在额度策略中的处理结果。"""

    action: str
    violation_count: int
    last_allowed_at: Optional[datetime]

    @property
    def is_allowed(self) -> bool:
        return self.action == "allow"

    @property
    def is_permanent(self) -> bool:
        return self.action == "permanent_mute"


def _get_default_db_path() -> Path:
    from config import config

    return Path(config.get("database.path", "data/bot.db"))

class Database:
    def __init__(self, db_path: Optional[str | Path] = None):
        if db_path is None:
            db_path = _get_default_db_path()
        else:
            db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self._blocked_words_cache: dict[int, list[tuple[str, str]]] = {}
        self._init_tables()

    def _get_conn(self):
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    @contextmanager
    def _get_cursor(self):
        """上下文管理器：自动提交和关闭"""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def _init_tables(self):
        # 临时连接用于初始化
        conn = sqlite3.connect(self.db_path)
        try:
            # 用户表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER,
                    chat_id INTEGER,
                    join_time TEXT,
                    message_count INTEGER DEFAULT 0,
                    check_count INTEGER DEFAULT 0,
                    verification_times INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, chat_id)
                )
            """)
            
            # Bot 自身通知中展示的广告按钮（保留上游兼容性）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS advertisements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    sort INTEGER DEFAULT 0,
                    validity_period TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # AI 已确认的群成员广告及违规记录。使用 Unix 时间戳，避免时区比较错误。
            conn.execute("""
                CREATE TABLE IF NOT EXISTS detected_ads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    detected_at INTEGER NOT NULL,
                    event_type TEXT NOT NULL CHECK(event_type IN ('allowed', 'violation')),
                    score INTEGER DEFAULT 0,
                    reason TEXT DEFAULT '',
                    UNIQUE(chat_id, message_id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_detected_ads_user_time
                ON detected_ads(chat_id, user_id, detected_at)
            """)

            # 每个群独立的手动屏蔽词。normalized_word 用于大小写和全半角兼容匹配。
            conn.execute("""
                CREATE TABLE IF NOT EXISTS blocked_words (
                    chat_id INTEGER NOT NULL,
                    word TEXT NOT NULL,
                    normalized_word TEXT NOT NULL,
                    created_by INTEGER NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (chat_id, normalized_word)
                )
            """)
            conn.commit()
        finally:
            conn.close()

    # ============ 用户管理 ============
    
    def get_user(self, user_id: int, chat_id: int) -> Optional[UserInfo]:
        with self._get_cursor() as cur:
            cur.execute(
                "SELECT * FROM users WHERE user_id=? AND chat_id=?",
                (user_id, chat_id)
            )
            row = cur.fetchone()
            if row:
                return UserInfo(
                    user_id=row[0],
                    chat_id=row[1],
                    join_time=datetime.fromisoformat(row[2]),
                    message_count=row[3],
                    check_count=row[4],
                    verification_times=row[5] if len(row) > 5 else 0
                )
        return None

    def save_user(self, user: UserInfo):
        with self._get_cursor() as cur:
            cur.execute("""
                INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)
            """, (user.user_id, user.chat_id, user.join_time.isoformat(),
                  user.message_count, user.check_count, user.verification_times))

    def increment_message_count(self, user_id: int, chat_id: int):
        with self._get_cursor() as cur:
            cur.execute(
                "UPDATE users SET message_count = message_count + 1 WHERE user_id=? AND chat_id=?",
                (user_id, chat_id)
            )

    def increment_check_count(self, user_id: int, chat_id: int):
        with self._get_cursor() as cur:
            cur.execute(
                "UPDATE users SET check_count = check_count + 1 WHERE user_id=? AND chat_id=?",
                (user_id, chat_id)
            )
    
    def increment_verification_times(self, user_id: int, chat_id: int):
        """增加验证通过次数"""
        with self._get_cursor() as cur:
            cur.execute(
                "UPDATE users SET verification_times = verification_times + 1 WHERE user_id=? AND chat_id=?",
                (user_id, chat_id)
            )

    # ============ 群成员广告额度与处罚 ============

    @staticmethod
    def _utc_timestamp(value: Optional[datetime] = None) -> int:
        value = value or datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp())

    def register_detected_ad(
        self,
        *,
        chat_id: int,
        user_id: int,
        message_id: int,
        ad_interval: timedelta,
        violation_window: timedelta,
        permanent_mute_after: int,
        score: int = 0,
        reason: str = "",
        now: Optional[datetime] = None,
    ) -> AdPolicyDecision:
        """原子登记广告并返回 allow/temporary_mute/permanent_mute。

        每个群、每个用户独立计算。SQLite 的 BEGIN IMMEDIATE 加进程内写锁，确保
        同时到达的两条广告最多只有一条能获得额度。
        """
        if ad_interval.total_seconds() <= 0:
            raise ValueError("ad_interval must be positive")
        if violation_window.total_seconds() <= 0:
            raise ValueError("violation_window must be positive")
        if permanent_mute_after <= 0:
            raise ValueError("permanent_mute_after must be positive")

        now_ts = self._utc_timestamp(now)
        quota_start = now_ts - int(ad_interval.total_seconds())
        violation_start = now_ts - int(violation_window.total_seconds())

        with self._write_lock:
            conn = self._get_conn()
            try:
                conn.execute("BEGIN IMMEDIATE")

                # 编辑消息或 Telegram 重投同一个 update 时保持幂等。
                existing = conn.execute(
                    """
                    SELECT event_type FROM detected_ads
                    WHERE chat_id=? AND message_id=?
                    """,
                    (chat_id, message_id),
                ).fetchone()
                if existing:
                    violations = conn.execute(
                        """
                        SELECT COUNT(*) FROM detected_ads
                        WHERE chat_id=? AND user_id=? AND event_type='violation'
                          AND detected_at>=?
                        """,
                        (chat_id, user_id, violation_start),
                    ).fetchone()[0]
                    last_row = conn.execute(
                        """
                        SELECT detected_at FROM detected_ads
                        WHERE chat_id=? AND user_id=? AND event_type='allowed'
                        ORDER BY detected_at DESC LIMIT 1
                        """,
                        (chat_id, user_id),
                    ).fetchone()
                    conn.commit()
                    action = "allow" if existing[0] == "allowed" else (
                        "permanent_mute" if violations >= permanent_mute_after else "temporary_mute"
                    )
                    return AdPolicyDecision(
                        action=action,
                        violation_count=violations,
                        last_allowed_at=(
                            datetime.fromtimestamp(last_row[0], timezone.utc) if last_row else None
                        ),
                    )

                last_row = conn.execute(
                    """
                    SELECT detected_at FROM detected_ads
                    WHERE chat_id=? AND user_id=? AND event_type='allowed'
                      AND detected_at>?
                    ORDER BY detected_at DESC LIMIT 1
                    """,
                    (chat_id, user_id, quota_start),
                ).fetchone()

                event_type = "violation" if last_row else "allowed"
                conn.execute(
                    """
                    INSERT INTO detected_ads
                        (chat_id, user_id, message_id, detected_at, event_type, score, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (chat_id, user_id, message_id, now_ts, event_type, score, reason),
                )

                violations = conn.execute(
                    """
                    SELECT COUNT(*) FROM detected_ads
                    WHERE chat_id=? AND user_id=? AND event_type='violation'
                      AND detected_at>=?
                    """,
                    (chat_id, user_id, violation_start),
                ).fetchone()[0]

                # 只保留足以计算策略和审计的记录，防止数据库无限增长。
                retention_start = now_ts - max(
                    int(violation_window.total_seconds()),
                    int(ad_interval.total_seconds()),
                ) * 2
                conn.execute("DELETE FROM detected_ads WHERE detected_at<?", (retention_start,))
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        if event_type == "allowed":
            return AdPolicyDecision("allow", violations, None)

        action = "permanent_mute" if violations >= permanent_mute_after else "temporary_mute"
        return AdPolicyDecision(
            action,
            violations,
            datetime.fromtimestamp(last_row[0], timezone.utc),
        )

    def get_ad_policy_status(
        self,
        user_id: int,
        chat_id: int,
        *,
        ad_interval: timedelta,
        violation_window: timedelta,
        now: Optional[datetime] = None,
    ) -> dict:
        now_ts = self._utc_timestamp(now)
        quota_start = now_ts - int(ad_interval.total_seconds())
        violation_start = now_ts - int(violation_window.total_seconds())
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT detected_at FROM detected_ads
                WHERE chat_id=? AND user_id=? AND event_type='allowed'
                  AND detected_at>?
                ORDER BY detected_at DESC LIMIT 1
                """,
                (chat_id, user_id, quota_start),
            )
            last_allowed = cur.fetchone()
            cur.execute(
                """
                SELECT COUNT(*) FROM detected_ads
                WHERE chat_id=? AND user_id=? AND event_type='violation'
                  AND detected_at>=?
                """,
                (chat_id, user_id, violation_start),
            )
            violations = cur.fetchone()[0]
        return {
            "last_allowed_at": (
                datetime.fromtimestamp(last_allowed[0], timezone.utc) if last_allowed else None
            ),
            "violation_count": violations,
        }

    def clear_ad_policy_history(self, user_id: int, chat_id: int) -> int:
        with self._write_lock, self._get_cursor() as cur:
            cur.execute(
                "DELETE FROM detected_ads WHERE chat_id=? AND user_id=?",
                (chat_id, user_id),
            )
            return cur.rowcount

    # ============ 手动屏蔽词 ============

    @staticmethod
    def normalize_blocked_text(value: str) -> str:
        return unicodedata.normalize("NFKC", str(value or "")).casefold().strip()

    def add_blocked_word(self, chat_id: int, word: str, created_by: int) -> bool:
        word = str(word or "").strip()
        normalized = self.normalize_blocked_text(word)
        if not normalized:
            raise ValueError("blocked word cannot be empty")
        if len(word) > 64:
            raise ValueError("blocked word is too long")

        with self._write_lock, self._get_cursor() as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO blocked_words
                    (chat_id, word, normalized_word, created_by)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, word, normalized, created_by),
            )
            inserted = cur.rowcount > 0
        self._blocked_words_cache.pop(chat_id, None)
        return inserted

    def remove_blocked_word(self, chat_id: int, word: str) -> bool:
        normalized = self.normalize_blocked_text(word)
        if not normalized:
            return False
        with self._write_lock, self._get_cursor() as cur:
            cur.execute(
                "DELETE FROM blocked_words WHERE chat_id=? AND normalized_word=?",
                (chat_id, normalized),
            )
            removed = cur.rowcount > 0
        self._blocked_words_cache.pop(chat_id, None)
        return removed

    def list_blocked_words(self, chat_id: int) -> List[str]:
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT word FROM blocked_words
                WHERE chat_id=? ORDER BY created_at, word
                """,
                (chat_id,),
            )
            return [row[0] for row in cur.fetchall()]

    def _blocked_word_pairs(self, chat_id: int) -> list[tuple[str, str]]:
        cached = self._blocked_words_cache.get(chat_id)
        if cached is not None:
            return cached
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT word, normalized_word FROM blocked_words
                WHERE chat_id=? ORDER BY LENGTH(normalized_word) DESC
                """,
                (chat_id,),
            )
            pairs = [(row[0], row[1]) for row in cur.fetchall()]
        self._blocked_words_cache[chat_id] = pairs
        return pairs

    def find_blocked_word(self, chat_id: int, text: str) -> Optional[str]:
        normalized_text = self.normalize_blocked_text(text)
        if not normalized_text:
            return None
        for original, normalized_word in self._blocked_word_pairs(chat_id):
            if normalized_word in normalized_text:
                return original
        return None

    # ============ 广告管理 ============
    
    def add_advertisement(self, ad: Advertisement) -> int:
        """添加广告"""
        with self._get_cursor() as cur:
            cur.execute("""
                INSERT INTO advertisements (title, url, sort, validity_period)
                VALUES (?, ?, ?, ?)
            """, (ad.title, ad.url, ad.sort, 
                  ad.validity_period.isoformat() if ad.validity_period else None))
            return cur.lastrowid
    
    def get_all_advertisements(self) -> List[Advertisement]:
        """获取所有广告"""
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT id, title, url, sort, validity_period, created_at
                FROM advertisements
                ORDER BY sort DESC, created_at DESC
            """)
            ads = []
            for row in cur.fetchall():
                ads.append(Advertisement(
                    id=row[0],
                    title=row[1],
                    url=row[2],
                    sort=row[3],
                    validity_period=datetime.fromisoformat(row[4]) if row[4] else None,
                    created_at=datetime.fromisoformat(row[5]) if row[5] else None
                ))
            return ads
    
    def get_valid_advertisements(self) -> List[Advertisement]:
        """获取有效的广告（未过期）"""
        now = datetime.now().isoformat()
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT id, title, url, sort, validity_period, created_at
                FROM advertisements
                WHERE validity_period IS NULL OR validity_period > ?
                ORDER BY sort DESC, created_at DESC
            """, (now,))
            ads = []
            for row in cur.fetchall():
                ads.append(Advertisement(
                    id=row[0],
                    title=row[1],
                    url=row[2],
                    sort=row[3],
                    validity_period=datetime.fromisoformat(row[4]) if row[4] else None,
                    created_at=datetime.fromisoformat(row[5]) if row[5] else None
                ))
            return ads
    
    def delete_advertisement(self, ad_id: int):
        """删除广告"""
        with self._get_cursor() as cur:
            cur.execute("DELETE FROM advertisements WHERE id=?", (ad_id,))

try:
    db = Database()
except (FileNotFoundError, ModuleNotFoundError):
    db = None
