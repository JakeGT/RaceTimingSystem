# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Events, races and entries (rebuild plan §4).

Every model that belongs to an event carries an `event` foreign key, even where it
could be reached through a parent, so exporting or checking out an event is one
query per table (ADR 0002). Child models fill it in from their parent on save.
"""

from datetime import date, timedelta
from functools import cache
from zoneinfo import available_timezones

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, RegexValidator
from django.db import models

from accounts.models import Organisation
from common.models import UUIDModel
from events.categories import Band, age_on, pick_category


@cache
def _timezones() -> frozenset[str]:
    return frozenset(available_timezones())


def validate_timezone(value: str) -> None:
    if value not in _timezones():
        raise ValidationError(f"{value!r} isn't a known IANA timezone (e.g. Europe/London).")


class Gender(models.TextChoices):
    FEMALE = "female", "Female"
    MALE = "male", "Male"
    NON_BINARY = "non_binary", "Non-binary"
    UNDISCLOSED = "undisclosed", "Prefer not to say"


# --------------------------------------------------------------------------- categories


class CategoryScheme(UUIDModel):
    """A reusable set of age/gender categories, e.g. "England Athletics road running"."""

    class AgeBasis(models.TextChoices):
        RACE_DAY = "race_day", "Age on race day"
        YEAR_END = "year_end", "Age on 31 December of the race year"

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="category_schemes"
    )
    name = models.CharField(max_length=150)
    age_basis = models.CharField(max_length=16, choices=AgeBasis.choices, default=AgeBasis.RACE_DAY)

    class Meta:
        ordering = ("name",)
        constraints = (
            models.UniqueConstraint(
                fields=("organisation", "name"), name="unique_scheme_name_per_organisation"
            ),
        )

    def __str__(self) -> str:
        return self.name

    def reference_date(self, race_day: date) -> date:
        if self.age_basis == self.AgeBasis.YEAR_END:
            return date(race_day.year, 12, 31)
        return race_day

    def bands(self) -> list[Band]:
        return [rule.as_band() for rule in self.rules.all()]


class CategoryRule(UUIDModel):
    """One category in a scheme. Rules are checked in `order`; the first match wins."""

    scheme = models.ForeignKey(CategoryScheme, on_delete=models.CASCADE, related_name="rules")
    code = models.CharField(max_length=16, help_text="Short label shown in results, e.g. MV40.")
    name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(
        max_length=16, choices=Gender.choices, blank=True, help_text="Blank matches any gender."
    )
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    max_age = models.PositiveSmallIntegerField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("scheme", "order")
        constraints = (
            models.UniqueConstraint(fields=("scheme", "code"), name="unique_category_code"),
            models.CheckConstraint(
                condition=models.Q(min_age__isnull=True)
                | models.Q(max_age__isnull=True)
                | models.Q(min_age__lte=models.F("max_age")),
                name="category_min_age_lte_max_age",
            ),
        )

    def __str__(self) -> str:
        return self.code

    def as_band(self) -> Band:
        return Band(self.code, self.gender, self.min_age, self.max_age)


# -------------------------------------------------------------------------- event tree


class Event(UUIDModel):
    """A race day (or weekend) at one venue. Times are stored in UTC and shown in
    the event's own timezone."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"
        FINISHED = "finished", "Finished"

    organisation = models.ForeignKey(Organisation, on_delete=models.PROTECT, related_name="events")
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=80)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True, help_text="Leave blank for one-day events.")
    timezone = models.CharField(
        max_length=64, default="Europe/London", validators=[validate_timezone]
    )
    venue_name = models.CharField(max_length=150, blank=True)
    address = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    longitude = models.DecimalField(max_digits=8, decimal_places=5, null=True, blank=True)
    website = models.URLField(blank=True)

    class Meta:
        ordering = ("-start_date", "name")
        constraints = (
            models.UniqueConstraint(
                fields=("organisation", "slug"), name="unique_event_slug_per_organisation"
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="event_end_date_after_start",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} ({self.start_date:%Y-%m-%d})"


class TimingPoint(UUIDModel):
    """A physical line where phones watch for runners, e.g. "Finish" or "Bridge".

    Several races can share one (a 5 km and a 10 km with the same finish), and one race
    can pass it more than once (laps). Races map onto timing points through Splits.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="timing_points")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ("event", "name")
        constraints = (
            models.UniqueConstraint(fields=("event", "name"), name="unique_timing_point_name"),
        )

    def __str__(self) -> str:
        return self.name


class Race(UUIDModel):
    """One race within an event, e.g. "10K" or "Junior 2K"."""

    class RankingBasis(models.TextChoices):
        GUN = "gun", "Gun time (from the wave start)"
        NET = "net", "Net time (from crossing the start line)"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="races")
    name = models.CharField(max_length=100)
    distance_m = models.PositiveIntegerField("distance (metres)")
    ranking_basis = models.CharField(
        max_length=8, choices=RankingBasis.choices, default=RankingBasis.GUN
    )
    category_scheme = models.ForeignKey(
        CategoryScheme, on_delete=models.PROTECT, null=True, blank=True, related_name="races"
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("event", "order", "name")
        constraints = (models.UniqueConstraint(fields=("event", "name"), name="unique_race_name"),)

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        scheme = self.category_scheme
        if (
            scheme is not None
            and self.event_id
            and scheme.organisation_id != self.event.organisation_id
        ):
            raise ValidationError(
                {"category_scheme": "Use a category scheme from the event's organisation."}
            )
        if self.ranking_basis == self.RankingBasis.NET and self.pk:
            has_start = self.splits.filter(kind=Split.Kind.START).exists()
            if not has_start:
                raise ValidationError(
                    {"ranking_basis": "Net-time ranking needs a start split on this race."}
                )


class Wave(UUIDModel):
    """A group of runners in a race that starts together. Every race has at least one.

    `start_at` is set when the starter presses the start button (or from a start-line
    read) and is the zero point for gun times.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="waves", editable=False)
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="waves")
    name = models.CharField(max_length=100, default="Main")
    start_at = models.DateTimeField(null=True, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("race", "order", "name")
        constraints = (models.UniqueConstraint(fields=("race", "name"), name="unique_wave_name"),)

    def __str__(self) -> str:
        return f"{self.race} - {self.name}"

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.event_id = self.race.event_id
        super().save(*args, **kwargs)


class Split(UUIDModel):
    """One point on a race's course: where a timing point falls along the route.

    A lapped race lists the same timing point several times. `min_elapsed` helps tell
    the passes apart: reads sooner than that after the start don't count for this split.
    """

    class Kind(models.TextChoices):
        START = "start", "Start"
        SPLIT = "split", "Split"
        FINISH = "finish", "Finish"

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="splits", editable=False
    )
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="splits")
    timing_point = models.ForeignKey(TimingPoint, on_delete=models.PROTECT, related_name="splits")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.SPLIT)
    name = models.CharField(max_length=100, blank=True, help_text='e.g. "5 km" or "Lap 1".')
    distance_m = models.PositiveIntegerField("distance from start (metres)", default=0)
    order = models.PositiveSmallIntegerField(default=0)
    min_elapsed = models.DurationField(null=True, blank=True)

    class Meta:
        ordering = ("race", "order")
        constraints = (
            models.UniqueConstraint(fields=("race", "order"), name="unique_split_order"),
            models.UniqueConstraint(
                fields=("race",),
                condition=models.Q(kind="start"),
                name="one_start_split_per_race",
            ),
            models.UniqueConstraint(
                fields=("race",),
                condition=models.Q(kind="finish"),
                name="one_finish_split_per_race",
            ),
        )

    def __str__(self) -> str:
        return self.name or f"{self.get_kind_display()} @ {self.timing_point}"

    def clean(self) -> None:
        if (
            self.race_id
            and self.timing_point_id
            and self.timing_point.event_id != self.race.event_id
        ):
            raise ValidationError({"timing_point": "Pick a timing point from the same event."})
        if self.race_id and self.distance_m > self.race.distance_m:
            raise ValidationError({"distance_m": "A split can't be past the race distance."})
        if self.min_elapsed is not None and self.min_elapsed < timedelta(0):
            raise ValidationError({"min_elapsed": "Must not be negative."})

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.event_id = self.race.event_id
        super().save(*args, **kwargs)


