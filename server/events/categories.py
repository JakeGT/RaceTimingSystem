# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Age and category calculation. Pure functions so the results engine can reuse them."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date


def age_on(date_of_birth: date, on: date) -> int:
    """Completed years on a given date (a birthday on that date counts)."""
    had_birthday = (on.month, on.day) >= (date_of_birth.month, date_of_birth.day)
    return on.year - date_of_birth.year - (0 if had_birthday else 1)


@dataclass(frozen=True)
class Band:
    """One category rule, detached from the ORM."""

    code: str
    gender: str  # "" matches any gender
    min_age: int | None
    max_age: int | None

    def matches(self, gender: str, age: int | None) -> bool:
        if self.gender and self.gender != gender:
            return False
        if self.min_age is None and self.max_age is None:
            return True
        if age is None:
            return False
        if self.min_age is not None and age < self.min_age:
            return False
        return self.max_age is None or age <= self.max_age


def pick_category(bands: Iterable[Band], gender: str, age: int | None) -> Band | None:
    """The first band (in the scheme's order) that matches, or None."""
    return next((band for band in bands if band.matches(gender, age)), None)
