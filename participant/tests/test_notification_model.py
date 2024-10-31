from django.test import TestCase
from manager.models import Queue
from .models import Participant, Notification

class NotificationModelTests(TestCase):

    def setUp(self):
        """Set up a Queue, Participant, and Notification instance for testing."""
        self.queue = Queue.objects.create(name="Test Queue", estimated_wait_time_per_turn=5)
        self.participant = Participant.objects.create(
            name="Test Participant",
            email="test@example.com",
            queue=self.queue,
            position=1,
        )
        self.notification = Notification.objects.create(
            queue=self.queue,
            participant=self.participant,
            message="Your turn is coming up soon!",
        )

    def test_notification_creation(self):
        """Test that a notification instance is created correctly."""
        self.assertEqual(self.notification.queue, self.queue)
        self.assertEqual(self.notification.participant, self.participant)
        self.assertEqual(self.notification.message, "Your turn is coming up soon!")
        self.assertFalse(self.notification.is_read)
        self.assertIsNotNone(self.notification.created_at)

    def test_is_read_default_false(self):
        """Test that the is_read field is set to False by default."""
        self.assertFalse(self.notification.is_read)

    def test_mark_as_read(self):
        """Test setting the notification as read."""
        self.notification.is_read = True
        self.notification.save()
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_string_representation(self):
        """Test the string representation of the notification."""
        expected_str = f"Notification for {self.participant}: {self.notification.message}"
        self.assertEqual(str(self.notification), expected_str)
