#  running/app/admin.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
#  used for creating admin permissions
from django.contrib import admin

#  used for admin record management
from .models import Participant, RaceResult

# ------------------------------------------------- Class Declarations -------------------------------------------------
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    """
    Admin configuration for participants.
    """

    list_display = ('name', 'race_number', 'age', 'gender')
    list_filter = ('gender',)
    search_fields = ('name', 'race_number')


@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    """
    Admin configuration for the RaceResult model.
    """

    list_display = ('participant', 'total_time')
    search_fields = ('participant__name', 'participant__race_number')
    list_filter = ('participant__gender',)
    ordering = ('total_time',)


