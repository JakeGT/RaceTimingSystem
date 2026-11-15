# vision/

The Python reference pipeline (detection, tracking, line crossing, digit recognition, matching readings to registered bibs), training scripts, the synthetic bib generator and the evaluation harness. See [the rebuild plan](../docs/REBUILD_PLAN.md) §6 and Phase 2, and [ADR 0003](../docs/decisions/0003-timing-on-the-tracked-object.md) (time the person, not the bib).

**Licensing rule:** nothing here may import `ultralytics` except code under `tools/legacy/`, which is internal-only (e.g. pre-labelling with the legacy model) and never shipped. CI enforces this. See [ADR 0001](../docs/decisions/0001-licence-and-detector.md). Dataset and model licences are tracked in [datasets.md](datasets.md).

```bash
uv run pytest
```

## The tracking core (`src/racevision/`)

Pure Python with no dependencies, so the phone apps can port it line for line. The models plug in from outside: the caller runs the detector on each frame and passes a function that reads one bib crop.

| Module | What it does |
|---|---|
| `geometry.py` | Boxes, and the homography from four marked points on the ground to metres |
| `profile.py` | Sport profiles: what to track, which part of it to time (torso or front), what identifies it. Only `RUNNING` exists |
| `lines.py` | Finish lines and sub-frame crossing times. A line drawn on the image (camera in the line's plane), or a line on the ground (any other angle) |
| `tracker.py` | A ByteTrack-style tracker: optimal matching with a cost that knows boxes at different depths differ in size and foot position, time-based motion prediction, a second pass for partly hidden people |
| `bibs.py` | Which person a bib belongs to, and combining a track's readings, snapped to the registered bibs |
| `pipeline.py` | Frames in, observations out: one per person who crosses, matching the device protocol |

```python
from racevision.lines import FinishLine
from racevision.pipeline import CrossingPipeline

pipeline = CrossingPipeline.for_event(line, registered_bibs)
for t, detections in frames:  # t: the frame's sensor timestamp, in seconds
    for obs in pipeline.update(t, detections, recognise=lambda box: reader.read(image, box)):
        send(obs)  # obs.at, obs.candidates, obs.box, obs.flags
for obs in pipeline.finish():
    send(obs)
```

## Camera placement

- **In the plane of the finish line** (a tripod on the end of the line, looking along it): draw the line on the image. Times are exact: the torso is timed and parallax can't happen.
- **Anywhere else:** mark four points on the ground around the line (cones) and use a ground line. The bottom centre of each person box is timed on the ground. The box's bottom edge sits about 18 cm ahead of the hips, so times are 0.02–0.06 s early depending on speed (up to 0.08 s with detection noise). The harness will measure that **distance** on real footage, and the correction will be a ground offset in metres, not a time. A line drawn on the image from an angle is wrong by up to ~0.5 s and misses runners.
- **Higher is better.** People hide each other less. On synthetic busy finishes (a runner every ~0.6 s), a camera 2.5 m up lost 0.4% of runners, sent 17% to review and added about 1% extra observations (all at low confidence, so they go to review too); at 4.5 m it lost 0.25% and sent 10% to review.

## What the synthetic tests show, and don't

`tests/scene.py` simulates runners as 3D boxes through a pinhole camera, with a detector that misses people who are mostly hidden. The busy-finish test in `tests/test_pipeline.py` is a **regression guard, not an accuracy claim**. Its limits are the measured numbers plus a little headroom, and the simulator is crude. Slice 2.2's harness replaces it with labelled footage.

The failures that remain are **two runners in the same lane, one overtaking the other**. Their boxes overlap almost completely, and nothing in the geometry tells them apart. The pipeline notices the doubt and cuts the confidence, so these mostly go to review. About 1 in 1,600 still went through confidently with the wrong bib. That's early evidence for appearance matching (re-identification) inside the tracker, which ADR 0003 left until the harness showed a need.
