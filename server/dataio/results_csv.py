# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Results as CSV, from the stored results (results.models).

Names follow the entry's "hide my name" choice, because results files get published.
Times are truncated, never rounded up: `1:02:03.97` shows as `1:02:03`.
"""

from datetime import timedelta
from uuid import UUID

from dataio.csvfiles import format_duration, write_csv
from events.models import Event, Race, Split
from results.models import Result

LEGACY_HEADER = ("race_number", "total_time")

_OUTCOME_ORDER = {o: i for i, o in enumerate(Result.Outcome)}


def _split_label(split: Split) -> str:
    if split.name:
        return split.name
    if split.distance_m:
        km = split.distance_m / 1000
        return f"{km:g} km"
    return str(split.timing_point)


def export_results(
    event: Event, *, race: Race | None = None, legacy: bool = False, decimals: int = 0
) -> str:
    results = list(
        Result.objects.filter(event=event)
        .select_related("race", "entry")
        .order_by("race__order", "race__name")
    )
    if race is not None:
        results = [r for r in results if r.race_id == race.pk]
    results.sort(
        key=lambda r: (
            r.race.order,
            r.race.name,
            r.overall_position is None,
            r.overall_position or 0,
            _OUTCOME_ORDER.get(Result.Outcome(r.outcome), 99),
            r.entry.bib,
        )
    )

    def fmt(value: timedelta | None) -> str:
        return format_duration(value, decimals=decimals)

    if legacy:
        return write_csv(
            LEGACY_HEADER,
            (
                (r.entry.bib, format_duration(r.ranking_time, two_digit_hours=True))
                for r in results
                if r.outcome == Result.Outcome.FINISHED
            ),
        )

    # One column per intermediate split label, across the races exported.
    labels: dict[UUID, str] = {}
    columns: list[str] = []
    splits = Split.objects.filter(event=event, kind=Split.Kind.SPLIT).select_related(
        "race", "timing_point"
    )
    for split in sorted(splits, key=lambda s: (s.race.order, s.race.name, s.order)):
        if race is not None and split.race_id != race.pk:
            continue
        label = _split_label(split)
        labels[split.pk] = label
        if label not in columns:
            columns.append(label)

    header = (
        "race",
        "position",
        "bib",
        "name",
        "gender",
        "category",
        "gender_position",
        "category_position",
        "club",
        "status",
        "gun_time",
        "net_time",
        *columns,
    )
    rows = []
    for r in results:
        by_label = {
            labels[UUID(s["split"])]: fmt(timedelta(microseconds=s["elapsed_us"]))
            for s in r.splits
            if UUID(s["split"]) in labels
        }
        rows.append(
            (
                r.race.name,
                r.overall_position or "",
                r.entry.bib,
                r.entry.public_name,
                r.entry.gender,
                r.category,
                r.gender_position or "",
                r.category_position or "",
                r.entry.club,
                r.outcome,
                fmt(r.gun_time),
                fmt(r.net_time),
                *(by_label.get(label, "") for label in columns),
            )
        )
    return write_csv(header, rows)
