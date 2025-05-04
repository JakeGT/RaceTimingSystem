#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import base64
import csv
import io
import json
import re
import secrets
from datetime import date, datetime, timedelta
from collections import defaultdict
from functools import wraps

import pyotp
import qrcode
from django.conf import settings
from django.contrib import messages

#  define custom user
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin
from django.contrib.sessions.models import Session
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import connection
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_time
from django.utils.timezone import make_aware
from django.views.decorators.csrf import csrf_exempt
from google.auth.transport import requests
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token

from .forms import (
    AdjustStartTimeForm,
    ImageUploadForm,
    OrganiserApplicationForm,
    ParticipantCategoryForm,
    RaceCategoryForm,
)
from .models import (
    Image,
    OrganiserApplication,
    Participant,
    ParticipantCategory,
    Race,
    RaceCategory,
    RaceResult,
)
from .utils.logger import setup_logging

User = get_user_model()

# --------------------------------------------------- RESTful API ------------------------------------------------------

# CSV version
#
# @csrf_exempt
# def upload_json(request, race_id):
#     if request.method == 'POST':
#         data = json.loads(request.body)
#         process_data(data, race_id)
#         return JsonResponse({"message": "Data processed and written to CSV."})
#     return JsonResponse({"error": "Invalid request method"}, status=400)

# def process_data(data, race_id):
#     bib_number = data.get('bib_number')
#     time = data.get('time')

#     # Specify the folder and CSV file name based on the race_id
#     folder = 'race_results'
#     if not os.path.exists(folder):
#         os.makedirs(folder)
#     csv_file = os.path.join(folder, f'race_{race_id}.csv')

#     # Write data to CSV file
#     with open(csv_file, mode='a', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow([bib_number, time])

#     print(f"Data written to {csv_file}: Bib Number - {bib_number}, Time - {time}")


# Objects version
@csrf_exempt
def upload_json(request, race_id):
    """
    Backend API for the upload of runner results data, requires the token with the associated race
    """

    if request.method == "POST":
        # check token in header or query string
        token = request.GET.get("token") or request.headers.get("token")
        if not token:
            return JsonResponse({"error": "Missing upload token"}, status=401)

        try:
            race = Race.objects.get(pk=race_id)
        except Race.DoesNotExist:
            return JsonResponse({'error': 'Invalid race ID'}, status=404)

        if race.token != token:
            logger.info("Invalid token in request.")
            return JsonResponse({'error': 'Invalid token'}, status=498)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        bib_number = data.get("bib_number")
        result_time = data.get("time")

        try:
            participant = Participant.objects.get(race=race, race_number=bib_number)
        except Participant.DoesNotExist:
            return JsonResponse({"error": "Participant not found"}, status=404)

        start_time = race.start_time
        result_time_obj = parse_time(result_time)

        start_time_datetime = datetime.combine(date.min, start_time)
        result_time_datetime = datetime.combine(date.min, result_time_obj)

        if result_time_datetime < start_time_datetime:
            result_time_datetime += timedelta(days=1)

        time_difference = result_time_datetime - start_time_datetime

        RaceResult.objects.create(
            participant=participant, race=race, total_time=str(time_difference)
        )

        return JsonResponse({"message": "Data processed and race result created."})

    return JsonResponse({"error": "Invalid request method"}, status=400)


# -------------------------------------------------- Setup Logging -----------------------------------------------------
logger = setup_logging()


# ------------------------------------------------- Class Declarations -------------------------------------------------
class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = "app/password_reset.html"
    email_template_name = "app/password_reset_email.html"
    subject_template_name = "app/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    success_message = "Password reset email sent! Check your inbox."


