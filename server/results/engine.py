# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The results engine: turns accepted reads into results for one race.

Pure Python with no Django imports, so it's fast to test and gives the same answer
in the cloud and on a venue laptop. Callers (slice 1.4) build the inputs from the
database, call `compute_results`, and store what comes back.

How reads become splits
-----------------------
Each entry's reads are matched to the race's splits in course order. For each split,
the engine takes the earliest unused read at that split's timing point that is:

- at or after the previous matched split (the course runs forwards), and at or
  after the wave start;
- at least `min_elapsed` after the wave start, if the split sets one (this is what
  tells lap 1 apart from the finish when both use the same line);
- more than `duplicate_window` after the last read used at the same timing point
  (a runner seen twice in a few seconds is one crossing, not two laps).

A split with no matching read is reported as missing, and matching carries on with
the next split, so a missed read at the halfway bridge doesn't stop the finish being
found.

Laps through one line are counted in order: the k-th crossing is the k-th split. If a
lap read is missed, the runner ends up one lap short (shown as on course) instead of
being given a finish time. One crossing at 41 minutes could be a fast finisher whose
lap read was missed or a slow runner finishing lap 1, and only a person can tell which.
The review queue is where that gets fixed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum
from math import ceil

DEFAULT_DUPLICATE_WINDOW = timedelta(seconds=10)


class SplitKind(StrEnum):
    START = "start"
    SPLIT = "split"
    FINISH = "finish"


class RankingBasis(StrEnum):
    GUN = "gun"
    NET = "net"


class ManualStatus(StrEnum):
    """What a person has decided about an entry (mirrors events.Entry.Status)."""

    ENTERED = "entered"
    DNS = "dns"
    DNF = "dnf"
    DSQ = "dsq"


class Outcome(StrEnum):
    FINISHED = "finished"
    ON_COURSE = "on_course"  # seen at a split, no finish yet
    NO_READS = "no_reads"  # wave started, never seen
    AWAITING_START = "awaiting_start"  # wave not started yet
    DNF = "dnf"
    DNS = "dns"
    DSQ = "dsq"


class Flag(StrEnum):
    """Things an organiser should look at. They never change the computed result."""

    READS_FOR_DNS = "reads_for_dns"  # marked DNS but seen on course
    FINISH_FOR_DNF = "finish_for_dnf"  # marked DNF but has a finish read
    NET_FROM_GUN = "net_from_gun"  # net ranking, but no start read: gun time used
    MISSED_SPLIT = "missed_split"  # finished but missing an intermediate split


class RaceWarning(StrEnum):
    """Problems with the race set-up that make results unreliable."""

    NO_FINISH_SPLIT = "no_finish_split"
    NET_WITHOUT_START_SPLIT = "net_without_start_split"
    REPEATED_TIMING_POINT_WITHOUT_MIN_ELAPSED = "repeated_timing_point_without_min_elapsed"


# ------------------------------------------------------------------------------ inputs


@dataclass(frozen=True)
class SplitDef:
    id: Hashable
    timing_point: Hashable
    kind: SplitKind
    order: int
    distance_m: int = 0
    min_elapsed: timedelta | None = None


@dataclass(frozen=True)
class EntryDef:
    id: Hashable
    bib: str
    wave: Hashable
    gender: str
    category: str | None = None  # resolved by the caller (events.categories)
    status: ManualStatus = ManualStatus.ENTERED


@dataclass(frozen=True)
class Read:
    """An accepted read: fusion has settled the bib, or a person confirmed it."""

    id: Hashable
    timing_point: Hashable
    bib: str
    at: datetime


@dataclass(frozen=True)
class RaceDef:
    splits: Sequence[SplitDef]
    ranking_basis: RankingBasis
    wave_starts: Mapping[Hashable, datetime | None]


# ----------------------------------------------------------------------------- outputs


@dataclass(frozen=True)
class SplitTime:
    split: Hashable
    read: Hashable
    at: datetime
    elapsed: timedelta  # since the wave start (gun)


@dataclass(frozen=True)
class Result:
    entry: EntryDef
    outcome: Outcome
    splits: tuple[SplitTime, ...] = ()
    missing_splits: tuple[Hashable, ...] = ()
    gun_time: timedelta | None = None
    net_time: timedelta | None = None
    ranking_time: timedelta | None = None
    overall_position: int | None = None
    gender_position: int | None = None
    category_position: int | None = None
    flags: frozenset[Flag] = frozenset()


