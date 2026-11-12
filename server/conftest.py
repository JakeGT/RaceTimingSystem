# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared fixtures: a small event with one race, one wave, a finish line and a scheme."""

from datetime import date

import pytest

from accounts.models import Organisation
from events.models import CategoryRule, CategoryScheme, Event, Gender, Race, TimingPoint, Wave


@pytest.fixture
def organisation(db: None) -> Organisation:
    return Organisation.objects.create(name="Exeter Harriers", slug="exeter-harriers")


@pytest.fixture
def event(organisation: Organisation) -> Event:
    return Event.objects.create(
        organisation=organisation,
        name="Riverside 10K",
        slug="riverside-10k",
        start_date=date(2026, 6, 14),
    )


@pytest.fixture
def scheme(organisation: Organisation) -> CategoryScheme:
    scheme = CategoryScheme.objects.create(organisation=organisation, name="Road running")
    bands = [
        ("SM", Gender.MALE, None, 39),
        ("MV40", Gender.MALE, 40, None),
        ("SF", Gender.FEMALE, None, 34),
        ("FV35", Gender.FEMALE, 35, None),
        ("OPEN", "", None, None),
    ]
    for order, (code, gender, lo, hi) in enumerate(bands):
        CategoryRule.objects.create(
            scheme=scheme, code=code, gender=gender, min_age=lo, max_age=hi, order=order
        )
    return scheme


@pytest.fixture
def race(event: Event, scheme: CategoryScheme) -> Race:
    return Race.objects.create(event=event, name="10K", distance_m=10_000, category_scheme=scheme)


@pytest.fixture
def wave(race: Race) -> Wave:
    return Wave.objects.create(race=race)


@pytest.fixture
def finish_line(event: Event) -> TimingPoint:
    return TimingPoint.objects.create(event=event, name="Finish")
