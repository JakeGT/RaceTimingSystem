# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Stored results: the last output of results.engine for each race.

These rows are a cache, never edited by hand. Change reads or entries through
timing.review and the race is rebuilt; `rebuild_results` rebuilds everything.
"""

from django.db import models

from common.models import UUIDModel
from events.models import Entry, Event, Race


class RaceResults(UUIDModel):
    """When a race was last rebuilt, and any problems with how it's set up."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="race_results")
    race = models.OneToOneField(Race, on_delete=models.CASCADE, related_name="computed")
    warnings = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField()

    class Meta:
        verbose_name_plural = "race results"

    def __str__(self) -> str:
        return f"{self.race} (computed {self.computed_at:%H:%M:%S})"


class Result(UUIDModel):
    class Outcome(models.TextChoices):
        FINISHED = "finished", "Finished"
        ON_COURSE = "on_course", "On course"
        NO_READS = "no_reads", "Started, not seen"
        AWAITING_START = "awaiting_start", "Waiting for start"
        DNF = "dnf", "Did not finish"
        DNS = "dns", "Did not start"
        DSQ = "dsq", "Disqualified"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="results")
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="results")
    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, related_name="result")
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    gun_time = models.DurationField(null=True, blank=True)
    net_time = models.DurationField(null=True, blank=True)
    ranking_time = models.DurationField(null=True, blank=True)
    overall_position = models.PositiveIntegerField(null=True, blank=True)
    gender_position = models.PositiveIntegerField(null=True, blank=True)
    category = models.CharField(max_length=16, blank=True)
    category_position = models.PositiveIntegerField(null=True, blank=True)
    splits = models.JSONField(
        default=list,
        blank=True,
        help_text='[{"split": id, "read": id, "at": ISO time, "elapsed_us": int}, ...]',
    )
    missing_splits = models.JSONField(default=list, blank=True)
    flags = models.JSONField(default=list, blank=True)
    computed_at = models.DateTimeField()

    class Meta:
        ordering = ("race", "overall_position")
        indexes = (models.Index(fields=("race", "overall_position")),)

    def __str__(self) -> str:
        return f"{self.entry.bib}: {self.get_outcome_display()}"
