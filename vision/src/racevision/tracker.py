# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A small ByteTrack-style tracker (Zhang et al. 2022), written for this project.

Each frame, tracks are first matched to confident detections, then to the leftover low-score
ones, which keeps a runner tracked while they're partly hidden. Motion is predicted at constant
velocity in time rather than frames, because phones drop frames and duty-cycle the camera.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from racevision.geometry import Box


@dataclass(frozen=True, slots=True)
class Detection:
    box: Box
    score: float
    label: str


@dataclass(slots=True)
class Track:
    id: int
    history: list[tuple[float, Box]]
    """(time, box) for every frame the track was detected in."""
    hits: int = 1
    score: float = 1.0
    """Detector score of the latest match. Low means partly hidden."""
    missed: int = 0
    """Frames in a row without a match, up to now."""
    gap: int = 0
    """Frames without a match just before the latest one."""
    cost: float = 0.0
    """`match_cost` of the latest match. High means the box jumped: maybe someone else."""
    velocity: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    """Change per second of centre x, centre y, width and height."""

    @property
    def last_seen(self) -> float:
        return self.history[-1][0]

    @property
    def box(self) -> Box:
        return self.history[-1][1]

    def predict(self, t: float) -> Box:
        dt = t - self.last_seen
        vx, vy, vw, vh = self.velocity
        return self.box.shifted(vx * dt, vy * dt, vw * dt, vh * dt)

    def add(self, t: float, box: Box, score: float, smoothing: float, cost: float = 0.0) -> None:
        dt = t - self.last_seen
        if dt > 0:
            prev = self.box
            measured = (
                (box.centre.x - prev.centre.x) / dt,
                (box.centre.y - prev.centre.y) / dt,
                (box.width - prev.width) / dt,
                (box.height - prev.height) / dt,
            )
            s = 1.0 if self.hits == 1 else smoothing
            (m0, m1, m2, m3), (v0, v1, v2, v3) = measured, self.velocity
            self.velocity = (
                s * m0 + (1 - s) * v0,
                s * m1 + (1 - s) * v1,
                s * m2 + (1 - s) * v2,
                s * m3 + (1 - s) * v3,
            )
        self.history.append((t, box))
        self.hits += 1
        self.score = score
        self.cost = cost
        self.gap, self.missed = self.missed, 0


@dataclass(frozen=True, slots=True)
class TrackerUpdate:
    matched: list[Track]
    """Tracks detected in this frame."""
    ended: list[Track]
    """Tracks dropped in this frame, after being lost too long."""


@dataclass
class Tracker:
    high_score: float = 0.5
    low_score: float = 0.1
    new_track_score: float = 0.6
    match_iou: float = 0.2
    max_lost_seconds: float = 1.0
    smoothing: float = 0.5
    _tracks: list[Track] = field(default_factory=list)
    _next_id: int = 1

    @property
    def tracks(self) -> list[Track]:
        return list(self._tracks)

    def update(self, t: float, detections: Sequence[Detection]) -> TrackerUpdate:
        if self._tracks and t <= max(tr.last_seen for tr in self._tracks):
            raise ValueError("Frames must arrive in time order.")
        high = [d for d in detections if d.score >= self.high_score]
        low = [d for d in detections if self.low_score <= d.score < self.high_score]
        predicted = {tr.id: tr.predict(t) for tr in self._tracks}

        pairs, unmatched_tracks, unmatched_high = _match(
            self._tracks, high, predicted, self.match_iou
        )
        # ByteTrack's second pass: established tracks may take a low-score detection.
        established = [tr for tr in unmatched_tracks if tr.hits > 1]
        more, _, _ = _match(established, low, predicted, self.match_iou)
        pairs += more

        matched: list[Track] = []
        for track, det in pairs:
            cost = match_cost(predicted[track.id], det.box)
            track.add(t, det.box, det.score, self.smoothing, cost)
            matched.append(track)
        for det in unmatched_high:
            if det.score >= self.new_track_score:
                track = Track(id=self._next_id, history=[(t, det.box)], score=det.score)
                self._next_id += 1
                self._tracks.append(track)
                matched.append(track)

        matched_ids = {tr.id for tr in matched}
        ended = [
            tr
            for tr in self._tracks
            if tr.id not in matched_ids
            # A track seen once and not again was probably a false detection.
            and (tr.hits == 1 or t - tr.last_seen > self.max_lost_seconds)
        ]
        ended_ids = {tr.id for tr in ended}
        self._tracks = [tr for tr in self._tracks if tr.id not in ended_ids]
        for tr in self._tracks:
            if tr.id not in matched_ids:
                tr.missed += 1
        return TrackerUpdate(matched=matched, ended=ended)

    def finish(self) -> list[Track]:
        """End every track (the clip is over)."""
        ended, self._tracks = self._tracks, []
        return ended


