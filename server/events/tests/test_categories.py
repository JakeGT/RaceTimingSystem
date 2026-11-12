# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import date

import pytest

from events.categories import Band, age_on, pick_category


@pytest.mark.parametrize(
    ("born", "on", "expected"),
    [
        (date(1986, 6, 14), date(2026, 6, 14), 40),  # birthday on race day counts
        (date(1986, 6, 15), date(2026, 6, 14), 39),
        (date(2000, 2, 29), date(2021, 2, 28), 20),  # leap-day birthdays turn on 1 March
        (date(2000, 2, 29), date(2021, 3, 1), 21),
        (date(2000, 2, 29), date(2024, 2, 29), 24),
    ],
)
def test_age_on(born: date, on: date, expected: int) -> None:
    assert age_on(born, on) == expected


BANDS = [
    Band("SM", "male", None, 39),
    Band("MV40", "male", 40, None),
    Band("F", "female", None, None),
    Band("OPEN", "", None, None),
]


@pytest.mark.parametrize(
    ("gender", "age", "expected"),
    [
        ("male", 39, "SM"),
        ("male", 40, "MV40"),
        ("female", None, "F"),  # no age limits, so no age needed
        ("male", None, "OPEN"),  # age-limited bands can't match without an age
        ("non_binary", 30, "OPEN"),
    ],
)
def test_pick_category_first_match_wins(gender: str, age: int | None, expected: str) -> None:
    band = pick_category(BANDS, gender, age)
    assert band is not None and band.code == expected


def test_pick_category_none_when_nothing_matches() -> None:
    assert pick_category([Band("SM", "male", 18, 39)], "female", 25) is None
