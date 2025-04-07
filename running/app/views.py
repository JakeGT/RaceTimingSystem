#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv
import re
import io
import json
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from google.auth.transport import requests

from .models import Participant, RaceResult, Race, ParticipantCategory, RaceCategory, Image, OrganiserApplication
from .utils.logger import setup_logging
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_time
from datetime import datetime, date, timedelta
from django.utils.timezone import make_aware
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from .forms import ParticipantCategoryForm, RaceCategoryForm, ImageUploadForm, AdjustStartTimeForm, OrganiserApplicationForm
from django.shortcuts import render
from django.shortcuts import redirect
from django.contrib.auth import login
from django.http import HttpResponse
from google.auth.transport.requests import Request
from google.oauth2.id_token import verify_oauth2_token
from django.conf import settings
from django.utils.dateparse import parse_datetime
from django.core.files.storage import default_storage

#  define custom user
from django.contrib.auth import get_user_model

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
    if request.method == 'POST':
        try:
            race = Race.objects.get(pk=race_id)
        except Race.DoesNotExist:
            return JsonResponse({"error": "Race not found"}, status=404)

        data = json.loads(request.body)
        bib_number = data.get('bib_number')
        result_time = data.get('time')

        #  fetch the participant based on race_id and bib_number (race_number)
        try:
            participant = Participant.objects.get(race=race, race_number=bib_number)
        except Participant.DoesNotExist:
            return JsonResponse({"error": "Participant not found"}, status=404)

        #  calculate the time difference between the start time and the given time
        start_time = race.start_time
        result_time_obj = parse_time(result_time)

        start_time_datetime = datetime.combine(date.min, start_time)
        result_time_datetime = datetime.combine(date.min, result_time_obj)

        if result_time_datetime < start_time_datetime:
            result_time_datetime += timedelta(days=1)

        time_difference = result_time_datetime - start_time_datetime

        #  create a RaceResult object
        RaceResult.objects.create(
            participant=participant,
            race=race,
            total_time=str(time_difference)
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
            return redirect('/')
        return view_func(request, *args, **kwargs)

    return _wrapped_view


def landing_page(request):
    """
    View for the landing page of the Race Timing System.
    """

    logger.info("Accessing the landing page view")

    return render(request, 'app/landing.html', {})


@logged_out_required
def user_register(request):
    """
    Handles user registration with password validation.
    """

    logger.info("Accessing the registration page view")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        logger.info(f"Registration attempt for username: {username}, email: {email}")

        #  password validation
        if password1 != password2:
            logger.info(f"Registration failed for {username}: Passwords do not match.")
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if len(password1) < 8:
            logger.info(f"Registration failed for {username}: Password too short.")
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("register")

        if not re.search(r"\d", password1):
            logger.info(f"Registration failed for {username}: Password missing a number.")
            messages.error(request, "Password must contain at least one number.")
            return redirect("register")

        if not re.search(r"[!@#$%^&*()\-_=+[\]{}|;:'\",.<>?/]", password1):
            logger.info(f"Registration failed for {username}: Password missing a special character.")
            messages.error(request, "Password must contain at least one special character.")
            return redirect("register")

        #  check if username already exists
        if User.objects.filter(username=username).exists():
            logger.info(f"Registration failed: Username '{username}' is already taken.")
            messages.error(request, "Username is already taken.")
            return redirect("register")

        #  check if email already exists
        if User.objects.filter(email=email).exists():
            logger.info(f"Registration failed: Email '{email}' is already registered.")
            messages.error(request, "An account with this email already exists.")
            return redirect("register")

        #  create and save the user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()

        logger.info(f"Registration successful for username: {username}, email: {email}")
        messages.success(request, "Registration successful! You can now log in.")
        return redirect("login")

    return render(request, "app/register.html")


@logged_out_required
def user_login(request):
    """
    Handles user login.
    """

    logger.info("Accessing the login page view")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        logger.info(f"Login attempt for username: {username}")

        #  authenticate the user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            logger.info(f"Login successful for username: {username}")
            messages.success(request, "Login successful!")
            return redirect("/")
        else:
            logger.info(f"Login failed for username: {username}: Invalid username or password.")
            messages.error(request, "Invalid username or password.")

    return render(request, "app/login.html")


@login_required
def user_logout(request):
    """
    Logs out the user.
    """

    #  log the logout attempt
    logger.info(f"User {request.user.username} logged out.")

    #  perform the logout
    logout(request)

    messages.success(request, "You have been logged out.")
    return redirect("login")


def dashboard(request):
    """
    View for the dashboard page.
    """

    logger.info("Accessing the dashboard page")

    #  get the search term
    race_search = request.GET.get('race_search', '').strip()

    #  get the completed filter
    completed = request.GET.get('completed', None)

    #  fetch all races
    races = Race.objects.all()

    #  apply search filter
    if race_search:
        logger.info(f"Filtering races with search term: '{race_search}'")
        races = races.filter(name__icontains=race_search)

    #  apply is_completed filter
    if completed is not None:
        if completed == 'on':
            logger.info("Filtering races with 'completed' status: True")
            races = races.filter(is_completed=True)
        else:
            logger.info("Filtering races with 'completed' status: False")
            races = races.filter(is_completed=False)

    if not races:
        logger.info("No races found in the database")
        return render(request, 'app/dashboard.html', {
            'races': races,
            'message': 'No races available matching your criteria.'
        })

    logger.info(f"Found {races.count()} races")
    return render(request, 'app/dashboard.html', {
        'races': races,
    })


@login_required
def race_config(request):
    """
    Views for race configuration page
    """
    logger.info(f"Accessing race configuration page by user: {request.user.username}")

    race_categories = RaceCategory.objects.all()
    participant_categories = ParticipantCategory.objects.all()
    saved_data = request.session.get('race_config_data', {})

    if request.method == 'POST':
        race_name = request.POST['race_name']
        race_date_str = request.POST['race_date']
        start_time = request.POST['start_time']
        no_location = request.POST.get('no_location', False)
        race_location = request.POST.get('race_location', '')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        if no_location:
            race_location = None
            latitude = None
            longitude = None

        #  save form values in session
        request.session['race_config_data'] = {
            'race_name': race_name,
            'race_date': race_date_str,
            'start_time': start_time,
            'race_category': request.POST.get('race_category', None),
            'participant_categories': request.POST.getlist('participant_categories'),
            'latitude': latitude,
            'longitude': longitude,
            'race_location': race_location,
            'no_location': no_location
        }

        #  validate race date
        try:
            race_date = make_aware(datetime.strptime(race_date_str, "%Y-%m-%d"))
            now = datetime.now().astimezone()
            if race_date.date() < now.date():
                messages.error(request, "Race date cannot be in the past.")
                return render(request, 'app/race_config.html', {
                    'race_categories': race_categories,
                    'participant_categories': participant_categories,
                    'saved_data': request.POST
                })
        except ValueError:
            messages.error(request, "Invalid race date format. Please use YYYY-MM-DD.")
            return render(request, 'app/race_config.html', {
                'race_categories': race_categories,
                'participant_categories': participant_categories,
                'saved_data': request.POST
            })

        logger.info(
            f"Race configuration submitted by {request.user.username} with name: {race_name},"
            f" date: {race_date_str}, start time: {start_time}, location: {race_location or 'No location'}"
        )

        if Race.objects.filter(name=race_name).exists():
            messages.error(request, f"A race named '{race_name}' already exists. Please choose a different name.")
            return render(request, 'app/race_config.html', {
                'race_categories': race_categories,
                'participant_categories': participant_categories,
                'saved_data': request.POST
            })

        race = Race.objects.create(
            name=race_name,
            date=race_date,
            start_time=start_time,
            latitude=latitude,
            longitude=longitude,
            address=race_location
        )
        race.organiser.add(request.user)
        logger.info(f"New race created: {race.name} with ID: {race.id} by {request.user.username}")

        race_category_id = request.POST.get('race_category')
        if race_category_id:
            try:
                race_category = RaceCategory.objects.get(id=race_category_id)
                race.category = race_category
                race.save()
                logger.info(f"Added race category {race_category.name} to race {race.name}")
            except RaceCategory.DoesNotExist:
                logger.error(f"Race category with ID {race_category_id} does not exist.")

        for category_id in request.POST.getlist('participant_categories'):
            try:
                participant_category = ParticipantCategory.objects.get(id=category_id)
                race.categories.add(participant_category)
                logger.info(f"Added participant category {participant_category.name} to race {race.name}")
            except ParticipantCategory.DoesNotExist:
                logger.error(f"Participant category with ID {category_id} does not exist.")

        request.session.pop('race_config_data', None)
        logger.info(f"Redirecting user {request.user.username} to the dashboard after race creation.")
        return redirect('/dashboard')

    logger.info(
        f"Rendering race configuration form with {len(race_categories)} race categories"
        f" and {len(participant_categories)} participant categories."
    )

    return render(request, 'app/race_config.html', {
        'race_categories': race_categories,
        'participant_categories': participant_categories,
        'saved_data': saved_data
    })


@login_required
def upload_results(request):
    """
    View for uploading race results via CSV file.
    """

    logger.info(f"Accessing the upload results page. Available races: {Race.objects.count()}")

    races = Race.objects.all()

    if request.method == 'POST':

        if 'file' in request.FILES:
            file = request.FILES['file']
            logger.info(f"File '{file.name}' received for upload.")

            try:
                #  decode the CSV file and process each row
                decoded_file = file.read().decode('utf-8').splitlines()
                reader = csv.reader(decoded_file)

                #  skip the header row if present
                header = next(reader, None)
                logger.info(f"CSV header: {header}")

                #  ensure race_id is provided
                race_id = request.POST.get('race_id')
                if not race_id:
                    messages.error(request, 'Please select a race before uploading CSV.')
                    logger.error("Race ID not provided.")
                    return render(request, 'app/upload_results.html', {'races': races})

                try:
                    race = Race.objects.get(id=race_id)
                    logger.info(f"Selected race for result upload: {race.name} (ID: {race.id})")
                except Race.DoesNotExist:
                    messages.error(request, 'Selected race does not exist.')
                    logger.error(f"Race with ID {race_id} not found.")
                    return render(request, 'app/upload_results.html', {'races': races})

                #  process each row in the CSV file
                for row in reader:
                    if len(row) < 2:
                        messages.error(request, 'CSV file format is incorrect.')
                        logger.error("CSV row format is incorrect (less than 2 columns).")
                        break

                    bib_number = row[0].strip()
                    result_time = row[1].strip()

                    #  skip empty rows
                    if not bib_number or not result_time:
                        logger.warning(f"Skipping empty row (bib_number: {bib_number}, result_time: {result_time})")
                        continue

                    #  find the participant
                    try:
                        participant = Participant.objects.get(race_id=race.id, race_number=bib_number)
                        logger.info(f"Found participant: {participant.name} (Bib: {bib_number})")
                    except Participant.DoesNotExist:
                        messages.error(request,
                                       f'Participant with bib number {bib_number} '
                                       f'not found for race {race.name}.')
                        logger.error(f"Participant with bib number {bib_number} not found for race {race.name}.")
                        continue

                    #  check if the result for this participant and race already exists
                    if RaceResult.objects.filter(race=race, participant=participant).exists():
                        messages.error(request,
                                       f'Result already uploaded for participant {bib_number}'
                                       f' in race {race.name}.')
                        logger.warning(f"Result already uploaded for participant {bib_number} in race {race.name}.")
                        continue

                    #  save the result to the database
                    RaceResult.objects.create(
                        race=race,
                        participant=participant,
                        total_time=result_time
                    )
                    logger.info(f"Result for participant {bib_number} successfully uploaded for race {race.name}.")

                messages.success(request, 'CSV file uploaded successfully!')
                logger.info(f"CSV upload for race {race.name} completed successfully.")

            except Exception as e:
                messages.error(request, f'Error uploading CSV: {str(e)}')
                logger.error(f"Error uploading CSV: {str(e)}")

    #  render the same page with all races and the messages
    logger.info("Rendering upload results page with races and any messages.")
    return render(request, 'app/upload_results.html', {'races': races})


@login_required
def upload_participants(request):
    """
    View for uploading participants either manually or via CSV.
    """

    logger.info("Accessing the upload participants page.")

    if request.method == 'POST':
        race_id = request.POST.get('race_id')

        if not race_id:
            messages.error(request, "Please select a race.")
            logger.warning("No race selected for participant upload.")
            return redirect('upload_participants')

        try:
            race = Race.objects.get(id=race_id)
            logger.info(f"Selected race for participant upload: {race.name} (ID: {race.id})")
        except Race.DoesNotExist:
            messages.error(request, "Invalid race selected.")
            logger.error(f"Invalid race selected. Race ID: {race_id} does not exist.")
            return redirect('upload_participants')

        # Handle CSV file upload
        if 'file' in request.FILES:
            csv_file = request.FILES['file']
            logger.info(f"CSV file '{csv_file.name}' received for upload.")

            #  ensure the uploaded file is a CSV
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Invalid file format. Please upload a CSV file.")
                logger.error(f"Invalid file format for upload. Expected .csv, but received {csv_file.name}.")
                return redirect('upload_participants')

            try:
                #  read and decode the CSV file
                decoded_file = csv_file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(decoded_file))

                #  required fields that must be present in the CSV
                required_fields = {'BibNumber', 'Firstname', 'Lastname', 'Gender', 'TeamName', 'AgeCategory', 'Age'}
                reader_fieldnames = {field.strip() for field in reader.fieldnames}
                missing_fields = required_fields - reader_fieldnames

                # Check for missing required columns
                if missing_fields:
                    messages.error(request, f"CSV file is missing required"
                                            f" columns: {', '.join(missing_fields)}")
                    logger.error(f"CSV file is missing required columns: {', '.join(missing_fields)}")
                    return redirect('upload_participants')

                participants = []
                for row in reader:
                    #  extract row data and ensure it's valid
                    bib_number = row.get('BibNumber', '').strip()
                    firstname = row.get('Firstname', '').strip()
                    lastname = row.get('Lastname', '').strip()
                    gender = row.get('Gender', '').strip()
                    club_name = row.get('ClubName', '').strip()
                    team_name = row.get('TeamName', '').strip()
                    age_category = row.get('AgeCategory', '').strip()
                    try:
                        age = int(row.get('Age', '').strip())
                    except ValueError:
                        age = None

                    #  skip rows with missing fields
                    if not all([bib_number, firstname, lastname, gender, team_name, age_category]) or age is None:
                        messages.warning(request, f"Skipping incomplete or invalid row: {row}")
                        logger.warning(f"Skipping incomplete or invalid row: {row}")
                        continue

                    #  validate gender
                    if gender not in ['male', 'female', 'other']:
                        messages.warning(request, f"Invalid gender in row: {row}. Skipping.")
                        logger.warning(f"Invalid gender in row: {row}. Gender must be 'male', 'female', or 'other'.")
                        continue

                    #  check if participant already exists with the same bib number
                    existing_participant = Participant.objects.filter(race=race, race_number=bib_number).first()
                    if existing_participant:
                        messages.warning(request, f"Participant with Bib Number {bib_number} already"
                                                  f" exists for this race.")
                        logger.warning(f"Participant with Bib Number {bib_number} already exists for race {race.name}.")
                        continue

                    #   add the valid participant
                    participants.append(Participant(
                        race=race,
                        race_number=bib_number,
                        name=f"{firstname} {lastname}",
                        age=age,
                        gender=gender,
                        club_name=club_name,
                        team_name=team_name,
                        age_category=age_category,
                        status='pending'
                    ))

                if participants:
                    Participant.objects.bulk_create(participants)
                    messages.success(request, f"Successfully uploaded {len(participants)} participants.")
                    logger.info(f"Successfully uploaded {len(participants)} participants for race {race.name}.")
                else:
                    messages.warning(request, "No valid participants were found in the CSV file.")
                    logger.warning("No valid participants found in the CSV file.")

            except csv.Error as e:
                messages.error(request, f"Error reading CSV file: {str(e)}")
                logger.error(f"CSV error: {str(e)}")
                return redirect('upload_participants')

            except Exception as e:
                messages.error(request, f"Error processing CSV file: {str(e)}")
                logger.error(f"Error processing CSV file: {str(e)}")
                return redirect('upload_participants')

            return redirect('upload_results')

        #  handle manual entry form
        elif 'bib_number' in request.POST:
            bib_number = request.POST.get('bib_number')
            firstname = request.POST.get('firstname')
            lastname = request.POST.get('lastname')
            gender = request.POST.get('gender')
            team_name = request.POST.get('team_name')
            age_category = request.POST.get('age_category')
            race_category = request.POST.get('race_category')
            age = int(request.POST.get('age', 0))

            #  validate form data
            if not all([bib_number, firstname, lastname, gender, team_name, age_category, race_category, age]):
                messages.error(request, "Please fill in all required fields.")
                return redirect('upload_participants')

            #  check for existing participant with the same bib number
            existing_participant = Participant.objects.filter(race=race, race_number=bib_number).first()
            if existing_participant:
                messages.warning(request, f"Participant with Bib Number {bib_number} already exists for this race.")
                return redirect('upload_participants')

            #  create participant
            participant = Participant(
                race=race,
                race_number=bib_number,
                name=f"{firstname} {lastname}",
                age=age,
                gender=gender,
                team_name=team_name,
                age_category=age_category,
                status='pending'
            )

            #  assign selected category if available
            if race_category:
                race_category_obj = RaceCategory.objects.filter(name=race_category).first()
                if race_category_obj:
                    participant.category = race_category_obj

            participant.save()
            messages.success(request, "Participant added successfully!")
            logger.info(f"Added participant {firstname} {lastname} (Bib: {bib_number}) for race {race.name}.")

            return redirect('upload_results')

    #  get all available races
    races = Race.objects.all()
    categories = RaceCategory.objects.all()  # Fetch all available race categories
    logger.info(f"Rendering upload participants page with {races.count()} races available.")
    return render(request, 'app/upload_participants.html', {'races': races, 'categories': categories})


