# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Device ⇄ server protocol (rebuild plan §5). Mounted at /api/v1/devices/.

Flow for a phone: pair with a one-time code → fetch config → sync its clock → send
observations in batches (and crops separately) → heartbeat every few seconds. Every
call after pairing uses `Authorization: Bearer <device token>`.
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Annotated, Any, Literal
from uuid import UUID

from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from ninja import Field, File, Router, Schema, Status
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.security import HttpBearer
from ninja.throttling import AnonRateThrottle

from events.models import Entry, TimingPoint
from timing.models import Device, Heartbeat, Observation, PairingCode
from timing.secrets import hash_secret, normalise_pairing_code

MAX_BATCH = 500
MAX_CROP_BYTES = 512 * 1024
MAX_FUTURE = timedelta(minutes=5)
MAX_CLOCK_OFFSET_MS = 24 * 3600 * 1000
BIB_PATTERN = r"^[0-9A-Za-z-]{1,16}$"


class DeviceAuth(HttpBearer):
    def authenticate(self, request: HttpRequest, token: str) -> Device | None:
        return (
            Device.objects.select_related("event", "timing_point")
            .filter(token_hash=hash_secret(token), revoked_at__isnull=True)
            .first()
        )


def current_device(request: HttpRequest) -> Device:
    device = getattr(request, "auth", None)
    if not isinstance(device, Device):  # only reachable if a route forgets auth=
        raise HttpError(401, "Device authentication required.")
    return device


router = Router(tags=["devices"], auth=DeviceAuth())


# ------------------------------------------------------------------------------ schemas


class Error(Schema):
    detail: str


class EventInfo(Schema):
    id: UUID
    name: str
    timezone: str
    start_date: str


class TimingPointInfo(Schema):
    id: UUID
    name: str


class PairIn(Schema):
    code: str = Field(min_length=4, max_length=32, description="Code from the pairing QR.")
    name: str = Field(min_length=1, max_length=100, description='e.g. "Finish - left tripod".')
    platform: str = Field("", max_length=32, description='e.g. "ios" or "android".')
    app_version: str = Field("", max_length=32)


class PairOut(Schema):
    device_id: UUID
    token: str = Field(description="Send as `Authorization: Bearer <token>`. Shown once.")
    event: EventInfo
    timing_point_id: UUID | None
    server_time: datetime


class DeviceConfig(Schema):
    device_id: UUID
    name: str
    event: EventInfo
    timing_point_id: UUID | None
    timing_points: list[TimingPointInfo]
    capture_config: dict[str, Any]
    bibs: list[str] = Field(description="Every bib entered in the event, for snapping reads.")
    config_version: str = Field(description="Changes whenever anything above changes.")
    server_time: datetime


class TimingPointIn(Schema):
    timing_point_id: UUID | None


class ClockIn(Schema):
    client_sent_at: datetime = Field(description="Device clock when the request was sent (t0).")


class ClockOut(Schema):
    """NTP-style exchange. With t3 = device clock when the response arrives:
    offset = ((t1 - t0) + (t2 - t3)) / 2 and round trip = (t3 - t0) - (t2 - t1)."""

    client_sent_at: datetime
    server_received_at: datetime
    server_sent_at: datetime


class HeartbeatIn(Schema):
    battery_pct: int | None = Field(None, ge=0, le=100)
    charging: bool | None = None
    temperature_c: float | None = Field(None, ge=-40, le=120)
    fps: float | None = Field(None, ge=0, le=1000)
    outbox_size: int | None = Field(None, ge=0)
    camera_ok: bool | None = None
    clock_offset_ms: int | None = Field(None, ge=-MAX_CLOCK_OFFSET_MS, le=MAX_CLOCK_OFFSET_MS)
    clock_rtt_ms: int | None = Field(None, ge=0, le=60_000)
    app_version: str | None = Field(None, max_length=32)


class HeartbeatOut(Schema):
    server_time: datetime
    config_version: str


class Candidate(Schema):
    bib: Annotated[str, Field(pattern=BIB_PATTERN)]
    confidence: float = Field(ge=0, le=1)


