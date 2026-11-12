# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Review services: every change is audited and rebuilds results (timing/review.py)."""

from datetime import timedelta

import pytest

from accounts.models import User
from events.models import Entry, Event, Race, Split, TimingPoint, Wave
from results.models import RaceResults, Result
from results.services import rebuild_event, rebuild_race
from timing import review
from timing.fusion import fuse_pending
from timing.models import Adjustment, Read
from timing.review import Actor, ReviewError
from timing.tests.conftest import GUN, MakeObservation

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("finish", "started")]
Action = Adjustment.Action


def result(entry: Entry) -> Result:
    return Result.objects.get(entry=entry)


@pytest.fixture
def unreadable(event: Event, entries: dict[str, Entry], observe: MakeObservation) -> Read:
    observe({}, 2400)
    fuse_pending(event)
    return Read.objects.get()


@pytest.fixture
def auto(event: Event, entries: dict[str, Entry], observe: MakeObservation) -> Read:
    observe({"101": 0.95}, 2400)
    fuse_pending(event)
    rebuild_event(event)
    return Read.objects.get()


def test_assign_bib_to_unreadable(
    unreadable: Read, entries: dict[str, Entry], referee: Actor
) -> None:
    review.assign_bib(unreadable, "102", referee)
    unreadable.refresh_from_db()
    assert (unreadable.bib, unreadable.state, unreadable.review_reason) == (
        "102",
        Read.State.CONFIRMED,
        "",
    )
    log = Adjustment.objects.get()
    assert (log.action, log.actor_label, log.read) == (
        Action.READ_BIB_CHANGED,
        "Chief timekeeper",
        unreadable,
    )
    assert (log.before["bib"], log.after["bib"]) == ("", "102")
    assert result(entries["102"]).gun_time == timedelta(minutes=40)


def test_assign_unentered_bib_is_refused(unreadable: Read, referee: Actor) -> None:
    with pytest.raises(ReviewError, match="999"):
        review.assign_bib(unreadable, "999", referee)
    assert not Adjustment.objects.exists()


def test_confirm(auto: Read, referee: Actor) -> None:
    review.confirm_read(auto, referee, "checked the photo")
    auto.refresh_from_db()
    assert auto.state == Read.State.CONFIRMED
    log = Adjustment.objects.get()
    assert (log.action, log.before["state"], log.after["state"], log.reason) == (
        Action.READ_CONFIRMED,
        "auto",
        "confirmed",
        "checked the photo",
    )


def test_cannot_confirm_without_bib(unreadable: Read, referee: Actor) -> None:
    with pytest.raises(ReviewError):
        review.confirm_read(unreadable, referee)


def test_reject_removes_the_finish(auto: Read, entries: dict[str, Entry], referee: Actor) -> None:
    assert result(entries["101"]).outcome == Result.Outcome.FINISHED
    review.reject_read(auto, referee, "spectator wearing an old bib")
    assert result(entries["101"]).outcome == Result.Outcome.NO_READS
    assert Adjustment.objects.get().action == Action.READ_REJECTED


def test_adjust_time_needs_a_reason(auto: Read, referee: Actor) -> None:
    with pytest.raises(ReviewError):
        review.adjust_time(auto, auto.at + timedelta(seconds=1), referee, "  ")


def test_adjust_time(auto: Read, entries: dict[str, Entry], referee: Actor) -> None:
    review.adjust_time(auto, GUN + timedelta(minutes=39, seconds=58), referee, "photo finish")
    auto.refresh_from_db()
    assert auto.state == Read.State.CONFIRMED
    assert result(entries["101"]).gun_time == timedelta(minutes=39, seconds=58)
    log = Adjustment.objects.get()
    assert log.before["at"] != log.after["at"]


def test_manual_read(
    event: Event, finish_line: TimingPoint, entries: dict[str, Entry], referee: Actor
) -> None:
    read = review.add_manual_read(
        event, finish_line, "103", GUN + timedelta(minutes=41), referee, "stopwatch backup"
    )
    assert read.state == Read.State.MANUAL
    assert result(entries["103"]).gun_time == timedelta(minutes=41)
    log = Adjustment.objects.get()
    assert (log.action, log.before, log.after["bib"]) == (Action.READ_ADDED, {}, "103")


