from django.test import TestCase
from django.contrib.auth.models import User
from datetime import time
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
        self.queue.distance_from_user = 1.5  # in kilometers
        self.assertEqual(self.queue.formatted_distance, "1.5 km")
        self.queue.distance_from_user = 0.5  # in kilometers
        self.assertEqual(self.queue.formatted_distance, "500 m")

    def test_is_closed_default(self):
        """Test the default value for is_closed field."""
        self.assertFalse(self.queue.is_closed)

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
        """Test calculating average service duration."""
        self.queue.calculate_average_service_duration(20)
        self.assertEqual(self.queue.average_service_duration, 20)

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

    def test_get_participants_today(self):
        """Test retrieving today's participants."""
        self.assertEqual(self.queue.get_participants_today(), 0)

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
            latitude=91.0,  # Invalid latitude
            longitude=-74.0060,
            category="restaurant",
        )
        with self.assertRaises(ValidationError):
            invalid_queue.clean()

        invalid_queue = Queue(
            name="Invalid Queue",
            latitude=-91.0,  # Invalid latitude
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