@login_required
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
    return redirect('/')


@login_required
def manage_participants(request, race_id):
    """
    Loads a page where organisers can approve or deny participants.
    """

    #  fetch race object
    race = get_object_or_404(Race, id=race_id)
    participants = race.participants.filter(status='pending')

    logger.info(f"Accessing manage participants page for race: {race.name} (ID: {race.id})")

    if request.method == 'POST':
        action = request.POST.get('action')
        participant_id = request.POST.get('participant_id')
        participant = get_object_or_404(Participant, id=participant_id)

        if action == 'approve':
            participant.status = 'approved'
            logger.info(f"Approved participant: {participant.name} (Bib: {participant.race_number}) for race"
                        f" {race.name}")
        elif action == 'deny':
            participant.status = 'denied'
            logger.info(f"Denying participant: {participant.name} (Bib:"
                        f" {participant.race_number}) for race {race.name}")
        else:
            logger.warning(f"Invalid action attempted: {action} for partic"
                           f"ipant {participant.name} (ID: {participant.id})")

        #  save the participant status
        participant.save()
        messages.success(request, f"Participant {participant.name} has been {participant.status}.")

        #  refresh page
        return redirect('manage_participants', race_id=race.id)

    return render(request, 'app/manage_participants.html',
                  {'race': race, 'participants': participants})


