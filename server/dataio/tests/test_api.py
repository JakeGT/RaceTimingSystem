# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The staff API for data in/out: who can do what, and the response shapes."""

import io
from collections.abc import Callable
from typing import Any

import pytest
from allauth.mfa.models import Authenticator
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from accounts.models import Membership, Organisation, Role, User
from dataio.tests.conftest import LEGACY_PARTICIPANTS, LEGACY_RESULTS
from events.models import Entry, Event, Race, Split, Wave
from timing.models import Read

pytestmark = pytest.mark.django_db

API = "/api/v1/staff"


@pytest.fixture
def staff(organisation: Organisation) -> Callable[[Role], Client]:
    def make(role: Role) -> Client:
        user = User.objects.create_user(email=f"{role}@example.com", password="x")
        Membership.objects.create(user=user, organisation=organisation, role=role)
        Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"secret": "x"})
        client = Client()
        client.force_login(user)
        return client

    return make


def upload(content: bytes, name: str = "file.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content, content_type="text/csv")


class TestEntries:
    def test_organiser_imports_and_downloads(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        client = staff(Role.ORGANISER)
        response = client.post(
            f"{API}/events/{event.pk}/entries/import", {"file": upload(LEGACY_PARTICIPANTS)}
        )
        assert response.status_code == 200, response.content
        assert response.json()["summary"] == "Imported: 6 new."
        response = client.get(f"{API}/events/{event.pk}/entries.csv?legacy=true")
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert 'filename="riverside-10k-entries.csv"' in response["Content-Disposition"]
        assert response.content.decode().startswith("BibNumber,Firstname")

    def test_problems_are_a_422_with_every_line(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        response = staff(Role.ORGANISER).post(
            f"{API}/events/{event.pk}/entries/import",
            {"file": upload(b"bib,name,gender\n1,Ada,robot\n1,Ben,male\n")},
        )
        assert response.status_code == 422
        assert [e["line"] for e in response.json()["errors"]] == [2, 3]
        assert not Entry.objects.exists()

    def test_unusable_file_is_a_400(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        response = staff(Role.ORGANISER).post(
            f"{API}/events/{event.pk}/entries/import", {"file": upload(b"name\nAda\n")}
        )
        assert response.status_code == 400
        assert "no bib column" in response.json()["detail"]

    def test_dry_run_and_race(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        response = staff(Role.ORGANISER).post(
            f"{API}/events/{event.pk}/entries/import",
            {"file": upload(LEGACY_PARTICIPANTS), "race_id": str(race.pk), "dry_run": "true"},
        )
        assert response.json()["dry_run"] is True and not Entry.objects.exists()

    def test_volunteers_cannot_see_personal_details(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        client = staff(Role.VOLUNTEER)
        assert client.get(f"{API}/events/{event.pk}/entries.csv").status_code == 403
        response = client.post(
            f"{API}/events/{event.pk}/entries/import", {"file": upload(LEGACY_PARTICIPANTS)}
        )
        assert response.status_code == 403

    def test_outsiders_get_404(self, event: Event, race: Race) -> None:
        user = User.objects.create_user(email="stranger@example.com", password="x")
        client = Client()
        client.force_login(user)
        assert client.get(f"{API}/events/{event.pk}/results.csv").status_code == 404


class TestTimesAndResults:
    def test_times_then_results(
        self,
        staff: Callable[[Role], Client],
        event: Event,
        race: Race,
        finish: Split,
        started: Wave,
    ) -> None:
        organiser = staff(Role.ORGANISER)
        organiser.post(
            f"{API}/events/{event.pk}/entries/import", {"file": upload(LEGACY_PARTICIPANTS)}
        )
        response = organiser.post(
            f"{API}/events/{event.pk}/times/import",
            {"file": upload(LEGACY_RESULTS, "stopwatch.csv"), "reason": "Backup watch"},
        )
        assert response.status_code == 200, response.content
        assert response.json()["created"] == 6
        assert Read.objects.first().adjustments.get().reason == (  # type: ignore[union-attr]
            "Imported from stopwatch.csv: Backup watch"
        )

        response = staff(Role.VOLUNTEER).get(f"{API}/events/{event.pk}/results.csv?legacy=true")
        assert response.status_code == 200
        assert response.content.decode().splitlines()[1] == "1,00:25:36"

    def test_timing_point_from_another_event(
        self, staff: Callable[[Role], Client], event: Event, race: Race
    ) -> None:
        response = staff(Role.ORGANISER).post(
            f"{API}/events/{event.pk}/times/import",
            {"file": upload(b"bib,clock\n1,10:00:00\n"), "timing_point_id": str(race.pk)},
        )
        assert response.status_code == 400

    def test_decimals_checked(self, staff: Callable[[Role], Client], event: Event) -> None:
        response = staff(Role.VOLUNTEER).get(f"{API}/events/{event.pk}/results.csv?decimals=9")
        assert response.status_code == 400


class TestBundles:
    def test_download_then_import(
        self,
        staff: Callable[[Role], Client],
        event: Event,
        race: Race,
        organisation: Organisation,
    ) -> None:
        Entry.objects.create(race=race, bib="1", given_name="Ada")
        response = staff(Role.ORGANISER).get(f"{API}/events/{event.pk}/bundle")
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        assert "riverside-10k-2026-06-14.bundle.zip" in response["Content-Disposition"]
        data = b"".join(response.streaming_content)  # type: ignore[attr-defined]

        owner = staff(Role.OWNER)
        path = f"{API}/organisations/{organisation.slug}/events/import"
        response = owner.post(path, {"file": upload(data, "b.zip")})
        assert response.status_code == 400
        assert "Replace it" in response.json()["detail"]
        response = owner.post(path, {"file": upload(data, "b.zip"), "replace": "true"})
        assert response.status_code == 200, response.content
        body: dict[str, Any] = response.json()
        assert (body["replaced"], body["rows"]["events.entry"]) == (True, 1)

    def test_only_owners_import(
        self, staff: Callable[[Role], Client], organisation: Organisation
    ) -> None:
        response = staff(Role.ORGANISER).post(
            f"{API}/organisations/{organisation.slug}/events/import",
            {"file": SimpleUploadedFile("b.zip", io.BytesIO(b"x").getvalue())},
        )
        assert response.status_code == 403

    def test_volunteers_cannot_download(
        self, staff: Callable[[Role], Client], event: Event
    ) -> None:
        assert staff(Role.VOLUNTEER).get(f"{API}/events/{event.pk}/bundle").status_code == 403
