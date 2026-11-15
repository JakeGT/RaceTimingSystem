# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The whole crossing pipeline on synthetic finishes with known answers."""

import random
from dataclasses import dataclass

import numpy as np
import pytest
from scipy.optimize import linear_sum_assignment

from racevision.geometry import Box
from racevision.lines import Direction
from racevision.pipeline import (
    JUMP,
    CrossingPipeline,
    Flag,
    Observation,
    Recogniser,
    expected,
    jump,
)
from racevision.profile import RUNNING, Anchor, SportProfile
from racevision.tracker import Track
from tests.scene import ANGLED, HIGH, Camera, Person, Scene

AUTO = 0.6
"""The server accepts reads at this confidence without review (timing.fusion.LOW_CONFIDENCE)."""


def run(
    scene: Scene, pipeline: CrossingPipeline, recognise: Recogniser | None = None
) -> list[Observation]:
    out: list[Observation] = []
    for t, detections in scene.frames():
        out += pipeline.update(t, detections, recognise)
    return out + pipeline.finish()


def field(seed: int, runners: int = 16, gap: float = 0.6) -> list[Person]:
    """Runners arriving every `gap` seconds or so, anywhere across an 8 m finish."""
    rng = random.Random(seed)
    people = []
    for n in range(runners):
        speed = rng.uniform(3.0, 6.5)
        arrive = 2.0 + n * gap + rng.uniform(-0.2, 0.2)
        y = rng.uniform(0.7, 7.3)
        people.append(Person(x0=-speed * arrive, y=y, speed=speed, bib=str(101 + n)))
    return people


@dataclass
class Score:
    lost: int = 0
    """Finishers with no observation within 0.5 s."""
    extra: int = 0
    """Observations with no finisher."""
    confident_wrong: int = 0
    """Observations the server would accept without review, with the wrong bib or time."""
    auto: int = 0
    observations: int = 0
    worst_error: float = 0.0
    """Largest timing error among observations accepted without review."""

    def add(self, people: list[Person], observations: list[Observation]) -> None:
        cost = [
            [d if (d := abs(o.at - p.crosses_at)) < 0.5 else 1e6 for o in observations]
            for p in people
        ]
        pairs: list[tuple[int, int]] = []
        if observations:
            rows, cols = linear_sum_assignment(np.array(cost))
            pairs = [(r, c) for r, c in zip(rows.tolist(), cols.tolist(), strict=True)]
        pairs = [(r, c) for r, c in pairs if cost[r][c] < 1e6]
        self.lost += len(people) - len(pairs)
        self.extra += len(observations) - len(pairs)
        self.observations += len(observations)
        by_bib = {p.bib: p for p in people}
        for o in observations:
            if o.confidence is None or o.confidence < AUTO:
                continue
            self.auto += 1
            p = by_bib.get(o.candidates[0].bib)
            if p is None or abs(o.at - p.crosses_at) > 0.1:
                self.confident_wrong += 1
            else:
                self.worst_error = max(self.worst_error, abs(o.at - p.crosses_at))


def race(camera: Camera, people: list[Person], seed: int, seconds: float = 16) -> list[Observation]:
    scene = Scene(camera, people, seconds=seconds, jitter=1.5, seed=seed)
    pipeline = CrossingPipeline.for_event(camera.ground_line(), [p.bib or "" for p in people])
    return run(scene, pipeline, scene.reader(correct=0.6))


