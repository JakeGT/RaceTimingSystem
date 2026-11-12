# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Smoke test: every admin page we register renders for a superuser."""

import pytest
from django.contrib import admin
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.urls import reverse

from accounts.models import User


def _request() -> HttpRequest:
    request = RequestFactory().get("/")
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    return request


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model",
    [
        m
        for m in admin.site._registry
        if m._meta.app_label in {"accounts", "events", "timing", "results"}
    ],
    ids=lambda m: m.__name__,
)
def test_admin_pages_render(client: Client, model: type, event: object, race: object) -> None:
    client.force_login(User.objects.create_superuser(email="root@example.com", password="x"))
    opts = model._meta  # type: ignore[attr-defined]
    can_add = admin.site._registry[model].has_add_permission(_request())
    for view in ("changelist", "add") if can_add else ("changelist",):
        response = client.get(reverse(f"admin:{opts.app_label}_{opts.model_name}_{view}"))
        assert response.status_code == 200, f"{opts.model_name} {view}"