class ObservationIn(Schema):
    id: UUID = Field(description="Generated on the device (UUIDv7 recommended). Idempotency key.")
    timing_point_id: UUID | None = Field(
        None, description="Defaults to the device's assigned timing point."
    )
    captured_at_device: datetime = Field(
        description="Frame timestamp on the device clock, with timezone."
    )
    clock_offset_ms: int = Field(
        ge=-MAX_CLOCK_OFFSET_MS,
        le=MAX_CLOCK_OFFSET_MS,
        description="Server time minus device time, as measured by the device.",
    )
    track_id: int | None = None
    candidates: list[Candidate] = Field(
        default_factory=list, max_length=5, description="Best guess first. Empty if unreadable."
    )
    direction: Literal["forward", "reverse"] | None = None
    confidence: float | None = Field(None, ge=0, le=1)


class ObservationBatchIn(Schema):
    observations: list[ObservationIn] = Field(min_length=1, max_length=MAX_BATCH)


RejectReason = Literal[
    "no_timing_point", "timing_point_not_in_event", "in_future", "id_used_by_another_device"
]


class Rejection(Schema):
    id: UUID
    reason: RejectReason


class ObservationBatchOut(Schema):
    accepted: list[UUID] = Field(description="Stored now.")
    duplicates: list[UUID] = Field(description="Already stored from an earlier upload: fine.")
    rejected: list[Rejection] = Field(description="Won't be stored. Don't resend.")


# ---------------------------------------------------------------------------- helpers


def _event_info(device: Device) -> EventInfo:
    event = device.event
    return EventInfo(
        id=event.pk, name=event.name, timezone=event.timezone, start_date=str(event.start_date)
    )


def _config(device: Device) -> DeviceConfig:
    points = [
        TimingPointInfo(id=p.pk, name=p.name)
        for p in TimingPoint.objects.filter(event=device.event_id).order_by("name")
    ]
    bibs = sorted(
        Entry.objects.filter(event=device.event_id).values_list("bib", flat=True),
        key=lambda b: (0, int(b), "") if b.isdigit() else (1, 0, b),
    )
    body = {
        "device_id": str(device.pk),
        "name": device.name,
        "event": _event_info(device).model_dump(mode="json"),
        "timing_point_id": str(device.timing_point_id) if device.timing_point_id else None,
        "timing_points": [p.model_dump(mode="json") for p in points],
        "capture_config": device.capture_config,
        "bibs": bibs,
    }
    version = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()[:16]
    return DeviceConfig(**body, config_version=version, server_time=timezone.now())


def _touch(device: Device) -> None:
    Device.objects.filter(pk=device.pk).update(last_seen_at=timezone.now())


# -------------------------------------------------------------------------- endpoints


@router.post(
    "/pair",
    auth=None,
    throttle=[AnonRateThrottle("10/m")],
    response={201: PairOut, 400: Error},
    summary="Pair a device with a one-time code",
)
def pair(request: HttpRequest, payload: PairIn) -> Status[PairOut]:
    now = timezone.now()
    code_hash = hash_secret(normalise_pairing_code(payload.code))
    with transaction.atomic():
        pairing = (
            PairingCode.objects.select_related("event")
            .filter(code_hash=code_hash, used_at__isnull=True, expires_at__gt=now)
            .first()
        )
        # Conditional update so two phones racing for the same code can't both win.
        if (
            pairing is None
            or PairingCode.objects.filter(pk=pairing.pk, used_at__isnull=True).update(used_at=now)
            != 1
        ):
            raise HttpError(400, "That pairing code is wrong, used or expired.")
        device, token = Device.pair(
            pairing, name=payload.name, platform=payload.platform, app_version=payload.app_version
        )
    return Status(
        201,
        PairOut(
            device_id=device.pk,
            token=token,
            event=_event_info(device),
            timing_point_id=device.timing_point_id,
            server_time=timezone.now(),
        ),
    )


@router.get("/me", response=DeviceConfig, summary="Get this device's configuration")
def get_config(request: HttpRequest) -> DeviceConfig:
    device = current_device(request)
    _touch(device)
    return _config(device)


@router.put(
    "/me/timing-point",
    response={200: DeviceConfig, 400: Error},
    summary="Choose which timing point this device is watching",
)
def set_timing_point(request: HttpRequest, payload: TimingPointIn) -> DeviceConfig:
    device = current_device(request)
    if payload.timing_point_id is not None:
        point = TimingPoint.objects.filter(
            pk=payload.timing_point_id, event=device.event_id
        ).first()
        if point is None:
            raise HttpError(400, "That timing point isn't part of this device's event.")
        device.timing_point = point
    else:
        device.timing_point = None
    device.save(update_fields=["timing_point", "updated_at"])
    return _config(device)


