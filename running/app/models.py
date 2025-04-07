# running/app/models.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.db import models
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import BaseUserManager
from django.utils.translation import gettext_lazy as _


# ------------------------------------------------- Class Declarations -------------------------------------------------
class Race(models.Model):
    """
    Model representing a race configuration.
    """

    name = models.CharField(max_length=255)
    date = models.DateField()
    start_time = models.TimeField()
    race_category = models.ForeignKey('RaceCategory', on_delete=models.SET_NULL, null=True, blank=True)
    participant_categories = models.ManyToManyField('ParticipantCategory', related_name='races')

    organiser = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='organised_races',
        blank=True
    )
    participants = models.ManyToManyField('Participant', related_name='races', blank=True)

    is_completed = models.BooleanField(default=False)

    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

    def get_location(self):
        return f"{self.address} (Lat: {self.latitude}, Lon: {self.longitude})" if self.address else "Location not set"


class Participant(models.Model):
    """
    Model representing the Participant of a race.
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='race_participants')
    name = models.CharField(max_length=100)
    race_number = models.CharField(max_length=10)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    club_name = models.CharField(max_length=100, blank=True, null=True)
    team_name = models.CharField(max_length=100, blank=True, null=True)
    age_category = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=10,
                              choices=[('pending', 'Pending'), ('approved', 'Approved'), ('denied', 'Denied')],
                              default='pending')

    class Meta:
        unique_together = ('race', 'race_number')

    def __str__(self):
        return f"{self.name} ({self.race.name}) - {self.status}"


class RaceResult(models.Model):
    """
    Model representing the results of a race.
    """

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='race_results')
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='race_results')
    total_time = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.participant.name} - {self.race.name} - {self.total_time}"


class Profile(models.Model):
    """
    Model for storing additional user profile settings.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notify_race_updates = models.BooleanField(default=True)

    def __str__(self):
        return self.user.name


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


class CustomUserManager(BaseUserManager):
    """
    Custom manager for CustomUser model.
    """

    def create_user(self, username, email, password=None, **extra_fields):
        """
        Creates and returns a regular user with an email, username, and password.
        """

        if not email:
            raise ValueError(_('The Email field must be set'))

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """
        Creates and returns a superuser with an email, username, and password.
        """

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self.create_user(username, email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Custom User model with additional fields like profile picture and name.
    """

    name = models.CharField(max_length=255, blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    objects = CustomUserManager()

    def save(self, *args, **kwargs):
        """
        Automatically set the `name` field to combine `first_name` and `last_name`.
        """

        if self.first_name and self.last_name:
            self.name = f"{self.first_name} {self.last_name}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.username


class Image(models.Model):
    """
    Model representing an image associated with a race.
    """

    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to='images/')
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='race_images')  # Link to a specific race
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.race.name}) - {self.timestamp}"


class OrganiserApplication(models.Model):
    """
    Model representing an application to become a race organiser.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='organiser_applications'
    )
    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name='organiser_applications'
    )
    message = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'race')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.race} ({self.status})"
