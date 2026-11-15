# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""From per-frame detections to observations: one per tracked object that crosses the line.

The models stay outside: the caller runs the detector on each frame and passes a `recognise`
function that reads one bib crop from that frame. The pipeline only asks it to read bibs of
tracks whose bib isn't confident yet, which is where the battery saving comes from.

Two aims, matching the server's rules (fusion sends reads under 0.6 confidence to review):

- **Don't lose anyone who crosses.** A runner hidden while crossing is joined up with the
  track that vanished just before the line ("stitching"), or, if there isn't one, their time
  is estimated backwards from where their track first appears.
- **Don't send a wrong bib confidently.** When a runner is hidden, partly hidden, overlaps
  someone or jumps unexpectedly, the tracker may have swapped them with someone else. Bib
  readings from before that stop counting ("identity segments") and the bib is read again.
  If identity at the moment of crossing is in doubt, the confidence is cut so it goes to
  review.

Neither is guaranteed: two runners in the same lane, one overtaking the other, can't be told
apart by geometry alone. On synthetic busy finishes (`tests/test_pipeline.py`; a runner every
~0.6 s, often hidden behind each other), 0.25 to 0.45% of runners are lost and about 1 in 800
is sent confidently with the wrong bib. A higher camera helps most. Appearance matching
(re-identification, ADR 0003) is the next step if real footage shows the same.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum

from racevision.bibs import MAX_CANDIDATES, BibList, BibVotes, Candidate, Reading, assign_bibs
from racevision.geometry import Box
from racevision.lines import Crossing, Direction, FinishLine, Position
from racevision.profile import RUNNING, SportProfile
from racevision.tracker import Detection, Track, Tracker

Recogniser = Callable[[Box], Sequence[Reading]]
"""Reads the bib inside `box` in the current frame: guesses, best first."""

DOUBT = 0.5
"""Confidence is multiplied by this when identity is in doubt, which sends it to review."""
OVERLAP = 0.4
"""Two tracks overlapping this much (IoU) might swap identities."""
JUMP = 0.5
"""A track's box changing this much in one frame (`jump`) might mean it's now someone else."""
STITCH_SECONDS = 2.0
"""How long a track that vanished before the line can be joined to one that appears past it."""


class Flag(StrEnum):
    HIDDEN_AT_LINE = "hidden_at_line"
    """The track wasn't cleanly visible on both sides of the crossing."""
    ESTIMATED = "estimated"
    """The track first appeared past the line: the time is extrapolated backwards."""
    IDENTITY_UNCERTAIN = "identity_uncertain"
    """No clean bib reading in the stretch of track around the crossing."""


@dataclass(frozen=True, slots=True)
class Observation:
    """One tracked object crossing the line. Maps onto the device protocol's observation."""

    track_id: int
    at: float
    """When it crossed, interpolated between frames, in the frames' time base."""
    direction: Direction
    candidates: list[Candidate]
    """Bib guesses, best first. Empty when the bib was never read: it goes to review."""
    box: Box
    """The tracked object's box in the frame nearest the crossing, for the crop."""
    frame_time: float
    """That frame's time."""
    bib_reads: int
    """How many times the recogniser ran for this track."""
    flags: frozenset[Flag] = frozenset()

    @property
    def confidence(self) -> float | None:
        return self.candidates[0].confidence if self.candidates else None


@dataclass(slots=True)
class _Segment:
    """A stretch of track with no reason to doubt it's the same person throughout."""

    start: float
    votes: BibVotes


@dataclass(slots=True)
class _TrackState:
    segments: list[_Segment]
    checked: int = 1
    """History index up to which crossings have been looked for."""
    crossing: Crossing | None = None
    flags: set[Flag] = field(default_factory=set)
    sent: bool = False
    reads: int = 0
    in_contact: bool = False
    contact_times: set[float] = field(default_factory=set)
    """Frames where the track was hidden, partly hidden or overlapping another track."""
    retired: bool = False
    """Joined onto a later track, which reports the crossing instead."""
    borrowed: list[_Segment] = field(default_factory=list)
    """Bib readings from the track this one was joined onto, as a fallback."""

    @property
    def votes(self) -> BibVotes:
        return self.segments[-1].votes

    def segment_at(self, t: float) -> _Segment:
        return next(s for s in reversed(self.segments) if s.start <= t or s is self.segments[0])


