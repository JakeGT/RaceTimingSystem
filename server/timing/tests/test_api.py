# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Device protocol API tests (protocol/README.md)."""

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import Client
from django.utils import timezone

from accounts.models import Organisation
from events.models import Entry, Event, Race, TimingPoint
from timing.models import Device, Heartbeat, Observation, PairingCode

API = "/api/v1/devices"
EXAMPLES = Path(settings.BASE_DIR).parent / "protocol" / "examples"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _reset_throttles() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _media(settings: Any, tmp_path: Path) -> None:
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def paired(event: Event, finish_line: TimingPoint) -> tuple[Device, str]:
    pairing, _ = PairingCode.issue(event, finish_line)
    return Device.pair(pairing, name="Finish left")


@pytest.fixture
def auth(paired: tuple[Device, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {paired[1]}"}


def post(client: Client, path: str, body: object, headers: dict[str, str] | None = None) -> Any:
    return client.post(
        f"{API}{path}", json.dumps(body), content_type="application/json", headers=headers
    )


def observation(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "id": str(uuid.uuid7()),
        "captured_at_device": (timezone.now() - timedelta(minutes=1)).isoformat(),
        "clock_offset_ms": 250,
        "candidates": [{"bib": "101", "confidence": 0.9}],
    }
    body.update(overrides)
    return body


@pytest.mark.django_db
class TestPairing:
    def test_pair_with_code(self, client: Client, event: Event, finish_line: TimingPoint) -> None:
        _, raw = PairingCode.issue(event, finish_line)
        response = post(client, "/pair", {"code": raw, "name": "Finish left"})
        assert response.status_code == 201, response.content
        body = response.json()
        assert body["event"]["id"] == str(event.pk)
        assert body["timing_point_id"] == str(finish_line.pk)
        device = Device.objects.get(pk=body["device_id"])
        assert device.token_hash != body["token"]  # only the hash is stored

    def test_code_is_forgiving_about_typing(self, client: Client, event: Event) -> None:
        pairing = PairingCode(event=event)
        raw = pairing.assign_new_code()
        pairing.save()
        typed = f"{raw[:5]}-{raw[5:]}".lower().replace("0", "o").replace("1", "l")
        assert post(client, "/pair", {"code": typed, "name": "x"}).status_code == 201

    def test_code_works_once(self, client: Client, event: Event) -> None:
        _, raw = PairingCode.issue(event)
        assert post(client, "/pair", {"code": raw, "name": "a"}).status_code == 201
        assert post(client, "/pair", {"code": raw, "name": "b"}).status_code == 400

    def test_expired_code(self, client: Client, event: Event) -> None:
        pairing, raw = PairingCode.issue(event)
        PairingCode.objects.filter(pk=pairing.pk).update(expires_at=timezone.now())
        response = post(client, "/pair", {"code": raw, "name": "a"})
        assert response.status_code == 400
        assert "expired" in response.json()["detail"]

    def test_wrong_code(self, client: Client, event: Event) -> None:
        PairingCode.issue(event)
        assert post(client, "/pair", {"code": "AAAAAAAAAA", "name": "a"}).status_code == 400

    def test_pairing_is_throttled(self, client: Client, db: None) -> None:
        codes = [post(client, "/pair", {"code": "AAAAAAAAAA", "name": "a"}).status_code]
        codes += [
            post(client, "/pair", {"code": "AAAAAAAAAA", "name": "a"}).status_code
            for _ in range(10)
        ]
        assert codes[0] == 400
        assert codes[-1] == 429


@pytest.mark.django_db
class TestAuth:
    def test_requires_token(self, client: Client) -> None:
        assert client.get(f"{API}/me").status_code == 401

    def test_rejects_bad_token(self, client: Client, paired: tuple[Device, str]) -> None:
        assert client.get(f"{API}/me", headers={"Authorization": "Bearer nope"}).status_code == 401

    def test_revoked_device(
        self, client: Client, paired: tuple[Device, str], auth: dict[str, str]
    ) -> None:
        Device.objects.filter(pk=paired[0].pk).update(revoked_at=timezone.now())
        assert client.get(f"{API}/me", headers=auth).status_code == 401


@pytest.mark.django_db
class TestConfig:
    def test_config_lists_points_and_bibs(
        self, client: Client, auth: dict[str, str], race: Race, finish_line: TimingPoint
    ) -> None:
        for bib in ["10", "2", "A7"]:
            Entry.objects.create(race=race, bib=bib, given_name="R")
        body = client.get(f"{API}/me", headers=auth).json()
        assert body["bibs"] == ["2", "10", "A7"]
        assert body["timing_points"] == [{"id": str(finish_line.pk), "name": "Finish"}]
        assert body["timing_point_id"] == str(finish_line.pk)

    def test_config_version_changes_with_entries(
        self, client: Client, auth: dict[str, str], race: Race
    ) -> None:
        before = client.get(f"{API}/me", headers=auth).json()["config_version"]
        assert client.get(f"{API}/me", headers=auth).json()["config_version"] == before
        Entry.objects.create(race=race, bib="55", given_name="New")
        assert client.get(f"{API}/me", headers=auth).json()["config_version"] != before

    def test_choose_timing_point(
        self, client: Client, auth: dict[str, str], event: Event, paired: tuple[Device, str]
    ) -> None:
        bridge = TimingPoint.objects.create(event=event, name="Bridge")
        response = client.put(
            f"{API}/me/timing-point",
            json.dumps({"timing_point_id": str(bridge.pk)}),
            content_type="application/json",
            headers=auth,
        )
        assert response.status_code == 200
        paired[0].refresh_from_db()
        assert paired[0].timing_point == bridge

    def test_cannot_choose_other_events_point(
        self, client: Client, auth: dict[str, str], organisation: Organisation
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=datetime(2026, 7, 1)
        )
        stray = TimingPoint.objects.create(event=other, name="Finish")
        response = client.put(
            f"{API}/me/timing-point",
            json.dumps({"timing_point_id": str(stray.pk)}),
            content_type="application/json",
            headers=auth,
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestClockAndHeartbeat:
    def test_clock_exchange(self, client: Client, auth: dict[str, str]) -> None:
        sent = datetime(2026, 6, 14, 8, 59, 58, tzinfo=UTC)
        before = timezone.now()
        body = post(client, "/me/clock", {"client_sent_at": sent.isoformat()}, headers=auth).json()
        assert datetime.fromisoformat(body["client_sent_at"]) == sent
        received = datetime.fromisoformat(body["server_received_at"])
        assert before <= received <= datetime.fromisoformat(body["server_sent_at"])

    def test_times_keep_microseconds(self, client: Client, auth: dict[str, str]) -> None:
        # Django's JSON encoder would cut this to .123 and bias clock sync.
        sent = datetime(2026, 6, 14, 8, 59, 58, 123456, tzinfo=UTC)
        body = post(client, "/me/clock", {"client_sent_at": sent.isoformat()}, headers=auth).json()
        assert body["client_sent_at"] == "2026-06-14T08:59:58.123456Z"

    def test_heartbeat_updates_device(
        self, client: Client, auth: dict[str, str], paired: tuple[Device, str]
    ) -> None:
        response = post(
            client,
            "/me/heartbeat",
            {"battery_pct": 64, "clock_offset_ms": -42, "clock_rtt_ms": 18, "app_version": "0.2"},
            headers=auth,
        )
        assert response.status_code == 200
        assert response.json()["config_version"]
        device = Device.objects.get(pk=paired[0].pk)
        assert (device.battery_pct, device.clock_offset_ms, device.app_version) == (64, -42, "0.2")
        assert device.last_seen_at is not None
        assert Heartbeat.objects.filter(device=device, event=device.event).count() == 1

    def test_heartbeat_validates_ranges(self, client: Client, auth: dict[str, str]) -> None:
        assert post(client, "/me/heartbeat", {"battery_pct": 140}, headers=auth).status_code == 422


@pytest.mark.django_db
class TestObservations:
    def test_accepts_and_corrects_clock(
        self, client: Client, auth: dict[str, str], finish_line: TimingPoint
    ) -> None:
        obs = observation()
        body = post(client, "/me/observations/batch", {"observations": [obs]}, headers=auth).json()
        assert body == {"accepted": [obs["id"]], "duplicates": [], "rejected": []}
        stored = Observation.objects.get(pk=str(obs["id"]))
        assert stored.timing_point == finish_line  # the device's assigned point
        assert stored.captured_at - stored.captured_at_device == timedelta(milliseconds=250)
        assert stored.candidates == [{"bib": "101", "confidence": 0.9}]

    def test_resending_is_idempotent(self, client: Client, auth: dict[str, str]) -> None:
        batch = {"observations": [observation(), observation()]}
        post(client, "/me/observations/batch", batch, headers=auth)
        body = post(client, "/me/observations/batch", batch, headers=auth).json()
        assert body["accepted"] == []
        assert len(body["duplicates"]) == 2
        assert Observation.objects.count() == 2

    def test_same_id_twice_in_one_batch(self, client: Client, auth: dict[str, str]) -> None:
        obs = observation()
        body = post(
            client, "/me/observations/batch", {"observations": [obs, obs]}, headers=auth
        ).json()
        assert (body["accepted"], body["duplicates"]) == ([obs["id"]], [obs["id"]])

    def test_id_from_another_device_is_rejected(
        self, client: Client, auth: dict[str, str], event: Event
    ) -> None:
        obs = observation()
        post(client, "/me/observations/batch", {"observations": [obs]}, headers=auth)
        pairing, _ = PairingCode.issue(event)
        _, other_token = Device.pair(pairing, name="Other")
        body = post(
            client,
            "/me/observations/batch",
            {"observations": [obs]},
            headers={"Authorization": f"Bearer {other_token}"},
        ).json()
        assert body["rejected"] == [{"id": obs["id"], "reason": "id_used_by_another_device"}]

    def test_rejections(
        self,
        client: Client,
        auth: dict[str, str],
        organisation: Organisation,
        paired: tuple[Device, str],
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=datetime(2026, 7, 1)
        )
        stray = TimingPoint.objects.create(event=other, name="Finish")
        future = observation(captured_at_device=(timezone.now() + timedelta(hours=1)).isoformat())
        wrong_point = observation(timing_point_id=str(stray.pk))
        body = post(
            client, "/me/observations/batch", {"observations": [future, wrong_point]}, headers=auth
        ).json()
        assert sorted(r["reason"] for r in body["rejected"]) == [
            "in_future",
            "timing_point_not_in_event",
        ]

        Device.objects.filter(pk=paired[0].pk).update(timing_point=None)
        body = post(
            client, "/me/observations/batch", {"observations": [observation()]}, headers=auth
        )
        assert body.json()["rejected"][0]["reason"] == "no_timing_point"

    def test_validation(self, client: Client, auth: dict[str, str]) -> None:
        bad_bib = observation(candidates=[{"bib": "12 34", "confidence": 0.5}])
        too_many = {"observations": [observation() for _ in range(501)]}
        assert (
            post(
                client, "/me/observations/batch", {"observations": [bad_bib]}, headers=auth
            ).status_code
            == 422
        )
        assert post(client, "/me/observations/batch", too_many, headers=auth).status_code == 422
        assert (
            post(client, "/me/observations/batch", {"observations": []}, headers=auth).status_code
            == 422
        )

    def test_unreadable_bib_is_still_stored(self, client: Client, auth: dict[str, str]) -> None:
        obs = observation(candidates=[])
        body = post(client, "/me/observations/batch", {"observations": [obs]}, headers=auth).json()
        assert body["accepted"] == [obs["id"]]


@pytest.mark.django_db
class TestCrops:
    @pytest.fixture
    def stored(self, client: Client, auth: dict[str, str]) -> str:
        obs = observation()
        post(client, "/me/observations/batch", {"observations": [obs]}, headers=auth)
        return str(obs["id"])

    def upload(self, client: Client, obs_id: str, data: bytes, auth: dict[str, str]) -> Any:
        from django.core.files.uploadedfile import SimpleUploadedFile

        image = SimpleUploadedFile("crop.jpg", data, content_type="image/jpeg")
        return client.post(f"{API}/me/observations/{obs_id}/crop", {"image": image}, headers=auth)

    def test_upload_and_replace(self, client: Client, auth: dict[str, str], stored: str) -> None:
        assert self.upload(client, stored, JPEG, auth).status_code == 204
        assert self.upload(client, stored, JPEG + b"v2", auth).status_code == 204
        crop = Observation.objects.get(pk=stored).crop
        assert crop.name is not None and crop.name.endswith(f"{stored}.jpg")
        assert crop.read() == JPEG + b"v2"

    def test_rejects_non_jpeg(self, client: Client, auth: dict[str, str], stored: str) -> None:
        assert self.upload(client, stored, b"\x89PNG....", auth).status_code == 400

    def test_rejects_large(self, client: Client, auth: dict[str, str], stored: str) -> None:
        assert self.upload(client, stored, JPEG + b"\x00" * 600_000, auth).status_code == 400

    def test_only_own_observations(
        self, client: Client, event: Event, stored: str, auth: dict[str, str]
    ) -> None:
        pairing, _ = PairingCode.issue(event)
        _, other = Device.pair(pairing, name="Other")
        response = self.upload(client, stored, JPEG, {"Authorization": f"Bearer {other}"})
        assert response.status_code == 404


@pytest.mark.django_db
class TestProtocolContract:
    """protocol/ is what mobile developers build against, so keep it honest."""

    def test_openapi_file_is_current(self) -> None:
        call_command("export_openapi", "--check")

    def test_examples_are_accepted(
        self, client: Client, event: Event, finish_line: TimingPoint
    ) -> None:
        def example(name: str) -> dict[str, Any]:
            loaded: dict[str, Any] = json.loads((EXAMPLES / f"{name}.request.json").read_text())
            return loaded

        _, raw = PairingCode.issue(event, finish_line)
        pair_body = example("pair") | {"code": raw}
        token = post(client, "/pair", pair_body).json()["token"]
        auth = {"Authorization": f"Bearer {token}"}

        assert post(client, "/me/clock", example("clock"), headers=auth).status_code == 200
        assert post(client, "/me/heartbeat", example("heartbeat"), headers=auth).status_code == 200
        body = post(
            client, "/me/observations/batch", example("observations_batch"), headers=auth
        ).json()
        assert len(body["accepted"]) == 2, body