@login_required
def race_history(request):
    """
    Views the history of a runner.
    """

    #  check if the user has an associated participant
    if hasattr(request.user, 'participant'):
        participant = request.user.participant
        logger.info(f"User {request.user.username} has an associated participant with ID: {participant.id}.")
    else:
        participant = None
        logger.info(f"User {request.user.username} does not have an associated participant.")

    #  render race history page
    return render(request, 'app/race_history.html', {'participant': participant})


def race_detail(request, race_id):
    """
    View for displaying race details, including race results or participant list.
    """

    #  fetch the race object based on the provided race_id
    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Accessed race details for race: {race.name} (ID: {race.id})")

    #  get race results
    race_results = RaceResult.objects.filter(race=race)

    #  get sorting and filtering parameters
    sort_by = request.GET.get('sort_by', '')
    sort_direction = request.GET.get('sort_direction', 'asc')

    #  initialise gender and age filters
    gender = request.GET.get('gender', None)
    age = request.GET.get('age', None)

    #  apply filters
    if race_results.exists():
        logger.info(f"Found {len(race_results)} race results for race: {race.name}")

        #  apply gender filter
        if gender:
            race_results = race_results.filter(participant__gender=gender)
            logger.info(f"Filtering race results by gender: {gender}")

        #  apply age filter
        if age:
            age_ranges = {
                '18': (18, 25),
                '26': (26, 35),
                '36': (36, 45),
                '46': (46, 60),
                '60': (60, 1000),
            }
            if age in age_ranges:
                min_age, max_age = age_ranges[age]
                race_results = race_results.filter(participant__age__gte=min_age, participant__age__lte=max_age)
                logger.info(f"Filtering race results by age range: {min_age}-{max_age}")

        #  apply sorting
        if sort_by:
            logger.info(f"Sorting race results by {sort_by} in {sort_direction} order.")
            if sort_by == 'name':
                race_results = race_results.order_by(
                    '-participant__name' if sort_direction == 'desc' else 'participant__name')
            elif sort_by == 'age':
                race_results = race_results.order_by(
                    '-participant__age' if sort_direction == 'desc' else 'participant__age')
            elif sort_by == 'total_time':
                race_results = race_results.order_by(
                    '-total_time' if sort_direction == 'desc' else 'total_time')

        #  render race results page
        return render(request, 'app/race_results.html', {
            'race': race,
            'race_results': race_results,
        })

    #  if there are no race results, display participants
    participants = Participant.objects.filter(race=race).values('name', 'age', 'gender', 'age_category', 'race_number')

    #  apply filters for participants
    if gender:
        participants = participants.filter(gender=gender)
        logger.info(f"Filtering participants by gender: {gender}")

    if age:
        age_ranges = {
            '18': (18, 25),
            '26': (26, 35),
            '36': (36, 45),
            '46': (46, 60),
            '60': (60, 1000),
        }
        if age in age_ranges:
            min_age, max_age = age_ranges[age]
            participants = participants.filter(age__gte=min_age, age__lte=max_age)
            logger.info(f"Filtering participants by age range: {min_age}-{max_age}")

    #  apply sorting
    if sort_by:
        logger.info(f"Sorting participants by {sort_by} in {sort_direction} order.")
        if sort_by == 'name':
            participants = participants.order_by('-name' if sort_direction == 'desc' else 'name')
        elif sort_by == 'age':
            participants = participants.order_by('-age' if sort_direction == 'desc' else 'age')

    #  count participants
    participants_count = participants.count()
    logger.info(f"Displaying {participants_count} participants for race: {race.name}")

    #  check if the race has a location
    location_info = None
    if race.address:
        location_info = race.address
    elif race.latitude and race.longitude:
        location_info = f"Lat: {race.latitude}, Lon: {race.longitude}"
    else:
        location_info = "None"

    #  check if the race has a category
    category_info = race.race_category if race.race_category else "None"

    return render(request, 'app/race_detail.html', {
        'race': race,
        'participants': participants,
        'participants_count': participants_count,
        'location_info': location_info,
        'category_info': category_info,
    })


