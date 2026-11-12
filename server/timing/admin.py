# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin for devices. Stopgap until the organiser console's device dashboard (Phase 4)."""

import json
from typing import Any

from django import forms
from django.contrib import admin, messages
from django.db.models import Model, QuerySet
from django.http import HttpRequest
from django.utils import timezone

from timing.models import PAIRING_CODE_LIFETIME, Device, Heartbeat, Observation, PairingCode


class PairingCodeForm(forms.ModelForm[PairingCode]):
    class Meta:
        model = PairingCode
        fields = ("event", "timing_point")

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        event, point = data.get("event"), data.get("timing_point")
        if event and point and point.event_id != event.pk:
            raise forms.ValidationError("Pick a timing point from the same event.")
        return data


@admin.register(PairingCode)
class PairingCodeAdmin(admin.ModelAdmin[PairingCode]):
    """Adding a pairing code shows the code once. It can't be seen again, only replaced."""

    form = PairingCodeForm
    list_display = ("event", "timing_point", "created_at", "expires_at", "used_at")
    list_filter = ("event",)

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def save_model(self, request: HttpRequest, obj: PairingCode, form: Any, change: bool) -> None:
        raw = obj.assign_new_code()
        super().save_model(request, obj, form, change)
        qr_payload = json.dumps(
            {"v": 1, "server": request.build_absolute_uri("/"), "code": raw},
            separators=(",", ":"),
        )
        minutes = int(PAIRING_CODE_LIFETIME.total_seconds() // 60)
        messages.success(
            request,
            f"Pairing code {raw[:5]}-{raw[5:]} (valid for {minutes} minutes, one device). "
            f"QR payload: {qr_payload}",
        )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin[Device]):
    list_display = (
        "name",
        "event",
        "timing_point",
        "platform",
        "last_seen_at",
        "battery_pct",
        "clock_offset_ms",
        "revoked_at",
    )
    list_filter = ("event", "timing_point")
    readonly_fields = (
        "event",
        "platform",
        "app_version",
        "last_seen_at",
        "battery_pct",
        "temperature_c",
        "clock_offset_ms",
        "clock_rtt_ms",
        "revoked_at",
    )
    fields = ("name", "timing_point", "capture_config", *readonly_fields)
    actions = ("revoke",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False  # devices are created by pairing

    @admin.action(description="Revoke selected devices (they stop being able to upload)")
    def revoke(self, request: HttpRequest, queryset: QuerySet[Device]) -> None:
        count = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        messages.success(request, f"Revoked {count} device(s).")


class ReadOnlyAdmin[M: Model](admin.ModelAdmin[M]):
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Observation)
class ObservationAdmin(ReadOnlyAdmin[Observation]):
    list_display = ("__str__", "device", "captured_at", "confidence", "direction")
    list_filter = ("event", "timing_point", "device")
    date_hierarchy = "captured_at"


@admin.register(Heartbeat)
class HeartbeatAdmin(ReadOnlyAdmin[Heartbeat]):
    list_display = ("device", "created_at", "battery_pct", "temperature_c", "fps", "outbox_size")
    list_filter = ("event", "device")
