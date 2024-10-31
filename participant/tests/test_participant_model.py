from django.test import TestCase
from django.utils import timezone
from manager.models import Queue
from .models import Participant

class ParticipantModelTests(TestCase):

    def setUp(self):
        """Set up a Queue and a Participant instance for testing."""
        self.queue = Queue.objects.create(name="Test Queue", estimated_wait_time_per_turn=5)
        self.participant = Participant.objects.create(
            name="Test Participant",
            email="test@example.com",
            queue=self.queue,
            position=1,
        )

    def test_participant_creation(self):
        """Test that a participant instance is created correctly."""
        self.assertEqual(self.participant.name, "Test Participant")
        self.assertEqual(self.participant.email, "test@example.com")
        self.assertEqual(self.participant.queue, self.queue)
        self.assertEqual(self.participant.position, 1)
        self.assertEqual(self.participant.state, 'waiting')
        self.assertIsNotNone(self.participant.code)

    def test_unique_code_generation(self):
        """Test that each participant has a unique code."""
        codes = {self.participant.code}
        for _ in range(10):
            new_participant = Participant.objects.create(
                name="Another Participant",
                queue=self.queue,
                position=1,
            )
            self.assertNotIn(new_participant.code, codes)
            codes.add(new_participant.code)

    def test_position_update(self):
        """Test updating a participant's position."""
        self.participant.update_position(3)
        self.assertEqual(self.participant.position, 3)

    def test_position_update_invalid(self):
        """Test that updating the position with a non-positive value raises an error."""
        with self.assertRaises(ValueError):
            self.participant.update_position(0)

    def test_calculate_estimated_wait_time(self):
        """Test the calculation of estimated wait time based on position."""
        self.participant.position = 3
        self.assertEqual(self.participant.calculate_estimated_wait_time(), 10)

    def test_start_service(self):
        """Test starting service for a participant."""
        self.participant.start_service()
        self.assertEqual(self.participant.state, 'serving')
        self.assertIsNotNone(self.participant.service_started_at)

    def test_complete_service(self):
        """Test completing service for a participant."""
        self.participant.start_service()
        self.participant.complete_service()
        self.assertEqual(self.participant.state, 'completed')
        self.assertIsNotNone(self.participant.service_completed_at)

    def test_get_wait_time_in_waiting_state(self):
        """Test wait time calculation when participant is in 'waiting' state."""
        self.participant.joined_at = timezone.localtime() - timezone.timedelta(minutes=20)
        self.assertEqual(self.participant.get_wait_time(), 20)

    def test_get_wait_time_in_serving_state(self):
        """Test wait time calculation when participant is in 'serving' state."""
        self.participant.start_service()
        self.participant.joined_at = timezone.localtime() - timezone.timedelta(minutes=15)
        self.assertEqual(self.participant.get_wait_time(), 15)

    def test_get_service_duration_while_serving(self):
        """Test service duration while participant is in 'serving' state."""
        self.participant.start_service()
        self.participant.service_started_at = timezone.localtime() - timezone.timedelta(minutes=10)
        self.assertEqual(self.participant.get_service_duration(), 10)

    def test_get_service_duration_completed(self):
        """Test service duration after service is completed."""
        self.participant.start_service()
        self.participant.service_started_at = timezone.localtime() - timezone.timedelta(minutes=10)
        self.participant.complete_service()
        self.participant.service_completed_at = timezone.localtime()
        self.assertEqual(self.participant.get_service_duration(), 10)

    def test_string_representation(self):
        """Test string representation of the participant."""
        self.assertEqual(str(self.participant), f"{self.participant.name} - {self.participant.state}")
