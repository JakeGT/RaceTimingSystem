from rest_framework import serializers
from ..models import Race
from .category_serializers import RaceCategorySerializer, ParticipantCategorySerializer

class RaceSerializer(serializers.ModelSerializer):
    race_category = RaceCategorySerializer()
    participant_categories = ParticipantCategorySerializer(many=True)

    class Meta:
        model = Race
        fields = (
            "id",
            "name",
            "start_datetime",
            "address",
            "latitude",
            "longitude",
            "race_category",
            "participant_categories",
            "organiser_website",
            "social_twitter",
            "social_instagram",
            "social_facebook",
            "stream_url",
            "is_completed",
        )


class RaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Race
        fields = (
            "name",
            "start_datetime",
            "address",
            "latitude",
            "longitude",
            "organiser_website",
            "social_twitter",
            "social_instagram",
            "social_facebook",
            "stream_url",
            "race_category",
            "participant_categories",
            "is_completed",
        )
