# forms.py
from django import forms
from .models import Participant, Race
import datetime

class RegisterRaceForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name', 'race_number', 'age', 'gender', 'race']

    race = forms.ModelChoiceField(queryset=Race.objects.filter(date__gte=datetime.date.today()), empty_label="Select Race")