@dataclass(frozen=True)
class RaceResults:
    results: list[Result]
    warnings: frozenset[RaceWarning] = field(default_factory=frozenset)


# ------------------------------------------------------------------------------ engine


def compute_results(
    race: RaceDef,
    entries: Iterable[EntryDef],
    reads: Iterable[Read],
    duplicate_window: timedelta = DEFAULT_DUPLICATE_WINDOW,
) -> RaceResults:
    """Compute results for every entry in one race.

    `reads` may include reads for other races or other timing points (a shared finish
    line sees everyone). Anything that doesn't belong to this race's entries and splits
    is ignored.
    """
    splits = sorted(race.splits, key=lambda s: s.order)
    race_points = {s.timing_point for s in splits}
    entry_list = list(entries)
    bibs = {e.bib for e in entry_list}

    reads_by_bib: dict[str, list[Read]] = defaultdict(list)
    for read in reads:
        if read.bib in bibs and read.timing_point in race_points:
            reads_by_bib[read.bib].append(read)

    unranked = [
        _result_for_entry(race, splits, entry, reads_by_bib.get(entry.bib, []), duplicate_window)
        for entry in entry_list
    ]
    ranked = _assign_positions(unranked)
    return RaceResults(results=sorted(ranked, key=_display_order), warnings=_warnings(race, splits))


def _result_for_entry(
    race: RaceDef,
    splits: list[SplitDef],
    entry: EntryDef,
    reads: list[Read],
    duplicate_window: timedelta,
) -> Result:
    start = race.wave_starts.get(entry.wave)
    matched: list[SplitTime] = []
    missing: list[Hashable] = []
    if start is not None:
        matched, missing = _match_splits(splits, reads, start, duplicate_window)

    kinds = {s.id: s.kind for s in splits}
    finish = next((m for m in matched if kinds[m.split] == SplitKind.FINISH), None)
    start_read = next((m for m in matched if kinds[m.split] == SplitKind.START), None)

    gun_time = finish.elapsed if finish else None
    net_time = finish.at - start_read.at if finish and start_read else None
    flags: set[Flag] = set()
    ranking_time = gun_time
    if race.ranking_basis == RankingBasis.NET and gun_time is not None:
        if net_time is None:
            flags.add(Flag.NET_FROM_GUN)
        else:
            ranking_time = net_time
    if finish and any(s.kind == SplitKind.SPLIT for s in splits if s.id in missing):
        flags.add(Flag.MISSED_SPLIT)

    outcome: Outcome
    match entry.status:
        case ManualStatus.DSQ:
            outcome = Outcome.DSQ
        case ManualStatus.DNS:
            outcome = Outcome.DNS
            if reads:
                flags.add(Flag.READS_FOR_DNS)
        case ManualStatus.DNF:
            outcome = Outcome.DNF
            if finish:
                flags.add(Flag.FINISH_FOR_DNF)
        case ManualStatus.ENTERED:
            if start is None:
                outcome = Outcome.AWAITING_START
            elif finish:
                outcome = Outcome.FINISHED
            elif matched:
                outcome = Outcome.ON_COURSE
            else:
                outcome = Outcome.NO_READS

    return Result(
        entry=entry,
        outcome=outcome,
        splits=tuple(matched),
        missing_splits=tuple(missing),
        gun_time=gun_time,
        net_time=net_time,
        ranking_time=ranking_time if outcome == Outcome.FINISHED else None,
        flags=frozenset(flags),
    )


def _match_splits(
    splits: list[SplitDef], reads: list[Read], start: datetime, duplicate_window: timedelta
) -> tuple[list[SplitTime], list[Hashable]]:
    by_point: dict[Hashable, list[Read]] = defaultdict(list)
    # Tie-break on id so equal timestamps give the same answer whatever the input order.
    for read in sorted(reads, key=lambda r: (r.at, str(r.id))):
        by_point[read.timing_point].append(read)

    used: set[Hashable] = set()
    last_used_at: dict[Hashable, datetime] = {}
    cursor = start
    matched: list[SplitTime] = []
    missing: list[Hashable] = []

    for split in splits:
        earliest = max(cursor, start + (split.min_elapsed or timedelta(0)))
        previous = last_used_at.get(split.timing_point)
        pick = next(
            (
                r
                for r in by_point[split.timing_point]
                if r.id not in used
                and r.at >= earliest
                and (previous is None or r.at - previous > duplicate_window)
            ),
            None,
        )
        if pick is None:
            missing.append(split.id)
            continue
        used.add(pick.id)
        last_used_at[split.timing_point] = pick.at
        cursor = pick.at
        matched.append(SplitTime(split.id, pick.id, pick.at, pick.at - start))
    return matched, missing


