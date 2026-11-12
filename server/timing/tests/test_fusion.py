# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fusion v1: observations become reads (timing/fusion.py)."""

from datetime import timedelta

import pytest

from events.models import Entry, Event
from timing.fusion import AMBIGUITY_MARGIN, LOW_CONFIDENCE, MERGE_WINDOW, decide, fuse_pending
from timing.models import Device, Read
from timing.tests.conftest import MakeObservation, as_seconds

ENTERED = {"101", "102", "103", "108"}
State, Why = Read.State, Read.ReviewReason


class TestDecide:
    def test_confident_entered_bib_is_accepted(self) -> None:
        d = decide([{"bib": "101", "confidence": 0.95}], ENTERED)
        assert (d.bib, d.state, d.reason) == ("101", State.AUTO, "")

    def test_no_candidates(self) -> None:
        d = decide([], ENTERED)
        assert (d.bib, d.state, d.reason) == ("", State.NEEDS_REVIEW, Why.UNREADABLE)

    def test_snaps_to_entered_bib(self) -> None:
        # The OCR's favourite isn't entered, but its runner-up is: trust the entry list.
        d = decide([{"bib": "1O1", "confidence": 0.9}, {"bib": "101", "confidence": 0.8}], ENTERED)
        assert (d.bib, d.state) == ("101", State.AUTO)

    def test_bib_nobody_has(self) -> None:
        d = decide([{"bib": "999", "confidence": 0.97}], ENTERED)
        assert (d.bib, d.state, d.reason, d.suggested_bib) == (
            "",
            State.NEEDS_REVIEW,
            Why.NOT_ENTERED,
            "999",
        )

    def test_low_confidence_keeps_the_guess(self) -> None:
        d = decide([{"bib": "101", "confidence": LOW_CONFIDENCE - 0.01}], ENTERED)
        assert (d.bib, d.state, d.reason) == ("101", State.NEEDS_REVIEW, Why.LOW_CONFIDENCE)

    def test_two_close_bibs(self) -> None:
        close = 0.9 - AMBIGUITY_MARGIN + 0.01
        d = decide(
            [{"bib": "103", "confidence": 0.9}, {"bib": "108", "confidence": close}], ENTERED
        )
        assert (d.bib, d.state, d.reason) == ("103", State.NEEDS_REVIEW, Why.AMBIGUOUS)

    def test_order_of_candidates_does_not_matter(self) -> None:
        d = decide([{"bib": "108", "confidence": 0.3}, {"bib": "103", "confidence": 0.9}], ENTERED)
        assert (d.bib, d.state) == ("103", State.AUTO)


@pytest.mark.django_db
class TestFusePending:
    def test_one_observation_one_read(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        obs = observe({"101": 0.95}, 2400)
        assert fuse_pending(event) == {obs.timing_point_id}
        read = Read.objects.get()
        assert (read.bib, read.state, read.at) == ("101", State.AUTO, obs.captured_at)
        obs.refresh_from_db()
        assert obs.read == read

    def test_two_phones_one_read_at_the_median(
        self,
        event: Event,
        entries: dict[str, Entry],
        observe: MakeObservation,
        phones: tuple[Device, Device],
    ) -> None:
        observe({"101": 0.95}, 2400.0, phones[0])
        observe({"101": 0.9}, 2400.4, phones[1])
        fuse_pending(event)
        read = Read.objects.get()
        assert as_seconds(read.at) == pytest.approx(2400.2)
        assert read.observations.count() == 2
        assert read.confidence == 0.95

    def test_three_sightings_use_the_middle_one(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        for s in (2400.0, 2400.3, 2401.5):
            observe({"101": 0.95}, s)
        fuse_pending(event)
        assert as_seconds(Read.objects.get().at) == pytest.approx(2400.3)

    def test_outside_window_is_a_second_crossing(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.95}, 2400)
        observe({"101": 0.95}, 2400 + MERGE_WINDOW.total_seconds() + 1)
        fuse_pending(event)
        assert Read.objects.count() == 2

    def test_unknown_reads_never_merge(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({}, 2400)
        observe({}, 2400.1)
        fuse_pending(event)
        assert list(Read.objects.values_list("state", flat=True)) == [State.NEEDS_REVIEW] * 2

    def test_is_idempotent(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.95}, 2400)
        fuse_pending(event)
        assert fuse_pending(event) == set()
        assert Read.objects.count() == 1

    def test_late_upload_joins_existing_read(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.95}, 2400)
        fuse_pending(event)
        observe({"101": 0.9}, 2401)
        fuse_pending(event)
        read = Read.objects.get()
        assert as_seconds(read.at) == pytest.approx(2400.5)

    def test_sure_second_phone_clears_review(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.4}, 2400)
        fuse_pending(event)
        assert Read.objects.get().state == State.NEEDS_REVIEW
        observe({"101": 0.95}, 2400.2)
        fuse_pending(event)
        read = Read.objects.get()
        assert (read.state, read.review_reason) == (State.AUTO, "")

    @pytest.mark.parametrize("decided", [State.CONFIRMED, State.MANUAL, State.REJECTED])
    def test_people_win_over_late_uploads(
        self,
        event: Event,
        entries: dict[str, Entry],
        observe: MakeObservation,
        decided: Read.State,
    ) -> None:
        observe({"101": 0.95}, 2400)
        fuse_pending(event)
        Read.objects.update(state=decided)
        observe({"101": 0.95}, 2401)
        fuse_pending(event)
        read = Read.objects.get()
        assert (read.state, as_seconds(read.at)) == (decided, 2400)

    def test_other_events_are_untouched(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.95}, 2400)
        other = Event.objects.create(
            organisation=event.organisation, name="Other", slug="other", start_date=event.start_date
        )
        assert fuse_pending(other) == set()
        assert not Read.objects.exists()

    def test_window_is_inclusive(
        self, event: Event, entries: dict[str, Entry], observe: MakeObservation
    ) -> None:
        observe({"101": 0.95}, 2400)
        observe({"101": 0.95}, 2400 + MERGE_WINDOW / timedelta(seconds=1))
        fuse_pending(event)
        assert Read.objects.count() == 1
