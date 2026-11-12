# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Scenario tests for the results engine. No database needed."""

from collections.abc import Hashable, Mapping
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest

from results.engine import (
    EntryDef,
    Flag,
    ManualStatus,
    Outcome,
    RaceDef,
    RaceWarning,
    RankingBasis,
    Read,
    Result,
    SplitDef,
    SplitKind,
    compute_results,
    round_up_to_second,
)

GUN = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
FINISH_LINE = "finish-line"
START_LINE = "start-line"
BRIDGE = "bridge"

FINISH = SplitDef("finish", FINISH_LINE, SplitKind.FINISH, order=10, distance_m=10_000)
START = SplitDef("start", START_LINE, SplitKind.START, order=0)
HALFWAY = SplitDef("5k", BRIDGE, SplitKind.SPLIT, order=5, distance_m=5_000)

_ids = count()


def read(bib: str, minutes: float, point: str = FINISH_LINE, *, start: datetime = GUN) -> Read:
    return Read(f"r{next(_ids)}", point, bib, start + timedelta(minutes=minutes))


def entry(
    bib: str,
    gender: str = "female",
    category: str | None = None,
    status: ManualStatus = ManualStatus.ENTERED,
    wave: str = "main",
) -> EntryDef:
    return EntryDef(f"e{bib}", bib, wave, gender, category, status)


def race(
    *splits: SplitDef,
    basis: RankingBasis = RankingBasis.GUN,
    waves: Mapping[Hashable, datetime | None] | None = None,
) -> RaceDef:
    return RaceDef(splits or (FINISH,), basis, waves if waves is not None else {"main": GUN})


def by_bib(results: list[Result]) -> dict[str, Result]:
    return {r.entry.bib: r for r in results}


class TestBasics:
    def test_gun_time_and_positions(self) -> None:
        out = compute_results(
            race(),
            [entry("1"), entry("2"), entry("3", gender="male")],
            [read("2", 40), read("1", 41.5), read("3", 39)],
        )
        r = by_bib(out.results)
        assert r["3"].gun_time == timedelta(minutes=39)
        assert [x.entry.bib for x in out.results] == ["3", "2", "1"]
        assert (r["3"].overall_position, r["2"].overall_position, r["1"].overall_position) == (
            1,
            2,
            3,
        )
        # Gender positions are counted separately.
        assert (r["3"].gender_position, r["2"].gender_position, r["1"].gender_position) == (
            1,
            1,
            2,
        )
        assert out.warnings == frozenset()

    def test_ties_share_a_place_and_skip_the_next(self) -> None:
        out = compute_results(
            race(),
            [entry("1"), entry("2"), entry("3")],
            [read("1", 40), read("2", 40), read("3", 41)],
        )
        assert [r.overall_position for r in out.results] == [1, 1, 3]

    def test_category_positions(self) -> None:
        out = compute_results(
            race(),
            [entry("1", category="FV35"), entry("2", category="SF"), entry("3", category="FV35")],
            [read("1", 40), read("2", 39), read("3", 41)],
        )
        r = by_bib(out.results)
        assert (r["1"].category_position, r["3"].category_position) == (1, 2)
        assert r["2"].category_position == 1

    def test_ignores_other_races_and_timing_points(self) -> None:
        # A shared finish line also sees the 5K runners; a bridge read isn't on this course.
        out = compute_results(
            race(), [entry("1")], [read("999", 20), read("1", 30, BRIDGE), read("1", 45)]
        )
        assert out.results[0].gun_time == timedelta(minutes=45)
        assert len(out.results) == 1

    def test_reads_before_the_gun_are_ignored(self) -> None:
        # e.g. walking through the finish on the way to the start.
        out = compute_results(race(), [entry("1")], [read("1", -15), read("1", 42)])
        assert out.results[0].gun_time == timedelta(minutes=42)


class TestWaves:
    def test_gun_time_is_from_own_wave(self) -> None:
        later = GUN + timedelta(minutes=5)
        out = compute_results(
            race(waves={"main": GUN, "b": later}),
            [entry("1"), entry("2", wave="b")],
            [read("1", 40), read("2", 43)],  # 2 finishes later on the clock...
        )
        r = by_bib(out.results)
        assert r["2"].gun_time == timedelta(minutes=38)
        assert r["2"].overall_position == 1  # ...but ran faster

    def test_awaiting_start(self) -> None:
        out = compute_results(race(waves={"main": None}), [entry("1")], [read("1", 40)])
        assert out.results[0].outcome == Outcome.AWAITING_START
        assert out.results[0].gun_time is None


