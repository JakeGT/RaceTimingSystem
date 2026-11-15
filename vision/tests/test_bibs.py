# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import random

import pytest
from hypothesis import given
from hypothesis import strategies as st

from racevision.bibs import (
    BibList,
    BibVotes,
    Reading,
    assign_bibs,
    edit_distance,
    normalise,
)
from racevision.geometry import Box

RUNNER = Box(100, 100, 200, 400)
BIB = Box(130, 180, 170, 220)


class TestAssignBibs:
    def test_bib_inside_a_person(self) -> None:
        assert assign_bibs([Box(500, 100, 600, 400), RUNNER], [BIB]) == {0: 1}

    def test_bib_outside_everyone(self) -> None:
        assert assign_bibs([RUNNER], [Box(300, 180, 340, 220)]) == {}

    def test_overlapping_runners_prefer_the_one_its_centred_on(self) -> None:
        behind = Box(150, 90, 250, 390)  # bib is inside both, but at the edge of this one
        assert assign_bibs([behind, RUNNER], [BIB]) == {0: 1}

    def test_too_close_to_call_is_skipped(self) -> None:
        twin = Box(101, 100, 201, 400)
        assert assign_bibs([RUNNER, twin], [BIB]) == {}


bibs = st.text(alphabet="0123456789", min_size=1, max_size=5)


class TestEditDistance:
    @given(bibs, bibs)
    def test_symmetric_and_bounded(self, a: str, b: str) -> None:
        d = edit_distance(a, b)
        assert d == edit_distance(b, a)
        assert abs(len(a) - len(b)) <= d <= max(len(a), len(b))
        assert (d == 0) == (a == b)

    def test_examples(self) -> None:
        assert edit_distance("123", "128") == 1
        assert edit_distance("123", "1234") == 1
        assert edit_distance("123", "321") == 2


def test_normalise() -> None:
    assert normalise(" a12 ") == "A12"
    assert normalise("12/3") is None
    assert normalise("") is None


class TestBibVotes:
    def test_consistent_readings_become_confident(self) -> None:
        votes = BibVotes(BibList(["123", "456"]))
        confidence = []
        for _ in range(6):
            votes.add([Reading("123", 0.8)])
            best = votes.best
            assert best is not None and best.bib == "123"
            confidence.append(best.confidence)
        assert confidence == sorted(confidence)
        assert confidence[0] < 0.5 < 0.8 < confidence[-1]

    def test_a_misread_digit_snaps_to_the_registered_bib(self) -> None:
        votes = BibVotes(BibList(["123", "456"]))
        votes.add([Reading("128", 0.9)])
        [only] = votes.candidates()
        assert only.bib == "123"

    def test_noisy_readings_still_find_the_truth(self) -> None:
        rng = random.Random(7)
        registered = [str(n) for n in range(100, 400)]
        votes = BibVotes(BibList(registered))
        for _ in range(12):
            if rng.random() < 0.5:
                votes.add([Reading("247", 0.6)])
            else:
                votes.add([Reading(rng.choice(["241", "277", "347", "24"]), 0.5)])
        best = votes.best
        assert best is not None and best.bib == "247"

    def test_unregistered_bib_still_reported(self) -> None:
        votes = BibVotes(BibList(["123"]))
        votes.add([Reading("9999", 0.9)])
        [only] = votes.candidates()
        assert only.bib == "9999"
        assert only.confidence < 0.3

    def test_no_bib_list(self) -> None:
        votes = BibVotes()
        votes.add([Reading("77", 0.9), Reading("71", 0.1)])
        assert [c.bib for c in votes.candidates()] == ["77", "71"]

    def test_at_most_five_candidates(self) -> None:
        votes = BibVotes()
        votes.add([Reading(str(n), 0.1) for n in range(10)])
        assert len(votes.candidates()) == 5

    def test_junk_is_ignored(self) -> None:
        votes = BibVotes()
        votes.add([Reading("??", 0.9), Reading("12", 0)])
        assert votes.candidates() == []
        assert votes.frames == 0

    @given(st.lists(st.tuples(bibs, st.floats(0, 1)), max_size=20))
    def test_confidence_is_a_probability(self, readings: list[tuple[str, float]]) -> None:
        votes = BibVotes(BibList(["1", "12", "123"]))
        for text, c in readings:
            votes.add([Reading(text, c)])
        for candidate in votes.candidates():
            assert 0 <= candidate.confidence < 1

    def test_two_edits_not_allowed(self) -> None:
        with pytest.raises(ValueError):
            BibList(["1"], max_distance=2)
