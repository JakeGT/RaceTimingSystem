# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Settings for the test suite: lets `uv run pytest` work without a .env file."""

import os

os.environ.setdefault("SECRET_KEY", "test-only-not-secret")

from config.settings import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
