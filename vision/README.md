# vision/

The Python reference pipeline (detection, tracking, line crossing, digit recognition, matching readings to registered bibs), training scripts, the synthetic bib generator and the evaluation harness. See [the rebuild plan](../docs/REBUILD_PLAN.md) §6 and Phase 2.

**Licensing rule:** nothing here may import `ultralytics` except code under `tools/legacy/`, which is internal-only (e.g. pre-labelling with the legacy model) and never shipped. CI enforces this. See [ADR 0001](../docs/decisions/0001-licence-and-detector.md).

```bash
uv run pytest
```
