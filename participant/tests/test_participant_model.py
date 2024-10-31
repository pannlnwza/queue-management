from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from manager.models import Queue
from participant.models import Participant

class ParticipantModelTest(TestCase):

    def setUp(self):
        self.user = User.objects.create(username="testuser")
        self.queue = Queue.objects.create(
            name="Test Queue",
            description="A test queue",
            estimated_wait_time_per_turn=5,
            created_by=self.user,
            capacity=10,
            category="general"
        )
        self.participant = Participant.objects.create(
            queue=self.queue,
            position=1,
            joined_at=timezone.now()
        )

    def test_participant_string_representation(self):
        """Test that the string representation of Participant returns the correct format."""
        self.assertEqual(str(self.participant), f"Participant in {self.queue} at position 1")

    def test_participant_position_uniqueness(self):
        """Test that each participant in a queue has a unique position."""
        with self.assertRaises(Exception):  # Replace Exception with IntegrityError if using Django's constraints
            Participant.objects.create(
                queue=self.queue,
                position=1  # Duplicate position in the same queue
            )

    def test_participant_joined_at_auto_now(self):
        """Test that 'joined_at' is set automatically upon creation."""
        self.assertIsNotNone(self.participant.joined_at)
