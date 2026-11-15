# ADR 0003: Time the person, not the bib

- **Status:** Accepted (2026-11-15)
- **Context:** [Rebuild plan](../REBUILD_PLAN.md) §6 and Phase 2; refines [ADR 0001](0001-licence-and-detector.md) (which detector) and §6's "the evaluation harness will settle it"

## Context

The first plan timed a runner when their **bib box** crossed the line. That has three problems:

- **The bib is often hidden at the line:** arms, other runners, a rolled-up vest, a bib pinned to shorts. If timing needs the bib, those runners get no time.
- **Bibs are small and flicker in and out of view,** so tracks break and the same runner gets counted twice or not at all.
- **The rules time something else:** the torso in athletics, the front tyre in cycling, the front wheel in wheelchair racing, the bow in rowing.

## Decisions

### 1. Time the tracked object; the bib only says who it is

The pipeline detects and tracks **people** (the "tracked object"), and times the moment a track crosses the line. Bib boxes are matched to the person box that contains them, and the bib can be read **anywhere along the track**, before or after the line. One clear look is enough, and recognition stops once a track's bib is confident.

A crossing whose bib was never read is still sent: the protocol already allows an observation with an empty `candidates` list, and it becomes an unknown read in the review queue with its crop. Nobody who crossed the line is lost.

### 2. Two line geometries, because timing the person doesn't remove parallax by itself

A finish line drawn on the image is really a line **on the ground**. A point at chest height (bib or torso) crosses the drawn line at the wrong moment unless the camera sits **in the vertical plane of the finish line**. The error grows with the camera's angle and the runner's distance from the line's plane.

- **In-plane camera (`ImageLine`):** the camera is on the line's plane (a tripod at the end of the finish line, a finish tower). The line is roughly vertical in the image and any point on the body can be timed against it. This is how photo-finish cameras are set up, and it's the most accurate option.
- **Any other angle (`GroundLine`):** four points on the ground (for example the corners of the finish line's lane, marked with cones) give a homography from the image to the ground plane. The **bottom centre of the person box**, roughly the point under the hips, is mapped onto the ground and timed against the line there. A point on the ground has no parallax, so the camera can stand anywhere it can see the runners' feet.

The evaluation harness measures both against labelled crossings, including how often feet are hidden in bunched finishes.

### 3. One detector, several classes

One detector finds **people and bibs** (and later bicycles or boats). The cost of a small detector barely changes with the number of classes, so this costs no more battery than a bib-only model. It's fine-tuned from **COCO-pretrained weights with COCO images mixed into training**, so it keeps the general classes (person, bicycle, boat …) instead of forgetting them.

### 4. Sport profiles, running only for now

What changes between sports goes in a **sport profile**, not in code:

| | Running (built) | Cycling (later) | Rowing (later) |
|---|---|---|---|
| Tracked object | person | bicycle | boat |
| Timing anchor | torso (box centre in-plane, bottom centre on the ground) | front of the box (front tyre) | front of the box (bow) |
| Identity | bib on the person | number plate or bib | lane draw (side-by-side racing), start order and bow number (head races) |

Only running is built in Phase 2. Rowing needs more than a profile, and that work sits outside Phase 2:

- **identity without OCR:** lane assignment, start order
- **crew entries:** the current Entry model is one person
- **an in-plane camera:** lanes spread across 100 m or more of water, so `GroundLine` with visible feet doesn't apply

**Adding a sport without heavy retraining:**

- **Sports whose object is a COCO class** (bicycle, boat, horse) need no retraining, because decision 3 keeps those classes.
- **Sports whose object isn't a COCO class:** an open-vocabulary detector, run offline on a workstation or the venue laptop, can auto-label a few clips. A short fine-tune then teaches the phone model the new class. Those detectors are far too heavy to run on a phone.

### 5. Re-identification: deferred to Phase 5, approach undecided

Re-identification (recognising the same person again by how they look) does two different jobs:

- **Within one camera, after an occlusion:** the phone's tracker re-joins the track. This is on the phone and part of Phase 2's tracker work, by motion first and by appearance later if the harness shows it's needed.
- **Across phones and timing points:** a bib read clearly by phone A or at the 5 km split identifies an unread crossing from phone B or at the finish. This belongs with fusion v2 (Phase 5).

There are two ways to do the second job. We'll choose when Phase 5 starts:

- **Phones send an appearance embedding with each observation:** a small vector from a small re-ID model. Matching happens on the server or venue laptop. It needs no live round trip, so the phone's offline outbox keeps working. It would be a protocol v2 field.
- **Phones send crops to a central compute service** (the venue laptop or the cloud), which runs a bigger re-ID model per runner. It's more accurate, but needs a live connection and compute at the venue. The "weak phone" fallback in §6 already streams crops to the laptop, so it could build on that.

Embeddings and crops are personal data. They're scoped to the event and deleted with the crops.

## Consequences

- **Ground truth per runner** becomes: bib, crossing frame by the torso rule, the person's box at that frame, and an occlusion flag.
- **The reference pipeline core** (slice 2.1): boxes, ByteTrack (Roboflow's `trackers`, Apache-2.0) behind an adapter, both line geometries with sub-frame interpolation, bib-to-person matching, bib voting snapped to the registered bibs, and the sport profile. The ML models plug into it later.
- **The protocol doesn't change now.** An optional embedding field is noted for protocol v2.
- **First measurements (synthetic, slice 2.1):**
  - **In-plane camera, line drawn on the image:** exact.
  - **Angled camera, ground line:** the box's bottom edge sits about 18 cm ahead of the hips, so 0.02–0.06 s early depending on speed. It needs correcting as a ground offset in metres, not as a time.
  - **Angled camera, line drawn on the image:** out by up to ~0.5 s, and misses runners.
  - **Busy finishes:** a camera 4.5 m up loses fewer runners than one at 2.5 m (0.25% against 0.45%), and about 1 in 800 runners is sent confidently with the wrong bib at either height. The errors that remain are same-lane overtakes, which geometry can't separate. That's early evidence for appearance matching inside the tracker. Details in [`vision/README.md`](../../vision/README.md).
- **Licences to check** before anything ships or weights are published are listed in [`vision/datasets.md`](../../vision/datasets.md). That covers re-ID models, open-vocabulary labellers and datasets. Nothing named in this ADR has been checked yet.
