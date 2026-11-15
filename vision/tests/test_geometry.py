# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from racevision.geometry import Box, Homography, Point
from tests.scene import ANGLED, IN_PLANE, Camera

coords = st.floats(min_value=-1000, max_value=1000, allow_nan=False)


class TestBox:
    def test_measures(self) -> None:
        box = Box(10, 20, 30, 60)
        assert (box.width, box.height, box.area) == (20, 40, 800)
        assert box.centre == Point(20, 40)
        assert box.bottom_centre == Point(20, 60)

    def test_overlap(self) -> None:
        a, b = Box(0, 0, 10, 10), Box(5, 0, 15, 10)
        assert a.iou(b) == pytest.approx(50 / 150)
        assert Box(2, 2, 4, 4).fraction_inside(a) == 1
        assert Box(8, 0, 12, 10).fraction_inside(a) == pytest.approx(0.5)
        assert a.iou(Box(20, 20, 30, 30)) == 0

    def test_negative_size_rejected(self) -> None:
        with pytest.raises(ValueError):
            Box(10, 0, 0, 10)

    def test_shifted_never_negative(self) -> None:
        assert Box(0, 0, 10, 10).shifted(5, 5, -50, -50).area == 0

    @given(coords, coords, coords, coords)
    def test_iou_symmetric_and_bounded(self, x: float, y: float, w: float, h: float) -> None:
        a = Box(0, 0, 100, 100)
        b = Box(x, y, x + abs(w), y + abs(h))
        assert a.iou(b) == pytest.approx(b.iou(a))
        assert 0 <= a.iou(b) <= 1


class TestHomography:
    def test_maps_the_four_points_exactly(self) -> None:
        src = [Point(100, 900), Point(1800, 880), Point(1300, 400), Point(500, 420)]
        dst = [Point(0, 0), Point(8, 0), Point(8, 30), Point(0, 30)]
        h = Homography.from_points(src, dst)
        for s, d in zip(src, dst, strict=True):
            mapped = h.apply(s)
            assert mapped is not None
            assert math.dist(mapped, d) < 1e-9

    @pytest.mark.parametrize("camera", [IN_PLANE, ANGLED], ids=["in_plane", "angled"])
    @given(x=st.floats(-3, 3), y=st.floats(0, 8))
    def test_recovers_ground_positions_through_a_camera(
        self, camera: Camera, x: float, y: float
    ) -> None:
        cones = [(-2.0, 0.0), (2.0, 0.0), (2.0, 8.0), (-2.0, 8.0)]
        h = Homography.from_points(
            [camera.must_project((cx, cy, 0)) for cx, cy in cones],
            [Point(cx, cy) for cx, cy in cones],
        )
        mapped = h.apply(camera.must_project((x, y, 0)))
        assert mapped is not None
        assert math.dist(mapped, (x, y)) < 1e-6

    def test_points_above_the_horizon_have_no_ground_position(self) -> None:
        cones = [(-2.0, 0.0), (2.0, 0.0), (2.0, 8.0), (-2.0, 8.0)]
        h = Homography.from_points(
            [ANGLED.must_project((cx, cy, 0)) for cx, cy in cones],
            [Point(cx, cy) for cx, cy in cones],
        )
        assert h.apply(Point(960, 0)) is None  # the sky

    def test_degenerate_points(self) -> None:
        with pytest.raises(ValueError, match="degenerate"):
            Homography.from_points(
                [Point(0, 0), Point(1, 1), Point(2, 2), Point(3, 3)],
                [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)],
            )