@dataclass
class CrossingPipeline:
    line: FinishLine
    profile: SportProfile = RUNNING
    bibs: BibList | None = None
    tracker: Tracker = field(default_factory=Tracker)
    _states: dict[int, _TrackState] = field(default_factory=dict)
    _vanished: dict[int, tuple[Track, _TrackState]] = field(default_factory=dict)
    """Recently ended tracks that never crossed, for stitching."""
    _estimates: list[tuple[float, float]] = field(default_factory=list)
    """(time, along) of crossings estimated for vanished tracks, so a late track that turns
    out to be the same runner isn't counted twice."""

    @classmethod
    def for_event(
        cls, line: FinishLine, bibs: Iterable[str], profile: SportProfile = RUNNING
    ) -> CrossingPipeline:
        return cls(line=line, profile=profile, bibs=BibList(bibs))

    def update(
        self,
        t: float,
        detections: Sequence[Detection],
        recognise: Recogniser | None = None,
    ) -> list[Observation]:
        """Feed one frame, even an empty one. Returns the observations that are finished."""
        p = self.profile
        tracked = [d for d in detections if d.label == p.tracked_label]
        update = self.tracker.update(t, tracked)
        self._note_contact(t, update.matched)

        if recognise is not None and p.identity_label is not None:
            ids = [d.box for d in detections if d.label == p.identity_label]
            people = [track.box for track in update.matched]
            for bib_index, person_index in assign_bibs(people, ids).items():
                state = self._state(update.matched[person_index])
                if not state.sent and not state.in_contact and not self._confident(state):
                    state.votes.add(recognise(ids[bib_index]))
                    state.reads += 1

        out: list[Observation] = []
        for track in update.matched:
            out.extend(self._look_for_crossing(track))
        for track in self.tracker.tracks:  # including ones briefly lost this frame
            waiting = self._states.get(track.id)
            if waiting is None or waiting.crossing is None or waiting.sent:
                continue
            if self._ready(waiting, waiting.crossing, t):
                out.append(self._send(track, waiting, waiting.crossing))
        for track in update.ended:
            out.extend(self._end(track))
        for tid, (gone, gone_state) in list(self._vanished.items()):
            if t - gone.last_seen > STITCH_SECONDS:
                del self._vanished[tid]
                out.extend(self._vanished_before_line(gone, gone_state))
        return out

    def finish(self) -> list[Observation]:
        """The clip is over: send everything still waiting for a bib."""
        out: list[Observation] = []
        for track in self.tracker.finish():
            out.extend(self._end(track))
            if track.missed == 0:  # still in view at the end: not hidden, just not there yet
                self._vanished.pop(track.id, None)
        for gone, gone_state in self._vanished.values():
            out.extend(self._vanished_before_line(gone, gone_state))
        self._vanished.clear()
        return out

    def _vanished_before_line(self, track: Track, state: _TrackState) -> list[Observation]:
        """The last resort for someone hidden at the line and never seen again (or seen too
        late to join up): a track that vanished just before the line, heading for it, gets an
        estimated crossing for review. A false one costs a click; a lost finisher costs a
        result."""
        if state.retired or state.crossing is not None:
            return []
        last_t, last_box = track.history[-1]
        last = self.line.position(last_box, self.profile.anchor)
        recent = [(t, b) for t, b in track.history if t >= last_t - 0.5]
        first_t, first_box = recent[0]
        first = self.line.position(first_box, self.profile.anchor)
        if last is None or first is None or last_t <= first_t or not self.line.within(last.along):
            return []
        speed = (last.distance - first.distance) / (last_t - first_t)
        if speed <= 0 or last.distance >= 0 or -last.distance / speed > STITCH_SECONDS:
            return []  # not heading for the line, or too slow to have reached it
        at = last_t - last.distance / speed
        crossing = Crossing(at=at, along=last.along, direction=Direction.FORWARD)
        state.flags = {Flag.ESTIMATED, Flag.HIDDEN_AT_LINE}
        self._estimates = [(et, ea) for et, ea in self._estimates if at - et < 4 * STITCH_SECONDS]
        self._estimates.append((at, last.along))
        return [self._send(track, state, crossing)]

    def _state(self, track: Track) -> _TrackState:
        if track.id not in self._states:
            first = track.history[0][0]
            self._states[track.id] = _TrackState(segments=[_Segment(first, BibVotes(self.bibs))])
        return self._states[track.id]

    def _note_contact(self, t: float, matched: list[Track]) -> None:
        """Mark tracks whose identity might have swapped in this frame, and start new segments
        for tracks coming out of such a stretch."""
        for track in matched:
            state = self._state(track)
            # Hidden tracks count too, where they're predicted to be: a runner the detector
            # can't see right now is exactly the one this track might swap with.
            touching = any(
                other is not track
                and _overlapping(track.box, other.box if other in matched else other.estimate)
                for other in self.tracker.tracks
            )
            contact = (
                touching
                or track.gap > 0
                or track.score < self.tracker.high_score
                or (track.hits > 2 and jump(expected(track), track.box) > JUMP)
            )
            if contact:
                state.contact_times.add(t)
            elif state.in_contact:
                state.segments.append(_Segment(t, BibVotes(self.bibs)))
            state.in_contact = contact

    def _confident(self, state: _TrackState) -> bool:
        best = state.votes.best
        return best is not None and best.confidence >= self.profile.confident_at

    def _ready(self, state: _TrackState, crossing: Crossing, t: float) -> bool:
        if self.profile.identity_label is None or t - crossing.at >= self.profile.hold_seconds:
            return True
        # Only the segment around the crossing counts, and it must be the one still growing.
        segment = state.segment_at(crossing.at)
        return segment is state.segments[-1] and self._confident(state)

    def _look_for_crossing(self, track: Track) -> list[Observation]:
        """Find the track's crossing. Returns anything that had to be sent early."""
        if track.hits < self.profile.min_track_hits:
            return []
        state = self._state(track)
        if state.retired:
            return []
        if state.checked == 1 and state.crossing is None:
            self._check_late_start(track, state)
        out: list[Observation] = []
        history = track.history
        for i in range(state.checked, len(history)):
            (t0, b0), (t1, b1) = history[i - 1], history[i]
            p0 = self.line.position(b0, self.profile.anchor)
            p1 = self.line.position(b1, self.profile.anchor)
            if p0 is None or p1 is None:
                continue
            crossing = self.line.crossing(t0, p0, t1, p1)
            if crossing is None:
                continue
            doubtful = t0 in state.contact_times or t1 in state.contact_times
            if crossing.direction is Direction.FORWARD and state.crossing is None:
                state.crossing = crossing
                state.flags = {Flag.HIDDEN_AT_LINE} if doubtful else set()
            elif crossing.direction is Direction.REVERSE and state.crossing and doubtful:
                # Back over the line while overlapping someone: the track has probably jumped
                # to a runner who hasn't finished. Send what we have and look again.
                if not state.sent:
                    out.append(self._send(track, state, state.crossing))
                state.crossing, state.sent, state.flags = None, False, set()
        state.checked = len(history)
        return out

    def _check_late_start(self, track: Track, state: _TrackState) -> None:
        """A track that starts past the line: someone who crossed while hidden.

        If a track vanished just before the line, the two are joined and the crossing is
        interpolated across the gap. Otherwise, if it starts close to the line and is heading
        on, the crossing is extrapolated backwards from its speed.
        """
        (t0, b0), (t1, b1) = track.history[0], track.history[-1]
        p0 = self.line.position(b0, self.profile.anchor)
        if p0 is None or p0.distance <= 0 or not self.line.within(p0.along):
            return
        donor = self._find_donor(track, t0, p0)
        if donor is not None:
            (dt, dp), donor_state = donor
            crossing = self.line.crossing(dt, dp, t0, p0)
            if crossing is not None:
                donor_state.retired = True
                state.crossing = crossing
                state.flags.add(Flag.HIDDEN_AT_LINE)
                state.borrowed = donor_state.segments
                return
        p1 = self.line.position(b1, self.profile.anchor)
        if p1 is None or t1 <= t0:
            return
        speed = (p1.distance - p0.distance) / (t1 - t0)
        if speed <= 0 or p0.distance / speed > STITCH_SECONDS:
            return  # not heading on, or too far past to have crossed while we were watching
        at = t0 - p0.distance / speed
        state.crossing = Crossing(at=at, along=p0.along, direction=Direction.FORWARD)
        state.flags.update({Flag.ESTIMATED, Flag.HIDDEN_AT_LINE})
        if any(abs(at - et) < 1.0 and abs(p0.along - ea) < 0.15 for et, ea in self._estimates):
            state.sent = True  # already sent when their old track vanished

    def _find_donor(
        self, track: Track, t0: float, p0: Position
    ) -> tuple[tuple[float, Position], _TrackState] | None:
        """The vanished track, last seen before the line, nearest along it to where `track`
        appeared."""
        options: list[tuple[float, tuple[float, Position], _TrackState]] = []
        hidden = [
            (tr, self._states[tr.id])
            for tr in self.tracker.tracks
            if tr is not track and tr.missed > 0 and tr.id in self._states
        ]
        for other, other_state in [*hidden, *self._vanished.values()]:
            last_t, last_box = other.history[-1]
            if other_state.retired or other_state.crossing is not None:
                continue
            if not 0 < t0 - last_t <= STITCH_SECONDS:
                continue
            last = self.line.position(last_box, self.profile.anchor)
            if last is None or last.distance >= 0 or not self.line.within(last.along):
                continue
            options.append((abs(last.along - p0.along), (last_t, last), other_state))
        if not options:
            return None
        _, seen, donor_state = min(options, key=lambda o: o[0])
        return seen, donor_state

    def _send(self, track: Track, state: _TrackState, crossing: Crossing) -> Observation:
        state.sent = True
        frame_time, box = min(track.history, key=lambda tb: abs(tb[0] - crossing.at))
        candidates = state.segment_at(crossing.at).votes.candidates()
        flags = set(state.flags)
        if not candidates:
            # No clean reading around the crossing: offer what the rest of the track saw.
            pooled: dict[str, float] = {}
            for segment in [*state.segments, *state.borrowed]:
                for c in segment.votes.candidates():
                    pooled[c.bib] = max(pooled.get(c.bib, 0.0), c.confidence)
            ranked = sorted(pooled.items(), key=lambda kv: -kv[1])
            candidates = [Candidate(bib, c) for bib, c in ranked[:MAX_CANDIDATES]]
            if candidates:
                flags.add(Flag.IDENTITY_UNCERTAIN)
        if flags:
            candidates = [replace(c, confidence=round(c.confidence * DOUBT, 3)) for c in candidates]
        return Observation(
            track_id=track.id,
            at=crossing.at,
            direction=crossing.direction,
            candidates=candidates,
            box=box,
            frame_time=frame_time,
            bib_reads=state.reads,
            flags=frozenset(flags),
        )

    def _end(self, track: Track) -> list[Observation]:
        out = self._look_for_crossing(track)
        state = self._states.pop(track.id, None)
        if state is not None and state.crossing is None and not state.retired:
            self._vanished[track.id] = (track, state)
        if state is None or state.crossing is None or state.sent:
            return out
        return [*out, self._send(track, state, state.crossing)]


def expected(track: Track) -> Box:
    """Where the latest box should be if the track kept moving as over its two previous
    matches. ByteTrack's own prediction isn't exposed after its update."""
    (t0, a), (t1, b), (t2, _) = track.history[-3:]
    k = (t2 - t1) / (t1 - t0)
    return b.shifted(
        k * (b.centre.x - a.centre.x),
        k * (b.centre.y - a.centre.y),
        k * (b.width - a.width),
        k * (b.height - a.height),
    )


def jump(before: Box, after: Box) -> float:
    """How far a box is from where it was expected: 0 for exactly there.

    Runners in different lanes are at different distances from the camera, so if a track has
    jumped to someone else, the box usually changes height and the feet move, not just the
    overlap.
    """
    h = max(before.height, 1e-6)
    size = abs(math.log(max(after.height, 1e-6) / h))
    feet = abs(after.y2 - before.y2) / h
    return (1 - before.iou(after)) + 2 * size + 2 * feet


def _overlapping(a: Box, b: Box) -> bool:
    return a.iou(b) >= OVERLAP or a.fraction_inside(b) >= 0.3 or b.fraction_inside(a) >= 0.3
