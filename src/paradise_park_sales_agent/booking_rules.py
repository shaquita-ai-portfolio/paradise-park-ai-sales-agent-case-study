from __future__ import annotations

from datetime import date, timedelta


ALLOWED_MONTH_WEEKS = frozenset({2, 4})
ALLOWED_WEEKDAYS = frozenset({1, 3, 4, 5, 6})

ALLOWED_WEEKDAY_NAMES = (
    "Tuesday, Thursday, Friday, Saturday or Sunday"
)


def week_of_month(value: date) -> int:
    """Return the week bucket based on the day of the month."""

    return ((value.day - 1) // 7) + 1


def service_dates(
    start_date: date,
    duration_days: int,
) -> tuple[date, ...]:
    """Return the consecutive dates in the retreat."""

    if duration_days < 1 or duration_days > 4:
        raise ValueError(
            "Retreat duration must be between 1 and 4 days."
        )

    return tuple(
        start_date + timedelta(days=offset)
        for offset in range(duration_days)
    )


def thanksgiving_blackout(year: int) -> tuple[date, date]:
    """Return Monday through Sunday of US Thanksgiving week."""

    november_first = date(year, 11, 1)
    days_until_thursday = (3 - november_first.weekday()) % 7
    first_thursday = november_first + timedelta(days=days_until_thursday)
    thanksgiving = first_thursday + timedelta(weeks=3)
    monday = thanksgiving - timedelta(days=thanksgiving.weekday())
    return monday, monday + timedelta(days=6)


def holiday_blackout_name(value: date) -> str | None:
    """Identify approved annual holiday booking blackouts."""

    thanksgiving_start, thanksgiving_end = thanksgiving_blackout(value.year)
    if thanksgiving_start <= value <= thanksgiving_end:
        return "Thanksgiving"
    if value.month == 12 and 22 <= value.day <= 28:
        return "Christmas"
    if (value.month == 12 and value.day >= 29) or (
        value.month == 1 and value.day <= 7
    ):
        return "New Year"
    return None


def validate_service_schedule(
    start_date: date,
    duration_days: int,
) -> tuple[date, ...]:
    """Validate every requested Paradise Park service date."""

    dates = service_dates(start_date, duration_days)

    holiday_dates = [
        (value, holiday_blackout_name(value))
        for value in dates
        if holiday_blackout_name(value)
    ]
    if holiday_dates:
        formatted = ", ".join(
            f"{value.isoformat()} ({name})" for value, name in holiday_dates
        )
        raise ValueError(
            "Paradise Park experiences are unavailable during our holiday "
            f"observance periods. Please choose another date. Date(s): {formatted}."
        )

    invalid_weeks = [
        value
        for value in dates
        if week_of_month(value) not in ALLOWED_MONTH_WEEKS
    ]

    if invalid_weeks:
        formatted = ", ".join(
            value.isoformat() for value in invalid_weeks
        )
        raise ValueError(
            "Paradise Park experiences are available only during "
            "the second or fourth week of each month. "
            f"Invalid date(s): {formatted}."
        )

    invalid_weekdays = [
        value
        for value in dates
        if value.weekday() not in ALLOWED_WEEKDAYS
    ]

    if invalid_weekdays:
        formatted = ", ".join(
            value.isoformat() for value in invalid_weekdays
        )
        raise ValueError(
            f"Available service days are {ALLOWED_WEEKDAY_NAMES}. "
            f"Invalid date(s): {formatted}."
        )

    return dates
