from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from ..models import ParticipantCategory, RaceCategory
from ..serializers.category_serializers import (ParticipantCategorySerializer, RaceCategorySerializer)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_categories(request):
    participant_categories = ParticipantCategory.objects.all()
    race_categories = RaceCategory.objects.all()

    return Response({
        "participant_categories": ParticipantCategorySerializer(participant_categories, many=True).data,
        "race_categories": RaceCategorySerializer(race_categories, many=True).data
    })