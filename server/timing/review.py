# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Every change a person makes to timing data goes through here.

Each function changes one thing, writes an Adjustment row saying who changed what
from what, and rebuilds the races it affects, all in one transaction. The admin and
(later) the review console and the venue laptop all call these, never the models.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from events.models import Entry, Event, TimingPoint, Wave
from results.services import races_using, rebuild_race
from timing.models import Adjustment, Read


class ReviewError(ValueError):
    """The change doesn't make sense; the message says why, for showing to staff."""


@dataclass(frozen=True)
class Actor:
    """Who made a change. `user` is empty for people and processes without accounts."""

    label: str
    user: User | None = None

    @classmethod
    def of(cls, user: User) -> "Actor":
        return cls(label=user.get_username(), user=user)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _read_state(read: Read) -> dict[str, Any]:
    return {"bib": read.bib, "at": _iso(read.at), "state": read.state}


def _log(
    event_id: Any,
    action: Adjustment.Action,
    by: Actor,
    before: dict[str, Any],
    after: dict[str, Any],
    reason: str,
    **target: Any,
) -> Adjustment:
    return Adjustment.objects.create(
        event_id=event_id,
        action=action,
        actor=by.user,
        actor_label=by.label,
        before=before,
        after=after,
        reason=reason,
        **target,
    )


def _require_reason(reason: str) -> str:
    reason = reason.strip()
    if not reason:
        raise ReviewError("Say why: this change shows in the audit log.")
    return reason


def _check_entered(event_id: Any, bib: str) -> str:
    bib = bib.strip()
    if not Entry.objects.filter(event_id=event_id, bib=bib).exists():
        raise ReviewError(f"Nobody in this event has bib {bib!r}.")
    return bib


def _rebuild_point(timing_point_id: Any) -> None:
    for race in races_using([timing_point_id]):
        rebuild_race(race)


@transaction.atomic
def _change_read(
    read: Read, action: Adjustment.Action, by: Actor, reason: str, **changes: Any
) -> Read:
    read = Read.objects.select_for_update().get(pk=read.pk)
    before = _read_state(read)
    for name, value in changes.items():
        setattr(read, name, value)
    read.save()
    _log(read.event_id, action, by, before, _read_state(read), reason, read=read)
    _rebuild_point(read.timing_point_id)
    return read


def confirm_read(read: Read, by: Actor, reason: str = "") -> Read:
    if not read.bib:
        raise ReviewError("This read has no bib yet. Assign one instead.")
    return _change_read(
        read,
        Adjustment.Action.READ_CONFIRMED,
        by,
        reason,
        state=Read.State.CONFIRMED,
        review_reason="",
    )


def reject_read(read: Read, by: Actor, reason: str = "") -> Read:
    return _change_read(
        read, Adjustment.Action.READ_REJECTED, by, reason, state=Read.State.REJECTED
    )


def assign_bib(read: Read, bib: str, by: Actor, reason: str = "") -> Read:
    """Set or correct the bib. That's a person's decision, so the read is confirmed."""
    return _change_read(
        read,
        Adjustment.Action.READ_BIB_CHANGED,
        by,
        reason,
        bib=_check_entered(read.event_id, bib),
        state=Read.State.CONFIRMED,
        review_reason="",
    )


def adjust_time(read: Read, at: datetime, by: Actor, reason: str) -> Read:
    reason = _require_reason(reason)
    state = read.state if read.state == Read.State.MANUAL else Read.State.CONFIRMED
    return _change_read(read, Adjustment.Action.READ_TIME_CHANGED, by, reason, at=at, state=state)


@transaction.atomic
def add_manual_read(
    event: Event, timing_point: TimingPoint, bib: str, at: datetime, by: Actor, reason: str
) -> Read:
    """For crossings no camera caught: a timekeeper's stopwatch, a marshal's note."""
    reason = _require_reason(reason)
    if timing_point.event_id != event.pk:
        raise ReviewError("That timing point belongs to another event.")
    read = Read.objects.create(
        event=event,
        timing_point=timing_point,
        bib=_check_entered(event.pk, bib),
        at=at,
        state=Read.State.MANUAL,
    )
    _log(event.pk, Adjustment.Action.READ_ADDED, by, {}, _read_state(read), reason, read=read)
    _rebuild_point(timing_point.pk)
    return read


@transaction.atomic
def set_entry_status(entry: Entry, status: Entry.Status, by: Actor, reason: str = "") -> Entry:
    entry = Entry.objects.select_for_update().get(pk=entry.pk)
    if status == Entry.Status.DSQ:
        reason = _require_reason(reason)
    before = {"status": entry.status, "status_reason": entry.status_reason}
    entry.status = status
    entry.status_reason = reason
    entry.save(update_fields=["status", "status_reason", "updated_at"])
    _log(
        entry.event_id,
        Adjustment.Action.ENTRY_STATUS_CHANGED,
        by,
        before,
        {"status": entry.status, "status_reason": entry.status_reason},
        reason,
        entry=entry,
    )
    rebuild_race(entry.race)
    return entry


@transaction.atomic
def start_wave(wave: Wave, by: Actor, at: datetime | None = None, reason: str = "") -> Wave:
    """Record the gun. `at` defaults to now; pass a time to correct a start."""
    wave = Wave.objects.select_for_update().get(pk=wave.pk)
    if wave.start_at is not None:
        reason = _require_reason(reason)  # changing a recorded start moves every time
    before = {"start_at": _iso(wave.start_at)}
    wave.start_at = at or timezone.now()
    wave.save(update_fields=["start_at", "updated_at"])
    _log(
        wave.event_id,
        Adjustment.Action.WAVE_STARTED,
        by,
        before,
        {"start_at": _iso(wave.start_at)},
        reason,
        wave=wave,
    )
    rebuild_race(wave.race)
    return wave
