# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rebuild stored results from reads and entries.

Every rebuild recomputes a whole race from scratch (the engine is fast and pure), so
stored results can never drift from the reads: there's no incremental state to get wrong.
"""

from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from events.categories import pick_category
from events.models import Event, Race
from results import engine
from results.models import RaceResults, Result
from timing.models import Read


def races_using(timing_point_ids: Iterable[UUID]) -> list[Race]:
    return list(Race.objects.filter(splits__timing_point_id__in=list(timing_point_ids)).distinct())


def rebuild_races(races: Iterable[Race]) -> None:
    for race in races:
        rebuild_race(race)


def rebuild_event(event: Event) -> None:
    rebuild_races(event.races.all())


def rebuild_race(race: Race) -> RaceResults:
    race = Race.objects.select_related("event", "category_scheme").get(pk=race.pk)
    splits = list(race.splits.all())
    waves = list(race.waves.all())
    only_wave = waves[0].pk if len(waves) == 1 else None
    bands = race.category_scheme.bands() if race.category_scheme else None

    entries = []
    for entry in race.entries.all():
        entry.race = race  # spares a query per entry in age_for_categories()
        band = pick_category(bands, entry.gender, entry.age_for_categories()) if bands else None
        entries.append(
            engine.EntryDef(
                id=entry.pk,
                bib=entry.bib,
                wave=entry.wave_id or only_wave,
                gender=entry.gender,
                category=band.code if band else None,
                status=engine.ManualStatus(entry.status),
            )
        )
    reads = [
        engine.Read(id=pk, timing_point=point, bib=bib, at=at)
        for pk, point, bib, at in Read.objects.filter(
            event_id=race.event_id,
            timing_point_id__in={s.timing_point_id for s in splits},
            state__in=Read.ACCEPTED_STATES,
        )
        .exclude(bib="")
        .values_list("pk", "timing_point_id", "bib", "at")
    ]
    computed = engine.compute_results(
        engine.RaceDef(
            splits=[
                engine.SplitDef(
                    id=s.pk,
                    timing_point=s.timing_point_id,
                    kind=engine.SplitKind(s.kind),
                    order=s.order,
                    distance_m=s.distance_m,
                    min_elapsed=s.min_elapsed,
                )
                for s in splits
            ],
            ranking_basis=engine.RankingBasis(race.ranking_basis),
            wave_starts={w.pk: w.start_at for w in waves},
        ),
        entries,
        reads,
    )

    now = timezone.now()
    with transaction.atomic():
        # entry__race catches entries that moved here from another race.
        Result.objects.filter(Q(race=race) | Q(entry__race=race)).delete()
        Result.objects.bulk_create(_row(race, r, now) for r in computed.results)
        summary, _ = RaceResults.objects.update_or_create(
            race=race,
            defaults={
                "event_id": race.event_id,
                "warnings": sorted(computed.warnings),
                "computed_at": now,
            },
        )
    return summary


def _row(race: Race, r: engine.Result, now: datetime) -> Result:
    return Result(
        event_id=race.event_id,
        race=race,
        entry_id=cast(UUID, r.entry.id),
        outcome=r.outcome.value,
        gun_time=r.gun_time,
        net_time=r.net_time,
        ranking_time=r.ranking_time,
        overall_position=r.overall_position,
        gender_position=r.gender_position,
        category=r.entry.category or "",
        category_position=r.category_position,
        splits=[
            {
                "split": str(s.split),
                "read": str(s.read),
                "at": s.at.isoformat(),
                "elapsed_us": s.elapsed // timedelta(microseconds=1),
            }
            for s in r.splits
        ],
        missing_splits=[str(s) for s in r.missing_splits],
        flags=sorted(r.flags),
        computed_at=now,
    )