def test_manual_read_at_another_events_point(
    event: Event, entries: dict[str, Entry], referee: Actor
) -> None:
    other = Event.objects.create(
        organisation=event.organisation, name="Other", slug="other", start_date=event.start_date
    )
    point = TimingPoint.objects.create(event=other, name="Finish")
    with pytest.raises(ReviewError):
        review.add_manual_read(event, point, "101", GUN, referee, "typo")


def test_dsq_needs_a_reason(auto: Read, entries: dict[str, Entry], referee: Actor) -> None:
    with pytest.raises(ReviewError):
        review.set_entry_status(entries["101"], Entry.Status.DSQ, referee)
    review.set_entry_status(entries["101"], Entry.Status.DSQ, referee, "cut the course")
    assert result(entries["101"]).outcome == Result.Outcome.DSQ
    entries["101"].refresh_from_db()
    assert entries["101"].status_reason == "cut the course"
    log = Adjustment.objects.get()
    assert (log.entry, log.before["status"], log.after["status"]) == (
        entries["101"],
        "entered",
        "dsq",
    )


def test_start_wave(race: Race, wave: Wave, entries: dict[str, Entry], referee: Actor) -> None:
    unstarted = Wave.objects.create(race=race, name="Fun run")
    review.start_wave(unstarted, referee, at=GUN + timedelta(minutes=5))
    unstarted.refresh_from_db()
    assert unstarted.start_at == GUN + timedelta(minutes=5)
    assert Adjustment.objects.get().action == Action.WAVE_STARTED


def test_restarting_a_wave_needs_a_reason(
    wave: Wave, auto: Read, entries: dict[str, Entry], referee: Actor
) -> None:
    with pytest.raises(ReviewError):
        review.start_wave(wave, referee, at=GUN + timedelta(seconds=10))
    review.start_wave(wave, referee, at=GUN + timedelta(seconds=10), reason="horn was late")
    assert result(entries["101"]).gun_time == timedelta(minutes=39, seconds=50)


def test_actor_from_user(auto: Read) -> None:
    user = User.objects.create_user(email="ref@example.com", password="x")
    review.confirm_read(auto, Actor.of(user))
    log = Adjustment.objects.get()
    assert (log.actor, log.actor_label) == (user, "ref@example.com")


def test_failed_change_rolls_back(
    auto: Read, referee: Actor, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*args: object) -> None:
        raise RuntimeError("rebuild failed")

    monkeypatch.setattr(review, "rebuild_race", boom)
    with pytest.raises(RuntimeError):
        review.reject_read(auto, referee)
    auto.refresh_from_db()
    assert auto.state == Read.State.AUTO
    assert not Adjustment.objects.exists()


class TestRebuild:
    def test_positions_and_categories(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation, race: Race
    ) -> None:
        observe({"102": 0.95}, 2300)
        observe({"101": 0.95}, 2400)
        observe({"999": 0.95}, 2450)  # not entered: goes to review
        fuse_pending(event)
        rebuild_race(race)
        rows = {r.entry.bib: r for r in Result.objects.select_related("entry")}
        assert (rows["102"].overall_position, rows["102"].category) == (1, "MV40")
        assert (
            rows["101"].overall_position,
            rows["101"].category,
            rows["101"].gender_position,
        ) == (2, "SF", 1)
        assert rows["103"].outcome == Result.Outcome.NO_READS
        assert rows["101"].splits[0]["elapsed_us"] == 2400 * 1_000_000
        assert RaceResults.objects.get(race=race).warnings == []
        assert Read.objects.get(suggested_bib="999").state == Read.State.NEEDS_REVIEW

    def test_rebuild_is_repeatable(self, race: Race, auto: Read, entries: dict[str, Entry]) -> None:
        rebuild_race(race)
        rebuild_race(race)
        assert Result.objects.count() == len(entries)

    def test_entry_moving_race(
        self,
        event: Event,
        race: Race,
        auto: Read,
        entries: dict[str, Entry],
        finish_line: TimingPoint,
    ) -> None:
        rebuild_race(race)
        fun = Race.objects.create(event=event, name="5K", distance_m=5000)
        Wave.objects.create(race=fun, start_at=GUN)
        Split.objects.create(race=fun, timing_point=finish_line, kind=Split.Kind.FINISH)
        entry = entries["101"]
        entry.race, entry.wave = fun, None
        entry.save()
        rebuild_race(fun)
        assert result(entry).race == fun
        assert result(entry).outcome == Result.Outcome.FINISHED
