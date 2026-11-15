# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""People tracking: ByteTrack (Zhang et al. 2022), from Roboflow's `trackers` (Apache-2.0).

This module only adapts it. Boxes go in with their sensor timestamps, so ByteTrack's Kalman
filter predicts by elapsed time, which copes with dropped frames and a slowed-down camera. What
comes back is kept per track in the form the crossing pipeline needs: every box the track was
matched to, plus a few signals the pipeline uses to decide when a track's identity is in doubt.

It reads ByteTrack's live tracks (`tracks`, `get_state_bbox()`) for where hidden tracks are,
which isn't documented API, so `trackers` is pinned to 2.7.x.

Which tracker the phones run is decided in slice 2.2 by comparing ByteTrack, OC-SORT, BoT-SORT,
C-BIoU and ByteTraX's changes on race footage (ADR 0003).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

import numpy as np
import supervision as sv
from trackers import ByteTrackTracker

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
    """(time, box) for every frame the track was matched in."""
    score: float
    """Detector score of the latest match. Low means partly hidden."""
    estimate: Box
    """ByteTrack's own estimate of the box this frame: where a hidden track probably is."""
    missed: int = 0
    """Frames in a row without a match, up to now."""
    gap: int = 0
    """Frames without a match just before the latest one."""

    @property
    def hits(self) -> int:
        return len(self.history)

    @property
    def last_seen(self) -> float:
        return self.history[-1][0]

    @property
    def box(self) -> Box:
        return self.history[-1][1]


@dataclass(frozen=True, slots=True)
class TrackerUpdate:
    matched: list[Track]
    """Tracks detected in this frame."""
    ended: list[Track]
    """Tracks ByteTrack has given up on: lost for longer than `lost_seconds`."""


@dataclass
class Tracker:
    """ByteTrack with our boxes and timestamps. Its defaults, except `lost_seconds`."""

    high_score: float = 0.6
    """Detections at or above this are matched first; the rest only rescue existing tracks."""
    new_track_score: float = 0.7
    min_iou: float = 0.1
    min_frames: int = 2
    """Matches in a row before a track gets an id."""
    lost_seconds: float = 1.0
    _bytetrack: ByteTrackTracker = field(init=False)
    _tracks: dict[int, Track] = field(default_factory=dict)
    _last_t: float | None = None

    def __post_init__(self) -> None:
        self._bytetrack = ByteTrackTracker(
            lost_track_buffer=round(self.lost_seconds * 30),  # it counts 30 fps frames
            track_activation_threshold=self.new_track_score,
            minimum_consecutive_frames=self.min_frames,
            minimum_iou_threshold=self.min_iou,
            high_conf_det_threshold=self.high_score,
        )

    @property
    def tracks(self) -> list[Track]:
        """Every live track, including ones hidden this frame."""
        return list(self._tracks.values())

    def update(self, t: float, detections: Sequence[Detection]) -> TrackerUpdate:
        if self._last_t is not None and t <= self._last_t:
            raise ValueError("Frames must arrive in time order.")
        self._last_t = t
        result = self._bytetrack.update(_to_supervision(detections), timestamp=t)

        matched: list[Track] = []
        ids = result.tracker_id if result.tracker_id is not None else np.empty(0, dtype=int)
        confidences = result.confidence if result.confidence is not None else np.ones(len(ids))
        for xyxy, confidence, tid in zip(result.xyxy, confidences, ids, strict=True):
            if tid < 0:
                continue  # not a track yet (or a stray low-score box)
            box = _box(xyxy)
            track = self._tracks.get(int(tid))
            if track is None:
                track = Track(id=int(tid), history=[], score=0.0, estimate=box)
                self._tracks[track.id] = track
            track.history.append((t, box))
            track.score = float(confidence)
            track.gap, track.missed = track.missed, 0
            matched.append(track)

        estimates = {
            int(tr.tracker_id): _box(tr.get_state_bbox())
            for tr in self._bytetrack.tracks
            if tr.tracker_id >= 0
        }
        matched_ids = {tr.id for tr in matched}
        ended: list[Track] = []
        for track in list(self._tracks.values()):
            if track.id in estimates:
                track.estimate = estimates[track.id]
            if track.id in matched_ids:
                continue
            track.missed += 1
            if track.id not in estimates:  # ByteTrack has dropped it
                ended.append(self._tracks.pop(track.id))
        return TrackerUpdate(matched=matched, ended=ended)

    def finish(self) -> list[Track]:
        """End every track (the clip is over)."""
        ended = list(self._tracks.values())
        self._tracks.clear()
        self._bytetrack.reset()
        self._last_t = None
        return ended


def _box(xyxy: Iterable[float]) -> Box:
    """A box from ByteTrack. Its estimate for a lost track can shrink past zero size, so a
    side that has crossed over collapses to the midpoint."""
    x1, y1, x2, y2 = (float(v) for v in xyxy)
    if x2 < x1:
        x1 = x2 = (x1 + x2) / 2
    if y2 < y1:
        y1 = y2 = (y1 + y2) / 2
    return Box(x1, y1, x2, y2)


def _to_supervision(detections: Sequence[Detection]) -> sv.Detections:
    if not detections:
        return sv.Detections.empty()
    return sv.Detections(
        xyxy=np.array([[d.box.x1, d.box.y1, d.box.x2, d.box.y2] for d in detections], dtype=float),
        confidence=np.array([d.score for d in detections], dtype=float),
        class_id=np.zeros(len(detections), dtype=int),
    )
