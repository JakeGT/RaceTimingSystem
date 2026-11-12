# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Property tests: invariants that must hold for any race, checked on random races."""

from datetime import UTC, datetime, timedelta
from random import Random

from hypothesis import given
from hypothesis import strategies as st

from results.engine import (
    EntryDef,
    ManualStatus,
    Outcome,
    RaceDef,
    RankingBasis,
    Read,
    SplitDef,
    SplitKind,
    compute_results,
)

GUN = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)
RACE = RaceDef(
    splits=(
        SplitDef("start", "start-line", SplitKind.START, 0),
        SplitDef("5k", "bridge", SplitKind.SPLIT, 5),
        SplitDef("finish", "finish-line", SplitKind.FINISH, 10),
    ),
    ranking_basis=RankingBasis.GUN,
    wave_starts={"main": GUN},
)
POINTS = ["start-line", "bridge", "finish-line"]


@st.composite
def races(draw: st.DrawFn) -> tuple[list[EntryDef], list[Read]]:
    bibs = draw(st.lists(st.integers(1, 500), min_size=0, max_size=25, unique=True))
    entries = [
        EntryDef(
            id=f"e{bib}",
            bib=str(bib),
            wave="main",
            gender=draw(st.sampled_from(["female", "male", "non_binary"])),
            category=draw(st.sampled_from([None, "SEN", "V40", "V50"])),
            # Mostly entered, sometimes DNS/DNF/DSQ.
            status=draw(st.just(ManualStatus.ENTERED) | st.sampled_from(list(ManualStatus))),
        )
        for bib in bibs
    ]
    reads = []
    for n, (bib, point, seconds) in enumerate(
        draw(
            st.lists(
                st.tuples(
                    st.sampled_from([str(b) for b in bibs] or ["1"]),
                    st.sampled_from(POINTS),
                    # Whole seconds, so ties happen often enough to be tested.
                    st.integers(-600, 3 * 3600),
                ),
                max_size=60,
            )
        )
    ):
        reads.append(Read(f"r{n}", point, bib, GUN + timedelta(seconds=seconds)))
    return entries, reads


@given(races())
def test_every_entry_appears_once(race: tuple[list[EntryDef], list[Read]]) -> None:
    entries, reads = race
    out = compute_results(RACE, entries, reads)
    assert sorted(str(r.entry.id) for r in out.results) == sorted(str(e.id) for e in entries)


@given(races(), st.randoms())
def test_read_order_does_not_matter(race: tuple[list[EntryDef], list[Read]], rng: Random) -> None:
    entries, reads = race
    shuffled = list(reads)
    rng.shuffle(shuffled)
    assert compute_results(RACE, entries, reads) == compute_results(RACE, entries, shuffled)


@given(races())
def test_times_are_never_negative_and_splits_run_forwards(
    race: tuple[list[EntryDef], list[Read]],
) -> None:
    out = compute_results(RACE, *race)
    for result in out.results:
        elapsed = [s.elapsed for s in result.splits]
        assert all(e >= timedelta(0) for e in elapsed)
        assert elapsed == sorted(elapsed)
        if result.net_time is not None:
            assert result.net_time >= timedelta(0)


@given(races())
def test_positions_follow_competition_ranking(race: tuple[list[EntryDef], list[Read]]) -> None:
    out = compute_results(RACE, *race)
    finished = [r for r in out.results if r.outcome == Outcome.FINISHED]
    others = [r for r in out.results if r.outcome != Outcome.FINISHED]
    assert all(r.overall_position is None for r in others)

    def expected(r_time: timedelta, group: list[timedelta]) -> int:
        return 1 + sum(t < r_time for t in group)

    for r in finished:
        assert r.ranking_time is not None
        times = [x.ranking_time for x in finished if x.ranking_time is not None]
        assert r.overall_position == expected(r.ranking_time, times)
        same_gender = [
            x.ranking_time
            for x in finished
            if x.entry.gender == r.entry.gender and x.ranking_time is not None
        ]
        assert r.gender_position == expected(r.ranking_time, same_gender)
        if r.entry.category is None:
            assert r.category_position is None
        else:
            same_category = [
                x.ranking_time
                for x in finished
                if x.entry.category == r.entry.category and x.ranking_time is not None
            ]
            assert r.category_position == expected(r.ranking_time, same_category)

    # Finishers come first, in position order.
    leading = [r.overall_position for r in out.results[: len(finished)]]
    assert None not in leading
    assert leading == sorted(p for p in leading if p is not None)
