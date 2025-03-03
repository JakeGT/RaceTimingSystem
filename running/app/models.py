# running/app/models.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.db import models
from django.contrib.auth.models import User


# ------------------------------------------------- Class Declarations -------------------------------------------------
class Race(models.Model):
    """
    Model representing a race configuration.
    """

    name = models.CharField(max_length=255)
    date = models.DateField()
    start_time = models.TimeField()
    categories = models.TextField()

    organiser = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organised_races')
    participants = models.ManyToManyField('Participant', related_name='races', blank=True)

    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Participant(models.Model):
    """
    Model representing the Participant of a race
    """

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='participant', null=True, blank=True)
    race = models.ForeignKey(Race, on_delete=models.CASCADE, related_name='race_participants')
    name = models.CharField(max_length=100)
    race_number = models.CharField(max_length=10)
    age = models.PositiveIntegerField()
    gender = models.CharField(max_length=10, choices=[('male', 'Male'), ('female', 'Female'), ('other', 'Other')])
    club_name = models.CharField(max_length=100, blank=True, null=True)
    team_name = models.CharField(max_length=100, blank=True, null=True)
    age_category = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('denied', 'Denied')], default='pending')

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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    notify_race_updates = models.BooleanField(default=True)

    def __str__(self):
        return self.user.username
