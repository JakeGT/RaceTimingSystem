# running/app/forms.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django import forms
from .models import Participant, Race, RaceCategory, ParticipantCategory
import datetime
from django.utils import timezone


# ------------------------------------------------- Class Declarations -------------------------------------------------
class ParticipantCategoryForm(forms.ModelForm):
    """
    Class for the participant category creation form
    """

    class Meta:
        model = ParticipantCategory
        fields = ['name']


class RaceCategoryForm(forms.ModelForm):
    """
    Class for the race category creation form
    """

    class Meta:
        model = RaceCategory
        fields = ['name']


class AdjustStartTimeForm(forms.Form):
    start_time = forms.DateTimeField(
        label='New Start Time',
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )