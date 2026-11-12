# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib


def hash_secret(value: str) -> str:
    """Hash a random token (device token, pairing code, invite link) for storage.

    SHA-256 is enough here: these are random, not chosen by people, so there's nothing
    for a slow password hash to protect against.
    """
    return hashlib.sha256(value.encode()).hexdigest()
