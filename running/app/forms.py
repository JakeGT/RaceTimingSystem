# running/app/forms.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django import forms
from .models import Participant, Race, RaceCategory, ParticipantCategory
import datetime


# ------------------------------------------------- Class Declarations -------------------------------------------------
class RegisterRaceForm(forms.ModelForm):
    """
    Class for the registering for a race form
    """

    class Meta:
        model = Participant
        fields = ['name', 'race_number', 'age', 'gender', 'race']

    race = forms.ModelChoiceField(queryset=Race.objects.filter(date__gte=datetime.date.today()), empty_label="Select "
                                                                                                             "Race")


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