def match_cost(predicted: Box, detected: Box) -> float:
    """How unlike each other two boxes are: 0 for identical, growing without limit.

    Overlap alone confuses runners who overlap in the image. Runners in different lanes are at
    different distances from the camera, so their boxes differ in height and in where their feet
    are, and those terms keep them apart.
    """
    h = max(predicted.height, 1e-6)
    size = abs(math.log(max(detected.height, 1e-6) / h))
    feet = abs(detected.y2 - predicted.y2) / h
    return (1 - predicted.iou(detected)) + 2 * size + 2 * feet


def _match(
    tracks: Sequence[Track],
    detections: Sequence[Detection],
    predicted: dict[int, Box],
    min_iou: float,
) -> tuple[list[tuple[Track, Detection]], list[Track], list[Detection]]:
    """The cheapest one-to-one matching, among pairs that overlap at least `min_iou`."""
    cost = [
        [
            match_cost(predicted[tr.id], det.box)
            if predicted[tr.id].iou(det.box) >= min_iou
            else _NO_MATCH
            for det in detections
        ]
        for tr in tracks
    ]
    found = [(ti, di) for ti, di in assign(cost) if cost[ti][di] < _NO_MATCH]
    used_t = {ti for ti, _ in found}
    used_d = {di for _, di in found}
    pairs = [(tracks[ti], detections[di]) for ti, di in found]
    rest_t = [tr for i, tr in enumerate(tracks) if i not in used_t]
    rest_d = [d for i, d in enumerate(detections) if i not in used_d]
    return pairs, rest_t, rest_d


_NO_MATCH = 1e6


def assign(cost: Sequence[Sequence[float]]) -> list[tuple[int, int]]:
    """Minimum-cost assignment of rows to columns (the Hungarian method, O(n^3)).

    Every row is matched if there are at least as many columns as rows, and vice versa.
    """
    rows = len(cost)
    cols = len(cost[0]) if rows else 0
    if rows == 0 or cols == 0:
        return []
    if rows > cols:
        return [(r, c) for c, r in assign([list(col) for col in zip(*cost, strict=True)])]
    # Shortest augmenting paths with potentials, 1-indexed, after e-maxx.
    inf = math.inf
    u = [0.0] * (rows + 1)
    v = [0.0] * (cols + 1)
    owner = [0] * (cols + 1)
    way = [0] * (cols + 1)
    for r in range(1, rows + 1):
        owner[0] = r
        c0 = 0
        best = [inf] * (cols + 1)
        used = [False] * (cols + 1)
        while True:
            used[c0] = True
            r0, delta, c1 = owner[c0], inf, 0
            for c in range(1, cols + 1):
                if not used[c]:
                    reduced = cost[r0 - 1][c - 1] - u[r0] - v[c]
                    if reduced < best[c]:
                        best[c], way[c] = reduced, c0
                    if best[c] < delta:
                        delta, c1 = best[c], c
            for c in range(cols + 1):
                if used[c]:
                    u[owner[c]] += delta
                    v[c] -= delta
                else:
                    best[c] -= delta
            c0 = c1
            if owner[c0] == 0:
                break
        while c0:
            c1 = way[c0]
            owner[c0] = owner[c1]
            c0 = c1
    return [(owner[c] - 1, c - 1) for c in range(1, cols + 1) if owner[c]]
