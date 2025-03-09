#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv
from django.shortcuts import get_object_or_404
from .models import Participant, RaceResult, Race
from .utils.logger import setup_logging
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User
from functools import wraps
import re
import io
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
import os
from django.utils.dateparse import parse_time
from .models import Race, Participant, RaceResult
from datetime import datetime, date, timedelta
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import F

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
#
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

        # Fetch the participant based on race_id and bib_number (race_number)
        try:
            participant = Participant.objects.get(race=race, race_number=bib_number)
        except Participant.DoesNotExist:
            return JsonResponse({"error": "Participant not found"}, status=404)

        # Calculate the time difference between the start time and the given time
        start_time = race.start_time
        result_time_obj = parse_time(result_time)

        start_time_datetime = datetime.combine(date.min, start_time)
        result_time_datetime = datetime.combine(date.min, result_time_obj)

        if result_time_datetime < start_time_datetime:
            result_time_datetime += timedelta(days=1)

        time_difference = result_time_datetime - start_time_datetime

        # Create a RaceResult object
        RaceResult.objects.create(
            participant=participant,
            race=race,
            total_time=str(time_difference)
        )

        return JsonResponse({"message": "Data processed and race result created."})
    return JsonResponse({"error": "Invalid request method"}, status=400)

# -------------------------------------------------- Setup Logging -----------------------------------------------------
logger = setup_logging()

