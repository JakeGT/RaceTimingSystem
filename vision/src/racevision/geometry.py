# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Points, boxes and the image-to-ground homography. Image coordinates are pixels, y down."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple


class Point(NamedTuple):
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Box:
    """An axis-aligned box: left, top, right, bottom."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError(f"Box has negative size: {self}")

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def centre(self) -> Point:
        return Point((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def bottom_centre(self) -> Point:
        """Roughly the point on the ground under a standing person."""
        return Point((self.x1 + self.x2) / 2, self.y2)

    @property
    def corners(self) -> tuple[Point, Point, Point, Point]:
        return (
            Point(self.x1, self.y1),
            Point(self.x2, self.y1),
            Point(self.x2, self.y2),
            Point(self.x1, self.y2),
        )

    @property
    def bottom_corners(self) -> tuple[Point, Point]:
        return Point(self.x1, self.y2), Point(self.x2, self.y2)

    def intersection(self, other: Box) -> float:
        w = min(self.x2, other.x2) - max(self.x1, other.x1)
        h = min(self.y2, other.y2) - max(self.y1, other.y1)
        return w * h if w > 0 and h > 0 else 0.0

    def iou(self, other: Box) -> float:
        inter = self.intersection(other)
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0

    def fraction_inside(self, other: Box) -> float:
        """How much of this box lies inside `other`, from 0 to 1."""
        return self.intersection(other) / self.area if self.area > 0 else 0.0

    def shifted(self, dx: float, dy: float, dw: float = 0.0, dh: float = 0.0) -> Box:
        """Moved by (dx, dy) and grown by (dw, dh) about its centre. Never below zero size."""
        cx, cy = self.centre
        w = max(self.width + dw, 0.0)
        h = max(self.height + dh, 0.0)
        return Box(cx + dx - w / 2, cy + dy - h / 2, cx + dx + w / 2, cy + dy + h / 2)

    @classmethod
    def around(cls, points: Sequence[Point]) -> Box:
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(min(xs), min(ys), max(xs), max(ys))


Matrix3 = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


@dataclass(frozen=True, slots=True)
class Homography:
    """A plane-to-plane projective map, e.g. image pixels to metres on the ground."""

    matrix: Matrix3

    @classmethod
    def from_points(cls, src: Sequence[Point], dst: Sequence[Point]) -> Homography:
        """The map taking four `src` points to four `dst` points (no three in a line)."""
        if len(src) != 4 or len(dst) != 4:
            raise ValueError("A homography needs exactly four point pairs.")
        rows: list[list[float]] = []
        for (x, y), (u, v) in zip(src, dst, strict=True):
            rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
            rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
        h = [*_solve(rows), 1.0]
        # Scale so w > 0 on the side of the horizon the points are on. apply() rejects the other.
        x, y = src[0]
        if h[6] * x + h[7] * y + h[8] < 0:
            h = [-v for v in h]
        return cls(((h[0], h[1], h[2]), (h[3], h[4], h[5]), (h[6], h[7], h[8])))

    def apply(self, p: Point) -> Point | None:
        """`p` mapped through the homography, or None for points on the horizon or beyond it."""
        (a, b, c), (d, e, f), (g, h, i) = self.matrix
        w = g * p.x + h * p.y + i
        if w <= 1e-12:
            return None
        return Point((a * p.x + b * p.y + c) / w, (d * p.x + e * p.y + f) / w)


def _solve(rows: list[list[float]]) -> list[float]:
    """Gaussian elimination with partial pivoting on an augmented n x (n+1) matrix."""
    n = len(rows)
    m = [row[:] for row in rows]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            raise ValueError("The points are degenerate (three of them are in a line).")
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(col + 1, n):
            factor = m[r][col] / m[col][col]
            for k in range(col, n + 1):
                m[r][k] -= factor * m[col][k]
    out = [0.0] * n
    for r in range(n - 1, -1, -1):
        out[r] = (m[r][n] - sum(m[r][k] * out[k] for k in range(r + 1, n))) / m[r][r]
    return out
