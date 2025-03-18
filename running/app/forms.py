# running/app/forms.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django import forms
from .models import RaceCategory, ParticipantCategory
from django.utils import timezone
from .models import Image


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
    """
    Class for adjusting race start time form
    """

    start_time = forms.DateTimeField(
        label='New Start Time',
        initial=timezone.now,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
    )


class ImageUploadForm(forms.ModelForm):
    """
    Class for upload images
    """

    class Meta:
        model = Image
        fields = ['name', 'image']
