from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.utils import timezone
from django.http import JsonResponse
import logging
from ..models import Race, RaceCategory, ParticipantCategory
from ..serializers.race_serializer import RaceSerializer, RaceUpdateSerializer

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_race(request):
    user = request.user
    data = request.data

    logger.info(f"[RaceCreation] Creating race for user: {user.username}")
    print("[RaceCreation] Request data:", data)

    race_name = data.get("race_name")
    start_datetime_iso = data.get("start_datetime_iso")

    if not race_name or not start_datetime_iso:
        return JsonResponse({"error": "race_name and start_datetime_iso are required."}, status=400)

    try:
        start_datetime = parse_datetime(start_datetime_iso)
        if not start_datetime or timezone.is_naive(start_datetime):
            raise ValueError
        if start_datetime < timezone.now():
            return JsonResponse({"error": "Race start time cannot be in the past."}, status=400)
    except Exception:
        return JsonResponse({"error": "Invalid ISO 8601 datetime or timezone missing."}, status=400)


    race_location = data.get("race_location") or None
    latitude = data.get("latitude")
    longitude = data.get("longitude")
    organiser_website = data.get("organiser_website", "").strip()
    social_twitter = data.get("social_twitter", "").strip()
    social_instagram = data.get("social_instagram", "").strip()
    social_facebook = data.get("social_facebook", "").strip()
    stream_url = data.get("youtube_stream_url", "").strip()

    race = Race.objects.create(
        name=race_name,
        start_datetime=start_datetime,
        latitude=float(latitude) if latitude else None,
        longitude=float(longitude) if longitude else None,
        address=race_location,
        organiser_website=organiser_website,
        social_twitter=social_twitter,
        social_instagram=social_instagram,
        social_facebook=social_facebook,
        stream_url=stream_url,
    )

    race.organisers.add(user)

    race_category_id = data.get("race_category")
    if race_category_id:
        try:
            race.race_category = RaceCategory.objects.get(id=race_category_id)
            race.save()
        except RaceCategory.DoesNotExist:
            logger.warning(f"[RaceCreation] Invalid race category ID: {race_category_id}")

    # Assign participant categories
    for cat_id in data.get("participant_categories", []):
        try:
            race.participant_categories.add(ParticipantCategory.objects.get(id=cat_id))
        except ParticipantCategory.DoesNotExist:
            logger.warning(f"[RaceCreation] Invalid participant category ID: {cat_id}")

    logger.info(f"[RaceCreation] Race created (ID {race.id}) by {user.username}")

    return JsonResponse({
        "message": "Race created successfully.",
        "race_id": race.id,
        "start_datetime": race.start_datetime.isoformat(),  # ISO 8601 with TZ
    }, status=201)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_my_races(request):
    user=request.user
    logger.info(f"[GetMyRaces] Fetching races for organiser: {user.username}")

    races = Race.objects.filter(organisers=user).distinct()

    serialized = RaceSerializer(races, many=True)
    return Response(serialized.data)

@api_view(["GET"])
@permission_classes([AllowAny])
def get_all_races(request):
    logger.info("[GetAllRaces] Fetching all races.")

    races = Race.objects.all()

    serialized = RaceSerializer(races, many=True)
    return Response(serialized.data)

@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def update_race(request, race_id):
    user = request.user
    try:
        race = Race.objects.get(id=race_id)
        if user not in race.organisers.all():
            logger.warning(f"[UpdateRace] Access designed to race ID {race_id} for user {user.username}")
            return Response({"error": "You are not an organiser of this race"}, status=403)
    except Race.DoesNotExist:
        logger.warning(f"[UpdateRace] Race not found (ID: {race_id})")
        return Response({"error": "Race not found."}, status=404)

    serializer = RaceUpdateSerializer(race, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(f"[UpdateRace] Race {race_id} updated by {user.username}")
        return Response(serializer.data, status=200)
    else:
        logger.error(f"[UpdateRace] Validation failed for Race {race_id}: {serializer.errors}")
        return Response(serializer.errors, status=400)