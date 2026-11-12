# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The versioned HTTP API. Its OpenAPI document is committed to protocol/openapi.json."""

from datetime import datetime
from typing import Any

from django.http import HttpRequest, HttpResponse
from ninja import NinjaAPI
from ninja.renderers import JSONRenderer
from ninja.responses import NinjaJSONEncoder

from accounts.api import public_router as invitations_router
from accounts.api import router as staff_router
from accounts.permissions import MfaRequired
from timing.api import router as devices_router
from timing.staff_api import router as staff_devices_router


class PreciseJSONEncoder(NinjaJSONEncoder):
    """Keep microseconds on datetimes. Django's encoder cuts them to milliseconds, which
    floors every clock-sync timestamp and biases timing by up to a millisecond."""

    def default(self, o: Any) -> Any:
        if isinstance(o, datetime):
            text = o.isoformat()
            return text.removesuffix("+00:00") + "Z" if text.endswith("+00:00") else text
        return super().default(o)


class PreciseJSONRenderer(JSONRenderer):
    encoder_class = PreciseJSONEncoder


api = NinjaAPI(
    title="Race Timing System API",
    version="1",
    description=(
        "Device protocol (see protocol/README.md) and the staff API. Staff sign in through "
        "allauth's headless API at /api/auth/ (session cookie or X-Session-Token)."
    ),
    urls_namespace="api-v1",
    renderer=PreciseJSONRenderer(),
)
api.add_router("/devices", devices_router)
api.add_router("/staff", staff_router)
api.add_router("/staff/events", staff_devices_router)
api.add_router("/invitations", invitations_router)


@api.exception_handler(MfaRequired)
def mfa_required(request: HttpRequest, exc: MfaRequired) -> HttpResponse:
    return api.create_response(request, {"detail": str(exc), "code": "mfa_required"}, status=403)
