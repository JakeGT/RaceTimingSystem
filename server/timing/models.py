# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capture devices and what they send (rebuild plan §4-§5).

Observations are append-only and keyed by the UUID the phone generates, so a phone can
resend a batch after a dropped connection without creating duplicates.
"""

from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from common.models import UUIDModel
from events.models import Event, TimingPoint
from timing.secrets import hash_secret, new_device_token, new_pairing_code

PAIRING_CODE_LIFETIME = timedelta(minutes=15)


class PairingCode(UUIDModel):
    """A one-time code an organiser shows (as a QR code) so a phone can join an event."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="pairing_codes")
    timing_point = models.ForeignKey(
        TimingPoint,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="pairing_codes",
        help_text="Optional: put the device straight onto this timing point.",
    )
    code_hash = models.CharField(max_length=64, unique=True, editable=False)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"Pairing code for {self.event} (expires {self.expires_at:%H:%M})"

    def assign_new_code(self) -> str:
        """Give this (unsaved) row a fresh code and expiry. Returns the raw code, which is
        never stored: show it once, then it's gone."""
        raw = new_pairing_code()
        self.code_hash = hash_secret(raw)
        self.expires_at = timezone.now() + PAIRING_CODE_LIFETIME
        return raw

    @classmethod
    def issue(
        cls, event: Event, timing_point: TimingPoint | None = None
    ) -> tuple["PairingCode", str]:
        """Create and save a code. Returns the row and the raw code."""
        pairing = cls(event=event, timing_point=timing_point)
        raw = pairing.assign_new_code()
        pairing.save()
        return pairing, raw

    @property
    def is_usable(self) -> bool:
        return self.used_at is None and timezone.now() < self.expires_at


class Device(UUIDModel):
    """A phone (or the replay simulator) paired to one event."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="devices")
    timing_point = models.ForeignKey(
        TimingPoint, on_delete=models.SET_NULL, null=True, blank=True, related_name="devices"
    )
    name = models.CharField(max_length=100)
    platform = models.CharField(max_length=32, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    capture_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Line position, region of interest and thresholds, pushed to the device.",
    )

    # Latest heartbeat, for the device dashboard. History is in Heartbeat.
    last_seen_at = models.DateTimeField(null=True, blank=True)
    battery_pct = models.PositiveSmallIntegerField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    clock_offset_ms = models.IntegerField(
        null=True, blank=True, help_text="Server time minus device time, as the device measured it."
    )
    clock_rtt_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("event", "name")

    def __str__(self) -> str:
        return self.name

    @classmethod
    def pair(
        cls, pairing: PairingCode, *, name: str, platform: str = "", app_version: str = ""
    ) -> tuple["Device", str]:
        """Create a device from a pairing code. Returns the raw token, which is never stored."""
        token = new_device_token()
        device = cls.objects.create(
            event=pairing.event,
            timing_point=pairing.timing_point,
            name=name,
            platform=platform,
            app_version=app_version,
            token_hash=hash_secret(token),
        )
        return device, token

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None


class Heartbeat(UUIDModel):
    """Periodic device health report. Kept as history so drift and battery can be graphed."""

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="heartbeats", editable=False
    )
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="heartbeats")
    battery_pct = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MaxValueValidator(100)]
    )
    charging = models.BooleanField(null=True, blank=True)
    temperature_c = models.FloatField(null=True, blank=True)
    fps = models.FloatField(null=True, blank=True)
    outbox_size = models.PositiveIntegerField(null=True, blank=True)
    camera_ok = models.BooleanField(null=True, blank=True)
    clock_offset_ms = models.IntegerField(null=True, blank=True)
    clock_rtt_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ("device", "-created_at")
        indexes = (models.Index(fields=("device", "created_at")),)

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.event_id = self.device.event_id
        super().save(*args, **kwargs)


def crop_upload_path(observation: "Observation", filename: str) -> str:
    return f"crops/{observation.event_id}/{observation.pk}.jpg"


class Observation(models.Model):
    """One runner crossing a line, as one device saw it. Fusion (slice 1.4) merges
    observations from all devices at a timing point into reads.

    The primary key is the UUID the device generated, which makes uploads idempotent.
    """

    id = models.UUIDField(primary_key=True, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="observations")
    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="observations")
    timing_point = models.ForeignKey(
        TimingPoint, on_delete=models.PROTECT, related_name="observations"
    )
    captured_at_device = models.DateTimeField(help_text="Frame timestamp on the device's clock.")
    clock_offset_ms = models.IntegerField(help_text="Offset the device applied (server - device).")
    captured_at = models.DateTimeField(
        db_index=True, help_text="Frame timestamp on the server's clock."
    )
    track_id = models.IntegerField(null=True, blank=True)
    candidates = models.JSONField(
        default=list, help_text='Ranked bib guesses: [{"bib": "123", "confidence": 0.93}, ...]'
    )
    direction = models.CharField(max_length=8, blank=True)
    confidence = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence that a runner crossed at all (detection + tracking).",
    )
    crop = models.FileField(upload_to=crop_upload_path, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("timing_point", "captured_at")
        indexes = (models.Index(fields=("timing_point", "captured_at")),)

    def __str__(self) -> str:
        best = self.candidates[0]["bib"] if self.candidates else "?"
        return f"{best} @ {self.timing_point} {self.captured_at:%H:%M:%S.%f}"