@login_required
def race_organiser_dashboard(request):
    """
    Defines the view for a race organiser dashboard.
    """

    logger.info(f"User {request.user.username} accessed the race organiser dashboard")

    #  get races where the logged-in user is the organiser
    races = Race.objects.filter(organiser=request.user)
    logger.info(f"Found {len(races)} races for organiser: {request.user.username}")

    #  calculate the total participants
    race_data = []
    for race in races:
        participants = Participant.objects.filter(race=race)

        #  count the filtered participants
        participants_count = participants.count()
        logger.info(f"Race {race.name} (ID: {race.id}) has {participants_count} participants")

        race_data.append({
            'race': race,
            'participants_count': participants_count
        })

    logger.info(f"Race organiser dashboard data prepared with {len(race_data)} races")

    return render(request, 'app/race_organiser_dashboard.html', {'race_data': race_data})


@login_required(login_url="login")
def upcoming_races(request):
    """
    View for displaying all upcoming races.
    Filters races that have a start date in the future.
    """

    logger.info("Accessing the upcoming races view")

    #  get current datetime
    current_time = timezone.now()
    logger.info(f"Current time is {current_time}")

    #  get all future races
    upcoming = Race.objects.filter(date__gte=current_time.date()).order_by('date', 'start_time')

    logger.info(f"Found {upcoming.count()} upcoming races")

    #  render the page with the upcoming races
    return render(request, 'app/upcoming_races.html', {'upcoming_races': upcoming})


