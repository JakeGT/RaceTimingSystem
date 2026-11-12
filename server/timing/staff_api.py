# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff API for devices: issuing pairing codes. Volunteers can do this ("run devices")."""

from datetime import datetime
from uuid import UUID

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router, Schema, Status
from ninja.errors import HttpError

from accounts.api import Error
from accounts.models import Role
from accounts.permissions import STAFF_AUTH, require_role
from events.models import Event, TimingPoint
from timing.models import PairingCode, pairing_qr_payload

router = Router(tags=["staff"], auth=STAFF_AUTH)


class PairingCodeIn(Schema):
    timing_point_id: UUID | None = None


class PairingCodeOut(Schema):
    code: str  # shown once; only its hash is stored
    expires_at: datetime
    qr_payload: str


@router.post(
    "/{event_id}/pairing-codes",
    response={201: PairingCodeOut, 400: Error, 403: Error, 404: Error},
    summary="Issue a one-use code (and QR payload) for pairing a phone to this event",
)
def issue_pairing_code(
    request: HttpRequest, event_id: UUID, payload: PairingCodeIn
) -> Status[PairingCodeOut]:
    event = get_object_or_404(Event.objects.select_related("organisation"), pk=event_id)
    require_role(request, event.organisation, Role.VOLUNTEER)
    point = None
    if payload.timing_point_id is not None:
        point = TimingPoint.objects.filter(pk=payload.timing_point_id, event=event).first()
        if point is None:
            raise HttpError(400, "That timing point isn't part of this event.")
    pairing, raw = PairingCode.issue(event, point)
    return Status(
        201,
        PairingCodeOut(
            code=raw,
            expires_at=pairing.expires_at,
            qr_payload=pairing_qr_payload(request.build_absolute_uri("/"), raw),
        ),
    )
