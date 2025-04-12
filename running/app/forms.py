# running/app/forms.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django import forms
from django.utils import timezone

from .models import Image, OrganiserApplication, ParticipantCategory, Race, RaceCategory


# ------------------------------------------------- Class Declarations -------------------------------------------------
class ParticipantCategoryForm(forms.ModelForm):
    """
    Class for the participant category creation form
    """

    class Meta:
        model = ParticipantCategory
        fields = ["name"]


class RaceCategoryForm(forms.ModelForm):
    """
    Class for the race category creation form
    """

    class Meta:
        model = RaceCategory
        fields = ["name"]


class AdjustStartTimeForm(forms.Form):
    """
    Form for adjusting the race start time.
    """

    start_time = forms.DateTimeField(
        label="New Start Time",
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )


class ImageUploadForm(forms.ModelForm):
    """
    Class for upload images form
    """

    class Meta:
        model = Image
        fields = ["name", "image"]


class OrganiserApplicationForm(forms.ModelForm):
    """
    Class for organiser application form
    """

    class Meta:
        model = OrganiserApplication
        fields = ["race", "message"]

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields["race"].queryset = Race.objects.exclude(organiser=user)