def _assign_positions(results: list[Result]) -> list[Result]:
    finished = [r for r in results if r.outcome == Outcome.FINISHED]
    overall = _competition_ranks(finished, key=lambda r: None)
    gender = _competition_ranks(finished, key=lambda r: r.entry.gender)
    category = _competition_ranks(
        [r for r in finished if r.entry.category is not None], key=lambda r: r.entry.category
    )
    out = []
    for r in results:
        if r.outcome != Outcome.FINISHED:
            out.append(r)
            continue
        out.append(
            replace(
                r,
                overall_position=overall[r.entry.id],
                gender_position=gender[r.entry.id],
                category_position=category.get(r.entry.id),
            )
        )
    return out


def _competition_ranks(
    results: list[Result], key: Callable[[Result], Hashable]
) -> dict[Hashable, int]:
    """Standard competition ranking within each group: equal times share a place
    and the next place is skipped (1, 2, 2, 4)."""
    groups: dict[Hashable, list[Result]] = defaultdict(list)
    for r in results:
        groups[key(r)].append(r)
    ranks: dict[Hashable, int] = {}
    for members in groups.values():
        members.sort(key=lambda r: (r.ranking_time, _bib_key(r.entry.bib)))
        previous_time: timedelta | None = None
        previous_rank = 0
        for index, r in enumerate(members, start=1):
            rank = previous_rank if r.ranking_time == previous_time else index
            ranks[r.entry.id] = rank
            previous_time, previous_rank = r.ranking_time, rank
    return ranks


_OUTCOME_ORDER = {
    Outcome.FINISHED: 0,
    Outcome.ON_COURSE: 1,
    Outcome.NO_READS: 2,
    Outcome.AWAITING_START: 3,
    Outcome.DNF: 4,
    Outcome.DNS: 5,
    Outcome.DSQ: 6,
}


def _display_order(r: Result) -> tuple[object, ...]:
    """Finishers by position; runners still out by how far they've got; the rest by bib."""
    group = _OUTCOME_ORDER[r.outcome]
    if r.outcome == Outcome.FINISHED:
        return (group, r.overall_position, _bib_key(r.entry.bib))
    if r.outcome == Outcome.ON_COURSE:
        last = r.splits[-1]
        return (group, -len(r.splits), last.elapsed, _bib_key(r.entry.bib))
    return (group, _bib_key(r.entry.bib))


def _bib_key(bib: str) -> tuple[int, int, str]:
    """Sort numeric bibs numerically ("2" before "10"), then everything else."""
    return (0, int(bib), "") if bib.isdigit() else (1, 0, bib)


def _warnings(race: RaceDef, splits: list[SplitDef]) -> frozenset[RaceWarning]:
    warnings: set[RaceWarning] = set()
    if not any(s.kind == SplitKind.FINISH for s in splits):
        warnings.add(RaceWarning.NO_FINISH_SPLIT)
    if race.ranking_basis == RankingBasis.NET and not any(
        s.kind == SplitKind.START for s in splits
    ):
        warnings.add(RaceWarning.NET_WITHOUT_START_SPLIT)
    seen: set[Hashable] = set()
    for split in splits:
        if split.timing_point in seen and split.min_elapsed is None:
            warnings.add(RaceWarning.REPEATED_TIMING_POINT_WITHOUT_MIN_ELAPSED)
        seen.add(split.timing_point)
    return frozenset(warnings)


# --------------------------------------------------------------------------- display


def round_up_to_second(duration: timedelta) -> timedelta:
    """Road-race times are published in whole seconds, rounded up (World Athletics
    rule 19.24). Rank on the precise time; show this one."""
    return timedelta(seconds=ceil(duration.total_seconds()))
