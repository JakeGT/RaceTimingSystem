# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fixtures for fusion and review: a 10K with a finish split, two phones and entries."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pytest

from events.models import Entry, Event, Gender, Race, Split, TimingPoint, Wave
from timing.models import Device, Observation, PairingCode
from timing.review import Actor

GUN = datetime(2026, 6, 14, 9, 0, tzinfo=UTC)


class MakeObservation(Protocol):
    def __call__(
        self, bibs: dict[str, float], seconds: float, device: Device | None = None
    ) -> Observation: ...


@pytest.fixture
def finish(race: Race, finish_line: TimingPoint) -> Split:
    return Split.objects.create(race=race, timing_point=finish_line, kind=Split.Kind.FINISH)


@pytest.fixture
def started(wave: Wave) -> Wave:
    wave.start_at = GUN
    wave.save()
    return wave


@pytest.fixture
def entries(race: Race, wave: Wave) -> dict[str, Entry]:
    people = [
        ("101", "Ada", Gender.FEMALE, 30),
        ("102", "Ben", Gender.MALE, 45),
        ("103", "Cal", Gender.MALE, 25),
        ("108", "Dee", Gender.FEMALE, 50),
    ]
    return {
        bib: Entry.objects.create(
            race=race, wave=wave, bib=bib, given_name=name, gender=g, declared_age=age
        )
        for bib, name, g, age in people
    }


def _device(event: Event, point: TimingPoint, name: str) -> Device:
    pairing, _ = PairingCode.issue(event, point)
    return Device.pair(pairing, name=name)[0]


@pytest.fixture
def phones(event: Event, finish_line: TimingPoint) -> tuple[Device, Device]:
    return _device(event, finish_line, "Left"), _device(event, finish_line, "Right")


@pytest.fixture
def observe(phones: tuple[Device, Device], finish_line: TimingPoint) -> MakeObservation:
    def make(bibs: dict[str, float], seconds: float, device: Device | None = None) -> Observation:
        device = device or phones[0]
        at = GUN + timedelta(seconds=seconds)
        return Observation.objects.create(
            id=uuid.uuid7(),
            event_id=device.event_id,
            device=device,
            timing_point=finish_line,
            captured_at_device=at,
            clock_offset_ms=0,
            captured_at=at,
            candidates=[{"bib": b, "confidence": c} for b, c in bibs.items()],
        )

    return make


@pytest.fixture
def referee() -> Actor:
    return Actor(label="Chief timekeeper")


def as_seconds(value: Any) -> float:
    return float((value - GUN).total_seconds())
