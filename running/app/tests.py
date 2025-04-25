import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Participant, Race, RaceCategory


class RaceTimingSystemTests(TestCase):
    def setUp(self):
        """
        Setup test data.
        """
        # Create a test user
        self.user = User.objects.create_user(
            username="test-user", password="password123"
        )

        # Create a race configuration
        self.race_config = Race.objects.create(
            name="Christmas Race",
            date="2024-12-25",
            start_time="12:00:00",
            organiser=self.user,
            is_completed=False,
        )

        # Create race categories
        self.category_5k = RaceCategory.objects.create(name="5k")
        self.category_10k = RaceCategory.objects.create(name="10k")

        # Create participants
        self.participant_1 = Participant.objects.create(
            name="John Doe",
            race_number="1",
            age=25,
            gender="male",
            race=self.race_config,
        )
        self.participant_2 = Participant.objects.create(
            name="Jane Smith",
            race_number="2",
            age=30,
            gender="female",
            race=self.race_config,
        )
        self.participant_3 = Participant.objects.create(
            name="Jane Doe",
            race_number="3",
            age=28,
            gender="female",
            race=self.race_config,
        )

    def test_dashboard_view(self):
        """
        Test the dashboard view loads correctly.
        """
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    # def test_dashboard_view_with_gender_filter(self):
    #     """
    #     Test the dashboard view with gender filter (Male).
    #     """
    #
    #     response = self.client.get(reverse('dashboard'), {'gender': 'male'})
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, 'John Doe')
    #
    # def test_dashboard_view_with_age_filter(self):
    #     """
    #     Test the dashboard view with age filter (18-25).
    #     """
    #     response = self.client.get(reverse('dashboard'), {'age': '18'})
    #     self.assertEqual(response.status_code, 200)
    #     self.assertContains(response, 'John Doe')

    def test_race_config_view_post(self):
        """
        Test saving the race configuration via POST.
        """
        data = {
            "name": "New Year Race",
            "date": "2025-01-25",
            "start_time": "12:00:00",
            "organiser": self.user.id,
            "is_completed": False,
        }
        response = self.client.post(reverse("race_config"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Race.objects.count(), 1)

    def test_upload_participants_view_post(self):
        """
        Test uploading participants via POST with a CSV file.
        """
        csv_file = io.StringIO(
            """
        name,race_number,age,gender
        Alice,125,28,female
        Bob,126,35,male
        """
        )
        csv_file.name = "participants.csv"
        response = self.client.post(
            reverse("upload_participants"),
            {"file": SimpleUploadedFile(csv_file.name, csv_file.getvalue().encode())},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Participant.objects.count(), 3)

    def test_race_config_invalid_post(self):
        """
        Test submitting race configuration with missing required fields.
        """
        data = {"name": "", "date": "", "start_time": ""}
        response = self.client.post(reverse("race_config"), data)
        self.assertEqual(response.status_code, 302)

    def test_upload_participants_invalid_data(self):
        """
        Test uploading a CSV with invalid data.
        """
        invalid_csv = io.StringIO(
            """
        name,race_number,age,gender
        Alice, , ,
        Bob,abc,xyz,male
        """
        )
        invalid_csv.name = "invalid_participants.csv"
        response = self.client.post(
            reverse("upload_participants"),
            {
                "file": SimpleUploadedFile(
                    invalid_csv.name, invalid_csv.getvalue().encode()
                )
            },
        )
        self.assertEqual(response.status_code, 302)
