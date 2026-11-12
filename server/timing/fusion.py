# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fusion: turn observations into reads (rebuild plan §6, fusion v1).

Each new observation is matched to the bibs entered in the event and then either
merged into an existing read (same timing point, same bib, within MERGE_WINDOW, from
any device) or turned into a new read. Anything uncertain becomes a read that needs
review rather than being dropped.

Fusion v2 (Phase 5) will weigh devices against each other. v1 already merges
sightings from several phones, which is enough for a second camera to back up the first.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.db import transaction

from events.models import Entry, Event
from timing.models import Observation, Read

MERGE_WINDOW = timedelta(seconds=2)
LOW_CONFIDENCE = 0.6
AMBIGUITY_MARGIN = 0.15


@dataclass(frozen=True)
class Decision:
    bib: str
    state: Read.State
    reason: str = ""
    suggested_bib: str = ""
    confidence: float | None = None


def decide(candidates: Sequence[dict[str, Any]], entered: set[str]) -> Decision:
    """Pick a bib for one observation. Pure, so it's easy to test and tune.

    Candidates for bibs nobody has entered are ignored ("snapping" to the entry list):
    if a phone reads 1Z34 then 1234, and only 1234 is entered, 1234 is the answer.
    """
    ranked = sorted(candidates, key=lambda c: c["confidence"], reverse=True)
    if not ranked:
        return Decision("", Read.State.NEEDS_REVIEW, Read.ReviewReason.UNREADABLE)
    plausible = [c for c in ranked if c["bib"] in entered]
    if not plausible:
        top = ranked[0]
        return Decision(
            "",
            Read.State.NEEDS_REVIEW,
            Read.ReviewReason.NOT_ENTERED,
            suggested_bib=top["bib"],
            confidence=top["confidence"],
        )
    best = plausible[0]
    bib, confidence = best["bib"], best["confidence"]
    if confidence < LOW_CONFIDENCE:
        return Decision(
            bib, Read.State.NEEDS_REVIEW, Read.ReviewReason.LOW_CONFIDENCE, bib, confidence
        )
    if len(plausible) > 1 and confidence - plausible[1]["confidence"] < AMBIGUITY_MARGIN:
        return Decision(bib, Read.State.NEEDS_REVIEW, Read.ReviewReason.AMBIGUOUS, bib, confidence)
    return Decision(bib, Read.State.AUTO, confidence=confidence)


def _median_time(times: Iterable[datetime]) -> datetime:
    ordered = sorted(times)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return ordered[mid - 1] + (ordered[mid] - ordered[mid - 1]) / 2


def fuse_pending(event: Event) -> set[UUID]:
    """Fuse every observation in the event that isn't in a read yet.

    Safe to run any number of times: observations already in a read are skipped.
    Returns the ids of timing points that got new or changed reads.
    """
    entered = set(Entry.objects.filter(event=event).values_list("bib", flat=True))
    touched: set[UUID] = set()
    with transaction.atomic():
        # One fusion run per event at a time (a row lock on Postgres; SQLite only has
        # one writer anyway), so two uploads can't both create a read for one crossing.
        Event.objects.select_for_update().filter(pk=event.pk).first()
        pending = Observation.objects.filter(event=event, read__isnull=True).order_by(
            "captured_at", "id"
        )
        for obs in pending:
            decision = decide(obs.candidates, entered)
            target = _merge_target(obs, decision) if decision.bib else None
            obs.read = target or Read.objects.create(
                event=event,
                timing_point_id=obs.timing_point_id,
                bib=decision.bib,
                at=obs.captured_at,
                state=decision.state,
                review_reason=decision.reason,
                suggested_bib=decision.suggested_bib,
                confidence=decision.confidence,
            )
            obs.save(update_fields=["read"])
            if target is not None:
                _absorb(target, decision)
            touched.add(obs.timing_point_id)
    return touched


def _merge_target(obs: Observation, decision: Decision) -> Read | None:
    """Rejected reads count too: a late upload from a second phone shouldn't bring
    back a crossing someone has already thrown out."""
    return (
        Read.objects.filter(
            timing_point_id=obs.timing_point_id,
            bib=decision.bib,
            at__gte=obs.captured_at - MERGE_WINDOW,
            at__lte=obs.captured_at + MERGE_WINDOW,
        )
        .order_by("at")
        .first()
    )


def _absorb(read: Read, decision: Decision) -> None:
    """Update a read after another device's sighting joined it."""
    if read.state in (Read.State.CONFIRMED, Read.State.MANUAL, Read.State.REJECTED):
        return  # a person has decided: leave their time and bib alone
    times = read.observations.values_list("captured_at", flat=True)
    read.at = _median_time(times)
    if decision.confidence is not None:
        read.confidence = max(read.confidence or 0.0, decision.confidence)
    if read.state == Read.State.NEEDS_REVIEW and decision.state == Read.State.AUTO:
        # A second device is sure where the first wasn't.
        read.state = Read.State.AUTO
        read.review_reason = ""
    read.save(update_fields=["at", "confidence", "state", "review_reason", "updated_at"])
