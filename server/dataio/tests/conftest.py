# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fixtures: the shared 10K (see server/conftest.py) with a finish split and a referee."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from accounts.models import User
from events.models import Race, Split, TimingPoint, Wave
from timing.review import Actor

GUN = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)  # 10:00 in London (BST)

# The legacy system's example files, verbatim (git tag `legacy`, running/examples/).
LEGACY_PARTICIPANTS = b"""BibNumber,Firstname,Lastname,Gender,ClubName,TeamName,AgeCategory,Age
1,John,Doe,male,Club X,Team A,Adult,25
2,Jane,Smith,female,Club Y,Team B,Senior,30
3,Michael,Johnson,male,Club Z,Team C,Adult,35
4,Emily,Davis,female,Club X,Team A,Junior,22
5,Chris,Brown,male,Club Y,Team B,Senior,27
6,Sarah,Wilson,female,Club Z,Team C,Adult,28
"""
LEGACY_RESULTS = b"""race_number,total_time
1,00:25:36
2,00:30:45
3,00:28:12
4,00:30:55
5,00:31:45
6,00:33:45"""
# First lines of drogo-10-results-10nov2024.csv: capitalised genders, an extra column.
LEGACY_DROGO = b"""BibNumber,Firstname,Lastname,ClubName,OldCategory,Gender,AgeCategory,TeamName,Age
377,Ceri,Rees,Unlisted Club,MV50,Male,M50,None,50
129,Ed,Dickinson,Falmouth Running Club,Sen. Male,Male,MSEN,None,75
294,Eirin,Mc Daid,Ranelagh Harriers,Sen. Male,Male,MSEN,None,75
"""


@pytest.fixture(autouse=True)
def _media(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def finish(race: Race, finish_line: TimingPoint) -> Split:
    return Split.objects.create(race=race, timing_point=finish_line, kind=Split.Kind.FINISH)


@pytest.fixture
def started(wave: Wave) -> Wave:
    wave.start_at = GUN
    wave.save()
    return wave


@pytest.fixture
def referee(db: None) -> Actor:
    user = User.objects.create_user(email="ref@example.com", password="x")
    return Actor.of(user)
