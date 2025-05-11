from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


# Create your models here.

class CustomUser(AbstractUser):
    is_runner = models.BooleanField(default=False)
    is_organiser = models.BooleanField(default=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)


class Race(models.Model):
    name = models.CharField(max_length=150)
    start_datetime = models.DateTimeField()
    race_category = models.ForeignKey(
        "RaceCategory", on_delete=models.SET_NULL, null=True, blank=True
    )
    participant_categories = models.ManyToManyField(
        "ParticipantCategory", related_name="races"
    )
    organisers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="organised_races",
        limit_choices_to={"is_organiser": True},
        blank=True,
    )
    participants = models.ManyToManyField(
        "Participant", related_name="races", blank=True
    )
    is_completed = models.BooleanField(default=False)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    organiser_website = models.URLField(blank=True, null=True)

    social_twitter = models.URLField(blank=True, null=True)
    social_instagram = models.URLField(blank=True, null=True)
    social_facebook = models.URLField(blank=True, null=True)

    stream_url = models.URLField(
        blank=True, null=True, help_text="URL to livestream (YouTube, Twitch, etc.)"
    )

    def __str__(self):
        return self.name

    def get_location(self):
        return (
            f"{self.address} (Lat: {self.latitude}, Lon: {self.longitude})"
            if self.address
            else "Location not set"
        )


class Participant(models.Model):
    """
    Model representing the Participant of a race.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="race_entries",
        limit_choices_to={"is_runner": True}
    )
    race = models.ForeignKey(
        "Race",
        on_delete=models.CASCADE,
        related_name="race_participants"
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)

    bib_number = models.IntegerField()

    age = models.PositiveIntegerField()

    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
    )

    notify_on_race_change = models.BooleanField(
        default=False,
        help_text="Check to recieve email updates about changes to this race."
    )

    club_name = models.CharField(max_length=100, blank=True, null=True)
    team_name = models.CharField(max_length=100, blank=True, null=True)
    age_category = models.CharField(max_length=50, blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("denied", "Denied"),
        ],
        default="pending",
    )

    class Meta:
        unique_together = ("race", "bib_number")

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.race.name}) - {self.status}"

    def clean(self):
        if self.notify_on_race_change and not self.user:
            raise ValidationError("Only participants linked to an account can receive notifications.")


class RaceResult(models.Model):
    """
    Model representing the results of a race.
    """

    participant = models.ForeignKey(
        "Participant", on_delete=models.CASCADE, related_name="race_results"
    )
    race = models.ForeignKey(
        "Race", on_delete=models.CASCADE, related_name="race_results"
    )
    total_time = models.DurationField()
    finish_time = models.DateTimeField()
    disqualified = models.BooleanField(default=False)
    position = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.participant} - {self.race.name} - {self.total_time}"

    def is_valid_result(self):
        return not self.disqualified and self.total_time is not None

    class Meta:
        unique_together = ("participant", "race")
        ordering = ["total_time"]
        indexes = [
            models.Index(fields=["race", "position"]),
            models.Index(fields=["race", "total_time"]),
        ]

class ParticipantCategory(models.Model):
    """
    Model for custom Participant category (e.g., "veteran" or "junior").
    """

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class RaceCategory(models.Model):
    """
    Model for custom Race Category (e.g., "5k", "10k", "Half-Marathon").
    """

    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class OrganiserApplication(models.Model):
    """
    Model representing an application to become a race organiser.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("denied", "Denied"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organiser_applications",
        limit_choices_to={"is_organiser": True}
    )
    race = models.ForeignKey(
        "Race",
        on_delete=models.CASCADE,
        related_name="organiser_applications"
    )

    message = models.TextField(blank=True)
    status = models.CharField(max_length=10,
                              choices=STATUS_CHOICES,
                              default="pending")

    created_at = models.DateTimeField(auto_now_add=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_organiser_applications"
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    review_comment = models.TextField(blank=True)

    class Meta:
        unique_together = ("user", "race")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.race} ({self.status})"

    def approve(self, approver, comment=""):
        self.status = "approved"
        self.approved_by = approver
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save()
        self.race.organiser.add(self.user)

    def deny(self, approver, comment=""):
        self.status = "denied"
        self.approved_by = approver
        self.reviewed_at = timezone.now()
        self.review_comment = comment
        self.save()
