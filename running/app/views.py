#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Participant, RaceResult, Race
from .utils.logger import setup_logging

logger = setup_logging()

# ------------------------------------------------ Function Definitions ------------------------------------------------
def landing_page(request):
    """
    View for the landing page of the Race Timing System.
    """

    logger.info("Accessing the landing page view")

    return render(request, 'app/landing.html', {})


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.forms import PasswordResetForm
from django.core.mail import send_mail
from django.conf import settings


def user_register(request):
    """
    Handles user registration.
    """

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return redirect("register")

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

        if user:
            login(request, user)
            messages.success(request, "Login successful!")
            return redirect("dashboard")
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
                # Send password reset email
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

    # Get the race_id, gender, and age filters
    race_id = request.GET.get('race_id')
    gender = request.GET.get('gender')
    age = request.GET.get('age')

    try:
        # Ensure race_id is an integer
        race_id = int(race_id) if race_id else None
        logger.debug(f"Parsed race_id: {race_id}")
    except ValueError:
        logger.warning(f"Invalid race_id provided: {race_id}")
        race_id = None

    # Fetch all races for the dropdown
    races = Race.objects.all()

    if not races:
        logger.info("No races found in the database")
        # If no races exist, show a message to the user
        return render(request, 'app/dashboard.html', {
            'races': races,
            'message': 'No races available. Please add a race first.'
        })

    if race_id:
        # Try to get the current race based on the given race_id
        current_race = get_object_or_404(Race, id=race_id)
    else:
        # Default to the first race if no race_id is provided
        current_race = races.first()

    # Use the current_race.id for getting participants and results
    participants = Participant.objects.filter(race=current_race)
    results = RaceResult.objects.filter(participant__race=current_race).order_by('total_time')

    # Apply gender filter
    if gender:
        participants = participants.filter(gender=gender)
        results = results.filter(participant__gender=gender)

    # Apply age filter
    if age:
        if age == '18':
            participants = participants.filter(age__gte=18, age__lte=25)
            results = results.filter(participant__age__gte=18, participant__age__lte=25)
        elif age == '26':
            participants = participants.filter(age__gte=26, age__lte=35)
            results = results.filter(participant__age__gte=26, participant__age__lte=35)
        elif age == '36':
            participants = participants.filter(age__gte=36, age__lte=45)
            results = results.filter(participant__age__gte=36, participant__age__lte=45)
        elif age == '46':
            participants = participants.filter(age__gte=46, age__lte=60)
            results = results.filter(participant__age__gte=46, participant__age__lte=60)
        elif age == '60':
            participants = participants.filter(age__gte=60)
            results = results.filter(participant__age__gte=60)

    logger.debug(f"Rendering dashboard with race_id: {current_race.id if current_race else None}")

    return render(request, 'app/dashboard.html', {
        'current_race': current_race,
        'races': races,
        'participants': participants,
        'results': results,
    })


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


def upload_participants(request):
    """
    View for uploading participants to a selected race via CSV.
    """

    logger.info("Accessing participants upload view")

    #  get all races
    races = Race.objects.all()

    if request.method == 'POST':
        #  get the selected race from the form
        race_id = request.POST.get('race_id')
        if not race_id:
            logger.error("Race ID not provided in the form")
            messages.error(request, "Please select a race.")
            return redirect('upload_participants')

        race = get_object_or_404(Race, id=race_id)

        #  get the uploaded file
        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            logger.warning(f"Invalid file format: {csv_file.name}")
            messages.error(request, "The uploaded file must be a CSV.")
            return redirect('upload_participants')

        #  read and process the CSV file
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            csv_reader = csv.reader(decoded_file)
            header = next(csv_reader)

            #  check if the header has the expected columns
            if header != ['Name', 'Race Number', 'Age', 'Gender']:
                logger.error(f"Invalid CSV header: {header}")
                messages.error(request, "Invalid CSV format. The header must be: Name, Race Number, Age, Gender.")
                return redirect('upload_participants')

            #  create participants from the CSV
            for row in csv_reader:
                if len(row) != 4:  #  ensure there are exactly 4 columns (Name, Race Number, Age, Gender)
                    logger.warning(f"Skipping invalid row: {row}")
                    messages.warning(request, f"Skipping row: Invalid number of columns. Expected 4, got {len(row)}.")
                    continue  #  skip incomplete rows

                #  unpack row data
                name, race_number, age, gender = row

                #  validate data
                if not race_number.isdigit():
                    logger.warning(f"Invalid data in row: {row}")
                    messages.warning(request, f"Skipping row: Invalid race number '{race_number}' (must be an integer).")
                    continue

                if not age.isdigit() or int(age) <= 0:
                    messages.warning(request, f"Skipping row: Invalid age '{age}' (must be a positive integer).")
                    continue

                #  create participant object
                Participant.objects.create(
                    name=name,
                    race_number=race_number,
                    age=int(age),
                    gender=gender.lower(),
                    race_id=race.id
                )
                logger.info(f"Added participant: {name} (Race Number: {race_number})")

            messages.success(request, f"Participants have been successfully uploaded to {race.name}.")
        except Exception as e:
            logger.error(f"Error processing participants CSV: {e}")
            messages.error(request, f"An error occurred while processing the CSV file: {e}")

        return redirect('dashboard')

    return render(request, 'app/upload_participants.html', {
        'races': races,
    })
