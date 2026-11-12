# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import pytest
from django.test import Client


@pytest.mark.django_db
def test_health_reports_ok(client: Client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_rejects_post(client: Client) -> None:
    assert client.post("/api/health").status_code == 405
