from datetime import datetime

from command_views import render_ad_list, render_stats_panel
from database import Advertisement


TRANSLATIONS = {
    "stats_panel": "stats {hours}:{minutes} total={total} pass={passed} ban={banned} fail={failed}",
    "stats_ban_rate": " rate={rate}",
    "ad_list_empty": "empty",
    "ad_list_header": "header\n",
    "ad_list_item": "id={id}|title={title}|url={url}|sort={sort}|valid={validity}|created={created}\n",
    "validity_permanent": "永久",
    "validity_unknown": "未知",
}


def translator(key: str, **kwargs):
    return TRANSLATIONS[key].format(**kwargs)


def test_render_stats_panel_without_ban_rate_when_no_checks():
    message = render_stats_panel(
        {
            "uptime_seconds": 3599,
            "checks_total": 0,
            "checks_passed": 0,
            "checks_banned": 0,
            "checks_failed": 0,
        },
        translator,
    )

    assert message == "stats 0:59 total=0 pass=0 ban=0 fail=0"


def test_render_stats_panel_includes_ban_rate():
    message = render_stats_panel(
        {
            "uptime_seconds": 7200,
            "checks_total": 4,
            "checks_passed": 1,
            "checks_banned": 2,
            "checks_failed": 1,
        },
        translator,
    )

    assert message == "stats 2:0 total=4 pass=1 ban=2 fail=1 rate=50.0"


def test_render_ad_list_for_empty_ads():
    assert render_ad_list([], translator) == "empty"


def test_render_ad_list_renders_items():
    ads = [
        Advertisement(
            id=1,
            title="A",
            url="https://example.com/a",
            sort=10,
            validity_period=datetime(2026, 1, 2, 3, 4, 0),
            created_at=datetime(2026, 1, 1, 1, 2, 0),
        ),
        Advertisement(
            id=2,
            title="B",
            url="https://example.com/b",
            sort=5,
            validity_period=None,
            created_at=None,
        ),
    ]

    message = render_ad_list(ads, translator)

    assert message == (
        "header\n"
        "id=1|title=A|url=https://example.com/a|sort=10|valid=2026-01-02 03:04|created=2026-01-01 01:02\n"
        "id=2|title=B|url=https://example.com/b|sort=5|valid=永久|created=未知\n"
    )
