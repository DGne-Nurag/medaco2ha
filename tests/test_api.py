"""Tests for parsing portal responses (structure copied from a real session)."""

from datetime import datetime, timezone

from custom_components.medaco import api

TREE = [
    {
        "name": "my metering points",
        "type": "root",
        "childs": [
            {
                "type": "mp",
                "id": "111",
                "name": "DE0001234 DE0001234",
                "commodity": "S",
                "childs": [
                    {
                        "type": "line",
                        "id": "201",
                        "name": "iMS - 1-1:1.29.0",
                        "details": {"unit": "kWh", "measured quantity": "OBIS 1-1:1.29.0 (kWh)"},
                    },
                    {
                        "type": "line",
                        "id": "202",
                        "name": "iMS - 1-1:2.29.0",
                        "details": {"unit": "kWh", "measured quantity": "OBIS 1-1:2.29.0 (kWh)"},
                    },
                ],
            }
        ],
    }
]


def test_parse_metering_points():
    [point] = api.parse_metering_points(TREE)
    assert point.id == "111"
    assert point.name == "DE0001234"
    assert [(l.id, l.obis) for l in point.lines] == [
        ("201", "1-1:1.29.0"),
        ("202", "1-1:2.29.0"),
    ]


def test_parse_series_uses_interval_start():
    data = {
        "timestamps": ["2026-07-31T22:15:00+00:00", "2026-07-31T22:30:00+00:00"],
        "timestampsLeft": ["2026-07-31T22:00:00+00:00", "2026-07-31T22:15:00+00:00"],
        "values": [0.259, None],
        "states": ["W", "E"],
        "unit": "kWh",
    }
    assert api.parse_series(data) == [
        api.Interval(datetime(2026, 7, 31, 22, 0, tzinfo=timezone.utc), 0.259)
    ]


def test_format_portal_time_matches_browser():
    moment = datetime(2026, 7, 31, 22, 0, tzinfo=timezone.utc)
    assert api.format_portal_time(moment) == "2026-8-1T00:00:00+02:00"
    winter = datetime(2026, 12, 1, 12, 5, tzinfo=timezone.utc)
    assert api.format_portal_time(winter) == "2026-12-1T13:05:00+01:00"


def test_login_form_csrf_regex():
    html = '<input type="hidden" name="_csrf_token" value="abc.def-_1" />'
    assert api._CSRF_RE.search(html).group(1) == "abc.def-_1"
