#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Participant, RaceResult, Race

# ------------------------------------------------ Function Definitions ------------------------------------------------
def dashboard(request):
    """
    View for the dashboard with race selection.
    """

    #  get the race_id
    race_id = request.GET.get('race_id')

    try:
        #  ensure race_id is an integer
        race_id = int(race_id) if race_id else None

    except ValueError:
        race_id = None

    #  fetch all races for dropdown
    races = Race.objects.all()

    if not races:
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

    #  use the current_race.id for getting participants and results
    participants = Participant.objects.all()
    results = RaceResult.objects.all().order_by('total_time')

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

    if request.method == 'POST':

        #  retrieve form data
        race_name = request.POST.get('race_name')
        race_date = request.POST.get('race_date')
        start_time = request.POST.get('start_time')
        race_categories = request.POST.getlist('race_categories')

        try:  #  try to save the race configuration to the database
            Race.objects.create(
                name=race_name,
                date=race_date,
                start_time=start_time,
                categories=','.join(race_categories)
            )

            #  success message
            messages.success(request, 'Race configuration saved successfully!')
            return redirect('upload_participants')

        except Exception as e:

            #  error message
            messages.error(request, f"Error saving race configuration: {e}")

    return render(request, 'app/race_config.html')


def upload_results(request):

    if request.method == "POST" and request.FILES["file"]:
        file = request.FILES["file"]
        race_id = request.POST["race_id"]

        #  find the selected race
        try:
            race = Race.objects.get(id=race_id)
        except Race.DoesNotExist:
            messages.error(request, "Selected race does not exist.")
            return redirect('upload_results')

        #  validate the file is a CSV
        if not file.name.endswith('.csv'):
            messages.error(request, "The uploaded file must be a CSV.")
            return redirect('upload_results')

        #  process the uploaded CSV file
        try:
            csv_file = file.read().decode('utf-8').splitlines()
            csv_reader = csv.DictReader(csv_file)

            #  validate the csv format
            expected_headers = {"race_number", "total_time"}
            if set(csv_reader.fieldnames) != expected_headers:
                messages.error(request, "CSV file must contain 'race_number' and 'total_time' columns.")
                return redirect('upload_results')

            #  iterate through each row in the CSV
            for row in csv_reader:

                #  ensure each row contains the necessary fields and valid data
                race_number = row.get("race_number")
                total_time = row.get("total_time")

                if not race_number or not total_time:
                    messages.warning(request, f"Missing data for race number {race_number}. Skipping row.")
                    continue

                try:
                    #  validate total_time format HH:MM:SS
                    hours, minutes, seconds = map(int, total_time.split(':'))
                    if not (0 <= hours <= 23 and 0 <= minutes <= 59 and 0 <= seconds <= 59):
                        messages.warning(request, f"Invalid time format for race number {race_number}. Skipping row.")
                        continue
                except ValueError:
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
                else:
                    #  if the participant does not exist, log a warning
                    messages.warning(request, f"Participant with race number {race_number} not found for this race.")

            messages.success(request, "Results uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error uploading CSV file: {e}")

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
    Handles CSV format with Name, Race Number, Age, and Gender columns.
    """

    #  get all races
    races = Race.objects.all()

    if request.method == 'POST':
        #  get the selected race from the form
        race_id = request.POST.get('race_id')
        if not race_id:
            messages.error(request, "Please select a race.")
            return redirect('upload_participants')

        race = get_object_or_404(Race, id=race_id)

        #  get the uploaded file
        csv_file = request.FILES['file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, "The uploaded file must be a CSV.")
            return redirect('upload_participants')

        #  read and process the CSV file
        try:
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            csv_reader = csv.reader(decoded_file)
            header = next(csv_reader)

            #  check if the header has the expected columns
            if header != ['Name', 'Race Number', 'Age', 'Gender']:
                messages.error(request, "Invalid CSV format. The header must be: Name, Race Number, Age, Gender.")
                return redirect('upload_participants')

            #  create participants from the CSV
            for row in csv_reader:
                if len(row) != 4:  #  ensure there are exactly 4 columns (Name, Race Number, Age, Gender)
                    messages.warning(request, f"Skipping row: Invalid number of columns. Expected 4, got {len(row)}.")
                    continue  #  skip incomplete rows

                #  unpack row data
                name, race_number, age, gender = row

                #  validate data
                if not race_number.isdigit():
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

            messages.success(request, f"Participants have been successfully uploaded to {race.name}.")
        except Exception as e:
            messages.error(request, f"An error occurred while processing the CSV file: {e}")

        return redirect('upload_participants')

    return render(request, 'app/upload_participants.html', {
        'races': races,
    })