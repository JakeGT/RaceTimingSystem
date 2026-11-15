# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The adapter around ByteTrack: what the crossing pipeline relies on, not ByteTrack itself."""

import pytest

from racevision.geometry import Box
from racevision.tracker import Detection, Tracker

FPS = 30


def person(x: float, y: float = 300, score: float = 0.9) -> Detection:
    return Detection(Box(x, y, x + 80, y + 240), score, "person")


def run(tracker: Tracker, frames: list[list[Detection]], start: int = 0) -> list[list[int]]:
    """Track ids matched in each frame, ordered by box x."""
    out = []
    for i, dets in enumerate(frames, start):
        update = tracker.update(i / FPS, dets)
        out.append([tr.id for tr in sorted(update.matched, key=lambda tr: tr.box.x1)])
    return out


class TestTracker:
    def test_follows_a_runner_once_confirmed(self) -> None:
        ids = run(Tracker(), [[person(100 + 12 * i)] for i in range(30)])
        assert ids[0] == []  # a track needs two matches before it gets an id
        assert {i for frame in ids[1:] for i in frame} == {ids[1][0]}

    def test_history_and_score(self) -> None:
        tracker = Tracker()
        run(tracker, [[person(100 + 12 * i, score=0.9 if i < 5 else 0.4)] for i in range(8)])
        [track] = tracker.tracks
        assert track.hits == 7  # every matched frame since it got an id
        assert track.box == Box(184, 300, 264, 540)
        assert track.score == pytest.approx(0.4)  # kept by ByteTrack's low-score pass

    def test_gap_and_estimate_while_hidden(self) -> None:
        """Hidden for 10 frames while moving 15 px a frame: ByteTrack keeps the track."""
        tracker = Tracker()
        frames = [[person(100 + 15 * i)] if not 20 <= i < 30 else [] for i in range(40)]
        ids = run(tracker, frames[:25])
        [track] = tracker.tracks
        assert track.missed == 5
        assert track.estimate.x1 > track.box.x1  # predicted on past where it was last seen
        ids += run(tracker, frames[25:31], start=25)
        assert track.gap == 10 and track.missed == 0  # seen again at frame 30
        ids += run(tracker, frames[31:], start=31)
        assert len({i for frame in ids for i in frame}) == 1
        assert track.gap == 0

    def test_lost_too_long_ends_the_track(self) -> None:
        tracker = Tracker(lost_seconds=0.5)
        run(tracker, [[person(100)]] * 5)
        assert tracker.update(5 / FPS, []).ended == []
        ended = tracker.update(5 / FPS + 0.6, []).ended
        assert len(ended) == 1
        assert tracker.tracks == []

    def test_low_score_detections_never_start_tracks(self) -> None:
        ids = run(Tracker(), [[person(100 + 12 * i, score=0.3)] for i in range(10)])
        assert ids == [[]] * 10

    def test_frames_out_of_order(self) -> None:
        tracker = Tracker()
        tracker.update(1.0, [person(100)])
        with pytest.raises(ValueError, match="time order"):
            tracker.update(0.5, [person(100)])

    def test_finish_ends_everything(self) -> None:
        tracker = Tracker()
        run(tracker, [[person(100), person(600)]] * 3)
        assert len(tracker.finish()) == 2
        assert tracker.tracks == []