class Entry(UUIDModel):
    """A runner entered in a race. Not linked to an account (ADR 0002).

    Bibs are unique across the whole event, because one finish line can serve several
    races and a bib read has to identify exactly one entry. `status` only records
    what a person decides (DNS/DNF/DSQ); started/finished come from timing data.
    """

    class Status(models.TextChoices):
        ENTERED = "entered", "Entered"
        DNS = "dns", "Did not start"
        DNF = "dnf", "Did not finish"
        DSQ = "dsq", "Disqualified"

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name="entries", editable=False
    )
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name="entries")
    wave = models.ForeignKey(
        Wave,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="entries",
        help_text="Leave blank if the race has a single wave.",
    )
    bib = models.CharField(
        max_length=16,
        validators=[RegexValidator(r"^[0-9A-Za-z-]+$", "Letters, digits and hyphens only.")],
    )
    given_name = models.CharField(max_length=100)
    family_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=16, choices=Gender.choices, default=Gender.UNDISCLOSED)
    date_of_birth = models.DateField(
        null=True, blank=True, help_text="Only needed for age categories. Never published."
    )
    declared_age = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(120)],
        help_text="Age on race day, if there's no date of birth.",
    )
    club = models.CharField(max_length=150, blank=True)
    email = models.EmailField(blank=True, help_text="Used only to send results.")
    hide_name = models.BooleanField(
        default=False, help_text='Show as "Anonymous" in public results.'
    )
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.ENTERED)
    status_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("event", "bib")
        verbose_name_plural = "entries"
        constraints = (
            models.UniqueConstraint(fields=("event", "bib"), name="unique_bib_per_event"),
        )
        indexes = (models.Index(fields=("race", "family_name", "given_name")),)

    def __str__(self) -> str:
        return f"{self.bib} {self.full_name}"

    @property
    def full_name(self) -> str:
        return f"{self.given_name} {self.family_name}".strip()

    @property
    def public_name(self) -> str:
        return "Anonymous" if self.hide_name else self.full_name

    def age_for_categories(self) -> int | None:
        scheme = self.race.category_scheme
        race_day = self.race.event.start_date
        if self.date_of_birth is not None:
            reference = scheme.reference_date(race_day) if scheme else race_day
            return age_on(self.date_of_birth, reference)
        return self.declared_age

    def category(self) -> Band | None:
        scheme = self.race.category_scheme
        if scheme is None:
            return None
        return pick_category(scheme.bands(), self.gender, self.age_for_categories())

    def clean(self) -> None:
        if self.wave is not None and self.race_id and self.wave.race_id != self.race_id:
            raise ValidationError({"wave": "Pick a wave from the same race."})
        if self.wave_id is None and self.race_id and self.race.waves.count() > 1:
            raise ValidationError({"wave": "This race has several waves, so pick one."})

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.event_id = self.race.event_id
        super().save(*args, **kwargs)
