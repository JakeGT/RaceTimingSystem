# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse

from accounts.models import Organisation, User
from dataio.tests.conftest import LEGACY_PARTICIPANTS, LEGACY_RESULTS
from events.models import Entry, Event, Race, Split, Wave
from timing.models import Read

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(db: None) -> Client:
    user = User.objects.create_superuser(email="admin@example.com", password="x")
    client = Client()
    client.force_login(user)
    return client


class TestAdmin:
    def test_links(self, admin_client: Client, event: Event) -> None:
        page = admin_client.get(reverse("admin:events_event_change", args=[event.pk]))
        assert reverse("admin:events_event_data", args=[event.pk]) in page.content.decode()
        page = admin_client.get(reverse("admin:events_event_changelist"))
        assert reverse("admin:events_event_import") in page.content.decode()

    def test_import_entries_then_times(
        self, admin_client: Client, event: Event, race: Race, finish: Split, started: Wave
    ) -> None:
        url = reverse("admin:events_event_data", args=[event.pk])
        assert admin_client.get(url).status_code == 200
        response = admin_client.post(
            url,
            {"form": "entries", "file": SimpleUploadedFile("p.csv", LEGACY_PARTICIPANTS)},
        )
        assert response.status_code == 302
        assert Entry.objects.count() == 6
        response = admin_client.post(
            url, {"form": "times", "file": SimpleUploadedFile("r.csv", LEGACY_RESULTS)}
        )
        assert response.status_code == 302
        assert Read.objects.count() == 6

    def test_problems_shown_by_line(self, admin_client: Client, event: Event, race: Race) -> None:
        url = reverse("admin:events_event_data", args=[event.pk])
        response = admin_client.post(
            url, {"form": "entries", "file": SimpleUploadedFile("p.csv", b"bib,name\n,Ada\n")}
        )
        assert response.status_code == 200
        assert "<td>2</td><td>No bib.</td>" in response.content.decode()

    @pytest.mark.parametrize(
        "what", ["entries", "entries-legacy", "results", "results-legacy", "bundle"]
    )
    def test_downloads(self, admin_client: Client, event: Event, race: Race, what: str) -> None:
        url = reverse("admin:events_event_download", args=[event.pk, what])
        assert admin_client.get(url).status_code == 200

    def test_bundle_import(
        self, admin_client: Client, event: Event, race: Race, organisation: Organisation
    ) -> None:
        Entry.objects.create(race=race, bib="1", given_name="Ada")
        response = admin_client.get(
            reverse("admin:events_event_download", args=[event.pk, "bundle"])
        )
        data = b"".join(response.streaming_content)  # type: ignore[attr-defined]
        url = reverse("admin:events_event_import")
        form = {"organisation": organisation.pk, "file": SimpleUploadedFile("b.zip", data)}
        response = admin_client.post(url, form)
        assert "already on this server" in response.content.decode()
        form["file"] = SimpleUploadedFile("b.zip", data)
        response = admin_client.post(url, {**form, "replace": "on"})
        assert response.status_code == 302


class TestCommands:
    def test_export_then_import(
        self, event: Event, race: Race, organisation: Organisation, tmp_path: Path
    ) -> None:
        Entry.objects.create(race=race, bib="1", given_name="Ada")
        path = tmp_path / "event.zip"
        call_command("export_event", "exeter-harriers/riverside-10k", "-o", str(path))
        with pytest.raises(CommandError, match="already on this server"):
            call_command("import_event", str(path), "exeter-harriers")
        call_command("import_event", str(path), "exeter-harriers", "--replace")
        assert Entry.objects.get().given_name == "Ada"

    def test_unknown_names(self, event: Event, tmp_path: Path) -> None:
        with pytest.raises(CommandError, match="No event"):
            call_command("export_event", "exeter-harriers/nope", "-o", str(tmp_path / "x"))
        with pytest.raises(CommandError, match="No organisation"):
            call_command("import_event", str(tmp_path / "x"), "nope")
        with pytest.raises(CommandError, match="isn't a zip"):
            (tmp_path / "x").write_bytes(b"x")
            call_command("import_event", str(tmp_path / "x"), "exeter-harriers")
