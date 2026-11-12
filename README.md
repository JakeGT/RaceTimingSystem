# Race Timing System

Open-source, low-cost race timing for grassroots running events. **Phones act as cameras**: each one detects and reads runners' bib numbers on the device and records when they cross a timing line. A server merges the readings into live results. Several phones can watch the same line to cut down occlusion, and groups of phones give split times. At venues with no signal, a laptop can run the whole event and upload it afterwards.

> **Status: being rebuilt.** This branch is a ground-up rewrite. The original university prototype (ECMM427, 2024/25) is kept on the [`legacy`](../../tree/legacy) tag.

## Where things are

| Path | What |
|---|---|
| [`docs/REBUILD_PLAN.md`](docs/REBUILD_PLAN.md) | Goals, architecture, domain model and phased plan |
| [`docs/decisions/`](docs/decisions/) | Architecture decision records |
| [`server/`](server/) | Django server: API, results engine, organiser admin |
| [`web/`](web/) | React + TypeScript web app: public results, organiser console, review queue |
| [`vision/`](vision/) | Reference vision pipeline, training tools and evaluation harness |
| [`mobile/`](mobile/) | Phone capture app (stack still to be chosen) |
| [`protocol/`](protocol/) | Device ⇄ server contract |

## Quick start

```bash
docker compose up
```

Then open http://localhost:5173 (web) or http://localhost:8000/admin (Django admin). See [CONTRIBUTING.md](CONTRIBUTING.md) for running the parts without Docker, and for the checks CI runs.

## Licence

[AGPL-3.0-or-later](LICENSE). Anyone who runs a modified version as a network service has to offer its source to the people using it. See [ADR 0001](docs/decisions/0001-licence-and-detector.md) for the reasoning, and [LICENSE-APPSTORE-EXCEPTION.md](LICENSE-APPSTORE-EXCEPTION.md) for the draft app-store permission.

## Original authors

The legacy prototype was built by Jake Talling, Max Bennett, Angelo Palmer, Lucy Dechaine and James Adam.