class TestFinish:
    def test_spread_out_finish_is_all_timed_and_identified(self) -> None:
        people = field(seed=1, runners=8, gap=1.5)
        observations = race(ANGLED, people, seed=1, seconds=18)
        assert len(observations) == len(people)
        for o in observations:
            [p] = [p for p in people if o.candidates and p.bib == o.candidates[0].bib]
            assert o.at == pytest.approx(p.crosses_at, abs=0.08)
            assert o.direction is Direction.FORWARD
            assert o.confidence is not None and o.confidence >= AUTO
            assert not o.flags

    @pytest.mark.parametrize(
        ("camera", "max_lost", "max_extra", "max_wrong", "min_auto"),
        [(ANGLED, 4, 8, 1, 0.82), (HIGH, 2, 2, 1, 0.87)],
        ids=["camera_2.5m", "camera_4.5m"],
    )
    def test_busy_finishes(
        self, camera: Camera, max_lost: int, max_extra: int, max_wrong: int, min_auto: float
    ) -> None:
        """A regression guard, not an accuracy claim: 25 busy finishes (400 runners, one
        every ~0.6 s, often hidden behind each other). The limits are what this code
        measured plus a little headroom. Slice 2.2's harness replaces this with real footage."""
        score = Score()
        for seed in range(1, 26):
            people = field(seed)
            score.add(people, race(camera, people, seed))
        assert score.lost <= max_lost
        assert score.extra <= max_extra
        assert score.confident_wrong <= max_wrong
        assert score.auto / score.observations >= min_auto
        assert score.worst_error < 0.09

    def test_reading_stops_once_confident(self) -> None:
        person = Person(x0=-20, y=4, speed=4, bib="42")
        scene = Scene(ANGLED, [person], seconds=8)
        pipeline = CrossingPipeline.for_event(ANGLED.ground_line(), ["42"])
        [obs] = run(scene, pipeline, scene.reader(correct=1.0))
        assert obs.bib_reads < len(scene.bib_reads) / 4
        assert obs.candidates[0].bib == "42"

    def test_bib_hidden_at_the_line_is_read_elsewhere(self) -> None:
        person = Person(x0=-16, y=4, speed=4, bib="42", bib_hidden=lambda t: abs(t - 4) < 1)
        scene = Scene(ANGLED, [person], seconds=8)
        pipeline = CrossingPipeline.for_event(ANGLED.ground_line(), ["42"])
        [obs] = run(scene, pipeline, scene.reader(correct=1.0))
        assert obs.candidates[0].bib == "42"
        assert obs.at == pytest.approx(4.0, abs=0.08)

    def test_bib_never_seen_still_timed_for_review(self) -> None:
        person = Person(x0=-16, y=4, speed=4, bib=None)
        scene = Scene(ANGLED, [person], seconds=8)
        pipeline = CrossingPipeline.for_event(ANGLED.ground_line(), ["42"])
        [obs] = run(scene, pipeline, scene.reader())
        assert obs.candidates == [] and obs.confidence is None
        assert obs.at == pytest.approx(4.0, abs=0.08)
        assert obs.frame_time == pytest.approx(4.0, abs=1 / 30)

    @pytest.mark.parametrize("hidden_for", [0.3, 1.2, 2.0])
    def test_hidden_while_crossing_is_still_timed(self, hidden_for: float) -> None:
        """Short gaps are bridged by the tracker, longer ones by stitching tracks together.
        Either way the time is interpolated across the gap and sent for review."""
        person = Person(
            x0=-16, y=4, speed=4, bib="42", hidden=lambda t: abs(t - 4) < hidden_for / 2
        )
        scene = Scene(ANGLED, [person], seconds=8)
        pipeline = CrossingPipeline.for_event(ANGLED.ground_line(), ["42"])
        [obs] = run(scene, pipeline, scene.reader(correct=1.0))
        assert obs.at == pytest.approx(4.0, abs=0.1)
        assert Flag.HIDDEN_AT_LINE in obs.flags
        assert obs.candidates[0].bib == "42"
        assert obs.confidence is not None and obs.confidence < AUTO

    def test_not_confident_is_sent_after_the_hold(self) -> None:
        person = Person(x0=-16, y=4, speed=4, bib="42")
        scene = Scene(ANGLED, [person], seconds=12)
        pipeline = CrossingPipeline.for_event(ANGLED.ground_line(), ["42"])
        sent_at = []
        for t, detections in scene.frames():
            # A recogniser that's never sure enough to stop.
            if pipeline.update(t, detections, lambda box: []):
                sent_at.append(t)
        assert sent_at == [pytest.approx(4.0 + RUNNING.hold_seconds, abs=1 / 30)]


class TestNotRunners:
    def test_people_who_dont_finish_are_ignored(self) -> None:
        bystanders = [
            Person(x0=1.0, y=3.0, speed=0.0),  # standing just past the line
            Person(x0=3.0, y=5.0, speed=-1.2),  # marshal walking back across it
            Person(x0=-8.0, y=11.0, speed=4.0),  # past the end of the line
            Person(x0=-8.0, y=-2.5, speed=4.0),  # before the start of it
        ]
        scene = Scene(ANGLED, bystanders, seconds=6)
        assert run(scene, CrossingPipeline(line=ANGLED.ground_line())) == []

    def test_brief_false_detection_is_ignored(self) -> None:
        pipeline = CrossingPipeline(line=ANGLED.ground_line())
        scene = Scene(ANGLED, [Person(x0=-0.5, y=4, speed=5)], seconds=0.1)  # 3 frames
        assert run(scene, pipeline) == []


def test_profile_without_identity_sends_straight_away() -> None:
    profile = SportProfile(
        name="test", tracked_label="person", identity_label=None, anchor=Anchor.FRONT
    )
    pipeline = CrossingPipeline(line=ANGLED.ground_line(), profile=profile)
    scene = Scene(ANGLED, [Person(x0=-16, y=4, speed=4)], seconds=8)
    sent_at = [t for t, d in scene.frames() if pipeline.update(t, d)]
    assert sent_at == [pytest.approx(4.0, abs=0.1)]


class TestJump:
    def track(self, *boxes: Box) -> Track:
        history = [(i / 30, box) for i, box in enumerate(boxes)]
        return Track(id=1, history=history, score=0.9, estimate=boxes[-1])

    def test_steady_runner_coming_closer_is_expected(self) -> None:
        """Moving right and growing, at an uneven frame rate: no jump."""
        a, b = Box(100, 200, 140, 300), Box(110, 198, 152, 303)
        c = Box(130, 194, 176, 309)  # twice the time step, twice the change
        track = self.track(a, b, c)
        track.history[-1] = (3 / 30, c)
        assert jump(expected(track), c) == pytest.approx(0, abs=1e-9)

    def test_switch_to_someone_at_another_depth_is_a_jump(self) -> None:
        a, b = Box(100, 200, 140, 300), Box(110, 200, 150, 300)
        nearer = Box(118, 190, 168, 340)  # overlaps a lot, but bigger and feet lower
        assert jump(expected(self.track(a, b, nearer)), nearer) > JUMP