# ------------------------------------------------ Function Definitions ------------------------------------------------
def logged_out_required(view_func):
    """
    Define a logged out wrapper for pages users cannot access whilst being logged in.
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
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

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        #  password validation
        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return redirect("register")

        if not re.search(r"\d", password1):
            messages.error(request, "Password must contain at least one number.")
            return redirect("register")

        if not re.search(r"[!@#$%^&*()\-_=+[\]{}|;:'\",.<>?/]", password1):
            messages.error(request, "Password must contain at least one special character.")
            return redirect("register")

        #  check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return redirect("register")

        #  create and save the user
        user = User.objects.create_user(username=username, email=email, password=password1)
        user.save()

        messages.success(request, "Registration successful! You can now log in.")
        return redirect("login")

    return render(request, "app/register.html")

@logged_out_required
def user_login(request):
    """
    Handles user login.
    """

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            messages.success(request, "Login successful!")
            return redirect("/")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "app/login.html")

@login_required(login_url="login")
def user_logout(request):
    """
    Logs out the user.
    """

    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")

class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = "app/password_reset.html"
    email_template_name = "app/password_reset_email.html"
    subject_template_name = "app/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")
    success_message = "Password reset email sent! Check your inbox."

def dashboard(request):
    """
    View for the dashboard with race search and completion status filter functionality.
    """

    logger.info("Accessing the dashboard view")

    #  get the search term if provided
    race_search = request.GET.get('race_search', '').strip()

    #  get the 'completed' filter if provided
    completed = request.GET.get('completed', None)

    #  fetch all races or filter by search term
    races = Race.objects.all()

    #  apply search filter if a race search term is provided
    if race_search:
        races = races.filter(name__icontains=race_search)

    #  apply is_completed filter if the checkbox is checked
    if completed is not None:
        # if completed checkbox is checked, filter to only show completed races
        races = races.filter(is_completed=True)
    else:
        races = races.filter(is_completed=False)

    #  if no races exist after filtering, show a message
    if not races:
        logger.info("No races found in the database based on search or completion criteria")
        return render(request, 'app/dashboard.html', {
            'races': races,
            'message': 'No races available matching your criteria.'
        })

    return render(request, 'app/dashboard.html', {
        'races': races,
    })

@login_required
def race_config(request):
    """
    View for the race configuration page.
    """

    if request.method == 'POST':
        #  handle form submission
        race_name = request.POST.get('race_name')
        race_date = request.POST.get('race_date')
        start_time = request.POST.get('start_time')

        #  create a new race object and assign the current user as the organiser
        race = Race.objects.create(
            name=race_name,
            date=race_date,
            start_time=start_time,
            organiser=request.user
        )

        #  after saving the race, redirect to the upload participants page
        return redirect('upload_participants')

    return render(request, 'app/race_config.html')

def upload_results(request):
    """
    View for uploading race results manually or via CSV file.
    """

    races = Race.objects.all()

    if request.method == 'POST':
        if 'upload_option' in request.POST:

            #  handle manual result entry
            if request.POST.get('upload_option') == 'manual':
                race_id = request.POST.get('race_id')
                bib_number = request.POST.get('bib_number')
                result_time = request.POST.get('result')

                #  validate and save the result
                if not race_id or not bib_number or not result_time:
                    messages.error(request, 'All fields are required for manual entry.')
                    return render(request, 'app/upload_results.html', {'races': races})

                try:
                    result = RaceResult.objects.create(race_id=race_id, bib_number=bib_number, result_time=result_time)
                    messages.success(request, 'Race result uploaded successfully!')
                except Exception as e:
                    messages.error(request, f'Error uploading result: {str(e)}')

                return redirect('race_organiser_dashboard')

            #  handle CSV upload
            elif request.FILES.get('file'):
                file = request.FILES['file']
                try:
                    decoded_file = file.read().decode('utf-8')
                    reader = csv.reader(decoded_file.splitlines())
                    for row in reader:
                        bib_number = row[0]
                        result_time = row[1]
                        race_id = request.POST.get('race_id')

                        #  save each result from the CSV file
                        RaceResult.objects.create(race_id=race_id, bib_number=bib_number, result_time=result_time)

                    messages.success(request, 'CSV file uploaded successfully!')
                except Exception as e:
                    messages.error(request, f'Error uploading CSV: {str(e)}')

                return redirect('dashboard')

    return render(request, 'app/upload_results.html', {'races': races})

@login_required(login_url="login")
def upload_participants(request):
    """
    View for uploading participants either manually or via CSV.
    """

    if request.method == 'POST':
        race_id = request.POST.get('race_id')

        if not race_id:
            messages.error(request, "Please select a race.")
            return redirect('upload_participants')

        try:
            race = Race.objects.get(id=race_id)
        except Race.DoesNotExist:
            messages.error(request, "Invalid race selected.")
            return redirect('upload_participants')

        #  handle CSV upload
        if 'file' in request.FILES:
            csv_file = request.FILES['file']

            #  ensure the uploaded file is a CSV
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Invalid file format. Please upload a CSV file.")
                return redirect('upload_participants')

            try:
                #  read and decode the CSV file
                decoded_file = csv_file.read().decode('utf-8')
                reader = csv.DictReader(io.StringIO(decoded_file))

                #  required fields that must be present in the CSV
                required_fields = {'BibNumber', 'Firstname', 'Lastname', 'Gender', 'TeamName', 'AgeCategory', 'Age'}
                missing_fields = required_fields - set(reader.fieldnames)

                #  check for missing required columns
                if missing_fields:
                    messages.error(request, f"CSV file is missing required columns: {', '.join(missing_fields)}")
                    return redirect('upload_participants')

                participants = []
                for row in reader:
                    #  extract row data and ensure its valid
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
                        age = None  #  default to None if Age is not a valid number

                    #  skip rows with missing or invalid fields
                    if not all([bib_number, firstname, lastname, gender, team_name, age_category]) or age is None:
                        messages.warning(request, f"Skipping incomplete or invalid row: {row}")
                        continue

                    #  validate gender
                    if gender not in ['male', 'female', 'other']:
                        messages.warning(request, f"Invalid gender in row: {row}. Skipping.")
                        continue

                    #  add the valid participant to the list
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
                else:
                    messages.warning(request, "No valid participants were found in the CSV file.")

            except Exception as e:
                #  handle any errors during file reading and processing
                messages.error(request, f"Error processing CSV file: {str(e)}")
                return redirect('upload_participants')

            return redirect('upload_results')

    #  get all available races to populate the race selection dropdown
    races = Race.objects.all()
    return render(request, 'app/upload_participants.html', {'races': races})

def user_logout(request):
    """
    Logs out the user and redirects to the homepage.
    """

    #  logs out the user
    logout(request)
    messages.success(request, "You have successfully logged out.")

    #  redirect the user to the homepage
    return redirect('/')

@login_required
def register_for_race(request):
    """
    Defines the user registration for races page.
    """

    #  get the current date and time
    current_time = timezone.now()

    #  filter races to future races
    races = Race.objects.filter(date__gte=current_time.date()).filter(start_time__gte=current_time.time())

    if request.method == 'POST':
        race_id = request.POST.get('race_id')
        race = get_object_or_404(Race, id=race_id)

        #  ensure the user has a Participant instance
        if hasattr(request.user, 'participant'):
            participant = request.user.participant

            #  register the participant for the race
            participant.races.add(race)
            participant.save()
            return render(request, 'app/registration_success.html', {'race': race})
        else:
            #  handle the case where the user doesn't have a participant record yet
            return render(request, 'app/error.html', {'message': 'You must have a participant record to register for a race.'})

    return render(request, 'app/register_for_race.html', {'races': races})

@login_required
def manage_participants(request, race_id):
    """
    Loads a page where organisers can approve or deny participants.
    """

    race = get_object_or_404(Race, id=race_id)
    participants = race.participants.filter(status='pending')

    if request.method == 'POST':
        action = request.POST.get('action')
        participant_id = request.POST.get('participant_id')
        participant = get_object_or_404(Participant, id=participant_id)

        if action == 'approve':
            participant.status = 'approved'
        elif action == 'deny':
            participant.status = 'denied'

        participant.save()
        return redirect('manage_participants', race_id=race.id)

    return render(request, 'app/manage_participants.html', {'race': race, 'participants': participants})

@login_required(login_url="login")
def race_history(request):
    """
    Views the history of a runner.
    """

    #  check if the user has an associated participant
    if hasattr(request.user, 'participant'):
        participant = request.user.participant

    else:
        #  handle the case where the user does not have an associated participant
        participant = None

    #  render the page with race history
    return render(request, 'app/race_history.html', {'participant': participant})


def race_detail(request, race_id):
    race = Race.objects.get(id=race_id)

    #  get all participants for this race
    participants = Participant.objects.filter(race=race)

    #  apply filtering by gender
    gender = request.GET.get('gender')
    if gender:
        participants = participants.filter(gender=gender)

    #  apply filtering by age
    age = request.GET.get('age')
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

    #  apply sorting
    sort_by = request.GET.get('sort_by')
    sort_direction = request.GET.get('sort_direction', 'asc')

    #  handle sorting based on available fields
    if sort_by:
        if sort_by == 'name':
            if sort_direction == 'desc':
                participants = participants.order_by(F('name').desc())
            else:
                participants = participants.order_by('name')
        elif sort_by == 'age':  # Sort by 'age' field
            if sort_direction == 'desc':
                participants = participants.order_by(F('age').desc())
            else:
                participants = participants.order_by('age')

    #  count the number of participants
    participants_count = participants.count()

    return render(request, 'app/race_detail.html', {
        'race': race,
        'participants': participants,
        'participants_count': participants_count,
    })

@login_required
def race_organiser_dashboard(request):
    """
    Defines the view for a race organiser dashboard
    """

    # TODO - currently assume the user is a race organiser
    races = Race.objects.filter(organiser=request.user)
    return render(request, 'app/race_organiser_dashboard.html', {'races': races})

@login_required(login_url="login")
def upcoming_races(request):
    """
    View for displaying all upcoming races.
    Filters races that have a start date in the future.
    """

    #  get the current date and time
    current_time = timezone.now()

    #  get all races that are scheduled to take place after the current date and time
    upcoming = Race.objects.filter(date__gte=current_time.date()).order_by('date', 'start_time')

    return render(request, 'app/upcoming_races.html', {'upcoming_races': upcoming})

@login_required
def organiser_race_detail(request, race_id):
    """
    Defines the view for an organiser viewing a specific race
    """

    race = get_object_or_404(Race, id=race_id)

    if request.method == 'POST':
        participant_id = request.POST.get('participant_id')
        participant = race.participants.get(id=participant_id)
        status = request.POST.get('status')

        #  update the status of the participant
        participant.status = status
        participant.save()

    participants = race.participants.all()
    return render(request, 'app/organiser_race_detail.html', {'race': race, 'participants': participants})

@login_required(login_url="login")
def race_results(request, race_id):
    """
    Defines the view for the results of a race.
    """

    #  get the race using the provided race_id
    race = get_object_or_404(Race, id=race_id)

    #  retrieve the results related to that race
    results = RaceResult.objects.filter(race=race)

    #  render the race results page with race and results context
    return render(request, 'app/race_results.html', {'race': race, 'results': results})

@login_required
def settings_view(request):
    """
    Defines the view for the settings page
    """

    if request.method == "POST":
        user = request.user
        username = request.POST.get("username")
        email = request.POST.get("email")
        notify_race_updates = request.POST.get("notify_race_updates") == "on"

        #  update user details
        user.username = username
        user.email = email
        user.save()

        #  update profile settings
        user.profile.notify_race_updates = notify_race_updates
        user.profile.save()

        messages.success(request, "Settings updated successfully!")
        return redirect("settings")

    return render(request, "app/settings.html")

@login_required
def profile_view(request):
    """
    Defines the view for the profile page
    """

    #  try to get the Participant instance associated with the logged-in user
    participant = Participant.objects.filter(user=request.user).first()

    #  if the user has no Participant entry return a message
    if not participant:
        return render(request, "app/profile.html", {"error": "You are not registered as a race participant."})

    #  query races where the user is a participant
    races = Race.objects.filter(participants=participant)

    return render(request, "app/profile.html", {"participant": participant, "races": races})

@login_required
def organiser_race_detail(request, race_id):
    """
    Defines the organiser view for a single race
    """

    race = get_object_or_404(Race, id=race_id)

    return render(request, 'app/organiser_race_detail.html', {
        'race': race
    })
