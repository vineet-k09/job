import datetime
import logging
from zoneinfo import ZoneInfo

logger = logging.getLogger("recruiting-platform.utils.timezone")


def guess_timezone(location: str | None, domain: str | None) -> str:
    """
    Guesses the timezone based on a job's location or company's domain.
    Defaults to 'Asia/Kolkata' (IST).
    """
    # Standard fallback is India Standard Time
    tz_name = "Asia/Kolkata"

    if location:
        loc_lower = location.lower()
        if any(
            kw in loc_lower
            for kw in [
                "india",
                "in",
                "bengaluru",
                "bangalore",
                "mumbai",
                "delhi",
                "noida",
                "hyderabad",
                "pune",
                "gurgaon",
                "gurugram",
            ]
        ):
            tz_name = "Asia/Kolkata"
        elif any(kw in loc_lower for kw in ["uk", "london", "united kingdom", "gb", "great britain", "england"]):
            tz_name = "Europe/London"
        elif any(
            kw in loc_lower
            for kw in [
                "eu",
                "europe",
                "germany",
                "berlin",
                "france",
                "paris",
                "amsterdam",
                "netherlands",
                "spain",
                "madrid",
                "italy",
                "rome",
                "ireland",
                "dublin",
            ]
        ):
            tz_name = "Europe/Berlin"
        elif any(
            kw in loc_lower
            for kw in [
                "us",
                "usa",
                "united states",
                "america",
                "san francisco",
                "new york",
                "boston",
                "seattle",
                "austin",
                "california",
                "ny",
                "ca",
                "wa",
                "tx",
                "ma",
                "chicago",
                "il",
            ]
        ):
            # Specific check for US West Coast
            if any(
                pt_kw in loc_lower
                for pt_kw in [
                    "san francisco",
                    "ca",
                    "california",
                    "seattle",
                    "wa",
                    "los angeles",
                    "silicon valley",
                    "portland",
                    "oregon",
                ]
            ):
                tz_name = "America/Los_Angeles"
            elif any(
                ct_kw in loc_lower
                for ct_kw in [
                    "chicago",
                    "il",
                    "illinois",
                    "texas",
                    "tx",
                    "austin",
                    "dallas",
                    "houston",
                    "denver",
                    "co",
                    "colorado",
                ]
            ):
                tz_name = "America/Chicago"
            else:
                # Default US to Eastern Time
                tz_name = "America/New_York"
        elif "singapore" in loc_lower:
            tz_name = "Asia/Singapore"
        elif "australia" in loc_lower or "sydney" in loc_lower or "melbourne" in loc_lower:
            tz_name = "Australia/Sydney"
        elif "canada" in loc_lower or "toronto" in loc_lower or "vancouver" in loc_lower:
            if "vancouver" in loc_lower:
                tz_name = "America/Vancouver"
            else:
                tz_name = "America/Toronto"

    elif domain:
        dom_lower = domain.lower()
        if dom_lower.endswith(".in"):
            tz_name = "Asia/Kolkata"
        elif dom_lower.endswith(".uk") or dom_lower.endswith(".co.uk"):
            tz_name = "Europe/London"
        elif any(dom_lower.endswith(tld) for tld in [".de", ".fr", ".nl", ".eu", ".it", ".es", ".ie"]):
            tz_name = "Europe/Berlin"
        elif dom_lower.endswith(".sg"):
            tz_name = "Asia/Singapore"
        elif dom_lower.endswith(".au"):
            tz_name = "Australia/Sydney"
        elif dom_lower.endswith(".ca"):
            tz_name = "America/Toronto"

    return tz_name


def calculate_scheduled_time(timezone_name: str, base_time: datetime.datetime | None = None) -> datetime.datetime:
    """
    Calculates the next occurrence of 8:45 AM in the target timezone.
    Returns it as a timezone-naive datetime in UTC.
    """
    if base_time is None:
        base_time = datetime.datetime.now(datetime.UTC)
    else:
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=datetime.UTC)

    try:
        tz = ZoneInfo(timezone_name)
    except Exception as e:
        logger.warning(f"Invalid timezone '{timezone_name}', falling back to Asia/Kolkata. Error: {e}")
        tz = ZoneInfo("Asia/Kolkata")

    # Convert base_time to target timezone
    local_time = base_time.astimezone(tz)

    # Set target to 8:45 AM on the same local day
    target_time = local_time.replace(hour=8, minute=45, second=0, microsecond=0)

    # If 8:45 AM is less than 5 hours in the future (or has already passed), schedule for tomorrow
    if target_time < local_time + datetime.timedelta(hours=5):
        target_time += datetime.timedelta(days=1)

    # Convert back to UTC and strip tzinfo to match the database's naive datetime representation
    utc_time = target_time.astimezone(datetime.UTC)
    return utc_time.replace(tzinfo=None)
