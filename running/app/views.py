#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Participant, RaceResult, Race
from .utils.logger import setup_logging
from .forms import RegisterRaceForm
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.conf import settings
import re


# -------------------------------------------------- Setup Logging -----------------------------------------------------
logger = setup_logging()

# ------------------------------------------------ Function Definitions ------------------------------------------------
def landing_page(request):
    """
    View for the landing page of the Race Timing System.
    """

    logger.info("Accessing the landing page view")

    return render(request, 'app/landing.html', {})

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

def user_logout(request):
    """
    Logs out the user.
    """

    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")

def password_reset_request(request):
    """
    Handles password reset request.
    """

    if request.method == "POST":
        email = request.POST.get("email")
        form = PasswordResetForm(request.POST)

        if form.is_valid():
            user = User.objects.filter(email=email).first()
            if user:
                #  send password reset email
                send_mail(
                    "Password Reset Request",
                    "Click the link below to reset your password.",
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                messages.success(request, "Password reset email sent! Check your inbox.")
                return redirect("login")
            else:
                messages.error(request, "No user found with this email.")

    return render(request, "app/password_reset.html")

def dashboard(request):
    """
    View for the dashboard with race selection.
    """

    logger.info("Accessing the dashboard view")

    #  get the race_id and other filters
    race_id = request.GET.get('race_id')
    gender = request.GET.get('gender')
    age = request.GET.get('age')

    try:
        #  ensure race_id is an integer
        race_id = int(race_id) if race_id else None
        logger.debug(f"Parsed race_id: {race_id}")
    except ValueError:
        logger.warning(f"Invalid race_id provided: {race_id}")
        race_id = None

    #  fetch all races for dropdown
    races = Race.objects.all()

    if not races:
        logger.info("No races found in the database")
        #  if no races exist, show a message to the user
        return render(request, 'app/dashboard.html', {
            'races': races,
            'message': 'No races available. Please add a race first.'
        })

    if race_id:
        #  try to get the current race based on the given race_id
        current_race = get_object_or_404(Race, id=race_id)
    else:
        #  default to the first race if no race_id is provided
        current_race = races.first()

    #  filter participants based on gender and age if provided
    participants = Participant.objects.filter(race=current_race)

    if gender:
        participants = participants.filter(gender=gender)

    if age:
        participants = participants.filter(age=age)

    #  fetch the race results related to the current race and participants
    results = RaceResult.objects.filter(participant__in=participants).order_by('total_time')
    logger.debug(f"Rendering dashboard with race_id: {current_race.id if current_race else None}")

    return render(request, 'app/dashboard.html', {
        'current_race': current_race,
        'races': races,
        'participants': participants,
        'results': results,
    })

@login_required(login_url="login")
def race_config(request):
    """
    View for race configuration.
    """

    logger.info("Accessing race configuration view")
    if request.method == 'POST':

        #  retrieve form data
        race_name = request.POST.get('race_name')
        race_date = request.POST.get('race_date')
        start_time = request.POST.get('start_time')
        race_categories = request.POST.getlist('race_categories')

        logger.debug(f"Received race configuration: {race_name}, {race_date}, {start_time}, {race_categories}")
        try:  #  try to save the race configuration to the database
            Race.objects.create(
                name=race_name,
                date=race_date,
                start_time=start_time,
                categories=','.join(race_categories)
            )
            logger.info(f"Race configuration saved: {race_name}")

            #  success message
            messages.success(request, 'Race configuration saved successfully!')
            return redirect('upload_participants')

        except Exception as e:
            logger.error(f"Error saving race configuration: {e}")

            #  error message
            messages.error(request, f"Error saving race configuration: {e}")

    return render(request, 'app/race_config.html')

@login_required(login_url="login")
def upload_results(request):
    """
    View for result upload.
    """

    logger.info("Accessing results upload view")

    if request.method == "POST" and request.FILES["file"]:
        file = request.FILES["file"]
        race_id = request.POST["race_id"]

        logger.debug(f"File uploaded: {file.name}, race_id: {race_id}")
        #  find the selected race
        try:
            race = Race.objects.get(id=race_id)
        except Race.DoesNotExist:
            logger.warning(f"Race with id {race_id} does not exist")
            messages.error(request, "Selected race does not exist.")
            return redirect('upload_results')

        #  validate the file is a CSV
        if not file.name.endswith('.csv'):
            logger.warning(f"Invalid file format: {file.name}")
            messages.error(request, "The uploaded file must be a CSV.")
            return redirect('upload_results')

        #  process the uploaded CSV file
        try:
            csv_file = file.read().decode('utf-8').splitlines()
            csv_reader = csv.DictReader(csv_file)

            #  validate the csv format
            expected_headers = {"race_number", "total_time"}
            if set(csv_reader.fieldnames) != expected_headers:
                logger.error(f"Invalid CSV headers: {csv_reader.fieldnames}")
                messages.error(request, "CSV file must contain 'race_number' and 'total_time' columns.")
                return redirect('upload_results')

            #  iterate through each row in the CSV
            for row in csv_reader:

                #  ensure each row contains the necessary fields and valid data
                race_number = row.get("race_number")
                total_time = row.get("total_time")
                logger.debug(f"Processing row: {row}")

                if not race_number or not total_time:
                    logger.warning(f"Missing data for row: {row}")
                    messages.warning(request, f"Missing data for race number {race_number}. Skipping row.")
                    continue

                try:
                    #  validate total_time format HH:MM:SS
                    hours, minutes, seconds = map(int, total_time.split(':'))
                    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                        messages.warning(request, f"Invalid time format for race number {race_number}. Skipping row.")
                        continue
                except ValueError:
                    logger.warning(f"Invalid time format: {total_time}")
                    messages.warning(request, f"Invalid time format for race number {race_number}. Skipping row.")
                    continue

                #  check if the race_number exists
                participant = race.participants.filter(race_number=race_number).first()

                if participant:
                    #  if the participant exists, update the result
                    RaceResult.objects.update_or_create(
                        participant=participant,
                        defaults={'total_time': total_time}
                    )
                    logger.info(f"Updated result for participant {race_number}")
                else:
                    #  if the participant does not exist, log a warning
                    logger.warning(f"Participant not found: {race_number}")
                    messages.warning(request, f"Participant with race number {race_number} not found for this race.")

            logger.info("Results uploaded successfully")
            messages.success(request, "Results uploaded successfully.")
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}")
            messages.error(request, f"Error uploading CSV file: {e}")

        return redirect('dashboard')

    #  get all available races
    races = Race.objects.all()
    selected_race = races.first() if races.exists() else None

    return render(request, 'app/upload_results.html', {
        'races': races,
        'selected_race': selected_race
    })

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

        #  try to get the race, if not found, return an error
        race = Race.objects.get(id=race_id)

        #  handle manual entry
        if 'bib_number' in request.POST:
            bib_number = request.POST['bib_number']
            firstname = request.POST['firstname']
            lastname = request.POST['lastname']
            gender = request.POST['gender']
            club_name = request.POST.get('club_name', '')
            team_name = request.POST['team_name']
            age_category = request.POST['age_category']

            #  create a new participant and associate with the selected race
            Participant.objects.create(
                race=race,
                race_number=bib_number,
                name=f"{firstname} {lastname}",
                gender=gender,
                club_name=club_name,
                team_name=team_name,
                age_category=age_category
            )
            messages.success(request, "Participant added successfully.")
            return redirect('upload_participants')

        #  handle CSV upload
        if 'file' in request.FILES:
            csv_file = request.FILES['file']
            messages.success(request, "CSV file uploaded successfully.")
            return redirect('upload_participants')

    #  if GET request, just display the form
    races = Race.objects.all()
    return render(request, 'app/upload_participants.html', {
        'races': races,
    })

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

@login_required(login_url="login")
def race_detail(request, race_id):
    """
    View for displaying the details of a specific race.
    """

    race = get_object_or_404(Race, id=race_id)
    return render(request, 'app/race_detail.html', {'race': race})

@login_required
def race_organiser_dashboard(request):

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
    upcoming_races = Race.objects.filter(date__gte=current_time.date()).order_by('date', 'start_time')

    return render(request, 'app/upcoming_races.html', {'upcoming_races': upcoming_races})

@login_required
def organiser_race_detail(request, race_id):

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

    #  get the race using the provided race_id
    race = get_object_or_404(Race, id=race_id)

    #  retrieve the results related to that race
    results = RaceResult.objects.filter(race=race)

    #  render the race results page with race and results context
    return render(request, 'race_results.html', {'race': race, 'results': results})