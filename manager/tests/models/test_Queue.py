import os
from datetime import timedelta
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from datetime import time
from django.utils import timezone
from manager.models import Queue, QueueLineLength
from participant.models import Participant
from django.core.exceptions import ValidationError


class QueueModelTests(TestCase):
    def setUp(self):
        """Set up common test data for all test cases."""
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.queue = Queue.objects.create(
            name="Test Queue",
            description="A test queue description",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            category="restaurant",
            latitude=40.7128,
            longitude=-74.0060,
        )
        self.participant = Participant.objects.create(queue=self.queue, state="waiting", created_by="guest")

    def test_queue_creation(self):
        """Test that a Queue object is created successfully."""
        self.assertEqual(self.queue.name, "Test Queue")
        self.assertEqual(self.queue.description, "A test queue description")
        self.assertEqual(self.queue.created_by, self.user)
        self.assertEqual(self.queue.status, "normal")
        self.assertEqual(self.queue.category, "restaurant")

    def test_generate_unique_queue_code(self):
        """Test that the unique queue code is generated correctly."""
        self.assertIsNotNone(self.queue.code)
        self.assertEqual(len(self.queue.code), 12)

    def test_get_top_featured_queues(self):
        """Test the retrieval of top featured queues."""
        Queue.objects.create(
            name="Another Queue",
            description="Another test queue",
            created_by=self.user,
            estimated_wait_time_per_turn=3,
            average_service_duration=8,
            category="restaurant",
            latitude=40.7138,
            longitude=-74.0050,
        )
        top_queues = Queue.get_top_featured_queues(category="restaurant")
        self.assertEqual(len(top_queues), 1)
        self.assertIn(self.queue, top_queues)

    def test_get_nearby_queues(self):
        """Test the retrieval of nearby queues based on distance."""
        nearby_queues = Queue.get_nearby_queues(user_lat=40.7128, user_lon=-74.0060, radius_km=5)
        self.assertIn(self.queue, nearby_queues)

    def test_formatted_distance(self):
        """Test the formatted distance property."""
        self.queue.distance_from_user = 1.5
        self.assertEqual(self.queue.formatted_distance, "1.5 km")

        self.queue.distance_from_user = 0.5  # in kilometers
        self.assertEqual(self.queue.formatted_distance, "500 m")

        self.queue.distance_from_user = None
        self.assertEqual(self.queue.formatted_distance, "Distance not available")

    def test_is_closed_default(self):
        """Test the default value for is_closed field."""
        self.assertFalse(self.queue.is_closed)

    def test_clean_method(self):
        """Test that the clean method invokes super().clean and performs custom validation."""
        valid_queue = Queue(
            name="Valid Queue",
            latitude=45.0,
            longitude=-93.0,
            category="restaurant",
        )
        # try:
            # This should pass as all validations are satisfied
        valid_queue.clean()
        # except ValidationError:
        #     self.fail("super().clean() raised ValidationError unexpectedly!")

        invalid_queue = Queue(
            name="Invalid Queue",
            latitude=91.0,  # Invalid latitude
            longitude=-74.0,
            category="restaurant",
        )
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

        invalid_queue.longitude = 181.0
        invalid_queue.latitude = 45.0
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

    def test_has_resources(self):
        """Test if the queue has resources."""
        self.assertTrue(self.queue.has_resources())

    def test_get_resources_by_status(self):
        """Test getting resources by status."""
        # Add mock resources if applicable
        self.assertEqual(self.queue.get_resources_by_status("available").count(), 0)

    def test_update_estimated_wait_time_per_turn(self):
        """Test updating estimated wait time per turn."""
        self.queue.update_estimated_wait_time_per_turn(15)
        self.assertEqual(self.queue.estimated_wait_time_per_turn, 15)

    def test_calculate_average_service_duration(self):
        """Test updating the average service duration based on recent serve times."""
        # Set up initial queue state
        self.queue.completed_participants_count = 2
        self.queue.average_service_duration = 10  # Current average is 10 minutes
        self.queue.save()

        # Call the method with a new serve time
        self.queue.calculate_average_service_duration(20)  # New serve time is 20 minutes

        # Expected new average:
        # Total time = (10 * 2) + 20 = 40
        # New average = 40 / 3 = 13.33, rounded to 14
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.average_service_duration, 14)
        self.assertEqual(self.queue.completed_participants_count, 3)

        self.queue.completed_participants_count = 0
        self.queue.average_service_duration = 0
        self.queue.save()
        self.queue.calculate_average_service_duration(15)
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.average_service_duration, 15)
        self.assertEqual(self.queue.completed_participants_count, 1)

    def test_get_average_service_duration(self):
        """Test calculating the average service duration for completed participants."""
        # Mock completed participants with service durations
        Participant.objects.create(
            queue=self.queue,
            state="completed",
            joined_at=timezone.now() - timedelta(minutes=60),
            service_started_at=timezone.now() - timedelta(minutes=50),
            service_completed_at=timezone.now() - timedelta(minutes=30),
        )  # Duration: 20 minutes

        Participant.objects.create(
            queue=self.queue,
            state="completed",
            joined_at=timezone.now() - timedelta(minutes=70),
            service_started_at=timezone.now() - timedelta(minutes=60),
            service_completed_at=timezone.now() - timedelta(minutes=40),
        )  # Duration: 20 minutes

        average_service_duration = self.queue.get_average_service_duration()

        # Expected average duration = (20 + 20) / 2 = 20 minutes
        self.assertEqual(average_service_duration, "20 mins")

    def test_get_participants(self):
        """Test retrieving all participants."""
        participants = self.queue.get_participants()
        self.assertIn(self.participant, participants)

    def test_update_participants_positions(self):
        """Test updating participant positions."""
        self.queue.update_participants_positions()
        self.participant.refresh_from_db()
        self.assertEqual(self.participant.position, 1)

    def test_get_number_of_participants(self):
        """Test counting total participants."""
        self.assertEqual(self.queue.get_number_of_participants(), 1)

    # def test_get_participants_today(self):
    #     """Test retrieving today's participants."""
    #     self.assertEqual(self.queue.get_participants_today(), 1)

    def test_get_logo_url_with_logo(self):
        """Test retrieving the logo URL when a logo is set."""
        # Mock an uploaded file for the logo
        mock_logo = SimpleUploadedFile("test_logo_UOBfYAx.png", b"file_content", content_type="image/png")
        self.queue.logo = mock_logo
        self.queue.save()

        # Call the method
        logo_url = self.queue.get_logo_url()

        # Assert the logo URL is returned
        self.assertIn("test_logo_UOBfYAx.png", logo_url)

    def tearDown(self):
        """Clean up test files."""
        if self.queue.logo and os.path.isfile(self.queue.logo.path):
            os.remove(self.queue.logo.path)

    def test_get_logo_url(self):
        """Test retrieving the logo URL or default logo."""
        default_logo = self.queue.get_logo_url()
        self.assertIn("restaurant_default_logo.png", default_logo)

    def test_edit(self):
        """Test editing queue details."""
        self.queue.edit(name="Updated Queue", description="Updated description", is_closed=True)
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.name, "Updated Queue")
        self.assertTrue(self.queue.is_closed)

    def test_edit_name_length_validation(self):
        """Test editing the queue with an invalid name length."""
        # Test for name too short
        with self.assertRaises(ValueError) as context:
            self.queue.edit(name='')  # Invalid name
        self.assertEqual(str(context.exception), "The name must be between 1 and 255 characters.")

        # Test for name too long
        with self.assertRaises(ValueError) as context:
            self.queue.edit(name="x" * 256)  # Name with 256 characters
        self.assertEqual(str(context.exception), "The name must be between 1 and 255 characters.")

    def test_edit_status(self):
        """Test editing the queue's status."""
        # Edit status to a valid choice
        self.queue.edit(status="busy")
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.status, "busy")

        # Test with an invalid status
        self.queue.edit(status="invalid_status")  # Should not change the status
        self.queue.refresh_from_db()
        self.assertNotEqual(self.queue.status, "invalid_status")
        self.assertEqual(self.queue.status, "busy")

    def test_get_available_resource(self):
        """Test retrieving an available resource."""
        resource = self.queue.get_available_resource()
        self.assertIsNone(resource)  # Assuming no resources are available

    def test_get_join_link(self):
        """Test retrieving the join link."""
        join_link = self.queue.get_join_link()
        self.assertIn(f"/welcome/{self.queue.code}/", join_link)

    def test_get_number_waiting_now(self):
        """Test counting participants currently waiting."""
        self.assertEqual(self.queue.get_number_waiting_now(), 1)

    def test_get_number_serving_now(self):
        """Test counting participants currently being served."""
        self.assertEqual(self.queue.get_number_serving_now(), 0)

    def test_get_number_served(self):
        """Test counting participants served."""
        self.assertEqual(self.queue.get_number_served(), 0)

    def test_get_number_dropoff(self):
        """Test counting dropout participants."""
        self.assertEqual(self.queue.get_number_dropoff(), 0)

    def test_get_guest_percentage(self):
        """Test percentage of participants joined by guests."""
        self.assertEqual(self.queue.get_guest_percentage(), 100.0)

    def test_get_number_created_by_staff(self):
        """Test counting the number of participants created by staff."""
        # Create participants with 'staff' as the creator
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")
        Participant.objects.create(queue=self.queue, state="waiting", created_by="guest")  # Not staff

        # Check the count of participants created by staff
        staff_count = self.queue.get_number_created_by_staff()
        self.assertEqual(staff_count, 2)  # Only 2 participants created by staff

    def test_get_number_unhandled(self):
        """Test calculating the number of unhandled participants."""
        # Clear existing participants
        self.queue.participant_set.all().delete()

        # Create specific participants for this test
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")
        Participant.objects.create(queue=self.queue, state="serving", created_by="guest")
        Participant.objects.create(queue=self.queue, state="completed", created_by="guest")  # Not unhandled

        # Check the number of unhandled participants
        unhandled_count = self.queue.get_number_unhandled()
        self.assertEqual(unhandled_count, 2)  # 1 'waiting' + 1 'serving'

    def test_get_unhandled_percentage(self):
        """Test calculating the percentage of unhandled participants."""
        # Clear existing participants
        self.queue.participant_set.all().delete()

        # Add participants with different states
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")
        Participant.objects.create(queue=self.queue, state="serving", created_by="guest")
        Participant.objects.create(queue=self.queue, state="completed", created_by="guest")

        # Total: 3, Waiting + Serving: 2, Percentage: (2/3) * 100 = 66.67
        unhandled_percentage = self.queue.get_unhandled_percentage()
        self.assertEqual(unhandled_percentage, 66.67)

        # Test with no participants
        self.queue.participant_set.all().delete()
        unhandled_percentage = self.queue.get_unhandled_percentage()
        self.assertEqual(unhandled_percentage, 0)

    def test_get_cancelled_percentage(self):
        """Test calculating the percentage of cancelled participants."""
        # Clear existing participants
        self.queue.participant_set.all().delete()

        # Add participants with different states
        Participant.objects.create(queue=self.queue, state="cancelled", created_by="guest")
        Participant.objects.create(queue=self.queue, state="removed", created_by="guest")
        Participant.objects.create(queue=self.queue, state="completed", created_by="guest")

        # Cancelled: 1, Total Dropoff: 2, Percentage: (1/2) * 100 = 50.0
        cancelled_percentage = self.queue.get_cancelled_percentage()
        self.assertEqual(cancelled_percentage, 50.0)

    def test_get_removed_percentage(self):
        """Test calculating the percentage of removed participants."""
        # Clear existing participants
        self.queue.participant_set.all().delete()

        # Add participants with different states
        Participant.objects.create(queue=self.queue, state="cancelled", created_by="guest")
        Participant.objects.create(queue=self.queue, state="removed", created_by="guest")
        Participant.objects.create(queue=self.queue, state="completed", created_by="guest")

        # Removed: 1, Total Dropoff: 2, Percentage: (1/2) * 100 = 50.0
        removed_percentage = self.queue.get_removed_percentage()
        self.assertEqual(removed_percentage, 50.0)

    # def test_get_average_waiting_time(self):
    #     """Test calculating the average waiting time for participants."""
    #     now = timezone.localtime()
    #
    #     # Create participants with explicitly correct timestamps
    #     p1 = Participant.objects.create(
    #         queue=self.queue,
    #         state="completed",
    #         joined_at=now - timedelta(minutes=50),  # Joined 50 minutes ago
    #         service_started_at=now - timedelta(minutes=30) # Started service 30 minutes ago
    #     )
    #     p2 = Participant.objects.create(
    #         queue=self.queue,
    #         state="completed",
    #         joined_at=now - timedelta(minutes=70),  # Joined 70 minutes ago
    #         service_started_at=now - timedelta(minutes=40)  # Started service 40 minutes ago
    #     )
    #
    #     # debug
    #     wait_time1 = int((p1.service_started_at - p1.joined_at).total_seconds() / 60)
    #     wait_time2 = int((p2.service_started_at - p2.joined_at).total_seconds() / 60)
    #     print(f"Wait time 1: {wait_time1}")
    #     print(f"Wait time 2: {wait_time2}")
    #
    #     # Call the method
    #     average_waiting_time = self.queue.get_average_waiting_time()
    #
    #     # Expected average = (20 + 30) / 2 = 25 minutes
    #     self.assertEqual(average_waiting_time, "25 mins")

    def test_get_staff_percentage(self):
        """Test calculating the percentage of participants created by staff."""
        # Clear existing participants
        self.queue.participant_set.all().delete()

        # Create specific participants for this test
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")
        Participant.objects.create(queue=self.queue, state="waiting", created_by="guest")
        Participant.objects.create(queue=self.queue, state="waiting", created_by="staff")

        # Check the percentage of participants created by staff
        staff_percentage = self.queue.get_staff_percentage()
        # Staff: 2, Total: 3, Percentage = (2/3) * 100 = 66.67
        self.assertEqual(staff_percentage, 66.67)

    def test_get_served_percentage(self):
        """Test percentage of participants served."""
        self.assertEqual(self.queue.get_served_percentage(), 0)

    def test_get_dropoff_percentage(self):
        """Test percentage of participants who dropped off."""
        self.assertEqual(self.queue.get_dropoff_percentage(), 0)

    def test_get_max_waiting_time(self):
        """Test maximum waiting time for participants."""
        max_wait_time = self.queue.get_max_waiting_time()
        self.assertEqual(max_wait_time, "0 mins")  # Assuming no wait times recorded

    def test_get_max_service_duration(self):
        """Test calculating the maximum service duration for completed participants."""
        # Mock completed participants with service durations
        Participant.objects.create(
            queue=self.queue,
            state="completed",
            joined_at=timezone.now() - timedelta(minutes=60),
            service_started_at=timezone.now() - timedelta(minutes=50),
            service_completed_at=timezone.now() - timedelta(minutes=30),
        )  # Duration: 20 minutes

        Participant.objects.create(
            queue=self.queue,
            state="completed",
            joined_at=timezone.now() - timedelta(minutes=70),
            service_started_at=timezone.now() - timedelta(minutes=60),
            service_completed_at=timezone.now() - timedelta(minutes=35),
        )  # Duration: 25 minutes

        max_service_duration = self.queue.get_max_service_duration()

        # Expected maximum duration = 25 minutes
        self.assertEqual(max_service_duration, "25 mins")

    def test_record_line_length(self):
        """Test recording line length."""
        self.queue.record_line_length()
        self.assertEqual(QueueLineLength.objects.filter(queue=self.queue).count(), 1)

    def test_get_peak_line_length(self):
        """Test retrieving the peak line length."""
        self.queue.record_line_length()
        peak_line_length = self.queue.get_peak_line_length()
        self.assertEqual(peak_line_length, 1)

    def test_get_avg_line_length(self):
        """Test calculating the average line length."""
        self.queue.record_line_length()
        avg_line_length = self.queue.get_avg_line_length()
        self.assertEqual(avg_line_length, 1)

    def test_get_avg_line_length_no_records(self):
        """Test get_avg_line_length when there are no QueueLineLength records."""
        # Ensure no QueueLineLength records exist for the queue
        QueueLineLength.objects.filter(queue=self.queue).delete()
        avg_line_length = self.queue.get_avg_line_length()
        self.assertEqual(avg_line_length, 0)

    def test_string_representation(self):
        """Test string representation of the queue."""
        self.assertEqual(str(self.queue), "Test Queue")



