# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from datetime import date

import pytest

from dataio.csvfiles import CsvError, read_table
from dataio.entries import ALIASES, export_entries, import_entries, parse_date, parse_gender
from dataio.tests.conftest import LEGACY_DROGO, LEGACY_PARTICIPANTS
from events.models import Entry, Event, Gender, Race, Split, TimingPoint, Wave
from results.models import Result

pytestmark = pytest.mark.django_db


class TestLegacyFiles:
    def test_example_participants(self, event: Event, race: Race) -> None:
        report = import_entries(event, LEGACY_PARTICIPANTS)
        assert report.ok, report.errors
        assert (report.created, report.ignored_columns) == (6, [])
        jane = Entry.objects.get(event=event, bib="2")
        assert (jane.given_name, jane.family_name, jane.gender) == ("Jane", "Smith", "female")
        assert (jane.club, jane.declared_age, jane.race) == ("Club Y", 30, race)

    def test_drogo_file(self, event: Event, race: Race) -> None:
        report = import_entries(event, LEGACY_DROGO)
        assert report.ok, report.errors
        eirin = Entry.objects.get(event=event, bib="294")
        assert (eirin.family_name, eirin.gender, eirin.club) == (
            "Mc Daid",
            Gender.MALE,
            "Ranelagh Harriers",
        )

    def test_importing_twice_changes_nothing(self, event: Event, race: Race) -> None:
        import_entries(event, LEGACY_PARTICIPANTS)
        report = import_entries(event, LEGACY_PARTICIPANTS)
        assert (report.created, report.updated, report.unchanged) == (0, 0, 6)
        assert Entry.objects.filter(event=event).count() == 6

    def test_corrected_file_updates_in_place(self, event: Event, race: Race) -> None:
        import_entries(event, LEGACY_PARTICIPANTS)
        fixed = LEGACY_PARTICIPANTS.replace(b"Jane,Smith", b"Jane,Smyth")
        report = import_entries(event, fixed)
        assert (report.updated, report.unchanged) == (1, 5)
        assert Entry.objects.get(event=event, bib="2").family_name == "Smyth"


class TestProblems:
    def test_every_problem_reported_and_nothing_saved(self, event: Event, race: Race) -> None:
        data = (
            b"bib,first name,gender,dob,email\n"
            b"1,Ada,female,2001-04-30,ada@example.com\n"
            b"1,Ada again,female,,\n"
            b"2,Ben,robot,,\n"
            b"3,Cal,male,31/02/1990,\n"
            b"4,Dee,female,,not-an-email\n"
            b",Eve,female,,\n"
            b"5 5,Fay,female,,\n"
        )
        report = import_entries(event, data)
        assert [e.line for e in report.errors] == [3, 4, 5, 6, 7, 8]
        assert "also on line 2" in report.errors[0].message
        assert "isn't a gender" in report.errors[1].message
        assert "isn't a real date" in report.errors[2].message
        assert "Email" in report.errors[3].message
        assert "Bib" in report.errors[5].message
        assert not Entry.objects.exists()
        assert report.summary() == "Nothing imported: 6 row(s) need fixing."

    def test_missing_columns(self, event: Event, race: Race) -> None:
        with pytest.raises(CsvError, match="no bib column"):
            import_entries(event, b"name\nAda\n")
        with pytest.raises(CsvError, match="no name column"):
            import_entries(event, b"bib\n1\n")

    def test_dry_run_saves_nothing(self, event: Event, race: Race) -> None:
        report = import_entries(event, LEGACY_PARTICIPANTS, dry_run=True)
        assert (report.ok, report.created) == (True, 6)
        assert report.summary() == "Would import: 6 new."
        assert not Entry.objects.exists()


