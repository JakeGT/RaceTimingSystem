# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Line crossing: exact interpolation, direction, the lane, and why parallax needs the ground."""

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from racevision.geometry import Box, Point
from racevision.lines import Direction, FinishLine
from racevision.pipeline import CrossingPipeline
from racevision.profile import Anchor
from tests.scene import ANGLED, IN_PLANE, Camera, Person, Scene


def dot(x: float, y: float) -> Box:
    return Box(x, y, x, y)


VERTICAL = FinishLine(start=Point(500, 100), end=Point(500, 900), beyond=Point(600, 500))


class TestFinishLine:
    def test_signed_distance_and_along(self) -> None:
        pos = VERTICAL.measure(Point(530, 300))
        assert pos.distance == pytest.approx(30)
        assert pos.along == pytest.approx(0.25)
        assert VERTICAL.measure(Point(470, 300)).distance == pytest.approx(-30)

    def test_beyond_sets_forward(self) -> None:
        flipped = FinishLine(start=Point(500, 100), end=Point(500, 900), beyond=Point(400, 500))
        assert flipped.measure(Point(470, 300)).distance == pytest.approx(30)

    def test_bad_lines(self) -> None:
        with pytest.raises(ValueError, match="same point"):
            FinishLine(start=Point(1, 1), end=Point(1, 1), beyond=Point(2, 2))
        with pytest.raises(ValueError, match="on the line"):
            FinishLine(start=Point(0, 0), end=Point(10, 0), beyond=Point(5, 0))

    @given(
        angle=st.floats(0, 2 * math.pi),
        speed=st.floats(0.5, 50),
        fps=st.sampled_from([2.0, 10.0, 30.0, 60.0, 240.0]),
        phase=st.floats(0, 0.999),  # at exactly 1 the first frame is on the line: no crossing
        along=st.floats(0.05, 0.95),
    )
    def test_interpolation_is_exact_for_steady_motion(
        self, angle: float, speed: float, fps: float, phase: float, along: float
    ) -> None:
        """A point at constant velocity: the crossing time is exact at any frame rate."""
        line = FinishLine(start=Point(0, 0), end=Point(100, 0), beyond=Point(50, 10))
        # Cross the line at `along`, heading `angle` off the line's normal (never parallel).
        heading = (math.sin(angle) * 0.9, abs(math.cos(angle)) + 0.1)
        assume(heading[1] > 0.2)
        crossing_point = (100 * along, 0.0)
        cross_time = 10.0

        def at(t: float) -> Point:
            return Point(
                crossing_point[0] + heading[0] * speed * (t - cross_time),
                crossing_point[1] + heading[1] * speed * (t - cross_time),
            )

        t0 = cross_time - (1 - phase) / fps
        t1 = t0 + 1 / fps
        crossing = line.crossing(t0, line.measure(at(t0)), t1, line.measure(at(t1)))
        assert crossing is not None
        assert crossing.direction is Direction.FORWARD
        assert crossing.at == pytest.approx(cross_time, abs=1e-9)
        assert crossing.along == pytest.approx(along, abs=1e-9)

    def test_reverse_and_no_crossing(self) -> None:
        a, b = VERTICAL.measure(Point(510, 500)), VERTICAL.measure(Point(490, 500))
        crossing = VERTICAL.crossing(0, a, 1, b)
        assert crossing is not None and crossing.direction is Direction.REVERSE
        assert VERTICAL.crossing(0, a, 1, a) is None

    def test_outside_the_lane_is_ignored(self) -> None:
        a, b = VERTICAL.measure(Point(490, 990)), VERTICAL.measure(Point(510, 990))
        assert VERTICAL.crossing(0, a, 1, b) is None

    def test_front_anchor_times_the_leading_edge(self) -> None:
        box = Box(480, 300, 520, 500)
        torso = VERTICAL.position(box, Anchor.TORSO)
        front = VERTICAL.position(box, Anchor.FRONT)
        assert torso is not None and front is not None
        assert torso.distance == pytest.approx(0)
        assert front.distance == pytest.approx(20)


def crossings(camera: Camera, line: FinishLine, person: Person) -> list[float]:
    pipeline = CrossingPipeline(line=line)
    scene = Scene(camera, [person], seconds=6)
    found = [o.at for t, d in scene.frames() for o in pipeline.update(t, d)]
    return found + [o.at for o in pipeline.finish()]


RUNS = [(y, v) for y in (1.0, 4.0, 7.0) for v in (3.0, 5.0, 8.0)]


class TestParallax:
    @pytest.mark.parametrize(("y", "speed"), RUNS)
    def test_in_plane_camera_times_the_torso_exactly(self, y: float, speed: float) -> None:
        person = Person(x0=-12, y=y, speed=speed)
        [at] = crossings(IN_PLANE, IN_PLANE.painted_line(), person)
        assert at == pytest.approx(person.crosses_at, abs=0.002)

    @pytest.mark.parametrize(("y", "speed"), RUNS)
    def test_angled_camera_on_the_ground_is_close(self, y: float, speed: float) -> None:
        """Within 0.06 s. The box's bottom edge sits a little ahead of the hips."""
        person = Person(x0=-12, y=y, speed=speed)
        [at] = crossings(ANGLED, ANGLED.ground_line(), person)
        assert at - person.crosses_at == pytest.approx(0, abs=0.06)

    def test_angled_camera_with_a_line_drawn_on_the_image_is_wrong(self) -> None:
        """Why the ground line exists: the drawn line misses runners or is out by ~0.4 s."""
        results = []
        for y, speed in RUNS:
            person = Person(x0=-12, y=y, speed=speed)
            found = crossings(ANGLED, ANGLED.painted_line(), person)
            results.append(abs(found[0] - person.crosses_at) if found else math.inf)
        assert min(results) > 0.2

    @given(
        x=st.floats(3, 15),
        y=st.floats(-15, -3),
        z=st.floats(1.5, 6),
        lane=st.floats(0.5, 7.5),
        speed=st.floats(2, 12),
    )
    def test_a_point_on_the_ground_is_exact_from_any_camera(
        self, x: float, y: float, z: float, lane: float, speed: float
    ) -> None:
        """A runner's foot point, mapped to the ground, crosses exactly when they do."""
        camera = Camera(position=(x, y, z), target=(0.0, 4.0, 0.5))
        line = camera.ground_line()
        t0, t1 = -0.37 / speed, 0.61 / speed  # either side of the true crossing at t = 0
        p0 = line.position(dot(*camera.must_project((-0.37, lane, 0))), Anchor.TORSO)
        p1 = line.position(dot(*camera.must_project((0.61, lane, 0))), Anchor.TORSO)
        assert p0 is not None and p1 is not None
        crossing = line.crossing(t0, p0, t1, p1)
        assert crossing is not None
        # On the ground the motion is linear again, so interpolating ~1 m apart is still exact.
        assert crossing.at == pytest.approx(0, abs=1e-6)
        assert crossing.along == pytest.approx(lane / 8, abs=1e-6)