def organiser_race_detail(request, race_id):
    """
    View for an organiser to see a specific race and its participants.
    """

    logger.info(f"Accessing organiser race detail view for race_id={race_id}")

    #  fetch the race object
    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Race details fetched: {race.name} - {race.date}")

    #  fetch all participants for the race
    participants = Participant.objects.filter(race=race)
    participants_count = participants.count()
    logger.info(f"Displaying {participants_count} participants for race: {race.name}")

    return render(request, 'app/organiser_race_detail.html', {
        'race': race,
        'participants': participants,
        'participants_count': participants_count,
    })


@login_required(login_url="login")
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
    logger.info(f"Fetched {results.count()} results for race {race.name} (ID: {race.id})")

    #  render race results page
    logger.info(f"Rendering race results page for race {race.name} (ID: {race.id}) with {results.count()} results")

    return render(request, 'app/race_results.html', {'race': race, 'results': results})


@login_required
def settings_view(request):
    """
    Defines the view for the settings page.
    """

    logger.info(f"Accessing settings page for user {request.user.username} (ID: {request.user.id})")

    if request.method == "POST":
        logger.info(f"Settings form submitted for user {request.user.username} (ID: {request.user.id})")

        user = request.user
        username = request.POST.get("username")
        email = request.POST.get("email")
        notify_race_updates = request.POST.get("notify_race_updates") == "on"

        #  update user details
        if username != user.username or email != user.email:
            logger.info(
                f"Updating user details: username from {user.username} to {username},"
                f" email from {user.email} to {email}")
        user.username = username
        user.email = email
        user.save()

        #  update profile settings
        if user.profile.notify_race_updates != notify_race_updates:
            logger.info(
                f"Updating profile settings: notify_race_updates from"
                f" {user.profile.notify_race_updates} to {notify_race_updates}")
        user.profile.notify_race_updates = notify_race_updates
        user.profile.save()

        messages.success(request, "Settings updated successfully!")
        logger.info(f"Settings updated successfully for user {request.user.username} (ID: {request.user.id})")

        return redirect("settings")

    return render(request, "app/settings.html")


