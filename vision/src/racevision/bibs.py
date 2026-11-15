# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Which person a bib belongs to, and what a track's bib says once every reading is counted."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import lru_cache

from racevision.geometry import Box

BIB_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,16}$")
"""The device protocol's bib rule (protocol/README.md)."""
MAX_CANDIDATES = 5
"""The protocol accepts at most five candidates per observation."""


@dataclass(frozen=True, slots=True)
class Reading:
    """One guess from the recogniser for one bib crop."""

    text: str
    confidence: float


@dataclass(frozen=True, slots=True)
class Candidate:
    bib: str
    confidence: float


def normalise(text: str) -> str | None:
    text = text.strip().upper().replace(" ", "")
    return text if BIB_PATTERN.match(text) else None


def assign_bibs(
    people: Sequence[Box],
    bibs: Sequence[Box],
    *,
    min_inside: float = 0.7,
    min_margin: float = 0.15,
) -> dict[int, int]:
    """Map bib index to person index.

    A bib belongs to a person whose box contains it, preferring the one it's most central in.
    When two people fit about equally well (one runner in front of another), the bib is left
    unassigned: reading it for the wrong person would be worse than skipping a frame.
    """
    out: dict[int, int] = {}
    for bi, bib in enumerate(bibs):
        scores = sorted(
            (
                (
                    bib.fraction_inside(person)
                    - abs(bib.centre.x - person.centre.x) / person.width,
                    pi,
                )
                for pi, person in enumerate(people)
                if person.width > 0 and bib.fraction_inside(person) >= min_inside
            ),
            reverse=True,
        )
        if scores and (len(scores) == 1 or scores[0][0] - scores[1][0] >= min_margin):
            out[bi] = scores[0][1]
    return out


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


class BibList:
    """The bibs registered for the event, for snapping noisy readings to real ones."""

    def __init__(self, bibs: Iterable[str], max_distance: int = 1) -> None:
        if max_distance not in (0, 1):
            raise ValueError("max_distance must be 0 or 1: two edits on a 3-digit bib is a guess.")
        self.bibs = frozenset(b for b in (normalise(x) for x in bibs) if b)
        self.max_distance = max_distance
        self.near = lru_cache(maxsize=4096)(self._near)

    def _near(self, text: str) -> tuple[tuple[str, int], ...]:
        """Registered bibs within `max_distance` edits of `text`."""
        if text in self.bibs:
            return ((text, 0),)
        return tuple(
            (bib, d)
            for bib in self.bibs
            if abs(len(bib) - len(text)) <= self.max_distance
            and (d := edit_distance(text, bib)) <= self.max_distance
        )


DISTANCE_WEIGHT = (1.0, 0.3)
"""How much a reading counts towards a registered bib 0 or 1 edits away."""
UNREGISTERED_WEIGHT = 0.5
"""How much a reading counts towards itself when it matches no registered bib."""
PRIOR = 1.0
"""Pseudo-count, so one confident reading isn't treated as certainty."""


@dataclass
class BibVotes:
    """Every reading of one track's bib, combined.

    For each frame, every bib a reading could mean gets that reading's confidence (less if it's
    an edit away, and only its best reading counts per frame). Confidence is a bib's share of all
    the evidence seen, so it grows as consistent frames add up.
    """

    bibs: BibList | None = None
    frames: int = 0
    _scores: defaultdict[str, float] = field(default_factory=lambda: defaultdict(float))
    _mass: float = 0.0

    def add(self, readings: Sequence[Reading]) -> None:
        frame: dict[str, float] = {}
        mass = 0.0
        for reading in readings:
            text = normalise(reading.text)
            c = min(max(reading.confidence, 0.0), 1.0)
            if text is None or c == 0:
                continue
            mass += c
            near = self.bibs.near(text) if self.bibs else ()
            if near:
                for bib, d in near:
                    frame[bib] = max(frame.get(bib, 0.0), c * DISTANCE_WEIGHT[d])
            else:
                weight = UNREGISTERED_WEIGHT if self.bibs else 1.0
                frame[text] = max(frame.get(text, 0.0), c * weight)
        if not frame:
            return
        self.frames += 1
        self._mass += min(mass, 1.0)
        for bib, score in frame.items():
            self._scores[bib] += score

    def candidates(self) -> list[Candidate]:
        ranked = sorted(self._scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            Candidate(bib, round(score / (self._mass + PRIOR), 3))
            for bib, score in ranked[:MAX_CANDIDATES]
        ]

    @property
    def best(self) -> Candidate | None:
        found = self.candidates()
        return found[0] if found else None