class TestNetTime:
    def test_net_ranking_uses_start_read(self) -> None:
        out = compute_results(
            race(START, FINISH, basis=RankingBasis.NET),
            [entry("1"), entry("2")],
            [
                read("1", 0.1, START_LINE),
                read("1", 40),  # gun 40:00, net 39:54
                read("2", 1.0, START_LINE),
                read("2", 40.5),  # gun 40:30, net 39:30
            ],
        )
        r = by_bib(out.results)
        assert r["2"].net_time == timedelta(minutes=39, seconds=30)
        assert r["2"].overall_position == 1
        assert r["1"].gun_time == timedelta(minutes=40)

    def test_missing_start_read_falls_back_to_gun(self) -> None:
        out = compute_results(
            race(START, FINISH, basis=RankingBasis.NET), [entry("1")], [read("1", 40)]
        )
        result = out.results[0]
        assert result.ranking_time == timedelta(minutes=40)
        assert result.net_time is None
        assert Flag.NET_FROM_GUN in result.flags

    def test_gun_ranking_still_reports_net(self) -> None:
        out = compute_results(
            race(START, FINISH), [entry("1")], [read("1", 0.5, START_LINE), read("1", 40)]
        )
        result = out.results[0]
        assert result.ranking_time == timedelta(minutes=40)
        assert result.net_time == timedelta(minutes=39, seconds=30)

    def test_net_without_start_split_warns(self) -> None:
        out = compute_results(race(FINISH, basis=RankingBasis.NET), [], [])
        assert RaceWarning.NET_WITHOUT_START_SPLIT in out.warnings


class TestSplitsAndLaps:
    LAP = SplitDef("lap1", FINISH_LINE, SplitKind.SPLIT, order=5, min_elapsed=timedelta(minutes=15))
    LAPPED_FINISH = SplitDef(
        "finish", FINISH_LINE, SplitKind.FINISH, order=10, min_elapsed=timedelta(minutes=30)
    )

    def test_two_laps_through_one_line(self) -> None:
        out = compute_results(
            race(self.LAP, self.LAPPED_FINISH), [entry("1")], [read("1", 20), read("1", 41)]
        )
        result = out.results[0]
        assert [s.split for s in result.splits] == ["lap1", "finish"]
        assert result.gun_time == timedelta(minutes=41)

    def test_missed_lap_read_leaves_runner_a_lap_short(self) -> None:
        # One crossing at 41 min: a fast finisher whose lap-1 read was missed, or a slow
        # runner finishing lap 1? The engine can't tell, so it counts passes in order
        # and leaves the runner on course rather than inventing a finish. The review
        # queue fixes it (add the missing read).
        out = compute_results(race(self.LAP, self.LAPPED_FINISH), [entry("1")], [read("1", 41)])
        result = out.results[0]
        assert result.outcome == Outcome.ON_COURSE
        assert [s.split for s in result.splits] == ["lap1"]
        assert result.missing_splits == ("finish",)

    def test_min_elapsed_ignores_passes_too_early_for_a_lap(self) -> None:
        # Crossing the line 2 minutes in (e.g. a start on the finish line) isn't lap 1.
        out = compute_results(
            race(self.LAP, self.LAPPED_FINISH),
            [entry("1")],
            [read("1", 2), read("1", 20), read("1", 41)],
        )
        assert [s.elapsed for s in out.results[0].splits] == [
            timedelta(minutes=20),
            timedelta(minutes=41),
        ]

    def test_lap_only_runner_is_on_course(self) -> None:
        out = compute_results(race(self.LAP, self.LAPPED_FINISH), [entry("1")], [read("1", 20)])
        assert out.results[0].outcome == Outcome.ON_COURSE

    def test_duplicate_reads_are_one_crossing(self) -> None:
        lap = SplitDef("lap1", FINISH_LINE, SplitKind.SPLIT, order=5)
        finish = SplitDef(
            "finish", FINISH_LINE, SplitKind.FINISH, order=10, min_elapsed=timedelta(0)
        )
        # Seen twice, 3 s apart, at the end of lap 1; finish 20 minutes later.
        out = compute_results(
            race(lap, finish),
            [entry("1")],
            [read("1", 20), read("1", 20.05), read("1", 40)],
        )
        assert out.results[0].gun_time == timedelta(minutes=40)

    def test_repeated_timing_point_without_min_elapsed_warns(self) -> None:
        lap = SplitDef("lap1", FINISH_LINE, SplitKind.SPLIT, order=5)
        finish = SplitDef("finish", FINISH_LINE, SplitKind.FINISH, order=10)
        out = compute_results(race(lap, finish), [], [])
        assert RaceWarning.REPEATED_TIMING_POINT_WITHOUT_MIN_ELAPSED in out.warnings

    def test_missed_intermediate_split_is_flagged(self) -> None:
        out = compute_results(race(HALFWAY, FINISH), [entry("1")], [read("1", 40)])
        result = out.results[0]
        assert result.outcome == Outcome.FINISHED
        assert result.missing_splits == ("5k",)
        assert Flag.MISSED_SPLIT in result.flags

    def test_split_elapsed_times(self) -> None:
        out = compute_results(
            race(HALFWAY, FINISH), [entry("1")], [read("1", 19.5, BRIDGE), read("1", 40)]
        )
        assert [s.elapsed for s in out.results[0].splits] == [
            timedelta(minutes=19, seconds=30),
            timedelta(minutes=40),
        ]

    def test_no_finish_split_warns(self) -> None:
        out = compute_results(race(HALFWAY), [entry("1")], [read("1", 20, BRIDGE)])
        assert RaceWarning.NO_FINISH_SPLIT in out.warnings
        assert out.results[0].outcome == Outcome.ON_COURSE


