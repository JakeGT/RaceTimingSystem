# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Synthetic scenes with known answers: runners as 3D boxes seen through a pinhole camera.

World coordinates are metres: x along the course (runners move towards +x), y across it, z up.
The finish line is x = 0 on the ground, from y = 0 to y = LINE_WIDTH.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from dataclasses import dataclass, field

from racevision.bibs import Reading
from racevision.geometry import Box, Homography, Point
from racevision.lines import FinishLine
from racevision.tracker import Detection

Vec3 = tuple[float, float, float]
LINE_WIDTH = 8.0


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _unit(a: Vec3) -> Vec3:
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


@dataclass(frozen=True)
class Camera:
    position: Vec3
    target: Vec3
    focal: float = 1400.0
    size: tuple[int, int] = (1920, 1080)

    def project(self, p: Vec3) -> Point | None:
        forward = _unit(_sub(self.target, self.position))
        right = _unit(_cross(forward, (0.0, 0.0, 1.0)))
        down = _cross(forward, right)
        d = _sub(p, self.position)
        z = _dot(d, forward)
        if z <= 0.1:
            return None
        cx, cy = self.size[0] / 2, self.size[1] / 2
        return Point(cx + self.focal * _dot(d, right) / z, cy + self.focal * _dot(d, down) / z)

    def must_project(self, p: Vec3) -> Point:
        q = self.project(p)
        if q is None:
            raise ValueError(f"{p} is behind the camera")
        return q

    def painted_line(self) -> FinishLine:
        """The finish line as drawn on the image: only right for an in-plane camera."""
        return FinishLine(
            start=self.must_project((0, 0, 0)),
            end=self.must_project((0, LINE_WIDTH, 0)),
            beyond=self.must_project((2, LINE_WIDTH / 2, 0)),
        )

    def ground_line(self) -> FinishLine:
        """The finish line on the ground, set up from four cones around it."""
        cones = [(-2.0, 0.0), (2.0, 0.0), (2.0, LINE_WIDTH), (-2.0, LINE_WIDTH)]
        image = [self.must_project((x, y, 0)) for x, y in cones]
        return FinishLine(
            start=Point(0, 0),
            end=Point(0, LINE_WIDTH),
            beyond=Point(1, LINE_WIDTH / 2),
            to_ground=Homography.from_points(image, [Point(x, y) for x, y in cones]),
        )


IN_PLANE = Camera(position=(0.0, -6.0, 1.6), target=(0.0, 4.0, 0.9))
"""On the end of the finish line, looking along it: no parallax."""
ANGLED = Camera(position=(7.0, -7.0, 2.5), target=(0.0, 4.0, 0.9))
"""Past the line and off to the side, looking back at the runners as they finish."""
HIGH = Camera(position=(7.0, -7.0, 4.5), target=(0.0, 4.0, 0.9))
"""The same, raised to 4.5 m (a pole or a balcony): runners hide each other less."""


@dataclass(frozen=True)
class Person:
    x0: float
    """Position along the course at time 0."""
    y: float
    speed: float
    """Metres per second along +x. Negative walks backwards."""
    bib: str | None = None
    depth: float = 0.3
    width: float = 0.5
    height: float = 1.75
    bib_hidden: Callable[[float], bool] = lambda t: False
    hidden: Callable[[float], bool] = lambda t: False
    """Times when something not in the scene (a sign, a spectator) hides them completely."""

    def x(self, t: float) -> float:
        return self.x0 + self.speed * t

    @property
    def crosses_at(self) -> float:
        """When the torso's centre reaches x = 0: the true finish time."""
        return -self.x0 / self.speed

    def box(self, camera: Camera, t: float) -> Box | None:
        x, d, w = self.x(t), self.depth / 2, self.width / 2
        corners = [
            (x + dx, self.y + dy, z) for dx in (-d, d) for dy in (-w, w) for z in (0, self.height)
        ]
        return _project_all(camera, corners)

    def bib_box(self, camera: Camera, t: float) -> Box | None:
        if self.bib is None or self.bib_hidden(t):
            return None
        front = self.x(t) + self.depth / 2
        corners = [(front, self.y + dy, z) for dy in (-0.11, 0.11) for z in (1.1, 1.32)]
        return _project_all(camera, corners)


def _project_all(camera: Camera, corners: list[Vec3]) -> Box | None:
    points = [camera.project(c) for c in corners]
    if any(p is None for p in points):
        return None
    return Box.around([p for p in points if p is not None])


@dataclass
class Scene:
    camera: Camera
    people: list[Person]
    fps: float = 30.0
    start: float = 0.0
    seconds: float = 6.0
    jitter: float = 0.0
    """Detection noise, in pixels."""
    seed: int = 0
    bib_reads: dict[Box, str] = field(default_factory=dict)

    def frames(self) -> list[tuple[float, list[Detection]]]:
        """Detections per frame, as a detector would see them.

        A person mostly hidden behind someone nearer the camera isn't detected at all, and a
        partly hidden one is detected with a low score. A bib with anyone nearer in front of it
        isn't detected.
        """
        rng = random.Random(self.seed)
        out = []
        n = round(self.seconds * self.fps)
        for i in range(n):
            t = self.start + i / self.fps
            visible = []
            for person in self.people:
                box = person.box(self.camera, t)
                if box is not None and _on_screen(box, self.camera) and not person.hidden(t):
                    visible.append((self._distance(person, t), person, box))
            visible.sort(key=lambda v: v[0])  # nearest first
            detections = []
            for k, (_, person, box) in enumerate(visible):
                nearer = [b for _, _, b in visible[:k]]
                hidden = max((box.fraction_inside(b) for b in nearer), default=0.0)
                if hidden >= 0.7:
                    continue
                score = 0.9 if hidden < 0.3 else 0.3
                seen = box
                if self.jitter:
                    seen = box.shifted(rng.gauss(0, self.jitter), rng.gauss(0, self.jitter))
                detections.append(Detection(seen, score, "person"))
                bib = person.bib_box(self.camera, t)
                if bib is None or person.bib is None:
                    continue
                if max((bib.fraction_inside(b) for b in nearer), default=0.0) > 0:
                    continue
                detections.append(Detection(bib, 0.8, "bib"))
                self.bib_reads[bib] = person.bib
            out.append((t, detections))
        return out

    def _distance(self, person: Person, t: float) -> float:
        cx, cy, cz = self.camera.position
        return math.dist((cx, cy, cz), (person.x(t), person.y, person.height / 2))

    def reader(
        self, *, correct: float = 0.7, rng: random.Random | None = None
    ) -> Callable[[Box], list[Reading]]:
        """A fake recogniser: right `correct` of the time, otherwise one digit off."""
        rng = rng or random.Random(self.seed)

        def read(box: Box) -> list[Reading]:
            truth = self.bib_reads[box]
            if rng.random() < correct:
                return [Reading(truth, 0.7)]
            i = rng.randrange(len(truth))
            wrong = truth[:i] + str((int(truth[i]) + 1) % 10) + truth[i + 1 :]
            return [Reading(wrong, 0.5)]

        return read


def _on_screen(box: Box, camera: Camera) -> bool:
    w, h = camera.size
    return box.x2 > 0 and box.x1 < w and box.y2 > 0 and box.y1 < h
