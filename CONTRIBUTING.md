# Contributing

Thanks for helping! This project is being rebuilt. Start with [the rebuild plan](docs/REBUILD_PLAN.md) and the [decision records](docs/decisions/).

## Development setup

You need [uv](https://docs.astral.sh/uv/), [pnpm](https://pnpm.io/) (it downloads the right Node version itself) and Docker.

```bash
docker compose up        # Postgres + Django (http://localhost:8000) + Vite (http://localhost:5173)
```

Or run the parts directly:

```bash
cd server && cp .env.example .env && uv run python manage.py migrate && uv run python manage.py runserver
cd web && pnpm install && pnpm dev
cd vision && uv run pytest
```

Install the git hooks once:

```bash
uvx pre-commit install
```

## Checks (the same ones CI runs)

| Part | Commands |
|---|---|
| `server/` | `uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest` |
| `web/` | `pnpm lint && pnpm format:check && pnpm typecheck && pnpm test && pnpm build` |
| `vision/` | `uv run ruff check . && uv run mypy src tests && uv run pytest` |
| repo | `uvx reuse lint`, gitleaks |

## Sign your commits (DCO)

Every commit has to be signed off under the [Developer Certificate of Origin](https://developercertificate.org/), which certifies that you have the right to contribute it under the project's licence:

```bash
git commit -s
```

That adds a `Signed-off-by: Your Name <you@example.com>` line. CI rejects pull requests with commits that aren't signed off.

## Licensing rules

- The project is **AGPL-3.0-or-later**. New source files start with an SPDX header:
  ```
  # SPDX-FileCopyrightText: 2026 Race Timing System contributors
  # SPDX-License-Identifier: AGPL-3.0-or-later
  ```
  (use `//` for TypeScript and JavaScript). Files that can't have headers are covered by [`REUSE.toml`](REUSE.toml).
- **Anything that ships on phones must use permissively licensed third-party code and models** (MIT, BSD, Apache-2.0). No GPL/AGPL dependencies in `mobile/`.
- **No `ultralytics` imports** outside `vision/tools/legacy/` (internal use only, never shipped). CI enforces this. See [ADR 0001](docs/decisions/0001-licence-and-detector.md).
- Never commit model weights, datasets, footage or `.env` files. Footage of real people is personal data. Follow the data policy in the rebuild plan §6.
