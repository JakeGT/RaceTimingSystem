# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import UTC, datetime, timedelta

import pytest

from dataio.csvfiles import CsvError
from dataio.entries import import_entries
from dataio.results_csv import export_results
from dataio.tests.conftest import GUN, LEGACY_PARTICIPANTS, LEGACY_RESULTS
from dataio.times import import_times
from events.models import Entry, Event, Race, Split, TimingPoint, Wave
from results.models import Result
from timing.models import Adjustment, Read
from timing.review import Actor

pytestmark = pytest.mark.django_db


@pytest.fixture
def runners(event: Event, race: Race, finish: Split) -> None:
    assert import_entries(event, LEGACY_PARTICIPANTS).ok


def reads() -> list[tuple[str, datetime]]:
    return list(Read.objects.order_by("at").values_list("bib", "at"))


class TestLegacyFiles:
    def test_bib_detector_output(self, event: Event, runners: None, referee: Actor) -> None:
        start = GUN.timestamp()
        data = (
            "BibNumber,Result,TrackerID,filename\n"
            f"1,{start + 1536.25},4,4_101536\n"
            f"-1,{start + 1600},5,5_101640\n"
            f"2,{start + 1845},6,6_103045\n"
        ).encode()
        report = import_times(event, data, referee, filename="results.csv")
        assert (report.ok, report.created, report.skipped) == (True, 2, 1)
        assert reads() == [
            ("1", GUN + timedelta(seconds=1536.25)),
            ("2", GUN + timedelta(seconds=1845)),
        ]
        assert set(Read.objects.values_list("state", flat=True)) == {Read.State.MANUAL}
        log = Adjustment.objects.get(read__bib="1")
        assert (log.action, log.actor_label, log.reason) == (
            Adjustment.Action.READ_ADDED,
            "ref@example.com",
            "Imported from results.csv",
        )

    def test_race_number_total_time(
        self, event: Event, runners: None, started: Wave, referee: Actor
    ) -> None:
        report = import_times(event, LEGACY_RESULTS, referee, reason="Stopwatch backup")
        assert (report.ok, report.created) == (True, 6)
        assert reads()[0] == ("1", GUN + timedelta(minutes=25, seconds=36))
        assert Adjustment.objects.first().reason == "Imported from a file: Stopwatch backup"  # type: ignore[union-attr]
        # Results are rebuilt straight away and export in the legacy layout again.
        assert Result.objects.get(entry__bib="1").gun_time == timedelta(minutes=25, seconds=36)
        exported = export_results(event, legacy=True)
        assert sorted(exported.splitlines()) == sorted(LEGACY_RESULTS.decode().splitlines())

    def test_elapsed_needs_a_started_wave(
        self, event: Event, runners: None, referee: Actor
    ) -> None:
        report = import_times(event, LEGACY_RESULTS, referee)
        assert "hasn't started" in report.errors[0].message
        assert len(report.errors) == 6 and not Read.objects.exists()


class TestTimeColumns:
    def test_clock_time_is_in_the_event_timezone(
        self, event: Event, runners: None, referee: Actor
    ) -> None:
        report = import_times(event, b"bib,time\n1,10:25:36.5\n", referee)
        assert report.ok, report.errors
        assert reads() == [("1", datetime(2026, 6, 14, 9, 25, 36, 500000, tzinfo=UTC))]

    def test_iso_times(self, event: Event, runners: None, referee: Actor) -> None:
        data = b"bib,at\n1,2026-06-14T10:25:36\n2,2026-06-14 09:30:00Z\n"
        assert import_times(event, data, referee).ok
        assert reads() == [
            ("1", datetime(2026, 6, 14, 9, 25, 36, tzinfo=UTC)),
            ("2", datetime(2026, 6, 14, 9, 30, tzinfo=UTC)),
        ]

    @pytest.mark.parametrize(
        ("data", "match"),
        [
            (b"bib,name\n1,Ada\n", "exactly one time column"),
            (b"bib,unix,elapsed\n1,1,1\n", "Found: unix, elapsed"),
            (b"name,unix\nA,1\n", "no bib column"),
        ],
    )
    def test_columns(
        self, event: Event, runners: None, referee: Actor, data: bytes, match: str
    ) -> None:
        with pytest.raises(CsvError, match=match):
            import_times(event, data, referee)

    def test_bad_values(self, event: Event, runners: None, referee: Actor) -> None:
        report = import_times(event, b"bib,clock\n1,25:00:00\n99,10:00:00\n2,\n", referee)
        assert [e.message for e in report.errors] == [
            "'25:00:00' isn't a real time of day.",
            "Nobody in this event has bib '99'.",
            "Needs a bib and a time.",
        ]


