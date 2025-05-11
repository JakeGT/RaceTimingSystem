from rest_framework import serializers
from ..models import ParticipantCategory, RaceCategory

class ParticipantCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ParticipantCategory
        fields = ("id", "name")

class RaceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = RaceCategory
        fields = ("id", "name")