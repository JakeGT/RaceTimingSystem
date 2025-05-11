class Profile(models.Model):
    """
    Model for storing additional user profile settings.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notify_race_updates = models.BooleanField(default=True)

    def __str__(self):
        return self.user.name



class Image(models.Model):
    """
    Model representing an image associated with a race.
    """

    name = models.CharField(max_length=100)
    image = models.ImageField(upload_to="images/")
    race = models.ForeignKey(
        Race, on_delete=models.CASCADE, related_name="race_images"
    )  # Link to a specific race
    timestamp = models.DateTimeField(auto_now_add=True)
    bib_number = models.IntegerField()

    def __str__(self):
        return f"{self.name} ({self.race.name}) - {self.timestamp}"