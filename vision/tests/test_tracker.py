# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest

from racevision.geometry import Box
from racevision.tracker import Detection, Tracker

FPS = 30


def person(x: float, y: float = 300, score: float = 0.9) -> Detection:
    return Detection(Box(x, y, x + 80, y + 240), score, "person")


def run(tracker: Tracker, frames: list[list[Detection]]) -> list[list[int]]:
    """Track ids matched in each frame, ordered by detection x."""
    out = []
    for i, dets in enumerate(frames):
        update = tracker.update(i / FPS, dets)
        out.append([tr.id for tr in sorted(update.matched, key=lambda tr: tr.box.x1)])
    return out


class TestTracker:
    def test_follows_a_runner(self) -> None:
        ids = run(Tracker(), [[person(100 + 12 * i)] for i in range(30)])
        assert ids == [[1]] * 30

    def test_two_runners_crossing_paths_keep_their_ids(self) -> None:
        """One runner overtakes another; in between, their boxes overlap heavily."""
        tracker = Tracker()
        frames = [[person(100 + 20 * i, 300), person(400 + 8 * i, 330)] for i in range(60)]
        run(tracker, frames)
        a, b = sorted(tracker.tracks, key=lambda tr: tr.id)
        assert a.box.x1 == pytest.approx(100 + 20 * 59)  # the faster one stayed id 1
        assert b.box.x1 == pytest.approx(400 + 8 * 59)
        assert len(a.history) == len(b.history) == 60

    def test_survives_a_gap_using_predicted_motion(self) -> None:
        """Hidden for 10 frames (a third of a second) while moving 15 px a frame."""
        frames = [[person(100 + 15 * i)] if not 20 <= i < 30 else [] for i in range(50)]
        ids = run(Tracker(), frames)
        assert {i for frame in ids for i in frame} == {1}

    def test_lost_too_long_ends_the_track(self) -> None:
        tracker = Tracker(max_lost_seconds=0.5)
        run(tracker, [[person(100)]] * 5)
        update = tracker.update(5 / FPS, [])
        assert update.ended == []
        update = tracker.update(5 / FPS + 0.6, [])
        assert [tr.id for tr in update.ended] == [1]

    def test_partly_hidden_runner_kept_by_low_score_detections(self) -> None:
        frames = [[person(100 + 12 * i, score=0.9 if i < 10 else 0.3)] for i in range(30)]
        ids = run(Tracker(), frames)
        assert ids == [[1]] * 30

    def test_low_score_detections_never_start_tracks(self) -> None:
        ids = run(Tracker(), [[person(100 + 12 * i, score=0.3)] for i in range(10)])
        assert ids == [[]] * 10

    def test_one_frame_false_detection_is_dropped(self) -> None:
        tracker = Tracker()
        tracker.update(0, [person(100)])
        update = tracker.update(1 / FPS, [])
        assert [tr.id for tr in update.ended] == [1]
        assert tracker.tracks == []

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