@login_required
def profile_view(request):
    """
    Defines the view for the profile page.
    """

    logger.info(f"Accessing profile page for user {request.user.username} (ID: {request.user.id})")

    #  try to get the Participant instance associated with the logged-in user
    participant = Participant.objects.filter(user=request.user).first()

    if not participant:
        logger.warning(f"User {request.user.username} (ID: {request.user.id}) is not"
                       f" registered as a race participant.")
        return render(request, "app/profile.html",
                      {"error": "You are not registered as a race participant."})

    #  query races where the user is a participant
    races = Race.objects.filter(participants=participant)
    logger.info(f"User {request.user.username} (ID: {request.user.id}) is registered for {races.count()} races.")

    return render(request, "app/profile.html", {"participant": participant, "races": races})


@login_required
def participant_category_list(request):
    """
    View to display the list of participant categories.
    """

    logger.info(f"User {request.user.username} (ID: {request.user.id}) is accessing the participant category list.")

    categories = ParticipantCategory.objects.all()

    logger.info(f"Loaded {categories.count()} participant categories.")

    return render(request, 'app/participant_category_list.html', {'categories': categories})


@login_required
def participant_category_create(request):
    """
    View to create a new participant category.
    """

    logger.info(f"User {request.user.username} (ID: {request.user.id}) is"
                f" accessing the create participant category page.")

    if request.method == 'POST':
        form = ParticipantCategoryForm(request.POST)

        if form.is_valid():
            form.save()
            logger.info(f"New participant category created by user {request.user.username} (ID: {request.user.id}).")
            return redirect('category_list')
        else:
            logger.warning(f"User {request.user.username} (ID: {request.user.id}) submitted invalid form data.")
    else:
        form = ParticipantCategoryForm()

    return render(request, 'app/participant_category_form.html', {'form': form})


def race_category_list(request):
    """
    View to list all the available race categories.
    """

    logger.info(f"User {request.user.username} (ID: {request.user.id}) is accessing the race category list.")

    categories = RaceCategory.objects.all()

    if not categories:
        logger.warning("No race categories found in the database.")

    return render(request, 'app/race_category_list.html', {'categories': categories})


@login_required
def race_category_create(request):
    """
    View to create a new race category.
    """

    logger.info(f"User {request.user.username} (ID: {request.user.id}) is accessing the create race category page.")

    if request.method == 'POST':
        form = RaceCategoryForm(request.POST)

        if form.is_valid():
            form.save()
            logger.info(f"Race category '{form.cleaned_data['name']}' created by user {request.user.username}.")
            return redirect('race_category_list')
        else:
            logger.warning(f"User {request.user.username} attempted to create a race category but the form is invalid.")
    else:
        form = RaceCategoryForm()

    return render(request, 'app/race_category_create.html', {'form': form})


