# ADR 0001: Project licence and detection model

- **Status:** Accepted (2026-11-12)
- **Date:** 2026-11-12
- **Context:** [Rebuild plan](../REBUILD_PLAN.md) §6 and Phase 0

> Not legal advice. Have the final licence text, especially the app-store permission, checked before the first public release.

## Context

- The legacy repo is **GPL-3.0**, and five people contributed to it.
- The legacy detector is **Ultralytics YOLO, which is AGPL-3.0**. Ultralytics says that [models trained with its software are also AGPL-3.0](https://ultralytics.com/license), including custom-trained and fine-tuned ones. Anything else needs a paid Enterprise licence.
- The rebuild ships **phone apps** that run the detector on the device. Distributing (A)GPL code through the iOS App Store is legally unclear, because Apple's usage terms add restrictions that GPL §10 forbids. A project can grant itself an exception for **its own** code, but it **can't grant one for Ultralytics' code or weights**.
- The goal is an **open-source product** that clubs can self-host.

Two decisions follow, and they're separate: **(A) which detector to use** and **(B) which licence the project uses**.

## Decision A: Detector — no Ultralytics in anything we ship

**Options**

| | Ultralytics YOLO11/26 | Apache/MIT-licensed detector |
|---|---|---|
| Tooling and exports | Best in class (CoreML, TFLite, NCNN in one command) | We maintain more of the export pipeline ourselves |
| Licence impact | Forces AGPL on the project *and* the shipped weights; blocks a clean iOS release; anyone building on it commercially has to buy a licence | No constraint, so the project licence is decided on its own merits |
| Accuracy for bibs | Excellent | More than enough: bibs are large, high-contrast rectangles |

**Decision:** use a permissively licensed detector, behind a narrow interface (`frame → boxes + scores`, ONNX as the interchange format, converted per platform). The Phase 3 spike chooses from this shortlist by measuring recall on bibs, phone latency, battery and heat:

1. **YOLOX-Nano / Tiny** (Apache-2.0): a small CNN that converts easily to TFLite, CoreML and NCNN, with existing mobile demos. *The safe choice.*
2. **RF-DETR Nano** (Apache-2.0; only the XL and 2XL sizes are under the PML licence): more accurate, but it's a transformer, so mobile conversion and latency are the risk. *The higher-accuracy choice.*
3. **D-FINE-N / DEIM-N** (Apache-2.0): DETR-style alternatives, if RF-DETR doesn't convert well.

**Related decisions**
- **Tracker:** our own small ByteTrack-style tracker (ByteTrack's reference code is MIT). We need custom line-crossing logic anyway.
- **Bib reading:** our own digit model (rebuild plan §6), with PaddleOCR (Apache-2.0) and EasyOCR (Apache-2.0) as baselines in the evaluation harness.
- **Legacy `best.pt`:** used **internally only**, to pre-label data in CVAT or Label Studio. It's never shipped or put in a release.
- **Training data licences decide whether we can release weights:** check the licence of the Roboflow `bibracenumber` dataset (and any others) before publishing weights trained on it. Track every dataset's licence in `vision/datasets.md`.

## Decision B: Project licence — AGPL-3.0-or-later

**Options**

| | AGPL-3.0 | GPL-3.0 (as now) | Apache-2.0 |
|---|---|---|---|
| Closed hosted forks | Not allowed: anyone running a modified server has to share their changes | Allowed (GPL only applies when code is distributed) | Allowed |
| Reusing legacy GPL-3.0 code | Yes (GPL-3.0 §13 allows combining with AGPL) | Yes | Only with the agreement of all five original authors, or a clean rewrite |
| Adoption by businesses (e.g. timing companies) | Lower | Medium | Highest |
| iOS App Store | Needs an additional-permission clause for our own code | Same | No problem |
| Changing licence later | Needs agreement from every contributor (no CLA planned) | Same | Same |

**Decision:** **AGPL-3.0-or-later** for the whole monorepo, with:
- a **GPL §7 additional permission** in the licence, allowing the mobile app to be distributed through app stores (it applies to project code; all shipped third-party code is permissively licensed thanks to Decision A);
- the **DCO** (`Signed-off-by`) for contributions instead of a CLA, which keeps contributing easy;
- SPDX headers on source files, and `reuse lint` in CI.

**Why:** it's the best fit for "open-source tool clubs self-host". It stops someone wrapping the project in a closed paid service, lets us reuse legacy code if we want to, and costs us little because we're not aiming at proprietary commercial users.

**When Apache-2.0 would be better:** if the priority becomes getting existing timing companies or app vendors to adopt or embed it. In that case, don't copy legacy code without agreement from all five original authors.

## Consequences
- The Phase 3 spike has an extra job: getting the shortlisted detectors exported and benchmarked. That's roughly a few extra days compared with Ultralytics' one-command export.
- `vision/` must not import `ultralytics` in any code that's shipped. Enforce it with a CI check, and allow it only under `vision/tools/legacy/`.
- The licence choice no longer depends on the ML tooling, so Decision B can be revisited before the first public release without having to retrain anything.
