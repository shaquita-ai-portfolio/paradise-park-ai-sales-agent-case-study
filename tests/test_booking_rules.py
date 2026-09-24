from datetime import date

import pytest

from paradise_park_sales_agent.booking_rules import (
    service_dates,
    validate_service_schedule,
    week_of_month,
)


def test_week_of_month() -> None:
    assert week_of_month(date(2026, 9, 8)) == 2
    assert week_of_month(date(2026, 9, 22)) == 4


def test_valid_single_day_retreat() -> None:
    dates = validate_service_schedule(
        date(2026, 9, 8),
        1,
    )

    assert dates == (date(2026, 9, 8),)


def test_valid_multiday_retreat() -> None:
    dates = validate_service_schedule(
        date(2026, 9, 10),
        4,
    )

    assert dates == (
        date(2026, 9, 10),
        date(2026, 9, 11),
        date(2026, 9, 12),
        date(2026, 9, 13),
    )


def test_rejects_first_week() -> None:
    with pytest.raises(
        ValueError,
        match="second or fourth week",
    ):
        validate_service_schedule(
            date(2026, 9, 3),
            1,
        )


def test_rejects_monday_or_wednesday() -> None:
    with pytest.raises(
        ValueError,
        match="Available service days",
    ):
        validate_service_schedule(
            date(2026, 9, 9),
            1,
        )


def test_rejects_invalid_multiday_schedule() -> None:
    with pytest.raises(
        ValueError,
        match="Available service days",
    ):
        validate_service_schedule(
            date(2026, 9, 8),
            2,
        )


def test_duration_is_limited_to_four_days() -> None:
    with pytest.raises(
        ValueError,
        match="between 1 and 4",
    ):
        service_dates(
            date(2026, 9, 10),
            5,
        )


def test_thanksgiving_week_is_blocked() -> None:
    with pytest.raises(ValueError, match="Thanksgiving"):
        validate_service_schedule(date(2026, 11, 26), 1)


def test_christmas_observance_is_blocked() -> None:
    with pytest.raises(ValueError, match="Christmas"):
        validate_service_schedule(date(2026, 12, 24), 1)


def test_new_year_observance_is_blocked() -> None:
    with pytest.raises(ValueError, match="New Year"):
        validate_service_schedule(date(2027, 1, 1), 1)

        
