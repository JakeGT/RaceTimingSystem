#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
# ADR 0001: Ultralytics (AGPL, and it claims trained weights) must never reach shipped code.
# Only vision/tools/legacy/ (internal tooling) may import it.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
hits=$(git grep -nE '^\s*(import|from)\s+ultralytics\b' -- '*.py' ':!vision/tools/legacy/**' || true)
deps=$(git grep -niE '"ultralytics' -- '*/pyproject.toml' 'pyproject.toml' || true)
if [[ -n "$hits$deps" ]]; then
  echo "Ultralytics is only allowed under vision/tools/legacy/ (see docs/decisions/0001-licence-and-detector.md):"
  [[ -n "$hits" ]] && echo "$hits"
  [[ -n "$deps" ]] && echo "$deps"
  exit 1
fi
