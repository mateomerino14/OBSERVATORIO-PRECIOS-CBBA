from datetime import date

from observatory.months import next_month, previous_month, shift_months


def test_next_month_crosses_the_year() -> None:
    assert next_month(date(2025, 12, 1)) == date(2026, 1, 1)
    assert next_month(date(2025, 4, 1)) == date(2025, 5, 1)


def test_previous_month_crosses_the_year() -> None:
    assert previous_month(date(2025, 1, 1)) == date(2024, 12, 1)
    assert previous_month(date(2025, 6, 1)) == date(2025, 5, 1)


def test_shift_months_moves_whole_years() -> None:
    assert shift_months(date(2025, 3, 1), -12) == date(2024, 3, 1)
    assert shift_months(date(2025, 11, 1), 14) == date(2027, 1, 1)
