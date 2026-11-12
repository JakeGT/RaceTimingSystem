# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The versioned HTTP API. Its OpenAPI document is committed to protocol/openapi.json."""

from datetime import datetime
from typing import Any

from ninja import NinjaAPI
from ninja.renderers import JSONRenderer
from ninja.responses import NinjaJSONEncoder

from timing.api import router as devices_router


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
    description="Device protocol and (later) organiser API. See protocol/README.md.",
    urls_namespace="api-v1",
    renderer=PreciseJSONRenderer(),
)
api.add_router("/devices", devices_router)