class TestStatuses:
    def test_dsq_takes_no_place(self) -> None:
        out = compute_results(
            race(),
            [entry("1", status=ManualStatus.DSQ), entry("2")],
            [read("1", 38), read("2", 40)],
        )
        r = by_bib(out.results)
        assert r["1"].outcome == Outcome.DSQ
        assert r["1"].overall_position is None
        assert r["1"].gun_time == timedelta(minutes=38)  # kept for the record
        assert r["2"].overall_position == 1

    def test_dns_with_reads_is_flagged(self) -> None:
        out = compute_results(race(), [entry("1", status=ManualStatus.DNS)], [read("1", 40)])
        assert out.results[0].outcome == Outcome.DNS
        assert Flag.READS_FOR_DNS in out.results[0].flags

    def test_dnf_with_finish_is_flagged(self) -> None:
        out = compute_results(race(), [entry("1", status=ManualStatus.DNF)], [read("1", 40)])
        assert out.results[0].outcome == Outcome.DNF
        assert Flag.FINISH_FOR_DNF in out.results[0].flags

    def test_no_reads(self) -> None:
        out = compute_results(race(), [entry("1")], [])
        assert out.results[0].outcome == Outcome.NO_READS


class TestDisplayOrder:
    def test_order_of_groups(self) -> None:
        out = compute_results(
            race(HALFWAY, FINISH),
            [
                entry("10", status=ManualStatus.DSQ),
                entry("9", status=ManualStatus.DNS),
                entry("8", status=ManualStatus.DNF),
                entry("7"),  # no reads
                entry("6"),  # at halfway, slower
                entry("5"),  # at halfway, faster
                entry("4"),  # finished second
                entry("3"),  # finished first
            ],
            [
                read("6", 22, BRIDGE),
                read("5", 21, BRIDGE),
                read("4", 41),
                read("3", 40),
            ],
        )
        assert [r.entry.bib for r in out.results] == ["3", "4", "5", "6", "7", "8", "9", "10"]

    def test_numeric_bibs_sort_numerically(self) -> None:
        out = compute_results(race(), [entry("10"), entry("2"), entry("A1")], [])
        assert [r.entry.bib for r in out.results] == ["2", "10", "A1"]


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(2399.0, 2399), (2399.01, 2400), (2399.999, 2400), (0.0, 0)],
)
def test_round_up_to_second(seconds: float, expected: int) -> None:
    assert round_up_to_second(timedelta(seconds=seconds)) == timedelta(seconds=expected)