@login_required
def adjust_start_time(request, race_id):
    """
    View for adjusting the start time of a race.
    """

    #  get the race object
    race = get_object_or_404(Race, id=race_id)

    logger.info(
        f"User {request.user.username} (ID: {request.user.id}) is adjusting the start time for race"
        f" '{race.name}' (ID: {race.id}).")

    if request.method == 'POST':
        form = AdjustStartTimeForm(request.POST)

        if form.is_valid():
            #  update start time
            new_start_time = form.cleaned_data['start_time']
            old_start_time = race.start_time

            logger.info(
                f"Start time for race '{race.name}' (ID: {race.id}) is being changed"
                f" from {old_start_time} to {new_start_time}.")

            race.start_time = new_start_time
            race.save()

            logger.info(
                f"Start time for race '{race.name}' (ID: {race.id}) successfully updated by user"
                f" {request.user.username}.")
            return redirect('organiser_race_detail', race_id=race.id)
        else:
            logger.warning(
                f"User {request.user.username} attempted to adjust the start time for race"
                f" '{race.name}' (ID: {race.id}) but the form was invalid.")
    else:
        form = AdjustStartTimeForm(initial={'start_time': race.start_time})

    return render(request, 'app/adjust_start_time.html', {'form': form, 'race': race})


def google_callback(request):
    """
    Handles the callback from Google after the user logs in.
    """

    #  retrieve token
    token = request.GET.get('credential')
    if not token:
        logger.error("No token provided in the Google callback.")
        return HttpResponse("Error: No token provided", status=400)

    try:
        #  verify token
        id_info = verify_oauth2_token(token, requests.Request(), settings.GOOGLE_CLIENT_ID)

        #  check if the tokens audience matches client ID
        if id_info['aud'] != settings.GOOGLE_CLIENT_ID:
            logger.error(f"Invalid token from Google callback: {token}")
            return HttpResponse("Error: Invalid token", status=400)

        #  get the users Google info
        user_email = id_info['email']
        user_name = id_info.get('given_name', '')
        user_picture = id_info.get('picture', '')

        logger.info(f"Google callback received for user: {user_email}. User name: {user_name},"
                    f" User picture: {user_picture}")

        #  handle user sign-in or registration
        user, created = User.objects.get_or_create(email=user_email,
                                                   defaults={'name': user_name, 'profile_picture': user_picture})

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
        return redirect('/')

    except Exception as e:
        logger.error(f"Error during Google callback: {str(e)}")
        return HttpResponse(f"Error: {str(e)}", status=400)


@csrf_exempt
def upload_image(request):
    """
    API endpoint function for the upload of images with a timestamp, for manual validation of results.
    """

    if request.method == 'POST' and request.FILES.get('image'):

        logger.info("Received POST request with an image file.")

        #   get race ID from request
        race_id = request.POST.get('race_id')
        if not race_id:
            logger.warning("No race ID provided in the request.")
            return JsonResponse({'error': 'Race ID is required'}, status=400)

        #   validate race
        try:
            race = Race.objects.get(id=race_id)
            logger.info(f"Race with ID {race_id} found.")
        except Race.DoesNotExist:
            logger.error(f"Race with ID {race_id} does not exist.")
            return JsonResponse({'error': 'Invalid race ID'}, status=404)

        #   get timestamp
        timestamp_str = request.POST.get('timestamp')
        if not timestamp_str:
            logger.warning("No timestamp provided in the request.")
            return JsonResponse({'error': 'Timestamp is required'}, status=400)

        timestamp = parse_datetime(timestamp_str)
        if not timestamp:
            logger.error(f"Invalid timestamp format: {timestamp_str}. Expected format: YYYY-MM-DD HH:MM:SS.")
            return JsonResponse({'error': 'Invalid timestamp format. Use YYYY-MM-DD HH:MM:SS'}, status=400)

        #   get the uploaded file
        uploaded_file = request.FILES['image']
        logger.info(f"Received image file: {uploaded_file.name}")

        try:
            #   save file to media
            file_path = default_storage.save(f'images/{uploaded_file.name}', ContentFile(uploaded_file.read()))
            file_url = default_storage.url(file_path)
            logger.info(f"File saved successfully at {file_url}.")
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}.")
            return JsonResponse({'error': 'Error saving file.'}, status=500)

        #   save to database
        try:
            image_instance = Image.objects.create(
                name=uploaded_file.name,
                image=file_path,
                race=race,
                timestamp=timestamp
            )
            logger.info(f"Image instance created with ID {image_instance.id}.")
        except Exception as e:
            logger.error(f"Error creating image instance: {str(e)}.")
            return JsonResponse({'error': 'Error saving image to database.'}, status=500)

        return JsonResponse(
            {'message': 'Image uploaded successfully!', 'file_url': file_url, 'image_id': image_instance.id}
        )

    logger.warning("Received request with no image file or incorrect method.")
    return JsonResponse({'error': 'No file uploaded or incorrect method'}, status=400)