class TestIdempotency:
    def test_importing_again_skips_existing(
        self, event: Event, runners: None, started: Wave, referee: Actor
    ) -> None:
        import_times(event, LEGACY_RESULTS, referee)
        report = import_times(event, LEGACY_RESULTS, referee)
        assert (report.created, report.skipped) == (0, 6)
        assert Read.objects.count() == 6 == Adjustment.objects.count()

    def test_duplicate_rows_in_one_file(self, event: Event, runners: None, referee: Actor) -> None:
        report = import_times(event, b"bib,clock\n1,10:00:01\n1,10:00:01\n", referee)
        assert (report.created, report.skipped) == (1, 1)

    def test_dry_run(self, event: Event, runners: None, referee: Actor) -> None:
        report = import_times(event, b"bib,clock\n1,10:00:01\n", referee, dry_run=True)
        assert (report.created, Read.objects.count()) == (1, 0)


class TestTimingPoint:
    def test_needs_a_finish(self, event: Event, race: Race, referee: Actor) -> None:
        Entry.objects.create(race=race, bib="1", given_name="Ada")
        with pytest.raises(CsvError, match="has no finish split"):
            import_times(event, b"bib,clock\n1,10:00:00\n", referee)

    def test_explicit_point(self, event: Event, runners: None, referee: Actor) -> None:
        bridge = TimingPoint.objects.create(event=event, name="Bridge")
        assert import_times(event, b"bib,clock\n1,10:10:00\n", referee, timing_point=bridge).ok
        assert Read.objects.get().timing_point == bridge

    def test_point_from_another_event(
        self, event: Event, runners: None, referee: Actor, organisation: object
    ) -> None:
        other = Event.objects.create(
            organisation=event.organisation, name="Other", slug="other", start_date=GUN.date()
        )
        point = TimingPoint.objects.create(event=other, name="Finish")
        with pytest.raises(CsvError, match="another event"):
            import_times(event, b"bib,clock\n1,10:00:00\n", referee, timing_point=point)


class TestResultsExport:
    def test_native_layout(
        self, event: Event, race: Race, runners: None, started: Wave, referee: Actor
    ) -> None:
        Entry.objects.filter(bib="2").update(hide_name=True)
        five_km = TimingPoint.objects.create(event=event, name="Halfway")
        Split.objects.filter(kind=Split.Kind.FINISH).update(order=2)
        Split.objects.create(race=race, timing_point=five_km, distance_m=5000, order=1)
        import_times(event, b"bib,elapsed\n1,12:00.5\n2,14:00\n", referee, timing_point=five_km)
        import_times(event, b"bib,elapsed\n1,25:36.97\n2,30:45\n", referee)
        lines = export_results(event, decimals=1).splitlines()
        assert lines[0] == (
            "race,position,bib,name,gender,category,gender_position,category_position,"
            "club,status,gun_time,net_time,5 km"
        )
        assert lines[1] == "10K,1,1,John Doe,male,SM,1,1,Club X,finished,0:25:36.9,,0:12:00.5"
        assert lines[2] == "10K,2,2,Anonymous,female,SF,1,1,Club Y,finished,0:30:45.0,,0:14:00.0"
        # Runners without a finish come after the finishers.
        assert [line.split(",")[2] for line in lines[3:]] == ["3", "4", "5", "6"]