class QueueModelEdgeCasesTests(TestCase):
    def setUp(self):
        """Set up common test data."""
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.queue = Queue.objects.create(
            name="Test Queue",
            description="A test queue description",
            created_by=self.user,
            latitude=40.7128,
            longitude=-74.0060,
            category="restaurant",
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
        )

    def test_get_top_featured_queues_no_participants(self):
        """Ensure queues with no participants are not included."""
        top_queues = Queue.get_top_featured_queues(category="restaurant")
        self.assertEqual(len(top_queues), 0)

    def test_get_top_featured_queues_zero_capacity(self):
        """Ensure queues with zero capacity handle properly."""
        self.queue.resource_set.create(capacity=0)
        top_queues = Queue.get_top_featured_queues(category="restaurant")
        self.assertEqual(len(top_queues), 0)

    def test_get_top_featured_queues_with_ratio(self):
        """Test the calculation of the queue's ratio (participants / max capacity * 100)."""
        resource = self.queue.resource_set.create(capacity=10, status="available")

        Participant.objects.create(queue=self.queue, state="waiting", created_by="guest")
        Participant.objects.create(queue=self.queue, state="waiting", created_by="guest")

        top_queues = Queue.get_top_featured_queues(category="restaurant")

        self.assertIn(self.queue, top_queues)

        num_participants = self.queue.get_number_waiting_now()
        max_capacity = resource.capacity
        expected_ratio = (num_participants / max_capacity) * 100

        self.assertEqual(len(top_queues), 1)
        self.assertAlmostEqual(
            top_queues[0].get_number_waiting_now() / max_capacity * 100,
            expected_ratio,
            places=2,
        )

    def test_get_nearby_queues_exact_radius(self):
        """Test a queue at exactly the edge of the radius."""
        nearby_queue = Queue.objects.create(
            name="Edge Queue",
            latitude=40.7128,  # Adjust for precision
            longitude=-74.0110,
            category="restaurant",
        )
        nearby_queues = Queue.get_nearby_queues(user_lat=40.7128, user_lon=-74.0060, radius_km=0.5)
        self.assertIn(nearby_queue, nearby_queues)


    def test_get_nearby_queues_large_radius(self):
        """Test retrieving queues with a large radius."""
        Queue.objects.create(
            name="Far Queue",
            latitude=41.0000,
            longitude=-74.0000,
            category="restaurant",
        )
        nearby_queues = Queue.get_nearby_queues(user_lat=40.7128, user_lon=-74.0060, radius_km=50)
        self.assertEqual(len(nearby_queues), 2)

    def test_lat_lon_validation(self):
        """Test latitude and longitude ranges."""
        invalid_queue = Queue(
            name="Invalid Queue",
            latitude=91.0,
            longitude=-74.0060,
            category="restaurant",
        )
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

        invalid_queue = Queue(
            name="Invalid Queue",
            latitude=-91.0,
            longitude=-74.0060,
            category="restaurant",
        )
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

        invalid_queue = Queue(
            name="Invalid Queue",
            latitude=40.7128,  # Valid latitude
            longitude=181.0,  # Invalid longitude
            category="restaurant",
        )
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

    def test_save_does_not_regenerate_code_on_update(self):
        """Ensure `save` does not regenerate `code` on update."""
        original_code = self.queue.code
        self.queue.name = "Updated Queue"
        self.queue.save()
        self.assertEqual(self.queue.code, original_code)

    def test_default_values(self):
        """Test default field values."""
        self.assertFalse(self.queue.is_closed)
        self.assertIsNone(self.queue.distance_from_user)
        self.assertIsNotNone(self.queue.created_at)