@router.post("/me/clock", response=ClockOut, summary="Clock sync exchange (NTP-style)")
def clock(request: HttpRequest, payload: ClockIn) -> ClockOut:
    received = timezone.now()
    return ClockOut(
        client_sent_at=payload.client_sent_at,
        server_received_at=received,
        server_sent_at=timezone.now(),
    )


@router.post("/me/heartbeat", response=HeartbeatOut, summary="Report device health")
def heartbeat(request: HttpRequest, payload: HeartbeatIn) -> HeartbeatOut:
    device = current_device(request)
    data = payload.model_dump(exclude={"app_version"})
    Heartbeat.objects.create(device=device, **data)
    device.last_seen_at = timezone.now()
    device.battery_pct = payload.battery_pct
    device.temperature_c = payload.temperature_c
    device.clock_offset_ms = payload.clock_offset_ms
    device.clock_rtt_ms = payload.clock_rtt_ms
    if payload.app_version:
        device.app_version = payload.app_version
    device.save()
    return HeartbeatOut(server_time=timezone.now(), config_version=_config(device).config_version)


@router.post(
    "/me/observations/batch",
    response=ObservationBatchOut,
    summary="Upload observations (idempotent: resending a batch is safe)",
)
def upload_observations(request: HttpRequest, payload: ObservationBatchIn) -> ObservationBatchOut:
    device = current_device(request)
    now = timezone.now()
    event_points = set(
        TimingPoint.objects.filter(event=device.event_id).values_list("pk", flat=True)
    )
    ids = [o.id for o in payload.observations]
    existing = dict(Observation.objects.filter(pk__in=ids).values_list("pk", "device_id"))

    accepted: list[UUID] = []
    duplicates: list[UUID] = []
    rejected: list[Rejection] = []
    new: dict[UUID, Observation] = {}
    for obs in payload.observations:
        if obs.id in existing:
            if existing[obs.id] == device.pk:
                duplicates.append(obs.id)
            else:
                rejected.append(Rejection(id=obs.id, reason="id_used_by_another_device"))
            continue
        if obs.id in new:  # repeated within the same batch
            duplicates.append(obs.id)
            continue
        point_id = obs.timing_point_id or device.timing_point_id
        if point_id is None:
            rejected.append(Rejection(id=obs.id, reason="no_timing_point"))
            continue
        if point_id not in event_points:
            rejected.append(Rejection(id=obs.id, reason="timing_point_not_in_event"))
            continue
        captured_at = obs.captured_at_device + timedelta(milliseconds=obs.clock_offset_ms)
        if captured_at > now + MAX_FUTURE:
            rejected.append(Rejection(id=obs.id, reason="in_future"))
            continue
        new[obs.id] = Observation(
            id=obs.id,
            event_id=device.event_id,
            device=device,
            timing_point_id=point_id,
            captured_at_device=obs.captured_at_device,
            clock_offset_ms=obs.clock_offset_ms,
            captured_at=captured_at,
            track_id=obs.track_id,
            candidates=[c.model_dump() for c in obs.candidates],
            direction=obs.direction or "",
            confidence=obs.confidence,
        )
        accepted.append(obs.id)

    with transaction.atomic():
        # ignore_conflicts covers two copies of the same batch arriving at once.
        Observation.objects.bulk_create(new.values(), ignore_conflicts=True)
        Device.objects.filter(pk=device.pk).update(last_seen_at=now)
    return ObservationBatchOut(accepted=accepted, duplicates=duplicates, rejected=rejected)


@router.post(
    "/me/observations/{observation_id}/crop",
    response={204: None, 400: Error, 404: Error},
    summary="Upload the crop image for an observation (JPEG, replaces any earlier upload)",
)
def upload_crop(
    request: HttpRequest, observation_id: UUID, image: File[UploadedFile]
) -> Status[None]:
    device = current_device(request)
    observation = Observation.objects.filter(pk=observation_id, device=device).first()
    if observation is None:
        raise HttpError(404, "No observation with that id from this device.")
    if image.size is None or image.size > MAX_CROP_BYTES:
        raise HttpError(400, f"Crops must be at most {MAX_CROP_BYTES // 1024} KB.")
    if image.read(3) != b"\xff\xd8\xff":
        raise HttpError(400, "Crops must be JPEG images.")
    image.seek(0)
    if observation.crop:
        observation.crop.delete(save=False)
    observation.crop.save(f"{observation.pk}.jpg", image, save=True)
    return Status(204, None)
