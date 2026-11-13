# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Crossing times from a file: a timekeeper's stopwatch export, another timing system,
or the legacy system's results files.

Each row becomes a manual read at one timing point (the race's finish by default),
audited like a manual read added by hand. Accepted layouts, by column:

- `bib` + `at`: ISO 8601 date and time (`2026-06-14T09:41:07.3`; no offset means the
  event's timezone)
- `bib` + `clock`: time of day (`09:41:07.3`) on the event's first day, event timezone
- `bib` + `unix`: seconds since 1970 (the legacy bib detector's `BibNumber,Result`)
- `bib` + `elapsed`: time since the runner's wave started (the legacy
  `race_number,total_time`), which needs the wave's start time

Rows whose read already exists (same point, bib and time) are skipped, so a file can be
imported again safely. Legacy detector rows with bib `-1` (unreadable) are skipped too.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from django.db import transaction

from dataio.csvfiles import CsvError, ImportReport, parse_duration, read_table
from events.models import Entry, Event, Race, Split, TimingPoint, Wave
from results.services import races_using, rebuild_races
from timing.models import Adjustment, Read
from timing.review import Actor

TIME_COLUMNS: dict[str, tuple[str, ...]] = {
    "at": ("at", "datetime", "timestamputc", "isotime"),
    "clock": ("clock", "timeofday", "time", "clocktime"),
    "unix": ("unix", "epoch", "timestamp", "result"),
    "elapsed": ("elapsed", "totaltime", "guntime", "racetime"),
}
ALIASES: dict[str, tuple[str, ...]] = {
    "bib": ("bib", "bibnumber", "bibno", "racenumber", "number"),
    **TIME_COLUMNS,
}
KNOWN_UNUSED = ("trackerid", "filename", "name", "position")
UNREADABLE_BIBS = {"-1", "?"}
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2}):(\d{2}(?:[.,]\d+)?)$")


def default_timing_point(event: Event, race: Race | None) -> TimingPoint:
    """The finish line, if the races in question share exactly one."""
    finishes = Split.objects.filter(event=event, kind=Split.Kind.FINISH)
    if race is not None:
        finishes = finishes.filter(race=race)
    points = list(TimingPoint.objects.filter(pk__in=finishes.values("timing_point")))
    if len(points) != 1:
        where = race.name if race else "this event"
        problem = "has no finish split" if not points else "has several finish lines"
        raise CsvError(f"{where} {problem}, so pick the timing point these times are for.")
    return points[0]


class _Clock:
    def __init__(self, event: Event) -> None:
        self.zone = ZoneInfo(event.timezone)
        self.day: date = event.start_date

    def at(self, text: str) -> datetime:
        try:
            value = datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            raise ValueError(f"{text!r} isn't a date and time like 2026-06-14T09:41:07.") from None
        return value if value.tzinfo else value.replace(tzinfo=self.zone)

    def clock(self, text: str) -> datetime:
        match = _CLOCK.match(text)
        if not match:
            raise ValueError(f"{text!r} isn't a time of day like 09:41:07.3.")
        hours, minutes, seconds = match.groups()
        whole = float(seconds.replace(",", "."))
        if int(hours) > 23 or int(minutes) > 59 or whole >= 60:
            raise ValueError(f"{text!r} isn't a real time of day.")
        midnight = datetime.combine(self.day, time(), tzinfo=self.zone)
        return midnight + timedelta(hours=int(hours), minutes=int(minutes), seconds=whole)

    @staticmethod
    def unix(text: str) -> datetime:
        try:
            return datetime.fromtimestamp(float(text), tz=UTC)
        except (ValueError, OverflowError, OSError):
            raise ValueError(f"{text!r} isn't a Unix timestamp.") from None


def import_times(
    event: Event,
    data: bytes,
    by: Actor,
    *,
    timing_point: TimingPoint | None = None,
    race: Race | None = None,
    filename: str = "",
    reason: str = "",
    dry_run: bool = False,
) -> ImportReport:
    report = ImportReport(dry_run=dry_run)
    if race is not None and race.event_id != event.pk:
        raise CsvError("That race belongs to another event.")
    if timing_point is not None and timing_point.event_id != event.pk:
        raise CsvError("That timing point belongs to another event.")
    table = read_table(data, ALIASES, known_unused=KNOWN_UNUSED)
    report.ignored_columns = table.ignored
    if "bib" not in table.columns:
        raise CsvError("There's no bib column (e.g. Bib, BibNumber or race_number).")
    kinds = [kind for kind in TIME_COLUMNS if kind in table.columns]
    if len(kinds) != 1:
        found = ", ".join(table.columns[k] for k in kinds) or "none"
        raise CsvError(
            "Use exactly one time column: at, clock, unix or elapsed "
            f"(legacy: Result or total_time). Found: {found}."
        )
    kind = kinds[0]
    point = timing_point or default_timing_point(event, race)

    entries = {e.bib: e for e in Entry.objects.filter(event=event).select_related("wave")}
    starts = _wave_starts(event) if kind == "elapsed" else {}
    clock = _Clock(event)
    existing = set(Read.objects.filter(timing_point=point).values_list("bib", "at"))
    planned: set[tuple[str, datetime]] = set()
    reads: list[Read] = []

    for line, row in table.rows:
        bib, text = row["bib"], row[kind]
        if bib in UNREADABLE_BIBS:
            report.skipped += 1
            continue
        if not bib or not text:
            report.error(line, "Needs a bib and a time.")
            continue
        entry = entries.get(bib)
        if entry is None:
            report.error(line, f"Nobody in this event has bib {bib!r}.")
            continue
        try:
            if kind == "elapsed":
                start = starts.get(entry.wave_id or entry.race_id)
                if start is None:
                    raise ValueError(
                        f"Bib {bib}'s wave hasn't started, so there's nothing to add "
                        "an elapsed time to. Start the wave first."
                    )
                at = start + parse_duration(text)
            else:
                at = getattr(clock, kind)(text)
        except ValueError as e:
            report.error(line, str(e))
            continue
        key = (bib, at)
        if key in existing or key in planned:
            report.skipped += 1
            continue
        planned.add(key)
        reads.append(Read(event=event, timing_point=point, bib=bib, at=at, state=Read.State.MANUAL))

    report.created = len(reads)
    if report.errors or dry_run or not reads:
        return report
    note = f"Imported from {filename or 'a file'}"
    full_reason = f"{note}: {reason.strip()}" if reason.strip() else note
    with transaction.atomic():
        Read.objects.bulk_create(reads)
        Adjustment.objects.bulk_create(
            Adjustment(
                event=event,
                action=Adjustment.Action.READ_ADDED,
                actor=by.user,
                actor_label=by.label,
                read=read,
                after={"bib": read.bib, "at": read.at.isoformat(), "state": read.state},
                reason=full_reason[:255],
            )
            for read in reads
        )
        rebuild_races(races_using([point.pk]))
    return report


def _wave_starts(event: Event) -> dict[UUID, datetime]:
    """Start time by wave id, plus by race id for races with a single wave (entries in
    those may leave the wave blank)."""
    starts: dict[UUID, datetime] = {}
    by_race: dict[UUID, list[Wave]] = {}
    for wave in Wave.objects.filter(event=event):
        by_race.setdefault(wave.race_id, []).append(wave)
        if wave.start_at:
            starts[wave.pk] = wave.start_at
    for race_id, waves in by_race.items():
        if len(waves) == 1 and waves[0].start_at:
            starts[race_id] = waves[0].start_at
    return starts
