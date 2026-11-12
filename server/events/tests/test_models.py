# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import date, timedelta

import pytest
from accounts.models import Organisation
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from events.models import (
    CategoryScheme,
    Entry,
    Event,
    Gender,
    Race,
    Split,
    TimingPoint,
    Wave,
)


def make_entry(race: Race, bib: str = "101", **kwargs: object) -> Entry:
    return Entry.objects.create(race=race, bib=bib, given_name="Sam", family_name="Lee", **kwargs)


@pytest.mark.django_db
class TestEvent:
    def test_rejects_unknown_timezone(self, event: Event) -> None:
        event.timezone = "Europe/Exeter"
        with pytest.raises(ValidationError, match="timezone"):
            event.full_clean()

    def test_end_date_cannot_precede_start(self, organisation: Organisation) -> None:
        with pytest.raises(IntegrityError):
            Event.objects.create(
                organisation=organisation,
                name="Backwards",
                slug="backwards",
                start_date=date(2026, 6, 14),
                end_date=date(2026, 6, 13),
            )


@pytest.mark.django_db
class TestEventScoping:
    """Child rows copy their event from the parent, so an event exports in one query each."""

    def test_children_take_event_from_race(
        self, event: Event, race: Race, wave: Wave, finish_line: TimingPoint
    ) -> None:
        split = Split.objects.create(race=race, timing_point=finish_line, kind=Split.Kind.FINISH)
        entry = make_entry(race)
        assert wave.event_id == split.event_id == entry.event_id == event.pk


@pytest.mark.django_db
class TestSplits:
    def test_timing_point_must_be_in_same_event(
        self, organisation: Organisation, race: Race
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=date(2026, 7, 1)
        )
        stray = TimingPoint.objects.create(event=other, name="Finish")
        split = Split(race=race, timing_point=stray, kind=Split.Kind.FINISH)
        with pytest.raises(ValidationError, match="same event"):
            split.full_clean()

    def test_distance_within_race(self, race: Race, finish_line: TimingPoint) -> None:
        split = Split(race=race, timing_point=finish_line, distance_m=race.distance_m + 1)
        with pytest.raises(ValidationError, match="past the race distance"):
            split.full_clean()

    def test_one_finish_per_race(self, race: Race, finish_line: TimingPoint) -> None:
        Split.objects.create(race=race, timing_point=finish_line, kind="finish", order=1)
        with pytest.raises(IntegrityError):
            Split.objects.create(race=race, timing_point=finish_line, kind="finish", order=2)

    def test_laps_reuse_a_timing_point(self, race: Race, finish_line: TimingPoint) -> None:
        Split.objects.create(
            race=race,
            timing_point=finish_line,
            name="Lap 1",
            distance_m=5_000,
            order=1,
            min_elapsed=timedelta(minutes=10),
        )
        Split.objects.create(
            race=race, timing_point=finish_line, kind="finish", distance_m=10_000, order=2
        )
        assert race.splits.filter(timing_point=finish_line).count() == 2

    def test_net_ranking_needs_start_split(self, race: Race) -> None:
        race.ranking_basis = Race.RankingBasis.NET
        with pytest.raises(ValidationError, match="start split"):
            race.full_clean()


@pytest.mark.django_db
class TestEntries:
    def test_bib_unique_across_races_in_event(self, event: Event, race: Race) -> None:
        five_k = Race.objects.create(event=event, name="5K", distance_m=5_000)
        make_entry(race, bib="42")
        with pytest.raises(IntegrityError):
            make_entry(five_k, bib="42")

    def test_same_bib_allowed_in_another_event(
        self, organisation: Organisation, race: Race
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=date(2026, 7, 1)
        )
        other_race = Race.objects.create(event=other, name="10K", distance_m=10_000)
        make_entry(race, bib="42")
        make_entry(other_race, bib="42")

    def test_wave_must_belong_to_race(self, event: Event, race: Race, wave: Wave) -> None:
        five_k = Race.objects.create(event=event, name="5K", distance_m=5_000)
        entry = Entry(race=five_k, wave=wave, bib="7", given_name="Kim")
        with pytest.raises(ValidationError, match="same race"):
            entry.full_clean()

    def test_wave_required_when_race_has_several(self, race: Race, wave: Wave) -> None:
        Wave.objects.create(race=race, name="Elite", order=1)
        entry = Entry(race=race, bib="7", given_name="Kim")
        with pytest.raises(ValidationError, match="several waves"):
            entry.full_clean()

    def test_hidden_name(self, race: Race) -> None:
        entry = make_entry(race, hide_name=True)
        assert entry.public_name == "Anonymous"
        assert entry.full_name == "Sam Lee"

    def test_category_from_date_of_birth_on_race_day(self, race: Race) -> None:
        # Race day is 2026-06-14: 40th birthday that day puts them in MV40.
        entry = make_entry(race, gender=Gender.MALE, date_of_birth=date(1986, 6, 14))
        category = entry.category()
        assert category is not None and category.code == "MV40"

    def test_category_with_year_end_basis(self, race: Race, scheme: CategoryScheme) -> None:
        scheme.age_basis = CategoryScheme.AgeBasis.YEAR_END
        scheme.save()
        # Turns 35 in November, after race day, but counts as 35 for the whole year.
        entry = make_entry(race, gender=Gender.FEMALE, date_of_birth=date(1991, 11, 2))
        category = entry.category()
        assert category is not None and category.code == "FV35"

    def test_category_falls_back_to_declared_age(self, race: Race) -> None:
        entry = make_entry(race, gender=Gender.FEMALE, declared_age=29)
        category = entry.category()
        assert category is not None and category.code == "SF"

    def test_no_category_without_scheme(self, event: Event) -> None:
        fun_run = Race.objects.create(event=event, name="Fun run", distance_m=2_000)
        assert make_entry(fun_run, bib="900").category() is None
