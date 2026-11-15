# Datasets and models: licences

Every dataset and pretrained model we use, and whether its licence lets us publish weights trained on it or ship it in the apps ([ADR 0001](../docs/decisions/0001-licence-and-detector.md), [ADR 0003](../docs/decisions/0003-timing-on-the-tracked-object.md)).

**Nothing below has been checked yet.** Before a row moves to "OK", read the licence text at the source, record the licence and the date checked, and link it. "Internal only" means usable for evaluation or pre-labelling but never shipped or published.

## Datasets

| Dataset | Used for | Licence | Status |
|---|---|---|---|
| Roboflow [`bibracenumber`](https://universe.roboflow.com/edoardo-cittadini-barxf/bibracenumber) | Bib detection; the legacy `best.pt` was trained on it | ? | Not checked |
| RBNR (Ben-Ami et al.) | Evaluating bib recognition | ? (may be research-only) | Not checked |
| SVHN | Pre-training the digit recogniser | ? (may be non-commercial only) | Not checked |
| COCO | Pretrained detector weights; mixed into fine-tuning to keep the general classes | ? (annotations and images are licensed separately) | Not checked |
| Synthetic bibs (ours) | Training the digit recogniser | Ours. Check each **font's** licence | Not checked |
| Staged sessions (ours) | Training and evaluation | Ours, with participants' consent (data policy) | No footage yet |
| Real races | Evaluation only | Private, deleted on schedule | No footage yet |

## Models

| Model | Used for | Licence | Status |
|---|---|---|---|
| YOLOX-Nano / Tiny | Detector shortlist | ? | Not checked |
| RF-DETR Nano | Detector shortlist | ? (only some sizes are permissive) | Not checked |
| D-FINE-N / DEIM-N | Detector shortlist | ? | Not checked |
| EasyOCR, PaddleOCR | Recognition baselines in the harness | ? | Not checked |
| Re-ID model (e.g. OSNet) | Re-identification, Phase 5 | ? | Not checked |
| Open-vocabulary detector (e.g. OWLv2, Grounding DINO) | Auto-labelling clips of new sports, offline | ? | Not checked |
| Legacy `best.pt` (Ultralytics) | Pre-labelling | AGPL-3.0 (Ultralytics) | Internal only, never shipped |
