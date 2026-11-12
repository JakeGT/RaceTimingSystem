# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared model bases."""

import uuid

from django.db import models


class UUIDModel(models.Model):
    """Base for every model that may be synced between servers (ADR 0002).

    UUIDv7 keys are time-ordered (good index locality) and globally unique, so rows
    created on a venue laptop never collide with rows created in the cloud.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
