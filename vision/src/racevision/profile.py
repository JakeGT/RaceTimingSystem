# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sport profiles: what to track, which part of it to time, and what identifies it (ADR 0003)."""

from dataclasses import dataclass
from enum import StrEnum


class Anchor(StrEnum):
    """Which part of the tracked object is timed."""

    TORSO = "torso"
    """Athletics: the torso. Box centre with an in-plane camera, bottom centre on the ground."""
    FRONT = "front"
    """Cycling, wheelchair racing, rowing: the leading edge of the box."""


@dataclass(frozen=True, slots=True)
class SportProfile:
    name: str
    tracked_label: str
    """Detector class that gets tracked and timed."""
    identity_label: str | None
    """Detector class that identifies a track (a bib), or None if identity comes from elsewhere."""
    anchor: Anchor
    min_track_hits: int = 3
    """Detections before a track counts. Filters one-off false detections."""
    hold_seconds: float = 2.5
    """How long after crossing to keep reading the bib before the crossing is sent anyway."""
    confident_at: float = 0.8
    """Stop reading a track's bib once its best candidate reaches this confidence."""


RUNNING = SportProfile(
    name="running", tracked_label="person", identity_label="bib", anchor=Anchor.TORSO
)
