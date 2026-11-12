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

from events.admin import ChangeReasonForm, actor
from events.models import Entry
from timing import review
from timing.models import (
    PAIRING_CODE_LIFETIME,
    Adjustment,
    Device,
    Heartbeat,
    Observation,
    PairingCode,
    Read,
)


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


class ReadForm(ChangeReasonForm[Read]):
    class Meta:
        model = Read
        fields = ("event", "timing_point", "bib", "at")

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        event = data.get("event") or (self.instance.event if self.instance.event_id else None)
        point = data.get("timing_point")
        if event and point and point.event_id != event.pk:
            self.add_error("timing_point", "Pick a timing point from the same event.")
        bib = (data.get("bib") or "").strip()
        if "bib" in self.changed_data or not self.instance.pk:
            if not bib:
                self.add_error("bib", "Enter a bib.")
            elif event and not Entry.objects.filter(event=event, bib=bib).exists():
                self.add_error("bib", f"Nobody in this event has bib {bib!r}.")
        needs_reason = not self.instance.pk or "at" in self.changed_data
        if needs_reason and not data.get("change_reason", "").strip():
            self.add_error("change_reason", "Say why: this change shows in the audit log.")
        return data


class ObservationInline(admin.TabularInline[Observation, Read]):
    model = Observation
    fields = ("device", "captured_at", "candidates", "crop")
    readonly_fields = fields
    extra = 0
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


@admin.register(Read)
class ReadAdmin(admin.ModelAdmin[Read]):
    """The review queue until the review console exists. Filter by "Needs review".

    Adding a read here records a manual read. Every change goes through timing.review.
    """

    form = ReadForm
    list_display = (
        "bib",
        "timing_point",
        "time",
        "state",
        "review_reason",
        "suggested_bib",
        "confidence",
    )
    list_filter = ("event", "timing_point", "state", "review_reason")
    search_fields = ("bib", "suggested_bib")
    readonly_fields = ("state", "review_reason", "suggested_bib", "confidence")
    inlines = (ObservationInline,)
    actions = ("confirm", "reject")

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        if obj is None:
            return ()
        return (*self.readonly_fields, "event", "timing_point")

    def get_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        if obj is None:
            return ("event", "timing_point", "bib", "at", "change_reason")
        return ("event", "timing_point", "bib", "at", "change_reason", *self.readonly_fields)

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False  # reject instead, so the audit log explains it

    @admin.display(description="Time", ordering="at")
    def time(self, obj: Read) -> str:
        return f"{obj.at:%H:%M:%S.%f}"[:-3]

    @admin.action(description="Confirm selected reads")
    def confirm(self, request: HttpRequest, queryset: QuerySet[Read]) -> None:
        self._apply(request, queryset, review.confirm_read, "Confirmed")

    @admin.action(description="Reject selected reads")
    def reject(self, request: HttpRequest, queryset: QuerySet[Read]) -> None:
        self._apply(request, queryset, review.reject_read, "Rejected")

    def _apply(
        self, request: HttpRequest, queryset: QuerySet[Read], change: Any, verb: str
    ) -> None:
        done, problems = 0, []
        for read in queryset:
            try:
                change(read, actor(request))
                done += 1
            except review.ReviewError as e:
                problems.append(f"{read}: {e}")
        messages.success(request, f"{verb} {done} read(s).")
        for problem in problems:
            messages.warning(request, problem)

    def save_model(self, request: HttpRequest, obj: Read, form: Any, change: bool) -> None:
        by, reason = actor(request), form.cleaned_data["change_reason"]
        if not change:
            read = review.add_manual_read(obj.event, obj.timing_point, obj.bib, obj.at, by, reason)
            obj.pk = read.pk
            return
        if "bib" in form.changed_data:
            review.assign_bib(obj, obj.bib, by, reason)
        if "at" in form.changed_data:
            review.adjust_time(obj, obj.at, by, reason)
        obj.refresh_from_db()


@admin.register(Adjustment)
class AdjustmentAdmin(ReadOnlyAdmin[Adjustment]):
    list_display = ("created_at", "action", "actor_label", "read", "entry", "wave", "reason")
    list_filter = ("event", "action")
    search_fields = ("actor_label", "reason")

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False  # append-only
