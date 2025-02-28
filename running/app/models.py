# running/app/models.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
# used for django app configuration
from django.db import models
from django.contrib.auth.models import User

# ------------------------------------------------- Class Declarations -------------------------------------------------

class RaceResult(models.Model):
    """
    Model representing the results of the race.
    """

    #  the participant key and time
    participant = models.ForeignKey('Participant', on_delete=models.CASCADE)
    total_time = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.participant.name} - {self.total_time}"


class Race(models.Model):
    """
    Model representing a race configuration.
    """

    #  the race name, date, start time and categories (5k, 10k, etc.)
    name = models.CharField(max_length=255)
    date = models.DateField()
    start_time = models.TimeField()
    categories = models.TextField()

    # Add the organiser field to relate a race to a user
    organiser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organised_races')

    def __str__(self):
        return self.name


class Participant(models.Model):
    """
    Model representing a participant of a race.
    """

    #  linking the participant to the User model
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='participant', null=True, blank=True)

    name = models.CharField(max_length=100)
    race_number = models.CharField(max_length=10)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='participants')

    status = models.CharField(
        max_length=10,
        choices=[('pending', 'Pending'), ('approved', 'Approved'), ('denied', 'Denied')],
        default='pending'
    )

    def __str__(self):
        return f"{self.name} - {self.race.name} - {self.status}"
