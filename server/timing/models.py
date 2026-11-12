# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capture devices and what they send (rebuild plan §4-§5).

Observations are append-only and keyed by the UUID the phone generates, so a phone can
resend a batch after a dropped connection without creating duplicates.
"""

from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from common.models import UUIDModel
from events.models import Entry, Event, TimingPoint, Wave
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
    read = models.ForeignKey(
        "Read",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
        help_text="The read fusion merged this into. Empty until fusion has run.",
    )

    class Meta:
        ordering = ("timing_point", "captured_at")
        indexes = (models.Index(fields=("timing_point", "captured_at")),)

    def __str__(self) -> str:
        best = self.candidates[0]["bib"] if self.candidates else "?"
        return f"{best} @ {self.timing_point} {self.captured_at:%H:%M:%S.%f}"


class Read(UUIDModel):
    """One runner crossing a timing point: what the results engine consumes.

    Fusion makes reads from observations. People confirm, reject or correct them, or
    add manual reads, always through timing.review so every change is audited.
    """

    class State(models.TextChoices):
        AUTO = "auto", "Accepted automatically"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CONFIRMED = "confirmed", "Confirmed by a person"
        REJECTED = "rejected", "Rejected"
        MANUAL = "manual", "Added by a person"

    class ReviewReason(models.TextChoices):
        UNREADABLE = "unreadable", "Bib couldn't be read"
        NOT_ENTERED = "not_entered", "Bib read, but nobody has that bib"
        LOW_CONFIDENCE = "low_confidence", "Low confidence"
        AMBIGUOUS = "ambiguous", "Two bibs almost equally likely"

    ACCEPTED_STATES = (State.AUTO, State.CONFIRMED, State.MANUAL)

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="reads")
    timing_point = models.ForeignKey(TimingPoint, on_delete=models.PROTECT, related_name="reads")
    bib = models.CharField(max_length=16, blank=True, help_text="Blank while unknown.")
    at = models.DateTimeField(help_text="Crossing time on the server clock.")
    state = models.CharField(max_length=16, choices=State.choices)
    review_reason = models.CharField(max_length=16, choices=ReviewReason.choices, blank=True)
    suggested_bib = models.CharField(
        max_length=16, blank=True, help_text="Best guess when the bib isn't an entered one."
    )
    confidence = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ("timing_point", "at")
        indexes = (
            models.Index(fields=("timing_point", "bib", "at")),
            models.Index(fields=("event", "state")),
        )

    def __str__(self) -> str:
        return f"{self.bib or '?'} @ {self.timing_point} {self.at:%H:%M:%S}"

    @property
    def is_accepted(self) -> bool:
        return self.state in self.ACCEPTED_STATES and bool(self.bib)


class Adjustment(UUIDModel):
    """Append-only audit log of every change a person makes to timing data.

    `actor` is set for signed-in staff; `actor_label` names everyone else (a venue
    staff session, a device, a system process), because those have no User row and
    the log has to survive being exported to another server (ADR 0002).
    """

    class Action(models.TextChoices):
        READ_CONFIRMED = "read_confirmed", "Read confirmed"
        READ_REJECTED = "read_rejected", "Read rejected"
        READ_BIB_CHANGED = "read_bib_changed", "Read bib changed"
        READ_TIME_CHANGED = "read_time_changed", "Read time changed"
        READ_ADDED = "read_added", "Manual read added"
        ENTRY_STATUS_CHANGED = "entry_status_changed", "Entry status changed"
        WAVE_STARTED = "wave_started", "Wave started"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="adjustments")
    action = models.CharField(max_length=32, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adjustments",
    )
    actor_label = models.CharField(max_length=150)
    read = models.ForeignKey(
        Read, on_delete=models.SET_NULL, null=True, blank=True, related_name="adjustments"
    )
    entry = models.ForeignKey(
        Entry, on_delete=models.SET_NULL, null=True, blank=True, related_name="adjustments"
    )
    wave = models.ForeignKey(
        Wave, on_delete=models.SET_NULL, null=True, blank=True, related_name="adjustments"
    )
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("event", "-created_at")

    def __str__(self) -> str:
        return f"{self.get_action_display()} by {self.actor_label}"
