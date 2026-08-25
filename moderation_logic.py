from __future__ import annotations

from datetime import datetime


class RuntimeStats:
    """简单的运行时内存统计。"""

    def __init__(self, start_time: datetime | None = None):
        self.checks_total = 0
        self.checks_passed = 0
        self.checks_banned = 0
        self.checks_failed = 0
        self.start_time = start_time or datetime.now()

    def record_check(self, result: str):
        self.checks_total += 1
        if result == "passed":
            self.checks_passed += 1
        elif result == "banned":
            self.checks_banned += 1
        elif result == "failed":
            self.checks_failed += 1

    def get_stats(self, now: datetime | None = None) -> dict:
        uptime = (now or datetime.now()) - self.start_time
        return {
            "uptime_seconds": int(uptime.total_seconds()),
            "checks_total": self.checks_total,
            "checks_passed": self.checks_passed,
            "checks_banned": self.checks_banned,
            "checks_failed": self.checks_failed,
        }


def should_check_user(user, strategy: dict, *, now: datetime | None = None) -> bool:
    """根据策略判断用户是否需要检测。"""
    now = now or datetime.now()

    max_verification = strategy.get("verification_times", 0)
    if max_verification > 0 and user.verification_times >= max_verification:
        return False

    max_days = strategy.get("joined_days", 3)
    joined_days = (now - user.join_time).days
    if joined_days > max_days:
        return False

    check_message_count = strategy.get("check_message_count", True)
    if check_message_count:
        min_messages = strategy.get("min_messages", 3)
        if user.message_count > min_messages:
            return False

    return True