class TestRacesAndWaves:
    @pytest.fixture
    def five_k(self, event: Event) -> Race:
        return Race.objects.create(event=event, name="5K", distance_m=5000)

    def test_race_column(self, event: Event, race: Race, five_k: Race) -> None:
        report = import_entries(event, b"bib,name,race\n1,Ada,10k\n2,Ben,5K\n")
        assert report.ok, report.errors
        assert Entry.objects.get(bib="1").race == race
        assert Entry.objects.get(bib="2").race == five_k

    def test_several_races_need_a_race(self, event: Event, race: Race, five_k: Race) -> None:
        report = import_entries(event, b"bib,name\n1,Ada\n")
        assert "Say which race" in report.errors[0].message
        report = import_entries(event, b"bib,name\n1,Ada\n", race=five_k)
        assert report.ok and Entry.objects.get(bib="1").race == five_k

    def test_unknown_race(self, event: Event, race: Race) -> None:
        report = import_entries(event, b"bib,name,race\n1,Ada,Marathon\n")
        assert "no race called 'Marathon' (races: 10K)" in report.errors[0].message

    def test_waves(self, event: Event, race: Race, wave: Wave) -> None:
        elite = Wave.objects.create(race=race, name="Elite")
        assert "several waves" in import_entries(event, b"bib,name\n1,Ada\n").errors[0].message
        report = import_entries(event, b"bib,name,wave\n1,Ada,elite\n")
        assert report.ok and Entry.objects.get(bib="1").wave == elite
        # A file without a wave column leaves the wave alone.
        assert import_entries(event, b"bib,name\n1,Ada\n").unchanged == 1

    def test_moving_race_rebuilds_both(
        self, event: Event, race: Race, five_k: Race, finish_line: TimingPoint
    ) -> None:
        Split.objects.create(race=race, timing_point=finish_line, kind=Split.Kind.FINISH)
        Split.objects.create(race=five_k, timing_point=finish_line, kind=Split.Kind.FINISH)
        import_entries(event, b"bib,name,race\n1,Ada,10K\n")
        assert Result.objects.get(entry__bib="1").race == race
        import_entries(event, b"bib,name,race\n1,Ada,5K\n")
        assert Result.objects.get(entry__bib="1").race == five_k


class TestExport:
    def test_native_round_trip(self, event: Event, race: Race) -> None:
        Entry.objects.create(
            race=race,
            bib="7",
            given_name="=cmd",
            family_name="O'Neil",
            gender=Gender.NON_BINARY,
            date_of_birth=date(1990, 1, 2),
            club="-Harriers",
            email="x@example.com",
            hide_name=True,
        )
        text = export_entries(event)
        assert text.splitlines()[1] == (
            "7,'=cmd,O'Neil,non_binary,1990-01-02,,'-Harriers,x@example.com,yes,10K,,entered"
        )
        report = import_entries(event, text.encode())
        assert (report.ok, report.unchanged, report.ignored_columns) == (True, 1, [])

    def test_legacy_layout(self, event: Event, race: Race) -> None:
        import_entries(event, LEGACY_PARTICIPANTS)
        lines = export_entries(event, legacy=True).splitlines()
        assert lines[0] == LEGACY_PARTICIPANTS.decode().splitlines()[0]
        # Categories come from the race's scheme, not the file.
        assert lines[2] == "2,Jane,Smith,female,Club Y,,SF,30"
        assert read_table(export_entries(event, legacy=True).encode(), ALIASES).rows

    def test_sorted_by_bib_number(self, event: Event, race: Race) -> None:
        import_entries(event, b"bib,name\n10,A\n9,B\nA1,C\n")
        assert [line.split(",")[0] for line in export_entries(event).splitlines()[1:]] == [
            "9",
            "10",
            "A1",
        ]


@pytest.mark.parametrize(
    ("text", "gender"),
    [("M", "male"), ("Female", "female"), ("other", "non_binary"), ("", "undisclosed")],
)
def test_gender_spellings(text: str, gender: str) -> None:
    assert parse_gender(text) == gender


def test_day_first_dates() -> None:
    assert parse_date("30/04/2001") == parse_date("2001-04-30") == date(2001, 4, 30)
    assert parse_date("") is None
    with pytest.raises(ValueError):
        parse_date("04/30/2001")