# ------------------------------------------------ Function Definitions ------------------------------------------------
def logged_out_required(view_func):
    """
    Define a logged out wrapper for pages users cannot access whilst being logged in.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            logger.info("Logged in user tried to access logged out only page")
            return redirect("/")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def two_factor_required(view_func):
    """
    Decorator to require 2fa completion before accessing certain views
    """

    def _wrapped_view(request, *args, **kwargs):
        if request.session.get("needs_2fa", False):
            return redirect("verify_2fa")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def login_and_2fa_required(view_func):
    """
    Decorator to require login and 2fa verification for a view
    """

    decorated_view = login_required(two_factor_required(view_func))
    return decorated_view


def login_and_2fa_optional(view_func):
    """
    Decorator that allows access to the view for non-logged-in users but requires
    2fa for logged-in users with 2FA enabled.
    """

    def wrapper(request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.mfa_enabled
            and not request.session.get("mfa_verified", False)
        ):
            return redirect("verify_2fa")

        return view_func(request, *args, **kwargs)

    return wrapper


@login_and_2fa_optional
def landing_page(request):
    """
    View for the landing page of the Race Timing System.
    """

    logger.info("Accessing the landing page view")

    return render(request, "app/landing.html", {})


@logged_out_required
def user_register(request):
    """
    Handles user registration with password validation.
    """

    logger.info("Accessing the registration page view")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        logger.info(f"Registration attempt for username: {username}, email: {email}")

        #  password validation
        if password1 != password2:
            logger.info(f"Registration failed for {username}: Passwords do not match.")
            messages.error(request, "Passwords do not match.")

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        if len(password1) < 8:
            logger.info(f"Registration failed for {username}: Password too short.")
            messages.error(request, "Password must be at least 8 characters long.")

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        if not re.search(r"\d", password1):
            logger.info(
                f"Registration failed for {username}: Password missing a number."
            )
            messages.error(request, "Password must contain at least one number.")

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        if not re.search(r"[!@#$%^&*()\-_=+[\]{}|;:'\",.<>?/]", password1):
            logger.info(
                f"Registration failed for {username}: Password missing a special character."
            )
            messages.error(
                request, "Password must contain at least one special character."
            )

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        #  check if username or email already exists
        if User.objects.filter(username=username).exists():
            logger.info(f"Registration failed: Username '{username}' is already taken.")
            messages.error(request, "Username is already taken.")

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        if User.objects.filter(email=email).exists():
            logger.info(f"Registration failed: Email '{email}' is already registered.")
            messages.error(request, "An account with this email already exists.")

            request.session['register_data'] = {
                'first_name': first_name,
                'last_name': last_name,
                'username': username,
                'email': email
            }

            return redirect("register")

        #  create and save the user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )
        user.save()

        request.session.pop('register_data', None)

        logger.info(f"Registration successful for username: {username}, email: {email}")
        messages.success(request, "Registration successful! You can now log in.")
        return redirect("login")

    return render(
        request,
        "app/register.html",
        {
            "google_client_id": settings.GOOGLE_CLIENT_ID,
            "register_data": request.session.get("register_data", {})
        }
    )


@logged_out_required
def user_login(request):
    """
    View for logging the user in.
    """

    logger.info("Accessing the login page view")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        remember_me = request.POST.get("remember_me") == "on"

        logger.info(f"Login attempt for username: {username}")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            logger.info(f"Login successful for username: {username}")
            messages.success(request, "Login successful!")

            # clear old login data
            request.session.pop('login_data', None)

            # session expiration logic
            if remember_me:
                request.session.set_expiry(60 * 60 * 24 * 30)
            else:
                request.session.set_expiry(0)

            if user.mfa_enabled:
                request.session["needs_2fa"] = True
                return redirect("verify_2fa")

            return redirect("/")

        else:
            logger.info(f"Login failed for username: {username}: Invalid credentials")
            messages.error(request, "Invalid username or password.")

            #  save username to repopulate form
            request.session['login_data'] = {
                'username': username
            }

    return render(
        request,
        "app/login.html",
        {
            "google_client_id": settings.GOOGLE_CLIENT_ID,
            "login_data": request.session.get("login_data", {}),
        }
    )


@login_and_2fa_optional
def dashboard(request):
    """
    The view for the users dashboard.
    """

    logger.info("Accessing the dashboard page")

    race_search = request.GET.get("race_search", "").strip()
    completed = request.GET.get("completed", None)
    upcoming = request.GET.get("upcoming", None)
    sort_by = request.GET.get("sort_by", "")
    sort_order = request.GET.get("sort_order", "asc")

    races = Race.objects.all()

    #  search functionality
    if race_search:
        logger.info(f"Filtering races with search term: '{race_search}'")
        races = races.filter(name__icontains=race_search)

    #  filter for completed races
    if completed == "on":
        logger.info("Filtering: Show only completed races")
        races = races.filter(is_completed=True)

    #  filter for upcoming races
    if upcoming == "on":
        logger.info("Filtering: Show only upcoming races")
        races = races.filter(is_completed=False)

    #  prevent conflicting filters
    if completed == "on" and upcoming == "on":
        logger.info("Both completed and upcoming selected — showing nothing")
        races = Race.objects.none()

    #  sorting functionality
    if sort_by == "name":
        logger.info("Sorting races by name")
        races = races.order_by("name" if sort_order == "asc" else "-name")
    elif sort_by == "date":
        logger.info("Sorting races by date")
        races = races.order_by("date" if sort_order == "asc" else "-date")

    return render(
        request,
        "app/dashboard.html",
        {
            "races": races,
        },
    )


@login_and_2fa_required
def race_config(request):
    """
    View for creating and cofiguring a race.
    """

    logger.info(f"Accessing race configuration page by user: {request.user.username}")

    race_categories = RaceCategory.objects.all()
    participant_categories = ParticipantCategory.objects.all()
    saved_data = request.session.get("race_config_data", {})

    if request.method == "POST":
        race_name = request.POST["race_name"]
        race_date_str = request.POST["race_date"]
        start_time = request.POST["start_time"]
        no_location = request.POST.get("no_location", False)
        race_location = request.POST.get("race_location", "")
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")
        organiser_website = request.POST.get("organiser_website", "").strip()
        social_twitter = request.POST.get("social_twitter", "").strip()
        social_instagram = request.POST.get("social_instagram", "").strip()
        social_facebook = request.POST.get("social_facebook", "").strip()
        youtube_stream_url = request.POST.get("youtube_stream_url", "").strip()

        if no_location:
            race_location = None
            latitude = None
            longitude = None

        request.session["race_config_data"] = {
            "race_name": race_name,
            "race_date": race_date_str,
            "start_time": start_time,
            "race_category": request.POST.get("race_category", None),
            "participant_categories": request.POST.getlist("participant_categories"),
            "latitude": latitude,
            "longitude": longitude,
            "race_location": race_location,
            "no_location": no_location,
            "organiser_website": organiser_website,
            "social_twitter": social_twitter,
            "social_instagram": social_instagram,
            "social_facebook": social_facebook,
            "youtube_stream_url": youtube_stream_url,
        }

        try:
            race_date = make_aware(datetime.strptime(race_date_str, "%Y-%m-%d"))
            if race_date.date() < datetime.now().astimezone().date():
                messages.error(request, "Race date cannot be in the past.")
                return render(
                    request,
                    "app/race_config.html",
                    {
                        "race_categories": race_categories,
                        "participant_categories": participant_categories,
                        "saved_data": request.POST,
                    },
                )
        except ValueError:
            messages.error(request, "Invalid race date format. Please use YYYY-MM-DD.")
            return render(
                request,
                "app/race_config.html",
                {
                    "race_categories": race_categories,
                    "participant_categories": participant_categories,
                    "saved_data": request.POST,
                },
            )

        if Race.objects.filter(name=race_name).exists():
            messages.error(
                request,
                f"A race named '{race_name}' already exists. Please choose a different name.",
            )
            return render(
                request,
                "app/race_config.html",
                {
                    "race_categories": race_categories,
                    "participant_categories": participant_categories,
                    "saved_data": request.POST,
                },
            )

        #  generate secure token
        token = secrets.token_urlsafe(16)

        try:
            start_time_obj = datetime.strptime(start_time, "%H:%M").time()
        except ValueError:
            messages.error(request, "Invalid start time format. Please use HH:MM.")
            return render(
                request,
                "app/race_config.html",
                {
                    "race_categories": race_categories,
                    "participant_categories": participant_categories,
                    "saved_data": request.POST,
                },
            )

        race = Race.objects.create(
            name=race_name,
            date=race_date.date(),
            start_time=start_time_obj,
            latitude=float(latitude) if latitude else None,
            longitude=float(longitude) if longitude else None,
            address=race_location,
            organiser_website=organiser_website,
            social_twitter=social_twitter,
            social_instagram=social_instagram,
            social_facebook=social_facebook,
            token=token,
            stream_url=youtube_stream_url,
        )
        race.organiser.add(request.user)

        #  send the token via email
        subject = f"Race Token for '{race_name}'"
        message = (
            f"Hi {request.user.first_name or request.user.username},\n\n"
            f'Your race "{race_name}" has been successfully created.\n\n'
            f"Here is your unique token:\n\n"
            f"{token}\n\n"
            f"You can use this token to manage or share the race securely.\n\n"
            f"— The Running App Team"
        )

        try:
            send_mail(
                subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email]
            )
            logger.info(f"Token email successfully sent to {request.user.email}")
        except Exception as e:
            logger.error(f"Failed to send token email to {request.user.email}: {e}")

        #  race category assignment
        race_category_id = request.POST.get("race_category")
        if race_category_id and race_category_id != "none":
            try:
                race.race_category = RaceCategory.objects.get(id=race_category_id)
                race.save()
            except RaceCategory.DoesNotExist:
                logger.warning(
                    f"Race category with ID {race_category_id} does not exist."
                )

        #  participant category assignments
        for category_id in request.POST.getlist("participant_categories"):
            try:
                race.participant_categories.add(
                    ParticipantCategory.objects.get(id=category_id)
                )
            except ParticipantCategory.DoesNotExist:
                logger.warning(
                    f"Participant category with ID {category_id} does not exist."
                )

        #  clear session data
        request.session.pop("race_config_data", None)

        #  success page
        return render(
            request,
            "app/race_success.html",
            {
                "race": race,
                "token": token,
            },
        )

    #  get request
    return render(
        request,
        "app/race_config.html",
        {
            "race_categories": race_categories,
            "participant_categories": participant_categories,
            "saved_data": saved_data,
        },
    )


@login_and_2fa_required
def upload_results(request):
    """
    View for uploading race results via CSV file.
    """

    logger.info(
        f"Accessing the upload results page. Available races: {Race.objects.count()}"
    )

    races = Race.objects.filter(organiser=request.user)

    if request.method == "POST":

        if "file" in request.FILES:
            file = request.FILES["file"]
            logger.info(f"File '{file.name}' received for upload.")

            try:
                decoded_file = file.read().decode("utf-8").splitlines()
                reader = csv.reader(decoded_file)

                header = next(reader, None)
                logger.info(f"CSV header: {header}")

                race_id = request.POST.get("race_id")
                if not race_id:
                    messages.error(
                        request, "Please select a race before uploading CSV."
                    )
                    logger.error("Race ID not provided.")
                    return render(request, "app/upload_results.html", {"races": races})

                try:
                    race = Race.objects.get(id=race_id)
                    logger.info(
                        f"Selected race for result upload: {race.name} (ID: {race.id})"
                    )
                except Race.DoesNotExist:
                    messages.error(request, "Selected race does not exist.")
                    logger.error(f"Race with ID {race_id} not found.")
                    return render(request, "app/upload_results.html", {"races": races})

                for row in reader:
                    if len(row) < 2:
                        messages.error(request, "CSV file format is incorrect.")
                        logger.error(
                            "CSV row format is incorrect (less than 2 columns)."
                        )
                        break

                    bib_number = row[0].strip()
                    result_time = row[1].strip()

                    if not bib_number or not result_time:
                        logger.warning(
                            f"Skipping empty row (bib_number: {bib_number}, result_time: {result_time})"
                        )
                        continue

                    try:
                        participant = Participant.objects.get(
                            race_id=race.id, race_number=bib_number
                        )
                        logger.info(
                            f"Found participant: {participant.name} (Bib: {bib_number})"
                        )
                    except Participant.DoesNotExist:
                        messages.error(
                            request,
                            f"Participant with bib number {bib_number} "
                            f"not found for race {race.name}.",
                        )
                        logger.error(
                            f"Participant with bib number {bib_number} not found for race {race.name}."
                        )
                        continue

                    if RaceResult.objects.filter(
                        race=race, participant=participant
                    ).exists():
                        messages.error(
                            request,
                            f"Result already uploaded for participant {bib_number}"
                            f" in race {race.name}.",
                        )
                        logger.warning(
                            f"Result already uploaded for participant {bib_number} in race {race.name}."
                        )
                        continue

                    RaceResult.objects.create(
                        race=race, participant=participant, total_time=result_time
                    )
                    logger.info(
                        f"Result for participant {bib_number} successfully uploaded for race {race.name}."
                    )

                #  check if all results have been uploaded
                total_participants = Participant.objects.filter(race=race).count()
                uploaded_results = RaceResult.objects.filter(race=race).count()

                if total_participants == uploaded_results and total_participants > 0:
                    race.is_completed = True
                    race.save()
                    logger.info(
                        f"Race '{race.name}' marked as completed (all results received)."
                    )
                    messages.success(
                        request,
                        f"All results have been uploaded. Race '{race.name}' is now marked as completed.",
                    )

                else:
                    logger.info(
                        f"Race '{race.name}' still has outstanding results: "
                        f"{total_participants - uploaded_results} remaining."
                    )

                messages.success(request, "CSV file uploaded successfully!")

            except Exception as e:
                messages.error(request, f"Error uploading CSV: {str(e)}")
                logger.error(f"Error uploading CSV: {str(e)}")

    return render(request, "app/upload_results.html", {"races": races})


@login_and_2fa_required
def upload_participants(request):
    """
    View for uploading participants either manually or via CSV.
    """

    logger.info("Accessing the upload participants page.")

    if request.method == "POST":
        race_id = request.POST.get("race_id")

        if not race_id:
            messages.error(request, "Please select a race.")
            logger.warning("No race selected for participant upload.")
            return redirect("upload_participants")

        try:
            race = Race.objects.get(id=race_id)
            logger.info(
                f"Selected race for participant upload: {race.name} (ID: {race.id})"
            )
        except Race.DoesNotExist:
            messages.error(request, "Invalid race selected.")
            logger.error(f"Invalid race selected. Race ID: {race_id} does not exist.")
            return redirect("upload_participants")

        # Handle CSV file upload
        if "file" in request.FILES:
            csv_file = request.FILES["file"]
            logger.info(f"CSV file '{csv_file.name}' received for upload.")

            #  ensure the uploaded file is a CSV
            if not csv_file.name.endswith(".csv"):
                messages.error(
                    request, "Invalid file format. Please upload a CSV file."
                )
                logger.error(
                    f"Invalid file format for upload. Expected .csv, but received {csv_file.name}."
                )
                return redirect("upload_participants")

            try:
                #  read and decode the CSV file
                decoded_file = csv_file.read().decode("utf-8")
                reader = csv.DictReader(io.StringIO(decoded_file))

                #  required fields that must be present in the CSV
                required_fields = {
                    "BibNumber",
                    "Firstname",
                    "Lastname",
                    "Gender",
                    "TeamName",
                    "AgeCategory",
                    "Age",
                }
                reader_fieldnames = {field.strip() for field in reader.fieldnames}
                missing_fields = required_fields - reader_fieldnames

                # Check for missing required columns
                if missing_fields:
                    messages.error(
                        request,
                        f"CSV file is missing required"
                        f" columns: {', '.join(missing_fields)}",
                    )
                    logger.error(
                        f"CSV file is missing required columns: {', '.join(missing_fields)}"
                    )
                    return redirect("upload_participants")

                participants = []
                for row in reader:
                    #  extract row data and ensure it's valid
                    bib_number = row.get("BibNumber", "").strip()
                    firstname = row.get("Firstname", "").strip()
                    lastname = row.get("Lastname", "").strip()
                    gender = row.get("Gender", "").strip().lower()
                    club_name = row.get("ClubName", "").strip()
                    team_name = row.get("TeamName", "").strip()
                    age_category = row.get("AgeCategory", "").strip()
                    try:
                        age = int(row.get("Age", "").strip())
                    except ValueError:
                        age = None

                    #  skip rows with missing fields
                    if (
                        not all(
                            [
                                bib_number,
                                firstname,
                                lastname,
                                gender,
                                team_name,
                                age_category,
                            ]
                        )
                        or age is None
                    ):
                        messages.warning(
                            request, f"Skipping incomplete or invalid row: {row}"
                        )
                        logger.warning(f"Skipping incomplete or invalid row: {row}")
                        continue

                    #  validate gender
                    if gender not in ["male", "female", "other"]:
                        messages.warning(
                            request, f"Invalid gender in row: {row}. Skipping."
                        )
                        logger.warning(
                            f"Invalid gender in row: {row}. Gender must be 'male', 'female', or 'other'."
                        )
                        continue

                    #  check if participant already exists with the same bib number
                    existing_participant = Participant.objects.filter(
                        race=race, race_number=bib_number
                    ).first()
                    if existing_participant:
                        messages.warning(
                            request,
                            f"Participant with Bib Number {bib_number} already"
                            f" exists for this race.",
                        )
                        logger.warning(
                            f"Participant with Bib Number {bib_number} already exists for race {race.name}."
                        )
                        continue

                    #   add the valid participant
                    participants.append(
                        Participant(
                            race=race,
                            race_number=bib_number,
                            name=f"{firstname} {lastname}",
                            age=age,
                            gender=gender,
                            club_name=club_name,
                            team_name=team_name,
                            age_category=age_category,
                            status="pending",
                        )
                    )

                if participants:
                    Participant.objects.bulk_create(participants)
                    messages.success(
                        request,
                        f"Successfully uploaded {len(participants)} participants.",
                    )
                    logger.info(
                        f"Successfully uploaded {len(participants)} participants for race {race.name}."
                    )
                else:
                    messages.warning(
                        request, "No valid participants were found in the CSV file."
                    )
                    logger.warning("No valid participants found in the CSV file.")

            except csv.Error as e:
                messages.error(request, f"Error reading CSV file: {str(e)}")
                logger.error(f"CSV error: {str(e)}")
                return redirect("upload_participants")

            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
                logger.error(f"Error processing CSV file: {str(e)}")
                return redirect("upload_participants")

            return redirect("upload_results")

        # handle manual entry form
        elif "bib_number" in request.POST:
            bib_number = request.POST.get("bib_number")
            firstname = request.POST.get("firstname")
            lastname = request.POST.get("lastname")
            gender = request.POST.get("gender")
            team_name = request.POST.get("team_name")
            age_category = request.POST.get("age_category")
            race_category = request.POST.get("race_category")
            age = int(request.POST.get("age", 0))
            participant_category = request.POST.get("category_id")

            # validate form data
            if not all(
                    [
                        bib_number,
                        firstname,
                        lastname,
                        gender,
                        team_name,
                        age_category,
                        race_category,
                        age,
                    ]
            ):
                messages.error(request, "Please fill in all required fields.")
                return redirect("upload_participants")

            # check for existing participant with the same bib number
            existing_participant = Participant.objects.filter(
                race=race, race_number=bib_number
            ).first()
            if existing_participant:
                messages.warning(
                    request,
                    f"Participant with Bib Number {bib_number} already exists for this race.",
                )
                return redirect("upload_participants")

            # create participant
            participant = Participant(
                race=race,
                race_number=bib_number,
                name=f"{firstname} {lastname}",
                age=age,
                gender=gender,
                team_name=team_name,
                age_category=age_category,
                status="pending",
            )

            # assign selected category if available
            if participant_category and participant_category != "none":
                race_category_obj = ParticipantCategory.objects.filter(id=participant_category).first()
                if race_category_obj:
                    participant.category = race_category_obj

            participant.save()
            messages.success(request, "Participant added successfully!")
            logger.info(
                f"Added participant {firstname} {lastname} (Bib: {bib_number}) for race {race.name}."
            )

            return redirect("upload_results")

    #  get all available races
    races = Race.objects.filter(organiser=request.user)
    categories = RaceCategory.objects.all()
    participant_categories = ParticipantCategory.objects.all()
    logger.info(
        f"Rendering upload participants page with {races.count()} races available."
    )
    return render(
        request,
        "app/upload_participants.html",
        {
            "races": races,
            "categories": categories,
            "participant_categories": participant_categories,
        },
    )


def user_logout(request):
    """
    Logs out the user and redirects to the homepage.
    """

    logger.info(f"User {request.user.username} is logging out.")

    #  log out the user
    logout(request)
    messages.success(request, "You have successfully logged out.")

    logger.info(f"User {request.user.username} logged out successfully.")

    #  redirect the user to the homepage
    return redirect("/")


@login_and_2fa_required
def manage_participants(request, race_id):
    """
    Loads a page where organisers can approve or deny participants.
    """

    #  fetch race object
    race = get_object_or_404(Race, id=race_id)
    participants = race.participants.filter(status="pending")

    logger.info(
        f"Accessing manage participants page for race: {race.name} (ID: {race.id})"
    )

    if request.method == "POST":
        action = request.POST.get("action")
        participant_id = request.POST.get("participant_id")
        participant = get_object_or_404(Participant, id=participant_id)

        if action == "approve":
            participant.status = "approved"
            logger.info(
                f"Approved participant: {participant.name} (Bib: {participant.race_number}) for race"
                f" {race.name}"
            )
        elif action == "deny":
            participant.status = "denied"
            logger.info(
                f"Denying participant: {participant.name} (Bib:"
                f" {participant.race_number}) for race {race.name}"
            )
        else:
            logger.warning(
                f"Invalid action attempted: {action} for partic"
                f"ipant {participant.name} (ID: {participant.id})"
            )

        #  save the participant status
        participant.save()
        messages.success(
            request, f"Participant {participant.name} has been {participant.status}."
        )

        #  refresh page
        return redirect("manage_participants", race_id=race.id)

    return render(
        request,
        "app/manage_participants.html",
        {"race": race, "participants": participants},
    )


@login_and_2fa_required
def race_history(request):
    """
    Views the history of a runner, including only completed races the user is participating in,
    with sorting and searching functionality.
    """

    logger.info("Accessing the race history view")

    #  check if the user has an associated participant
    if hasattr(request.user, "participant"):
        participant = request.user.participant
        logger.info(
            f"User {request.user.username} has an associated participant with ID: {participant.id}."
        )
    else:
        participant = None
        logger.info(
            f"User {request.user.username} does not have an associated participant."
        )

    #  get search query and sorting parameters
    search_query = request.GET.get("search", "")
    sort_by = request.GET.get("sort", "date")

    #  construct the raw SQL query
    query = """
        SELECT r.id, r.name, r.date, r.start_time, rr.total_time
        FROM app_race r
        LEFT JOIN app_participant p ON r.id = p.race_id
        LEFT JOIN app_raceresult rr ON p.id = rr.participant_id
        WHERE p.user_id = %s
          AND r.is_completed = TRUE
    """

    #  add filtering by search query
    if search_query:
        query += """
            AND (r.name LIKE %s OR rr.total_time LIKE %s)
        """

    #  add sorting
    if sort_by == "name":
        query += " ORDER BY r.name"
    else:
        query += " ORDER BY r.date, r.start_time"

    #  execute the query with parameters
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                query, [request.user.id, f"%{search_query}%", f"%{search_query}%"]
            )
        else:
            cursor.execute(query, [request.user.id])

        races = cursor.fetchall()

    #  prepare the data to be rendered in the template
    user_races = []
    for race in races:
        race_id, race_name, race_date, race_start_time, total_time = race
        user_races.append(
            {
                "id": race_id,
                "name": race_name,
                "date": race_date,
                "start_time": race_start_time,
                "total_time": total_time,
            }
        )

    #  render the page with the filtered race history
    return render(
        request,
        "app/race_history.html",
        {"races": user_races, "search_query": search_query, "sort_by": sort_by},
    )


@login_and_2fa_optional
def race_detail(request, race_id):
    """
    View for displaying race details, including race results or participant list.
    """

    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Accessed race details for race: {race.name} (ID: {race.id})")

    race_results = RaceResult.objects.filter(race=race)

    sort_by = request.GET.get("sort_by", "")
    age_category = request.GET.get("age_category", "")
    sort_direction = request.GET.get("sort_direction", "asc")
    gender = request.GET.get("gender", "")
    age = request.GET.get("age", "")
    search_query = request.GET.get("search", "").strip()

    if race_results.exists():
        logger.info(f"Found {len(race_results)} race results for race: {race.name}")

        if search_query:
            race_results = race_results.filter(
                participant__name__icontains=search_query
            )
            logger.info(f"Filtering race results by name containing: {search_query}")

        if gender:
            race_results = race_results.filter(participant__gender=gender)
            logger.info(f"Filtering race results by gender: {gender}")

        if age_category:
            try:
                #  get the category by ID
                category = ParticipantCategory.objects.get(id=age_category)
                category_name = category.name

                #  filter race results by the name of the age category
                race_results = race_results.filter(participant__age_category=category_name)
                logger.info(f"Filtering race results by age category: {category_name}")

            except ParticipantCategory.DoesNotExist:
                logger.warning(f"Age category with ID {age_category} does not exist.")
                race_results = race_results.none() 

        categories = race.participant_categories.all()

        if age:
            age_ranges = {
                "18": (18, 25),
                "26": (26, 35),
                "36": (36, 45),
                "46": (46, 60),
                "60": (60, 1000),
            }
            if age in age_ranges:
                min_age, max_age = age_ranges[age]
                race_results = race_results.filter(
                    participant__age__gte=min_age, participant__age__lte=max_age
                )
                logger.info(f"Filtering race results by age: {min_age}-{max_age}")

        if sort_by:
            logger.info(f"Sorting race results by {sort_by} in {sort_direction} order.")
            if sort_by == "name":
                race_results = race_results.order_by(
                    "-participant__name"
                    if sort_direction == "desc"
                    else "participant__name"
                )
            elif sort_by == "age":
                race_results = race_results.order_by(
                    "-participant__age"
                    if sort_direction == "desc"
                    else "participant__age"
                )
            elif sort_by == "total_time":
                race_results = race_results.order_by(
                    "-total_time" if sort_direction == "desc" else "total_time"
                )

        #  get club data for each participant and add it to the context
        clubs = set(race_results.values_list("participant__club_name", flat=True))
        logger.info(f"Found the following clubs in the race results: {', '.join(clubs)}")

        #  get team data for each participant and add it to the context
        teams = set(race_results.values_list("participant__team_name", flat=True))
        logger.info(f"Found the following teams in the race results: {', '.join(teams)}")

        return render(
            request,
            "app/race_results.html",
            {
                "race": race,
                "race_results": race_results,
                "filters": request.GET,
                "categories": categories,
                "clubs": clubs,
                "teams": teams,
            },
        )

    #  if there are no results just show participants
    participants = Participant.objects.filter(race=race)

    if age_category:
        try:
            category = ParticipantCategory.objects.get(id=age_category)
            category_name = category.name
            participants = participants.filter(age_category=category_name)
            logger.info(f"Filtering participants by age category: {category_name}")
        except ParticipantCategory.DoesNotExist:
            logger.warning(f"Age category with ID {age_category} does not exist.")
            participants = participants.none()

    #  apply search filter if query exists
    if search_query:
        race_results = race_results.filter(participant__name__icontains=search_query)
        logger.info(f"Filtering race results by name containing: {search_query}")

    if gender:
        participants = participants.filter(gender=gender)
        logger.info(f"Filtering participants by gender: {gender}")

    if age:
        age_ranges = {
            "18": (18, 25),
            "26": (26, 35),
            "36": (36, 45),
            "46": (46, 60),
            "60": (60, 1000),
        }
        if age in age_ranges:
            min_age, max_age = age_ranges[age]
            participants = participants.filter(age__gte=min_age, age__lte=max_age)
            logger.info(f"Filtering participants by age: {min_age}-{max_age}")

    if sort_by:
        logger.info(f"Sorting participants by {sort_by} in {sort_direction} order.")
        if sort_by == "name":
            participants = participants.order_by(
                "-name" if sort_direction == "desc" else "name"
            )
        elif sort_by == "age":
            participants = participants.order_by(
                "-age" if sort_direction == "desc" else "age"
            )

    participants_count = participants.count()

    #  build grouped dictionaries
    teams = defaultdict(list)
    clubs = defaultdict(list)

    for p in participants:
        if p.team_name:
            teams[p.team_name].append(p)
        if p.club_name:
            clubs[p.club_name].append(p)

    location_info = race.address or (
        f"Lat: {race.latitude}, Lon: {race.longitude}"
        if race.latitude and race.longitude
        else "None"
    )
    category_info = race.race_category if race.race_category else "None"
    categories = race.participant_categories.all()

    return render(
        request,
        "app/race_detail.html",
        {
            "race": race,
            "participants": participants,
            "participants_count": participants_count,
            "location_info": location_info,
            "category_info": category_info,
            "filters": request.GET,
            "categories": categories,
            "teams": dict(teams),
            "clubs": dict(clubs),
        },
    )


@login_and_2fa_required
def race_organiser_dashboard(request):
    """
    Defines the view for a race organiser dashboard.
    """

    logger.info(f"User {request.user.username} accessed the race organiser dashboard")

    query = request.GET.get("q", "")
    races = Race.objects.filter(organiser=request.user)

    if query:
        races = races.filter(name__icontains=query)
        logger.info(f"Filtered races with query: '{query}', {len(races)} results found")

    # calculate the total participants
    race_data = []
    for race in races:
        participants = Participant.objects.filter(race=race)
        participants_count = participants.count()
        race_data.append({"race": race, "participants_count": participants_count})

    return render(
        request,
        "app/race_organiser_dashboard.html",
        {
            "race_data": race_data,
            "query": query,
        },
    )


@login_and_2fa_required
def upcoming_races(request):
    """
    View for displaying all upcoming races that the authenticated user is participating in
    and where the race is not completed yet, with search and sorting functionality.
    """
    logger.info("Accessing the upcoming races view")

    #  get current datetime
    current_time = timezone.localtime(timezone.now())
    logger.info(f"Current time is {current_time}")

    #  get search query and sorting parameters
    search_query = request.GET.get("search", "")
    sort_by = request.GET.get("sort", "date")

    #  construct the raw SQL query
    query = """
        SELECT DISTINCT r.id, r.name, r.date, r.start_time
        FROM app_race r
        LEFT JOIN app_participant p ON r.id = p.race_id
        WHERE r.date >= %s
          AND r.is_completed = FALSE
          AND (p.user_id = %s OR p.user_id IS NULL)
    """

    #  add filtering
    if search_query:
        query += """
            AND (r.name LIKE %s)
        """

    #  add sorting
    if sort_by == "name":
        query += " ORDER BY r.name"
    else:
        query += " ORDER BY r.date, r.start_time"

    #  execute query
    with connection.cursor() as cursor:
        if search_query:
            cursor.execute(
                query, [current_time.date(), request.user.id, f"%{search_query}%"]
            )
        else:
            cursor.execute(query, [current_time.date(), request.user.id])

        races = cursor.fetchall()

    #  prepare the data to be rendered in the template
    user_upcoming_races = []
    for race in races:
        race_id, race_name, race_date, race_start_time = race
        user_upcoming_races.append(
            {
                "id": race_id,
                "name": race_name,
                "date": race_date,
                "start_time": race_start_time,
            }
        )

    #  render the page with the filtered upcoming races
    return render(
        request,
        "app/upcoming_races.html",
        {
            "upcoming_races": user_upcoming_races,
            "search_query": search_query,
            "sort_by": sort_by,
        },
    )


@login_and_2fa_required
def organiser_race_detail(request, race_id):
    """
    View for an organiser to see a specific race and its participants.
    """

    logger.info(f"Accessing organiser race detail view for race_id={race_id}")

    race = get_object_or_404(Race, id=race_id)
    participants = Participant.objects.filter(race=race)
    participants_count = participants.count()
    results = RaceResult.objects.filter(race=race).select_related("participant")

    logger.info(f"Race details fetched: {race.name} - {race.date}")
    logger.info(f"Displaying {participants_count} participants for race: {race.name}")
    logger.info(f"Found {results.count()} results for race: {race.name}")

    return render(
        request,
        "app/organiser_race_detail.html",
        {
            "race": race,
            "participants": participants,
            "participants_count": participants_count,
            "results": results if results.exists() else None,
        },
    )


@login_and_2fa_required
def race_results(request, race_id):
    """
    Defines the view for the results of a race.
    """

    logger.info(f"Accessing race results view for race_id={race_id}")

    #  get the race object
    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Race details fetched: {race.name} - {race.date} (ID: {race.id})")

    #  get the results
    results = RaceResult.objects.filter(race=race)
    logger.info(
        f"Fetched {results.count()} results for race {race.name} (ID: {race.id})"
    )

    #  render race results page
    logger.info(
        f"Rendering race results page for race {race.name} (ID: {race.id}) with {results.count()} results"
    )

    return render(request, "app/race_results.html", {"race": race, "results": results})


@login_and_2fa_required
def settings_view(request):
    """
    Defines the view for the settings page.
    """

    logger.info(
        f"Accessing settings page for user {request.user.username} (ID: {request.user.id})"
    )

    if request.method == "POST":
        logger.info(
            f"Settings form submitted for user {request.user.username} (ID: {request.user.id})"
        )

        user = request.user
        username = request.POST.get("username")
        email = request.POST.get("email")
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")

        #  update user details
        if (
            username != user.username
            or email != user.email
            or first_name != user.first_name
            or last_name != user.last_name
        ):
            logger.info(
                f"Updating user details: username from {user.username} to {username},"
                f" email from {user.email} to {email},"
                f" first_name from {user.first_name} to {first_name},"
                f" last_name from {user.last_name} to {last_name}"
            )

        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()

        messages.success(request, "Settings updated successfully!")
        logger.info(
            f"Settings updated successfully for user {request.user.username} (ID: {request.user.id})"
        )

        return redirect("settings")

    return render(request, "app/settings.html")


@login_and_2fa_required
def profile_view(request):
    """
    Defines the view for the profile page.
    """

    user = request.user
    logger.info(f"Accessing profile page for user {user.username} (ID: {user.id})")

    #  check for MFA secret
    if not user.mfa_secret:
        user.mfa_secret = pyotp.random_base32()
        user.save()

    otp_uri = pyotp.totp.TOTP(user.mfa_secret).provisioning_uri(
        name=user.email, issuer_name="Automated Run Timing"
    )

    qr = qrcode.make(otp_uri)
    buffer = io.BytesIO()
    qr.save(buffer, format="PNG")

    buffer.seek(0)
    qr_code = base64.b64encode(buffer.getvalue()).decode("utf-8")

    qr_code_data_uri = f"data:image/png;base64,{qr_code}"

    #  handle 2fa enable/disable
    if request.method == "POST":
        if "enable_2fa" in request.POST:
            otp = request.POST.get("otp")
            if otp:
                totp = pyotp.TOTP(user.mfa_secret)
                if totp.verify(otp):
                    user.mfa_enabled = True
                    user.save()
                    messages.success(
                        request, "Two-factor authentication enabled successfully!"
                    )
                    return redirect("profile")

                messages.error(request, "Invalid OTP. Please try again.")
        elif "disable_2fa" in request.POST:
            user.mfa_enabled = False
            user.save()
            messages.success(
                request, "Two-factor authentication disabled successfully!"
            )
            return redirect("profile")

    return render(
        request,
        "app/profile.html",
        {"qrcode": qr_code_data_uri, "mfa_enabled": user.mfa_enabled},
    )


@login_and_2fa_required
def participant_category_list(request):
    """
    View to display the list of participant categories.
    """

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is accessing the participant category list."
    )

    categories = ParticipantCategory.objects.all()

    logger.info(f"Loaded {categories.count()} participant categories.")

    return render(
        request, "app/participant_category_list.html", {"categories": categories}
    )


@login_and_2fa_required
def participant_category_create(request):
    """
    View to create a new participant category.
    """

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is"
        f" accessing the create participant category page."
    )

    if request.method == "POST":
        form = ParticipantCategoryForm(request.POST)

        if form.is_valid():
            form.save()
            logger.info(
                f"New participant category created by user {request.user.username} (ID: {request.user.id})."
            )
            return redirect("category_list")
        else:
            logger.warning(
                f"User {request.user.username} (ID: {request.user.id}) submitted invalid form data."
            )
    else:
        form = ParticipantCategoryForm()

    return render(request, "app/participant_category_form.html", {"form": form})


@login_and_2fa_required
def race_category_list(request):
    """
    View to list all the available race categories.
    """

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is accessing the race category list."
    )

    categories = RaceCategory.objects.all()

    if not categories:
        logger.warning("No race categories found in the database.")

    return render(request, "app/race_category_list.html", {"categories": categories})


@login_and_2fa_required
def race_category_create(request):
    """
    View to create a new race category.
    """

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is accessing the create race category page."
    )

    if request.method == "POST":
        form = RaceCategoryForm(request.POST)

        if form.is_valid():
            form.save()
            logger.info(
                f"Race category '{form.cleaned_data['name']}' created by user {request.user.username}."
            )
            return redirect("race_category_list")
        else:
            logger.warning(
                f"User {request.user.username} attempted to create a race category but the form is invalid."
            )
    else:
        form = RaceCategoryForm()

    return render(request, "app/race_category_create.html", {"form": form})


@login_and_2fa_required
def adjust_start_time(request, race_id):
    """
    View for adjusting the start time of a race.
    """
    race = get_object_or_404(Race, id=race_id)

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is adjusting the start time for race "
        f"'{race.name}' (ID: {race.id})."
    )

    if request.method == "POST":
        form = AdjustStartTimeForm(request.POST)

        if form.is_valid():
            new_start_datetime = form.cleaned_data["start_time"]
            old_date, old_time = race.date, race.start_time

            race.date = new_start_datetime.date()
            race.start_time = new_start_datetime.time()
            race.save()

            logger.info(
                f"Race '{race.name}' (ID: {race.id}) start date/time changed from "
                f"{old_date} {old_time} to {race.date} {race.start_time} by user {request.user.username}."
            )

            messages.success(request, "Start time updated successfully.")
            return redirect("organiser_race_detail", race_id=race.id)
        else:
            logger.warning(
                f"Invalid form submission by user {request.user.username} while adjusting start time "
                f"for race '{race.name}' (ID: {race.id})."
            )
    else:
        #  combine race.date and race.start_time into a datetime object
        initial_start_datetime = datetime.combine(race.date, race.start_time)
        form = AdjustStartTimeForm(initial={"start_time": initial_start_datetime})

    return render(request, "app/adjust_start_time.html", {"form": form, "race": race})


def google_callback(request):
    """
    Handles the callback from Google after the user logs in.
    """

    #  retrieve token
    token = request.GET.get("credential")
    if not token:
        logger.error("No token provided in the Google callback.")
        return HttpResponse("Error: No token provided", status=400)

    try:
        #  verify token
        id_info = verify_oauth2_token(
            token, requests.Request(), settings.GOOGLE_CLIENT_ID
        )

        #  check if the tokens audience matches client ID
        if id_info["aud"] != settings.GOOGLE_CLIENT_ID:
            logger.error(f"Invalid token from Google callback: {token}")
            return HttpResponse("Error: Invalid token", status=400)

        #  get the users Google info
        user_email = id_info["email"]
        user_name = id_info.get("given_name", "")
        user_picture = id_info.get("picture", "")

        logger.info(
            f"Google callback received for user: {user_email}. User name: {user_name},"
            f" User picture: {user_picture}"
        )

        #  handle user sign-in or registration
        user, created = User.objects.get_or_create(
            email=user_email,
            defaults={"name": user_name, "profile_picture": user_picture},
        )

        #  update user
        if not created:
            logger.info(f"User {user_email} already exists. Updating user information.")
            user.name = user_name
            user.profile_picture = user_picture
            user.save()
        else:
            logger.info(f"New user created: {user_email}")

        #  log in
        login(request, user)
        logger.info(f"User {user_email} successfully logged in.")

        #  redirect to landing page
        return redirect("/")

    except Exception as e:
        logger.error(f"Error during Google callback: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=400)


@csrf_exempt
def upload_image(request, race_id):
    """
    API endpoint function for the upload of images with a timestamp, for manual validation of results.
    """

    if request.method == 'POST' and request.FILES.get('image'):
        #  fetch token either
        token = request.POST.get('token') or request.GET.get('token') or request.headers.get('token')
        if not token:
            return JsonResponse({"error": "Missing upload token"}, status=401)

        logger.info("Received POST request with an image file.")

        #  validate race
        try:
            race = Race.objects.get(id=race_id)
            logger.info(f"Race with ID {race_id} found.")
        except Race.DoesNotExist:
            logger.error(f"Race with ID {race_id} does not exist.")
            return JsonResponse({'error': 'Invalid race ID'}, status=404)

        if race.token != token:
            logger.info("Invalid token in request.")
            return JsonResponse({'error': 'Invalid token'}, status=498)

        #  get timestamp
        timestamp_str = request.POST.get("timestamp")
        if not timestamp_str:
            logger.warning("No timestamp provided in the request.")
            return JsonResponse({"error": "Timestamp is required"}, status=400)

        timestamp = parse_datetime(timestamp_str)
        if not timestamp:
            logger.error(
                f"Invalid timestamp format: {timestamp_str}. Expected format: YYYY-MM-DD HH:MM:SS."
            )
            return JsonResponse(
                {"error": "Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS"},
                status=400,
            )

        #  get uploaded file
        uploaded_file = request.FILES["image"]
        logger.info(f"Received image file: {uploaded_file.name}")

        #  get optional bib_number
        bib_number = request.POST.get('bib_number') or -1

        try:
            #  save file to media storage
            file_path = default_storage.save(
                f"images/{uploaded_file.name}", ContentFile(uploaded_file.read())
            )
            file_url = default_storage.url(file_path)
            logger.info(f"File saved successfully at {file_url}.")
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}.")
            return JsonResponse({"error": "Error saving file."}, status=500)

        #  save image
        try:
            image_instance = Image.objects.create(
                name=uploaded_file.name,
                image=file_path,
                race=race,
                timestamp=timestamp,
                bib_number=bib_number
            )
            logger.info(f"Image instance created with ID {image_instance.id}.")
        except Exception as e:
            logger.error(f"Error creating image instance: {str(e)}.")
            return JsonResponse(
                {"error": "Error saving image to database."}, status=500
            )

        #  redirect to gallery view after successful upload
        return redirect('gallery_view', race_id=race.id)

        return JsonResponse(
            {
                "message": "Image uploaded successfully!",
                "file_url": file_url,
                "image_id": image_instance.id,
            }
        )

    logger.warning("Received request with no image file or incorrect method.")
    return JsonResponse({"error": "No file uploaded or incorrect method"}, status=400)


@login_and_2fa_required
def gallery_view(request, race_id):
    """
    A view for organisers to manually validate bib numbers for a specific race
    and manage images.
    """

    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Race with ID {race_id} found.")

    images = Image.objects.filter(race=race)
    logger.info(f"Found {images.count()} images associated with race ID {race_id}.")

    if request.method == "POST":
        #  detect if its a delete request
        if 'delete_image_id' in request.POST:
            delete_image_id = request.POST.get('delete_image_id')
            image_to_delete = images.filter(id=delete_image_id).first()

            if image_to_delete:
                logger.info(f"Deleting image with ID {delete_image_id}.")
                image_to_delete.delete()
                messages.success(request, "Image deleted successfully.")
            else:
                logger.warning(f"Attempted to delete non-existent image ID {delete_image_id}.")
                messages.error(request, "Image not found.")
            return redirect('gallery_view', race_id=race.id)

        #  normal bib number submission flow
        bib_number = request.POST.get("bib_number")
        image_id = request.POST.get("image_id")
        image_timestamp = request.POST.get("image_timestamp")

        logger.info(
            f"Received POST request for bib number: {bib_number}, image ID: {image_id},"
            f" and timestamp: {image_timestamp}."
        )

        image = images.filter(id=image_id).first()
        if not image:
            logger.warning(
                f"Image with ID {image_id} not found or does not belong to race ID {race_id}."
            )
            messages.error(request, "Image not found or does not belong to this race.")
            return render(
                request,
                "app/gallery.html",
                {"images": images, "MEDIA_URL": settings.MEDIA_URL, "race": race},
            )

        try:
            participant = Participant.objects.get(race=race, race_number=bib_number)
            logger.info(
                f"Participant with bib number {bib_number} found: {participant.name}"
            )

            #  check if a race result already exists for this participant and race
            existing_result = RaceResult.objects.filter(participant=participant, race=race).first()

            if existing_result:
                #  delete existing results
                logger.info(f"Deleting existing race result for participant {participant.name}.")
                existing_result.delete()
                messages.info(request, "Existing result deleted. Creating new result.")

            try:
                timestamp = datetime.strptime(image_timestamp, "%d %b %Y, %I:%M %p")
                if timezone.is_naive(timestamp):
                    timestamp = timezone.make_aware(timestamp)

                time = timestamp.strftime("%H:%M:%S")

                #  create the new race result
                RaceResult.objects.create(
                    participant=participant, race=race, total_time=time
                )

                logger.info(
                    f"Race result created for participant: {participant.name} with time: {time}."
                )
                messages.success(
                    request, f"Race result created for {participant.name}!"
                )

            except ValueError:
                logger.error(
                    f"Invalid timestamp format provided: {image_timestamp}. "
                    f"Expected format: '%d %b %Y, %I:%M %p'."
                )
                messages.error(
                    request, "Invalid timestamp format. Please check the input."
                )

        except Participant.DoesNotExist:
            logger.error(
                f"No participant found with bib number {bib_number} for race ID {race_id}."
            )
            messages.error(
                request, "No participant found with the given bib number for this race."
            )

    return render(
        request,
        "app/gallery.html",
        {"images": images, "MEDIA_URL": settings.MEDIA_URL, "race": race},
    )


def custom_404(request, exception):
    """
    Define a custom 404 page
    """

    logger.error(f"Page not found: {request.path} - Exception: {exception}")

    #  render custom 404 page
    return render(request, "404.html", status=404)


def custom_500(request):
    """
    Define a custom 500 page
    """

    logger.error(f"Internal Server Error at {request.path}.")

    #  render the custom 500 page
    return render(request, "500.html", status=500)


def custom_403(request, exception):
    """
    Define a custom 403 page
    """

    logger.warning(f"Permission Denied (403) at {request.path}. Exception: {exception}")

    #  render the custom 403 page
    return render(request, "403.html", status=403)


@login_and_2fa_required
def organiser_delete_race(request, race_id):
    """
    Deletes a race that the logged-in user is organising.
    """

    race = get_object_or_404(Race, id=race_id)

    #  check if the user is in the organisers list
    if request.user not in race.organiser.all():
        messages.error(request, "You are not authorised to delete this race.")
        return redirect("race_organiser_dashboard")

    #  delete the race
    race.delete()
    messages.success(request, "Race has been deleted successfully.")
    return redirect("race_organiser_dashboard")


@login_and_2fa_required
def apply_as_organiser(request):
    """
    Applies to be the organiser of a race.
    """

    #  exclude races the user already organises
    available_races = Race.objects.exclude(organiser=request.user)

    if request.method == "POST":
        form = OrganiserApplicationForm(request.POST, user=request.user)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Your application has been submitted.")
            return redirect("race_organiser_dashboard")
    else:
        form = OrganiserApplicationForm(user=request.user)

    return render(
        request,
        "app/apply_as_organiser.html",
        {"form": form, "available_races": available_races},
    )


@login_and_2fa_required
def view_applications(request):
    """
    views the organiser applications for a race.
    """

    races = request.user.organised_races.all()
    applications = OrganiserApplication.objects.filter(race__in=races, status="pending")
    return render(
        request, "app/organiser_applications.html", {"applications": applications}
    )


@login_and_2fa_required
def handle_application(request, app_id, action):
    """
    approves or denies an application to become the race organiser.
    """

    app = get_object_or_404(OrganiserApplication, id=app_id)

    #  ensure current user is an organiser of the race
    if request.user not in app.race.organiser.all():
        return redirect("organiser_dashboard")

    if action == "approve":
        app.status = "approved"
        app.race.organiser.add(app.user)
        messages.success(
            request, f"{app.user.username} is now an organiser for {app.race.name}."
        )
    elif action == "deny":
        app.status = "denied"
        messages.info(request, f"Application by {app.user.username} has been denied.")

    app.save()
    return redirect("view_applications")


@login_required
def verify_2fa_view(request):
    """
    Handles the OTP verification for 2FA during login.
    """

    #  check if the session has the flag indicating 2FA verification is needed
    if not request.session.get("needs_2fa", False):
        return redirect("/")

    user = request.user

    if request.method == "POST":
        otp = request.POST.get("otp")

        #  generate OTP validator
        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(otp):
            #  authenticate user
            messages.success(request, "2FA verification successful!")

            request.session["mfa_verified"] = True
            del request.session["needs_2fa"]

            return redirect("/")

        else:
            messages.error(request, "Invalid OTP. Please try again.")

    return render(request, "app/verify_2fa.html")


@login_and_2fa_required
def delete_participant(request, race_id, participant_id):
    """
    View to handle the deletion of a participant after confirmation.
    """

    #  get the race and participant objects
    race = get_object_or_404(Race, id=race_id)
    participant = get_object_or_404(Participant, id=participant_id)

    #  check if the user is one of the organisers of the race
    if request.user not in race.organiser.all():
        return HttpResponseForbidden(
            "You are not authorized to delete this participant."
        )

    #  delete the participant from the race
    participant.delete()

    messages.success(request, f"Participant {participant.name} has been deleted.")
    return redirect("organiser_race_detail", race_id=race.id)


@login_and_2fa_required
def edit_participant(request, race_id, participant_id):
    """
    Edits a participant data.
    """

    participant = get_object_or_404(Participant, id=participant_id, race_id=race_id)

    if request.method == "POST":
        participant.name = request.POST.get("name")
        participant.age = request.POST.get("age")
        participant.gender = request.POST.get("gender")
        participant.club_name = request.POST.get("club_name", participant.club_name)
        participant.team_name = request.POST.get("team_name", participant.team_name)
        participant.race_number = request.POST.get("race_number", participant.race_number)
        participant.save()
        messages.success(request, "Participant details updated successfully.")

    return redirect("organiser_race_detail", race_id=race_id)


@login_and_2fa_required
def add_participant(request, race_id):
    race = get_object_or_404(Race, id=race_id)

    name = request.POST.get("name")
    age = request.POST.get("age")
    gender = request.POST.get("gender")
    club_name = request.POST.get("club_name", "")
    team_name = request.POST.get("team_name", "")

    if name and age and gender:
        Participant.objects.create(
            race=race,
            name=name,
            age=age,
            gender=gender,
            club_name=club_name,
            team_name=team_name,
        )

    return redirect("race_detail", race_id=race.id)


@login_and_2fa_required
def confirm_delete_participant(request, race_id, participant_id):
    """
    View to confirm participant deletion.
    """

    #  get the race and participant objects
    race = get_object_or_404(Race, id=race_id)
    participant = get_object_or_404(Participant, id=participant_id)

    #  check if the user is one of the organisers of the race
    if request.user not in race.organiser.all():
        return HttpResponseForbidden(
            "You are not authorized to delete this participant."
        )

    return render(
        request,
        "app/confirm_delete_participant.html",
        {"participant": participant, "race": race},
    )


@login_required
def link_participant(request, participant_id):
    """
    Links a participant to the current user account.
    Only if the participant name matches the user's name.
    Each user can only be linked to one participant.
    """

    participant = get_object_or_404(Participant, id=participant_id)

    #  check if this participant is already linked
    if participant.user is not None:
        messages.error(request, "This participant is already linked to another user.")
        return redirect("race_detail", race_id=participant.race.id)

    #  check if the current user is already linked to another participant
    if Participant.objects.filter(user=request.user).exists():
        messages.error(request, "You are already linked to a participant.")
        return redirect("race_detail", race_id=participant.race.id)

    #  check if participant's name matches user's full name
    if participant.name.strip().lower() != request.user.name.strip().lower():
        messages.error(
            request, "Your account name does not match the participant's name."
        )
        return redirect("race_detail", race_id=participant.race.id)

    #  link the participant to the user
    participant.user = request.user
    participant.save()

    messages.success(request, f"You've successfully linked to {participant.name}!")
    return redirect("race_detail", race_id=participant.race.id)


@login_and_2fa_required
def manage_organiser_permissions(request, race_id):
    race = get_object_or_404(Race, id=race_id)
    organisers = race.organiser.all()
    main_organiser = organisers.first()

    if request.user != main_organiser:
        return HttpResponseForbidden(
            "Only the main organiser can manage organiser permissions."
        )

    # You could render a form or list to add/remove/manage permissions
    return render(
        request,
        "app/manage_organisers.html",
        {
            "race": race,
            "organisers": organisers,
        },
    )


def remove_organiser(request, race_id, organiser_id):
    race = get_object_or_404(Race, id=race_id)
    organiser = get_object_or_404(User, id=organiser_id)

    if request.user != race.organiser.all().first():
        return redirect("forbidden")

    race.organiser.remove(organiser)
    return redirect("manage_organiser_permissions", race_id=race.id)
