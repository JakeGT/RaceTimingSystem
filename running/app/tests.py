#  running/app/tests.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Participant, RaceResult, RaceConfig
import io

# -------------------------------------------------- Test Definitions --------------------------------------------------
class RaceTimingSystemTests(TestCase):

    def setUp(self):
        """
        Setup test data.
        """

        #  create a test user
        self.user = User.objects.create_user(username='test-user', password='password123')

        #  create participants
        self.participant_1 = Participant.objects.create(name='John Doe', race_number='1', age=25, gender='Male')
        self.participant_2 = Participant.objects.create(name='Jane Smith', race_number='2', age=30, gender='Female')
        self.participant_3 = Participant.objects.create(name='Jane Doe', race_number='3', age=28, gender='Female')

        #  create a race configuration
        self.race_config = RaceConfig.objects.create(
            name="christmas",
            date="2024-12-25",
            start_time="12:00:00",
            categories="['5k', '10k']"
        )

    def test_dashboard_view(self):
        """
        Test the dashboard view loads correctly.
        """

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dashboard')

    def test_race_config_view_post(self):
        """
        Test saving the race configuration via POST.
        """

        data = {
            'race_name': 'New Year',
            'race_date': '2025-01-25',
            'start_time': '12:00:00',
            'race_categories': ['5k', '10k']
        }

        response = self.client.post(reverse('race_config'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RaceConfig.objects.count(), 2)
        self.assertRedirects(response, reverse('race_config'))

    def test_upload_results_view_post(self):
        """
        Test uploading results via POST with a CSV file.
        """

        #  define results data
        csv_file = io.StringIO("""
        race_number,total_time
        1,00:30:00
        2,00:28:30
        3,00:29:30
        """)
        csv_file.name = 'results.csv'
        response = self.client.post(reverse('upload_results'), {'file': SimpleUploadedFile(csv_file.name, csv_file.getvalue().encode())})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RaceResult.objects.count(), 0)
        self.assertRedirects(response, reverse('upload_results'))

    def test_upload_participants_view_post(self):
        """
        Test uploading participants via POST with a CSV file.
        """

        #  define participants data
        csv_file = io.StringIO("""
        name,race_number,age
        Alice,125,28
        Bob,126,35
        """)
        csv_file.name = 'participants.csv'

        response = self.client.post(reverse('upload_participants'), {'file': SimpleUploadedFile(csv_file.name, csv_file.getvalue().encode())})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Participant.objects.count(), 3)

    def test_real_time_results_view(self):
        """
        Test the real-time results view.
        """

        response = self.client.get(reverse('real_time_results'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'], [
        ])

    def test_race_config_invalid_post(self):
        """
        Test submitting race configuration with missing required fields.
        """

        data = {'race_name': 'Invalid Race', 'race_date': '', 'start_time': '', 'race_categories': []}
        response = self.client.post(reverse('race_config'), data)
        self.assertEqual(response.status_code, 200)
        #  TODO self.assertContains(response, "This field is required")

    def test_upload_results_invalid_file_format(self):
        """
        Test uploading an invalid file format (non-CSV).
        """

        invalid_file = SimpleUploadedFile('invalid.txt', b"invalid data")
        response = self.client.post(reverse('upload_results'), {'file': invalid_file})
        self.assertEqual(response.status_code, 302)
        #  TODO self.assertContains(response, "Error processing file")

    def test_upload_participants_invalid_data(self):
        """
        Test uploading a CSV with invalid data.
        """

        #  define invalid participants data
        invalid_csv = io.StringIO("""
        name,race_number,age
        Alice, , 
        Bob,abc,xyz
        """)
        invalid_csv.name = 'invalid_participants.csv'

        response = self.client.post(reverse('upload_participants'), {'file': SimpleUploadedFile(invalid_csv.name, invalid_csv.getvalue().encode())})
        self.assertEqual(response.status_code, 200)