@login_required
def gallery_view(request, race_id):
    """
    A view for organisers to manually validate bib numbers for a specific race.
    """

    #   get the race object
    race = get_object_or_404(Race, id=race_id)
    logger.info(f"Race with ID {race_id} found.")

    #   fetch images
    images = Image.objects.filter(race=race)
    logger.info(f"Found {images.count()} images associated with race ID {race_id}.")

    if request.method == 'POST':
        bib_number = request.POST.get('bib_number')
        image_id = request.POST.get('image_id')
        image_timestamp = request.POST.get('image_timestamp')

        logger.info(f"Received POST request for bib number: {bib_number}, image ID: {image_id},"
                    f" and timestamp: {image_timestamp}.")

        #   find the image based on ID
        image = images.filter(id=image_id).first()
        if not image:
            logger.warning(f"Image with ID {image_id} not found or does not belong to race ID {race_id}.")
            messages.error(request, "Image not found or does not belong to this race.")
            return render(request, 'app/gallery.html',
                          {'images': images, 'MEDIA_URL': settings.MEDIA_URL, 'race': race})

        try:
            #   try to find participant with the given bib number
            participant = Participant.objects.get(race=race, race_number=bib_number)
            logger.info(f"Participant with bib number {bib_number} found: {participant.name}")

            try:
                #   parse the timestamp from the input
                timestamp = datetime.strptime(image_timestamp, "%d %b %Y, %I:%M %p")
                if timezone.is_naive(timestamp):
                    timestamp = timezone.make_aware(timestamp)

                time = timestamp.strftime("%H:%M:%S")

                #   create race result
                RaceResult.objects.create(
                    participant=participant,
                    race=race,
                    total_time=time
                )

                logger.info(f"Race result created for participant: {participant.name} with time: {time}.")
                messages.success(request, f"Race result created for {participant.name}!")

            except ValueError:
                logger.error(f"Invalid timestamp format provided: {image_timestamp}. "
                             f"Expected format: '%d %b %Y, %I:%M %p'.")
                messages.error(request, "Invalid timestamp format. Please check the input.")

        except Participant.DoesNotExist:
            logger.error(f"No participant found with bib number {bib_number} for race ID {race_id}.")
            messages.error(request, "No participant found with the given bib number for this race.")

    return render(request, 'app/gallery.html', {
        'images': images,
        'MEDIA_URL': settings.MEDIA_URL,
        'race': race
    })


def custom_404(request, exception):
    """
    Define a custom 404 page
    """

    logger.error(f"Page not found: {request.path} - Exception: {exception}")

    #  render custom 404 page
    return render(request, '404.html', status=404)


def custom_500(request):
    """
    Define a custom 500 page
    """

    logger.error(f"Internal Server Error at {request.path}.")

    #  render the custom 500 page
    return render(request, '500.html', status=500)


def custom_403(request, exception):
    """
    Define a custom 403 page
    """

    logger.warning(f"Permission Denied (403) at {request.path}. Exception: {exception}")

    #  render the custom 403 page
    return render(request, '403.html', status=403)


@login_required
def organiser_delete_race(request, race_id):
    """
    Deletes a race that the logged-in user is organising.
    """

    race = get_object_or_404(Race, id=race_id)

    #  check if the user is in the organisers list
    if request.user not in race.organiser.all():
        messages.error(request, "You are not authorised to delete this race.")
        return redirect('race_organiser_dashboard')

    #  delete the race
    race.delete()
    messages.success(request, "Race has been deleted successfully.")
    return redirect('race_organiser_dashboard')

@login_required
def apply_as_organiser(request):
    """
    Applies to be the organiser of a race.
    """

    #  fetch races where the user is not the organiser
    available_races = Race.objects.exclude(organiser=request.user)

    if request.method == 'POST':
        form = OrganiserApplicationForm(request.POST)
        if form.is_valid():
            app = form.save(commit=False)
            app.user = request.user
            app.save()
            messages.success(request, "Your application has been submitted.")
            return redirect('race_organiser_dashboard')
    else:
        form = OrganiserApplicationForm()

    return render(request, 'app/apply_as_organiser.html', {'form': form, 'available_races': available_races})



@login_required
def view_applications(request):
    """
    views the organiser applications for a race.
    """

    races = request.user.organised_races.all()
    applications = OrganiserApplication.objects.filter(race__in=races, status='pending')
    return render(request, 'app/organiser_applications.html', {'applications': applications})


@login_required
def handle_application(request, app_id, action):
    """
    approves or denies an application to become the race organiser.
    """

    app = get_object_or_404(OrganiserApplication, id=app_id)

    #  ensure current user is an organiser of the race
    if request.user not in app.race.organiser.all():
        return redirect('organiser_dashboard')

    if action == 'approve':
        app.status = 'approved'
        app.race.organiser.add(app.user)
        messages.success(request, f"{app.user.username} is now an organiser for {app.race.name}.")
    elif action == 'deny':
        app.status = 'denied'
        messages.info(request, f"Application by {app.user.username} has been denied.")

    app.save()
    return redirect('view_applications')
