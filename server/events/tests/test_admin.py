# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Smoke test: every admin page we register renders for a superuser."""

import pytest
from accounts.models import User
from django.contrib import admin
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    [m for m in admin.site._registry if m._meta.app_label in {"accounts", "events"}],
    ids=lambda m: m.__name__,
)
def test_admin_pages_render(client: Client, model: type, event: object, race: object) -> None:
    client.force_login(User.objects.create_superuser(email="root@example.com", password="x"))
    opts = model._meta  # type: ignore[attr-defined]
    for view in ("changelist", "add"):
        response = client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_{view}"))
        assert response.status_code == 200, f"{opts.model_name} {view}"
