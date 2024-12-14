#  running/app/models.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
#  used for django app configuration
from django.db import models

# ------------------------------------------------- Class Declarations -------------------------------------------------
class Participant(models.Model):
    """
    Model representing a participant of a race.
    """

    #  participants name, race number (bib number), age and gender
    name = models.CharField(max_length=100)
    race_number = models.CharField(max_length=10)
    age = models.IntegerField()
    gender = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class RaceResult(models.Model):
    """
    Model representing the results of the race.
    """

    #  the participant key, and the time (as a string)
    participant = models.ForeignKey('Participant', on_delete=models.CASCADE)
    total_time = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.participant.name} - {self.total_time}"


class RaceConfig(models.Model):
    """
    Model representing a race configuration.
    """

    #  the race name, date, start time (as a string) and categories (5k, 10k, etc.)
    name = models.CharField(max_length=255)
    date = models.DateField()
    start_time = models.TimeField()
    categories = models.TextField()

    def __str__(self):
        return self.name
