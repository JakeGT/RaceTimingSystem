# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Finish lines and the sub-frame moment something crosses one.

A line drawn on the image only gives correct times when the camera sits in the vertical plane of
the finish line. From any other angle, set `to_ground` (a homography from four marked points on
the ground) and give the line in ground coordinates: the bottom centre of the person box is then
timed against the line on the ground, which has no parallax. See ADR 0003.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from racevision.geometry import Box, Homography, Point
from racevision.profile import Anchor


class Direction(StrEnum):
    FORWARD = "forward"
    REVERSE = "reverse"


@dataclass(frozen=True, slots=True)
class Position:
    """Where a tracked object is relative to the line."""

    distance: float
    """Signed distance from the line, positive once past it (pixels, or metres on the ground)."""
    along: float
    """Where along the line: 0 at `start`, 1 at `end`."""


@dataclass(frozen=True, slots=True)
class Crossing:
    at: float
    """Interpolated time of the crossing, in the frames' time base."""
    along: float
    direction: Direction


@dataclass(frozen=True, slots=True)
class FinishLine:
    start: Point
    end: Point
    beyond: Point
    """Any point on the finished side of the line. Sets which way is forward."""
    to_ground: Homography | None = None
    """Image to ground. When set, `start`, `end` and `beyond` are ground coordinates."""
    margin: float = 0.05
    """How far past either end of the line still counts, as a fraction of its length."""

    def __post_init__(self) -> None:
        if self.start == self.end:
            raise ValueError("The line's start and end are the same point.")
        if self._raw_distance(self.beyond) == 0:
            raise ValueError("`beyond` is on the line, so it can't say which side is forward.")

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    def _raw_distance(self, p: Point) -> float:
        (ax, ay), (bx, by) = self.start, self.end
        return ((bx - ax) * (p.y - ay) - (by - ay) * (p.x - ax)) / self.length

    def measure(self, p: Point) -> Position:
        """`p` in the line's own coordinates (image or ground)."""
        sign = 1.0 if self._raw_distance(self.beyond) > 0 else -1.0
        (ax, ay), (bx, by) = self.start, self.end
        along = ((p.x - ax) * (bx - ax) + (p.y - ay) * (by - ay)) / self.length**2
        return Position(sign * self._raw_distance(p), along)

    def position(self, box: Box, anchor: Anchor) -> Position | None:
        """Where the timed part of `box` (in image pixels) is, or None if it can't be placed.

        The distance comes from the timed part (torso or front). `along` always comes from the
        point on the ground under the object: with an in-plane camera every height on the body
        lands on the same image line, so only the feet say where along the line someone is.
        """
        if self.to_ground is None:
            timed = [box.centre] if anchor is Anchor.TORSO else list(box.corners)
            ground_point: Point | None = box.bottom_centre
        else:
            image = [box.bottom_centre] if anchor is Anchor.TORSO else list(box.bottom_corners)
            mapped = [self.to_ground.apply(p) for p in image]
            ground_point = self.to_ground.apply(box.bottom_centre)
            timed = [p for p in mapped if p is not None]
            if len(timed) < len(mapped):
                return None
        if ground_point is None:
            return None
        distance = max(self.measure(p).distance for p in timed)
        return Position(distance=distance, along=self.measure(ground_point).along)

    def within(self, along: float) -> bool:
        return -self.margin <= along <= 1 + self.margin

    def crossing(self, t0: float, p0: Position, t1: float, p1: Position) -> Crossing | None:
        """The crossing between two observations, linearly interpolated, if there is one."""
        if p0.distance < 0 <= p1.distance:
            direction = Direction.FORWARD
        elif p1.distance < 0 <= p0.distance:
            direction = Direction.REVERSE
        else:
            return None
        f = p0.distance / (p0.distance - p1.distance)
        along = p0.along + f * (p1.along - p0.along)
        if not self.within(along):
            return None
        return Crossing(at=t0 + f * (t1 - t0), along=along, direction=direction)
