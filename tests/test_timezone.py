import datetime

from src.utils.timezone import calculate_scheduled_time, guess_timezone


def test_guess_timezone():
    # Test location matching
    assert guess_timezone("Bangalore, India", None) == "Asia/Kolkata"
    assert guess_timezone("London, UK", None) == "Europe/London"
    assert guess_timezone("Berlin, Germany", None) == "Europe/Berlin"
    assert guess_timezone("San Francisco, CA", None) == "America/Los_Angeles"
    assert guess_timezone("Seattle, WA", None) == "America/Los_Angeles"
    assert guess_timezone("Chicago, IL", None) == "America/Chicago"
    assert guess_timezone("New York, NY", None) == "America/New_York"
    assert guess_timezone("Singapore", None) == "Asia/Singapore"
    assert guess_timezone("Sydney, Australia", None) == "Australia/Sydney"
    assert guess_timezone("Toronto, Canada", None) == "America/Toronto"
    assert guess_timezone("Vancouver, Canada", None) == "America/Vancouver"

    # Test domain matching (when location is None)
    assert guess_timezone(None, "google.co.in") == "Asia/Kolkata"
    assert guess_timezone(None, "bbc.co.uk") == "Europe/London"
    assert guess_timezone(None, "sap.de") == "Europe/Berlin"
    assert guess_timezone(None, "singpost.sg") == "Asia/Singapore"
    assert guess_timezone(None, "atlassian.com.au") == "Australia/Sydney"
    assert guess_timezone(None, "shopify.ca") == "America/Toronto"

    # Fallback cases
    assert guess_timezone(None, None) == "Asia/Kolkata"
    assert guess_timezone("Remote", None) == "Asia/Kolkata"
    assert guess_timezone("Unknown Location", "unknown.com") == "Asia/Kolkata"


def test_calculate_scheduled_time():
    # Let's mock a base time: 2026-07-15 05:00:00 UTC
    # In Asia/Kolkata (UTC+5.5), local time is 2026-07-15 10:30:00 AM (which is past 8:45 AM).
    # So the next 8:45 AM local time should be tomorrow: 2026-07-16 08:45:00 local,
    # which is 2026-07-16 03:15:00 UTC.
    base_time_past = datetime.datetime(2026, 7, 15, 5, 0, 0, tzinfo=datetime.UTC)
    scheduled_past = calculate_scheduled_time("Asia/Kolkata", base_time_past)
    assert scheduled_past == datetime.datetime(2026, 7, 16, 3, 15, 0)

    # Let's mock a base time: 2026-07-15 01:00:00 UTC
    # In Asia/Kolkata (UTC+5.5), local time is 2026-07-15 06:30:00 AM (which is before 8:45 AM).
    # So the next 8:45 AM local time should be today: 2026-07-15 08:45:00 local,
    # which is 2026-07-15 03:15:00 UTC.
    base_time_before = datetime.datetime(2026, 7, 15, 1, 0, 0, tzinfo=datetime.UTC)
    scheduled_before = calculate_scheduled_time("Asia/Kolkata", base_time_before)
    assert scheduled_before == datetime.datetime(2026, 7, 15, 3, 15, 0)

    # Let's test with America/New_York (UTC-4 in July DST)
    # base_time: 2026-07-15 10:00:00 UTC -> Local time is 06:00:00 AM (before 8:45 AM).
    # Scheduled should be today at 08:45:00 AM local -> 12:45:00 UTC.
    base_time_ny = datetime.datetime(2026, 7, 15, 10, 0, 0, tzinfo=datetime.UTC)
    scheduled_ny = calculate_scheduled_time("America/New_York", base_time_ny)
    assert scheduled_ny == datetime.datetime(2026, 7, 15, 12, 45, 0)

    # base_time: 2026-07-15 14:00:00 UTC -> Local time is 10:00:00 AM (after 8:45 AM).
    # Scheduled should be tomorrow at 08:45:00 AM local -> 2026-07-16 12:45:00 UTC.
    base_time_ny_late = datetime.datetime(2026, 7, 15, 14, 0, 0, tzinfo=datetime.UTC)
    scheduled_ny_late = calculate_scheduled_time("America/New_York", base_time_ny_late)
    assert scheduled_ny_late == datetime.datetime(2026, 7, 16, 12, 45, 0)
