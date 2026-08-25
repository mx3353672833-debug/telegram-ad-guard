from __future__ import annotations


def render_stats_panel(stats_snapshot: dict, translator) -> str:
    uptime_hours = stats_snapshot["uptime_seconds"] // 3600
    uptime_mins = (stats_snapshot["uptime_seconds"] % 3600) // 60

    message = translator(
        "stats_panel",
        hours=uptime_hours,
        minutes=uptime_mins,
        total=stats_snapshot["checks_total"],
        passed=stats_snapshot["checks_passed"],
        banned=stats_snapshot["checks_banned"],
        failed=stats_snapshot["checks_failed"],
    )

    if stats_snapshot["checks_total"] > 0:
        ban_rate = (stats_snapshot["checks_banned"] / stats_snapshot["checks_total"]) * 100
        message += translator("stats_ban_rate", rate=f"{ban_rate:.1f}")

    return message


def render_ad_list(ads, translator) -> str:
    if not ads:
        return translator("ad_list_empty")

    message = translator("ad_list_header")
    for ad in ads:
        validity_str = ad.validity_period.strftime("%Y-%m-%d %H:%M") if ad.validity_period else translator("validity_permanent")
        created_str = ad.created_at.strftime("%Y-%m-%d %H:%M") if ad.created_at else translator("validity_unknown")
        message += translator(
            "ad_list_item",
            id=ad.id,
            title=ad.title,
            url=ad.url,
            sort=ad.sort,
            validity=validity_str,
            created=created_str,
        )

    return message
