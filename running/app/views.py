#  running/app/views.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
import csv
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib import messages
from .models import Participant, RaceResult, RaceConfig

# ------------------------------------------------ Function Definitions ------------------------------------------------
def dashboard(request):
    """
    View for the dashboard.
    """

    participants = Participant.objects.all()
    results = RaceResult.objects.all().order_by('total_time')
    return render(request, 'app/dashboard.html', {'participants': participants, 'results': results})

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
            RaceConfig.objects.create(
                name=race_name,
                date=race_date,
                start_time=start_time,
                categories=','.join(race_categories)
            )

            #  success message
            messages.success(request, 'Race configuration saved successfully!')
            return redirect('race_config')

        except Exception as e:

            #  error message
            messages.error(request, f"Error saving race configuration: {e}")

    return render(request, 'app/race_config.html')

def real_time_results(request):
    """
    View for the real time results.
    """

    #  fetch real-time race data
    results = RaceResult.objects.all()
    return JsonResponse({'results': list(results.values())})


def upload_results(request):
    """
    View for the manual upload of results.
    """

    if request.method == 'POST' and request.FILES['file']:

        #  obtain the csv file storing the results
        file = request.FILES['file']

        try:  #  try to process results data
            decoded_file = file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)

            #  process each row in the results CSV file
            for row in reader:
                race_number = row.get('race_number')
                total_time = row.get('total_time')

                #  find the participant by race number
                try:
                    participant = Participant.objects.get(race_number=race_number)
                except Participant.DoesNotExist:
                    messages.error(request, f"Participant with race number {race_number} does not exist.")
                    continue

                #  create or update the race result
                RaceResult.objects.update_or_create(
                    participant=participant,
                    defaults={'total_time': total_time}
                )

            #  success message
            messages.success(request, 'Race results uploaded successfully!')
            return redirect('upload_results')

        except Exception as e:

            #  error message
            messages.error(request, f"Error processing file: {e}")

    return render(request, 'app/upload_results.html')

def upload_participants(request):
    """
    View for uploading participants.
    """

    if request.method == 'POST' and request.FILES['file']:
        uploaded_file = request.FILES['file']

        try:  #  try to read and decode the participant CSV file
            file_content = uploaded_file.read().decode('utf-8').splitlines()
            csv_reader = csv.reader(file_content)

            #  skip the header row if present
            next(csv_reader)

            #  process each row in the CSV, containing name, number and age
            for row in csv_reader:
                name = row[0]
                race_number = row[1]
                age = row[2]

                #  TODO - handle other formats/data

                #  create or update participant in the database
                Participant.objects.get_or_create(
                    name=name,
                    race_number=race_number,
                    age=age
                )

            #  success message
            messages.success(request, 'Participants uploaded successfully!')
            return redirect('dashboard')
        except Exception as e:

            #  error message
            messages.error(request, f"Error processing file: {e}")

    return render(request, 'app/upload_participants.html')
