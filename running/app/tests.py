#  running/app/tests.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Participant, Race
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
        self.participant_1 = Participant.objects.create(name='John Doe', race_number='1', age=25, gender='Male', race_id=1)
        self.participant_2 = Participant.objects.create(name='Jane Smith', race_number='2', age=30, gender='Female', race_id=1)
        self.participant_3 = Participant.objects.create(name='Jane Doe', race_number='3', age=28, gender='Female', race_id=1)

        #  create a race configuration
        self.race_config = Race.objects.create(
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

    def test_dashboard_view_with_gender_filter(self):
        """
        Test the dashboard view with gender filter (Male).
        """

        response = self.client.get(reverse('dashboard'), {'gender': 'male'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')
        #  TODO implement functional filters
        # self.assertNotContains(response, 'Jane Smith')
        # self.assertNotContains(response, 'Jane Doe')

    def test_dashboard_view_with_age_filter(self):
        """
        Test the dashboard view with age filter (18-25).
        """
        response = self.client.get(reverse('dashboard'), {'age': '18'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John Doe')

        #  TODO implement functional filters
        # self.assertNotContains(response, 'Jane Smith')

    def test_dashboard_view_with_gender_and_age_filter(self):
        """
        Test the dashboard view with both gender and age filters.
        """

        response = self.client.get(reverse('dashboard'), {'gender': 'female', 'age': '28'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jane Smith')

        #  TODO implement functional filters
        # self.assertContains(response, 'Jane Doe')
        # self.assertNotContains(response, 'John Doe')

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
        self.assertEqual(Race.objects.count(), 2)

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
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Participant.objects.count(), 3)

    def test_race_config_invalid_post(self):
        """
        Test submitting race configuration with missing required fields.
        """

        data = {'race_name': 'Invalid Race', 'race_date': '', 'start_time': '', 'race_categories': []}
        response = self.client.post(reverse('race_config'), data)
        self.assertEqual(response.status_code, 200)

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
        self.assertEqual(response.status_code, 302)
