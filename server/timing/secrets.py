# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Device tokens and pairing codes. Only hashes are stored (rebuild plan §2)."""

import hashlib
import secrets

# Crockford base32 without I, L, O, U: easy to read off a screen and type.
_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
PAIRING_CODE_LENGTH = 10  # 50 bits; codes expire in minutes and the endpoint is throttled
TOKEN_BYTES = 32


def hash_secret(value: str) -> str:
    """SHA-256 is enough here: tokens and codes are random, not chosen by people, so
    there's nothing for a slow password hash to protect against."""
    return hashlib.sha256(value.encode()).hexdigest()


def new_pairing_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(PAIRING_CODE_LENGTH))


def normalise_pairing_code(code: str) -> str:
    """Accept what people actually type: lower case, spaces/hyphens, O for 0, I/L for 1."""
    cleaned = code.upper().replace("-", "").replace(" ", "")
    return cleaned.translate(str.maketrans("OIL", "011"))


def new_device_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)
